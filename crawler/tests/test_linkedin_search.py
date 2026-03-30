from __future__ import annotations

from crawler.platforms import linkedin


def test_linkedin_search_extracts_company_results_from_html() -> None:
    html = """
    <html>
      <body>
        <div class="search-result">
          <a href="/company/openai/">OpenAI</a>
          <div>AI research company</div>
        </div>
        <div class="search-result">
          <a href="/company/anthropic/">Anthropic</a>
          <div>AI safety company</div>
        </div>
      </body>
    </html>
    """

    extracted = linkedin._extract_linkedin_search(
        {"platform": "linkedin", "resource_type": "search", "query": "openai", "search_type": "company"},
        {"url": "https://www.linkedin.com/search/results/companies/?keywords=openai", "html": html, "content_type": "text/html"},
    )

    results = extracted["structured"]["linkedin"]["results"]
    assert extracted["metadata"]["result_count"] == 2
    assert results[0]["resource_type"] == "company"
    assert results[0]["identifier"] == "openai"
    assert results[0]["discovery_input"]["company_slug"] == "openai"


def test_linkedin_search_filters_results_by_search_type() -> None:
    html = """
    <html>
      <body>
        <div><a href="/company/openai/">OpenAI</a><div>Company</div></div>
        <div><a href="/in/sam-altman/">Sam Altman</a><div>Profile</div></div>
        <div><a href="/jobs/view/123456/">Research Engineer</a><div>Job</div></div>
      </body>
    </html>
    """

    extracted = linkedin._extract_linkedin_search(
        {"platform": "linkedin", "resource_type": "search", "query": "openai", "search_type": "profile"},
        {"url": "https://www.linkedin.com/search/results/people/?keywords=openai", "html": html, "content_type": "text/html"},
    )

    results = extracted["structured"]["linkedin"]["results"]
    assert len(results) == 1
    assert results[0]["resource_type"] == "profile"
    assert results[0]["identifier"] == "sam-altman"


def test_linkedin_search_returns_empty_results_without_exception() -> None:
    extracted = linkedin._extract_linkedin_search(
        {"platform": "linkedin", "resource_type": "search", "query": "nothing", "search_type": "job"},
        {"url": "https://www.linkedin.com/search/results/jobs/?keywords=nothing", "html": "<html><body>No matches</body></html>", "content_type": "text/html"},
    )

    assert extracted["structured"]["linkedin"]["results"] == []
    assert extracted["metadata"]["result_count"] == 0
