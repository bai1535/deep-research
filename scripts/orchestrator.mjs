#!/usr/bin/env node
/**
 * Orchestrator for the code-generation skill.
 *
 * Turns "open a project + give a requirement" into a guided, enforced pipeline:
 *
 *   scan   -> generate/update the project map (AGENTS.md, ARCHITECTURE.md,
 *             PROGRESS.md, DECISIONS.md, features.json, harness.config.json)
 *   map    -> show the current map/readiness status
 *   intake -> create spec.md + sprint-contract.md from a raw requirement
 *
 * The actual thinking is still done by the three agents; this script ensures the
 * right artifacts exist at the right time so the agents are not guessing.
 *
 * Usage:
 *   node scripts/orchestrator.mjs scan
 *   node scripts/orchestrator.mjs map
 *   node scripts/orchestrator.mjs intake "用 Web Audio API 做一个浏览器端 DAW"
 */

import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import process from "node:process";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SKILL_ROOT = path.resolve(__dirname, "..");
const HARNESS = path.join(SKILL_ROOT, "scripts", "harness.mjs");

function log(msg) {
  process.stderr.write(msg + "\n");
}

function runHarness(args, cwd) {
  const result = spawnSync(process.execPath, [HARNESS, ...args], {
    cwd,
    encoding: "utf8",
  });
  if (result.stdout) process.stdout.write(result.stdout);
  if (result.stderr) process.stderr.write(result.stderr);
  return result.status === 0;
}

function ensureFile(filePath, content) {
  if (fs.existsSync(filePath)) {
    log(`EXISTS: ${filePath}`);
    return false;
  }
  fs.writeFileSync(filePath, content, "utf8");
  log(`CREATED: ${filePath}`);
  return true;
}

function detectProject(cwd) {
  const info = {
    packageManager: null,
    testCommand: "",
    buildCommand: "",
    startCommand: "",
    hasGit: fs.existsSync(path.join(cwd, ".git")),
  };
  if (fs.existsSync(path.join(cwd, "package.json"))) {
    info.packageManager = "npm";
    info.testCommand = "npm test";
    info.buildCommand = "npm run build";
    info.startCommand = "npm start";
  } else if (fs.existsSync(path.join(cwd, "pyproject.toml"))) {
    info.packageManager = "python";
    info.testCommand = "pytest";
    info.buildCommand = "";
    info.startCommand = "";
  } else if (fs.existsSync(path.join(cwd, "requirements.txt"))) {
    info.packageManager = "python";
    info.testCommand = "pytest";
    info.buildCommand = "";
    info.startCommand = "";
  } else if (fs.existsSync(path.join(cwd, "go.mod"))) {
    info.packageManager = "go";
    info.testCommand = "go test ./...";
    info.buildCommand = "go build ./...";
    info.startCommand = "go run .";
  }
  return info;
}

