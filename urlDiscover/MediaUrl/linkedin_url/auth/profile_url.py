"""
从已保存的 Playwright ``storage_state`` 解析当前登录用户的个人主页规范 URL。

做法：在带会话的上下文中访问 ``https://www.linkedin.com/in/me/``，领英会重定向到
``/in/{vanity}/``，再经 ``standard_canonical_url`` 去掉 query 等。
"""

from __future__ import annotations

import logging
from pathlib import Path

from linkedin_url.auth.paths import default_storage_state_path
from linkedin_url.auth.proxy import resolve_playwright_proxy
from linkedin_url.normalize import standard_canonical_url

logger = logging.getLogger(__name__)

_ME_REDIRECT_URL = "https://www.linkedin.com/in/me/"


def _require_playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError as e:
        raise ImportError(
            "需要安装 Playwright：pip install playwright && playwright install chromium"
        ) from e


def profile_canonical_url_from_storage_state(
    state_path: Path | None = None,
    *,
    proxy: str | None = None,
    headless: bool = True,
    timeout_ms: float = 60_000,
) -> str | None:
    """
    使用已保存会话打开 ``/in/me/``，读取重定向后的地址并归一为标准 Profile URL。

    未登录、会话失效或仍停留在登录/验证页时返回 ``None``。
    """
    _require_playwright()
    from playwright.sync_api import sync_playwright

    path = Path(state_path) if state_path is not None else default_storage_state_path()
    if not path.is_file():
        raise FileNotFoundError(
            f"未找到会话文件：{path}\n请先运行：python -m linkedin_url login"
        )

    proxy_cfg = resolve_playwright_proxy(explicit=proxy)
    if proxy_cfg:
        logger.info("profile_url: 使用代理 %s", proxy_cfg.get("server"))

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
        logger.info("GET %s (解析当前用户主页)", _ME_REDIRECT_URL)
        page.goto(_ME_REDIRECT_URL, wait_until="domcontentloaded", timeout=timeout_ms)
        final = (page.url or "").strip()
        browser.close()

    low = final.lower()
    if not final or "login" in low or "checkpoint" in low or "challenge" in low:
        logger.warning("未能从重定向得到主页（可能未登录）：%s", final[:200])
        return None

    out = standard_canonical_url(final)
    if not out:
        logger.warning("重定向 URL 无法归一为四类标准 Profile：%s", final[:200])
    return out
