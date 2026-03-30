"""Tests for the Layer 2 Extract Pipeline."""
from __future__ import annotations

import json
from pathlib import Path

from crawler.extract.content_cleaner import ContentCleaner
from crawler.extract.main_content import MainContentExtractor
from crawler.extract.chunking.hybrid_chunker import HybridChunker, _estimate_tokens
from crawler.extract.structured.json_extractor import JsonExtractor
from crawler.extract.pipeline import ExtractPipeline
from crawler.extract.models import MainContent, ContentSection


# ---------------------------------------------------------------------------
# ContentCleaner tests
# ---------------------------------------------------------------------------


def test_cleaner_removes_script_and_style_tags() -> None:
    html = """
    <html><body>
      <script>alert('x')</script>
      <style>.foo{color:red}</style>
      <p>Real content here</p>
    </body></html>
    """
    cleaner = ContentCleaner()
    result = cleaner.clean(html)
    assert "<script>" not in result.html
    assert "<style>" not in result.html
    assert "Real content here" in result.html
    assert result.noise_removed >= 2


def test_cleaner_removes_nav_footer_aside() -> None:
    html = """
    <html><body>
      <nav>Menu stuff</nav>
      <main><p>Main content</p></main>
      <footer>Footer stuff</footer>
      <aside>Sidebar</aside>
    </body></html>
    """
    cleaner = ContentCleaner()
    result = cleaner.clean(html)
    assert "Menu stuff" not in result.html
    assert "Footer stuff" not in result.html
    assert "Sidebar" not in result.html
    assert "Main content" in result.html


def test_cleaner_removes_noise_class_patterns() -> None:
    html = """
    <html><body>
      <div class="ad-banner">Ad here</div>
      <div class="sidebar-widget">Widget</div>
      <p>Article text</p>
    </body></html>
    """
    cleaner = ContentCleaner()
    result = cleaner.clean(html)
    assert "Ad here" not in result.html
    assert "Article text" in result.html


def test_cleaner_removes_hidden_elements() -> None:
    html = """
    <html><body>
      <div hidden>Hidden div</div>
      <div style="display: none">Invisible div</div>
      <p>Visible content</p>
    </body></html>
    """
    cleaner = ContentCleaner()
    result = cleaner.clean(html)
    assert "Hidden div" not in result.html
    assert "Invisible div" not in result.html
    assert "Visible content" in result.html


def test_cleaner_handles_decomposed_nested_noise_nodes() -> None:
    html = """
    <html><body>
      <div class="sidebar">
        <span>Nested noise</span>
      </div>
      <p>Visible content</p>
    </body></html>
    """
    cleaner = ContentCleaner()
    result = cleaner.clean(html)
    assert "Nested noise" not in result.html
    assert "Visible content" in result.html


def test_cleaner_uses_platform_selectors(monkeypatch) -> None:
    html = """
    <html><body>
      <div class="global-nav">LinkedIn Nav</div>
      <p>Profile content</p>
    </body></html>
    """
    monkeypatch.setattr(
        "crawler.extract.content_cleaner._platform_selectors_cache",
        {"linkedin": [".global-nav"]},
    )
    cleaner = ContentCleaner()
    result = cleaner.clean(html, platform="linkedin")
    assert "LinkedIn Nav" not in result.html
    assert "Profile content" in result.html


def test_cleaner_tracks_original_and_cleaned_size() -> None:
    html = "<html><body><script>x</script><p>Text</p></body></html>"
    cleaner = ContentCleaner()
    result = cleaner.clean(html)
    assert result.original_size == len(html)
    assert result.cleaned_size < result.original_size


# ---------------------------------------------------------------------------
# MainContentExtractor tests
# ---------------------------------------------------------------------------


