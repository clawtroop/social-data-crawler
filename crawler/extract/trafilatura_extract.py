from __future__ import annotations

try:
    import trafilatura
except ModuleNotFoundError:  # pragma: no cover
    trafilatura = None

from .html_extract import _is_html_content_type, extract_html_document


def extract_article_text(html: str, url: str, content_type: str | None = None) -> dict:
    if not _is_html_content_type(content_type):
        return extract_html_document(html, url, content_type=content_type)

    if trafilatura is not None:
        markdown = trafilatura.extract(
            html,
            include_links=True,
            include_images=True,
            include_tables=True,
            output_format="markdown",
            no_fallback=False,
        )
        if markdown:
            result = extract_html_document(html, url, content_type=content_type)
            result.update(
                {
                    "markdown": markdown,
                    "plain_text": markdown,
                    "extractor": "trafilatura",
                }
            )
            return result
    return extract_html_document(html, url, content_type=content_type)
