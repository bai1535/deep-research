"""Pure MCTS data structures and search helpers for MCTS-RAG.

This module contains no LLM calls.  It is designed so the later
LLM/tool-driven runner can focus on action generation while tree
bookkeeping stays deterministic and unit-testable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from .actions import MCTSAction


@dataclass
class MCTSNode:
    """One node in the MCTS reasoning tree.

    A node represents a reasoning state: the original/current question,
    accumulated context (reasoning + retrieved knowledge), and the action
    that produced it.
    """

    question: str
    parent: Optional["MCTSNode"] = None
    children: list["MCTSNode"] = field(default_factory=list)
    visits: int = 0
    total_reward: float = 0.0
    action: Optional[MCTSAction] = None
    context: str = ""
    candidate_answer: Optional[str] = None
    terminal: bool = False
    depth: int = 0

    @property
    def avg_reward(self) -> float:
        return self.total_reward / self.visits if self.visits else 0.0

    def add_child(
        self,
        *,
        question: str,
        action: Optional[MCTSAction] = None,
        context: str = "",
        candidate_answer: Optional[str] = None,
        terminal: bool = False,
    ) -> "MCTSNode":
        child = MCTSNode(
            question=question,
            parent=self,
            action=action,
            context=context,
            candidate_answer=candidate_answer,
            terminal=terminal,
            depth=self.depth + 1,
        )
        self.children.append(child)
        return child


def uct_score(node: MCTSNode, parent_visits: int, c: float = 1.4) -> float:
    """Upper Confidence Bound for Trees.

    Unvisited children return infinity so they are always explored before
    exploitation dominates.
    """
    if node.visits == 0:
        return float("inf")
    if parent_visits <= 0:
        return node.avg_reward
    exploration = c * math.sqrt(math.log(max(1.0, parent_visits)) / node.visits)
    return node.avg_reward + exploration


def select_child(node: MCTSNode, c: float = 1.4) -> Optional[MCTSNode]:
    """Select the next child to expand using UCT.

    Returns None when the node has no children.
    """
    if not node.children:
        return None
    unvisited = [child for child in node.children if child.visits == 0]
    if unvisited:
        return unvisited[0]
    return max(node.children, key=lambda child: uct_score(child, node.visits, c))


def best_child_by_visits(node: MCTSNode) -> Optional[MCTSNode]:
    """Return the most-visited child (used after search to pick a path)."""
    if not node.children:
        return None
    return max(node.children, key=lambda child: child.visits)


def best_child_by_reward(node: MCTSNode) -> Optional[MCTSNode]:
    """Return the child with the highest average reward."""
    if not node.children:
        return None
    return max(node.children, key=lambda child: child.avg_reward)


def backpropagate(node: MCTSNode, reward: float) -> None:
    """Propagate a simulation reward from *node* up to the root."""
    current: Optional[MCTSNode] = node
    while current is not None:
        current.visits += 1
        current.total_reward += reward
        current = current.parent
