# skill / 插件 / Platform Service 补充联调记录 - 2026-03-29

## 1. 本轮目的

对以下三部分再做一次联调复核：

- `social-data-crawler` skill 当前抓取能力
- `social-crawler-agent` 插件职责链路
- `http://101.47.73.95` 当前 Swagger 暴露接口的真实行为

## 2. 本轮新结论

本轮复测后，结论比上一轮更精确：

1. Swagger 真实在线，`/swagger/doc.json` 可直接访问，不再只是浏览器缓存。
2. 插件目录当前不是一套可直接复跑的源码工程：
   - `plugins/social-crawler-agent` 下只剩 `__pycache__/*.pyc`
   - 设计文档要求存在的 `plugin.json` / `run_tool.py` 当前本地缺失
3. Mining 侧接口没有整体失效：
   - `POST /api/mining/v1/miners/heartbeat` 仍可用
   - `GET /api/mining/v1/miners/online` 可看到在线 miner
4. `claim` 语义仍有异常：
   - 新创建的 refresh task 已明确返回 `assigned_miner_id = auth-disabled-miner`
   - 但 `POST /api/mining/v1/refresh-tasks/claim` 仍返回 `404`
5. 即使 `claim` 返回 `404`，`POST /api/mining/v1/refresh-tasks/{id}/report` 仍可成功把任务置为 `completed`
6. 本地 skill 抓取能力本身没有问题，真正暴露出的新根因是：
   - 插件/任务映射若把 Wikipedia URL 一律降成 `generic/page`
   - 则 `http` 和 `playwright` 都可能拿到页面但抽不出正文
   - 同一 URL 一旦被正确映射成 `wikipedia/article`，就能稳定拿到完整正文

## 3. 平台接口复测结果

### 3.1 Swagger

- `GET http://101.47.73.95/swagger/index.html`：`200`
- `GET http://101.47.73.95/swagger/doc.json`：`200`

当前 Swagger 中仍然存在以下 mining 路由：

- `/api/mining/v1/miners/heartbeat`
- `/api/mining/v1/miners/online`
- `/api/mining/v1/refresh-tasks`
- `/api/mining/v1/refresh-tasks/claim`
- `/api/mining/v1/refresh-tasks/{id}/report`
- `/api/mining/v1/repeat-crawl-tasks`
- `/api/mining/v1/repeat-crawl-tasks/claim`
- `/api/mining/v1/repeat-crawl-tasks/{id}/report`

### 3.2 heartbeat

请求：

- `POST /api/mining/v1/miners/heartbeat`

结果：

- `200`
- 返回 miner：
  - `miner_id = auth-disabled-miner`
  - `online = true`
  - `credit = 0`

### 3.3 online 列表

请求：

- `GET /api/mining/v1/miners/online?page=1&page_size=10`

结果：

- `200`
- 能查到刚刚 heartbeat 的 `auth-disabled-miner`

### 3.4 创建 refresh task

请求：

- `POST /api/mining/v1/refresh-tasks`

请求体：

```json
{
  "dataset_id": "ds_uj006_cc947b668a",
  "epoch_id": "2026-03-29",
  "url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
  "excluded_ips": [],
  "historical_miner_ids": []
}
```

结果：

- `201`
- 成功创建：
  - `id = rfs_358b0dd0-ec56-4b90-b593-90dc4094f8d7`
  - `assigned_miner_id = auth-disabled-miner`
  - `status = pending_claim`

### 3.5 claim refresh task

请求：

- `POST /api/mining/v1/refresh-tasks/claim`

结果：

- `404`
- 空响应体

判断：

- 现在不能再解释成“没有任务”
- 因为该 task 是刚创建且已明确分配给 `auth-disabled-miner`
- 更像是 claim 路由内部状态机或鉴权/分配判定存在异常

### 3.6 report refresh task

请求：

- `POST /api/mining/v1/refresh-tasks/rfs_358b0dd0-ec56-4b90-b593-90dc4094f8d7/report`

请求体：

```json
{
  "cleaned_data": "<1500 chars excerpt>"
}
```

结果：

- `200`
- 返回：
  - `status = completed`
  - `submission_id = sub_2d47074f-9104-44b4-aa7b-959258ae37dd`

判断：

- 在当前 auth-disabled 场景下，report 并未被 claim 结果阻断
- 这意味着平台现阶段可能允许“已分配 miner 直接 report”
- 或者 claim 路由本身有问题，但 report 路径仍然走通

