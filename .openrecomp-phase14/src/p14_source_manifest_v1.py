#!/usr/bin/env python3
"""Phase-14 source-integrity manifest.

The manifest covers the Phase-14 implementation sources, runtime sources and
official gates. Control-plane documents, evidence sidecars and generated or
untracked build products are outside the manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
MANIFEST = ROOT / ".openrecomp-phase14" / "SOURCE_SHA256SUMS.txt"

INTEGRITY_MARKER = "OPENRECOMP_PHASE14_SOURCE_INTEGRITY"

PATTERNS = (
    ".openrecomp-phase14/src/*.py",
    ".openrecomp-phase14/runtime/*",
    "tools/test_phase14_*.py",
)


def tracked_paths() -> tuple[str, ...]:
    found: set[str] = set()
    for pattern in PATTERNS:
        for path in ROOT.glob(pattern):
            if not path.is_file() or path.name == "__init__.py":
                continue
            relative = path.relative_to(ROOT)
            if "__pycache__" in relative.parts or relative.suffix == ".pyc":
                continue
            found.add(relative.as_posix())
    return tuple(sorted(found))


def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_text(paths: tuple[str, ...]) -> str:
    return "".join(f"{digest(ROOT / rel)} *{rel}\n" for rel in paths)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    paths = tracked_paths()
    expected = expected_text(paths)
    if args.write:
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(expected, encoding="utf-8", newline="\n")
        return 0
    if not MANIFEST.is_file():
        print(f"{INTEGRITY_MARKER}=FAIL missing-manifest")
        return 1
    recorded = [line.split(" *", 1)[1] for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line.strip()]
    if tuple(recorded) != paths:
        print(f"{INTEGRITY_MARKER}=FAIL entry-set")
        return 1
    if MANIFEST.read_text(encoding="utf-8") != expected:
        print(f"{INTEGRITY_MARKER}=FAIL digest")
        return 1
    print(f"{INTEGRITY_MARKER}=PASS entries={len(paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
