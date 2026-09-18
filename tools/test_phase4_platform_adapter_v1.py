#!/usr/bin/env python3
"""OpenRecomp Phase-4 platform adapter interface gate (P4-05).

Proves the architecture-neutral platform-adapter contract in
``.openrecomp-phase4/src/p4_platform_adapter_v1.py``:

* identity, memory-map, timing, service-profile and optional graphics/audio
  hook slots, with adapter ids as the only platform names;
* the service profile may only declare interfaces from the *generic*
  catalog (P4-03 base plus P4-04 I/O); platform behaviour is expressed
  through aliases and handlers, never by adding platform names to the core;
* host clock sources, invalid memory maps and unbindable service profiles
  fail closed at validation and binding;
* binding composes the adapter with the P4-02 guest memory model, the P4-04
  deterministic I/O runtime and the P4-03 mediator, producing an explicit
  capabilities document and explicit negative compatibility claims
  (``console_compatibility: false``, ``arbitrary_binary_compatibility:
  false``);
* optional graphics/audio hooks receive the P2-08 frame/audio contracts and
  are never mandatory to the core.

It emits::

    OPENRECOMP_P4_05=PASS
    OPENRECOMP_PHASE4_PLATFORM_ADAPTER_V1=PASS tests=<count>
    OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase4_platform_adapter_v1.py
    python tools/test_phase4_platform_adapter_v1.py --evidence-dir .openrecomp-phase4/evidence/P4-05
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
for candidate in (str(ROOT), str(ROOT / ".openrecomp-phase4" / "src")):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import p4_deterministic_io_v1 as dio  # noqa: E402
import p4_guest_memory_v1 as gm  # noqa: E402
import p4_platform_adapter_v1 as pa  # noqa: E402
import p4_runtime_services_v1 as svc  # noqa: E402
from openrecomp import runtime_abi as rt  # noqa: E402
from openrecomp.program_model import canonical_json  # noqa: E402

STAGE = "P4-05"
STAGE_MARKER = "OPENRECOMP_P4_05"
FEATURE_MARKER = "OPENRECOMP_PHASE4_PLATFORM_ADAPTER_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY"

SOURCE_SUMS = "SOURCE_SHA256SUMS.txt"
SOURCE_SUMS_SHA256 = "76f77bbc97780afe9c2b41a0cb89b5323ab22450c4b2a368dd03fb4d7bbe1095"
SOURCE_SUMS_ENTRIES = 134
P3_SUMS = ".openrecomp-phase3/SOURCE_SHA256SUMS.txt"
P3_SUMS_SHA256 = "a7d0953c0f02276ad233db50e326d9e71a3136542648bb04a95de9d3e05e2488"
P3_SUMS_ENTRIES = 24
P4_SUMS = ".openrecomp-phase4/SOURCE_SHA256SUMS.txt"
MODULE_PATH = ".openrecomp-phase4/src/p4_platform_adapter_v1.py"

EXPECTED_GENERIC_IDS = (
    "or.runtime.exit",
    "or.runtime.stream_write",
    "or.runtime.stream_read",
    "or.runtime.clock_ticks",
    "or.runtime.input_poll",
)
PLATFORM_IMPORT_TOKENS = (
    "SDL", "Vulkan", "vulkan", "Direct3D", "d3d", "OpenGL", "opengl",
    "XAudio", "WASAPI", "Rt64", "RT64",
)
FORBIDDEN_CORE_TOKENS = (
    "coremark", "mips", "ps1", "ps2", "psp", "n64", "r5900", "emotion",
    "ee_", "uart",
)

RESULTS: list[dict[str, str]] = []
FINDINGS: dict[str, Any] = {}


def check(label: str, condition: bool) -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        print(f"FAIL: {label}", flush=True)
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}", flush=True)


def expect_fail(label: str, thunk, error_type=pa.PlatformAdapterError) -> None:
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


# --- test adapters ----------------------------------------------------------
class RecordingGraphicsHook(pa.GraphicsHook):
    def __init__(self) -> None:
        self.frames: list[rt.RuntimeFrame] = []

    def submit_frame(self, frame: rt.RuntimeFrame) -> None:
        self.frames.append(frame)

    def to_document(self) -> dict[str, Any]:
        return {"hook_id": "graphics", "frames": len(self.frames),
                "checksums": [frame.checksum() for frame in self.frames]}


class RecordingAudioHook(pa.AudioHook):
    def __init__(self) -> None:
        self.buffers: list[rt.RuntimeAudio] = []

    def submit_audio(self, audio: rt.RuntimeAudio) -> None:
        self.buffers.append(audio)

    def to_document(self) -> dict[str, Any]:
        return {"hook_id": "audio", "buffers": len(self.buffers),
                "checksums": [audio.checksum() for audio in self.buffers]}


def io_interface(service_id: str, arg_types: tuple[str, ...],
                 result_type: str | None) -> svc.RuntimeServiceInterface:
    return svc.RuntimeServiceInterface(service_id, rt.RUNTIME_ABI_VERSION,
                                       arg_types, result_type, False,
                                       f"Generic interface {service_id}.")


class ReferenceAdapter(pa.PlatformAdapter):
    def __init__(self, hooks: pa.PlatformHooks | None = None) -> None:
        self._hooks = hooks or pa.PlatformHooks()

    def identity(self) -> pa.AdapterIdentity:
        return pa.AdapterIdentity("synthetic-reference", rt.RUNTIME_ABI_VERSION,
                                  "bounded synthetic reference adapter")

    def memory_map(self) -> pa.MemoryMap:
        return pa.MemoryMap((
            gm.region("code", 0x1000, 0x40, gm.RegionKind.CODE,
                      file_data=bytes(range(0x40))),
            gm.region("data", 0x2000, 0x40, gm.RegionKind.DATA),
        ))

    def timing_profile(self) -> pa.TimingProfile:
        return pa.TimingProfile(initial_ticks=7)

    def recorded_input(self) -> dio.RecordedInput:
        return dio.RecordedInput(console_input=b"xy", initial_ticks=7)

    def service_profile(self) -> pa.ServiceProfile:
        return pa.ServiceProfile(
            interfaces=(
                io_interface("or.runtime.stream_read", ("u32",), "u32"),
                io_interface("or.runtime.clock_ticks", (), "u64"),
                io_interface("or.runtime.input_poll", (), "u32"),
            ),
            aliases=(svc.ServiceAlias(
                "synthetic.out", rt.RUNTIME_ABI_VERSION,
                svc.STREAM_WRITE_INTERFACE, rt.RUNTIME_ABI_VERSION, (0,),
                "synthetic raw output alias onto the generic stream interface"),),
        )

    def hooks(self) -> pa.PlatformHooks:
        return self._hooks


class NoIdentityAdapter(pa.PlatformAdapter):
    def memory_map(self) -> pa.MemoryMap:
        return pa.MemoryMap((gm.region("d", 0, 16, gm.RegionKind.DATA),))


class BadMemoryAdapter(pa.PlatformAdapter):
    def identity(self) -> pa.AdapterIdentity:
        return pa.AdapterIdentity("bad-memory", rt.RUNTIME_ABI_VERSION, "overlapping regions")

    def memory_map(self) -> pa.MemoryMap:
        return pa.MemoryMap((
            gm.region("a", 0, 16, gm.RegionKind.DATA),
            gm.region("b", 8, 16, gm.RegionKind.DATA),
        ))


class HostTimingAdapter(pa.PlatformAdapter):
    def identity(self) -> pa.AdapterIdentity:
        return pa.AdapterIdentity("host-timing", rt.RUNTIME_ABI_VERSION, "host clock")

    def memory_map(self) -> pa.MemoryMap:
        return pa.MemoryMap((gm.region("d", 0, 16, gm.RegionKind.DATA),))

    def timing_profile(self) -> pa.TimingProfile:
        return pa.TimingProfile(tick_source="host")


class BadServiceAdapter(pa.PlatformAdapter):
    def identity(self) -> pa.AdapterIdentity:
        return pa.AdapterIdentity("bad-service", rt.RUNTIME_ABI_VERSION, "unknown interface")

    def memory_map(self) -> pa.MemoryMap:
        return pa.MemoryMap((gm.region("d", 0, 16, gm.RegionKind.DATA),))

    def service_profile(self) -> pa.ServiceProfile:
        return pa.ServiceProfile(interfaces=(
            io_interface("or.runtime.mystery", (), None),))


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
# Contract surface
# ---------------------------------------------------------------------------
def audit_contract() -> None:
    document = pa.core_contract_document()
    check("contract:name", document["name"] == "openrecomp-platform-adapter")
    check("contract:version", document["version"] == rt.RUNTIME_ABI_VERSION)
    check("contract:id-pattern", document["adapter_id_pattern"] == r"^[a-z][a-z0-9_-]*$")
    check("contract:timing-sources", tuple(document["timing_sources"]) == ("virtual",))
    check("contract:generic-catalog",
          tuple(interface.service_id for interface in pa.generic_interfaces())
          == EXPECTED_GENERIC_IDS)
    check("contract:generic-catalog-includes-io",
          {"or.runtime.stream_read", "or.runtime.clock_ticks", "or.runtime.input_poll"}
          <= set(EXPECTED_GENERIC_IDS))
    check("contract:hooks", tuple(document["optional_hooks"]) == ("graphics", "audio"))
    check("contract:negative-claims",
          document["claims"] == {"console_compatibility": False,
                                 "arbitrary_binary_compatibility": False})
    check("contract:fingerprint-stable",
          pa.core_contract_fingerprint() == pa.core_contract_fingerprint())
    text = canonical_json(document).lower()
    check("contract:no-console-tokens",
          not any(token in text for token in FORBIDDEN_CORE_TOKENS))
    check("contract:no-platform-tokens",
          not any(token.lower() in text for token in PLATFORM_IMPORT_TOKENS))

    base = pa.PlatformAdapter()
    check("base:timing-default", base.timing_profile().tick_source == "virtual")
    check("base:input-default", isinstance(base.recorded_input(), dio.RecordedInput))
    check("base:service-default", not base.service_profile().interfaces)
    check("base:hooks-default", base.hooks().graphics is None and base.hooks().audio is None)
    expect_fail("base:identity-not-implemented", lambda: base.identity(),
                NotImplementedError)
    expect_fail("base:memory-not-implemented", lambda: base.memory_map(),
                NotImplementedError)
    FINDINGS["contract"] = {"fingerprint": pa.core_contract_fingerprint(),
                            "generic_interfaces": list(EXPECTED_GENERIC_IDS)}


# ---------------------------------------------------------------------------
# Component validation
# ---------------------------------------------------------------------------
def audit_components() -> None:
    identity = pa.AdapterIdentity("test-adapter", rt.RUNTIME_ABI_VERSION, "x")
    check("identity:valid", identity.adapter_id == "test-adapter")
    check("identity:document", identity.to_document()["contract"]["name"]
          == "openrecomp-platform-adapter")
    expect_fail("identity:bad-id", lambda: pa.AdapterIdentity("Bad Id", rt.RUNTIME_ABI_VERSION, "x"))
    expect_fail("identity:bad-version", lambda: pa.AdapterIdentity("a", "9.0.0", "x"))
    expect_fail("identity:empty-description", lambda: pa.AdapterIdentity("a", rt.RUNTIME_ABI_VERSION, ""))

    memory = pa.MemoryMap((gm.region("code", 0, 16, gm.RegionKind.CODE),))
    check("memory:model", memory.model().fetch(0, 8) == 0)
    expect_fail("memory:empty", lambda: pa.MemoryMap(()))
    expect_fail("memory:overlap", lambda: pa.MemoryMap((
        gm.region("a", 0, 16, gm.RegionKind.DATA),
        gm.region("b", 8, 16, gm.RegionKind.DATA))))
    expect_fail("memory:bad-entry", lambda: pa.MemoryMap(("region",)))

    check("timing:virtual-default", pa.TimingProfile().tick_source == "virtual")
    expect_fail("timing:host", lambda: pa.TimingProfile(tick_source="host"))
    expect_fail("timing:negative-ticks", lambda: pa.TimingProfile(initial_ticks=-1))

    clock_interface = io_interface("or.runtime.clock_ticks", (), "u64")
    profile = pa.ServiceProfile(interfaces=(clock_interface,))
    check("profile:interface", profile.interfaces[0].service_id == "or.runtime.clock_ticks")
    expect_fail("profile:unknown-interface",
                lambda: pa.ServiceProfile(interfaces=(
                    io_interface("or.runtime.mystery", (), None),)))
    expect_fail("profile:handler-without-interface", lambda: pa.ServiceProfile(
        handlers={"or.runtime.clock_ticks": lambda _args: 0}))
    expect_fail("profile:terminating-handler", lambda: pa.ServiceProfile(
        interfaces=(svc.RuntimeServiceInterface(
            "or.runtime.exit", rt.RUNTIME_ABI_VERSION, ("u32",), None, True, "exit"),),
        handlers={"or.runtime.exit": lambda _args: None}))
    expect_fail("profile:alias-unknown-target", lambda: pa.ServiceProfile(
        interfaces=(clock_interface,),
        aliases=(svc.ServiceAlias("x.out", rt.RUNTIME_ABI_VERSION,
                                  "or.runtime.none", rt.RUNTIME_ABI_VERSION, (), "x"),)))
    check("profile:document", pa.ServiceProfile(interfaces=(clock_interface,))
          .to_document()["interfaces"][0]["service_id"] == "or.runtime.clock_ticks")
    FINDINGS["components"] = {
        "interface_ids": list(EXPECTED_GENERIC_IDS),
    }


# ---------------------------------------------------------------------------
# Adapter validation and binding
# ---------------------------------------------------------------------------
def audit_binding() -> None:
    check("validate:reference", pa.validate_adapter(ReferenceAdapter()) == [])
    check("validate:not-adapter", pa.validate_adapter(object())
          == ["adapter must be a PlatformAdapter instance"])
    check("validate:no-identity",
          any("identity" in problem for problem in pa.validate_adapter(NoIdentityAdapter())))
    check("validate:bad-memory",
          any("memory" in problem for problem in pa.validate_adapter(BadMemoryAdapter())))
    check("validate:host-timing",
          any("timing" in problem for problem in pa.validate_adapter(HostTimingAdapter())))
    check("validate:bad-service",
          any("service_profile" in problem for problem in pa.validate_adapter(BadServiceAdapter())))
    expect_fail("bind:not-adapter", lambda: pa.bind_platform(object()))
    expect_fail("bind:no-identity", lambda: pa.bind_platform(NoIdentityAdapter()))
    expect_fail("bind:bad-memory", lambda: pa.bind_platform(BadMemoryAdapter()))
    expect_fail("bind:host-timing", lambda: pa.bind_platform(HostTimingAdapter()))
    expect_fail("bind:bad-service", lambda: pa.bind_platform(BadServiceAdapter()))

    bound = pa.bind_platform(ReferenceAdapter())
    check("bound:identity", bound.identity.adapter_id == "synthetic-reference")
    check("bound:memory-code", bound.memory.fetch(0x1000, 32)
          == int.from_bytes(bytes(range(4)), "little"))
    check("bound:memory-write-data", bound.memory.try_write(0x2000, 0x1234, 16).ok)
    check("bound:io-input", bound.io.read_stream(dio.STREAM_CONSOLE_IN) == ord("x"))
    check("bound:interface-ids",
          bound.interface_ids == ("or.runtime.exit", "or.runtime.stream_write",
                                  "or.runtime.stream_read", "or.runtime.clock_ticks",
                                  "or.runtime.input_poll"))
    check("bound:capabilities",
          dict(bound.capabilities) == {
              "memory": True, "timing_virtual": True, "input_streams": True,
              "event_delivery": True, "console_output": True,
              "graphics_hook": False, "audio_hook": False,
              "platform_services": False})
    check("bound:claims",
          dict(bound.claims) == {"console_compatibility": False,
                                 "arbitrary_binary_compatibility": False,
                                 "cycle_accuracy": False})
    check("bound:alias-output", bound.mediator.dispatch("synthetic.out", (0x41,)).ok)
    check("bound:console-output", bound.io.console.output == b"A")
    check("bound:clock", bound.mediator.dispatch("or.runtime.clock_ticks", ()).value == 7)
    check("bound:poll-empty",
          bound.mediator.dispatch("or.runtime.input_poll", ()).value == dio.NO_EVENT_SENTINEL)
    check("bound:read", bound.mediator.dispatch("or.runtime.stream_read", (1,)).value
          == ord("y"))
    check("bound:unknown-fails-closed",
          bound.mediator.dispatch("synthetic.none", ()).failure.code
          is rt.RuntimeFailureCode.UNKNOWN_HOST_SERVICE)
    check("bound:document-roundtrip",
          json.loads(canonical_json(bound.to_document())) == bound.to_document())
    check("bound:document-no-host-path",
          not any(token in canonical_json(bound.to_document())
                  for token in ("C:\\", "D:\\", "/home/")))

    graphics = RecordingGraphicsHook()
    audio = RecordingAudioHook()
    hooked = pa.bind_platform(ReferenceAdapter(pa.PlatformHooks(graphics=graphics,
                                                                audio=audio)))
    frame = rt.RuntimeFrame(2, 1, rt.RuntimePixelFormat.RGBA8, bytes(range(8)), sequence=1)
    hooked.hooks.graphics.submit_frame(frame)
    sound = rt.RuntimeAudio(rt.RuntimeSampleFormat.U8, 8000, 1, 4, b"\x01\x02\x03\x04")
    hooked.hooks.audio.submit_audio(sound)
    check("hooks:graphics-capability", bool(hooked.capabilities["graphics_hook"]))
    check("hooks:audio-capability", bool(hooked.capabilities["audio_hook"]))
    check("hooks:graphics-recorded",
          hooked.hooks.graphics.to_document() == {
              "hook_id": "graphics", "frames": 1,
              "checksums": [frame.checksum()]})
    check("hooks:audio-recorded",
          hooked.hooks.audio.to_document() == {
              "hook_id": "audio", "buffers": 1,
              "checksums": [sound.checksum()]})
    check("hooks:optional-in-core", not bound.capabilities["graphics_hook"])

    first = pa.bind_platform(ReferenceAdapter())
    second = pa.bind_platform(ReferenceAdapter())
    check("determinism:document",
          canonical_json(first.to_document()) == canonical_json(second.to_document()))
    check("determinism:fingerprint", first.fingerprint() == second.fingerprint())

    module_source = read_text(ROOT / MODULE_PATH)
    imported_platforms = [token for token in PLATFORM_IMPORT_TOKENS
                          if token in module_source]
    check("containment:no-platform-imports", not imported_platforms)
    check("containment:no-fixture-tokens",
          not any(token in module_source.lower() for token in FORBIDDEN_CORE_TOKENS))
    FINDINGS["binding"] = {
        "capabilities": dict(bound.capabilities),
        "fingerprint": first.fingerprint(),
        "interface_ids": list(bound.interface_ids),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="P4-05 platform adapter gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase4/evidence/P4-05")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}

    print("=== P4-05 Platform Adapter Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("source_integrity")
        audit_source_integrity()
        banner("contract")
        audit_contract()
        banner("components")
        audit_components()
        banner("binding")
        audit_binding()
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
    (EVIDENCE_DIR / "p4_05_tests.json").write_bytes(
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
