#!/usr/bin/env node
// Local-mirror verification for F10: Firecrawl last-resort / quality-gate gating.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const toolsInit = fs.readFileSync(path.join(root, "src/deep_research/tools/__init__.py"), "utf8");
const researchCrew = fs.readFileSync(path.join(root, "src/deep_research/crews/research_crew.py"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");
const constraints = fs.readFileSync(path.join(root, "src/deep_research/tools/CONSTRAINTS.md"), "utf8");

const checks = [
  { name: "tools/__init__.py has free/quality tool factories", ok: toolsInit.includes("def get_free_search_tools") && toolsInit.includes("def get_quality_search_tools") },
  { name: "get_search_tools defaults to free only", ok: toolsInit.includes("return get_free_search_tools()") },
  { name: "default free tools exclude Firecrawl/Wikipedia/Wikidata", ok: toolsInit.includes("return [BaiduSearchTool(), BingSearchTool()]") },
  { name: "quality tools append knowledge+Firecrawl", ok: toolsInit.includes("tools.extend([WikipediaSearchTool(), WikidataLookupTool()])") && toolsInit.includes("tools.append(FirecrawlSearchTool())") },
  { name: "research_crew enables quality tools on feedback", ok: researchCrew.includes("use_quality_tools=bool(feedback)") && researchCrew.includes("get_quality_search_tools()") },
  { name: "CONSTRAINTS.md documents free-first/quality-gate", ok: constraints.includes("质量门重搜") },
  { name: "PROGRESS.md records Firecrawl saving strategy", ok: progress.includes("Firecrawl 省额度策略") },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F10 verification failed.");
  process.exit(1);
}
console.log("Local F10 verification passed. Real make test will run on remote after sync.");
