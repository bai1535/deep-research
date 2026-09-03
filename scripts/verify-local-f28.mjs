#!/usr/bin/env node
// Local-mirror verification for F28: Researcher non-JSON salvage.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const rc = fs.readFileSync(path.join(root, "src/deep_research/crews/research_crew.py"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");
const decisions = fs.readFileSync(path.join(root, "DECISIONS.md"), "utf8");

const checks = [
  { name: "research_crew has RESEARCHER_SALVAGE_TASK", ok: rc.includes("RESEARCHER_SALVAGE_TASK") },
  { name: "research_crew has _salvage_researcher_output", ok: rc.includes("async def _salvage_researcher_output") },
  { name: "retry path calls salvage after last parse failure", ok: rc.includes("last_parse_failed") && rc.includes("_salvage_researcher_output(pname, sub_q, raw") },
  { name: "salvage agent has no tools and json_object", ok: rc.includes("tools=[]") && rc.includes('response_format={"type": "json_object"}') },
  { name: "PROGRESS.md records F28", ok: progress.includes("Researcher 输出救捞") },
  { name: "DECISIONS.md records F28", ok: decisions.includes("Researcher 输出救捞") },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F28 verification failed.");
  process.exit(1);
}
console.log("Local F28 verification passed. Real make test will run on remote after sync.");
