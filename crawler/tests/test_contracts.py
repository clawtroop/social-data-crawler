from __future__ import annotations

from pathlib import Path

from crawler import CrawlerConfig, CrawlCommand
from crawler.contracts import NormalizedError
from crawler.platforms.registry import get_platform_adapter


def test_crawler_config_from_mapping_normalizes_paths_and_command() -> None:
    config = CrawlerConfig.from_mapping(
        {
            "command": "enrich",
            "input_path": "data/input.jsonl",
            "output_dir": "output",
            "cookies_path": "data/cookies.json",
            "platform": "linkedin",
        }
    )

    assert config.command is CrawlCommand.ENRICH
    assert config.input_path == Path("data/input.jsonl")
    assert config.output_dir == Path("output")
    assert config.cookies_path == Path("data/cookies.json")
    assert config.platform == "linkedin"


def test_crawler_config_defaults_command_to_run() -> None:
    config = CrawlerConfig.from_mapping(
        {
            "command": "run",
            "input_path": "data/input.jsonl",
            "output_dir": "output",
        }
    )

    assert config.command is CrawlCommand.RUN
    assert config.cookies_path is None
    assert config.platform is None


def test_crawler_config_normalizes_enrichment_options() -> None:
    config = CrawlerConfig.from_mapping(
        {
            "command": "enrich",
            "input_path": "data/input.jsonl",
            "output_dir": "output",
            "field_groups": ["summaries", "risk"],
        }
    )

    assert config.field_groups == ("summaries", "risk")


def test_crawler_config_normalizes_css_schema_path() -> None:
    config = CrawlerConfig.from_mapping(
        {
            "command": "crawl",
            "input_path": "data/input.jsonl",
            "output_dir": "output",
            "css_schema_path": "config/css-schema.json",
        }
    )

    assert config.css_schema_path == Path("config/css-schema.json")


def test_crawler_config_normalizes_llm_schema_paths() -> None:
    config = CrawlerConfig.from_mapping(
        {
            "command": "run",
            "input_path": "data/input.jsonl",
            "output_dir": "output",
            "extract_llm_schema_path": "config/extract-llm-schema.json",
            "enrich_llm_schema_path": "config/enrich-llm-schema.json",
            "model_config_path": "config/model.json",
        }
    )

    assert config.extract_llm_schema_path == Path("config/extract-llm-schema.json")
    assert config.enrich_llm_schema_path == Path("config/enrich-llm-schema.json")
    assert config.model_config_path == Path("config/model.json")


def test_platform_adapter_exposes_plans_and_hooks() -> None:
    adapter = get_platform_adapter("linkedin")

    assert adapter.discovery.resource_types == ("search", "profile", "company", "post", "job")
    assert adapter.fetch.default_backend == "api"
    assert adapter.fetch.fallback_backends == ("playwright", "camoufox")
    assert adapter.extract.strategy == "document"
    assert adapter.normalize.hook_name == "linkedin"
    assert adapter.enrich.route == "social_graph"
    assert adapter.error.normalized_code == "LINKEDIN_FETCH_FAILED"


def test_normalized_error_builds_from_platform_context() -> None:
    error = NormalizedError.from_exception(
        platform="wikipedia",
        resource_type="article",
        operation="fetch",
        error_code="WIKIPEDIA_FETCH_FAILED",
        exception=RuntimeError("network unavailable"),
        retryable=True,
    )

    assert error.platform == "wikipedia"
    assert error.resource_type == "article"
    assert error.operation == "fetch"
    assert error.normalized_code == "WIKIPEDIA_FETCH_FAILED"
    assert error.retryable is True
    assert error.message == "network unavailable"
