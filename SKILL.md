---
name: social-data-crawler
description: Use when an agent needs to discover URLs, crawl public or authenticated records, persist crawl artifacts, and optionally run structured AI enrichment for Wikipedia, arXiv, Amazon, Base, or LinkedIn.
metadata:
  openclaw:
    bootstrap: ./scripts/bootstrap.sh
    windows_bootstrap: ./scripts/bootstrap.ps1
    smoke_test: ./scripts/smoke_test.py
    requires:
      bins:
        - python3
      anyBins:
        - pip3
        - pip
---

# Social Data Crawler

Agent-first crawler skill for deterministic record collection and follow-up enrichment.

这个 skill 面向 **agent 内部执行**。文档中的 CLI 示例用于说明调用形式与参数契约，不应要求用户手动运行命令。

## Use This Skill When

Use this skill when the task requires any of:

- build canonical URLs from dataset identifiers
- crawl `Wikipedia`, `arXiv`, `Amazon`, `Base`, or `LinkedIn`
- crawl arbitrary public pages through `generic/page`
- extract readable Markdown or text from HTML or PDFs
- **produce LLM-ready chunked content** for RAG or embedding pipelines
- write stable structured outputs for downstream agents
- rerun enrichment on already crawled records

Do not use this skill for:

- generic exploratory web browsing
- one-off search tasks without structured output requirements
- unsupported platforms such as `Twitter/X`

## Supported Platforms

| Platform | Resource Types | Default Backend | Special Notes |
| --- | --- | --- | --- |
| `wikipedia` | `article` | `api` | MediaWiki API first, page fetch fallback |
| `arxiv` | `paper` | `api` | arXiv Atom API first, PDF artifact path |
| `amazon` | `product`, `seller`, `search` | `http` | HTTP first, then `playwright`, then `camoufox` |
| `base` | `address`, `transaction`, `token`, `contract` | `api` | Base RPC / explorer API first |
| `linkedin` | `profile`, `company`, `post`, `job`, `search` | `api` | Voyager API first when auth is present; `post` stays browser-oriented |
| `generic` | `page` | `http` | Direct URL input, then fallback chain `playwright -> camoufox` |

## Core Commands

Use this command selection rule strictly:

| Goal | Command | Notes |
| --- | --- | --- |
| discover more related URLs from one or more seeds | `discover-crawl` | the only public discovery CLI entrypoint; supports multi-hop expansion |
| fetch known pages into canonical records with chunks | `crawl` | no automatic URL expansion |
| fetch and then enrich in one pass | `run` | no automatic URL expansion |
| enrich existing crawl output only | `enrich` | reads prior `records.jsonl` |
| fill `pending_agent` enrichment results | `fill-enrichment` | legacy/manual completion path |

Do **not** invent or use `discover-map` from this skill. That path is now an **internal adapter capability**, not a public CLI entrypoint. If you need automatic discovery, always start with `discover-crawl`.

## Installation Gate

Before using this skill in a fresh environment:

- `metadata.openclaw.requires` is only a trigger gate, not an installer
- run `./scripts/bootstrap.sh`
- on Windows, prefer `./scripts/bootstrap.ps1`
- do not trigger browser-backed flows until bootstrap finishes
- if bootstrap reports missing host libraries, fix them first and rerun
- treat `scripts/verify_env.py` success as the package and browser-bundle validation step
- treat `scripts/smoke_test.py` success as the minimum usable state

Run crawl only:

```bash
python -m crawler crawl --input ./records.jsonl --output ./out
```

Run enrich only on existing records:

```bash
python -m crawler enrich --input ./out/records.jsonl --output ./out-enriched
```

Run crawl plus enrich:

```bash
python -m crawler run --input ./records.jsonl --output ./out
```

`run` executes the full `crawl -> enrich` path in one command and writes enriched records to the target output directory.

Run automatic discovery with multi-hop expansion:

```bash
python -m crawler discover-crawl \
  --input ./seeds.jsonl \
  --output ./out-discovery \
  --max-depth 2 \
  --max-pages 100
```

