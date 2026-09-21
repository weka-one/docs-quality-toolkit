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

SCRIPT_BLOCK = re.compile(r"(?is)<script\b([^>]*)>(.*?)</script>")
STYLE_BLOCK = re.compile(r"(?is)<style\b[^>]*>(.*?)</style>")
# The name a payload is parked under, whichever framework parked it there.
PAYLOAD_NAME = re.compile(
    r"""(?x)
      id=["']([^"']+)["']                     # <script id="__NEXT_DATA__">
    | (?:window|self|globalThis)\.([A-Za-z_$][\w$]*)\s*=   # window.SIGI_STATE =
    | ^\s*(?:var|let|const)\s+([A-Za-z_$][\w$]*)\s*=       # var RENDER_DATA =
    """
)

# Words of readable text per KB of HTML. A server-rendered documentation page
# sits in the tens; an app shell sits under one.
MIN_DENSITY = 4.0


def density(html: str, words: int) -> float:
    return words / max(1.0, len(html) / 1024)


def looks_like_json(text: str) -> bool:
    stripped = text.strip()
    if stripped[:1] in "{[":
        return True
    # A payload assigned to a variable: find the first { or [ after the =.
    head = stripped[:400]
    return bool(re.search(r"=\s*[{\[]", head))


def inline_payloads(html: str) -> list[tuple[str, int, bool]]:
    """Large inline scripts, with whatever name they are parked under.

    Guessing framework names does not scale: the first version of this probe
    matched __NEXT_DATA__, __NUXT__ and a few others, and missed the site it
    was pointed at. Measuring the bytes works whatever the framework is called.
    """
    payloads = []
    for attrs, body in SCRIPT_BLOCK.findall(html):
        if not body.strip():
            continue        # <script src=...>, no inline content
        match = PAYLOAD_NAME.search(attrs) or PAYLOAD_NAME.search(body[:400])
        name = next((g for g in (match.groups() if match else ()) if g), "(anonymous)")
        payloads.append((name, len(body), looks_like_json(body)))
    return sorted(payloads, key=lambda p: -p[1])


def byte_budget(html: str) -> dict:
    script_bytes = sum(len(b) for _, b in SCRIPT_BLOCK.findall(html))
    style_bytes = sum(len(b) for b in STYLE_BLOCK.findall(html))
    return {
        "total": len(html),
        "inline_script": script_bytes,
        "inline_style": style_bytes,
        "markup": max(0, len(html) - script_bytes - style_bytes),
    }


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
    # A big JSON payload sitting inline means the prose shipped with the page,
    # just not as HTML. Detected by size and shape, not by framework name.
    payloads = inline_payloads(html)
    if payloads and payloads[0][1] >= 20_000 and payloads[0][2]:
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


def _analyse_page(args, base: str) -> tuple[bool, str]:
    """Fetch one page and report what is actually in it."""
    import time

    print("\npage content")
    sample = args.page or "/"
    sample_url = f"{base}/{sample.lstrip('/')}" if sample.strip("/") else base
    time.sleep(args.delay)
    status, html = fetch(sample_url)

    if args.dump and status == 200:
        args.dump.parent.mkdir(parents=True, exist_ok=True)
        args.dump.write_text(html, encoding="utf-8")
        print(f"  saved the HTML to {args.dump} ({len(html):,} bytes)")
    if status != 200:
        print(f"  {sample_url} returned HTTP {status}")
        return False, "blocked"

    text = html_to_markdown(html)
    words = len(re.findall(r"\b\w+\b", text))
    scripts = len(re.findall(r"(?i)<script", html))
    budget = byte_budget(html)
    print(f"  {sample_url}")
    print(f"  {len(html):,} bytes of HTML, {scripts} script tags")
    print(f"  reduces to {words:,} words of readable text "
          f"({density(html, words):.1f} words per KB)")
    print(f"  where the bytes are: {budget['inline_script']:,} in inline scripts, "
          f"{budget['inline_style']:,} in inline styles, {budget['markup']:,} in markup")
    payloads = inline_payloads(html)
    if payloads:
        print("  largest inline scripts:")
        for name, size, jsonish in payloads[:5]:
            print(f"    {size:>9,} bytes  {name}  ({'JSON-shaped' if jsonish else 'code'})")
    else:
        print("  no inline scripts with content")

    verdict = diagnose(html, words)
    if verdict == "ok":
        print("  -> the text is in the HTML; plain fetching works")
    elif verdict == "embedded":
        print("  -> little readable text, but a large JSON payload ships with the page")
    elif verdict == "spa":
        print("  -> an app shell with script bundles and no data payload")
    else:
        print("  -> a stub, not the real page")
    return verdict == "ok", verdict


