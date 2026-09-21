"""Adjudicate extracted claims against the OpenAPI spec.

Each detector answers one falsifiable question and reports a `Finding` with a
confidence. Confidence is not decoration -- the evaluation harness uses it to
draw a precision/recall curve, and the CLI uses it to decide what blocks CI.

Design bias: **precision over recall.** A docs freshness checker is used by
writers who did not build it. One confident false positive teaches a writer the
tool is noise, and they stop reading its output; a miss costs one stale line
nobody was looking at anyway. So every detector abstains when the spec is
ambiguous, and the ambiguous cases are counted and reported rather than guessed.
"""
from __future__ import annotations

import dataclasses
import difflib
from typing import Iterable

from .extract import Claim
from .spec import Operation, Spec


def default_bases(spec: Spec, claims: Iterable[Claim] | None = None) -> set[str]:
    """Bases that count as "this API": the spec's own servers, plus any
    placeholder that dominates the corpus.

    Auto-detection is a convenience, not magic -- the CLI prints what it chose
    so the decision is visible and can be overridden in config.
    """
    import collections
    import urllib.parse

    bases: set[str] = {""}
    for server in spec.doc.get("servers") or []:
        url = str(server.get("url", ""))
        if url:
            bases.add(url.rstrip("/"))
            parsed = urllib.parse.urlparse(url)
            if parsed.netloc:
                bases.add(parsed.netloc)
    if claims:
        counts = collections.Counter(
            c.base for c in claims if c.base and c.kind == "endpoint"
        )
        if counts:
            top, n = counts.most_common(1)[0]
            # Only adopt a placeholder that is clearly the corpus default.
            if n >= 3 and n >= 0.5 * sum(counts.values()):
                bases.add(top)
                bases.add("${%s}" % top.strip("${}"))
                bases.add("$" + top.strip("${}"))
    return bases

# Path segments that are placeholders in prose rather than real resources.
_PLACEHOLDERISH = {"index_uid", "indexuid", "uid", "id", "your-index", "your_index"}


@dataclasses.dataclass
class Finding:
    detector: str
    page: str
    line: int
    message: str
    confidence: float
    evidence: str = ""
    suggestion: str = ""
    needs_review: bool = False
    # Provenance of the claim that produced this finding. Carried so a reviewer
    # -- human or machine -- can judge the sample itself rather than a window of
    # surrounding prose. Regexing the surrounding page meant one `github.com`
    # link dismissed every uncertain finding near it.
    base: str = ""
    origin: str = "curl"
    snippet: str = ""

    @property
    def key(self) -> tuple:
        """Identity for comparison against labels: page, line, detector, subject."""
        return (self.page, self.line, self.detector, self.evidence)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def _closest(name: str, candidates: Iterable[str], cutoff: float = 0.82) -> str | None:
    matches = difflib.get_close_matches(name, list(candidates), n=1, cutoff=cutoff)
    return matches[0] if matches else None


def _looks_templated(path: str) -> bool:
    segments = [s for s in path.strip("/").split("/") if s]
    return any(
        s.startswith("{") or s.startswith("<") or s.startswith(":") or s.lower() in _PLACEHOLDERISH
        for s in segments
    )


