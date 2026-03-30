"""维基主命名空间条目 URL 拼接（可读形式：保留 ``:`` 与 ``/``，空格为 ``_``）。"""

from __future__ import annotations

from urllib.parse import quote


def wiki_article_url_readable(lang: str, title: str) -> str:
    """
    ``https://{lang}.wikipedia.org/wiki/{Title}``，路径段中对 ``:``、``/`` 不采用 ``%3A``、``%2F``。
    其余字符按 URL 规则编码。
    """
    fragment = title.replace(" ", "_")
    return f"https://{lang}.wikipedia.org/wiki/{quote(fragment, safe=':/')}"


__all__ = ["wiki_article_url_readable"]
