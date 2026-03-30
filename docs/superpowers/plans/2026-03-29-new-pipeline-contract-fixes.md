# New Pipeline Contract Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the documented CLI contracts for the default pipeline by making `enrich` consume existing records directly, making auth-required flows return stable auth errors, and making JSON/JSONL input tolerant of UTF-8 BOM.

**Architecture:** Keep `crawl` and `run` on the new fetch/extract pipeline, but split `enrich` into a record-driven path that skips rediscovery and refetching. Centralize JSON/JSONL reading behind BOM-safe helpers, and share session bootstrap/auth checks in the new pipeline so LinkedIn and other auth-backed platforms behave like the legacy dispatcher.

**Tech Stack:** Python 3.11+, pytest, asyncio pipeline, existing `SessionStore`, existing `EnrichPipeline`

---

### Task 1: Add failing regression tests for BOM-safe input

**Files:**
- Modify: `crawler/tests/test_cli.py`
- Test: `crawler/tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_main_handles_bom_prefixed_jsonl_input(workspace_tmp_path: Path) -> None:
    input_path = workspace_tmp_path / "input.jsonl"
    output_dir = workspace_tmp_path / "out"
    input_path.write_text(
        "\ufeff" + '{"platform":"wikipedia","resource_type":"article","title":"Artificial intelligence"}\n',
        encoding="utf-8",
    )

    exit_code = main(["crawl", "--input", str(input_path), "--output", str(output_dir)])

    assert exit_code == 0
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "success"


def test_fill_enrichment_handles_bom_prefixed_json_files(workspace_tmp_path: Path) -> None:
    records_path = workspace_tmp_path / "records.jsonl"
    responses_path = workspace_tmp_path / "responses.json"
    records_path.write_text(
        '\ufeff{"doc_id":"doc-1","enrichment":{"enrichment_results":{"summaries":{"field_group":"summaries","status":"pending_agent","fields":[]}},"enriched_fields":{}}}\n',
        encoding="utf-8",
    )
    responses_path.write_text('\ufeff{"doc-1:summaries":"{\\"summary\\":\\"摘要\\"}"}', encoding="utf-8")

    exit_code = main(["fill-enrichment", "--records", str(records_path), "--responses", str(responses_path)])

    assert exit_code == 0
    updated = records_path.read_text(encoding="utf-8")
    assert '"status": "success"' in updated or '"status":"success"' in updated
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python -m pytest -q crawler/tests/test_cli.py -k bom`

Expected: `JSONDecodeError` caused by UTF-8 BOM in one or both tests.

- [ ] **Step 3: Write minimal implementation**

```python
# crawler/io/json_utils.py
def read_json_file(path: Path) -> dict[str, Any] | list[Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl_file(path: Path) -> list[dict[str, Any]]:
    records = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records
```

Update current readers in `crawler/cli.py`, `crawler/core/pipeline.py`, and `crawler/core/dispatcher.py` to call the shared helpers instead of parsing raw `utf-8` text directly.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python -m pytest -q crawler/tests/test_cli.py -k bom`

Expected: both tests pass.

### Task 2: Add failing regression tests for new-pipeline auth handling

**Files:**
- Modify: `crawler/tests/test_pipeline.py`
- Test: `crawler/tests/test_pipeline.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_new_pipeline_returns_auth_required_for_linkedin_without_session(workspace_tmp_path: Path) -> None:
    input_path = workspace_tmp_path / "input.jsonl"
    output_dir = workspace_tmp_path / "out"
    input_path.write_text(
        json.dumps({"platform": "linkedin", "resource_type": "profile", "public_identifier": "john-doe"}) + "\n",
        encoding="utf-8",
    )

    config = parse_args(["crawl", "--input", str(input_path), "--output", str(output_dir)])
    records, errors = run_command(config)

    assert records == []
    assert errors[0]["error_code"] == "AUTH_REQUIRED"
    assert errors[0]["next_action"] == "provide cookies or storage state"


def test_new_pipeline_imports_cookies_before_api_fetch(monkeypatch, workspace_tmp_path: Path) -> None:
    input_path = workspace_tmp_path / "input.jsonl"
    output_dir = workspace_tmp_path / "out"
    cookies_path = workspace_tmp_path / "cookies.json"
    input_path.write_text(
        json.dumps({"platform": "linkedin", "resource_type": "profile", "public_identifier": "john-doe"}) + "\n",
        encoding="utf-8",
    )
    cookies_path.write_text(json.dumps({"li_at": "secret"}), encoding="utf-8")
    captured: dict[str, str | None] = {"storage_state_path": None}

    class FakeAdapter:
        default_backend = "api"
        requires_auth = True

        def fetch_record(self, record: dict, discovered: dict, backend: str, storage_state_path: str | None = None) -> dict:
            captured["storage_state_path"] = storage_state_path
            return {
                "backend": "api",
                "url": discovered["canonical_url"],
                "content_type": "application/json",
                "json_data": {"id": "ok"},
            }

    monkeypatch.setattr("crawler.core.pipeline.get_platform_adapter", lambda platform: FakeAdapter())
    monkeypatch.setattr(
        "crawler.core.pipeline.build_url",
        lambda record: {"canonical_url": "https://www.linkedin.com/in/john-doe/", "fields": {}, "artifacts": {}},
    )

    config = parse_args(["crawl", "--input", str(input_path), "--output", str(output_dir), "--cookies", str(cookies_path)])
    records, errors = run_command(config)

    assert errors == []
    assert captured["storage_state_path"] is not None
    assert Path(captured["storage_state_path"]).exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python -m pytest -q crawler/tests/test_pipeline.py -k "auth_required or imports_cookies"`

Expected: first test fails with path/file error instead of `AUTH_REQUIRED`; second fails because cookies are ignored.

- [ ] **Step 3: Write minimal implementation**

```python
# inside crawler/core/pipeline.py
session_store = SessionStore(session_root)
...
if config.cookies_path is not None:
    storage_state_path = str(session_store.import_cookies(platform, config.cookies_path))
