"""Classify fetch errors into structured categories for agent decision-making."""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx


@dataclass(frozen=True, slots=True)
class FetchError:
    error_code: str       # e.g. "RATE_LIMITED", "AUTH_EXPIRED"
    agent_hint: str       # e.g. "wait_and_retry", "refresh_session"
    message: str          # human-readable description
    retryable: bool
    status_code: int | None = None


def classify_http_error(exc: Exception) -> FetchError:
    """Classify an httpx exception into a structured FetchError."""
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code == 429:
            return FetchError("RATE_LIMITED", "wait_and_retry",
                              "Rate limit hit", True, code)
        if code in (401, 403):
            return FetchError("AUTH_EXPIRED", "refresh_session",
                              f"Auth failed ({code})", True, code)
        if code == 404:
            return FetchError("PAGE_NOT_FOUND", "skip",
                              "Page not found", False, code)
        if 500 <= code < 600:
            return FetchError("SERVER_ERROR", "retry_later",
                              f"Server error ({code})", True, code)

    if isinstance(exc, httpx.TimeoutException):
        return FetchError("NETWORK_ERROR", "retry",
                          "Request timed out", True)

    if isinstance(exc, httpx.ConnectError):
        return FetchError("NETWORK_ERROR", "retry",
                          "Connection failed", True)

    return FetchError("UNKNOWN_ERROR", "inspect", str(exc), False)


def classify_content(html: str | None, final_url: str) -> FetchError | None:
    """Detect content-level issues in a fetched page."""
    if html is None or len(html) < 200:
        return FetchError("CONTENT_EMPTY", "retry_with_browser",
                          "Page body is empty or too short", True)

    lower = html.lower()
    if "authwall" in lower or "/login" in final_url or "/checkpoint" in final_url:
        return FetchError("AUTH_EXPIRED", "refresh_session",
                          "Hit auth wall or login redirect", True)

    if re.search(r"captcha|robot check", lower):
        return FetchError("CAPTCHA", "notify_user",
                          "Captcha or robot check detected", False)

    if _looks_like_amazon_product_shell(lower, final_url):
        return FetchError("CONTENT_PARTIAL", "retry_with_browser",
                          "Amazon product page returned a shell page without product details", True)

    return None


def _looks_like_amazon_product_shell(lower_html: str, final_url: str) -> bool:
    lower_url = final_url.lower()
    if "amazon." not in lower_url:
        return False
    if "/dp/" not in lower_url and "/gp/product/" not in lower_url:
        return False

    has_generic_amazon_title = (
        '<meta property="og:title" content="amazon"' in lower_html
        or "<title>amazon</title>" in lower_html
        or '<meta property="og:description" content="amazon"' in lower_html
    )
    has_product_markers = any(
        marker in lower_html
        for marker in (
            'id="producttitle"',
            'id="feature-bullets"',
            'id="acrcustomerreviewtext"',
            'id="bylineinfo"',
            'id="coreprice',
        )
    )
    has_shell_marker = "previewdoh/amazon.png" in lower_html or 'id="page-shell"' in lower_html
    return has_generic_amazon_title and has_shell_marker and not has_product_markers


def classify(
    exc: Exception | None,
    html: str | None = None,
    final_url: str = "",
) -> FetchError | None:
    """Unified classifier: check exception first, then content."""
    if exc is not None:
        return classify_http_error(exc)
    if html is not None:
        return classify_content(html, final_url)
    return None
