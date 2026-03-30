from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx

from crawler.contracts import CrawlerConfig
from crawler.io import read_json_file, read_jsonl_file
from crawler.discovery.url_builder import build_url
from crawler.enrich.orchestrator import route_enrichment
from crawler.extract.html_extract import _is_html_content_type
from crawler.extract.unstructured_extract import _is_document_content_type, extract_document_blocks
from crawler.fetch.unified import unified_fetch  # unified entry point, replaces orchestrator
from crawler.fetch.session_store import SessionStore
from crawler.normalize.canonical import build_canonical_record
from crawler.output.artifact_writer import write_artifact_bytes, write_artifact_json, write_artifact_text
from crawler.platforms.registry import get_platform_adapter


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return read_jsonl_file(path)


def _resolve_storage_state_path(config: CrawlerConfig, platform: str, adapter, session_store: SessionStore) -> str | None:
    if config.cookies_path is not None:
        return str(session_store.import_cookies(platform, config.cookies_path))
    if session_store.load(platform) is not None:
        return str(session_store.root / f"{platform}.json")
    if getattr(adapter, "requires_auth", False) and config.auto_login and platform == "linkedin":
        from crawler.integrations import LinkedInAutoBrowserBridge, get_default_auto_browser_script

        bridge = LinkedInAutoBrowserBridge(
            script_path=get_default_auto_browser_script(),
            workdir=Path(os.environ.get("WORKDIR", Path.home() / ".openclaw" / "vrd-data")),
        )
        exported_path = bridge.ensure_exported_session(session_store.root.parent)
        return str(session_store.import_cookies(platform, exported_path))
    return None


def _build_error(
    *,
    platform: str,
    resource_type: str | None,
    stage: str,
    error_code: str,
    retryable: bool,
    next_action: str,
    message: str,
) -> dict[str, Any]:
    return {
        "platform": platform,
        "resource_type": resource_type,
        "stage": stage,
        "status": "failed",
        "error_code": error_code,
        "retryable": retryable,
        "next_action": next_action,
        "message": message,
    }


def _classify_auth_error(
    *,
    platform: str,
    resource_type: str | None,
    exception: Exception,
    has_session: bool,
) -> dict[str, Any] | None:
    if not has_session:
        return None
    if isinstance(exception, httpx.HTTPStatusError) and exception.response is not None:
        if exception.response.status_code in {401, 403}:
            return _build_error(
                platform=platform,
                resource_type=resource_type,
                stage="fetch",
                error_code="AUTH_EXPIRED",
                retryable=True,
                next_action="refresh login session and retry",
                message=str(exception),
            )
    return None


def _artifacts_root(config: CrawlerConfig) -> Path:
    return config.artifacts_dir or (config.output_dir / "artifacts")


def _record_slug(index: int, record: dict[str, Any], discovered: dict[str, Any]) -> str:
    canonical_url = discovered["canonical_url"].rstrip("/")
    tail = canonical_url.split("/")[-1] or f"record-{index}"
    slug = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in tail)
    return slug or f"record-{index}"


def _artifact_relpath(path: Path, root: Path) -> str:
    return path.relative_to(root.parent).as_posix()


def _persist_fetch_artifacts(
    *,
    artifact_root: Path,
    slug: str,
    fetched: dict[str, Any],
    root_for_rel: Path,
) -> list[dict[str, Any]]:
    written: list[dict[str, Any]] = []
    content_type = fetched.get("content_type")
    if fetched.get("backend") == "api" or fetched.get("json_data") is not None:
        api_path = artifact_root / slug / "api_response.json"
        write_artifact_text(api_path, fetched.get("text", ""))
        written.append(
            {
                "kind": "api_response",
                "path": _artifact_relpath(api_path, root_for_rel),
                "content_type": content_type or "application/json",
            }
        )
        # Write fetch.json for API responses too (consistency with HTML path)
        metadata_path = artifact_root / slug / "fetch.json"
        write_artifact_json(
            metadata_path,
            {
                "url": fetched.get("url"),
                "status_code": fetched.get("status_code"),
                "headers": fetched.get("headers", {}),
                "backend": fetched.get("backend"),
                "content_type": content_type,
            },
        )
        written.append({"kind": "fetch", "path": _artifact_relpath(metadata_path, root_for_rel), "content_type": "application/json"})
        return written
    if fetched.get("content_bytes") is not None:
        if _is_html_content_type(content_type):
            html_path = artifact_root / slug / "page.html"
            write_artifact_text(html_path, fetched.get("text") or fetched["content_bytes"].decode("utf-8", "ignore"))
            written.append(
                {
                    "kind": "html",
                    "path": _artifact_relpath(html_path, root_for_rel),
                    "content_type": content_type,
                }
            )
        else:
            ext = ".pdf" if str(content_type or "").startswith("application/pdf") else ".bin"
            binary_path = artifact_root / slug / f"source{ext}"
            write_artifact_bytes(binary_path, fetched["content_bytes"])
            written.append(
                {
                    "kind": "source",
                    "path": _artifact_relpath(binary_path, root_for_rel),
                    "content_type": content_type,
                }
            )
    if fetched.get("screenshot_bytes") is not None:
        screenshot_path = artifact_root / slug / "screenshot.png"
        write_artifact_bytes(screenshot_path, fetched["screenshot_bytes"])
        written.append(
            {
                "kind": "screenshot",
                "path": _artifact_relpath(screenshot_path, root_for_rel),
                "content_type": "image/png",
            }
        )
    metadata_path = artifact_root / slug / "fetch.json"
    write_artifact_json(
        metadata_path,
        {
            "url": fetched.get("url"),
            "status_code": fetched.get("status_code"),
            "headers": fetched.get("headers", {}),
            "backend": fetched.get("backend"),
            "content_type": content_type,
        },
    )
    written.append({"kind": "fetch", "path": _artifact_relpath(metadata_path, root_for_rel), "content_type": "application/json"})
    return written


