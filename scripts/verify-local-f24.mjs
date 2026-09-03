#!/usr/bin/env node
// Local-mirror verification for F24: Claim-level provenance Phase D (eval metrics + golden set).
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const evalScript = fs.readFileSync(path.join(root, "scripts/eval_claims.py"), "utf8");
const metricsModule = fs.readFileSync(path.join(root, "src/deep_research/claim_metrics.py"), "utf8");
const makefile = fs.readFileSync(path.join(root, "Makefile"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");
const design = fs.readFileSync(path.join(root, "docs/claim-level-provenance.md"), "utf8");
const golden = fs.existsSync(path.join(root, "data/claim_golden.json"));
const test = fs.existsSync(path.join(root, "tests/test_eval_claims.py"));

const checks = [
  { name: "claim_metrics.py has metric computation", ok: metricsModule.includes("def compute_run_metrics") && metricsModule.includes("def audit_granularity") },
  { name: "eval_claims.py imports shared metrics", ok: evalScript.includes("from deep_research.claim_metrics import") },
  { name: "claim_metrics.py includes traceability/evidence metrics", ok: metricsModule.includes("traceability") && metricsModule.includes("evidence_coverage") },
  { name: "golden set exists", ok: golden },
  { name: "Makefile has eval-claims target", ok: makefile.includes("eval-claims:") },
  { name: "F24 tests exist", ok: test },
  { name: "design doc mentions Phase D metrics", ok: design.includes("粒度评分") && design.includes("黄金拆分样例") },
  { name: "PROGRESS.md records F24", ok: progress.includes("Claim 级溯源 Phase D") },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F24 verification failed.");
  process.exit(1);
}
console.log("Local F24 verification passed. Real make test will run on remote after sync.");
