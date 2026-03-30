from __future__ import annotations

from pathlib import Path

from crawler.extract.html_extract import extract_html_document
from crawler.extract.trafilatura_extract import extract_article_text
from crawler.extract.unstructured_extract import extract_document_blocks


def test_extract_html_document_collects_title_and_markdown() -> None:
    html = """
    <html lang="en">
      <head>
        <title>Example Page</title>
        <meta name="description" content="Short description">
      </head>
      <body><h1>Hello</h1><p>World</p></body>
    </html>
    """

    result = extract_html_document(html, "https://example.com")

    assert result["metadata"]["title"] == "Example Page"
    assert "Hello" in result["markdown"]


def test_extract_article_text_prefers_trafilatura_for_html(monkeypatch) -> None:
    monkeypatch.setattr(
        "crawler.extract.trafilatura_extract.trafilatura.extract",
        lambda html, **kwargs: "## Extracted article",
    )

    result = extract_article_text("<html><body><article>Hello</article></body></html>", "https://example.com")

    assert result["markdown"] == "## Extracted article"
    assert result["plain_text"] == "## Extracted article"
    assert result["extractor"] == "trafilatura"


def test_extract_article_text_skips_trafilatura_for_non_html_content_type(monkeypatch) -> None:
    def fail_extract(*args, **kwargs):  # pragma: no cover - defensive in test
        raise AssertionError("trafilatura should not be called for non-html content")

    monkeypatch.setattr("crawler.extract.trafilatura_extract.trafilatura.extract", fail_extract)

    result = extract_article_text(
        "<html><head><title>Fallback</title></head><body><p>Plain</p></body></html>",
        "https://example.com",
        content_type="application/pdf",
    )

    assert result["metadata"]["title"] == "Fallback"
    assert "Plain" in result["plain_text"]
    assert result["extractor"] == "html"


def test_extract_document_blocks_only_partitions_documents(monkeypatch, workspace_tmp_path: Path) -> None:
    source_path = workspace_tmp_path / "doc.pdf"
    source_path.write_bytes(b"fake-pdf")

    class FakeElement:
        def __str__(self) -> str:
            return "Section text"

    FakeElement.__name__ = "Title"

    monkeypatch.setattr(
        "crawler.extract.unstructured_extract.partition",
        lambda filename: [FakeElement()],
    )

    result = extract_document_blocks(str(source_path), content_type="application/pdf")

    assert result["document_blocks"][0]["text"] == "Section text"
    assert result["plain_text"] == "Section text"
    assert result["extractor"] == "unstructured"
