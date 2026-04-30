import { execFileSync } from "node:child_process";

const EXPLORER_HOST = "127.0.0.1";
const DEFAULT_EXPLORER_PORT = 4178;
const parsedExplorerPort = Number.parseInt(process.env.EXPLORER_PORT || "", 10);
const EXPLORER_PORT = Number.isFinite(parsedExplorerPort) ? parsedExplorerPort : DEFAULT_EXPLORER_PORT;
const EXPLORER_URL = `http://${EXPLORER_HOST}:${EXPLORER_PORT}`;
const SHUTDOWN_TIMEOUT_MS = 5000;
const POLL_INTERVAL_MS = 200;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function run(command, args) {
  try {
    return execFileSync(command, args, {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    });
  } catch {
    return "";
  }
}

function parsePsRows() {
  if (process.platform === "win32") {
    return [];
  }

  return run("ps", ["-axo", "pid=,ppid=,command="])
    .split("\n")
    .map((line) => {
      const match = line.trim().match(/^(\d+)\s+(\d+)\s+(.+)$/);
      if (!match) {
        return null;
      }
      return {
        pid: Number(match[1]),
        ppid: Number(match[2]),
        command: match[3],
      };
    })
    .filter(Boolean);
}

function descendantsOf(rows, rootPids) {
  const descendants = new Set();
  let added = true;
  while (added) {
    added = false;
    for (const row of rows) {
      if (rootPids.has(row.ppid) || descendants.has(row.ppid)) {
        if (!descendants.has(row.pid)) {
          descendants.add(row.pid);
          added = true;
        }
      }
    }
  }
  return descendants;
}

function findListeningPids() {
  if (process.platform === "win32") {
    return new Set();
  }

  return new Set(
    run("lsof", ["-nP", `-iTCP:${EXPLORER_PORT}`, "-sTCP:LISTEN", "-t"])
      .split(/\s+/)
      .map((value) => Number(value))
      .filter(Number.isInteger),
  );
}

function findExplorerPids() {
  const rows = parsePsRows();
  const listeningPids = findListeningPids();
  const candidates = new Set(listeningPids);

  for (const row of rows) {
    if (candidates.has(row.pid)) {
      const parent = rows.find((candidate) => candidate.pid === row.ppid);
      if (parent?.command.includes("npm run dev")) {
        candidates.add(parent.pid);
      }
    }
    if (
      row.command.includes("vite")
      && row.command.includes("cad/explorer")
      && row.command.includes(`--config`)
    ) {
      candidates.add(row.pid);
    }
  }

  for (const pid of descendantsOf(rows, candidates)) {
    candidates.add(pid);
  }

  candidates.delete(process.pid);
  return [...candidates].sort((left, right) => right - left);
}

function isRunning(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

async function waitForExit(pids) {
  const deadline = Date.now() + SHUTDOWN_TIMEOUT_MS;
  while (Date.now() < deadline) {
    if (pids.every((pid) => !isRunning(pid))) {
      return true;
    }
    await sleep(POLL_INTERVAL_MS);
  }
  return pids.every((pid) => !isRunning(pid));
}

async function main() {
  const pids = findExplorerPids();
  if (pids.length === 0) {
    console.log(`CAD Explorer is not running at ${EXPLORER_URL}`);
    return;
  }

  for (const pid of pids) {
    try {
      process.kill(pid, "SIGTERM");
    } catch {
      // The process may have already exited.
    }
  }

  if (!(await waitForExit(pids))) {
    for (const pid of pids) {
      if (isRunning(pid)) {
        try {
          process.kill(pid, "SIGKILL");
        } catch {
          // The process may have exited after the final check.
        }
      }
    }
  }

  console.log(`Stopped CAD Explorer dev server at ${EXPLORER_URL}`);
  console.log(`Stopped PIDs: ${pids.join(", ")}`);
}

await main();
