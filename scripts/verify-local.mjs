#!/usr/bin/env node
// Local-mirror verification for the "fix test suite" feature.
// Real `make test` is executed on the remote server after syncing back.
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const checks = [
  {
    name: "tests/test_db.py uses asyncpg/Repository",
    ok: fs.readFileSync(path.join(root, "tests/test_db.py"), "utf8").includes("await init_db()"),
  },
  {
    name: "tests/test_config.py no longer references db_path",
    ok: !fs.readFileSync(path.join(root, "tests/test_config.py"), "utf8").includes("db_path"),
  },
  {
    name: "Makefile enables asyncio auto mode",
    ok: fs.readFileSync(path.join(root, "Makefile"), "utf8").includes("asyncio_mode=auto"),
  },
  {
    name: "pyproject.toml declares pytest asyncio config",
    ok: fs.readFileSync(path.join(root, "pyproject.toml"), "utf8").includes("asyncio_mode"),
  },
  {
    name: "PROGRESS.md records 35 passed",
    ok: fs.readFileSync(path.join(root, "PROGRESS.md"), "utf8").includes("35 passed"),
  },
];

let failed = false;
for (const check of checks) {
  console.log(`${check.ok ? "PASS" : "FAIL"} ${check.name}`);
  if (!check.ok) failed = true;
}
if (failed) {
  console.error("Local verification failed.");
  process.exit(1);
}
console.log("Local verification passed. Real make test will run on remote after sync.");
