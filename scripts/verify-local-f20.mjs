#!/usr/bin/env node
// Local-mirror verification for F20: verifier status normalization + researcher JSON constraints.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const vc = fs.readFileSync(path.join(root, "src/deep_research/crews/verification_crew.py"), "utf8");
const rc = fs.readFileSync(path.join(root, "src/deep_research/crews/research_crew.py"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");
const test = fs.existsSync(path.join(root, "tests/test_verification_status.py"));

const checks = [
  { name: "verification_crew has status normalizer", ok: vc.includes("def _normalise_verification_status") && vc.includes("def _normalise_entries") },
  { name: "verification_crew applies normalization before construction", ok: vc.includes("_normalise_entries(vdata.data.get") && vc.includes("_normalise_entries(v2data.data.get") },
  { name: "researcher task has strong JSON instruction", ok: rc.includes("禁止输出 Markdown") && rc.includes("字段只能包含 perspective/research_question/key_findings/gaps/raw_transcript") },
  { name: "researcher retry prompt is stronger", ok: rc.includes("你上一次的输出不是合法 JSON") },
  { name: "PROGRESS.md records F20", ok: progress.includes("Verifier 状态容错 + Researcher JSON 约束") },
  { name: "F20 tests exist", ok: test },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F20 verification failed.");
  process.exit(1);
}
console.log("Local F20 verification passed. Real make test will run on remote after sync.");
