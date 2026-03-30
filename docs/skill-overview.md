# Social Data Crawler Skill Overview

## Purpose

`social-data-crawler` 是一个面向 agent 的本地数据抓取与增强 skill。它的目标不是“打开网页给人看”，而是把目标页面或文档转成稳定、可重跑、可恢复、可继续 enrich 的结构化产物。

它当前覆盖 5 类数据源：

- `Wikipedia`
- `arXiv`
- `Amazon`
- `Base`
- `LinkedIn`

核心流水线是：

`discovery -> fetch -> extract -> normalize -> enrich -> write`

这意味着它会先根据输入记录构造规范 URL，再抓取内容、提取文本或文档块、归一化成 canonical record，最后可选执行 AI enrichment，并把结果与 artifacts 一起写盘。

## This Document vs `SKILL.md`

这份文档是给人看的，回答这些问题：

- 这个 skill 是干什么的
- 怎么用
- 当前实现到了什么程度
- 内部架构怎么组织
- 后续应该怎么扩展

[`SKILL.md`](/d:/kaifa/clawtroop/social-data-crawler/SKILL.md) 是给 agent 看的执行说明，应该关注：

- 什么时候用
- 怎么调用 CLI
- 输入输出约束
- 恢复与重试规则
- agent 在执行时优先查看哪些文件

两者不应承担同样职责。

## What The Skill Does

这个 skill 的最小价值不是“抓到 HTML”，而是产出 agent 可消费的结果：

- `records.jsonl`
- `errors.jsonl`
- `summary.json`
- `run_manifest.json`
- `artifacts/`

其中：

- `records.jsonl` 是主输出，后续 enrich、分析、二次处理都应以它为准
- `errors.jsonl` 是失败与恢复入口
- `summary.json` 适合先读，快速判断本轮是否成功
- `run_manifest.json` 记录本轮执行参数
- `artifacts/` 保存 HTML、Markdown、纯文本、抓取元数据、PDF、document blocks 等中间产物

## Supported Platforms

### Wikipedia

- 资源类型：`article`
- 默认 backend：`api`
- 典型提取：MediaWiki API -> 纯文本、Markdown、页面属性
- 典型输出：标题、摘要、正文 Markdown、纯文本、pageprops

### arXiv

- 资源类型：`paper`
- 默认 backend：`api`
- 典型提取：arXiv Atom API + PDF artifact
- 典型输出：页面正文、PDF 文档块、基础 paper 标识

### Amazon

- 资源类型：`product`、`seller`、`search`
- 默认 backend：`http`
- 提取特点：HTTP 优先，可升级到 `playwright` / `camoufox`
- 当前归一化重点：页面标题、ASIN 等基础结构字段

### Base

- 资源类型：`address`、`transaction`、`token`、`contract`
- 默认 backend：`api`
- 提取特点：JSON-RPC / explorer API 优先，页面抓取兜底

### LinkedIn

- 资源类型：`profile`、`company`、`post`、`job`
- 默认 backend：`api`
- 特点：通常需要认证态，`post` 资源仍更偏浏览器抓取
- 当前实现：支持 cookie / storage state 导入、会话复用、未认证时显式报 `AUTH_REQUIRED`

## CLI Usage

### Crawl Only

```bash
python -m crawler crawl --input ./records.jsonl --output ./out
```

### Enrich Only

```bash
python -m crawler enrich --input ./out/records.jsonl --output ./out-enriched
```

### Crawl + Enrich

```bash
python -m crawler run --input ./records.jsonl --output ./out
```

### Common Controls

```bash
python -m crawler crawl \
  --input ./records.jsonl \
  --output ./out \
  --backend http \
  --resume \
  --artifacts-dir ./out/artifacts \
  --strict
```

这些参数的作用：

- `--backend`：强制使用 `api`、`http`、`playwright` 或 `camoufox`
- `--resume`：向既有输出目录追加 `records/errors`
- `--artifacts-dir`：把 artifacts 写到显式路径
- `--strict`：只要有失败记录就返回非 0 exit code
- `--cookies`：为 LinkedIn 等需要登录态的平台导入 cookie / storage state
- `--field-group`：指定 enrich 执行哪些组
- `--model-config`：提供 enrich 执行配置

