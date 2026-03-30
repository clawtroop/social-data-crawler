"""LinkedIn discovery adapter for profile, company, and job discovery."""
from __future__ import annotations

import re
from dataclasses import replace
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from crawler.discovery.adapters.base import BaseDiscoveryAdapter
from crawler.discovery.contracts import (
    DiscoveryCandidate,
    DiscoveryMode,
    DiscoveryRecord,
)
from crawler.discovery.map_engine import MapResult


class LinkedInDiscoveryAdapter(BaseDiscoveryAdapter):
    """Discovery adapter for LinkedIn entities.

    Handles discovery of profiles, companies, posts, and jobs from search results.
    """

    platform = "linkedin"
    supported_resource_types = ("search", "profile", "company", "post", "job")

    def can_handle_url(self, url: str) -> bool:
        return "linkedin.com" in url

    def build_seed_records(self, input_record: dict[str, Any]) -> list[DiscoveryRecord]:
        from crawler.discovery.url_builder import build_seed_records

        return build_seed_records(input_record)

    async def map_search_candidates(
        self,
        query: str,
        search_type: str,
        candidates: list[dict[str, Any]],
    ) -> MapResult:
        """Promote search candidates to entity candidates.

        Args:
            query: The search query used
            search_type: Type of search (profile, company, job, etc.)
            candidates: List of candidate dicts with canonical_url and resource_type

        Returns:
            MapResult with accepted entity candidates
        """
        accepted: list[DiscoveryCandidate] = []

        for item in candidates:
            accepted.append(
                DiscoveryCandidate(
                    platform="linkedin",
                    resource_type=item["resource_type"],
                    canonical_url=item["canonical_url"],
                    seed_url=None,
                    fields={},
                    discovery_mode=DiscoveryMode.SEARCH_RESULTS,
                    score=0.85,
                    score_breakdown={"search_results": 0.85},
                    hop_depth=1,
                    parent_url=None,
                    metadata={"query": query, "search_type": search_type},
                )
            )

        return MapResult(accepted=accepted, rejected=[], exhausted=True, next_seeds=[])

    async def map(
        self, seed: DiscoveryRecord, context: dict[str, Any]
    ) -> MapResult:
        """Extract entity candidates from a LinkedIn page."""
        search_candidates = list(context.get("search_candidates", []))
        if not search_candidates:
            html = str(context.get("html") or "")
            soup = BeautifulSoup(html, "html.parser")
            for anchor in soup.find_all("a", href=True):
                href = str(anchor.get("href") or "")
                absolute = urljoin(seed.canonical_url, href)
                if "/company/" in absolute:
                    search_candidates.append({"canonical_url": absolute.rstrip("/").split("?")[0] + "/", "resource_type": "company"})
                elif "/in/" in absolute:
                    search_candidates.append({"canonical_url": absolute.rstrip("/").split("?")[0] + "/", "resource_type": "profile"})
                elif "/jobs/view/" in absolute:
                    search_candidates.append({"canonical_url": absolute.split("?")[0], "resource_type": "job"})

            for match in re.findall(r'https://www\.linkedin\.com/(company/[^"\']+|in/[^"\']+|jobs/view/\d+)', html):
                canonical_url = f"https://www.linkedin.com/{match}".split("?")[0]
                resource_type = "company" if match.startswith("company/") else "profile" if match.startswith("in/") else "job"
                if resource_type in {"company", "profile"} and not canonical_url.endswith("/"):
                    canonical_url += "/"
                search_candidates.append({"canonical_url": canonical_url, "resource_type": resource_type})

        # For now, delegate to search candidates if available
        if search_candidates:
            return await self.map_search_candidates(
                query=context.get("query", ""),
                search_type=context.get("search_type", ""),
                candidates=list({
                    (item["canonical_url"], item["resource_type"]): item
                    for item in search_candidates
                }.values()),
            )
        return MapResult(accepted=[], rejected=[], exhausted=True, next_seeds=[])

    async def crawl(
        self, candidate: DiscoveryCandidate, context: dict[str, Any]
    ) -> Any:
        fetch_fn = context.get("fetch_fn")
        if not callable(fetch_fn) or not candidate.canonical_url:
            return {"candidate": candidate, "fetched": {}, "spawned_candidates": []}

        fetched = fetch_fn(candidate.canonical_url)
        if hasattr(fetched, "__await__"):
            fetched = await fetched
        if not isinstance(fetched, dict):
            to_legacy_dict = getattr(fetched, "to_legacy_dict", None)
            if callable(to_legacy_dict):
                fetched = to_legacy_dict()
        if not isinstance(fetched, dict):
            raise TypeError("linkedin crawl expected fetched payload as dict or to_legacy_dict()")

        seed = DiscoveryRecord(
            platform=candidate.platform,
            resource_type=candidate.resource_type,
            discovery_mode=candidate.discovery_mode,
            canonical_url=candidate.canonical_url,
            identity=dict(candidate.fields),
            source_seed=None,
            discovered_from={"parent_url": candidate.parent_url},
            metadata=dict(candidate.metadata),
        )
        map_result = await self.map(
            seed,
            {
                "query": context.get("query", ""),
                "search_type": context.get("search_type", ""),
                "html": fetched.get("html", ""),
            },
        )
        spawned_candidates = [
            replace(
                spawned,
                seed_url=candidate.seed_url or candidate.canonical_url,
                hop_depth=candidate.hop_depth + 1,
                parent_url=candidate.canonical_url,
            )
            for spawned in map_result.accepted
        ]
        return {
            "candidate": candidate,
            "fetched": fetched,
            "spawned_candidates": spawned_candidates,
        }
