from __future__ import annotations

import re

from crawler.fetch.api_backend import fetch_api_get

from .base import (
    PlatformAdapter,
    PlatformDiscoveryPlan,
    PlatformEnrichmentPlan,
    PlatformErrorPlan,
    PlatformExtractPlan,
    PlatformFetchPlan,
    PlatformNormalizePlan,
    default_fetch_executor,
    default_backend_resolver,
    hook_normalizer,
    route_enrichment_groups,
    strategy_extractor,
)

FETCH_PLAN = PlatformFetchPlan(default_backend="api", fallback_backends=("http", "playwright"))
EXTRACT_PLAN = PlatformExtractPlan(strategy="paper_metadata")
NORMALIZE_PLAN = PlatformNormalizePlan(hook_name="arxiv")
ENRICH_PLAN = PlatformEnrichmentPlan(route="research_graph", field_groups=("summaries", "citations"))


def _fetch_arxiv_api(record: dict, discovered: dict, storage_state_path: str | None) -> dict:
    arxiv_id = discovered["fields"]["arxiv_id"]
    endpoint = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
    return fetch_api_get(
        canonical_url=discovered["canonical_url"],
        api_endpoint=endpoint,
        headers={"Accept": "application/atom+xml,text/xml;q=0.9,*/*;q=0.8"},
    )


def _extract_arxiv(record: dict, fetched: dict) -> dict:
    text = fetched.get("text", "")
    title_matches = re.findall(r"<title>\s*(.*?)\s*</title>", text, flags=re.S)
    summary_match = re.search(r"<summary>\s*(.*?)\s*</summary>", text, flags=re.S)
    authors = re.findall(r"<name>\s*(.*?)\s*</name>", text, flags=re.S)
    raw_title = title_matches[1] if len(title_matches) > 1 else (title_matches[0] if title_matches else record.get("arxiv_id"))
    title = re.sub(r"\s+", " ", raw_title).strip()
    summary = re.sub(r"\s+", " ", summary_match.group(1)).strip() if summary_match else ""
    markdown = f"# {title}\n\n{summary}".strip()
    return {
        "metadata": {
            "title": title,
            "authors": authors,
            "content_type": fetched.get("content_type"),
            "source_url": fetched["url"],
        },
        "plain_text": summary,
        "markdown": markdown,
        "document_blocks": [],
        "structured": {"authors": authors},
        "extractor": "arxiv_api",
    }


ADAPTER = PlatformAdapter(
    platform="arxiv",
    discovery=PlatformDiscoveryPlan(resource_types=("paper",), canonicalizer="arxiv"),
    fetch=FETCH_PLAN,
    extract=EXTRACT_PLAN,
    normalize=NORMALIZE_PLAN,
    enrich=ENRICH_PLAN,
    error=PlatformErrorPlan(normalized_code="ARXIV_FETCH_FAILED"),
    resolve_backend_fn=default_backend_resolver(FETCH_PLAN),
    fetch_fn=default_fetch_executor(_fetch_arxiv_api),
    extract_fn=_extract_arxiv,
    normalize_fn=hook_normalizer(NORMALIZE_PLAN.hook_name),
    enrichment_fn=route_enrichment_groups(ENRICH_PLAN),
)
