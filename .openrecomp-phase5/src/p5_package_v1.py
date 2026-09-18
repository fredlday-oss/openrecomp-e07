#!/usr/bin/env python3
"""Phase-5 reproducible public NES package (P5-12).

Builds a deterministic ZIP containing only redistributable Phase-5 artifacts:
the control plane, sources, the original fixture assembly, all gates, evidence
P5-00 .. P5-10, the generated native translation sources for the declared
canonical plan, reproduction instructions and a per-member manifest.

Fail-closed exclusions: the private TMNT image (bytes, banks, evidence P5-11),
binary members, CRLF text, build/scratch workspaces.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import zipfile
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for entry in (str(ROOT), str(ROOT / "tools"), str(ROOT / ".openrecomp-phase5" / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import p5_emit_v1 as emit  # noqa: E402
import p5_fixture_build_v1 as fixture_build  # noqa: E402
import p5_frontier_v1 as frontier  # noqa: E402
import p5_ines_v1 as ingestion  # noqa: E402
import p5_structure_v1 as structure  # noqa: E402
import p5_support_v1 as support_module  # noqa: E402
from openrecomp.frontends import nes6502 as bridge  # noqa: E402

PACKAGE_DIR = ROOT / ".openrecomp-phase5" / "package"
PACKAGE_NAME = "phase5_nes_package_v1.zip"
MANIFEST_NAME = "P5_PACKAGE_MANIFEST.json"
REPRODUCE_NAME = "REPRODUCE.md"
CANONICAL_PLAN = (0x01, 0x00, 0x04, 0x80, 0x00, 0x00, 0x00, 0x00)
EVIDENCE_STAGES = tuple(f"P5-{index:02d}"
                        for index in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10))
CONTROL_FILES = (
    "CONTROL_POLICY.md", "EVIDENCE_SCHEMA.md", "FIXTURE_POLICY.md",
    "HANDOFF.md", "SCOPE.md", "SOURCE_SHA256SUMS.txt", "STAGE_QUEUE.md",
    "STATE.md",
)
FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
PRIVATE_ROM = pathlib.Path(r"D:\OpenRecomp\Roms\phase1\nes\primary\tmnt.nes")
PRIVATE_PROBE_SLICE = (0x2000, 0x2100)


class PackageError(ValueError):
    """Fail-closed package error."""


def _read(path: pathlib.Path) -> bytes:
    data = path.read_bytes()
    return data


SELF_REFERENTIAL_GATES = frozenset({
    "test_phase5_package_v1.py",
    "test_phase5_whole_regression_v1.py",
    "test_phase5_evidence_index_v1.py",
    "test_phase5_final_verdict_v1.py",
})


def _check_text(name: str, data: bytes) -> None:
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PackageError(f"{name}: member is not UTF-8 text") from exc
    if b"\r" in data:
        raise PackageError(f"{name}: member contains CR bytes")


def _private_probe() -> bytes:
    if not PRIVATE_ROM.is_file():
        raise PackageError("private fixture is not present for the exclusion scan")
    data = PRIVATE_ROM.read_bytes()
    start, end = PRIVATE_PROBE_SLICE
    return data[16 + start:16 + end]


def collect_members() -> dict[str, bytes]:
    members: dict[str, bytes] = {}
    for name in CONTROL_FILES:
        path = ROOT / ".openrecomp-phase5" / name
        members[f"control/{name}"] = _read(path)
    members["fixture/p5_public_fixture.asm"] = _read(
        ROOT / ".openrecomp-phase5" / "fixture" / "p5_public_fixture.asm")
    for path in sorted((ROOT / ".openrecomp-phase5" / "src").glob("*.py")):
        members[f"src/{path.name}"] = _read(path)
    for path in sorted((ROOT / "tools").glob("test_phase5_*.py")):
        if path.name in SELF_REFERENTIAL_GATES:
            continue  # the terminal gates verify the package and are hash-pinned elsewhere
        members[f"gates/{path.name}"] = _read(path)
    for stage in EVIDENCE_STAGES:
        directory = ROOT / ".openrecomp-phase5" / "evidence" / stage
        for path in sorted(directory.iterdir()):
            if path.is_file():
                members[f"evidence/{stage}/{path.name}"] = _read(path)
    rom, metadata = fixture_build.build()
    inventory = ingestion.ingest(rom, source_label="public_fixture").to_document()
    image = frontier.build_cpu_image(rom, 16, metadata["prg_size"])
    start, end = frontier.code_region_from_metadata(metadata)
    instructions = bridge.bridge_region(image, entry=start, end=end)
    analysis = structure.build_structure(rom, metadata, inventory)
    exit_sites = {item["address"]: emit.EXIT_SERVICE_NAME
                  for item in analysis["indirect_classifications"]}
    program = emit.emit_program(instructions, metadata, exit_sites)
    support = support_module.emit_support(rom, inventory, CANONICAL_PLAN,
                                          rom_sha256=metadata["rom_sha256"])
    members["generated/p5_nes_program.c"] = program.encode("utf-8")
    members["generated/p5_nes_support.c"] = support.encode("utf-8")
    members["generated/public_fixture_metadata.json"] = (
        json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode("utf-8")
    members[REPRODUCE_NAME] = reproduce_text(metadata).encode("utf-8")
    return members


def reproduce_text(metadata: dict) -> str:
    plan = ", ".join(f"0x{value:02X}" for value in CANONICAL_PLAN)
    return f"""# OpenRecomp Phase-5 NES package reproduction

