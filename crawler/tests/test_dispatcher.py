from __future__ import annotations

import json
from pathlib import Path

import httpx

from crawler.cli import main
from crawler.core.dispatcher import run_crawl


def test_crawl_command_writes_agent_friendly_outputs(workspace_tmp_path: Path) -> None:
    """Legacy pipeline test - uses --use-legacy-pipeline for predictable output format."""
    input_path = workspace_tmp_path / "input.jsonl"
    output_dir = workspace_tmp_path / "out"
    input_path.write_text(
        json.dumps({"platform": "arxiv", "resource_type": "paper", "arxiv_id": "2401.12345"}) + "\n",
        encoding="utf-8",
    )

    exit_code = main(["crawl", "--input", str(input_path), "--output", str(output_dir), "--use-legacy-pipeline"])

    assert exit_code == 0
    assert (output_dir / "records.jsonl").exists()
    assert (output_dir / "errors.jsonl").exists()
    assert (output_dir / "summary.json").exists()
    assert (output_dir / "run_manifest.json").exists()

    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "success"
    assert summary["records_total"] == 1
    records = [json.loads(line) for line in (output_dir / "records.jsonl").read_text(encoding="utf-8").splitlines()]
    assert records[0]["metadata"]["title"]
    assert records[0]["markdown"]
    assert records[0]["artifacts"]


