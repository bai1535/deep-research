#!/usr/bin/env node
/**
 * Harness CLI for the code-generation skill (Node version).
 *
 * Enforces the workflow outside the model's context:
 * - feature list state machine (not_started / active / blocked / passing)
 * - WIP=1 (only one active feature at a time)
 * - passing only via successful verification command
 * - exit checklist (build/test/progress/clean/start)
 * - fresh-session doctor checks
 *
 * Usage:
 *   node scripts/harness.mjs init
 *   node scripts/harness.mjs features
 *   node scripts/harness.mjs start F01
 *   node scripts/harness.mjs verify F01
 *   node scripts/harness.mjs pass F01
 *   node scripts/harness.mjs block F01 --reason "waiting for API key"
 *   node scripts/harness.mjs validate
 *   node scripts/harness.mjs exit-check
 *   node scripts/harness.mjs doctor
 */

import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import process from "node:process";

const CONFIG_NAME = "harness.config.json";
const DEFAULT_CONFIG = {
  feature_list: "features.json",
  progress: "PROGRESS.md",
  decisions: "DECISIONS.md",
  commands: {
    setup: "",
    build: "",
    test: "",
    start: "",
  },
  exit_check: {
    debug_patterns: [
      "console\\.log\\s*\\(",
      "debugger\\s*;?",
      "TODO",
      "FIXME",
    ],
    scan_extensions: [
      ".js", ".jsx", ".ts", ".tsx", ".py", ".go", ".rs",
      ".java", ".rb", ".php", ".cs", ".c", ".cpp", ".h", ".hpp",
    ],
    skip_dirs: [
      ".git", "node_modules", "dist", "build", "coverage",
      ".venv", "venv", "__pycache__", ".next", ".nuxt",
    ],
  },
};

const ALLOWED_STATES = new Set(["not_started", "active", "blocked", "passing"]);

function log(msg) {
  process.stderr.write(msg + "\n");
}

function loadConfig(cwd) {
  const cfgPath = path.join(cwd, CONFIG_NAME);
  let userCfg = {};
  if (fs.existsSync(cfgPath)) {
    try {
      userCfg = JSON.parse(fs.readFileSync(cfgPath, "utf8"));
    } catch (err) {
      log(`ERROR: ${CONFIG_NAME} is not valid JSON: ${err.message}`);
      process.exit(2);
    }
  }
  const merged = structuredClone(DEFAULT_CONFIG);
  Object.assign(merged, userCfg);
  Object.assign(merged.commands, userCfg.commands ?? {});
  Object.assign(merged.exit_check, userCfg.exit_check ?? {});
  return merged;
}

function loadFeatures(cwd, cfg) {
  const filePath = path.join(cwd, cfg.feature_list);
  if (!fs.existsSync(filePath)) return null;
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch (err) {
    log(`ERROR: ${filePath} is not valid JSON: ${err.message}`);
    process.exit(2);
  }
}

function saveFeatures(cwd, cfg, data) {
  const filePath = path.join(cwd, cfg.feature_list);
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2) + "\n", "utf8");
}

function findFeature(data, id) {
  return (data.features ?? []).find((f) => f.id === id);
}

function requireFeatures(data) {
  if (!data) {
    log("ERROR: feature list not found. Run `harness.mjs init` first.");
    process.exit(1);
  }
}

function runCommand(cmd, cwd) {
  log(`$ ${cmd}`);
  return spawnSync(cmd, { cwd, shell: true, encoding: "utf8" });
}

function now() {
  return new Date().toISOString();
}

function cmdInit(args, cwd, cfg) {
  const filePath = path.join(cwd, cfg.feature_list);
  if (fs.existsSync(filePath)) {
    log(`ERROR: ${filePath} already exists. Refusing to overwrite.`);
    return 1;
  }
  saveFeatures(cwd, cfg, { features: [] });
  log(`Created ${filePath} with an empty feature list.`);
  return 0;
}

function cmdFeatures(args, cwd, cfg) {
  const data = loadFeatures(cwd, cfg);
  requireFeatures(data);
  const feats = data.features ?? [];
  if (feats.length === 0) {
    log("Feature list is empty.");
    return 0;
  }
  console.log("ID     STATE        BEHAVIOR                                                       VERIFICATION");
  console.log("-".repeat(140));
  for (const f of feats) {
    const behavior = (f.behavior ?? "").length > 60 ? f.behavior.slice(0, 57) + "..." : f.behavior ?? "";
    const verification = (f.verification ?? "").length > 40 ? f.verification.slice(0, 37) + "..." : f.verification ?? "";
    console.log(`${(f.id ?? "?").padEnd(6)} ${(f.state ?? "?").padEnd(12)} ${behavior.padEnd(60)} ${verification}`);
  }
  return 0;
}

