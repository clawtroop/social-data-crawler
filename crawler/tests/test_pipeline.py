from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock

import pytest

from crawler.cli import parse_args
from crawler.contracts import CrawlerConfig
from crawler.core.pipeline import _persist_extraction_artifacts, run_command


def test_run_command_uses_new_pipeline_by_default(monkeypatch, workspace_tmp_path: Path) -> None:
    """New 3-layer pipeline is used by default."""
    input_path = workspace_tmp_path / "input.jsonl"
    input_path.write_text(
        json.dumps({"platform": "wikipedia", "resource_type": "article", "title": "Test"}) + "\n",
        encoding="utf-8",
    )

    config = parse_args(["run", "--input", str(input_path), "--output", str(workspace_tmp_path / "out")])
    assert config.use_legacy_pipeline is False

    # Mock the new pipeline's async implementation
    mock_result = (
        [{"platform": "wikipedia", "resource_type": "article", "status": "success", "enrichment": {"status": "routed"}}],
        [],
    )
    with patch("crawler.core.pipeline._run_new_pipeline", return_value=mock_result):
        records, errors = run_command(config)

    assert errors == []
    assert records[0]["enrichment"]["status"] == "routed"


def test_discovery_map_pipeline_uses_platform_specific_adapter(monkeypatch, workspace_tmp_path: Path) -> None:
    input_path = workspace_tmp_path / "input.jsonl"
    output_dir = workspace_tmp_path / "out"
    input_path.write_text(
        json.dumps({"platform": "wikipedia", "resource_type": "article", "title": "Artificial intelligence"}) + "\n",
        encoding="utf-8",
    )

    class FakeDiscoveryAdapter:
        def build_seed_records(self, input_record: dict) -> list[SimpleNamespace]:
            return [
                SimpleNamespace(
                    platform="wikipedia",
                    resource_type="article",
                    discovery_mode=SimpleNamespace(value="template_construction"),
                    canonical_url="https://en.wikipedia.org/wiki/Artificial_intelligence",
                    identity={"title": "Artificial_intelligence"},
                    source_seed=input_record,
                    discovered_from=None,
                    metadata={},
                )
            ]

        async def map(self, seed, context: dict) -> SimpleNamespace:
            assert context["options"].sitemap_mode == "include"
            return SimpleNamespace(
                accepted=[
                    SimpleNamespace(
                        platform="wikipedia",
                        resource_type="article",
                        canonical_url="https://en.wikipedia.org/wiki/Machine_learning",
                        discovery_mode=SimpleNamespace(value="api_lookup"),
                        seed_url=seed.canonical_url,
                        hop_depth=1,
                        score=0.8,
                        metadata={},
                    )
                ]
            )

    monkeypatch.setattr(
        "crawler.discovery.adapters.registry.get_discovery_adapter",
        lambda platform: FakeDiscoveryAdapter(),
    )

    config = parse_args(["discover-map", "--input", str(input_path), "--output", str(output_dir)])
    records, errors = run_command(config)

    assert errors == []
    assert records[0]["platform"] == "wikipedia"
    assert records[0]["canonical_url"] == "https://en.wikipedia.org/wiki/Machine_learning"


def test_run_command_with_legacy_flag_uses_dispatcher(monkeypatch, workspace_tmp_path: Path) -> None:
    """--use-legacy-pipeline flag routes to the old dispatcher."""
    input_path = workspace_tmp_path / "input.jsonl"
    input_path.write_text(
        json.dumps({"platform": "wikipedia", "resource_type": "article", "title": "Test"}) + "\n",
        encoding="utf-8",
    )

    config = parse_args([
        "run",
        "--input", str(input_path),
        "--output", str(workspace_tmp_path / "out"),
        "--use-legacy-pipeline",
    ])
    assert config.use_legacy_pipeline is True

    # Mock the legacy pipeline's run_crawl and run_enrich
    monkeypatch.setattr(
        "crawler.core.dispatcher.run_crawl",
        lambda config, records=None: ([{"platform": "wikipedia", "resource_type": "article", "status": "success"}], []),
    )
    monkeypatch.setattr(
        "crawler.core.dispatcher.run_enrich",
        lambda config, records=None: ([{**records[0], "enrichment": {"status": "routed"}}], []),
    )

    records, errors = run_command(config)

    assert errors == []
    assert records[0]["enrichment"]["status"] == "routed"


def test_crawl_command_uses_new_pipeline(workspace_tmp_path: Path) -> None:
    """Crawl command uses new pipeline by default."""
    input_path = workspace_tmp_path / "input.jsonl"
    input_path.write_text(
        json.dumps({"platform": "wikipedia", "resource_type": "article", "title": "Test"}) + "\n",
        encoding="utf-8",
    )

    config = parse_args(["crawl", "--input", str(input_path), "--output", str(workspace_tmp_path / "out")])

    mock_result = (
        [{"platform": "wikipedia", "resource_type": "article", "status": "success"}],
        [],
    )
    with patch("crawler.core.pipeline._run_new_pipeline", return_value=mock_result):
        records, errors = run_command(config)

    assert errors == []
    assert records[0]["status"] == "success"


