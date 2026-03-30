from __future__ import annotations

import inspect
from datetime import datetime, timezone
from typing import Any

from crawler.discovery.contracts import CrawlOptions, DiscoveryCandidate
from crawler.discovery.scheduler import DiscoveryScheduler
from crawler.discovery.state.frontier import FrontierEntry
from crawler.discovery.state.visited import VisitRecord
from crawler.discovery.store.visited_store import InMemoryVisitedStore


async def run_discover_crawl(
    *,
    seeds: list[DiscoveryCandidate],
    fetch_fn: Any,
    options: CrawlOptions,
    adapter_resolver: Any | None = None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if options.max_pages <= 0:
        return records

    if adapter_resolver is not None:
        return await _run_discover_crawl_graph(
            seeds=seeds,
            fetch_fn=fetch_fn,
            options=options,
            adapter_resolver=adapter_resolver,
        )

    for candidate in seeds:
        if len(records) >= options.max_pages:
            break
        if candidate.hop_depth > options.max_depth:
            continue
        if not candidate.canonical_url:
            continue

        fetched = fetch_fn(candidate.canonical_url)
        if inspect.isawaitable(fetched):
            fetched = await fetched

        record = {
            "platform": candidate.platform,
            "resource_type": candidate.resource_type,
            "canonical_url": candidate.canonical_url,
            "seed_url": candidate.seed_url,
            "discovery_mode": candidate.discovery_mode.value,
            "hop_depth": candidate.hop_depth,
            "fetched": _normalize_fetched_payload(fetched),
        }
        records.append(record)

    return records


async def _run_discover_crawl_graph(
    *,
    seeds: list[DiscoveryCandidate],
    fetch_fn: Any,
    options: CrawlOptions,
    adapter_resolver: Any,
) -> list[dict[str, Any]]:
    scheduler = DiscoveryScheduler()
    visited_store = InMemoryVisitedStore()
    candidates_by_frontier_id: dict[str, DiscoveryCandidate] = {}
    records: list[dict[str, Any]] = []

    for index, seed in enumerate(seeds):
        if not seed.canonical_url:
            continue
        frontier_id = f"seed-{index}"
        candidates_by_frontier_id[frontier_id] = seed
        scheduler.enqueue(
            FrontierEntry(
                frontier_id=frontier_id,
                job_id="discover-crawl",
                url_key=_url_key(seed),
                canonical_url=seed.canonical_url,
                adapter=seed.platform,
                entity_type=seed.resource_type,
                depth=seed.hop_depth,
                priority=seed.score,
                discovered_from={"parent_url": seed.parent_url} if seed.parent_url else None,
                discovery_reason=seed.discovery_mode.value,
            )
        )

    while len(records) < options.max_pages:
        leased = scheduler.lease_next("worker-1")
        if leased is None:
            break

        candidate = candidates_by_frontier_id.get(leased.frontier_id)
        if candidate is None or not candidate.canonical_url or candidate.hop_depth > options.max_depth:
            continue
        if visited_store.get(_url_key(candidate)) is not None:
            continue

        adapter = adapter_resolver(candidate.platform)
        crawl_result = await adapter.crawl(
            candidate,
            {
                "fetch_fn": lambda _ignored=None, _candidate=candidate: _call_fetch(fetch_fn, _candidate),
                "options": options,
                "query": candidate.metadata.get("query", ""),
                "search_type": candidate.metadata.get("search_type", ""),
            },
        )
        fetched = _normalize_fetched_payload(crawl_result.get("fetched", {}))
        records.append(
            {
                "platform": candidate.platform,
                "resource_type": candidate.resource_type,
                "canonical_url": candidate.canonical_url,
                "seed_url": candidate.seed_url,
                "discovery_mode": candidate.discovery_mode.value,
                "hop_depth": candidate.hop_depth,
                "fetched": fetched,
            }
        )
        visited_store.put(
            VisitRecord(
                url_key=_url_key(candidate),
                canonical_url=candidate.canonical_url,
                scope_key=_scope_key(candidate.canonical_url),
                first_seen_at=_now_iso(),
                last_seen_at=_now_iso(),
                best_depth=candidate.hop_depth,
                crawl_state="done",
                final_url=str(fetched.get("final_url") or fetched.get("url") or candidate.canonical_url),
                http_status=int(fetched.get("status_code", 200)) if fetched.get("status_code") is not None else None,
            )
        )

        for spawned in crawl_result.get("spawned_candidates", []):
            if not spawned.canonical_url or spawned.hop_depth > options.max_depth:
                continue
            if visited_store.get(_url_key(spawned)) is not None:
                continue
            frontier_id = f"{leased.frontier_id}:{len(candidates_by_frontier_id)}"
            candidates_by_frontier_id[frontier_id] = spawned
            scheduler.enqueue(
                FrontierEntry(
                    frontier_id=frontier_id,
                    job_id="discover-crawl",
                    url_key=_url_key(spawned),
                    canonical_url=spawned.canonical_url,
                    adapter=spawned.platform,
                    entity_type=spawned.resource_type,
                    depth=spawned.hop_depth,
                    priority=spawned.score,
                    discovered_from={"parent_url": spawned.parent_url} if spawned.parent_url else None,
                    discovery_reason=spawned.discovery_mode.value,
                )
            )

    return records


async def _call_fetch(fetch_fn: Any, candidate: DiscoveryCandidate) -> dict[str, Any]:
    try:
        fetched = fetch_fn(candidate)
    except TypeError:
        fetched = fetch_fn(candidate.canonical_url)
    if inspect.isawaitable(fetched):
        fetched = await fetched
    if not isinstance(fetched, dict):
        fetched = fetch_fn(candidate.canonical_url)
        if inspect.isawaitable(fetched):
            fetched = await fetched
    return _normalize_fetched_payload(fetched)


def _url_key(candidate: DiscoveryCandidate) -> str:
    return f"{candidate.platform}:{candidate.canonical_url}"


def _scope_key(url: str) -> str:
    if "//" in url:
        return url.split("//", 1)[1].split("/", 1)[0]
    return url


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _normalize_fetched_payload(fetched: Any) -> dict[str, Any]:
    if isinstance(fetched, dict):
        return fetched

    to_legacy_dict = getattr(fetched, "to_legacy_dict", None)
    if callable(to_legacy_dict):
        payload = to_legacy_dict()
        if isinstance(payload, dict):
            return payload

    raise TypeError(
        "run_discover_crawl expected fetch_fn to return a dict or an object with to_legacy_dict()"
    )
