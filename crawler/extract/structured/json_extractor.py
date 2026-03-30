"""Structured field extraction from API JSON responses and HTML metadata."""
from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..models import StructuredFields


def _safe_get(data: dict, *keys: str, default: Any = None) -> Any:
    """Safely navigate nested dict keys."""
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
    return current


def _extract_og_meta(soup: BeautifulSoup, url: str) -> dict[str, Any]:
    """Extract OpenGraph and standard meta tags."""
    fields: dict[str, Any] = {}
    sources: dict[str, str] = {}

    # Title
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        fields["title"] = og_title["content"]
        sources["title"] = "html_meta:og:title"
    elif soup.title and soup.title.string:
        fields["title"] = soup.title.string.strip()
        sources["title"] = "html_meta:title"

    # Description
    og_desc = soup.find("meta", property="og:description")
    if og_desc and og_desc.get("content"):
        fields["description"] = og_desc["content"]
        sources["description"] = "html_meta:og:description"
    else:
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            fields["description"] = meta_desc["content"]
            sources["description"] = "html_meta:description"

    # Canonical URL
    canonical = soup.find("link", rel="canonical")
    if canonical and canonical.get("href"):
        fields["canonical_url"] = urljoin(url, canonical["href"])
        sources["canonical_url"] = "html_meta:canonical"

    # Type
    og_type = soup.find("meta", property="og:type")
    if og_type and og_type.get("content"):
        fields["og_type"] = og_type["content"]
        sources["og_type"] = "html_meta:og:type"

    # Image
    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.get("content"):
        fields["image_url"] = urljoin(url, og_image["content"])
        sources["image_url"] = "html_meta:og:image"

    return {"fields": fields, "sources": sources}