def test_new_pipeline_uses_discovery_seed_builder(monkeypatch, workspace_tmp_path: Path) -> None:
    input_path = workspace_tmp_path / "input.jsonl"
    output_dir = workspace_tmp_path / "out"
    input_path.write_text(
        json.dumps({"platform": "generic", "resource_type": "page", "url": "https://example.com/docs"}) + "\n",
        encoding="utf-8",
    )

    class FakeAdapter:
        requires_auth = False

        def resolve_backend(self, record: dict, override_backend: str | None = None, retry_count: int = 0) -> str:
            return "http"

        def normalize_record(self, record: dict, discovered: dict, extracted: dict, supplemental: dict) -> dict:
            return {"title": "Test"}

    captured: dict[str, object] = {}

    def fake_build_seed_records(record: dict) -> list[SimpleNamespace]:
        captured["record"] = record
        return [
            SimpleNamespace(
                platform="generic",
                resource_type="page",
                canonical_url="https://example.com/docs",
                identity={"url": "https://example.com/docs"},
                metadata={"artifacts": {"self": "https://example.com/docs"}},
            )
        ]

    async def fake_fetch(
        self,
        url: str,
        platform: str,
        resource_type: str | None = None,
        *,
        requires_auth: bool = False,
        override_backend: str | None = None,
        api_fetcher=None,
        api_kwargs=None,
        preferred_backend: str | None = None,
        fallback_chain=None,
    ):
        from datetime import datetime, timezone
        from crawler.fetch.models import FetchTiming, RawFetchResult

        return RawFetchResult(
            url=url,
            final_url=url,
            backend="http",
            fetch_time=datetime.now(timezone.utc),
            content_type="text/html; charset=utf-8",
            status_code=200,
            html="<html><body><article><h1>Docs</h1></article></body></html>",
            content_bytes=b"<html></html>",
            timing=FetchTiming(start_ms=0, navigation_ms=1, wait_strategy_ms=0, total_ms=1),
        )

    monkeypatch.setattr("crawler.platforms.registry.get_platform_adapter", lambda platform: FakeAdapter())
    monkeypatch.setattr("crawler.discovery.url_builder.build_seed_records", fake_build_seed_records)
    monkeypatch.setattr("crawler.fetch.engine.FetchEngine.fetch", fake_fetch)

    config = parse_args(["crawl", "--input", str(input_path), "--output", str(output_dir)])
    records, errors = run_command(config)

    assert errors == []
    assert captured["record"] == {"platform": "generic", "resource_type": "page", "url": "https://example.com/docs"}
    assert records[0]["canonical_url"] == "https://example.com/docs"


def _fake_extracted_document() -> SimpleNamespace:
    return SimpleNamespace(
        doc_id="doc-1",
        full_text="plain text",
        full_markdown="# title",
        cleaned_html="<article><p>plain text</p></article>",
        structured=SimpleNamespace(
            title="Title",
            description="Desc",
            canonical_url="https://www.linkedin.com/in/john-doe/",
            platform_fields={"headline": "Headline"},
            field_sources={},
        ),
        chunks=[],
        quality=SimpleNamespace(content_ratio=1.0, noise_removed=0, chunking_strategy="test"),
        total_chunks=0,
    )


def test_persist_extraction_artifacts_writes_cleaned_html(workspace_tmp_path: Path) -> None:
    extracted = _fake_extracted_document()

    artifacts = _persist_extraction_artifacts(
        artifact_root=workspace_tmp_path / "artifacts",
        slug="record-1",
        extracted=extracted,
        root_for_rel=workspace_tmp_path / "out",
    )

    artifact_kinds = {artifact["kind"] for artifact in artifacts}
    assert "cleaned_html" in artifact_kinds


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
    cookies_path.write_text(json.dumps({"li_at": "secret-token"}), encoding="utf-8")
    captured: dict[str, str | None] = {"storage_state_path": None}

    class FakeAdapter:
        default_backend = "api"
        requires_auth = True

        def resolve_backend(self, record: dict, override_backend: str | None = None, retry_count: int = 0) -> str:
            return "api"

        def fetch_record(self, record: dict, discovered: dict, backend: str, storage_state_path: str | None = None) -> dict:
            captured["storage_state_path"] = storage_state_path
            return {
                "backend": "api",
                "url": discovered["canonical_url"],
                "content_type": "application/json",
                "json_data": {"included": []},
            }

        def extract_content(self, record: dict, fetched: dict) -> dict:
            return {
                "metadata": {
                    "title": "Title",
                    "description": "Desc",
                    "content_type": fetched.get("content_type"),
                    "source_url": fetched.get("url"),
                },
                "plain_text": "plain text",
                "markdown": "# title",
                "structured": {"headline": "Headline"},
                "document_blocks": [],
            }

        def normalize_record(self, record: dict, discovered: dict, extracted: dict, supplemental: dict) -> dict:
            return {"headline": "Headline"}

    monkeypatch.setattr("crawler.platforms.registry.get_platform_adapter", lambda platform: FakeAdapter())
    monkeypatch.setattr(
        "crawler.discovery.url_builder.build_url",
        lambda record: {"canonical_url": "https://www.linkedin.com/in/john-doe/", "fields": {}, "artifacts": {}},
    )
    monkeypatch.setattr("crawler.extract.pipeline.ExtractPipeline.extract", lambda self, fetched, platform, resource_type: _fake_extracted_document())

    config = parse_args(["crawl", "--input", str(input_path), "--output", str(output_dir), "--cookies", str(cookies_path)])
    records, errors = run_command(config)

    assert errors == []
    assert records[0]["status"] == "success"
    assert captured["storage_state_path"] is not None
    assert Path(captured["storage_state_path"]).exists()