def _extract_primary_content(
    *,
    adapter,
    record: dict[str, Any],
    fetched: dict[str, Any],
    artifact_root: Path,
    slug: str,
    root_for_rel: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    content_type = fetched.get("content_type")
    written: list[dict[str, Any]] = []
    if fetched.get("backend") == "api" or fetched.get("json_data") is not None:
        extracted = adapter.extract_content(record, fetched)
        markdown_path = artifact_root / slug / "content.md"
        write_artifact_text(markdown_path, extracted.get("markdown", ""))
        written.append({"kind": "markdown", "path": _artifact_relpath(markdown_path, root_for_rel), "content_type": "text/markdown"})
        text_path = artifact_root / slug / "content.txt"
        write_artifact_text(text_path, extracted.get("plain_text", ""))
        written.append({"kind": "plain_text", "path": _artifact_relpath(text_path, root_for_rel), "content_type": "text/plain"})
        metadata_path = artifact_root / slug / "metadata.json"
        write_artifact_json(metadata_path, extracted.get("metadata", {}))
        written.append({"kind": "metadata", "path": _artifact_relpath(metadata_path, root_for_rel), "content_type": "application/json"})
        return extracted, written
    if _is_html_content_type(content_type):
        extracted = adapter.extract_content(record, fetched)
        markdown_path = artifact_root / slug / "content.md"
        write_artifact_text(markdown_path, extracted.get("markdown", ""))
        written.append({"kind": "markdown", "path": _artifact_relpath(markdown_path, root_for_rel), "content_type": "text/markdown"})
        text_path = artifact_root / slug / "content.txt"
        write_artifact_text(text_path, extracted.get("plain_text", ""))
        written.append({"kind": "plain_text", "path": _artifact_relpath(text_path, root_for_rel), "content_type": "text/plain"})
        metadata_path = artifact_root / slug / "metadata.json"
        write_artifact_json(metadata_path, extracted.get("metadata", {}))
        written.append({"kind": "metadata", "path": _artifact_relpath(metadata_path, root_for_rel), "content_type": "application/json"})
        return extracted, written

    if _is_document_content_type(content_type):
        source_path = artifact_root / slug / "source.pdf"
        write_artifact_bytes(source_path, fetched["content_bytes"])
        extracted = extract_document_blocks(str(source_path), content_type=content_type)
        blocks_path = artifact_root / slug / "document_blocks.json"
        write_artifact_json(blocks_path, extracted)
        written.append({"kind": "document_blocks", "path": _artifact_relpath(blocks_path, root_for_rel), "content_type": "application/json"})
        return extracted, written

    return {"metadata": {}, "plain_text": "", "markdown": "", "document_blocks": []}, written


def _fetch_secondary_artifacts(
    *,
    record: dict[str, Any],
    discovered: dict[str, Any],
    artifact_root: Path,
    slug: str,
    root_for_rel: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    written: list[dict[str, Any]] = []
    extracted: dict[str, Any] = {}
    pdf_url = discovered.get("artifacts", {}).get("pdf_url")
    if pdf_url:
        pdf_fetch = unified_fetch(pdf_url, platform=record["platform"], backend="http")
        pdf_path = artifact_root / slug / "artifact.pdf"
        write_artifact_bytes(pdf_path, pdf_fetch["content_bytes"])
        written.append({"kind": "pdf", "path": _artifact_relpath(pdf_path, root_for_rel), "content_type": pdf_fetch.get("content_type")})
        pdf_extract = extract_document_blocks(str(pdf_path), content_type=pdf_fetch.get("content_type"))
        pdf_blocks_path = artifact_root / slug / "pdf_blocks.json"
        write_artifact_json(pdf_blocks_path, pdf_extract)
        written.append({"kind": "pdf_blocks", "path": _artifact_relpath(pdf_blocks_path, root_for_rel), "content_type": "application/json"})
        extracted = pdf_extract
    return written, extracted


def _fetch_with_attempts(
    *,
    adapter,
    record: dict[str, Any],
    discovered: dict[str, Any],
    storage_state_path: str | None,
    override_backend: str | None,
) -> dict[str, Any]:
    max_attempts = 1 if override_backend else 1 + len(getattr(adapter, "fallback_backends", ()))
    last_error: Exception | None = None

    for retry_count in range(max_attempts):
        backend = adapter.resolve_backend(record, override_backend, retry_count=retry_count)
        try:
            return adapter.fetch_record(record, discovered, backend, storage_state_path)
        except Exception as exc:  # pragma: no cover - exercised through caller error handling
            last_error = exc

    if last_error is None:  # pragma: no cover - defensive guard
        raise RuntimeError("fetch attempts exhausted without a captured error")
    raise last_error


def _crawl_records(
    config: CrawlerConfig,
    source_records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    artifact_root = _artifacts_root(config)
    session_store = SessionStore(config.output_dir / ".sessions")

    for index, record in enumerate(source_records, start=1):
        platform = record.get("platform")
        resource_type = record.get("resource_type")
        storage_state_path: str | None = None
        has_session = False
        try:
            adapter = get_platform_adapter(platform)
            discovered = build_url(record)
            slug = _record_slug(index, record, discovered)

            storage_state_path = _resolve_storage_state_path(config, platform, adapter, session_store)
            has_session = storage_state_path is not None

            if adapter.requires_auth and storage_state_path is None:
                errors.append(
                    _build_error(
                        platform=platform,
                        resource_type=resource_type,
                        stage="fetch",
                        error_code="AUTH_REQUIRED",
                        retryable=False,
                        next_action="provide cookies or storage state",
                        message=f"{platform} requires authenticated browser state",
                    )
                )
                continue

            fetched = _fetch_with_attempts(
                adapter=adapter,
                record=record,
                discovered=discovered,
                storage_state_path=storage_state_path,
                override_backend=config.backend,
            )
            artifacts = _persist_fetch_artifacts(
                artifact_root=artifact_root,
                slug=slug,
                fetched=fetched,
                root_for_rel=config.output_dir,
            )
            extracted, extraction_artifacts = _extract_primary_content(
                adapter=adapter,
                record=record,
                fetched=fetched,
                artifact_root=artifact_root,
                slug=slug,
                root_for_rel=config.output_dir,
            )
            artifacts.extend(extraction_artifacts)
            secondary_artifacts, supplemental = _fetch_secondary_artifacts(
                record=record,
                discovered=discovered,
                artifact_root=artifact_root,
                slug=slug,
                root_for_rel=config.output_dir,
            )
            artifacts.extend(secondary_artifacts)

            normalized = build_canonical_record(
                platform=platform,
                entity_type=resource_type,
                canonical_url=discovered["canonical_url"],
            )
            normalized["artifacts"] = artifacts
            normalized["discovery"] = discovered
            normalized["source"] = record
            normalized["metadata"] = extracted.get("metadata", {})
            normalized["plain_text"] = extracted.get("plain_text", "")
            normalized["markdown"] = extracted.get("markdown", "")
            normalized["document_blocks"] = extracted.get("document_blocks", []) or supplemental.get("document_blocks", [])
            normalized["structured"] = adapter.normalize_record(record, discovered, extracted, supplemental)
            normalized.update({key: value for key, value in normalized["structured"].items() if key not in normalized})
            results.append(normalized)
        except Exception as exc:  # pragma: no cover - runtime integration path
            auth_error = _classify_auth_error(
                platform=platform or "unknown",
                resource_type=resource_type,
                exception=exc,
                has_session=has_session,
            )
            if auth_error is not None:
                errors.append(auth_error)
                continue
            errors.append(
                _build_error(
                    platform=platform or "unknown",
                    resource_type=resource_type,
                    stage="crawl",
                    error_code=f"{str(platform or 'unknown').upper()}_CRAWL_FAILED",
                    retryable=False,
                    next_action="inspect artifacts and error details",
                    message=str(exc),
                )
            )
    return results, errors


def run_crawl(
    config: CrawlerConfig,
    records: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return _crawl_records(config, records or _read_jsonl(config.input_path))


def run_enrich(
    config: CrawlerConfig,
    records: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for record in records or _read_jsonl(config.input_path):
        try:
            adapter = get_platform_adapter(record["platform"])
            enriched = dict(record)
            enrichment_request = adapter.build_enrichment_request(enriched, config.field_groups)
            field_groups = enrichment_request["field_groups"]
            enriched["enrichment"] = route_enrichment(
                enriched,
                field_groups=field_groups,
                mode="full" if config.command.value == "run" else "enrich",
            )
            results.append(enriched)
        except Exception as exc:  # pragma: no cover
            errors.append(
                _build_error(
                    platform=record.get("platform", "unknown"),
                    resource_type=record.get("resource_type") or record.get("entity_type"),
                    stage="enrich",
                    error_code="ENRICHMENT_FAILED",
                    retryable=False,
                    next_action="use new pipeline for generative enrichment",
                    message=str(exc),
                )
            )
    return results, errors
