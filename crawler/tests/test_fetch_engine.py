"""Tests for the Layer 1 Fetch Engine components."""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from crawler.fetch.backend_router import get_escalation_backend, resolve_backend
from crawler.fetch.error_classifier import classify_content
from crawler.fetch.models import FetchTiming, RawFetchResult, SessionStatus
from crawler.fetch.rate_limiter import RateLimiter
from crawler.fetch.session_manager import SessionManager
from crawler.fetch.wait_strategy import get_wait_config


# ---------------------------------------------------------------------------
# models.py
# ---------------------------------------------------------------------------

class TestRawFetchResult:
    def test_from_legacy_http(self):
        legacy = {
            "url": "https://en.wikipedia.org/wiki/AI",
            "status_code": 200,
            "headers": {"content-type": "text/html"},
            "content_type": "text/html",
            "text": "<html>hello</html>",
            "content_bytes": b"<html>hello</html>",
            "backend": "http",
        }
        result = RawFetchResult.from_legacy(legacy, backend="http", url="https://en.wikipedia.org/wiki/AI")
        assert result.backend == "http"
        assert result.html == "<html>hello</html>"
        assert result.status_code == 200
        assert result.final_url == "https://en.wikipedia.org/wiki/AI"
        assert isinstance(result.fetch_time, datetime)

    def test_from_legacy_playwright(self):
        legacy = {
            "url": "https://example.com",
            "html": "<html>page</html>",
            "content_type": "text/html; charset=utf-8",
            "content_bytes": b"<html>page</html>",
            "screenshot_bytes": b"\x89PNG...",
            "backend": "playwright",
        }
        result = RawFetchResult.from_legacy(legacy, backend="playwright", url="https://example.com")
        assert result.backend == "playwright"
        assert result.screenshot == b"\x89PNG..."
        assert result.status_code == 200

    def test_to_legacy_dict(self):
        result = RawFetchResult(
            url="https://example.com",
            final_url="https://example.com/final",
            backend="http",
            fetch_time=datetime(2026, 1, 1),
            content_type="text/html",
            status_code=200,
            html="<html>test</html>",
            content_bytes=b"<html>test</html>",
            headers={"content-type": "text/html"},
        )
        legacy = result.to_legacy_dict()
        assert legacy["url"] == "https://example.com/final"
        assert legacy["html"] == "<html>test</html>"
        assert legacy["text"] == "<html>test</html>"
        assert legacy["backend"] == "http"
        assert legacy["status_code"] == 200

    def test_to_legacy_dict_with_json(self):
        result = RawFetchResult(
            url="https://api.example.com",
            final_url="https://api.example.com",
            backend="api",
            fetch_time=datetime(2026, 1, 1),
            content_type="application/json",
            status_code=200,
            json_data={"key": "value"},
        )
        legacy = result.to_legacy_dict()
        assert legacy["json_data"] == {"key": "value"}
        assert "html" not in legacy


class TestFetchTiming:
    def test_frozen(self):
        t = FetchTiming(start_ms=100, navigation_ms=200, wait_strategy_ms=50, total_ms=350)
        assert t.total_ms == 350
        with pytest.raises(AttributeError):
            t.total_ms = 999  # type: ignore[misc]


# ---------------------------------------------------------------------------
# backend_router.py
# ---------------------------------------------------------------------------

class TestBackendRouter:
    def test_linkedin_post_routes_camoufox(self):
        backend, chain = resolve_backend("linkedin", "post")
        assert backend == "camoufox"
        assert "playwright" in chain

    def test_linkedin_auth_routes_api(self):
        backend, chain = resolve_backend("linkedin", "profile", requires_auth=True)
        assert backend == "api"
        assert "playwright" in chain
        assert "camoufox" in chain

    def test_amazon_routes_playwright(self):
        backend, chain = resolve_backend("amazon", "product")
        assert backend == "http"
        assert "playwright" in chain
        assert "camoufox" in chain

    def test_wikipedia_routes_http(self):
        backend, chain = resolve_backend("wikipedia", "article")
        assert backend == "api"
        assert "http" in chain

    def test_unknown_platform_uses_default(self):
        backend, chain = resolve_backend("unknown_platform", "page")
        assert backend == "http"

    def test_escalation_returns_next_backend(self):
        next_b = get_escalation_backend("amazon", "playwright", "product")
        assert next_b == "camoufox"

    def test_escalation_returns_none_at_end(self):
        next_b = get_escalation_backend("amazon", "camoufox", "product")
        assert next_b is None

    def test_escalation_unknown_current(self):
        next_b = get_escalation_backend("amazon", "nonexistent", "product")
        assert next_b == "playwright"


# ---------------------------------------------------------------------------
# wait_strategy.py
# ---------------------------------------------------------------------------

