#!/usr/bin/env node
// Local-mirror verification for F07: log viewer readability.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const html = fs.readFileSync(path.join(root, "web/logs.html"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");

const checks = [
  {
    name: "logs.html sets color-scheme: dark",
    ok: html.includes("color-scheme: dark"),
  },
  {
    name: "log lines default to light text",
    ok: html.includes(".log-line {") && html.includes("color: var(--text)"),
  },
  {
    name: "PROGRESS.md records readability fix",
    ok: progress.includes("日志查看器可读性"),
  },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F07 verification failed.");
  process.exit(1);
}
console.log("Local F07 verification passed.");
