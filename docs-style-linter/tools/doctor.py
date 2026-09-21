#!/usr/bin/env python3
"""Check that everything the toolkit needs is installed, and say what to do.

Written for someone who does not spend their day in a terminal. Every failure
names the exact command that fixes it, rather than printing a stack trace and
leaving the reader to guess.
"""
from __future__ import annotations

import importlib.util
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO = ROOT.parent

OK, BAD = "  ok  ", " todo "


# 3.9 is the real floor: every module uses `from __future__ import annotations`,
# so modern type syntax stays lazy, and the only 3.9-specific call is
# pathlib.Path.is_relative_to in the pipeline's staging guard. Checked with
# vermin. An earlier version of this file demanded 3.11 and would have sent a
# macOS user (which ships 3.9) off to install a Python they did not need.
MIN_PYTHON = (3, 9)


def check_python() -> tuple[bool, str, str]:
    version = sys.version_info
    good = (version.major, version.minor) >= MIN_PYTHON
    wanted = ".".join(str(n) for n in MIN_PYTHON)
    return good, f"Python {version.major}.{version.minor}", (
        "" if good else f"Install Python {wanted} or newer from python.org"
    )


def check_pyyaml() -> tuple[bool, str, str]:
    found = importlib.util.find_spec("yaml") is not None
    return found, "PyYAML package", (
        "" if found else f"{sys.executable} -m pip install -r requirements.txt"
    )


def check_vale() -> tuple[bool, str, str]:
    path = shutil.which("vale") or str(pathlib.Path.home() / "go" / "bin" / "vale")
    if not pathlib.Path(path).exists():
        return False, "Vale", "./tools/install_vale.sh"
    try:
        version = subprocess.run([path, "--version"], capture_output=True, text=True,
                                 timeout=20).stdout.strip()
    except Exception:
        version = "unknown version"
    if not shutil.which("vale"):
        return False, f"Vale ({version}) found but not on PATH", (
            'export PATH="$HOME/.local/bin:$PATH"  (add to ~/.zshrc or ~/.bashrc)'
        )
    return True, f"Vale — {version}", ""


def check_corpus() -> tuple[bool, str, str]:
    corpus = REPO / "corpus" / "meilisearch-docs"
    pages = len(list(corpus.rglob("*.mdx"))) if corpus.is_dir() else 0
    return pages > 0, f"Example docs ({pages} pages)", (
        "" if pages else "The corpus/ folder is missing. Re-clone the repository."
    )


def check_spec() -> tuple[bool, str, str]:
    spec = REPO / "spec" / "meilisearch-openapi.json"
    return spec.is_file(), "Example API definition", (
        "" if spec.is_file() else "spec/meilisearch-openapi.json is missing. Re-clone the repository."
    )


def main() -> int:
    checks = [check_python, check_pyyaml, check_vale, check_corpus, check_spec]
    results = [check() for check in checks]

    print("\nChecking what's installed:\n")
    for good, label, _ in results:
        print(f"[{OK if good else BAD}] {label}")

    missing = [(label, fix) for good, label, fix in results if not good]
    if not missing:
        print("\nEverything is ready. Try:  make report\n")
        return 0

    print("\nTo fix:\n")
    for label, fix in missing:
        print(f"  {label}")
        print(f"    {fix}\n")
    print("Then run `make doctor` again.\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