`discover-crawl` is the only public discovery command. It fetches each seed, lets the platform discovery adapter emit `spawned_candidates`, deduplicates them, and keeps expanding until it hits `--max-depth` or `--max-pages`.

Use execution controls when needed:

```bash
python -m crawler crawl \
  --input ./records.jsonl \
  --output ./out \
  --backend http \
  --resume \
  --artifacts-dir ./out/artifacts \
  --strict
```

## Pipeline Architecture (Default)

The crawler uses a 3-layer pipeline architecture by default:

1. **FetchEngine** — BrowserPool, intelligent wait strategies, automatic backend escalation
2. **ExtractPipeline** — HTML cleaning, main content detection, semantic chunking
3. **EnrichPipeline** — Extractive-first enrichment, LLM only when needed

```bash
python -m crawler run \
  --input ./records.jsonl \
  --output ./out \
  --max-chunk-tokens 512 \
  --chunk-overlap 50
```

### Pipeline Options

| Option | Default | Description |
| ------ | ------- | ----------- |
| `--use-legacy-pipeline` | off | Fall back to old dispatcher-based pipeline |
| `--max-chunk-tokens` | 512 | Maximum tokens per chunk |
| `--chunk-overlap` | 50 | Overlap tokens between chunks |

### Discovery Controls

| Option | Default | Description |
| ------ | ------- | ----------- |
| `--max-depth` | 2 | Maximum hop depth for `discover-crawl` |
| `--max-pages` | 100 | Maximum discovered/fetched records for `discover-crawl` |
| `--sitemap-mode` | `include` | Sitemap handling mode for discovery adapters |
| `--resume` | off | Reuse prior `.discovery_state` and append outputs |

## Discovery Mode

Use `discover-crawl` when the task is "I only have a seed and need the crawler to keep finding the next URLs."

What it does:

1. reads each input line as a depth-0 `DiscoveryCandidate`
2. fetches the current page with `FetchEngine`
3. calls the platform discovery adapter's `crawl()` method
4. accepts any returned `spawned_candidates`
5. deduplicates by `platform + canonical_url`
6. enqueues new candidates until depth/page limits are reached

What it does **not** do:

- it does not run the full extract/chunk/enrich pipeline
- it does not replace `crawl` or `run`
- it does not expose `discover-map` as a CLI choice

Agent decision rules:

- If the user wants **more URLs** or **multi-hop expansion**, use `discover-crawl`
- If the user already knows the target pages and wants **content/chunks**, use `crawl`
- If the user already has `records.jsonl` and wants **structured fields**, use `enrich`
- If the user wants both content and enrichment in one pass, use `run`

Internal note for agents: discovery adapters may still use `map()` / `MapResult` internally to convert fetched HTML into candidate URLs. Treat that as an implementation detail and do not expose it as a public command choice.

### Output Fields

Records include LLM-ready chunked content:

```json
{
  "chunks": [
    {
      "chunk_id": "abc123#chunk_0",
      "chunk_index": 0,
      "text": "...",
      "markdown": "...",
      "section_path": ["Introduction", "Overview"],
      "heading_text": "Overview",
      "heading_level": 2,
      "char_offset_start": 0,
      "char_offset_end": 512,
      "token_count_estimate": 128
    }
  ],
  "extraction_quality": {
    "content_ratio": 0.42,
    "noise_removed": 15,
    "chunking_strategy": "hybrid:platform_selector",
    "total_chunks": 8
  }
}
```

Use `chunks[]` directly for:
- RAG vector embedding (each chunk has context via `section_path`)
- LLM context window management (respect `token_count_estimate`)
- Source attribution (use `char_offset_*` for highlighting)

## Input Contract

Input must be JSONL. Each line must include:

- `platform`
- `resource_type`
- discovery fields required by that platform

Examples:

