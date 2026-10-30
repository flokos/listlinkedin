"""Reading a page's metadata (apps.metadata.parser)."""

from apps.metadata.parser import MAX_TITLE_LENGTH, parse

URL = "https://site.test/docs/page"


def test_reads_title_description_site_name_and_preview_image():
    found = parse(
        b"""<html><head>
        <title>Plain title</title>
        <meta property="og:title" content="Open Graph title">
        <meta name="description" content="What the page is about.">
        <meta property="og:site_name" content="Site">
        <meta property="og:image" content="/img/preview.png">
        </head><body><title>not this</title></body></html>""",
        URL,
    )
    assert found.title == "Open Graph title"
    assert found.description == "What the page is about."
    assert found.site_name == "Site"
    assert found.image_url == "https://site.test/img/preview.png"


def test_falls_back_to_the_title_element_and_decodes_entities():
    found = parse(b"<title>\n  Caf&eacute; &amp;\t friends  </title>", URL)
    assert found.title == "Café & friends"
    assert found.description is None and found.image_url is None


def test_icons_best_first_without_svg_and_with_the_favicon_last():
    found = parse(
        b"""<base href="https://cdn.site.test/assets/">
        <link rel="icon" href="small.png" sizes="16x16">
        <link rel="icon" href="logo.svg" type="image/svg+xml">
        <link rel="shortcut icon" href="big.png" sizes="16x16 64x64">
        <link rel="apple-touch-icon" href="/touch.png">
        <link rel="icon" href="javascript:alert(1)">
        <link rel="stylesheet" href="style.css">""",
        URL,
    )
    assert found.icon_urls == [
        "https://cdn.site.test/touch.png",
        "https://cdn.site.test/assets/big.png",
        "https://cdn.site.test/assets/small.png",
        "https://site.test/favicon.ico",
    ]


def test_a_page_without_icons_still_offers_the_favicon():
    assert parse(b"<title>x</title>", URL).icon_urls == ["https://site.test/favicon.ico"]


def test_only_http_urls_are_kept():
    found = parse(b'<meta property="og:image" content="data:image/png;base64,AAAA">', URL)
    assert found.image_url is None


def test_the_charset_comes_from_the_header_then_the_page():
    greek = "<title>Καλημέρα</title>".encode("iso-8859-7")
    assert parse(greek, URL, "iso-8859-7").title == "Καλημέρα"
    with_meta = b'<meta charset="iso-8859-7">' + greek
    assert parse(with_meta, URL).title == "Καλημέρα"
    assert parse("<title>Ünïcode</title>".encode(), URL).title == "Ünïcode"  # UTF-8 default
    assert parse(b"<title>ok</title>", URL, "no-such-charset").title == "ok"


def test_values_are_cleaned_and_cut_to_length():
    found = parse(
        ("<title>" + "A\u0000B​C " + "x" * 400 + "</title>").encode()
        + b'<meta name="description" content="  two\n\nlines  ">',
        URL,
    )
    assert found.title.startswith("ABC x")
    assert len(found.title) == MAX_TITLE_LENGTH and found.title.endswith("…")
    assert found.description == "two lines"


def test_the_first_of_repeated_tags_wins_and_broken_html_is_fine():
    found = parse(
        b'<meta name="description" content="first"><meta name="description" content="second">'
        b"<title>Unclosed <b>bold",
        URL,
    )
    assert found.description == "first"
    assert found.title is None  # an unclosed title is no title