elif session_store.load(platform) is not None:
    storage_state_path = str(session_root / f"{platform}.json")
else:
    storage_state_path = None

if requires_auth and storage_state_path is None:
    errors.append(
        {
            "platform": platform,
            "resource_type": resource_type,
            "stage": "fetch",
            "status": "failed",
            "error_code": "AUTH_REQUIRED",
            "retryable": False,
            "next_action": "provide cookies or storage state",
            "message": f"{platform} requires authenticated browser state",
        }
    )
    continue
```

Keep the auth behavior aligned with `crawler/core/dispatcher.py` so old and new pipelines return the same contract.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python -m pytest -q crawler/tests/test_pipeline.py -k "auth_required or imports_cookies"`

Expected: both tests pass.

### Task 3: Add failing regression tests for enrich-only existing records in new pipeline

**Files:**
- Modify: `crawler/tests/test_pipeline.py`
- Test: `crawler/tests/test_pipeline.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_new_pipeline_enrich_uses_existing_record_without_build_url(monkeypatch, workspace_tmp_path: Path) -> None:
    input_path = workspace_tmp_path / "records.jsonl"
    output_dir = workspace_tmp_path / "out"
    input_path.write_text(
        json.dumps(
            {
                "platform": "linkedin",
                "resource_type": "profile",
                "canonical_url": "https://www.linkedin.com/in/test/",
                "plain_text": "Python engineer with SQL and machine learning experience.",
                "markdown": "# Test\n\nPython engineer",
                "structured": {"headline": "Senior Python Engineer"},
                "metadata": {"title": "Test User", "description": "Profile"},
                "status": "success",
                "stage": "normalized",
            }
        ) + "\n",
        encoding="utf-8",
    )

    def fail_build_url(record: dict) -> dict:
        raise AssertionError("build_url should not be called for enrich-only existing records")

    monkeypatch.setattr("crawler.core.pipeline.build_url", fail_build_url)

    config = parse_args(
        ["enrich", "--input", str(input_path), "--output", str(output_dir), "--field-group", "skills_extraction"]
    )
    records, errors = run_command(config)

    assert errors == []
    assert records[0]["canonical_url"] == "https://www.linkedin.com/in/test/"
    assert "enrichment" in records[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest -q crawler/tests/test_pipeline.py -k "enrich_uses_existing_record"`

Expected: failure because `build_url()` is still called.

- [ ] **Step 3: Write minimal implementation**

```python
def _is_existing_enrich_record(record: dict[str, Any]) -> bool:
    return bool(record.get("canonical_url")) and any(
        record.get(key) not in (None, "", [], {})
        for key in ("plain_text", "markdown", "structured", "metadata")
    )


async def _enrich_existing_record(...):
    enrich_input = {
        "doc_id": record.get("doc_id") or stable_hash(record["canonical_url"]),
        "canonical_url": record["canonical_url"],
        "platform": record.get("platform"),
        "resource_type": record.get("resource_type") or record.get("entity_type"),
        "plain_text": record.get("plain_text", ""),
        "markdown": record.get("markdown", ""),
        "structured": record.get("structured", {}),
        "title": (record.get("metadata") or {}).get("title"),
        "description": (record.get("metadata") or {}).get("description"),
    }
```

In `_run_new_pipeline_async`, if `config.command is CrawlCommand.ENRICH` and the record already looks canonical, skip discovery/fetch/extract and return the record with updated `enrichment`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest -q crawler/tests/test_pipeline.py -k "enrich_uses_existing_record"`

Expected: pass without calling `build_url`.

### Task 4: Run the focused regression set and full verification

**Files:**
- Modify: `crawler/core/pipeline.py`
- Modify: `crawler/core/dispatcher.py`
- Modify: `crawler/cli.py`
- Create: `crawler/io/json_utils.py`
- Modify: `crawler/tests/test_cli.py`
- Modify: `crawler/tests/test_pipeline.py`

- [ ] **Step 1: Run focused regression suite**

Run:

```bash
.venv\Scripts\python -m pytest -q crawler/tests/test_cli.py crawler/tests/test_pipeline.py
```

Expected: targeted regression tests pass with no new failures.

- [ ] **Step 2: Run full test suite**

Run:

```bash
.venv\Scripts\python -m pytest -q
```

Expected: full suite passes.

- [ ] **Step 3: Manual CLI smoke verification**

Run these commands and inspect `summary.json` / `errors.jsonl`:

```bash
.venv\Scripts\python -m crawler crawl --input output\manual_smoke\crawl_input.jsonl --output output\manual_smoke\crawl_out
.venv\Scripts\python -m crawler enrich --input output\manual_smoke\enrich_input.jsonl --output output\manual_smoke\enrich_out --field-group skills_extraction
.venv\Scripts\python -m crawler crawl --input output\manual_smoke\linkedin_input.jsonl --output output\manual_smoke\linkedin_out
```

Expected:
- `crawl` succeeds
- `enrich` no longer attempts rediscovery for existing records
- LinkedIn unauthenticated crawl writes `AUTH_REQUIRED` instead of a file path error