class Detectors:
    """Runs every detector over a page's claims."""

    def __init__(self, spec: Spec, bases: set[str] | None = None):
        """`bases` limits adjudication to samples targeting the API under test.

        A documentation corpus calls more than one service. Passing `None`
        checks every sample, which is almost never what you want: on the
        vendored corpus it produced 13 findings about GitHub download URLs and
        a hosted analytics endpoint, none of them actionable.
        """
        self.spec = spec
        self.bases = bases
        self.abstentions: list[tuple[str, str]] = []
        self.out_of_scope = 0

    def in_scope(self, claim: Claim) -> bool:
        if self.bases is None or claim.kind == "enum_value":
            return True
        if not claim.base:
            return True  # already a server-relative path
        return claim.base in self.bases

    # --- helpers ---------------------------------------------------------
    def _operation(self, claim: Claim) -> Operation | None:
        return self.spec.find(claim.method, claim.path)

    def _path_exists_under_other_method(self, claim: Claim) -> list[str]:
        methods = []
        for path in self.spec.match_path(claim.path):
            for op in self.spec.operations.values():
                if op.path == path:
                    methods.append(op.method)
        return sorted(set(methods))

    # --- detectors -------------------------------------------------------
    def unknown_endpoint(self, claim: Claim) -> Finding | None:
        """The docs call a method+path the spec does not define."""
        if claim.kind != "endpoint":
            return None
        if self._operation(claim):
            return None

        # A route marker is a structural declaration ("this page documents this
        # route"), so it is trusted like a curl sample. Inline prose is not: it
        # carries no base URL, and a migration guide documents a competitor's
        # routes in identical syntax. Those are reported for review, never
        # asserted.
        if claim.origin == "inline":
            near = _closest(claim.path, self.spec.paths_for_method(claim.method), cutoff=0.7)
            return Finding(
                detector="unknown_endpoint",
                page=claim.page, line=claim.line,
                message=(
                    f"`{claim.method} {claim.path}` is named in prose but is not in the spec."
                    + (f" Closest match: `{near}`." if near else "")
                ),
                confidence=0.45 if near else 0.35,
                evidence=f"{claim.method} {claim.path}",
                suggestion=f"{claim.method} {near}" if near else "",
                needs_review=True,
            )

        others = self._path_exists_under_other_method(claim)
        if others:
            # The path exists but not under this method. That is a precise,
            # high-value finding: usually a verb that changed.
            return Finding(
                detector="unknown_endpoint",
                page=claim.page, line=claim.line,
                message=(
                    f"`{claim.method} {claim.path}` is not in the spec. "
                    f"The path exists, but only for {', '.join(others)}."
                ),
                confidence=0.9,
                evidence=f"{claim.method} {claim.path}",
                suggestion=f"{others[0]} {claim.path}",
            )

        near = _closest(claim.path, self.spec.paths_for_method(claim.method), cutoff=0.7)
        if near:
            return Finding(
                detector="unknown_endpoint",
                page=claim.page, line=claim.line,
                message=f"`{claim.method} {claim.path}` is not in the spec. Closest match: `{near}`.",
                confidence=0.75,
                evidence=f"{claim.method} {claim.path}",
                suggestion=f"{claim.method} {near}",
            )

        # No neighbour at all. This is frequently a third-party or
        # illustrative URL rather than drift, so it is reported at low
        # confidence and flagged for review rather than asserted.
        return Finding(
            detector="unknown_endpoint",
            page=claim.page, line=claim.line,
            message=f"`{claim.method} {claim.path}` does not appear in the spec.",
            confidence=0.4,
            evidence=f"{claim.method} {claim.path}",
            needs_review=True,
        )

    def unknown_parameter(self, claim: Claim) -> Finding | None:
        """A request body field or query parameter the operation does not accept."""
        if claim.kind not in ("body_param", "query_param"):
            return None
        op = self._operation(claim)
        if op is None:
            return None  # unknown_endpoint already owns this page's problem

        if claim.kind == "body_param":
            known, where = op.body_params, "request body"
            if not known:
                # The operation declares no JSON body schema. Silence beats a
                # guess: the spec simply does not describe this surface.
                self.abstentions.append((claim.location(), f"{op.key} has no body schema"))
                return None
        else:
            known, where = op.query_params, "query string"
            if not known:
                self.abstentions.append((claim.location(), f"{op.key} declares no query parameters"))
                return None

        if claim.name in known:
            return None

        near = _closest(claim.name, known)
        return Finding(
            detector="unknown_parameter",
            page=claim.page, line=claim.line,
            message=(
                f"`{claim.name}` is not a {where} field of `{op.key}`."
                + (f" Closest match: `{near}`." if near else "")
            ),
            confidence=0.85 if near else 0.7,
            evidence=f"{op.key} {claim.name}",
            suggestion=near or "",
        )

    def unknown_enum_value(self, claim: Claim) -> Finding | None:
        """A documented value for a field the spec constrains to an enum."""
        if claim.kind != "enum_value":
            return None
        allowed = self.spec.enums.get(claim.field)
        if not allowed:
            return None
        if claim.value in allowed:
            return None
        # Values that are obviously not enum members (types, examples) are
        # filtered by the extractor; anything reaching here is a real mismatch
        # for a field the spec genuinely constrains.
        near = _closest(claim.value, allowed, cutoff=0.75)
        return Finding(
            detector="unknown_enum_value",
            page=claim.page, line=claim.line,
            message=(
                f"`{claim.value}` is not an accepted value for `{claim.field}`."
                + (f" Closest match: `{near}`." if near else "")
            ),
            confidence=0.8 if near else 0.6,
            evidence=f"{claim.field}={claim.value}",
            suggestion=near or "",
            needs_review=near is None,
        )

    def missing_auth(self, claim: Claim) -> Finding | None:
        """A sample calls a secured endpoint with no Authorization header."""
        if claim.kind != "auth" or claim.has_auth:
            return None
        op = self._operation(claim)
        if op is None or not op.secured:
            return None
        return Finding(
            detector="missing_auth",
            page=claim.page, line=claim.line,
            message=(
                f"`{op.key}` requires authorization "
                f"({', '.join(op.security) or 'a key'}), but this sample sends no "
                "`Authorization` header."
            ),
            confidence=0.65,
            evidence=f"{op.key}",
            needs_review=True,
        )

    def deprecated_endpoint(self, claim: Claim) -> Finding | None:
        """The spec marks the operation deprecated and the page does not say so."""
        if claim.kind != "endpoint":
            return None
        op = self._operation(claim)
        if op is None or not op.deprecated:
            return None
        return Finding(
            detector="deprecated_endpoint",
            page=claim.page, line=claim.line,
            message=f"`{op.key}` is marked deprecated in the spec.",
            confidence=0.95,
            evidence=op.key,
        )

    DETECTORS = (
        "unknown_endpoint",
        "unknown_parameter",
        "unknown_enum_value",
        "missing_auth",
        "deprecated_endpoint",
    )

    @staticmethod
    def _attach(finding: Finding, claim: Claim) -> Finding:
        finding.base = claim.base
        finding.origin = claim.origin
        finding.snippet = claim.snippet
        return finding

    def run(self, claims: Iterable[Claim]) -> list[Finding]:
        findings: list[Finding] = []
        seen: set[tuple] = set()
        for claim in claims:
            if not self.in_scope(claim):
                self.out_of_scope += 1
                continue
            for name in self.DETECTORS:
                finding = getattr(self, name)(claim)
                if finding:
                    self._attach(finding, claim)
                if finding and finding.key not in seen:
                    seen.add(finding.key)
                    findings.append(finding)
        findings.sort(key=lambda f: (f.page, f.line, f.detector))
        return findings