```json
{"platform":"wikipedia","resource_type":"article","title":"Artificial intelligence"}
{"platform":"arxiv","resource_type":"paper","arxiv_id":"2401.12345"}
{"platform":"amazon","resource_type":"product","asin":"B09V3KXJPB"}
{"platform":"base","resource_type":"transaction","tx_hash":"0xabc..."}
{"platform":"linkedin","resource_type":"profile","public_identifier":"john-doe-ai"}
{"platform":"generic","resource_type":"page","url":"https://www.notion.so/..."}
```

For `discover-crawl`, each line must include at least:

- `url` or `canonical_url`
- optional `platform`
- optional `resource_type`

## Output Contract

Each run writes:

- `records.jsonl`
- `errors.jsonl`
- `summary.json`
- `run_manifest.json`
- `artifacts/`

Key agent-facing fields in `records.jsonl`:

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

## LinkedIn Auth

`LinkedIn` usually requires authenticated browser state.

Recommended agent workflow:

1. invoke `auto-browser` to open the login page in the shared VRD browser
2. ask the user to complete only the browser-side login / captcha / confirmation steps
3. export the current browser session from `auto-browser`
4. pass the exported session file into this skill as `--cookies`

Internal CLI form:

```bash
python -m crawler crawl --input ./linkedin.jsonl --output ./out --cookies ./cookies.json
```

`cookies.json` may be any of:

- a raw cookie list
- a Playwright `storage_state` JSON object
- a wrapper object with a top-level `storage_state` field exported by another tool

The crawler normalizes this into `output/.sessions/<platform>.json` and reuses it on later runs in the same output directory. Browser-backed fetches also refresh the stored Playwright state after a successful run.

If a run fails with `error_code: AUTH_REQUIRED`:

1. Inspect `errors.jsonl`
2. Provide valid cookies or storage state
3. Rerun the same command
4. Use `--resume` if you want to append into the same output directory

If the error is `AUTH_EXPIRED`, refresh the login session and rerun the same command.

The user should only complete the web login action itself. Session export, retry, and rerun are all agent responsibilities.

## Autonomous Fallback Policy

The agent owns backend selection. Do not ask the user whether to switch from `api` to `http` or browser mode.

Default behavior:

- try the platform's preferred backend first
- if it fails, automatically escalate through the configured fallback chain
- continue until a backend succeeds or the chain is exhausted
- only interrupt the user for login, captcha, permissions, or other human-gated blockers

Preferred chains:

- `wikipedia` / `arxiv` / `base`: `api -> http -> playwright`
- `amazon` / `generic`: `http -> playwright -> camoufox`
- `linkedin profile/company/search/job`: `api -> playwright -> camoufox`
- `linkedin post`: `playwright -> camoufox`

If content looks partial, the agent should attempt the next backend automatically before reporting back.

## Enrichment Rules

Enrichment is **extractive-first, agent-generative on demand**. No API key is needed.

### How It Works

1. **Extractive** (lookup tables, regex patterns) runs first — zero cost, instant
2. If extractive succeeds with high confidence → done
3. If extractive fails or has low confidence → returns `pending_agent` with the LLM prompt
4. **Agent executes the prompt itself** using its own LLM capability
5. Agent fills results back via `fill-enrichment` command

### Field Groups

| Group | Strategy | Description |
|-------|----------|-------------|
| `classifications` | extractive_only | Classify record into categories via lookup |
| `linkables` | extractive_only | Extract cross-system identifiers via regex |
| `standardized_job_title` | extractive_then_generative | O*NET lookup, LLM fallback for rare titles |
| `skills_extraction` | extractive_then_generative | Regex pattern matching, LLM for complex cases |
| `about_summary` | generative_only | Always needs LLM |
| `summaries` | generative_only | Always needs LLM |

### Agent Integration (Recommended)

使用 `AgentEnrichmentExecutor` 一步完成 enrichment，无需手动协调 pending_agent 回填流程：

