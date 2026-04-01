# Social Data Crawler 项目介绍与交接文档

面向对象：懂技术的老板、项目协作同事、后续接手维护人员

文档定位：这不是一份快速上手 README，而是一份覆盖项目定位、架构、核心流程、集成方式、运行机制、测试现状和后续风险的全景交接文档。

写作方式：采用 `agentteam` 分工视角组织，各章节由不同“责任 Agent”给出说明，但整篇保持统一主线，便于连续阅读。

---

## 0. AgentTeam 分工视角

- `Agent 1 / 架构负责人`：解释项目定位、整体结构、边界和设计原则
- `Agent 2 / 采集链路负责人`：解释 `discover -> fetch -> extract -> enrich -> write` 主流程
- `Agent 3 / 平台集成负责人`：解释 OpenClaw plugin、Worker、Platform Service 集成
- `Agent 4 / 运行交付负责人`：解释安装、配置、命令、输出、验证和运维事项
- `Agent 5 / 风险与路线负责人`：解释当前成熟度、已知限制、建议的后续工作

这种写法的目的不是形式化“分角色表演”，而是把项目解释责任拆清楚，方便老板和同事按主题阅读。

---

## 1. 项目概览

### 1.1 项目是什么

`social-data-crawler` 是一个面向 Agent 工作流的本地结构化采集项目。它不是单纯的网页爬虫，也不是只会抓原始 HTML 的工具，而是一个围绕“可持续运行、可结构化输出、可接入平台调度、可在需要时引入浏览器/登录/AI 补全”的采集运行时。

项目当前支持的平台包括：

- `Wikipedia`
- `arXiv`
- `Amazon`
- `Base`
- `LinkedIn`
- `generic/page`

支持的核心能力包括：

- 从结构化输入构建规范化 URL
- 对目标页面或 API 进行抓取
- 将原始内容清洗为 `plain_text`、`markdown`、`structured`、`chunks`
- 对已抓取内容执行抽取式或生成式 enrichment
- 将结果写入稳定的 `records.jsonl` / `errors.jsonl` / `summary.json`
- 在 OpenClaw 场景下作为 plugin runtime 接入 worker 和平台任务流

### 1.2 项目解决什么问题

这个项目解决的是“把外部公开或半公开网页资源，稳定地转化成平台可消费的结构化记录”的问题。传统抓取脚本常见的问题有：

- 只适合一次性使用，不能恢复
- 直接 dump 页面，不利于后续分析
- 认证和会话逻辑散落，无法复用
- 平台调度、任务认领、结果提交没有统一入口
- 遇到验证码、登录过期、PoW challenge 时容易中断

`social-data-crawler` 的设计方向则更偏向“工程化采集基础设施”：

- 输入输出格式稳定
- 平台适配器明确
- 抓取、抽取、增强链路分层
- session 和 auth 状态可复用
- 失败与重试信息显式记录
- 可以挂到 OpenClaw 和 Platform Service 上形成持续 worker

### 1.3 它不是什么

为了避免误解，这个项目当前不是：

- 通用互联网搜索工具
- 面向任意站点的万能采集器
- 云端托管服务
- 完整闭环的数据平台
- 全自动解决所有验证码和复杂风控的系统

它更准确的定位是：`一个面向特定平台集合和平台任务链路的、本地可运行的结构化采集运行时 + OpenClaw 集成层`。

---

## 2. 总体架构

### 2.1 三层结构

`Agent 1 / 架构负责人`

项目可以分成三层：

1. `Crawler Runtime`
2. `OpenClaw Plugin Integration`
3. `Platform Service / Mining & Core API`

可用一句话概括：

`Platform task / dataset -> OpenClaw plugin worker -> Python crawler runtime -> structured output -> export / submit back to platform`

### 2.2 目录级结构理解

核心目录：

- `crawler/`
  - Python 主运行时
- `integrations/openclaw-plugin-src/`
  - OpenClaw 原生 plugin 源码
- `dist/openclaw-plugin/`
  - 打包后的最小运行时
- `auto-browser/`
  - 浏览器接管与人工协作能力
- `references/`
  - schema、selector、route、限流和平台规则参考数据
- `scripts/`
  - bootstrap、安装、环境诊断、冒烟测试
- `docs/`
  - 设计文档和集成说明

### 2.3 逻辑边界

边界划分比较清楚，这是项目目前比较成熟的一点。

`crawler` 负责：

