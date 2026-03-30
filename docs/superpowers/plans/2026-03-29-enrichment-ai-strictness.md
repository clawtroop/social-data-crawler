# Enrichment AI Strictness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make generative enrichment groups require a working AI configuration and fail explicitly instead of silently falling back.

**Architecture:** Keep extractive-only groups on rule-based enrichment, but route all generative strategies through the registry-backed enrichment pipeline. The main `run_enrich` flow should surface strict generative failures as record-level enrichment errors, while preserving unknown-group skips and extractive-only behavior.

**Tech Stack:** Python 3.11, pytest, dataclasses, existing enrichment registry and orchestrator modules

---

## Task 1: Lock behavior with tests

**Files:**

- Modify: `crawler/tests/test_enrichment.py`
- Modify: `crawler/tests/test_enrich_pipeline.py`

- [ ] Add tests showing legacy `route_enrichment` now raises when a generative group has no AI config.
- [ ] Add tests showing `EnrichPipeline` fails `extractive_then_generative` groups when AI config is missing.
- [ ] Add tests showing extractive-only groups still succeed without AI.

## Task 2: Enforce strict generative execution

**Files:**

- Modify: `crawler/enrich/orchestrator.py`
- Modify: `crawler/enrich/pipeline.py`
- Modify: `crawler/enrich/generative/llm_client.py`

- [ ] Add explicit generative configuration validation helpers.
- [ ] Remove silent fallback behavior on generative paths.
- [ ] Return or raise explicit errors for missing config, empty model responses, and failed model calls.

## Task 3: Connect main enrich flow to strict semantics

**Files:**

- Modify: `crawler/core/dispatcher.py`
- Modify: `crawler/tests/test_dispatcher.py`

- [ ] Make `run_enrich` surface strict generative failures as enrichment errors.
- [ ] Preserve extractive-only success behavior.
- [ ] Verify `run` mode inherits the same behavior.

## Task 4: Verify targeted regressions

**Files:**

- Test: `crawler/tests/test_enrichment.py`
- Test: `crawler/tests/test_enrich_pipeline.py`
- Test: `crawler/tests/test_dispatcher.py`

- [ ] Run focused pytest commands for changed tests.
- [ ] Fix any failures caused by tightened semantics.
- [ ] Re-run the focused suite until clean.
