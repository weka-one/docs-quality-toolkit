import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from freshness.spec import Spec  # noqa: E402

SPEC_PATH = ROOT.parent / "spec" / "meilisearch-openapi.json"
CORPUS = ROOT.parent / "corpus" / "meilisearch-docs"


@pytest.fixture(scope="session")
def spec() -> Spec:
    return Spec.load(SPEC_PATH)


@pytest.fixture(scope="session")
def corpus() -> pathlib.Path:
    return CORPUS