def _page_section(args, base: str, one_request: bool = False) -> int:
    rendered_ok, verdict = _analyse_page(args, base)
    print("\n" + "=" * 60)
    if verdict == "ok":
        print("The text is in the HTML. Plain fetching works.")
    elif verdict == "embedded":
        print("The prose shipped with the page, inside a JSON payload.")
        print("No browser needed - an extractor that reads it is enough.")
    elif verdict == "spa":
        print("The page really is built in the browser: no data payload to read.")
        print("Getting the source text out of the CMS is the right path.")
    else:
        print("That was not the real page. Check the URL in a browser first.")
    print()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("base", nargs="?", default="",
                    help="site root, e.g. https://developers.tiktok.com")
    ap.add_argument("--file", type=pathlib.Path,
                    help="analyse a saved HTML file instead of fetching (no network)")
    ap.add_argument("--page", default="", help="a documentation page path to sample")
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--page-only", action="store_true",
                    help="skip robots.txt and the sitemap scan; fetch and analyse one page")
    ap.add_argument("--dump", type=pathlib.Path,
                    help="save the sampled page's HTML here, for working out how to read it")
    args = ap.parse_args()

    # Offline mode: everything worth knowing about rendering can be answered
    # from a page already on disk, without touching the site again.
    if args.file:
        if not args.file.is_file():
            print(
                f"\nNo file at {args.file}\n\n"
                "If you saved it with --dump into a folder you have since replaced,\n"
                "it is gone with the folder. Fetch the page again with one request:\n\n"
                f"  curl -s https://developers.tiktok.com/doc/overview > ~/Desktop/page.html\n"
                f"  python3 pipeline/probe.py --file ~/Desktop/page.html\n\n"
                "Saving outside this folder keeps it through an update.\n",
                file=sys.stderr,
            )
            return 1
        html = args.file.read_text(encoding="utf-8", errors="replace")
        if not html.strip():
            print(
                f"\n{args.file} is empty ({args.file.stat().st_size} bytes).\n\n"
                "The download produced nothing, so there is nothing to analyse. Use\n"
                "the probe's own fetcher instead of curl - it already pulled this\n"
                "page successfully:\n\n"
                "  python3 pipeline/probe.py https://developers.tiktok.com \\\n"
                "      --page /doc/overview --page-only --dump ~/Desktop/page.html\n",
                file=sys.stderr,
            )
            return 1
        text = html_to_markdown(html)
        words = len(re.findall(r"\b\w+\b", text))
        budget = byte_budget(html)
        verdict = diagnose(html, words)
        print(f"\nReading {args.file} ({len(html):,} bytes)\n" + "=" * 60)
        print(f"\n  {words:,} words of readable text ({density(html, words):.1f} per KB)")
        print(f"  bytes: {budget['inline_script']:,} inline script, "
              f"{budget['inline_style']:,} inline style, {budget['markup']:,} markup")
        payloads = inline_payloads(html)
        if payloads:
            print("\n  largest inline scripts:")
            for name, size, jsonish in payloads[:5]:
                print(f"    {size:>9,} bytes  {name}  "
                      f"({'JSON-shaped' if jsonish else 'code'})")
        else:
            print("\n  no inline scripts with content")
        print("\n" + "=" * 60)
        if verdict == "embedded":
            top = payloads[0]
            print(f"The prose shipped with the page, inside `{top[0]}` "
                  f"({top[1]:,} bytes).")
            print("No browser needed - an extractor that reads that payload is enough.")
        elif verdict == "ok":
            print("The text is in the HTML. Plain fetching works.")
        elif verdict == "blocked":
            print("This looks like a stub from a bot check or proxy, not the real page.")
        else:
            print("No sizeable inline payload: the page really is built in the browser.")
            print("Getting the source text out of the CMS is the right path.")
        print()
        return 0

    if not args.base:
        ap.error("give a site root, or --file to analyse a saved page")
    base = args.base.rstrip("/")
    print(f"\nProbing {base}\n" + "=" * 60)

    declared: list[str] = []
    found = None
    if args.page_only:
        print("\n(skipping robots.txt and the sitemap scan)")
        return _page_section(args, base, one_request=True)

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

    rendered_ok, verdict = _analyse_page(args, base)

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
    elif verdict == "spa":
        print("No sitemap, and the pages are assembled in the browser.")
        print("Page discovery is solvable - the crawler can follow links from a seed")
        print("page (discover_from) or take a list of URLs. Rendering is the blocker.")
        print("\nOptions, best first:")
        print("  1. Ask whoever runs the CMS for an export or a read API. The source")
        print("     text is what you want to check anyway.")
        print("  2. Render each page with a headless browser before checking it.")
        print("\nBefore either, check the byte breakdown above: if most of the page")
        print("is one large JSON-shaped inline script, the prose shipped with the")
        print("page and an extractor is enough.")
    else:
        print("Neither a sitemap nor readable page text. This site cannot be checked")
        print("by fetching it. Get the source text out of the CMS instead.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
