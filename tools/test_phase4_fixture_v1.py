#!/usr/bin/env python3
"""OpenRecomp Phase-4 interactive fixture gate (P4-07).

Builds and characterises the original, legally clean interactive fixture in
``.openrecomp-phase4/fixture/``:

* provenance: original work under the repository Apache-2.0 license, with no
  third-party, console, commercial or generated-asset material;
* reproducible build: the recorded ``zig cc`` 0.13.0 toolchain and bounded
  flags produce a byte-identical ECC MIPS32 ELF from two isolated build
  roots;
* ingestion: the frozen Phase-3 ELF32 ingestion layer parses the fixture
  (identity, sections, load map) without modification;
* decode frontier: the frozen Phase-3 decode/reachability layers inventory the
  complete instruction frontier; every reachable word must be either adapter
  supported or in the bounded P3-04 semantic class, with no unresolved
  control flow, so the fixture stays inside the proven translation frontier;
* feature inventory: code/rodata/data/bss layout, recursion, zero-fill
  storage, bounded static arena, runtime-service windows and the declared
  deterministic input plan;
* a clearly labelled preliminary Python mirror of the fixture algorithm
  records the policy-independent transcript fields (the tick fields remain
  policy-dependent and are confirmed by the independent reference in P4-09).

It emits::

    OPENRECOMP_P4_07=PASS
    OPENRECOMP_PHASE4_FIXTURE_V1=PASS tests=<count>
    OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase4_fixture_v1.py
    python tools/test_phase4_fixture_v1.py --evidence-dir .openrecomp-phase4/evidence/P4-07
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
for candidate in (str(ROOT), str(ROOT / ".openrecomp-phase4" / "src"),
                  str(ROOT / ".openrecomp-phase3" / "src")):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from p3_code_frontier_v1 import analyze  # noqa: E402
from p3_elf_image_v1 import ingest  # noqa: E402
from p3_target_mips32_v1 import MIPS32_O32  # noqa: E402

STAGE = "P4-07"
STAGE_MARKER = "OPENRECOMP_P4_07"
FEATURE_MARKER = "OPENRECOMP_PHASE4_FIXTURE_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY"

SOURCE_SUMS = "SOURCE_SHA256SUMS.txt"
SOURCE_SUMS_SHA256 = "76f77bbc97780afe9c2b41a0cb89b5323ab22450c4b2a368dd03fb4d7bbe1095"
SOURCE_SUMS_ENTRIES = 134
P3_SUMS = ".openrecomp-phase3/SOURCE_SHA256SUMS.txt"
P3_SUMS_SHA256 = "a7d0953c0f02276ad233db50e326d9e71a3136542648bb04a95de9d3e05e2488"
P3_SUMS_ENTRIES = 24
P4_SUMS = ".openrecomp-phase4/SOURCE_SHA256SUMS.txt"

ZIG = ROOT / ".openrecomp-phase3" / "tools" / "zig" / "zig.exe"
FIXTURE_DIR = ROOT / ".openrecomp-phase4" / "fixture"
BUILD_ROOT = ROOT / ".openrecomp-phase4" / "build" / "P4-07"
ELF_SHA256 = "acb4f4e57a7f996e87989e99d702d802259b752aabb2476f574665ef061969bc"
ELF_SIZE = 9884
TOOLCHAIN_VERSION = "0.13.0"
EXPECTED_FIB10 = 55
EXPECTED_PRIMES_SUM = 381
EXPECTED_CHECKSUM = "0xd43e5ba6"
# p4_start.S is not pinned to LF by the repository .gitattributes (whose root
# copy is hash-frozen), so its integrity is verified over LF-normalized text
# rather than raw bytes.
START_STUB = FIXTURE_DIR / "p4_start.S"
START_STUB_SHA256_LF = "0d17292f0ad810a26f1153863c6f2bcd86f2c81ef31ff9ccb39ebbe761af1409"

COMMON_FLAGS = (
    "--target=mipsel-linux-musl", "-march=mips32", "-mabi=32", "-msoft-float",
    "-mno-abicalls", "-G0", "-ffreestanding", "-fno-builtin",
    "-fno-stack-protector", "-fomit-frame-pointer", "-fno-pic", "-O1",
    "-nostdlib", "-static", "-I.openrecomp-phase4/fixture", "-include", "stddef.h",
)
SOURCES = (
    ("00_util_v1.o", "p4_fixture_util.c"),
    ("01_main_v1.o", "p4_fixture_main.c"),
    ("90_start_v1.o", "p4_start.S"),
)
LINKER_SCRIPT = ".openrecomp-phase4/fixture/p4_fixture.ld"
INPUT_PLAN = FIXTURE_DIR / "input_plan.json"
ALLOWED_UNSUPPORTED = frozenset({"movz", "movn", "mul", "divu", "teq", "swl", "swr", "jalr"})
FORBIDDEN_PROVENANCE_TOKENS = (
    "nintendo", "sony", "playstation", "sega", "atari", "gameboy", "psx",
    "ps2", "n64", "coremark", "eembc", "rom image", "bios", ".iso",
)
BINARY_MAGICS = (b"NES\x1a", b"FDS\x1a", b"UNIF")

RESULTS: list[dict[str, str]] = []
FINDINGS: dict[str, Any] = {}
ARTIFACTS: dict[str, bytes] = {}


def check(label: str, condition: bool) -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        print(f"FAIL: {label}", flush=True)
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}", flush=True)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def banner(name: str) -> None:
    print(f"\n--- {name} ---", flush=True)


def parse_manifest(path: pathlib.Path) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for line in read_text(path).strip().splitlines():
        if not line.strip():
            continue
        match = re.match(r"^([0-9a-f]{64}) \*(.+)$", line)
        if match is None:
            raise AssertionError(f"malformed manifest line: {line[:80]}")
        entries.append((match.group(1), match.group(2)))
    return entries


def run(command: list[str], *, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


# ---------------------------------------------------------------------------
# Source integrity
# ---------------------------------------------------------------------------
def audit_source_integrity() -> None:
    check("source:root-manifest", sha256_file(ROOT / SOURCE_SUMS) == SOURCE_SUMS_SHA256)
    root_entries = parse_manifest(ROOT / SOURCE_SUMS)
    check("source:root-manifest-entries", len(root_entries) == SOURCE_SUMS_ENTRIES)
    check("source:root-manifest-verified",
          all((ROOT / rel).is_file() and sha256_file(ROOT / rel) == digest
              for digest, rel in root_entries))
    check("source:phase3-manifest", sha256_file(ROOT / P3_SUMS) == P3_SUMS_SHA256)
    phase3_entries = parse_manifest(ROOT / P3_SUMS)
    check("source:phase3-manifest-entries", len(phase3_entries) == P3_SUMS_ENTRIES)
    phase4_entries = parse_manifest(ROOT / P4_SUMS)
    bad = [rel for digest, rel in phase4_entries
           if not (ROOT / rel).is_file() or sha256_file(ROOT / rel) != digest]
    check("source:phase4-manifest-verified", phase4_entries and not bad)
    FINDINGS["source_integrity"] = {
        "root_entries": len(root_entries),
        "phase3_entries": len(phase3_entries),
        "phase4_entries": len(phase4_entries),
    }


# ---------------------------------------------------------------------------
# Provenance and license
# ---------------------------------------------------------------------------
def audit_provenance() -> None:
    fixture_files = sorted(path for path in FIXTURE_DIR.iterdir() if path.is_file())
    check("provenance:files-present",
          {path.name for path in fixture_files}
          >= {"p4_fixture.h", "p4_fixture_util.c", "p4_fixture_main.c",
              "p4_start.S", "p4_fixture.ld", "README.md", "input_plan.json"})
    origins = 0
    problems: list[str] = []
    for path in fixture_files:
        data = path.read_bytes()
        for magic in BINARY_MAGICS:
            if data.startswith(magic):
                problems.append(f"{path.name}:forbidden-magic")
        text = data.decode("utf-8", errors="replace")
        lowered = text.lower()
        for token in FORBIDDEN_PROVENANCE_TOKENS:
            if token in lowered:
                problems.append(f"{path.name}:{token}")
        if path.suffix in (".c", ".h", ".S", ".ld") and "OpenRecomp Phase 4" in text:
            origins += 1
        if path.name == "README.md":
            check("provenance:license-statement",
                  "Apache License 2.0" in text and "Original work" in text)
            check("provenance:no-third-party",
                  "Original work authored for OpenRecomp" in text)
    check("provenance:no-forbidden-tokens", not problems)
    check("provenance:original-headers", origins >= 5)
    start_stub = START_STUB.read_bytes().replace(b"\r\n", b"\n")
    check("provenance:start-stub",
          sha256_bytes(start_stub) == START_STUB_SHA256_LF)
    check("provenance:repo-license",
          "Apache License" in read_text(ROOT / "LICENSE")[:200])
    FINDINGS["provenance"] = {
        "files": [path.name for path in fixture_files],
        "problems": problems,
        "license": "Apache-2.0 (repository LICENSE)",
        "authorship": "original OpenRecomp work",
    }


# ---------------------------------------------------------------------------
# Reproducible build
# ---------------------------------------------------------------------------
def build_fixture(root_name: str) -> dict[str, Any]:
    base = BUILD_ROOT / root_name
    obj_dir = base / "obj"
    obj_dir.mkdir(parents=True, exist_ok=True)
    commands: list[list[str]] = []
    for object_name, source_name in SOURCES:
        flags = list(COMMON_FLAGS)
        if source_name.endswith(".S"):
            include_index = flags.index("-include")
            del flags[include_index:include_index + 2]
        command = [str(ZIG), "cc", *flags, "-c",
                   f".openrecomp-phase4/fixture/{source_name}", "-o",
                   f".openrecomp-phase4/build/P4-07/{root_name}/obj/{object_name}"]
        commands.append(command)
        completed = run(command)
        if completed.returncode != 0:
            raise AssertionError(f"compile failed: {completed.stderr.strip()[:400]}")
    elf_path = base / "p4_fixture_mips32_O1.elf"
    link_command = [str(ZIG), "ld.lld", "-m", "elf32ltsmip", "-T", LINKER_SCRIPT,
                    "--strip-debug", "--build-id=none", "-o",
                    elf_path.relative_to(ROOT).as_posix(),
                    *[f".openrecomp-phase4/build/P4-07/{root_name}/obj/{name}"
                      for name, _ in SOURCES]]
    commands.append(link_command)
    completed = run(link_command)
    if completed.returncode != 0:
        raise AssertionError(f"link failed: {completed.stderr.strip()[:400]}")
    data = elf_path.read_bytes()
    return {
        "root": root_name,
        "elf_sha256": sha256_bytes(data),
        "elf_size": len(data),
        "commands": commands,
        "data": data,
    }


def audit_build() -> bytes:
    check("toolchain:zig-present", ZIG.is_file())
    version = run([str(ZIG), "version"])
    check("toolchain:version", version.returncode == 0
          and version.stdout.strip() == TOOLCHAIN_VERSION)
    first = build_fixture("candidate-a")
    second = build_fixture("candidate-b")
    check("build:byte-identical", first["elf_sha256"] == second["elf_sha256"])
    check("build:minimal-size", 0 < first["elf_size"] < 65536)
    if ELF_SHA256 != "PINNED-BY-EVIDENCE":
        check("build:elf-sha256-pinned", first["elf_sha256"] == ELF_SHA256)
        check("build:elf-size-pinned", first["elf_size"] == ELF_SIZE)
    ARTIFACTS["build.json"] = (
        json.dumps({
            "stage": STAGE,
            "toolchain": {"identity": "zig cc", "version": TOOLCHAIN_VERSION},
            "flags": list(COMMON_FLAGS),
            "linker_script": LINKER_SCRIPT,
            "candidate_a": {k: first[k] for k in ("elf_sha256", "elf_size", "commands")},
            "candidate_b": {k: second[k] for k in ("elf_sha256", "elf_size", "commands")},
            "byte_identical": first["elf_sha256"] == second["elf_sha256"],
        }, indent=2, sort_keys=True) + "\n").encode("utf-8")
    FINDINGS["build"] = {
        "elf_sha256": first["elf_sha256"],
        "elf_size": first["elf_size"],
        "byte_identical": first["elf_sha256"] == second["elf_sha256"],
    }
    return first["data"]


# ---------------------------------------------------------------------------
# Ingestion and decode frontier
# ---------------------------------------------------------------------------
def audit_ingestion(data: bytes) -> dict[str, Any]:
    ingested = ingest(data, MIPS32_O32)
    parsed = ingested.parsed
    section_names = {section.name for section in parsed.sections}
    check("ingest:identity-fields",
          parsed.header.e_machine == 8 and parsed.header.e_type == 2
          and parsed.identification.elf_class == 1
          and parsed.identification.data_encoding == 1)
    check("ingest:required-sections",
          {".text", ".rodata", ".data", ".bss"} <= section_names)
    check("ingest:entry-in-text",
          any(section.name == ".text"
              and section.sh_addr <= parsed.header.e_entry < section.sh_addr + section.sh_size
              for section in parsed.sections))
    check("ingest:no-dynamic",
          all(header.p_type != 2 for header in parsed.program_headers))
    text = next(section for section in parsed.sections if section.name == ".text")
    bss = next(section for section in parsed.sections if section.name == ".bss")
    data_section = next(section for section in parsed.sections if section.name == ".data")
    check("ingest:bss-zero-fill", bss.sh_size > 0 and bss.sh_type == 8)
    check("ingest:data-initialised", data_section.sh_size > 0)
    identity = ingested.identity
    check("ingest:identity-flags",
          identity["machine"] == 8 and identity["elf_class"] == "ELF32"
          and identity["static"] is True and identity["dynamic"] is False)
    check("ingest:image-identity",
          re.fullmatch(r"[0-9a-f]{64}", ingested.image.executable_sha256()) is not None)

    frontier = analyze(ingested.image.read_u32, text.sh_addr,
                       text.sh_addr + text.sh_size, parsed.header.e_entry)
    summary = frontier["summary"]
    check("frontier:unknown-encodings", summary["unknown_encoding_words"] == 0)
    check("frontier:reachable-invalid", summary["reachable_invalid_words"] == 0)
    check("frontier:reachable-words", summary["reachable_words"] > 200)
    unsupported = set(summary["unsupported_reachable_histogram"])
    check("frontier:reachable-ops-in-bounded-class",
          unsupported <= ALLOWED_UNSUPPORTED)
    check("frontier:no-unresolved-flow", frontier["unresolved"] == [])
    counts = summary["control_flow_site_counts"]
    check("frontier:no-indirect-jumps", counts.get("indirect-jumps", 0) == 0)
    check("frontier:no-indirect-calls", counts.get("indirect-calls", 0) == 0)
    check("frontier:no-unsupported-control",
          counts.get("unsupported-control-transfers", 0) == 0)
    check("frontier:has-direct-calls", counts.get("direct-calls", 0) > 0)
    check("frontier:has-branches", counts.get("conditional-branches", 0) > 0)
    check("frontier:has-returns", counts.get("returns", 0) > 0)

    payload = {
        "stage": STAGE,
        "identity": ingested.identity,
        "sections": [
            {"name": section.name, "addr": section.sh_addr, "size": section.sh_size,
             "type": section.sh_type, "flags": section.sh_flags}
            for section in parsed.sections
        ],
        "entry": parsed.header.e_entry,
        "frontier_summary": summary,
        "control_flow_site_counts": counts,
        "unsupported_reachable_histogram": summary["unsupported_reachable_histogram"],
    }
    ARTIFACTS["elf_characterisation.json"] = (
        json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    FINDINGS["ingestion"] = {
        "entry": hex(parsed.header.e_entry),
        "text_start": hex(text.sh_addr),
        "text_size": text.sh_size,
        "bss_size": bss.sh_size,
        "image_executable_sha256": ingested.image.executable_sha256(),
        "frontier": summary,
    }
    return {"ingested": ingested, "frontier": frontier, "text": text}


# ---------------------------------------------------------------------------
# Feature inventory and preliminary expected transcript
# ---------------------------------------------------------------------------
def audit_features(characterisation: dict[str, Any]) -> None:
    ingested = characterisation["ingested"]
    summary = characterisation["frontier"]["summary"]
    check("features:reachable-words", summary["reachable_words"] > 200)
    check("features:supported-words", summary["supported_words"] > 200)
    check("features:function-scale", summary["reachable_words"] < 4096)
    image_document = ingested.image.describe(
        ingested.identity.get("source_sha256", ""),
        ingested.identity.get("source_size", 0),
        ingested.parsed.header.e_entry)
    check("features:region-model", bool(image_document))

    plan = json.loads(read_text(INPUT_PLAN))
    raw = bytes.fromhex(plan["console_input_hex"])
    check("plan:terminator", raw and raw[-1] == 0xFF)
    check("plan:has-input-bytes", len(raw) > 1)
    check("plan:tick-policy",
          "one virtual tick per retired guest instruction" in plan["tick_policy"])

    values = []
    for byte in raw[:-1]:
        values.append(byte)
    primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53]
    fib = [0, 1]
    while len(fib) <= 10:
        fib.append(fib[-1] + fib[-2])

    def mix(state: int, value: int) -> int:
        current = state
        for index in range(4):
            current ^= (value >> (index * 8)) & 0xFF
            current = (current * 16777619) & 0xFFFFFFFF
        return current

    def transform(value: int, selector: int) -> int:
        index = selector & 3
        if index == 0:
            return (value + 1) & 0xFFFFFFFF
        if index == 1:
            return (value ^ (value >> 1)) & 0xFFFFFFFF
        if index == 2:
            return (value * 3 + 3) & 0xFFFFFFFF
        return (value - 4) & 0xFFFFFFFF

    input_count = 0
    input_xor = 0
    checksum = 0x811C9DC5
    for byte in values:
        input_count += 1
        input_xor ^= byte
        checksum = mix(checksum, transform(byte, input_count & 3))

    bss_sum = 0
    for index in range(256):
        scratch = (0x5A + index * 7) & 0xFF
        bss_sum = ((bss_sum << 1) ^ scratch) & 0xFFFFFFFF
    heap_sum = 0
    for index in range(64):
        cell = (0x33 + index * 5) & 0xFF
        heap_sum = ((heap_sum << 1) ^ cell) & 0xFFFFFFFF
    fib_value = fib[10]
    primes_sum = sum(primes)
    prime_count = len(primes)
    for value in (fib_value, primes_sum, prime_count, bss_sum, heap_sum):
        checksum = mix(checksum, value)
    check("model:checksum-32bit", 0 <= checksum <= 0xFFFFFFFF)
    check("model:known-fib10", fib_value == EXPECTED_FIB10)
    check("model:known-primes-sum", primes_sum == EXPECTED_PRIMES_SUM)
    check("model:known-checksum", f"0x{checksum:08x}" == EXPECTED_CHECKSUM)

    transcript_lines = [
        "P4FIXTURE v1",
        f"input_bytes={input_count}",
        f"input_xor={input_xor}",
        f"fib10={fib_value}",
        f"prime_count={prime_count}",
        f"primes_sum={primes_sum}",
        f"bss_sum={bss_sum}",
        f"heap_sum={heap_sum}",
        f"checksum=0x{checksum:08x}",
        "ticks_start=<runtime tick policy>",
        "ticks_end=<runtime tick policy>",
    ]
    payload = {
        "stage": STAGE,
        "kind": "preliminary-model-derived",
        "note": ("Policy-independent transcript fields computed by a Python "
                 "mirror of the fixture algorithm. The tick fields are runtime "
                 "policy dependent and are confirmed by the independent "
                 "reference in P4-09, not by this mirror."),
        "input_hex": plan["console_input_hex"],
        "transcript_lines": transcript_lines,
        "checksum": f"0x{checksum:08x}",
    }
    ARTIFACTS["expected_transcript.json"] = (
        json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    FINDINGS["features"] = {
        "input_bytes": input_count,
        "checksum": f"0x{checksum:08x}",
        "fib10": fib_value,
        "primes_sum": primes_sum,
        "bss_sum": bss_sum,
        "heap_sum": heap_sum,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="P4-07 fixture gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase4/evidence/P4-07")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, ARTIFACTS
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    ARTIFACTS = {}

    print("=== P4-07 Interactive Fixture Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("source_integrity")
        audit_source_integrity()
        banner("provenance")
        audit_provenance()
        banner("build")
        data = audit_build()
        banner("ingestion")
        characterisation = audit_ingestion(data)
        banner("features")
        audit_features(characterisation)
    except Exception as exc:  # noqa: BLE001 - fail closed without traceback
        failure = f"{type(exc).__name__}: {exc}"

    passed = sum(1 for item in RESULTS if item["status"] == "PASS")
    failed = sum(1 for item in RESULTS if item["status"] == "FAIL") + (1 if failure else 0)
    status = "FAIL" if failure else "PASS"

    result = {
        "stage": STAGE,
        "stage_name": FEATURE_MARKER,
        "status": status,
        "tests": passed,
        "passed": passed,
        "failed": failed,
        "markers": {
            "stage": f"{STAGE_MARKER}={status}",
            "gate": f"{FEATURE_MARKER}={status} tests={passed}",
            "terminal": f"{TERMINAL_MARKER}=NOT_PROVEN",
            "compatibility": f"{COMPAT_MARKER}=NOT_PROVEN",
        },
        "checks": sorted(RESULTS, key=lambda item: item["check"]),
        "findings": FINDINGS,
        "failure": failure,
    }
    for name, payload in ARTIFACTS.items():
        (EVIDENCE_DIR / name).write_bytes(payload)
    (EVIDENCE_DIR / "p4_07_tests.json").write_bytes(
        (json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))

    print("\n=== RESULT ===")
    if status == "PASS":
        print(f"{STAGE_MARKER}=PASS")
        print(f"{FEATURE_MARKER}=PASS tests={passed}")
        print(f"{TERMINAL_MARKER}=NOT_PROVEN")
        print(f"{COMPAT_MARKER}=NOT_PROVEN")
        return 0
    print(f"{STAGE_MARKER}=FAIL ({failure})")
    print(f"{FEATURE_MARKER}=FAIL")
    print(f"{TERMINAL_MARKER}=NOT_PROVEN")
    print(f"{COMPAT_MARKER}=NOT_PROVEN")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
