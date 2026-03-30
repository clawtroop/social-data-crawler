from linkedin_url.profile_expand import classify_linkedin_url, filter_global_nav_urls


def test_classify_company():
    assert classify_linkedin_url("https://www.linkedin.com/company/foo/") == "company"


def test_classify_post():
    assert (
        classify_linkedin_url(
            "https://www.linkedin.com/feed/update/urn:li:activity:123/"
        )
        == "post"
    )


def test_classify_profile_activity():
    u = "https://www.linkedin.com/in/jianli-wang-926768a9/recent-activity/comments/"
    assert classify_linkedin_url(u) == "profile_activity"


def test_classify_profile_root():
    assert (
        classify_linkedin_url("https://www.linkedin.com/in/someone/")
        == "profile"
    )


def test_filter_nav():
    raw = [
        "https://www.linkedin.com/company/x/",
        "https://www.linkedin.com/feed/?nis=true",
        "https://www.linkedin.com/mynetwork/",
    ]
    kept = filter_global_nav_urls(raw)
    assert "https://www.linkedin.com/company/x/" in kept
    assert len(kept) == 1
