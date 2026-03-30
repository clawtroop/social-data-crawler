from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from crawler.contracts import CrawlCommand, CrawlerConfig
from crawler.io import read_json_file, read_jsonl_file


def run_command(config: CrawlerConfig) -> tuple[list[dict], list[dict]]:
    """Run the crawler pipeline.

    By default uses the new 3-layer pipeline (FetchEngine → ExtractPipeline → EnrichPipeline).
    Pass --use-legacy-pipeline to fall back to the old dispatcher-based implementation.
    """
    if config.command is CrawlCommand.DISCOVER_MAP:
        return _run_discovery_map_pipeline(config)
    if config.command is CrawlCommand.DISCOVER_CRAWL:
        return _run_discovery_crawl_pipeline(config)
    if config.use_legacy_pipeline:
        return _run_legacy_pipeline(config)
    return _run_new_pipeline(config)


def _run_discovery_map_pipeline(config: CrawlerConfig) -> tuple[list[dict], list[dict]]:
    """Run the discovery map pipeline."""
    return asyncio.run(_run_discovery_map_pipeline_async(config))


async def _run_discovery_map_pipeline_async(config: CrawlerConfig) -> tuple[list[dict], list[dict]]:
    """Async implementation of discovery map pipeline."""
    from crawler.discovery.adapters.registry import get_discovery_adapter
    from crawler.discovery.contracts import MapOptions
    from crawler.fetch.engine import FetchEngine

    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    input_records = _read_jsonl(config.input_path)
    options = MapOptions(
        limit=config.max_pages,
        sitemap_mode=config.sitemap_mode,
    )

    session_root = config.output_dir / ".sessions"
    session_root.mkdir(parents=True, exist_ok=True)

    async with FetchEngine(session_root) as fetch_engine:
        for input_record in input_records:
            try:
                adapter = get_discovery_adapter(str(input_record.get("platform") or "generic"))
                seeds = adapter.build_seed_records(input_record)

                for seed in seeds:
                    context = await _build_discovery_map_context(
                        adapter=adapter,
                        seed=seed,
                        input_record=input_record,
                        options=options,
                        fetch_engine=fetch_engine,
                    )
                    map_result = await adapter.map(seed, context)

                    for candidate in map_result.accepted:
                        records.append({
                            "platform": candidate.platform,
                            "resource_type": candidate.resource_type,
                            "canonical_url": candidate.canonical_url,
                            "discovery_mode": candidate.discovery_mode.value,
                            "seed_url": candidate.seed_url,
                            "hop_depth": candidate.hop_depth,
                            "score": candidate.score,
                            "metadata": candidate.metadata,
                        })

            except Exception as exc:
                errors.append({
                    "platform": str(input_record.get("platform") or "generic"),
                    "resource_type": str(input_record.get("resource_type") or "page"),
                    "stage": "discovery_map",
                    "status": "failed",
                    "error_code": "DISCOVERY_MAP_FAILED",
                    "retryable": False,
                    "message": str(exc),
                })

    return records, errors


def _run_discovery_crawl_pipeline(config: CrawlerConfig) -> tuple[list[dict], list[dict]]:
    """Run the discovery crawl pipeline."""
    return asyncio.run(_run_discovery_crawl_pipeline_async(config))


