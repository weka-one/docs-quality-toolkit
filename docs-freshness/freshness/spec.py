"""Index an OpenAPI 3.x document for lookup by path template and method.

The spec is the source of truth. Everything this package reports is a
disagreement between a documentation page and this index, so the index has to
be right about three awkward things:

* `$ref` indirection - request bodies are almost always refs, and a checker
  that cannot follow them sees every body parameter as unknown.
* Composition - `allOf`/`oneOf`/`anyOf` spread one logical object across
  several schemas. Missing this produces false "unknown parameter" findings on
  correct documentation, which is the failure mode that gets a tool uninstalled.
* Path templating - docs write `/indexes/movies/search`; the spec writes
  `/indexes/{index_uid}/search`.
"""
from __future__ import annotations

import dataclasses
import json
import pathlib
import re
from typing import Any, Iterable

HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")


@dataclasses.dataclass(frozen=True)
class Operation:
    path: str                      # spec template, e.g. /indexes/{index_uid}/search
    method: str                    # uppercase
    operation_id: str
    summary: str
    deprecated: bool
    security: tuple[str, ...]      # scopes required, flattened
    secured: bool
    path_params: frozenset[str]
    query_params: frozenset[str]
    required_query: frozenset[str]
    body_params: frozenset[str]
    required_body: frozenset[str]
    status_codes: frozenset[str]

    @property
    def key(self) -> str:
        return f"{self.method} {self.path}"


