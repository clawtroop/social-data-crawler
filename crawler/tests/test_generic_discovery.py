from __future__ import annotations

import pytest

from crawler.discovery.adapters.generic import GenericDiscoveryAdapter
from crawler.discovery.contracts import DiscoveryCandidate, DiscoveryMode, DiscoveryRecord, MapOptions


@pytest.mark.asyncio
async def test_generic_map_extracts_same_domain_links_only() -> None:
    adapter = GenericDiscoveryAdapter()
    seed = DiscoveryRecord(
        platform="generic",
        resource_type="page",
        discovery_mode=DiscoveryMode.DIRECT_INPUT,
        canonical_url="https://example.com/docs",
        identity={"url": "https://example.com/docs"},
        source_seed=None,
        discovered_from=None,
        metadata={},
    )
    context = {
        "html": """
            <html><body>
              <a href="/guide">Guide</a>
              <a href="https://example.com/api">API</a>
              <a href="https://other.com/offsite">Offsite</a>
            </body></html>
        """,
        "options": MapOptions(),
    }

    result = await adapter.map(seed, context)
    urls = [candidate.canonical_url for candidate in result.accepted]

    assert "https://example.com/guide" in urls
    assert "https://example.com/api" in urls
    assert "https://other.com/offsite" not in urls


@pytest.mark.asyncio
async def test_generic_map_filters_external_and_subdomain_links_by_default() -> None:
    adapter = GenericDiscoveryAdapter()
    seed = DiscoveryRecord(
        platform="generic",
        resource_type="page",
        discovery_mode=DiscoveryMode.DIRECT_INPUT,
        canonical_url="https://example.com/docs",
        identity={"url": "https://example.com/docs"},
        source_seed=None,
        discovered_from=None,
        metadata={},
    )
    context = {
        "html": """
            <html><body>
              <a href="https://example.com/guide">Guide</a>
              <a href="https://sub.example.com/subpage">Subdomain</a>
              <a href="https://other.com/offsite">Offsite</a>
            </body></html>
        """,
        "options": MapOptions(),
    }

    result = await adapter.map(seed, context)
    urls = [candidate.canonical_url for candidate in result.accepted]

    assert "https://example.com/guide" in urls
    assert "https://sub.example.com/subpage" not in urls
    assert "https://other.com/offsite" not in urls


@pytest.mark.asyncio
async def test_generic_map_accepts_external_links_when_enabled() -> None:
    adapter = GenericDiscoveryAdapter()
    seed = DiscoveryRecord(
        platform="generic",
        resource_type="page",
        discovery_mode=DiscoveryMode.DIRECT_INPUT,
        canonical_url="https://example.com/docs",
        identity={"url": "https://example.com/docs"},
        source_seed=None,
        discovered_from=None,
        metadata={},
    )
    context = {
        "html": """
            <html><body>
              <a href="https://other.com/offsite">Offsite</a>
            </body></html>
        """,
        "options": MapOptions(allow_external_links=True),
    }

    result = await adapter.map(seed, context)
    urls = [candidate.canonical_url for candidate in result.accepted]

    assert "https://other.com/offsite" in urls


@pytest.mark.asyncio
async def test_generic_map_can_include_subdomains_when_enabled() -> None:
    adapter = GenericDiscoveryAdapter()
    seed = DiscoveryRecord(
        platform="generic",
        resource_type="page",
        discovery_mode=DiscoveryMode.DIRECT_INPUT,
        canonical_url="https://example.com/docs",
        identity={"url": "https://example.com/docs"},
        source_seed=None,
        discovered_from=None,
        metadata={},
    )
    context = {
        "html": """
            <html><body>
              <a href="https://sub.example.com/subpage">Subdomain</a>
            </body></html>
        """,
        "options": MapOptions(include_subdomains=True),
    }

    result = await adapter.map(seed, context)
    urls = [candidate.canonical_url for candidate in result.accepted]

    assert "https://sub.example.com/subpage" in urls


@pytest.mark.asyncio
async def test_generic_map_collapses_query_variants_when_ignored() -> None:
    adapter = GenericDiscoveryAdapter()
    seed = DiscoveryRecord(
        platform="generic",
        resource_type="page",
        discovery_mode=DiscoveryMode.DIRECT_INPUT,
        canonical_url="https://example.com/docs",
        identity={"url": "https://example.com/docs"},
        source_seed=None,
        discovered_from=None,
        metadata={},
    )
    context = {
        "html": """
            <html><body>
              <a href="https://example.com/page?ref=one">One</a>
              <a href="https://example.com/page?ref=two">Two</a>
            </body></html>
        """,
        "options": MapOptions(ignore_query_parameters=True),
    }

    result = await adapter.map(seed, context)
    urls = [candidate.canonical_url for candidate in result.accepted]

    assert urls == ["https://example.com/page"]


