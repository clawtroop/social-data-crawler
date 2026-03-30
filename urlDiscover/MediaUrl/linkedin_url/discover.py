"""
从页面 / 文本中发现新的 LinkedIn URL，与结构化字段抽取解耦。

若未传入 html 且 ``fetch=True``，将使用 ``linkedin_url.auth.fetch`` 带会话拉取页面
（需事先 ``python -m linkedin_url login`` 保存 storage_state）。
"""

from __future__ import annotations

from urllib.parse import urljoin, urlparse


def discover_from_html(html: str, *, base_url: str = "https://www.linkedin.com/") -> list[str]:
    """
    从 HTML 中收集指向 linkedin.com 的链接（含相对路径），去重、去掉 fragment。
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError as e:
        raise ImportError("discover_from_html 需要 beautifulsoup4：pip install beautifulsoup4 lxml") from e

    if not html or not html.strip():
        return []

    soup = BeautifulSoup(html, "lxml")
    base = base_url if base_url.endswith("/") else base_url + "/"
    seen: set[str] = set()
    out: list[str] = []

    for tag in soup.find_all(href=True):
        href = (tag.get("href") or "").strip()
        if not href or href.startswith("#") or href.lower().startswith("javascript:"):
            continue
        if "/linkedin.com" not in href and "linkedin.com" not in href and not href.startswith("/"):
            continue
        if href.startswith("/"):
            full = urljoin(base, href)
        else:
            full = href
        low = full.lower()
        if "linkedin.com" not in low:
            continue
        # 只保留 http(s)
        p = urlparse(full)
        if p.scheme not in ("http", "https"):
            continue
        no_frag = full.split("#", 1)[0]
        if no_frag in seen:
            continue
        seen.add(no_frag)
        out.append(no_frag)

    return out


def discover_from_html_deep(html: str, *, base_url: str = "https://www.linkedin.com/") -> list[str]:
    """
    合并 ``<a href>`` 与整页 HTML 文本中的正则提取（覆盖内嵌 JSON / ``<code>`` 中的 URL）。

    领英个人页大量链接仅出现在序列化数据里，仅用 BeautifulSoup 锚点会漏掉公司/人脉等。

    公司 **Posts（动态）** 列表、单条 **feed/update** 详情页同理：评论区头像/姓名链到 ``/in/…``，
    侧栏「你可能还喜欢」等常含其它 ``/company/…``、``/in/…``，只要出现在 HTML 或内嵌 JSON 中即可被本函数收集。
    """
    anchor = discover_from_html(html, base_url=base_url)
    from linkedin_url.normalize import extract_linkedin_urls

    embedded: list[str] = []
    for r in extract_linkedin_urls(html):
        u = (r.original_url or "").split("#", 1)[0].strip()
        if u:
            embedded.append(u)
    seen: set[str] = set()
    out: list[str] = []
    for u in anchor + embedded:
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def discover_from_page(
    *,
    page_url: str,
    html: str | None = None,
    fetch: bool = False,
    state_path: str | None = None,
    proxy: str | None = None,
) -> list[str]:
    """
    输入：当前页面 URL 与可选 HTML；若未提供 ``html`` 且 ``fetch=True``，则用已保存会话拉取后再发现。

    ``state_path``：会话 JSON 路径，默认使用 ``LINKEDIN_STORAGE_STATE`` 或 ``.secrets/linkedin_storage_state.json``。
    ``proxy``：显式代理 URL；默认 None 时使用环境变量中的代理设置。
    """
    if html is None:
        if not fetch:
            return []
        from pathlib import Path

        from linkedin_url.auth.fetch import fetch_html_sync
        from linkedin_url.auth.paths import default_storage_state_path

        path = Path(state_path) if state_path else default_storage_state_path()
        html = fetch_html_sync(page_url, state_path=path, proxy=proxy)

    return discover_from_html_deep(html, base_url=page_url)


def discover_from_text(text: str) -> list[str]:
    """从任意文本中提取 linkedin.com URL 字符串（未归一化）。"""
    from linkedin_url.normalize import extract_linkedin_urls

    return [r.original_url for r in extract_linkedin_urls(text)]
