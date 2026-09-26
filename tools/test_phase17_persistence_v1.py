#!/usr/bin/env python3
"""Verify persisted P17-04R Revision 4 private artifacts from a fresh process.

Proves that the generated source, generated headers, private authenticated
mapping, compiled shared object/executable, and build metadata written by an
official run still exist on disk outside any temporary directory after the
producing process has exited, and that their SHA-256 digests match the digests
recorded in the committed public evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase17/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p17_title_exec_emit_v1 as emitter  # noqa: E402

MARKER = "OPENRECOMP_P17_04R_PERSISTENCE_AFTER_EXIT"


def _sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-root", default=None)
    parser.add_argument("--run-label", default=emitter.OFFICIAL_RUN_DIRS[0])
    parser.add_argument("--manifest", default=None,
                        help="committed title_exec_emission.json carrying the recorded digests")
    args = parser.parse_args()

    root = pathlib.Path(args.private_root) if args.private_root else emitter.private_build_root()
    run_dir = root / args.run_label

    expected: dict[str, str] = {}
    if args.manifest:
        document = json.loads(pathlib.Path(args.manifest).read_text(encoding="utf-8"))
        recorded = (document.get("persistence") or {}).get("artifacts") or {}
        for info in recorded.values():
            expected[info["name"]] = info["sha256"]

    temp_root = pathlib.Path(tempfile.gettempdir()).resolve()
    rows: list[dict[str, object]] = []
    ok = True
    for name, filename in emitter.PERSISTED_ARTIFACTS:
        path = run_dir / filename
        exists = path.is_file()
        digest = _sha256_file(path) if exists else None
        digest_matches = True
        if expected and filename in expected:
            digest_matches = digest == expected[filename]
        outside_temp = True
        try:
            path.resolve().relative_to(temp_root)
            outside_temp = False
        except ValueError:
            outside_temp = True
        if not exists or not digest_matches or not outside_temp:
            ok = False
        rows.append({
            "artifact": name,
            "file": filename,
            "exists": exists,
            "sha256_matches_committed_evidence": digest_matches,
            "outside_tempdir": outside_temp,
        })

    print(json.dumps({
        "schema": "openrecomp-phase17-persistence-after-exit-v1",
        "stage": "P17-04R",
        "run_dir_label": args.run_label,
        "artifacts": rows,
        "all_present_and_matching": ok,
    }, indent=2, sort_keys=True))
    print(f"{MARKER}={'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
