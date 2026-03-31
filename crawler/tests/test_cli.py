from __future__ import annotations

import json
from pathlib import Path

import pytest

from crawler import CrawlCommand
from crawler.cli import build_parser, main, parse_args


def test_build_parser_parses_expected_subcommand_arguments() -> None:
    parser = build_parser()
    namespace = parser.parse_args(
        [
            "crawl",
            "--input",
            "data/input.jsonl",
            "--output",
            "output",
            "--cookies",
            "data/cookies.json",
            "--platform",
            "linkedin",
        ]
    )

    assert namespace.command is CrawlCommand.CRAWL
    assert namespace.input_path == Path("data/input.jsonl")
    assert namespace.output_dir == Path("output")
    assert namespace.cookies_path == Path("data/cookies.json")
    assert namespace.platform == "linkedin"


def test_parse_args_returns_crawler_config_with_command() -> None:
    config = parse_args(
        [
            "run",
            "--input",
            "data/input.jsonl",
            "--output",
            "output",
        ]
    )

    assert config.command is CrawlCommand.RUN
    assert config.input_path == Path("data/input.jsonl")
    assert config.output_dir == Path("output")


def test_parse_args_supports_enrichment_options() -> None:
    config = parse_args(
        [
            "enrich",
            "--input",
            "data/input.jsonl",
            "--output",
            "output",
            "--field-group",
            "summaries",
            "--field-group",
            "linkables",
        ]
    )

    assert config.command is CrawlCommand.ENRICH
    assert config.field_groups == ("summaries", "linkables")


def test_parse_args_supports_execution_controls() -> None:
    config = parse_args(
        [
            "crawl",
            "--input",
            "data/input.jsonl",
            "--output",
            "output",
            "--auto-login",
            "--backend",
            "playwright",
            "--resume",
            "--artifacts-dir",
            "output/custom-artifacts",
            "--strict",
            "--concurrency",
            "5",
        ]
    )

    assert config.auto_login is True
    assert config.backend == "playwright"
    assert config.resume is True
    assert config.artifacts_dir == Path("output/custom-artifacts")
    assert config.strict is True
    assert config.concurrency == 5


def test_parse_args_supports_css_schema() -> None:
    config = parse_args(
        [
            "crawl",
            "--input",
            "data/input.jsonl",
            "--output",
            "output",
            "--css-schema",
            "config/css-schema.json",
        ]
    )

    assert config.css_schema_path == Path("config/css-schema.json")


def test_parse_args_supports_llm_schema_options() -> None:
    config = parse_args(
        [
            "run",
            "--input",
            "data/input.jsonl",
            "--output",
            "output",
            "--extract-llm-schema",
            "config/extract-llm-schema.json",
            "--enrich-llm-schema",
            "config/enrich-llm-schema.json",
            "--model-config",
            "config/model.json",
        ]
    )

    assert config.extract_llm_schema_path == Path("config/extract-llm-schema.json")
    assert config.enrich_llm_schema_path == Path("config/enrich-llm-schema.json")
    assert config.model_config_path == Path("config/model.json")


def test_parse_args_rejects_unknown_subcommand() -> None:
    with pytest.raises(SystemExit):
        parse_args(
            [
                "invalid",
                "--input",
                "data/input.jsonl",
                "--output",
                "output",
            ]
        )


def test_parse_discover_crawl_command() -> None:
    config = parse_args(
        ["discover-crawl", "--input", "in.jsonl", "--output", "out", "--max-depth", "3"]
    )
    assert config.command is CrawlCommand.DISCOVER_CRAWL
    assert config.max_depth == 3


def test_parse_discover_crawl_accepts_all_discovery_options() -> None:
    config = parse_args(
        [
            "discover-crawl",
            "--input",
            "in.jsonl",
            "--output",
            "out",
            "--max-depth",
            "5",
            "--max-pages",
            "200",
            "--sitemap-mode",
            "only",
        ]
    )
    assert config.max_depth == 5
    assert config.max_pages == 200
    assert config.sitemap_mode == "only"