class TestWaitStrategy:
    def test_linkedin_profile_config(self):
        config = get_wait_config("linkedin", "profile")
        assert config["wait_for_selector"] == "section.artdeco-card"
        assert config["wait_for_network_quiet"] is True
        assert config["max_wait_ms"] == 15000

    def test_amazon_product_config(self):
        config = get_wait_config("amazon", "product")
        assert config["wait_for_selector"] == "#productTitle"
        assert config["max_wait_ms"] == 10000

    def test_unknown_uses_defaults(self):
        config = get_wait_config("unknown", "page")
        assert config.get("max_wait_ms") == 10000
        assert config.get("wait_for_network_quiet") is False

    def test_scroll_config(self):
        config = get_wait_config("linkedin", "company")
        assert config.get("scroll_to_load") is True
        assert config.get("scroll_count") == 3


# ---------------------------------------------------------------------------
# session_manager.py
# ---------------------------------------------------------------------------

class TestSessionManager:
    def test_missing_session(self, workspace_tmp_path: Path):
        mgr = SessionManager(workspace_tmp_path)
        assert mgr.validate_session("linkedin") == SessionStatus.MISSING

    def test_valid_session(self, workspace_tmp_path: Path):
        mgr = SessionManager(workspace_tmp_path)
        state = {
            "cookies": [
                {"name": "li_at", "value": "abc123", "domain": ".linkedin.com", "path": "/"},
                {"name": "JSESSIONID", "value": "sess1", "domain": ".linkedin.com", "path": "/"},
            ],
            "origins": [],
        }
        (workspace_tmp_path / "linkedin.json").write_text(json.dumps(state), encoding="utf-8")
        assert mgr.validate_session("linkedin") == SessionStatus.VALID

    def test_expired_session(self, workspace_tmp_path: Path):
        mgr = SessionManager(workspace_tmp_path)
        past = time.time() - 3600  # 1 hour ago
        state = {
            "cookies": [
                {"name": "li_at", "value": "abc123", "domain": ".linkedin.com", "path": "/", "expires": past},
                {"name": "JSESSIONID", "value": "sess1", "domain": ".linkedin.com", "path": "/"},
            ],
            "origins": [],
        }
        (workspace_tmp_path / "linkedin.json").write_text(json.dumps(state), encoding="utf-8")
        assert mgr.validate_session("linkedin") == SessionStatus.EXPIRED

    def test_invalid_session_missing_cookie(self, workspace_tmp_path: Path):
        mgr = SessionManager(workspace_tmp_path)
        state = {
            "cookies": [
                {"name": "li_at", "value": "abc123"},
                # Missing JSESSIONID
            ],
            "origins": [],
        }
        (workspace_tmp_path / "linkedin.json").write_text(json.dumps(state), encoding="utf-8")
        assert mgr.validate_session("linkedin") == SessionStatus.INVALID

    def test_platform_without_critical_cookies(self, workspace_tmp_path: Path):
        mgr = SessionManager(workspace_tmp_path)
        state = {
            "cookies": [{"name": "some_cookie", "value": "val"}],
            "origins": [],
        }
        (workspace_tmp_path / "wikipedia.json").write_text(json.dumps(state), encoding="utf-8")
        assert mgr.validate_session("wikipedia") == SessionStatus.VALID

    def test_has_valid_session(self, workspace_tmp_path: Path):
        mgr = SessionManager(workspace_tmp_path)
        assert mgr.has_valid_session("linkedin") is False

    def test_corrupt_file(self, workspace_tmp_path: Path):
        mgr = SessionManager(workspace_tmp_path)
        (workspace_tmp_path / "linkedin.json").write_text("NOT JSON", encoding="utf-8")
        assert mgr.validate_session("linkedin") == SessionStatus.MISSING


# ---------------------------------------------------------------------------
# engine.py - unit tests (mocked browser)
# ---------------------------------------------------------------------------

