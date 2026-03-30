from linkedin_url.discover import discover_from_html


def test_discover_from_html_hrefs():
    html = """
    <html><body>
    <a href="/in/janedoe/">p</a>
    <a href="https://www.linkedin.com/company/acme/">c</a>
    <a href="https://example.com/x">skip</a>
    </body></html>
    """
    urls = discover_from_html(html, base_url="https://www.linkedin.com/in/someone/")
    assert "https://www.linkedin.com/in/janedoe/" in urls
    assert "https://www.linkedin.com/company/acme/" in urls
    assert len([u for u in urls if "example.com" in u]) == 0


def test_discover_dedupe_fragment():
    html = '<a href="/in/a/#x"></a><a href="/in/a/"></a>'
    urls = discover_from_html(html, base_url="https://www.linkedin.com/")
    assert urls.count("https://www.linkedin.com/in/a/") == 1
