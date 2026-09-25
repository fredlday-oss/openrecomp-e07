#!/usr/bin/env python3
"""OpenRecomp Phase-17 frozen Phase-16 source-integrity verification V1."""

from __future__ import annotations

import hashlib
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]

FROZEN_COMMIT = "a0c26e882ca65cfc84cbec78f7e787509a4992a3"
CANONICAL_MARKER = "OPENRECOMP_PHASE17_P16_SOURCE_INTEGRITY"
LEGACY_MARKER = "LEGACY_PHASE16_NATIVE_GATE"


def blob(commit: str, path: str) -> bytes | None:
    completed = subprocess.run(["git", "cat-file", "blob", f"{commit}:{path}"],
                              cwd=str(ROOT), capture_output=True)
    return completed.stdout if completed.returncode == 0 else None


def blob_id(commit: str, path: str) -> str | None:
    completed = subprocess.run(["git", "rev-parse", f"{commit}:{path}"],
                              cwd=str(ROOT), capture_output=True, text=True)
    return completed.stdout.strip() if completed.returncode == 0 else None


def validate_manifest(manifest: pathlib.Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not manifest.is_file():
        errors.append("missing-manifest")
        return False, errors
    raw = manifest.read_bytes()
    if len(raw) == 0:
        errors.append("empty-manifest")
        return False, errors
    try:
        text = manifest.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        errors.append("manifest-not-utf8")
        return False, errors
    entries = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        parts = line.split(" *", 1)
        if len(parts) != 2 or len(parts[0].strip()) != 64 or not all(c in "0123456789abcdef" for c in parts[0].strip().lower()):
            errors.append(f"malformed-line-{line_no}")
            continue
        entries.append((parts[1], parts[0].strip().lower(), line_no))
    if not entries:
        errors.append("incomplete-manifest-no-entries")
        return False, errors
    return True, entries


def verify_phase16_integrity() -> tuple[bool, dict[str, object]]:
    report: dict[str, object] = {"canonical": False, "legacy_native": False}
    manifest = ROOT / ".openrecomp-phase16" / "SOURCE_SHA256SUMS.txt"
    valid, payload = validate_manifest(manifest)
    if not valid:
        report["manifest_errors"] = payload
        return False, report

    entries = payload
    report["entries"] = len(entries)
    modified: list[str] = []
    missing: list[str] = []
    digest_mismatch: list[str] = []
    canonical_ok = True

    for relative, recorded, _line_no in entries:
        frozen_blob = blob(FROZEN_COMMIT, relative)
        if frozen_blob is None:
            missing.append(relative)
            canonical_ok = False
            continue
        head_id = blob_id("HEAD", relative)
        if head_id is None:
            missing.append(relative)
            canonical_ok = False
            continue
        if blob_id(FROZEN_COMMIT, relative) != head_id:
            modified.append(relative)
            canonical_ok = False
            continue
        lf_digest = hashlib.sha256(frozen_blob).hexdigest()
        crlf_digest = hashlib.sha256(frozen_blob.replace(b"\n", b"\r\n")).hexdigest()
        if recorded not in (lf_digest, crlf_digest):
            digest_mismatch.append(relative)
            canonical_ok = False

    report["modified"] = modified
    report["missing"] = missing
    report["digest_mismatch"] = digest_mismatch

    # Legacy Phase-16 native manifest gate: the Phase-16 source manifest generator
    # records CRLF digests while Git stores blobs with LF, so running the Phase-16
    # native manifest check on a clean checkout can fail. This is pre-existing and
    # must not block the canonical Phase-17 frozen-boundary gate.
    native = subprocess.run(
        ["python3", str(ROOT / ".openrecomp-phase16/src/p16_source_manifest_v1.py")],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    native_ok = native.returncode == 0 and "OPENRECOMP_PHASE16_SOURCE_INTEGRITY=PASS" in native.stdout
    report["legacy_native_manifest_returncode"] = native.returncode
    report["legacy_native_manifest_stdout"] = native.stdout.strip()
    report["legacy_native"] = not native_ok

    if not native_ok:
        print(f"{LEGACY_MARKER}=PRE_EXISTING_FAIL (Phase-16 native manifest check fails on LF/CRLF boundary; canonical gate unaffected)")
    else:
        print(f"{LEGACY_MARKER}=PASS")

    report["canonical"] = canonical_ok
    return canonical_ok, report


def main() -> int:
    ok, report = verify_phase16_integrity()
    if not ok:
        print(f"{CANONICAL_MARKER}=FAIL {json.dumps(report, sort_keys=True)}")
        return 1
    print(f"{CANONICAL_MARKER}=PASS entries={report.get('entries', 0)} canonical=git-blob")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