function configContent(info) {
  return JSON.stringify(
    {
      feature_list: "features.json",
      progress: "PROGRESS.md",
      decisions: "DECISIONS.md",
      commands: {
        setup: info.packageManager === "npm" ? "npm install" : "",
        build: info.buildCommand,
        test: info.testCommand,
        start: info.startCommand,
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
    },
    null,
    2
  ) + "\n";
}

function agentsMdContent(info) {
  return `# AGENTS.md

## 项目概览
（待 Planner 根据需求补充）

## 快速开始
- 安装：\`${info.packageManager === "npm" ? "npm install" : "见项目文档"}\`
- 测试：\`${info.testCommand || "见项目文档"}\`
- 构建：\`${info.buildCommand || "见项目文档"}\`
- 启动：\`${info.startCommand || "见项目文档"}\`

## 硬约束
（待补充，最多 15 条）

## 专题文档
- 架构说明：\`ARCHITECTURE.md\`
- 进度：\`PROGRESS.md\`
- 设计决策：\`DECISIONS.md\`
`;
}

function architectureMdContent() {
  return `# Architecture

（待 Planner 补充高层技术设计；不要在这里写微观实现细节。）

## 模块
- （待补充）

## 关键接口
- （待补充）

## 约束
- （待补充）
`;
}

function progressMdContent() {
  return `# 项目进度

## 当前状态
- 最新 commit: （待补充）
- 测试状态: （待补充）

## 已完成
- （待补充）

## 进行中
- （待补充）

## 下一步
1. （待补充）
`;
}

function decisionsMdContent() {
  return `# 设计决策

（记录重要决策：选了什么、为什么、否决了什么。）
`;
}

function specMdContent(requirement) {
  return `# 产品规格

## 原始需求
${requirement}

## 产品概述
（待 Planner 补充）

## 目标用户与核心场景
（待 Planner 补充）

## 范围
（大胆设定范围；待 Planner 补充）

## 成功标准
（待 Planner 补充）

## 高层技术设计
（只写模块/架构/关键接口，不深入微观实现；待 Planner 补充）

## 约束与假设
（待 Planner 补充）

## 待确认问题
（待 Planner 补充）

## 建议 sprint 切分
（待 Planner 补充）
`;
}

function sprintContractMdContent() {
  return `# Sprint Contract

## Sprint / Feature
- Feature ID: （待分配）
- Goal: （待补充）

## 范围（In Scope）
- （待补充）

## 排除项（Out of Scope）
- （待补充）

## 验收标准（Definition of Done）
- [ ] \`node scripts/harness.mjs verify <ID>\` 通过
- [ ] 端到端流程通过
- [ ] 构建通过
- [ ] 所有测试通过

## 验证命令
- （待补充）

## 风险 / 已知问题
- （待补充）
`;
}

function cmdScan(cwd) {
  const info = detectProject(cwd);
  log(`Scanning project: ${cwd}`);
  log(`Detected: ${info.packageManager ?? "unknown"}${info.hasGit ? ", git" : ""}`);

  ensureFile(path.join(cwd, "harness.config.json"), configContent(info));
  const featPath = path.join(cwd, "features.json");
  if (!fs.existsSync(featPath)) {
    runHarness(["init"], cwd);
  } else {
    log(`EXISTS: features.json`);
  }
  ensureFile(path.join(cwd, "AGENTS.md"), agentsMdContent(info));
  ensureFile(path.join(cwd, "ARCHITECTURE.md"), architectureMdContent());
  ensureFile(path.join(cwd, "PROGRESS.md"), progressMdContent());
  ensureFile(path.join(cwd, "DECISIONS.md"), decisionsMdContent());

  log("Scan complete. Run `node scripts/orchestrator.mjs map` to see readiness.");
  return 0;
}

function cmdMap(cwd) {
  const required = [
    "harness.config.json",
    "features.json",
    "AGENTS.md",
    "ARCHITECTURE.md",
    "PROGRESS.md",
    "DECISIONS.md",
  ];
  let ok = true;
  for (const rel of required) {
    const exists = fs.existsSync(path.join(cwd, rel));
    console.log(`[${exists ? "x" : " "}] ${rel}`);
    ok = ok && exists;
  }
  const cfgPath = path.join(cwd, "harness.config.json");
  if (fs.existsSync(cfgPath)) {
    try {
      const cfg = JSON.parse(fs.readFileSync(cfgPath, "utf8"));
      for (const name of ["setup", "build", "test", "start"]) {
        const cmd = cfg.commands?.[name] ?? "";
        console.log(`[${cmd ? "x" : " "}] command: ${name} = ${cmd || "(not configured)"}`);
        ok = ok && Boolean(cmd);
      }
    } catch {
      ok = false;
    }
  }
  console.log("Map:", ok ? "READY" : "INCOMPLETE");
  return ok ? 0 : 1;
}

function cmdIntake(requirement, cwd) {
  if (!requirement) {
    log("ERROR: missing requirement. Usage: node scripts/orchestrator.mjs intake \"...\"");
    return 2;
  }
  ensureFile(path.join(cwd, "spec.md"), specMdContent(requirement));
  ensureFile(path.join(cwd, "sprint-contract.md"), sprintContractMdContent());
  log("Intake complete.");
  log("Next: Planner reads spec.md and fills it; then Generator/Evaluator negotiate sprint contracts.");
  return 0;
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
  const requirement = argv.slice(1).join(" ").trim();
  if (!fs.existsSync(cwd) || !fs.statSync(cwd).isDirectory()) {
    log(`ERROR: bad --cwd: ${cwd}`);
    process.exit(2);
  }
  switch (command) {
    case "scan":
      process.exit(cmdScan(cwd));
      break;
    case "map":
      process.exit(cmdMap(cwd));
      break;
    case "intake":
      process.exit(cmdIntake(requirement, cwd));
      break;
    default:
      console.error("Unknown command:", command ?? "(none)");
      console.error("Available: scan, map, intake");
      process.exit(2);
  }
}

main();