- URL 规范化和平台适配
- 数据抓取
- 内容抽取和清洗
- enrichment
- 输出记录与制品

`plugin` 负责：

- 以 OpenClaw 工具形式暴露能力
- 把平台任务转成 crawler 可执行输入
- 管理 worker 状态机
- 心跳、claim、resume、preflight、report、core submission
- 对接 `awp-wallet` 和签名请求

`auto-browser` 负责：

- 在登录、验证码、人工确认场景下提供共享浏览器会话
- 让 agent 和人工在同一 Chrome/CDP 会话协作

### 2.4 设计原则

项目整体体现出几个明确设计原则：

- 结构化输出优先，而不是原始页面转储优先
- 平台适配优先，而不是完全抽象化的“万能抓取”
- 本地可运行和可恢复优先
- 失败显式化优先
- 尽量把 OpenClaw 平台耦合收敛在 plugin 层，而不是污染 crawler 通用运行时

---

## 3. 核心执行链路

`Agent 2 / 采集链路负责人`

主执行模型可以概括为：

`discover -> fetch -> extract -> enrich -> write`

对于平台任务模式，还会继续延伸为：

`claim -> preflight -> crawl/discover/run -> report -> export -> submit`

### 3.1 Discover

`discover-crawl` 的目标不是直接产出完整内容，而是从 seed 扩展出更多候选 URL。

它适用于：

- 已知起始入口，但未知完整目标 URL 集
- 希望围绕 dataset 自动发现增量对象
- 希望按深度和页面数控制采集边界

核心特征：

- 有自己的 `CrawlOptions`
- 支持 `max_depth`、`max_pages`、`sitemap_mode`
- 通过 discovery adapter 生成 `DiscoveryCandidate`
- 会保存 discovery state，用于 `--resume`

输出会偏 discovery 语义，例如：

- `canonical_url`
- `seed_url`
- `hop_depth`
- `discovery_mode`
- `fetched`

它不保证像 `crawl` / `run` 那样产出完整 `structured` 和 `chunks`。

### 3.2 Fetch

抓取层通过 `FetchEngine` 统一调度多后端。

支持的后端包括：

- `api`
- `http`
- `playwright`
- `camoufox`

不同平台会有不同的首选后端和回退链。例如：

- `wikipedia/arxiv/base`: `api -> http -> playwright`
- `amazon`: `http -> playwright -> camoufox`
- `linkedin profile/company/search/job`: `api -> playwright -> camoufox`
- `linkedin post`: `playwright -> camoufox`
- `generic/page`: `http -> playwright -> camoufox`

这一层的关键价值在于：

- 后端切换不是外部脚本硬编码，而是平台适配驱动
- fetch 失败时能够带出分类后的错误
- 认证过期时可以结合 `--auto-login` 做一次刷新重试
- 能把抓取阶段的关键制品落到 `artifacts/`

### 3.3 Extract

抽取层负责把抓取结果转成可消费的文档内容，而不是仅保留原始 HTML。

输出通常包括：

- `plain_text`
- `markdown`
- `structured`
- `chunks`
- 各类 `artifact`

这层集成了多种抽取方式：

- HTML 解析与正文提取
- 清洗与去噪
- PDF 提取
- 基于 schema 的结构化抽取
- LLM schema 抽取

抽取层的目标不是“尽量多保留原始细节”，而是“形成稳定、可复用、适合后续 enrichment 和提交的内容表示”。

### 3.4 Enrich

enrichment 的原则是 `extractive-first`。

也就是说：

- 如果规则或 lookup 足够强，就直接从现有内容抽取
- 只有在抽取式方法不够时才调用生成式模型
- 如果需要生成但当前没有 model config，则结果标记为 `pending_agent`
- 后续可通过 `fill-enrichment` 把 agent 的响应回填到 `records.jsonl`

这套机制使 enrichment 既可以完全自动跑，也可以在资源、权限或模型接入受限时退化为“半自动”。

### 3.5 Write

运行结束后，结果会稳定落盘到输出目录：

- `records.jsonl`
- `errors.jsonl`
- `summary.json`
- `run_manifest.json`
- `runtime_metrics.json`
- `artifacts/`
- 可选 `dlq.jsonl`

这意味着项目天然适合：

- 离线分析
- 后处理
- 重跑与追责
- 平台回传

---

## 4. 代码模块拆解

`Agent 2 / 采集链路负责人`

