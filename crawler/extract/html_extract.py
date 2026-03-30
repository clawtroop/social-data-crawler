from __future__ import annotations

from urllib.parse import urljoin

from markdownify import markdownify as to_markdown

from .content_cleaner import ContentCleaner
from .fit_content import FitContentReducer
from .html_parse import parse_html
from .main_content import MainContentExtractor


def _is_html_content_type(content_type: str | None) -> bool:
    if content_type is None:
        return True
    content_type = content_type.lower()
    return "html" in content_type or content_type in {"text/xml", "application/xml"}


def extract_html_document(
    html: str,
    url: str,
    content_type: str | None = None,
    *,
    platform: str = "",
    resource_type: str = "",
) -> dict:
    soup = parse_html(html)
    title = soup.title.string.strip() if soup.title and soup.title.string else None
    description_tag = soup.find("meta", attrs={"name": "description"})
    description = description_tag.get("content") if description_tag else None
    icon_tag = soup.find("link", rel=lambda value: value and "icon" in value)
    favicon = urljoin(url, icon_tag.get("href")) if icon_tag and icon_tag.get("href") else None

    markdown = to_markdown(str(soup), heading_style="ATX", bullets="-")
    plain_text = soup.get_text("\n", strip=True)
    if _is_html_content_type(content_type):
        cleaned = ContentCleaner().clean(html, platform=platform)
        cleaned_soup = parse_html(cleaned.html)
        main_content = MainContentExtractor().extract(
            cleaned_soup,
            platform,
            resource_type,
        )
        reduced_content = FitContentReducer().reduce(main_content)
        if reduced_content.markdown:
            markdown = reduced_content.markdown
        if reduced_content.text:
            plain_text = reduced_content.text

    return {
        "metadata": {
            "title": title,
            "description": description,
            "favicon": favicon,
            "content_type": content_type,
            "source_url": url,
        },
        "markdown": markdown,
        "plain_text": plain_text,
        "extractor": "html",
    }
