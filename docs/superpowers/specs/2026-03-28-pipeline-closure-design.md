# Pipeline Closure Design

**Context**

`social-data-crawler` already has useful layer boundaries across CLI, dispatcher, platform adapters, fetch backends, and session storage. The current breakages come from runtime semantics being split across those layers without a single execution center. As a result, the documented capabilities and the actual runtime diverge.

This design closes the gap without expanding scope into LinkedIn content extraction. LinkedIn remains unchanged in this pass.

**Goals**

- Make `crawl`, `enrich`, and `run` execute through one explicit pipeline contract.
- Make backend fallback a real runtime behavior instead of dead configuration.
- Keep platform capability declarations aligned with executable support.
- Unify browser backend session semantics so authenticated fallbacks remain swappable.
- Add regression tests for the broken paths that currently escape coverage.

**Non-Goals**

- Rework LinkedIn post extraction.
- Add new platforms.
- Add parallel execution, queues, or async orchestration.

**Architecture**

Add a new runtime orchestration module at `crawler/core/pipeline.py`.

The module becomes the single place that maps a command to a sequence of stages:

- `crawl` runs crawl only
- `enrich` runs enrich only
- `run` runs crawl followed by enrich on the in-memory crawl results

`cli.py` will call this orchestration layer and remain responsible only for:

- argument parsing
- creating the output directory
- writing output files
- determining exit code

`dispatcher.py` remains the execution layer for crawl and enrich work, but it stops owning command semantics. It gains a focused record-level execution path that performs backend attempts and fallback resolution. Platform adapters continue to declare backend preferences through `resolve_backend(record, override_backend, retry_count)`, while dispatcher owns the retry loop and failure collection.

**Component Boundaries**

- `crawler/cli.py`
  - No command branching beyond invoking pipeline entrypoint.
  - No hidden assumption that `run == crawl`.
- `crawler/core/pipeline.py`
  - Defines command semantics.
  - Composes stage results.
  - Ensures `run` forwards crawled records into enrich without temporary output files.
- `crawler/core/dispatcher.py`
  - Executes crawl stage over input records or supplied in-memory records.
  - Executes enrich stage over input records or supplied in-memory records.
  - Owns backend attempt loop for a single record.
- `crawler/platforms/*.py`
  - Declare capability truthfully.
  - `base` gains full `contract` API support.
- `crawler/fetch/orchestrator.py`
  - Dispatches to backend implementations with a consistent backend signature.
- `crawler/fetch/playwright_backend.py`
  - Keeps existing storage-state behavior.
- `crawler/fetch/camoufox_backend.py`
  - Adopts the same `storage_state_path` contract as Playwright.

**Data Flow**

For `crawl`:

1. Read input records.
2. Resolve adapter and discovery data.
3. Execute fetch attempts through dispatcher-managed fallback loop.
4. Persist artifacts.
5. Extract and normalize.
6. Return normalized records and errors.

For `run`:

1. Execute the full crawl flow.
2. Enrich the successful crawl records in memory.
3. Return enriched records plus crawl and enrich errors.

For `enrich`:

1. Read input records.
2. Build platform enrichment request.
3. Route enrichment.
4. Return enriched records and errors.

**Fallback Model**

Fallback is promoted from metadata to runtime behavior.

Rules:

- If `--backend` is provided, honor it and do not auto-fallback.
- Otherwise, dispatcher will attempt backends by calling `adapter.resolve_backend(..., retry_count=n)` for increasing `n`.
- The attempt count is bounded by the adapter’s declared default backend plus fallback backend list.
- Failures during fetch trigger the next attempt.
- Non-fetch stages do not silently retry on another backend.

This keeps retry scope narrow and makes backend escalation explicit and testable.

**Base Platform Contract**

`base` currently declares `address`, `transaction`, `token`, and `contract`.

This design requires all four resource types to have:

- executable fetch path
- successful extract path
- stable normalize path

`contract` will be implemented through the API path instead of being left as a registered but unsupported type.

**Browser Session Contract**

Both browser backends must accept:

- `url`
- `storage_state_path`

The meaning of `storage_state_path` is consistent across backends:

- if a state file exists, use it as browser session input
- if browser execution refreshes state, write it back when possible

This preserves session reuse expectations in dispatcher and session store code.

**Error Handling**

- Missing auth session for auth-required platforms remains a pre-fetch validation error.
- Auth expiration remains classified from HTTP status responses when a session was present.
- Final crawl failure after exhausting backend attempts is reported once, with the last exception message.
- Enrich failures remain isolated per record.

**Testing**

Add regression coverage for:

- `run` producing enrichment output instead of crawl-only output
- dispatcher fallback across real adapter resolution and orchestrator dispatch
- `base` successful extraction path including JSON serialization
- `base contract` API path
- camoufox session-path propagation

**Tradeoffs**

Why this design over patching existing files:

- It introduces one execution center instead of continuing to spread runtime meaning across CLI and dispatcher.
- It keeps adapter APIs stable while making their declarations executable.
- It avoids a larger refactor into async workers or state machines, which would exceed the scope of the reported defects.

**Acceptance Criteria**

- `python -m crawler run ...` returns records with enrichment content.
- Backend fallback is observable in dispatcher tests without monkeypatching pure selection helpers alone.
- `base` address/transaction/token/contract all execute through registered support.
- camoufox can consume persisted session state via the same contract as Playwright.
- Existing non-LinkedIn behavior remains intact.
