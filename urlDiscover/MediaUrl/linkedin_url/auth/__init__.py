"""
LinkedIn 真实访问：浏览器登录并持久化 Playwright storage_state，供后续带 Cookie 拉取页面。

流程：交互式登录 → 保存 storage_state → 后续任务复用同一会话拉取页面。
"""

from linkedin_url.auth.fetch import fetch_html_sync
from linkedin_url.auth.paths import default_storage_state_path
from linkedin_url.auth.profile_url import profile_canonical_url_from_storage_state
from linkedin_url.auth.proxy import resolve_playwright_proxy

__all__ = [
    "default_storage_state_path",
    "fetch_html_sync",
    "profile_canonical_url_from_storage_state",
    "resolve_playwright_proxy",
]
