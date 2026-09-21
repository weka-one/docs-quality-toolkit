"""Read a page the way a reader does: let a browser render it, then take the text.

The JSON-island reader in `json_island.py` guesses. It looks through whatever
data a site inlines and scores each string on how much it reads like prose. On
developers.tiktok.com that guess lands on the site's own interface copy - the
newsletter blurb, the NDA modal, the unsubscribe line - because those are long,
grammatical English sentences sitting in a translation dictionary. The actual
documentation is chopped into fragments too short to score. No amount of tuning
makes guessing reliable, because every site hides its content in a different
shape and changes that shape without warning.

This module stops guessing. It runs a real browser with no window, waits for the
page to finish assembling itself, and reads the finished document. That works on
any site, needs no knowledge of the framework, and survives a redesign.

The cost is time - roughly a second or two per page against a few milliseconds -
which is the right trade for a check that runs nightly rather than per keystroke.
Two things keep it viable over a whole documentation set:

    one browser for the entire batch, not one per page
    images, fonts and video refused before they are fetched

The second matters more than it sounds. A documentation page is mostly pictures
by weight and entirely text by value.

What the browser gives us that the JSON never could is structure. A rendered
page says which part is navigation, which is the footer, and which is the
article. `MAIN_SELECTORS` and `PICK_MAIN_JS` use that to return the body of the
document and leave the site furniture behind, which is the failure this module
exists to fix.
"""
from __future__ import annotations

import os
import pathlib
import re
import sys
import urllib.parse
from typing import Iterator, Optional

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from pipeline.sources import (  # noqa: E402
    Page,
    SiteCrawlSource,
    SourceError,
    _first_heading,
    html_to_markdown,
)

#: Tried in order. Every one is a standard way of saying "the content is here",
#: so the list is about documentation sites in general, not any single one.
MAIN_SELECTORS = (
    "main",
    '[role="main"]',
    "article",
    "#main-content",
    "#content",
    ".markdown-body",
    ".markdown",
    ".doc-content",
    ".docs-content",
    ".article-content",
    ".content-wrapper",
)

#: Stripped from whatever container wins. These are the parts of a page that
#: repeat on every page, which is exactly what a per-page check must not read.
CHROME_SELECTOR = (
    "script,style,noscript,template,svg,iframe,form,button,"
    "nav,header,footer,aside,"
    '[role="navigation"],[role="banner"],[role="contentinfo"],[role="search"],'
    '[aria-hidden="true"],[hidden]'
)

#: How little text means the page never really arrived.
MIN_CONTENT_CHARS = 200

PICK_MAIN_JS = """
(args) => {
  const { selectors, chrome, minChars } = args;
  const clean = (el) => {
    const copy = el.cloneNode(true);
    copy.querySelectorAll(chrome).forEach((n) => n.remove());
    return copy;
  };
  const size = (el) => (el.textContent || '').replace(/\\s+/g, ' ').trim().length;

  // A named container is the site telling us where its content is. Take the
  // first one that holds enough text to be the content, and remember the
  // biggest of them either way: on a short page nothing clears the bar, and a
  // small <main> is still a better answer than the whole document.
  let named = null, namedSize = 0;
  for (const sel of selectors) {
    for (const el of document.querySelectorAll(sel)) {
      const copy = clean(el);
      const n = size(copy);
      if (n >= minChars) return { html: copy.innerHTML, via: sel, chars: n };
      if (n > namedSize) { named = copy; namedSize = n; named.__via = sel; }
    }
  }

  // Nothing named is big enough. Score containers by the text sitting in real
  // content tags - paragraphs, headings, list items, code, table cells.
  // Navigation scores near zero here because menus are links, not prose, which
  // is the whole reason to measure it this way.
  const BLOCKS = 'p,h1,h2,h3,h4,h5,h6,li,pre,code,td,th,dd,blockquote';
  let dense = null, denseScore = 0, denseDepth = -1;
  for (const el of document.querySelectorAll('body div,body section,body article,body td')) {
    const copy = clean(el);
    let score = 0;
    copy.querySelectorAll(BLOCKS).forEach((b) => { score += size(b); });
    let depth = 0;
    for (let n = el; n; n = n.parentElement) depth++;
    // A parent always scores at least as high as its child, so on a tie take
    // the deeper one: the tightest wrapper, carrying the least chrome.
    if (score > denseScore || (score === denseScore && score > 0 && depth > denseDepth)) {
      dense = copy; denseScore = score; denseDepth = depth;
    }
  }
  if (denseScore >= minChars) return { html: dense.innerHTML, via: 'densest-block', chars: denseScore };

  // Both are under the bar, so this is simply a short page. Prefer whichever
  // actually found something, and fall back to the stripped document.
  if (namedSize >= denseScore && namedSize > 0) {
    return { html: named.innerHTML, via: named.__via, chars: namedSize };
  }
  if (denseScore > 0) return { html: dense.innerHTML, via: 'densest-block', chars: denseScore };
  const body = clean(document.body);
  return { html: body.innerHTML, via: 'body', chars: size(body) };
}
"""

