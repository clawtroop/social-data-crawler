"""
用已保存的 storage_state 访问一条动态 URL，根据 HTTP 状态与 HTML 特征判断「是否像已登录可见」。

说明：领英页面结构会变；若动态被删、无权限或仅好友可见，即使用户已登录也可能显示不可用。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from linkedin_url.auth.paths import default_storage_state_path
from linkedin_url.auth.proxy import resolve_playwright_proxy

logger = logging.getLogger(__name__)


def analyze_linkedin_activity_html(html: str) -> tuple[bool, bool, str]:
    """
    返回 (looks_like_guest_wall, looks_like_feed_content, message)。
    供单元测试与 CLI 共用；领英改版时需更新关键词。
    """
    low = html.lower()
    guest_wall = (
        "sign in or join now to see" in low
        or ("sign in or join now" in low and "join linkedin" in low[:8000])
    )
    feed_ok = (
        "feed-shared-update-v2" in low
        or "feed-shared-update-v2__description" in low
        or "update-components-text" in low
    )

    if guest_wall:
        msg = "判定：当前 HTML 仍像访客墙（未登录或 li_at 等 Cookie 未生效）。请重新 login 或检查代理。"
    elif feed_ok:
        msg = "判定：页面中出现动态正文相关结构，会话大概率可用。若仍看不到内容，可能是权限/删帖/风控。"
    else:
        msg = "判定：无法自动区分。请用 --save-html 查看页面或在本机有头浏览器对比。"

    return guest_wall, feed_ok, msg


@dataclass(frozen=True)
class SessionVerifyResult:
    http_status: int | None
    url_final: str
    html_length: int
    looks_like_guest_wall: bool
    looks_like_feed_content: bool
    message: str
    html: str


def _require_playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError as e:
        raise ImportError(
            "需要安装 Playwright：pip install playwright && playwright install chromium"
        ) from e


def verify_session_on_activity_url(
    url: str,
    *,
    state_path: Path | None = None,
    proxy: str | None = None,
    headless: bool = True,
    timeout_ms: float = 60_000,
) -> SessionVerifyResult:
    """
    访问 ``url``（建议用 ``/feed/update/urn:li:activity:...``），判断是否仍被要求登录。

    访客态常见文案：「Sign in or join now to see …」；已登录且页面渲染动态模块时常含 ``feed-shared-update-v2`` 等类名。
    """
    _require_playwright()
    from playwright.sync_api import sync_playwright

    path = Path(state_path) if state_path is not None else default_storage_state_path()
    if not path.is_file():
        raise FileNotFoundError(
            f"未找到会话文件：{path}\n请先：python -m linkedin_url login"
        )

    proxy_cfg = resolve_playwright_proxy(explicit=proxy)

    with sync_playwright() as p:
        launch_kw: dict = dict(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        if proxy_cfg:
            launch_kw["proxy"] = proxy_cfg
        browser = p.chromium.launch(**launch_kw)
        context = browser.new_context(storage_state=str(path))
        page = context.new_page()
        resp = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        status = resp.status if resp else None
        final = page.url
        html = page.content()
        browser.close()

    guest_wall, feed_ok, msg = analyze_linkedin_activity_html(html)

    return SessionVerifyResult(
        http_status=status,
        url_final=final,
        html_length=len(html),
        looks_like_guest_wall=guest_wall,
        looks_like_feed_content=feed_ok,
        message=msg,
        html=html,
    )