function cmdStart(args, cwd, cfg) {
  const data = loadFeatures(cwd, cfg);
  requireFeatures(data);
  const feat = findFeature(data, args.id);
  if (!feat) {
    log(`ERROR: feature ${args.id} not found.`);
    return 1;
  }
  if (feat.state === "passing") {
    log(`ERROR: ${args.id} is already passing.`);
    return 1;
  }
  const active = (data.features ?? []).filter((f) => f.state === "active");
  if (active.length > 0 && active[0].id !== args.id) {
    log(`ERROR: WIP=1 violated. ${active[0].id} is already active.`);
    return 1;
  }
  feat.state = "active";
  feat.active_at = now();
  delete feat.blocked_reason;
  saveFeatures(cwd, cfg, data);
  log(`${args.id} -> active`);
  return 0;
}

function cmdBlock(args, cwd, cfg) {
  const data = loadFeatures(cwd, cfg);
  requireFeatures(data);
  const feat = findFeature(data, args.id);
  if (!feat) {
    log(`ERROR: feature ${args.id} not found.`);
    return 1;
  }
  if (feat.state !== "active") {
    log(`ERROR: only an active feature can be blocked (current: ${feat.state}).`);
    return 1;
  }
  feat.state = "blocked";
  feat.blocked_reason = args.reason || "no reason given";
  saveFeatures(cwd, cfg, data);
  log(`${args.id} -> blocked`);
  return 0;
}

function cmdVerify(args, cwd, cfg, applyPass = false) {
  const data = loadFeatures(cwd, cfg);
  requireFeatures(data);
  const feat = findFeature(data, args.id);
  if (!feat) {
    log(`ERROR: feature ${args.id} not found.`);
    return 1;
  }
  const verification = (feat.verification ?? "").trim();
  if (!verification) {
    log(`ERROR: ${args.id} has no verification command.`);
    return 1;
  }
  const result = runCommand(verification, cwd);
  if (result.stdout) process.stdout.write(result.stdout);
  if (result.stderr) process.stderr.write(result.stderr);
  if (result.status === 0) {
    log(`VERIFY OK: ${args.id}`);
    if (applyPass) {
      feat.state = "passing";
      feat.evidence = {
        verified_at: now(),
        command: verification,
        exit_code: 0,
      };
      delete feat.blocked_reason;
      saveFeatures(cwd, cfg, data);
      log(`${args.id} -> passing`);
    }
    return 0;
  }
  log(`VERIFY FAILED: ${args.id} (exit code ${result.status})`);
  return 1;
}

function cmdPass(args, cwd, cfg) {
  return cmdVerify(args, cwd, cfg, true);
}

function cmdValidate(args, cwd, cfg) {
  const data = loadFeatures(cwd, cfg);
  requireFeatures(data);
  const errors = [];
  const active = [];
  for (const feat of data.features ?? []) {
    const id = feat.id;
    if (!id) {
      errors.push("feature missing id");
      continue;
    }
    for (const field of ["behavior", "verification", "state"]) {
      if (!feat[field]) errors.push(`${id}: missing '${field}'`);
    }
    const state = feat.state;
    if (!ALLOWED_STATES.has(state)) errors.push(`${id}: invalid state '${state}'`);
    if (state === "active") active.push(id);
    if (state === "passing" && !feat.evidence) errors.push(`${id}: passing but no evidence`);
    if ((state === "not_started" || state === "blocked") && feat.evidence) {
      errors.push(`${id}: has evidence but is not passing`);
    }
  }
  if (active.length > 1) errors.push(`WIP=1 violated: multiple active features ${active.join(", ")}`);
  if (errors.length > 0) {
    for (const e of errors) log(`ERROR: ${e}`);
    return 1;
  }
  log("Validation OK.");
  return 0;
}

function scanDebugArtifacts(cwd, cfg) {
  const patterns = (cfg.exit_check.debug_patterns ?? []).map((p) => new RegExp(p));
  const extensions = new Set(cfg.exit_check.scan_extensions ?? []);
  const skipDirs = new Set(cfg.exit_check.skip_dirs ?? []);
  const hits = [];
  function walk(dir) {
    let entries;
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      if (entry.isDirectory()) {
        if (skipDirs.has(entry.name) || entry.name.startsWith(".")) continue;
        walk(path.join(dir, entry.name));
      } else if (entry.isFile()) {
        const ext = path.extname(entry.name);
        if (!extensions.has(ext)) continue;
        const filePath = path.join(dir, entry.name);
        let text;
        try {
          text = fs.readFileSync(filePath, "utf8");
        } catch {
          continue;
        }
        const lines = text.split(/\r?\n/);
        for (let i = 0; i < lines.length; i++) {
          if (patterns.some((re) => re.test(lines[i]))) {
            hits.push(`${path.relative(cwd, filePath)}:${i + 1}: ${lines[i].trim().slice(0, 120)}`);
          }
        }
      }
    }
  }
  walk(cwd);
  return hits;
}

