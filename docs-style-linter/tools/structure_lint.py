#!/usr/bin/env python3
"""Structural checks Vale cannot express.

Vale reasons about spans of prose. A large part of the TT4D style guide is
about *document structure* -- what sections a reference page has and in what
order, whether a heading level was skipped, which column of a table a value
sits in, whether a code fence declares a language. None of that is a regex over
text, and trying to force it into one produces rules that are wrong in ways
that are hard to see.

`RequirementColumn` is the worked example. As a Vale rule scoped to table
cells, it flagged every cell containing `true` -- 90 on the evaluation corpus --
because Vale has no concept of which column a cell belongs to. Here it reads
the header row first and only checks cells under `Required`.

Each check maps to a line in the guide's pre-publish checklist (Appendix B).
Checks that need a human stay in the checklist and are listed in COVERAGE.md
rather than faked here.

Usage:
    tools/structure_lint.py <docs-dir> [--format markdown|json] [--fail-on error]
"""
from __future__ import annotations

import argparse
import collections
import dataclasses
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import valelib  # noqa: E402

# --------------------------------------------------------------------- policy
#
# Everything that varies by house style is loaded from a config file, not
# hardcoded. The checks below are the mechanism; config/*.yml is the policy.

DEFAULT_CONFIG = pathlib.Path(__file__).resolve().parents[1] / "config" / "tiktok.yml"


def load_policy(path: pathlib.Path) -> dict:
    import yaml

    policy = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    policy.setdefault("h1_source", "heading")
    policy.setdefault("approved_fences", [])
    policy.setdefault("required_column_values", ["Yes", "No", "Conditional"])
    policy.setdefault("banned_column_names", [])
    policy.setdefault("max_table_columns", 5)
    policy.setdefault("approved_callouts", [])
    policy.setdefault("retired_callouts", {})
    policy.setdefault("max_callouts_per_section", 2)
    policy.setdefault("exclude", [])
    policy.setdefault("globally_known_placeholders", [])

    # YAML 1.1 keyword coercion turns a bare `Yes` into True. Caught here
    # rather than at the point of use, where it surfaces as a confusing
    # TypeError deep inside a check.
    problems = []
    for key in ("approved_fences", "required_column_values", "banned_column_names",
                "approved_callouts", "exclude", "globally_known_placeholders"):
        for item in policy[key]:
            if not isinstance(item, str):
                problems.append(
                    f"{key}: {item!r} parsed as {type(item).__name__}, not str "
                    "- quote it (YAML 1.1 reads bare Yes/No/On/Off as booleans)"
                )
    if not isinstance(policy["h1_source"], str) or policy["h1_source"] not in (
        "heading", "frontmatter", "either"
    ):
        problems.append(f"h1_source: {policy['h1_source']!r} is not heading, frontmatter, or either")
    if problems:
        sys.exit(f"invalid policy in {path}:\n  " + "\n  ".join(problems))
    return policy


@dataclasses.dataclass
class Issue:
    check: str
    page: str
    line: int
    message: str
    level: str = "error"

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$", re.M)
FENCE_OPEN = re.compile(r"^([ \t]*)(`{3,}|~{3,})([^\n]*)$", re.M)
TABLE_ROW = re.compile(r"^\s*\|(.+)\|\s*$", re.M)
CALLOUT = re.compile(r"^\s*\*\*(?P<label>[A-Za-z]+)\*\*\s*(?P<sep>:|\s)", re.M)


def cells(row: str) -> list[str]:
    return [c.strip() for c in row.strip().strip("|").split("|")]


def is_separator(row: str) -> bool:
    return all(re.fullmatch(r":?-{2,}:?", c) for c in cells(row) if c)