### 4.1 `crawler/cli.py`

这是命令入口层，负责对外暴露统一 CLI。

当前主要命令：

- `discover-crawl`
- `crawl`
- `run`
- `enrich`
- `fill-enrichment`
- `export-submissions`

可以把它理解为：`所有能力最终都从这里进出`。外部脚本、plugin bridge 和本地人工调试，都是围绕这套 CLI 在工作。

### 4.2 `crawler/core/pipeline.py`

这是运行时核心编排层。

主要职责：

- 根据命令分流到 discovery pipeline 或主 pipeline
- 串起 fetch、extract、enrich
- 控制并发和 resume 行为
- 统一错误收集
- 统一 artifact 落盘

这是整个 crawler 的“大脑”。

### 4.3 `crawler/discovery/`

这一层负责“从种子扩展出目标”。

包含的能力包括：

- 平台 discovery adapter
- 候选项 contract
- BFS / crawl / map engine
- 调度与 throttle
- frontier / visited / checkpoint / occupancy 等 state store
- 特定平台的 expand 和 normalize 规则

它的价值不只是多发现 URL，还在于：

- 可以把发现过程状态化
- 允许多跳扩展
- 让平台差异收敛在 adapter 内

### 4.4 `crawler/fetch/`

这一层负责“怎么拿到内容”。

包含：

- 后端路由
- 浏览器池
- rate limiter
- circuit breaker
- session manager / session store
- wait strategy
- api/http/playwright/camoufox 后端实现
- error classifier

这是抓取成功率和稳定性的关键层。

### 4.5 `crawler/extract/`

这一层负责“拿到内容后，怎么把它变成人和系统都能用的文档”。

包含：

- HTML 解析
- 主体内容提取
- 内容清洗
- markdown/plain text 生成
- 结构化抽取
- LLM schema 抽取
- chunking
- PDF 抽取

它决定的是结果“质量”，而不只是结果“有无”。

### 4.6 `crawler/enrich/`

这一层负责在已有抽取结果上补充更高层结构。

包含：

- 输入规范化
- extractive enricher
- lookup enricher
- 生成式 prompt 渲染
- LLM client
- 批量异步执行
- field group registry

它负责把原始内容提升为更适合平台消费和业务分析的字段集合。

### 4.7 `crawler/output/`

这层负责：

- JSON / JSONL 读写
- artifact 落盘
- summary 构建

职责很朴素，但对可追踪性很关键。

### 4.8 `crawler/platforms/`

平台适配器层负责把平台差异封装起来。

包括：

- seed 构建
- backend 选择
- API 抓取逻辑
- enrichment request 构建
- record normalize

当前已覆盖的平台，基本都通过这一层完成差异收敛。

---

## 5. 输入、输出与数据契约

`Agent 2 / 采集链路负责人`

### 5.1 输入

输入采用 JSONL，每一行是一个待处理 record。

基础字段至少包括：

- `platform`
- `resource_type`
- 目标平台所需的识别字段

例如：

```json
{"platform":"wikipedia","resource_type":"article","title":"Artificial intelligence"}
{"platform":"amazon","resource_type":"product","asin":"B09V3KXJPB"}
{"platform":"linkedin","resource_type":"profile","public_identifier":"john-doe-ai"}
```

这种输入设计意味着：

- 很适合批处理
- 很适合平台 claim 后一条一条落盘给 crawler
- 很适合从 discovery 到 crawl 的分阶段传递

### 5.2 输出

最关键的输出文件是：

- `records.jsonl`
- `errors.jsonl`
- `summary.json`
- `run_manifest.json`
- `artifacts/`

最有价值的记录字段包括：

- `status`
- `stage`
- `retryable`
- `error_code`
- `next_action`
- `plain_text`
- `markdown`
- `structured`
- `chunks`
- `enrichment`

对接和排查时建议按这个顺序看：

1. `summary.json`
2. `errors.jsonl`
3. `records.jsonl`
4. `artifacts/`

### 5.3 下游提交契约

项目支持把 `records.jsonl` 转成平台侧提交 payload。

相关入口：

- CLI: `export-submissions`
- 代码：`crawler/submission_export.py`

提交 payload 的核心结构为：

- `dataset_id`
- `entries[]`
  - `url`
  - `cleaned_data`
  - `structured_data`
  - `crawl_timestamp`

plugin 在真正提交前还会根据 dataset schema 做一次字段规整：

