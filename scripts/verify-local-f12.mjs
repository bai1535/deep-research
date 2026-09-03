#!/usr/bin/env node
// Local-mirror verification for F12: Query Planner.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const qp = fs.readFileSync(path.join(root, "src/deep_research/query_planner.py"), "utf8");
const crew = fs.readFileSync(path.join(root, "src/deep_research/crews/research_crew.py"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");
const crewArch = fs.readFileSync(path.join(root, "src/deep_research/crews/ARCHITECTURE.md"), "utf8");
const testQp = fs.existsSync(path.join(root, "tests/test_query_planner.py"));

const checks = [
  { name: "query_planner.py defines planner/parse/format", ok: qp.includes("class QueryPlanner") && qp.includes("def parse_search_plan") && qp.includes("def format_search_plan") },
  { name: "planner prompt covers question types", ok: qp.includes("entity_fact") && qp.includes("multi_hop_clue") && qp.includes("historical_archive") },
  { name: "research_crew runs planner before orchestrator", ok: crew.includes("planner.plan(question)") && crew.includes("_run_orchestrator(orchestrator, question, search_plan)") },
  { name: "research_crew injects plan into researcher task", ok: crew.includes("format_search_plan(self.blackboard.read(\"search_plan\")") },
  { name: "crews ARCHITECTURE records query planner", ok: crewArch.includes("查询规划器") },
  { name: "PROGRESS.md records query planner", ok: progress.includes("查询规划器") },
  { name: "query planner tests exist", ok: testQp },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F12 verification failed.");
  process.exit(1);
}
console.log("Local F12 verification passed. Real make test will run on remote after sync.");