async def _run_discovery_crawl_pipeline_async(config: CrawlerConfig) -> tuple[list[dict], list[dict]]:
    """Async implementation of discovery crawl pipeline."""
    from crawler.discovery.adapters.registry import get_discovery_adapter
    from crawler.discovery.contracts import CrawlOptions, DiscoveryCandidate, DiscoveryMode
    from crawler.discovery.runner import run_discover_crawl
    from crawler.fetch.engine import FetchEngine

    errors: list[dict[str, Any]] = []

    input_records = _read_jsonl(config.input_path)
    options = CrawlOptions(
        max_depth=config.max_depth,
        max_pages=config.max_pages,
        sitemap_mode=config.sitemap_mode,
    )

    # Build candidates from input
    seeds: list[DiscoveryCandidate] = []
    for input_record in input_records:
        url = input_record.get("url") or input_record.get("canonical_url")
        if not url:
            continue
        seeds.append(DiscoveryCandidate(
            platform=input_record.get("platform", "generic"),
            resource_type=input_record.get("resource_type", "page"),
            canonical_url=url,
            seed_url=url,
            fields={},
            discovery_mode=DiscoveryMode.DIRECT_INPUT,
            score=1.0,
            score_breakdown={"direct_input": 1.0},
            hop_depth=0,
            parent_url=None,
            metadata={},
        ))

    session_root = config.output_dir / ".sessions"
    session_root.mkdir(parents=True, exist_ok=True)

    async with FetchEngine(session_root) as fetch_engine:
        async def fetch_fn(target: DiscoveryCandidate | str) -> dict[str, Any]:
            if isinstance(target, DiscoveryCandidate):
                url = target.canonical_url or ""
                platform = target.platform
                resource_type = target.resource_type
            else:
                url = str(target)
                platform = "generic"
                resource_type = "page"
            result = await fetch_engine.fetch(
                url=url,
                platform=platform,
                resource_type=resource_type,
                requires_auth=False,
            )
            return result.to_legacy_dict()

        try:
            records = await run_discover_crawl(
                seeds=seeds,
                fetch_fn=fetch_fn,
                options=options,
                adapter_resolver=get_discovery_adapter,
            )
        except Exception as exc:
            errors.append({
                "platform": "generic",
                "resource_type": "page",
                "stage": "discovery_crawl",
                "status": "failed",
                "error_code": "DISCOVERY_CRAWL_FAILED",
                "retryable": False,
                "message": str(exc),
            })
            records = []

    return records, errors


def _run_legacy_pipeline(config: CrawlerConfig) -> tuple[list[dict], list[dict]]:
    """Run the legacy dispatcher-based pipeline (deprecated)."""
    from .dispatcher import run_crawl, run_enrich

    if config.command is CrawlCommand.CRAWL:
        return run_crawl(config)
    if config.command is CrawlCommand.ENRICH:
        return run_enrich(config)

    crawled_records, crawl_errors = run_crawl(config)
    enriched_records, enrich_errors = run_enrich(config, records=crawled_records)
    return enriched_records, [*crawl_errors, *enrich_errors]


def _run_new_pipeline(config: CrawlerConfig) -> tuple[list[dict], list[dict]]:
    """Run the new 3-layer pipeline: FetchEngine -> ExtractPipeline -> EnrichPipeline."""
    return asyncio.run(_run_new_pipeline_async(config))


