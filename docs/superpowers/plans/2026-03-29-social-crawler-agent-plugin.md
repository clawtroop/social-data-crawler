# Social Crawler Agent Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a separate OpenClaw plugin project and worker layer so `social-data-crawler` can claim mining tasks, execute local crawl jobs, and report results back to Platform Service without mixing plugin code into the skill project.

**Architecture:** Add a new `crawler.agent` package for reusable protocol logic and a `plugins/social-crawler-agent` scaffold for installation and execution. Keep crawler fetch/extract/enrich internals unchanged and integrate through CLI/API boundaries.

**Tech Stack:** Python 3.11+, `httpx`, pytest, existing `crawler` CLI

---

### Task 1: Agent data models and mapping

**Files:**
- Create: `crawler/agent/models.py`
- Create: `crawler/agent/task_mapper.py`
- Test: `crawler/tests/test_agent_task_mapper.py`

- [ ] Add failing tests for claim payload normalization and report payload mapping.
- [ ] Implement task dataclasses plus mapping helpers.
- [ ] Run `pytest crawler/tests/test_agent_task_mapper.py -v`.

### Task 2: Platform client

**Files:**
- Create: `crawler/agent/platform_client.py`
- Test: `crawler/tests/test_platform_client.py`

- [ ] Add failing tests for heartbeat, claim, report, and Core submission requests.
- [ ] Implement `PlatformClient` with auth headers and endpoint methods.
- [ ] Run `pytest crawler/tests/test_platform_client.py -v`.

### Task 3: Crawler runner and worker orchestration

**Files:**
- Create: `crawler/agent/crawler_runner.py`
- Create: `crawler/agent/worker.py`
- Test: `crawler/tests/test_agent_worker.py`

- [ ] Add failing tests for generated input files, CLI invocation, and one-loop execution.
- [ ] Implement runner and worker loop with injected dependencies for testability.
- [ ] Run `pytest crawler/tests/test_agent_worker.py -v`.

### Task 4: Separate plugin scaffold

**Files:**
- Create: `../openclaw-social-crawler-plugin/openclaw.plugin.json`
- Create: `../openclaw-social-crawler-plugin/package.json`
- Create: `../openclaw-social-crawler-plugin/index.ts`
- Create: `../openclaw-social-crawler-plugin/src/tools.ts`
- Create: `../openclaw-social-crawler-plugin/scripts/run_tool.py`
- Modify: `README.md`

- [ ] Add OpenClaw-native plugin files in the separate plugin project.
- [ ] Document the skill/plugin separation in both READMEs.

### Task 5: Verification

**Files:**
- Verify: `crawler/tests/test_agent_task_mapper.py`
- Verify: `crawler/tests/test_platform_client.py`
- Verify: `crawler/tests/test_agent_worker.py`

- [ ] Run `pytest crawler/tests/test_agent_task_mapper.py crawler/tests/test_platform_client.py crawler/tests/test_agent_worker.py -v`.
- [ ] Fix any failures and rerun until green.
