# Social Data Crawler: Production-Grade Architecture Refactor

> **Version**: 1.0
> **Date**: 2026-03-29
> **Scope**: 面向 AI/LLM 消费的社媒数据采集系统架构重构

---

## 1. Executive Summary

### 1.1 业务目标

构建 **LLM-enhanced 数据产品平台**：采集社媒数据（LinkedIn、Twitter、Amazon 等）→ 结构化提取 → LLM enrichment → 数据产品输出。

### 1.2 技术目标

将现有采集系统重构为三层架构，核心改进：

1. **Fetch Engine**: Browser Pool、智能等待、风险分级 Backend 路由、Session 管理
2. **Extract Pipeline**: 内容清洗、主体识别、智能 Chunking、结构化字段提取
3. **Enrich Pipeline**: Extractive 优先 + Generative 按需、批量执行、成本追踪

### 1.3 关键借鉴

- **Playwright**: Browser Context 池化、storage_state 持久化、wait_for 策略、请求拦截
- **Camoufox**: 风险分级启用、指纹配置、与 Playwright 的无缝切换

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Layer 1: Fetch Engine                     │
│  Browser Pool · 智能等待 · 请求拦截 · Session 管理 · 反检测  │
│  输出：RawFetchResult (html/json + screenshot + metadata)    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Layer 2: Extract Pipeline                   │
│  HTML → Clean Content · Chunking · Structured Fields         │
│  输出：ExtractedDocument (chunks[] + structured + metadata)  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 Layer 3: Enrich Pipeline                     │
│  Extractive (无LLM) · Generative (LLM) · Batch/Streaming    │
│  输出：EnrichedRecord (标准 field_groups + confidence)       │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Layer 1: Fetch Engine

### 3.1 Directory Structure

```
crawler/fetch/
├── engine.py              # FetchEngine 主入口
├── browser_pool.py        # Browser/Context 池化管理
├── session_manager.py     # Session 有效性检测与刷新
├── wait_strategy.py       # 平台特定的等待策略
├── backend_router.py      # 根据风险等级选择 backend
├── request_interceptor.py # 请求拦截与资源过滤
├── backends/
│   ├── http.py            # httpx 纯 HTTP
│   ├── playwright.py      # Playwright 标准模式
│   ├── camoufox.py        # Camoufox 反检测模式
│   └── api.py             # 平台私有 API
└── models.py              # RawFetchResult 数据结构
```

### 3.2 Core Components

#### 3.2.1 RawFetchResult

```python
@dataclass
class RawFetchResult:
    url: str
    final_url: str                    # 重定向后最终 URL
    backend: Literal["http", "playwright", "camoufox", "api"]
    fetch_time: datetime

    content_type: str
    html: str | None
    json_data: dict | None
    content_bytes: bytes | None

    screenshot: bytes | None
    dom_snapshot: str | None

    status_code: int
    headers: dict[str, str]
    cookies_updated: bool

    wait_strategy_used: str
    resources_blocked: list[str]
    timing: FetchTiming
```

#### 3.2.2 BrowserPool

- 预热 Browser 实例，Context 按 platform 隔离
- `max_contexts_per_platform: int = 2`
- 自动保存/刷新 storage_state
- 避免冷启动，提升 2-3x 速度

#### 3.2.3 WaitStrategy

配置驱动 (`references/wait_strategies.json`):

```json
{
  "linkedin": {
    "profile": {
      "wait_for_selector": "section.artdeco-card",
      "wait_for_network_quiet": true,
      "network_quiet_timeout_ms": 2000,
      "max_wait_ms": 15000,
      "scroll_to_load": false
    }
  }
}
```

执行顺序：
1. 等待关键元素出现
2. 等待网络安静（可选）
3. 滚动加载（可选）

#### 3.2.4 BackendRouter

配置驱动 (`references/backend_routing.json`):

```json
{
  "rules": [
    {"match": {"platform": "linkedin", "resource_type": "post"}, "initial_backend": "camoufox"},
    {"match": {"platform": "linkedin", "requires_auth": true}, "initial_backend": "api", "fallback_chain": ["playwright", "camoufox"]},
    {"match": {"platform": "amazon"}, "initial_backend": "playwright", "fallback_chain": ["camoufox"]}
  ],
  "failure_escalation": {
    "403": "escalate",
    "429": "retry_later",
    "5xx": "retry_same"
  }
}
```

#### 3.2.5 SessionManager

- 检测关键 cookie 是否存在且未过期
- 可选：发轻量级 API 请求验证
- 自动从 Context 提取并持久化 storage_state

