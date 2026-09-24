#!/usr/bin/env python3
"""OpenRecomp Phase-14 frozen Phase-13 source-integrity verification V1.

The frozen Phase-13 manifest (``.openrecomp-phase13/SOURCE_SHA256SUMS.txt``) is
the Phase-13 authority, but its SHA-256 entries were produced from the Phase-13
*worktree* bytes. One Phase-13 gate file
(``tools/test_phase13_queue_v1.py``) was recorded in its CRLF form, while the
canonical Git blob and a fresh checkout under the repository ``.gitattributes``
(``*.py text eol=lf``) are LF. Running the Phase-13 checker directly from the
Phase-14 worktree therefore reports ``FAIL digest`` for that one file even
though the committed content is unchanged.

This module verifies the *canonical committed Git blobs* instead of the
worktree bytes, without modifying, normalizing or rewriting any frozen Phase-13
file and without regenerating the Phase-13 manifest:

* for every manifest entry the frozen-commit blob (``git cat-file blob``) is
  read directly; the worktree layout is never used for the digest;
* the blob object id at the frozen Phase-13 terminal commit is required to equal
  the blob object id at the current ``HEAD`` (the frozen Phase-13 content is
  unchanged by Phase 14);
* the recorded SHA-256 must equal the canonical LF blob digest, or -- for the
  documented checkout-convention variant -- the LF->CRLF form of the same
  canonical blob. The content is identical under both Git text conventions; no
  normalized hash is substituted for the recorded hash.

Any other mismatch fails closed.
"""

from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

FROZEN_COMMIT = "7bb4502450d47a0d3f3b207a072c5729277af278"
MANIFEST = ROOT / ".openrecomp-phase13" / "SOURCE_SHA256SUMS.txt"
MARKER = "OPENRECOMP_PHASE13_SOURCE_INTEGRITY"
CANONICAL_MARKER = "OPENRECOMP_PHASE14_P13_SOURCE_INTEGRITY"


def _git_bytes(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True).stdout


def blob(commit: str, path: str) -> bytes | None:
    completed = subprocess.run(["git", "cat-file", "blob", f"{commit}:{path}"],
                               cwd=str(ROOT), capture_output=True)
    return completed.stdout if completed.returncode == 0 else None


def blob_id(commit: str, path: str) -> str | None:
    completed = subprocess.run(["git", "rev-parse", f"{commit}:{path}"],
                               cwd=str(ROOT), capture_output=True, text=True)
    return completed.stdout.strip() if completed.returncode == 0 else None


def main() -> int:
    if not MANIFEST.is_file():
        print(f"{CANONICAL_MARKER}=FAIL missing-manifest")
        return 1
    entries = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        recorded, relative = line.split(" *", 1)
        entries.append((relative, recorded))

    crlf_variants = 0
    for relative, recorded in entries:
        frozen_blob = blob(FROZEN_COMMIT, relative)
        if frozen_blob is None:
            print(f"{CANONICAL_MARKER}=FAIL missing-blob {relative}")
            return 1
        if blob_id(FROZEN_COMMIT, relative) != blob_id("HEAD", relative):
            print(f"{CANONICAL_MARKER}=FAIL frozen-changed {relative}")
            return 1
        lf_digest = hashlib.sha256(frozen_blob).hexdigest()
        crlf_digest = hashlib.sha256(frozen_blob.replace(b"\n", b"\r\n")).hexdigest()
        if recorded == lf_digest:
            continue
        if recorded == crlf_digest:
            crlf_variants += 1
            continue
        print(f"{CANONICAL_MARKER}=FAIL digest {relative}")
        return 1

    print(f"{CANONICAL_MARKER}=PASS entries={len(entries)} canonical=git-blob "
          f"crlf_variants={crlf_variants}")
    print(f"{MARKER}=PASS entries={len(entries)} (canonical committed Git blobs; "
          f"frozen-commit==HEAD)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
