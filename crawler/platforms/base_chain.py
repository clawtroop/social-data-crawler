from __future__ import annotations

import json
import os

from crawler.fetch.api_backend import fetch_api_get, fetch_api_post

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
EXTRACT_PLAN = PlatformExtractPlan(strategy="blockchain_scan")
NORMALIZE_PLAN = PlatformNormalizePlan(hook_name="base_chain")
ENRICH_PLAN = PlatformEnrichmentPlan(
    route="onchain_graph",
    field_groups=(
        "base_addresses_basic",
        "base_addresses_activity",
        "base_transactions_basic",
    ),
)


def _fetch_base_api(record: dict, discovered: dict, storage_state_path: str | None) -> dict:
    resource_type = record["resource_type"]
    if resource_type == "address":
        payload = {"jsonrpc": "2.0", "method": "eth_getBalance", "params": [discovered["fields"]["address"], "latest"], "id": 1}
        return fetch_api_post(
            canonical_url=discovered["canonical_url"],
            api_endpoint="https://mainnet.base.org",
            headers={"Content-Type": "application/json"},
            json_payload=payload,
        )
    if resource_type == "transaction":
        payload = {"jsonrpc": "2.0", "method": "eth_getTransactionByHash", "params": [discovered["fields"]["tx_hash"]], "id": 1}
        return fetch_api_post(
            canonical_url=discovered["canonical_url"],
            api_endpoint="https://mainnet.base.org",
            headers={"Content-Type": "application/json"},
            json_payload=payload,
        )
    if resource_type == "token":
        api_key = os.environ.get("BASESCAN_API_KEY", "")
        endpoint = (
            "https://api.basescan.org/api"
            f"?module=token&action=tokeninfo&contractaddress={discovered['fields']['contract_address']}"
        )
        if api_key:
            endpoint += f"&apikey={api_key}"
        return fetch_api_get(canonical_url=discovered["canonical_url"], api_endpoint=endpoint)
    if resource_type == "contract":
        api_key = os.environ.get("BASESCAN_API_KEY", "")
        endpoint = (
            "https://api.basescan.org/api"
            f"?module=contract&action=getsourcecode&address={discovered['fields']['contract_address']}"
        )
        if api_key:
            endpoint += f"&apikey={api_key}"
        return fetch_api_get(canonical_url=discovered["canonical_url"], api_endpoint=endpoint)
    raise ValueError(f"unsupported api resource for base: {resource_type}")


def _extract_base(record: dict, fetched: dict) -> dict:
    data = fetched.get("json_data") or {}
    result = data.get("result")
    plain_text = json.dumps(result, ensure_ascii=False, default=str)
    markdown = f"```json\n{plain_text}\n```"
    return {
        "metadata": {
            "title": record["resource_type"],
            "content_type": fetched.get("content_type"),
            "source_url": fetched["url"],
        },
        "plain_text": plain_text,
        "markdown": markdown,
        "document_blocks": [],
        "structured": {"rpc_result": result},
        "extractor": "base_api",
    }


ADAPTER = PlatformAdapter(
    platform="base",
    discovery=PlatformDiscoveryPlan(
        resource_types=("address", "transaction", "token", "contract"),
        canonicalizer="base_chain",
    ),
    fetch=FETCH_PLAN,
    extract=EXTRACT_PLAN,
    normalize=NORMALIZE_PLAN,
    enrich=ENRICH_PLAN,
    error=PlatformErrorPlan(normalized_code="BASE_CHAIN_FETCH_FAILED"),
    resolve_backend_fn=default_backend_resolver(FETCH_PLAN),
    fetch_fn=default_fetch_executor(_fetch_base_api),
    extract_fn=_extract_base,
    normalize_fn=hook_normalizer(NORMALIZE_PLAN.hook_name),
    enrichment_fn=route_enrichment_groups(ENRICH_PLAN),
)
