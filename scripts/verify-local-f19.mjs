#!/usr/bin/env node
// Local-mirror verification for F19 Phase 1: event sourcing infrastructure.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const es = fs.readFileSync(path.join(root, "src/deep_research/eventsourcing.py"), "utf8");
const agent = fs.readFileSync(path.join(root, "src/deep_research/core/agent.py"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");
const testEs = fs.existsSync(path.join(root, "tests/test_eventsourcing.py"));

const checks = [
  { name: "eventsourcing.py defines Event/EventStore", ok: es.includes("class Event") && es.includes("class EventStore") },
  { name: "eventsourcing.py has trace/rollback", ok: es.includes("def trace_text") && es.includes("def rollback_to") },
  { name: "agent.py records tool events", ok: agent.includes('self._record_event(tool_name') },
  { name: "agent.py records LLM events", ok: agent.includes('self._record_event("llm_call"') },
  { name: "PROGRESS.md records event sourcing Phase 1", ok: progress.includes("事件溯源 Phase 1") },
  { name: "event sourcing tests exist", ok: testEs },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F19 verification failed.");
  process.exit(1);
}
console.log("Local F19 verification passed. Real make test will run on remote after sync.");
