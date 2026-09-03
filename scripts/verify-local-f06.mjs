#!/usr/bin/env node
// Local-mirror verification for F06: log filter + Scorer default.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const api = fs.readFileSync(path.join(root, "web/api.py"), "utf8");
const schemas = fs.readFileSync(path.join(root, "src/deep_research/models/schemas.py"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");

const checks = [
  {
    name: "web/api.py uses regex for level filtering",
    ok: api.includes("level_re") && api.includes("re.escape"),
  },
  {
    name: "ScoreResult.overall_score has default 0",
    ok: schemas.includes("overall_score: int = Field(default=0"),
  },
  {
    name: "PROGRESS.md records log/scorer fixes",
    ok: progress.includes("日志过滤与 Scorer 容错"),
  },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F06 verification failed.");
  process.exit(1);
}
console.log("Local F06 verification passed.");
