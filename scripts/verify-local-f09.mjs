#!/usr/bin/env node
// Local-mirror verification for F09: ModSearch-inspired Firecrawl keyless bridge.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const bridge = fs.readFileSync(path.join(root, "src/deep_research/tools/firecrawl_bridge.py"), "utf8");
const knowledge = fs.readFileSync(path.join(root, "src/deep_research/tools/knowledge.py"), "utf8");
const search = fs.readFileSync(path.join(root, "src/deep_research/tools/search.py"), "utf8");
const webFetch = fs.readFileSync(path.join(root, "src/deep_research/tools/web_fetch.py"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");
const constraints = fs.readFileSync(path.join(root, "src/deep_research/tools/CONSTRAINTS.md"), "utf8");
const testBridge = fs.existsSync(path.join(root, "tests/test_firecrawl_bridge.py"));

const checks = [
  { name: "firecrawl_bridge.py defines search/scrape helpers", ok: bridge.includes("async def firecrawl_search") && bridge.includes("async def firecrawl_scrape") },
  { name: "knowledge.py uses Firecrawl keyless bridge", ok: knowledge.includes("firecrawl_search") && knowledge.includes("firecrawl_scrape_json") },
  { name: "FirecrawlSearchTool supports keyless mode", ok: search.includes("firecrawl_search keyless failed") },
  { name: "WebFetchTool supports keyless Firecrawl scrape", ok: webFetch.includes("Keyless Firecrawl free tier") },
  { name: "CONSTRAINTS.md marks Wikipedia/Wikidata available", ok: constraints.includes("Firecrawl keyless 桥接") },
  { name: "PROGRESS.md records ModSearch borrowing", ok: progress.includes("ModSearch 借鉴") },
  { name: "bridge tests exist", ok: testBridge },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F09 verification failed.");
  process.exit(1);
}
console.log("Local F09 verification passed. Real make test will run on remote after sync.");
