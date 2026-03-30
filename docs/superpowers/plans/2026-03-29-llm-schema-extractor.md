# LLM Schema Extractor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add opt-in LLM schema extraction to extract and enrich flows without changing the default pipeline.

**Architecture:** Introduce one shared LLM schema runtime, then connect it to extract-stage structured extraction and enrich-stage field-group execution through separate schema files. Keep all defaults unchanged when no schema paths are configured.

**Tech Stack:** Python, pytest, httpx, existing crawler extract/enrich pipelines

---

### Task 1: Config Surface

**Files:**
- Modify: `crawler/contracts.py`
- Modify: `crawler/cli.py`
- Test: `crawler/tests/test_cli.py`
- Test: `crawler/tests/test_contracts.py`

- [ ] Add config fields for `extract_llm_schema_path`, `enrich_llm_schema_path`, and `model_config_path`.
- [ ] Add CLI flags for the same three fields.
- [ ] Add tests that verify parsing and normalization.

### Task 2: Shared Runtime

**Files:**
- Create: `crawler/schema_runtime/model_config.py`
- Create: `crawler/schema_runtime/llm_executor.py`
- Test: `crawler/tests/test_llm_schema_runtime.py`

- [ ] Write failing tests for model-config loading and JSON response parsing.
- [ ] Implement the minimal shared runtime.
- [ ] Verify tests pass.

### Task 3: Extract-Stage LLM Schema

**Files:**
- Create: `crawler/extract/structured/llm_schema_extractor.py`
- Modify: `crawler/extract/pipeline.py`
- Modify: `crawler/core/pipeline.py`
- Test: `crawler/tests/test_extract_pipeline.py`

- [ ] Write failing tests for opt-in extract-stage schema merging.
- [ ] Implement extractor-stage LLM schema execution and `StructuredFields` merge behavior.
- [ ] Verify default path still passes.

### Task 4: Enrich-Stage LLM Schema

**Files:**
- Modify: `crawler/enrich/pipeline.py`
- Modify: `crawler/enrich/models.py`
- Test: `crawler/tests/test_enrich_pipeline.py`

- [ ] Write failing tests for opt-in enrich-stage schema group execution.
- [ ] Implement a dedicated field-group result path for enrich schema extraction.
- [ ] Verify pending/failure semantics remain explicit.

### Task 5: Docs and Examples

**Files:**
- Modify: `README.md`
- Modify: `docs/project-overview.md`
- Create: `references/extract_llm_schema.example.json`
- Create: `references/enrich_llm_schema.example.json`

- [ ] Add minimal usage docs and example schema files.
- [ ] Verify examples match the implemented config names.
