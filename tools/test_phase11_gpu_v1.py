#!/usr/bin/env python3
"""Deterministic P11-05 typed GPU command-stream frontier gate.

The gate performs a controlled causal A/B at the private P11-04 frontier and
uses only original public synthetic fixtures for behavioral coverage. The A
variant retains the fail-closed A0:49 site. The B variant resolves the
documented one-argument, void ``GPU_cw`` service and submits its word through
the frozen Phase-9 typed GP0 boundary. That boundary remains the sole command
classifier and event recorder; this stage adds no renderer or GPU emulation.

Private evidence contains only bounded addresses, counters, hashes and typed
classifications. It never records payload bytes, raw instruction words,
reconstructive disassembly, or private paths.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase3/src", ".openrecomp-phase8/src",
              ".openrecomp-phase9/src", ".openrecomp-phase9/fixture",
              ".openrecomp-phase10/src", ".openrecomp-phase11/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p9_emission_v1 as p9_emission  # noqa: E402
import p9_gpu_boundary_v1 as gpu_boundary  # noqa: E402
import p9_image_bridge_v1 as bridge  # noqa: E402
import p9_memory_map_v1 as memory_map  # noqa: E402
import p9_psx_exe_v1 as psx  # noqa: E402
import p10_fixture_identity_v1 as fixture  # noqa: E402
import p10_structure_v1 as p10_structure  # noqa: E402
import p11_bios_v1 as bios  # noqa: E402
import p11_dynamic_v1 as dynamic  # noqa: E402
import p11_emission_v1 as emission  # noqa: E402
import p11_native_v1 as native  # noqa: E402
import p11_structure_v1 as structure_bridge  # noqa: E402
import p11_trace_v1 as trace  # noqa: E402
from openrecomp.program_model import ProgramSource  # noqa: E402
from tools import test_phase10_semantics_v1 as fixture_gate  # noqa: E402


STAGE = "P11-05"
FEATURE_MARKER = "OPENRECOMP_PHASE11_GPU_COMMAND_STREAM_V1"
GPU_MARKER = "OPENRECOMP_PHASE11_HERCULES_GPU_COMMAND_PROOF"
INITIALIZATION_MARKER = "OPENRECOMP_PHASE11_HERCULES_INITIALIZATION_PROOF"
FRAME_MARKER = "OPENRECOMP_PHASE11_HERCULES_FRAME_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE11_HERCULES_PLAYABILITY_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY"
PROVEN = "PROVEN"
NOT_PROVEN = "NOT_PROVEN"

DEFAULT_PRIVATE_FIXTURE_ROOT = ROOT.parents[1] / "fixtures" / "psx" / "hercules"
PROVEN_METHOD_POINTER = 0x80016384
DRIVER_METHOD_SITE = 0x80016204
GPU_CW_SITE = 0x8001B424
GPU_CW_ARGUMENT = 0x0002A244
ACCESS_BUDGET = 1_500_000
BLOCK_BUDGET = 8_000_000
PREFIX_BLOCK_BUDGET = 468_286
EXPECTED_B_FRONTIER = {
    "site": "0x8001882c",
    "source_value": "0x8001a7dc",
    "message": "unresolved indirect call",
    "function_entry": "0x8001b3f4",
    "function_id": "fn_800187b0",
    "block_id": "blk_80018824",
    "block_index": 468323,
    "failure_count": 23,
    "terminal_op": "jalr",
}

SERVICE_SUBSET_A = {
    "A0": {
        0x2B: bios.DOCUMENTED_A0_SERVICES[0x2B],
        0x3F: bios.DOCUMENTED_A0_SERVICES[0x3F],
    },
    "B0": {},
    "C0": {},
}
SERVICE_SUBSET_B = {
    "A0": {
        0x2B: bios.DOCUMENTED_A0_SERVICES[0x2B],
        0x3F: bios.DOCUMENTED_A0_SERVICES[0x3F],
        0x49: bios.DOCUMENTED_A0_SERVICES[0x49],
    },
    "B0": {},
    "C0": {},
}
SERVICE_SUBSET_SYNTHETIC = {
    "A0": {0x49: bios.DOCUMENTED_A0_SERVICES[0x49]},
    "B0": {},
    "C0": {},
}

P11_04_OBSERVABLE_KEYS = (
    "failed", "error", "exit_status", "registers", "memory",
    "gpu_events", "gpu", "input_events", "input", "spu_events", "spu",
    "cdrom_events", "cdrom", "reads", "writes", "denied", "host_calls",
    "p10_access_budget", "p10_access_count", "p10_budget_denials",
    "p10_service_calls", "p10_service_failures",
    "nonram_signatures", "nonram_overflow",
)

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    RESULTS.append({"check": label, "status": "PASS" if condition else "FAIL", "detail": detail})
    if not condition:
        raise AssertionError(f"{label}: condition failed ({detail})")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: pathlib.Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def _string_values(document):
    if isinstance(document, dict):
        for value in document.values():
            yield from _string_values(value)
    elif isinstance(document, list):
        for value in document:
            yield from _string_values(value)
    elif isinstance(document, str):
        yield document


def assert_no_payload_leak(label: str, document: dict, payload: bytes) -> None:
    text = json.dumps(document, sort_keys=True)
    sample = payload[:64]
    check(f"{label}:no-hex", sample.hex() not in text.lower(), "payload hex absent")
    check(f"{label}:no-base64", base64.b64encode(sample).decode("ascii") not in text,
          "payload base64 absent")
    for start in range(0, min(len(payload), 512)):
        run = payload[start:start + 8]
        if len(run) == 8 and all(32 <= byte < 127 for byte in run):
            check(f"{label}:no-ascii-run", run.decode("ascii") not in text,
                  f"ascii payload run absent at {start}")
    for value in _string_values(document):
        check(f"{label}:string-length", len(value) <= 128, f"{len(value)} chars")


def fnv1a64(data: bytes) -> str:
    value = 0xCBF29CE484222325
    for byte in data:
        value ^= byte
        value = (value * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return f"0x{value:016x}"


def emit_load_immediate(assembler, register: int, value: int) -> None:
    assembler.i("lui", rt=register, imm=(value >> 16) & 0xFFFF)
    assembler.i("ori", rs=register, rt=register, imm=value & 0xFFFF)


def gpu_cw_words(commands: tuple[int, ...], *, index: int = 0x49) -> list[int]:
    """Original public program calling the documented A0 vector convention."""
    assembler = fixture_gate.Assembler()
    assembler.i("addiu", rt=2, imm=0x1234)  # void-call preservation sentinel
    for command in commands:
        emit_load_immediate(assembler, 4, command & 0xFFFFFFFF)
        assembler.jump("jal", "bios_stub")
        assembler.nop()
    assembler.i("addiu", rt=16, imm=0x55)   # continuation marker
    assembler.r("jr", rs=31)
    assembler.nop()
    assembler.label("bios_stub")
    assembler.i("addiu", rt=10, imm=0xA0)
    assembler.r("jr", rs=10)
    assembler.i("addiu", rt=9, imm=index)
    return assembler.finish()


def source_for(sha256: str) -> ProgramSource:
    return ProgramSource("mips32-bounded-v1", adapter="adapters.mips32",
                         address_width_bits=32, endianness="little",
                         input_sha256=sha256)


def structure_for_words(words: list[int]):
    data = fixture_gate.builder.build_from_words(words, load_address=fixture_gate.LOAD)
    image = psx.ingest(data)
    contract = memory_map.build_contract(image)
    flat = memory_map.flat_image(image)
    pipeline = bridge.analyze(image, contract, flat)
    source = source_for(image.file_sha256)
    base = p10_structure.analyze_structure(pipeline.analysis, source=source, entry=image.header.pc0)
    result, document = structure_bridge.analyze_structure_with_bios(
        pipeline.analysis, source=source, entry=image.header.pc0,
        services=SERVICE_SUBSET_SYNTHETIC,
    )
    return image, contract, flat, base, result, bios.resolved_sites(document), document


def private_structures(fixture_root: pathlib.Path):
    image = psx.ingest((fixture_root / fixture.PRIMARY_EXECUTABLE).read_bytes())
    contract = memory_map.build_contract(image)
    flat = memory_map.flat_image(image)
    pipeline = bridge.analyze(image, contract, flat)
    source = source_for(image.file_sha256)
    base = p10_structure.analyze_structure(
        pipeline.analysis, source=source, entry=image.header.pc0
    )
    read_word = lambda address: memory_map.read_u32(contract, flat, address)
    merged, extension, extra = dynamic.extend_analysis(
        pipeline.analysis, read_word, image.header.t_addr,
        image.header.t_addr + image.header.t_size, (PROVEN_METHOD_POINTER,),
    )
    common = {
        "source": source,
        "entry": image.header.pc0,
        "dynamic_observations": {DRIVER_METHOD_SITE: (PROVEN_METHOD_POINTER,)},
        "extensions": extra,
        "merged_analysis": merged,
    }
    result_a, sites_a, targets_a = structure_bridge.analyze_structure_with_overlays(
        pipeline.analysis, services=SERVICE_SUBSET_A, **common
    )
    result_b, sites_b, targets_b = structure_bridge.analyze_structure_with_overlays(
        pipeline.analysis, services=SERVICE_SUBSET_B, **common
    )
    return {
        "image": image, "contract": contract, "flat": flat, "base": base,
        "result_a": result_a, "result_b": result_b,
        "site_document_a": sites_a, "site_document_b": sites_b,
        "sites_a": bios.resolved_sites(sites_a), "sites_b": bios.resolved_sites(sites_b),
        "targets_a": targets_a, "targets_b": targets_b, "extension": extension,
    }


def classify_writes(parsed: dict) -> list[dict]:
    classified: list[dict] = []
    for item in parsed.get("gpu_writes", []):
        value = int(item["value"], 16)
        if int(item["address"], 16) == gpu_boundary.GP0_WRITE:
            classification = gpu_boundary.classify_gp0(value)
        elif int(item["address"], 16) == gpu_boundary.GP1_WRITE:
            classification = gpu_boundary.classify_gp1(value)
        else:
            classification = {"port": "UNKNOWN", "class": "UNKNOWN_PORT",
                              "known": False, "emulated": False}
        classified.append({**item, "classification": classification})
    return classified


def observables(parsed: dict) -> dict:
    return {key: parsed.get(key) for key in P11_04_OBSERVABLE_KEYS}


def run_both(native_build: dict, *, access_budget: int | None = None,
             block_budget: int | None = None, timeout: int = 900) -> tuple[dict, dict]:
    first = native.run_native(native_build["executables"][0], access_budget=access_budget,
                              block_budget=block_budget, timeout=timeout)
    second = native.run_native(native_build["executables"][1], access_budget=access_budget,
                               block_budget=block_budget, timeout=timeout)
    return first, second


def malformed_driver(service_id: int) -> str:
    return f'''#include <stdint.h>
#include <stdio.h>
void p9_runtime_init(void);
int or_rt_host_call(uint64_t, uint32_t, const uint64_t *, uint64_t *);
uint64_t p9_runtime_host_calls(void);
uint32_t p9_runtime_gpu_event_count(void);
uint64_t p10_runtime_mips_service_calls(void);
uint64_t p10_runtime_mips_service_failures(void);
int main(void)
{{
    uint64_t out_value = UINT64_C(0x11223344);
    int status;
    p9_runtime_init();
    status = or_rt_host_call(UINT64_C({service_id}), 0u, NULL, &out_value);
    printf("status=%d\\n", status);
    printf("out_value=0x%08llx\\n", (unsigned long long)out_value);
    printf("host_calls=%llu\\n", (unsigned long long)p9_runtime_host_calls());
    printf("service_calls=%llu\\n", (unsigned long long)p10_runtime_mips_service_calls());
    printf("service_failures=%llu\\n", (unsigned long long)p10_runtime_mips_service_failures());
    printf("gpu_events=%lu\\n", (unsigned long)p9_runtime_gpu_event_count());
    return 0;
}}
'''


def parse_simple(stdout: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in stdout.decode("utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase11/evidence/P11-05")
    parser.add_argument("--private-fixture-root", default=str(DEFAULT_PRIVATE_FIXTURE_ROOT))
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()
    fixture_root = pathlib.Path(options.private_fixture_root)
    build_root = ROOT / ".openrecomp-phase11" / "build"

    try:
        private = private_structures(fixture_root)
        image = private["image"]
        contract = private["contract"]
        flat = private["flat"]

        # The B overlay must add exactly the documented A0:49 service.
        a_services = {site.service_id for site in private["sites_a"]}
        b_services = {site.service_id for site in private["sites_b"]}
        check("bios:a0-49-added-only-in-b",
              b_services - a_services == {"ps1.bios.A0.49"},
              json.dumps(sorted(b_services - a_services)))
        gpu_sites = [site for site in private["sites_b"]
                     if site.service_id == "ps1.bios.A0.49"]
        check("bios:a0-49-one-site", len(gpu_sites) == 1, str(len(gpu_sites)))
        gpu_site = gpu_sites[0]
        check("bios:a0-49-site", gpu_site.site == GPU_CW_SITE, f"0x{gpu_site.site:08x}")
        check("bios:a0-49-vector-index",
              gpu_site.vector == "A0" and gpu_site.function_index == 0x49,
              f"{gpu_site.vector}:{gpu_site.function_index}")
        service = bios.DOCUMENTED_A0_SERVICES[0x49]
        check("bios:a0-49-one-argument", service["signature"] == ["command"],
              json.dumps(service["signature"]))
        check("bios:a0-49-void", service["result_register"] is None,
              str(service["result_register"]))

        private_b_build_set = emission.build_bios_build_set(
            private["result_b"], private["base"], contract, flat, image.file_sha256,
            sites=private["sites_b"], trace=True, guarded_resolved_indirect=True,
        )
        bios_rules = private_b_build_set["semantics"]["bios_rules"]
        gpu_rule = [item for item in bios_rules if item["service"] == "ps1.bios.A0.49"]
        check("semantics:a0-49-one-rule", len(gpu_rule) == 1, str(len(gpu_rule)))
        check("semantics:a0-49-arity-result",
              gpu_rule[0]["args"] == ["bios_arg0"] and gpu_rule[0]["result"] is None,
              json.dumps(gpu_rule[0], sort_keys=True))
        arities = private_b_build_set["semantics"]["service_arities"]
        check("semantics:a0-49-service-arity", arities["ps1.bios.A0.49"] == 1,
              str(arities["ps1.bios.A0.49"]))

        # Original public positive: two known opcode-0 NOP words in order.
        positive = structure_for_words(gpu_cw_words((0x00000000, 0x00000001)))
        pos_image, pos_contract, pos_flat, pos_base, pos_result, pos_sites, _ = positive
        pos_build_set = emission.build_bios_build_set(
            pos_result, pos_base, pos_contract, pos_flat, pos_image.file_sha256,
            sites=pos_sites, trace=True,
        )
        program_text = pos_build_set["files"][emission.PROGRAM_NAME]
        support_text = pos_build_set["files"][emission.SUPPORT_NAME]
        check("synthetic:positive:host-call-arity",
              "OR_RT_SERVICE_PS1_BIOS_A0_49, 1u" in program_text,
              "one-argument host call emitted")
        call_position = program_text.index("OR_RT_SERVICE_PS1_BIOS_A0_49, 1u")
        call_window = program_text[call_position:call_position + 512]
        check("synthetic:positive:void-no-result-assignment",
              "= or_call_result" not in call_window, "void call preserves r2")
        check("synthetic:positive:typed-boundary",
              "or_rt_memory_write((uint64_t)P9_GP0_ADDR, 32u, (uint64_t)command)" in support_text,
              "typed GP0 write is the implementation")
        bios_source = (ROOT / ".openrecomp-phase11/runtime/p11_bios_extension_v1.c").read_text(
            encoding="utf-8"
        )
        check("synthetic:positive:no-raw-port-literal", "0x1F801810" not in bios_source,
              "service uses the named typed boundary")
        pos_build = native.build_native(
            pos_build_set, build_root / "p11-05-public-positive",
            fixture_id="p11-05-public-positive", run_count=2,
        )
        check("synthetic:positive:build", all(x == "OK" for x in pos_build["build_status"]),
              str(pos_build["build_status"]))
        check("synthetic:positive:build-reproducible", pos_build["build_reproducible"],
              pos_build["executable_sha256"])
        pos_first, pos_second = run_both(pos_build, timeout=300)
        check("synthetic:positive:exit",
              pos_first["returncode"] == 0 and pos_second["returncode"] == 0,
              f"{pos_first['returncode']}/{pos_second['returncode']}")
        check("synthetic:positive:stderr",
              pos_first["stderr_bytes"] == 0 and pos_second["stderr_bytes"] == 0,
              f"{pos_first['stderr_bytes']}/{pos_second['stderr_bytes']}")
        check("synthetic:positive:deterministic",
              pos_first["stdout"] == pos_second["stdout"], pos_first["stdout_sha256"])
        pos = pos_first["parsed"]
        pos_classified = classify_writes(pos)
        check("synthetic:positive:success", pos.get("failed") == "0" and pos.get("error") == "",
              str((pos.get("failed"), pos.get("error"))))
        check("synthetic:positive:void-return-preserved",
              pos["register_file"].get("r02") == "0x00001234",
              str(pos["register_file"].get("r02")))
        check("synthetic:positive:continuation",
              pos["register_file"].get("r16") == "0x00000055",
              str(pos["register_file"].get("r16")))
        check("synthetic:positive:ordered-values",
              [item["value"] for item in pos_classified] == ["0x00000000", "0x00000001"],
              json.dumps([item["value"] for item in pos_classified]))
        check("synthetic:positive:ordered-sequence",
              [item["sequence"] for item in pos_classified] == [0, 1],
              json.dumps([item["sequence"] for item in pos_classified]))
        check("synthetic:positive:classification",
              all(item["classification"] == {
                  "port": "GP0", "command": "0x00", "class": "NOP",
                  "known": True, "emulated": False,
              } for item in pos_classified), json.dumps(pos_classified, sort_keys=True))
        check("synthetic:positive:gpu-counts",
              (pos.get("gpu_write_events"), pos.get("gpu_gp0_writes"),
               pos.get("gpu_gp1_writes"), pos.get("gpu_known_writes"),
               pos.get("gpu_blocker_writes")) == ("2", "2", "0", "2", "0"),
              "typed ordered GP0 NOP writes only")
        check("synthetic:positive:ram-unchanged", pos.get("memory") == fnv1a64(pos_flat),
              str(pos.get("memory")))
        check("synthetic:positive:no-fabricated-devices",
              pos.get("input_events") == "0" and pos.get("spu_events") == "0"
              and pos.get("cdrom_events") == "0" and pos.get("writes") == "0"
              and pos.get("denied") == "0",
              "no RAM/device/interrupt/DMA side effect")

        # Original public negative: unknown GP0 opcode is recorded then rejected.
        unknown = structure_for_words(gpu_cw_words((0x03000000,)))
        unk_image, unk_contract, unk_flat, unk_base, unk_result, unk_sites, _ = unknown
        unk_build_set = emission.build_bios_build_set(
            unk_result, unk_base, unk_contract, unk_flat, unk_image.file_sha256,
            sites=unk_sites, trace=True,
        )
        unk_build = native.build_native(
            unk_build_set, build_root / "p11-05-public-unknown",
            fixture_id="p11-05-public-unknown", run_count=2,
        )
        check("synthetic:unknown:build", all(x == "OK" for x in unk_build["build_status"]),
              str(unk_build["build_status"]))
        check("synthetic:unknown:build-reproducible", unk_build["build_reproducible"],
              unk_build["executable_sha256"])
        unk_first, unk_second = run_both(unk_build, timeout=300)
        check("synthetic:unknown:exit-stderr",
              unk_first["returncode"] == 0 and unk_second["returncode"] == 0
              and unk_first["stderr_bytes"] == 0 and unk_second["stderr_bytes"] == 0,
              "exit 0 and empty stderr")
        check("synthetic:unknown:deterministic", unk_first["stdout"] == unk_second["stdout"],
              unk_first["stdout_sha256"])
        unk = unk_first["parsed"]
        unk_classified = classify_writes(unk)
        check("synthetic:unknown:rejected",
              unk.get("failed") == "1"
              and unk.get("error") == "runtime host service ps1.bios.A0.49 failed",
              str((unk.get("failed"), unk.get("error"))))
        check("synthetic:unknown:typed-blocker",
              len(unk_classified) == 1
              and unk_classified[0]["flags"] == 2
              and unk_classified[0]["classification"]["class"] == "UNKNOWN_COMMAND"
              and unk_classified[0]["classification"]["known"] is False,
              json.dumps(unk_classified, sort_keys=True))
        check("synthetic:unknown:counters",
              unk.get("gpu_gp0_writes") == "1" and unk.get("gpu_blocker_writes") == "1"
              and unk.get("denied") == "1" and unk.get("p10_service_failures") == "1",
              "unknown command fails closed once")
        check("synthetic:unknown:ram-unchanged", unk.get("memory") == fnv1a64(unk_flat),
              str(unk.get("memory")))

        # Malformed call directly exercises the composed production dispatcher.
        service_id = pos_build_set["runtime_composition"]["bios_fragment"][
            "service_numeric_ids"
        ]["ps1.bios.A0.49"]
        malformed_set = dict(pos_build_set)
        malformed_set["files"] = dict(pos_build_set["files"])
        malformed_set["files"][emission.DRIVER_NAME] = (
            p9_emission.render_image_header(pos_contract) + "\n" + malformed_driver(service_id)
        )
        malformed_build = native.build_native(
            malformed_set, build_root / "p11-05-public-malformed",
            fixture_id="p11-05-public-malformed", run_count=2,
        )
        check("synthetic:malformed:build",
              all(x == "OK" for x in malformed_build["build_status"]),
              str(malformed_build["build_status"]))
        check("synthetic:malformed:build-reproducible", malformed_build["build_reproducible"],
              malformed_build["executable_sha256"])
        malformed_runs = [
            subprocess.run([str(executable)], capture_output=True, timeout=300)
            for executable in malformed_build["executables"]
        ]
        check("synthetic:malformed:exit-stderr",
              all(run.returncode == 0 and not run.stderr for run in malformed_runs),
              "exit 0 and empty stderr")
        check("synthetic:malformed:deterministic",
              malformed_runs[0].stdout == malformed_runs[1].stdout,
              sha256_bytes(malformed_runs[0].stdout))
        malformed = parse_simple(malformed_runs[0].stdout)
        check("synthetic:malformed:rejected",
              malformed == {
                  "status": "13", "out_value": "0x11223344", "host_calls": "1",
                  "service_calls": "1", "service_failures": "1", "gpu_events": "0",
              }, json.dumps(malformed, sort_keys=True))

        # Private causal A/B: independently build each composition twice.
        build_set_a = emission.build_bios_build_set(
            private["result_a"], private["base"], contract, flat, image.file_sha256,
            sites=private["sites_a"], trace=True, guarded_resolved_indirect=True,
        )
        build_set_b = private_b_build_set
        build_a = native.build_native(
            build_set_a, build_root / "p11-05-private-a", fixture_id="p11-05-private-a",
            run_count=2,
        )
        build_b = native.build_native(
            build_set_b, build_root / "p11-05-private-b", fixture_id="p11-05-private-b",
            run_count=2,
        )
        for label, built in (("a", build_a), ("b", build_b)):
            check(f"private:{label}:build", all(x == "OK" for x in built["build_status"]),
                  str(built["build_status"]))
            check(f"private:{label}:build-reproducible", built["build_reproducible"],
                  built["executable_sha256"])

        prefix_a, prefix_a_second = run_both(
            build_a, access_budget=ACCESS_BUDGET, block_budget=PREFIX_BLOCK_BUDGET
        )
        prefix_b, prefix_b_second = run_both(
            build_b, access_budget=ACCESS_BUDGET, block_budget=PREFIX_BLOCK_BUDGET
        )
        for label, first, second in (
            ("a", prefix_a, prefix_a_second), ("b", prefix_b, prefix_b_second)
        ):
            check(f"private:prefix-{label}:exit-stderr",
                  first["returncode"] == 0 and second["returncode"] == 0
                  and first["stderr_bytes"] == 0 and second["stderr_bytes"] == 0,
                  "exit 0 and empty stderr")
            check(f"private:prefix-{label}:deterministic", first["stdout"] == second["stdout"],
                  first["stdout_sha256"])
        pa = prefix_a["parsed"]
        pb = prefix_b["parsed"]
        check("private:prefix:block-count",
              pa.get("trace_block_events") == pb.get("trace_block_events") == "468287",
              str((pa.get("trace_block_events"), pb.get("trace_block_events"))))
        check("private:prefix:block-stream",
              pa.get("trace_block_digest") == pb.get("trace_block_digest"),
              str((pa.get("trace_block_digest"), pb.get("trace_block_digest"))))
        for key in ("registers", "memory", "input_events", "input", "spu_events", "spu",
                    "cdrom_events", "cdrom", "reads", "writes", "denied",
                    "p10_budget_denials", "p10_service_failures", "nonram_overflow"):
            check(f"private:prefix:same:{key}", pa.get(key) == pb.get(key),
                  str((pa.get(key), pb.get(key))))
        check("private:prefix:host-service-delta",
              int(pb["host_calls"]) == int(pa["host_calls"]) + 1
              and int(pb["p10_service_calls"]) == int(pa["p10_service_calls"]) + 1,
              f"{pa['host_calls']}/{pb['host_calls']}")
        check("private:prefix:access-delta",
              int(pb["p10_access_count"]) == int(pa["p10_access_count"]) + 1,
              f"{pa['p10_access_count']}/{pb['p10_access_count']}")
        check("private:prefix:nonram-signature-delta",
              int(pb["nonram_signatures"]) == int(pa["nonram_signatures"]) + 1,
              f"{pa['nonram_signatures']}/{pb['nonram_signatures']}")
        prefix_writes = classify_writes(pb)
        check("private:prefix:a-no-gpu-write", pa.get("gpu_write_events") == "0",
              str(pa.get("gpu_write_events")))
        check("private:prefix:b-one-typed-write",
              len(prefix_writes) == 1 and prefix_writes[0]["value"] == "0x0002a244"
              and prefix_writes[0]["classification"]["class"] == "NOP"
              and prefix_writes[0]["classification"]["known"] is True
              and prefix_writes[0]["classification"]["emulated"] is False,
              json.dumps(prefix_writes, sort_keys=True))

        # Full identical-budget runs establish movement and the next frontier.
        full_a, full_a_second = run_both(
            build_a, access_budget=ACCESS_BUDGET, block_budget=BLOCK_BUDGET
        )
        full_b, full_b_second = run_both(
            build_b, access_budget=ACCESS_BUDGET, block_budget=BLOCK_BUDGET
        )
        for label, first, second in (
            ("a", full_a, full_a_second), ("b", full_b, full_b_second)
        ):
            check(f"private:full-{label}:exit-stderr",
                  first["returncode"] == 0 and second["returncode"] == 0
                  and first["stderr_bytes"] == 0 and second["stderr_bytes"] == 0,
                  "exit 0 and empty stderr")
            check(f"private:full-{label}:deterministic", first["stdout"] == second["stdout"],
                  first["stdout_sha256"])
        fa = full_a["parsed"]
        fb = full_b["parsed"]
        frozen_frontier = json.loads(
            (ROOT / ".openrecomp-phase11/evidence/P11-04/frontier.json").read_text(
                encoding="utf-8"
            )
        )
        frozen_observables = frozen_frontier["frontier_run"]["observables"]
        frozen_mismatches = [
            key for key in P11_04_OBSERVABLE_KEYS
            if fa.get(key) != frozen_observables.get(key)
        ]
        check("private:a-preserves-24-p11-04-observables", not frozen_mismatches,
              ",".join(frozen_mismatches) or "24 observables")
        analysis_a = trace.analyze_trace(fa, trace.StructureIndex(private["result_a"]), None)
        analysis_b = trace.analyze_trace(fb, trace.StructureIndex(private["result_b"]), None)
        failure_a = analysis_a["failure"]
        failure_b = analysis_b["failure"]
        check("private:a-frontier",
              failure_a["site"] == "0x8001b424"
              and failure_a["block_index"] == 468286,
              f"{failure_a['site']}@{failure_a['block_index']}")
        check("private:b-moves-frontier",
              failure_b["block_index"] > 468286 and failure_b["site"] != "0x8001b424",
              f"{failure_b['site']}@{failure_b['block_index']}")
        check("private:b-exact-frontier",
              all(failure_b.get(key) == value for key, value in EXPECTED_B_FRONTIER.items()),
              json.dumps(failure_b, sort_keys=True))
        full_b_writes = classify_writes(fb)
        check("private:b-genuine-first-gp0-write",
              len(full_b_writes) >= 1
              and full_b_writes[0]["address"] == "0x1f801810"
              and full_b_writes[0]["value"] == "0x0002a244"
              and full_b_writes[0]["classification"]["class"] == "NOP"
              and full_b_writes[0]["classification"]["known"] is True,
              json.dumps(full_b_writes[:1], sort_keys=True))

        # Evidence: intentionally non-reconstructive and path-free.
        diagnostic_document = {
            "schema": "openrecomp-phase11-gpu-cw-diagnostic-v1",
            "stage": STAGE,
            "classification": "GUEST_VALUE_CONFIRMED",
            "failure_block_index": 468286,
            "bios_site": "0x8001b424",
            "bios_vector": "A0",
            "function_index": "0x49",
            "service": "ps1.bios.A0.49",
            "vector_register": "$t2",
            "vector_value": "0x000000a0",
            "vector_provenance": {
                "defining_pc": "0x8001b420",
                "operation": "addiu",
                "source_register": "$zero",
                "source_value": "0x00000000",
                "destination_register": "$t2",
                "result_value": "0x000000a0",
                "block_transition": "same block to 0x8001b424",
                "category": "arithmetic immediate",
                "delay_slot": False,
            },
            "argument_register": "$a0",
            "argument_value": "0x0002a244",
            "argument_provenance": {
                "kind": "stable RAM-derived pointer",
                "initial_word": "0x8002a244",
                "runtime_mask": "0x00ffffff",
                "overlapping_writes_before_call": 0,
                "reference_value": "0x0002a244",
            },
            "divergence": None,
            "excluded_defects": ["CPU semantics", "translation", "ABI", "memory", "runtime state"],
            "gp0": {"opcode": "0x00", "class": "NOP", "known": True, "emulated": False},
            "privacy": {
                "payload_bytes": "not recorded",
                "raw_instruction_words": "not recorded",
                "reconstructive_disassembly": "not recorded",
                "private_paths": "not recorded",
            },
        }
        causal_document = {
            "schema": "openrecomp-phase11-gpu-cw-causal-ab-v1",
            "stage": STAGE,
            "budgets": {"access": ACCESS_BUDGET, "prefix_blocks": PREFIX_BLOCK_BUDGET,
                        "full_blocks": BLOCK_BUDGET},
            "a": {
                "policy": "A0:49 remains fail closed",
                "failure": failure_a,
                "observables": observables(fa),
                "stdout_sha256": full_a["stdout_sha256"],
            },
            "b": {
                "policy": "documented A0:49 through typed GP0 boundary",
                "failure": failure_b,
                "observables": observables(fb),
                "stdout_sha256": full_b["stdout_sha256"],
                "gpu_writes": full_b_writes,
            },
            "prefix": {
                "same_block_events": pa.get("trace_block_events"),
                "same_block_digest": pa.get("trace_block_digest"),
                "a_host_calls": pa.get("host_calls"),
                "b_host_calls": pb.get("host_calls"),
                "a_service_calls": pa.get("p10_service_calls"),
                "b_service_calls": pb.get("p10_service_calls"),
                "a_access_count": pa.get("p10_access_count"),
                "b_access_count": pb.get("p10_access_count"),
                "a_nonram_signatures": pa.get("nonram_signatures"),
                "b_nonram_signatures": pb.get("nonram_signatures"),
                "required_gpu_write": prefix_writes,
            },
            "conclusion": "frontier moved; only the documented void service and typed NOP differ pre-frontier",
        }
        public_records = {
            "known_nop": {
                "commands": ["0x00000000", "0x00000001"],
                "stdout_sha256": pos_first["stdout_sha256"],
                "gpu_writes": pos_classified,
                "ram_unchanged": True,
                "fabricated_gpu_state": False,
            },
            "unknown_opcode": {
                "command": "0x03000000",
                "stdout_sha256": unk_first["stdout_sha256"],
                "gpu_writes": unk_classified,
                "rejected": True,
            },
            "malformed_call": {
                "stdout_sha256": sha256_bytes(malformed_runs[0].stdout),
                "result": malformed,
                "rejected": True,
            },
        }
        frontier_document = {
            "schema": "openrecomp-phase11-gpu-command-frontier-v1",
            "stage": STAGE,
            "milestone_c": {
                "established": True,
                "basis": "genuine typed GP0 write with deterministic ordering and NOP classification",
            },
            "milestone_b": {"established": False, "reason": "initialization completion not proven"},
            "new_frontier": failure_b,
            "private_run": {
                "access_budget": ACCESS_BUDGET,
                "block_budget": BLOCK_BUDGET,
                "executable_sha256": build_b["executable_sha256"],
                "stdout_sha256": full_b["stdout_sha256"],
                "observables": observables(fb),
                "gpu_writes": full_b_writes,
            },
            "implementation": {
                "bios_service": "ps1.bios.A0.49",
                "typed_boundary": "or_rt_memory_write(P9_GP0_ADDR, 32, command)",
                "frozen_classifier_reused": True,
                "renderer": False, "vram_mutation": False, "dma": False,
                "interrupt": False, "unrelated_gpu_state": False,
            },
            "public_synthetic": public_records,
            "structure": {
                "functions": len(private["result_b"].units.units),
                "blocks": sum(len(unit.blocks) for unit in private["result_b"].units.units),
                "proven_entry": "0x80016384",
            },
            "builds": {
                "a_executable_sha256": build_a["executable_sha256"],
                "b_executable_sha256": build_b["executable_sha256"],
                "a_program_sha256": build_set_a["hashes"][emission.PROGRAM_NAME],
                "b_program_sha256": build_set_b["hashes"][emission.PROGRAM_NAME],
            },
        }
        for name, document in (("diagnostic.json", diagnostic_document),
                               ("causal_ab.json", causal_document),
                               ("frontier.json", frontier_document)):
            write_json(evidence / name, document)
            assert_no_payload_leak(f"public:{name}", document, image.payload)

        check("claim:gpu-command-stream-promoted", True, PROVEN)
        check("claim:initialization-not-promoted", True, NOT_PROVEN)
        check("claim:frame-not-promoted", True, NOT_PROVEN)
        check("claim:playability-not-promoted", True, NOT_PROVEN)
        check("claim:general-permanent", True, NOT_PROVEN)
    except AssertionError as exc:
        RESULTS.append({"check": "gate:assertion", "status": "FAIL", "detail": str(exc)})
    except Exception as exc:
        RESULTS.append({"check": "gate:exception", "status": "FAIL",
                        "detail": f"{type(exc).__name__}: {exc}"})

    failed = [item for item in RESULTS if item["status"] == "FAIL"]
    status = "PASS" if not failed else "FAIL"
    results = sorted(RESULTS, key=lambda item: item["check"])
    stage_record = {
        "stage": STAGE,
        "stage_name": "GPU command-stream frontier",
        "status": status,
        "tests": len(results),
        "passed": sum(1 for item in results if item["status"] == "PASS"),
        "failed": len(failed),
        "checks": results,
        "failure": None if not failed else [item["check"] for item in failed],
    }
    write_json(evidence / "p11_05_tests.json", stage_record)

    for item in results:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P11_05={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(f"{GPU_MARKER}={PROVEN if status == 'PASS' else NOT_PROVEN}")
    print(f"{INITIALIZATION_MARKER}={NOT_PROVEN}")
    print(f"{FRAME_MARKER}={NOT_PROVEN}")
    print(f"{PLAYABILITY_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
