"""Teachability — cross-run experience layer.

Every agent's system prompt is static and every run starts from an
empty conversation, so the system never learns from history.  This
module adds a lightweight experience feedback loop (AutoGen
"teachable memory" style):

- STATIC_EXPERIENCE: hand-written lessons, tagged with the agent they
  apply to (`[orchestrator]`, `[researcher]`, `[search]`, `[all]`,
  `[perspective:名字]`).
- Dynamic lessons: after each completed run, `ExperienceStore.learn`
  aggregates the real outcomes from evidence.json by ROLE (roles are
  stable across runs; perspective names are question-specific) and
  rewrites `runs/experience.json`.  Underperforming roles teach the
  orchestrator to re-scope them; strong roles get praised into deeper
  dives.
- `lessons_for(agent_name, tools)` selects the applicable lessons and
  returns an injection block; `create_agent` appends it to the agent's
  system prompt.

The system gets measurably smarter with every run — the main
difference between this and a fixed pipeline.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("deep_research.experience")

# ── hand-written lessons (curated from real runs) ──────────────────
# Tag prefix decides which agents receive each lesson:
#   [all]                 → every agent
#   [orchestrator]        → the orchestrator (picks perspectives/roles)
#   [researcher]          → any researcher-* agent
#   [search]              → agents with search/fetch tools
#   [perspective:名字]    → the researcher with exactly that perspective
STATIC_EXPERIENCE: list[str] = [
    "[orchestrator] 贸易/政策类问题 (CBAM, 半导体): 批判者(critical)视角产出最丰富，行业视角次要",
    "[orchestrator] 技术类问题 (GIL, RSC): 技术专家(technical)视角产出最丰富",
    "[search] 中文/国内新发布内容用 baidu_search；英文技术文档/源码/论文用 bing_search；付费 API 仅在免费引擎无结果或需要结构化内容时使用",
    "[researcher] 每条发现尽量带 1-2 个具体数字/时间/版本号，纯定性描述会被质量评审打低分",
    "[all] 引用来源按可信度排序: 官方文档/学术论文 > 权威媒体 > 技术博客 > 社区帖子",
]

_SEARCH_TOOLS = {"baidu_search", "bing_search", "firecrawl_search", "tavily_search", "wikipedia_search", "wikidata_lookup", "web_fetch"}

MAX_LESSONS_INJECTED = 6       # per agent
MAX_LESSON_CHARS = 120         # per lesson (truncated)
MAX_INJECTED_CHARS = 800       # total injection block budget

# Dynamic-lesson generation thresholds (guard against noise from few runs)
MIN_RUNS_FOR_STRONG = 3        # roles with ≥3 runs may be "strong" lessons
MIN_RUNS_FOR_WEAK = 2          # roles with ≥2 runs may be "weak" lessons
STRONG_RATIO = 1.25            # avg ≥ overall_avg × 1.25 → strong
WEAK_ZERO_RATE = 0.5           # ≥50% zero-finding runs → weak


def _load_json(path: Path) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("experience: failed to read %s: %s", path, exc)
    return {}


class ExperienceStore:
    """Loads/merges experience from a JSON file on disk.

    The file holds cumulative per-role stats plus the derived lessons:
        {"stats": {role: {"runs": n, "findings_total": n, "zero_runs": n}},
         "lessons": [{"tag": "...", "text": "..."}]}
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else Path(os.getenv("RESEARCH_OUTPUT_DIR", "./runs")) / "experience.json"

    # ── read side: what an agent's prompt should include ───────────

    def lessons_for(self, agent_name: str, tool_names: list[str] | None = None) -> str:
        """Return the injection block applicable to this agent, or ''."""
        tool_names = tool_names or []
        has_search = any(t in _SEARCH_TOOLS for t in tool_names)

        picks: list[str] = []
        for tag, text in self._all_lessons():
            if tag == "all":
                match = True
            elif tag == "orchestrator":
                match = agent_name == "orchestrator"
            elif tag == "researcher":
                match = agent_name.startswith("researcher")
            elif tag == "search":
                match = has_search
            elif tag.startswith("perspective:"):
                match = agent_name == f"researcher-{tag.split(':', 1)[1]}"
            else:
                match = False
            if match:
                picks.append(text)

        if not picks:
            return ""
        picks = picks[:MAX_LESSONS_INJECTED]

        lines: list[str] = []
        budget = MAX_INJECTED_CHARS
        for text in picks:
            if len(text) > MAX_LESSON_CHARS:
                text = text[:MAX_LESSON_CHARS - 1] + "…"
            if budget - len(text) - 2 < 0:
                break
            lines.append(f"- {text}")
            budget -= len(text) + 2
        return "\n".join(lines)

    # ── write side: learn from a completed run ─────────────────────

    def learn(self, run_id: str, evidence: dict) -> None:
        """Merge this run's per-card outcomes into the experience file.

        Called after a run completes (evidence.json exists).  Aggregation
        is by ROLE — perspective names are question-specific, roles are
        not.  Idempotent-ish: each card counts once; re-learning the same
        run would over-count, so callers must only learn each run once.
        """
        cards = evidence.get("cards") or []
        if not cards:
            return

        stats = self._load_stats()
        for card in cards:
            role = str(card.get("role") or "").strip() or "未标注角色"
            n = len(card.get("key_findings") or [])
            s = stats.setdefault(role, {"runs": 0, "findings_total": 0, "zero_runs": 0})
            s["runs"] += 1
            s["findings_total"] += n
            if n == 0:
                s["zero_runs"] += 1

        self._save(stats)
        logger.info(
            "experience: learned from run %s — %d card(s), %d role stats",
            run_id, len(cards), len(stats),
        )

    # ── internals ──────────────────────────────────────────────────

    def _all_lessons(self) -> list[tuple[str, str]]:
        """Static + derived lessons, as (tag, text)."""
        lessons: list[tuple[str, str]] = []
        for raw in STATIC_EXPERIENCE:
            if raw.startswith("["):
                tag, _, text = raw[1:].partition("]")
                lessons.append((tag.strip(), text.strip()))
            else:
                lessons.append(("all", raw.strip()))
        for dynamic in self._load_lessons():
            lessons.append((dynamic.get("tag", "all"), dynamic.get("text", "")))
        return lessons

    def _load_stats(self) -> dict:
        return _load_json(self.path).get("stats", {})

    def _load_lessons(self) -> list[dict]:
        return _load_json(self.path).get("lessons", [])

    def _save(self, stats: dict) -> None:
        """Rebuild derived lessons from stats and atomically write."""
        lessons = _derive_lessons(stats)
        payload = {"version": 1, "stats": stats, "lessons": lessons}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: tmp + rename so a crash mid-write never corrupts
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)


