# OpenClaw Social Crawler 联调能力对比

更新时间：2026-03-31

本文档对照三段链路的能力接通情况：

- `openclaw-social-crawler-plugin`
- `social-data-crawler`
- `http://101.47.73.95/swagger/index.html` 对应 Platform Service

目标不是描述理论设计，而是记录当前实测结果、已接通能力、未接通能力、差异原因和补齐建议。

## 1. 联调范围

当前已实测的链路：

`OpenClaw tool -> plugin Python runtime -> social-data-crawler CLI/runtime -> Platform Service API`

涉及的服务面：

- Swagger/UI：`/swagger/index.html`
- OpenAPI 文档：`/swagger/doc.json`
- Mining API
- Core API

不在本次“已完全验证”范围内的内容：

- 每个平台适配器的全量平台能力
- 所有 browser/login/captcha 恢复分支
- 所有提交流程的成功闭环

## 2. 实测结论摘要

### 2.1 已接通的主链路

以下能力已经通过真实请求或真实 worker 迭代验证：

- Swagger 文档可访问
- plugin 可以加载当前版 `social-data-crawler`
- plugin 可以使用 `awp-wallet` 发起 EIP-712 签名请求
- `heartbeat` 已成功发到 Platform Service
- `run-worker` 已连续运行多轮
- worker 可以成功执行：
  - unified heartbeat
  - miner heartbeat
  - claim refresh task
  - claim repeat_crawl task
  - dataset discovery
  - URL occupancy check
  - submit preflight
  - 本地 backlog / resume 处理

### 2.2 当前未完全打通的能力

以下能力尚未完成“稳定成功闭环”验证：

- `report -> core submission` 全链路成功提交
- 遇到 `CAPTCHA` 后的自动/人工恢复继续执行
- 真实 PoW challenge 的回答成功闭环
- 每个平台适配器的逐平台成功抓取与提交流程

## 3. 能力矩阵

### 3.1 控制面能力矩阵

| 能力 | Plugin | Crawler | Server | 当前状态 | 说明 |
| --- | --- | --- | --- | --- | --- |
| Swagger 可访问 | N/A | N/A | 是 | 已接通 | `index.html` 返回 200 |
| OpenAPI 文档可访问 | N/A | N/A | 是 | 已接通 | 实际地址是 `/swagger/doc.json` |
| Python runtime 启动 | 是 | N/A | N/A | 已接通 | 已修复旧 `crawler.io` 依赖 |
| Crawler CLI 调用 | 是 | 是 | N/A | 已接通 | `run_tool.py -> python -m crawler` 正常 |
| EIP-712 签名 | 是 | N/A | 是 | 已接通 | 依赖 `awp-wallet` |
| unified heartbeat | 是 | N/A | 是 | 已接通 | 实测成功 |
| miner heartbeat | 是 | N/A | 是 | 已接通 | 实测成功 |
| claim refresh task | 是 | N/A | 是 | 已接通 | 实测成功 |
| claim repeat task | 是 | N/A | 是 | 已接通 | 实测成功 |
| backlog/resume | 是 | 是 | N/A | 已接通 | worker state 正常读写 |

### 3.2 数据面能力矩阵

| 能力 | Plugin | Crawler | Server | 当前状态 | 说明 |
| --- | --- | --- | --- | --- | --- |
| dataset discovery | 是 | 是 | 是 | 已接通 | 实测返回 discovery item |
| discover-crawl 执行 | 是 | 是 | N/A | 已接通 | 实测发现 follow-up URL |
| URL occupancy check | 是 | N/A | 是 | 已接通 | 已真实命中 occupied 分支 |
| submit preflight | 是 | N/A | 是 | 已接通 | 已真实命中 rejected 分支 |
| repeat/refresh 跳过逻辑 | 是 | 是 | 是 | 已接通 | occupied / rejected 都已验证 |
| crawl 输出 records | 是 | 是 | N/A | 部分接通 | 已有运行产物，但未覆盖所有平台 |
| report task result | 是 | N/A | 是 | 部分接通 | 路径已接，成功闭环未稳定验证 |
| export core submissions | 是 | 是 | N/A | 部分接通 | 本地导出能力已接 |
| submit core submissions | 是 | N/A | 是 | 未完全接通 | 本轮未形成稳定成功提交 |
| fetch existing submission | 是 | N/A | 是 | 部分接通 | 命中过 `404 sub_fake_not_created` |
| CAPTCHA 进入人工待处理队列 | 是 | 是 | N/A | 已补齐 | plugin 已将 `CAPTCHA` 归类到 `auth_pending` |
| CAPTCHA 恢复执行 | 是 | 是 | N/A | 未接通 | 已暴露问题，未走完恢复流程 |
| PoW challenge answer | 是 | N/A | 是 | 未完全接通 | 代码路径已接，未遇到成功样例 |