Public fixture (original, Apache-2.0):
- rom_sha256: {metadata['rom_sha256']}
- prg_sha256: {metadata['prg_sha256']}
- chr_sha256: {metadata['chr_sha256']}
- mapper: 0 (NROM-128); mirroring: horizontal

Steps (Windows, from the repository root):

1. Rebuild the public fixture and verify its identity:

       python .openrecomp-phase5/src/p5_fixture_build_v1.py

2. Re-run the Phase-5 stage gates with the stage runner, for example:

       python .openrecomp-phase5/src/p5_stage_runner_v1.py --stage P5-08 \\
         --script tools/test_phase5_host_emit_v1.py \\
         --evidence-dir .openrecomp-phase5/evidence/P5-08 \\
         --tests-json p5_08_tests.json

3. Rebuild the native translation from the packaged generated sources with
   zig 0.13.0 (recorded toolchain identity; not shipped):

       zig cc -std=c11 -O1 -o program.exe generated/p5_nes_program.c \\
         generated/p5_nes_support.c

   The canonical input plan embedded in the support is: {plan}.

4. Whole regression (P5-90):

       python tools/test_phase5_whole_regression_v1.py

Determinism: the stage gates are run twice with byte-identical stdout and
identical evidence records; the native build is `EXECUTABLE_REPRODUCIBLE`
through the shared Phase-2 build pipeline.

Claim boundary: this package proves only the bounded audited public-fixture
claim. No general NES, mapper, commercial-game, cycle-accuracy or full
PPU/APU compatibility is claimed.
"""


def build_package() -> tuple[bytes, dict[str, Any]]:
    members = collect_members()
    probe = _private_probe()
    for name, data in members.items():
        _check_text(name, data)
        if data == probe:
            raise PackageError(f"{name}: contains the private fixture probe")
        if len(data) == 262160 and hashlib.sha256(data).hexdigest() == (
                "2a9345e608ec0c57470dc6658ce8199ddea9c18076134d9ef2a56f91b0a066d1"):
            raise PackageError(f"{name}: private fixture bytes are packaged")
    if any(name.startswith("evidence/P5-11/") for name in members):
        raise PackageError("private P5-11 evidence must not be packaged")

    manifest_members = []
    for name in sorted(members):
        data = members[name]
        manifest_members.append({
            "name": name,
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    fingerprint = hashlib.sha256(
        (json.dumps(manifest_members, indent=2, sort_keys=True) + "\n").encode("utf-8")
    ).hexdigest()
    manifest = {
        "package": "openrecomp-phase5-nes-v1",
        "stage": "P5-12",
        "member_count": len(manifest_members),
        "members": manifest_members,
        "fingerprint": fingerprint,
        "exclusions": ["private TMNT image and P5-11 evidence", "binary members",
                       "build/scratch workspaces"],
    }
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    members[MANIFEST_NAME] = manifest_bytes

    buffer = __import__("io").BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as archive:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, members[name])
    return buffer.getvalue(), manifest


def package_path() -> pathlib.Path:
    return PACKAGE_DIR / PACKAGE_NAME


def write_package() -> tuple[pathlib.Path, dict[str, Any]]:
    data, manifest = build_package()
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
    package_path().write_bytes(data)
    return package_path(), manifest


__all__ = [
    "CANONICAL_PLAN",
    "CONTROL_FILES",
    "EVIDENCE_STAGES",
    "MANIFEST_NAME",
    "PACKAGE_NAME",
    "PackageError",
    "REPRODUCE_NAME",
    "build_package",
    "collect_members",
    "package_path",
    "reproduce_text",
    "write_package",
]
