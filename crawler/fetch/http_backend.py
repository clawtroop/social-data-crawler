from __future__ import annotations

import httpx

DEFAULT_HEADERS = {
    "User-Agent": "social-data-crawler/0.1 (contact: crawler@example.com)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _build_fetch_payload(response: httpx.Response, backend: str) -> dict:
    headers = dict(response.headers)
    content_type = headers.get("content-type")
    encoding = response.encoding or headers.get("charset")
    return {
        "url": str(response.url),
        "status_code": response.status_code,
        "headers": headers,
        "content_type": content_type,
        "encoding": encoding,
        "text": response.text,
        "content_bytes": response.content,
        "backend": backend,
    }


def fetch_http(url: str, timeout: float = 20.0) -> dict:
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        response = client.get(url, headers=DEFAULT_HEADERS)
        response.raise_for_status()
        return _build_fetch_payload(response, backend="http")
