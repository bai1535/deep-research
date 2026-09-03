#!/usr/bin/env node
// Local-mirror verification for F25: report page evidence visibility + clickable URLs.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const indexHtml = fs.readFileSync(path.join(root, "web/index.html"), "utf8");
const reportHtml = fs.readFileSync(path.join(root, "web/report.html"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");

const checks = [
  { name: "index.html fetches claims in loadHero", ok: indexHtml.includes("/claims") },
  { name: "index.html renders inline superscript markers", ok: indexHtml.includes("renderMarkdownWithClaims") && indexHtml.includes("claim-sup") },
  { name: "index.html renders linked evidence footnotes", ok: indexHtml.includes("renderEvidenceFootnotes") && indexHtml.includes("evidence-footnotes") },
  { name: "index.html colors superscripts by confidence/status", ok: indexHtml.includes("claimColorClass") && indexHtml.includes("claim-sup.status-verified") },
  { name: "index.html click superscript jumps to footnote", ok: indexHtml.includes("getElementById('evidence-' + claimId)") },
  { name: "report.html also uses inline superscripts + confidence colors", ok: reportHtml.includes("renderMarkdownWithClaims") && reportHtml.includes("claimColorClass") },
  { name: "PROGRESS.md records F25", ok: progress.includes("主报告页") && progress.includes("F25") },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F25 verification failed.");
  process.exit(1);
}
console.log("Local F25 verification passed. Real make test will run on remote after sync.");