def test_main_extractor_finds_article_tag() -> None:
    from bs4 import BeautifulSoup

    html = """
    <html><body>
      <div id="wrapper">
        <article>
          <h1>Article Title</h1>
          <p>Article paragraph with enough text to pass the 50 char threshold for semantic detection.</p>
        </article>
      </div>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    extractor = MainContentExtractor()
    result = extractor.extract(soup)
    assert "Article Title" in result.text
    assert "semantic:article" == result.selector_used


def test_main_extractor_falls_back_to_density() -> None:
    from bs4 import BeautifulSoup

    html = """
    <html><body>
      <div id="content">
        <p>This is a longer paragraph with sufficient content for density analysis.
        It contains multiple sentences that should give it a high density score
        compared to other elements on the page. The density algorithm looks at
        the ratio of text to HTML markup.</p>
      </div>
      <div id="small"><span>x</span></div>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    extractor = MainContentExtractor()
    result = extractor.extract(soup)
    assert "density" in result.selector_used or "fallback" in result.selector_used


def test_main_extractor_uses_platform_selector(monkeypatch) -> None:
    from bs4 import BeautifulSoup

    monkeypatch.setattr(
        "crawler.extract.main_content._main_content_selectors_cache",
        {"wikipedia": {"article": "#mw-content-text"}},
    )
    html = """
    <html><body>
      <div id="mw-content-text">
        <p>Wikipedia article content here.</p>
      </div>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    extractor = MainContentExtractor()
    result = extractor.extract(soup, platform="wikipedia", resource_type="article")
    assert "Wikipedia article content" in result.text
    assert "platform:" in result.selector_used


def test_main_extractor_extracts_sections_from_headings() -> None:
    from bs4 import BeautifulSoup

    html = """
    <html><body>
      <article>
        <h1>Main Title</h1>
        <p>Intro paragraph with enough text content here to be meaningful.</p>
        <h2>Section One</h2>
        <p>Content for section one.</p>
        <h2>Section Two</h2>
        <p>Content for section two.</p>
        <h3>Subsection 2.1</h3>
        <p>Nested content.</p>
      </article>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    extractor = MainContentExtractor()
    result = extractor.extract(soup)
    assert len(result.sections) >= 3
    # Check section_path hierarchy: h1 > h2 > h3 gives 3-level path
    sub_sections = [s for s in result.sections if s.heading_level == 3]
    if sub_sections:
        assert len(sub_sections[0].section_path) == 3
        assert sub_sections[0].section_path[-1] == "Subsection 2.1"


# ---------------------------------------------------------------------------
# HybridChunker tests
# ---------------------------------------------------------------------------


def test_estimate_tokens_basic() -> None:
    assert _estimate_tokens("hello world") == 2
    assert _estimate_tokens("") == 0


def test_chunker_small_section_single_chunk() -> None:
    sections = [
        ContentSection(
            heading_text="Title",
            heading_level=1,
            section_path=["Title"],
            html="<h1>Title</h1><p>Short text</p>",
            text="Short text",
            markdown="# Title\n\nShort text",
            char_offset_start=0,
            char_offset_end=10,
        )
    ]
    main = MainContent(
        html="<h1>Title</h1><p>Short text</p>",
        text="Short text",
        markdown="# Title\n\nShort text",
        sections=sections,
        selector_used="test",
    )
    chunker = HybridChunker(max_chunk_tokens=512)
    chunks = chunker.chunk(main, doc_id="test-doc")
    assert len(chunks) == 1
    assert chunks[0].section_path == ["Title"]
    assert chunks[0].chunk_id == "test-doc#chunk_0"


def test_chunker_large_section_splits() -> None:
    # Create a section with 1000+ tokens
    long_text = " ".join(f"word{i}" for i in range(600))
    sections = [
        ContentSection(
            heading_text="Big Section",
            heading_level=1,
            section_path=["Big Section"],
            html=f"<p>{long_text}</p>",
            text=long_text,
            markdown=long_text,
            char_offset_start=0,
            char_offset_end=len(long_text),
        )
    ]
    main = MainContent(
        html=f"<p>{long_text}</p>",
        text=long_text,
        markdown=long_text,
        sections=sections,
        selector_used="test",
    )
    chunker = HybridChunker(max_chunk_tokens=200, min_chunk_tokens=50)
    chunks = chunker.chunk(main, doc_id="test-doc")
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.section_path == ["Big Section"]
        assert chunk.token_count_estimate > 0


