from __future__ import annotations

import json
from pathlib import Path

from crawler.platforms import linkedin, wikipedia
from crawler.platforms.base import hook_normalizer
from crawler.platforms.registry import get_platform_adapter
from crawler.platforms.registry import list_platform_adapters


def test_wikipedia_adapter_declares_article_support() -> None:
    adapter = get_platform_adapter("wikipedia")
    assert adapter.platform == "wikipedia"
    assert "article" in adapter.supported_resource_types
    assert adapter.default_backend == "api"


def test_wikipedia_extract_includes_page_id_in_metadata() -> None:
    extracted = wikipedia._extract_wikipedia(
        {"platform": "wikipedia", "resource_type": "article", "title": "Artificial intelligence"},
        {
            "url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
            "content_type": "application/json",
            "json_data": {
                "query": {
                    "pages": {
                        "1164": {
                            "pageid": 1164,
                            "title": "Artificial intelligence",
                            "extract": "Artificial intelligence is the capability of computational systems.",
                            "categories": [{"title": "Category:Artificial intelligence"}],
                            "pageprops": {"wikibase-shortdesc": "Intelligence of machines"},
                        }
                    }
                }
            },
        },
    )

    assert extracted["metadata"]["page_id"] == "1164"


def test_wikipedia_normalizer_maps_page_id_for_submission_schema() -> None:
    normalizer = hook_normalizer("wikipedia")

    normalized = normalizer(
        {"platform": "wikipedia", "resource_type": "article", "title": "Artificial intelligence"},
        {"fields": {"title": "Artificial_intelligence"}},
        {
            "metadata": {
                "title": "Artificial intelligence",
                "page_id": "1164",
            },
            "plain_text": "Artificial intelligence is the capability of computational systems.",
        },
        {},
    )

    assert normalized["title"] == "Artificial intelligence"
    assert normalized["page_id"] == "1164"


def test_linkedin_adapter_requires_auth_and_browser() -> None:
    adapter = get_platform_adapter("linkedin")
    assert adapter.requires_auth is True
    assert adapter.default_backend == "api"
    assert "profile" in adapter.supported_resource_types
    assert "search" in adapter.supported_resource_types


def test_registry_lists_all_known_adapters() -> None:
    platforms = {adapter.platform for adapter in list_platform_adapters()}

    assert platforms == {"wikipedia", "arxiv", "amazon", "base", "linkedin", "generic"}


def test_generic_adapter_declares_page_support_with_http_default() -> None:
    adapter = get_platform_adapter("generic")

    assert adapter.platform == "generic"
    assert adapter.supported_resource_types == ("page",)
    assert adapter.requires_auth is False
    assert adapter.default_backend == "http"

    assert adapter.resolve_backend(
        {"platform": "generic", "resource_type": "page", "url": "https://example.com"},
        None,
        retry_count=0,
    ) == "http"
    assert adapter.resolve_backend(
        {"platform": "generic", "resource_type": "page", "url": "https://example.com"},
        None,
        retry_count=1,
    ) == "playwright"
    assert adapter.resolve_backend(
        {"platform": "generic", "resource_type": "page", "url": "https://example.com"},
        None,
        retry_count=2,
    ) == "camoufox"


def test_linkedin_headers_preserve_ajax_prefixed_jsessionid(workspace_tmp_path: Path) -> None:
    storage_state_path = workspace_tmp_path / "linkedin.json"
    storage_state_path.write_text(
        json.dumps(
            {
                "cookies": [
                    {"name": "li_at", "value": "secret-token", "domain": ".linkedin.com", "path": "/"},
                    {"name": "JSESSIONID", "value": '"ajax:123"', "domain": ".linkedin.com", "path": "/"},
                    {"name": "lang", "value": "v=2&lang=zh-cn", "domain": ".linkedin.com", "path": "/"},
                ],
                "origins": [],
            }
        ),
        encoding="utf-8",
    )

    headers = linkedin._storage_state_headers(str(storage_state_path), None, {"canonical_url": "https://www.linkedin.com/"})

    assert headers["csrf-token"] == "ajax:123"
    assert headers["x-li-lang"] == "zh_CN"
    assert "li_at=secret-token" in headers["Cookie"]


