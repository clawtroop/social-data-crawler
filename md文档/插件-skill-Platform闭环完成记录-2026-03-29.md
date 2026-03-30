# 插件 / skill / Platform Service 闭环完成记录 - 2026-03-29

## 1. 本轮完成范围

本轮按“插件编排层 + skill 抓取层”的方案完成了以下本地能力：

- `openclaw-social-crawler-plugin` 可直接驱动 `social-data-crawler`
- 插件可处理 `heartbeat -> claim -> crawl -> report -> export`
- 当远端 `claim` 不稳定时，插件可直接消费任务 payload 文件，走同一条执行链
- 插件已兼容当前 Platform Service 的两个真实特性：
  - `report` 有时直接生成 `submission_id`
  - `submission_id` 刚返回时，`GET /api/core/v1/submissions/{id}` 可能短暂 `404`

## 2. 本轮关键代码变更

插件仓库：

- [agent_runtime.py](d:/kaifa/clawtroop/openclaw-social-crawler-plugin/scripts/agent_runtime.py)
- [run_tool.py](d:/kaifa/clawtroop/openclaw-social-crawler-plugin/scripts/run_tool.py)
- [tools.ts](d:/kaifa/clawtroop/openclaw-social-crawler-plugin/src/tools.ts)
- [index.ts](d:/kaifa/clawtroop/openclaw-social-crawler-plugin/index.ts)
- [openclaw.plugin.json](d:/kaifa/clawtroop/openclaw-social-crawler-plugin/openclaw.plugin.json)
- [README.md](d:/kaifa/clawtroop/openclaw-social-crawler-plugin/README.md)

新增/补强能力：

- URL 平台识别与任务映射
- `process-task-file` 兜底入口
- `platformToken` 改为可空，兼容 `auth-disabled`
- `report` 返回 `submission_id` 时，不再重复 `POST /api/core/v1/submissions`
- 导出 Core payload 前，按数据集 schema 自动补齐 `title/content/url`
- 提交前自动裁剪 `structured_data`，移除 schema 外字段，避免 Core `400`
- 任务 payload 文件支持 `UTF-8 BOM`

## 3. 真实联调结果

联调时间：

- 2026-03-29

目标服务：

- `http://101.47.73.95`

本轮实测结论：

1. `POST /api/mining/v1/miners/heartbeat` 可直接成功。
2. `POST /api/mining/v1/refresh-tasks/claim` 仍然不稳定，本轮再次出现 `no task available`。
3. 用创建任务返回的 payload 文件走插件兜底入口，可以跑完整条本地闭环。
4. `report` 返回的 `submission_id` 不能假定立刻可 `GET` 到，插件已做回退处理。
5. Core 提交必须按数据集 schema 过滤 `structured_data`，否则会 `400`。

本轮真实成功命令：

```powershell
python scripts/run_tool.py process-task-file refresh D:\kaifa\clawtroop\social-data-crawler\output\manual_smoke\plugin_e2e_20260329\refresh-task.json
```

成功输出：

```text
processed refresh task rfs_f465427a-7c8a-486b-837f-a4008002d4f0 in D:\kaifa\clawtroop\social-data-crawler\output\agent-runs\refresh\rfs_f465427a-7c8a-486b-837f-a4008002d4f0; exported core submissions to D:\kaifa\clawtroop\social-data-crawler\output\agent-runs\refresh\rfs_f465427a-7c8a-486b-837f-a4008002d4f0\core-submissions.json
```

对应产物：

- [refresh-task.json](d:/kaifa/clawtroop/social-data-crawler/output/manual_smoke/plugin_e2e_20260329/refresh-task.json)
- [records.jsonl](d:/kaifa/clawtroop/social-data-crawler/output/agent-runs/refresh/rfs_f465427a-7c8a-486b-837f-a4008002d4f0/records.jsonl)
- [core-submissions.json](d:/kaifa/clawtroop/social-data-crawler/output/agent-runs/refresh/rfs_f465427a-7c8a-486b-837f-a4008002d4f0/core-submissions.json)
- [core-submissions-response.json](d:/kaifa/clawtroop/social-data-crawler/output/agent-runs/refresh/rfs_f465427a-7c8a-486b-837f-a4008002d4f0/core-submissions-response.json)
- [summary.json](d:/kaifa/clawtroop/social-data-crawler/output/agent-runs/refresh/rfs_f465427a-7c8a-486b-837f-a4008002d4f0/summary.json)

## 4. 当前可用结论

可以认为当前本地已经完成：

- 插件功能
- skill 功能
- 插件与 skill 的主交互链
- `report` 后的 Core 导出闭环
- 对当前远端异常行为的兼容

不能认为当前远端已经稳定：

- `claim` 路由的可用性仍然不稳定
- `submission_id` 的即时可见性仍然不稳定

但这些远端问题现在不会阻断本地闭环执行。

## 5. 验证

插件测试：

```powershell
python -m pytest tests/test_agent_runtime.py tests/test_run_tool.py -q
```

结果：

- `15 passed`
