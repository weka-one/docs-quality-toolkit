"""Where documentation comes from.

Both tools in this repository were built assuming a Git checkout: a directory
of Markdown that a pull request changes. That assumption does not survive a
docs set whose system of record is a CMS. There is no pull request to gate, no
merge base to diff against, and no file on disk until something fetches it.

The checks themselves were never the problem — Vale, the structure linter and
the freshness checker all operate on text. What needed replacing is the layer
that produces the text. A source yields `Page` objects; everything downstream
is unchanged.

Three adapters, covering the three situations a docs team is actually in:

    FilesystemSource  a directory, or an export the CMS produced
    CmsApiSource      a REST API, described by config rather than by code
    SiteCrawlSource   the published site, when the CMS offers no usable API

The last one is the unglamorous fallback, and it is the one most likely to be
needed. A CMS that cannot export and has no read API still serves HTML.
"""
from __future__ import annotations

import dataclasses
import html
import json
import pathlib
import re
import urllib.parse
import urllib.request
from typing import Iterator, Protocol


class SourceError(RuntimeError):
    """A problem fetching content, phrased for the person who has to fix it."""


@dataclasses.dataclass
class Page:
    """One documentation page, however it was obtained.

    `path` is the stable identifier used in reports. For a filesystem source it
    is the relative path; for a CMS it is the slug. Reports are read by people
    who need to find the page again, so this must be something they can act on
    — which is why `url` exists alongside it.
    """
    path: str
    text: str
    title: str = ""
    url: str = ""
    revision: str = ""

    @property
    def is_markdown(self) -> bool:
        return self.path.endswith((".md", ".mdx"))


class Source(Protocol):
    name: str

    def pages(self) -> Iterator[Page]:
        ...


class FilesystemSource:
    """A directory of Markdown. Also the shape a CMS export lands in."""

    name = "filesystem"

    def __init__(self, root: pathlib.Path, patterns: tuple[str, ...] = ("*.md", "*.mdx")):
        self.root = pathlib.Path(root)
        self.patterns = patterns

    def pages(self) -> Iterator[Page]:
        seen: set[pathlib.Path] = set()
        for pattern in self.patterns:
            for path in sorted(self.root.rglob(pattern)):
                if path in seen:
                    continue
                seen.add(path)
                text = path.read_text(encoding="utf-8")
                yield Page(
                    path=str(path.relative_to(self.root)),
                    text=text,
                    title=_frontmatter_title(text) or path.stem,
                )


def _dig(obj, dotted: str):
    """Read a dotted path out of nested JSON, tolerating lists of one."""
    for part in dotted.split("."):
        if obj is None:
            return None
        if isinstance(obj, list):
            obj = obj[0] if obj else None
            if obj is None:
                return None
        if not isinstance(obj, dict):
            return None
        obj = obj.get(part)
    return obj