class JsonExtractor:
    """Extract structured fields from API JSON and HTML metadata."""

    def extract_document_from_json(
        self,
        *,
        json_data: dict[str, Any],
        platform: str,
        resource_type: str,
        canonical_url: str,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        extracted = self._extract_via_platform_adapter(
            json_data=json_data,
            platform=platform,
            resource_type=resource_type,
            canonical_url=canonical_url,
            content_type=content_type,
        )
        if extracted is None:
            structured = self.extract_from_json(
                json_data=json_data,
                platform=platform,
                resource_type=resource_type,
                canonical_url=canonical_url,
            )
            plain_text, markdown = self._render_generic_document(structured)
            return {
                "structured": structured,
                "plain_text": plain_text,
                "markdown": markdown,
            }

        raw_structured = extracted.get("structured")
        platform_fields = raw_structured if isinstance(raw_structured, dict) else {}
        if platform == "linkedin":
            linkedin_fields = platform_fields.get("linkedin")
            if isinstance(linkedin_fields, dict) and linkedin_fields:
                platform_fields = linkedin_fields
        metadata = extracted.get("metadata") if isinstance(extracted.get("metadata"), dict) else {}
        description = (
            metadata.get("description")
            or (platform_fields.get("description") if isinstance(platform_fields, dict) else None)
            or (platform_fields.get("headline") if isinstance(platform_fields, dict) else None)
            or extracted.get("plain_text")
            or self._description_from_metadata(metadata)
        )
        title = (
            metadata.get("title")
            or (platform_fields.get("title") if isinstance(platform_fields, dict) else None)
        )
        field_sources = {
            key: f"legacy_platform:{platform}"
            for key, value in (platform_fields.items() if isinstance(platform_fields, dict) else [])
            if value not in (None, "", [], {})
        }
        if title:
            field_sources.setdefault("title", f"legacy_platform:{platform}")
        if description:
            field_sources.setdefault("description", f"legacy_platform:{platform}")
        structured = StructuredFields(
            platform=platform,
            resource_type=resource_type,
            title=title,
            description=description,
            canonical_url=canonical_url,
            platform_fields=platform_fields if isinstance(platform_fields, dict) else {},
            field_sources=field_sources,
        )
        plain_text = extracted.get("plain_text") or ""
        markdown = extracted.get("markdown") or ""
        if not plain_text and (structured.title or structured.description or structured.platform_fields):
            plain_text, markdown = self._render_generic_document(structured)
        elif not markdown and plain_text:
            if structured.title:
                markdown = f"# {structured.title}\n\n{plain_text}".strip()
            else:
                markdown = plain_text
        return {
            "structured": structured,
            "plain_text": plain_text,
            "markdown": markdown,
        }

    def extract_from_json(
        self,
        json_data: dict[str, Any],
        platform: str,
        resource_type: str,
        canonical_url: str,
    ) -> StructuredFields:
        """Extract structured fields from an API JSON response."""
        fields: dict[str, Any] = {}
        sources: dict[str, str] = {}
        title = None
        description = None

        # LinkedIn Voyager API
        if platform == "linkedin":
            title, description, fields, sources = self._extract_linkedin_fields(json_data, resource_type)
        # Generic JSON: try common patterns
        else:
            title = (
                _safe_get(json_data, "title")
                or _safe_get(json_data, "name")
                or _safe_get(json_data, "data", "title")
            )
            if title:
                sources["title"] = "api_json"
            description = (
                _safe_get(json_data, "description")
                or _safe_get(json_data, "summary")
                or _safe_get(json_data, "data", "description")
            )
            if description:
                sources["description"] = "api_json"

        return StructuredFields(
            platform=platform,
            resource_type=resource_type,
            title=title,
            description=description,
            canonical_url=canonical_url,
            platform_fields=fields,
            field_sources=sources,
        )

    def extract_from_html(
        self,
        html: str,
        platform: str,
        resource_type: str,
        url: str,
    ) -> StructuredFields:
        """Extract structured fields from HTML meta tags."""
        soup = BeautifulSoup(html, "html.parser")
        meta = _extract_og_meta(soup, url)
        fields = meta["fields"]
        sources = meta["sources"]

        return StructuredFields(
            platform=platform,
            resource_type=resource_type,
            title=fields.pop("title", None),
            description=fields.pop("description", None),
            canonical_url=fields.pop("canonical_url", url),
            platform_fields=fields,
            field_sources=sources,
        )

    def _extract_linkedin_fields(
        self,
        json_data: dict[str, Any],
        resource_type: str,
    ) -> tuple[str | None, str | None, dict[str, Any], dict[str, str]]:
        fields: dict[str, Any] = {}
        sources: dict[str, str] = {}
        title = None
        description = None

        included = json_data.get("included", [])
        if not isinstance(included, list):
            included = []

        if resource_type == "profile":
            for item in included:
                if "Profile" in item.get("$type", ""):
                    first = item.get("firstName", "")
                    last = item.get("lastName", "")
                    title = f"{first} {last}".strip() or None
                    description = item.get("headline")
                    fields["public_identifier"] = item.get("publicIdentifier")
                    fields["entity_urn"] = item.get("entityUrn")
                    sources.update({k: "api_json:voyager" for k in ("title", "description", "public_identifier", "entity_urn")})
                    break

        elif resource_type == "company":
            for item in included:
                item_type = item.get("$type", "")
                if "Company" in item_type or "Organization" in item_type:
                    if item.get("name"):
                        title = item["name"]
                        description = item.get("description") or item.get("tagline")
                        fields["universal_name"] = item.get("universalName")
                        fields["staff_count"] = item.get("staffCount")
                        fields["industry"] = (item.get("industries") or [None])[0]
                        sources.update({k: "api_json:voyager" for k in ("title", "description", "universal_name", "staff_count", "industry")})
                        break

        elif resource_type == "job":
            for item in included:
                if "JobPosting" in item.get("$type", ""):
                    title = item.get("title")
                    desc_obj = item.get("description")
                    if isinstance(desc_obj, dict):
                        description = desc_obj.get("text")
                    elif isinstance(desc_obj, str):
                        description = desc_obj
                    fields["entity_urn"] = item.get("entityUrn")
                    sources.update({k: "api_json:voyager" for k in ("title", "description", "entity_urn")})
                    break

        return title, description, fields, sources

    def _extract_via_platform_adapter(
        self,
        *,
        json_data: dict[str, Any],
        platform: str,
        resource_type: str,
        canonical_url: str,
        content_type: str | None,
    ) -> dict[str, Any] | None:
        fetched = {
            "url": canonical_url,
            "content_type": content_type or "application/json",
            "json_data": json_data,
        }
        record = {
            "platform": platform,
            "resource_type": resource_type,
        }
        if platform == "wikipedia":
            from crawler.platforms.wikipedia import _extract_wikipedia

            return _extract_wikipedia(record, fetched)
        if platform == "base":
            from crawler.platforms.base_chain import _extract_base

            return _extract_base(record, fetched)
        if platform == "linkedin":
            from crawler.platforms.linkedin import _extract_linkedin

            return _extract_linkedin(record, fetched)
        return None

    def _render_generic_document(self, structured: StructuredFields) -> tuple[str, str]:
        text_parts: list[str] = []
        if structured.title:
            text_parts.append(structured.title)
        if structured.description:
            text_parts.append(structured.description)
        for key, value in structured.platform_fields.items():
            if value is not None and value != "" and not isinstance(value, (dict, list)):
                text_parts.append(f"{key}: {value}")

        plain_text = "\n\n".join(text_parts)
        markdown_parts: list[str] = []
        if structured.title:
            markdown_parts.append(f"# {structured.title}")
        if structured.description:
            markdown_parts.append(str(structured.description))
        for key, value in structured.platform_fields.items():
            if value is not None and value != "" and not isinstance(value, (dict, list)):
                markdown_parts.append(f"**{key}**: {value}")
        markdown = "\n\n".join(markdown_parts)
        return plain_text, markdown

    def _description_from_metadata(self, metadata: dict[str, Any]) -> str | None:
        pageprops = metadata.get("pageprops")
        if isinstance(pageprops, dict):
            shortdesc = pageprops.get("wikibase-shortdesc")
            if isinstance(shortdesc, str) and shortdesc.strip():
                return shortdesc.strip()
        return None
