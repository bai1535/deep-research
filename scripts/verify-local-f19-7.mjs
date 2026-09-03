#!/usr/bin/env node
// Local-mirror verification for F19-7: replay LLM + regenerate report.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const rp = fs.readFileSync(path.join(root, "src/deep_research/replay.py"), "utf8");
const api = fs.readFileSync(path.join(root, "web/api.py"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");

const checks = [
  { name: "replay.py has replay_and_regenerate", ok: rp.includes("def replay_and_regenerate") },
  { name: "replay_and_regenerate calls SynthesisCrewRunner", ok: rp.includes("SynthesisCrewRunner") },
  { name: "rollback API supports regenerate", ok: api.includes("regenerate: bool") && api.includes("engine.replay_and_regenerate") },
  { name: "PROGRESS.md records replay LLM/report", ok: progress.includes("重放 LLM + 重新生成报告") },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F19-7 verification failed.");
  process.exit(1);
}
console.log("Local F19-7 verification passed. Real make test will run on remote after sync.");
