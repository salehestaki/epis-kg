from ingestion_service.sanitize import content_id, extract_urls, sanitize


def test_sanitize_collapses_whitespace_and_controls():
    assert sanitize("hello\x00   \n world\t") == "hello world"


def test_sanitize_normalises_unicode():
    # Fullwidth 'Ａ' -> 'A'
    assert sanitize("ＡBC") == "ABC"


def test_content_id_is_deterministic_and_url_sensitive():
    a = content_id("same text", "http://a")
    b = content_id("same text", "http://a")
    c = content_id("same text", "http://b")
    assert a == b
    assert a != c
    assert a.startswith("doc_")


def test_extract_urls():
    urls = extract_urls("see http://x.com/a and https://y.org/b?q=1 now")
    assert "http://x.com/a" in urls
    assert "https://y.org/b?q=1" in urls
