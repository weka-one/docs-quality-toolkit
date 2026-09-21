"""Content source adapters.

The tests that matter here are the hostile ones. A CMS slug and a sitemap URL
are untrusted input, and the pipeline writes them to disk.
"""
import io
import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from pipeline.sources import (  # noqa: E402
    CmsApiSource,
    FilesystemSource,
    Page,
    SiteCrawlSource,
    build,
    html_to_markdown,
    materialise,
)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def opener_for(payloads: dict):
    def _open(request, timeout=None):
        url = request.full_url if hasattr(request, "full_url") else request
        if url not in payloads:
            raise AssertionError(f"unexpected fetch: {url}")
        return FakeResponse(payloads[url].encode())
    return _open


# --- filesystem -------------------------------------------------------------

def test_filesystem_reads_markdown_and_title(tmp_path):
    (tmp_path / "guide").mkdir()
    (tmp_path / "guide" / "a.mdx").write_text("---\ntitle: Query Creator Info\n---\n\nBody.\n")
    pages = list(FilesystemSource(tmp_path).pages())
    assert len(pages) == 1
    assert pages[0].path == "guide/a.mdx"
    assert pages[0].title == "Query Creator Info"


# --- CMS API ----------------------------------------------------------------

def test_cms_api_paginates_and_maps_fields():
    page1 = json.dumps({
        "results": [{"slug": "a", "attributes": {"name": "A"}, "content": {"md": "# A"}}],
        "links": {"next": "https://cms.example/p2"},
    })
    page2 = json.dumps({
        "results": [{"slug": "b", "attributes": {"name": "B"}, "content": {"md": "# B"}}],
        "links": {"next": None},
    })
    source = CmsApiSource(
        {
            "list_url": "https://cms.example/p1",
            "fields": {
                "items": "results", "next": "links.next", "id": "slug",
                "title": "attributes.name", "body": "content.md",
            },
        },
        opener=opener_for({"https://cms.example/p1": page1, "https://cms.example/p2": page2}),
    )
    pages = list(source.pages())
    assert [p.path for p in pages] == ["a", "b"]
    assert pages[0].title == "A"


def test_cms_api_stops_on_self_referential_next_link():
    """A next-link pointing at itself would otherwise loop until the job is killed."""
    payload = json.dumps({
        "results": [{"slug": "a", "content": {"md": "# A"}}],
        "links": {"next": "https://cms.example/p1"},
    })
    source = CmsApiSource(
        {"list_url": "https://cms.example/p1",
         "fields": {"items": "results", "next": "links.next", "id": "slug", "body": "content.md"}},
        opener=opener_for({"https://cms.example/p1": payload}),
    )
    assert len(list(source.pages())) == 1


def test_cms_api_requires_its_token(monkeypatch):
    monkeypatch.delenv("CMS_TOKEN", raising=False)
    source = CmsApiSource(
        {"list_url": "https://cms.example/p1", "auth_header": "Authorization",
         "auth_env": "CMS_TOKEN", "fields": {}},
        opener=opener_for({}),
    )
    with pytest.raises(RuntimeError, match="CMS_TOKEN"):
        list(source.pages())


def test_cms_api_skips_records_with_no_body():
    payload = json.dumps({"results": [{"slug": "a", "content": {}}, {"slug": "b", "content": {"md": "# B"}}]})
    source = CmsApiSource(
        {"list_url": "https://cms.example/p1",
         "fields": {"items": "results", "id": "slug", "body": "content.md"}},
        opener=opener_for({"https://cms.example/p1": payload}),
    )
    assert [p.path for p in source.pages()] == ["b"]


# --- site crawl -------------------------------------------------------------

SITEMAP = """<?xml version="1.0"?><urlset>
<url><loc>https://docs.example/a</loc></url>
<url><loc>https://docs.example/blog/b</loc></url>
<url><loc>https://evil.example/c</loc></url>
</urlset>"""


def test_crawl_stays_on_host_and_honours_excludes():
    source = SiteCrawlSource(
        {"sitemap_url": "https://docs.example/sitemap.xml", "exclude_patterns": ["/blog/"]},
        opener=opener_for({"https://docs.example/sitemap.xml": SITEMAP}),
    )
    assert source.urls() == ["https://docs.example/a"]


def test_crawl_survives_one_bad_page():
    def flaky(request, timeout=None):
        url = request.full_url
        if url.endswith("sitemap.xml"):
            return FakeResponse(SITEMAP.encode())
        raise OSError("connection reset")
    source = SiteCrawlSource(
        {"sitemap_url": "https://docs.example/sitemap.xml",
         "exclude_patterns": ["/blog/"], "delay_seconds": 0},
        opener=flaky,
    )
    pages = list(source.pages())
    assert len(pages) == 1 and "error" in pages[0].revision


def test_html_reduction_keeps_headings_and_code():
    md = html_to_markdown(
        "<nav>menu</nav><h1>Query Creator Info</h1><p>Call <code>GET /v2/user/info/</code>.</p>"
        "<pre>curl https://example.com</pre><script>x=1</script>"
    )
    assert "# Query Creator Info" in md
    assert "`GET /v2/user/info/`" in md
    assert "```" in md and "curl https://example.com" in md
    assert "menu" not in md and "x=1" not in md


