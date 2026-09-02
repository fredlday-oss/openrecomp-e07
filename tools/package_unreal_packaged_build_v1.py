#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import zipfile

FIXED_TIME = (2026, 9, 2, 0, 0, 0)
ROOT_NAME = "OPENRECOMP_UNREAL_PACKAGED_BUILD_V1"


def add_bytes(zf: zipfile.ZipFile, archive_name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(archive_name, FIXED_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    zf.writestr(info, data)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin", required=True)
    parser.add_argument("--support", required=True)
    parser.add_argument("--dll", required=True)
    parser.add_argument("--source-head", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    plugin = Path(args.plugin).resolve()
    support = Path(args.support).resolve()
    dll = Path(args.dll).resolve()
    out = Path(args.out).resolve()

    if not (plugin / "OpenRecompRuntime.uplugin").is_file():
        raise SystemExit("plugin descriptor missing")
    if not support.is_dir():
        raise SystemExit("packaged-build support directory missing")
    if not dll.is_file():
        raise SystemExit(f"DLL missing: {dll}")
    if len(args.source_head) != 40 or any(c not in "0123456789abcdefABCDEF" for c in args.source_head):
        raise SystemExit("--source-head must be a 40-character commit SHA")

    entries: list[tuple[str, bytes]] = []
    for path in sorted(p for p in plugin.rglob("*") if p.is_file()):
        relative_path = path.relative_to(plugin)
        if any(part in {"Binaries", "Intermediate", "Saved", "DerivedDataCache"} for part in relative_path.parts):
            continue
        entries.append((f"{ROOT_NAME}/OpenRecompRuntime/{relative_path.as_posix()}", path.read_bytes()))

    entries.append((f"{ROOT_NAME}/OpenRecompRuntime/Binaries/Win64/openrecomp-e07-rv32i.dll", dll.read_bytes()))

    for path in sorted(p for p in support.rglob("*") if p.is_file()):
        relative = path.relative_to(support).as_posix()
        entries.append((f"{ROOT_NAME}/{relative}", path.read_bytes()))

    provenance = (
        "OPENRECOMP_UNREAL_PACKAGED_BUILD_V1_PROVENANCE\n"
        f"SOURCE_HEAD={args.source_head.lower()}\n"
        "HOSTED_CI_SCOPE=source-contract+validated-native-module+engine-independent-host-core+deterministic-handoff\n"
        "LOCAL_GATE=Unreal Engine 5.8 Windows x64 Development package+launch\n"
        "EXPECTED_MODULE=e07.rv32i.fixture-full.ir-v1\n"
        "EXPECTED_ARCH=riscv32-rv32i\n"
        "EXPECTED_OBSERVED_STATE=48\n"
        "EXPECTED_CHECKSUM=122010428\n"
        "EXPECTED_OPERATIONS=3866\n"
    ).encode("ascii")
    entries.append((f"{ROOT_NAME}/OPENRECOMP_PACKAGED_BUILD_V1_PROVENANCE.txt", provenance))

    manifest_lines = []
    for archive_name, data in sorted(entries):
        relative = archive_name.removeprefix(f"{ROOT_NAME}/")
        manifest_lines.append(f"{hashlib.sha256(data).hexdigest()}  {relative}")
    manifest = ("\n".join(manifest_lines) + "\n").encode("ascii")
    entries.append((f"{ROOT_NAME}/OPENRECOMP_PACKAGED_BUILD_V1_SHA256SUMS.txt", manifest))
    entries.append((f"{ROOT_NAME}/OpenRecompRuntime/OPENRECOMP_PACKAGED_BUILD_V1_SHA256SUMS.txt", manifest))

    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w") as zf:
        for archive_name, data in sorted(entries):
            add_bytes(zf, archive_name, data)

    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    print(f"OPENRECOMP_UNREAL_PACKAGED_BUILD_V1_HANDOFF_SHA256={digest}")
    print(f"OPENRECOMP_UNREAL_PACKAGED_BUILD_V1_HANDOFF_FILES={len(entries)}")
    print("OPENRECOMP_UNREAL_PACKAGED_BUILD_V1_HANDOFF=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