def test_linkedin_company_fetch_uses_browser_verified_detail_query(monkeypatch, workspace_tmp_path: Path) -> None:
    storage_state_path = workspace_tmp_path / "linkedin.json"
    storage_state_path.write_text(
        json.dumps(
            {
                "cookies": [
                    {"name": "li_at", "value": "secret-token", "domain": ".linkedin.com", "path": "/"},
                    {"name": "JSESSIONID", "value": '"ajax:123"', "domain": ".linkedin.com", "path": "/"},
                ],
                "origins": [],
            }
        ),
        encoding="utf-8",
    )
    calls: list[dict] = []

    def fake_fetch(*, canonical_url: str, api_endpoint: str, headers: dict[str, str] | None = None, timeout: float = 30.0) -> dict:
        calls.append({"canonical_url": canonical_url, "api_endpoint": api_endpoint, "headers": headers or {}})
        return {
            "url": canonical_url,
            "api_endpoint": api_endpoint,
            "content_type": "application/json",
            "json_data": {"included": [{"$type": "com.linkedin.voyager.organization.Company", "name": "OpenAI"}]},
        }

    monkeypatch.setattr("crawler.platforms.linkedin.fetch_api_get", fake_fetch)

    linkedin._fetch_linkedin_api(
        {"platform": "linkedin", "resource_type": "company", "company_slug": "openai"},
        {"canonical_url": "https://www.linkedin.com/company/openai/"},
        str(storage_state_path),
    )

    assert len(calls) == 1
    assert calls[0]["api_endpoint"].startswith("https://www.linkedin.com/voyager/api/organization/companies")
    assert "q=universalName" in calls[0]["api_endpoint"]
    assert "universalName=openai" in calls[0]["api_endpoint"]
    assert "decorationId=com.linkedin.voyager.deco.organization.web.WebFullCompanyMain-12" in calls[0]["api_endpoint"]


def test_linkedin_profile_fetch_uses_browser_verified_profile_query(monkeypatch, workspace_tmp_path: Path) -> None:
    storage_state_path = workspace_tmp_path / "linkedin.json"
    storage_state_path.write_text(
        json.dumps(
            {
                "cookies": [
                    {"name": "li_at", "value": "secret-token", "domain": ".linkedin.com", "path": "/"},
                    {"name": "JSESSIONID", "value": '"ajax:123"', "domain": ".linkedin.com", "path": "/"},
                ],
                "origins": [],
            }
        ),
        encoding="utf-8",
    )
    calls: list[dict] = []

    def fake_fetch(*, canonical_url: str, api_endpoint: str, headers: dict[str, str] | None = None, timeout: float = 30.0) -> dict:
        calls.append({"canonical_url": canonical_url, "api_endpoint": api_endpoint, "headers": headers or {}})
        return {
            "url": canonical_url,
            "api_endpoint": api_endpoint,
            "content_type": "application/json",
            "json_data": {"data": {"entityUrn": "urn:li:fsd_profile:ACoAAA"}},
        }

    monkeypatch.setattr("crawler.platforms.linkedin.fetch_api_get", fake_fetch)

    linkedin._fetch_linkedin_api(
        {"platform": "linkedin", "resource_type": "profile", "public_identifier": "satyanadella"},
        {"canonical_url": "https://www.linkedin.com/in/satyanadella/"},
        str(storage_state_path),
    )

    assert len(calls) == 1
    assert "variables=(vanityName:satyanadella)" in calls[0]["api_endpoint"]
    assert "queryId=voyagerIdentityDashProfiles.34ead06db82a2cc9a778fac97f69ad6a" in calls[0]["api_endpoint"]


def test_linkedin_extracts_profile_from_graphql_collection_shape() -> None:
    extracted = linkedin._extract_linkedin_profile(
        {
            "data": {
                "identityDashProfilesByMemberIdentity": {
                    "elements": [
                        {
                            "_type": "com.linkedin.voyager.dash.identity.profile.Profile",
                            "entityUrn": "urn:li:fsd_profile:123",
                            "publicIdentifier": "john-doe-ai",
                            "firstName": "John",
                            "lastName": "Doe",
                            "headline": "AI at Self",
                        }
                    ]
                }
            }
        }
    )

    assert extracted["title"] == "John Doe"
    assert extracted["structured"]["source_id"] == "123"
    assert extracted["structured"]["public_identifier"] == "john-doe-ai"
    assert extracted["structured"]["headline"] == "AI at Self"


