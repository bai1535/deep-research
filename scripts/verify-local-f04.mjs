#!/usr/bin/env node
// Local-mirror verification for F04: benchmark integration.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const script = fs.readFileSync(path.join(root, "scripts/eval_benchmarks.py"), "utf8");
const makefile = fs.readFileSync(path.join(root, "Makefile"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");

const checks = [
  {
    name: "scripts/eval_benchmarks.py exists",
    ok: fs.existsSync(path.join(root, "scripts/eval_benchmarks.py")),
  },
  {
    name: "eval_benchmarks.py loads DeepResearch Bench",
    ok: script.includes("load_deepresearch_tasks"),
  },
  {
    name: "eval_benchmarks.py loads BrowseComp-Plus",
    ok: script.includes("load_browsecomp_tasks"),
  },
  {
    name: "Makefile has eval-bench target",
    ok: makefile.includes("eval-bench:"),
  },
  {
    name: "PROGRESS.md records benchmark integration",
    ok: progress.includes("公开基准接入"),
  },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F04 verification failed.");
  process.exit(1);
}
console.log("Local F04 verification passed. Real --list will run on remote after sync.");