async def _run_new_pipeline_async(config: CrawlerConfig) -> tuple[list[dict], list[dict]]:
    """Async implementation of the new pipeline."""
    from crawler.extract.pipeline import ExtractPipeline
    from crawler.enrich.pipeline import EnrichPipeline
    from crawler.fetch.engine import FetchEngine
    from crawler.fetch.session_store import SessionStore
    from crawler.discovery.url_builder import build_seed_records
    from crawler.platforms.registry import get_platform_adapter
    from crawler.normalize.canonical import build_canonical_record
    from crawler.output.artifact_writer import write_artifact_bytes, write_artifact_json, write_artifact_text
    from crawler.schema_runtime.model_config import load_model_config

    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    # Read input records
    records = _read_jsonl(config.input_path)

    model_config = load_model_config(config.model_config_path)
    enrich_pipeline = EnrichPipeline(
        enrich_llm_schema_path=config.enrich_llm_schema_path,
        model_config=model_config,
    )
    if config.command is CrawlCommand.ENRICH:
        return await _run_new_enrich_only_pipeline(records, config, enrich_pipeline)

    # Initialize pipelines
    session_root = config.output_dir / ".sessions"
    session_root.mkdir(parents=True, exist_ok=True)
    artifact_root = config.artifacts_dir or (config.output_dir / "artifacts")
    session_store = SessionStore(session_root)
    extract_pipeline = ExtractPipeline(
        max_chunk_tokens=config.max_chunk_tokens,
        min_chunk_tokens=100,
        overlap_tokens=config.chunk_overlap,
        css_schema_path=config.css_schema_path,
        extract_llm_schema_path=config.extract_llm_schema_path,
        model_config=model_config,
    )

    async with FetchEngine(session_root) as fetch_engine:
        for idx, record in enumerate(records, start=1):
            platform = record.get("platform", "unknown")
            resource_type = record.get("resource_type", "unknown")

            try:
                # Step 1: URL Discovery
                adapter = get_platform_adapter(platform)
                discovered = _discovered_from_seed(build_seed_records(record)[0])
                url = discovered["canonical_url"]
                slug = _make_slug(idx, url)

                # Step 2: Fetch (using new FetchEngine)
                requires_auth = getattr(adapter, "requires_auth", False)
                storage_state_path = _resolve_storage_state_path(
                    config=config,
                    platform=platform,
                    requires_auth=requires_auth,
                    session_store=session_store,
                )
                if requires_auth and storage_state_path is None:
                    errors.append(_build_auth_required_error(platform=platform, resource_type=resource_type))
                    continue

                # For API backends, we need the adapter's API fetcher
                initial_backend = adapter.resolve_backend(record, config.backend, retry_count=0)
                if initial_backend == "api":
                    raw_result = await fetch_engine.fetch(
                        url=url,
                        platform=platform,
                        resource_type=resource_type,
                        requires_auth=requires_auth,
                        override_backend=config.backend,
                        preferred_backend=initial_backend if config.backend is None else None,
                        fallback_chain=list(getattr(adapter, "fallback_backends", ())),
                        api_fetcher=lambda _url, **_kwargs: adapter.fetch_record(
                            record,
                            discovered,
                            "api",
                            storage_state_path,
                        ),
                    )
                    fetch_result = raw_result.to_legacy_dict()
                else:
                    raw_result = await fetch_engine.fetch(
                        url=url,
                        platform=platform,
                        resource_type=resource_type,
                        requires_auth=requires_auth,
                        override_backend=config.backend,
                    )
                    fetch_result = raw_result.to_legacy_dict()

                # Persist fetch artifacts
                fetch_artifacts = _persist_fetch_artifacts_new(
                    artifact_root=artifact_root,
                    slug=slug,
                    fetched=fetch_result,
                    root_for_rel=config.output_dir,
                )

                # Step 3: Extract (using new ExtractPipeline)
                extracted_doc = extract_pipeline.extract(fetch_result, platform, resource_type)
                legacy_extracted = _build_legacy_compatible_extracted(
                    adapter=adapter,
                    record=record,
                    discovered=discovered,
                    fetch_result=fetch_result,
                    extracted_doc=extracted_doc,
                )

                # Persist extraction artifacts
                extraction_artifacts = _persist_extraction_artifacts(
                    artifact_root=artifact_root,
                    slug=slug,
                    extracted=extracted_doc,
                    root_for_rel=config.output_dir,
                )

                # Step 4: Enrich (if field_groups specified or running full pipeline)
                field_groups = list(config.field_groups) if config.field_groups else ["summaries"]
                if config.command in (CrawlCommand.RUN, CrawlCommand.ENRICH):
                    # Prepare document for enrichment
                    enrich_input = {
                        "doc_id": extracted_doc.doc_id,
                        "canonical_url": url,
                        "platform": platform,
                        "resource_type": resource_type,
                        "plain_text": extracted_doc.full_text,
                        "markdown": extracted_doc.full_markdown,
                        "structured": extracted_doc.structured.platform_fields,
                        "title": extracted_doc.structured.title,
                        "description": extracted_doc.structured.description,
                    }
                    enriched = await enrich_pipeline.enrich(enrich_input, field_groups)
                    enrichment_result = enriched.to_dict()
                else:
                    enrichment_result = None

                # Build final record
                normalized = build_canonical_record(
                    platform=platform,
                    entity_type=resource_type,
                    canonical_url=url,
                )
                normalized["artifacts"] = fetch_artifacts + extraction_artifacts
                normalized["discovery"] = discovered
                normalized["source"] = record
                normalized["metadata"] = legacy_extracted.get("metadata", {})
                normalized["plain_text"] = extracted_doc.full_text
                normalized["markdown"] = extracted_doc.full_markdown
                normalized["structured"] = extracted_doc.structured.platform_fields
                normalized["document_blocks"] = legacy_extracted.get("document_blocks", [])
                normalized["chunks"] = [chunk.to_dict() for chunk in extracted_doc.chunks]
                normalized["extraction_quality"] = {
                    "content_ratio": extracted_doc.quality.content_ratio,
                    "noise_removed": extracted_doc.quality.noise_removed,
                    "chunking_strategy": extracted_doc.quality.chunking_strategy,
                    "total_chunks": extracted_doc.total_chunks,
                }
                normalized_structured = adapter.normalize_record(record, discovered, legacy_extracted, {})
                if isinstance(normalized_structured, dict):
                    normalized.update({key: value for key, value in normalized_structured.items() if key not in normalized})
                if enrichment_result:
                    normalized["enrichment"] = enrichment_result

                results.append(normalized)

            except Exception as exc:
                errors.append({
                    "platform": platform,
                    "resource_type": resource_type,
                    "stage": "new_pipeline",
                    "status": "failed",
                    "error_code": f"{platform.upper()}_PIPELINE_FAILED",
                    "retryable": False,
                    "next_action": "inspect error and retry",
                    "message": str(exc),
                })

    return results, errors


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return read_jsonl_file(path)


