#!/usr/bin/env python3
"""OpenRecomp Phase-17 frozen Phase-16 source-integrity verification V1."""

from __future__ import annotations

import hashlib
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]

FROZEN_COMMIT = "a0c26e882ca65cfc84cbec78f7e787509a4992a3"
CANONICAL_MARKER = "OPENRECOMP_PHASE17_P16_SOURCE_INTEGRITY"


def blob(commit: str, path: str) -> bytes | None:
    completed = subprocess.run(["git", "cat-file", "blob", f"{commit}:{path}"],
                              cwd=str(ROOT), capture_output=True)
    return completed.stdout if completed.returncode == 0 else None


def blob_id(commit: str, path: str) -> str | None:
    completed = subprocess.run(["git", "rev-parse", f"{commit}:{path}"],
                              cwd=str(ROOT), capture_output=True, text=True)
    return completed.stdout.strip() if completed.returncode == 0 else None


def verify_phase16_integrity() -> bool:
    manifest = ROOT / ".openrecomp-phase16" / "SOURCE_SHA256SUMS.txt"
    if not manifest.is_file():
        return False
    entries = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
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
    if not verify_phase16_integrity():
        print(f"{CANONICAL_MARKER}=FAIL")
        return 1
    print(f"{CANONICAL_MARKER}=PASS entries=31 canonical=git-blob")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