_INSTALL_HELP = """This step needs a headless browser, which is not installed yet.

Two commands, once:

    python3 -m pip install --user playwright
    python3 -m playwright install chromium

The first installs the controller, the second downloads a private copy of
Chromium (about 150 MB) that is used only by this tool. Neither needs Homebrew
and neither touches the browser you browse with."""


def _require_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SourceError(_INSTALL_HELP) from None
    return sync_playwright


class Renderer:
    """One browser, held open for a whole batch of pages.

    Starting a browser costs far more than loading a page in one, so a run that
    launched per page would spend most of its time on startup. Held open, the
    per-page cost is the page itself.
    """

    BLOCKED_RESOURCES = {"image", "media", "font"}

    def __init__(
        self,
        timeout_ms: int = 30000,
        settle_ms: int = 400,
        user_agent: str = "",
        block_resources: bool = True,
        browser_path: str = "",
    ):
        self.timeout_ms = timeout_ms
        self.settle_ms = settle_ms
        self.user_agent = user_agent
        self.block_resources = block_resources
        # An escape hatch for a machine that already has Chrome, or one where
        # the download is blocked. Empty means "use Playwright's own copy".
        self.browser_path = browser_path or os.environ.get("DOCS_PIPELINE_BROWSER", "")
        self._pw = None
        self._browser = None
        self._context = None

    def __enter__(self):
        sync_playwright = _require_playwright()
        self._pw = sync_playwright().start()
        try:
            self._browser = self._pw.chromium.launch(
                headless=True,
                executable_path=self.browser_path or None,
            )
        except Exception as exc:
            self._pw.stop()
            raise SourceError(
                f"{_INSTALL_HELP}\n\n(The browser failed to start: {exc})"
            ) from None
        self._context = self._browser.new_context(
            user_agent=self.user_agent or None,
            java_script_enabled=True,
        )
        self._context.set_default_timeout(self.timeout_ms)
        if self.block_resources:
            # Refusing pictures before they are fetched is most of the speed.
            self._context.route(
                "**/*",
                lambda route: (
                    route.abort()
                    if route.request.resource_type in self.BLOCKED_RESOURCES
                    else route.continue_()
                ),
            )
        return self

    def __exit__(self, *exc):
        for closer in (self._context, self._browser):
            try:
                closer and closer.close()
            except Exception:
                pass
        try:
            self._pw and self._pw.stop()
        except Exception:
            pass
        self._pw = self._browser = self._context = None
        return False

    def content_html(self, url: str) -> tuple[str, str]:
        """Load `url`, wait for it to assemble, return (content HTML, how found)."""
        if self._context is None:
            raise SourceError("Renderer must be used as a context manager.")
        page = self._context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
            # An app shell arrives empty and fills in a moment later. Wait for the
            # text to appear rather than for a fixed period, so a fast page stays
            # fast and a slow one still works.
            try:
                page.wait_for_function(
                    "min => document.body && document.body.innerText.trim().length >= min",
                    arg=MIN_CONTENT_CHARS,
                    timeout=self.timeout_ms,
                )
            except Exception:
                pass          # a genuinely short page is still a page
            if self.settle_ms:
                page.wait_for_timeout(self.settle_ms)
            result = page.evaluate(
                PICK_MAIN_JS,
                {
                    "selectors": list(MAIN_SELECTORS),
                    "chrome": CHROME_SELECTOR,
                    "minChars": MIN_CONTENT_CHARS,
                },
            )
            return result.get("html", ""), result.get("via", "")
        finally:
            try:
                page.close()
            except Exception:
                pass