class PageLinter:
    def __init__(self, page: str, text: str, policy: dict):
        self.page = page
        self.text = text
        self.policy = policy
        self.frontmatter_title = self._frontmatter_title(text)
        self.body, self.offset = self._strip_frontmatter(text)
        self.issues: list[Issue] = []
        # Only whole-line masking: headings and fences are line constructs.
        self.editable = "".join(
            seg if ok else "\n" * seg.count("\n")
            for seg, ok in valelib.split_lines_outside_code(self.body)
        )

    @staticmethod
    def _frontmatter_title(text: str) -> str | None:
        m = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
        if not m:
            return None
        t = re.search(r"^title:\s*(.+?)\s*$", m.group(1), re.M)
        return t.group(1).strip().strip("\"'") if t else None

    @staticmethod
    def _strip_frontmatter(text: str) -> tuple[str, int]:
        m = re.match(r"\A---\n.*?\n---\n", text, re.S)
        return (text[m.end():], text[: m.end()].count("\n")) if m else (text, 0)

    def line_of(self, index: int, source: str) -> int:
        return self.offset + source[:index].count("\n") + 1

    def add(self, check: str, line: int, message: str, level: str = "error") -> None:
        self.issues.append(Issue(check, self.page, line, message, level))

    # --- checks -----------------------------------------------------------
    def headings(self) -> list[tuple[int, str, int]]:
        out = []
        for m in HEADING.finditer(self.editable):
            out.append((len(m.group(1)), m.group(2), self.line_of(m.start(), self.editable)))
        return out

    def check_heading_hierarchy(self) -> None:
        """Appendix B: heading levels are sequential; every heading has text under it."""
        previous = 0
        for level, title, line in self.headings():
            if previous and level > previous + 1:
                self.add("heading_skip", line,
                         f"Heading level jumps from H{previous} to H{level} at '{title}'.")
            previous = level

    def page_title(self) -> str | None:
        """The page's title, from wherever this doc set keeps it."""
        h1s = [t for lvl, t, _ in self.headings() if lvl == 1]
        source = self.policy["h1_source"]
        if source == "frontmatter":
            return self.frontmatter_title or (h1s[0] if h1s else None)
        if source == "heading":
            return h1s[0] if h1s else None
        return h1s[0] if h1s else self.frontmatter_title

    def check_single_h1(self) -> None:
        h1s = [(t, l) for lvl, t, l in self.headings() if lvl == 1]
        if len(h1s) > 1:
            self.add("multiple_h1", h1s[1][1],
                     f"{len(h1s)} H1 headings on one page; use exactly one.")
        if not self.page_title():
            where = ("frontmatter `title` or an H1"
                     if self.policy["h1_source"] == "frontmatter" else "H1")
            self.add("missing_title", 1, f"Page has no {where}.", "warning")

    def check_heading_uniqueness(self) -> None:
        """Duplicate headings break anchor links and the right-hand navigation."""
        seen: dict[str, int] = {}
        for _, title, line in self.headings():
            key = title.strip().lower()
            if key in seen:
                self.add("duplicate_heading", line,
                         f"'{title}' repeats the heading at line {seen[key]}.")
            else:
                seen[key] = line

    def check_empty_headings(self) -> None:
        """Every heading is followed by text before the next heading."""
        entries = list(HEADING.finditer(self.editable))
        for i, m in enumerate(entries):
            start = m.end()
            end = entries[i + 1].start() if i + 1 < len(entries) else len(self.editable)
            if not self.editable[start:end].strip():
                self.add("empty_heading", self.line_of(m.start(), self.editable),
                         f"'{m.group(2)}' is immediately followed by another heading.",
                         "warning")

    def check_fence_labels(self) -> None:
        """Appendix B: every code fence has a correct, lowercase language label."""
        depth_open = None
        for m in FENCE_OPEN.finditer(self.body):
            info = m.group(3).strip()
            line = self.line_of(m.start(), self.body)
            if depth_open is not None:
                depth_open = None       # this is the closing fence
                continue
            depth_open = line
            if not info:
                self.add("fence_no_language", line,
                         "Code fence declares no language.")
                continue
            label = info.split()[0]
            if label != label.lower():
                self.add("fence_case", line,
                         f"Fence label `{label}` must be lowercase (`{label.lower()}`).")
            elif label not in self.policy["approved_fences"]:
                self.add("fence_unapproved", line,
                         f"`{label}` is not in this doc set's approved fence labels.",
                         "suggestion")

    def check_callouts(self) -> None:
        """Approved labels only, formatted `**Label**:`, max two per H2, never stacked."""
        per_section: collections.Counter = collections.Counter()
        section = "(top)"
        previous_callout_line = None
        heading_lines = {l: (lvl, t) for lvl, t, l in self.headings()}

        for m in CALLOUT.finditer(self.editable):
            line = self.line_of(m.start(), self.editable)
            for hl in sorted(heading_lines):
                if hl <= line and heading_lines[hl][0] == 2:
                    section = heading_lines[hl][1]
            label = m.group("label")
            if label in self.policy["retired_callouts"]:
                self.add("callout_retired", line,
                         f"`{label}` is retired. Use `{self.policy['retired_callouts'][label]}`.")
            elif label not in self.policy["approved_callouts"]:
                continue     # a bold run-in heading, not a callout
            if m.group("sep") != ":":
                self.add("callout_format", line,
                         f"Callout label must be `**{label}**:` followed by a space.", "warning")
            per_section[section] += 1
            if previous_callout_line is not None and line - previous_callout_line <= 2:
                self.add("callout_stacked", line,
                         "Two callouts in a row. Combine them or move one.")
            previous_callout_line = line

        for name, count in per_section.items():
            if count > self.policy["max_callouts_per_section"]:
                self.add("callout_density", 1,
                         f"Section '{name}' has {count} callouts; the maximum is "
                         f"{self.policy['max_callouts_per_section']}.", "warning")

    def tables(self):
        """Yield (header_cells, [(row_cells, line)]) for each Markdown table."""
        rows = [(m.group(1), self.line_of(m.start(), self.editable))
                for m in TABLE_ROW.finditer(self.editable)]
        i = 0
        while i < len(rows):
            if i + 1 < len(rows) and is_separator(rows[i + 1][0]):
                header = cells(rows[i][0])
                body = []
                j = i + 2
                while j < len(rows) and not is_separator(rows[j][0]):
                    body.append((cells(rows[j][0]), rows[j][1]))
                    j += 1
                yield header, body, rows[i][1]
                i = j
            else:
                i += 1

    def check_tables(self) -> None:
        """Column vocabulary, Required values, empty cells, column count."""
        for header, body, line in self.tables():
            plain = [re.sub(r"[*`]", "", h).strip() for h in header]

            if len(plain) > self.policy["max_table_columns"]:
                self.add("table_width", line,
                         f"{len(plain)} columns; the maximum is "
                         f"{self.policy['max_table_columns']} (mobile rendering).",
                         "warning")

            for name in plain:
                if name in self.policy["banned_column_names"]:
                    self.add("table_column_name", line,
                             f"Use `Field`, not `{name}`, as the parameter column header.")

            # Required column values: this is the check Vale cannot do, because
            # it needs to know which column a cell sits in.
            if "Required" in plain:
                idx = plain.index("Required")
                for row, row_line in body:
                    if idx >= len(row):
                        continue
                    value = re.sub(r"[*`]", "", row[idx]).strip()
                    if value and value not in self.policy["required_column_values"]:
                        self.add("required_value", row_line,
                                 f"Required column contains '{value}'; use "
                                 f"{', '.join(self.policy['required_column_values'])}.")

            for row, row_line in body:
                if any(c == "" for c in row) and len(row) == len(plain):
                    self.add("table_empty_cell", row_line,
                             "Empty table cell. Use an em dash or N/A, consistently.",
                             "warning")

    def check_placeholders_explained(self) -> None:
        """A placeholder used in a code sample is explained somewhere in prose.

        Scoped to placeholders that actually appear inside a code block: an
        UPPER_SNAKE token in prose is usually an enum value or a constant, not
        something the reader has to substitute. An earlier version skipped this
        distinction and reported 779 issues, nearly all of them enum values.
        """
        code = "".join(
            seg for seg, editable in valelib.split_lines_outside_code(self.body)
            if not editable
        )
        in_code = set(re.findall(r"\b([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)\b", code))
        prose = self.editable
        known = set(self.policy["globally_known_placeholders"])
        for name in sorted(in_code - known):
            if re.search(rf"`?{re.escape(name)}`?\s*[:\u2014-]", prose):
                continue          # "`CLIENT_KEY`: the client key from..."
            if re.search(rf"[Rr]eplace\b[^.]*\b{re.escape(name)}\b", prose):
                continue
            if re.search(rf"\b{re.escape(name)}\b", prose):
                continue          # mentioned in prose at all
            m = re.search(rf"\b{re.escape(name)}\b", self.body)
            self.add("placeholder_unexplained", self.line_of(m.start(), self.body),
                     f"Placeholder `{name}` is used in a code sample but never explained.",
                     "suggestion")

    def run(self) -> list[Issue]:
        for check in (
            self.check_heading_hierarchy,
            self.check_single_h1,
            self.check_heading_uniqueness,
            self.check_empty_headings,
            self.check_fence_labels,
            self.check_callouts,
            self.check_tables,
            self.check_placeholders_explained,
        ):
            check()
        return self.issues


