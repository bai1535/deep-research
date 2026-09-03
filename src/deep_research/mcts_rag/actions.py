"""MCTS-RAG action space.

The six actions mirror the MCTS-RAG paper:

- A1 Direct Answer
- A2 Quick Reasoning
- A3 Decompose Question
- A4 Retrieval Reasoning
- A5 Retrieval Decompose
- A6 Summarized Answer

This module is intentionally pure/declarative so prompts, routing and
tree expansion can share one definition.
"""

from __future__ import annotations

from enum import StrEnum


class MCTSAction(StrEnum):
    DIRECT_ANSWER = "direct_answer"
    QUICK_REASONING = "quick_reasoning"
    DECOMPOSE_QUESTION = "decompose_question"
    RETRIEVAL_REASONING = "retrieval_reasoning"
    RETRIEVAL_DECOMPOSE = "retrieval_decompose"
    SUMMARIZE_ANSWER = "summarize_answer"


ACTION_NAMES_ZH: dict[MCTSAction, str] = {
    MCTSAction.DIRECT_ANSWER: "直接回答",
    MCTSAction.QUICK_REASONING: "快速推理",
    MCTSAction.DECOMPOSE_QUESTION: "拆解问题",
    MCTSAction.RETRIEVAL_REASONING: "检索后推理",
    MCTSAction.RETRIEVAL_DECOMPOSE: "检索并拆解",
    MCTSAction.SUMMARIZE_ANSWER: "汇总答案",
}

ALL_ACTIONS: list[MCTSAction] = [
    MCTSAction.DIRECT_ANSWER,
    MCTSAction.QUICK_REASONING,
    MCTSAction.DECOMPOSE_QUESTION,
    MCTSAction.RETRIEVAL_REASONING,
    MCTSAction.RETRIEVAL_DECOMPOSE,
    MCTSAction.SUMMARIZE_ANSWER,
]


def requires_retrieval(action: MCTSAction) -> bool:
    """Whether this action should call an external search/retrieval tool."""
    return action in (
        MCTSAction.RETRIEVAL_REASONING,
        MCTSAction.RETRIEVAL_DECOMPOSE,
    )


def is_terminal_action(action: MCTSAction) -> bool:
    """Whether this action produces a final/summary answer for a branch."""
    return action in (
        MCTSAction.DIRECT_ANSWER,
        MCTSAction.SUMMARIZE_ANSWER,
    )
