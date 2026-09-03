#!/usr/bin/env node
// Local-mirror verification for F21: Claim-level provenance Phase A.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const annotator = fs.readFileSync(path.join(root, "src/deep_research/claim_annotator.py"), "utf8");
const schemas = fs.readFileSync(path.join(root, "src/deep_research/models/schemas.py"), "utf8");
const synthesis = fs.readFileSync(path.join(root, "src/deep_research/crews/synthesis_crew.py"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");
const design = fs.existsSync(path.join(root, "docs/claim-level-provenance.md"));
const test = fs.existsSync(path.join(root, "tests/test_claim_annotator.py"));

const checks = [
  { name: "claim_annotator.py has ClaimAnnotator", ok: annotator.includes("class ClaimAnnotator") },
  { name: "claim_annotator.py has non-destructive prompt", ok: annotator.includes("不允许改写") && annotator.includes("连续子串") },
  { name: "claim_annotator.py has span search", ok: annotator.includes("def _find_span") },
  { name: "schemas has ClaimNode/AnswerDocument", ok: schemas.includes("class ClaimNode") && schemas.includes("class AnswerDocument") },
  { name: "synthesis crew calls ClaimAnnotator and writes claims.json", ok: synthesis.includes("ClaimAnnotator") && synthesis.includes("claims.json") },
  { name: "F21 tests exist", ok: test },
  { name: "design doc exists", ok: design },
  { name: "PROGRESS.md records F21", ok: progress.includes("Claim 级溯源 Phase A") },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F21 verification failed.");
  process.exit(1);
}
console.log("Local F21 verification passed. Real make test will run on remote after sync.");
