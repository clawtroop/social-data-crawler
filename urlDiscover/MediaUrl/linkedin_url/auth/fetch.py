"""使用已保存的 Playwright storage_state 拉取页面 HTML（解决未登录仅返回登录墙的问题）。"""

from __future__ import annotations

import logging
from pathlib import Path

from linkedin_url.auth.paths import default_storage_state_path
from linkedin_url.auth.proxy import resolve_playwright_proxy

logger = logging.getLogger(__name__)


def _require_playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError as e:
        raise ImportError(
            "需要安装 Playwright：pip install playwright && playwright install chromium"
        ) from e


def _looks_like_timeout(exc: BaseException) -> bool:
    """Playwright 导航/等待超时通常为 TimeoutError 或 Error 子类。"""
    name = type(exc).__name__
    if "Timeout" in name:
        return True
    msg = str(exc).lower()
    return "timeout" in msg or "exceeded" in msg


def fetch_html_sync(
    url: str,
    *,
    state_path: Path | None = None,
    headless: bool = True,
    wait_until: str = "domcontentloaded",
    timeout_ms: float = 60_000,
    proxy: str | None = None,
    settle_ms: int = 0,
    scroll_passes: int = 0,
    scroll_step_delay_ms: int = 0,
    scroll_bottom_delay_ms: int = 0,
    expand_show_more: bool = False,
    expand_max_rounds: int = 12,
    expand_post_delay_ms: int = 0,
    skip_on_timeout: bool = False,
) -> str:
    """
    在已登录上下文中访问 ``url``，返回 ``page.content()``。

    :param wait_until: 传给 ``page.goto``，表示「加载完成」的判据；常用 ``domcontentloaded``（较快）、
        ``load``（资源更多）、``networkidle``（易超时，慎用）。
    :param settle_ms: 导航后 **额外** 固定等待毫秒；默认 0，不硬等。仅当页面明显注水慢时再加大。
    :param scroll_passes: 向下滚动次数，触发懒加载；为 0 则不滚动。
    :param scroll_step_delay_ms: 每步滚动后的等待；**0 表示不等待**（仅依赖 goto 的 wait_until）。
    :param scroll_bottom_delay_ms: 滚到底后的等待；**0 表示不等待**。
    :param expand_post_delay_ms: 展开「显示更多」后、再滚动前的等待；0 表示不等待。
    :param expand_show_more: 若为 True，尝试点击「Show more / 显示更多」等后再滚动取 HTML。
    :param expand_max_rounds: 展开逻辑最大轮数。
    :param skip_on_timeout: 若为 True，导航或内部等待超时则记录警告并返回空字符串 ``""``，不抛异常。
    """
    _require_playwright()
    from playwright.sync_api import sync_playwright

    path = Path(state_path) if state_path is not None else default_storage_state_path()
    if not path.is_file():
        raise FileNotFoundError(
            f"未找到会话文件：{path}\n"
            "请先运行：python -m linkedin_url login"
        )

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
        try:
            context = browser.new_context(storage_state=str(path))
            page = context.new_page()
            logger.info("GET %s", url)

            def _run() -> str:
                page.goto(url, wait_until=wait_until, timeout=timeout_ms)
                if settle_ms > 0:
                    page.wait_for_timeout(settle_ms)

                def _scroll_loop() -> None:
                    for _ in range(max(0, scroll_passes)):
                        page.evaluate(
                            "window.scrollTo(0, Math.min(document.body.scrollHeight, "
                            "(window.scrollY || 0) + window.innerHeight * 1.2))"
                        )
                        if scroll_step_delay_ms > 0:
                            page.wait_for_timeout(scroll_step_delay_ms)
                    if scroll_passes > 0:
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        if scroll_bottom_delay_ms > 0:
                            page.wait_for_timeout(scroll_bottom_delay_ms)

                _scroll_loop()

                if expand_show_more:
                    from linkedin_url.auth.linkedin_expand import expand_show_more_sections

                    expand_show_more_sections(page, max_rounds=expand_max_rounds)
                    if expand_post_delay_ms > 0:
                        page.wait_for_timeout(expand_post_delay_ms)
                    for _ in range(max(0, scroll_passes)):
                        page.evaluate(
                            "window.scrollTo(0, Math.min(document.body.scrollHeight, "
                            "(window.scrollY || 0) + window.innerHeight * 1.2))"
                        )
                        if scroll_step_delay_ms > 0:
                            page.wait_for_timeout(scroll_step_delay_ms)
                    if scroll_passes > 0:
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        if scroll_bottom_delay_ms > 0:
                            page.wait_for_timeout(scroll_bottom_delay_ms)

                return page.content()

            try:
                return _run()
            except Exception as e:
                if skip_on_timeout and _looks_like_timeout(e):
                    logger.warning(
                        "fetch_html_sync 超时已跳过（返回空 HTML）: url=%s err=%s",
                        url,
                        e,
                    )
                    return ""
                raise
        finally:
            browser.close()