async def _build_discovery_map_context(
    *,
    adapter,
    seed,
    input_record: dict[str, Any],
    options,
    fetch_engine,
) -> dict[str, Any]:
    context: dict[str, Any] = {
        "options": options,
        "query": input_record.get("query", ""),
        "search_type": input_record.get("search_type", ""),
    }
    for key in ("page_links", "search_urls", "search_candidates"):
        if key in input_record:
            context[key] = input_record[key]

    if any(key in context for key in ("page_links", "search_urls", "search_candidates")):
        return context

    raw_result = await fetch_engine.fetch(
        url=seed.canonical_url,
        platform=seed.platform,
        resource_type=seed.resource_type,
        requires_auth=False,
    )
    fetched = raw_result.to_legacy_dict()
    context["html"] = fetched.get("html", "")
    context["fetched"] = fetched
    return context


def _discovered_from_seed(seed) -> dict[str, Any]:
    return {
        "platform": seed.platform,
        "resource_type": seed.resource_type,
        "canonical_url": seed.canonical_url,
        "artifacts": dict(seed.metadata.get("artifacts", {})),
        "fields": dict(seed.identity),
    }


def _resolve_storage_state_path(
    *,
    config: CrawlerConfig,
    platform: str,
    requires_auth: bool,
    session_store,
) -> str | None:
    if not requires_auth:
        return None
    if config.cookies_path is not None:
        return str(session_store.import_cookies(platform, config.cookies_path))
    if session_store.load(platform) is not None:
        return str(session_store.root / f"{platform}.json")
    if config.auto_login and platform == "linkedin":
        return _export_linkedin_session_via_auto_browser(session_store)
    return None


def _build_auth_required_error(*, platform: str, resource_type: str | None) -> dict[str, Any]:
    return {
        "platform": platform,
        "resource_type": resource_type,
        "stage": "fetch",
        "status": "failed",
        "error_code": "AUTH_REQUIRED",
        "retryable": False,
        "next_action": "provide cookies or storage state",
        "message": f"{platform} requires authenticated browser state",
    }


