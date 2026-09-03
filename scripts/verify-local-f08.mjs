#!/usr/bin/env node
// Local-mirror verification for F08: Wikipedia/Wikidata tools + final answer extractor.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const knowledge = fs.readFileSync(path.join(root, "src/deep_research/tools/knowledge.py"), "utf8");
const toolsInit = fs.readFileSync(path.join(root, "src/deep_research/tools/__init__.py"), "utf8");
const registry = fs.readFileSync(path.join(root, "src/deep_research/agents/registry.py"), "utf8");
const synthesis = fs.readFileSync(path.join(root, "src/deep_research/crews/synthesis_crew.py"), "utf8");
const finalAnswer = fs.readFileSync(path.join(root, "src/deep_research/final_answer.py"), "utf8");
const evalScript = fs.readFileSync(path.join(root, "scripts/eval_benchmarks.py"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");
const testKnowledge = fs.existsSync(path.join(root, "tests/test_knowledge_tools.py"));
const testFinal = fs.existsSync(path.join(root, "tests/test_final_answer.py"));

const checks = [
  { name: "knowledge.py defines WikipediaSearchTool", ok: knowledge.includes("class WikipediaSearchTool") },
  { name: "knowledge.py defines WikidataLookupTool", ok: knowledge.includes("class WikidataLookupTool") },
  { name: "tools/__init__.py imports knowledge tools", ok: toolsInit.includes("from .knowledge import WikipediaSearchTool, WikidataLookupTool") },
  { name: "tools/__init__.py registers knowledge tools", ok: toolsInit.includes("WikipediaSearchTool(), WikidataLookupTool()") },
  { name: "registry.py injects Wikipedia/Wikidata strategy", ok: registry.includes("wikipedia_search / wikidata_lookup") },
  { name: "synthesis_crew.py extracts final answer", ok: synthesis.includes("extract_final_answer(report_text)") && synthesis.includes('"final_answer": final_answer') },
  { name: "final_answer.py exists", ok: finalAnswer.includes("def extract_final_answer") },
  { name: "eval_benchmarks.py records final_answer", ok: evalScript.includes("final_answer") },
  { name: "tests for knowledge tools exist", ok: testKnowledge },
  { name: "tests for final answer extractor exist", ok: testFinal },
  { name: "PROGRESS.md records F08", ok: progress.includes("Wikipedia/Wikidata") || progress.includes("最终答案抽取器") },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F08 verification failed.");
  process.exit(1);
}
console.log("Local F08 verification passed. Real make test will run on remote after sync.");
