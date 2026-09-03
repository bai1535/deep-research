"""Agent — LLM-powered agent with transparent tool-use loop.

Every agent has:
- a private mutable_messages list (conversation history)
- a set of BuildTool instances
- an optional Blackboard reference for cross-agent data sharing
- a Compressor to keep context bounded

The run() method is the main entry point — it runs the full
observe → think → act → observe loop until the model produces
a final text response.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import litellm

from deep_research.core.blackboard import Blackboard
from deep_research.core.compressor import Compressor
from deep_research.core.file_cache import FileCache
from deep_research.core.policy_audit import log_policy_event
from deep_research.core.tool import BuildTool
from deep_research.trace import trace_logger

logger = logging.getLogger("deep_research.core.agent")

# Tools that are always free and do not consume Firecrawl quota.
FREE_SEARCH_TOOL_NAMES = {"baidu_search", "bing_search"}

# Tool-calling loop guard — prevent infinite loops
MAX_TOOL_ROUNDS = 20        # absolute safety valve, never removed
# Smart termination (per agent task, all programmable via constructor):
STALL_SIGNATURE_LIMIT = 3   # N consecutive identical (tool, query) rounds → stalled, stop
TOOL_ERROR_LIMIT = 2        # N consecutive rounds where every tool result is ERROR/empty → stop


def _deep_sizeof(obj: Any, _seen: set | None = None) -> int:
    """Recursive sizeof — measures dict, list, str, int and their nesting."""
    if _seen is None:
        _seen = set()
    obj_id = id(obj)
    if obj_id in _seen:
        return 0
    _seen.add(obj_id)
    size = sys.getsizeof(obj)
    if isinstance(obj, dict):
        for k, v in obj.items():
            size += _deep_sizeof(k, _seen) + _deep_sizeof(v, _seen)
    elif isinstance(obj, (list, tuple, set)):
        for item in obj:
            size += _deep_sizeof(item, _seen)
    elif isinstance(obj, str):
        # sys.getsizeof already counts the full string buffer
        pass
    return size


@dataclass
class LLMConfig:
    """Minimal LLM endpoint descriptor."""

    model: str = "openai/deepseek-chat"
    base_url: str = "https://api.deepseek.com/v1"
    api_key: str = ""
    max_tokens: int = 16384
    timeout: float = 300.0


class Agent:
    """LLM agent with transparent tool-use loop."""

    def __init__(
        self,
        *,
        name: str,
        system_prompt: str,
        tools: list[BuildTool] | None = None,
        llm_config: LLMConfig | None = None,
        blackboard: Blackboard | None = None,
        file_cache: FileCache | None = None,
        trace_id: str = "",
        event_bus=None,  # optional EventBus for streaming progress
        max_tool_rounds: int | None = None,   # programmable termination: round cap
        stall_limit: int | None = None,       # consecutive identical tool calls → stop
        tool_error_limit: int | None = None,  # consecutive all-error rounds → stop
        response_format: dict[str, Any] | None = None,  # {"type":"json_object"} for structured output
        reserved_tools: list[BuildTool] | None = None,  # unlocked when free search is insufficient
        policy: Any | None = None,  # AgentPolicy metadata (enforced in later phases)
    ) -> None:
        self.name = name
        self.policy = policy
        # If no bus was passed explicitly, discover it via the blackboard
        # (pipeline writes "event_bus" there for every run).
        if event_bus is None and blackboard is not None:
            event_bus = blackboard.read("event_bus")
        self.event_bus = event_bus
        # Termination conditions — defaults are the module constants,
        # overridable per agent (e.g. a short-lived agent gets a small cap)
        self.max_tool_rounds = max_tool_rounds or MAX_TOOL_ROUNDS
        self.stall_limit = stall_limit or STALL_SIGNATURE_LIMIT
        self.tool_error_limit = tool_error_limit or TOOL_ERROR_LIMIT
        self.system_prompt = system_prompt
        self.tools: dict[str, BuildTool] = {t.name: t for t in (tools or [])}
        self.reserved_tools: dict[str, BuildTool] = {t.name: t for t in (reserved_tools or [])}
        self._quality_unlocked = False
        self._event_store = None
        self._last_event_id: str | None = None
        self.llm_config = llm_config or LLMConfig()
        self.blackboard = blackboard
        self.file_cache = file_cache
        self.trace_id = trace_id
        self.response_format = response_format

        self._log = trace_logger(logger, trace_id, prefix=name) if trace_id else logger
        self.messages: list[dict[str, Any]] = []
        self.compressor = Compressor(
            api_base=self.llm_config.base_url,
            api_key=self.llm_config.api_key,
        )
        # Token / cost tracking (accumulated across all LLM calls in this run)
        self.token_usage: dict[str, int] = {"prompt": 0, "completion": 0, "total": 0}
        self.cost: float = 0.0
        self.llm_calls: int = 0
        self._tool_call_counts: dict[str, int] = {}
        self._total_tool_calls: int = 0
        # Memory tracking
        self._peak_messages_kb: int = 0
        self._peak_serialized_kb: int = 0

    # ── public API ───────────────────────────────────────────────

    async def run(self, task: str) -> str:
        """Execute one task and return the final text response.

        The method:
        1. Appends the task as a user message
        2. Loops: call LLM → execute tools → repeat
        3. Returns the model's final content when tool_calls stop
        """
        self.messages = []  # fresh conversation per task
        self.token_usage = {"prompt": 0, "completion": 0, "total": 0}
        self.cost = 0.0
        self.llm_calls = 0
        self._peak_messages_kb = 0
        self._peak_serialized_kb = 0
        self._add_message("user", task)
        self._measure_messages()

        if self.event_bus is not None:
            self.event_bus.emit({"type": "agent_start", "agent": self.name})

        # ── smart termination state ────────────────────────────────
        stall_streak = 0            # consecutive rounds with identical tool calls
        error_streak = 0            # consecutive rounds where every tool failed
        last_signature: tuple | None = None
        termination = ""            # why the loop ended ("stalled-N", "tools-failed-N", "max-rounds")

        for _round in range(self.max_tool_rounds):
            # Compress if conversation is too long
            if len(self.messages) > self.compressor.max_messages:
                self.messages = await self.compressor.compress(self.messages)
                self._measure_messages()  # track after compression

            response = await self._call_llm()
            if response is None:
                self._log.warning("LLM returned None on round %d", _round)
                termination = "llm-error"
                self._log_usage(termination)
                return ""

            content = response.get("content")
            tool_calls = response.get("tool_calls")
            self._record_event("llm_call", {
                "input": {"messages": len(self.messages)},
                "output": {
                    "content": content or "",
                    "tool_calls": [tc.get("function", {}).get("name", "") for tc in tool_calls or []],
                },
            })

            if tool_calls:
                # Record the assistant message that requested tools
                self.messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})

                # Execute all tool calls in parallel
                async def _run_one(tc: dict) -> dict:
                    func = tc.get("function", {})
                    tool_name = func.get("name", "")
                    try:
                        args = json.loads(func.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        args = {}
                    # Emit a "searching/fetching" event — the useful live signal
                    if self.event_bus is not None:
                        query = str(args.get("query") or args.get("url") or "")[:80]
                        self.event_bus.emit({
                            "type": "tool_call",
                            "agent": self.name,
                            "tool": tool_name,
                            "query": query,
                        })
                    tool = self.tools.get(tool_name)
                    _start = time.monotonic()
                    if tool:
                        allowed, reason = self._tool_allowed(tool_name)
                        if not allowed:
                            result_str = f"ERROR: tool '{tool_name}' blocked by policy ({reason})"
                            self._log.warning("Tool %s blocked for agent %s: %s", tool_name, self.name, reason)
                            log_policy_event(
                                agent=self.name,
                                action="tool_call",
                                target=tool_name,
                                reason=reason,
                                allowed=False,
                            )
                        else:
                            result_str = await tool.run(args)
                            self._tool_call_counts[tool_name] = self._tool_call_counts.get(tool_name, 0) + 1
                            self._total_tool_calls += 1
                    else:
                        result_str = f"ERROR: unknown tool '{tool_name}'"
                    self._log_call(tool_name, args, result_str, (time.monotonic() - _start) * 1000.0)
                    if self.event_bus is not None:
                        self.event_bus.emit({
                            "type": "tool_done",
                            "agent": self.name,
                            "tool": tool_name,
                            "chars": len(result_str),
                            # first 200 chars of the tool's formatted result —
                            # the frontend shows it so users SEE what the
                            # search/fetch actually returned
                            "preview": result_str[:200],
                        })
                    return {
                        "tool_call_id": tc.get("id", str(uuid.uuid4())),
                        "tool": tool_name,
                        "content": result_str,
                    }

                results = await asyncio.gather(*[_run_one(tc) for tc in tool_calls])
                for r in results:
                    self.messages.append({"role": "tool", "tool_call_id": r["tool_call_id"], "content": r["content"]})
                self._maybe_unlock_quality_tools(results)
                self._measure_messages()  # track after tool results

                # ── smart termination: no-progress detection ──────────
                # ③ Every tool errored → the tool is broken (quota,
                #    ban, unknown name); keep burning rounds is pointless.
                all_failed = all(
                    not r["content"] or str(r["content"]).startswith("ERROR")
                    for r in results
                )
                if all_failed:
                    # Healthy tools still untried → prompt a switch instead
                    # of terminating.  The model may keep picking dead tools
                    # (quota/ban) while working ones remain; only accumulate
                    # the error streak once no healthy tool is left untried.
                    healthy = [n for n, t in self.tools.items() if not t.is_disabled()]
                    untried = [n for n in healthy if n not in {r.get("tool") for r in results}]
                    if untried:
                        self._add_message(
                            "user",
                            "你刚才调用的工具全部返回错误。仍然可用但未尝试的工具："
                            + "、".join(untried)
                            + "。请换用它们重试，或直接基于已有信息给出最终答案。",
                        )
                        error_streak = 0
                        continue
                    error_streak += 1
                else:
                    error_streak = 0

                if error_streak >= self.tool_error_limit:
                    termination = f"tools-failed-{error_streak}"
                    self._log.warning(
                        "tools failed %d rounds in a row — early stop (round %d)",
                        error_streak, _round,
                    )
                    self._log_usage(termination)
                    # Don't return an empty string — the caller's parser
                    # would report "Empty input" and lose every diagnostic.
                    # Return the last round's tool errors so the retry path
                    # sees WHAT failed instead of nothing.
                    return self._tool_error_summary(results)

                # ② The model keeps calling the SAME tools with the SAME
                #    queries — it is going in circles, not converging.
                signature = self._tools_signature(tool_calls)
                stall_streak = stall_streak + 1 if signature == last_signature else 0
                last_signature = signature
                if stall_streak >= self.stall_limit:
                    termination = f"stalled-{stall_streak}"
                    self._log.warning(
                        "identical tool calls %d rounds in a row — early stop (round %d)",
                        stall_streak, _round,
                    )
                    self._log_usage(termination)
                    return content or ""
                continue  # loop back to LLM with all tool results at once

            # No tool calls → final response (termination ①: complete answer)
            if content:
                self.messages.append({"role": "assistant", "content": content})
            # Log token / cost summary for this agent run
            self._log_usage(termination)
            return content or ""

        termination = "max-rounds"
        self._log.warning("exceeded max tool rounds (%d)", self.max_tool_rounds)
        self._log_usage(termination)
        return ""

    # ── internals ─────────────────────────────────────────────────

    def _add_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})

    def _measure_messages(self) -> None:
        """Track peak memory of self.messages (Python objects + serialised)."""
        # Recursive sizeof — measures the whole dict tree
        obj_kb = _deep_sizeof(self.messages) // 1024
        # Serialised to JSON — approximates what's sent to the LLM as context
        try:
            ser_kb = len(json.dumps(self.messages, ensure_ascii=False, default=str)) // 1024
        except Exception:
            ser_kb = 0
        if obj_kb > self._peak_messages_kb:
            self._peak_messages_kb = obj_kb
        if ser_kb > self._peak_serialized_kb:
            self._peak_serialized_kb = ser_kb

    @staticmethod
    def _tools_signature(tool_calls: list[dict]) -> tuple:
        """Stable signature of a tool round: sorted (tool, query) pairs.

        Two rounds with the same signature mean the model is going in
        circles (stall detection).  Query = the "query"/"url" argument,
        truncated to 80 chars so identical-but-noisy args still match.
        """
        sigs: list[tuple[str, str]] = []
        for tc in tool_calls:
            fn = tc.get("function", {})
            name = str(fn.get("name", ""))
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except (json.JSONDecodeError, TypeError):
                args = {}
            if not isinstance(args, dict):
                args = {}
            query = str(args.get("query") or args.get("url") or "")[:80]
            sigs.append((name, query))
        return tuple(sorted(sigs))

    def _maybe_unlock_quality_tools(self, results: list[dict]) -> None:
        """Unlock reserved quality tools when free search engines underperform.

        Trigger: at least one free search tool (baidu/bing) was called this
        round, and every called free search result is an error, empty, or
        returned fewer than 2 URLs.  This lets a researcher fall back to
        Firecrawl/Wikipedia/Wikidata in the next round without waiting for
        the whole Reflector quality gate.
        """
        if self._quality_unlocked or not self.reserved_tools:
            return
        called_free = [r for r in results if r.get("tool") in FREE_SEARCH_TOOL_NAMES]
        if not called_free:
            return
        verdicts = []
        for r in called_free:
            content = str(r.get("content") or "")
            urls = re.findall(r"(?m)^\s*URL:\s*\S+", content)
            bad = (
                content.startswith("ERROR")
                or "No results found." in content
                or len(urls) < 2
            )
            verdicts.append(bad)
        if not all(verdicts):
            return

        added: list[str] = []
        for name, tool in self.reserved_tools.items():
            if name not in self.tools:
                self.tools[name] = tool
                added.append(name)
        if added:
            self._quality_unlocked = True
            self._add_message(
                "user",
                "免费搜索引擎（baidu/bing）本轮结果不足，现已解锁："
                + "、".join(added)
                + "。请优先使用这些工具继续搜索。",
            )
            self._log.info("Unlocked quality tools for %s: %s", self.name, ", ".join(added))

    @staticmethod
    def _tool_error_summary(results: list[dict[str, Any]]) -> str:
        """Summarise a round where every tool errored.

        Used by the tools-failed early-stop path: returning this instead
        of an empty string means the caller's parser logs the actual
        failures ("ERROR: ...") rather than a useless "Empty input".
        """
        lines = ["【工具调用全部失败】"]
        for r in results:
            content = str(r.get("content", "")).strip()
            if content:
                lines.append(f"- {content[:200]}")
        return "\n".join(lines)

    def _tool_allowed(self, tool_name: str) -> tuple[bool, str]:
        """Check AgentPolicy before executing a tool call."""
        policy = self.policy
        if policy is None:
            return True, ""
        tp = policy.tools
        if tool_name in (tp.denied_tools or []):
            return False, "denied by AgentPolicy"
        if tp.allowed_tools is not None and tool_name not in tp.allowed_tools:
            return False, "not in AgentPolicy.allowed_tools"
        max_calls = (tp.per_tool_max_calls or {}).get(tool_name)
        if max_calls is not None and self._tool_call_counts.get(tool_name, 0) >= max_calls:
            return False, "per-tool budget exceeded"
        if policy.budget.max_tool_calls is not None and self._total_tool_calls >= policy.budget.max_tool_calls:
            return False, "tool-call budget exceeded"
        return True, ""

    def _record_event(self, action: str, payload: dict) -> None:
        """Best-effort event sourcing record for this agent action."""
        try:
            from deep_research.eventsourcing import EventStore, record_event
            if self._event_store is None:
                self._event_store = EventStore()
            run_id = self.blackboard.read("run_id", "") if self.blackboard else ""
            if not run_id:
                return
            ev = record_event(
                run_id=run_id,
                action=action,
                agent=self.name,
                parent_event_id=self._last_event_id,
                payload=payload,
                store=self._event_store,
            )
            self._last_event_id = ev.event_id
            if "output" in payload:
                from deep_research.replay import OutputCache
                OutputCache().put(run_id, f"{action}:{ev.input_hash}", payload["output"])
        except Exception:
            pass

    def _log_call(self, tool_name: str, args: dict, result: str, duration_ms: float) -> None:
        """Record one tool invocation to logs/search_calls.jsonl.

        Captures the fields needed to answer "which engine, how many calls,
        how many succeeded, what latency, what errors" without reading the
        transcript.  Never raises — logging is best-effort.
        """
        try:
            from deep_research.core.call_log import log_call
            run_id = self.blackboard.read("run_id", "") if self.blackboard else ""
            query = str(args.get("query") or args.get("url") or "")[:200]
            result = str(result)
            # Search tools format results as "URL: <url>" lines.  Keep the
            # returned URLs so offline evaluation can compute Hit@5 / nDCG@5.
            result_urls = re.findall(r"(?m)^\s*URL:\s*(\S+)", result)[:10]
            log_call({
                "run_id": run_id,
                "trace_id": self.trace_id,
                "agent": self.name,
                "tool": tool_name,
                "query": query,
                "status": "error" if result.startswith("ERROR") else "ok",
                "duration_ms": round(duration_ms, 1),
                "error": result[:200] if result.startswith("ERROR") else "",
                "result_urls": result_urls,
            })
            self._record_event(tool_name, {"input": args, "output": result})
        except Exception:
            pass

    def _calc_cost(self) -> float:
        """Calculate USD cost from accumulated token usage.

        Uses DeepSeek pricing: $0.27/M input, $1.10/M output.
        Falls back to litellm.completion_cost if available.
        """
        p = self.token_usage["prompt"] / 1_000_000
        c = self.token_usage["completion"] / 1_000_000
        self.cost = round(p * 0.27 + c * 1.10, 6)
        return self.cost

    def _log_usage(self, termination: str = "") -> None:
        """Log token usage, cost, and memory for this agent run.

        *termination* records why the loop ended ("stalled-3",
        "tools-failed-2", "max-rounds", "llm-error", or "" for a normal
        complete-answer stop) — surfaced in the agent_done stream event.
        """
        cost = self._calc_cost()
        self._log.info(
            "%d calls | %d prompt + %d completion = %d tokens | $%.4f | msg: %d objs / %d KB | ser: %d KB%s",
            self.llm_calls,
            self.token_usage["prompt"], self.token_usage["completion"],
            self.token_usage["total"], cost,
            len(self.messages), self._peak_messages_kb, self._peak_serialized_kb,
            f" | termination={termination}" if termination else "",
        )
        if self.blackboard is not None:
            self.blackboard.write(f"usage:{self.name}", {
                "calls": self.llm_calls,
                "prompt": self.token_usage["prompt"],
                "completion": self.token_usage["completion"],
                "total": self.token_usage["total"],
                "cost": cost,
                "peak_messages_kb": self._peak_messages_kb,
                "peak_serialized_kb": self._peak_serialized_kb,
                "termination": termination,
            })
        if self.event_bus is not None:
            self.event_bus.emit({
                "type": "agent_done",
                "agent": self.name,
                "calls": self.llm_calls,
                "tokens": self.token_usage["total"],
                "cost": round(cost, 4),
                "termination": termination,
            })

    async def _call_llm(self) -> dict[str, Any] | None:
        """Call the LLM and return a simplified response dict.

        Returns:
            {"content": str|None, "tool_calls": list|None}
            or None on failure.
        """
        # Enforce ResourceBudget before making another LLM call.
        if self.policy is not None and self.policy.budget is not None:
            budget = self.policy.budget
            reason = ""
            if budget.max_llm_calls is not None and self.llm_calls >= budget.max_llm_calls:
                reason = f"max_llm_calls={budget.max_llm_calls} exceeded"
            elif budget.max_tokens is not None and self.token_usage["total"] >= budget.max_tokens:
                reason = f"max_tokens={budget.max_tokens} exceeded"
            elif budget.max_cost_usd is not None and self.cost >= budget.max_cost_usd:
                reason = f"max_cost_usd={budget.max_cost_usd} exceeded"
            if reason:
                self._log.warning("LLM call blocked for %s by ResourceBudget: %s", self.name, reason)
                log_policy_event(
                    agent=self.name,
                    action="llm_call",
                    target="llm",
                    reason=reason,
                    allowed=False,
                )
                return None

        # Build the full message list
        full_messages: list[dict] = [
            {"role": "system", "content": self.system_prompt},
        ]

        # Optionally inject blackboard context
        if self.blackboard:
            ctx = self._blackboard_context()
            if ctx:
                full_messages.append({"role": "system", "content": ctx})

        full_messages.extend(self.messages)

        # Reinforce format instruction at the end of context.
        # In long conversations the system prompt drifts out of the
        # model's effective attention window.  A trailing reminder
        # ensures the model sees the format constraint right before
        # generating its response.
        format_hint = "只输出任务要求的格式。"
        if self.response_format:
            format_hint = "只输出任务要求的 JSON（json）对象，不要代码块、不要其他文字。"
        full_messages.append({
            "role": "user",
            "content": (
                "【提醒】直接输出最终结果。不要描述计划，不要用 'Excellent'/'Now I have'/"
                f"'Let me' 开头。{format_hint}"
            ),
        })

        tool_schemas = None
        if self.tools:
            # Filter out process-disabled tools so the LLM stops selecting
            # dead backends (e.g. quota-exhausted Tavily) instead of wasting
            # a round on each "unavailable" error.  Empty → pass None, not [],
            # so litellm treats it as "no tools" rather than an empty schema.
            enabled = [t for t in self.tools.values() if not t.is_disabled()]
            tool_schemas = [t.to_openai_schema() for t in enabled] if enabled else None

        try:
            kwargs: dict[str, Any] = {
                "model": self.llm_config.model,
                "messages": full_messages,
                "tools": tool_schemas,
                "api_base": self.llm_config.base_url,
                "api_key": self.llm_config.api_key,
                "max_tokens": self.llm_config.max_tokens,
                "timeout": self.llm_config.timeout,
            }
            if self.response_format is not None:
                kwargs["response_format"] = self.response_format
            resp = await litellm.acompletion(**kwargs)
        except Exception as exc:
            self._log.error("LLM call failed — %s", exc)
            return None

        # ── track token usage ──────────────────────────────────
        self.llm_calls += 1
        if hasattr(resp, "usage") and resp.usage:
            self.token_usage["prompt"] += resp.usage.prompt_tokens or 0
            self.token_usage["completion"] += resp.usage.completion_tokens or 0
            self.token_usage["total"] += resp.usage.total_tokens or 0

        choice = resp.choices[0]
        msg = choice.message

        tool_calls = None
        if msg.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ]

        return {
            "content": msg.content,
            "tool_calls": tool_calls,
        }

    def _blackboard_context(self) -> str:
        """Build a brief context injection from the blackboard."""
        if self.blackboard is None:
            return ""
        keys = self.blackboard.keys()
        if not keys:
            return ""
        lines = ["[Shared context from other agents:]"]
        for k in sorted(keys):
            v = self.blackboard.read(k)
            v_str = str(v)
            if len(v_str) > 500:
                v_str = v_str[:500] + "..."
            lines.append(f"  {k}: {v_str}")
        return "\n".join(lines)