# --- staging ----------------------------------------------------------------

class ListSource:
    name = "list"

    def __init__(self, pages):
        self._pages = pages

    def pages(self):
        return iter(self._pages)


def test_materialise_writes_tree_and_index(tmp_path):
    source = ListSource([
        Page(path="guides/get-started", text="# Get Started", title="Get Started",
             url="https://docs.example/guides/get-started"),
    ])
    out = materialise(source, tmp_path / "stage")
    written = out / "guides" / "get-started.md"
    assert written.read_text() == "# Get Started"
    index = json.loads((out / "_index.json").read_text())
    assert index["guides/get-started.md"]["url"] == "https://docs.example/guides/get-started"


def test_materialise_refuses_path_traversal(tmp_path):
    """A CMS slug is untrusted input and is written to disk."""
    source = ListSource([
        Page(path="../../etc/passwd", text="pwned"),
        Page(path="ok", text="fine"),
    ])
    out = materialise(source, tmp_path / "stage")
    assert not (tmp_path / "etc").exists()
    assert (out / "ok.md").read_text() == "fine"


def test_build_rejects_unknown_type():
    with pytest.raises(ValueError):
        build({"type": "telepathy"})


# --- robots.txt -------------------------------------------------------------

ROBOTS = """User-agent: *
Disallow: /internal/
Crawl-delay: 3
"""


def test_crawl_obeys_robots_disallow():
    """The site published rules; a crawler that ignores them deserves blocking."""
    sitemap = """<?xml version="1.0"?><urlset>
    <url><loc>https://docs.example/public</loc></url>
    <url><loc>https://docs.example/internal/secret</loc></url>
    </urlset>"""
    source = SiteCrawlSource(
        {"sitemap_url": "https://docs.example/sitemap.xml", "delay_seconds": 0},
        opener=opener_for({
            "https://docs.example/robots.txt": ROBOTS,
            "https://docs.example/sitemap.xml": sitemap,
        }),
    )
    assert source.urls() == ["https://docs.example/public"]
    assert source.skipped_by_robots == 1


def test_crawl_adopts_published_crawl_delay():
    source = SiteCrawlSource(
        {"sitemap_url": "https://docs.example/sitemap.xml", "delay_seconds": 0.5},
        opener=opener_for({
            "https://docs.example/robots.txt": ROBOTS,
            "https://docs.example/sitemap.xml": SITEMAP,
        }),
    )
    source.urls()
    assert source.delay == 3.0


def test_missing_robots_is_permission_not_a_stop():
    def no_robots(request, timeout=None):
        if request.full_url.endswith("robots.txt"):
            raise OSError("404")
        return FakeResponse(SITEMAP.encode())
    source = SiteCrawlSource(
        {"sitemap_url": "https://docs.example/sitemap.xml", "exclude_patterns": ["/blog/"]},
        opener=no_robots,
    )
    assert source.urls() == ["https://docs.example/a"]


# --- no sitemap: the two fallbacks ------------------------------------------

def test_explicit_url_list(tmp_path):
    listing = tmp_path / "urls.txt"
    listing.write_text(
        "# TT4D doc pages\n"
        "https://docs.example/doc/a\n"
        "https://docs.example/doc/b\n"
        "https://other.example/doc/c\n"   # off-host, must be dropped
    )
    source = SiteCrawlSource(
        {"urls_file": str(listing), "sitemap_url": "https://docs.example/sitemap.xml"},
        opener=opener_for({"https://docs.example/robots.txt": "User-agent: *\n"}),
    )
    assert source.urls() == ["https://docs.example/doc/a", "https://docs.example/doc/b"]


def test_link_discovery_stays_on_host_and_respects_depth():
    pages = {
        "https://docs.example/robots.txt": "User-agent: *\n",
        "https://docs.example/start": (
            '<a href="/doc/a">A</a><a href="https://evil.example/x">X</a>'
            '<a href="/doc/b">B</a>'
        ),
        "https://docs.example/doc/a": '<a href="/doc/deep">deep</a>',
        "https://docs.example/doc/b": "",
        "https://docs.example/doc/deep": "",
    }
    source = SiteCrawlSource(
        {"discover_from": "https://docs.example/start", "discover_depth": 1,
         "delay_seconds": 0},
        opener=opener_for(pages),
    )
    found = source.urls()
    assert "https://docs.example/doc/a" in found
    assert "https://docs.example/doc/b" in found
    assert not any("evil.example" in u for u in found)
    # depth 1 means the seed's links, not their links
    assert "https://docs.example/doc/deep" not in found


def test_include_patterns_narrow_the_crawl(tmp_path):
    listing = tmp_path / "urls.txt"
    listing.write_text("https://docs.example/doc/a\nhttps://docs.example/blog/b\n")
    source = SiteCrawlSource(
        {"urls_file": str(listing), "sitemap_url": "https://docs.example/s.xml",
         "include_patterns": ["/doc/"]},
        opener=opener_for({"https://docs.example/robots.txt": "User-agent: *\n"}),
    )
    assert source.urls() == ["https://docs.example/doc/a"]
