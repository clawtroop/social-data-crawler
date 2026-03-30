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


def test_extract_html_document_excludes_hidden_modal_text() -> None:
    html = """
    <html lang="en">
      <head>
        <title>Example Page</title>
      </head>
      <body>
        <div style="display:none">
          <div class="details-panel">
            This hidden modal contains a lot of text that should not leak into
            extracted plain text or markdown even when it is very long.
          </div>
        </div>
        <main>
          <h1>Hello</h1>
          <p>World</p>
        </main>
      </body>
    </html>
    """

    result = extract_html_document(html, "https://example.com")

    assert "should not leak" not in result["plain_text"]
    assert "should not leak" not in result["markdown"]
    assert "Hello" in result["plain_text"]


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


def test_extract_document_blocks_returns_empty_for_missing_file() -> None:
    result = extract_document_blocks("/nonexistent/path.pdf", content_type="application/pdf")

    assert result["document_blocks"] == []
    assert result["plain_text"] == ""
    assert result["extractor"] == "none"
    assert result["extraction_skipped_reason"] == "file_not_found"


def test_extract_document_blocks_returns_empty_for_unsupported_content_type(workspace_tmp_path: Path) -> None:
    source_path = workspace_tmp_path / "doc.txt"
    source_path.write_text("plain text")

    result = extract_document_blocks(str(source_path), content_type="text/plain")

    assert result["document_blocks"] == []
    assert result["extractor"] == "none"
    assert "unsupported" in result["extraction_skipped_reason"]


def test_extract_document_blocks_with_pypdf(monkeypatch, workspace_tmp_path: Path) -> None:
    source_path = workspace_tmp_path / "doc.pdf"
    source_path.write_bytes(b"fake-pdf")

    # Mock pypdf
    class FakePage:
        def extract_text(self):
            return "Page content"

    class FakeReader:
        pages = [FakePage()]

    monkeypatch.setattr(
        "crawler.extract.unstructured_extract._HAS_PYPDF",
        True,
    )
    monkeypatch.setattr(
        "crawler.extract.unstructured_extract.PdfReader",
        lambda path: FakeReader(),
    )

    result = extract_document_blocks(str(source_path), content_type="application/pdf")

    assert result["document_blocks"][0]["text"] == "Page content"
    assert result["plain_text"] == "Page content"
    assert result["extractor"] == "pypdf"
