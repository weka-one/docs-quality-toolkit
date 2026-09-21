#!/usr/bin/env python3
"""Inject known drift into clean documentation pages.

Recall is the hard half of evaluating a freshness checker. Precision can be
measured by adjudicating what the tool reports; recall needs the things it
*failed* to report, and finding those in a real corpus means reading every page
against the spec by hand.

Mutation sidesteps that. Each mutation is the textual form of a change that
really happens to an API -- a parameter renamed, an enum value dropped, a route
moved, a verb changed -- applied to a page that currently passes. Ground truth
is exact by construction: the mutation knows which line it changed and which
detector should fire.

The limit of the method, stated plainly: mutations measure recall against drift
*of the kinds modelled here*. They say nothing about drift nobody thought to
model. That is why the evaluation set also contains real, hand-adjudicated
pages -- see eval/README.md.

Seeded, so the set is reproducible.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import random
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from freshness.extract import extract, iter_code_blocks  # noqa: E402
from freshness.spec import Spec  # noqa: E402


@dataclasses.dataclass
class Mutation:
    name: str
    detector: str          # the detector expected to catch it
    page: str
    line: int
    before: str
    after: str
    note: str


class Mutator:
    """Applies one mutation per page, chosen from what the page contains."""

    def __init__(self, spec: Spec, seed: int = 20260921):
        self.spec = spec
        self.random = random.Random(seed)

    # --- individual mutations --------------------------------------------
    def rename_body_param(self, text: str, claims) -> tuple[str, Mutation] | None:
        """A request-body field the API renamed. Detector: unknown_parameter."""
        candidates = [c for c in claims if c.kind == "body_param"]
        self.random.shuffle(candidates)
        for claim in candidates:
            op = self.spec.find(claim.method, claim.path)
            if not op or claim.name not in op.body_params:
                continue
            # A plausible rename: camelCase -> snake_case, which is the single
            # most common shape of real parameter drift.
            renamed = re.sub(r"(?<!^)(?=[A-Z])", "_", claim.name).lower()
            if renamed == claim.name or renamed in op.body_params:
                renamed = claim.name + "_v2"
            pattern = f'"{claim.name}"'
            if pattern not in text:
                continue
            mutated = text.replace(pattern, f'"{renamed}"', 1)
            line = text[: text.index(pattern)].count("\n") + 1
            return mutated, Mutation(
                "rename_body_param", "unknown_parameter", "", line,
                claim.name, renamed, f"{op.key} body field renamed",
            )
        return None

    def change_http_verb(self, text: str, claims) -> tuple[str, Mutation] | None:
        """A route that changed verb. Detector: unknown_endpoint."""
        candidates = [c for c in claims if c.kind == "endpoint"]
        self.random.shuffle(candidates)
        for claim in candidates:
            op = self.spec.find(claim.method, claim.path)
            if not op:
                continue
            swap = {"POST": "PUT", "PUT": "POST", "PATCH": "PUT", "GET": "POST", "DELETE": "POST"}
            new_method = swap.get(claim.method)
            if not new_method or self.spec.find(new_method, claim.path):
                continue
            pattern = f"-X {claim.method}"
            if pattern not in text:
                continue
            mutated = text.replace(pattern, f"-X {new_method}", 1)
            line = text[: text.index(pattern)].count("\n") + 1
            return mutated, Mutation(
                "change_http_verb", "unknown_endpoint", "", line,
                f"{claim.method} {claim.path}", f"{new_method} {claim.path}",
                f"verb changed on {op.path}",
            )
        return None

    def move_route(self, text: str, claims) -> tuple[str, Mutation] | None:
        """A route that moved under a new prefix. Detector: unknown_endpoint."""
        candidates = [c for c in claims if c.kind == "endpoint"]
        self.random.shuffle(candidates)
        for claim in candidates:
            if not self.spec.find(claim.method, claim.path):
                continue
            segments = [s for s in claim.path.strip("/").split("/") if s]
            if len(segments) < 2:
                continue
            moved = "/" + "/".join(["v2", *segments])
            if self.spec.find(claim.method, moved):
                continue
            if claim.path not in text:
                continue
            mutated = text.replace(claim.path, moved, 1)
            line = text[: text.index(claim.path)].count("\n") + 1
            return mutated, Mutation(
                "move_route", "unknown_endpoint", "", line,
                claim.path, moved, "route moved behind a version prefix",
            )
        return None

    def drop_enum_value(self, text: str, claims) -> tuple[str, Mutation] | None:
        """An enum value the API removed. Detector: unknown_enum_value."""
        candidates = [c for c in claims if c.kind == "enum_value"]
        self.random.shuffle(candidates)
        for claim in candidates:
            allowed = self.spec.enums.get(claim.field)
            if not allowed or claim.value not in allowed:
                continue
            retired = claim.value + "_legacy"
            pattern = f"`{claim.value}`"
            if pattern not in text:
                continue
            mutated = text.replace(pattern, f"`{retired}`", 1)
            line = text[: text.index(pattern)].count("\n") + 1
            return mutated, Mutation(
                "drop_enum_value", "unknown_enum_value", "", line,
                claim.value, retired, f"`{claim.field}` no longer accepts this value",
            )
        return None

    def strip_auth_header(self, text: str, claims) -> tuple[str, Mutation] | None:
        """A sample that lost its Authorization header. Detector: missing_auth."""
        candidates = [c for c in claims if c.kind == "auth" and c.has_auth]
        self.random.shuffle(candidates)
        for claim in candidates:
            op = self.spec.find(claim.method, claim.path)
            if not op or not op.secured:
                continue
            m = re.search(r"[ \t]*-H\s+'Authorization:[^']*'\s*\\?\n", text)
            if not m:
                continue
            mutated = text[: m.start()] + text[m.end():]
            line = text[: m.start()].count("\n") + 1
            return mutated, Mutation(
                "strip_auth_header", "missing_auth", "", line,
                m.group(0).strip(), "", f"{op.key} sample lost its credentials",
            )
        return None

    MUTATIONS = (
        "rename_body_param",
        "change_http_verb",
        "move_route",
        "drop_enum_value",
        "strip_auth_header",
    )

    def mutate(self, page: str, text: str, prefer: str | None = None):
        claims = extract(page, text)
        order = list(self.MUTATIONS)
        if prefer:
            order.remove(prefer)
            order.insert(0, prefer)
        for name in order:
            result = getattr(self, name)(text, claims)
            if result:
                mutated, mutation = result
                return mutated, dataclasses.replace(mutation, page=page)
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", type=pathlib.Path, default=pathlib.Path("../corpus/meilisearch-docs"))
    ap.add_argument("--spec", type=pathlib.Path, default=pathlib.Path("../spec/meilisearch-openapi.json"))
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path("eval/mutated"))
    ap.add_argument("--manifest", type=pathlib.Path, default=pathlib.Path("eval/mutations.jsonl"))
    ap.add_argument("--count", type=int, default=15)
    ap.add_argument("--seed", type=int, default=20260921)
    args = ap.parse_args()

    spec = Spec.load(args.spec)
    mutator = Mutator(spec, args.seed)

    pages = sorted(args.corpus.rglob("*.mdx"))
    # Deterministic shuffle so the selected pages are stable across runs.
    random.Random(args.seed).shuffle(pages)

    if args.out.exists():
        import shutil

        shutil.rmtree(args.out)
    args.out.mkdir(parents=True)

    # Fill each mutation kind independently rather than round-robining with
    # fallback. Fallback silently produced zero `drop_enum_value` cases,
    # leaving that detector's recall unmeasured while the totals still looked
    # healthy -- exactly the kind of gap an eval set exists to prevent.
    kinds = list(Mutator.MUTATIONS)
    per_kind = max(1, args.count // len(kinds))
    manifest, used_pages = [], set()

    for kind in kinds:
        made = 0
        for path in pages:
            if made >= per_kind or len(manifest) >= args.count:
                break
            rel = str(path.relative_to(args.corpus))
            if rel in used_pages:
                continue
            text = path.read_text(encoding="utf-8")
            result = getattr(mutator, kind)(text, extract(rel, text))
            if not result:
                continue
            mutated, mutation = result
            if mutated == text:
                continue
            out_path = args.out / rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(mutated, encoding="utf-8")
            manifest.append(dataclasses.asdict(dataclasses.replace(mutation, page=rel)))
            used_pages.add(rel)
            made += 1
        if made < per_kind:
            print(
                f"  note: only {made}/{per_kind} pages support `{kind}`",
                file=sys.stderr,
            )

    produced = len(manifest)

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text("\n".join(json.dumps(m) for m in manifest) + "\n")

    print(f"{produced} mutated page(s) -> {args.out}")
    import collections

    for name, n in collections.Counter(m["name"] for m in manifest).most_common():
        print(f"  {name}: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
