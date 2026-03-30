# Pipeline Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align documented crawler behavior with actual runtime execution by centralizing command orchestration, making backend fallback real, completing Base capability support, and unifying browser session contracts.

**Architecture:** Add `crawler/core/pipeline.py` as the command-semantic entrypoint, keep dispatcher focused on stage execution, and move fetch fallback into a record-level dispatcher executor. Unify browser backend signatures so session-aware fallback remains interchangeable.

**Tech Stack:** Python 3.11+, pytest, httpx, Playwright, Camoufox

---

### Task 1: Add Pipeline Entry Point

**Files:**
- Create: `crawler/core/pipeline.py`
- Modify: `crawler/cli.py`
- Test: `crawler/tests/test_pipeline.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from crawler.cli import parse_args
from crawler.core.pipeline import run_command


def test_run_command_executes_crawl_then_enrich(monkeypatch, workspace_tmp_path: Path) -> None:
    config = parse_args(["run", "--input", "input.jsonl", "--output", str(workspace_tmp_path / "out")])

    monkeypatch.setattr(
        "crawler.core.pipeline.run_crawl",
        lambda config, records=None: ([{"platform": "wikipedia", "resource_type": "article", "status": "success"}], []),
    )
    monkeypatch.setattr(
        "crawler.core.pipeline.run_enrich",
        lambda config, records=None: ([{**records[0], "enrichment": {"status": "routed"}}], []),
    )

    records, errors = run_command(config)

    assert errors == []
    assert records[0]["enrichment"]["status"] == "routed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest crawler/tests/test_pipeline.py::test_run_command_executes_crawl_then_enrich -v`
Expected: FAIL with `ModuleNotFoundError` or missing `run_command`

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

from crawler.contracts import CrawlCommand, CrawlerConfig

from .dispatcher import run_crawl, run_enrich


def run_command(config: CrawlerConfig) -> tuple[list[dict], list[dict]]:
    if config.command is CrawlCommand.CRAWL:
        return run_crawl(config)
    if config.command is CrawlCommand.ENRICH:
        return run_enrich(config)
    crawled_records, crawl_errors = run_crawl(config)
    enriched_records, enrich_errors = run_enrich(config, records=crawled_records)
    return enriched_records, [*crawl_errors, *enrich_errors]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest crawler/tests/test_pipeline.py::test_run_command_executes_crawl_then_enrich -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add crawler/core/pipeline.py crawler/cli.py crawler/tests/test_pipeline.py
git commit -m "refactor crawler command pipeline"
```

### Task 2: Make Dispatcher Accept In-Memory Records And Real Fallback Attempts

**Files:**
- Modify: `crawler/core/dispatcher.py`
- Test: `crawler/tests/test_dispatcher.py`

- [ ] **Step 1: Write the failing test**

```python
import json

from crawler.cli import parse_args
from crawler.core.dispatcher import run_crawl


