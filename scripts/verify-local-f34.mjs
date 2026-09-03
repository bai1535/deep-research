#!/usr/bin/env node
// Local-mirror verification for F34: adaptive compute allocation.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const adaptive = fs.readFileSync(path.join(root, "src/deep_research/adaptive.py"), "utf8");
const researchCrew = fs.readFileSync(path.join(root, "src/deep_research/crews/research_crew.py"), "utf8");
const pipeline = fs.readFileSync(path.join(root, "src/deep_research/pipeline.py"), "utf8");
const tests = fs.readFileSync(path.join(root, "tests/test_adaptive.py"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");
const decisions = fs.readFileSync(path.join(root, "DECISIONS.md"), "utf8");

const checks = [
  { name: "adaptive module exists with allocation model", ok: adaptive.includes("class ComputeAllocation") },
  { name: "build_compute_plan maps question type to depth", ok: adaptive.includes("def build_compute_plan") && adaptive.includes("def base_depth_for_question_type") },
  { name: "weakness scoring exists", ok: adaptive.includes("def card_weakness_score") },
  { name: "augment targets are selected adaptively", ok: adaptive.includes("def select_augment_targets") && adaptive.includes("def allocation_for_augment") },
  { name: "research_crew writes compute_plan and uses allocations", ok: researchCrew.includes('self.blackboard.write("compute_plan"') && researchCrew.includes("allocation=allocation") },
  { name: "research_crew enforces dynamic ResourceBudget", ok: researchCrew.includes("policy.budget.max_tool_calls = allocation.max_tool_calls") },
  { name: "augment passes augment_count from pipeline", ok: pipeline.includes("augment_count=state.get(\"augment_count\", 0)") },
  { name: "tests cover adaptive allocation", ok: tests.includes("test_build_compute_plan_returns_one_allocation_per_brief") && tests.includes("test_select_augment_targets_with_feedback_skips_strong_cards") },
  { name: "PROGRESS.md records F34", ok: progress.includes("自适应计算分配") && progress.includes("F34") },
  { name: "DECISIONS.md records F34", ok: decisions.includes("自适应计算分配 F34") && decisions.includes("adaptive.py") },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F34 verification failed.");
  process.exit(1);
}
console.log("Local F34 verification passed. Real make test will run on remote after sync.");
