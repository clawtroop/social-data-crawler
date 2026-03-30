import pytest

from linkedin_url import LinkedInEntityType, normalize_linkedin_url
from linkedin_url.normalize import standard_canonical_url


@pytest.mark.parametrize(
    "raw,etype,canonical,vanity,company,job_id,activity",
    [
        (
            "https://www.linkedin.com/in/%E5%A4%A7%E5%BC%BA-%E7%8E%8B-b738b93b9/",
            LinkedInEntityType.PROFILE,
            "https://www.linkedin.com/in/%E5%A4%A7%E5%BC%BA-%E7%8E%8B-b738b93b9/",
            "大强-王-b738b93b9",
            None,
            None,
            None,
        ),
        (
            "https://www.linkedin.com/company/chinese-alibaba-group/",
            LinkedInEntityType.COMPANY,
            "https://www.linkedin.com/company/chinese-alibaba-group/",
            None,
            "chinese-alibaba-group",
            None,
            None,
        ),
        (
            "https://www.linkedin.com/jobs/view/4391229467/",
            LinkedInEntityType.JOB,
            "https://www.linkedin.com/jobs/view/4391229467/",
            None,
            None,
            "4391229467",
            None,
        ),
        (
            "https://www.linkedin.com/feed/update/urn:li:activity:7406859439900827648/",
            LinkedInEntityType.POST,
            "https://www.linkedin.com/feed/update/urn:li:activity:7406859439900827648/",
            None,
            None,
            None,
            "7406859439900827648",
        ),
        (
            "https://www.linkedin.com/posts/kasem-bau-2438a7b6_october-2024-marks-a-significant-milestone-activity-7257300242126036994-uH1u/",
            LinkedInEntityType.POST,
            "https://www.linkedin.com/feed/update/urn:li:activity:7257300242126036994/",
            None,
            None,
            None,
            "7257300242126036994",
        ),
    ],
)
def test_canonical_examples(raw, etype, canonical, vanity, company, job_id, activity):
    r = normalize_linkedin_url(raw)
    assert r.entity_type == etype
    assert r.canonical_url == canonical
    assert r.profile_vanity == vanity
    assert r.company_vanity == company
    assert r.job_id == job_id
    assert r.activity_id == activity


def test_strip_query():
    r = normalize_linkedin_url(
        "https://www.linkedin.com/in/johndoe/?originalSubdomain=uk"
    )
    assert r.entity_type == LinkedInEntityType.PROFILE
    assert r.profile_vanity == "johndoe"
    assert "stripped_query" in r.notes


def test_http_to_https_and_www():
    r = normalize_linkedin_url("http://linkedin.com/in/janedoe")
    assert r.canonical_url == "https://www.linkedin.com/in/janedoe/"


def test_unknown_sales_nav():
    r = normalize_linkedin_url("https://www.linkedin.com/sales/lead/123")
    assert r.entity_type == LinkedInEntityType.UNKNOWN


def test_standard_canonical_url_four_kinds():
    assert (
        standard_canonical_url("https://www.linkedin.com/in/foo/?trk=1")
        == "https://www.linkedin.com/in/foo/"
    )
    assert (
        standard_canonical_url("https://www.linkedin.com/company/bar/jobs/")
        == "https://www.linkedin.com/company/bar/"
    )
    assert (
        standard_canonical_url("https://www.linkedin.com/jobs/view/123/?ref=1")
        == "https://www.linkedin.com/jobs/view/123/"
    )
    assert (
        standard_canonical_url(
            "https://www.linkedin.com/feed/update/urn:li:activity:99/?x=1"
        )
        == "https://www.linkedin.com/feed/update/urn:li:activity:99/"
    )
    assert standard_canonical_url("https://www.linkedin.com/sales/foo") is None