def test_run_crawl_retries_with_adapter_fallback(monkeypatch, workspace_tmp_path) -> None:
    input_path = workspace_tmp_path / "input.jsonl"
    output_dir = workspace_tmp_path / "out"
    input_path.write_text(json.dumps({"platform": "amazon", "resource_type": "product", "asin": "B000"}) + "\n", encoding="utf-8")

    attempted_backends = []

    class FakeAdapter:
        requires_auth = False
        fallback_backends = ("playwright",)

        def resolve_backend(self, record, override_backend=None, retry_count=0):
            return "http" if retry_count == 0 else "playwright"

        def fetch_record(self, record, discovered, backend, storage_state_path=None):
            attempted_backends.append(backend)
            if backend == "http":
                raise RuntimeError("blocked")
            return {"backend": backend, "url": discovered["canonical_url"], "content_type": "text/html", "text": "<html><body>ok</body></html>"}

        def extract_content(self, record, fetched):
            return {"metadata": {"title": "ok"}, "plain_text": "ok", "markdown": "ok", "document_blocks": []}

        def normalize_record(self, record, discovered, extracted, supplemental):
            return {"title": "ok"}

    monkeypatch.setattr("crawler.core.dispatcher.get_platform_adapter", lambda platform: FakeAdapter())
    monkeypatch.setattr("crawler.core.dispatcher.build_url", lambda record: {"canonical_url": "https://example.com", "fields": {}, "artifacts": {}})

    records, errors = run_crawl(parse_args(["crawl", "--input", str(input_path), "--output", str(output_dir)]))

    assert errors == []
    assert attempted_backends == ["http", "playwright"]
    assert records[0]["title"] == "ok"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest crawler/tests/test_dispatcher.py::test_run_crawl_retries_with_adapter_fallback -v`
Expected: FAIL because only the first backend is attempted

- [ ] **Step 3: Write minimal implementation**

```python
def _crawl_records(config: CrawlerConfig, source_records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ...


def _fetch_with_attempts(adapter, record, discovered, storage_state_path, override_backend):
    max_attempts = 1 if override_backend else 1 + len(getattr(adapter, "fallback_backends", ()))
    last_error = None
    for retry_count in range(max_attempts):
        backend = adapter.resolve_backend(record, override_backend, retry_count=retry_count)
        try:
            return backend, adapter.fetch_record(record, discovered, backend, storage_state_path)
        except Exception as exc:
            last_error = exc
    raise last_error


def run_crawl(config: CrawlerConfig, records: list[dict[str, Any]] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return _crawl_records(config, records or _read_jsonl(config.input_path))


def run_enrich(config: CrawlerConfig, records: list[dict[str, Any]] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_records = records or _read_jsonl(config.input_path)
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest crawler/tests/test_dispatcher.py::test_run_crawl_retries_with_adapter_fallback -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add crawler/core/dispatcher.py crawler/tests/test_dispatcher.py
git commit -m "refactor crawl fallback execution"
```

### Task 3: Complete Base Platform Capability Truthfully

**Files:**
- Modify: `crawler/platforms/base_chain.py`
- Test: `crawler/tests/test_base_chain.py`

- [ ] **Step 1: Write the failing tests**

```python
from crawler.platforms.base_chain import _extract_base, _fetch_base_api


def test_extract_base_serializes_result_payload() -> None:
    extracted = _extract_base(
        {"resource_type": "address"},
        {"json_data": {"result": {"balance": "10"}}, "content_type": "application/json", "url": "https://base.org"},
    )

    assert '"balance": "10"' in extracted["plain_text"]


def test_fetch_base_api_supports_contract(monkeypatch) -> None:
    calls = []

    def fake_fetch_api_get(*, canonical_url, api_endpoint, headers=None):
        calls.append((canonical_url, api_endpoint))
        return {"url": canonical_url, "json_data": {"result": [{"SourceCode": "contract C {}"}]}, "content_type": "application/json"}

    monkeypatch.setattr("crawler.platforms.base_chain.fetch_api_get", fake_fetch_api_get)

    result = _fetch_base_api(
        {"resource_type": "contract"},
        {"canonical_url": "https://basescan.org/address/0xabc#code", "fields": {"contract_address": "0xabc"}},
        None,
    )

    assert result["json_data"]["result"][0]["SourceCode"] == "contract C {}"
    assert "getsourcecode" in calls[0][1]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest crawler/tests/test_base_chain.py -v`
Expected: FAIL with `NameError: name 'json' is not defined` and unsupported contract path

- [ ] **Step 3: Write minimal implementation**

```python
import json


def _fetch_base_api(record: dict, discovered: dict, storage_state_path: str | None) -> dict:
    ...
    if resource_type == "contract":
        api_key = os.environ.get("BASESCAN_API_KEY", "")
        endpoint = (
            "https://api.basescan.org/api"
            f"?module=contract&action=getsourcecode&address={discovered['fields']['contract_address']}"
        )
        if api_key:
            endpoint += f"&apikey={api_key}"
        return fetch_api_get(canonical_url=discovered["canonical_url"], api_endpoint=endpoint)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest crawler/tests/test_base_chain.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add crawler/platforms/base_chain.py crawler/tests/test_base_chain.py
git commit -m "fix base platform capability coverage"
```

### Task 4: Unify Camoufox Session Contract

**Files:**
- Modify: `crawler/fetch/camoufox_backend.py`
- Modify: `crawler/fetch/orchestrator.py`
- Test: `crawler/tests/test_fetch_pipeline.py`

- [ ] **Step 1: Write the failing test**

```python
from crawler.fetch.orchestrator import fetch_with_backend


def test_fetch_with_backend_passes_storage_state_to_camoufox(monkeypatch) -> None:
    seen = {}

    monkeypatch.setattr(
        "crawler.fetch.orchestrator.fetch_with_camoufox",
        lambda url, storage_state_path=None: {
            "backend": "camoufox",
            "url": url,
            "storage_state_path": storage_state_path,
        },
    )

    result = fetch_with_backend(
        "https://example.com",
        platform="linkedin",
        requires_browser=True,
        retry_count=2,
        backend="camoufox",
        storage_state_path="session.json",
    )

    assert result["storage_state_path"] == "session.json"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest crawler/tests/test_fetch_pipeline.py::test_fetch_with_backend_passes_storage_state_to_camoufox -v`
Expected: FAIL because orchestrator or backend signature drops the state path

- [ ] **Step 3: Write minimal implementation**

```python
def fetch_with_camoufox(url: str, storage_state_path: str | None = None) -> dict:
    ...


def fetch_with_backend(...):
    ...
    if backend == "camoufox":
        return fetch_with_camoufox(url, storage_state_path=storage_state_path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest crawler/tests/test_fetch_pipeline.py::test_fetch_with_backend_passes_storage_state_to_camoufox -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add crawler/fetch/camoufox_backend.py crawler/fetch/orchestrator.py crawler/tests/test_fetch_pipeline.py
git commit -m "unify browser session backend contract"
```

### Task 5: Rewire CLI To Use Pipeline And Prove Run Output

**Files:**
- Modify: `crawler/cli.py`
- Modify: `crawler/tests/test_dispatcher.py`
- Test: `crawler/tests/test_dispatcher.py`

- [ ] **Step 1: Write the failing test**

```python
import json

from crawler.cli import main


def test_run_command_writes_enriched_records(monkeypatch, workspace_tmp_path) -> None:
    input_path = workspace_tmp_path / "input.jsonl"
    output_dir = workspace_tmp_path / "out"
    input_path.write_text(json.dumps({"platform": "wikipedia", "resource_type": "article", "title": "AI"}) + "\n", encoding="utf-8")

    monkeypatch.setattr(
        "crawler.cli.run_command",
        lambda config: (
            [{"platform": "wikipedia", "resource_type": "article", "enrichment": {"status": "routed"}}],
            [],
        ),
    )

    exit_code = main(["run", "--input", str(input_path), "--output", str(output_dir)])

    records = [json.loads(line) for line in (output_dir / "records.jsonl").read_text(encoding="utf-8").splitlines()]
    assert exit_code == 0
    assert records[0]["enrichment"]["status"] == "routed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest crawler/tests/test_dispatcher.py::test_run_command_writes_enriched_records -v`
Expected: FAIL because CLI does not call pipeline entrypoint

- [ ] **Step 3: Write minimal implementation**

```python
from .core.pipeline import run_command


def main(argv: Sequence[str] | None = None) -> int:
    config = parse_args(argv)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    records, errors = run_command(config)
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest crawler/tests/test_dispatcher.py::test_run_command_writes_enriched_records -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add crawler/cli.py crawler/tests/test_dispatcher.py
git commit -m "wire cli through unified pipeline"
```

### Task 6: Full Regression Verification

**Files:**
- Modify: `crawler/tests/test_dispatcher.py`
- Modify: `crawler/tests/test_fetch_pipeline.py`
- Modify: `crawler/tests/test_base_chain.py`
- Modify: `crawler/tests/test_pipeline.py`

- [ ] **Step 1: Run focused regression suite**

```bash
pytest crawler/tests/test_pipeline.py crawler/tests/test_dispatcher.py crawler/tests/test_fetch_pipeline.py crawler/tests/test_base_chain.py -v
```

Expected: PASS with no failures in the newly added regression coverage.

- [ ] **Step 2: Run broader crawler suite**

```bash
pytest crawler/tests -v
```

Expected: PASS for existing crawler test coverage.

- [ ] **Step 3: Review requirement coverage**

```text
- run goes through crawl + enrich
- fallback is runtime-real
- base contract support is executable
- camoufox shares storage-state contract
- linkedin scope unchanged
```

- [ ] **Step 4: Commit**

```bash
git add crawler/tests
git commit -m "add pipeline closure regression coverage"
```