function cmdExitCheck(args, cwd, cfg) {
  const failures = [];
  const data = loadFeatures(cwd, cfg);
  requireFeatures(data);

  for (const name of ["build", "test"]) {
    const cmd = (cfg.commands?.[name] ?? "").trim();
    if (!cmd) {
      log(`SKIP ${name}: no command configured`);
      continue;
    }
    const result = runCommand(cmd, cwd);
    if (result.stdout) process.stdout.write(result.stdout);
    if (result.stderr) process.stderr.write(result.stderr);
    if (result.status !== 0) {
      failures.push(`${name} failed (exit ${result.status})`);
    } else {
      log(`OK: ${name}`);
    }
  }

  for (const rel of [cfg.feature_list, cfg.progress, cfg.decisions]) {
    if (!fs.existsSync(path.join(cwd, rel))) {
      failures.push(`missing required file: ${rel}`);
    } else {
      log(`OK: ${rel} exists`);
    }
  }

  const hits = scanDebugArtifacts(cwd, cfg);
  if (hits.length > 0) {
    failures.push(`debug artifacts found (${hits.length}):`);
    for (const h of hits.slice(0, 20)) failures.push("  " + h);
  } else {
    log("OK: no debug artifacts found");
  }

  if (failures.length > 0) {
    log("EXIT CHECK FAILED:");
    for (const f of failures) log("  - " + f);
    return 1;
  }
  log("EXIT CHECK PASSED.");
  return 0;
}

function cmdDoctor(args, cwd, cfg) {
  let ok = true;
  for (const rel of [cfg.feature_list, cfg.progress, cfg.decisions, CONFIG_NAME]) {
    const exists = fs.existsSync(path.join(cwd, rel));
    console.log(`[${exists ? "x" : " "}] ${rel}`);
    ok = ok && exists;
  }
  const data = loadFeatures(cwd, cfg);
  if (!data) {
    console.log("[ ] feature list is valid JSON");
    ok = false;
  } else {
    console.log("[x] feature list is valid JSON");
    ok = cmdValidate(args, cwd, cfg) === 0 && ok;
  }
  for (const name of ["setup", "build", "test", "start"]) {
    const cmd = (cfg.commands?.[name] ?? "").trim();
    console.log(`[${cmd ? "x" : " "}] command: ${name} = ${cmd || "(not configured)"}`);
    ok = ok && Boolean(cmd);
  }
  console.log("Doctor:", ok ? "OK" : "INCOMPLETE");
  return ok ? 0 : 1;
}

function buildParser() {
  const commands = {
    init: { run: cmdInit },
    features: { run: cmdFeatures },
    start: { run: cmdStart, args: ["id"] },
    block: { run: cmdBlock, args: ["id"], options: [["--reason", "reason"]] },
    verify: { run: cmdVerify, args: ["id"] },
    pass: { run: cmdPass, args: ["id"] },
    validate: { run: cmdValidate },
    "exit-check": { run: cmdExitCheck },
    doctor: { run: cmdDoctor },
  };
  return { commands };
}

function main() {
  const argv = process.argv.slice(2);
  const cwdIndex = argv.indexOf("--cwd");
  let cwd = process.cwd();
  if (cwdIndex >= 0 && argv[cwdIndex + 1]) {
    cwd = path.resolve(argv[cwdIndex + 1]);
    argv.splice(cwdIndex, 2);
  }
  const command = argv[0];
  const parser = buildParser();
  const meta = parser.commands[command];
  if (!meta) {
    console.error(`Unknown command: ${command ?? "(none)"}`);
    console.error("Available: " + Object.keys(parser.commands).join(", "));
    process.exit(2);
  }
  const args = { id: undefined, reason: "" };
  if (meta.args) {
    args.id = argv[1];
    if (!args.id) {
      console.error(`Missing id for ${command}`);
      process.exit(2);
    }
  }
  if (meta.options) {
    for (const [flag, key] of meta.options) {
      const idx = argv.indexOf(flag);
      if (idx >= 0 && argv[idx + 1]) args[key] = argv[idx + 1];
    }
  }
  if (!fs.existsSync(cwd) || !fs.statSync(cwd).isDirectory()) {
    log(`ERROR: bad --cwd: ${cwd}`);
    process.exit(2);
  }
  const cfg = loadConfig(cwd);
  process.exit(meta.run(args, cwd, cfg));
}

main();
