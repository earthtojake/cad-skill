import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

import { normalizeExplorerRootDir } from "../lib/cadDirectoryScanner.mjs";
import {
  normalizeExplorerDefaultFile,
  normalizeExplorerGithubUrl,
} from "../lib/explorerConfig.mjs";

const EXPLORER_HOST = "127.0.0.1";
const DEFAULT_EXPLORER_PORT = 4178;
const parsedExplorerPort = Number.parseInt(process.env.EXPLORER_PORT || "", 10);
const EXPLORER_PORT = Number.isFinite(parsedExplorerPort) ? parsedExplorerPort : DEFAULT_EXPLORER_PORT;
const EXPLORER_ROOT_DIR = normalizeExplorerRootDir(process.env.EXPLORER_ROOT_DIR ?? "");
const EXPLORER_DEFAULT_FILE = normalizeExplorerDefaultFile(process.env.EXPLORER_DEFAULT_FILE ?? "");
const EXPLORER_GITHUB_URL = normalizeExplorerGithubUrl(process.env.EXPLORER_GITHUB_URL ?? "");
const SCRIPT_PATH = fileURLToPath(import.meta.url);
const EXPLORER_APP_ROOT = path.resolve(path.dirname(SCRIPT_PATH), "..");
const WORKSPACE_ROOT = path.resolve(process.env.EXPLORER_WORKSPACE_ROOT || process.env.INIT_CWD || process.cwd());
const HEALTH_PATH = "/__cad/catalog";
const HEALTH_URL = `http://${EXPLORER_HOST}:${EXPLORER_PORT}${HEALTH_PATH}`;
const EXPLORER_URL = `http://${EXPLORER_HOST}:${EXPLORER_PORT}`;
const PROBE_TIMEOUT_MS = 1000;
const STARTUP_TIMEOUT_MS = 30000;
const POLL_INTERVAL_MS = 250;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function probeExplorer() {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), PROBE_TIMEOUT_MS);

  try {
    const response = await fetch(HEALTH_URL, {
      signal: controller.signal,
      cache: "no-store",
    });
    if (!response.ok) {
      return { state: "unavailable" };
    }
    const catalog = await response.json();
    if (catalog?.schemaVersion !== 3 || !Array.isArray(catalog?.entries)) {
      return { state: "unavailable" };
    }
    const actualRootDir = normalizeExplorerRootDir(catalog?.root?.dir);
    if (actualRootDir !== EXPLORER_ROOT_DIR) {
      return { state: "wrong-root", actualRootDir };
    }
    const expectedRootName = EXPLORER_ROOT_DIR ? path.basename(EXPLORER_ROOT_DIR) : path.basename(WORKSPACE_ROOT);
    if (String(catalog?.root?.name || "") !== expectedRootName) {
      return {
        state: "wrong-root",
        actualRootDir,
        actualRootName: String(catalog?.root?.name || ""),
      };
    }
    const actualDefaultFile = normalizeExplorerDefaultFile(catalog?.config?.defaultFile);
    if (actualDefaultFile !== EXPLORER_DEFAULT_FILE) {
      return {
        state: "wrong-default-file",
        actualDefaultFile,
      };
    }
    const actualGithubUrl = normalizeExplorerGithubUrl(catalog?.config?.githubUrl);
    if (actualGithubUrl !== EXPLORER_GITHUB_URL) {
      return {
        state: "wrong-github-url",
        actualGithubUrl,
      };
    }
    return { state: "ready" };
  } catch {
    return { state: "unavailable" };
  } finally {
    clearTimeout(timeout);
  }
}

async function waitForExplorer() {
  const deadline = Date.now() + STARTUP_TIMEOUT_MS;
  while (Date.now() < deadline) {
    const probe = await probeExplorer();
    if (probe.state === "ready") {
      return true;
    }
    await sleep(POLL_INTERVAL_MS);
  }
  return false;
}

async function main() {
  const initialProbe = await probeExplorer();
  if (initialProbe.state === "ready") {
    console.log(`CAD Explorer is already running at ${EXPLORER_URL}`);
    return;
  }

  const viteCommand = path.join(EXPLORER_APP_ROOT, "node_modules", ".bin", process.platform === "win32" ? "vite.cmd" : "vite");

  if (["wrong-root", "wrong-default-file", "wrong-github-url"].includes(initialProbe.state)) {
    if (initialProbe.state === "wrong-default-file") {
      const actual = initialProbe.actualDefaultFile || "(unset)";
      const expected = EXPLORER_DEFAULT_FILE || "(unset)";
      console.log(`CAD Explorer is running at ${EXPLORER_URL} with default file ${actual}; restarting with default file ${expected}.`);
    }
    if (initialProbe.state === "wrong-github-url") {
      const actual = initialProbe.actualGithubUrl || "(unset)";
      console.log(`CAD Explorer is running at ${EXPLORER_URL} with GitHub URL ${actual}; restarting with GitHub URL ${EXPLORER_GITHUB_URL}.`);
    }
    const actual = initialProbe.actualRootDir || initialProbe.actualRootName || "(workspace root)";
    const expected = EXPLORER_ROOT_DIR || path.basename(WORKSPACE_ROOT) || "(workspace root)";
    if (initialProbe.state === "wrong-root") {
      console.log(`CAD Explorer is running at ${EXPLORER_URL} with root ${actual}; restarting with root ${expected}.`);
    }
    await new Promise((resolve) => {
      const child = spawn(process.execPath, [path.join(EXPLORER_APP_ROOT, "scripts", "stop-dev-server.mjs")], {
        cwd: EXPLORER_APP_ROOT,
        env: {
          ...process.env,
          EXPLORER_PORT: String(EXPLORER_PORT),
        },
        stdio: "inherit",
      });
      child.on("exit", resolve);
      child.on("error", resolve);
    });
  }

  console.log(`Starting CAD Explorer dev server at ${EXPLORER_URL} for ${EXPLORER_ROOT_DIR || WORKSPACE_ROOT}`);
  const child = spawn(viteCommand, ["dev", "--config", path.join(EXPLORER_APP_ROOT, "vite.config.mjs")], {
    cwd: WORKSPACE_ROOT,
    detached: true,
    env: {
      ...process.env,
      EXPLORER_PORT: String(EXPLORER_PORT),
      EXPLORER_ROOT_DIR,
    },
    stdio: "ignore",
  });
  child.unref();

  if (await waitForExplorer()) {
    console.log(`CAD Explorer is ready at ${EXPLORER_URL}`);
    return;
  }

  console.error(`CAD Explorer did not become ready at ${HEALTH_URL} within ${STARTUP_TIMEOUT_MS}ms.`);
  process.exitCode = 1;
}

await main();
