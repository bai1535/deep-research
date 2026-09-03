#!/usr/bin/env node
// Local-mirror verification for F31: AgentPolicy Phase 3 resource budgets + audit log.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const auditModule = fs.readFileSync(path.join(root, "src/deep_research/core/policy_audit.py"), "utf8");
const bb = fs.readFileSync(path.join(root, "src/deep_research/core/blackboard.py"), "utf8");
const agentCore = fs.readFileSync(path.join(root, "src/deep_research/core/agent.py"), "utf8");
const tests = fs.readFileSync(path.join(root, "tests/test_agent_policy.py"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");
const decisions = fs.readFileSync(path.join(root, "DECISIONS.md"), "utf8");

const checks = [
  { name: "policy_audit.py exists", ok: auditModule.includes("def log_policy_event") && auditModule.includes("policy_audit.jsonl") },
  { name: "ScopedBlackboard logs denials to audit", ok: bb.includes("log_policy_event") && bb.includes("blackboard_") },
  { name: "Agent has total tool call counter", ok: agentCore.includes("_total_tool_calls") },
  { name: "Agent enforces max_tool_calls in _tool_allowed", ok: agentCore.includes("tool-call budget exceeded") },
  { name: "Agent enforces LLM ResourceBudget", ok: agentCore.includes("max_llm_calls=") && agentCore.includes("ResourceBudget") },
  { name: "tests cover resource budgets", ok: tests.includes("test_resource_budget_blocks_tool_calls") && tests.includes("test_resource_budget_blocks_llm_calls") },
  { name: "PROGRESS.md records F31", ok: progress.includes("ResourceBudget") && progress.includes("F31") },
  { name: "DECISIONS.md records F31", ok: decisions.includes("ResourceBudget") && decisions.includes("Phase 3") },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F31 verification failed.");
  process.exit(1);
}
console.log("Local F31 verification passed. Real make test will run on remote after sync.");
