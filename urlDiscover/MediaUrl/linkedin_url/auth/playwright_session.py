"""
使用 Playwright Chromium：打开领英登录页，人工完成验证后保存 storage_state。

说明：
- 采用 Playwright 因其 `storage_state` JSON 与 `browser.new_context(storage_state=...)` 原生兼容。
- **无头模式无法完成扫码/二次验证**，首次登录请使用默认 headed；自动化跑任务时可 headless 复用已保存状态。
"""

from __future__ import annotations

import logging
from pathlib import Path

from linkedin_url.auth.paths import default_storage_state_path
from linkedin_url.auth.proxy import resolve_playwright_proxy

logger = logging.getLogger(__name__)

DEFAULT_LOGIN_URL = "https://www.linkedin.com/login"


def _require_playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError as e:
        raise ImportError(
            "需要安装 Playwright：pip install playwright && playwright install chromium"
        ) from e


def interactive_save_storage_state(
    *,
    state_path: Path | None = None,
    login_url: str = DEFAULT_LOGIN_URL,
    headless: bool = False,
    wait_for_enter: bool = True,
    proxy: str | None = None,
) -> Path:
    """
    启动浏览器 → 打开登录页 →（可选）等待终端确认 → 将当前上下文的 cookies/localStorage 写入 JSON。

    :param headless: 仅当本机已有可用 state 需刷新且站点不要求交互时可 True；首次登录请 False。
    :param proxy: 显式代理 URL；若为 None，则读取环境变量 ``LINKEDIN_PROXY`` / ``HTTPS_PROXY`` / ``HTTP_PROXY`` / ``ALL_PROXY``。
    """
    _require_playwright()
    from playwright.sync_api import sync_playwright

    out = Path(state_path) if state_path is not None else default_storage_state_path()
    out.parent.mkdir(parents=True, exist_ok=True)

    proxy_cfg = resolve_playwright_proxy(explicit=proxy)
    if proxy_cfg:
        logger.info("使用代理：%s", proxy_cfg.get("server"))

    with sync_playwright() as p:
        launch_kw: dict = dict(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        if proxy_cfg:
            launch_kw["proxy"] = proxy_cfg
        browser = p.chromium.launch(**launch_kw)
        context = browser.new_context(
            locale="en-US",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        logger.info("正在打开 %s", login_url)
        page.goto(login_url, wait_until="domcontentloaded", timeout=60_000)

        if wait_for_enter:
            print(
                "\n请在浏览器中完成登录（含 2FA）。完成后回到此终端按 Enter 保存会话...\n"
                "若仅想放弃，可按 Ctrl+C。\n"
            )
            try:
                input()
            except EOFError:
                pass

        context.storage_state(path=str(out))
        browser.close()

    logger.info("已保存 storage_state：%s", out)
    return out


def storage_state_exists(path: Path | None = None) -> bool:
    p = Path(path) if path is not None else default_storage_state_path()
    return p.is_file() and p.stat().st_size > 0