def test_chunker_preserves_section_path() -> None:
    sections = [
        ContentSection(
            heading_text="A",
            heading_level=1,
            section_path=["A"],
            html="", text="Content A", markdown="Content A",
            char_offset_start=0, char_offset_end=9,
        ),
        ContentSection(
            heading_text="B",
            heading_level=2,
            section_path=["A", "B"],
            html="", text="Content B", markdown="Content B",
            char_offset_start=10, char_offset_end=19,
        ),
    ]
    main = MainContent(
        html="", text="Content A\nContent B", markdown="Content A\nContent B",
        sections=sections, selector_used="test",
    )
    chunker = HybridChunker()
    chunks = chunker.chunk(main, doc_id="doc1")
    assert chunks[0].section_path == ["A"]
    assert chunks[1].section_path == ["A", "B"]


def test_chunker_empty_content_returns_empty() -> None:
    main = MainContent(html="", text="", markdown="", sections=[], selector_used="test")
    chunker = HybridChunker()
    chunks = chunker.chunk(main, doc_id="empty")
    assert chunks == []


# ---------------------------------------------------------------------------
# JsonExtractor tests
# ---------------------------------------------------------------------------


def test_json_extractor_linkedin_profile() -> None:
    data = {
        "included": [
            {
                "$type": "com.linkedin.voyager.dash.identity.profile.Profile",
                "firstName": "John",
                "lastName": "Doe",
                "headline": "Software Engineer",
                "publicIdentifier": "johndoe",
                "entityUrn": "urn:li:fsd_profile:123",
            }
        ]
    }
    extractor = JsonExtractor()
    result = extractor.extract_from_json(data, "linkedin", "profile", "https://linkedin.com/in/johndoe")
    assert result.title == "John Doe"
    assert result.description == "Software Engineer"
    assert result.platform_fields["public_identifier"] == "johndoe"
    assert result.field_sources["title"] == "api_json:voyager"


def test_json_extractor_linkedin_company() -> None:
    data = {
        "included": [
            {
                "$type": "com.linkedin.voyager.dash.organization.Company",
                "name": "Acme Inc",
                "description": "We build stuff",
                "universalName": "acme-inc",
                "staffCount": 500,
                "industries": ["Technology"],
            }
        ]
    }
    extractor = JsonExtractor()
    result = extractor.extract_from_json(data, "linkedin", "company", "https://linkedin.com/company/acme-inc")
    assert result.title == "Acme Inc"
    assert result.description == "We build stuff"
    assert result.platform_fields["staff_count"] == 500


def test_json_extractor_generic_json() -> None:
    data = {"title": "Test Item", "description": "A test description", "extra": "value"}
    extractor = JsonExtractor()
    result = extractor.extract_from_json(data, "custom", "item", "https://example.com/item/1")
    assert result.title == "Test Item"
    assert result.description == "A test description"


def test_json_extractor_html_meta() -> None:
    html = """
    <html>
      <head>
        <title>Page Title</title>
        <meta property="og:title" content="OG Title">
        <meta property="og:description" content="OG Desc">
        <meta property="og:image" content="/img.png">
        <link rel="canonical" href="https://example.com/canonical">
      </head>
      <body></body>
    </html>
    """
    extractor = JsonExtractor()
    result = extractor.extract_from_html(html, "test", "page", "https://example.com/page")
    assert result.title == "OG Title"
    assert result.description == "OG Desc"
    assert result.canonical_url == "https://example.com/canonical"
    assert result.field_sources["title"] == "html_meta:og:title"


# ---------------------------------------------------------------------------
# ExtractPipeline integration tests
# ---------------------------------------------------------------------------