class RenderedCrawlSource(SiteCrawlSource):
    """A site crawl that renders each page instead of reading raw HTML.

    Everything about which pages to visit, and how politely, is inherited: the
    sitemap and link discovery, robots.txt, the delay between requests, the host
    restriction. Only the fetch changes.
    """

    name = "rendered-crawl"

    def __init__(self, config: dict, renderer=None):
        super().__init__(config)
        self._renderer = renderer
        self.picked_via: dict[str, str] = {}

    def _make_renderer(self):
        return Renderer(
            timeout_ms=int(self.config.get("timeout", 30)) * 1000,
            settle_ms=int(self.config.get("settle_ms", 400)),
            user_agent=self.user_agent,
            block_resources=self.config.get("block_resources", True),
            browser_path=self.config.get("browser_path", ""),
        )

    def pages(self) -> Iterator[Page]:
        import contextlib
        import time

        urls = self.urls()
        if not urls:
            return
        # An injected renderer is already open; ours is opened for this batch.
        opened = self._renderer or self._make_renderer()
        manager = contextlib.nullcontext(opened) if self._renderer else opened
        with manager as renderer:
            for i, url in enumerate(urls):
                if i:
                    time.sleep(self.delay)
                try:
                    raw, via = renderer.content_html(url)
                except SourceError:
                    raise
                except Exception as exc:    # one bad page must not end the run
                    yield Page(
                        path=_url_path(url), text="", title="",
                        url=url, revision=f"error: {exc}",
                    )
                    continue
                self.picked_via[url] = via
                markdown = html_to_markdown(raw)
                yield Page(
                    path=_url_path(url),
                    text=markdown,
                    title=_first_heading(markdown),
                    url=url,
                )


def _url_path(url: str) -> str:
    return urllib.parse.urlparse(url).path.strip("/") or "index"


def _words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def main(argv: Optional[list] = None) -> int:
    """Render one page and show what came back, before committing to a batch."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Render a single page in a headless browser and show the text.",
    )
    parser.add_argument("url", help="the page to render")
    parser.add_argument("--chars", type=int, default=600,
                        help="how much of the text to print (default 600)")
    parser.add_argument("--html", action="store_true",
                        help="print the extracted HTML instead of the Markdown")
    parser.add_argument("--timeout", type=int, default=30, help="seconds (default 30)")
    parser.add_argument("--browser-path", default="",
                        help="use this Chrome/Chromium binary instead of Playwright's own")
    args = parser.parse_args(argv)

    try:
        with Renderer(timeout_ms=args.timeout * 1000,
                      browser_path=args.browser_path) as renderer:
            html_text, via = renderer.content_html(args.url)
    except SourceError as exc:
        print(f"\n{exc}\n")
        return 1
    except Exception as exc:
        print(f"\nCould not render {args.url}\n  {type(exc).__name__}: {exc}\n")
        return 1

    markdown = html_to_markdown(html_text)
    body = html_text if args.html else markdown
    print(f"\nRendered {args.url}")
    print(f"  content found via: {via}")
    print(f"  {_words(markdown):,} words, {len(html_text):,} bytes of HTML")
    heading = _first_heading(markdown)
    print(f"  first heading: {heading or '(none)'}")
    if _words(markdown) < 50:
        print("\n  That is very little text. The page may need longer to load")
        print("  (try --timeout 60), or it may genuinely be a stub.")
    print(f"\n{'-' * 68}\n")
    print(body[: args.chars])
    if len(body) > args.chars:
        print(f"\n[... {len(body) - args.chars:,} more characters]")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
