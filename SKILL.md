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

## OpenClaw Single-Repo Install

This repo also ships the OpenClaw plugin source and packaged runtime.

Primary install entrypoints:

- `./scripts/install_openclaw_integration.sh`
- `./scripts/install_openclaw_integration.ps1`

The installer builds `dist/openclaw-plugin`, updates `~/.openclaw/openclaw.json` or `OPENCLAW_CONFIG_PATH`, installs a workspace skill wrapper, and prefers `awpWalletTokenRef` SecretRef wiring when a fresh `awp-wallet` token is not already available.

这个 skill 面向 agent 内部执行。下面的 CLI 片段只说明调用契约，不要求用户手动跑整套命令。

## Use This Skill When

Use this skill when the task requires any of:

- build canonical URLs from dataset identifiers
- crawl `Wikipedia`, `arXiv`, `Amazon`, `Base`, `LinkedIn`, or `generic/page`
- collect readable text or markdown from HTML, PDF, or API responses
- produce stable `records.jsonl` plus crawl artifacts
- enrich existing records with extractive or generative field groups
- expand a seed set into more URLs through multi-hop discovery

Do not use this skill for:

- casual web browsing
- one-off search without structured output
- unsupported targets such as `Twitter/X`

## Command Choice

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

Default execution path:

`discover -> FetchEngine -> ExtractPipeline -> EnrichPipeline -> write`

Practical rules:

- backend fallback is runtime behavior, not just metadata
- browser-backed retries can reuse normalized session state
- surface auth/captcha/human-gated blockers explicitly

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

1. use `auto-browser` when login, captcha, or human confirmation is needed
2. let the user complete only the browser-side confirmation step
3. pass exported state through `--cookies` or let `--auto-login` refresh it

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
- use `fill-enrichment` only when generation was intentionally deferred to the agent

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
