#!/usr/bin/env python3
"""OpenRecomp Phase-4 platform-adapter execution gate (P4-08).

Translates the P4-07 fixture with the frozen architecture-neutral instruction
emitter, verifies the generated sources against the P4-01 ABI and the declared
fixture instance profile, builds them with the deterministic Phase-2 host
build pipeline, and runs the native program as a real implementation of the
platform-adapter/runtime contracts:

* every reachable fixture word is emitted; unsupported records fail closed at
  emission time;
* generated sources reference only the declared ABI entries and services;
* the emitted support implements checked memory over the fixture region table,
  typed service dispatch, the deterministic input plan, bounded output and
  virtual ticks, and prints the P4-01 canonical observable;
* a `BoundPlatform` built from a fixture platform adapter (memory map,
  generic service aliases, recorded input, optional boundary hooks) exposes
  the same declared service profile as the native support (numeric ids, arg
  types, aliases) and mediates the fixture services fail-closed;
* native execution reproduces the fixture transcript exactly (fixed fields
  from the P4-07 model, pinned tick fields and state digest) with identical
  replays and a byte-reproducible executable;
* tiny negative programs demonstrate fail-closed memory faults and step-limit
  exhaustion.

It emits::

    OPENRECOMP_P4_08=PASS
    OPENRECOMP_PHASE4_ADAPTER_EXECUTION_V1=PASS tests=<count>
    OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase4_adapter_execution_v1.py
    python tools/test_phase4_adapter_execution_v1.py --evidence-dir .openrecomp-phase4/evidence/P4-08
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
for candidate in (str(ROOT), str(ROOT / ".openrecomp-phase4" / "src"),
                  str(ROOT / ".openrecomp-phase3" / "src")):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import openrecomp.build_pipeline as bp  # noqa: E402
import p4_deterministic_io_v1 as dio  # noqa: E402
import p4_fixture_exec_v1 as fx  # noqa: E402
import p4_graphics_audio_v1 as ga  # noqa: E402
import p4_platform_adapter_v1 as pa  # noqa: E402
import p4_runtime_abi_v1 as abi  # noqa: E402
from p3_host_emit_v1 import HostEmitError, emit_instruction  # noqa: E402
from openrecomp import runtime_abi as rt  # noqa: E402
from openrecomp.program_model import canonical_json  # noqa: E402

STAGE = "P4-08"
STAGE_MARKER = "OPENRECOMP_P4_08"
FEATURE_MARKER = "OPENRECOMP_PHASE4_ADAPTER_EXECUTION_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY"

SOURCE_SUMS = "SOURCE_SHA256SUMS.txt"
SOURCE_SUMS_SHA256 = "76f77bbc97780afe9c2b41a0cb89b5323ab22450c4b2a368dd03fb4d7bbe1095"
SOURCE_SUMS_ENTRIES = 134
P3_SUMS = ".openrecomp-phase3/SOURCE_SHA256SUMS.txt"
P3_SUMS_SHA256 = "a7d0953c0f02276ad233db50e326d9e71a3136542648bb04a95de9d3e05e2488"
P3_SUMS_ENTRIES = 24
P4_SUMS = ".openrecomp-phase4/SOURCE_SHA256SUMS.txt"

FIXTURE_ELF_SHA256 = "acb4f4e57a7f996e87989e99d702d802259b752aabb2476f574665ef061969bc"
PROGRAM_SHA256 = "abd138ea391fb48cd5ba17b54f56f93a77aaa6ebab201d715210635a7f1edc48"
SUPPORT_SHA256 = "755a004630560ae606ce571c2c111934b94e945db6c4c6d6aea5c105a2b8a8fd"
EXECUTABLE_SHA256 = "c966e1854dcc9c9169859b20ef40c07810e7d40d7dc7700b2e202a168e5b3caa"
STDOUT_SHA256 = "8a96b7083c04f63e7c0ed8181f3462e9a73d41e9f40ea67ccd66e85d76cb1c50"
EXPECTED = {
    "input_bytes": 4,
    "input_xor": 136,
    "fib10": 55,
    "prime_count": 16,
    "primes_sum": 381,
    "bss_sum": 4028012831,
    "heap_sum": 3784880468,
    "checksum": "0xd43e5ba6",
    "ticks_start": 19,
    "ticks_end": 6691,
}
EXPECTED_STEPS = 6784
EXPECTED_PC = "0x00001bf4"
EXPECTED_STATE_DIGEST = "0x5185479717fe4020"
REPLAY_COUNT = 3
WORKSPACE = ROOT / ".openrecomp-phase4" / "build" / "P4-08"

RESULTS: list[dict[str, str]] = []
FINDINGS: dict[str, Any] = {}
ARTIFACTS: dict[str, bytes] = {}


class FixtureExecGateError(ValueError):
    pass


def check(label: str, condition: bool) -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        print(f"FAIL: {label}", flush=True)
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}", flush=True)


def expect_fail(label: str, thunk, error_type=Exception) -> None:
    try:
        thunk()
    except error_type:
        check(f"reject:{label}", True)
        return
    except Exception as exc:  # noqa: BLE001 - fail closed
        raise AssertionError(
            f"{label}: raised {type(exc).__name__} instead of {error_type.__name__}") from exc
    raise AssertionError(f"{label}: accepted")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def banner(name: str) -> None:
    print(f"\n--- {name} ---", flush=True)


def analysis_reserved_addresses(data: bytes) -> list[str]:
    frontier = fx.analyze_fixture(data)["frontier"]
    reachable = set(frontier["reachable_addresses"])
    return [f"0x{record['address']:08x}" for record in frontier["records"]
            if record.get("decode_class") in ("RESERVED_ENCODING", "UNKNOWN_ENCODING")
            and record["address"] not in reachable]


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


# ---------------------------------------------------------------------------
# Source integrity and translation
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


def audit_translation(data: bytes) -> fx.FixtureTranslation:
    check("fixture:elf-sha256", sha256_bytes(data) == FIXTURE_ELF_SHA256)
    rebuilt = fx.rebuild_fixture("p4-08-a")
    check("fixture:rebuild-identity", sha256_bytes(rebuilt) == FIXTURE_ELF_SHA256)
    regions = fx.fixture_regions(data)
    check("fixture:region-count", len(regions) == 5)
    check("fixture:region-kinds",
          [item.kind.value for item in regions]
          == ["rodata", "code", "rodata", "data", "bss"])
    model = fx.fixture_memory_model(data)
    check("fixture:model-entry-fetch",
          model.fetch(fx.FIXTURE_ENTRY, 32)
          == int.from_bytes(fx.fixture_image(data)[fx.FIXTURE_ENTRY:fx.FIXTURE_ENTRY + 4],
                            "little"))

    translation = fx.translate_fixture(data)
    check("translation:reachable-words", translation.reachable_words == 774)
    check("translation:program-sha256", translation.program_sha256 == PROGRAM_SHA256)
    check("translation:support-sha256", translation.support_sha256 == SUPPORT_SHA256)
    second = fx.translate_fixture(bytes(data))
    check("translation:deterministic",
          second.program_sha256 == translation.program_sha256
          and second.support_sha256 == translation.support_sha256)

    contract = abi.build_contract()
    profile = fx.fixture_profile()
    check("translation:profile-valid", contract.verify_profile(profile) == [])
    verifier = abi.GeneratedSourceVerifier(contract, profile)
    check("translation:program-compliant",
          verifier.verify_program(translation.program_text) == [])
    check("translation:support-compliant",
          verifier.verify_runtime_support(translation.support_text) == [])
    check("translation:profile-artifacts", verifier.check_profile_artifacts(ROOT) == [])
    check("translation:service-macros",
          all(f"#define OR_RT_SERVICE_FIXTURE_{name.upper()} UINT64_C({index})"
              in translation.program_text
              for index, name in enumerate(("exit", "in", "out", "ticks"), start=1)))
    cases = re.findall(r"case 0x([0-9a-f]{8})u:", translation.program_text)
    check("translation:all-reachable-emitted", len(cases) == translation.reachable_words)
    check("translation:no-duplicate-cases", len(cases) == len(set(cases)))
    check("translation:entry-case", f"case 0x{fx.FIXTURE_ENTRY:08x}u:" in translation.program_text)
    unreachable = set(analysis_reserved_addresses(data)) - set(
        f"0x{address:08x}" for address in
        fx.analyze_fixture(data)["frontier"]["reachable_addresses"])
    check("translation:reserved-words-not-emitted",
          all(f"case {address}u:" not in translation.program_text
              for address in unreachable))
    expect_fail("emission-unsupported-op",
                lambda: emit_instruction({"address": 0x1000, "op": "syscall", "fields": {}}),
                HostEmitError)

    ARTIFACTS["translation.json"] = (
        json.dumps(translation.to_document(), indent=2, sort_keys=True) + "\n").encode("utf-8")
    FINDINGS["translation"] = {
        "program_sha256": translation.program_sha256,
        "support_sha256": translation.support_sha256,
        "reachable_words": translation.reachable_words,
        "profile": profile.to_document(),
    }
    return translation


# ---------------------------------------------------------------------------
# Deterministic native build
# ---------------------------------------------------------------------------
def build_program(program_text: str, support_text: str, name: str) -> tuple[Any, pathlib.Path]:
    workspace = WORKSPACE / name
    for run_name in ("run1", "run2"):
        target = workspace / run_name
        if target.exists():
            shutil.rmtree(target)
    workspace.mkdir(parents=True, exist_ok=True)
    comparison = bp.build_generated_host(
        lambda: program_text,
        support_sources=(
            bp.BuildSource("p4_fixture_support.c",
                           bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
                           support_text.encode("utf-8")),
        ),
        config=bp.BuildConfig(fixture_id="p4-08-fixture-adapter", smoke_test=False,
                              run_count=2),
        workspace=workspace,
        keep_workspace=True,
    )
    return comparison, workspace / "run1" / "program.exe"


def run_executable(executable: pathlib.Path, *, repeats: int = REPLAY_COUNT) -> list[str]:
    outputs = []
    for _ in range(repeats):
        completed = subprocess.run([str(executable)], capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=600)
        if completed.returncode != 0:
            raise FixtureExecGateError(
                f"executable exited {completed.returncode}: {completed.stderr[:200]}")
        outputs.append(completed.stdout)
    return outputs


def parse_observable(stdout: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            fields[key] = value
    return fields


def transcript_from_hex(hex_text: str) -> list[str]:
    return bytes.fromhex(hex_text).decode("ascii").splitlines()


def audit_build(translation: fx.FixtureTranslation) -> pathlib.Path:
    comparison, executable = build_program(translation.program_text,
                                           translation.support_text, "fixture")
    check("build:status-ok",
          all(run.manifest.build_status is bp.BuildStatus.OK for run in comparison.runs))
    check("build:classification",
          comparison.classification is bp.BuildReproducibility.EXECUTABLE_REPRODUCIBLE)
    check("build:executable-reproducible", comparison.executable_reproducible is True)
    check("build:manifest-reproducible", comparison.manifest_reproducible)
    check("build:manifest-deterministic",
          comparison.runs[0].manifest.serialize() == comparison.runs[1].manifest.serialize())
    check("build:toolchain-identity",
          all(run.manifest.toolchain.compiler.identity == "clang-cl.exe"
              and run.manifest.toolchain.linker.identity == "lld-link.exe"
              for run in comparison.runs))
    manifest_text = comparison.runs[0].manifest.serialize().decode("utf-8")
    check("build:no-host-path-leak", str(ROOT) not in manifest_text)
    check("build:executable-sha256", sha256_file(executable) == EXECUTABLE_SHA256)
    outputs = comparison.runs[0].manifest.outputs
    check("build:artifact-set",
          sorted(item.name for item in outputs)
          == ["generated.obj", "p4_fixture_support.obj", "program.exe"])
    ARTIFACTS["build.json"] = (
        json.dumps({
            "stage": STAGE,
            "classification": comparison.classification.value,
            "executable_sha256": EXECUTABLE_SHA256,
            "manifest_sha256": comparison.runs[0].manifest.fingerprint(),
            "runs": [{
                "index": run.index,
                "manifest_sha256": run.manifest.fingerprint(),
                "outputs": [{"name": item.name, "kind": item.kind.value,
                             "sha256": item.sha256} for item in run.manifest.outputs],
                "compile_commands": [list(command) for command in run.manifest.compile_commands],
                "link_command": list(run.manifest.link_command),
            } for run in comparison.runs],
        }, indent=2, sort_keys=True) + "\n").encode("utf-8")
    FINDINGS["build"] = {
        "classification": comparison.classification.value,
        "executable_sha256": EXECUTABLE_SHA256,
        "manifest_sha256": comparison.runs[0].manifest.fingerprint(),
    }
    return executable


def audit_execution(executable: pathlib.Path) -> dict[str, str]:
    outputs = run_executable(executable)
    check("execution:replay-identical", len(set(outputs)) == 1)
    stdout = outputs[0]
    check("execution:stdout-sha256", sha256_bytes(stdout.encode("utf-8")) == STDOUT_SHA256)
    observable = parse_observable(stdout)
    check("execution:no-failure",
          observable.get("failed") == "0" and observable.get("failure") == "")
    check("execution:exit-status", observable.get("exit_status") == "0")
    check("execution:steps", observable.get("steps") == str(EXPECTED_STEPS))
    check("execution:pc", observable.get("pc") == EXPECTED_PC)
    check("execution:state-digest", observable.get("state_fnv1a64") == EXPECTED_STATE_DIGEST)
    transcript = transcript_from_hex(observable.get("output_hex", ""))
    check("execution:transcript-header", transcript[0] == "P4FIXTURE v1")
    check("execution:transcript-line-count", len(transcript) == 11)
    fixed = {}
    for line in transcript[1:]:
        key, value = line.split("=", 1)
        fixed[key] = value
    for key, value in EXPECTED.items():
        check(f"execution:transcript:{key}", fixed.get(key) == str(value))
    check("execution:output-bytes",
          observable.get("output_bytes") == str(len(bytes.fromhex(observable["output_hex"]))))
    ARTIFACTS["execution.json"] = (
        json.dumps({
            "stage": STAGE,
            "replays": REPLAY_COUNT,
            "stdout_sha256": STDOUT_SHA256,
            "observable": observable,
            "transcript_lines": transcript,
        }, indent=2, sort_keys=True) + "\n").encode("utf-8")
    FINDINGS["execution"] = {
        "stdout_sha256": STDOUT_SHA256,
        "steps": EXPECTED_STEPS,
        "pc": EXPECTED_PC,
        "state_fnv1a64": EXPECTED_STATE_DIGEST,
        "transcript": transcript,
    }
    return observable


# ---------------------------------------------------------------------------
# Platform adapter integration
# ---------------------------------------------------------------------------
class FixtureAdapter(pa.PlatformAdapter):
    def __init__(self, data: bytes, hooks: pa.PlatformHooks) -> None:
        self._regions = fx.fixture_regions(data)
        self._hooks = hooks

    def identity(self) -> pa.AdapterIdentity:
        return pa.AdapterIdentity("p4-fixture", rt.RUNTIME_ABI_VERSION,
                                  "P4-07 interactive fixture adapter")

    def memory_map(self) -> pa.MemoryMap:
        return pa.MemoryMap(self._regions)

    def timing_profile(self) -> pa.TimingProfile:
        return pa.TimingProfile(initial_ticks=0)

    def recorded_input(self) -> dio.RecordedInput:
        return dio.RecordedInput(console_input=fx.INPUT_PLAN, initial_ticks=0)

    def service_profile(self) -> pa.ServiceProfile:
        return pa.ServiceProfile(
            interfaces=(
                dio.io_interfaces()[0],  # or.runtime.stream_read
                dio.io_interfaces()[1],  # or.runtime.clock_ticks
            ),
            aliases=(
                svc_alias("fixture.out", 3, pa.svc.STREAM_WRITE_INTERFACE, (0,),
                          "fixture transcript byte to generic stream 0"),
                svc_alias("fixture.in", 2, "or.runtime.stream_read", (1,),
                          "fixture input byte from generic stream 1"),
                svc_alias("fixture.exit", 1, pa.svc.EXIT_INTERFACE, (),
                          "fixture termination to the generic exit interface"),
                svc_alias("fixture.ticks", 4, "or.runtime.clock_ticks", (),
                          "fixture virtual ticks to the generic clock interface"),
            ),
        )

    def hooks(self) -> pa.PlatformHooks:
        return self._hooks


def svc_alias(service_id: str, expected_numeric: int, target: str,
              bound: tuple[int, ...], description: str) -> pa.svc.ServiceAlias:
    numeric = fx.SERVICE_NUMERIC[service_id]
    if numeric != expected_numeric:
        raise FixtureExecGateError(f"service {service_id} numeric order changed")
    return pa.svc.ServiceAlias(
        source_service_id=service_id,
        source_version=rt.RUNTIME_ABI_VERSION,
        target_service_id=target,
        target_version=rt.RUNTIME_ABI_VERSION,
        bound_args=bound,
        description=description,
    )


def audit_adapter(data: bytes, translation: fx.FixtureTranslation) -> None:
    graphics = ga.HeadlessGraphics(ga.GraphicsCapabilities(("RGBA8",), 8, 8))
    audio = ga.HeadlessAudio(ga.AudioCapabilities(("U8",), (8000,), 1, 64))
    adapter = FixtureAdapter(data, pa.PlatformHooks(
        graphics=ga.GraphicsBoundaryHook(graphics),
        audio=ga.AudioBoundaryHook(audio)))
    check("adapter:valid", pa.validate_adapter(adapter) == [])
    bound = pa.bind_platform(adapter)
    check("adapter:interface-ids",
          bound.interface_ids == ("or.runtime.exit", "or.runtime.stream_write",
                                  "or.runtime.stream_read", "or.runtime.clock_ticks"))
    check("adapter:capabilities",
          dict(bound.capabilities) == {
              "memory": True, "timing_virtual": True, "input_streams": True,
              "event_delivery": False, "console_output": True,
              "graphics_hook": True, "audio_hook": True, "platform_services": False})
    check("adapter:negative-claims",
          dict(bound.claims)["console_compatibility"] is False)
    check("adapter:memory-fetch",
          bound.memory.fetch(fx.FIXTURE_ENTRY, 32)
          == int.from_bytes(fx.fixture_image(data)[fx.FIXTURE_ENTRY:fx.FIXTURE_ENTRY + 4],
                            "little"))
    check("adapter:out-alias", bound.mediator.dispatch("fixture.out", (0x41,)).ok)
    check("adapter:out-byte", bound.io.console.output == b"A")
    check("adapter:in-alias", bound.mediator.dispatch("fixture.in", ()).value == fx.INPUT_PLAN[0])
    check("adapter:ticks-alias",
          bound.mediator.dispatch("fixture.ticks", ()).value == 0)
    bound.io.advance_ticks(5)
    check("adapter:ticks-read",
          bound.mediator.dispatch("fixture.ticks", ()).value == 5)
    check("adapter:exit-alias", bound.mediator.dispatch("fixture.exit", (0,)).ok)
    check("adapter:post-exit-fails-closed",
          bound.mediator.dispatch("fixture.ticks", ()).failure.code
          is rt.RuntimeFailureCode.TRAP)
    fresh = pa.bind_platform(FixtureAdapter(data, pa.PlatformHooks()))
    check("adapter:unknown-fails-closed",
          fresh.mediator.dispatch("fixture.none", ()).failure.code
          is rt.RuntimeFailureCode.UNKNOWN_HOST_SERVICE)
    check("adapter:profile-matches-translation",
          all(f"#define OR_RT_SERVICE_FIXTURE_{name.upper()} "
              f"UINT64_C({fx.SERVICE_NUMERIC[f'fixture.{name}']})"
              in translation.program_text
              for name in ("exit", "in", "out", "ticks")))
    check("adapter:document-roundtrip",
          json.loads(canonical_json(bound.to_document())) == bound.to_document())
    ARTIFACTS["adapter.json"] = (
        json.dumps({
            "stage": STAGE,
            "capabilities": dict(bound.capabilities),
            "claims": dict(bound.claims),
            "interface_ids": list(bound.interface_ids),
            "profile": fx.fixture_profile().to_document(),
            "adapter_fingerprint": bound.fingerprint(),
        }, indent=2, sort_keys=True) + "\n").encode("utf-8")
    FINDINGS["adapter"] = {
        "capabilities": dict(bound.capabilities),
        "fingerprint": bound.fingerprint(),
    }


# ---------------------------------------------------------------------------
# Fail-closed negatives
# ---------------------------------------------------------------------------
def audit_negatives(translation: fx.FixtureTranslation) -> None:
    rows: list[dict[str, Any]] = []

    step_text = translation.program_text.replace(
        "#define OR_MAX_STEPS 20000000u", "#define OR_MAX_STEPS 10u")
    check("negative:step-limit-patched", step_text != translation.program_text)
    _, executable = build_program(step_text, translation.support_text, "neg-step")
    observable = parse_observable(run_executable(executable, repeats=1)[0])
    check("negative:step-limit", observable.get("failed") == "1"
          and observable.get("failure") == "step limit exceeded"
          and observable.get("exit_status") == "4294967295")
    rows.append({"name": "step-limit", "failed": observable.get("failed"),
                 "failure": observable.get("failure")})

    marker = f"    case 0x{fx.FIXTURE_ENTRY:08x}u:"
    store_text = translation.program_text.replace(
        marker, marker + "\n        or_store(0x30000000u, 4u, 1u);", 1)
    check("negative:unmapped-store-patched", store_text != translation.program_text)
    _, executable = build_program(store_text, translation.support_text, "neg-memory")
    observable = parse_observable(run_executable(executable, repeats=1)[0])
    check("negative:unmapped-store", observable.get("failed") == "1"
          and observable.get("failure") == "MEMORY_OUT_OF_RANGE")
    rows.append({"name": "unmapped-store", "failed": observable.get("failed"),
                 "failure": observable.get("failure")})

    ARTIFACTS["negatives.json"] = (
        json.dumps({"stage": STAGE, "negatives": rows},
                   indent=2, sort_keys=True) + "\n").encode("utf-8")
    FINDINGS["negatives"] = rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="P4-08 adapter execution gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase4/evidence/P4-08")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, ARTIFACTS
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    ARTIFACTS = {}

    print("=== P4-08 Platform-Adapter Execution Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("source_integrity")
        audit_source_integrity()
        banner("translation")
        data = fx.load_fixture_elf()
        translation = audit_translation(data)
        banner("build")
        executable = audit_build(translation)
        banner("execution")
        audit_execution(executable)
        banner("adapter")
        audit_adapter(data, translation)
        banner("negatives")
        audit_negatives(translation)
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
    (EVIDENCE_DIR / "p4_08_tests.json").write_bytes(
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