def lint_corpus(root: pathlib.Path, policy: dict) -> tuple[list[Issue], dict]:
    issues: list[Issue] = []
    h1_index: dict[str, list[str]] = collections.defaultdict(list)
    pages = sorted([*root.rglob("*.mdx"), *root.rglob("*.md")])
    if policy["exclude"]:
        # fnmatch on the repo-relative path, not pathlib.glob: `snippets/**`
        # matches directories in pathlib and silently excluded nothing.
        import fnmatch

        def excluded(path: pathlib.Path) -> bool:
            rel = path.relative_to(root).as_posix()
            return any(
                fnmatch.fnmatch(rel, pattern) or rel.startswith(pattern.rstrip("*").rstrip("/") + "/")
                for pattern in policy["exclude"]
            )

        pages = [p for p in pages if not excluded(p)]

    for path in pages:
        rel = str(path.relative_to(root))
        text = path.read_text(encoding="utf-8")
        linter = PageLinter(rel, text, policy)
        issues.extend(linter.run())
        title = linter.page_title()
        if title:
            h1_index[title.strip().lower()].append(rel)

    # Cross-page: the guide requires every H1 to be unique across the doc set,
    # because "Get Started" and "Error Handling" collide across products.
    for title, owners in sorted(h1_index.items()):
        if len(owners) > 1:
            for owner in owners:
                issues.append(Issue(
                    "title_not_unique", owner, 1,
                    f"Title '{title}' is used on {len(owners)} pages. "
                    "Qualify it with the product name.",
                    "warning",
                ))

    issues.sort(key=lambda i: (i.page, i.line, i.check))
    return issues, {"pages": len(pages)}


