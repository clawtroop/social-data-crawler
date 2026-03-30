from __future__ import annotations

from crawler.extract.html_extract import extract_html_document

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

FETCH_PLAN = PlatformFetchPlan(default_backend="http", fallback_backends=("playwright", "camoufox"))
EXTRACT_PLAN = PlatformExtractPlan(strategy="commerce_page")
NORMALIZE_PLAN = PlatformNormalizePlan(hook_name="amazon")
ENRICH_PLAN = PlatformEnrichmentPlan(route="commerce_graph", field_groups=("pricing", "availability"))


def _extract_amazon(record: dict, fetched: dict) -> dict:
    html = fetched.get("text") or fetched.get("html") or fetched.get("content_bytes", b"").decode("utf-8", "ignore")
    return extract_html_document(
        html,
        fetched["url"],
        content_type=fetched.get("content_type"),
        platform=record["platform"],
        resource_type=record.get("resource_type", ""),
    )


ADAPTER = PlatformAdapter(
    platform="amazon",
    discovery=PlatformDiscoveryPlan(
        resource_types=("product", "seller", "search"),
        canonicalizer="amazon",
    ),
    fetch=FETCH_PLAN,
    extract=EXTRACT_PLAN,
    normalize=NORMALIZE_PLAN,
    enrich=ENRICH_PLAN,
    error=PlatformErrorPlan(normalized_code="AMAZON_FETCH_FAILED"),
    resolve_backend_fn=default_backend_resolver(FETCH_PLAN),
    fetch_fn=default_fetch_executor(),
    extract_fn=_extract_amazon,
    normalize_fn=hook_normalizer(NORMALIZE_PLAN.hook_name),
    enrichment_fn=route_enrichment_groups(ENRICH_PLAN),
)
