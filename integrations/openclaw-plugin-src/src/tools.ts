import path from "node:path";
import { spawn } from "node:child_process";
import { Type } from "@sinclair/typebox";
import type { OpenClawPluginApi } from "../api.js";

const MAX_STDOUT_BYTES = 10 * 1024 * 1024; // 10 MB
const PROCESS_TIMEOUT_MS = 10 * 60 * 1000; // 10 minutes

// Whitelist of environment variables passed to Python subprocess
const ENV_PASSTHROUGH_KEYS = new Set([
  "PATH", "HOME", "USERPROFILE", "TEMP", "TMP", "TMPDIR",
  "LANG", "LC_ALL", "LC_CTYPE",
  "PYTHONPATH", "PYTHONIOENCODING", "VIRTUAL_ENV",
  "OPENCLAW_CONFIG_PATH", "OPENCLAW_GATEWAY_TOKEN",
  "OPENCLAW_GATEWAY_BASE_URL", "OPENCLAW_ENRICH_MODE",
  "OPENCLAW_ENRICH_MODEL", "OPENCLAW_UPSTREAM_MODEL",
  "SYSTEMROOT", "COMSPEC", // Windows essentials
]);

type PluginConfig = {
  secretRef?: {
    source?: string;
    provider?: string;
    id?: string;
  };
  crawlerRoot?: string;
  pythonBin?: string;
  platformBaseUrl?: string;
  platformToken?: string;
  minerId?: string;
  outputRoot?: string;
  defaultBackend?: string;
  awpWalletBin?: string;
  awpWalletToken?: string;
  awpWalletTokenRef?: {
    source?: string;
    provider?: string;
    id?: string;
  };
  workerStateRoot?: string;
  workerMaxParallel?: number;
  datasetRefreshSeconds?: number;
  discoveryMaxPages?: number;
  discoveryMaxDepth?: number;
  authRetryIntervalSeconds?: number;
};

function resolvePluginConfig(api: OpenClawPluginApi): Required<Pick<PluginConfig, "crawlerRoot" | "platformBaseUrl" | "minerId">> & PluginConfig {
  const cfg = (api.pluginConfig ?? {}) as PluginConfig;
  if (!cfg.crawlerRoot?.trim()) {
    throw new Error("plugins.entries.social-crawler-agent.config.crawlerRoot is required");
  }
  if (!cfg.platformBaseUrl?.trim()) {
    throw new Error("plugins.entries.social-crawler-agent.config.platformBaseUrl is required");
  }
  if (!cfg.minerId?.trim()) {
    throw new Error("plugins.entries.social-crawler-agent.config.minerId is required");
  }
  return {
    ...cfg,
    crawlerRoot: cfg.crawlerRoot,
    platformBaseUrl: cfg.platformBaseUrl,
    minerId: cfg.minerId,
  };
}

function buildSafeEnv(cfg: Required<Pick<PluginConfig, "crawlerRoot" | "platformBaseUrl" | "minerId">> & PluginConfig, pythonBin: string): NodeJS.ProcessEnv {
  // Start from whitelisted process.env keys only
  const safeEnv: Record<string, string> = {};
  for (const key of ENV_PASSTHROUGH_KEYS) {
    if (process.env[key]) {
      safeEnv[key] = process.env[key]!;
    }
  }
  // Add plugin-specific variables
  Object.assign(safeEnv, {
    SOCIAL_CRAWLER_ROOT: cfg.crawlerRoot,
    PLATFORM_BASE_URL: cfg.platformBaseUrl,
    PLATFORM_TOKEN: cfg.platformToken ?? "",
    MINER_ID: cfg.minerId,
    CRAWLER_OUTPUT_ROOT: cfg.outputRoot ?? path.join(cfg.crawlerRoot, "output", "agent-runs"),
    DEFAULT_BACKEND: cfg.defaultBackend ?? "",
    AWP_WALLET_BIN: cfg.awpWalletBin ?? "awp-wallet",
    AWP_WALLET_TOKEN: cfg.awpWalletToken ?? "",
    AWP_WALLET_TOKEN_SECRET_REF: cfg.awpWalletTokenRef ? JSON.stringify(cfg.awpWalletTokenRef) : "",
    PLUGIN_PYTHON_BIN: pythonBin,
    WORKER_STATE_ROOT: cfg.workerStateRoot ?? path.join(cfg.crawlerRoot, "output", "agent-runs", "_worker_state"),
    WORKER_MAX_PARALLEL: String(cfg.workerMaxParallel ?? 3),
    DATASET_REFRESH_SECONDS: String(cfg.datasetRefreshSeconds ?? 900),
    DISCOVERY_MAX_PAGES: String(cfg.discoveryMaxPages ?? 25),
    DISCOVERY_MAX_DEPTH: String(cfg.discoveryMaxDepth ?? 1),
    AUTH_RETRY_INTERVAL_SECONDS: String(cfg.authRetryIntervalSeconds ?? 300),
  });
  return safeEnv;
}