def test_new_pipeline_auto_login_exports_session_when_missing(monkeypatch, workspace_tmp_path: Path) -> None:
    input_path = workspace_tmp_path / "input.jsonl"
    output_dir = workspace_tmp_path / "out"
    input_path.write_text(
        json.dumps({"platform": "linkedin", "resource_type": "profile", "public_identifier": "john-doe"}) + "\n",
        encoding="utf-8",
    )
    captured: dict[str, str | None] = {"storage_state_path": None}

    class FakeAdapter:
        default_backend = "api"
        requires_auth = True

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
                            {"name": "JSESSIONID", "value": "ajax:123", "domain": ".linkedin.com", "path": "/"},
                        ],
                        "origins": [],
                    },
                }
            ),
            encoding="utf-8",
        )
        return exported

    monkeypatch.setattr("crawler.platforms.registry.get_platform_adapter", lambda platform: FakeAdapter())
    monkeypatch.setattr(
        "crawler.discovery.url_builder.build_url",
        lambda record: {"canonical_url": "https://www.linkedin.com/in/john-doe/", "fields": {"public_identifier": "john-doe"}, "artifacts": {}},
    )
    monkeypatch.setattr("crawler.extract.pipeline.ExtractPipeline.extract", lambda self, fetched, platform, resource_type: _fake_extracted_document())
    monkeypatch.setattr("crawler.integrations.linkedin_auth.LinkedInAutoBrowserBridge.ensure_exported_session", fake_export)

    config = parse_args(["crawl", "--input", str(input_path), "--output", str(output_dir), "--auto-login"])
    records, errors = run_command(config)

    assert errors == []
    assert records[0]["status"] == "success"
    assert captured["storage_state_path"] is not None
    assert Path(captured["storage_state_path"]).exists()


