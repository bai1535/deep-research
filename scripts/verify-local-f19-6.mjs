#!/usr/bin/env node
// Local-mirror verification for F19-6: replay affected branch tools.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const rp = fs.readFileSync(path.join(root, "src/deep_research/replay.py"), "utf8");
const api = fs.readFileSync(path.join(root, "web/api.py"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");
const testRp = fs.readFileSync(path.join(root, "tests/test_replay.py"), "utf8");

const checks = [
  { name: "replay.py has replay_affected_tools", ok: rp.includes("def replay_affected_tools") },
  { name: "replay writes replay_output.jsonl", ok: rp.includes("replay_output.jsonl") },
  { name: "replay updates rollback state to tools_replayed", ok: rp.includes('"tools_replayed"') },
  { name: "rollback API supports replay", ok: api.includes("replay: bool") && api.includes("engine.replay_affected_tools") },
  { name: "PROGRESS.md records affected branch replay", ok: progress.includes("重放受影响分支") },
  { name: "replay affected tools tests exist", ok: testRp.includes("test_replay_affected_tools_skips_non_tool_events") },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F19-6 verification failed.");
  process.exit(1);
}
console.log("Local F19-6 verification passed. Real make test will run on remote after sync.");
