from __future__ import annotations

from crawler.discovery.contracts import (
    CrawlOptions,
    DiscoveryCandidate,
    DiscoveryRecord,
    DiscoveryMode,
    MapOptions,
)
from crawler.discovery.url_builder import build_seed_records


def test_discovery_candidate_defaults() -> None:
    candidate = DiscoveryCandidate(
        platform="generic",
        resource_type="page",
        canonical_url="https://example.com/docs",
        seed_url="https://example.com",
        fields={},
        discovery_mode=DiscoveryMode.PAGE_LINKS,
        score=0.4,
        score_breakdown={"domain_trust": 0.4},
        hop_depth=1,
        parent_url="https://example.com",
        metadata={},
    )
    assert candidate.platform == "generic"
    assert candidate.discovery_mode is DiscoveryMode.PAGE_LINKS


def test_map_options_defaults_are_conservative() -> None:
    options = MapOptions()
    assert options.sitemap_mode == "include"
    assert options.include_subdomains is False
    assert options.allow_external_links is False
    assert options.ignore_query_parameters is True


def test_discovery_record_keeps_explicit_metadata() -> None:
    record = DiscoveryRecord(
        platform="generic",
        resource_type="page",
        discovery_mode=DiscoveryMode.DIRECT_INPUT,
        canonical_url="https://example.com/docs",
        identity={"url": "https://example.com/docs"},
        source_seed={"platform": "generic"},
        discovered_from={"reason": "seed"},
        metadata={"score": 1.0},
    )
    assert record.discovery_mode is DiscoveryMode.DIRECT_INPUT
    assert record.metadata == {"score": 1.0}


def test_crawl_options_extend_map_defaults() -> None:
    options = CrawlOptions()
    assert options.sitemap_mode == "include"
    assert options.max_depth == 2
    assert options.max_pages == 100
    assert options.crawl_entire_domain is False


def test_crawler_config_accepts_discovery_commands() -> None:
    from crawler.contracts import CrawlCommand, CrawlerConfig

    map_config = CrawlerConfig.from_mapping(
        {
            "command": "discover-map",
            "input_path": "input.jsonl",
            "output_dir": "out",
        }
    )
    crawl_config = CrawlerConfig.from_mapping(
        {
            "command": "discover-crawl",
            "input_path": "input.jsonl",
            "output_dir": "out",
        }
    )
    assert map_config.command is CrawlCommand.DISCOVER_MAP
    assert crawl_config.command is CrawlCommand.DISCOVER_CRAWL


def test_build_seed_records_returns_discovery_record() -> None:
    seed = {"platform": "wikipedia", "resource_type": "article", "title": "Artificial intelligence"}
    records = build_seed_records(seed)
    assert len(records) == 1
    record = records[0]
    assert record.discovery_mode is DiscoveryMode.TEMPLATE_CONSTRUCTION
    assert record.canonical_url == "https://en.wikipedia.org/wiki/Artificial_intelligence"
    assert record.identity == {"title": "Artificial_intelligence"}
    assert record.identity is not seed
    assert record.source_seed is seed
    assert record.metadata["artifacts"] == {}
    seed["title"] = "Machine learning"
    assert record.identity == {"title": "Artificial_intelligence"}
