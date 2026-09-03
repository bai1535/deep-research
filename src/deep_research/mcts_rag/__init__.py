"""MCTS-RAG 2.0 — experimental package.

This is the 2.0 development line.  The package will eventually implement
a Monte Carlo Tree Search planner that interleaves LLM reasoning with
external retrieval (search/web fetch) to solve hard multi-hop questions.

Current milestone: pure algorithm scaffolding (action space, tree search,
voting) with unit tests.  LLM/tool wiring comes in the next milestone.
"""

from __future__ import annotations

from .actions import (
    ALL_ACTIONS,
    ACTION_NAMES_ZH,
    MCTSAction,
    is_terminal_action,
    requires_retrieval,
)
from .tree import (
    MCTSNode,
    backpropagate,
    best_child_by_reward,
    best_child_by_visits,
    select_child,
    uct_score,
)
from .voting import (
    AnswerGroup,
    CandidateResult,
    group_candidates,
    normalize_answer,
    select_final_answer,
)

__all__ = [
    "ACTION_NAMES_ZH",
    "ALL_ACTIONS",
    "AnswerGroup",
    "CandidateResult",
    "MCTSAction",
    "MCTSNode",
    "backpropagate",
    "best_child_by_reward",
    "best_child_by_visits",
    "group_candidates",
    "is_terminal_action",
    "normalize_answer",
    "requires_retrieval",
    "select_child",
    "select_final_answer",
    "uct_score",
]