def _derive_lessons(stats: dict) -> list[dict]:
    """Turn cumulative role stats into (bounded) dynamic lessons."""
    strong = {r: s for r, s in stats.items() if s["runs"] >= MIN_RUNS_FOR_STRONG}
    lessons: list[dict] = []
    if not strong:
        # even weak data can teach the orchestrator what to avoid
        weak = {r: s for r, s in stats.items() if s["runs"] >= MIN_RUNS_FOR_WEAK}
        for role, s in sorted(weak.items(), key=lambda x: -x[1]["zero_runs"]):
            if s["zero_runs"] / s["runs"] >= WEAK_ZERO_RATE:
                lessons.append({
                    "tag": "orchestrator",
                    "text": (
                        f"角色「{role}」历史 {s['zero_runs']}/{s['runs']} 轮产出为 0，"
                        "派给它时要求聚焦子问题、更换搜索关键词"
                    ),
                })
        return lessons[:MAX_LESSONS_INJECTED]

    overall_avg = sum(s["findings_total"] for s in strong.values()) / sum(s["runs"] for s in strong.values())
    for role, s in sorted(strong.items(), key=lambda x: -(x[1]["findings_total"] / x[1]["runs"])):
        avg = s["findings_total"] / s["runs"]
        if avg >= overall_avg * STRONG_RATIO:
            lessons.append({
                "tag": "researcher",
                "text": (
                    f"角色「{role}」历史平均产出 {avg:.1f} 条发现"
                    f"(全体平均 {overall_avg:.1f})，该角色擅长深挖，保持"
                ),
            })
        elif s["zero_runs"] / s["runs"] >= WEAK_ZERO_RATE:
            lessons.append({
                "tag": "orchestrator",
                "text": (
                    f"角色「{role}」历史 {s['zero_runs']}/{s['runs']} 轮产出为 0，"
                    "派给它时要求聚焦子问题、更换搜索关键词"
                ),
            })
    return lessons[:MAX_LESSONS_INJECTED]


# ── module-level convenience (used by registry.create_agent) ────────
_store: ExperienceStore | None = None


def get_lessons_for_agent(agent_name: str, tool_names: list[str] | None = None) -> str:
    """Read the experience file and return the injection block ('' if none).

    Reads the file on every call — the file is a few KB and agents are
    created once per task, so this is cheap and always fresh.
    """
    global _store
    if _store is None:
        _store = ExperienceStore()
    try:
        return _store.lessons_for(agent_name, tool_names)
    except Exception as exc:
        logger.warning("experience: lessons_for failed: %s", exc)
        return ""