def test_linkedin_extracts_company_from_top_level_elements_shape() -> None:
    extracted = linkedin._extract_linkedin_company(
        {
            "elements": [
                {
                    "entityUrn": "urn:li:fs_normalized_company:11130470",
                    "name": "OpenAI",
                    "universalName": "openai",
                    "description": "AI research company",
                    "companyIndustries": [{"localizedName": "Research Services"}],
                    "headquarter": {"city": "San Francisco"},
                    "followingInfo": {"followerCount": 123456},
                    "logo": {
                        "image": {
                            "rootUrl": "https://cdn.example.com/",
                            "artifacts": [
                                {"width": 100, "fileIdentifyingUrlPathSegment": "logo-small.png"},
                                {"width": 200, "fileIdentifyingUrlPathSegment": "logo-large.png"},
                            ],
                        }
                    },
                }
            ]
        }
    )

    assert extracted["title"] == "OpenAI"
    assert extracted["structured"]["source_id"] == "11130470"
    assert extracted["structured"]["company_slug"] == "openai"
    assert extracted["structured"]["industry"] == "Research Services"
    assert extracted["structured"]["follower_count"] == 123456
    assert extracted["structured"]["logo_url"] == "https://cdn.example.com/logo-large.png"


def test_linkedin_extracts_company_logo_from_vector_image_wrapper() -> None:
    extracted = linkedin._extract_linkedin_company(
        {
            "elements": [
                {
                    "entityUrn": "urn:li:fs_normalized_company:11130470",
                    "name": "OpenAI",
                    "universalName": "openai",
                    "logo": {
                        "image": {
                            "com.linkedin.common.VectorImage": {
                                "rootUrl": "https://media.licdn.com/dms/image/v2/D560BAQHpzXbqSyR74A/company-logo_",
                                "artifacts": [
                                    {
                                        "width": 100,
                                        "fileIdentifyingUrlPathSegment": "100_100/logo-small.png",
                                    },
                                    {
                                        "width": 400,
                                        "fileIdentifyingUrlPathSegment": "400_400/logo-large.png",
                                    },
                                ],
                            }
                        }
                    },
                }
            ]
        }
    )

    assert (
        extracted["structured"]["logo_url"]
        == "https://media.licdn.com/dms/image/v2/D560BAQHpzXbqSyR74A/company-logo_400_400/logo-large.png"
    )


def test_linkedin_normalizer_preserves_extracted_structured_fields() -> None:
    normalized = linkedin.ADAPTER.normalize_record(
        {"platform": "linkedin", "resource_type": "company", "company_slug": "openai"},
        {"fields": {"company_slug": "openai"}},
        {
            "metadata": {"title": "OpenAI"},
            "structured": {
                "linkedin": {
                    "source_id": "11130470",
                    "title": "OpenAI",
                    "company_slug": "openai",
                    "follower_count": 123456,
                }
            },
        },
        {},
    )

    assert normalized["source_id"] == "11130470"
    assert normalized["company_slug"] == "openai"
    assert normalized["follower_count"] == 123456
    assert normalized["title"] == "OpenAI"


# =============================================================================
# Fallback backend escalation tests
# =============================================================================


def test_non_auth_platform_fallback_escalates_on_retry() -> None:
    """Non-auth platforms (Amazon, Base, Wikipedia) should also escalate to fallback backends on retry."""
    from crawler.platforms.amazon import ADAPTER as amazon_adapter

    # First attempt: default backend (http for Amazon)
    backend_0 = amazon_adapter.resolve_backend({"platform": "amazon", "resource_type": "product"}, None, retry_count=0)
    assert backend_0 == "http"

    # Retry 1: first fallback (playwright)
    backend_1 = amazon_adapter.resolve_backend({"platform": "amazon", "resource_type": "product"}, None, retry_count=1)
    assert backend_1 == "playwright"

    # Retry 2: second fallback (camoufox)
    backend_2 = amazon_adapter.resolve_backend({"platform": "amazon", "resource_type": "product"}, None, retry_count=2)
    assert backend_2 == "camoufox"


def test_amazon_adapter_uses_resource_specific_default_field_groups() -> None:
    from crawler.platforms.amazon import ADAPTER as amazon_adapter

    product_request = amazon_adapter.build_enrichment_request({"platform": "amazon", "resource_type": "product"})
    seller_request = amazon_adapter.build_enrichment_request({"platform": "amazon", "resource_type": "seller"})
    review_request = amazon_adapter.build_enrichment_request({"platform": "amazon", "resource_type": "review"})

    assert product_request["field_groups"] == (
        "amazon_products_identity",
        "amazon_products_pricing",
        "amazon_products_description",
        "amazon_products_category",
        "amazon_products_visual",
        "amazon_products_availability",
        "amazon_products_competition",
        "amazon_products_reviews_summary",
        "amazon_products_variants",
        "amazon_products_compliance",
        "amazon_products_multimodal_images",
        "amazon_products_multi_level_summary",
        "amazon_products_market_positioning",
        "amazon_products_listing_quality",
        "amazon_products_linkable_ids",
    )
    assert seller_request["field_groups"] == (
        "amazon_sellers_identity",
        "amazon_sellers_performance",
        "amazon_sellers_portfolio",
        "amazon_sellers_business_intel",
        "amazon_sellers_multi_level_summary",
        "amazon_sellers_linkable_ids",
    )
    assert review_request["field_groups"] == (
        "amazon_reviews_identity",
        "amazon_reviews_content",
        "amazon_reviews_analysis",
        "amazon_reviews_quality",
        "amazon_reviews_structured",
        "amazon_reviews_media",
        "amazon_reviews_multimodal_images",
        "amazon_reviews_multi_level_summary",
        "amazon_reviews_review_depth",
    )


