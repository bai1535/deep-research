#!/usr/bin/env node
// Local-mirror verification for F05: search strategy optimization.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const search = fs.readFileSync(path.join(root, "src/deep_research/tools/search.py"), "utf8");
const registry = fs.readFileSync(path.join(root, "src/deep_research/agents/registry.py"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");

const checks = [
  {
    name: "search.py has English-market Bing params",
    ok: search.includes("mkt=en-US") && search.includes("ensearch=1"),
  },
  {
    name: "registry.py has SEARCH_STRATEGY_GUIDE",
    ok: registry.includes("SEARCH_STRATEGY_GUIDE"),
  },
  {
    name: "create_agent injects search strategy into search-tool agents",
    ok: registry.includes("SEARCH_STRATEGY_GUIDE") && registry.includes("for t in tools"),
  },
  {
    name: "PROGRESS.md records search strategy optimization",
    ok: progress.includes("搜索策略优化"),
  },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F05 verification failed.");
  process.exit(1);
}
console.log("Local F05 verification passed.");
