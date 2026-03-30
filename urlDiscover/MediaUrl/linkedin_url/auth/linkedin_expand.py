"""
领英页面中「显示更多 / Show more」「显示全部 / Show all」等折叠控件：在取 HTML 前尽量展开，否则链接不在 DOM 中。

说明：UI 与 class 会变，采用 **role + 可见文本** 与 **aria-label** 多路匹配；无法保证 100% 覆盖。
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page

logger = logging.getLogger(__name__)

# 稍宽：避免点到「Follow」「Message」等（要求整段文本较短且匹配）
_SHOW_MORE_LOOSE = re.compile(
    r"show more|see more|显示更多|查看更多|显示全部|"
    r"show all\b|see all\b|see all experiences|show all \d+|see all \d+|"
    r"see more jobs|see all jobs|查看全部职位|显示全部职位|"
    r"all activity|全部动态",
    re.I,
)


def expand_show_more_sections(page: "Page", *, max_rounds: int = 12) -> int:
    """
    在 ``main``（若无则 ``body``）内多轮点击「显示更多」类控件，返回累计点击次数。

    每轮结束后滚动到底部，便于新注入的懒加载/折叠块出现。
    """
    _require_playwright_page(page)
    root = page.locator("main").first
    if root.count() == 0:
        root = page.locator("body")

    total = 0
    for rnd in range(max_rounds):
        round_clicks = 0

        # 1) role=button / role=link + 名称正则
        for role in ("button", "link"):
            loc = root.get_by_role(role, name=_SHOW_MORE_LOOSE)
            n = loc.count()
            for i in range(min(n, 30)):
                try:
                    el = loc.nth(i)
                    if not el.is_visible(timeout=400):
                        continue
                    txt = (el.inner_text(timeout=500) or "").strip()
                    if len(txt) > 80:
                        continue
                    if not _SHOW_MORE_LOOSE.search(txt):
                        continue
                    el.click(timeout=2000)
                    round_clicks += 1
                    total += 1
                    page.wait_for_timeout(350)
                except Exception:
                    pass

        # 2) aria-label（部分区块用图标按钮；CSS 不支持 /i，多写几种大小写）
        try:
            aria_sel = (
                '[aria-label*="Show more"], [aria-label*="show more"], '
                '[aria-label*="See more"], [aria-label*="see more"], '
                '[aria-label*="Show all"], [aria-label*="show all"], '
                '[aria-label*="See all"], [aria-label*="see all"], '
                '[aria-label*="显示更多"], [aria-label*="查看更多"], [aria-label*="显示全部"], '
                '[aria-label*="See all jobs"], [aria-label*="see all jobs"], '
                '[aria-label*="See more jobs"], [aria-label*="查看全部职位"]'
            )
            al = root.locator(aria_sel)
            m = al.count()
            for i in range(min(m, 15)):
                try:
                    el = al.nth(i)
                    if el.is_visible(timeout=400):
                        el.click(timeout=2000)
                        round_clicks += 1
                        total += 1
                        page.wait_for_timeout(350)
                except Exception:
                    pass
        except Exception:
            pass

        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(600)

        if round_clicks == 0:
            logger.debug("expand_show_more: no more clicks at round %s", rnd)
            break
        logger.debug("expand_show_more: round %s clicks=%s", rnd, round_clicks)

    logger.info("expand_show_more: total clicks=%s", total)
    return total


def _require_playwright_page(page: object) -> None:
    if page is None or not hasattr(page, "locator"):
        raise TypeError("需要 Playwright Page 实例")