这些命令示例用于说明 skill 的内部调用方式，不是给最终用户的终端操作说明。实际使用时应由 agent 自己执行命令，只在浏览器登录、验证码、扫码或确认页面这类动作上请求用户介入。

## Input Contract

输入文件必须是 JSONL，每行一个 record。

最小要求：

- `platform`
- `resource_type`
- 每个平台所需 discovery 字段

示例：

```json
{"platform":"wikipedia","resource_type":"article","title":"Artificial intelligence"}
{"platform":"arxiv","resource_type":"paper","arxiv_id":"2401.12345"}
{"platform":"amazon","resource_type":"product","asin":"B09V3KXJPB"}
{"platform":"base","resource_type":"transaction","tx_hash":"0xabc..."}
{"platform":"linkedin","resource_type":"profile","public_identifier":"john-doe-ai"}
```

URL 构造依赖：

- [`url_templates.json`](/d:/kaifa/clawtroop/social-data-crawler/references/url_templates.json)
- [`field_mappings.json`](/d:/kaifa/clawtroop/social-data-crawler/references/field_mappings.json)

## Output Contract

标准 record 至少包含这些控制字段：

- `platform`
- `entity_type`
- `resource_type`
- `canonical_url`
- `status`
- `stage`
- `retryable`
- `error_code`
- `next_action`
- `artifacts`
- `metadata`
- `plain_text`
- `markdown`
- `document_blocks`
- `structured`

标准 error record 至少包含：

- `platform`
- `resource_type`
- `stage`
- `status`
- `error_code`
- `retryable`
- `next_action`
- `message`

## Recovery Model

这个 skill 的一个关键设计点是“恢复显式化”。

当失败发生时，不应靠人工猜，而应先读：

1. `summary.json`
2. `errors.jsonl`
3. `records.jsonl`
4. `artifacts/`

常见恢复路径：

- `AUTH_REQUIRED`
  - agent 调起 `auto-browser`，让用户只完成浏览器中的登录动作
  - agent 导出会话并作为 `--cookies` 导入
  - 或复用输出目录下已有 `.sessions/`
- `AUTH_EXPIRED`
  - agent 重新调起 `auto-browser` 刷新登录态
  - agent 重新导出会话并重试
- 抓取成功但 enrich 未执行
  - 对已有 `records.jsonl` 跑 `enrich`
- 局部记录失败
  - 修正输入或会话，再用 `--resume` 续跑

## Internal Architecture

### 1. Discovery

[`url_builder.py`](/d:/kaifa/clawtroop/social-data-crawler/crawler/discovery/url_builder.py) 根据模板和字段别名把输入转成：

- `canonical_url`
- 平台 artifact URL，比如 arXiv 的 `pdf_url`
- 已解析字段

### 2. Platform Adapter Layer

平台差异主要放在 [`crawler/platforms/`](/d:/kaifa/clawtroop/social-data-crawler/crawler/platforms/)。

每个 adapter 现在负责：

- backend 解析
- 内容抽取入口
- 记录归一化入口
- enrich 路由计划

也就是说，dispatcher 不再自己硬编码“某个平台应该怎样 normalizer/extractor”，而是调用 adapter 暴露的方法。

### 3. Fetch Layer

[`crawler/fetch/`](/d:/kaifa/clawtroop/social-data-crawler/crawler/fetch/) 负责实际抓取：

- [`http_backend.py`](/d:/kaifa/clawtroop/social-data-crawler/crawler/fetch/http_backend.py)
- [`playwright_backend.py`](/d:/kaifa/clawtroop/social-data-crawler/crawler/fetch/playwright_backend.py)
- [`camoufox_backend.py`](/d:/kaifa/clawtroop/social-data-crawler/crawler/fetch/camoufox_backend.py)
- [`session_store.py`](/d:/kaifa/clawtroop/social-data-crawler/crawler/fetch/session_store.py)
- [`orchestrator.py`](/d:/kaifa/clawtroop/social-data-crawler/crawler/fetch/orchestrator.py)

HTTP backend 目前使用带联系信息的 UA，以避免 Wikipedia 一类站点直接 403。

### 4. Extract Layer

[`crawler/extract/`](/d:/kaifa/clawtroop/social-data-crawler/crawler/extract/) 负责把抓到的内容变成可消费文本：

- HTML 提取
- Trafilatura 提取
- Unstructured 文档分块

HTML 通常写出：