class CmsApiSource:
    """A read-only CMS API, described entirely by configuration.

    No CMS is hardcoded, because the one this is aimed at is internal and its
    API is not something this repository can know. What it can do is fix the
    shape: paginate a list endpoint, pull a field from each record, and stop.
    Pointing it at a different CMS is a config change, not a code change.

    Config keys: `list_url`, `page_size`, `auth_header`/`auth_env`, and a
    `fields` map naming the JSON paths for id, title, body and url.
    """

    name = "cms-api"

    def __init__(self, config: dict, opener=None):
        self.config = config
        self.fields = config.get("fields") or {}
        self._opener = opener or urllib.request.urlopen

    def _request(self, url: str) -> dict:
        import os

        headers = {"Accept": "application/json"}
        header_name = self.config.get("auth_header")
        if header_name:
            token = os.environ.get(self.config.get("auth_env", ""), "")
            if not token:
                raise RuntimeError(
                    f"{self.config.get('auth_env')} is not set; the CMS source cannot authenticate"
                )
            headers[header_name] = self.config.get("auth_format", "{token}").format(token=token)
        request = urllib.request.Request(url, headers=headers)
        with self._opener(request, timeout=self.config.get("timeout", 60)) as response:
            return json.loads(response.read().decode("utf-8"))

    def pages(self) -> Iterator[Page]:
        url = self.config["list_url"]
        items_path = self.fields.get("items", "items")
        next_path = self.fields.get("next", "")
        seen_urls: set[str] = set()

        while url:
            if url in seen_urls:
                break           # a next-link that points at itself would loop forever
            seen_urls.add(url)
            payload = self._request(url)
            items = _dig(payload, items_path) or []
            for item in items:
                body = _dig(item, self.fields.get("body", "body"))
                if not body:
                    continue
                yield Page(
                    path=str(_dig(item, self.fields.get("id", "slug")) or ""),
                    text=body,
                    title=str(_dig(item, self.fields.get("title", "title")) or ""),
                    url=str(_dig(item, self.fields.get("url", "url")) or ""),
                    revision=str(_dig(item, self.fields.get("revision", "updated_at")) or ""),
                )
            url = _dig(payload, next_path) if next_path else None


_TAG = re.compile(r"<[^>]+>")
_SCRIPT = re.compile(r"<(script|style|nav|header|footer)\b.*?</\1>", re.S | re.I)
_PRE = re.compile(r"<pre\b[^>]*>(.*?)</pre>", re.S | re.I)
_CODE = re.compile(r"<code\b[^>]*>(.*?)</code>", re.S | re.I)
_H = re.compile(r"<h([1-6])\b[^>]*>(.*?)</h\1>", re.S | re.I)
_LOC = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.S | re.I)