def test_base_platform_fallback_escalates_on_retry() -> None:
    """Base chain platform should escalate to fallback backends on retry."""
    from crawler.platforms.base_chain import ADAPTER as base_adapter

    # First attempt: default backend (api for base)
    backend_0 = base_adapter.resolve_backend({"platform": "base", "resource_type": "address"}, None, retry_count=0)
    assert backend_0 == "api"

    # Retry 1: first fallback (http)
    backend_1 = base_adapter.resolve_backend({"platform": "base", "resource_type": "address"}, None, retry_count=1)
    assert backend_1 == "http"

    # Retry 2: second fallback (playwright)
    backend_2 = base_adapter.resolve_backend({"platform": "base", "resource_type": "address"}, None, retry_count=2)
    assert backend_2 == "playwright"


def test_base_token_prefers_http_html_flow() -> None:
    from crawler.platforms.base_chain import ADAPTER as base_adapter

    backend_0 = base_adapter.resolve_backend({"platform": "base", "resource_type": "token"}, None, retry_count=0)
    backend_1 = base_adapter.resolve_backend({"platform": "base", "resource_type": "token"}, None, retry_count=1)

    assert backend_0 == "http"
    assert backend_1 == "playwright"


def test_base_contract_prefers_http_html_flow() -> None:
    from crawler.platforms.base_chain import ADAPTER as base_adapter

    backend_0 = base_adapter.resolve_backend({"platform": "base", "resource_type": "contract"}, None, retry_count=0)
    backend_1 = base_adapter.resolve_backend({"platform": "base", "resource_type": "contract"}, None, retry_count=1)

    assert backend_0 == "http"
    assert backend_1 == "playwright"


def test_linkedin_post_escalates_to_camoufox_on_retry() -> None:
    """LinkedIn post should start with playwright and escalate to camoufox on retry."""
    from crawler.platforms.linkedin import _resolve_linkedin_backend, FETCH_PLAN

    # First attempt: playwright for post
    backend_0 = _resolve_linkedin_backend({"resource_type": "post"}, None, retry_count=0)
    assert backend_0 == "playwright"

    # Retry 1: should escalate to first fallback (playwright in FETCH_PLAN.fallback_backends)
    backend_1 = _resolve_linkedin_backend({"resource_type": "post"}, None, retry_count=1)
    assert backend_1 == FETCH_PLAN.fallback_backends[0]  # playwright

    # Retry 2: should escalate to second fallback (camoufox)
    backend_2 = _resolve_linkedin_backend({"resource_type": "post"}, None, retry_count=2)
    assert backend_2 == "camoufox"


def test_linkedin_profile_escalates_to_camoufox_on_retry() -> None:
    """LinkedIn profile should start with api and escalate through fallback chain on retry."""
    from crawler.platforms.linkedin import _resolve_linkedin_backend

    # First attempt: api for profile
    backend_0 = _resolve_linkedin_backend({"resource_type": "profile"}, None, retry_count=0)
    assert backend_0 == "api"

    # Retry 1: first fallback (playwright)
    backend_1 = _resolve_linkedin_backend({"resource_type": "profile"}, None, retry_count=1)
    assert backend_1 == "playwright"

    # Retry 2: second fallback (camoufox)
    backend_2 = _resolve_linkedin_backend({"resource_type": "profile"}, None, retry_count=2)
    assert backend_2 == "camoufox"


def test_linkedin_search_starts_with_api_and_falls_back() -> None:
    backend_0 = linkedin._resolve_linkedin_backend({"resource_type": "search", "search_type": "company"}, None, retry_count=0)
    backend_1 = linkedin._resolve_linkedin_backend({"resource_type": "search", "search_type": "company"}, None, retry_count=1)
    backend_2 = linkedin._resolve_linkedin_backend({"resource_type": "search", "search_type": "company"}, None, retry_count=2)

    assert backend_0 == "api"
    assert backend_1 == "playwright"
    assert backend_2 == "camoufox"