def test_enrich_command_adds_enrichment_envelope(workspace_tmp_path: Path) -> None:
    """Legacy pipeline test - uses --use-legacy-pipeline for enrich-only command."""
    input_path = workspace_tmp_path / "records.jsonl"
    output_dir = workspace_tmp_path / "enriched"
    input_path.write_text(
        json.dumps(
            {
                "platform": "wikipedia",
                "entity_type": "article",
                "canonical_url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
                "status": "success",
                "stage": "normalized",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(["enrich", "--input", str(input_path), "--output", str(output_dir), "--use-legacy-pipeline"])

    assert exit_code == 1
    assert (output_dir / "records.jsonl").read_text(encoding="utf-8").strip() == ""
    errors = [json.loads(line) for line in (output_dir / "errors.jsonl").read_text(encoding="utf-8").splitlines()]
    assert errors[0]["stage"] == "enrich"
    assert errors[0]["error_code"] == "ENRICHMENT_FAILED"


def test_run_command_exits_non_zero_when_run_contains_errors(monkeypatch, workspace_tmp_path: Path) -> None:
    input_path = workspace_tmp_path / "input.jsonl"
    output_dir = workspace_tmp_path / "out"
    input_path.write_text(
        json.dumps({"platform": "wikipedia", "resource_type": "article", "title": "AI"}) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "crawler.cli.run_command",
        lambda config: (
            [],
            [
                {
                    "platform": "wikipedia",
                    "resource_type": "article",
                    "stage": "enrich",
                    "error_code": "ENRICHMENT_FAILED",
                    "retryable": False,
                    "next_action": "inspect record and model config",
                    "message": "AI configuration required for generative field group",
                }
            ],
        ),
    )

    exit_code = main(["run", "--input", str(input_path), "--output", str(output_dir)])

    assert exit_code == 1


def test_run_crawl_returns_auth_failure_for_linkedin_without_session(workspace_tmp_path: Path) -> None:
    input_path = workspace_tmp_path / "input.jsonl"
    input_path.write_text(
        json.dumps({"platform": "linkedin", "resource_type": "profile", "public_identifier": "john-doe"}) + "\n",
        encoding="utf-8",
    )

    records, errors = run_crawl(
        main.__globals__["parse_args"](
            ["crawl", "--input", str(input_path), "--output", str(workspace_tmp_path / "out")]
        )
    )

    assert records == []
    assert errors[0]["error_code"] == "AUTH_REQUIRED"
    assert errors[0]["retryable"] is False
    assert errors[0]["next_action"] == "provide cookies or storage state"


def test_run_crawl_returns_auth_expired_when_session_is_rejected(monkeypatch, workspace_tmp_path: Path) -> None:
    input_path = workspace_tmp_path / "input.jsonl"
    output_dir = workspace_tmp_path / "out"
    input_path.write_text(
        json.dumps({"platform": "linkedin", "resource_type": "profile", "public_identifier": "john-doe"}) + "\n",
        encoding="utf-8",
    )
    sessions_dir = output_dir / ".sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    (sessions_dir / "linkedin.json").write_text(
        json.dumps({"cookies": [{"name": "li_at", "value": "expired"}], "origins": []}),
        encoding="utf-8",
    )

    request = httpx.Request("GET", "https://www.linkedin.com/voyager/api/identity/dash/profiles")
    response = httpx.Response(401, request=request)

    class FakeAdapter:
        requires_auth = True

        def resolve_backend(self, record: dict, override_backend: str | None = None, retry_count: int = 0) -> str:
            return "api"

        def fetch_record(self, record: dict, discovered: dict, backend: str, storage_state_path: str | None = None) -> dict:
            raise httpx.HTTPStatusError("unauthorized", request=request, response=response)

        def extract_content(self, record: dict, fetched: dict) -> dict:
            raise AssertionError("should not reach extract_content")

        def normalize_record(self, record: dict, discovered: dict, extracted: dict, supplemental: dict) -> dict:
            raise AssertionError("should not reach normalize_record")

    monkeypatch.setattr(
        "crawler.core.dispatcher.get_platform_adapter",
        lambda platform: FakeAdapter(),
    )

    records, errors = run_crawl(
        main.__globals__["parse_args"](["crawl", "--input", str(input_path), "--output", str(output_dir)])
    )

    assert records == []
    assert errors[0]["error_code"] == "AUTH_EXPIRED"
    assert errors[0]["retryable"] is True
    assert errors[0]["next_action"] == "refresh login session and retry"


def test_run_crawl_uses_auto_login_for_linkedin_when_enabled(monkeypatch, workspace_tmp_path: Path) -> None:
    input_path = workspace_tmp_path / "input.jsonl"
    output_dir = workspace_tmp_path / "out"
    input_path.write_text(
        json.dumps({"platform": "linkedin", "resource_type": "profile", "public_identifier": "john-doe"}) + "\n",
        encoding="utf-8",
    )
    captured: dict[str, str | None] = {"storage_state_path": None}

    class FakeAdapter:
        requires_auth = True
        fallback_backends = ()

        def resolve_backend(self, record: dict, override_backend: str | None = None, retry_count: int = 0) -> str:
            return "api"

        def fetch_record(self, record: dict, discovered: dict, backend: str, storage_state_path: str | None = None) -> dict:
            captured["storage_state_path"] = storage_state_path
            return {
                "backend": "api",
                "url": discovered["canonical_url"],
                "content_type": "application/json",
                "status_code": 200,
                "headers": {},
                "json_data": {"included": []},
            }

        def extract_content(self, record: dict, fetched: dict) -> dict:
            return {
                "metadata": {"title": "John Doe", "content_type": "application/json", "source_url": fetched["url"]},
                "plain_text": "AI Engineer",
                "markdown": "# John Doe\n\nAI Engineer",
                "structured": {"linkedin": {"headline": "AI Engineer"}},
                "document_blocks": [],
            }

        def normalize_record(self, record: dict, discovered: dict, extracted: dict, supplemental: dict) -> dict:
            return {"headline": "AI Engineer"}

    def fake_export(self, output_dir_path: Path) -> Path:
        exported = output_dir_path / ".sessions" / "linkedin.auto-browser.json"
        exported.parent.mkdir(parents=True, exist_ok=True)
        exported.write_text(
            json.dumps(
                {
                    "platform": "linkedin",
                    "source": "auto-browser",
                    "storage_state": {
                        "cookies": [
                            {"name": "li_at", "value": "secret-token", "domain": ".linkedin.com", "path": "/"},
                        ],
                        "origins": [],
                    },
                }
            ),
            encoding="utf-8",
        )
        return exported

    monkeypatch.setattr("crawler.core.dispatcher.get_platform_adapter", lambda platform: FakeAdapter())
    monkeypatch.setattr(
        "crawler.core.dispatcher.build_url",
        lambda record: {"canonical_url": "https://www.linkedin.com/in/john-doe/", "fields": {"public_identifier": "john-doe"}, "artifacts": {}},
    )
    monkeypatch.setattr("crawler.integrations.linkedin_auth.LinkedInAutoBrowserBridge.ensure_exported_session", fake_export)

    records, errors = run_crawl(
        main.__globals__["parse_args"](
            ["crawl", "--input", str(input_path), "--output", str(output_dir), "--auto-login"]
        )
    )

    assert errors == []
    assert records[0]["headline"] == "AI Engineer"
    assert captured["storage_state_path"] is not None


def test_run_crawl_retries_with_adapter_fallback(monkeypatch, workspace_tmp_path: Path) -> None:
    input_path = workspace_tmp_path / "input.jsonl"
    output_dir = workspace_tmp_path / "out"
    input_path.write_text(
        json.dumps({"platform": "amazon", "resource_type": "product", "asin": "B000"}) + "\n",
        encoding="utf-8",
    )

    attempted_backends: list[str] = []

    class FakeAdapter:
        requires_auth = False
        fallback_backends = ("playwright",)

        def resolve_backend(self, record: dict, override_backend: str | None = None, retry_count: int = 0) -> str:
            return "http" if retry_count == 0 else "playwright"

        def fetch_record(self, record: dict, discovered: dict, backend: str, storage_state_path: str | None = None) -> dict:
            attempted_backends.append(backend)
            if backend == "http":
                raise RuntimeError("blocked")
            return {
                "backend": backend,
                "url": discovered["canonical_url"],
                "content_type": "text/html",
                "text": "<html><body>ok</body></html>",
            }

        def extract_content(self, record: dict, fetched: dict) -> dict:
            return {"metadata": {"title": "ok"}, "plain_text": "ok", "markdown": "ok", "document_blocks": []}

        def normalize_record(self, record: dict, discovered: dict, extracted: dict, supplemental: dict) -> dict:
            return {"title": "ok"}

    monkeypatch.setattr("crawler.core.dispatcher.get_platform_adapter", lambda platform: FakeAdapter())
    monkeypatch.setattr(
        "crawler.core.dispatcher.build_url",
        lambda record: {"canonical_url": "https://example.com", "fields": {}, "artifacts": {}},
    )

    records, errors = run_crawl(main.__globals__["parse_args"](["crawl", "--input", str(input_path), "--output", str(output_dir)]))

    assert errors == []
    assert attempted_backends == ["http", "playwright"]
    assert records[0]["title"] == "ok"


def test_run_command_writes_enriched_records(monkeypatch, workspace_tmp_path: Path) -> None:
    input_path = workspace_tmp_path / "input.jsonl"
    output_dir = workspace_tmp_path / "out"
    input_path.write_text(
        json.dumps({"platform": "wikipedia", "resource_type": "article", "title": "AI"}) + "\n",
        encoding="utf-8",
    )

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


def test_api_fetch_writes_fetch_json_artifact(monkeypatch, workspace_tmp_path: Path) -> None:
    """API backend should also write fetch.json artifact for consistency with HTML path."""
    input_path = workspace_tmp_path / "input.jsonl"
    output_dir = workspace_tmp_path / "out"
    input_path.write_text(
        json.dumps({"platform": "wikipedia", "resource_type": "article", "title": "Test"}) + "\n",
        encoding="utf-8",
    )

    class FakeAdapter:
        requires_auth = False
        fallback_backends = ()

        def resolve_backend(self, record: dict, override_backend: str | None = None, retry_count: int = 0) -> str:
            return "api"

        def fetch_record(self, record: dict, discovered: dict, backend: str, storage_state_path: str | None = None) -> dict:
            return {
                "backend": "api",
                "url": discovered["canonical_url"],
                "status_code": 200,
                "headers": {"content-type": "application/json"},
                "content_type": "application/json",
                "text": '{"title": "Test Article"}',
                "json_data": {"title": "Test Article"},
            }

        def extract_content(self, record: dict, fetched: dict) -> dict:
            return {"metadata": {"title": "Test Article"}, "plain_text": "Test", "markdown": "# Test", "document_blocks": []}

        def normalize_record(self, record: dict, discovered: dict, extracted: dict, supplemental: dict) -> dict:
            return {"title": "Test Article"}

    monkeypatch.setattr("crawler.core.dispatcher.get_platform_adapter", lambda platform: FakeAdapter())
    monkeypatch.setattr(
        "crawler.core.dispatcher.build_url",
        lambda record: {"canonical_url": "https://example.com/test", "fields": {}, "artifacts": {}},
    )

    records, errors = run_crawl(main.__globals__["parse_args"](["crawl", "--input", str(input_path), "--output", str(output_dir)]))

    assert errors == []
    assert len(records) == 1

    # Check that fetch.json artifact is present for API response
    artifacts = records[0]["artifacts"]
    artifact_kinds = {a["kind"] for a in artifacts}
    assert "api_response" in artifact_kinds
    assert "fetch" in artifact_kinds  # This was the bug: fetch.json was missing for API

    # Verify the fetch.json file exists (path is relative to output_dir parent)
    fetch_artifact = next(a for a in artifacts if a["kind"] == "fetch")
    # artifact path is like "out/artifacts/test/fetch.json" - relative to output_dir's parent
    fetch_path = output_dir.parent / fetch_artifact["path"]
    assert fetch_path.exists(), f"Expected {fetch_path} to exist"

    fetch_data = json.loads(fetch_path.read_text(encoding="utf-8"))
    assert fetch_data["backend"] == "api"
    assert fetch_data["status_code"] == 200
