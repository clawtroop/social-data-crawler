"""Structured field extraction from API JSON responses and HTML metadata."""
from __future__ import annotations

import json
import re
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
    is_amazon = "amazon." in url.lower()

    # Title
    og_title = soup.find("meta", property="og:title")
    og_title_content = og_title.get("content").strip() if og_title and og_title.get("content") else ""
    if og_title_content and not (is_amazon and og_title_content.lower() == "amazon"):
        fields["title"] = og_title_content
        sources["title"] = "html_meta:og:title"
    elif soup.title and soup.title.string:
        fields["title"] = soup.title.string.strip()
        sources["title"] = "html_meta:title"

    # Description
    og_desc = soup.find("meta", property="og:description")
    og_desc_content = og_desc.get("content").strip() if og_desc and og_desc.get("content") else ""
    if og_desc_content and not (is_amazon and og_desc_content.lower() == "amazon"):
        fields["description"] = og_desc_content
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

        if platform == "amazon":
            if resource_type == "product":
                amazon = self._extract_amazon_product_html(soup, url)
                fields.update(amazon["fields"])
                sources.update(amazon["sources"])
            elif resource_type == "seller":
                amazon = self._extract_amazon_seller_html(soup, url)
                fields.update(amazon["fields"])
                sources.update(amazon["sources"])
        elif platform == "base":
            base = self._extract_base_html(soup, url, resource_type)
            fields.update(base["fields"])
            sources.update(base["sources"])

        return StructuredFields(
            platform=platform,
            resource_type=resource_type,
            title=fields.pop("title", None),
            description=fields.pop("description", None),
            canonical_url=fields.pop("canonical_url", url),
            platform_fields=fields,
            field_sources=sources,
        )

    def _extract_amazon_product_html(
        self,
        soup: BeautifulSoup,
        canonical_url: str,
    ) -> dict[str, dict[str, Any]]:
        fields: dict[str, Any] = {}
        sources: dict[str, str] = {}

        def set_field(name: str, value: Any, source: str) -> None:
            if value in (None, "", [], {}):
                return
            fields[name] = value
            sources[name] = source

        def set_if_missing(name: str, value: Any, source: str) -> None:
            if name in fields:
                return
            set_field(name, value, source)

        title_node = soup.select_one("#productTitle")
        if title_node is not None:
            set_field("title", title_node.get_text(" ", strip=True), "amazon_html:#productTitle")

        byline_node = soup.select_one("#bylineInfo")
        if byline_node is not None:
            byline_text = byline_node.get_text(" ", strip=True)
            brand = self._normalize_amazon_brand(byline_text)
            set_field("brand", brand, "amazon_html:#bylineInfo")
            if byline_node.get("href"):
                set_field("brand_url", urljoin(canonical_url, str(byline_node["href"])), "amazon_html:#bylineInfo@href")

        price_node = soup.select_one(
            "#corePrice_feature_div .a-offscreen, "
            "#corePrice_desktop .a-offscreen, "
            "#apex_desktop .a-offscreen, "
            ".a-price .a-offscreen"
        )
        if price_node is not None:
            set_field("price", price_node.get_text(" ", strip=True), "amazon_html:price")

        availability_node = soup.select_one(
            "#availability .a-color-success, "
            "#availability span, "
            "#availability_feature_div span.a-color-success, "
            "#availability_feature_div #availability span, "
            "#outOfStock .a-color-price, "
            "#outOfStock .a-text-bold"
        )
        if availability_node is not None:
            availability_text = availability_node.get_text(" ", strip=True)
            if availability_node.find_parent(id="outOfStock") is not None:
                out_of_stock = availability_node.find_parent(id="outOfStock")
                if out_of_stock is not None:
                    availability_text = out_of_stock.get_text(" ", strip=True)
            set_field("availability", availability_text, "amazon_html:availability")

        rating_node = soup.select_one("#averageCustomerReviews_feature_div .a-icon-alt, #acrPopover .a-icon-alt")
        if rating_node is not None:
            set_field("rating", rating_node.get_text(" ", strip=True), "amazon_html:rating")

        review_count_node = soup.select_one("#acrCustomerReviewText")
        if review_count_node is not None:
            set_field("reviews_count", review_count_node.get_text(" ", strip=True), "amazon_html:#acrCustomerReviewText")

        no_reviews_text = soup.find(string=re.compile(r"no customer reviews yet", re.IGNORECASE))
        if no_reviews_text is not None:
            if "rating" not in fields:
                set_field("rating", "No customer reviews yet", "amazon_html:no_reviews")
            if "reviews_count" not in fields:
                set_field("reviews_count", "0 reviews", "amazon_html:no_reviews")

        category_nodes = soup.select("#wayfinding-breadcrumbs_feature_div a")
        if category_nodes:
            categories = [
                node.get_text(" ", strip=True)
                for node in category_nodes
                if node.get_text(" ", strip=True)
            ]
            set_field("category", categories, "amazon_html:breadcrumbs")

        bullet_nodes = soup.select("#feature-bullets .a-list-item")
        if bullet_nodes:
            bullets = []
            for node in bullet_nodes:
                text = node.get_text(" ", strip=True)
                if text:
                    bullets.append(text)
            set_field("bullet_points", bullets, "amazon_html:#feature-bullets")

        if "category" not in fields:
            meta_title = soup.find("meta", attrs={"name": "title"})
            title_text = meta_title.get("content", "").strip() if meta_title is not None else ""
            if not title_text and soup.title and soup.title.string:
                title_text = soup.title.string.strip()
            category = self._extract_amazon_meta_category(title_text)
            if category:
                set_field("category", [category], "amazon_html:meta_title_category")

        image_nodes = soup.select("#imgTagWrapperId img[src], #altImages img[src]")
        if image_nodes:
            images: list[str] = []
            for node in image_nodes:
                src = node.get("src")
                if not src:
                    continue
                absolute = urljoin(canonical_url, str(src))
                if absolute not in images:
                    images.append(absolute)
            set_field("images", images, "amazon_html:images")

        description_node = soup.select_one("#productDescription, #productDescription_feature_div, #bookDescription_feature_div")
        if description_node is not None:
            set_field("description", description_node.get_text(" ", strip=True), "amazon_html:description")

        fulfillment_node = soup.select_one(
            "#mir-layout-DELIVERY_BLOCK-slot-PRIMARY_DELIVERY_MESSAGE_LARGE, "
            "#deliveryBlockMessage, "
            "#mir-layout-DELIVERY_BLOCK-slot-DELIVERY_MESSAGE, "
            "#exports_desktop_qualifiedBuybox_deliveryPromiseMessaging_feature_div"
        )
        if fulfillment_node is not None:
            set_field("fulfillment", fulfillment_node.get_text(" ", strip=True), "amazon_html:fulfillment")
        elif "availability" in fields and re.search(r"unavailable|out of stock|back in stock", str(fields["availability"]), re.IGNORECASE):
            set_field("fulfillment", fields["availability"], "amazon_html:availability_fallback")

        variant_nodes = soup.select("#twister li[data-defaultasin], #twister li[data-asin]")
        twister_variant_state = self._extract_amazon_twister_variant_state(soup)
        if variant_nodes:
            variants: list[dict[str, Any]] = []
            for node in variant_nodes:
                asin = node.get("data-defaultasin") or node.get("data-asin")
                label = node.get("title")
                if not label:
                    image = node.select_one("img[alt]")
                    if image is not None:
                        label = image.get("alt")
                variant: dict[str, Any] = {}
                if asin:
                    variant["asin"] = str(asin)
                if label:
                    variant["label"] = str(label).strip()
                if asin and str(asin) in twister_variant_state:
                    variant.update(twister_variant_state[str(asin)])
                if variant:
                    variants.append(variant)
            set_field("variants", variants, "amazon_html:variants")

        embedded_json_objects = self._extract_amazon_embedded_json_objects(soup)

        if "price" not in fields:
            embedded_price = self._extract_amazon_embedded_price(embedded_json_objects)
            if embedded_price:
                set_field("price", embedded_price, "amazon_html:embedded_json_price")

        if "variants" not in fields:
            embedded_variants = self._extract_amazon_embedded_variants(embedded_json_objects)
            if embedded_variants:
                for variant in embedded_variants:
                    asin = variant.get("asin")
                    if isinstance(asin, str) and asin in twister_variant_state:
                        variant.update(twister_variant_state[asin])
                set_field("variants", embedded_variants, "amazon_html:embedded_json_variants")

        seller_node = soup.select_one("#merchant-info")
        if seller_node is not None:
            set_field("seller", seller_node.get_text(" ", strip=True), "amazon_html:#merchant-info")

        return {"fields": fields, "sources": sources}

    def _extract_amazon_seller_html(
        self,
        soup: BeautifulSoup,
        canonical_url: str,
    ) -> dict[str, dict[str, Any]]:
        fields: dict[str, Any] = {}
        sources: dict[str, str] = {}

        def set_field(name: str, value: Any, source: str) -> None:
            if value in (None, "", [], {}):
                return
            fields[name] = value
            sources[name] = source

        seller_name_node = soup.select_one("#seller-name, #seller-profile-container h1, h1")
        if seller_name_node is not None:
            seller_name = seller_name_node.get_text(" ", strip=True)
            set_field("title", seller_name, "amazon_html:seller_name")
            set_field("seller_name", seller_name, "amazon_html:seller_name")

        seller_rating_node = soup.select_one("#seller-rating, #seller-info-feedback-summary, .seller-rating")
        if seller_rating_node is not None:
            set_field("seller_rating", seller_rating_node.get_text(" ", strip=True), "amazon_html:seller_rating")

        feedback_count_node = soup.select_one("#feedback-count, #seller-feedback-count, .feedback-count")
        if feedback_count_node is not None:
            set_field("feedback_count", feedback_count_node.get_text(" ", strip=True), "amazon_html:feedback_count")

        seller_since_node = soup.select_one("#seller-since, .seller-since")
        if seller_since_node is not None:
            set_field("seller_since", seller_since_node.get_text(" ", strip=True), "amazon_html:seller_since")

        product_cards = soup.select("#seller-listings .seller-product, .seller-product")
        if product_cards:
            product_listings: list[dict[str, Any]] = []
            for card in product_cards:
                product: dict[str, Any] = {}
                asin = card.get("data-asin")
                if asin:
                    product["asin"] = str(asin)
                link_node = card.select_one("a.seller-product-link[href], a[href*='/dp/']")
                if link_node is not None:
                    title = link_node.get_text(" ", strip=True)
                    href = link_node.get("href")
                    if title:
                        product["title"] = title
                    if href:
                        product["url"] = urljoin(canonical_url, str(href))
                price_node = card.select_one(".a-price .a-offscreen, .seller-product-price")
                if price_node is not None:
                    product["price"] = price_node.get_text(" ", strip=True)
                rating_node = card.select_one(".a-icon-alt, .seller-product-rating")
                if rating_node is not None:
                    product["rating"] = rating_node.get_text(" ", strip=True)
                if product:
                    product_listings.append(product)
            set_field("product_listings", product_listings, "amazon_html:product_listings")

        return {"fields": fields, "sources": sources}

    def _normalize_amazon_brand(self, byline_text: str) -> str:
        text = byline_text.strip()
        if not text:
            return text

        visit_match = re.match(r"visit the\s+(.+?)\s+store$", text, flags=re.IGNORECASE)
        if visit_match:
            return visit_match.group(1).strip()

        brand_match = re.match(r"brand:\s*(.+)$", text, flags=re.IGNORECASE)
        if brand_match:
            return brand_match.group(1).strip()

        return text

    def _extract_amazon_meta_category(self, title_text: str) -> str | None:
        text = title_text.strip()
        if not text:
            return None
        match = re.search(r":\s*([^:]+?)\s*:\s*([^:]+?)\s*$", text)
        if match:
            return match.group(2).strip()
        return None

    def _extract_amazon_embedded_json_objects(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        objects: list[dict[str, Any]] = []
        for script in soup.select("script"):
            script_text = script.string or script.get_text()
            if not script_text:
                continue
            for match in re.finditer(r"""parseJSON\('(?P<json>\{.*?\})'\)""", script_text, flags=re.DOTALL):
                raw_json = match.group("json")
                try:
                    parsed = json.loads(raw_json)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    objects.append(parsed)
        return objects

    def _extract_amazon_twister_variant_state(self, soup: BeautifulSoup) -> dict[str, dict[str, Any]]:
        state_by_asin: dict[str, dict[str, Any]] = {}
        for script in soup.select('script[data-amazon-twister-responses="true"]'):
            script_text = script.string or script.get_text()
            if not script_text.strip():
                continue
            try:
                payloads = json.loads(script_text)
            except json.JSONDecodeError:
                continue
            if not isinstance(payloads, list):
                continue
            for payload in payloads:
                if not isinstance(payload, dict):
                    continue
                body = payload.get("body")
                if not isinstance(body, str) or not body.strip():
                    continue
                for chunk in body.split("&&&"):
                    entry = chunk.strip()
                    if not entry:
                        continue
                    try:
                        parsed = json.loads(entry)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(parsed, dict):
                        continue
                    asin = parsed.get("ASIN")
                    if not isinstance(asin, str) or not asin.strip():
                        continue
                    content = parsed.get("Value", {}).get("content", {}) if isinstance(parsed.get("Value"), dict) else {}
                    if not isinstance(content, dict):
                        continue
                    variant_state: dict[str, Any] = {}
                    twister_slot_json = content.get("twisterSlotJson")
                    if isinstance(twister_slot_json, dict):
                        price = twister_slot_json.get("price")
                        if price not in (None, "", [], {}):
                            variant_state["price"] = self._extract_amazon_twister_price_text(content) or str(price)
                        is_available = twister_slot_json.get("isAvailable")
                        if isinstance(is_available, bool):
                            variant_state["availability"] = "In Stock" if is_available else "Unavailable"
                    if variant_state:
                        state_by_asin[asin.strip()] = variant_state
        return state_by_asin

    def _extract_amazon_twister_price_text(self, content: dict[str, Any]) -> str | None:
        twister_slot_div = content.get("twisterSlotDiv")
        if not isinstance(twister_slot_div, str) or not twister_slot_div.strip():
            return None
        soup = BeautifulSoup(twister_slot_div, "html.parser")
        price_node = soup.select_one(".a-offscreen, .a-price")
        if price_node is None:
            return None
        text = price_node.get_text(" ", strip=True)
        return text or None

    def _extract_amazon_embedded_price(self, objects: list[dict[str, Any]]) -> str | None:
        def find_price(value: Any) -> str | None:
            if isinstance(value, dict):
                for path in (
                    ("priceToPay", "price"),
                    ("priceToPay", "displayPrice"),
                    ("dealPrice", "price"),
                    ("apexPriceToPay", "price"),
                    ("apexPriceToPay", "displayPrice"),
                    ("price",),
                    ("displayPrice",),
                ):
                    current: Any = value
                    for key in path:
                        if not isinstance(current, dict):
                            current = None
                            break
                        current = current.get(key)
                    if isinstance(current, (str, int, float)) and str(current).strip():
                        return str(current).strip()
                for nested in value.values():
                    nested_price = find_price(nested)
                    if nested_price:
                        return nested_price
            elif isinstance(value, list):
                for item in value:
                    nested_price = find_price(item)
                    if nested_price:
                        return nested_price
            return None

        for obj in objects:
            price = find_price(obj)
            if price:
                return price
        return None

    def _extract_amazon_embedded_variants(self, objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
        variants: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        def append_variant(label: str, asin: str) -> None:
            normalized_label = label.strip()
            normalized_asin = asin.strip()
            if not normalized_label or not normalized_asin:
                return
            key = (normalized_label, normalized_asin)
            if key in seen:
                return
            seen.add(key)
            variants.append({"asin": normalized_asin, "label": normalized_label})

        def extract_from_mapping(mapping: Any) -> None:
            if isinstance(mapping, str):
                try:
                    parsed = json.loads(mapping)
                except json.JSONDecodeError:
                    return
                extract_from_mapping(parsed)
                return
            if not isinstance(mapping, dict):
                return
            for label, value in mapping.items():
                if isinstance(value, str):
                    append_variant(str(label), value)
                elif isinstance(value, dict):
                    asin = value.get("asin")
                    if isinstance(asin, str):
                        append_variant(str(label), asin)

        def visit(value: Any) -> None:
            if isinstance(value, dict):
                if "colorToAsin" in value:
                    extract_from_mapping(value["colorToAsin"])
                for nested in value.values():
                    visit(nested)
            elif isinstance(value, list):
                for item in value:
                    visit(item)

        for obj in objects:
            visit(obj)
        return variants

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

    def _extract_base_html(
        self,
        soup: BeautifulSoup,
        canonical_url: str,
        resource_type: str,
    ) -> dict[str, dict[str, Any]]:
        fields: dict[str, Any] = {}
        sources: dict[str, str] = {}

        def set_field(name: str, value: Any, source: str) -> None:
            if value in (None, "", [], {}):
                return
            fields[name] = value
            sources[name] = source

        def set_if_missing(name: str, value: Any, source: str) -> None:
            if name in fields:
                return
            set_field(name, value, source)

        title_node = soup.select_one("main h1, #ContentPlaceHolder1_maincontentinner h1")
        if title_node is not None:
            set_field("title", title_node.get_text(" ", strip=True), "base_html:h1")

        for script in soup.select('script[type="application/ld+json"]'):
            raw_json = script.string or script.get_text()
            if not raw_json.strip():
                continue
            try:
                data = json.loads(raw_json)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            if data.get("@type") == "Product":
                set_field("title", data.get("name"), "base_html:ldjson")
                set_field("description", data.get("description"), "base_html:ldjson")
                offers = data.get("offers")
                if isinstance(offers, dict):
                    set_field("price_usd", offers.get("price"), "base_html:ldjson:offers.price")
                    set_field("price_currency", offers.get("priceCurrency"), "base_html:ldjson:offers.priceCurrency")

        description_text = fields.get("description")
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc is not None and meta_desc.get("content"):
            meta_description = meta_desc.get("content", "").strip()
            if not description_text and meta_description:
                set_field("description", meta_description, "base_html:meta_description")

            token_rep = re.search(r"Token Rep:\s*([^|]+)", meta_description, flags=re.IGNORECASE)
            price = re.search(r"Price:\s*([^|]+)", meta_description, flags=re.IGNORECASE)
            market_cap = re.search(r"Onchain Market Cap:\s*([^|]+)", meta_description, flags=re.IGNORECASE)
            holders = re.search(r"Holders:\s*([^|]+)", meta_description, flags=re.IGNORECASE)
            contract_status = re.search(r"Contract:\s*([^|]+)", meta_description, flags=re.IGNORECASE)
            transactions = re.search(r"Transactions:\s*([^|]+)", meta_description, flags=re.IGNORECASE)

            if token_rep:
                set_if_missing("token_reputation", token_rep.group(1).strip(), "base_html:meta_description")
            if price:
                set_if_missing("price_usd", price.group(1).strip(), "base_html:meta_description")
            if market_cap:
                set_if_missing("market_cap", market_cap.group(1).strip(), "base_html:meta_description")
            if holders:
                set_if_missing("holders", holders.group(1).strip(), "base_html:meta_description")
            if contract_status:
                set_if_missing("contract_status", contract_status.group(1).strip(), "base_html:meta_description")
            if transactions:
                set_if_missing("transactions", transactions.group(1).strip(), "base_html:meta_description")

        if resource_type == "contract":
            source_code_node = soup.select_one("#verifiedbytecode2, #editor, pre")
            if source_code_node is not None:
                set_field("source_code", source_code_node.get_text("\n", strip=True), "base_html:source_code")

        return {"fields": fields, "sources": sources}

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