- 填充必需字段，如 `title`、`content`、`url`
- 丢掉 Core API 不接受的 schema 外字段

这说明项目并不是“抓完就完”，而是明确考虑了平台接收契约。

---

## 6. OpenClaw Plugin 与 Worker 机制

`Agent 3 / 平台集成负责人`

这是本项目和普通 crawler 最大的区别之一。

### 6.1 Plugin 的定位

`integrations/openclaw-plugin-src/` 是 OpenClaw 原生 plugin 层。

它的作用不是重复实现 crawler，而是：

- 把 crawler 包装成 OpenClaw 可调用工具
- 注入平台和钱包相关配置
- 负责 worker 生命周期
- 和 Platform Service 通信

也就是说：

- `crawler` 负责采集和结构化
- `plugin` 负责把采集能力接进平台生态

### 6.2 暴露的工具

plugin 当前注册的主要工具包括：

- `social_crawler_worker`
- `social_crawler_heartbeat`
- `social_crawler_run_once`
- `social_crawler_run_loop`
- `social_crawler_process_task_file`
- `social_crawler_export_core_submissions`

其中真正的主入口已经偏向 `social_crawler_worker`。

### 6.3 Python Bridge

plugin 不是直接重写 crawler 逻辑，而是通过 Python bridge 调用现有运行时：

- `scripts/run_tool.py`
- `scripts/agent_runtime.py`

这样做的价值是：

- plugin 层保持轻量
- crawler CLI 成为唯一能力源
- 同一套逻辑既可本地运行，也可 plugin 运行

### 6.4 Worker 状态机

`agent_runtime.py` 展示出这个项目已经从“脚本”演进到“worker”。

worker 当前具备的能力包括：

- 发送 unified heartbeat
- 发送 miner heartbeat
- claim repeat-crawl task
- claim refresh task
- 从 backlog / auth_pending / submit_pending 恢复任务
- 基于 active dataset 做 autonomous discovery
- 根据任务类型选择 `discover-crawl` / `crawl` / `run`
- 对结果执行 report
- 导出并提交 core submissions

从实现上看，worker 至少管理了三个关键状态队列：

- `backlog`
- `auth_pending`
- `submit_pending`

这意味着它具备基础的“不中断运行能力”。

### 6.5 Preflight、占位检查与 PoW

在真正执行 crawler 前，worker 还做了几层平台约束处理：

- URL occupancy check
- preflight
- challenge 处理

对应逻辑大意是：

- 如果 URL 已被占用，则直接跳过
- 如果 preflight 拒绝，则记录并跳过
- 如果收到 challenge，尝试求解
- 当前 challenge 求解支持受限，未解出时会进入 terminal skip

这是项目往“可持续平台 worker”方向发展的重要一步，因为它已经不只是“抓得到内容”，而是“知道什么时候不该抓、什么时候还不能提交”。

### 6.6 Report 与 Core Submission

任务处理完成后，worker 会根据任务类型进行 report。

若有 `dataset_id`，还会继续：

- 导出 `core-submissions.json`
- 调用平台创建或补提交流程
- 记录 `core-submissions-response.json`

同时对 `report_result.submission_id` 采取了更稳健的策略：

- 如果 report 已经返回 `submission_id`，先尝试 fetch existing submission
- 如果 fetch 返回 `404`，则回退到显式 `submit_core_submissions`

这表明团队已经遇到并处理过平台侧“返回了看似成功的 submission_id，但实际上未真正创建”的集成问题。

---

## 7. 认证、会话与人工接管

`Agent 3 / 平台集成负责人`

### 7.1 为什么这一层重要

像 LinkedIn 这类目标，真正的难点通常不在抽取，而在：

- 登录状态
- cookies / storage_state
- auth 过期
- captcha
- 人机协作切换

项目在这块已经有比较完整的设计。

### 7.2 Session 与 cookies

crawler 支持通过 `--cookies` 提供认证状态。

可接受的输入形式包括：

- 原始 cookie 列表
- Playwright `storage_state`
- 包含顶层 `storage_state` 的 wrapper 对象

系统会把这些状态规范化到输出目录下的 `.sessions/`，后续运行可复用。

### 7.3 `--auto-login`

对于支持的场景，`--auto-login` 允许在检测到 `AUTH_EXPIRED` 后做一次刷新重试。

这并不意味着 crawler 能自动处理所有登录和风控，而是意味着：

