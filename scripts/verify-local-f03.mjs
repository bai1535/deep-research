#!/usr/bin/env node
// Local-mirror verification for F03: response_parser smart-quote fix.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const parser = fs.readFileSync(path.join(root, "src/deep_research/response_parser.py"), "utf8");
const checks = [
  {
    name: "response_parser.py has _normalize_smart_quotes",
    ok: parser.includes("_normalize_smart_quotes"),
  },
  {
    name: "parse_json_response calls quote normalization",
    ok: parser.includes("raw = _normalize_smart_quotes(raw)"),
  },
  {
    name: "tests/test_response_parser.py exists",
    ok: fs.existsSync(path.join(root, "tests/test_response_parser.py")),
  },
  {
    name: "parser test covers curly double quotes",
    ok: fs.readFileSync(path.join(root, "tests/test_response_parser.py"), "utf8").includes("“"),
  },
  {
    name: "PROGRESS.md records parser fix",
    ok: fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8").includes("解析器引号修复"),
  },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F03 verification failed.");
  process.exit(1);
}
console.log("Local F03 verification passed. Real make test will run on remote after sync.");
