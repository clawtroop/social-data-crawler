"""
使用标准库 ``urllib`` 调用 MediaWiki Action API（JSON），避免部分环境下 ``httpx``/``httpcore``
直连维基超时、而 ``urllib`` 正常的问题。

端点：``https://{lang}.wikipedia.org/w/api.php``
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def mw_api_get(
    lang: str,
    params: dict[str, Any],
    *,
    user_agent: str,
    timeout: float,
) -> dict[str, Any]:
    base = f"https://{lang}.wikipedia.org/w/api.php"
    q = dict(params)
    q.setdefault("format", "json")
    url = base + "?" + urllib.parse.urlencode(q, doseq=True, safe="")
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        raise RuntimeError(f"MediaWiki HTTP {e.code}: {body[:500]}") from e
    return json.loads(raw)


def query_random_titles(
    lang: str,
    *,
    limit: int,
    user_agent: str,
    timeout: float,
    rnfilterredirects: str = "nonredirects",
) -> list[dict[str, Any]]:
    """
    ``list=random``，主命名空间。

    ``rnfilterredirects``：``nonredirects`` | ``redirects`` | ``all``（维基 API）。

    返回 ``[{"id": pageid, "ns": 0, "title": "..."}, ...]``
    """
    params: dict[str, Any] = {
        "action": "query",
        "list": "random",
        "rnnamespace": 0,
        "rnlimit": min(500, max(1, limit)),
        "rnfilterredirects": rnfilterredirects,
    }
    data = mw_api_get(lang, params, user_agent=user_agent, timeout=timeout)
    return list(data.get("query", {}).get("random", []))


def query_all_links_titles(
    lang: str,
    title: str,
    *,
    user_agent: str,
    timeout: float,
) -> list[str]:
    """
    ``prop=links``，分页拉全；含各命名空间链出标题（由调用方过滤）。
    """
    collected: list[str] = []
    params: dict[str, Any] = {
        "action": "query",
        "titles": title,
        "redirects": "1",
        "prop": "links",
        "pllimit": "500",
    }
    while True:
        data = mw_api_get(lang, params, user_agent=user_agent, timeout=timeout)
        q = data.get("query", {})
        pages = q.get("pages", {})
        for _pid, page in pages.items():
            if "missing" in page:
                continue
            for ln in page.get("links", []):
                t = ln.get("title")
                if t:
                    collected.append(t)
        cont = data.get("continue")
        if not cont:
            break
        for k, v in cont.items():
            params[k] = v
    return collected


def query_all_links(
    lang: str,
    title: str,
    *,
    user_agent: str,
    timeout: float,
) -> list[dict[str, Any]]:
    """
    ``prop=links``，分页拉全。每项含 ``ns``、``title``（与其它 API 字段）。

    用于区分主命名空间条目（``ns==0``）与 ``Wikipedia:`` 项目页（``ns==4``）等。
    """
    collected: list[dict[str, Any]] = []
    params: dict[str, Any] = {
        "action": "query",
        "titles": title,
        "redirects": "1",
        "prop": "links",
        "pllimit": "500",
    }
    while True:
        data = mw_api_get(lang, params, user_agent=user_agent, timeout=timeout)
        q = data.get("query", {})
        pages = q.get("pages", {})
        for _pid, page in pages.items():
            if "missing" in page:
                continue
            for ln in page.get("links", []):
                collected.append(dict(ln))
        cont = data.get("continue")
        if not cont:
            break
        for k, v in cont.items():
            params[k] = v
    return collected


def query_page_exists(
    lang: str,
    title: str,
    *,
    user_agent: str,
    timeout: float,
) -> tuple[bool, str]:
    """是否存在；若存在返回 (True, 规范化标题)。"""
    params = {
        "action": "query",
        "titles": title,
        "redirects": "1",
        "prop": "info",
    }
    data = mw_api_get(lang, params, user_agent=user_agent, timeout=timeout)
    pages = data.get("query", {}).get("pages", {})
    for _pid, page in pages.items():
        if "missing" in page:
            return False, title
        t = page.get("title", title)
        return True, t
    return False, title


__all__ = [
    "mw_api_get",
    "query_all_links",
    "query_all_links_titles",
    "query_page_exists",
    "query_random_titles",
]
