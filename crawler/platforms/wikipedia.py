from __future__ import annotations

from urllib.parse import quote

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
EXTRACT_PLAN = PlatformExtractPlan(strategy="article_html")
NORMALIZE_PLAN = PlatformNormalizePlan(hook_name="wikipedia")
ENRICH_PLAN = PlatformEnrichmentPlan(
    route="knowledge_base",
    field_groups=(
        "summaries",
        "wikipedia_multi_level_summary",
        "wikipedia_relations",
    ),
)


def _fetch_wikipedia_api(record: dict, discovered: dict, storage_state_path: str | None) -> dict:
    title = discovered["fields"]["title"]
    endpoint = (
        "https://en.wikipedia.org/w/api.php"
        f"?action=query&titles={quote(title)}"
        "&prop=extracts|categories|pageprops&explaintext=1&cllimit=20&format=json&redirects=1"
    )
    return fetch_api_get(
        canonical_url=discovered["canonical_url"],
        api_endpoint=endpoint,
        headers={"Accept": "application/json"},
    )


def _extract_wikipedia(record: dict, fetched: dict) -> dict:
    data = fetched.get("json_data") or {}
    pages = ((data.get("query") or {}).get("pages") or {}).values()
    page = next(iter(pages), {})
    categories = [item.get("title", "").removeprefix("Category:") for item in page.get("categories", [])]
    title = page.get("title") or record.get("title")
    plain_text = page.get("extract") or ""
    markdown = f"# {title}\n\n{plain_text}".strip()
    return {
        "metadata": {
            "title": title,
            "content_type": fetched.get("content_type"),
            "source_url": fetched["url"],
            "pageprops": page.get("pageprops", {}),
        },
        "plain_text": plain_text,
        "markdown": markdown,
        "document_blocks": [],
        "structured": {"categories": categories},
        "extractor": "wikipedia_api",
    }


ADAPTER = PlatformAdapter(
    platform="wikipedia",
    discovery=PlatformDiscoveryPlan(resource_types=("article",), canonicalizer="wikipedia"),
    fetch=FETCH_PLAN,
    extract=EXTRACT_PLAN,
    normalize=NORMALIZE_PLAN,
    enrich=ENRICH_PLAN,
    error=PlatformErrorPlan(normalized_code="WIKIPEDIA_FETCH_FAILED"),
    resolve_backend_fn=default_backend_resolver(FETCH_PLAN),
    fetch_fn=default_fetch_executor(_fetch_wikipedia_api),
    extract_fn=_extract_wikipedia,
    normalize_fn=hook_normalizer(NORMALIZE_PLAN.hook_name),
    enrichment_fn=route_enrichment_groups(ENRICH_PLAN),
)
