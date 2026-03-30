from __future__ import annotations

from crawler.discovery.url_builder import build_url


def test_build_url_for_arxiv_paper() -> None:
    result = build_url({"platform": "arxiv", "resource_type": "paper", "arxiv_id": "2401.12345"})
    assert result["canonical_url"] == "https://arxiv.org/abs/2401.12345"
    assert result["artifacts"]["pdf_url"] == "https://arxiv.org/pdf/2401.12345.pdf"


def test_build_url_for_linkedin_profile() -> None:
    result = build_url(
        {
            "platform": "linkedin",
            "resource_type": "profile",
            "public_identifier": "john-doe-ai",
        }
    )
    assert result["canonical_url"] == "https://www.linkedin.com/in/john-doe-ai/"


def test_build_url_for_linkedin_search() -> None:
    result = build_url(
        {
            "platform": "linkedin",
            "resource_type": "search",
            "query": "openai engineer",
            "search_type": "job",
        }
    )
    assert result["canonical_url"] == "https://www.linkedin.com/search/results/jobs/?keywords=openai%20engineer"


def test_build_url_normalizes_wikipedia_title() -> None:
    result = build_url(
        {
            "platform": "wikipedia",
            "resource_type": "article",
            "title": "Artificial intelligence",
        }
    )
    assert result["canonical_url"].endswith("/Artificial_intelligence")


def test_build_url_encodes_amazon_search_query() -> None:
    result = build_url(
        {
            "platform": "amazon",
            "resource_type": "search",
            "query": "wireless mouse",
        }
    )
    assert result["canonical_url"] == "https://www.amazon.com/s?k=wireless%20mouse"


def test_build_url_for_generic_page_uses_input_url_verbatim() -> None:
    result = build_url(
        {
            "platform": "generic",
            "resource_type": "page",
            "url": "https://www.notion.so/example-page",
        }
    )

    assert result["canonical_url"] == "https://www.notion.so/example-page"
    assert result["fields"]["url"] == "https://www.notion.so/example-page"