def _export_linkedin_session_via_auto_browser(session_store) -> str:
    from crawler.integrations import LinkedInAutoBrowserBridge, get_default_auto_browser_script

    bridge = LinkedInAutoBrowserBridge(
        script_path=get_default_auto_browser_script(),
        workdir=Path(os.environ.get("WORKDIR", Path.home() / ".openclaw" / "vrd-data")),
    )
    exported_path = bridge.ensure_exported_session(session_store.root.parent)
    return str(session_store.import_cookies("linkedin", exported_path))


def _build_doc_id(canonical_url: str, platform: str) -> str:
    payload = f"{platform}:{canonical_url}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _build_enrich_input_from_record(record: dict[str, Any]) -> dict[str, Any]:
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    return {
        "doc_id": record.get("doc_id") or _build_doc_id(record["canonical_url"], record.get("platform", "unknown")),
        "canonical_url": record["canonical_url"],
        "platform": record.get("platform", "unknown"),
        "resource_type": record.get("resource_type") or record.get("entity_type") or "unknown",
        "plain_text": record.get("plain_text", ""),
        "markdown": record.get("markdown", ""),
        "structured": record.get("structured", {}),
        "title": metadata.get("title"),
        "description": metadata.get("description"),
    }


async def _run_new_enrich_only_pipeline(
    records: list[dict[str, Any]],
    config: CrawlerConfig,
    enrich_pipeline,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    field_groups = list(config.field_groups) if config.field_groups else ["summaries"]

    for record in records:
        try:
            enrich_input = _build_enrich_input_from_record(record)
            enriched = dict(record)
            enriched["enrichment"] = (await enrich_pipeline.enrich(enrich_input, field_groups)).to_dict()
            results.append(enriched)
        except Exception as exc:
            errors.append({
                "platform": record.get("platform", "unknown"),
                "resource_type": record.get("resource_type") or record.get("entity_type"),
                "stage": "enrich",
                "status": "failed",
                "error_code": "ENRICHMENT_FAILED",
                "retryable": False,
                "next_action": "inspect record and model config",
                "message": str(exc),
            })

    return results, errors


def _make_slug(index: int, url: str) -> str:
    tail = url.rstrip("/").split("/")[-1] or f"record-{index}"
    slug = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in tail)
    return slug or f"record-{index}"


def _artifact_relpath(path: Path, root: Path) -> str:
    return path.relative_to(root.parent).as_posix()


def _persist_fetch_artifacts_new(
    *,
    artifact_root: Path,
    slug: str,
    fetched: dict[str, Any],
    root_for_rel: Path,
) -> list[dict[str, Any]]:
    """Persist fetch artifacts (similar to dispatcher but simpler)."""
    from crawler.output.artifact_writer import write_artifact_bytes, write_artifact_json, write_artifact_text

    written: list[dict[str, Any]] = []
    content_type = fetched.get("content_type", "")
    is_api_payload = fetched.get("backend") == "api" or fetched.get("json_data") is not None

    if is_api_payload:
        if fetched.get("json_data") is not None:
            json_path = artifact_root / slug / "api_response.json"
            write_artifact_json(json_path, fetched["json_data"])
            written.append({
                "kind": "api_response",
                "path": _artifact_relpath(json_path, root_for_rel),
                "content_type": "application/json",
            })
    else:
        # HTML content
        if fetched.get("html"):
            html_path = artifact_root / slug / "page.html"
            write_artifact_text(html_path, fetched["html"])
            written.append({
                "kind": "html",
                "path": _artifact_relpath(html_path, root_for_rel),
                "content_type": content_type or "text/html",
            })

    # Screenshot
    if fetched.get("screenshot"):
        screenshot_path = artifact_root / slug / "screenshot.png"
        write_artifact_bytes(screenshot_path, fetched["screenshot"])
        written.append({
            "kind": "screenshot",
            "path": _artifact_relpath(screenshot_path, root_for_rel),
            "content_type": "image/png",
        })

    # Fetch metadata
    metadata_path = artifact_root / slug / "fetch.json"
    write_artifact_json(metadata_path, {
        "url": fetched.get("url"),
        "final_url": fetched.get("final_url"),
        "status_code": fetched.get("status_code"),
        "backend": fetched.get("backend"),
        "content_type": content_type,
        "timing": fetched.get("timing"),
    })
    written.append({
        "kind": "fetch",
        "path": _artifact_relpath(metadata_path, root_for_rel),
        "content_type": "application/json",
    })

    return written