## 4. 真实联调证据

### 4.1 直接验证结果

- `http://101.47.73.95/swagger/index.html` 返回 `200`
- `heartbeat` 成功返回 `heartbeat sent`
- `run-worker 10 1` 成功执行
- `run-worker 10 3` 成功连续执行三轮

### 4.2 最近一次 worker 结果

来源：`output/agent-runs/_run_once/last-summary.json`

关键字段：

- `heartbeat_sent: true`
- `unified_heartbeat_sent: true`
- `claimed_items: 2`
- `processed_items: 0`
- `skipped_items: 2`
- `retry_pending: 0`
- `auth_pending: []`
- `errors: []`

说明：

- 控制链路已稳定
- 当前平台返回的任务主要命中了业务规则分支（occupied / preflight rejected）
- 不是本地调用失败

## 5. 已补齐的本地问题

本次联调中已修复以下本地问题：

### 5.1 Plugin 与 crawler 版本结构不兼容

问题：

- plugin 仍依赖 `crawler.io`
- 当前版 `social-data-crawler` 已迁移到 `crawler.output`

补齐：

- plugin 已兼容旧 `crawler.io` 和新 `crawler.output`

影响：

- plugin 能实际启动并发出后续 HTTP 请求

### 5.2 缺签名时错误信息不可操作

问题：

- 之前只有 `401 Unauthorized`
- 联调时难以快速确认缺的是签名头

补齐：

- 当服务端返回 `MISSING_HEADERS` 时，plugin 明确提示需要 `awpWalletToken`

### 5.3 Windows 下 `awp-wallet` 环境不稳定

问题：

- `awp-wallet` 依赖 `HOME`
- 当前 Windows 环境主要提供 `USERPROFILE`

补齐：

- signer 现在会在缺少 `HOME` 时回退到 `USERPROFILE`

### 5.4 Python 子进程找不到 `awp-wallet`

问题：

- PowerShell 能找到 `awp-wallet`
- Python `subprocess` 在当前环境下不稳定解析 wrapper

补齐：

- 已在 OpenClaw 配置中显式设置 `awpWalletBin`
- 当前建议：将 `awpWalletBin` 设为 `awp-wallet`，由目标机器的 `PATH` 负责解析

### 5.5 CAPTCHA 未进入 auth pending

问题：

- crawler 会产出 `CAPTCHA`
- plugin 之前只把 `AUTH_*` 归类为需要人工介入
- 结果是 CAPTCHA 任务只进入普通错误/回退逻辑，不进入 `auth_pending`

补齐：

- plugin 已把 `CAPTCHA` 纳入人工介入队列
- 当前行为是：
  - 任务进入 `auth_pending`
  - 可以由后续人工/browser 恢复流程继续处理

### 5.6 repeat_crawl 缺失 submission 的错误不可诊断

问题：

- 当 `repeat_crawl` 任务只有 `submission_id` 且对应 submission 不存在时
- plugin 之前只会出现泛化的 claim 失败

补齐：

- plugin 现在会明确指出：
  - 哪个 `submission_id` 无法加载
  - 当前 task payload 又没有 `url`
- 这不会伪造缺失数据，但能把问题准确归因到平台任务数据

## 6. 当前未接通项与原因

### 6.1 `report -> core submission` 成功闭环未稳定验证

表现：

- 本轮连续 worker 中没有稳定出现 `submitted_items > 0`
- 出现过：
  - `/api/core/v1/submissions/sub_fake_not_created` 返回 `404`

判断：

- 这更像是平台测试数据问题，或 report/submission 约定不一致
- 不是 plugin/crawler 无法访问 server
- 当前已补的部分仅是诊断增强，不会伪造缺失的 submission/url

### 6.2 CAPTCHA 恢复链路未打通

表现：

- 运行中出现 `CAPTCHA`

判断：

- 说明 discovery/crawl 已经走到真实站点保护层
- `CAPTCHA -> auth_pending` 已补齐
- 但还没有接上 `auto-browser` 或人工登录后的继续执行

### 6.3 PoW 成功样例未覆盖

