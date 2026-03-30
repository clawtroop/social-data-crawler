"""
Playwright 代理配置：优先显式参数，其次环境变量（与常见 CLI 工具习惯一致）。

支持：
- ``LINKEDIN_PROXY``：仅本工具使用，避免与系统其它程序冲突
- ``HTTPS_PROXY`` / ``HTTP_PROXY`` / ``ALL_PROXY``：标准变量

示例（PowerShell）::

    $env:HTTPS_PROXY = \"http://127.0.0.1:7890\"
    python -m linkedin_url login

示例（带账号密码的 HTTP 代理）::

    $env:LINKEDIN_PROXY = \"http://user:pass@127.0.0.1:7890\"
"""

from __future__ import annotations

import os
from urllib.parse import unquote, urlparse

# 读取顺序：专用 > 常见代理 env
_ENV_KEYS = (
    "LINKEDIN_PROXY",
    "HTTPS_PROXY",
    "HTTP_PROXY",
    "ALL_PROXY",
)


def _first_non_empty_env() -> str | None:
    for key in _ENV_KEYS:
        v = os.getenv(key, "").strip()
        if v:
            return v
    return None


def playwright_proxy_from_url(proxy_url: str) -> dict[str, str]:
    """
    将 ``http(s)://[user:pass@]host:port`` 转为 Playwright ``launch(proxy=...)`` 字典。
    SOCKS5 示例：``socks5://127.0.0.1:1080``
    """
    raw = (proxy_url or "").strip()
    if not raw:
        raise ValueError("empty proxy url")

    p = urlparse(raw)
    if not p.scheme or not p.hostname:
        return {"server": raw}

    default_ports = {"http": 80, "https": 443, "socks5": 1080, "socks4": 1080}
    port = p.port
    if port is None:
        port = default_ports.get(p.scheme.lower(), 80)
    server = f"{p.scheme}://{p.hostname}:{port}"

    cfg: dict[str, str] = {"server": server}
    if p.username:
        cfg["username"] = unquote(p.username)
    if p.password:
        cfg["password"] = unquote(p.password)
    return cfg


def resolve_playwright_proxy(*, explicit: str | None = None) -> dict[str, str] | None:
    """
    返回 Playwright 可用的 ``proxy`` 字典；若未配置则 ``None``（不走代理）。

    :param explicit: 命令行 ``--proxy`` 等传入时优先使用。
    """
    url = (explicit or "").strip() or _first_non_empty_env()
    if not url:
        return None
    return playwright_proxy_from_url(url)
