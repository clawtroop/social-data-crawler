# Social Data Crawler

Agent-first local crawler for `Wikipedia`, `arXiv`, `Amazon`, `Base`, `LinkedIn`, and `generic/page`.

The runtime is built for stable structured output, not raw page dumping:

`discover -> fetch -> extract -> enrich -> write`

## Commands

- `discover-crawl`: start from seed URLs and keep expanding until depth/page limits
- `crawl`: fetch known targets into canonical records plus artifacts/chunks
- `enrich`: enrich an existing `records.jsonl`
- `run`: `crawl -> enrich` in one pass
- `fill-enrichment`: fill `pending_agent` enrichment results
- `export-submissions`: convert crawler output into downstream submission payloads

## Platforms

- `wikipedia` -> `article`
- `arxiv` -> `paper`
- `amazon` -> `product`, `seller`, `search`
- `base` -> `address`, `transaction`, `token`, `contract`
- `linkedin` -> `profile`, `company`, `post`, `job`, `search`
- `generic` -> `page`

## Quick Start

Install:

```bash
./scripts/bootstrap.sh
```

Windows PowerShell:

```powershell
./scripts/bootstrap.ps1
```

Crawl:

```bash
python -m crawler crawl --input ./records.jsonl --output ./out
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

## Runtime Model

Backend behavior is adapter-driven:

- start from the preferred backend
- retry through the fallback chain on fetch failure
- reuse saved browser session state where possible
- surface auth or captcha blockers explicitly

Typical backend chains:

- `wikipedia` / `arxiv` / `base`: `api -> http -> playwright`
- `amazon`: `http -> playwright -> camoufox`
- `linkedin profile/company/search/job`: `api -> playwright -> camoufox`
- `linkedin post`: `playwright -> camoufox`
- `generic/page`: `http -> playwright -> camoufox`

## Input And Output

Input is JSONL. Each line must include:

- `platform`
- `resource_type`
- platform-specific discovery fields

Example:

```json
{"platform":"wikipedia","resource_type":"article","title":"Artificial intelligence"}
{"platform":"amazon","resource_type":"product","asin":"B09V3KXJPB"}
{"platform":"linkedin","resource_type":"profile","public_identifier":"john-doe-ai"}
```

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

## Optional Schema Features

CSS schema extraction:

```bash
python -m crawler crawl \
  --input ./records.jsonl \
  --output ./out \
  --css-schema ./references/css_schema.example.json
```

LLM schema extraction:

```bash
python -m crawler run \
  --input ./records.jsonl \
  --output ./out \
  --extract-llm-schema ./references/extract_llm_schema.example.json \
  --enrich-llm-schema ./references/enrich_llm_schema.example.json \
  --model-config ./model.json \
  --field-group llm_schema
```

Rules:

- extract-stage schema extends `structured`
- enrich-stage schema writes to `enrichment`
- schema failures are recorded explicitly

## Auth And Sessions

`LinkedIn` and some browser-backed flows may require cookies or persisted Playwright state.

```bash
python -m crawler crawl --input ./linkedin.jsonl --output ./out --cookies ./cookies.json
```

`cookies.json` may be:

- a raw cookie list
- a Playwright `storage_state` object
- a wrapper object with top-level `storage_state`

The crawler normalizes this into `output/.sessions/` and reuses it on reruns. With `--auto-login`, it can trigger the built-in browser auth flow and retry once when stored state is expired.

Common auth outcomes:

- `AUTH_REQUIRED`: provide cookies/storage state or enable `--auto-login`
- `AUTH_EXPIRED`: refresh and retry

## Enrichment

Enrichment is extractive-first.

- if an extractive rule is strong enough, the field group finishes immediately
- if generation is needed and no model is configured, the result becomes `pending_agent`
- use `fill-enrichment` to write agent-produced responses back into `records.jsonl`

## Recovery

- partial crawl failure: fix input/auth and rerun
- crawl complete, enrich missing: rerun `enrich` on prior `records.jsonl`
- need non-zero exit on any failure: use `--strict`
- need append/resume semantics: use `--resume`

## Notes

- This repo is the crawler engine and skill, not a monolithic plugin host.
- Keep runtime examples small and deterministic.
