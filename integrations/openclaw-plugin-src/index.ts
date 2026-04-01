import { definePluginEntry, type OpenClawPluginApi } from "./api.js";
import {
  createMainWorkerTool,
  createRunOnceTool,
  createRunLoopTool,
  createHeartbeatTool,
  createExportCoreSubmissionsTool,
  createProcessTaskFileTool,
} from "./src/tools.js";

export default definePluginEntry({
  id: "social-crawler-agent",
  name: "Social Crawler Agent",
  description: "Runs social-data-crawler jobs from OpenClaw tools and worker triggers.",
  register(api: OpenClawPluginApi) {
    api.registerTool(createMainWorkerTool(api), { optional: true });
    api.registerTool(createHeartbeatTool(api), { optional: true });
    api.registerTool(createRunOnceTool(api), { optional: true });
    api.registerTool(createRunLoopTool(api), { optional: true });
    api.registerTool(createProcessTaskFileTool(api), { optional: true });
    api.registerTool(createExportCoreSubmissionsTool(api), { optional: true });
  },
});