表现：

- preflight 路径已接入
- 代码有 challenge answer 逻辑
- 但当前没有拿到一个真实成功通过的 challenge 样例

判断：

- 代码接线层面基本具备
- 业务闭环仍需平台侧真实样本验证

### 6.4 平台适配器覆盖面不足

当前实测重点是总控链路，不是各平台逐一验收。

未完成的维度包括：

- Wikipedia 全量抓取提交流程
- arXiv 抓取提交流程
- Amazon 抓取提交流程
- LinkedIn 登录态抓取流程
- generic/page 在不同站点上的稳定性

## 7. 当前接通比例评估

这是工程判断，不是精确数学统计。

### 7.1 控制面

约 `80%~90%`

理由：

- plugin 启动、签名、worker 主循环、server 核心控制接口都已打通
- 剩余问题不是主链路不可达，而是个别业务分支

### 7.2 数据面

约 `50%~60%`

理由：

- discovery / occupancy / preflight / skip 分支已验证
- 但抓取成功样本、report、core submission、captcha 恢复仍未全打通

### 7.3 端到端总体

约 `70%`

理由：

- 主链路稳定
- 业务闭环还缺关键成功案例

## 8. 对照补充建议

### 8.1 第一优先级：补齐提交闭环

目标：

- 至少得到一条真实 `submitted_items > 0`

建议动作：

- 找一条不会命中 occupied / preflight rejected 的 refresh/repeat task
- 跟踪：
  - report request/response
  - exported `core-submissions.json`
  - `core-submissions-response.json`
- 重点核查 server 返回的 `submission_id` 是否真实可查

### 8.2 第二优先级：补齐 CAPTCHA 恢复

目标：

- 打通 `CAPTCHA -> 人工/auto-browser -> 继续 worker`

建议动作：

- 将出现 CAPTCHA 的任务单独落盘
- 用 `auto-browser` 接管一次
- 登录/验证后恢复相同 output root 下的 worker
- 观察该任务是否从 backlog/auth pending 成功恢复

### 8.3 第三优先级：补齐真实 PoW 样例

目标：

- 验证 challenge answer 成功放行

建议动作：

- 找一条会触发真实 challenge 的 dataset/task
- 保存：
  - `preflight/challenge.json`
  - `preflight/answer.json`
  - challenge answer response

### 8.4 第四优先级：逐平台验收

建议按以下顺序：

1. `wikipedia`
2. `arxiv`
3. `generic/page`
4. `amazon`
5. `linkedin`

原因：

- 前三者更容易拿到稳定、低认证门槛样本
- 后两者更容易遇到登录、反爬和 captcha

## 9. 推荐的最小验收标准

认为“三段链路已基本打通”前，至少应满足：

- 一次 `heartbeat` 成功
- 一次 `claim` 成功
- 一次 `discover-crawl` 成功产生 follow-up
- 一次非 occupied 的 `crawl/run` 成功产出 record
- 一次 `report` 成功
- 一次 `core submission` 成功创建或成功查询已创建 submission
- 一次 `CAPTCHA` 或 auth 分支成功恢复

当前已满足：

- 前 4 项中的大部分

当前未满足：

- 稳定的 `report + core submission` 成功闭环
- `CAPTCHA/auth` 成功恢复

## 10. 相关路径

- crawler README：`README.md`
- 当前联调结果：`output/agent-runs/_run_once/last-summary.json`
- worker 状态：
  - `output/agent-runs/_worker_state/backlog.json`
  - `output/agent-runs/_worker_state/auth_pending.json`
- plugin 项目：`../openclaw-social-crawler-plugin`
## 11. Supplemental Update 2026-03-31

- `CAPTCHA` now carries an `auto-browser` recovery hint instead of generic `notify user`.
- Plugin `auth_pending` records now backfill `public_url` from the task URL when crawler output omits it.
- Plugin resume flow is regression-tested for `auth_pending -> due -> rerun -> clear pending entry`.
- Still not closed: syncing the repo changes into the installed OpenClaw plugin copy under the current sandbox.
- Plugin now treats `report_result.submission_id` as a lookup hint instead of a guaranteed success signal:
  - when `fetch existing submission` succeeds, it persists the fetched submission response
  - when the platform returns `404` for synthetic or missing ids such as `sub_fake_not_created`, plugin falls back to explicit `submit_core_submissions`
- Still not closed: a real server-side rerun is still needed to confirm the fallback path against the live Platform Service contract.
