from __future__ import annotations

from dataclasses import fields

import pytest

from crawler.discovery.state.checkpoint import Checkpoint
from crawler.discovery.state.frontier import FrontierEntry, FrontierStatus
from crawler.discovery.state.edges import DiscoveryEdge
from crawler.discovery.state.occupancy import OccupancyLease
from crawler.discovery.state.job import JobSpec
from crawler.discovery.state.visited import VisitRecord
from crawler.discovery.scheduler import DiscoveryScheduler
from crawler.discovery.store.checkpoint_store import InMemoryCheckpointStore
from crawler.discovery.store.frontier_store import InMemoryFrontierStore


def test_job_spec_keeps_mode_and_session_ref() -> None:
    job = JobSpec(
        job_id="job-1",
        mode="map",
        adapter="generic",
        seed_set=["https://example.com"],
        limits={"max_pages": 10},
        session_ref=None,
        created_at="2026-03-30T00:00:00Z",
    )
    assert job.mode == "map"
    assert job.session_ref is None
    assert job.seed_set == ["https://example.com"]
    assert job.limits == {"max_pages": 10}


def test_frontier_entry_starts_queued() -> None:
    entry = FrontierEntry(
        frontier_id="f1",
        job_id="job-1",
        url_key="generic:https://example.com",
        canonical_url="https://example.com",
        adapter="generic",
        entity_type="page",
        depth=0,
        priority=1.0,
        discovered_from=None,
        discovery_reason="direct_input",
    )
    assert entry.status is FrontierStatus.QUEUED
    assert entry.attempt == 0
    assert entry.discovered_from is None


def test_visit_record_separates_map_and_crawl_state() -> None:
    record = VisitRecord(
        url_key="generic:https://example.com",
        canonical_url="https://example.com",
        scope_key="example.com",
        first_seen_at="2026-03-30T00:00:00Z",
        last_seen_at="2026-03-30T00:00:00Z",
        best_depth=0,
    )
    assert record.map_state is None
    assert record.crawl_state is None
    assert record.adapter_state == {}


def test_checkpoint_keeps_cursor_state_minimal() -> None:
    checkpoint = Checkpoint(
        job_id="job-1",
        checkpoint_id="ckpt-1",
        created_at="2026-03-30T00:00:00Z",
        frontier_cursor="frontier:1",
        visited_cursor="visited:1",
    )
    assert checkpoint.frontier_cursor == "frontier:1"
    assert checkpoint.visited_cursor == "visited:1"
    assert "notes" in {field.name for field in fields(Checkpoint)}


def test_checkpoint_store_uses_explicit_checkpoint_id() -> None:
    store = InMemoryCheckpointStore()
    checkpoint = Checkpoint(
        job_id="job-1",
        checkpoint_id="ckpt-1",
        created_at="2026-03-30T00:00:00Z",
        frontier_cursor="frontier:1",
        visited_cursor="visited:1",
    )
    store.put("ckpt-1", checkpoint)
    assert store.get("ckpt-1") is checkpoint
    assert store.get("job-1") is None


def test_occupancy_lease_captures_worker_ownership() -> None:
    lease = OccupancyLease(
        lease_id="lease-1",
        job_id="job-1",
        frontier_id="f1",
        worker_id="worker-1",
        leased_at="2026-03-30T00:00:00Z",
    )
    assert lease.worker_id == "worker-1"
    assert lease.expires_at is None


def test_discovery_edge_remains_typed_and_small() -> None:
    edge = DiscoveryEdge(
        edge_id="edge-1",
        job_id="job-1",
        parent_url="https://example.com",
        child_url="https://example.com/docs",
        reason="page_link",
        observed_at="2026-03-30T00:00:00Z",
    )
    assert edge.parent_url == "https://example.com"
    assert edge.child_url == "https://example.com/docs"
    assert edge.reason == "page_link"
    assert edge.observed_at == "2026-03-30T00:00:00Z"


@pytest.mark.asyncio
async def test_scheduler_leases_highest_priority_entry() -> None:
    scheduler = DiscoveryScheduler()
    scheduler.enqueue(
        FrontierEntry(
            frontier_id="low",
            job_id="job-1",
            url_key="k-low",
            canonical_url="https://example.com/low",
            adapter="generic",
            entity_type="page",
            depth=0,
            priority=0.1,
            discovered_from=None,
            discovery_reason="page_links",
        )
    )
    scheduler.enqueue(
        FrontierEntry(
            frontier_id="high",
            job_id="job-1",
            url_key="k-high",
            canonical_url="https://example.com/high",
            adapter="generic",
            entity_type="page",
            depth=0,
            priority=0.9,
            discovered_from=None,
            discovery_reason="sitemap",
        )
    )
    leased = await scheduler.lease_next(worker_id="worker-1")
    assert leased is not None
    assert leased.frontier_id == "high"
    assert scheduler.occupancy_store.list()[0].leased_at.endswith("Z")


def test_frontier_store_does_not_lease_non_queued_entries() -> None:
    store = InMemoryFrontierStore()
    entry = FrontierEntry(
        frontier_id="done",
        job_id="job-1",
        url_key="k-done",
        canonical_url="https://example.com/done",
        adapter="generic",
        entity_type="page",
        depth=0,
        priority=1.0,
        discovered_from=None,
        discovery_reason="page_links",
        status=FrontierStatus.DONE,
        attempt=2,
    )
    store.put(entry)

    leased = store.lease("done")

    assert leased is None
    assert store.get("done") is entry
    assert store.get("done").attempt == 2
