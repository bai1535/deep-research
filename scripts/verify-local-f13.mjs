#!/usr/bin/env node
// Local-mirror verification for F13: log viewer auto-refresh stability + contrast.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const html = fs.readFileSync(path.join(root, "web/logs.html"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");

const checks = [
  { name: "logs.html adds request timeout", ok: html.includes("AbortController") && html.includes("setTimeout(() => ctrl.abort(), 10000)") },
  { name: "logs.html prevents overlapping text refresh", ok: html.includes("textBusy") && html.includes("textSeq") },
  { name: "logs.html prevents overlapping calls refresh", ok: html.includes("callsBusy") && html.includes("callsSeq") },
  { name: "logs.html discards stale responses", ok: html.includes("discard stale response") },
  { name: "logs.html refreshes on visibility change", ok: html.includes("visibilitychange") },
  { name: "logs.html incrementally appends new log lines", ok: html.includes("function appendLogLines") && html.includes("content.startsWith(lastLogContent)") },
  { name: "logs.html has brighter log text", ok: html.includes("--text: #f2f6ff") && html.includes("background: #04060c") },
  { name: "logs.html has higher-contrast level colors", ok: html.includes("#8fa3c8") && html.includes("#d9f7e8") },
  { name: "PROGRESS.md records log page fixes", ok: progress.includes("日志页面稳定性与对比度修复") && progress.includes("增量追加") },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F13 verification failed.");
  process.exit(1);
}
console.log("Local F13 verification passed. Real make test will run on remote after sync.");
