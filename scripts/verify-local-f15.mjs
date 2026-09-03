#!/usr/bin/env node
// Local-mirror verification for F15: Wayback Machine historical archive access.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const wb = fs.readFileSync(path.join(root, "src/deep_research/tools/wayback.py"), "utf8");
const toolsInit = fs.readFileSync(path.join(root, "src/deep_research/tools/__init__.py"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");
const testWb = fs.existsSync(path.join(root, "tests/test_wayback.py"));

const checks = [
  { name: "wayback.py defines WaybackLookupTool", ok: wb.includes("class WaybackLookupTool") },
  { name: "wayback tool uses Firecrawl bridge", ok: wb.includes("firecrawl_scrape_json") && wb.includes("firecrawl_scrape") },
  { name: "tools/__init__.py registers wayback_lookup", ok: toolsInit.includes("WaybackLookupTool") && toolsInit.includes("tools.extend([WikipediaSearchTool(), WikidataLookupTool(), WaybackLookupTool()])") },
  { name: "PROGRESS.md records Wayback access", ok: progress.includes("Wayback Machine 历史档案接入") },
  { name: "wayback tests exist", ok: testWb },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F15 verification failed.");
  process.exit(1);
}
console.log("Local F15 verification passed. Real make test will run on remote after sync.");
