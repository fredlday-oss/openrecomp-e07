#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import zipfile

FIXED_TIME = (2026, 9, 1, 0, 0, 0)


def add_bytes(zf: zipfile.ZipFile, archive_name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(archive_name, FIXED_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    zf.writestr(info, data)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin", required=True)
    parser.add_argument("--dll")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    plugin = Path(args.plugin).resolve()
    out = Path(args.out).resolve()
    if not (plugin / "OpenRecompRuntime.uplugin").is_file():
        raise SystemExit("plugin descriptor missing")

    entries: list[tuple[str, bytes]] = []
    for path in sorted(p for p in plugin.rglob("*") if p.is_file()):
        relative = path.relative_to(plugin).as_posix()
        if any(part in {"Binaries", "Intermediate", "Saved", "DerivedDataCache"} for part in path.relative_to(plugin).parts):
            continue
        entries.append((f"OpenRecompRuntime/{relative}", path.read_bytes()))

    if args.dll:
        dll = Path(args.dll).resolve()
        if not dll.is_file():
            raise SystemExit(f"DLL missing: {dll}")
        entries.append(("OpenRecompRuntime/Binaries/Win64/openrecomp-e07-rv32i.dll", dll.read_bytes()))

    manifest_lines = []
    for archive_name, data in sorted(entries):
        manifest_lines.append(f"{hashlib.sha256(data).hexdigest()}  {archive_name}")
    manifest = ("\n".join(manifest_lines) + "\n").encode("ascii")
    entries.append(("OpenRecompRuntime/OPENRECOMP_PLUGIN_V1_SHA256SUMS.txt", manifest))

    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w") as zf:
        for archive_name, data in sorted(entries):
            add_bytes(zf, archive_name, data)

    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    print(f"OPENRECOMP_UNREAL_PLUGIN_V1_PACKAGE_SHA256={digest}")
    print(f"OPENRECOMP_UNREAL_PLUGIN_V1_PACKAGE_FILES={len(entries)}")
    print("OPENRECOMP_UNREAL_PLUGIN_V1_PACKAGE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
