"""Amazon URL normalization and ASIN extraction.

Migrated from ``urlDiscover/Amazon/scripts/amazon_url_discovery.py``
(class ``AmazonURLUtils``).
"""

from __future__ import annotations

import re

from .base import NormalizeResult

# ------------------------------------------------------------------
# ASIN patterns
# ------------------------------------------------------------------

# Bare ASIN: 10 uppercase-alphanumeric characters
ASIN_PATTERN = re.compile(r"\b([A-Z0-9]{10})\b")

# Product URL variants (capture group = ASIN)
PRODUCT_URL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"amazon\.com/dp/([A-Z0-9]{10})", re.IGNORECASE),
    re.compile(r"amazon\.com/gp/product/([A-Z0-9]{10})", re.IGNORECASE),
    re.compile(r"amazon\.com/[^/]+/dp/([A-Z0-9]{10})", re.IGNORECASE),
    re.compile(r"amazon\.com/exec/obidos/ASIN/([A-Z0-9]{10})", re.IGNORECASE),
]

# data-asin HTML attribute
DATA_ASIN_PATTERN = re.compile(
    r'data-asin=["\']([A-Z0-9]{10})["\']', re.IGNORECASE
)

# ------------------------------------------------------------------
# Utility functions
# ------------------------------------------------------------------


def extract_asin(url: str) -> str | None:
    """Return the ASIN embedded in *url*, or ``None``."""
    for pattern in PRODUCT_URL_PATTERNS:
        m = pattern.search(url)
        if m:
            return m.group(1).upper()
    return None


def build_product_url(asin: str) -> str:
    """Build the canonical ``/dp/{ASIN}`` product URL."""
    return f"https://www.amazon.com/dp/{asin.upper()}"


def is_valid_asin(asin: str) -> bool:
    """Check whether *asin* looks like a valid 10-char ASIN."""
    if not asin or len(asin) != 10:
        return False
    return bool(re.match(r"^[A-Z0-9]{10}$", asin.upper()))


def extract_asins_from_html(html: str) -> set[str]:
    """Extract every valid ASIN found in *html* (URLs + ``data-asin`` attrs)."""
    asins: set[str] = set()

    for pattern in PRODUCT_URL_PATTERNS:
        for m in pattern.finditer(html):
            asins.add(m.group(1).upper())

    for m in DATA_ASIN_PATTERN.finditer(html):
        asins.add(m.group(1).upper())

    return {a for a in asins if is_valid_asin(a)}


# ------------------------------------------------------------------
# URL normalization
# ------------------------------------------------------------------


def normalize_amazon_url(url: str) -> NormalizeResult:
    """Normalize an Amazon product URL into a canonical ``/dp/{ASIN}`` form.

    Returns a :class:`NormalizeResult` with ``entity_type="product"`` when
    an ASIN can be extracted, or ``entity_type="unknown"`` otherwise.
    """
    raw = (url or "").strip()
    if not raw:
        return NormalizeResult(
            entity_type="unknown",
            canonical_url="",
            original_url=raw,
            notes=("empty_input",),
        )

    asin = extract_asin(raw)
    if asin is None:
        return NormalizeResult(
            entity_type="unknown",
            canonical_url="",
            original_url=raw,
            notes=("no_asin_found",),
        )

    return NormalizeResult(
        entity_type="product",
        canonical_url=build_product_url(asin),
        identity={"asin": asin},
        original_url=raw,
    )