```python
from crawler.enrich.agent_executor import AgentEnrichmentExecutor, enrich_with_llm

# 方式 1: 传入 LLM 调用函数（最简单）
async def my_llm(prompt: str, system: str = None) -> str:
    # 使用 agent 自己的 LLM 能力
    return await agent.generate(prompt, system)

result = await enrich_with_llm(
    document={"platform": "linkedin", "about": "10年工程师经验..."},
    field_groups=["linkedin_profiles_about", "linkedin_profiles_skills"],
    llm_call=my_llm,
    model_capabilities={"vision": False}
)

# result.structured.fields 包含所有补全字段
print(result.structured.fields["about_summary"])
print(result.structured.fields["skills_extracted"])


# 方式 2: 使用 Executor 实例（更多控制）
executor = AgentEnrichmentExecutor(
    llm_call=my_llm,
    model_capabilities={"vision": True}
)
result = await executor.enrich(document, field_groups)


# 方式 3: 使用 subagent 并行执行（最快）
executor = AgentEnrichmentExecutor(
    llm_call=my_llm,
    use_subagents=True,
    spawn_subagent=agent.spawn_subagent,  # async (name, prompt, system) -> str
)
result = await executor.enrich(document, field_groups, parallel=True)


# 方式 4: 自动选择字段组
result = await executor.auto_enrich(document)  # 根据 platform/resource_type 自动选择
```

### CLI Workflow (Legacy)

CLI 方式仍然可用，适合批量处理或调试：

```bash
# Step 1: Run enrichment — extractive runs, generative returns pending_agent
python -m crawler enrich \
  --input ./out/records.jsonl \
  --output ./out-enriched \
  --field-group summaries \
  --field-group classifications

# Step 2: Check for pending_agent results in records.jsonl
# Look for: "status": "pending_agent", "agent_prompt": "...", "output_fields": [...]

# Step 3: Agent executes each agent_prompt using its own LLM capability
# and writes responses to a JSON file:
# {
#   "https://example.com:summaries": "{\"summary\": \"A concise summary...\"}",
#   "https://example.com:about_summary": "{\"about_summary\": \"...\", \"about_topics\": [...], \"about_sentiment\": \"...\"}"
# }

# Step 4: Fill results back into records
python -m crawler fill-enrichment \
  --records ./out-enriched/records.jsonl \
  --responses ./agent_responses.json
```

## Recovery Guidance

Always inspect outputs in this order:

1. `summary.json`
2. `errors.jsonl`
3. `records.jsonl`
4. `artifacts/`

Use these recovery patterns:

- Crawl partial failure: fix input/auth and rerun
- Crawl complete, enrich missing: rerun `enrich` on prior `records.jsonl`
- Need deterministic non-zero exit on failures: use `--strict`
- Need to keep adding records to one run tree: use `--resume`

## What To Inspect In Code First

When working on this skill, inspect these files first:

**Core Pipeline:**
1. [`pipeline.py`](crawler/core/pipeline.py) — command routing, new vs legacy pipeline selection
2. [`dispatcher.py`](crawler/core/dispatcher.py) — legacy crawl/enrich execution
3. [`base.py`](crawler/platforms/base.py) — platform adapter base class

**New 3-Layer Pipeline:**
4. [`fetch/engine.py`](crawler/fetch/engine.py) — FetchEngine with BrowserPool
5. [`extract/pipeline.py`](crawler/extract/pipeline.py) — ExtractPipeline with chunking
6. [`enrich/pipeline.py`](crawler/enrich/pipeline.py) — EnrichPipeline with extractive-first strategy

**Platform Adapters:**
7. one concrete adapter under [`crawler/platforms/`](crawler/platforms)

**Configuration Files:**

| File | Purpose |
|------|---------|
| [`references/url_templates.json`](references/url_templates.json) | URL canonicalization patterns |
| [`references/field_mappings.json`](references/field_mappings.json) | Input field normalization |
| [`references/backend_routing.json`](references/backend_routing.json) | Backend selection rules per platform |
| [`references/wait_strategies.json`](references/wait_strategies.json) | Page wait strategies per platform |
| [`references/noise_selectors.json`](references/noise_selectors.json) | HTML noise element selectors |
| [`references/main_content_selectors.json`](references/main_content_selectors.json) | Main content CSS selectors |
| [`references/skill_patterns.json`](references/skill_patterns.json) | Skill extraction regex patterns |