def test_new_pipeline_routes_api_platforms_through_fetch_engine_without_locking_backend(monkeypatch, workspace_tmp_path: Path) -> None:
    input_path = workspace_tmp_path / "input.jsonl"
    output_dir = workspace_tmp_path / "out"
    input_path.write_text(
        json.dumps({"platform": "wikipedia", "resource_type": "article", "title": "Test"}) + "\n",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    class FakeAdapter:
        default_backend = "api"
        requires_auth = False

        def resolve_backend(self, record: dict, override_backend: str | None = None, retry_count: int = 0) -> str:
            return "api"

        def fetch_record(self, record: dict, discovered: dict, backend: str, storage_state_path: str | None = None) -> dict:
            captured["adapter_backend"] = backend
            return {
                "url": discovered["canonical_url"],
                "content_type": "application/json",
                "json_data": {
                    "query": {
                        "pages": {
                            "1": {
                                "title": "Test",
                                "extract": "Body text",
                                "categories": [{"title": "Category:Example"}],
                            }
                        }
                    }
                },
                "headers": {},
                "status_code": 200,
            }

        def extract_content(self, record: dict, fetched: dict) -> dict:
            return {
                "metadata": {
                    "title": "Test",
                    "content_type": fetched.get("content_type"),
                    "source_url": fetched.get("url"),
                },
                "plain_text": "Body text",
                "markdown": "# Test\n\nBody text",
                "structured": {"categories": ["Example"]},
                "document_blocks": [],
            }

        def normalize_record(self, record: dict, discovered: dict, extracted: dict, supplemental: dict) -> dict:
            return {"title": "Test"}

    async def fake_fetch(
        self,
        url: str,
        platform: str,
        resource_type: str | None = None,
        *,
        requires_auth: bool = False,
        override_backend: str | None = None,
        api_fetcher=None,
        api_kwargs=None,
        preferred_backend: str | None = None,
        fallback_chain=None,
    ):
        from datetime import datetime, timezone
        from crawler.fetch.models import FetchTiming, RawFetchResult

        captured["override_backend"] = override_backend
        captured["preferred_backend"] = preferred_backend
        assert api_fetcher is not None
        payload = api_fetcher(url)
        return RawFetchResult(
            url=url,
            final_url=payload["url"],
            backend="api",
            fetch_time=datetime.now(timezone.utc),
            content_type=payload["content_type"],
            status_code=payload["status_code"],
            json_data=payload["json_data"],
            headers=payload["headers"],
            timing=FetchTiming(start_ms=0, navigation_ms=1, wait_strategy_ms=0, total_ms=1),
        )

    monkeypatch.setattr("crawler.platforms.registry.get_platform_adapter", lambda platform: FakeAdapter())
    monkeypatch.setattr(
        "crawler.discovery.url_builder.build_url",
        lambda record: {"canonical_url": "https://en.wikipedia.org/wiki/Test", "fields": {}, "artifacts": {}},
    )
    monkeypatch.setattr("crawler.fetch.engine.FetchEngine.fetch", fake_fetch)

    config = parse_args(["crawl", "--input", str(input_path), "--output", str(output_dir)])
    records, errors = run_command(config)

    assert errors == []
    assert captured["override_backend"] is None
    assert captured["preferred_backend"] == "api"
    assert captured["adapter_backend"] == "api"
    assert records[0]["metadata"]["title"] == "Test"


def test_new_pipeline_respects_explicit_backend_override(monkeypatch, workspace_tmp_path: Path) -> None:
    input_path = workspace_tmp_path / "input.jsonl"
    output_dir = workspace_tmp_path / "out"
    input_path.write_text(
        json.dumps({"platform": "wikipedia", "resource_type": "article", "title": "Test"}) + "\n",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    class FakeAdapter:
        default_backend = "api"
        requires_auth = False

        def resolve_backend(self, record: dict, override_backend: str | None = None, retry_count: int = 0) -> str:
            return override_backend or "api"

        def fetch_record(self, record: dict, discovered: dict, backend: str, storage_state_path: str | None = None) -> dict:
            captured["adapter_backend"] = backend
            return {
                "url": discovered["canonical_url"],
                "content_type": "text/html",
                "text": "<html><body><h1>Test</h1><p>Body text</p></body></html>",
                "headers": {},
                "status_code": 200,
            }

        def extract_content(self, record: dict, fetched: dict) -> dict:
            return {
                "metadata": {
                    "title": "Test",
                    "content_type": fetched.get("content_type"),
                    "source_url": fetched.get("url"),
                },
                "plain_text": "Body text",
                "markdown": "# Test\n\nBody text",
                "structured": {"categories": ["Example"]},
                "document_blocks": [],
            }

        def normalize_record(self, record: dict, discovered: dict, extracted: dict, supplemental: dict) -> dict:
            return {"title": "Test"}

    async def fake_fetch(
        self,
        url: str,
        platform: str,
        resource_type: str | None = None,
        *,
        requires_auth: bool = False,
        override_backend: str | None = None,
        api_fetcher=None,
        api_kwargs=None,
        preferred_backend: str | None = None,
        fallback_chain=None,
    ):
        from datetime import datetime, timezone
        from crawler.fetch.models import FetchTiming, RawFetchResult

        captured["override_backend"] = override_backend
        captured["preferred_backend"] = preferred_backend
        return RawFetchResult(
            url=url,
            final_url=url,
            backend=override_backend or "http",
            fetch_time=datetime.now(timezone.utc),
            content_type="text/html",
            status_code=200,
            html="<html><body><h1>Test</h1><p>Body text</p></body></html>",
            content_bytes=b"<html><body><h1>Test</h1><p>Body text</p></body></html>",
            headers={},
            timing=FetchTiming(start_ms=0, navigation_ms=1, wait_strategy_ms=0, total_ms=1),
        )

    monkeypatch.setattr("crawler.platforms.registry.get_platform_adapter", lambda platform: FakeAdapter())
    monkeypatch.setattr(
        "crawler.discovery.url_builder.build_url",
        lambda record: {"canonical_url": "https://en.wikipedia.org/wiki/Test", "fields": {}, "artifacts": {}},
    )
    monkeypatch.setattr("crawler.fetch.engine.FetchEngine.fetch", fake_fetch)

    config = parse_args(["crawl", "--input", str(input_path), "--output", str(output_dir), "--backend", "http"])
    records, errors = run_command(config)

    assert errors == []
    assert captured["override_backend"] == "http"
    assert captured["preferred_backend"] is None
    assert records[0]["metadata"]["title"] == "Test"


def test_new_pipeline_crawl_persists_structured_fields_for_api_records(monkeypatch, workspace_tmp_path: Path) -> None:
    input_path = workspace_tmp_path / "input.jsonl"
    output_dir = workspace_tmp_path / "out"
    input_path.write_text(
        json.dumps({"platform": "wikipedia", "resource_type": "article", "title": "Artificial intelligence"}) + "\n",
        encoding="utf-8",
    )

    class FakeAdapter:
        default_backend = "api"
        requires_auth = False

        def resolve_backend(self, record: dict, override_backend: str | None = None, retry_count: int = 0) -> str:
            return "api"

        def fetch_record(self, record: dict, discovered: dict, backend: str, storage_state_path: str | None = None) -> dict:
            return {
                "backend": "api",
                "url": discovered["canonical_url"],
                "content_type": "application/json",
                "json_data": {
                    "query": {
                        "pages": {
                            "1164": {
                                "title": "Artificial intelligence",
                                "extract": "Artificial intelligence is the capability of computational systems.",
                                "categories": [{"title": "Category:Artificial intelligence"}],
                            }
                        }
                    }
                },
            }

        def extract_content(self, record: dict, fetched: dict) -> dict:
            return {
                "metadata": {
                    "title": "Artificial intelligence",
                    "content_type": fetched.get("content_type"),
                    "source_url": fetched.get("url"),
                },
                "plain_text": "Artificial intelligence is the capability of computational systems.",
                "markdown": "# Artificial intelligence\n\nArtificial intelligence is the capability of computational systems.",
                "structured": {"categories": ["Artificial intelligence"]},
                "document_blocks": [],
            }

        def normalize_record(self, record: dict, discovered: dict, extracted: dict, supplemental: dict) -> dict:
            return {"title": "Artificial intelligence"}

    monkeypatch.setattr("crawler.platforms.registry.get_platform_adapter", lambda platform: FakeAdapter())
    monkeypatch.setattr(
        "crawler.discovery.url_builder.build_url",
        lambda record: {
            "canonical_url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
            "fields": {"title": "Artificial_intelligence"},
            "artifacts": {},
        },
    )

    config = parse_args(["crawl", "--input", str(input_path), "--output", str(output_dir)])
    records, errors = run_command(config)

    assert errors == []
    assert records[0]["metadata"]["title"] == "Artificial intelligence"
    assert "computational systems" in records[0]["plain_text"]
    assert records[0]["markdown"].startswith("# Artificial intelligence")
    assert records[0]["structured"]["categories"] == ["Artificial intelligence"]


def test_new_pipeline_preserves_api_metadata_and_top_level_compat_fields(monkeypatch, workspace_tmp_path: Path) -> None:
    input_path = workspace_tmp_path / "input.jsonl"
    output_dir = workspace_tmp_path / "out"
    input_path.write_text(
        json.dumps({"platform": "linkedin", "resource_type": "profile", "public_identifier": "john-doe"}) + "\n",
        encoding="utf-8",
    )

    class FakeAdapter:
        default_backend = "api"
        requires_auth = False

        def resolve_backend(self, record: dict, override_backend: str | None = None, retry_count: int = 0) -> str:
            return "api"

        def fetch_record(self, record: dict, discovered: dict, backend: str, storage_state_path: str | None = None) -> dict:
            return {
                "backend": "api",
                "url": discovered["canonical_url"],
                "content_type": "application/json",
                "status_code": 200,
                "headers": {},
                "json_data": {
                    "included": [
                        {
                            "$type": "com.linkedin.voyager.dash.identity.profile.Profile",
                            "firstName": "John",
                            "lastName": "Doe",
                            "headline": "AI Engineer",
                            "publicIdentifier": "john-doe",
                            "entityUrn": "urn:li:fsd_profile:123",
                        }
                    ]
                },
            }

        def extract_content(self, record: dict, fetched: dict) -> dict:
            return {
                "metadata": {
                    "title": "John Doe",
                    "content_type": "application/json",
                    "source_url": fetched["url"],
                    "entity_type": "person",
                    "source_id": "123",
                },
                "plain_text": "AI Engineer",
                "markdown": "# John Doe\n\nAI Engineer",
                "structured": {
                    "linkedin": {
                        "source_id": "123",
                        "title": "John Doe",
                        "headline": "AI Engineer",
                        "public_identifier": "john-doe",
                    }
                },
                "document_blocks": [],
            }

        def normalize_record(self, record: dict, discovered: dict, extracted: dict, supplemental: dict) -> dict:
            structured = extracted.get("structured", {})
            linkedin = structured.get("linkedin", {}) if isinstance(structured, dict) else {}
            result = dict(linkedin) if isinstance(linkedin, dict) else {}
            result.setdefault("public_identifier", discovered["fields"].get("public_identifier"))
            result.setdefault("title", extracted.get("metadata", {}).get("title"))
            return result

    monkeypatch.setattr("crawler.platforms.registry.get_platform_adapter", lambda platform: FakeAdapter())
    monkeypatch.setattr(
        "crawler.discovery.url_builder.build_url",
        lambda record: {
            "canonical_url": "https://www.linkedin.com/in/john-doe/",
            "fields": {"public_identifier": "john-doe"},
            "artifacts": {},
        },
    )

    config = parse_args(["crawl", "--input", str(input_path), "--output", str(output_dir)])
    records, errors = run_command(config)

    assert errors == []
    assert records[0]["metadata"]["content_type"] == "application/json"
    assert records[0]["metadata"]["source_url"] == "https://www.linkedin.com/in/john-doe/"
    assert records[0]["metadata"]["entity_type"] == "person"
    assert records[0]["metadata"]["source_id"] == "123"
    assert records[0]["source_id"] == "123"
    assert records[0]["headline"] == "AI Engineer"
    assert records[0]["public_identifier"] == "john-doe"


def test_new_pipeline_uses_legacy_metadata_for_wikipedia_api(monkeypatch, workspace_tmp_path: Path) -> None:
    input_path = workspace_tmp_path / "input.jsonl"
    output_dir = workspace_tmp_path / "out"
    input_path.write_text(
        json.dumps({"platform": "wikipedia", "resource_type": "article", "title": "Artificial intelligence"}) + "\n",
        encoding="utf-8",
    )

    class FakeAdapter:
        default_backend = "api"
        requires_auth = False

        def resolve_backend(self, record: dict, override_backend: str | None = None, retry_count: int = 0) -> str:
            return "api"

        def fetch_record(self, record: dict, discovered: dict, backend: str, storage_state_path: str | None = None) -> dict:
            return {
                "backend": "api",
                "url": discovered["canonical_url"],
                "content_type": "application/json",
                "status_code": 200,
                "headers": {},
                "json_data": {
                    "query": {
                        "pages": {
                            "1164": {
                                "title": "Artificial intelligence",
                                "extract": "Artificial intelligence is the capability of computational systems.",
                                "categories": [{"title": "Category:Artificial intelligence"}],
                                "pageprops": {"wikibase-shortdesc": "Intelligence of machines"},
                            }
                        }
                    }
                },
            }

        def extract_content(self, record: dict, fetched: dict) -> dict:
            return {
                "metadata": {
                    "title": "Artificial intelligence",
                    "content_type": "application/json",
                    "source_url": fetched["url"],
                    "pageprops": {"wikibase-shortdesc": "Intelligence of machines"},
                },
                "plain_text": "Artificial intelligence is the capability of computational systems.",
                "markdown": "# Artificial intelligence\n\nArtificial intelligence is the capability of computational systems.",
                "structured": {"categories": ["Artificial intelligence"]},
                "document_blocks": [],
            }

        def normalize_record(self, record: dict, discovered: dict, extracted: dict, supplemental: dict) -> dict:
            return {
                "title": extracted.get("metadata", {}).get("title"),
                "summary": extracted.get("plain_text", "").splitlines()[0] if extracted.get("plain_text") else "",
            }

    monkeypatch.setattr("crawler.platforms.registry.get_platform_adapter", lambda platform: FakeAdapter())
    monkeypatch.setattr(
        "crawler.discovery.url_builder.build_url",
        lambda record: {
            "canonical_url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
            "fields": {"title": "Artificial_intelligence"},
            "artifacts": {},
        },
    )

    config = parse_args(["crawl", "--input", str(input_path), "--output", str(output_dir)])
    records, errors = run_command(config)

    assert errors == []
    assert records[0]["metadata"]["pageprops"]["wikibase-shortdesc"] == "Intelligence of machines"


def test_new_pipeline_does_not_write_html_artifact_for_api_payload(monkeypatch, workspace_tmp_path: Path) -> None:
    input_path = workspace_tmp_path / "input.jsonl"
    output_dir = workspace_tmp_path / "out"
    input_path.write_text(
        json.dumps({"platform": "base", "resource_type": "address", "address": "0x123"}) + "\n",
        encoding="utf-8",
    )

    class FakeAdapter:
        default_backend = "api"
        requires_auth = False

        def resolve_backend(self, record: dict, override_backend: str | None = None, retry_count: int = 0) -> str:
            return "api"

        def fetch_record(self, record: dict, discovered: dict, backend: str, storage_state_path: str | None = None) -> dict:
            return {
                "backend": "api",
                "url": discovered["canonical_url"],
                "content_type": "application/json",
                "status_code": 200,
                "headers": {},
                "text": '{"result":"0xabc"}',
                "json_data": {"result": "0xabc"},
            }

        def extract_content(self, record: dict, fetched: dict) -> dict:
            return {
                "metadata": {
                    "title": "address",
                    "content_type": "application/json",
                    "source_url": fetched["url"],
                },
                "plain_text": '"0xabc"',
                "markdown": '```json\n"0xabc"\n```',
                "structured": {"rpc_result": "0xabc"},
                "document_blocks": [],
            }

        def normalize_record(self, record: dict, discovered: dict, extracted: dict, supplemental: dict) -> dict:
            return {"title": "address"}

    monkeypatch.setattr("crawler.platforms.registry.get_platform_adapter", lambda platform: FakeAdapter())
    monkeypatch.setattr(
        "crawler.discovery.url_builder.build_url",
        lambda record: {
            "canonical_url": "https://basescan.org/address/0x123",
            "fields": {"address": "0x123"},
            "artifacts": {},
        },
    )

    config = parse_args(["crawl", "--input", str(input_path), "--output", str(output_dir)])
    records, errors = run_command(config)

    assert errors == []
    artifact_kinds = {artifact["kind"] for artifact in records[0]["artifacts"]}
    assert "api_response" in artifact_kinds
    assert "html" not in artifact_kinds


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
        )
        + "\n",
        encoding="utf-8",
    )

    def fail_build_url(record: dict) -> dict:
        raise AssertionError("build_url should not be called for enrich-only existing records")

    class FakeEnrichmentResult:
        def to_dict(self) -> dict:
            return {
                "doc_id": "doc-1",
                "enrichment_results": {"skills_extraction": {"field_group": "skills_extraction", "status": "success", "fields": []}},
                "enriched_fields": {},
            }

    async def fake_enrich(self, record: dict, field_groups: list[str]) -> FakeEnrichmentResult:
        assert record["canonical_url"] == "https://www.linkedin.com/in/test/"
        assert record["plain_text"].startswith("Python engineer")
        return FakeEnrichmentResult()

    monkeypatch.setattr("crawler.discovery.url_builder.build_url", fail_build_url)
    monkeypatch.setattr("crawler.enrich.pipeline.EnrichPipeline.enrich", fake_enrich)

    config = parse_args(
        ["enrich", "--input", str(input_path), "--output", str(output_dir), "--field-group", "skills_extraction"]
    )
    records, errors = run_command(config)

    assert errors == []
    assert records[0]["canonical_url"] == "https://www.linkedin.com/in/test/"
    assert records[0]["enrichment"]["doc_id"] == "doc-1"


