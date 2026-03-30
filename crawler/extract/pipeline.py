"""Extract Pipeline — main entry point for content extraction.

Routes fetch results through cleaning, main content extraction, chunking,
and structured field extraction to produce LLM-ready ExtractedDocument output.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from markdownify import markdownify as to_markdown

from .chunking.hybrid_chunker import HybridChunker, _estimate_tokens
from .content_cleaner import ContentCleaner
from .fit_content import FitContentReducer
from .main_content import MainContentExtractor
from .models import (
    ContentChunk,
    ContentSection,
    ExtractedDocument,
    ExtractionQuality,
    MainContent,
    StructuredFields,
)
from .structured.css_extractor import CssExtractionStrategy
from .structured.json_extractor import JsonExtractor
from .structured.llm_schema_extractor import LLMSchemaExtractor


def _generate_doc_id(url: str, platform: str) -> str:
    """Generate a deterministic doc_id from URL and platform."""
    hash_input = f"{platform}:{url}".encode("utf-8")
    return hashlib.sha256(hash_input).hexdigest()[:16]


class ExtractPipeline:
    def __init__(
        self,
        max_chunk_tokens: int = 512,
        min_chunk_tokens: int = 100,
        overlap_tokens: int = 50,
        css_schema_path: Path | None = None,
        extract_llm_schema_path: Path | None = None,
        model_config: dict[str, Any] | None = None,
    ):
        self.cleaner = ContentCleaner()
        self.main_extractor = MainContentExtractor()
        self.reducer = FitContentReducer()
        self.chunker = HybridChunker(
            max_chunk_tokens=max_chunk_tokens,
            min_chunk_tokens=min_chunk_tokens,
            overlap_tokens=overlap_tokens,
        )
        self.json_extractor = JsonExtractor()
        self.css_extractor = CssExtractionStrategy(css_schema_path) if css_schema_path is not None else None
        self.llm_schema_extractor = LLMSchemaExtractor(extract_llm_schema_path, model_config or {}) if extract_llm_schema_path is not None else None

    def extract(
        self,
        fetch_result: dict[str, Any],
        platform: str,
        resource_type: str,
    ) -> ExtractedDocument:
        """Extract structured content from a fetch result.

        Handles two branches:
        - API JSON: structured extraction + text generation + chunking
        - HTML: cleaning -> main content identification -> chunking -> structured extraction
        """
        url = fetch_result.get("url", "")
        doc_id = _generate_doc_id(url, platform)
        json_data = fetch_result.get("json_data")

        if json_data is not None:
            return self._extract_from_json(
                json_data=json_data,
                fetch_result=fetch_result,
                platform=platform,
                resource_type=resource_type,
                url=url,
                doc_id=doc_id,
            )

        return self._extract_from_html(
            fetch_result=fetch_result,
            platform=platform,
            resource_type=resource_type,
            url=url,
            doc_id=doc_id,
        )

    def _extract_from_json(
        self,
        *,
        json_data: dict[str, Any],
        fetch_result: dict[str, Any],
        platform: str,
        resource_type: str,
        url: str,
        doc_id: str,
    ) -> ExtractedDocument:
        """Branch 1: API JSON -> structured extraction + text generation + chunking."""
        extracted = self.json_extractor.extract_document_from_json(
            json_data=json_data,
            platform=platform,
            resource_type=resource_type,
            canonical_url=url,
            content_type=fetch_result.get("content_type"),
        )
        structured = extracted["structured"]
        full_text = extracted["plain_text"]
        full_markdown = extracted["markdown"]

        # Create sections from structured data for chunking
        sections: list[ContentSection] = []
        if full_text or full_markdown or structured.title or structured.description:
            sections.append(ContentSection(
                heading_text=structured.title,
                heading_level=1,
                section_path=[structured.title or "Main"],
                html="",
                text=full_text,
                markdown=full_markdown,
                char_offset_start=0,
                char_offset_end=len(full_text),
            ))

        main_content = MainContent(
            html="",
            text=full_text,
            markdown=full_markdown,
            sections=sections,
            selector_used="api_json",
        )
        reduced_content = self.reducer.reduce(main_content)

        chunks = self.chunker.chunk(reduced_content, doc_id=doc_id)

        # Quality metrics for JSON extraction
        raw_size = len(json.dumps(json_data, default=str))
        content_size = len(reduced_content.text)
        quality = ExtractionQuality(
            content_ratio=content_size / max(raw_size, 1),
            noise_removed=0,
            chunking_strategy="json_structured",
        )

        return ExtractedDocument(
            doc_id=doc_id,
            source_url=url,
            platform=platform,
            resource_type=resource_type,
            extracted_at=datetime.now(timezone.utc),
            chunks=chunks,
            total_chunks=len(chunks),
            full_text=reduced_content.text,
            full_markdown=reduced_content.markdown,
            structured=structured,
            quality=quality,
            cleaned_html="",
        )

    def _extract_from_html(
        self,
        *,
        fetch_result: dict[str, Any],
        platform: str,
        resource_type: str,
        url: str,
        doc_id: str,
    ) -> ExtractedDocument:
        """Branch 2: HTML -> clean -> main content -> chunk -> structured."""
        html = (
            fetch_result.get("text")
            or fetch_result.get("html")
            or (fetch_result.get("content_bytes", b"") or b"").decode("utf-8", "ignore")
        )
        original_size = len(html)

        # Step 1: Clean HTML
        cleaned = self.cleaner.clean(html, platform)

        # Step 2: Identify main content
        soup = BeautifulSoup(cleaned.html, "html.parser")
        main_content = self.main_extractor.extract(soup, platform, resource_type)
        reduced_content = self.reducer.reduce(main_content)

        # Step 3: Chunk content
        chunks = self.chunker.chunk(reduced_content, doc_id=doc_id)

        # Step 4: Extract structured fields from HTML meta
        structured = self.json_extractor.extract_from_html(
            html=html,  # Use original HTML for meta extraction
            platform=platform,
            resource_type=resource_type,
            url=url,
        )
        if self.css_extractor is not None:
            css_structured = self.css_extractor.extract(
                html=cleaned.html,
                canonical_url=url,
                platform=platform,
                resource_type=resource_type,
            )
            structured = self._merge_structured_fields(structured, css_structured)
        if self.llm_schema_extractor is not None:
            llm_structured, llm_error = self.llm_schema_extractor.extract(
                plain_text=reduced_content.text,
                markdown=reduced_content.markdown,
                cleaned_html=reduced_content.html,
                metadata={"title": structured.title, "description": structured.description},
                platform=platform,
                resource_type=resource_type,
                canonical_url=url,
            )
            if llm_structured is not None:
                structured = self._merge_structured_fields(structured, llm_structured)
            elif llm_error is not None:
                structured.platform_fields.setdefault("_schema_errors", []).append(llm_error)

        # Quality metrics
        content_size = len(reduced_content.text)
        quality = ExtractionQuality(
            content_ratio=content_size / max(original_size, 1),
            noise_removed=cleaned.noise_removed,
            chunking_strategy=f"hybrid:{main_content.selector_used}",
        )

        return ExtractedDocument(
            doc_id=doc_id,
            source_url=url,
            platform=platform,
            resource_type=resource_type,
            extracted_at=datetime.now(timezone.utc),
            chunks=chunks,
            total_chunks=len(chunks),
            full_text=reduced_content.text,
            full_markdown=reduced_content.markdown,
            structured=structured,
            quality=quality,
            cleaned_html=reduced_content.html,
        )

    def _merge_structured_fields(
        self,
        base: StructuredFields,
        override: StructuredFields,
    ) -> StructuredFields:
        merged_fields = dict(base.platform_fields)
        merged_fields.update(override.platform_fields)
        merged_sources = dict(base.field_sources)
        merged_sources.update(override.field_sources)
        return StructuredFields(
            platform=base.platform,
            resource_type=base.resource_type,
            title=override.title or base.title,
            description=override.description or base.description,
            canonical_url=base.canonical_url,
            platform_fields=merged_fields,
            field_sources=merged_sources,
        )

    def extract_to_legacy(
        self,
        fetch_result: dict[str, Any],
        platform: str,
        resource_type: str,
    ) -> dict[str, Any]:
        """Extract and return in the legacy dict format for backward compatibility
        with PlatformAdapter.extract_content interface."""
        doc = self.extract(fetch_result, platform, resource_type)
        return {
            "metadata": {
                "title": doc.structured.title,
                "description": doc.structured.description,
                "content_type": fetch_result.get("content_type"),
                "source_url": doc.source_url,
            },
            "markdown": doc.full_markdown,
            "plain_text": doc.full_text,
            "document_blocks": [],
            "structured": doc.structured.platform_fields,
            "extractor": "extract_pipeline",
            "extract_document": doc.to_dict(),
        }
