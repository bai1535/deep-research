#!/usr/bin/env node
// Local-mirror verification for F18: candidate verification result normalization + confidence threshold.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const cv = fs.readFileSync(path.join(root, "src/deep_research/candidate_verifier.py"), "utf8");
const test = fs.readFileSync(path.join(root, "tests/test_candidate_verifier.py"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");

const checks = [
  { name: "candidate_verifier.py has normalize function", ok: cv.includes("def _normalize_result") },
  { name: "verify() uses normalize before storing", ok: cv.includes("data = _normalize_result(result.data)") },
  { name: "low-confidence final is suppressed", ok: cv.includes("MIN_FINAL_CONFIDENCE") && cv.includes("data[\"final_candidate\"] = None") },
  { name: "normalization handles single candidate object", ok: test.includes("test_normalize_single_object_with_weak_candidate") && test.includes("test_normalize_low_score_candidate_not_forced") },
  { name: "PROGRESS.md records normalization fix", ok: progress.includes("候选验证结果归一化") && progress.includes("置信度门槛") },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F18 verification failed.");
  process.exit(1);
}
console.log("Local F18 verification passed. Real make test will run on remote after sync.");
