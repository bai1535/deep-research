"""Candidate answer aggregation and final selection.

MCTS-RAG produces multiple reasoning trajectories; each trajectory ends
with a candidate answer and an accumulated reward.  The paper selects the
final answer by summing the rewards of trajectories that share the same
semantic answer (Equation 1/2 in the paper).

This module implements a deterministic text-normalisation version.  A
future milestone can add an LLM-based semantic grouping step.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

_PUNCT_RE = re.compile(r"[\s,，。.;；:：!！?？'\"“”‘’()（）\[\]【】\-—]+")


@dataclass(frozen=True)
class CandidateResult:
    """One completed MCTS trajectory."""

    answer: str
    reward: float = 1.0
    path_rewards: tuple[float, ...] = field(default_factory=tuple)


@dataclass
class AnswerGroup:
    """Group of candidate trajectories that map to the same answer."""

    answer: str
    score: float = 0.0
    count: int = 0
    rewards: list[float] = field(default_factory=list)


def normalize_answer(answer: str) -> str:
    """Lowercase and strip common punctuation/whitespace for grouping."""
    if not answer:
        return ""
    text = str(answer).strip().lower()
    text = _PUNCT_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def group_candidates(candidates: Iterable[CandidateResult]) -> list[AnswerGroup]:
    """Group candidates by normalised answer.

    Returns groups ordered by descending score.
    """
    groups: dict[str, AnswerGroup] = {}
    for candidate in candidates:
        key = normalize_answer(candidate.answer)
        if not key:
            continue
        group = groups.setdefault(
            key,
            AnswerGroup(answer=candidate.answer),
        )
        group.score += candidate.reward
        group.count += 1
        group.rewards.append(candidate.reward)
    return sorted(groups.values(), key=lambda g: (-g.score, -g.count))


def select_final_answer(
    candidates: Iterable[CandidateResult],
) -> AnswerGroup | None:
    """Select the best answer group using summed trajectory reward."""
    groups = group_candidates(candidates)
    return groups[0] if groups else None
