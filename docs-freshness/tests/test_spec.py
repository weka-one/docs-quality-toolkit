"""The spec index is the source of truth; if it is wrong, every finding is."""
from freshness.spec import Spec


def test_loads_real_spec(spec):
    assert spec.version == "1.54.0"
    assert len(spec.operations) > 100


def test_resolves_request_body_refs(spec):
    """Bodies are almost always $refs. Not following them makes every body
    parameter look unknown."""
    op = spec.find("POST", "/indexes/movies/search")
    assert op is not None
    assert "matchingStrategy" in op.body_params
    assert "q" in op.body_params
    assert len(op.body_params) > 20


def test_path_templating(spec):
    """Docs write concrete paths; the spec writes templates."""
    op = spec.find("GET", "/indexes/movies/documents")
    assert op.path == "/indexes/{index_uid}/documents"
    assert "limit" in op.query_params


def test_prefers_literal_over_templated_match(spec):
    """/documents/delete must not resolve to /documents/{document_id}."""
    matches = spec.match_path("/indexes/movies/documents/delete")
    assert matches[0] == "/indexes/{index_uid}/documents/delete"


def test_unknown_method_on_known_path(spec):
    assert spec.find("GET", "/indexes/movies") is not None
    assert spec.find("POST", "/indexes/movies") is None


def test_enums_follow_refs(spec):
    """Enums live in components/schemas behind a $ref. Reading only inline
    enums found 4 enum-bearing fields in this spec; following refs finds 20+."""
    assert len(spec.enums) > 20
    assert spec.enums["matchingStrategy"] == {"last", "all", "frequency"}
    assert "enqueued" in spec.enums["status"]


def test_enums_from_query_parameters(spec):
    """Parameter enums sit on the parameter's schema, not under properties."""
    assert spec.enums["sizeFormat"] == {"human", "raw"}


def test_security_scopes(spec):
    op = spec.find("POST", "/indexes/movies/search")
    assert op.secured
    assert "search" in op.security


def test_cyclic_ref_terminates():
    doc = {
        "openapi": "3.1.0",
        "info": {"title": "t", "version": "1"},
        "paths": {},
        "components": {"schemas": {"Loop": {"allOf": [{"$ref": "#/components/schemas/Loop"}]}}},
    }
    s = Spec(doc)
    assert s.object_properties({"$ref": "#/components/schemas/Loop"}) == (set(), set())


def _spec_with_body_schema(schema: dict) -> Spec:
    """Minimal spec whose single operation has `schema` as its JSON body."""
    return Spec({
        "openapi": "3.1.0",
        "info": {"title": "t", "version": "1"},
        "paths": {
            "/x": {
                "post": {
                    "requestBody": {"content": {"application/json": {"schema": schema}}},
                },
            },
        },
    })


def test_allof_merges_properties_and_required():
    s = _spec_with_body_schema({
        "allOf": [
            {"type": "object", "properties": {"a": {}}, "required": ["a"]},
            {"type": "object", "properties": {"b": {}}},
        ],
    })
    op = s.find("POST", "/x")
    assert op.body_params == {"a", "b"}
    assert op.required_body == {"a"}


def test_oneof_contributes_properties_but_not_required():
    """A field required by one branch of a oneOf is not required by the
    operation. Treating it as required would flag correct samples."""
    s = _spec_with_body_schema({
        "oneOf": [
            {"type": "object", "properties": {"a": {}}, "required": ["a"]},
            {"type": "object", "properties": {"b": {}}},
        ],
    })
    op = s.find("POST", "/x")
    assert op.body_params == {"a", "b"}
    assert op.required_body == set()


def test_array_body_documents_item_fields():
    s = _spec_with_body_schema({
        "type": "array",
        "items": {"type": "object", "properties": {"id": {}, "title": {}}},
    })
    assert s.find("POST", "/x").body_params == {"id", "title"}
