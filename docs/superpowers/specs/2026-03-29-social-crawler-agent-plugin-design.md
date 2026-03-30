# Social Crawler Agent Plugin Design

## Goal

Add a deployable plugin and worker layer that lets `social-data-crawler` participate in distributed mining flows by claiming mining tasks, running local crawl jobs, and reporting results back to Platform Service. The plugin lives in a separate OpenClaw plugin project and calls `social-data-crawler` as an external skill/engine dependency.

## Scope

The first implementation targets miner-side execution only:

- send miner heartbeats
- claim `repeat-crawl` and `refresh` tasks
- transform claimed tasks into crawler JSONL input
- run local crawl jobs with the existing CLI
- transform crawl output into mining report payloads
- optionally export and submit Core submissions
- provide a plugin skeleton that external agent frameworks can install

Out of scope for this slice:

- validator task execution
- PoW / preflight enforcement
- settlement flows
- browser UI for operations

## Architecture

The implementation keeps crawler internals unchanged and adds a thin agent integration layer.

### New Python package

Create `crawler/agent/` for reusable runtime logic:

- `models.py`
  shared dataclasses for claimed tasks, report payloads, and worker config
- `task_mapper.py`
  converts Platform Service task payloads to crawler records and report payloads
- `platform_client.py`
  wraps HTTP calls to Platform Service Mining/Core endpoints
- `crawler_runner.py`
  runs existing `crawler` CLI commands against generated JSONL input
- `worker.py`
  orchestrates heartbeat, claim, crawl, report, and loop control

### Plugin scaffold

Create a separate plugin project, for example `openclaw-social-crawler-plugin/`:

- `openclaw.plugin.json`
  native OpenClaw plugin manifest
- `package.json`
  package metadata plus OpenClaw extension entrypoint
- `index.ts`
  plugin registration entry
- `src/tools.ts`
  OpenClaw tool registrations
- `scripts/run_tool.py`
  Python bridge that calls the crawler project

## Data flow

### Repeat crawl / refresh task flow

1. Worker sends miner heartbeat.
2. Worker claims a task from Mining API.
3. `task_mapper` normalizes the claim response into a `ClaimedTask`.
4. `crawler_runner` writes one-record JSONL input and runs local crawl.
5. Runner reads `records.jsonl` and returns the canonical record.
6. `task_mapper` converts the canonical record into a Mining report payload.
7. `platform_client` reports task completion.

### Core submission flow

1. A completed crawl run produces `records.jsonl`.
2. `export-submissions` converts records into Core submission payload.
3. `platform_client` submits payload to `/api/core/v1/submissions`.

## Error handling

- Claim endpoints returning no task should produce `None`, not exceptions.
- Missing task URL should fail fast before invoking crawler.
- Crawl failures should surface the task id, exit code, and output directory.
- Report failures should preserve the task output path so the run can be replayed.
- Worker loop should continue after per-task failures unless explicitly configured to stop.

## Configuration

Environment-backed worker config:

- `PLATFORM_BASE_URL`
- `PLATFORM_TOKEN`
- `MINER_ID`
- `HEARTBEAT_INTERVAL_SECONDS`
- `CLAIM_INTERVAL_SECONDS`
- `CRAWLER_OUTPUT_ROOT`
- `DEFAULT_BACKEND`
- optional `CRAWLER_COMMAND`

## Testing strategy

Add focused unit tests for:

- task mapping from mining claim payload to crawler input
- report payload generation from crawler output
- platform client request paths and auth headers
- crawler runner command construction
- worker single-iteration orchestration across heartbeat, claim, crawl, and report

Keep tests local and mock network/process boundaries through injected fakes.
