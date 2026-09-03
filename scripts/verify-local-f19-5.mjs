#!/usr/bin/env node
// Local-mirror verification for F19-5: actual rollback execution.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const rp = fs.readFileSync(path.join(root, "src/deep_research/replay.py"), "utf8");
const api = fs.readFileSync(path.join(root, "web/api.py"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");
const testRp = fs.readFileSync(path.join(root, "tests/test_replay.py"), "utf8");

const checks = [
  { name: "OutputCache has delete", ok: rp.includes("def delete") },
  { name: "ReplayEngine has execute_rollback", ok: rp.includes("def execute_rollback") },
  { name: "execute_rollback writes rollback_state", ok: rp.includes("rollback_state.json") },
  { name: "rollback API supports execute", ok: api.includes("execute: bool") && api.includes("engine.execute_rollback") },
  { name: "PROGRESS.md records actual rollback", ok: progress.includes("实际执行 rollback") },
  { name: "execute rollback tests exist", ok: testRp.includes("test_execute_rollback_clears_affected_cache") },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F19-5 verification failed.");
  process.exit(1);
}
console.log("Local F19-5 verification passed. Real make test will run on remote after sync.");
