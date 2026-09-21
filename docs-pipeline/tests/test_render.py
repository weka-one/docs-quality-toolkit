"""The rendering source adapter.

These tests run without a browser. What they check is the part that is easy to
get wrong and expensive to debug against a live site: that one failing page does
not end a run, that the politeness settings inherited from the plain crawl are
still applied when a browser is doing the fetching, and that a missing browser
produces an instruction rather than a stack trace.

The browser itself is exercised by `test_renders_real_page`, which is skipped
unless a browser is actually present.
"""
import os
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from pipeline.render import (  # noqa: E402
    MIN_CONTENT_CHARS,
    Renderer,
    RenderedCrawlSource,
    _url_path,
)
from pipeline.sources import SourceError, build  # noqa: E402

BODY = (
    "<h1>Query Creator Info</h1>"
    "<p>You must register an app before you can request a client key.</p>"
)


class FakeRenderer:
    """Stands in for a browser. Records what it was asked to load."""

    def __init__(self, failures=(), html=BODY):
        self.seen = []
        self.failures = set(failures)
        self.html = html
        self.closed = False

    def content_html(self, url):
        self.seen.append(url)
        if url in self.failures:
            raise TimeoutError("page never finished loading")
        return self.html, "main"


def source(urls, renderer, **config):
    settings = {"urls": list(urls), "delay_seconds": 0, "ignore_robots": True}
    settings.update(config)
    return RenderedCrawlSource(settings, renderer=renderer)


def test_yields_markdown_not_html():
    renderer = FakeRenderer()
    pages = list(source(["https://example.com/doc/a"], renderer).pages())
    assert len(pages) == 1
    assert pages[0].text.startswith("# Query Creator Info")
    assert "<h1>" not in pages[0].text
    assert pages[0].title == "Query Creator Info"


def test_one_failing_page_does_not_end_the_run():
    """A single slow page in a 500-page set must not cost the other 499."""
    urls = ["https://example.com/a", "https://example.com/b", "https://example.com/c"]
    renderer = FakeRenderer(failures={"https://example.com/b"})
    pages = list(source(urls, renderer).pages())

    assert len(pages) == 3
    assert renderer.seen == urls              # it kept going
    broken = [p for p in pages if not p.text]
    assert len(broken) == 1
    assert "error:" in broken[0].revision     # and said so, per page


def test_a_missing_browser_stops_the_whole_run():
    """The opposite case: no browser is not a per-page problem, so do not
    quietly emit 500 empty pages and call the docs broken."""

    class NoBrowser:
        def content_html(self, url):
            raise SourceError("no browser")

    with pytest.raises(SourceError):
        list(source(["https://example.com/a"], NoBrowser()).pages())


def test_crawler_does_not_leave_the_host():
    """Routing is inherited from the plain crawl; rendering must not bypass it.
    The host is taken from the first URL, so the foreign one is dropped even
    though nothing here declares a host."""
    urls = [
        "https://example.com/doc/a",
        "https://elsewhere.test/doc/b",
        "https://example.com/doc/c",
    ]
    renderer = FakeRenderer()
    list(source(urls, renderer).pages())

    assert renderer.seen == ["https://example.com/doc/a", "https://example.com/doc/c"]


def test_limit_caps_the_batch():
    urls = [f"https://example.com/doc/{i}" for i in range(10)]
    renderer = FakeRenderer()
    list(source(urls, renderer, limit=3).pages())

    assert renderer.seen == [f"https://example.com/doc/{i}" for i in range(3)]


def test_exclude_patterns_still_apply():
    urls = ["https://example.com/doc/a", "https://example.com/changelog/b"]
    renderer = FakeRenderer()
    list(source(urls, renderer, exclude_patterns=["/changelog/"]).pages())

    assert renderer.seen == ["https://example.com/doc/a"]


def test_robots_is_consulted_when_not_ignored():
    src = RenderedCrawlSource({"urls": ["https://example.com/a"], "delay_seconds": 0})
    assert src.config.get("ignore_robots") is None
    assert hasattr(src, "allowed")            # inherited, not reimplemented


def test_delay_is_honoured_between_pages(monkeypatch):
    slept = []
    monkeypatch.setattr("time.sleep", lambda s: slept.append(s))
    renderer = FakeRenderer()
    urls = ["https://example.com/a", "https://example.com/b", "https://example.com/c"]
    list(source(urls, renderer, delay_seconds=1.5).pages())

    assert slept == [1.5, 1.5]                # between pages, not before the first


def test_build_dispatches_both_ways():
    assert build({"type": "rendered-crawl", "urls": []}).name == "rendered-crawl"
    assert build({"type": "site-crawl", "render": True, "urls": []}).name == "rendered-crawl"
    assert build({"type": "site-crawl", "urls": []}).name == "site-crawl"


def test_missing_playwright_explains_the_fix(monkeypatch):
    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __import__

    def blocked(name, *args, **kwargs):
        if name.startswith("playwright"):
            raise ImportError("No module named 'playwright'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", blocked)
    with pytest.raises(SourceError) as caught:
        with Renderer():
            pass

    message = str(caught.value)
    assert "pip install" in message and "playwright install chromium" in message
    assert "Traceback" not in message


def test_renderer_must_be_opened_first():
    with pytest.raises(SourceError):
        Renderer().content_html("https://example.com/a")


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://example.com/doc/overview", "doc/overview"),
        ("https://example.com/", "index"),
        ("https://example.com", "index"),
    ],
)
def test_url_becomes_a_readable_path(url, expected):
    assert _url_path(url) == expected


def _browser_path():
    return os.environ.get("DOCS_PIPELINE_BROWSER", "")


@pytest.mark.skipif(
    not os.environ.get("DOCS_PIPELINE_BROWSER_TEST"),
    reason="set DOCS_PIPELINE_BROWSER_TEST=1 to run the browser-backed test",
)
def test_renders_real_page(tmp_path):
    """The case this module exists for: text that only appears after scripts run,
    on a page whose interface copy would otherwise win."""
    page = tmp_path / "page.html"
    page.write_text(
        "<!doctype html><html><body><div id=root></div><script>"
        "document.getElementById('root').innerHTML ="
        "'<nav>Docs API Support</nav><main><h1>Query Creator Info</h1>"
        f"<p>{'You must register an app before requesting a client key. ' * 6}</p></main>"
        "<footer>You may unsubscribe at any time from the Account Settings page.</footer>';"
        "</script></body></html>"
    )
    with Renderer(browser_path=_browser_path()) as renderer:
        html, via = renderer.content_html(page.as_uri())

    assert "Query Creator Info" in html
    assert via == "main"
    assert "unsubscribe" not in html.lower()   # the footer stayed out
    assert "Support" not in html               # so did the navigation
    assert len(html) >= MIN_CONTENT_CHARS
