#!/usr/bin/env node
// Local-mirror verification for F23: Claim-level provenance Phase C (API + UI).
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const api = fs.readFileSync(path.join(root, "web/api.py"), "utf8");
const reportHtml = fs.readFileSync(path.join(root, "web/report.html"), "utf8");
const webArch = fs.readFileSync(path.join(root, "web/ARCHITECTURE.md"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");
const design = fs.readFileSync(path.join(root, "docs/claim-level-provenance.md"), "utf8");

const checks = [
  { name: "api has GET claims endpoint", ok: api.includes('@app.get("/research/{run_id}/claims")') },
  { name: "api has claim trace endpoint", ok: api.includes('@app.get("/research/{run_id}/claims/{claim_id}/trace")') },
  { name: "api has report viewer page", ok: api.includes('@app.get("/report/{run_id}")') },
  { name: "report.html has flow/evidence dual view", ok: reportHtml.includes("流畅版") && reportHtml.includes("证据版") },
  { name: "report.html has claim highlight + trace", ok: reportHtml.includes("mark") && reportHtml.includes("trace-btn") },
  { name: "web architecture doc lists new endpoints", ok: webArch.includes("/research/{run_id}/claims") && webArch.includes("/report/{run_id}") },
  { name: "design doc mentions Phase C UI/API", ok: design.includes("API + UI 双视图") || design.includes("Phase C") },
  { name: "PROGRESS.md records F23", ok: progress.includes("Claim 级溯源 Phase C") },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F23 verification failed.");
  process.exit(1);
}
console.log("Local F23 verification passed. Real make test will run on remote after sync.");
