from linkedin_url.discover import discover_from_html_deep


def test_deep_finds_embedded_url():
    html = """
    <html><body>
    <script>var x = "https://www.linkedin.com/company/acme-corp/";</script>
    </body></html>
    """
    urls = discover_from_html_deep(html, base_url="https://www.linkedin.com/in/foo/")
    assert any("company/acme-corp" in u for u in urls)
