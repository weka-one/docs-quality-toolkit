#!/usr/bin/env python3
"""Find out whether a site can be crawled, before trying to crawl it.

Answers, in one pass:

  * does robots.txt name a sitemap, and what does it allow?
  * is there a sitemap at any of the usual addresses?
  * does a page return readable text, or an empty shell that only fills in
    once JavaScript runs?

That last question is the one that decides the approach. A modern docs site is
often rendered in the browser: fetching the URL returns a few hundred bytes of
scaffolding and no prose. Plain fetching cannot check a site like that, and it
is better to find out in one request than after crawling a thousand pages of
nothing.

    pipeline/probe.py https://developers.tiktok.com
    pipeline/probe.py https://developers.tiktok.com --page /doc/login-kit-web
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from pipeline.sources import html_to_markdown  # noqa: E402

UA = "docs-pipeline-probe/1.0 (checking whether this site can be crawled)"
COMMON_SITEMAPS = [
    "/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml",
    "/sitemap/sitemap.xml", "/docs/sitemap.xml", "/sitemap.txt",
]


# A page with no readable text has three very different causes, and they lead
# to three different decisions. Guessing wrong sends someone to build a
# headless-browser crawler when the real problem was a corporate proxy.
BLOCKED_MARKERS = re.compile(
    r"(?i)(just a moment|checking your browser|attention required|access denied"
    r"|captcha|cf-chl|cf-browser-verification|ddos protection|request blocked"
    r"|enable javascript (?:and cookies )?to continue|are you a robot)"
)
SPA_ROOTS = re.compile(r'(?i)<div[^>]+id=["\'](root|__next|app|__nuxt|svelte)["\']')

# Frameworks that server-render into a JSON island rather than into HTML. The
# prose IS in the response, just not as text - which is a far easier problem
# than a page that has to be executed to exist.
EMBEDDED_DATA = re.compile(
    r"(__NEXT_DATA__|self\.__next_f|__NUXT__|__remixContext"
    r"|window\.__INITIAL_STATE__|window\.__APOLLO_STATE__|__sveltekit_)"
)

# Words of readable text per KB of HTML. A server-rendered documentation page
# sits in the tens; an app shell sits under one.
MIN_DENSITY = 4.0


def density(html: str, words: int) -> float:
    return words / max(1.0, len(html) / 1024)


def diagnose(html: str, words: int) -> str:
    """Why does this page have little text: blocked, embedded, rendered, or fine?

    Word count alone is not enough. A 229 KB page yielding 161 words passed an
    earlier `words >= 150` check and was reported as fine; at 0.7 words per KB
    it was an app shell whose prose never appeared in the HTML at all. Density
    is what separates a real page from a wrapper around one.
    """
    if BLOCKED_MARKERS.search(html):
        return "blocked"
    if words >= 150 and density(html, words) >= MIN_DENSITY:
        return "ok"
    if EMBEDDED_DATA.search(html):
        return "embedded"
    bundles = len(re.findall(r'(?i)<script[^>]+src=', html))
    if SPA_ROOTS.search(html) or bundles >= 3:
        return "spa"
    if len(html) < 5000:
        # Small, no app shell, no bundles, no text: a stub served by something
        # in the middle rather than the real page.
        return "blocked"
    return "spa"


def fetch(url: str, timeout: int = 30) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except Exception as exc:
        return 0, f"{type(exc).__name__}: {exc}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("base", help="site root, e.g. https://developers.tiktok.com")
    ap.add_argument("--page", default="", help="a documentation page path to sample")
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--dump", type=pathlib.Path,
                    help="save the sampled page's HTML here, for working out how to read it")
    args = ap.parse_args()

    base = args.base.rstrip("/")
    print(f"\nProbing {base}\n" + "=" * 60)

    # --- robots.txt -------------------------------------------------------
    print("\nrobots.txt")
    status, body = fetch(f"{base}/robots.txt")
    declared: list[str] = []
    if status == 200:
        declared = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", body)
        disallows = re.findall(r"(?im)^\s*disallow:\s*(\S*)", body)
        print(f"  found ({len(body)} bytes)")
        if declared:
            for entry in declared:
                print(f"  declares a sitemap: {entry}")
        else:
            print("  no Sitemap: line")
        if disallows:
            shown = [d for d in disallows if d][:8]
            print(f"  disallows {len(disallows)} path(s)" + (f": {', '.join(shown)}" if shown else ""))
    else:
        print(f"  not available (HTTP {status}) - no published rules, crawling is permitted by default")

    # --- sitemaps ---------------------------------------------------------
    print("\nsitemap")
    found = None
    for candidate in [*declared, *[base + p for p in COMMON_SITEMAPS]]:
        time.sleep(args.delay)
        url = candidate if candidate.startswith("http") else base + candidate
        status, body = fetch(url)
        if status == 200 and ("<urlset" in body or "<sitemapindex" in body or body.strip().startswith("http")):
            count = len(re.findall(r"<loc>", body)) or len(body.strip().splitlines())
            kind = "index of sitemaps" if "<sitemapindex" in body else "list of pages"
            print(f"  OK  {url}\n      {kind}, {count} entries")
            found = url
            break
        if status == 200:
            looks = ("HTML" if "<html" in body[:2000].lower() else
                     "JSON" if body.lstrip()[:1] in "{[" else "something else")
            print(f"  200 {url}\n      but it is {looks} ({len(body):,} bytes), not a sitemap")
        else:
            print(f"  --  {url} (HTTP {status})")

    # --- can a page be read without a browser? ---------------------------
    print("\npage content")
    sample = args.page or "/"
    sample_url = f"{base}/{sample.lstrip('/')}" if sample.strip("/") else base
    time.sleep(args.delay)
    status, html = fetch(sample_url)
    if args.dump and status == 200:
        args.dump.write_text(html, encoding="utf-8")
        print(f"  saved the HTML to {args.dump} ({len(html):,} bytes)")
    if status != 200:
        print(f"  {sample_url} returned HTTP {status}")
        verdict = "blocked"
        rendered_ok = False
    else:
        text = html_to_markdown(html)
        words = len(re.findall(r"\b\w+\b", text))
        scripts = len(re.findall(r"(?i)<script", html))
        print(f"  {sample_url}")
        print(f"  {len(html):,} bytes of HTML, {scripts} script tags")
        print(f"  reduces to {words:,} words of readable text "
              f"({density(html, words):.1f} words per KB)")
        verdict = diagnose(html, words)
        rendered_ok = verdict == "ok"
        if verdict == "ok":
            print("  -> the text is in the HTML; plain fetching works")
        elif verdict == "embedded":
            print("  -> little readable text, but the page carries a JSON data island")
            print("     (Next.js, Nuxt, Remix or similar). The prose IS in the")
            print("     response, just not as HTML text.")
        elif verdict == "spa":
            print("  -> almost no text, but the page carries an app shell and script")
            print("     bundles. It is assembled in the browser by JavaScript.")
        else:
            print("  -> almost no text, and no app shell either. Something between")
            print("     you and the site returned a stub: a bot check, a corporate")
            print("     proxy, or a firewall. This is NOT a JavaScript problem.")

    # --- verdict ----------------------------------------------------------
    print("\n" + "=" * 60)
    if found and rendered_ok:
        print("Ready to crawl. Put this in config.tiktok.yml:\n")
        print(f"  sitemap_url: {found}\n")
    elif verdict == "embedded":
        print("The prose is in the page, inside a JSON payload rather than as HTML.")
        print("This is the good version of the problem: no browser needed, just an")
        print("extractor that reads that payload. Send me the output of:\n")
        print(f"  python3 pipeline/probe.py {base} --page {args.page or '/'} --dump page.html\n")
        print("and I can write the extractor against the real shape.")
    elif found and verdict == "spa":
        print("A sitemap exists, but the pages are assembled in the browser.")
        print("Crawling would collect empty pages. Options, best first:")
        print("  1. Ask whether the CMS can export the source text, or offer a read API.")
        print("  2. Render each page with a headless browser before checking it.")
        print("  3. Check the source text before it is published, not the live site.")
    elif found:
        print("A sitemap exists, but the sample page came back as a stub.")
        print("Before changing anything, rule out the network:")
        print("  1. Open that page in a browser and use View Source. If the text is")
        print("     there, the site is fine and something in between is blocking.")
        print("  2. Try off the corporate network or VPN.")
        print("  3. Re-run with --delay 5 in case of rate limiting.")
    elif rendered_ok:
        print("Pages are readable, but no sitemap was found.")
        print("Options: ask whether one exists at a non-standard address, or give the")
        print("crawler a list of URLs instead of a sitemap.")
    else:
        print("Neither a sitemap nor readable page text. This site cannot be checked")
        print("by fetching it. Get the source text out of the CMS instead.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
