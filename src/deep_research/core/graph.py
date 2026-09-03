"""Lightweight data-driven state graph — LangGraph-inspired, zero dependencies.

Instead of hard-coding orchestration as sequential `await` calls, the
workflow is declared as a graph:

    graph = StateGraph()
    graph.add_node("research", research_node)
    graph.add_node("verify", verify_node)
    graph.add_edge("research", "verify")
    graph.add_conditional_edges("research", should_skip_verify)
    await graph.run(initial_state)

Each node is an async callable `(state: dict) -> dict` that returns a
partial state update (merged into state).  The graph is pure data —
it can be serialised, visualised, and modified at runtime.

Execution model
---------------
- A queue is seeded with the entry node.
- Each popped node executes ONCE per visit, then its outgoing edges are
  routed (possibly pushing the node back onto the queue — cycles are
  allowed, e.g. an "augment" node that loops until its condition is met).
- Loop termination is the condition function's responsibility (e.g. a
  counter in state that stops returning the loop target).  A `max_steps`
  safety valve aborts a runaway loop.
- Resume: initial_state may carry `{"__visited__": [...]}`.  Nodes listed
  there were completed in a prior session (crash) — they are not re-run,
  but their outgoing edges are still routed so execution continues from
  where the last checkpoint was written.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import deque
from typing import Any, Awaitable, Callable

logger = logging.getLogger("deep_research.graph")

# A node: async (state) -> partial_state_update
NodeFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
# A condition: (state) -> target_node_name | None  (None = don't traverse)
ConditionFn = Callable[[dict[str, Any]], str | None]
# Checkpoint callback: (node_name, serialisable_state) -> None
CheckpointFn = Callable[[str, dict[str, Any]], Awaitable[None]]

# Safety valve: cap total node executions to abort a runaway loop
DEFAULT_MAX_STEPS = 200


class StateGraph:
    """Directed graph of nodes connected by (possibly conditional) edges.

    Execution semantics:
    - A NON-reentrant node executes AT MOST ONCE per graph run, no matter
      how many edges reach it (converging paths, self-loops).  Use it for
      "do this phase once" work (research, verify, synthesize).
      TRAP: if two paths push the same non-reentrant node onto the queue,
      the second push is silently dropped by the executed-guard.  Converging
      paths must not rely on parallel re-entry — route through a reentrant
      node (or a dedicated fan-in node) instead.
    - A reentrant node may execute MULTIPLE times, driven by a conditional
      edge whose condition reads a counter from state (e.g. augment loops
      until its budget is exhausted).  Reentrant nodes are also NOT
      skipped on resume — they re-run and rely on the counter to
      terminate.
    """

    def __init__(
        self,
        *,
        name: str = "graph",
        checkpoint: CheckpointFn | None = None,
        max_steps: int = DEFAULT_MAX_STEPS,
    ) -> None:
        self.name = name
        self._nodes: dict[str, NodeFn] = {}
        self._edges: dict[str, list[tuple[str, ConditionFn | None]]] = {}
        self._entry: str | None = None
        self._checkpoint = checkpoint  # async (node_name, state) -> None
        self._max_steps = max_steps
        self._reentrant: set[str] = set()

    # ── construction ────────────────────────────────────────────────

    def add_node(self, name: str, fn: NodeFn, *, reentrant: bool = False) -> None:
        """Register a node.  *fn* is async (state) -> partial_state_update.

        *reentrant* marks a node that may run MULTIPLE times via a
        conditional-edge loop (e.g. an "augment" node whose repeat count
        lives in state).  Reentrant nodes are NOT skipped on resume —
        they re-run and rely on their counter to terminate.
        """
        self._nodes[name] = fn
        if reentrant:
            self._reentrant.add(name)
        if self._entry is None:
            self._entry = name

    def add_edge(self, source: str, target: str) -> None:
        """Unconditional edge: source always routes to target."""
        self._edges.setdefault(source, []).append((target, None))

    def add_conditional_edges(
        self,
        source: str,
        condition: ConditionFn,
        default: str | None = None,
    ) -> None:
        """Conditional edge: condition(state) decides target.

        If condition returns None, routes to *default* (if given).
        """
        existing = self._edges.setdefault(source, [])
        # #9: behaviour must not depend on registration order.  If an
        # unconditional edge was added first, a conditional edge would
        # silently suppress it at runtime — refuse loudly instead.
        if any(cond is None for _, cond in existing):
            raise ValueError(
                f"[graph:{self.name}] add_conditional_edges('{source}') after "
                "add_edge() would silently suppress the unconditional edge. "
                "Register conditional edges before unconditional ones, or "
                "remove the conflicting add_edge call."
            )
        existing.append((default or "", condition))

    # ── introspection (the graph is data) ───────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialise the graph structure."""
        return {
            "name": self.name,
            "entry": self._entry,
            "nodes": {name: fn.__name__ for name, fn in self._nodes.items()},
            "edges": {
                src: [(tgt, cond.__name__ if cond else None) for tgt, cond in edges]
                for src, edges in self._edges.items()
            },
        }

    def render_mermaid(self) -> str:
        """Render the graph as a Mermaid diagram (paste into Mermaid live editor)."""
        lines = ["graph TD"]
        for name in self._nodes:
            lines.append(f"    {name}[\"{name}\"]")
        for src, edges in self._edges.items():
            for tgt, cond in edges:
                label = f" -- {cond.__name__} --> " if cond else " --> "
                lines.append(f"    {src}{label}{tgt}")
        return "\n".join(lines)

    # ── routing ─────────────────────────────────────────────────────

    def _route_edges(self, node_name: str, state: dict[str, Any], queue: deque) -> None:
        """Push the downstream node onto the queue.

        Routing semantics:
        - If the node has conditional edges, they are MUTUALLY EXCLUSIVE:
          the FIRST condition that returns a truthy target wins, and no
          unconditional edges fire (avoids both the "all branches fire"
          fan-out and the "unconditional edge also fires" footgun).
        - Otherwise all unconditional edges fire (a node may fan out to
          several downstream nodes — each becomes a parallel path).
        """
        edges = self._edges.get(node_name, [])
        conditional = [(t, c) for t, c in edges if c is not None]
        unconditional = [(t, c) for t, c in edges if c is None]

        if conditional:
            for target, cond in conditional:
                route = cond(state)
                if route:
                    queue.append(route)
                    return
            # No condition matched → fall back to the registered `default`
            # target, which lives in the conditional edge's target slot
            # (add_conditional_edges stores it there).
            for target, _ in conditional:
                if target:
                    queue.append(target)
                    return
            return

        for target, _ in unconditional:
            if target:
                queue.append(target)

    # ── execution ───────────────────────────────────────────────────

    async def run(self, initial_state: dict[str, Any]) -> dict[str, Any]:
        """Execute the graph from the entry node, supporting cycles & resume."""
        if not self._nodes:
            raise ValueError("Graph has no nodes")
        if self._entry is None:
            raise ValueError("Graph has no entry node")

        state: dict[str, Any] = dict(initial_state)
        # Nodes completed in a PRIOR session (crash resume) — skip execution.
        prior_completed: set[str] = set(initial_state.get("__visited__", []))
        # Nodes executed in THIS session (for checkpoint bookkeeping).
        executed: set[str] = set()
        # #4: deque — O(1) popleft instead of list.pop(0) O(n)
        queue: deque[str] = deque([self._entry])
        steps = 0
        checkpoint_failures = 0

        if prior_completed:
            logger.info("[graph:%s] RESUMING — %d prior nodes: %s",
                        self.name, len(prior_completed), sorted(prior_completed))
        logger.info("[graph:%s] start → %s", self.name, self._entry)

        while queue:
            node_name = queue.popleft()
            # #5: a typo'd node name in a condition function should blow up
            # in development, not silently skip a branch.
            if node_name not in self._nodes:
                raise ValueError(
                    f"[graph:{self.name}] unknown node '{node_name}' — "
                    "check your conditional-edge target names."
                )

            steps += 1
            if steps > self._max_steps:
                raise RuntimeError(
                    f"[graph:{self.name}] aborted after {self._max_steps} steps — "
                    "possible infinite loop. Check your conditional-edge conditions."
                )

            # Resume: a NON-reentrant node finished in a prior session is
            # skipped (but its edges still route).  Reentrant nodes (loop
            # members) re-run — their repeat count lives in state, so the
            # condition will terminate them at the right number of rounds.
            if (
                node_name in prior_completed
                and node_name not in executed
                and node_name not in self._reentrant
            ):
                logger.info("[graph:%s] ⟳ %s (resumed, skip)", self.name, node_name)
                self._route_edges(node_name, state, queue)
                continue

            # Loop-guard for NON-reentrant nodes: if this node already ran
            # this session (e.g. it is reachable via two converging edges,
            # or a conditional edge points back at it), drop it — its edges
            # were already routed when it first executed.  Re-routing here
            # would re-push it forever (a self-loop).
            if node_name in executed and node_name not in self._reentrant:
                logger.debug("[graph:%s] ↷ %s (already ran, skip)", self.name, node_name)
                continue

            executed.add(node_name)
            fn = self._nodes[node_name]
            try:
                update = await fn(state)
            except Exception as exc:
                logger.error("[graph:%s] node '%s' failed: %s", self.name, node_name, exc, exc_info=True)
                raise

            if update:
                state.update(update)
            logger.info("[graph:%s] ✓ %s", self.name, node_name)

            # Persist a checkpoint after each node completes.
            # #1: MERGE prior-completed and this-session nodes.  Overwriting
            # with only `executed` would forget what earlier sessions did,
            # making a second resume re-run already-finished work.
            if self._checkpoint is not None:
                combined = prior_completed | executed
                state["__visited__"] = sorted(combined)
                try:
                    await self._checkpoint(node_name, state)
                    checkpoint_failures = 0
                except Exception as exc:
                    # #2: silent checkpoint failures make resume silently
                    # useless.  Escalate after a few consecutive failures.
                    checkpoint_failures += 1
                    if checkpoint_failures >= 3:
                        logger.error(
                            "[graph:%s] checkpoint failed %d times in a row — "
                            "crash resume will NOT work. Last error: %s",
                            self.name, checkpoint_failures, exc, exc_info=True,
                        )
                    else:
                        logger.warning(
                            "[graph:%s] checkpoint persist failed (%d): %s",
                            self.name, checkpoint_failures, exc,
                        )

            self._route_edges(node_name, state, queue)

        logger.info("[graph:%s] done — %d nodes executed this session", self.name, len(executed))
        return state
