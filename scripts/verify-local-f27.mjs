#!/usr/bin/env node
// Local-mirror verification for F27: log page auto-refresh robustness.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const logsHtml = fs.readFileSync(path.join(root, "web/logs.html"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");

const checks = [
  { name: "logs.html has watchdog timer", ok: logsHtml.includes("watchdogTimer") },
  { name: "logs.html tracks lastTextSuccess", ok: logsHtml.includes("lastTextSuccess") },
  { name: "autoTail refreshes in any text mode", ok: logsHtml.includes("if ($('autoTail').checked) loadText()") },
  { name: "watchdog forces reload after stall", ok: logsHtml.includes("log auto-refresh watchdog: forcing reload") },
  { name: "visibilitychange resets busy and restarts timers", ok: logsHtml.includes("textBusy = false;") && logsHtml.includes("startTimers();") },
  { name: "PROGRESS.md records F27", ok: progress.includes("日志页自动刷新增强") && progress.includes("F27") },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F27 verification failed.");
  process.exit(1);
}
console.log("Local F27 verification passed. Real make test will run on remote after sync.");