## Operational Model

### Legacy Pipeline (default)

```
discovery → fetch → extract → normalize → enrich → write
```

- Dispatcher drives execution via `adapter.fetch_record()`
- Backend fallback through adapter-declared `fallback_backends`
- All fetch operations now route through `unified_fetch()` → `FetchEngine`

### New Pipeline (`--use-new-pipeline`)

```
discovery → FetchEngine → ExtractPipeline → EnrichPipeline → write
           ↓              ↓                 ↓
        BrowserPool    Chunking         Extractive-first
        WaitStrategy   Cleaning         LLM on demand
        SessionMgr     Structured
```

**FetchEngine features:**
- `BrowserPool` — reuses browser contexts, avoids cold starts
- `WaitStrategy` — per-platform intelligent waiting (selector + network quiet + scroll)
- `BackendRouter` — config-driven backend selection with automatic escalation
- `SessionManager` — detects expired sessions, auto-refreshes storage state

**ExtractPipeline features:**
- `ContentCleaner` — removes nav, footer, ads, hidden elements
- `MainContentExtractor` — finds article body via platform selectors → semantic tags → density analysis
- `HybridChunker` — splits by headings first, then paragraphs, respects token limits

**EnrichPipeline features:**
- `FieldGroupRegistry` — declarative field group definitions
- `ExtractiveEnricher` — regex + lookup table enrichment (free, instant)
- `GenerativeEnricher` — LLM calls only when extractive fails or for complex fields
- `BatchExecutor` — async parallel enrichment with progress tracking

### Backend Selection

Backends are selected via `references/backend_routing.json`:

```json
{
  "rules": [
    {"match": {"platform": "linkedin", "requires_auth": true}, "initial_backend": "api", "fallback_chain": ["playwright", "camoufox"]},
    {"match": {"platform": "amazon"}, "initial_backend": "http", "fallback_chain": ["playwright", "camoufox"]},
    {"match": {"platform": "wikipedia"}, "initial_backend": "api", "fallback_chain": ["http", "playwright"]}
  ]
}
```

On fetch failure:
- `403` → escalate to next backend
- `429` → retry same backend after delay
- `5xx` → retry same backend

## Agent Instructions

### General

- Prefer `crawl` first, then `enrich`, unless the task explicitly needs both in one pass.
- Preserve `records.jsonl` as the source of truth for follow-up runs.
- Do not manually edit output files if structured rerun is possible.
- When a platform requires auth, prefer supplying cookies/storage state instead of bypassing checks.
- When debugging content quality, inspect `artifacts/` before changing extraction logic.
- For browser-gated auth flows, invoke `auto-browser` and keep all CLI execution on the agent side; the user should only interact with the web page when prompted.
- Do not ask the user to choose `api`, `http`, or browser mode. The agent should auto-escalate and report the result.
- If the first extraction is partial, keep escalating within the configured chain before asking the user anything.

### When to Use Legacy Pipeline

The new 3-layer pipeline is the default. Use `--use-legacy-pipeline` only when:

- You need maximum compatibility with existing downstream code that expects the old output format
- You're debugging platform adapter issues
- You need raw HTML/markdown without chunking overhead

The default pipeline is recommended for:

- LLM consumption (RAG, embedding, summarization)
- Semantic chunks with section context
- Content quality optimization
- Automatic HTML noise removal

### Chunking Guidance

| Content Type | Recommended `--max-chunk-tokens` |
|--------------|----------------------------------|
| Dense technical docs | 256-512 |
| Articles/blog posts | 512-768 |
| Long-form content | 768-1024 |

Set `--chunk-overlap` to ~10% of max tokens for context continuity.
