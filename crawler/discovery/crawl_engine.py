from __future__ import annotations

from typing import Any

from crawler.discovery.contracts import CrawlOptions, DiscoveryCandidate


def normalize_fetched_payload(fetched: Any) -> dict[str, Any]:
    if isinstance(fetched, dict):
        return fetched

    to_legacy_dict = getattr(fetched, "to_legacy_dict", None)
    if callable(to_legacy_dict):
        payload = to_legacy_dict()
        if isinstance(payload, dict):
            return payload

    raise TypeError(
        "expected fetch payload to be a dict or an object with to_legacy_dict()"
    )


async def crawl_generic(
    *,
    seeds: list[DiscoveryCandidate],
    fetch_fn: Any,
    options: CrawlOptions,
) -> list[dict[str, Any]]:
    from crawler.discovery.runner import run_discover_crawl

    return await run_discover_crawl(seeds=seeds, fetch_fn=fetch_fn, options=options)
