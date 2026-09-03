#!/usr/bin/env node
// Local-mirror verification for F02: effect evaluation system.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const checks = [
  {
    name: "scripts/search_eval.py exists",
    ok: fs.existsSync(path.join(root, "scripts/search_eval.py")),
  },
  {
    name: "search_eval.py implements Hit@k / nDCG@k",
    ok: fs.readFileSync(path.join(root, "scripts/search_eval.py"), "utf8").includes("nDCG@") &&
        fs.readFileSync(path.join(root, "scripts/search_eval.py"), "utf8").includes("Hit@"),
  },
  {
    name: "agent.py logs result_urls",
    ok: fs.readFileSync(path.join(root, "src/deep_research/core/agent.py"), "utf8").includes("result_urls"),
  },
  {
    name: "Makefile has eval target",
    ok: fs.readFileSync(path.join(root, "Makefile"), "utf8").includes("eval:"),
  },
  {
    name: "PROGRESS.md records effect evaluation",
    ok: fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8").includes("效果评估体系"),
  },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F02 verification failed.");
  process.exit(1);
}
console.log("Local F02 verification passed. Real make eval/test will run on remote after sync.");
