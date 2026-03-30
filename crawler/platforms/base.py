from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from crawler.contracts import NormalizedError
from crawler.extract.html_extract import extract_html_document
from crawler.fetch.unified import unified_fetch


@dataclass(frozen=True, slots=True)
class PlatformDiscoveryPlan:
    resource_types: tuple[str, ...]
    canonicalizer: str = "default"


@dataclass(frozen=True, slots=True)
class PlatformFetchPlan:
    default_backend: str
    fallback_backends: tuple[str, ...] = ()
    requires_auth: bool = False


@dataclass(frozen=True, slots=True)
class PlatformExtractPlan:
    strategy: str


@dataclass(frozen=True, slots=True)
class PlatformNormalizePlan:
    hook_name: str


@dataclass(frozen=True, slots=True)
class PlatformEnrichmentPlan:
    route: str
    field_groups: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PlatformErrorPlan:
    normalized_code: str
    retryable: bool = False


@dataclass(frozen=True, slots=True)
class PlatformAdapter:
    platform: str
    discovery: PlatformDiscoveryPlan
    fetch: PlatformFetchPlan
    extract: PlatformExtractPlan
    normalize: PlatformNormalizePlan
    enrich: PlatformEnrichmentPlan
    error: PlatformErrorPlan
    resolve_backend_fn: Callable[[dict[str, Any], str | None, int], str]
    fetch_fn: Callable[[dict[str, Any], dict[str, Any], str, str | None], dict[str, Any]]
    extract_fn: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]
    normalize_fn: Callable[[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]], dict[str, Any]]
    enrichment_fn: Callable[[dict[str, Any], tuple[str, ...]], dict[str, Any]]

    @property
    def supported_resource_types(self) -> tuple[str, ...]:
        return self.discovery.resource_types

    @property
    def requires_auth(self) -> bool:
        return self.fetch.requires_auth

    @property
    def default_backend(self) -> str:
        return self.fetch.default_backend

    @property
    def fallback_backends(self) -> tuple[str, ...]:
        return self.fetch.fallback_backends

    def resolve_backend(self, record: dict[str, Any], override_backend: str | None = None, retry_count: int = 0) -> str:
        return self.resolve_backend_fn(record, override_backend, retry_count)

    def extract_content(self, record: dict[str, Any], fetched: dict[str, Any]) -> dict[str, Any]:
        return self.extract_fn(record, fetched)

    def fetch_record(
        self,
        record: dict[str, Any],
        discovered: dict[str, Any],
        backend: str,
        storage_state_path: str | None = None,
    ) -> dict[str, Any]:
        return self.fetch_fn(record, discovered, backend, storage_state_path)

    def normalize_record(
        self,
        record: dict[str, Any],
        discovered: dict[str, Any],
        extracted: dict[str, Any],
        supplemental: dict[str, Any],
    ) -> dict[str, Any]:
        return self.normalize_fn(record, discovered, extracted, supplemental)

    def build_enrichment_request(self, record: dict[str, Any], requested_groups: tuple[str, ...] = ()) -> dict[str, Any]:
        return self.enrichment_fn(record, requested_groups)

    def normalize_error(
        self,
        *,
        resource_type: str | None,
        operation: str,
        exception: Exception,
    ) -> NormalizedError:
        return NormalizedError.from_exception(
            platform=self.platform,
            resource_type=resource_type,
            operation=operation,
            error_code=self.error.normalized_code,
            exception=exception,
            retryable=self.error.retryable,
        )


def default_backend_resolver(fetch: PlatformFetchPlan) -> Callable[[dict[str, Any], str | None, int], str]:
    def resolver(record: dict[str, Any], override_backend: str | None = None, retry_count: int = 0) -> str:
        if override_backend:
            return override_backend
        # Fallback applies to ALL platforms with declared fallback_backends, not just auth-required ones
        if fetch.fallback_backends and retry_count > 0:
            return fetch.fallback_backends[min(retry_count - 1, len(fetch.fallback_backends) - 1)]
        return fetch.default_backend

    return resolver