---

## 4. Layer 2: Extract Pipeline

### 4.1 Directory Structure

```
crawler/extract/
├── pipeline.py              # ExtractPipeline 主入口
├── content_cleaner.py       # HTML 清洗
├── main_content.py          # 主体内容识别
├── chunking/
│   ├── strategy.py          # ChunkingStrategy 基类
│   ├── heading_chunker.py   # 按 heading 层级分块
│   ├── paragraph_chunker.py # 按段落分块
│   ├── token_chunker.py     # 按 token 数分块
│   └── hybrid_chunker.py    # 混合策略
├── structured/
│   ├── json_extractor.py    # API JSON 提取
│   └── schema_mapper.py     # 映射到标准 schema
└── models.py
```

### 4.2 Core Data Structures

#### 4.2.1 ContentChunk

```python
@dataclass
class ContentChunk:
    chunk_id: str                     # "{doc_id}#chunk_{index}"
    chunk_index: int

    text: str
    markdown: str

    section_path: list[str]           # ["About", "Company Overview"]
    heading_text: str | None
    heading_level: int | None

    char_offset_start: int
    char_offset_end: int
    source_element: str | None

    token_count_estimate: int
```

#### 4.2.2 ExtractedDocument

```python
@dataclass
class ExtractedDocument:
    doc_id: str
    source_url: str
    platform: str
    resource_type: str
    extracted_at: datetime

    chunks: list[ContentChunk]
    total_chunks: int

    full_text: str
    full_markdown: str

    structured: StructuredFields
    metadata: DocumentMetadata
    quality: ExtractionQuality
    raw_artifacts: list[ArtifactRef]
```

### 4.3 Core Components

#### 4.3.1 ContentCleaner

多层清洗策略：
1. 移除噪音标签 (nav, footer, aside, script, style)
2. 移除平台特定噪音选择器
3. 移除隐藏元素 (display:none)
4. 移除 class/id 匹配噪音模式的元素

#### 4.3.2 MainContentExtractor

策略优先级：
1. 平台特定选择器（最可靠）
2. 语义化标签 (`<main>`, `<article>`)
3. 内容密度分析（文本/标签比）
4. Trafilatura 兜底

#### 4.3.3 HybridChunker

配置参数：
- `max_chunk_tokens: int = 512`
- `min_chunk_tokens: int = 100`
- `overlap_tokens: int = 50`

执行流程：
1. 按 heading 切分成 sections，保留层级路径
2. 小 section 整块输出
3. 大 section 按段落切分，贪心合并到接近 max_chunk_tokens
4. 块间保留 overlap 保持上下文连贯

---

## 5. Layer 3: Enrich Pipeline

### 5.1 Directory Structure

```
crawler/enrich/
├── pipeline.py              # EnrichPipeline 主入口
├── router.py                # 路由到 enricher
├── extractive/
│   ├── regex_enricher.py
│   ├── rule_enricher.py
│   └── lookup_enricher.py
├── generative/
│   ├── llm_client.py
│   ├── prompt_templates/
│   └── output_parser.py
├── batch/
│   ├── batch_manager.py
│   └── async_executor.py
└── schemas/
    └── field_group_registry.py
```

### 5.2 Two-Tier Enrichment Architecture

```
Field Group Request
        │
        ▼
   EnrichmentRouter
        │
   ┌────┴────┐
   ▼         ▼
Extractive  Generative
(无LLM)     (LLM)
   │         │
   └────┬────┘
        ▼
  Result Merger
```

### 5.3 FieldGroupSpec

```python
@dataclass
class FieldGroupSpec:
    name: str
    description: str
    required_source_fields: list[str]
    output_fields: list[OutputFieldSpec]
    strategy: Literal["extractive_only", "generative_only", "extractive_then_generative"]
    extractive_config: ExtractiveConfig | None
    generative_config: GenerativeConfig | None
```

### 5.4 Enrichment Strategies

| Strategy | 使用场景 | 示例 |
|----------|---------|------|
| `extractive_only` | 纯规则/查表可解决 | email 提取、URL 解析 |
| `generative_only` | 必须用 LLM | about_summary、sentiment |
| `extractive_then_generative` | 先尝试规则，不够再 LLM | job_title 标准化、skills 提取 |

### 5.5 EnrichedRecord

