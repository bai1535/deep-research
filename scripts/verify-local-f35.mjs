#!/usr/bin/env node
// Local-mirror verification for F35: MCTS-RAG 2.0 pure scaffolding.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const pkg = path.join(root, "src/deep_research/mcts_rag");
const actions = fs.readFileSync(path.join(pkg, "actions.py"), "utf8");
const tree = fs.readFileSync(path.join(pkg, "tree.py"), "utf8");
const voting = fs.readFileSync(path.join(pkg, "voting.py"), "utf8");
const init = fs.readFileSync(path.join(pkg, "__init__.py"), "utf8");
const tests = fs.readFileSync(path.join(root, "tests/test_mcts_rag.py"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");
const decisions = fs.readFileSync(path.join(root, "DECISIONS.md"), "utf8");
const roadmap = fs.readFileSync(path.join(root, "docs/mcts-rag-2.0.md"), "utf8");

const checks = [
  { name: "action space A1-A6 exists", ok: actions.includes("DIRECT_ANSWER") && actions.includes("QUICK_REASONING") && actions.includes("DECOMPOSE_QUESTION") && actions.includes("RETRIEVAL_REASONING") && actions.includes("RETRIEVAL_DECOMPOSE") && actions.includes("SUMMARIZE_ANSWER") },
  { name: "MCTS tree has UCT/backprop", ok: tree.includes("class MCTSNode") && tree.includes("def uct_score") && tree.includes("def backpropagate") },
  { name: "voting has normalize/group/select", ok: voting.includes("def normalize_answer") && voting.includes("def group_candidates") && voting.includes("def select_final_answer") },
  { name: "package exports public API", ok: init.includes("MCTSAction") && init.includes("MCTSNode") && init.includes("CandidateResult") && init.includes("best_child_by_reward") },
  { name: "tests cover MCTS-RAG scaffolding", ok: tests.includes("test_uct_prefers_unvisited") && tests.includes("test_backpropagate_updates_ancestors") && tests.includes("test_select_final_answer_uses_reward_sum") },
  { name: "roadmap doc exists", ok: roadmap.includes("M1 纯算法脚手架") && roadmap.includes("M2 LLM 动作执行器") },
  { name: "PROGRESS.md records F35", ok: progress.includes("MCTS-RAG") && progress.includes("F35") },
  { name: "DECISIONS.md records F35", ok: decisions.includes("MCTS-RAG") && decisions.includes("F35") },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F35 verification failed.");
  process.exit(1);
}
console.log("Local F35 verification passed. Real make test will run on remote after sync.");
