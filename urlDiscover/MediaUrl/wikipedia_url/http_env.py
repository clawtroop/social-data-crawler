"""
控制调用维基 API 时是否使用系统/环境变量中的 HTTP 代理。

Wikimedia 站点常可直连；若终端长期设置 ``HTTPS_PROXY`` 指向本地代理而代理未开或异常，
会导致 ``ConnectTimeout``。默认在发起 Wikipedia-API 请求时**不使用**环境代理。

* ``WIKIPEDIA_USE_SYSTEM_PROXY=1``（或 ``true`` / ``yes``）— 仍使用 ``HTTP(S)_PROXY`` 等（与 httpx ``trust_env``）。
* 否则 — 临时移除上述环境变量，并对 ``httpx.Client`` 设置 ``trust_env=False``（仅在本上下文中）。

说明：仅删除环境变量有时仍不足以阻止 httpx 使用代理；故与 ``trust_env=False`` 双管齐下。
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import Iterator
from typing import Any, Callable

_PROXY_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)


def use_system_proxy_for_wikipedia() -> bool:
    v = os.getenv("WIKIPEDIA_USE_SYSTEM_PROXY", "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _patch_httpx_trust_env_disabled() -> tuple[Callable[..., Any], Callable[..., Any]]:
    import httpx

    _orig_sync = httpx.Client.__init__
    _orig_async = httpx.AsyncClient.__init__

    def _sync(self: Any, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("trust_env", False)
        return _orig_sync(self, *args, **kwargs)

    def _async(self: Any, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("trust_env", False)
        return _orig_async(self, *args, **kwargs)

    httpx.Client.__init__ = _sync  # type: ignore[method-assign]
    httpx.AsyncClient.__init__ = _async  # type: ignore[method-assign]
    return _orig_sync, _orig_async


def _restore_httpx_init(
    _orig_sync: Callable[..., Any], _orig_async: Callable[..., Any]
) -> None:
    import httpx

    httpx.Client.__init__ = _orig_sync  # type: ignore[method-assign]
    httpx.AsyncClient.__init__ = _orig_async  # type: ignore[method-assign]


@contextlib.contextmanager
def wikipedia_requests() -> Iterator[None]:
    """
    在 ``with`` 块内创建/使用 ``wikipediaapi.Wikipedia`` 时，默认直连（不读代理环境）。

    若 ``WIKIPEDIA_USE_SYSTEM_PROXY=1``，则保持 httpx 默认行为并保留代理相关环境变量。
    """
    if use_system_proxy_for_wikipedia():
        yield
        return

    saved: dict[str, str] = {}
    for k in _PROXY_KEYS:
        if k in os.environ:
            saved[k] = os.environ.pop(k)

    _orig_s, _orig_a = _patch_httpx_trust_env_disabled()
    try:
        yield
    finally:
        _restore_httpx_init(_orig_s, _orig_a)
        for k, v in saved.items():
            os.environ[k] = v


__all__ = ["use_system_proxy_for_wikipedia", "wikipedia_requests"]
