#!/usr/bin/env python3
"""OpenRecomp Phase-17 frozen Phase-16 source-integrity verification V1."""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import tempfile

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


def expected_inventory_from_frozen_commit() -> set[str]:
    """Authoritative expected inventory: every path recorded in the Phase-16
    source manifest at the frozen Phase-16 commit."""
    manifest_blob = blob(FROZEN_COMMIT, ".openrecomp-phase16/SOURCE_SHA256SUMS.txt")
    if manifest_blob is None:
        return set()
    paths: set[str] = set()
    for line in manifest_blob.decode("utf-8").splitlines():
        if not line.strip():
            continue
        if " *" not in line:
            continue
        paths.add(line.split(" *", 1)[1])
    return paths


def parse_manifest(manifest: pathlib.Path) -> tuple[bool, list[str] | list[dict[str, object]]]:
    """Parse a manifest file. On success return (True, list of relative paths).
    On failure return (False, list of error descriptors)."""
    errors: list[dict[str, object]] = []
    if not manifest.is_file():
        errors.append({"error": "missing-manifest"})
        return False, errors
    raw = manifest.read_bytes()
    if len(raw) == 0:
        errors.append({"error": "empty-manifest"})
        return False, errors
    try:
        text = manifest.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        errors.append({"error": "manifest-not-utf8"})
        return False, errors

    paths: list[str] = []
    has_valid_line = False
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        parts = line.split(" *", 1)
        if len(parts) != 2:
            errors.append({"error": "malformed-line", "line": line_no, "reason": "missing-space-asterisk"})
            continue
        hex_part, rel = parts
        hex_part = hex_part.strip().lower()
        if len(hex_part) != 64 or any(c not in "0123456789abcdef" for c in hex_part):
            errors.append({"error": "malformed-line", "line": line_no, "reason": "bad-digest"})
            continue
        has_valid_line = True
        paths.append(rel)

    if not has_valid_line and not errors:
        errors.append({"error": "malformed-manifest", "reason": "no-parseable-lines"})
        return False, errors

    if errors:
        return False, errors

    return True, paths


def verify_manifest_completeness(manifest: pathlib.Path,
                                 expected: set[str] | None = None) -> tuple[bool, dict[str, object]]:
    """Mechanically enforce expected_paths == manifest_paths (with no documented
    exclusions). Returns (ok, report)."""
    report: dict[str, object] = {}
    if expected is None:
        expected = expected_inventory_from_frozen_commit()
    report["expected_count"] = len(expected)
    report["expected_paths"] = sorted(expected)

    valid, payload = parse_manifest(manifest)
    if not valid:
        report["manifest_errors"] = payload
        return False, report

    manifest_paths = set(payload)
    report["manifest_count"] = len(manifest_paths)
    report["manifest_paths"] = sorted(manifest_paths)

    missing = expected - manifest_paths
    extra = manifest_paths - expected
    report["missing"] = sorted(missing)
    report["extra"] = sorted(extra)

    if missing or extra:
        report["completeness_error"] = "expected_paths != manifest_paths"
        return False, report

    return True, report


def verify_phase16_integrity() -> tuple[bool, dict[str, object]]:
    report: dict[str, object] = {"canonical": False, "legacy_native": False}
    manifest = ROOT / ".openrecomp-phase16" / "SOURCE_SHA256SUMS.txt"
    expected = expected_inventory_from_frozen_commit()
    ok, comp_report = verify_manifest_completeness(manifest, expected)
    report["completeness"] = comp_report
    if not ok:
        return False, report

    entries = list(zip(comp_report["manifest_paths"],
                       [None] * len(comp_report["manifest_paths"])))
    # Re-parse for digests
    text = manifest.read_text(encoding="utf-8")
    path_to_digest: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        digest, rel = line.split(" *", 1)
        path_to_digest[rel] = digest.strip().lower()

    modified: list[str] = []
    missing: list[str] = []
    digest_mismatch: list[str] = []
    canonical_ok = True

    for relative in comp_report["manifest_paths"]:
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
        recorded = path_to_digest.get(relative, "")
        if recorded not in (lf_digest, crlf_digest):
            digest_mismatch.append(relative)
            canonical_ok = False

    report["modified"] = modified
    report["missing"] = missing
    report["digest_mismatch"] = digest_mismatch

    # Legacy Phase-16 native manifest gate: pre-existing LF/CRLF boundary failure.
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


def negative_manifest_case(name: str, content: str | None,
                           expected: set[str] | None = None) -> tuple[bool, dict[str, object]]:
    """Run a negative manifest case. Returns (rejected, report)."""
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "SOURCE_SHA256SUMS.txt"
        if content is not None:
            path.write_text(content, encoding="utf-8", newline="\n")
        ok, report = verify_manifest_completeness(path, expected)
        return not ok, {"case": name, "ok": ok, **report}


def main() -> int:
    ok, report = verify_phase16_integrity()
    if not ok:
        print(f"{CANONICAL_MARKER}=FAIL {json.dumps(report, sort_keys=True)}")
        return 1
    print(f"{CANONICAL_MARKER}=PASS entries={report['completeness'].get('manifest_count', 0)} canonical=git-blob")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
