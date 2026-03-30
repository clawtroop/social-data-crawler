"""
从已抓取 HTML 抽取轻量结构化字段（与 discover 解耦）。

复杂解析可后续接 LLM；当前仅 title / og 元数据，便于快照与排错。
"""

from __future__ import annotations

from typing import Any


def extract_page_metadata(html: str | None) -> dict[str, Any]:
    """
    返回 ``title``, ``og_title``, ``og_description`` 等（缺失则为 None）。
    """
    if not html or not html.strip():
        return {"title": None, "og_title": None, "og_description": None}

    try:
        from bs4 import BeautifulSoup
    except ImportError as e:
        raise ImportError("extract_page_metadata 需要 beautifulsoup4：pip install beautifulsoup4 lxml") from e

    soup = BeautifulSoup(html, "lxml")
    title = None
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    og_title = None
    og_description = None
    for m in soup.find_all("meta"):
        p = m.get("property") or m.get("name") or ""
        c = m.get("content")
        if not c:
            continue
        if p in ("og:title", "twitter:title"):
            og_title = c.strip()
        if p in ("og:description", "twitter:description", "description"):
            og_description = c.strip()

    return {
        "title": title or og_title,
        "og_title": og_title,
        "og_description": og_description,
    }


def extract_profile_fields(*, profile_vanity: str, html: str | None = None) -> dict[str, Any]:
    """预留：细粒度 profile 字段。"""
    base = extract_page_metadata(html)
    base["profile_vanity"] = profile_vanity
    return base


def extract_company_fields(*, company_vanity: str, html: str | None = None) -> dict[str, Any]:
    base = extract_page_metadata(html)
    base["company_vanity"] = company_vanity
    return base


def extract_job_fields(*, job_id: str, html: str | None = None) -> dict[str, Any]:
    base = extract_page_metadata(html)
    base["job_id"] = job_id
    return base


def extract_post_fields(*, activity_id: str, html: str | None = None) -> dict[str, Any]:
    base = extract_page_metadata(html)
    base["activity_id"] = activity_id
    return base
