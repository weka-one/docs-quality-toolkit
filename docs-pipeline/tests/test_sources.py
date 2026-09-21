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
