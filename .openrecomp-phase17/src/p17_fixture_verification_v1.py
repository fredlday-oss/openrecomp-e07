#!/usr/bin/env python3
"""Fail-closed private fixture verification helpers for Phase-17."""

from __future__ import annotations

import hashlib
import pathlib
from typing import Callable

EXPECTED_BIN_SHA256 = "2ce144ba0e1fed6952ad80976814e3033fec6cddfb5e17cdf0294517ea311365"
EXPECTED_CUE_SHA256 = "beea454de356689cdaa06702f4ed76a5474fd125a7460619ee678c1ae8725df2"
EXPECTED_SLUS_SHA256 = "c230ff5cd14bdfa392f5d5765c9c907b631875aaaa7844792b38b9ac54930f6f"

EXPECTED_SIZES = {
    "bin": 409_452_624,
    "cue": 101,
    "slus": 129_024,
}


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_fixture(fixture_dir: pathlib.Path) -> tuple[bool, dict[str, object]]:
    """Fail-closed verification of the private Hercules fixture set.

    Returns (ok, report). Any missing file, wrong size, or digest mismatch
    causes failure.
    """
    report: dict[str, object] = {"fixture_dir": fixture_dir.name}
    bin_file = fixture_dir / "Disney's Hercules Action Game (USA).bin"
    cue_file = fixture_dir / "Disney's Hercules Action Game (USA).cue"
    slus_file = fixture_dir / "SLUS_005.29"

    ok = True
    for name, path, expected_hash, expected_size in (
        ("bin", bin_file, EXPECTED_BIN_SHA256, EXPECTED_SIZES["bin"]),
        ("cue", cue_file, EXPECTED_CUE_SHA256, EXPECTED_SIZES["cue"]),
        ("slus", slus_file, EXPECTED_SLUS_SHA256, EXPECTED_SIZES["slus"]),
    ):
        exists = path.is_file()
        report[f"{name}_exists"] = exists
        if not exists:
            ok = False
            continue
        size = path.stat().st_size
        report[f"{name}_size"] = size
        if size != expected_size:
            ok = False
        digest = sha256_file(path)
        report[f"{name}_sha256"] = digest
        if digest != expected_hash:
            report[f"{name}_hash_ok"] = False
            ok = False
        else:
            report[f"{name}_hash_ok"] = True

    return ok, report


def verify_fixture_with_callback(
    fixture_dir: pathlib.Path,
    check: Callable[[str, bool, str], None],
) -> dict[str, object]:
    ok, report = verify_fixture(fixture_dir)
    for name in ("bin", "cue", "slus"):
        exists = report.get(f"{name}_exists", False)
        hash_ok = report.get(f"{name}_hash_ok", False)
        check(f"fixture:{name}-exists", exists, name)
        if exists:
            check(f"fixture:{name}-hash", hash_ok, report.get(f"{name}_sha256", ""))
    return report
