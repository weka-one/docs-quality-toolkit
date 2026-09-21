#!/usr/bin/env python3
"""Deterministic remediation for the mechanically-fixable subset of rules.

Only a minority of style rules can be fixed by a machine. `Terminology` and
`ApiKeyCase` are pure substitutions with exactly one correct output.
`Filler`, `FirstPerson` and `SentenceLength` need a human to decide what the
sentence was trying to say, and a tool that guesses at those produces prose
that passes the linter while reading worse than the original.

That split is the point of the before/after measurement: it shows how much of a
style backlog is genuinely automatable, rather than implying all of it is.

Fixes are applied to prose only — see valelib.split_prose. Rewriting a quote or
a capitalised term inside a code sample would break the sample.

Usage:
    tools/remediate.py --src ../corpus/meilisearch-docs --dst build/after
    tools/remediate.py --src ../corpus/meilisearch-docs --dst build/after --dry-run
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import valelib  # noqa: E402


def keep_case(replacement: str):
    """Return a re.sub callable that mirrors the matched text's capitalisation.

    'Click on' -> 'Click', 'click on' -> 'click'. Without this, a fix at the
    start of a sentence silently lowercases it.
    """

    def repl(m: re.Match) -> str:
        found = m.group(0)
        if found.isupper() and len(found) > 1:
            return replacement.upper()
        if found[:1].isupper():
            return replacement[:1].upper() + replacement[1:]
        return replacement

    return repl


def drop_and_capitalise(m: re.Match) -> str:
    """Delete a filler stem and re-capitalise the word that now starts the sentence."""
    rest = m.group("rest")
    return rest[:1].upper() + rest[1:]


I = re.IGNORECASE
M = re.MULTILINE

# rule name -> list of (compiled pattern, replacement)
# Rule names match the Vale check they resolve, so the report can attribute
# every fix to the rule that would otherwise have flagged it.
FIXES: dict[str, list[tuple[re.Pattern, object]]] = {
    "ApiKeyCase": [
        (re.compile(r"\bAPI[ ]Key(s?)\b"), r"API key\1"),
        (re.compile(r"\bApi[ ][Kk]ey(s?)\b"), r"API key\1"),
        (re.compile(r"\bapi[ ][Kk]ey(s?)\b"), r"API key\1"),
        (re.compile(r"\bAPI[ ]KEY(S?)\b"), "API key"),
        (re.compile(r"\bAccess[ ]Token(s?)\b"), r"access token\1"),
        (re.compile(r"\bRefresh[ ]Token(s?)\b"), r"refresh token\1"),
        (re.compile(r"\bBearer[ ]Token(s?)\b"), r"bearer token\1"),
        (re.compile(r"\bClient[ ]Secret(s?)\b"), r"client secret\1"),
    ],
    "Terminology": [
        (re.compile(r"\bJavascript\b|\bJava[ ]Script\b"), "JavaScript"),
        (re.compile(r"\bTypescript\b"), "TypeScript"),
        (re.compile(r"\bNodeJS\b|\bNode\.JS\b"), "Node.js"),
        (re.compile(r"\bGithub\b"), "GitHub"),
        (re.compile(r"\bJSon\b|\bJson\b"), "JSON"),
        (re.compile(r"\bYaml\b"), "YAML"),
        (re.compile(r"\bUrl(s?)\b"), r"URL\1"),
        (re.compile(r"\bUri\b"), "URI"),
        (re.compile(r"\bHttps\b"), "HTTPS"),
        (re.compile(r"\bHttp\b"), "HTTP"),
        (re.compile(r"\bSdk(s?)\b"), r"SDK\1"),
        (re.compile(r"\bApi(s?)\b"), r"API\1"),
        (re.compile(r"\bUuid\b"), "UUID"),
        (re.compile(r"\bJwt\b"), "JWT"),
        (re.compile(r"\bOauth\b|\boauth\b|\bOAuth2(?:\.0)?\b"), "OAuth 2.0"),
        (re.compile(r"\bweb[ ]hook(s?)\b", I), keep_case("webhook")),
        (re.compile(r"\bweb[ ]site(s?)\b", I), keep_case("website")),
        (re.compile(r"\be-mail(s?)\b", I), keep_case("email")),
        (re.compile(r"\bdata[ ]base(s?)\b", I), keep_case("database")),
        (re.compile(r"\bMacOS\b|\bMac[ ]OS[ ]X\b|\bMac[ ]OS\b"), "macOS"),
    ],
    "UIActions": [
        (re.compile(r"\bclick[ ]on\b", I), keep_case("click")),
        (re.compile(r"\btap[ ]on\b", I), keep_case("tap")),
        (re.compile(r"\bpress[ ]on\b", I), keep_case("press")),
        (re.compile(r"\bright[ ]click\b", I), keep_case("right-click")),
    ],
    "CurlyQuotes": [
        (re.compile("[“”]"), '"'),
        (re.compile("[‘’]"), "'"),
    ],
    "InclusiveLanguage": [
        (re.compile(r"\bwhite[ -]?list(s|ed|ing)?\b", I), keep_case("allowlist")),
        (re.compile(r"\bblack[ -]?list(s|ed|ing)?\b", I), keep_case("blocklist")),
        (re.compile(r"\bmaster/slave\b", I), keep_case("primary/replica")),
        (re.compile(r"\bsanity[ ]check\b", I), keep_case("consistency check")),
        (re.compile(r"\bgrandfathered\b", I), keep_case("legacy")),
    ],
    "GenderNeutral": [
        (re.compile(r"\bhe/she\b", I), keep_case("they")),
        (re.compile(r"\bs/he\b", I), keep_case("they")),
        (re.compile(r"\bhis/her\b", I), keep_case("their")),
        (re.compile(r"\bhim/her\b", I), keep_case("them")),
        (re.compile(r"\bhis[ ]or[ ]her\b", I), keep_case("their")),
        (re.compile(r"\bhe[ ]or[ ]she\b", I), keep_case("they")),
    ],
    "Wordiness": [
        (re.compile(r"\bin[ ]order[ ]to\b", I), keep_case("to")),
        (re.compile(r"\bin[ ]order[ ]for\b", I), keep_case("for")),
        (re.compile(r"\bat[ ]th(?:is|e)[ ](?:point[ ]in[ ]time|present[ ]time)\b", I), keep_case("now")),
        (re.compile(r"\bdue[ ]to[ ]the[ ]fact[ ]that\b", I), keep_case("because")),
        (re.compile(r"\bin[ ]the[ ]event[ ]that\b", I), keep_case("if")),
        (re.compile(r"\bfor[ ]the[ ]purpose[ ]of\b", I), keep_case("for")),
        (re.compile(r"\bprior[ ]to\b", I), keep_case("before")),
        (re.compile(r"\bsubsequent[ ]to\b", I), keep_case("after")),
        (re.compile(r"\bthe[ ]majority[ ]of\b", I), keep_case("most")),
        (re.compile(r"\butilizes\b", I), keep_case("uses")),
        (re.compile(r"\butilized\b", I), keep_case("used")),
        (re.compile(r"\butilize\b", I), keep_case("use")),
        (re.compile(r"\bleverages\b", I), keep_case("uses")),
        (re.compile(r"\bleveraged\b", I), keep_case("used")),
        (re.compile(r"\bleverage\b", I), keep_case("use")),
        (re.compile(r"\bmake[ ]use[ ]of\b", I), keep_case("use")),
        (re.compile(r"\bis[ ]able[ ]to\b", I), "can"),
        (re.compile(r"\bare[ ]able[ ]to\b", I), "can"),
        (re.compile(r"\bhas[ ]the[ ]ability[ ]to\b", I), "can"),
    ],
    "AllowsYouTo": [
        (re.compile(r"\ballows[ ]you[ ]to\b", I), keep_case("lets you")),
        (re.compile(r"\ballow[ ]you[ ]to\b", I), keep_case("let you")),
        (re.compile(r"\benables[ ]you[ ]to\b", I), keep_case("lets you")),
        (re.compile(r"\benable[ ]you[ ]to\b", I), keep_case("let you")),
        (re.compile(r"\bpermits[ ]you[ ]to\b", I), keep_case("lets you")),
        (re.compile(r"\bgives[ ]you[ ]the[ ]ability[ ]to\b", I), keep_case("lets you")),
    ],
    "LatinAbbreviations": [
        (re.compile(r"\be\.g\.,?[ ]"), "for example, "),
        (re.compile(r"\bi\.e\.,?[ ]"), "that is, "),
        (re.compile(r",[ ]*etc\."), ", and so on."),
        (re.compile(r"[ ]etc\."), " and so on."),
        (re.compile(r"\bvs\.[ ]"), "versus "),
    ],
}

# Line- and sentence-anchored rules.
#
# These cannot go through `sub_in_prose`: it masks inline code spans, so a
# pattern anchored with `$` matches at the mask boundary instead of the end of
# the line. That turned "##### Response: `201 Created`" into
# "##### Response`201 Created`" before this split existed.
#
# `skip_quoted` protects documented UI strings. Deleting "Please" from
# `"High demand right now. Please wait a moment."` makes the docs describe an
# error message the product never emits.
LINE_FIXES: dict[str, list[tuple[re.Pattern, object, bool]]] = {
    "HeadingPunctuation": [
        # '?' is deliberately preserved: "What is a task?" is a valid heading.
        (re.compile(r"^(#{1,6}[ ].*?)[.!;:]+[ \t]*$", M), r"\1", False),
    ],
    "Please": [
        # Sentence-initial only. Mid-sentence "please" usually sits inside a
        # quoted string or a UI label where deleting it changes meaning.
        (re.compile(r"(?:^|(?<=[.!?][ ]))[Pp]lease[ ](?P<rest>\w)", M), drop_and_capitalise, True),
    ],
    "NoteThat": [
        (re.compile(r"(?:^|(?<=[.!?][ ]))(?:[Nn]ote|[Pp]lease[ ]note)[ ]that[ ](?P<rest>\w)", M), drop_and_capitalise, True),
        (re.compile(r"(?:^|(?<=[.!?][ ]))[Kk]eep[ ]in[ ]mind[ ]that[ ](?P<rest>\w)", M), drop_and_capitalise, True),
        (re.compile(r"(?:^|(?<=[.!?][ ]))[Bb]ear[ ]in[ ]mind[ ]that[ ](?P<rest>\w)", M), drop_and_capitalise, True),
    ],
}

# Rules deliberately left to humans, with the reason. Surfaced in the report so
# the unfixed remainder is explained rather than merely counted.
NOT_AUTOMATABLE = {
    "Filler": "deleting 'simply' can leave a sentence that no longer parses; the fix is usually a rewrite",
    "FirstPerson": "requires knowing whether 'we' means the product, the team, or the reader",
    "Hedging": "requires deciding whether the step is required or optional - a judgement about the API, not the prose",
    "SentenceLength": "splitting a sentence requires understanding it",
    "Acronyms": "the expansion has to be written, and belongs at first use, which may be on another page",
    "HeadingSentenceCase": "cannot distinguish a product name from a capitalised common noun without a maintained vocabulary",
    "LinkText": "the replacement text is the destination's subject, which means reading the destination",
    "EndpointInCode": "adding code spans changes rendering; safe in prose, unsafe inside tables and existing spans",
    "HTTPMethodCase": "'get /path' is ambiguous between the HTTP method and the English verb",
    "StatusCodeName": "requires mapping the numeric code to its canonical reason phrase in context",
}


def remediate_text(text: str) -> tuple[str, collections.Counter]:
    counts: collections.Counter = collections.Counter()
    for rule, patterns in FIXES.items():
        for pattern, repl in patterns:
            text, n = valelib.sub_in_prose(text, pattern, repl)
            if n:
                counts[rule] += n
    for rule, patterns in LINE_FIXES.items():
        for pattern, repl, skip_quoted in patterns:
            text, n = valelib.sub_outside_code(text, pattern, repl, skip_quoted=skip_quoted)
            if n:
                counts[rule] += n
    return text, counts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, type=pathlib.Path)
    ap.add_argument("--dst", required=True, type=pathlib.Path)
    ap.add_argument("--dry-run", action="store_true", help="report counts without writing")
    ap.add_argument("--json", type=pathlib.Path, help="write per-rule fix counts here")
    args = ap.parse_args()

    src = args.src.resolve()
    if not src.is_dir():
        sys.exit(f"source corpus not found: {src}")

    files = sorted(src.rglob("*.mdx")) + sorted(src.rglob("*.md"))
    if not args.dry_run:
        if args.dst.exists():
            shutil.rmtree(args.dst)
        args.dst.mkdir(parents=True)

    totals: collections.Counter = collections.Counter()
    touched = 0
    for path in files:
        original = path.read_text(encoding="utf-8")
        fixed, counts = remediate_text(original)
        if counts:
            touched += 1
            totals.update(counts)
        if not args.dry_run:
            out = args.dst / path.relative_to(src)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(fixed, encoding="utf-8")

    total = sum(totals.values())
    print(f"{len(files)} files scanned, {touched} modified, {total} fixes applied\n")
    width = max((len(r) for r in totals), default=10)
    for rule, n in totals.most_common():
        print(f"  {rule:<{width}}  {n:>5}")
    if not totals:
        print("  (no mechanically-fixable violations found)")
    print(f"\n{len(NOT_AUTOMATABLE)} rules left to human review by design:")
    for rule, why in sorted(NOT_AUTOMATABLE.items()):
        print(f"  {rule}: {why}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(
                {
                    "files_scanned": len(files),
                    "files_modified": touched,
                    "fixes_total": total,
                    "fixes_by_rule": dict(totals),
                    "not_automatable": NOT_AUTOMATABLE,
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
