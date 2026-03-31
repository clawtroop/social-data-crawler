# Social Data Crawler 项目介绍文档

## 1. 项目简介 (Project Overview)

`social-data-crawler` 是一个生产级、面向 AI Agent 优先的 Web 爬虫与数据丰富（Enrichment）框架。它专为需要稳定、结构化输出（而非原始页面转储）的 Agent 设计，能够从多个主流平台（如 LinkedIn、Amazon、arXiv 等）进行确定性的数据提取。

该项目摒弃了传统的单一爬取模式，采用了 **发现 (Discovery) → 获取 (Fetch) → 提取 (Extract) → 规范化 (Normalize) → 丰富 (Enrich) → 写入 (Write)** 的现代化流水线架构。通过本地执行、API 优先、会话持久化等设计理念，为大语言模型（LLM）和下游 Agent 提供高质量、高纯净度的上下文数据。

## 2. 核心特性 (Core Features)

- **三层核心流水线**：将数据处理严格划分为 Fetch（获取）、Extract（提取）、Enrich（丰富）三个独立且可插拔的阶段。
- **AI 驱动的数据丰富 (AI-powered Enrichment)**：将 LLM 结构化提取和数据增强作为一个独立的流水线阶段，支持基于大模型的生成式提取和基于正则/规则的抽取式增强。
- **智能多后端回退机制**：API 优先，若无稳定 API 则回退到页面抓取。支持 `HTTP`、`Playwright` 和 `Camoufox`（反指纹浏览器）等多种抓取后端，并支持在抓取失败时自动按策略升级后端。
- **LLM 友好的输出契约**：输出确定性的 JSONL 文件，包含清洗后的 `plain_text`、`markdown` 以及语义分块（`chunks`），直接可用作 LLM 的上下文。
- **会话与状态持久化**：针对 LinkedIn 等需要登录的平台，支持 Playwright 浏览器上下文和 Cookie 的持久化与复用，降低封控风险。
- **灵活的 URL 发现机制**：内置针对复杂平台（如 Amazon 评论/卖家图谱、arXiv 论文关系、LinkedIn 媒体链接）的 URL 发现与规范化脚本。

## 3. 架构与目录结构 (Architecture & Directory Structure)

项目整体包含约 10,000 行核心代码，采用声明式平台适配器和配置驱动的路由设计。

```text
social-data-crawler/
├── crawler/                              # 核心 Python 包
│   ├── cli.py                            # 命令行入口
│   ├── core/                             # 流水线编排调度
│   ├── discovery/                        # URL 规范化与构建
│   ├── fetch/                            # 数据获取层 (引擎、浏览器池、会话管理)
│   ├── extract/                          # 内容提取层 (HTML清洗、Trafilatura、分块)
│   ├── enrich/                           # 数据丰富层 (LLM客户端、正则提取、批处理)
│   ├── platforms/                        # 平台适配器 (Wikipedia, arXiv, Amazon等)
│   ├── normalize/                        # 输出规范化
│   └── output/                           # 结果写入 (JSONL, Summary, Artifacts)
├── urlDiscover/                          # 复杂 URL 发现机制与脚本
│   ├── Amazon/                           # Amazon 商品/卖家/评论 URL 发现
│   ├── arxiv/                            # arXiv 论文 URL 发现
│   └── MediaUrl/                         # LinkedIn/Wikipedia 媒体与实体 URL 发现
├── auto-browser/                         # 自动化浏览器集成 (VRD 会话管理)
├── references/                           # 配置驱动文件 (路由规则、等待策略、选择器等)
├── scripts/                              # 环境引导与测试脚本 (bootstrap, verify_env)
├── README.md                             # 项目快速入门
└── ARCHITECTURE_ANALYSIS.md              # 详细架构分析文档
```

## 4. 支持的平台与数据源 (Supported Platforms)

系统通过 `platforms/` 目录下的适配器实现了对以下数据源的深度支持：

- **Wikipedia (`wikipedia`)**：支持 `article`（文章）资源类型的抓取与解析。
- **arXiv (`arxiv`)**：支持 `paper`（论文）资源类型，提取元数据及摘要。
- **Amazon (`amazon`)**：支持 `product`（商品）、`seller`（卖家）和 `search`（搜索结果）资源类型。
- **Base (`base`)**：区块链数据源，支持 `address`（地址）、`transaction`（交易）、`token`（代币）和 `contract`（合约）。
- **LinkedIn (`linkedin`)**：支持 `profile`（个人主页）、`公司`（company）、`post`（帖子）和 `job`（职位）。
- **Generic (`generic`)**：通用网页抓取，支持任意公共 URL，通过 `http -> playwright -> camoufox` 链路进行智能路由和抓取。

## 5. 核心模块说明 (Core Modules)

### 5.1 URL 发现模块 (URL Discover & Discovery)
位于 `urlDiscover/` 和 `crawler/discovery/`。负责将非结构化的输入（如关键词、ID）转换为规范的、可抓取的 URL。`urlDiscover` 目录下包含了针对 Amazon 评论图谱、arXiv 论文网络以及 LinkedIn 复杂页面结构的独立发现脚本和方法论。

### 5.2 数据获取层 (Fetch Layer)
位于 `crawler/fetch/`。作为数据采集的引擎，负责网络请求和反爬对抗。
- **Backend Router**: 根据配置决定使用哪种后端。
- **Browser Pool & Session Manager**: 管理 Playwright 和 Camoufox 的浏览器实例池，复用 Context 和 Cookie，优化性能并维持登录状态。
- **Wait Strategy**: 针对不同平台（如 SPA 单页应用）实现智能的等待策略，确保 DOM 渲染完成。

### 5.3 内容提取层 (Extract Layer)
位于 `crawler/extract/`。负责从杂乱的 HTML 或 PDF 中提取核心内容。
- **Content Cleaner**: 移除 HTML 中的导航栏、页脚、广告等噪音（基于 CSS 选择器）。
- **Main Content**: 语义化主内容检测，支持通过 Trafilatura 提取文章正文，通过 Unstructured 解析 PDF。
- **Chunking**: 将长文本进行基于标题和段落的混合分块（Hybrid Chunking），直接输出 LLM 友好的格式。

### 5.4 数据丰富层 (Enrich Layer)
位于 `crawler/enrich/`。负责对提取出的纯文本进行结构化增强。
- **Extractive**: 极速的基于正则（Regex）和查找表（Lookup）的本地提取。
- **Generative**: 通过内置的 LLM Client 调用 OpenAI 兼容接口，根据预定义的 Schema（如 `linkedin_field_groups`）进行深度语义抽取和字段补全。

## 6. 技术栈 (Tech Stack)

- **核心语言**: Python 3
- **抓取与反爬 (Fetch)**:
  - `Playwright`: 用于需要执行 JavaScript 的动态页面抓取。
  - `Camoufox`: 专业的反指纹浏览器后端，用于应对高风险、强风控页面。
  - `httpx`: 用于高效的静态页面和 API 请求。
- **解析与提取 (Extract)**:
  - `Trafilatura`: 高效的网页正文提取库。
  - `Unstructured`: 用于处理 PDF 和富文本文件。
  - `Crawl4AI` (理念借鉴): 生成 LLM 友好的 Markdown 输出。
- **数据丰富与 AI (Enrich)**:
  - `OpenAI API 兼容客户端`: 用于生成式字段提取。
  - `Pydantic`: 用于数据契约和 Schema 校验。
- **架构设计**: 借鉴了 `Scrapy` 的流水线分层、重试机制和去重思想，但完全面向 Agent 进行了现代化重构。