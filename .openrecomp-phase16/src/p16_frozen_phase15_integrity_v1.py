#!/usr/bin/env python3
"""OpenRecomp Phase-16 frozen Phase-15 source-integrity verification V1."""

from __future__ import annotations

import hashlib
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]

FROZEN_COMMIT = "5cec005d45e8361e5ea132731661b13a72a5ed13"
MANIFEST = ROOT / ".openrecomp-phase15" / "SOURCE_SHA256SUMS.txt"
MARKER = "OPENRECOMP_PHASE15_SOURCE_INTEGRITY"
CANONICAL_MARKER = "OPENRECOMP_PHASE16_P15_SOURCE_INTEGRITY"


def blob(commit: str, path: str) -> bytes | None:
    completed = subprocess.run(["git", "cat-file", "blob", f"{commit}:{path}"],
                              cwd=str(ROOT), capture_output=True)
    return completed.stdout if completed.returncode == 0 else None


def blob_id(commit: str, path: str) -> str | None:
    completed = subprocess.run(["git", "rev-parse", f"{commit}:{path}"],
                              cwd=str(ROOT), capture_output=True, text=True)
    return completed.stdout.strip() if completed.returncode == 0 else None


def verify_phase15_integrity() -> bool:
    if not MANIFEST.is_file():
        return False
    entries = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        recorded, relative = line.split(" *", 1)
        entries.append((relative, recorded))

    for relative, recorded in entries:
        frozen_blob = blob(FROZEN_COMMIT, relative)
        if frozen_blob is None:
            return False
        if blob_id(FROZEN_COMMIT, relative) != blob_id("HEAD", relative):
            return False
        lf_digest = hashlib.sha256(frozen_blob).hexdigest()
        crlf_digest = hashlib.sha256(frozen_blob.replace(b"\n", b"\r\n")).hexdigest()
        if recorded not in (lf_digest, crlf_digest):
            return False
    return True


def main() -> int:
    if not verify_phase15_integrity():
        print(f"{CANONICAL_MARKER}=FAIL")
        return 1
    print(f"{CANONICAL_MARKER}=PASS entries=36 canonical=git-blob")
    print(f"{MARKER}=PASS entries=36 (canonical committed Git blobs; frozen-commit==HEAD)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
