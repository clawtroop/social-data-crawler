# Social Data Crawler

Agent-first local crawler skill for `Wikipedia`, `arXiv`, `Amazon`, `Base`, and `LinkedIn`.

## What It Does

The redesigned package is built for agents that need stable structured outputs instead of raw page dumps. The intended pipeline is:

`discovery -> fetch -> extract -> normalize -> enrich -> write`

Key properties:

- one local Python CLI
- one skill entry point
- deterministic output files
- explicit status and recovery fields for agents
- AI-powered data enhancement as a standalone stage
- API-first where stable APIs exist, page fetch fallback where they do not
- `run` executes `crawl -> enrich` as one pipeline, instead of crawl-only aliasing
- backend fallback is a real runtime retry path rather than static adapter metadata

## Reference Capabilities Integrated

- `Playwright`: browser contexts, storage state, waiting, interception, screenshots, DOM capture
- `Camoufox`: anti-detection browser backend for high-risk pages
- `Firecrawl`: resilient URL-to-clean-content fallback philosophy
- `Crawl4AI`: LLM-friendly Markdown and JSON output contracts
- `Scrapy`: queue, retry, dedupe, rate-limit, and pipeline layering
- `Trafilatura`: article body extraction
- `Unstructured`: PDF and rich-document parsing

## Supported Platforms

- `wikipedia` -> `article`
- `arxiv` -> `paper`
- `amazon` -> `product`, `seller`, `search`
- `base` -> `address`, `transaction`, `token`, `contract`
- `linkedin` -> `profile`, `company`, `post`, `job`
- `generic` -> `page` for arbitrary public URLs routed through `http -> playwright -> camoufox`

## Agent Workflow

1. Prepare JSONL input records with explicit `platform` and `resource_type`.
2. Run the CLI in `crawl`, `enrich`, or `run` mode.
3. Inspect `summary.json` first.
4. If the run is partial or failed, inspect `errors.jsonl`.
5. Read `records.jsonl` for canonical or enriched records.
6. Use `artifacts/` only when deeper debugging is needed.

## OpenClaw Integration

This project remains the crawler engine and skill only.

If you want to install it into OpenClaw as a native plugin, keep that plugin in a separate project such as `openclaw-social-crawler-plugin/` and let the plugin call this crawler through its CLI or exported Python helpers.

Common execution controls:

- `--backend api|http|playwright|camoufox`
- `--resume` to append into an existing run directory
- `--artifacts-dir <path>` to move artifact persistence
- `--css-schema <path>` to opt into CSS-based structured extraction for HTML pages
- `--extract-llm-schema <path>` to opt into extract-stage LLM schema extraction
- `--enrich-llm-schema <path>` to opt into enrich-stage LLM schema extraction
- `--model-config <path>` to provide OpenAI-compatible model settings for LLM schema execution
- `--strict` to return a non-zero exit code if any record fails

If `--backend` is omitted, the dispatcher may escalate through adapter-declared fallback backends after fetch failures. Browser backends share the same session-state contract, so stored auth state can be reused across fallback attempts.

## Output Contract

Each run is expected to produce:

- `records.jsonl`
- `errors.jsonl`
- `summary.json`
- `run_manifest.json`
- `artifacts/`

Agent-oriented record control fields:

- `status`
- `stage`
- `retryable`
- `error_code`
- `next_action`

Extraction-oriented content fields:

- `plain_text`: compact LLM-ready body text after main-content extraction
- `markdown`: compact LLM-ready Markdown after the same reduction pass
- `structured`: platform or page-level structured fields
- `chunks`: semantic chunks generated from the compacted content

Artifact layering for HTML records is intentionally single-path:

`raw page html -> cleaned_html -> compact plain_text/markdown -> chunks`

Notes:

- `cleaned_html` is the reduced HTML body used to derive the final text outputs
- `plain_text` and `markdown` are not raw page dumps; they are compacted outputs with obvious boilerplate removed
- chunking runs on the compacted content, not on the raw extracted page

## CSS Extraction

HTML extraction supports an explicit opt-in CSS schema:

```bash
python -m crawler crawl \
  --input ./records.jsonl \
  --output ./out \
  --css-schema ./references/css_schema.example.json
```