```python
@dataclass
class EnrichedRecord:
    doc_id: str
    source_url: str
    platform: str
    resource_type: str

    chunks: list[ContentChunk]
    structured: StructuredFields

    enrichment_results: dict[str, FieldGroupResult]
    enriched_fields: dict[str, Any]
    enrichment_summary: EnrichmentSummary
```

### 5.6 Batch Execution

- `max_concurrency: int = 10`
- `batch_size: int = 50`
- 异步并发执行
- 进度回调支持

---

## 6. Configuration Files

### 6.1 New Config Files

| File | Purpose |
|------|---------|
| `references/wait_strategies.json` | 平台特定等待策略 |
| `references/backend_routing.json` | Backend 选择规则 |
| `references/noise_selectors.json` | 平台噪音元素选择器 |
| `references/main_content_selectors.json` | 主体内容选择器 |
| `references/field_group_registry.json` | Field group 定义 |
| `references/lookup_tables/onet_job_mapping.json` | Job title 映射表 |
| `references/skill_patterns.json` | 技能提取正则模式 |

### 6.2 Existing Config Files (Retained)

| File | Changes |
|------|---------|
| `references/url_templates.json` | No change |
| `references/field_mappings.json` | No change |
| `references/rate_limits.json` | Will be consumed by FetchEngine |

---

## 7. Migration Plan

### 7.1 Phase 1: Fetch Engine (Week 1)

1. Implement BrowserPool
2. Implement WaitStrategy with config
3. Implement BackendRouter with config
4. Refactor existing backends to new interface
5. Add SessionManager

### 7.2 Phase 2: Extract Pipeline (Week 1-2)

1. Implement ContentCleaner
2. Implement MainContentExtractor
3. Implement HybridChunker
4. Implement StructuredFieldExtractor
5. Define ExtractedDocument schema

### 7.3 Phase 3: Enrich Pipeline (Week 2)

1. Define FieldGroupSpec registry
2. Implement Extractive enrichers (regex, lookup)
3. Implement Generative enricher with prompt templates
4. Implement BatchEnrichmentExecutor
5. Integrate with existing CLI

### 7.4 Phase 4: Integration & Testing (Week 2-3)

1. End-to-end integration tests
2. Performance benchmarks
3. Documentation updates

---

## 8. Key Design Decisions

### 8.1 Why Three Layers?

- **Separation of concerns**: Each layer has a single responsibility
- **Independent evolution**: Can improve extraction without touching fetch
- **Testability**: Each layer can be unit tested in isolation
- **Parallel development**: Teams can work on different layers

### 8.2 Why Extractive-First Enrichment?

- **Cost control**: LLM calls are expensive; avoid when unnecessary
- **Latency**: Regex/lookup is instant; LLM adds 1-3s per call
- **Determinism**: Rules produce consistent results
- **Fallback**: Graceful degradation when LLM unavailable

### 8.3 Why Config-Driven?

- **No code changes for new platforms**: Add JSON config, not Python code
- **A/B testing**: Easy to experiment with different strategies
- **Visibility**: Non-engineers can review/modify behavior
- **Version control**: Config changes are tracked in git

---

## 9. Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Fetch cold start time | 2-3s | <500ms (pool hit) |
| LinkedIn profile success rate | ~70% | >95% |
| Content extraction noise ratio | ~40% | <10% |
| Chunk token utilization | N/A | 80-100% of max |
| Enrichment LLM call rate | 100% | <30% (extractive handles rest) |
| End-to-end latency (single record) | ~10s | <5s |

---

## 10. Open Questions

1. **Storage state encryption**: Should we encrypt stored cookies/sessions?
2. **Proxy integration**: Where does proxy rotation fit in the architecture?
3. **Rate limit coordination**: How do multiple instances share rate limit state?
4. **Chunk overlap strategy**: Fixed overlap vs semantic boundary overlap?

---

## Appendix A: Playwright Best Practices Borrowed

| Playwright Feature | Our Implementation |
|-------------------|-------------------|
| Browser Context isolation | BrowserPool with per-platform contexts |
| storage_state persistence | SessionManager auto-save/load |
| wait_for_selector | WaitStrategy config |
| wait_for_load_state | WaitStrategy network_quiet |
| page.screenshot | RawFetchResult.screenshot |
| request interception | RequestInterceptor (optional) |

## Appendix B: Camoufox Best Practices Borrowed

| Camoufox Feature | Our Implementation |
|-----------------|-------------------|
| Fingerprint rotation | BackendRouter risk-based selection |
| Stealth mode | High-risk platforms default to camoufox |
| Playwright compatibility | Same Page interface, seamless switch |