def default_fetch_executor(
    api_fetcher: Callable[[dict[str, Any], dict[str, Any], str | None], dict[str, Any]] | None = None,
) -> Callable[[dict[str, Any], dict[str, Any], str, str | None], dict[str, Any]]:
    """
    Creates a fetch executor that routes to the unified fetch interface.

    For "api" backend, uses the provided api_fetcher callable.
    For all other backends (http, playwright, camoufox), uses unified_fetch()
    which internally uses FetchEngine with BrowserPool, WaitStrategy, etc.
    """
    def fetcher(
        record: dict[str, Any],
        discovered: dict[str, Any],
        backend: str,
        storage_state_path: str | None = None,
    ) -> dict[str, Any]:
        if backend == "api":
            if api_fetcher is None:
                raise ValueError(f"platform {record['platform']} does not support api backend")
            return api_fetcher(record, discovered, storage_state_path)

        # Use unified fetch (internally uses FetchEngine)
        return unified_fetch(
            url=discovered["canonical_url"],
            platform=record["platform"],
            resource_type=record.get("resource_type"),
            backend=backend,
            storage_state_path=storage_state_path,
        )

    return fetcher


def strategy_extractor(strategy: str) -> Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]:
    def extractor(record: dict[str, Any], fetched: dict[str, Any]) -> dict[str, Any]:
        content_type = fetched.get("content_type")
        html = fetched.get("text") or fetched.get("html") or fetched.get("content_bytes", b"").decode("utf-8", "ignore")
        return extract_html_document(
            html,
            fetched["url"],
            content_type=content_type,
            platform=record["platform"],
            resource_type=record.get("resource_type", ""),
        )

    return extractor


def hook_normalizer(hook_name: str) -> Callable[[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]], dict[str, Any]]:
    def normalizer(
        record: dict[str, Any],
        discovered: dict[str, Any],
        extracted: dict[str, Any],
        supplemental: dict[str, Any],
    ) -> dict[str, Any]:
        metadata = extracted.get("metadata", {})
        if hook_name == "wikipedia":
            return {
                "title": metadata.get("title") or record.get("title"),
                "summary": extracted.get("plain_text", "").splitlines()[0] if extracted.get("plain_text") else "",
            }
        if hook_name == "arxiv":
            return {
                "arxiv_id": discovered["fields"].get("arxiv_id"),
                "abstract": extracted.get("plain_text", "").splitlines()[0] if extracted.get("plain_text") else "",
                "pdf_document_blocks": supplemental.get("document_blocks", []),
            }
        if hook_name == "amazon":
            return {"asin": discovered["fields"].get("asin"), "title": metadata.get("title")}
        if hook_name == "base_chain":
            return {
                "identifier": next(iter(discovered["fields"].values()), None),
                "title": metadata.get("title"),
            }
        if hook_name == "linkedin":
            extracted_structured = extracted.get("structured", {})
            linkedin_data = extracted_structured.get("linkedin", {}) if isinstance(extracted_structured, dict) else {}
            result = dict(linkedin_data) if isinstance(linkedin_data, dict) else {}
            public_identifier = discovered["fields"].get("public_identifier")
            if public_identifier:
                result.setdefault("public_identifier", public_identifier)
            title = metadata.get("title")
            if title:
                result.setdefault("title", title)
            return result
        if hook_name == "generic_page":
            result: dict[str, Any] = {}
            title = metadata.get("title")
            description = metadata.get("description")
            source_url = metadata.get("source_url")
            if title:
                result["title"] = title
            if description:
                result["description"] = description
            if source_url:
                result["source_url"] = source_url
            return result
        return {}

    return normalizer


def route_enrichment_groups(
    plan: PlatformEnrichmentPlan,
) -> Callable[[dict[str, Any], tuple[str, ...]], dict[str, Any]]:
    def builder(record: dict[str, Any], requested_groups: tuple[str, ...] = ()) -> dict[str, Any]:
        field_groups = requested_groups or plan.field_groups
        return {
            "route": plan.route,
            "field_groups": tuple(field_groups),
        }

    return builder
