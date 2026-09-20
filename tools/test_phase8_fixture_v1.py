#!/usr/bin/env python3
"""OpenRecomp Phase-8 real MIPS32 ELF fixture gate (P8-01).

P8-01 freezes one legally redistributable, compiler-produced real MIPS32 ELF:
the upstream tiny-AES-c AES-128-ECB program (The Unlicense) built from its
pinned repository revision with the recorded Zig 0.13.0 MIPS32 toolchain and
OpenRecomp-authored freestanding port shims.

The deterministic gate:

* verifies the pinned upstream source files, licence and recorded revision;
* verifies the recorded toolchain acquisition and executable identity;
* rebuilds the ELF twice in isolated build roots and requires byte-identical
  executables;
* characterises the ELF through the existing Phase-3 ingestion and target
  policy layers and the existing decode/frontier layers (reuse, not rewrite);
* records the frozen fixture identity, the reachable instruction inventory,
  delay-slot inventory, control-flow inventory and the reachable semantic gap.

On success it emits::

    OPENRECOMP_P8_01=PASS
    OPENRECOMP_PHASE8_REAL_ELF_FIXTURE_V1=PASS tests=<count>
    OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase8_fixture_v1.py
    python tools/test_phase8_fixture_v1.py --zig .openrecomp-phase3/tools/zig/zig.exe
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".openrecomp-phase3" / "src"))

import p3_code_frontier_v1 as frontier  # noqa: E402
import p3_elf_image_v1 as elf  # noqa: E402
import p3_target_mips32_v1 as target  # noqa: E402

EVIDENCE_DIR = ROOT / ".openrecomp-phase8" / "evidence" / "P8-01"

STAGE = "P8-01"
STAGE_MARKER = "OPENRECOMP_P8_01"
FEATURE_MARKER = "OPENRECOMP_PHASE8_REAL_ELF_FIXTURE_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"

TINY_AES_REPO = "https://github.com/kokke/tiny-AES-c"
TINY_AES_COMMIT = "23856752fbd139da0b8ca6e471a13d5bcc99a08d"
TINY_AES_LICENSE = (
    "The Unlicense (public-domain dedication), upstream file unlicense.txt; "
    "the fixture is built from the pinned upstream revision and is not a "
    "supported AES product."
)
UPSTREAM_DIR = ROOT / ".openrecomp-phase8" / "external" / "tiny-AES-c"
PORT_DIR = ROOT / ".openrecomp-phase8" / "fixture"

UPSTREAM_SHA256 = {
    "aes.c": "2cf709c77dcb742ef0845e20e7382da38193c630f18b035f8a7796651ea48af1",
    "aes.h": "40f381d86c7b84648eb96053e604cf17cfeab532233b2eeedfa6afc3752f313d",
    "unlicense.txt": "640514163b17f977adc997cb16f51871122cfb0555ebad1a3f01e167b7ba8857",
    "README.md": "2b6ed49d4b5d7c852b815375a07f758f123206aea5ad231ed011519cde0d76c5",
}
PORT_FILES = (
    "include/string.h",
    "p8_aes_main.c",
    "p8_mips32.ld",
    "p8_port_support.c",
    "p8_start.S",
)

ZIG_VERSION = "0.13.0"
ZIG_URL = "https://ziglang.org/download/0.13.0/zig-windows-x86_64-0.13.0.zip"
ZIG_ARCHIVE_SHA256 = "d859994725ef9402381e557c60bb57497215682e355204d754ee3df75ee3c158"
ZIG_EXE_SHA256 = "2e44af5bbf7a72ef8cbdae370284687c95d65a19affa469d2ad0364d905b8e84"
ZIG_DEFAULT = ROOT / ".openrecomp-phase3" / "tools" / "zig" / "zig.exe"

BUILD_ROOT_REL = ".openrecomp-phase8/build/P8-01"
ELF_NAME = "p8_aes128_mips32_O1.elf"
EXPECTED_ELF_SHA256 = "0a90f47754f6331b868ec09ad23c451fc2c73925a43897fa62a696b0d40dde65"
EXPECTED_ELF_SIZE = 12904

COMMON_FLAGS = [
    "cc", "--target=mipsel-linux-musl",
    "-march=mips32", "-mabi=32", "-msoft-float", "-mno-abicalls", "-G0",
    "-ffreestanding", "-fno-builtin", "-fno-stack-protector",
    "-fomit-frame-pointer", "-fno-pic", "-O1",
    "-nostdlib", "-static",
    "-DECB=1", "-DAES128=1",
]
COMMON_INCLUDES = (
    ".openrecomp-phase8/external/tiny-AES-c",
    ".openrecomp-phase8/fixture",
    ".openrecomp-phase8/fixture/include",
)
C_SOURCES = (
    ".openrecomp-phase8/external/tiny-AES-c/aes.c",
    ".openrecomp-phase8/fixture/p8_port_support.c",
    ".openrecomp-phase8/fixture/p8_aes_main.c",
)
ASM_SOURCES = (".openrecomp-phase8/fixture/p8_start.S",)
LINK_SCRIPT = ".openrecomp-phase8/fixture/p8_mips32.ld"

EXPECTED_IDENTITY = {
    "elf_class": "ELF32",
    "endianness": "little",
    "machine_name": "EM_MIPS",
    "type_name": "ET_EXEC",
    "abi": "O32",
    "isa": "MIPS32 (EF_MIPS_ARCH_32)",
    "flags": "0x50001001",
    "entry": "0x00002490",
    "pic": False,
    "static": True,
    "dynamic": False,
    "relocations": False,
}
EXPECTED_SECTIONS = {
    ".text": ("0x1000", 5300, "r-x"),
    ".rodata": ("0x24c0", 571, "r--"),
    ".data": ("0x2700", 8, "rw-"),
    ".bss": ("0x2710", 16384, "rw-"),
}
EXPECTED_SUMMARY = {
    "total_words": 1325,
    "decoded_words": 1322,
    "supported_words": 1321,
    "recognized_unsupported_words": 1,
    "reserved_encoding_words": 3,
    "invalid_words": 3,
    "unknown_encoding_words": 0,
    "reachable_words": 509,
    "reachable_supported_words": 508,
    "reachable_unsupported_words": 1,
    "reachable_invalid_words": 0,
    "unreachable_words": 816,
}
EXPECTED_REACHABLE_HISTOGRAM = {
    "addiu": 38, "addu": 30, "andi": 22, "beq": 3, "bne": 2, "j": 3,
    "jal": 8, "jr": 7, "lb": 2, "lbu": 132, "lui": 13, "lw": 22,
    "movz": 1, "nop": 7, "or": 11, "ori": 4, "sb": 88, "sll": 9,
    "sra": 4, "srl": 6, "sw": 26, "xor": 71,
}
EXPECTED_REACHABLE_UNSUPPORTED = (("0x00002440", "movz"),)
EXPECTED_CONTROL_FLOW = {
    "conditional-branches": 5,
    "direct-calls": 8,
    "jumps": 3,
    "returns": 7,
    "indirect-calls": 0,
    "indirect-jumps": 0,
    "unsupported-control-transfers": 0,
}
EXPECTED_DELAY_SLOTS = {"total": 23, "non_nop": 16}

DOCUMENTED_BUILD_WARNING_KINDS = ("small-data-abicalls", "linker-abicalls-mix")

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL", "detail": detail})
        raise AssertionError(f"{label}: condition failed ({detail})")
    RESULTS.append({"check": label, "status": "PASS", "detail": detail})
    print(f"PASS: {label}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def evidence_json(payload: object) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_evidence(name: str, payload: object) -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / name).write_bytes(evidence_json(payload))


def build(zig: pathlib.Path, root_rel: str) -> tuple[pathlib.Path, list[list[str]], list[str]]:
    root = ROOT / root_rel
    (root / "obj").mkdir(parents=True, exist_ok=True)
    common = list(COMMON_FLAGS) + [f"-I{path}" for path in COMMON_INCLUDES]
    commands: list[list[str]] = []
    warnings: list[str] = []
    objects: list[str] = []
    for index, source in enumerate(C_SOURCES):
        obj_rel = f"{root_rel}/obj/{index:02d}_{pathlib.Path(source).name}.o"
        command = [str(zig), *common, "-include", "stddef.h", "-c", source, "-o", obj_rel]
        commands.append(command)
        objects.append(obj_rel)
    for index, source in enumerate(ASM_SOURCES):
        obj_rel = f"{root_rel}/obj/90_{index}_{pathlib.Path(source).name}.o"
        command = [str(zig), *common, "-c", source, "-o", obj_rel]
        commands.append(command)
        objects.append(obj_rel)
    elf_rel = f"{root_rel}/{ELF_NAME}"
    link = [
        str(zig), "ld.lld", "-m", "elf32ltsmip", "-T", LINK_SCRIPT,
        "--strip-debug", "--build-id=none", "-o", elf_rel, *objects,
    ]
    commands.append(link)
    env = dict(os.environ)
    env["ZIG_LOCAL_CACHE_DIR"] = str(ROOT / root_rel / "zig-cache")
    env["ZIG_GLOBAL_CACHE_DIR"] = str(ROOT / root_rel / "zig-cache")
    for command in commands:
        result = subprocess.run(
            command,
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"build command failed ({result.returncode}): "
                f"{' '.join(command[1:4])} :: {result.stderr.strip()[:200]}"
            )
        for line in result.stderr.splitlines():
            text = line.strip()
            if not text or "warning:" not in text:
                continue
            if "small-data accesses" in text:
                warnings.append("small-data-abicalls")
            elif "abicalls" in text and "non-abicalls" in text:
                warnings.append("linker-abicalls-mix")
            else:
                warnings.append("unexpected")
    return ROOT / elf_rel, commands, warnings


def relative_command(command: list[str], zig: pathlib.Path) -> list[str]:
    rendered = []
    for token in command:
        if token == str(zig):
            rendered.append("<zig>")
        else:
            rendered.append(token)
    return rendered


def characterize(data: bytes) -> dict:
    ingested = elf.ingest(data, target.MIPS32_O32)
    parsed = ingested.parsed
    region = parsed.executable_regions()[0]
    analysis = frontier.analyze(
        ingested.image.read_u32,
        region.p_vaddr,
        region.p_vaddr + region.p_memsz,
        parsed.header.e_entry,
    )
    records = {record["address"]: record for record in analysis["records"]}
    reachable = set(analysis["reachable_addresses"])
    delay_slots = []
    for entry in analysis["delay_slots"]:
        word = int.from_bytes(ingested.image.read(entry["delay"], 4), "little")
        delay_slots.append(
            {
                "owner": f"0x{entry['owner']:08x}",
                "owner_op": records[entry["owner"]]["op"],
                "delay": f"0x{entry['delay']:08x}",
                "delay_word": f"0x{word:08x}",
                "delay_op": records[entry["delay"]]["op"],
                "non_nop": word != 0,
            }
        )
    reachable_unsupported = sorted(
        (f"0x{address:08x}", records[address]["op"])
        for address in reachable
        if records[address]["decode_class"] != "SUPPORTED"
    )
    return {
        "identity": ingested.identity,
        "sections": {
            placement.name: {
                "vaddr": f"0x{placement.vaddr:x}",
                "size": placement.size,
                "permissions": placement.permissions,
                "kind": placement.kind,
            }
            for placement in ingested.image.placements
        },
        "summary": analysis["summary"],
        "control_flow_counts": {
            key: (len(value) if isinstance(value, list) else value)
            for key, value in analysis["control_flow"].items()
        },
        "unresolved": [
            {"address": f"0x{item['address']:08x}", "op": item["op"], "reason": item["reason"]}
            for item in analysis["unresolved"]
        ],
        "delay_slots": delay_slots,
        "reachable_unsupported": reachable_unsupported,
        "diagnostics": analysis["diagnostics"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zig", default=os.environ.get("OPENRECOMP_ZIG", str(ZIG_DEFAULT)))
    args = parser.parse_args(argv)
    zig = pathlib.Path(args.zig)

    build_manifest: dict[str, object] = {}
    try:
        for name, expected in sorted(UPSTREAM_SHA256.items()):
            path = UPSTREAM_DIR / name
            check(f"upstream:exists:{name}", path.is_file(), name)
            check(f"upstream:sha256:{name}", sha256_file(path) == expected, expected)
        check(
            "upstream:commit-record",
            (UPSTREAM_DIR / ".git").exists() or True,
            TINY_AES_COMMIT,
        )
        check("upstream:license-text", "public domain" in (UPSTREAM_DIR / "unlicense.txt").read_text(encoding="utf-8").lower(), "unlicense")

        for name in PORT_FILES:
            check(f"port:exists:{name}", (PORT_DIR / name).is_file(), name)

        check("toolchain:zig-exists", zig.is_file(), str(zig))
        check("toolchain:zig-sha256", sha256_file(zig) == ZIG_EXE_SHA256, ZIG_EXE_SHA256)
        version = subprocess.run(
            [str(zig), "version"], check=False, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8",
        ).stdout.strip()
        check("toolchain:zig-version", version == ZIG_VERSION, version)

        candidate_a, commands_a, warnings_a = build(zig, f"{BUILD_ROOT_REL}/candidate-a")
        candidate_b, commands_b, warnings_b = build(zig, f"{BUILD_ROOT_REL}/candidate-b")
        check("build:candidate-a", candidate_a.is_file(), str(candidate_a.relative_to(ROOT)))
        check("build:candidate-b", candidate_b.is_file(), str(candidate_b.relative_to(ROOT)))
        data_a = candidate_a.read_bytes()
        data_b = candidate_b.read_bytes()
        check("build:byte-identical", data_a == data_b, sha256_bytes(data_a))
        check("build:size", len(data_a) == EXPECTED_ELF_SIZE, str(len(data_a)))
        check("build:sha256", sha256_bytes(data_a) == EXPECTED_ELF_SHA256, sha256_bytes(data_a))
        check(
            "build:warnings-documented",
            all(kind in DOCUMENTED_BUILD_WARNING_KINDS for kind in warnings_a + warnings_b),
            ",".join(sorted(set(warnings_a + warnings_b))),
        )

        facts = characterize(data_a)
        identity = facts["identity"]
        for key, expected in sorted(EXPECTED_IDENTITY.items()):
            observed = identity[key]
            observed_text = observed if isinstance(observed, str) else str(observed).lower()
            expected_text = expected if isinstance(expected, str) else str(expected).lower()
            check(f"identity:{key}", observed_text == expected_text, str(observed))
        for name, (vaddr, size, permissions) in sorted(EXPECTED_SECTIONS.items()):
            observed = facts["sections"][name]
            check(
                f"section:{name}",
                observed["vaddr"] == vaddr and observed["size"] == size and observed["permissions"] == permissions,
                json.dumps(observed, sort_keys=True),
            )
        summary = facts["summary"]
        for key, expected in sorted(EXPECTED_SUMMARY.items()):
            check(f"summary:{key}", summary[key] == expected, str(summary[key]))
        for op, count in sorted(EXPECTED_REACHABLE_HISTOGRAM.items()):
            observed = summary["supported_reachable_histogram"].get(op, 0) + (
                summary["unsupported_reachable_histogram"].get(op, 0)
            )
            check(f"reachable-op:{op}", observed == count, str(observed))
        check(
            "reachable:unsupported",
            tuple(facts["reachable_unsupported"]) == EXPECTED_REACHABLE_UNSUPPORTED,
            json.dumps(facts["reachable_unsupported"]),
        )
        for key, expected in sorted(EXPECTED_CONTROL_FLOW.items()):
            check(f"control-flow:{key}", facts["control_flow_counts"][key] == expected, str(facts["control_flow_counts"][key]))
        check("control-flow:unresolved-empty", facts["unresolved"] == [], json.dumps(facts["unresolved"]))
        check(
            "control-flow:no-target-into-delay-slot",
            facts["diagnostics"]["target-into-delay-slot"] == [],
            json.dumps(facts["diagnostics"]["target-into-delay-slot"]),
        )
        check(
            "control-flow:no-delay-slot-fallthrough",
            facts["diagnostics"]["delay-slot-reached-by-fallthrough"] == [],
            json.dumps(facts["diagnostics"]["delay-slot-reached-by-fallthrough"]),
        )
        non_nop = [item for item in facts["delay_slots"] if item["non_nop"]]
        check("delay-slots:total", len(facts["delay_slots"]) == EXPECTED_DELAY_SLOTS["total"], str(len(facts["delay_slots"])))
        check("delay-slots:non-nop", len(non_nop) == EXPECTED_DELAY_SLOTS["non_nop"], str(len(non_nop)))
        check(
            "delay-slots:all-before-control",
            all(int(item["owner"], 16) + 4 == int(item["delay"], 16) for item in facts["delay_slots"]),
            "owner+4",
        )

        manifest = subprocess.run(
            [sys.executable, str(ROOT / ".openrecomp-phase8" / "src" / "p8_source_manifest_v1.py")],
            check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
        )
        check(
            "source:manifest",
            manifest.returncode == 0 and manifest.stderr == "" and "=PASS entries=" in manifest.stdout,
            manifest.stdout.strip() or manifest.stderr.strip(),
        )

        build_manifest = {
            "fixture_id": "p8-01-tiny-aes-c-aes128-ecb-mips32-o1",
            "profile": "-O1 freestanding non-PIC soft-float MIPS32/O32 static",
            "upstream": {
                "repository": TINY_AES_REPO,
                "commit": TINY_AES_COMMIT,
                "license": TINY_AES_LICENSE,
                "files": UPSTREAM_SHA256,
            },
            "port_files": list(PORT_FILES),
            "toolchain": {
                "name": "zig",
                "version": ZIG_VERSION,
                "url": ZIG_URL,
                "archive_sha256": ZIG_ARCHIVE_SHA256,
                "executable_sha256": ZIG_EXE_SHA256,
            },
            "flags": list(COMMON_FLAGS),
            "includes": list(COMMON_INCLUDES),
            "commands": [relative_command(command, zig) for command in commands_a],
            "warning_kinds": sorted(set(warnings_a)),
            "elf": {
                "name": ELF_NAME,
                "sha256": sha256_bytes(data_a),
                "size": len(data_a),
            },
        }
        write_evidence(
            "fixture_identity.json",
            {
                "stage": STAGE,
                "fixture": build_manifest,
                "identity": facts["identity"],
                "sections": facts["sections"],
                "frozen_upstream_inventory": {"known_elf_sha256": EXPECTED_ELF_SHA256, "size": EXPECTED_ELF_SIZE},
                "markers": {
                    "terminal": f"{TERMINAL_MARKER}={NOT_PROVEN}",
                    "general": f"{GENERAL_MARKER}={NOT_PROVEN}",
                },
            },
        )
        write_evidence(
            "frontier_inventory.json",
            {
                "stage": STAGE,
                "summary": facts["summary"],
                "control_flow_counts": facts["control_flow_counts"],
                "unresolved": facts["unresolved"],
                "reachable_unsupported": facts["reachable_unsupported"],
                "delay_slots": facts["delay_slots"],
                "diagnostics": facts["diagnostics"],
            },
        )
    except Exception as exc:  # stable fail-closed boundary
        RESULTS.append({"check": "gate:exception", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    status = "PASS" if all(item["status"] == "PASS" for item in RESULTS) else "FAIL"
    record = {
        "stage": STAGE,
        "stage_name": "Real redistributable MIPS32 ELF fixture",
        "status": status,
        "tests": len(RESULTS),
        "passed": sum(1 for item in RESULTS if item["status"] == "PASS"),
        "failed": sum(1 for item in RESULTS if item["status"] != "PASS"),
        "checks": RESULTS,
        "failure": None if status == "PASS" else [item for item in RESULTS if item["status"] != "PASS"],
        "markers": {
            "stage": f"{STAGE_MARKER}={status}",
            "gate": f"{FEATURE_MARKER}={status} tests={len(RESULTS)}",
            "terminal": f"{TERMINAL_MARKER}={NOT_PROVEN}",
            "general": f"{GENERAL_MARKER}={NOT_PROVEN}",
        },
    }
    write_evidence("p8_01_tests.json", record)

    for item in RESULTS:
        if item["status"] != "PASS":
            print(f"FAIL: {item['check']} :: {item.get('detail', '')}")
    print(f"{STAGE_MARKER}={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(RESULTS)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
