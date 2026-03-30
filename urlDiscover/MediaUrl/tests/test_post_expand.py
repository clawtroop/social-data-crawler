from linkedin_url.post_expand import expand_post_from_saved_html, merge_post_expand_results


def test_expand_post_from_saved_html_finds_profile_link():
    html = (
        '<html><body>'
        '<a href="https://www.linkedin.com/in/commenter-example/">Commenter</a>'
        '</body></html>'
    )
    post_url = "https://www.linkedin.com/feed/update/urn:li:activity:999888777/"
    r = expand_post_from_saved_html(html=html, post_canonical_url=post_url)
    assert r["activity_id"] == "999888777"
    assert r["canonical_post_url"].endswith("/feed/update/urn:li:activity:999888777/")
    profiles = r["buckets"].get("profile") or []
    assert any("commenter-example" in u for u in profiles)


def test_merge_post_expand_results():
    a = expand_post_from_saved_html(
        html='<a href="https://www.linkedin.com/in/a/">x</a>',
        post_canonical_url="https://www.linkedin.com/feed/update/urn:li:activity:1/",
    )
    b = expand_post_from_saved_html(
        html='<a href="https://www.linkedin.com/company/acme/">y</a>',
        post_canonical_url="https://www.linkedin.com/feed/update/urn:li:activity:2/",
    )
    m = merge_post_expand_results([a, b])
    assert m["post_count"] == 2
    assert len(m["urls_discovered"]) >= 2
    assert (m["buckets"].get("profile") or []) and (m["buckets"].get("company") or [])
