#!/usr/bin/env node
// Local-mirror verification for F11: lightweight per-round search quality gate.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const agent = fs.readFileSync(path.join(root, "src/deep_research/core/agent.py"), "utf8");
const registry = fs.readFileSync(path.join(root, "src/deep_research/agents/registry.py"), "utf8");
const researchCrew = fs.readFileSync(path.join(root, "src/deep_research/crews/research_crew.py"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");
const coreArch = fs.readFileSync(path.join(root, "src/deep_research/core/ARCHITECTURE.md"), "utf8");
const testGate = fs.existsSync(path.join(root, "tests/test_agent_quality_gate.py"));

const checks = [
  { name: "agent.py defines free-search gate", ok: agent.includes("FREE_SEARCH_TOOL_NAMES") && agent.includes("_maybe_unlock_quality_tools") },
  { name: "agent.py unlocks reserved tools on weak free results", ok: agent.includes("reserved_tools") && agent.includes("免费搜索引擎") },
  { name: "create_agent forwards reserved_tools", ok: registry.includes("reserved_tools") && registry.includes("reserved_tools=reserved_tools") },
  { name: "research_crew passes reserved_tools to researchers", ok: researchCrew.includes("reserved_tools=reserved") },
  { name: "core ARCHITECTURE records per-round gate", ok: coreArch.includes("轻量每轮搜索质量门") },
  { name: "PROGRESS.md records per-round gate", ok: progress.includes("轻量每轮搜索质量门") },
  { name: "quality gate tests exist", ok: testGate },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F11 verification failed.");
  process.exit(1);
}
console.log("Local F11 verification passed. Real make test will run on remote after sync.");
