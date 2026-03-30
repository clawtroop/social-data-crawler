from linkedin_url.auth.verify import analyze_linkedin_activity_html


def test_guest_wall_from_external_snippet():
    # 与未登录访客可见的公开页文案类似
    html = "<html>Sign in or join now to see Yan's post</html>"
    g, f, _ = analyze_linkedin_activity_html(html)
    assert g is True
    assert f is False


def test_feed_structure_hint():
    html = '<div class="feed-shared-update-v2__description">hello</div>'
    g, f, _ = analyze_linkedin_activity_html(html)
    assert g is False
    assert f is True