The schema format is intentionally small:

- `title`: one selector for the record title
- `description`: one selector for the record description
- `fields`: additional structured fields

Each field supports:

- `selector`: required CSS selector
- `multiple`: optional, return a list when `true`
- `attribute`: optional, read an attribute instead of text, for example `href`

When `--css-schema` is not provided, the default extraction path is unchanged.

## LLM Schema Extraction

Two separate opt-in LLM schema paths are supported:

- extract stage: extends `structured`
- enrich stage: extends `enrichment`

Example:

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

- extract-stage schema only adds or overrides `structured` fields
- enrich-stage schema only writes to `enrichment`
- if no schema path is provided, the default pipeline is unchanged
- if schema execution fails, the crawler records the failure explicitly instead of silently falling back

## LinkedIn Auth

`LinkedIn` usually requires cookies or persisted browser state.

Use:

```bash
python -m crawler crawl --input ./linkedin.jsonl --output ./out --cookies ./cookies.json
```

`cookies.json` may be any of:

- a raw cookie list
- a Playwright `storage_state` object
- a wrapper object with a top-level `storage_state` field exported by another tool

The crawler normalizes session state into `output/.sessions/` and reuses it on later runs in the same output directory. Browser-backed fetches also refresh the stored Playwright state after a successful run.

If a run fails with `error_code: AUTH_REQUIRED`, provide valid cookies or storage state and rerun, optionally with `--resume`.

If a run fails with `error_code: AUTH_EXPIRED`, refresh the login session and rerun the same command.

## Installation

```bash
./scripts/bootstrap.sh
```

PowerShell on Windows:

```powershell
./scripts/bootstrap.ps1
```

CMD-friendly wrapper on Windows:

```cmd
scripts\bootstrap.cmd
```

### What `bootstrap.sh` does

`metadata.openclaw.requires` should only be treated as a coarse availability gate.
It checks whether the host looks plausible for activation, but it does not prove Python packages,
browser bundles, or system libraries are actually ready. `bootstrap.sh` is the real installation step.

- checks required host binaries such as `bash` and `python3`
- prints host dependency guidance before browser install
- performs best-effort host dependency checks before browser install
- creates `.venv`
- installs layered dependency files
- runs `python -m playwright install`
- runs `python -m camoufox fetch`
- runs [`scripts/verify_env.py`](scripts/verify_env.py) to validate installed Python modules and Playwright browser bundles for the selected profile
- runs a local smoke test via [`scripts/smoke_test.py`](scripts/smoke_test.py)

### Dependency layers

- [`requirements-core.txt`](requirements-core.txt): runtime packages needed for HTTP/API crawling and extraction
- [`requirements-browser.txt`](requirements-browser.txt): browser-backed crawling packages
- [`requirements-ocr.txt`](requirements-ocr.txt): OCR / PDF / rich document parsing
- [`requirements-dev.txt`](requirements-dev.txt): test and development tools
- [`requirements.txt`](requirements.txt): aggregate file that includes all layers

Both bootstrap scripts support `INSTALL_PROFILE`:

- `minimal`: core only
- `browser`: core + browser
- `full`: core + browser + OCR/PDF + dev

### Host dependency guidance

- Linux: install the system libraries Playwright browsers need before expecting browser-backed crawling to work
- macOS: install Xcode Command Line Tools first
- Windows: run `bootstrap.sh` from Git Bash or WSL

Use [`scripts/host_diagnostics.py`](scripts/host_diagnostics.py) directly when you need a structured host prerequisite report:

```bash
python ./scripts/host_diagnostics.py --json
```

The smoke test is intentionally local and deterministic. It starts a temporary local HTTP server, crawls a `generic/page` URL through the standard CLI, and verifies `records.jsonl` plus `summary.json`.

Use [`scripts/verify_env.py`](scripts/verify_env.py) directly when you need a fast post-install check without running the full smoke test:

```bash
python ./scripts/verify_env.py --profile browser
```

Machine-readable output for agents:

```bash
python ./scripts/verify_env.py --profile browser --json
```

## Status

This directory is under active rewrite. Legacy `scripts/` and old fixtures are being replaced by the new package-oriented implementation.
