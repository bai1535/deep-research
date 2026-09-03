#!/usr/bin/env node
// Local-mirror verification for F32: AgentPolicy Phase 4 verification standard prompts.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const policyModule = fs.readFileSync(path.join(root, "src/deep_research/agents/policy.py"), "utf8");
const registry = fs.readFileSync(path.join(root, "src/deep_research/agents/registry.py"), "utf8");
const tests = fs.readFileSync(path.join(root, "tests/test_agent_policy.py"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");
const decisions = fs.readFileSync(path.join(root, "DECISIONS.md"), "utf8");

const checks = [
  { name: "VerificationStandard has render_prompt", ok: policyModule.includes("def render_prompt") },
  { name: "verifier default has rubric", ok: policyModule.includes("verifier_rubric_v1") && policyModule.includes("多源官方/一手来源") },
  { name: "second-opinion cannot see first pass", ok: policyModule.includes("independent_review_v1") && policyModule.includes("can_see_first_pass = False") },
  { name: "registry injects verification block into system prompt", ok: registry.includes("verification_block") && registry.includes("policy.verification.render_prompt()") },
  { name: "tests cover render and injection", ok: tests.includes("test_verification_standard_renders_prompt_block") && tests.includes("test_default_verifier_prompt_includes_rubric") },
  { name: "PROGRESS.md records F32", ok: progress.includes("VerificationStandard") && progress.includes("F32") },
  { name: "DECISIONS.md records F32", ok: decisions.includes("VerificationStandard") && decisions.includes("Phase 4") },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F32 verification failed.");
  process.exit(1);
}
console.log("Local F32 verification passed. Real make test will run on remote after sync.");
