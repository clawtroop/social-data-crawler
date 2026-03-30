"""HTML content cleaner — removes noise elements before extraction."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Comment, Tag

from .html_parse import parse_html
from .models import CleanedContent

_REFERENCES_DIR = Path(__file__).resolve().parents[1].parent / "references"

NOISE_TAGS = {"nav", "footer", "aside", "script", "style", "noscript", "iframe", "svg"}

NOISE_CLASS_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"(^|\b)(nav|menu|sidebar|footer|header|ad|ads|tracking|cookie|banner|popup|modal|overlay|social-share|share-bar|breadcrumb|pagination|related-posts|comments|comment-form)(\b|$)",
    ]
]

NOISE_ID_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"(^|\b)(nav|menu|sidebar|footer|header|ad|ads|tracking|cookie|banner|popup|modal|overlay)(\b|$)",
    ]
]

_platform_selectors_cache: dict[str, list[str]] | None = None


def _load_platform_selectors() -> dict[str, list[str]]:
    global _platform_selectors_cache
    if _platform_selectors_cache is not None:
        return _platform_selectors_cache
    path = _REFERENCES_DIR / "noise_selectors.json"
    if path.exists():
        _platform_selectors_cache = json.loads(path.read_text(encoding="utf-8"))
    else:
        _platform_selectors_cache = {}
    return _platform_selectors_cache


# 规范上应为 void 的标签若被子节点错误嵌套（常见于畸形 HTML + html.parser），
# 会导致正文挂在 img 等标签下；后续再按 display:none 整棵删除会误删主内容。
_VOID_TAGS = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
)
def _matches_noise_pattern(tag: Tag) -> bool:
    if not isinstance(getattr(tag, "attrs", None), dict):
        return False
    classes = " ".join(tag.get("class", []))
    tag_id = tag.get("id", "")
    for pattern in NOISE_CLASS_PATTERNS:
        if pattern.search(classes):
            return True
    for pattern in NOISE_ID_PATTERNS:
        if isinstance(tag_id, str) and pattern.search(tag_id):
            return True
    return False


def _unwrap_void_with_element_children(tag: Tag) -> bool:
    """void 标签不应包含元素子节点；若存在则展开标签，把子树提升到父级。"""
    if tag.name not in _VOID_TAGS:
        return False
    has_element_child = any(isinstance(c, Tag) for c in tag.children)
    if not has_element_child:
        return False
    tag.unwrap()
    return True


def _collect_hidden_candidates(soup: BeautifulSoup) -> list[Tag]:
    seen: set[int] = set()
    out: list[Tag] = []
    for tag in soup.find_all(True, attrs={"hidden": True}):
        i = id(tag)
        if i not in seen:
            seen.add(i)
            out.append(tag)
    for tag in soup.find_all(True, style=re.compile(r"display\s*:\s*none")):
        i = id(tag)
        if i not in seen:
            seen.add(i)
            out.append(tag)
    return out


class ContentCleaner:
    def clean(self, html: str, platform: str = "") -> CleanedContent:
        original_size = len(html)
        soup = parse_html(html)
        noise_removed = 0

        # 0. 修复 void 标签错误嵌套（在删除隐藏节点之前）
        for tag in list(soup.find_all(True)):
            if isinstance(tag, Tag) and _unwrap_void_with_element_children(tag):
                noise_removed += 1

        # 1. Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
            noise_removed += 1

        # 2. Remove noise tags by tag name
        for tag_name in NOISE_TAGS:
            for element in soup.find_all(tag_name):
                element.decompose()
                noise_removed += 1

        # 3. Remove elements matching noise class/id patterns
        for tag in soup.find_all(True):
            if _matches_noise_pattern(tag):
                tag.decompose()
                noise_removed += 1

        # 4. Remove platform-specific selectors
        selectors = _load_platform_selectors().get(platform, [])
        for selector in selectors:
            try:
                for element in soup.select(selector):
                    element.decompose()
                    noise_removed += 1
            except Exception:
                pass

        # 5. 删除隐藏节点。void 误嵌套已在步骤 0 展开，这里保持隐藏内容不泄漏到正文。
        for tag in _collect_hidden_candidates(soup):
            if not isinstance(tag, Tag) or tag.parent is None:
                continue
            tag.decompose()
            noise_removed += 1

        cleaned_html = str(soup)
        return CleanedContent(
            html=cleaned_html,
            noise_removed=noise_removed,
            original_size=original_size,
            cleaned_size=len(cleaned_html),
        )