- 它知道 auth 失效是一类特定问题
- 它会尝试沿着“刷新状态 -> 再试一次”的路径恢复

### 7.4 `auth_pending`

当 worker 发现错误属于认证类问题时，不会把它和普通 retryable 错误混在一起。

而是通过 `AuthOrchestrator` 进入 `auth_pending` 队列。

这很关键，因为认证问题往往需要人工介入，不适合无限重试。

### 7.5 `auto-browser`

`auto-browser` 提供共享 Chrome/CDP 会话和 VNC 协作能力，用于：

- 登录
- 验证码
- 人工确认
- 会话导出

它的意义是：

- agent 和人工可以在同一个浏览器上下文里接力
- 人工只做“必须人工做的那一步”
- 完成后可导出 session，再交回 crawler 自动跑

这使项目在面对现实世界站点时更可用，而不只是理论上支持 browser backend。

---

## 8. 运行方式与常用命令

`Agent 4 / 运行交付负责人`

### 8.1 安装与环境初始化

常用入口：

- `scripts/bootstrap.sh`
- `scripts/bootstrap.ps1`
- `scripts/bootstrap.cmd`

OpenClaw 单仓安装入口：

- `scripts/install_openclaw_integration.sh`
- `scripts/install_openclaw_integration.ps1`

安装脚本会负责：

- 构建 `dist/openclaw-plugin`
- 更新 OpenClaw 配置
- 安装 workspace skill wrapper
- 尝试配置 `awp-wallet` 相关能力

### 8.2 常用命令

抓取已知目标：

```bash
python -m crawler crawl --input ./records.jsonl --output ./out
```

全流程：

```bash
python -m crawler run --input ./records.jsonl --output ./out
```

仅增强：

```bash
python -m crawler enrich --input ./out/records.jsonl --output ./out-enriched
```

发现式抓取：

```bash
python -m crawler discover-crawl --input ./seeds.jsonl --output ./out-discovery --max-depth 2 --max-pages 100
```

导出平台提交数据：

```bash
python -m crawler export-submissions --input ./out/records.jsonl --output ./out/core-submissions.json --dataset-id dataset_xxx
```

### 8.3 常用运行参数

常见标志：

- `--backend`
- `--resume`
- `--strict`
- `--artifacts-dir`
- `--css-schema`
- `--extract-llm-schema`
- `--enrich-llm-schema`
- `--model-config`
- `--auto-login`
- `--max-chunk-tokens`
- `--chunk-overlap`
- `--concurrency`

### 8.4 Worker 相关入口

plugin README 给出的本地验证入口包括：

- `python scripts/run_tool.py --help`
- `python scripts/run_tool.py run-worker 60 1`
- `python scripts/run_tool.py run-loop 60 1`

这些入口适合验证：

- plugin 到 Python bridge 是否通
- worker 配置是否正确
- 平台心跳和 claim 是否能走通

---

## 9. 测试、验证与当前成熟度

`Agent 4 / 运行交付负责人`

### 9.1 自动化测试现状

当前 `crawler/tests/` 下约有 `24` 个测试文件，覆盖面已经不算很薄。

从文件名看，已覆盖的核心区域包括：

- CLI
- contracts
- discovery contracts / runner / state
- url builder
- fetch engine / pipeline / session store
- extract pipeline / extractors
- enrich pipeline / enrichment / schema runtime
- output contracts
- integration pipeline
- platform registry
- submission export

这说明项目已经不只是“能跑”，而是有较明显的回归测试意识。

### 9.2 验证方式

项目提供了几类典型验证入口：

- `scripts/verify_env.py`
- `scripts/smoke_test.py`
- crawler 测试套件
- plugin 本地运行命令
- host diagnostics

### 9.3 当前成熟度判断

从代码和文档状态判断，项目当前更接近：

- `Crawler Runtime`: 中高完成度
- `Plugin / Worker Integration`: 中等完成度，已具备连续运行框架
- `真实平台闭环验证`: 部分路径已验证，部分路径仍依赖线上再确认

特别是提交链路、challenge、captcha 和平台 API 合约差异，仍然是成熟度最敏感的区域。

---

## 10. 已知限制与风险

`Agent 5 / 风险与路线负责人`

### 10.1 平台闭环依赖真实环境

很多关键路径只能在真实平台环境确认，包括：

- claim 是否稳定
- report 与 submission 的契约是否完全一致
- preflight/challenge 的真实返回形态
- auth 过期和 captcha 的真实恢复体验

