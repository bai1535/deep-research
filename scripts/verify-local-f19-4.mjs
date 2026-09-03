#!/usr/bin/env node
// Local-mirror verification for F19-4: branch rollback + API.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const es = fs.readFileSync(path.join(root, "src/deep_research/eventsourcing.py"), "utf8");
const rp = fs.readFileSync(path.join(root, "src/deep_research/replay.py"), "utf8");
const api = fs.readFileSync(path.join(root, "web/api.py"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");
const testRp = fs.readFileSync(path.join(root, "tests/test_replay.py"), "utf8");

const checks = [
  { name: "eventsourcing.py has descendants", ok: es.includes("def descendants") },
  { name: "replay.py has branch rollback plan", ok: rp.includes("build_branch_rollback_plan") },
  { name: "web/api.py has events endpoint", ok: api.includes("/research/{run_id}/events") },
  { name: "web/api.py has rollback endpoint", ok: api.includes("/research/{run_id}/rollback") },
  { name: "web/api.py has trace endpoint", ok: api.includes("/research/{run_id}/trace") },
  { name: "PROGRESS.md records branch rollback/API", ok: progress.includes("分支级回滚与 API") },
  { name: "branch rollback tests exist", ok: testRp.includes("test_branch_rollback_plan_separates_parallel_branch") },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F19-4 verification failed.");
  process.exit(1);
}
console.log("Local F19-4 verification passed. Real make test will run on remote after sync.");
