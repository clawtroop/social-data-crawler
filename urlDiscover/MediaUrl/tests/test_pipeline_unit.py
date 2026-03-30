"""无 DB：仅验证 discover → normalize 链路可组合。"""

from linkedin_url.discover import discover_from_html
from linkedin_url.normalize import normalize_linkedin_url


def test_discover_then_normalize():
    html = '<a href="https://www.linkedin.com/in/jane/">x</a>'
    urls = discover_from_html(html, base_url="https://www.linkedin.com/company/acme/")
    assert urls
    r = normalize_linkedin_url(urls[0])
    assert r.profile_vanity == "jane"