因此，离线测试不能完全替代线上联调。

### 10.2 平台集成耦合仍然存在

虽然设计上已经尽量把平台耦合压缩在 plugin 层，但 worker 侧仍然深度依赖：

- Mining API
- Core API
- dataset schema
- Web3 签名链路

这意味着平台接口一旦变化，plugin 层会首先受影响。

### 10.3 Challenge 与复杂风控能力仍有限

代码中对 PoW challenge 已有处理入口，但并不是一个通用求解系统。

这意味着：

- 简单 challenge 可以纳入链路
- 复杂 challenge 仍可能中断任务

### 10.4 认证类问题仍然是主要非确定性来源

尤其是在 LinkedIn 场景：

- cookie 失效
- 登录策略变化
- captcha
- 人工确认

这些都不是纯代码层面可以完全消除的。

### 10.5 文档与实际安装副本同步风险

仓库里已经有源码、打包产物和安装脚本。实际运行时，如果 OpenClaw 使用的是已安装拷贝而不是当前源码目录，存在“仓库修改未同步到真实安装副本”的风险。

这类问题在联调时很常见，需要特别警惕。

---

## 11. 接手建议

`Agent 5 / 风险与路线负责人`

如果后续由新同事接手，建议按以下顺序建立认知。

### 11.1 第一步：先理解主线

先读这些文件：

- `README.md`
- `crawler/cli.py`
- `crawler/core/pipeline.py`
- `integrations/openclaw-plugin-src/README.md`
- `integrations/openclaw-plugin-src/scripts/agent_runtime.py`

目标不是看细节，而是先建立完整链路脑图。

### 11.2 第二步：区分 crawler 与 plugin

一定要明确：

- crawler 是采集运行时
- plugin 是平台接入层

不要把平台问题误判为 crawler 问题，也不要把采集质量问题误判为 plugin 问题。

### 11.3 第三步：先本地跑 CLI，再跑 worker

推荐顺序：

1. `crawl` / `run`
2. `discover-crawl`
3. `export-submissions`
4. `run-worker`
5. `run-loop`

先确认采集本身，再确认平台接入。

### 11.4 第四步：优先看输出而不是猜

排查时优先看：

- `summary.json`
- `errors.jsonl`
- `records.jsonl`
- `core-submissions.json`
- `core-submissions-response.json`
- `_worker_state/*`
- `_run_artifacts/*`

这个项目的一个优点就是产物比较完整，很多问题不需要靠猜。

---

## 12. 对老板和团队的结论

`AgentTeam 联合结论`

`social-data-crawler` 已经不是一个“零散的爬虫脚本集合”，而是一个成型中的结构化采集运行时，具备以下几个显著特点：

- 有清晰的分层和目录边界
- 有统一 CLI 和稳定输出契约
- 有 discovery、fetch、extract、enrich 的完整链路
- 有 OpenClaw plugin 和 worker 状态机
- 已考虑平台任务认领、报告、导出和提交
- 已考虑 auth、session、captcha、人机协作这些真实问题

从工程判断上看，这个项目已经具备“作为内部采集底座继续投资”的条件，但还没有达到“可以忽略外部平台不确定性、完全自动稳定运行”的状态。

更准确的评价是：

- `架构方向正确`
- `运行时主体已成型`
- `平台集成能力已具备`
- `生产级稳定性仍取决于后续联调、风控对抗和闭环验证`

如果继续投入，最值得优先强化的方向是：

- 真实平台闭环验证
- challenge/captcha 恢复链路
- plugin 安装副本与源码同步流程
- 更明确的运维观察面和失败分层

---

## 13. 附：关键文件索引

- `README.md`
- `crawler/cli.py`
- `crawler/core/pipeline.py`
- `crawler/submission_export.py`
- `crawler/platforms/registry.py`
- `crawler/discovery/runner.py`
- `crawler/fetch/engine.py`
- `crawler/extract/pipeline.py`
- `crawler/enrich/pipeline.py`
- `integrations/openclaw-plugin-src/README.md`
- `integrations/openclaw-plugin-src/src/tools.ts`
- `integrations/openclaw-plugin-src/scripts/run_tool.py`
- `integrations/openclaw-plugin-src/scripts/agent_runtime.py`
- `auto-browser/SKILL.md`
- `docs/integration-capability-matrix-2026-03-31.md`

