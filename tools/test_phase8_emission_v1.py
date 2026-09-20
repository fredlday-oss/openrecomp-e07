#!/usr/bin/env python3
"""OpenRecomp Phase-8 host-source emission gate (P8-06).

P8-06 feeds the bounded real MIPS32 program through the existing
architecture-neutral host emitter and produces the complete deterministic
build input set for the native stages:

* `program.c` (existing host emitter + closed P8 MIPS32 rule table);
* `p8_image_v1.c` (generated guest image contract unit);
* `p8_runtime_support.c` (bounded runtime support, composed);
* `p8_driver.c` (observable driver, composed).

The gate proves stable filenames, recorded content hashes, byte-identical
output for unchanged input, continuity with the P8-04 emission fingerprint,
and that no original MIPS32 machine code is executed at runtime (the guest
image is inert data; all semantics are generated C).

On success it emits::

    OPENRECOMP_P8_06=PASS
    OPENRECOMP_PHASE8_HOST_EMISSION_V1=PASS tests=<count>
    OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase8_emission_v1.py
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".openrecomp-phase3" / "src"))
sys.path.insert(0, str(ROOT / ".openrecomp-phase8" / "src"))

import adapters.mips32 as mips32_adapter  # noqa: E402
import p3_code_frontier_v1 as frontier  # noqa: E402
import p3_elf_image_v1 as elf  # noqa: E402
import p3_target_mips32_v1 as target  # noqa: E402
import p8_emission_v1 as emission  # noqa: E402
import p8_memory_contract_v1 as contract_v1  # noqa: E402
import p8_structure_v1 as structure_bridge  # noqa: E402
from openrecomp.program_model import ProgramSource  # noqa: E402

EVIDENCE_DIR = ROOT / ".openrecomp-phase8" / "evidence" / "P8-06"
EMISSION_DIR = ROOT / ".openrecomp-phase8" / "build" / "P8-06" / "emission"

STAGE = "P8-06"
STAGE_MARKER = "OPENRECOMP_P8_06"
FEATURE_MARKER = "OPENRECOMP_PHASE8_HOST_EMISSION_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"

FIXTURE_ELF = ROOT / ".openrecomp-phase8" / "build" / "P8-01" / "candidate-a" / "p8_aes128_mips32_O1.elf"
FIXTURE_SHA256 = "0a90f47754f6331b868ec09ad23c451fc2c73925a43897fa62a696b0d40dde65"
EXPECTED_PROGRAM_FINGERPRINT = "3df423e0efdd1b6d0c91ce9f95bd33d0b58f08833226314bd43aff407751c704"
EXPECTED_FUNCTIONS = (
    "fn_fn_1000",
    "fn_fn_101c",
    "fn_fn_11b8",
    "fn_fn_11dc",
    "fn_fn_2290",
    "fn_fn_2360",
    "fn_fn_2490",
)
EXPECTED_FILE_ORDER = ("program.c", "p8_image_v1.c", "p8_runtime_support.c", "p8_driver.c")

SUPPORT_SOURCE = ROOT / ".openrecomp-phase8" / "runtime" / "p8_runtime_support.c"
DRIVER_SOURCE = ROOT / ".openrecomp-phase8" / "runtime" / "p8_observable_driver.c"

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL", "detail": detail})
        raise AssertionError(f"{label}: condition failed ({detail})")
    RESULTS.append({"check": label, "status": "PASS", "detail": detail})
    print(f"PASS: {label}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def evidence_json(payload: object) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_evidence(name: str, payload: object) -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / name).write_bytes(evidence_json(payload))


def derive_structure():
    data = FIXTURE_ELF.read_bytes()
    ingested = elf.ingest(data, target.MIPS32_O32)
    region = ingested.parsed.executable_regions()[0]
    analysis = frontier.analyze(ingested.image.read_u32, region.p_vaddr, region.p_vaddr + region.p_memsz, ingested.parsed.header.e_entry)
    source = ProgramSource(
        mips32_adapter.info.architecture_id,
        adapter="adapters.mips32",
        address_width_bits=32,
        endianness="little",
        input_sha256=sha256_bytes(data),
    )
    structure = structure_bridge.analyze_structure(analysis, source=source, entry=ingested.parsed.header.e_entry)
    return data, ingested, structure


def main() -> int:
    try:
        data, ingested, structure = derive_structure()
        check("fixture:sha256", sha256_bytes(data) == FIXTURE_SHA256, sha256_bytes(data))
        contract = contract_v1.build_contract(ingested)
        image = contract_v1.flat_image(ingested)
        support_text = SUPPORT_SOURCE.read_text(encoding="utf-8")
        driver_text = DRIVER_SOURCE.read_text(encoding="utf-8")

        first = emission.build_build_set(structure, contract, image, support_text, driver_text, FIXTURE_SHA256)
        second = emission.build_build_set(structure, contract, image, support_text, driver_text, FIXTURE_SHA256)
        check("emission:deterministic", first["files"] == second["files"], "byte-identical input set")
        check(
            "emission:program-fingerprint",
            first["program_fingerprint"] == EXPECTED_PROGRAM_FINGERPRINT,
            first["program_fingerprint"],
        )
        check("emission:file-order", tuple(first["files"]) == EXPECTED_FILE_ORDER, json.dumps(tuple(first["files"])))
        check(
            "emission:functions",
            sorted(item.function_name for item in first["program"].translations) == sorted(EXPECTED_FUNCTIONS),
            json.dumps(sorted(item.function_name for item in first["program"].translations)),
        )

        program_text = first["files"]["program.c"]
        check("program:entry-driver", "void openrecomp_run(void)" in program_text, "run boundary")
        check("program:no-main", "int main(" not in program_text, "driver supplies main")
        check("program:register-file", "static uint64_t g_r[32];" in program_text, "explicit register file")
        check("program:abi-surface", "or_rt_memory_read" in program_text and "or_rt_memory_write" in program_text, "runtime ABI")
        check("program:no-image", "p8_image" not in program_text, "program never touches the inert image directly")
        check("program:no-system", "#include <stdio.h>" not in program_text and "system(" not in program_text, "portable C only")
        check(
            "program:no-machine-code",
            "__asm" not in program_text and "asm(" not in program_text and "{ 0x" not in program_text,
            "no inline machine code or embedded instruction array",
        )

        image_text = first["files"]["p8_image_v1.c"]
        check("image:inert-data", "const unsigned char p8_image[P8_IMAGE_SIZE]" in image_text, "byte array")
        check("image:regions", "const struct p8_region p8_regions[]" in image_text, "region table")
        check("image:elf-magic-as-data", "0x7f, 0x45, 0x4c, 0x46," in image_text, "ELF header embedded as inert data")
        check("image:no-control-flow", "goto" not in image_text and "return" not in image_text, "data-only unit")

        support_out = first["files"]["p8_runtime_support.c"]
        check("support:abi-implementations", "int or_rt_memory_read(" in support_out and "int or_rt_memory_write(" in support_out and "int or_rt_host_call(" in support_out, "ABI implemented")
        check("support:output-service", "P8_OUTPUT_ADDR" in support_out and "or_rt_host_call" in support_out, "MMIO mapped to service")

        driver_out = first["files"]["p8_driver.c"]
        check("driver:fixture-identity", f'#define P8_FIXTURE_SHA256 "{FIXTURE_SHA256}"' in driver_out, "fixture hash")
        check("driver:observables", all(token in driver_out for token in ("exit_status=", "registers=0x", "memory=0x", "transcript_len=", "reads=")), "observable record")
        check("driver:digest-recipe", "0xcbf29ce484222325" in driver_out and "0x100000001b3" in driver_out, "FNV-1a 64")

        if EMISSION_DIR.exists():
            for stale in EMISSION_DIR.iterdir():
                if stale.is_file():
                    stale.unlink()
        EMISSION_DIR.mkdir(parents=True, exist_ok=True)
        written = {}
        for name, text in first["files"].items():
            (EMISSION_DIR / name).write_text(text, encoding="utf-8", newline="\n")
            written[name] = sha256_bytes(text.encode("utf-8"))
        check("emission:stable-filenames", sorted(path.name for path in EMISSION_DIR.iterdir()) == sorted(EXPECTED_FILE_ORDER), "stable names")
        check(
            "emission:content-hashes",
            all(sha256_bytes((EMISSION_DIR / name).read_bytes()) == digest for name, digest in written.items()),
            json.dumps(written, sort_keys=True),
        )
        check(
            "emission:no-host-paths",
            all(("D:\\" not in text and "C:\\" not in text) for text in first["files"].values()),
            "portable",
        )
        check(
            "emission:no-nondeterministic-macros",
            all(("__DATE__" not in text and "__TIME__" not in text and "__FILE__" not in text) for text in first["files"].values()),
            "deterministic content",
        )

        write_evidence(
            "emission_set.json",
            {
                "stage": STAGE,
                "fixture": {"sha256": FIXTURE_SHA256},
                "emission": emission.emission_document(first),
                "emission_digest": emission.emission_digest(first),
                "program_source_bytes": len(program_text.encode("utf-8")),
                "program_operations": sum(item.operations_emitted for item in first["program"].translations),
                "markers": {
                    "terminal": f"{TERMINAL_MARKER}={NOT_PROVEN}",
                    "general": f"{GENERAL_MARKER}={NOT_PROVEN}",
                },
            },
        )
    except Exception as exc:  # stable fail-closed boundary
        RESULTS.append({"check": "gate:exception", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    status = "PASS" if all(item["status"] == "PASS" for item in RESULTS) else "FAIL"
    record = {
        "stage": STAGE,
        "stage_name": "Host-source emission",
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
    write_evidence("p8_06_tests.json", record)

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