def test_pipeline_html_extraction() -> None:
    fetch_result = {
        "url": "https://en.wikipedia.org/wiki/Python",
        "text": """
        <html>
          <head>
            <title>Python - Wikipedia</title>
            <meta name="description" content="Python is a programming language">
          </head>
          <body>
            <nav>Navigation menu</nav>
            <article>
              <h1>Python (programming language)</h1>
              <p>Python is a high-level, general-purpose programming language.
              Its design philosophy emphasizes code readability with the use of
              significant indentation.</p>
              <h2>History</h2>
              <p>Python was conceived in the late 1980s by Guido van Rossum
              at Centrum Wiskunde &amp; Informatica in the Netherlands.</p>
              <h2>Features</h2>
              <p>Python is dynamically typed and garbage-collected. It supports
              multiple programming paradigms.</p>
            </article>
            <footer>Footer content</footer>
          </body>
        </html>
        """,
        "content_type": "text/html",
    }

    pipeline = ExtractPipeline()
    doc = pipeline.extract(fetch_result, "wikipedia", "article")

    assert doc.platform == "wikipedia"
    assert doc.resource_type == "article"
    assert doc.source_url == "https://en.wikipedia.org/wiki/Python"
    assert "Python" in doc.full_text
    assert doc.total_chunks == len(doc.chunks)
    assert doc.total_chunks > 0
    assert doc.quality.noise_removed > 0
    assert doc.structured.title is not None
    # Check chunks have section paths
    for chunk in doc.chunks:
        assert chunk.chunk_id.startswith(doc.doc_id)
        assert chunk.token_count_estimate > 0


def test_pipeline_json_extraction() -> None:
    fetch_result = {
        "url": "https://www.linkedin.com/in/johndoe",
        "json_data": {
            "included": [
                {
                    "$type": "com.linkedin.voyager.dash.identity.profile.Profile",
                    "firstName": "John",
                    "lastName": "Doe",
                    "headline": "Software Engineer at BigCo",
                    "publicIdentifier": "johndoe",
                    "entityUrn": "urn:li:fsd_profile:abc123",
                }
            ]
        },
        "content_type": "application/json",
    }

    pipeline = ExtractPipeline()
    doc = pipeline.extract(fetch_result, "linkedin", "profile")

    assert doc.platform == "linkedin"
    assert doc.structured.title == "John Doe"
    assert doc.structured.description == "Software Engineer at BigCo"
    assert doc.total_chunks > 0
    assert doc.quality.chunking_strategy == "json_structured"


def test_pipeline_json_extraction_wikipedia_has_title_text_markdown_and_structure() -> None:
    fetch_result = {
        "url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
        "json_data": {
            "query": {
                "pages": {
                    "1164": {
                        "title": "Artificial intelligence",
                        "extract": "Artificial intelligence is the capability of computational systems to perform tasks associated with human intelligence.",
                        "categories": [
                            {"title": "Category:Artificial intelligence"},
                            {"title": "Category:Computer science"},
                        ],
                        "pageprops": {"wikibase-shortdesc": "Intelligence of machines"},
                    }
                }
            }
        },
        "content_type": "application/json",
    }

    pipeline = ExtractPipeline()
    doc = pipeline.extract(fetch_result, "wikipedia", "article")

    assert doc.structured.title == "Artificial intelligence"
    assert "computational systems" in doc.full_text
    assert doc.full_markdown.startswith("# Artificial intelligence")
    assert doc.structured.platform_fields["categories"] == ["Artificial intelligence", "Computer science"]


def test_pipeline_json_extraction_base_has_meaningful_output() -> None:
    fetch_result = {
        "url": "https://basescan.org/address/0x4200000000000000000000000000000000000006",
        "json_data": {
            "jsonrpc": "2.0",
            "result": "0x360fe4a3fc66beffcabd",
            "id": 1,
        },
        "content_type": "application/json",
    }

    pipeline = ExtractPipeline()
    doc = pipeline.extract(fetch_result, "base", "address")

    assert doc.structured.title == "address"
    assert "0x360fe4a3fc66beffcabd" in doc.full_text
    assert "```json" in doc.full_markdown
    assert doc.structured.platform_fields["rpc_result"] == "0x360fe4a3fc66beffcabd"


