#!/usr/bin/env node
// Local-mirror verification for F14: candidate answer verification loop.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const cv = fs.readFileSync(path.join(root, "src/deep_research/candidate_verifier.py"), "utf8");
const syn = fs.readFileSync(path.join(root, "src/deep_research/crews/synthesis_crew.py"), "utf8");
const progress = fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8");
const crewArch = fs.readFileSync(path.join(root, "src/deep_research/crews/ARCHITECTURE.md"), "utf8");
const testCv = fs.existsSync(path.join(root, "tests/test_candidate_verifier.py"));

const checks = [
  { name: "candidate_verifier.py defines verifier/format", ok: cv.includes("class CandidateVerifier") && cv.includes("def format_candidate_verification") },
  { name: "candidate verifier gates by suitable types", ok: cv.includes("SUITABLE_TYPES") && cv.includes('"entity_fact"') && cv.includes('"multi_hop_clue"') && cv.includes('"historical_archive"') },
  { name: "synthesis_crew runs candidate verifier", ok: syn.includes("CandidateVerifier") && syn.includes("verifier.verify(question, cards, verified)") },
  { name: "candidate result written to evidence", ok: syn.includes('"candidate_verification": candidate_result') },
  { name: "final_answer can use verified candidate", ok: syn.includes("final_candidate") && syn.includes("final_answer =") },
  { name: "crews ARCHITECTURE records candidate verification", ok: crewArch.includes("Candidate Verification") },
  { name: "PROGRESS.md records candidate verification", ok: progress.includes("候选答案验证循环") },
  { name: "candidate verifier tests exist", ok: testCv },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local F14 verification failed.");
  process.exit(1);
}
console.log("Local F14 verification passed. Real make test will run on remote after sync.");
