#!/usr/bin/env node
// Local-mirror verification for F26: independent second-opinion verifier + fact/presentation separation.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const vc = fs.readFileSync(path.join(root, "src/deep_research/crews/verification_crew.py"), "utf8");
const schemas = fs.readFileSync(path.join(root, "src/deep_research/models/schemas.py"), "utf8");
const tests = fs.readFileSync(path.join(root, "tests/test_verification_status.py"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");
const decisions = fs.readFileSync(path.join(root, "DECISIONS.md"), "utf8");

const checks = [
  { name: "verification_crew has SECOND_OPINION_TASK", ok: vc.includes("SECOND_OPINION_TASK") },
  { name: "verification_crew has _second_opinion method", ok: vc.includes("async def _second_opinion") },
  { name: "verification_crew has _merge_entries", ok: vc.includes("def _merge_entries") },
  { name: "verification_crew has fact_status normalizer", ok: vc.includes("def _normalise_fact_status") },
  { name: "schemas VerificationEntry has fact_status/confidence/presentation_issues", ok: schemas.includes("fact_status: str | None") && schemas.includes("presentation_issues: list[str]") },
  { name: "tests cover second-opinion merge", ok: tests.includes("test_merge_entries_second_opinion_can_upgrade_suspect") && tests.includes("test_merge_entries_second_opinion_can_downgrade_verified") },
  { name: "PROGRESS.md records F26", ok: progress.includes("独立二次核查员") },
  { name: "DECISIONS.md records F26", ok: decisions.includes("独立二次核查") },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F26 verification failed.");
  process.exit(1);
}
console.log("Local F26 verification passed. Real make test will run on remote after sync.");
