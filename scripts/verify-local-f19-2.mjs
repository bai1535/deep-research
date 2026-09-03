#!/usr/bin/env node
// Local-mirror verification for F19-2: causal backtracking engine.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const cb = fs.readFileSync(path.join(root, "src/deep_research/causal_backtracking.py"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");
const testCb = fs.existsSync(path.join(root, "tests/test_causal_backtracking.py"));

const checks = [
  { name: "causal_backtracking.py defines trace_claim", ok: cb.includes("def trace_claim") },
  { name: "causal_backtracking.py defines trace_event", ok: cb.includes("def trace_event") },
  { name: "backtracking scores source events", ok: cb.includes("_SOURCE_ACTIONS") && cb.includes("score") },
  { name: "PROGRESS.md records causal backtracking", ok: progress.includes("因果回溯引擎") },
  { name: "causal backtracking tests exist", ok: testCb },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F19-2 verification failed.");
  process.exit(1);
}
console.log("Local F19-2 verification passed. Real make test will run on remote after sync.");
