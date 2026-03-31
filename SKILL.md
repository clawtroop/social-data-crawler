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

Agent-first crawler skill for deterministic collection, extraction, and enrichment.

这个 skill 面向 agent 内部执行。CLI 片段用于说明契约，不要求用户手动跑整套命令。

## Use This Skill When

Use this skill when the task requires any of:

- build canonical URLs from dataset identifiers
- crawl `Wikipedia`, `arXiv`, `Amazon`, `Base`, `LinkedIn`, or `generic/page`
- collect readable text or markdown from HTML / PDF / API responses
- produce stable `records.jsonl` plus crawl artifacts
- enrich existing records with extractive or agent-executed generative field groups
- expand a seed set into more URLs through multi-hop discovery

Do not use this skill for:

- casual web browsing
- one-off search without structured output
- unsupported targets such as `Twitter/X`

## Command Choice

Choose commands by goal:

- need more URLs from seeds: `discover-crawl`
- already know the target pages and need content/chunks: `crawl`
- already have `records.jsonl` and only need enrichment: `enrich`
- need crawl plus enrich in one pass: `run`
- need to write agent responses back into `pending_agent` results: `fill-enrichment`

Do not expose `discover-map` as a public command. Discovery adapters may use mapping internally, but the public entrypoint is `discover-crawl`.

## Supported Platforms

| Platform | Resource Types | Preferred Backend |
| --- | --- | --- |
| `wikipedia` | `article` | `api` |
| `arxiv` | `paper` | `api` |
| `amazon` | `product`, `seller`, `search` | `http` |
| `base` | `address`, `transaction`, `token`, `contract` | `api` |
| `linkedin` | `profile`, `company`, `post`, `job`, `search` | `api` or browser |
| `generic` | `page` | `http` |

## Installation Gate

Before using the skill in a fresh environment:

- treat `metadata.openclaw.requires` as a coarse gate only
- run `./scripts/bootstrap.sh`
- on Windows, prefer `./scripts/bootstrap.ps1`
- wait for `scripts/verify_env.py` and `scripts/smoke_test.py` to pass before browser-backed runs

## Core Usage

Crawl:

```bash
python -m crawler crawl --input ./records.jsonl --output ./out
```

Enrich:

```bash
python -m crawler enrich --input ./out/records.jsonl --output ./out-enriched
```

Run full pipeline:

```bash
python -m crawler run --input ./records.jsonl --output ./out
```

Discovery crawl:

```bash
python -m crawler discover-crawl \
  --input ./seeds.jsonl \
  --output ./out-discovery \
  --max-depth 2 \
  --max-pages 100
```

Useful flags:

- `--backend api|http|playwright|camoufox`
- `--resume`
- `--strict`
- `--artifacts-dir <path>`
- `--css-schema <path>`
- `--extract-llm-schema <path>`
- `--enrich-llm-schema <path>`
- `--model-config <path>`
- `--auto-login`
- `--max-chunk-tokens <n>`
- `--chunk-overlap <n>`

## Runtime Model

Default execution uses the newer fetch/extract/enrich pipeline:

`discover -> FetchEngine -> ExtractPipeline -> EnrichPipeline -> write`

Practical rules:

- use the default pipeline unless you are debugging compatibility
- `--use-legacy-pipeline` exists only as a fallback path
- backend fallback is runtime behavior, not just metadata
- browser-backed retries can reuse normalized session state

Typical backend chains:

- `wikipedia` / `arxiv` / `base`: `api -> http -> playwright`
- `amazon`: `http -> playwright -> camoufox`
- `linkedin profile/company/search/job`: `api -> playwright -> camoufox`
- `linkedin post`: `playwright -> camoufox`
- `generic/page`: `http -> playwright -> camoufox`

## Discovery Rules

Use `discover-crawl` only when the task is to find more URLs.

Expect discovery-oriented outputs such as:

- `canonical_url`
- `seed_url`
- `hop_depth`
- `discovery_mode`
- `fetched`

Do not assume `discover-crawl` returns the same `structured` or `chunks` payloads as `crawl` / `run`.

## Input And Output

Input is JSONL. Each line must include:

- `platform`
- `resource_type`
- required platform-specific discovery fields

Each run writes:

- `records.jsonl`
- `errors.jsonl`
- `summary.json`
- `run_manifest.json`
- `artifacts/`

Most useful record fields:

- `status`
- `stage`
- `retryable`
- `error_code`
- `next_action`
- `plain_text`
- `markdown`
- `structured`
- `chunks`

Inspect outputs in this order:

1. `summary.json`
2. `errors.jsonl`
3. `records.jsonl`
4. `artifacts/`

## Auth And Sessions

`LinkedIn` and some browser-backed flows require cookies or persisted state.