def test_pipeline_json_extraction_linkedin_company_uses_voyager_shape() -> None:
    fetch_result = {
        "url": "https://www.linkedin.com/company/openai/",
        "json_data": {
            "elements": [
                {
                    "$recipeType": "com.linkedin.voyager.deco.organization.web.WebFullCompanyMain",
                    "name": "OpenAI",
                    "description": "OpenAI is an AI research and deployment company.",
                    "entityUrn": "urn:li:fs_normalized_company:11130470",
                    "universalName": "openai",
                    "staffCount": 7722,
                    "companyIndustries": [{"localizedName": "软件开发"}],
                    "headquarter": {"city": "San Francisco"},
                    "followingInfo": {"followerCount": 10478857},
                    "companyPageUrl": "https://openai.com/",
                    "specialities": ["artificial intelligence", "machine learning"],
                }
            ]
        },
        "content_type": "application/json",
    }

    pipeline = ExtractPipeline()
    doc = pipeline.extract(fetch_result, "linkedin", "company")

    assert doc.structured.title == "OpenAI"
    assert "AI research and deployment company" in doc.full_text
    assert doc.full_markdown.startswith("# OpenAI")
    assert doc.structured.platform_fields["company_slug"] == "openai"
    assert doc.structured.platform_fields["follower_count"] == 10478857


def test_pipeline_html_extraction_compacts_llm_ready_content() -> None:
    fetch_result = {
        "url": "https://example.com/post",
        "text": """
        <html>
          <body>
            <article>
              <h1>Intentional Systems</h1>
              <p>Sign in to keep reading</p>
              <p>Intentional systems are built around clear interfaces and strong feedback loops.</p>
              <p>Intentional systems are built around clear interfaces and strong feedback loops.</p>
              <p>Teams use them to reduce ambiguity and operational drift over time.</p>
              <ul>
                <li>Clear ownership</li>
                <li>Fast feedback</li>
              </ul>
              <p>Share this article</p>
              <p>All rights reserved</p>
            </article>
          </body>
        </html>
        """,
        "content_type": "text/html",
    }

    pipeline = ExtractPipeline()
    doc = pipeline.extract(fetch_result, "test", "page")

    assert "Sign in to keep reading" not in doc.full_text
    assert "Share this article" not in doc.full_text
    assert "All rights reserved" not in doc.full_text
    assert doc.full_text.count("Intentional systems are built around clear interfaces and strong feedback loops.") == 1
    assert "# Intentional Systems" in doc.full_markdown
    assert "Clear ownership" in doc.full_markdown
    assert "Fast feedback" in doc.full_markdown
    assert doc.cleaned_html
    assert "Share this article" not in doc.cleaned_html
    assert "All rights reserved" not in doc.cleaned_html


def test_pipeline_html_extraction_applies_css_schema_when_configured(workspace_tmp_path: Path) -> None:
    schema_path = workspace_tmp_path / "css-schema.json"
    schema_path.write_text(
        json.dumps(
            {
                "title": {"selector": ".hero-title"},
                "description": {"selector": ".hero-subtitle"},
                "fields": {
                    "price": {"selector": ".price"},
                    "features": {"selector": ".feature", "multiple": True},
                    "checkout_url": {"selector": ".cta", "attribute": "href"},
                },
            }
        ),
        encoding="utf-8",
    )
    fetch_result = {
        "url": "https://example.com/product",
        "text": """
        <html>
          <head>
            <title>Fallback Title</title>
            <meta name="description" content="Fallback description">
          </head>
          <body>
            <article>
              <h1 class="hero-title">Structured Product</h1>
              <p class="hero-subtitle">Made for deterministic extraction.</p>
              <div class="price">$19</div>
              <ul>
                <li class="feature">Fast setup</li>
                <li class="feature">Clear output</li>
              </ul>
              <a class="cta" href="/checkout">Buy now</a>
            </article>
          </body>
        </html>
        """,
        "content_type": "text/html",
    }

    pipeline = ExtractPipeline(css_schema_path=schema_path)
    doc = pipeline.extract(fetch_result, "test", "page")

    assert doc.structured.title == "Structured Product"
    assert doc.structured.description == "Made for deterministic extraction."
    assert doc.structured.platform_fields["price"] == "$19"
    assert doc.structured.platform_fields["features"] == ["Fast setup", "Clear output"]
    assert doc.structured.platform_fields["checkout_url"] == "https://example.com/checkout"


