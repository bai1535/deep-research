#!/usr/bin/env node
// Local-mirror verification for F33: AgentPolicy Phase 5 runtime isolation.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const policyModule = fs.readFileSync(path.join(root, "src/deep_research/agents/policy.py"), "utf8");
const tests = fs.readFileSync(path.join(root, "tests/test_agent_policy.py"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");
const decisions = fs.readFileSync(path.join(root, "DECISIONS.md"), "utf8");

const checks = [
  { name: "second-opinion read keys exclude run data", ok: policyModule.includes('"run_id"') && policyModule.includes('"usage:*"') && !policyModule.includes('"run:*"') },
  { name: "second-opinion write only usage", ok: policyModule.includes('policy.context.write_blackboard_keys = ["usage:*"]') },
  { name: "tests cover runtime blackboard isolation", ok: tests.includes("test_second_opinion_agent_cannot_read_run_data_from_blackboard") },
  { name: "PROGRESS.md records F33", ok: progress.includes("运行时无法读取第一轮结论") && progress.includes("F33") },
  { name: "DECISIONS.md records F33", ok: decisions.includes("运行时隔离") && decisions.includes("Phase 5") },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F33 verification failed.");
  process.exit(1);
}
console.log("Local F33 verification passed. Real make test will run on remote after sync.");
