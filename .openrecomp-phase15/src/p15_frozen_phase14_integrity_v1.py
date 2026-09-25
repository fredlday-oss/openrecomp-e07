#!/usr/bin/env python3
"""OpenRecomp Phase-15 frozen Phase-14 source-integrity verification V1.

The frozen Phase-14 manifest (``.openrecomp-phase14/SOURCE_SHA256SUMS.txt``) is
the Phase-14 authority. This module verifies the *canonical committed Git blobs*
of every manifest entry at the frozen Phase-14 terminal commit against the
current ``HEAD``, without modifying, normalizing or rewriting any frozen
Phase-14 file:

* for every manifest entry the frozen-commit blob (``git cat-file blob``) is
  read directly;
* the blob object id at the frozen Phase-14 terminal commit is required to equal
  the blob object id at the current ``HEAD``;
* the recorded SHA-256 must equal the canonical LF blob digest, or the LF->CRLF
  form of the same canonical blob (documented checkout convention). No
  normalized hash is substituted for the recorded hash.

Any other mismatch fails closed.
"""

from __future__ import annotations

import hashlib
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]

FROZEN_COMMIT = "830be0f7be998061e8d442134cfae511d5dd8c62"
MANIFEST = ROOT / ".openrecomp-phase14" / "SOURCE_SHA256SUMS.txt"
MARKER = "OPENRECOMP_PHASE14_SOURCE_INTEGRITY"
CANONICAL_MARKER = "OPENRECOMP_PHASE15_P14_SOURCE_INTEGRITY"


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