def test_pipeline_html_extraction_applies_llm_schema_when_configured(monkeypatch, workspace_tmp_path: Path) -> None:
    schema_path = workspace_tmp_path / "extract-llm-schema.json"
    schema_path.write_text(
        json.dumps({"schema_name": "extract-product", "instruction": "Extract product fields"}),
        encoding="utf-8",
    )
    fetch_result = {
        "url": "https://example.com/product",
        "text": """
        <html>
          <body>
            <article>
              <h1>Fallback Product</h1>
              <p>Compact source text for schema extraction.</p>
            </article>
          </body>
        </html>
        """,
        "content_type": "text/html",
    }

    async def fake_execute(self, payload: dict) -> dict:
        return {
            "success": True,
            "data": {
                "title": "LLM Product",
                "description": "Generated by schema extraction.",
                "fields": {"price": "$29", "sku": "SKU-29"},
            },
            "schema_name": "extract-product",
        }

    monkeypatch.setattr(
        "crawler.extract.structured.llm_schema_extractor.LLMSchemaExtractor.execute",
        fake_execute,
    )

    pipeline = ExtractPipeline(extract_llm_schema_path=schema_path, model_config={"model": "test-model", "base_url": "https://api.example.com"})
    doc = pipeline.extract(fetch_result, "test", "page")

    assert doc.structured.title == "LLM Product"
    assert doc.structured.description == "Generated by schema extraction."
    assert doc.structured.platform_fields["price"] == "$29"
    assert doc.structured.platform_fields["sku"] == "SKU-29"
    assert doc.structured.field_sources["price"] == "llm_schema:extract-product"


def test_pipeline_legacy_output() -> None:
    fetch_result = {
        "url": "https://example.com/page",
        "text": "<html><head><title>Test</title></head><body><article><p>Hello world content paragraph.</p></article></body></html>",
        "content_type": "text/html",
    }
    pipeline = ExtractPipeline()
    result = pipeline.extract_to_legacy(fetch_result, "test", "page")

    assert "metadata" in result
    assert "markdown" in result
    assert "plain_text" in result
    assert result["extractor"] == "extract_pipeline"
    assert "extract_document" in result


def test_pipeline_to_dict_serializable() -> None:
    fetch_result = {
        "url": "https://example.com",
        "text": "<html><body><article><h1>Title</h1><p>Body text content.</p></article></body></html>",
        "content_type": "text/html",
    }
    pipeline = ExtractPipeline()
    doc = pipeline.extract(fetch_result, "test", "page")
    d = doc.to_dict()

    assert isinstance(d, dict)
    assert d["platform"] == "test"
    assert isinstance(d["chunks"], list)
    assert isinstance(d["quality"], dict)
    assert isinstance(d["structured"], dict)


def test_pipeline_empty_html() -> None:
    fetch_result = {
        "url": "https://example.com/empty",
        "text": "<html><body></body></html>",
        "content_type": "text/html",
    }
    pipeline = ExtractPipeline()
    doc = pipeline.extract(fetch_result, "test", "page")
    assert doc.total_chunks == 0
    assert doc.full_text == ""
