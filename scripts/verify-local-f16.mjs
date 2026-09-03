#!/usr/bin/env node
// Local-mirror verification for F16: automated eval judge.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const judge = fs.readFileSync(path.join(root, "scripts/eval_judge.py"), "utf8");
const makefile = fs.readFileSync(path.join(root, "Makefile"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");

const checks = [
  { name: "eval_judge.py exists with judge_one", ok: judge.includes("def judge_one") && judge.includes("JUDGE_PROMPT") },
  { name: "eval_judge.py outputs yes/partial/no", ok: judge.includes('"match": "yes|partial|no"') || judge.includes('"match": "yes|partial|no"') },
  { name: "Makefile has judge target", ok: makefile.includes("judge:") && makefile.includes("eval_judge.py") },
  { name: "PROGRESS.md records automated judge", ok: progress.includes("自动评测 Judge") },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F16 verification failed.");
  process.exit(1);
}
console.log("Local F16 verification passed. Real make test will run on remote after sync.");
