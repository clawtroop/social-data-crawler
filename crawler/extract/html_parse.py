"""统一 HTML 解析入口：优先 lxml（与浏览器树更接近），失败时回退 html.parser。"""
from __future__ import annotations

from bs4 import BeautifulSoup


def parse_html(html: str, *, features: str | None = None) -> BeautifulSoup:
    """解析 HTML。默认使用 lxml；未安装或解析失败时回退到 html.parser。"""
    if features:
        return BeautifulSoup(html, features)
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")
