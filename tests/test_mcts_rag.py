"""Tests for MCTS-RAG 2.0 pure scaffolding."""

from deep_research.mcts_rag import (
    MCTSAction,
    MCTSNode,
    AnswerGroup,
    CandidateResult,
    backpropagate,
    best_child_by_reward,
    best_child_by_visits,
    group_candidates,
    is_terminal_action,
    normalize_answer,
    requires_retrieval,
    select_child,
    select_final_answer,
    uct_score,
)


def test_action_space_retrieval_and_terminal_flags():
    assert requires_retrieval(MCTSAction.RETRIEVAL_REASONING) is True
    assert requires_retrieval(MCTSAction.RETRIEVAL_DECOMPOSE) is True
    assert requires_retrieval(MCTSAction.DIRECT_ANSWER) is False
    assert is_terminal_action(MCTSAction.DIRECT_ANSWER) is True
    assert is_terminal_action(MCTSAction.SUMMARIZE_ANSWER) is True
    assert is_terminal_action(MCTSAction.QUICK_REASONING) is False


def test_mcts_node_add_child():
    root = MCTSNode(question="root")
    child = root.add_child(
        question="child",
        action=MCTSAction.DECOMPOSE_QUESTION,
        context="ctx",
    )
    assert child.parent is root
    assert child.depth == 1
    assert child.action == MCTSAction.DECOMPOSE_QUESTION
    assert root.children == [child]


def test_uct_prefers_unvisited():
    node = MCTSNode(question="q", visits=0)
    assert uct_score(node, parent_visits=5) == float("inf")


def test_select_child_explores_unvisited_first():
    root = MCTSNode(question="q")
    visited = root.add_child(question="visited")
    visited.visits = 3
    visited.total_reward = 1.0
    unvisited = root.add_child(question="unvisited")
    assert select_child(root) is unvisited


def test_backpropagate_updates_ancestors():
    root = MCTSNode(question="root")
    child = root.add_child(question="child")
    leaf = child.add_child(question="leaf")
    backpropagate(leaf, reward=1.0)
    assert leaf.visits == 1
    assert leaf.total_reward == 1.0
    assert child.visits == 1
    assert child.total_reward == 1.0
    assert root.visits == 1
    assert root.total_reward == 1.0


def test_best_child_by_visits_and_reward():
    root = MCTSNode(question="q")
    a = root.add_child(question="a")
    a.visits = 5
    a.total_reward = 2.0
    b = root.add_child(question="b")
    b.visits = 2
    b.total_reward = 1.8
    assert best_child_by_visits(root) is a
    assert best_child_by_reward(root) is b  # 0.9 avg > 0.4 avg


def test_normalize_answer():
    assert normalize_answer("  The Answer:  Queen Arwa University! ") == "the answer queen arwa university"
    assert normalize_answer("Queen Arwa University") == normalize_answer("queen arwa university")


def test_group_candidates_sums_rewards():
    candidates = [
        CandidateResult(answer="Blue", reward=0.6),
        CandidateResult(answer="blue", reward=0.4),
        CandidateResult(answer="Red", reward=0.7),
    ]
    groups = group_candidates(candidates)
    assert groups[0].answer == "Blue"
    assert groups[0].score == 1.0
    assert groups[0].count == 2


def test_select_final_answer_uses_reward_sum():
    candidates = [
        CandidateResult(answer="Red", reward=0.8),
        CandidateResult(answer="Blue", reward=0.9),
        CandidateResult(answer="blue", reward=0.5),
    ]
    final = select_final_answer(candidates)
    assert final is not None
    assert final.answer == "Blue"
    assert final.score == 1.4