@pytest.mark.asyncio
async def test_generic_map_respects_limit() -> None:
    adapter = GenericDiscoveryAdapter()
    seed = DiscoveryRecord(
        platform="generic",
        resource_type="page",
        discovery_mode=DiscoveryMode.DIRECT_INPUT,
        canonical_url="https://example.com/docs",
        identity={"url": "https://example.com/docs"},
        source_seed=None,
        discovered_from=None,
        metadata={},
    )
    context = {
        "html": """
            <html><body>
              <a href="/one">One</a>
              <a href="/two">Two</a>
              <a href="/three">Three</a>
            </body></html>
        """,
        "options": MapOptions(limit=2),
    }

    result = await adapter.map(seed, context)

    assert len(result.accepted) == 2


def test_discovery_registry_returns_platform_specific_adapter() -> None:
    from crawler.discovery.adapters.registry import get_discovery_adapter
    from crawler.discovery.adapters.wikipedia import WikipediaDiscoveryAdapter

    adapter = get_discovery_adapter("wikipedia")

    assert isinstance(adapter, WikipediaDiscoveryAdapter)


def test_discovery_registry_falls_back_to_generic_for_unknown_platform() -> None:
    from crawler.discovery.adapters.generic import GenericDiscoveryAdapter
    from crawler.discovery.adapters.registry import get_discovery_adapter

    adapter = get_discovery_adapter("unknown")

    assert isinstance(adapter, GenericDiscoveryAdapter)


# --- Wikipedia Discovery Adapter Tests ---


@pytest.mark.asyncio
async def test_wikipedia_map_emits_article_candidates_from_api_links() -> None:
    from crawler.discovery.adapters.wikipedia import WikipediaDiscoveryAdapter

    adapter = WikipediaDiscoveryAdapter()
    seed = DiscoveryRecord(
        platform="wikipedia",
        resource_type="article",
        discovery_mode=DiscoveryMode.TEMPLATE_CONSTRUCTION,
        canonical_url="https://en.wikipedia.org/wiki/Artificial_intelligence",
        identity={"title": "Artificial_intelligence"},
        source_seed=None,
        discovered_from=None,
        metadata={},
    )
    context = {
        "page_links": ["Machine learning", "Deep learning"],
    }

    result = await adapter.map(seed, context)

    assert result.accepted[0].platform == "wikipedia"
    assert result.accepted[0].resource_type == "article"
    assert "Machine_learning" in result.accepted[0].canonical_url
    assert result.accepted[1].canonical_url == "https://en.wikipedia.org/wiki/Deep_learning"


# --- Amazon Discovery Adapter Tests ---


@pytest.mark.asyncio
async def test_amazon_map_promotes_search_results_to_product_candidates() -> None:
    from crawler.discovery.adapters.amazon import AmazonDiscoveryAdapter

    adapter = AmazonDiscoveryAdapter()
    result = await adapter.map_search_results(
        query="mechanical keyboard",
        urls=[
            "https://www.amazon.com/dp/B000000001",
            "https://www.amazon.com/dp/B000000002",
        ],
    )

    assert len(result.accepted) == 2
    assert result.accepted[0].resource_type == "product"
    assert result.accepted[0].fields["asin"] == "B000000001"
    assert result.accepted[1].fields["asin"] == "B000000002"


# --- LinkedIn Discovery Adapter Tests ---


@pytest.mark.asyncio
async def test_linkedin_map_promotes_search_results_to_entity_candidates() -> None:
    from crawler.discovery.adapters.linkedin import LinkedInDiscoveryAdapter

    adapter = LinkedInDiscoveryAdapter()
    result = await adapter.map_search_candidates(
        query="openai",
        search_type="company",
        candidates=[
            {
                "canonical_url": "https://www.linkedin.com/company/openai/",
                "resource_type": "company",
            }
        ],
    )

    assert len(result.accepted) == 1
    assert result.accepted[0].resource_type == "company"
    assert result.accepted[0].canonical_url == "https://www.linkedin.com/company/openai/"
    assert result.accepted[0].metadata["query"] == "openai"
    assert result.accepted[0].metadata["search_type"] == "company"


@pytest.mark.asyncio
async def test_generic_crawl_fetches_page_and_spawns_follow_on_candidates() -> None:
    adapter = GenericDiscoveryAdapter()
    candidate = DiscoveryCandidate(
        platform="generic",
        resource_type="page",
        canonical_url="https://example.com/docs",
        seed_url="https://example.com/docs",
        fields={},
        discovery_mode=DiscoveryMode.DIRECT_INPUT,
        score=1.0,
        score_breakdown={"direct_input": 1.0},
        hop_depth=0,
        parent_url=None,
        metadata={},
    )

    async def fake_fetch(url: str) -> dict[str, object]:
        return {
            "url": url,
            "html": '<html><body><a href="/guide">Guide</a></body></html>',
            "content_type": "text/html",
        }

    result = await adapter.crawl(candidate, {"fetch_fn": fake_fetch, "options": MapOptions()})

    assert result["fetched"]["url"] == "https://example.com/docs"
    assert result["spawned_candidates"][0].canonical_url == "https://example.com/guide"