class Spec:
    def __init__(self, document: dict):
        self.doc = document
        self.version = document.get("info", {}).get("version", "unknown")
        self.title = document.get("info", {}).get("title", "unknown")
        self._resolving: set[str] = set()
        self.operations: dict[str, Operation] = {}
        self.enums: dict[str, frozenset[str]] = {}
        self.named_enums: dict[str, frozenset[str]] = {}
        self._build()

    # --- loading ---------------------------------------------------------
    @classmethod
    def load(cls, path: pathlib.Path) -> "Spec":
        text = pathlib.Path(path).read_text(encoding="utf-8")
        if path.suffix in (".yaml", ".yml"):
            import yaml

            return cls(yaml.safe_load(text))
        return cls(json.loads(text))

    def resolve(self, node: Any) -> Any:
        """Follow a local $ref. Cycles resolve to {} rather than recursing forever."""
        if not isinstance(node, dict) or "$ref" not in node:
            return node
        ref = node["$ref"]
        if not ref.startswith("#/"):
            return {}
        if ref in self._resolving:
            return {}
        self._resolving.add(ref)
        try:
            target: Any = self.doc
            for part in ref[2:].split("/"):
                part = part.replace("~1", "/").replace("~0", "~")
                if not isinstance(target, dict) or part not in target:
                    return {}
                target = target[part]
            return self.resolve(target)
        finally:
            self._resolving.discard(ref)

    # --- schema flattening -----------------------------------------------
    def object_properties(self, schema: Any, _depth: int = 0) -> tuple[set[str], set[str]]:
        """Return (all property names, required property names).

        Walks allOf/oneOf/anyOf so a body split across composed schemas is seen
        as one object. Only `allOf` contributes to `required`: a property
        required by one branch of a `oneOf` is not required by the operation.
        """
        schema = self.resolve(schema)
        if not isinstance(schema, dict) or _depth > 12:
            return set(), set()

        props: set[str] = set()
        required: set[str] = set()

        if isinstance(schema.get("properties"), dict):
            props |= set(schema["properties"])
        if isinstance(schema.get("required"), list):
            required |= {r for r in schema["required"] if isinstance(r, str)}

        for branch in schema.get("allOf") or []:
            p, r = self.object_properties(branch, _depth + 1)
            props |= p
            required |= r
        for key in ("oneOf", "anyOf"):
            for branch in schema.get(key) or []:
                p, _ = self.object_properties(branch, _depth + 1)
                props |= p

        # A body declared as an array of objects documents the item's fields.
        if schema.get("type") == "array" and schema.get("items"):
            p, _ = self.object_properties(schema["items"], _depth + 1)
            props |= p

        return props, required

    def _enum_values(self, schema: Any, _depth: int = 0) -> set[str]:
        """Return the enum values a schema admits, following refs and wrappers.

        Enums are almost never inline on the property: the property is a `$ref`
        to a named component (`matchingStrategy` -> `MatchingStrategy`), or an
        array whose `items` is that ref (`actions` -> `[Action]`). Reading only
        inline enums found 4 enum-bearing fields in this spec; following refs
        finds 60.
        """
        schema = self.resolve(schema)
        if not isinstance(schema, dict) or _depth > 8:
            return set()
        values: set[str] = set()
        if isinstance(schema.get("enum"), list):
            values |= {str(v) for v in schema["enum"] if v is not None}
        for key in ("items", "propertyNames", "additionalProperties"):
            if schema.get(key):
                values |= self._enum_values(schema[key], _depth + 1)
        for key in ("allOf", "oneOf", "anyOf"):
            for branch in schema.get(key) or []:
                values |= self._enum_values(branch, _depth + 1)
        return values

    def _collect_enums(self, node: Any, field: str | None = None, _depth: int = 0) -> None:
        """Record enum values keyed by the property name that carries them.

        Keying by field name is what makes enums checkable from prose: a page
        says "`status` can be `enqueued`", and the field name is the only
        handle the page gives us.

        Where two unrelated schemas share a field name (`source` is both an
        embedder source and a chat-completion source) the values are unioned.
        That is deliberate: a union can only cause a missed finding, while
        picking one arbitrarily would flag correct documentation as wrong, and
        a false positive costs far more trust than a miss.
        """
        if _depth > 16:
            return
        if isinstance(node, dict):
            if "$ref" in node:
                node = self.resolve(node)
                if not isinstance(node, dict):
                    return
            props = node.get("properties")
            if isinstance(props, dict):
                for prop_name, prop in props.items():
                    values = self._enum_values(prop)
                    if values:
                        self.enums[prop_name] = frozenset(
                            self.enums.get(prop_name, frozenset()) | values
                        )
                    self._collect_enums(prop, prop_name, _depth + 1)
            for key, value in node.items():
                if key in ("properties", "$ref", "example", "examples", "default"):
                    continue
                self._collect_enums(value, field, _depth + 1)
        elif isinstance(node, list):
            for item in node:
                self._collect_enums(item, field, _depth + 1)

    def _collect_named_enums(self) -> None:
        """Also expose component schemas that are themselves enums.

        Lets a caller ask about `Action` or `MatchingStrategy` directly when a
        page names the type rather than a field.
        """
        for name, schema in (self.doc.get("components", {}).get("schemas") or {}).items():
            values = self._enum_values(schema)
            if values:
                self.named_enums[name] = frozenset(values)

    # --- build ------------------------------------------------------------
    def _build(self) -> None:
        self._collect_enums(self.doc)
        self._collect_named_enums()
        global_security = self.doc.get("security") or []

        for path, item in (self.doc.get("paths") or {}).items():
            if not isinstance(item, dict):
                continue
            shared = item.get("parameters") or []
            for method in HTTP_METHODS:
                op = item.get(method)
                if not isinstance(op, dict):
                    continue

                params = [self.resolve(p) for p in [*shared, *(op.get("parameters") or [])]]
                # Query and path parameters carry enums too (`sizeFormat`,
                # `proximityPrecision`), and they live on the parameter's
                # schema rather than under any `properties` map.
                for param in params:
                    values = self._enum_values(param.get("schema"))
                    if values and param.get("name"):
                        name = param["name"]
                        self.enums[name] = frozenset(self.enums.get(name, frozenset()) | values)
                path_params = {p["name"] for p in params if p.get("in") == "path" and p.get("name")}
                query = {p["name"] for p in params if p.get("in") == "query" and p.get("name")}
                required_query = {
                    p["name"] for p in params
                    if p.get("in") == "query" and p.get("required") and p.get("name")
                }

                body_params: set[str] = set()
                required_body: set[str] = set()
                body = self.resolve(op.get("requestBody") or {})
                for media, content in (body.get("content") or {}).items():
                    if "json" not in media:
                        continue
                    p, r = self.object_properties(content.get("schema"))
                    body_params |= p
                    required_body |= r

                security = op.get("security", global_security) or []
                scopes: list[str] = []
                for entry in security:
                    if isinstance(entry, dict):
                        for values in entry.values():
                            scopes.extend(str(v) for v in values or [])

                operation = Operation(
                    path=path,
                    method=method.upper(),
                    operation_id=op.get("operationId") or f"{method}:{path}",
                    summary=op.get("summary") or "",
                    deprecated=bool(op.get("deprecated")),
                    security=tuple(sorted(set(scopes))),
                    secured=bool(security),
                    path_params=frozenset(path_params),
                    query_params=frozenset(query),
                    required_query=frozenset(required_query),
                    body_params=frozenset(body_params),
                    required_body=frozenset(required_body),
                    status_codes=frozenset(str(c) for c in (op.get("responses") or {})),
                )
                self.operations[operation.key] = operation

    # --- lookup -----------------------------------------------------------
    @staticmethod
    def _segments(path: str) -> list[str]:
        return [s for s in path.strip("/").split("/") if s]

    def match_path(self, concrete: str) -> list[str]:
        """Map a documented path onto spec templates.

        `/indexes/movies/search` matches `/indexes/{index_uid}/search`. More
        than one template can match when a literal and a templated segment
        overlap (`/indexes/{index_uid}/documents/delete` vs
        `.../documents/{document_id}`), so all candidates are returned and the
        caller prefers literal matches.
        """
        want = self._segments(concrete)
        matches = []
        for path in {op.path for op in self.operations.values()}:
            have = self._segments(path)
            if len(have) != len(want):
                continue
            literal = 0
            for spec_seg, doc_seg in zip(have, want):
                if spec_seg.startswith("{") and spec_seg.endswith("}"):
                    continue
                if spec_seg != doc_seg:
                    break
                literal += 1
            else:
                matches.append((literal, path))
        return [p for _, p in sorted(matches, reverse=True)]

    def find(self, method: str, concrete_path: str) -> Operation | None:
        method = method.upper()
        for path in self.match_path(concrete_path):
            op = self.operations.get(f"{method} {path}")
            if op:
                return op
        return None

    def paths_for_method(self, method: str) -> set[str]:
        return {op.path for op in self.operations.values() if op.method == method.upper()}

    def known_fields(self) -> set[str]:
        fields: set[str] = set()
        for op in self.operations.values():
            fields |= set(op.body_params) | set(op.query_params) | set(op.path_params)
        return fields

    def __repr__(self) -> str:
        return (
            f"<Spec {self.title} {self.version}: "
            f"{len(self.operations)} operations, {len(self.enums)} enum fields, "
            f"{len(self.named_enums)} named enums>"
        )
