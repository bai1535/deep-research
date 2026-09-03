#!/usr/bin/env node
// Local-mirror verification for F19-3: deterministic replay.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const rp = fs.readFileSync(path.join(root, "src/deep_research/replay.py"), "utf8");
const agent = fs.readFileSync(path.join(root, "src/deep_research/core/agent.py"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");
const testRp = fs.existsSync(path.join(root, "tests/test_replay.py"));

const checks = [
  { name: "replay.py defines OutputCache", ok: rp.includes("class OutputCache") },
  { name: "replay.py defines ReplayEngine", ok: rp.includes("class ReplayEngine") },
  { name: "agent writes outputs to cache", ok: agent.includes("OutputCache().put") },
  { name: "PROGRESS.md records deterministic replay", ok: progress.includes("确定性缓存与重放") },
  { name: "replay tests exist", ok: testRp },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F19-3 verification failed.");
  process.exit(1);
}
console.log("Local F19-3 verification passed. Real make test will run on remote after sync.");