## 4. skill / crawler 复测结果

### 4.1 按插件现有粗映射执行：`generic/page`

输入：

```json
{"platform":"generic","resource_type":"page","url":"https://en.wikipedia.org/wiki/Artificial_intelligence"}
```

运行目录：

- [summary.json](d:/kaifa/clawtroop/social-data-crawler/output/agent-runs/refresh/rfs_358b0dd0-ec56-4b90-b593-90dc4094f8d7/summary.json)
- [records.jsonl](d:/kaifa/clawtroop/social-data-crawler/output/agent-runs/refresh/rfs_358b0dd0-ec56-4b90-b593-90dc4094f8d7/records.jsonl)

结果：

- CLI 退出码 `0`
- `records_succeeded = 1`
- 但内容质量失败：
  - `plain_text = ""`
  - `markdown = ""`
  - `total_chunks = 0`
  - `content_ratio = 0.0`

同样问题在显式 `--backend playwright` 下仍复现：

- [summary.json](d:/kaifa/clawtroop/social-data-crawler/output/agent-runs/refresh/rfs_358b0dd0-ec56-4b90-b593-90dc4094f8d7-playwright/summary.json)
- [records.jsonl](d:/kaifa/clawtroop/social-data-crawler/output/agent-runs/refresh/rfs_358b0dd0-ec56-4b90-b593-90dc4094f8d7-playwright/records.jsonl)

结论：

- 这里不是抓取失败，而是“抓到 HTML 但抽取为空”
- 对公开平台 URL 统一按 `generic/page` 处理，映射策略太粗

### 4.2 按平台感知映射执行：`wikipedia/article`

输入：

```json
{"platform":"wikipedia","resource_type":"article","title":"Artificial intelligence"}
```

运行目录：

- [summary.json](d:/kaifa/clawtroop/social-data-crawler/output/manual_smoke/refresh_task_platform_mapped/run/summary.json)
- [records.jsonl](d:/kaifa/clawtroop/social-data-crawler/output/manual_smoke/refresh_task_platform_mapped/run/records.jsonl)

结果：

- CLI 退出码 `0`
- `records_succeeded = 1`
- 抽取成功：
  - `content.md` 非空
  - `content.txt` 非空
  - `total_chunks = 29`
  - `content_ratio ≈ 0.9686`

结论：

- 本地 skill/crawler 没问题
- 真正需要改的是插件侧 `task_mapper`：
  - 应优先按 URL 域名和路径模式识别可支持平台
  - 不要无脑降为 `generic/page`

## 5. 插件侧新增发现

当前仓库中的插件目录：

- [plugins/social-crawler-agent](d:/kaifa/clawtroop/social-data-crawler/plugins/social-crawler-agent)

现状：

- 缺失 `.codex-plugin/plugin.json`
- 缺失源码脚本，仅剩 `scripts/__pycache__/run_tool*.pyc`

这意味着：

- 本轮“插件联调”只能按插件协议职责进行人工仿真
- 不能直接把当前仓库目录当成一套可安装、可复跑的插件源码

## 6. 本轮最重要的结论

本轮补测把链路拆清楚了：

1. 平台接口仍在线，Swagger 可直接读取。
2. heartbeat 正常，online 列表正常。
3. refresh task 创建正常。
4. refresh task claim 仍异常，即使任务已被分配也返回 `404`。
5. report 仍可成功完成任务并生成 submission。
6. 本地 crawler 能力正常。
7. 当前最值得修的不是 crawler，而是插件 task mapper：
   - 应把 `wikipedia.org/wiki/...` 识别为 `wikipedia/article`
   - 而不是映射为 `generic/page`

## 7. 建议下一步

1. 修复插件源码缺失问题，补回可安装的 `plugin.json` 和 Python bridge 脚本。
2. 在插件的 task mapper 中加入平台感知 URL 识别：
   - `wikipedia.org/wiki/*` -> `wikipedia/article`
   - `arxiv.org/abs/*` -> `arxiv/paper`
   - 其他未识别 URL 再降为 `generic/page`
3. 单独向服务端确认：
   - 为什么 `pending_claim` 且已 assigned 的 refresh task 仍然 claim `404`
   - 为什么在 auth-disabled 场景下 report 可绕过 claim 成功完成任务
