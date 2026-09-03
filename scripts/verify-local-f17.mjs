#!/usr/bin/env node
// Local-mirror verification for F17: Verifier active search + contradiction adjudicator.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const registry = fs.readFileSync(path.join(root, "src/deep_research/agents/registry.py"), "utf8");
const vc = fs.readFileSync(path.join(root, "src/deep_research/crews/verification_crew.py"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");
const testVs = fs.existsSync(path.join(root, "tests/test_verifier_search.py"));

const checks = [
  { name: "VERIFIER_CONFIG includes search tools", ok: registry.includes('"tools": [*get_search_tools(), WebFetchTool(), SQLiteReadTool()]') },
  { name: "verification_crew passes reserved quality tools", ok: vc.includes("reserved_tools=reserved") },
  { name: "verification_crew defines contradiction adjudicator", ok: vc.includes("CONTRADICTION_ADJUDICATOR_TASK") && vc.includes("_adjudicate_contradictions") },
  { name: "verification_crew runs adjudicator on contradictions", ok: vc.includes('"⚠️ 矛盾" in cross') || vc.includes('"contradiction" in cross.lower()') },
  { name: "PROGRESS.md records verifier search/adjudicator", ok: progress.includes("Verifier 主动搜索 + 矛盾裁决器") },
  { name: "verifier search tests exist", ok: testVs },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F17 verification failed.");
  process.exit(1);
}
console.log("Local F17 verification passed. Real make test will run on remote after sync.");
