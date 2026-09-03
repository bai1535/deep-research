#!/usr/bin/env node
// Local-mirror verification for F22: Claim-level provenance Phase B.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const verifier = fs.readFileSync(path.join(root, "src/deep_research/claim_verifier.py"), "utf8");
const synthesis = fs.readFileSync(path.join(root, "src/deep_research/crews/synthesis_crew.py"), "utf8");
const schemas = fs.readFileSync(path.join(root, "src/deep_research/models/schemas.py"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");
const design = fs.readFileSync(path.join(root, "docs/claim-level-provenance.md"), "utf8");
const test = fs.existsSync(path.join(root, "tests/test_claim_verifier.py"));

const checks = [
  { name: "claim_verifier.py has AtomicClaimVerifier", ok: verifier.includes("class AtomicClaimVerifier") },
  { name: "claim_verifier.py has atomic task", ok: verifier.includes("ATOMIC_CLAIM_VERIFIER_TASK") },
  { name: "claim_verifier.py has status normalization", ok: verifier.includes("def _normalize_status") },
  { name: "synthesis crew calls AtomicClaimVerifier", ok: synthesis.includes("AtomicClaimVerifier") },
  { name: "schemas ClaimNode has reasoning", ok: schemas.includes("reasoning: str") },
  { name: "F22 tests exist", ok: test },
  { name: "design doc describes Phase B", ok: design.includes("原子验证") && design.includes("Phase B") },
  { name: "PROGRESS.md records F22", ok: progress.includes("Claim 级溯源 Phase B") },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F22 verification failed.");
  process.exit(1);
}
console.log("Local F22 verification passed. Real make test will run on remote after sync.");
