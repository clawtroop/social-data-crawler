from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from .backend_router import get_escalation_backend, resolve_backend
from .browser_pool import BrowserPool
from .models import FetchTiming, RawFetchResult
from .session_manager import SessionManager
from .wait_strategy import apply_wait_strategy

logger = logging.getLogger(__name__)

_DEFAULT_HTTP_HEADERS = {
    "User-Agent": "social-data-crawler/0.1 (contact: crawler@example.com)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class FetchEngine:
    """Unified fetch engine integrating browser pool, wait strategies, backend routing, and session management."""

    def __init__(
        self,
        session_root: Path,
        *,
        max_retries: int = 2,
        http_timeout: float = 20.0,
    ) -> None:
        self._session_root = session_root
        self._max_retries = max_retries
        self._http_timeout = http_timeout
        self._pool = BrowserPool(session_root)
        self._session_mgr = SessionManager(session_root)
        self._started = False

    @property
    def session_manager(self) -> SessionManager:
        return self._session_mgr

    @property
    def browser_pool(self) -> BrowserPool:
        return self._pool

    async def start(self) -> None:
        if not self._started:
            await self._pool.start()
            self._started = True

    async def close(self) -> None:
        if self._started:
            await self._pool.close()
            self._started = False

    async def __aenter__(self) -> FetchEngine:
        await self.start()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    async def fetch(
        self,
        url: str,
        platform: str,
        resource_type: str | None = None,
        *,
        requires_auth: bool = False,
        override_backend: str | None = None,
        preferred_backend: str | None = None,
        fallback_chain: list[str] | None = None,
        api_fetcher: Any | None = None,
        api_kwargs: dict | None = None,
    ) -> RawFetchResult:
        """Fetch a URL with automatic backend selection, wait strategies, and retry/escalation."""
        if override_backend:
            initial_backend = override_backend
            fallback_chain: list[str] = []
        elif preferred_backend is not None:
            initial_backend = preferred_backend
            fallback_chain = list(fallback_chain or [])
        else:
            initial_backend, fallback_chain = resolve_backend(platform, resource_type, requires_auth)

        backends_to_try = [initial_backend] + fallback_chain
        last_error: Exception | None = None

        for attempt, backend in enumerate(backends_to_try):
            if attempt > self._max_retries:
                break
            try:
                result = await self._fetch_with_backend(
                    url=url,
                    platform=platform,
                    resource_type=resource_type or "",
                    backend=backend,
                    api_fetcher=api_fetcher,
                    api_kwargs=api_kwargs,
                )
                return result
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Fetch failed with backend=%s for %s (attempt %d): %s",
                    backend, url, attempt + 1, exc,
                )
                continue

        raise RuntimeError(
            f"All backends exhausted for {url} (tried {backends_to_try[:self._max_retries + 1]})"
        ) from last_error

    async def _fetch_with_backend(
        self,
        *,
        url: str,
        platform: str,
        resource_type: str,
        backend: str,
        api_fetcher: Any | None = None,
        api_kwargs: dict | None = None,
    ) -> RawFetchResult:
        start_ms = _now_ms()

        if backend == "http":
            return await self._fetch_http(url, start_ms)
        elif backend == "api":
            return await self._fetch_api(url, api_fetcher, api_kwargs, start_ms)
        elif backend in ("playwright", "camoufox"):
            return await self._fetch_browser(url, platform, resource_type, backend, start_ms)
        else:
            raise ValueError(f"Unsupported backend: {backend!r}")

    async def _fetch_http(self, url: str, start_ms: int) -> RawFetchResult:
        nav_start = _now_ms()
        async with httpx.AsyncClient(
            timeout=self._http_timeout,
            follow_redirects=True,
            headers=_DEFAULT_HTTP_HEADERS,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

        nav_ms = _now_ms() - nav_start
        headers = dict(response.headers)
        content_type = headers.get("content-type", "")
        json_data = None
        if "json" in content_type:
            try:
                json_data = response.json()
            except Exception:
                pass

        return RawFetchResult(
            url=url,
            final_url=str(response.url),
            backend="http",
            fetch_time=datetime.now(UTC),
            content_type=content_type,
            status_code=response.status_code,
            html=response.text,
            json_data=json_data,
            content_bytes=response.content,
            headers=headers,
            timing=FetchTiming(
                start_ms=start_ms,
                navigation_ms=nav_ms,
                wait_strategy_ms=0,
                total_ms=_now_ms() - start_ms,
            ),
        )

    async def _fetch_api(
        self,
        url: str,
        api_fetcher: Any | None,
        api_kwargs: dict | None,
        start_ms: int,
    ) -> RawFetchResult:
        if api_fetcher is None:
            raise ValueError("api backend requires an api_fetcher callable")
        nav_start = _now_ms()
        kwargs = api_kwargs or {}
        if asyncio.iscoroutinefunction(api_fetcher):
            data = await api_fetcher(url, **kwargs)
        else:
            data = api_fetcher(url, **kwargs)
        nav_ms = _now_ms() - nav_start

        return RawFetchResult(
            url=url,
            final_url=data.get("url", url),
            backend="api",
            fetch_time=datetime.now(UTC),
            content_type=data.get("content_type", ""),
            status_code=data.get("status_code", 200),
            html=data.get("text") or data.get("html"),
            json_data=data.get("json_data"),
            content_bytes=data.get("content_bytes"),
            headers=data.get("headers", {}),
            timing=FetchTiming(
                start_ms=start_ms,
                navigation_ms=nav_ms,
                wait_strategy_ms=0,
                total_ms=_now_ms() - start_ms,
            ),
        )

    async def _fetch_browser(
        self,
        url: str,
        platform: str,
        resource_type: str,
        backend: str,
        start_ms: int,
    ) -> RawFetchResult:
        if not self._started:
            await self.start()

        context = await self._pool.acquire_context(platform, backend)
        try:
            page = await context.new_page()
            nav_start = _now_ms()

            try:
                await page.goto(url, wait_until="domcontentloaded")
            except Exception as exc:
                logger.warning("Navigation to %s failed: %s", url, exc)
                raise

            nav_ms = _now_ms() - nav_start

            # Apply wait strategy
            wait_name, wait_ms = await apply_wait_strategy(page, platform, resource_type)

            html = await page.content()
            final_url = page.url
            screenshot = await page.screenshot(type="png")

            # Check if cookies were updated
            cookies_updated = await self._session_mgr.refresh_session(platform, context)

            total_ms = _now_ms() - start_ms

            return RawFetchResult(
                url=url,
                final_url=final_url,
                backend=backend,  # type: ignore[arg-type]
                fetch_time=datetime.now(UTC),
                content_type="text/html; charset=utf-8",
                status_code=200,
                html=html,
                content_bytes=html.encode("utf-8"),
                screenshot=screenshot,
                cookies_updated=cookies_updated,
                wait_strategy_used=wait_name,
                timing=FetchTiming(
                    start_ms=start_ms,
                    navigation_ms=nav_ms,
                    wait_strategy_ms=wait_ms,
                    total_ms=total_ms,
                ),
            )
        finally:
            await self._pool.release_context(platform, context, backend)


def _now_ms() -> int:
    return int(time.monotonic() * 1000)
