#!/usr/bin/env node
// Local-mirror verification for F30: AgentPolicy Phase 2 enforcement.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const bb = fs.readFileSync(path.join(root, "src/deep_research/core/blackboard.py"), "utf8");
const registry = fs.readFileSync(path.join(root, "src/deep_research/agents/registry.py"), "utf8");
const agentCore = fs.readFileSync(path.join(root, "src/deep_research/core/agent.py"), "utf8");
const tests = fs.readFileSync(path.join(root, "tests/test_agent_policy.py"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");
const decisions = fs.readFileSync(path.join(root, "DECISIONS.md"), "utf8");

const checks = [
  { name: "blackboard has ScopedBlackboard", ok: bb.includes("class ScopedBlackboard") },
  { name: "create_agent wraps blackboard in ScopedBlackboard", ok: registry.includes("ScopedBlackboard(") && registry.includes("read_patterns=policy.context.read_blackboard_keys") },
  { name: "Agent has _tool_allowed", ok: agentCore.includes("def _tool_allowed") },
  { name: "Agent enforces tool policy before run", ok: agentCore.includes("blocked by policy") && agentCore.includes("_tool_call_counts") },
  { name: "tests cover scoped blackboard and tool blocking", ok: tests.includes("test_scoped_blackboard_enforces_read_write_patterns") && tests.includes("test_agent_tool_policy_blocks_disallowed_tools") },
  { name: "PROGRESS.md records F30", ok: progress.includes("ScopedBlackboard") && progress.includes("F30") },
  { name: "DECISIONS.md records F30", ok: decisions.includes("Phase 2") && decisions.includes("ScopedBlackboard") },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F30 verification failed.");
  process.exit(1);
}
console.log("Local F30 verification passed. Real make test will run on remote after sync.");
