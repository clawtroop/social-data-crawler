from __future__ import annotations

import asyncio

import pytest

from crawler.discovery.contracts import CrawlOptions, DiscoveryCandidate, DiscoveryMode
from crawler.discovery.runner import run_discover_crawl


@pytest.mark.asyncio
async def test_run_discover_crawl_fetches_seed_and_returns_record() -> None:
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
            "html": "<html><body><h1>Docs</h1></body></html>",
            "content_type": "text/html",
        }

    records = await run_discover_crawl(
        seeds=[candidate],
        fetch_fn=fake_fetch,
        options=CrawlOptions(max_depth=0, max_pages=1),
    )

    record = records[0]
    assert record["canonical_url"] == "https://example.com/docs"
    assert record["fetched"] == {
        "url": "https://example.com/docs",
        "html": "<html><body><h1>Docs</h1></body></html>",
        "content_type": "text/html",
    }


@pytest.mark.asyncio
async def test_run_discover_crawl_accepts_to_legacy_dict_payload() -> None:
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

    class LegacyFetchResult:
        def to_legacy_dict(self) -> dict[str, object]:
            return {
                "url": "https://example.com/docs",
                "html": "<html><body><h1>Docs</h1></body></html>",
                "content_type": "text/html",
            }

    async def fake_fetch(url: str) -> LegacyFetchResult:
        return LegacyFetchResult()

    records = await run_discover_crawl(
        seeds=[candidate],
        fetch_fn=fake_fetch,
        options=CrawlOptions(max_depth=0, max_pages=1),
    )

    assert records[0]["fetched"] == {
        "url": "https://example.com/docs",
        "html": "<html><body><h1>Docs</h1></body></html>",
        "content_type": "text/html",
    }


@pytest.mark.asyncio
async def test_run_discover_crawl_rejects_unsupported_fetch_payload() -> None:
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

    async def fake_fetch(url: str) -> object:
        return object()

    with pytest.raises(TypeError, match="to_legacy_dict"):
        await run_discover_crawl(
            seeds=[candidate],
            fetch_fn=fake_fetch,
            options=CrawlOptions(max_depth=0, max_pages=1),
        )


@pytest.mark.asyncio
async def test_run_discover_crawl_uses_scheduler_and_visited_to_expand_graph() -> None:
    root = DiscoveryCandidate(
        platform="generic",
        resource_type="page",
        canonical_url="https://example.com/root",
        seed_url="https://example.com/root",
        fields={},
        discovery_mode=DiscoveryMode.DIRECT_INPUT,
        score=1.0,
        score_breakdown={"direct_input": 1.0},
        hop_depth=0,
        parent_url=None,
        metadata={},
    )

    child = DiscoveryCandidate(
        platform="generic",
        resource_type="page",
        canonical_url="https://example.com/child",
        seed_url="https://example.com/root",
        fields={},
        discovery_mode=DiscoveryMode.PAGE_LINKS,
        score=0.5,
        score_breakdown={"page_links": 0.5},
        hop_depth=1,
        parent_url="https://example.com/root",
        metadata={},
    )

    async def fake_fetch(url: str) -> dict[str, object]:
        return {"url": url, "html": f"<html>{url}</html>", "content_type": "text/html"}

    class FakeAdapter:
        async def crawl(self, candidate: DiscoveryCandidate, context: dict[str, object]) -> dict[str, object]:
            fetched = await context["fetch_fn"](candidate.canonical_url)
            spawned = [child, child] if candidate.canonical_url == "https://example.com/root" else []
            return {"candidate": candidate, "fetched": fetched, "spawned_candidates": spawned}

    def resolve_adapter(platform: str) -> FakeAdapter:
        assert platform == "generic"
        return FakeAdapter()

    records = await run_discover_crawl(
        seeds=[root],
        fetch_fn=fake_fetch,
        options=CrawlOptions(max_depth=2, max_pages=10),
        adapter_resolver=resolve_adapter,
    )

    assert [record["canonical_url"] for record in records] == [
        "https://example.com/root",
        "https://example.com/child",
    ]


@pytest.mark.asyncio
async def test_run_discover_crawl_persists_state_and_resumes(workspace_tmp_path) -> None:
    root = DiscoveryCandidate(
        platform="generic",
        resource_type="page",
        canonical_url="https://example.com/root",
        seed_url="https://example.com/root",
        fields={},
        discovery_mode=DiscoveryMode.DIRECT_INPUT,
        score=1.0,
        score_breakdown={"direct_input": 1.0},
        hop_depth=0,
        parent_url=None,
        metadata={},
    )
    child = DiscoveryCandidate(
        platform="generic",
        resource_type="page",
        canonical_url="https://example.com/child",
        seed_url="https://example.com/root",
        fields={},
        discovery_mode=DiscoveryMode.PAGE_LINKS,
        score=0.6,
        score_breakdown={"page_links": 0.6},
        hop_depth=1,
        parent_url="https://example.com/root",
        metadata={},
    )
    state_dir = workspace_tmp_path / "discovery-state"

    class FakeAdapter:
        async def crawl(self, candidate: DiscoveryCandidate, context: dict[str, object]) -> dict[str, object]:
            spawned = [child] if candidate.canonical_url == root.canonical_url else []
            return {
                "candidate": candidate,
                "fetched": {"url": candidate.canonical_url, "html": "<html></html>", "content_type": "text/html"},
                "spawned_candidates": spawned,
            }

    first = await run_discover_crawl(
        seeds=[root],
        fetch_fn=lambda _: {"url": "unused"},
        options=CrawlOptions(max_depth=2, max_pages=1),
        adapter_resolver=lambda platform: FakeAdapter(),
        state_dir=state_dir,
    )
    second = await run_discover_crawl(
        seeds=[root],
        fetch_fn=lambda _: {"url": "unused"},
        options=CrawlOptions(max_depth=2, max_pages=10),
        adapter_resolver=lambda platform: FakeAdapter(),
        state_dir=state_dir,
        resume=True,
    )

    assert [record["canonical_url"] for record in first] == ["https://example.com/root"]
    assert [record["canonical_url"] for record in second] == ["https://example.com/child"]


@pytest.mark.asyncio
async def test_run_discover_crawl_uses_multiple_workers_for_independent_seeds() -> None:
    seeds = [
        DiscoveryCandidate(
            platform="generic",
            resource_type="page",
            canonical_url=f"https://example.com/{i}",
            seed_url=f"https://example.com/{i}",
            fields={},
            discovery_mode=DiscoveryMode.DIRECT_INPUT,
            score=1.0,
            score_breakdown={"direct_input": 1.0},
            hop_depth=0,
            parent_url=None,
            metadata={},
        )
        for i in range(4)
    ]
    active = 0
    max_active = 0

    class FakeAdapter:
        async def crawl(self, candidate: DiscoveryCandidate, context: dict[str, object]) -> dict[str, object]:
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.02)
            active -= 1
            return {
                "candidate": candidate,
                "fetched": {"url": candidate.canonical_url, "html": "<html></html>", "content_type": "text/html"},
                "spawned_candidates": [],
            }

    records = await run_discover_crawl(
        seeds=seeds,
        fetch_fn=lambda _: {"url": "unused"},
        options=CrawlOptions(max_depth=0, max_pages=10, max_concurrency=2),
        adapter_resolver=lambda platform: FakeAdapter(),
    )

    assert len(records) == 4
    assert max_active >= 2