Recommended agent workflow:

1. use `auto-browser` when login/captcha/human confirmation is needed
2. let the user complete only the browser-side confirmation step
3. pass the exported state through `--cookies` or let `--auto-login` refresh it

`cookies.json` may be:

- a raw cookie list
- a Playwright `storage_state` object
- a wrapper object with top-level `storage_state`

Common auth outcomes:

- `AUTH_REQUIRED`: provide state or enable `--auto-login`
- `AUTH_EXPIRED`: refresh and retry once

The crawler normalizes session state into `.sessions/` under the chosen output root and reuses it on reruns.

## Enrichment Model

Enrichment is extractive-first.

- if extractive confidence is sufficient, finish immediately
- if generation is needed and no model is configured, return `pending_agent`
- if model config exists, run the generative step directly
- use `fill-enrichment` only when the run intentionally deferred generation to the agent

Common field groups:

- `classifications`
- `linkables`
- `standardized_job_title`
- `skills_extraction`
- `about_summary`
- `summaries`
- `llm_schema`

## Recovery

- partial crawl failure: fix input/auth and rerun
- crawl complete but enrich missing: rerun `enrich` on prior `records.jsonl`
- require non-zero exit on any failure: use `--strict`
- append into an existing run tree: use `--resume`

Do not manually patch output files if a deterministic rerun is possible.

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

Quick validation rule:

- test the skill by running its public CLI directly
- do not build a wrapper script or ad-hoc harness unless you are debugging the crawler itself
- for `generic/page` discovery smoke, prefer stable docs-style sites such as `https://docs.python.org/3/`
- avoid using anti-bot-heavy or low-content pages as first validation seeds

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

## Auth Orchestration

Auth handling is now unified for `crawl`, `run`, and `discover-crawl`.

Use this rule strictly:

1. If the target platform does not require auth, run normally.
2. If the platform requires auth and `--cookies` or `output/.sessions/<platform>.json` already exists, reuse that session.
3. If the platform requires auth and there is no session:
   - without `--auto-login`, the crawler returns `AUTH_REQUIRED`
   - with `--auto-login`, the crawler launches `@social-data-crawler/auto-browser`, opens the login page, and waits for browser-side completion
4. If fetch fails with `AUTH_EXPIRED` and `--auto-login` is enabled, the crawler refreshes the session once through `auto-browser` and retries that failed item once

The user should only handle browser-side actions such as captcha, account/password input, scan, MFA, or confirmation screens.

### Agent Workflow For Auth Platforms

When `--auto-login` is enabled, the expected behavior is:

1. keep processing other records and platforms normally
2. open the auth platform in the shared VRD browser
3. if manual takeover is needed, show the `PUBLIC_URL` / VNC link to the user
4. wait for the user to click "已完成，继续"
5. export `<platform>.auto-browser.json`
6. normalize that export into `output/.sessions/<platform>.json`
7. retry only the failed item once, not the whole batch

If the browser-side step times out or export fails, the crawler writes a structured auth error into `errors.jsonl`. These auth errors may include:

- `public_url`
- `login_url`
- `error_code`
- `next_action`

### Auth Input Formats

`--cookies` may be any of:

- a raw cookie list
- a Playwright `storage_state` JSON object
- a wrapper object with a top-level `storage_state` field exported by `auto-browser`

The crawler normalizes this into `output/.sessions/<platform>.json` and reuses it on later runs in the same output directory.

### Recommended CLI Forms

Manual session import:

```bash
python -m crawler crawl --input ./linkedin.jsonl --output ./out --cookies ./cookies.json
```

Automatic login and retry:

```bash
python -m crawler run --input ./records.jsonl --output ./out --auto-login
```

Automatic discovery plus auth handling:

```bash
python -m crawler discover-crawl --input ./seeds.jsonl --output ./out --auto-login --resume
```

### Error Semantics

- `AUTH_REQUIRED`: no valid session is available for an auth-required platform
- `AUTH_EXPIRED`: an existing session was rejected and should be refreshed
- `AUTH_INTERACTIVE_TIMEOUT`: the crawler exposed `PUBLIC_URL`, but the browser-side login was not completed in time
- `AUTH_SESSION_EXPORT_FAILED`: the user finished login but session export failed
- `AUTH_AUTO_LOGIN_FAILED`: `auto-browser` could not start or open the login page

### Resume Policy

Prefer failed-item retry, not full rerun:

1. inspect `errors.jsonl`
2. keep the same `--output`
3. rerun the same command with `--resume`
4. only resubmit failed auth items when you are driving the retry from the agent side

`LinkedIn` is still the main auth-required platform today, but this auth flow is intentionally platform-agnostic and should be reused for any future auth-required platform.

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