function validatePath(filePath: string, rootDir: string, label: string): string {
  const resolved = path.resolve(rootDir, filePath);
  const normalizedRoot = path.resolve(rootDir);
  if (!resolved.startsWith(normalizedRoot + path.sep) && resolved !== normalizedRoot) {
    throw new Error(`${label} must be within the plugin root directory`);
  }
  return resolved;
}

async function runPythonTool(
  api: OpenClawPluginApi,
  command: string,
  extraArgs: string[] = [],
): Promise<string> {
  const cfg = resolvePluginConfig(api);
  const pythonBin = cfg.pythonBin?.trim() || "python";
  const scriptPath = path.join(api.rootDir ?? ".", "scripts", "run_tool.py");
  const env = buildSafeEnv(cfg, pythonBin);

  return await new Promise((resolve, reject) => {
    const child = spawn(pythonBin, [scriptPath, command, ...extraArgs], {
      cwd: api.rootDir,
      env,
      stdio: ["ignore", "pipe", "pipe"],
    });

    let stdoutLen = 0;
    let stderrLen = 0;
    const stdoutChunks: Buffer[] = [];
    const stderrChunks: Buffer[] = [];

    child.stdout.on("data", (chunk: Buffer) => {
      stdoutLen += chunk.length;
      if (stdoutLen <= MAX_STDOUT_BYTES) {
        stdoutChunks.push(chunk);
      }
    });
    child.stderr.on("data", (chunk: Buffer) => {
      stderrLen += chunk.length;
      if (stderrLen <= MAX_STDOUT_BYTES) {
        stderrChunks.push(chunk);
      }
    });

    const timer = setTimeout(() => {
      child.kill("SIGTERM");
      reject(new Error(`python helper timed out after ${PROCESS_TIMEOUT_MS / 1000}s`));
    }, PROCESS_TIMEOUT_MS);

    child.on("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      const stdout = Buffer.concat(stdoutChunks).toString("utf-8");
      const stderr = Buffer.concat(stderrChunks).toString("utf-8");
      if (code === 0) {
        resolve(stdout.trim() || "ok");
        return;
      }
      reject(new Error(stderr.trim() || `python helper exited with code ${code}`));
    });
  });
}

export function createHeartbeatTool(api: OpenClawPluginApi) {
  return {
    name: "social_crawler_heartbeat",
    label: "Social Crawler Heartbeat",
    description: "Send one miner heartbeat to Platform Service using the configured crawler worker identity.",
    parameters: Type.Object({}),
    async execute() {
      const text = await runPythonTool(api, "heartbeat");
      return { content: [{ type: "text", text }] };
    },
  };
}

export function createRunOnceTool(api: OpenClawPluginApi) {
  return {
    name: "social_crawler_run_once",
    label: "Social Crawler Run Once",
    description: "Send heartbeat, claim one repeat-crawl or refresh task, execute social-data-crawler, and report the result.",
    parameters: Type.Object({}),
    async execute() {
      const text = await runPythonTool(api, "run-once");
      return { content: [{ type: "text", text }] };
    },
  };
}