def test_new_pipeline_crawls_linkedin_search_results(monkeypatch, workspace_tmp_path: Path) -> None:
    input_path = workspace_tmp_path / "input.jsonl"
    output_dir = workspace_tmp_path / "out"
    cookies_path = workspace_tmp_path / "cookies.json"
    input_path.write_text(
        json.dumps(
            {
                "platform": "linkedin",
                "resource_type": "search",
                "query": "openai",
                "search_type": "company",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    cookies_path.write_text(json.dumps({"li_at": "secret-token", "JSESSIONID": "ajax:123"}), encoding="utf-8")

    async def fake_fetch(
        self,
        url: str,
        platform: str,
        resource_type: str | None = None,
        *,
        requires_auth: bool = False,
        override_backend: str | None = None,
        api_fetcher=None,
        api_kwargs=None,
        preferred_backend: str | None = None,
        fallback_chain=None,
    ):
        from datetime import datetime, timezone
        from crawler.fetch.models import FetchTiming, RawFetchResult

        html = """
        <html><body>
          <div><a href="/company/openai/">OpenAI</a><div>AI research company</div></div>
          <div><a href="/company/anthropic/">Anthropic</a><div>AI safety company</div></div>
        </body></html>
        """
        return RawFetchResult(
            url=url,
            final_url=url,
            backend="playwright",
            fetch_time=datetime.now(timezone.utc),
            content_type="text/html; charset=utf-8",
            status_code=200,
            html=html,
            content_bytes=html.encode("utf-8"),
            timing=FetchTiming(start_ms=0, navigation_ms=1, wait_strategy_ms=1, total_ms=2),
        )

    monkeypatch.setattr("crawler.fetch.engine.FetchEngine.fetch", fake_fetch)

    config = parse_args(["crawl", "--input", str(input_path), "--output", str(output_dir), "--cookies", str(cookies_path)])
    records, errors = run_command(config)

    assert errors == []
    assert records[0]["resource_type"] == "search"
    assert records[0]["results"][0]["resource_type"] == "company"
    assert records[0]["results"][0]["identifier"] == "openai"


def test_new_pipeline_crawls_generic_page_with_standard_html_extraction(monkeypatch, workspace_tmp_path: Path) -> None:
    input_path = workspace_tmp_path / "input.jsonl"
    output_dir = workspace_tmp_path / "out"
    input_path.write_text(
        json.dumps(
            {
                "platform": "generic",
                "resource_type": "page",
                "url": "https://example.com/docs/protocol",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    async def fake_fetch(
        self,
        url: str,
        platform: str,
        resource_type: str | None = None,
        *,
        requires_auth: bool = False,
        override_backend: str | None = None,
        api_fetcher=None,
        api_kwargs=None,
        preferred_backend: str | None = None,
        fallback_chain=None,
    ):
        from datetime import datetime, timezone
        from crawler.fetch.models import FetchTiming, RawFetchResult

        captured["platform"] = platform
        captured["resource_type"] = resource_type
        captured["override_backend"] = override_backend
        html = """
        <html>
          <head>
            <title>Data Mining Protocol</title>
            <meta name="description" content="Protocol overview">
          </head>
          <body>
            <article>
              <h1>Data Mining Protocol</h1>
              <p>This page defines the protocol lifecycle and settlement rules.</p>
            </article>
          </body>
        </html>
        """
        return RawFetchResult(
            url=url,
            final_url=url,
            backend="http",
            fetch_time=datetime.now(timezone.utc),
            content_type="text/html; charset=utf-8",
            status_code=200,
            html=html,
            content_bytes=html.encode("utf-8"),
            timing=FetchTiming(start_ms=0, navigation_ms=1, wait_strategy_ms=0, total_ms=1),
        )

    monkeypatch.setattr("crawler.fetch.engine.FetchEngine.fetch", fake_fetch)

    config = parse_args(["crawl", "--input", str(input_path), "--output", str(output_dir)])
    records, errors = run_command(config)

    assert errors == []
    assert captured["platform"] == "generic"
    assert captured["resource_type"] == "page"
    assert captured["override_backend"] is None
    assert records[0]["canonical_url"] == "https://example.com/docs/protocol"
    assert records[0]["metadata"]["title"] == "Data Mining Protocol"
    assert records[0]["metadata"]["source_url"] == "https://example.com/docs/protocol"
    assert "settlement rules" in records[0]["plain_text"]
    assert records[0]["title"] == "Data Mining Protocol"


def test_run_command_dispatches_discover_map(monkeypatch, workspace_tmp_path: Path) -> None:
    """Discover-map command dispatches to discovery map pipeline."""
    input_path = workspace_tmp_path / "input.jsonl"
    output_dir = workspace_tmp_path / "out"
    input_path.write_text(
        json.dumps({"url": "https://example.com/docs"}) + "\n",
        encoding="utf-8",
    )

    async def fake_fetch(
        self,
        url: str,
        platform: str,
        resource_type: str | None = None,
        *,
        requires_auth: bool = False,
        **kwargs,
    ):
        from datetime import datetime, timezone
        from crawler.fetch.models import FetchTiming, RawFetchResult

        html = """
        <html><body>
          <a href="/guide">Guide</a>
          <a href="/api">API</a>
        </body></html>
        """
        return RawFetchResult(
            url=url,
            final_url=url,
            backend="http",
            fetch_time=datetime.now(timezone.utc),
            content_type="text/html",
            status_code=200,
            html=html,
            content_bytes=html.encode("utf-8"),
            timing=FetchTiming(start_ms=0, navigation_ms=1, wait_strategy_ms=0, total_ms=1),
        )

    monkeypatch.setattr("crawler.fetch.engine.FetchEngine.fetch", fake_fetch)

    config = CrawlerConfig.from_mapping({
        "command": "discover-map",
        "input_path": str(input_path),
        "output_dir": str(output_dir),
    })
    records, errors = run_command(config)

    assert isinstance(records, list)
    assert errors == []
    assert len(records) >= 1
    # Should discover links from the page
    urls = [r["canonical_url"] for r in records]
    assert any("guide" in url for url in urls)


def test_run_command_dispatches_discover_crawl(monkeypatch, workspace_tmp_path: Path) -> None:
    """Discover-crawl command dispatches to discovery crawl pipeline."""
    input_path = workspace_tmp_path / "input.jsonl"
    output_dir = workspace_tmp_path / "out"
    input_path.write_text(
        json.dumps({"url": "https://example.com/docs"}) + "\n",
        encoding="utf-8",
    )

    async def fake_fetch(
        self,
        url: str,
        platform: str,
        resource_type: str | None = None,
        *,
        requires_auth: bool = False,
        **kwargs,
    ):
        from datetime import datetime, timezone
        from crawler.fetch.models import FetchTiming, RawFetchResult

        html = "<html><body><h1>Docs</h1><p>Content here</p></body></html>"
        return RawFetchResult(
            url=url,
            final_url=url,
            backend="http",
            fetch_time=datetime.now(timezone.utc),
            content_type="text/html",
            status_code=200,
            html=html,
            content_bytes=html.encode("utf-8"),
            timing=FetchTiming(start_ms=0, navigation_ms=1, wait_strategy_ms=0, total_ms=1),
        )

    monkeypatch.setattr("crawler.fetch.engine.FetchEngine.fetch", fake_fetch)

    config = CrawlerConfig.from_mapping({
        "command": "discover-crawl",
        "input_path": str(input_path),
        "output_dir": str(output_dir),
        "max_depth": 0,
        "max_pages": 1,
    })
    records, errors = run_command(config)

    assert isinstance(records, list)
    assert errors == []
    assert len(records) == 1
    assert records[0]["canonical_url"] == "https://example.com/docs"
    assert "fetched" in records[0]
