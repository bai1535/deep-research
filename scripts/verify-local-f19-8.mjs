#!/usr/bin/env node
// Local-mirror verification for F19-8: log viewer events/rollback UI.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const html = fs.readFileSync(path.join(root, "web/logs.html"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");

const checks = [
  { name: "logs.html has events tab", ok: html.includes('data-tab="events"') && html.includes('id="panel-events"') },
  { name: "logs.html has event list loader", ok: html.includes("async function loadEvents") },
  { name: "logs.html has rollback actions", ok: html.includes("rollbackAction") && html.includes("rollbackRegenerate") },
  { name: "logs.html has trace action", ok: html.includes("traceClaimAction") },
  { name: "PROGRESS.md records frontend events/rollback", ok: progress.includes("日志/前端事件查看和回滚入口") },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F19-8 verification failed.");
  process.exit(1);
}
console.log("Local F19-8 verification passed. Real make test will run on remote after sync.");
