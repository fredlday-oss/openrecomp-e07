#!/usr/bin/env python3
"""Create or verify the Phase-10 source-integrity manifest.

The manifest covers the Phase-10 implementation sources, fixtures, runtime
sources and official gates only. Control-plane documents, evidence sidecars and
generated or untracked build products are intentionally outside the manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[2]
MANIFEST = ROOT / ".openrecomp-phase10" / "SOURCE_SHA256SUMS.txt"

PATTERNS = (
    ".openrecomp-phase10/src/*.py",
    ".openrecomp-phase10/fixture/*",
    ".openrecomp-phase10/fixture/**/*",
    ".openrecomp-phase10/runtime/*",
    "tools/test_phase10_*.py",
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
        print("OPENRECOMP_PHASE10_SOURCE_INTEGRITY=FAIL missing-manifest")
        return 1
    recorded: list[str] = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        recorded.append(line.split(" *", 1)[1])
    if tuple(recorded) != paths:
        print("OPENRECOMP_PHASE10_SOURCE_INTEGRITY=FAIL entry-set")
        return 1
    if MANIFEST.read_text(encoding="utf-8") != expected:
        print("OPENRECOMP_PHASE10_SOURCE_INTEGRITY=FAIL digest")
        return 1
    print(f"OPENRECOMP_PHASE10_SOURCE_INTEGRITY=PASS entries={len(paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