class TestFetchEngineHttp:
    def test_rate_limiter_waits_between_requests(self):
        async def run():
            limiter = RateLimiter()
            limiter._config = {"defaults": {"requests_per_minute": 60}}
            limiter._last_request["linkedin"] = time.monotonic()

            with patch("crawler.fetch.rate_limiter.asyncio.sleep", new=AsyncMock()) as sleep_mock:
                await limiter.acquire("linkedin")

            sleep_mock.assert_awaited_once()
            assert sleep_mock.await_args.args[0] == pytest.approx(1.0, rel=0.2)

        asyncio.run(run())

    def test_classify_content_detects_authwall(self):
        err = classify_content("<html><body>authwall</body></html>" * 20, "https://www.linkedin.com/login")
        assert err is not None
        assert err.error_code == "AUTH_EXPIRED"
        assert err.agent_hint == "refresh_session"

    def test_fetch_http_success(self):
        """Test HTTP fetch via the engine with a mocked httpx response."""
        from crawler.fetch.engine import FetchEngine

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = "<html>test</html>"
        mock_response.content = b"<html>test</html>"
        mock_response.url = "https://en.wikipedia.org/wiki/AI"
        mock_response.raise_for_status = MagicMock()
        mock_response.json.side_effect = Exception("not json")

        async def run():
            with patch("crawler.fetch.engine.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                engine = FetchEngine(Path("/tmp/test-sessions"))
                result = await engine._fetch_http("https://en.wikipedia.org/wiki/AI", 0)
                assert result.backend == "http"
                assert result.html == "<html>test</html>"
                assert result.status_code == 200

        asyncio.run(run())

    def test_fetch_api_with_sync_fetcher(self):
        """Test API backend with a synchronous fetcher function."""
        from crawler.fetch.engine import FetchEngine

        def my_api_fetcher(url, **kwargs):
            return {
                "url": url,
                "status_code": 200,
                "content_type": "application/json",
                "json_data": {"result": "ok"},
                "headers": {},
            }

        async def run():
            engine = FetchEngine(Path("/tmp/test-sessions"))
            result = await engine._fetch_api(
                "https://api.example.com/data",
                api_fetcher=my_api_fetcher,
                api_kwargs={},
                start_ms=0,
            )
            assert result.backend == "api"
            assert result.json_data == {"result": "ok"}

        asyncio.run(run())

    def test_fetch_api_without_fetcher_raises(self):
        """Test that api backend without fetcher raises ValueError."""
        from crawler.fetch.engine import FetchEngine

        async def run():
            engine = FetchEngine(Path("/tmp/test-sessions"))
            with pytest.raises(ValueError, match="api_fetcher"):
                await engine._fetch_api("https://api.example.com", None, None, 0)

        asyncio.run(run())

    def test_fetch_automatically_escalates_from_api_to_http(self):
        """Automatic backend routing should keep falling back when api fails."""
        from crawler.fetch.engine import FetchEngine
        from crawler.fetch.models import FetchTiming, RawFetchResult

        async def run():
            engine = FetchEngine(Path("/tmp/test-sessions"))
            calls: list[str] = []

            async def fake_fetch_with_backend(*, backend: str, **kwargs):
                calls.append(backend)
                if backend == "api":
                    raise RuntimeError("api unavailable")
                return RawFetchResult(
                    url="https://example.com",
                    final_url="https://example.com",
                    backend=backend,
                    fetch_time=datetime(2026, 1, 1),
                    content_type="text/html",
                    status_code=200,
                    html="<html><body>" + ("ok " * 100) + "</body></html>",
                    timing=FetchTiming(start_ms=0, navigation_ms=1, wait_strategy_ms=0, total_ms=1),
                )

            with patch.object(engine, "_fetch_with_backend", side_effect=fake_fetch_with_backend):
                result = await engine.fetch(
                    url="https://example.com",
                    platform="wikipedia",
                    resource_type="article",
                    api_fetcher=lambda _url, **_kwargs: {"url": "https://example.com", "status_code": 200},
                )

            assert calls == ["api", "http"]
            assert result.backend == "http"

        asyncio.run(run())

    def test_fetch_raises_structured_error_for_content_level_issue(self):
        from crawler.fetch.engine import FetchEngine

        async def run():
            engine = FetchEngine(Path("/tmp/test-sessions"))

            async def fake_fetch_with_backend(**kwargs):
                return RawFetchResult(
                    url="https://www.linkedin.com/in/test/",
                    final_url="https://www.linkedin.com/login",
                    backend="playwright",
                    fetch_time=datetime(2026, 1, 1),
                    content_type="text/html; charset=utf-8",
                    status_code=200,
                    html="<html><body>authwall</body></html>" * 20,
                    timing=FetchTiming(start_ms=0, navigation_ms=1, wait_strategy_ms=0, total_ms=1),
                )

            with patch.object(engine, "_fetch_with_backend", side_effect=fake_fetch_with_backend):
                with pytest.raises(RuntimeError) as exc_info:
                    await engine.fetch(
                        url="https://www.linkedin.com/in/test/",
                        platform="linkedin",
                        resource_type="profile",
                    )

            fetch_error = getattr(exc_info.value, "fetch_error", None)
            assert fetch_error is not None
            assert fetch_error.error_code == "AUTH_EXPIRED"
            assert fetch_error.agent_hint == "refresh_session"

        asyncio.run(run())

    def test_fetch_opens_circuit_after_repeated_rate_limits(self):
        from crawler.fetch.engine import FetchEngine

        async def run():
            engine = FetchEngine(Path("/tmp/test-sessions"))
            attempts = 0

            async def fake_fetch_with_backend(**kwargs):
                nonlocal attempts
                attempts += 1
                request = httpx.Request("GET", "https://example.com")
                response = httpx.Response(429, request=request)
                raise httpx.HTTPStatusError("rate limited", request=request, response=response)

            with patch.object(engine, "_fetch_with_backend", side_effect=fake_fetch_with_backend):
                with pytest.raises(RuntimeError):
                    await engine.fetch(url="https://example.com", platform="linkedin", resource_type="profile")
                with pytest.raises(RuntimeError) as exc_info:
                    await engine.fetch(url="https://example.com/2", platform="linkedin", resource_type="profile")

            fetch_error = getattr(exc_info.value, "fetch_error", None)
            assert fetch_error is not None
            assert fetch_error.error_code == "CIRCUIT_OPEN"
            assert attempts >= 1

        asyncio.run(run())
