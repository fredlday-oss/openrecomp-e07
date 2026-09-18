#!/usr/bin/env python3
"""OpenRecomp Phase-4 graphics/audio abstraction boundary gate (P4-06).

Proves the reusable graphics/audio boundaries in
``.openrecomp-phase4/src/p4_graphics_audio_v1.py``:

* capability declarations for pixel/sample formats, dimensions, rates and
  bounds, validated against the P2-08 neutral frame/audio contracts;
* adapter interfaces (``GraphicsBoundary``/``AudioBoundary``) with fail-closed
  submission validation and bounded, deterministic presentation ledgers
  (``HeadlessGraphics``/``HeadlessAudio``) plus accept-nothing reference
  boundaries (``NullGraphics``/``NullAudio``);
* P4-05 hook routing (``GraphicsBoundaryHook``/``AudioBoundaryHook``) and
  binding through the platform adapter with the graphics/audio capabilities
  reflected;
* no renderer or audio system (RT64, SDL, Vulkan, Direct3D, XAudio2, WASAPI
  or any other) is imported or required; the contract records
  ``renderer_backend_mandatory: false`` and ``audio_backend_mandatory:
  false``.

It emits::

    OPENRECOMP_P4_06=PASS
    OPENRECOMP_PHASE4_GRAPHICS_AUDIO_V1=PASS tests=<count>
    OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase4_graphics_audio_v1.py
    python tools/test_phase4_graphics_audio_v1.py --evidence-dir .openrecomp-phase4/evidence/P4-06
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

import p4_graphics_audio_v1 as ga  # noqa: E402
import p4_guest_memory_v1 as gm  # noqa: E402
import p4_platform_adapter_v1 as pa  # noqa: E402
from openrecomp import runtime_abi as rt  # noqa: E402
from openrecomp.program_model import canonical_json  # noqa: E402

STAGE = "P4-06"
STAGE_MARKER = "OPENRECOMP_P4_06"
FEATURE_MARKER = "OPENRECOMP_PHASE4_GRAPHICS_AUDIO_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY"

SOURCE_SUMS = "SOURCE_SHA256SUMS.txt"
SOURCE_SUMS_SHA256 = "76f77bbc97780afe9c2b41a0cb89b5323ab22450c4b2a368dd03fb4d7bbe1095"
SOURCE_SUMS_ENTRIES = 134
P3_SUMS = ".openrecomp-phase3/SOURCE_SHA256SUMS.txt"
P3_SUMS_SHA256 = "a7d0953c0f02276ad233db50e326d9e71a3136542648bb04a95de9d3e05e2488"
P3_SUMS_ENTRIES = 24
P4_SUMS = ".openrecomp-phase4/SOURCE_SHA256SUMS.txt"
MODULE_PATH = ".openrecomp-phase4/src/p4_graphics_audio_v1.py"

EXPECTED_PIXEL_FORMATS = ("RGBA8", "BGRA8", "RGB565", "INDEX8", "GRAY8")
EXPECTED_SAMPLE_FORMATS = ("U8", "S16LE", "S16BE", "S32LE", "F32LE", "F32BE")
BACKEND_TOKENS = (
    "SDL", "sdl_", "Vulkan", "vulkan", "Direct3D", "d3d", "OpenGL", "opengl",
    "XAudio", "WASAPI", "rt64", "Rt64", "gfx", "wgpu", "Metal",
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


def expect_fail(label: str, thunk, error_type=ga.GraphicsAudioError) -> None:
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


def frame(width: int = 2, height: int = 1, pixel_format: rt.RuntimePixelFormat =
          rt.RuntimePixelFormat.RGBA8, sequence: int = 1) -> rt.RuntimeFrame:
    payload = bytes(range(width * height * (4 if pixel_format is rt.RuntimePixelFormat.RGBA8
                                             else 1)))
    return rt.RuntimeFrame(width, height, pixel_format, payload, sequence=sequence)


_SAMPLE_BYTES = {"U8": 1, "S16LE": 2, "S16BE": 2, "S32LE": 4, "F32LE": 4, "F32BE": 4}


def sound(sample_count: int = 4, sample_format: rt.RuntimeSampleFormat =
          rt.RuntimeSampleFormat.U8, sequence: int = 1) -> rt.RuntimeAudio:
    size = sample_count * _SAMPLE_BYTES[sample_format.value]
    return rt.RuntimeAudio(sample_format, 8000, 1, sample_count,
                           bytes(index % 256 for index in range(size)), sequence=sequence)


class BoundaryAdapter(pa.PlatformAdapter):
    def __init__(self, hooks: pa.PlatformHooks) -> None:
        self._hooks = hooks

    def identity(self) -> pa.AdapterIdentity:
        return pa.AdapterIdentity("boundary-test", rt.RUNTIME_ABI_VERSION,
                                  "graphics/audio boundary test adapter")

    def memory_map(self) -> pa.MemoryMap:
        return pa.MemoryMap((gm.region("data", 0, 16, gm.RegionKind.DATA),))

    def hooks(self) -> pa.PlatformHooks:
        return self._hooks


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
# Contract and capabilities
# ---------------------------------------------------------------------------
def audit_contract() -> None:
    document = ga.contract_document()
    check("contract:name", document["name"] == "openrecomp-graphics-audio-boundary")
    check("contract:version", document["version"] == rt.RUNTIME_ABI_VERSION)
    check("contract:pixel-formats", tuple(document["pixel_formats"])
          == EXPECTED_PIXEL_FORMATS)
    check("contract:sample-formats", tuple(document["sample_formats"])
          == EXPECTED_SAMPLE_FORMATS)
    check("contract:limits", document["limits"] == {
        "max_dimension": 16384, "max_channels": 64, "max_sample_rate": 384000,
        "max_samples_per_buffer": 1 << 20})
    check("contract:no-mandatory-backend",
          document["claims"] == {
              "renderer_backend_mandatory": False,
              "audio_backend_mandatory": False,
              "backend_integrations_are_future_adapters": True})
    check("contract:fingerprint-stable",
          ga.contract_fingerprint() == ga.contract_fingerprint())
    text = canonical_json(document).lower()
    check("contract:no-backend-tokens",
          not any(token.lower() in text for token in BACKEND_TOKENS))

    graphics = ga.GraphicsCapabilities(("RGBA8", "GRAY8"), 320, 240, capacity=2)
    check("graphics-caps:supports", graphics.supports(320, 240, "RGBA8"))
    check("graphics-caps:rejects-dimensions", not graphics.supports(321, 240, "RGBA8"))
    check("graphics-caps:rejects-format", not graphics.supports(320, 240, "RGB565"))
    check("graphics-caps:empty-formats",
          not ga.GraphicsCapabilities(tuple(), 1, 1).supports(1, 1, "RGBA8"))
    check("graphics-caps:document", graphics.to_document()["max_width"] == 320)
    expect_fail("graphics-caps:unknown-format",
                lambda: ga.GraphicsCapabilities(("YUV420",), 1, 1))
    expect_fail("graphics-caps:zero-dimension",
                lambda: ga.GraphicsCapabilities(("RGBA8",), 0, 1))
    expect_fail("graphics-caps:oversized",
                lambda: ga.GraphicsCapabilities(("RGBA8",), 20000, 1))
    expect_fail("graphics-caps:zero-capacity",
                lambda: ga.GraphicsCapabilities(("RGBA8",), 1, 1, capacity=0))

    audio = ga.AudioCapabilities(("U8", "S16LE"), (8000, 44100), 2, 16, capacity=2)
    check("audio-caps:supports", audio.supports("U8", 8000, 1, 4))
    check("audio-caps:rejects-rate", not audio.supports("U8", 11025, 1, 4))
    check("audio-caps:rejects-channels", not audio.supports("U8", 8000, 3, 4))
    check("audio-caps:rejects-samples", not audio.supports("U8", 8000, 1, 17))
    check("audio-caps:rejects-format", not audio.supports("F32LE", 8000, 1, 4))
    expect_fail("audio-caps:unknown-format",
                lambda: ga.AudioCapabilities(("MP3",), (8000,), 1, 1))
    expect_fail("audio-caps:duplicate-rates",
                lambda: ga.AudioCapabilities(("U8",), (8000, 8000), 1, 1))
    expect_fail("audio-caps:zero-rate",
                lambda: ga.AudioCapabilities(("U8",), (0,), 1, 1))
    expect_fail("audio-caps:bad-channels",
                lambda: ga.AudioCapabilities(("U8",), (8000,), 65, 1))
    expect_fail("audio-caps:bad-samples",
                lambda: ga.AudioCapabilities(("U8",), (8000,), 1, 1 << 21))
    FINDINGS["contract"] = {
        "fingerprint": ga.contract_fingerprint(),
        "pixel_formats": list(EXPECTED_PIXEL_FORMATS),
        "sample_formats": list(EXPECTED_SAMPLE_FORMATS),
    }


# ---------------------------------------------------------------------------
# Graphics boundary
# ---------------------------------------------------------------------------
def audit_graphics() -> None:
    boundary = ga.HeadlessGraphics(ga.GraphicsCapabilities(
        ("RGBA8", "GRAY8"), 8, 8, capacity=2))
    first = frame(2, 1, rt.RuntimePixelFormat.RGBA8, sequence=1)
    boundary.present(first)
    boundary.present(frame(1, 1, rt.RuntimePixelFormat.GRAY8, sequence=2))
    check("graphics:record-count", len(boundary.presentations) == 2)
    check("graphics:record-fields",
          boundary.presentations[0].to_document() == {
              "sequence": 1, "width": 2, "height": 1, "pixel_format": "RGBA8",
              "checksum": first.checksum()})
    check("graphics:document-ledger",
          boundary.to_document()["presentation_count"] == 2
          and boundary.to_document()["output"] is None)
    expect_fail("graphics:capacity",
                lambda: boundary.present(frame(1, 1, rt.RuntimePixelFormat.RGBA8, 3)))
    expect_fail("graphics:unsupported-format", lambda: ga.HeadlessGraphics(
        ga.GraphicsCapabilities(("GRAY8",), 8, 8)).present(
            frame(1, 1, rt.RuntimePixelFormat.RGBA8)))
    expect_fail("graphics:unsupported-dimension", lambda: ga.HeadlessGraphics(
        ga.GraphicsCapabilities(("RGBA8",), 4, 4)).present(
            frame(5, 1, rt.RuntimePixelFormat.RGBA8)))
    expect_fail("graphics:not-a-frame", lambda: ga.HeadlessGraphics(
        ga.GraphicsCapabilities(("RGBA8",), 8, 8)).present("frame"))
    expect_fail("graphics:bad-capabilities", lambda: ga.HeadlessGraphics("caps"))

    null = ga.NullGraphics()
    check("graphics:null-capabilities-empty", null.capabilities().pixel_formats == ())
    expect_fail("graphics:null-rejects",
                lambda: null.present(frame(1, 1, rt.RuntimePixelFormat.RGBA8)))
    check("graphics:null-document", null.to_document()["boundary"] == "null")

    fresh_a = ga.HeadlessGraphics(ga.GraphicsCapabilities(("RGBA8",), 4, 4))
    fresh_b = ga.HeadlessGraphics(ga.GraphicsCapabilities(("RGBA8",), 4, 4))
    for boundary_ in (fresh_a, fresh_b):
        boundary_.present(frame(1, 1, rt.RuntimePixelFormat.RGBA8, 1))
        boundary_.present(frame(2, 2, rt.RuntimePixelFormat.RGBA8, 2))
    check("graphics:deterministic-document",
          canonical_json(fresh_a.to_document()) == canonical_json(fresh_b.to_document()))
    check("graphics:deterministic-fingerprint",
          fresh_a.fingerprint() == fresh_b.fingerprint())
    check("graphics:ledger-sensitive",
          fresh_a.to_document()["ledger_sha256"] != boundary.to_document()["ledger_sha256"])
    FINDINGS["graphics"] = {
        "ledger_sha256": fresh_a.to_document()["ledger_sha256"],
        "fingerprint": fresh_a.fingerprint(),
    }


# ---------------------------------------------------------------------------
# Audio boundary
# ---------------------------------------------------------------------------
def audit_audio() -> None:
    boundary = ga.HeadlessAudio(ga.AudioCapabilities(("U8", "S16LE"), (8000, 44100),
                                                     2, 16, capacity=2))
    first = sound(4, rt.RuntimeSampleFormat.U8, sequence=1)
    boundary.submit(first)
    boundary.submit(sound(2, rt.RuntimeSampleFormat.S16LE, sequence=2))
    check("audio:record-count", len(boundary.buffers) == 2)
    check("audio:record-fields",
          boundary.buffers[0].to_document() == {
              "sequence": 1, "sample_format": "U8", "sample_rate": 8000,
              "channels": 1, "sample_count": 4, "checksum": first.checksum()})
    check("audio:document-ledger",
          boundary.to_document()["buffer_count"] == 2
          and boundary.to_document()["output"] is None)
    expect_fail("audio:capacity",
                lambda: boundary.submit(sound(1, rt.RuntimeSampleFormat.U8, 3)))
    expect_fail("audio:unsupported-format", lambda: ga.HeadlessAudio(
        ga.AudioCapabilities(("U8",), (8000,), 1, 4)).submit(
            sound(1, rt.RuntimeSampleFormat.S16LE)))
    expect_fail("audio:unsupported-rate", lambda: ga.HeadlessAudio(
        ga.AudioCapabilities(("U8",), (8000,), 1, 4)).submit(
            rt.RuntimeAudio(rt.RuntimeSampleFormat.U8, 11025, 1, 1, b"\x00")))
    expect_fail("audio:not-a-buffer", lambda: ga.HeadlessAudio(
        ga.AudioCapabilities(("U8",), (8000,), 1, 4)).submit("audio"))
    expect_fail("audio:bad-capabilities", lambda: ga.HeadlessAudio("caps"))

    null = ga.NullAudio()
    check("audio:null-capabilities-empty", null.capabilities().sample_formats == ())
    expect_fail("audio:null-rejects", lambda: null.submit(sound(1)))
    check("audio:null-document", null.to_document()["boundary"] == "null")

    fresh_a = ga.HeadlessAudio(ga.AudioCapabilities(("U8",), (8000,), 1, 8))
    fresh_b = ga.HeadlessAudio(ga.AudioCapabilities(("U8",), (8000,), 1, 8))
    for boundary_ in (fresh_a, fresh_b):
        boundary_.submit(sound(1, sequence=1))
        boundary_.submit(sound(2, sequence=2))
    check("audio:deterministic-document",
          canonical_json(fresh_a.to_document()) == canonical_json(fresh_b.to_document()))
    check("audio:deterministic-fingerprint",
          fresh_a.fingerprint() == fresh_b.fingerprint())
    FINDINGS["audio"] = {
        "ledger_sha256": fresh_a.to_document()["ledger_sha256"],
        "fingerprint": fresh_a.fingerprint(),
    }


# ---------------------------------------------------------------------------
# P4-05 hook integration, determinism and backend independence
# ---------------------------------------------------------------------------
def audit_integration() -> None:
    graphics = ga.HeadlessGraphics(ga.GraphicsCapabilities(("RGBA8",), 4, 4))
    audio = ga.HeadlessAudio(ga.AudioCapabilities(("U8",), (8000,), 1, 4))
    graphics_hook = ga.GraphicsBoundaryHook(graphics)
    audio_hook = ga.AudioBoundaryHook(audio)
    check("hooks:types", isinstance(graphics_hook, pa.GraphicsHook)
          and isinstance(audio_hook, pa.AudioHook))
    expect_fail("hooks:bad-boundary", lambda: ga.GraphicsBoundaryHook("boundary"))
    expect_fail("hooks:bad-audio-boundary", lambda: ga.AudioBoundaryHook("boundary"))

    adapter = BoundaryAdapter(pa.PlatformHooks(graphics=graphics_hook, audio=audio_hook))
    check("hooks:adapter-valid", pa.validate_adapter(adapter) == [])
    bound = pa.bind_platform(adapter)
    check("hooks:bound-graphics", bool(bound.capabilities["graphics_hook"]))
    check("hooks:bound-audio", bool(bound.capabilities["audio_hook"]))
    bound.hooks.graphics.submit_frame(frame(1, 1, rt.RuntimePixelFormat.RGBA8))
    bound.hooks.audio.submit_audio(sound(1))
    check("hooks:routed-graphics", len(graphics.presentations) == 1)
    check("hooks:routed-audio", len(audio.buffers) == 1)
    check("hooks:document-includes-boundary",
          bound.hooks.to_document()["graphics"]["boundary"]["boundary"] == "headless"
          and bound.hooks.to_document()["audio"]["boundary"]["boundary"] == "headless")
    check("hooks:claims-unchanged",
          dict(bound.claims)["console_compatibility"] is False)

    module_source = read_text(ROOT / MODULE_PATH)
    backend_hits = [token for token in BACKEND_TOKENS
                    if token.lower() in module_source.lower()]
    check("independence:no-backend-tokens", not backend_hits)
    imports = re.findall(r"^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_.]*)",
                         module_source, re.MULTILINE)
    allowed = all(
        name.startswith(("openrecomp", "p4_")) or name in (
            "__future__", "hashlib", "re", "dataclasses", "enum", "typing")
        for name in imports)
    check("independence:neutral-imports", allowed)
    FINDINGS["integration"] = {
        "backend_hits": backend_hits,
        "imports": imports,
        "graphics_fingerprint": graphics.fingerprint(),
        "audio_fingerprint": audio.fingerprint(),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="P4-06 graphics/audio boundary gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase4/evidence/P4-06")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}

    print("=== P4-06 Graphics/Audio Boundary Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("source_integrity")
        audit_source_integrity()
        banner("contract")
        audit_contract()
        banner("graphics")
        audit_graphics()
        banner("audio")
        audit_audio()
        banner("integration")
        audit_integration()
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
    (EVIDENCE_DIR / "p4_06_tests.json").write_bytes(
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