- `metadata`
- `markdown`
- `plain_text`

PDF/文档通常写出：

- `document_blocks`
- `sections`
- `plain_text`

### 5. Dispatcher

[`dispatcher.py`](/d:/kaifa/clawtroop/social-data-crawler/crawler/core/dispatcher.py) 是运行时编排器。

它负责：

- 读输入
- 取 adapter
- 做 discovery
- 解析 backend
- 执行 fetch
- 写 fetch artifacts
- 执行 extract
- 写 extract artifacts
- 如有 PDF artifact 再抓二级文档
- 归一化成 canonical record
- enrich 时调用 enrich orchestrator

### 6. Enrichment

[`crawler/enrich/orchestrator.py`](/d:/kaifa/clawtroop/social-data-crawler/crawler/enrich/orchestrator.py) 和 [`crawler/enrich/templates/__init__.py`](/d:/kaifa/clawtroop/social-data-crawler/crawler/enrich/templates/__init__.py) 现在已经不是单纯 catalog 挂载。

它支持两层执行：

- 默认本地 extractive/template 路径
- OpenAI-compatible HTTP 调用路径

`--model-config` 目前可消费：

- `provider`
- `base_url`
- `model`
- `api_key`
- `temperature`
- `timeout`

当 `provider` 为：

- `extractive` / `template` / `catalog-only`：走本地模板生成
- `local` / `echo`：保底走本地回显
- `openai` / `openai_compatible` / `compatible`：走兼容 `chat/completions` 的 HTTP 调用

## Current Capability Assessment

当前已经具备：

- 真正的网络抓取
- HTML/PDF artifact 写盘
- Wikipedia 实抓可用
- arXiv PDF 二级抓取
- LinkedIn cookie / storage state 导入与复用
- `--backend`、`--resume`、`--artifacts-dir`、`--strict`
- enrich 路由与 model-config 消费

当前仍然偏“基础版”的地方：

- enrich 的本地模板仍然比较轻，只是一个稳定执行骨架，不是高质量业务 prompt 系统
- Amazon/Base/LinkedIn 的结构化归一化还比较薄，更多是先保留通路
- adapter 已经可执行，但还不是完整的面向对象平台插件体系

## How To Extend It

### Add a New Platform

需要至少补这几处：

1. `references/url_templates.json`
2. `references/field_mappings.json`
3. `references/enrichment_catalog/<platform>.json`
4. `crawler/platforms/<platform>.py`
5. 如有特殊逻辑，再补 extract/normalize/enrich 支持

### Add a New Resource Type

最少要补：

- URL 模板
- discovery 字段映射
- adapter 的 `resource_types`
- normalize 输出字段

### Add a New Enrichment Group

至少补：

- field-group template
- prompt
- source fields
- 目标输出字段

如果需要真实模型执行，就让它走 `model-config` 路径，不要把网络调用散落到 dispatcher 里。

## Assessment of Current `SKILL.md`

结论：需要重写，而且应该重写成“纯 agent 指令版”。

原因有 4 个：

1. 当前 `SKILL.md` 混合了给人看的产品说明和给 agent 的执行规则，职责重叠。
2. 它没有充分反映当前已经实现的 adapter-execution、session reuse、artifacts、strict/resume 等细节。
3. 它对 enrich 的描述仍偏抽象，没有清楚区分“本地模板执行”和“OpenAI-compatible 调用”。
4. 它没有把 agent 真正应该优先查看的文件、执行顺序、恢复动作压缩成足够可执行的指令。

所以正确做法不是继续在当前 `SKILL.md` 上堆说明，而是：

- 人类说明放这份 overview
- agent 约束放重写后的 `SKILL.md`

## Recommended Reading Order

如果你是使用者：

1. 先读这份 overview
2. 再看 [`README.md`](/d:/kaifa/clawtroop/social-data-crawler/README.md)
3. 最后按需要看 sample input 和 `references/`

如果你是维护者：

1. 先读这份 overview 的架构部分
2. 再看 [`dispatcher.py`](/d:/kaifa/clawtroop/social-data-crawler/crawler/core/dispatcher.py)
3. 再看 [`platforms/base.py`](/d:/kaifa/clawtroop/social-data-crawler/crawler/platforms/base.py)
4. 然后看具体平台 adapter
5. 最后看 enrich / fetch / extract / tests
