from linkedin_url.extract import extract_page_metadata


def test_extract_og():
    html = """
    <html><head>
    <title> X </title>
    <meta property="og:title" content="OG Title" />
    <meta property="og:description" content="Desc" />
    </head></html>
    """
    m = extract_page_metadata(html)
    assert m["og_title"] == "OG Title"
    assert m["title"] in ("X", "OG Title")