def _build_legacy_compatible_extracted(
    *,
    adapter,
    record: dict[str, Any],
    discovered: dict[str, Any],
    fetch_result: dict[str, Any],
    extracted_doc: Any,
) -> dict[str, Any]:
    if getattr(adapter, "default_backend", None) == "api":
        extracted = adapter.extract_content(record, fetch_result)
        if isinstance(extracted, dict):
            metadata = extracted.get("metadata") if isinstance(extracted.get("metadata"), dict) else {}
            metadata.setdefault("title", extracted_doc.structured.title)
            metadata.setdefault("description", extracted_doc.structured.description)
            extracted["metadata"] = metadata
            extracted.setdefault("plain_text", extracted_doc.full_text)
            extracted.setdefault("markdown", extracted_doc.full_markdown)
            extracted.setdefault("structured", extracted_doc.structured.platform_fields)
            extracted.setdefault("document_blocks", [])
            return extracted

    metadata = {
        "title": extracted_doc.structured.title,
        "description": extracted_doc.structured.description,
        "content_type": fetch_result.get("content_type"),
        "source_url": extracted_doc.source_url,
    }
    return {
        "metadata": metadata,
        "plain_text": extracted_doc.full_text,
        "markdown": extracted_doc.full_markdown,
        "structured": extracted_doc.structured.platform_fields,
        "document_blocks": [],
    }


def _persist_extraction_artifacts(
    *,
    artifact_root: Path,
    slug: str,
    extracted: Any,  # ExtractedDocument
    root_for_rel: Path,
) -> list[dict[str, Any]]:
    """Persist extraction artifacts."""
    from crawler.output.artifact_writer import write_artifact_json, write_artifact_text

    written: list[dict[str, Any]] = []

    # Markdown content
    markdown_path = artifact_root / slug / "content.md"
    write_artifact_text(markdown_path, extracted.full_markdown)
    written.append({
        "kind": "markdown",
        "path": _artifact_relpath(markdown_path, root_for_rel),
        "content_type": "text/markdown",
    })

    # Plain text
    text_path = artifact_root / slug / "content.txt"
    write_artifact_text(text_path, extracted.full_text)
    written.append({
        "kind": "plain_text",
        "path": _artifact_relpath(text_path, root_for_rel),
        "content_type": "text/plain",
    })

    if getattr(extracted, "cleaned_html", ""):
        cleaned_html_path = artifact_root / slug / "cleaned.html"
        write_artifact_text(cleaned_html_path, extracted.cleaned_html)
        written.append({
            "kind": "cleaned_html",
            "path": _artifact_relpath(cleaned_html_path, root_for_rel),
            "content_type": "text/html",
        })

    # Chunks as JSON
    chunks_path = artifact_root / slug / "chunks.json"
    write_artifact_json(chunks_path, [c.to_dict() for c in extracted.chunks])
    written.append({
        "kind": "chunks",
        "path": _artifact_relpath(chunks_path, root_for_rel),
        "content_type": "application/json",
    })

    # Structured fields
    structured_path = artifact_root / slug / "structured.json"
    write_artifact_json(structured_path, {
        "title": extracted.structured.title,
        "description": extracted.structured.description,
        "canonical_url": extracted.structured.canonical_url,
        "platform_fields": extracted.structured.platform_fields,
        "field_sources": extracted.structured.field_sources,
    })
    written.append({
        "kind": "structured",
        "path": _artifact_relpath(structured_path, root_for_rel),
        "content_type": "application/json",
    })

    return written