def html_to_markdown(source: str) -> str:
    """A deliberately small HTML-to-Markdown reduction.

    Not a general converter. It preserves exactly what the checks read:
    headings, fenced code, inline code, and paragraph text. Everything else is
    flattened. A fuller converter would invent structure the checks would then
    treat as real, which is worse than losing it.
    """
    text = _SCRIPT.sub(" ", source)
    text = _PRE.sub(lambda m: "\n```\n" + _TAG.sub("", m.group(1)).strip() + "\n```\n", text)
    text = _CODE.sub(lambda m: "`" + _TAG.sub("", m.group(1)).strip() + "`", text)
    text = _H.sub(lambda m: "\n" + "#" * int(m.group(1)) + " " + _TAG.sub("", m.group(2)).strip() + "\n", text)
    text = re.sub(r"</(p|div|li|tr)>", "\n", text, flags=re.I)
    text = _TAG.sub("", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


class SiteCrawlSource:
    """Fetch the published site and reduce each page to Markdown.

    The fallback for a CMS with no export and no read API. It checks what
    readers actually see, which is a real advantage over checking a source of
    truth that may not match what was published.

    Politeness is not optional here: it reads a sitemap rather than following
    links, honours a delay between requests, and refuses to leave the
    configured host.
    """

    name = "site-crawl"

    def __init__(self, config: dict, opener=None):
        self.config = config
        self._opener = opener or urllib.request.urlopen
        self.delay = float(config.get("delay_seconds", 1.0))
        self.limit = int(config.get("limit", 0)) or None
        self.user_agent = config.get("user_agent", "docs-pipeline/1.0")
        self._robots = None
        self.skipped_by_robots = 0

    def robots(self):
        """Load the site's robots.txt once.

        Checking it is not optional politeness. This is the one adapter that
        fetches somebody's live site at volume, and the site has already
        published the rules it wants followed. A crawler that ignores them gets
        blocked, and deserves to be.

        A missing or unreadable robots.txt means no rules were published, which
        is permission by default - not a reason to stop.
        """
        if self._robots is not None:
            return self._robots
        import urllib.robotparser

        origin = (self.config.get("sitemap_url") or self.config.get("discover_from")
                  or (self.config.get("urls") or [""])[0])
        parsed = urllib.parse.urlparse(origin)
        parser = urllib.robotparser.RobotFileParser()
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        try:
            request = urllib.request.Request(
                robots_url, headers={"User-Agent": self.user_agent}
            )
            with self._opener(request, timeout=self.config.get("timeout", 60)) as response:
                parser.parse(response.read().decode("utf-8", errors="replace").splitlines())
        except Exception:
            parser.allow_all = True
        self._robots = parser

        # A site that asks for a slower pace gets it.
        try:
            published = parser.crawl_delay(self.user_agent)
        except Exception:
            published = None
        if published and float(published) > self.delay:
            self.delay = float(published)
        return parser

    def allowed(self, url: str) -> bool:
        if self.config.get("ignore_robots"):
            return True
        try:
            return self.robots().can_fetch(self.user_agent, url)
        except Exception:
            return True

    def _get(self, url: str) -> str:
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with self._opener(request, timeout=self.config.get("timeout", 60)) as response:
            return response.read().decode("utf-8", errors="replace")

    def urls(self) -> list[str]:
        """Where the list of pages comes from, in order of preference.

        A sitemap is the polite, complete answer, and plenty of sites do not
        have one - developers.tiktok.com returns 404 for every usual address.
        So two fallbacks: an explicit list of URLs, and following links from a
        seed page. Both honour robots.txt and the delay exactly as the sitemap
        path does.
        """
        if self.config.get("urls"):
            return self._filter(list(self.config["urls"]))
        if self.config.get("urls_file"):
            listing = pathlib.Path(self.config["urls_file"])
            if not listing.is_file():
                raise SourceError(
                    f"urls_file points at {listing}, which does not exist.\n"
                    "Create it with one URL per line, or remove urls_file from the\n"
                    "config to fall back to discover_from or the sitemap."
                )
            listed = listing.read_text(encoding="utf-8")
            return self._filter([
                line.strip() for line in listed.splitlines()
                if line.strip() and not line.startswith("#")
            ])
        if self.config.get("discover_from"):
            return self._discover()
        return self._from_sitemap()

    def _filter(self, candidates: list[str]) -> list[str]:
        host = urllib.parse.urlparse(
            self.config.get("sitemap_url") or self.config.get("discover_from") or candidates[0]
        ).netloc
        kept = []
        for url in candidates:
            if urllib.parse.urlparse(url).netloc != host:
                continue
            if any(re.search(p, url) for p in self.config.get("exclude_patterns", [])):
                continue
            include = self.config.get("include_patterns") or []
            if include and not any(re.search(p, url) for p in include):
                continue
            if not self.allowed(url):
                self.skipped_by_robots += 1
                continue
            kept.append(url)
        seen, unique = set(), []
        for url in kept:
            if url not in seen:
                seen.add(url)
                unique.append(url)
        return unique[: self.limit] if self.limit else unique

    def _discover(self) -> list[str]:
        """Follow links from a seed page, staying on the host.

        Breadth-first with a depth cap, because a docs site's navigation is
        usually two or three clicks deep and an uncapped crawl wanders into
        every archive the site has.
        """
        import time

        seed = self.config["discover_from"]
        max_depth = int(self.config.get("discover_depth", 2))
        budget = self.limit or 500

        host = urllib.parse.urlparse(seed).netloc
        seen, found, frontier = {seed}, [], [(seed, 0)]
        link_re = re.compile(r'(?i)<a\b[^>]*href=["\']([^"\'#]+)')

        while frontier and len(found) < budget:
            url, depth = frontier.pop(0)
            if not self.allowed(url):
                self.skipped_by_robots += 1
                continue
            try:
                html = self._get(url)
            except Exception:
                continue
            found.append(url)
            if depth >= max_depth:
                continue
            for href in link_re.findall(html):
                target = urllib.parse.urljoin(url, href).split("#")[0].rstrip("/")
                if not target or target in seen:
                    continue
                if urllib.parse.urlparse(target).netloc != host:
                    continue
                seen.add(target)
                frontier.append((target, depth + 1))
            time.sleep(self.delay)

        return self._filter(found)

    def _from_sitemap(self) -> list[str]:
        url = self.config["sitemap_url"]
        try:
            sitemap = self._get(url)
        except Exception as exc:
            # This is the first thing a crawl does, so it is where a wrong
            # address, a VPN requirement or a blocked network shows up. A raw
            # traceback here tells the reader nothing they can act on.
            raise SourceError(
                f"Could not read the sitemap at {url}\n"
                f"  ({type(exc).__name__}: {exc})\n\n"
                "Things to check, in order:\n"
                "  1. Open that address in a browser. If it 404s, look for a "
                "'Sitemap:' line in the site's robots.txt and use that address.\n"
                "  2. If the site is behind a VPN or SSO, connect first.\n"
                "  3. If the browser works but this does not, the site may be "
                "blocking automated requests; try a slower delay_seconds."
            ) from exc
        host = urllib.parse.urlparse(self.config["sitemap_url"]).netloc
        found = []
        for loc in _LOC.findall(sitemap):
            loc = html.unescape(loc.strip())
            if urllib.parse.urlparse(loc).netloc != host:
                continue        # never wander off the configured host
            if any(re.search(p, loc) for p in self.config.get("exclude_patterns", [])):
                continue
            if not self.allowed(loc):
                self.skipped_by_robots += 1
                continue
            found.append(loc)
        return found[: self.limit] if self.limit else found

    def pages(self) -> Iterator[Page]:
        import time

        for i, url in enumerate(self.urls()):
            if i:
                time.sleep(self.delay)
            try:
                raw = self._get(url)
            except Exception as exc:       # one bad page must not end the run
                yield Page(path=url, text="", title="", url=url, revision=f"error: {exc}")
                continue
            markdown = html_to_markdown(raw)
            path = urllib.parse.urlparse(url).path.strip("/") or "index"
            yield Page(path=path, text=markdown, title=_first_heading(markdown), url=url)


def _frontmatter_title(text: str) -> str:
    m = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
    if not m:
        return ""
    t = re.search(r"^title:\s*(.+?)\s*$", m.group(1), re.M)
    return t.group(1).strip().strip("\"'") if t else ""


def _first_heading(text: str) -> str:
    m = re.search(r"^#\s+(.+)$", text, re.M)
    return m.group(1).strip() if m else ""


def build(config: dict) -> Source:
    kind = config.get("type", "filesystem")
    if kind == "filesystem":
        return FilesystemSource(pathlib.Path(config["root"]))
    if kind == "cms-api":
        return CmsApiSource(config)
    if kind == "site-crawl":
        return SiteCrawlSource(config)
    raise ValueError(f"unknown source type: {kind}")


def materialise(source: Source, workdir: pathlib.Path) -> pathlib.Path:
    """Write a source's pages to disk so file-based tools can read them.

    Vale is a binary that takes paths. Rather than reimplement it, the pipeline
    stages whatever the source produced into a temporary tree and points the
    existing tools at that. The staging directory mirrors each page's `path`,
    so every finding's location is still something a writer can look up.
    """
    workdir = pathlib.Path(workdir)
    if workdir.exists():
        import shutil

        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)

    index = {}
    for page in source.pages():
        safe = page.path.strip("/") or "index"
        if not safe.endswith((".md", ".mdx")):
            safe += ".md"
        target = workdir / safe
        # Refuse to escape the staging directory: a CMS slug is untrusted input.
        if not target.resolve().is_relative_to(workdir.resolve()):
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page.text, encoding="utf-8")
        index[safe] = {"title": page.title, "url": page.url, "revision": page.revision}

    (workdir / "_index.json").write_text(json.dumps(index, indent=2, sort_keys=True))
    return workdir
