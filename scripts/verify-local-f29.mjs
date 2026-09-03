#!/usr/bin/env node
// Local-mirror verification for F29: AgentPolicy Phase 1 models + attachment.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const policyModule = fs.readFileSync(path.join(root, "src/deep_research/agents/policy.py"), "utf8");
const registry = fs.readFileSync(path.join(root, "src/deep_research/agents/registry.py"), "utf8");
const agentCore = fs.readFileSync(path.join(root, "src/deep_research/core/agent.py"), "utf8");
const tests = fs.existsSync(path.join(root, "tests/test_agent_policy.py"));
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");
const design = fs.existsSync(path.join(root, "docs/agent-independence-policy.md"));

const checks = [
  { name: "agents/policy.py has AgentPolicy models", ok: policyModule.includes("class AgentPolicy") && policyModule.includes("class ContextPolicy") && policyModule.includes("class ToolPolicy") },
  { name: "agents/policy.py has default_policy_for", ok: policyModule.includes("def default_policy_for") },
  { name: "registry imports default_policy_for", ok: registry.includes("from deep_research.agents.policy import AgentPolicy, default_policy_for") },
  { name: "create_agent attaches policy", ok: registry.includes("policy: AgentPolicy | None = None") && registry.includes("policy=policy") },
  { name: "core Agent stores policy", ok: agentCore.includes("policy: Any | None = None") && agentCore.includes("self.policy = policy") },
  { name: "F29 tests exist", ok: tests },
  { name: "design doc exists", ok: design },
  { name: "PROGRESS.md records F29", ok: progress.includes("Agent 独立性治理 Phase 1") },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F29 verification failed.");
  process.exit(1);
}
console.log("Local F29 verification passed. Real make test will run on remote after sync.");