export function createProcessTaskFileTool(api: OpenClawPluginApi) {
  return {
    name: "social_crawler_process_task_file",
    label: "Process Task File",
    description:
      "Process one refresh or repeat-crawl task payload JSON through crawl, report, and core submission export/submit. Useful when remote claim is unavailable.",
    parameters: Type.Object({
      taskType: Type.Union(
        [Type.Literal("refresh"), Type.Literal("repeat_crawl")],
        { description: "Platform task type." },
      ),
      taskPath: Type.String({ description: "Absolute or plugin-relative path to a task payload JSON file." }),
    }),
    async execute(_id: string, params: Record<string, unknown>) {
      const taskType = typeof params.taskType === "string" ? params.taskType : "";
      const taskPath = typeof params.taskPath === "string" ? params.taskPath : "";
      if (!taskType.trim() || !taskPath.trim()) {
        throw new Error("taskType and taskPath are required");
      }
      const rootDir = api.rootDir ?? ".";
      const safePath = validatePath(taskPath, rootDir, "taskPath");
      const text = await runPythonTool(api, "process-task-file", [taskType, safePath]);
      return { content: [{ type: "text", text }] };
    },
  };
}

export function createRunLoopTool(api: OpenClawPluginApi) {
  return {
    name: "social_crawler_run_loop",
    label: "Social Crawler Run Loop",
    description:
      "Start continuous mining: heartbeat, claim tasks, crawl, and report in a loop. Stops on interrupt or max iterations.",
    parameters: Type.Object({
      interval: Type.Optional(
        Type.Number({ description: "Seconds between iterations. Default 60.", default: 60 }),
      ),
      maxIterations: Type.Optional(
        Type.Number({ description: "Stop after N iterations. 0 = infinite. Default 0.", default: 0 }),
      ),
    }),
    async execute(_id: string, params: Record<string, unknown>) {
      const interval =
        typeof params.interval === "number" ? String(Math.max(10, params.interval)) : "60";
      const maxIter =
        typeof params.maxIterations === "number" ? String(params.maxIterations) : "0";
      const text = await runPythonTool(api, "run-loop", [interval, maxIter]);
      return { content: [{ type: "text", text }] };
    },
  };
}

export function createMainWorkerTool(api: OpenClawPluginApi) {
  return {
    name: "social_crawler_worker",
    label: "Social Crawler Worker",
    description:
      "Run the single-entry autonomous worker: heartbeat, task discovery/claim, crawl orchestration, auth handling, report, submit, and resume.",
    parameters: Type.Object({
      interval: Type.Optional(
        Type.Number({ description: "Seconds between iterations. Default 60.", default: 60 }),
      ),
      maxIterations: Type.Optional(
        Type.Number({ description: "Stop after N iterations. 1 = single cycle, 0 = infinite. Default 1.", default: 1 }),
      ),
    }),
    async execute(_id: string, params: Record<string, unknown>) {
      const interval =
        typeof params.interval === "number" ? String(Math.max(10, params.interval)) : "60";
      const maxIter =
        typeof params.maxIterations === "number" ? String(params.maxIterations) : "1";
      const text = await runPythonTool(api, "run-worker", [interval, maxIter]);
      return { content: [{ type: "text", text }] };
    },
  };
}

export function createExportCoreSubmissionsTool(api: OpenClawPluginApi) {
  return {
    name: "social_crawler_export_core_submissions",
    label: "Export Core Submissions",
    description: "Convert crawler records.jsonl into Platform Service Core submission payload JSON.",
    parameters: Type.Object({
      inputPath: Type.String({ description: "Absolute or plugin-relative path to records.jsonl." }),
      outputPath: Type.String({ description: "Absolute or plugin-relative path for the exported JSON." }),
      datasetId: Type.String({ description: "Platform Service dataset id." }),
    }),
    async execute(_id: string, params: Record<string, unknown>) {
      const inputPath = typeof params.inputPath === "string" ? params.inputPath : "";
      const outputPath = typeof params.outputPath === "string" ? params.outputPath : "";
      const datasetId = typeof params.datasetId === "string" ? params.datasetId : "";
      if (!inputPath.trim() || !outputPath.trim() || !datasetId.trim()) {
        throw new Error("inputPath, outputPath, and datasetId are required");
      }
      const rootDir = api.rootDir ?? ".";
      const safeInput = validatePath(inputPath, rootDir, "inputPath");
      const safeOutput = validatePath(outputPath, rootDir, "outputPath");
      const text = await runPythonTool(api, "export-core-submissions", [safeInput, safeOutput, datasetId]);
      return { content: [{ type: "text", text }] };
    },
  };
}