def render_markdown(issues: list[Issue], stats: dict) -> str:
    by_check = collections.Counter(i.check for i in issues)
    by_level = collections.Counter(i.level for i in issues)
    out = ["# Structure report", "",
           f"Checked **{stats['pages']} pages** against `{stats.get('policy', 'default')}`. "
           f"**{len(issues)}** issue(s): " +
           ", ".join(f"{by_level[l]} {l}" for l in ("error", "warning", "suggestion") if by_level[l]),
           "", "| Check | Count |", "| --- | ---: |"]
    for check, n in by_check.most_common():
        out.append(f"| `{check}` | {n} |")
    if issues:
        out += ["", "## Issues", "", "| Page | Line | Check | Message |", "| --- | ---: | --- | --- |"]
        for i in issues[:200]:
            out.append(f"| `{i.page}` | {i.line} | `{i.check}` | {i.message} |")
        if len(issues) > 200:
            out.append(f"\n_{len(issues) - 200} further issue(s) omitted._")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("docs", type=pathlib.Path)
    ap.add_argument("--config", type=pathlib.Path, default=DEFAULT_CONFIG,
                    help="structural policy file (default: config/tiktok.yml)")
    ap.add_argument("--format", default="markdown", choices=["markdown", "json"])
    ap.add_argument("--out", type=pathlib.Path)
    ap.add_argument("--fail-on", choices=["error", "warning", "suggestion", "never"], default="never")
    args = ap.parse_args()

    if not args.docs.is_dir():
        sys.exit(f"not a directory: {args.docs}")

    policy = load_policy(args.config)
    issues, stats = lint_corpus(args.docs, policy)
    stats["policy"] = args.config.name
    text = (render_markdown(issues, stats) if args.format == "markdown"
            else json.dumps({"stats": stats, "issues": [i.to_dict() for i in issues]}, indent=2))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
        print(f"wrote {args.out} ({len(issues)} issues)")
    else:
        print(text)

    if args.fail_on != "never":
        order = ["error", "warning", "suggestion"]
        threshold = order.index(args.fail_on)
        blocking = [i for i in issues if order.index(i.level) <= threshold]
        if blocking:
            print(f"\n{len(blocking)} issue(s) at or above `{args.fail_on}`.", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