def test_main_handles_bom_prefixed_jsonl_input(workspace_tmp_path: Path) -> None:
    input_path = workspace_tmp_path / "input.jsonl"
    output_dir = workspace_tmp_path / "out"
    input_path.write_text(
        "\ufeff" + json.dumps({"platform": "wikipedia", "resource_type": "article", "title": "Artificial intelligence"}) + "\n",
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

        html = "<html><body><article><h1>Artificial intelligence</h1></article></body></html>"
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

    from unittest.mock import patch

    with patch("crawler.fetch.engine.FetchEngine.fetch", fake_fetch):
        exit_code = main(["crawl", "--input", str(input_path), "--output", str(output_dir)])

    assert exit_code == 0
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "success"


def test_main_writes_dlq_and_runtime_metrics(workspace_tmp_path: Path, monkeypatch) -> None:
    input_path = workspace_tmp_path / "input.jsonl"
    output_dir = workspace_tmp_path / "out"
    input_path.write_text(json.dumps({"platform": "generic", "resource_type": "page", "url": "https://example.com"}) + "\n", encoding="utf-8")

    monkeypatch.setattr(
        "crawler.cli.run_command",
        lambda config: (
            [{"platform": "generic", "resource_type": "page", "canonical_url": "https://example.com"}],
            [
                {
                    "platform": "generic",
                    "resource_type": "page",
                    "canonical_url": "https://example.com/retry",
                    "error_code": "NETWORK_ERROR",
                    "retryable": True,
                    "message": "temporary failure",
                }
            ],
        ),
    )

    exit_code = main(["crawl", "--input", str(input_path), "--output", str(output_dir), "--concurrency", "4"])

    assert exit_code == 0
    dlq_lines = (output_dir / "dlq.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(dlq_lines) == 1
    dlq_entry = json.loads(dlq_lines[0])
    assert dlq_entry["error_code"] == "NETWORK_ERROR"
    metrics = json.loads((output_dir / "runtime_metrics.json").read_text(encoding="utf-8"))
    assert metrics["concurrency"] == 4
    assert metrics["retryable_errors"] == 1


def test_fill_enrichment_handles_bom_prefixed_json_files(workspace_tmp_path: Path) -> None:
    records_path = workspace_tmp_path / "records.jsonl"
    responses_path = workspace_tmp_path / "responses.json"
    records_path.write_text(
        "\ufeff"
        + json.dumps(
            {
                "doc_id": "doc-1",
                "enrichment": {
                    "enrichment_results": {
                        "summaries": {
                            "field_group": "summaries",
                            "status": "pending_agent",
                            "fields": [],
                        }
                    },
                    "enriched_fields": {},
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    responses_path.write_text(
        "\ufeff" + json.dumps({"doc-1:summaries": '{"summary":"摘要"}'}, ensure_ascii=False),
        encoding="utf-8",
    )

    exit_code = main(["fill-enrichment", "--records", str(records_path), "--responses", str(responses_path)])

    assert exit_code == 0
    updated = records_path.read_text(encoding="utf-8")
    assert '"status": "success"' in updated


def test_fill_enrichment_accepts_nested_enrichment_doc_id(workspace_tmp_path: Path) -> None:
    records_path = workspace_tmp_path / "records.jsonl"
    responses_path = workspace_tmp_path / "responses.json"
    records_path.write_text(
        json.dumps(
            {
                "canonical_url": "https://example.com/company/acme",
                "enrichment": {
                    "doc_id": "nested-doc-1",
                    "enrichment_results": {
                        "summaries": {
                            "field_group": "summaries",
                            "status": "pending_agent",
                            "fields": [],
                        }
                    },
                    "enriched_fields": {},
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    responses_path.write_text(
        json.dumps({"nested-doc-1:summaries": '{"summary":"Acme summary"}'}, ensure_ascii=False),
        encoding="utf-8",
    )

    exit_code = main(["fill-enrichment", "--records", str(records_path), "--responses", str(responses_path)])

    assert exit_code == 0
    updated = records_path.read_text(encoding="utf-8")
    assert '"status": "success"' in updated
    assert '"summary": "Acme summary"' in updated
