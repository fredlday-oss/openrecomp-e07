#!/usr/bin/env python3
"""Deterministic P18-06 VRAM mutation / display-state gate.

P18-06 establishes mechanically whether authentic graphics commands mutate VRAM
or the display configuration by the P18-05 continuation.  Because P18-04 and
P18-05 established zero GP0/GP1 writes and zero DMA-channel accesses, the honest
primary outcome is an explicit, evidence-backed VRAM / DISPLAY FRONTIER NOT YET
REACHED verdict - and this stage proves the deterministic VRAM/display model it
applies is genuine, so "unreached" is a real frontier state, not a missing
implementation.

  * the generated runtime is shown to contain the genuine, window-gated GPU
    write path (P18-04 discipline) and the DMA-window tap (P18-05);
  * the authentic continuation records zero GPU-window writes;
  * a controlled probe compiled against the official generated runtime source
    drives the generated GPU write entry points, and the produced words are
    applied to the VRAM/display model, yielding deterministic VRAM and
    framebuffer evidence;
  * positive and negative controls exercise the model (fill, CPU-to-VRAM copy,
    display enable/start, bounds, alignment, unsupported commands).

It promotes NO proof marker: FIRST_FRAME_READY stays NO and the Phase-18 claim
markers stay NOT_PROVEN.  An image alone is not proof and no frame is promoted.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase18/src", ".openrecomp-phase17/src",
              ".openrecomp-phase3/src", ".openrecomp-phase9/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p18_causal_transcript_v1 as causal
import p18_contracts_v1 as contract
import p18_dma_frontier_v1 as dma
import p18_exec_continuation_v1 as cont
import p18_fixture_verification_v1 as fixture
import p18_gpu_command_frontier_v1 as gpu
import p18_gpustat_state_model_v1 as state_model
import p18_poll_condition_auth_v1 as poll_auth
import p18_vram_display_v1 as vram
import p17_side_effects_exec_v1 as side
from p18_gate_v1 import Gate, assert_public_safe, run_stage, write_json

STAGE = "P18-06"
NEXT_STAGE = "P18-07"

STAGE_MARKER = "OPENRECOMP_P18_06"
FRONTIER_MARKER = "OPENRECOMP_PHASE18_VRAM_DISPLAY_FRONTIER"

_run_dirs_holder: dict[str, Any] = {"dir": None}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True,
                          text=True).stdout.strip()


def run_authority() -> tuple[bool, str]:
    completed = subprocess.run(
        [sys.executable, ".openrecomp-phase18/src/p18_frozen_phase17_authority_v1.py"],
        cwd=str(ROOT), capture_output=True, text=True)
    ok = (completed.returncode == 0
          and "OPENRECOMP_PHASE18_P17_AUTHORITY_FROZEN=PASS" in completed.stdout)
    return ok, completed.stdout.strip() if not ok else "authority-ok"


def phase17_evidence_untouched() -> tuple[bool, list[str]]:
    changed = git("diff", "--name-only", f"{contract.PHASE17_TERMINAL_COMMIT}..HEAD",
                  "--", *contract.FROZEN_NAMESPACES).splitlines()
    dirty = git("status", "--porcelain", "--", *contract.FROZEN_NAMESPACES).splitlines()
    return (not changed and not dirty), changed + dirty


def _raises(fn, exc_type=Exception, code: str | None = None) -> bool:
    try:
        fn()
        return False
    except exc_type as exc:
        if code is None:
            return True
        return getattr(exc, "code", None) == code


# --- GP0 packet assembly (lengths derived from public PS1 hardware) --------

def _gp0_packet_length(command: int, words: list[int], index: int) -> int:
    if command == vram.GP0_FILL_RECTANGLE:
        return 4
    if command == vram.GP0_VRAM_TO_VRAM_COPY:
        return 4
    if command == vram.GP0_VRAM_TO_CPU_COPY:
        return 3
    if command == vram.GP0_CPU_TO_VRAM_COPY:
        if len(words) < index + 3:
            raise vram.VramDisplayError("GP0_PACKET_TRUNCATED", "cpu-to-vram")
        _, _ = vram._decode_xy(words[index + 1])
        w, h = vram._decode_xy(words[index + 2])
        return 3 + (w * h + 1) // 2
    raise vram.VramDisplayError("GP0_PACKET_LENGTH_UNKNOWN", f"0x{command:02x}")


def _assemble_gp0_packets(words: list[int]) -> list[list[int]]:
    packets: list[list[int]] = []
    index = 0
    while index < len(words):
        command = (words[index] >> 24) & 0xFF
        length = _gp0_packet_length(command, words, index)
        if index + length > len(words):
            raise vram.VramDisplayError("GP0_PACKET_TRUNCATED", "assembler")
        packets.append(words[index:index + length])
        index += length
    return packets


# --- Negative controls -----------------------------------------------------

def negative_vram_coord_out_of_range() -> bool:
    return _raises(lambda: vram.vram_offset(1024, 0),
                   vram.VramDisplayError, "VRAM_COORD_OUT_OF_RANGE")


def negative_vram_address_out_of_range() -> bool:
    """A VRAM byte address outside 0x000000..0x0FFFFF fails closed."""
    return _raises(lambda: vram.vram_address(vram.VRAM_SIZE),
                   vram.VramDisplayError, "VRAM_ADDRESS_OUT_OF_RANGE")


def negative_vram_address_unaligned() -> bool:
    """A VRAM byte address off a 16-bit pixel boundary fails closed, unrounded."""
    return _raises(lambda: vram.vram_address(1),
                   vram.VramDisplayError, "VRAM_ADDRESS_UNALIGNED")


def negative_vram_unaligned() -> bool:
    """A region write that runs off the VRAM edge fails closed."""
    state = vram.VramDisplayState()
    return _raises(lambda: state._write_region(1020, 0, 8, 1, lambda c, r: 0),
                   vram.VramDisplayError, "VRAM_REGION_OUT_OF_RANGE")


def negative_region_out_of_range() -> bool:
    state = vram.VramDisplayState()
    return _raises(lambda: state._write_region(0, 500, 4, 16, lambda c, r: 0),
                   vram.VramDisplayError, "VRAM_REGION_OUT_OF_RANGE")


def display_start_max_is_in_range() -> bool:
    """GP1 0x05 encodes x in 10 bits and y in 9 bits.

    That field width exactly spans the 1024x512 VRAM coordinate space, so the
    command cannot express an out-of-range start by construction.  This control
    records that fact explicitly so the out-of-range control below is not
    mistaken for coverage of GP1 encoding.
    """
    state = vram.VramDisplayState()
    word = (vram.GP1_DISPLAY_AREA_START << 24) | (0x1FF << 10) | 0x3FF
    event = state.apply_gp1(word)
    return (event.get("start_x") == 0x3FF and event.get("start_y") == 0x1FF
            and state.display["display_start_x"] == 0x3FF
            and state.display["display_start_y"] == 0x1FF)


def negative_display_start_out_of_range() -> bool:
    """Framebuffer derivation fails closed on out-of-range display state.

    GP1 0x05 cannot encode an out-of-range start (see the control above), so the
    reachable fail-closed path for DISPLAY_START_OUT_OF_RANGE is the display
    state fed to derive_framebuffer.
    """
    return _raises(
        lambda: vram.derive_framebuffer({"display_start_x": vram.VRAM_WIDTH,
                                         "display_start_y": 0}),
        vram.VramDisplayError, "DISPLAY_START_OUT_OF_RANGE")


def negative_gp1_unsupported() -> bool:
    state = vram.VramDisplayState()
    return _raises(lambda: state.apply_gp1(0x1F000000),
                   vram.VramDisplayError, "GP1_COMMAND_UNSUPPORTED")


def negative_unknown_gp0_not_noop() -> dict[str, Any]:
    state = vram.VramDisplayState()
    record = state.apply_gp0([0xFF123456], sequence=0)
    return {"class": record.get("class"), "applied": record.get("applied"),
            "ok": (record.get("class") == "UNKNOWN"
                   and record.get("applied") is False
                   and len(state.unsupported) == 1)}


def negative_primitive_not_modelled() -> dict[str, Any]:
    state = vram.VramDisplayState()
    record = state.apply_gp0([0x28000000], sequence=0)
    return {"mutation": record.get("mutation"), "applied": record.get("applied"),
            "ok": (record.get("mutation") == "PRIMITIVE_RASTERISATION_NOT_MODELLED"
                   and record.get("applied") is False)}


def negative_event_without_owner(document: dict[str, Any],
                                 provenance_map: dict[int, str]) -> bool:
    forged = dict(document)
    events = [dict(event) for event in forged["events"]]
    events.append({
        "sequence": len(events),
        "register": "GP0",
        "physical_address": vram.hex32(gpu.GP0_PHYS),
        "owner_pc": "0x80030000",
        "owner_provenance_digest": "0" * 64,
        "word_digest": "0" * 64,
    })
    forged["events"] = events
    return _raises(lambda: vram.validate_vram_display(forged, provenance_map),
                   vram.VramDisplayError, "EVENT_WITHOUT_PROVENANCE")


def negative_unreached_status_missing() -> bool:
    document = {"schema": "openrecomp-phase18-vram-display-frontier-v1",
                "events": [], "first_frame_ready": "NO"}
    return _raises(lambda: vram.validate_vram_display(document, {}),
                   vram.VramDisplayError, "UNREACHED_STATUS_MISSING")


def negative_first_frame_promoted() -> bool:
    document = {"schema": "openrecomp-phase18-vram-display-frontier-v1",
                "events": [], "vram_display_status": "NOT_REACHED",
                "first_frame_ready": "YES"}
    return _raises(lambda: vram.validate_vram_display(document, {}),
                   vram.VramDisplayError, "FIRST_FRAME_READY_PROMOTED")


def negative_unmodelled_bit() -> bool:
    model = state_model.GpuStatModel()
    return _raises(lambda: model.consume_mask(1 << 28),
                   state_model.GpuStatModelError, "UNMODELLED_GPUSTAT_BIT")


# --- Positive controls -----------------------------------------------------

def positive_model_controls() -> dict[str, Any]:
    """Deterministic positive controls for the VRAM/display model."""
    results: dict[str, Any] = {}

    fill = vram.VramDisplayState()
    # word2 = (y<<16)|x = (0x20<<16)|0x10; word3 = (h<<16)|w = (0x10<<16)|0x20
    fill_record = fill.apply_gp0([0x0200AABB, 0x0000BBAA, 0x00200010,
                                  0x00100020], sequence=0)
    results["fill_ok"] = (fill_record.get("mutation") == "FILL_RECTANGLE"
                          and fill_record.get("x") == 0x10
                          and fill_record.get("y") == 0x20
                          and fill_record.get("width") == 0x20
                          and fill_record.get("height") == 0x10
                          and fill_record.get("region_digest")
                          == vram.vram_region_digest(fill.vram, 0x10, 0x20, 0x20, 0x10)
                          and fill_record.get("region_digest") != _sha256_zeroes())
    results["fill_digest"] = fill.vram_digest()
    results["fill_non_zero"] = fill.vram_digest() != _sha256_zeroes()

    copy_state = vram.VramDisplayState()
    # CPU-to-VRAM copy of a 2x2 block at (4,4): words pack two pixels each.
    packed = 0x1234 | (0x5678 << 16)
    copy_record = copy_state.apply_gp0([0xA0000000, 0x00040004, 0x00020002,
                                        packed, packed], sequence=0)
    results["cpu_to_vram_ok"] = (copy_record.get("mutation") == "CPU_TO_VRAM_COPY"
                                 and copy_state._read_pixel(4, 4) == 0x1234
                                 and copy_state._read_pixel(5, 4) == 0x5678)
    results["cpu_to_vram_non_zero"] = copy_state.vram_digest() != _sha256_zeroes()

    display = vram.VramDisplayState()
    display.apply_gp1((vram.GP1_DISPLAY_ENABLE << 24) | 0x1, sequence=0)
    display.apply_gp1((vram.GP1_DISPLAY_AREA_START << 24) | (0x40 << 10) | 0x20,
                      sequence=1)
    display.apply_gp1((vram.GP1_DISPLAY_MODE << 24) | 0x1, sequence=2)
    fb = vram.derive_framebuffer(display.display)
    results["display_ok"] = (display.display["display_enabled"] == 1
                             and fb["start_x"] == 0x20 and fb["start_y"] == 0x40
                             and fb["width_px"] == 320)
    results["framebuffer_digest"] = display.framebuffer_digest()

    # Determinism: replaying the identical sequence yields identical digests.
    replay = vram.VramDisplayState()
    replay.apply_gp0([0x0200AABB, 0x0000BBAA, 0x00200010, 0x00100020], sequence=0)
    results["deterministic_replay"] = replay.vram_digest() == fill.vram_digest()

    results["gp1_start_max_in_range"] = display_start_max_is_in_range()

    results["ok"] = all(results[key] for key in
                        ("fill_ok", "fill_non_zero", "cpu_to_vram_ok",
                         "cpu_to_vram_non_zero", "display_ok",
                         "deterministic_replay", "gp1_start_max_in_range"))
    return results


def _sha256_zeroes() -> str:
    import hashlib
    return hashlib.sha256(bytes(vram.VRAM_SIZE)).hexdigest()


# --- Controlled probe ------------------------------------------------------

def controlled_model_path(run_analysis) -> dict[str, Any]:
    """Prove the VRAM/display model applies to the emitted GPU write path.

    Compiles a probe against the official generated runtime source, drives the
    generated GPU write entry points with a fill packet and a display-enable /
    display-start sequence, parses the FIFO tap, and applies the resulting words
    to the model.  A non-empty, deterministic VRAM digest must result; the same
    words replayed must give the same digest.  The probe runs in a throwaway
    private directory and the official runtime is untouched.
    """
    provenance_map = side.provenance_digest_map(run_analysis)
    run_dir = _run_dirs_holder["dir"]
    work = vram.private_build_root() / "vram-path-control"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)
    for name in ("or_side_effects_v1.h", "or_side_effects_v1.c"):
        (work / name).write_bytes((run_dir / name).read_bytes())

    owner_pc = min(provenance_map)
    probe_lines = [
        "#include <stdio.h>",
        "#include <stdint.h>",
        "int main(void) {",
        "    uint32_t i;",
        f"    g_p18_pc = 0x{owner_pc:08x}u;",
        "    or_p18_mmio_write(1u, 0x1f801810u, 0x0200aabbu);",
        "    or_p18_mmio_write(1u, 0x1f801810u, 0x0000bbaau);",
        "    or_p18_mmio_write(1u, 0x1f801810u, 0x00200010u);",
        "    or_p18_mmio_write(1u, 0x1f801810u, 0x00100020u);",
        "    or_p18_mmio_write(1u, 0x1f801814u, 0x03000001u);",
        "    or_p18_mmio_write(1u, 0x1f801814u, 0x05004020u);",
        '    printf("P18G_GP0_TOTAL %u\\n", (unsigned)or_p18g_gp0_total());',
        '    printf("P18G_GP1_TOTAL %u\\n", (unsigned)or_p18g_gp1_total());',
        '    printf("P18G_FIFO_COUNT %u\\n", (unsigned)or_p18g_fifo_count());',
        '    printf("P18G_FIFO_OVERFLOW %u\\n", (unsigned)or_p18g_fifo_overflow());',
        "    for (i = 0u; i < or_p18g_fifo_count(); i++) {",
        '        printf("P18G_FIFO %u 0x%08x 0x%08x 0x%08x\\n", (unsigned)i,',
        "               (unsigned)or_p18g_fifo_phys(i),",
        "               (unsigned)or_p18g_fifo_word(i),",
        "               (unsigned)or_p18g_fifo_owner(i));",
        "    }",
        "    return 0;",
        "}",
        "",
    ]
    (work / "probe.c").write_text("\n".join(probe_lines), encoding="utf-8",
                                  newline="\n")
    include_flag = f"-I{work}"
    probe_exe = work / "probe"
    subprocess.run(cont.emitter._compile_c(
        work / "probe.c", probe_exe,
        extra_flags=("-include", str(work / "or_side_effects_v1.c"), include_flag)),
        check=True, capture_output=True)
    completed = subprocess.run([str(probe_exe)], capture_output=True, text=True)
    parsed = gpu._parse_fifo_lines(completed.stdout)

    gp0_words = [e["word"] for e in parsed["entries"]
                 if e["physical_address"] == gpu.GP0_PHYS]
    gp1_words = [e["word"] for e in parsed["entries"]
                 if e["physical_address"] == gpu.GP1_PHYS]
    owner_pcs = {e["owner_pc"] for e in parsed["entries"]}

    state = vram.VramDisplayState()
    for index, packet in enumerate(_assemble_gp0_packets(gp0_words)):
        state.apply_gp0(packet, owner_pc=owner_pc, sequence=index)
    for index, word in enumerate(gp1_words):
        state.apply_gp1(word, sequence=index)
    snapshot = state.snapshot()
    first_digest = snapshot["vram_digest"]

    replay = vram.VramDisplayState()
    for index, packet in enumerate(_assemble_gp0_packets(gp0_words)):
        replay.apply_gp0(packet, owner_pc=owner_pc, sequence=index)
    for index, word in enumerate(gp1_words):
        replay.apply_gp1(word, sequence=index)
    replay_digest = replay.snapshot()["vram_digest"]

    owners_authenticated = all(pc in provenance_map for pc in owner_pcs)
    return {
        "gp0_word_count": len(gp0_words),
        "gp1_word_count": len(gp1_words),
        "mutation_count": snapshot["mutation_count"],
        "display_event_count": snapshot["display_event_count"],
        "vram_digest": first_digest,
        "framebuffer_digest": snapshot["framebuffer_digest"],
        "deterministic": first_digest == replay_digest,
        "owner_authenticated": owners_authenticated,
        "ok": (len(gp0_words) >= 4 and len(gp1_words) >= 1
               and snapshot["mutation_count"] >= 1
               and first_digest != _sha256_zeroes()
               and first_digest == replay_digest
               and owners_authenticated),
    }


# --- Gate body -------------------------------------------------------------

def body(gate: Gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    stale = evidence / "p18_06_tests.json"
    if stale.is_file():
        stale.unlink()

    ok, out = run_authority()
    gate.check("authority:phase17-frozen", ok, out)
    untouched, offenders = phase17_evidence_untouched()
    gate.check("frozen:phase1-17-untouched", untouched, ",".join(offenders[:5]))

    fx = vram.fixture_root()
    fixture.verify_fixture_with_callback(
        fx, lambda label, condition, detail="": gate.check(label, condition, str(detail)))
    transcript_doc, digest = poll_auth.load_transcript()
    gate.check("source:transcript-digest",
               digest == poll_auth.P17_06R_TRANSCRIPT_SHA256, "P17-06R transcript digest")

    gate.check("vram:size", vram.VRAM_SIZE == 1024 * 512 * 2, "1 MiB")
    gate.check("vram:geometry", vram.VRAM_WIDTH == 1024 and vram.VRAM_HEIGHT == 512)

    p18b_anchors = cont.overlay_anchor_selftest()
    gate.check("overlay:p18-02-anchor-controls", p18b_anchors["ok"],
               json.dumps(p18b_anchors, sort_keys=True))
    causal_anchors = causal.overlay_anchor_selftest()
    gate.check("overlay:p18-03-anchor-controls", causal_anchors["ok"],
               json.dumps(causal_anchors, sort_keys=True))
    gpu_anchors = gpu.overlay_anchor_selftest()
    gate.check("overlay:p18-04-anchor-controls", gpu_anchors["ok"],
               json.dumps(gpu_anchors, sort_keys=True))
    dma_anchors = dma.overlay_anchor_selftest()
    gate.check("overlay:p18-05-anchor-controls", dma_anchors["ok"],
               json.dumps(dma_anchors, sort_keys=True))

    private_root = vram.private_build_root()

    def _fresh_run(label: str):
        gens = private_root / f"{label}-discovery"
        if gens.exists():
            shutil.rmtree(gens)
        gens.mkdir(parents=True, exist_ok=False)
        run_analysis = vram.continuation_analysis()
        manifest, observations, run_analysis = vram.run_continuation(gens, run_analysis)
        run_dir = vram.official_run_dir(label)
        if run_dir.exists():
            shutil.rmtree(run_dir)
        run_dir.mkdir(parents=True, exist_ok=False)
        final = vram.emit_continuation(run_dir, run_analysis)
        return manifest, observations, run_analysis, final, run_dir

    manifests, observations, analyses, finals, run_dirs = [], [], [], [], []
    for label in causal.OFFICIAL_RUN_LABELS:
        m, obs, a, final, run_dir = _fresh_run(label)
        manifests.append(m); observations.append(obs); analyses.append(a)
        finals.append(final); run_dirs.append(run_dir)

    run_analysis = analyses[-1]
    manifest = manifests[-1]
    rr = manifest["runtime_result"]
    _run_dirs_holder["dir"] = run_dirs[-1]
    generated_runtime = (run_dirs[-1] / "or_side_effects_v1.c").read_text(encoding="utf-8")

    gpu_path = gpu.write_path_discipline(generated_runtime)
    dma_path = dma.dma_path_discipline(generated_runtime)
    gate.check("write-path:present", gpu_path["gp0gp1_write_path_present"],
               json.dumps(gpu_path, sort_keys=True))
    gate.check("dma-path:present", dma_path["dma_window_tap_present"],
               json.dumps(dma_path, sort_keys=True))

    provenance_map = side.provenance_digest_map(run_analysis)
    doc, doc_sha = vram.build_vram_display(rr, generated_runtime, provenance_map)
    gate.check("vram-frontier:schema",
               doc["schema"] == "openrecomp-phase18-vram-display-frontier-v1")
    gate.check("vram-frontier:validated", True, doc_sha)
    gate.check("vram-frontier:not-first-frame", doc["first_frame_ready"] == "NO")

    executed_pcs = [int(str(pc), 16) for pc in rr["distinct_executed_pcs"]]
    gate.check("continuation:executed-pcs-have-provenance",
               all(pc in provenance_map for pc in executed_pcs),
               json.dumps({"executed": len(executed_pcs)}, sort_keys=True))
    gate.check("continuation:typed-stop-reason",
               rr["stop_reason"] in side.ALLOWED_STOP_REASONS, rr["stop_reason"])

    if not doc["vram_frontier_reached"]:
        gate.check("vram-frontier:not-reached",
                   doc["gp0_write_count"] == 0 and doc["gp1_write_count"] == 0
                   and doc["dma_access_count"] == 0,
                   json.dumps({"gp0": doc["gp0_write_count"],
                               "gp1": doc["gp1_write_count"],
                               "dma": doc["dma_access_count"]}, sort_keys=True))
        gate.check("vram-frontier:explicit-not-reached",
                   doc.get("vram_display_status") == "NOT_REACHED"
                   and doc.get("explicit_not_reached") is True)
        gate.check("vram-frontier:no-events", len(doc["events"]) == 0)
    else:
        gate.check("vram-frontier:events-authenticated",
                   all(event["owner_provenance_digest"] in set(provenance_map.values())
                       for event in doc["events"]))

    positive = positive_model_controls()
    gate.check("model:positive-controls", positive["ok"],
               json.dumps({k: positive[k] for k in ("fill_ok", "cpu_to_vram_ok",
                                                    "display_ok",
                                                    "deterministic_replay")},
                          sort_keys=True))

    control = controlled_model_path(run_analysis)
    gate.check("control:model-applies-to-generated-path", control["ok"],
               json.dumps({k: control[k] for k in ("gp0_word_count", "gp1_word_count",
                                                   "mutation_count", "deterministic",
                                                   "owner_authenticated")},
                          sort_keys=True))
    gate.check("control:contrast-with-unreached-frontier",
               control["gp0_word_count"] >= 4 and doc["gp0_write_count"] == 0,
               json.dumps({"control_gp0": control["gp0_word_count"],
                           "frontier_gp0": doc["gp0_write_count"]}, sort_keys=True))

    gate.check("determinism:manifest-identical", finals[0] == finals[1])
    gate.check("determinism:gpu-fifo-identical",
               manifests[0]["runtime_result"]["p18g_fifo"]
               == manifests[1]["runtime_result"]["p18g_fifo"])
    gate.check("determinism:frontier-identical",
               vram.build_vram_display(finals[0]["runtime_result"], generated_runtime,
                                       provenance_map)[1] == doc_sha)
    gate.check("determinism:regions-identical",
               [r["entry_pc"] for r in analyses[0].region_log]
               == [r["entry_pc"] for r in analyses[1].region_log])

    causal_doc, causal_sha = causal.build_causal_transcript(manifest, run_analysis,
                                                            provenance_map)
    causal.validate_causal_transcript(causal_doc, provenance_map)
    gate.check("causal:validated", True, causal_sha)

    unknown_control = negative_unknown_gp0_not_noop()
    primitive_control = negative_primitive_not_modelled()
    gate.check("negative:unknown-gp0-not-noop", unknown_control["ok"],
               json.dumps(unknown_control, sort_keys=True))
    gate.check("negative:primitive-not-modelled", primitive_control["ok"],
               json.dumps(primitive_control, sort_keys=True))
    gate.check("negative:vram-coord-out-of-range", negative_vram_coord_out_of_range())
    gate.check("negative:vram-address-out-of-range",
               negative_vram_address_out_of_range())
    gate.check("negative:vram-address-unaligned", negative_vram_address_unaligned())
    gate.check("negative:vram-unaligned-region", negative_vram_unaligned())
    gate.check("negative:region-out-of-range", negative_region_out_of_range())
    gate.check("negative:display-start-out-of-range",
               negative_display_start_out_of_range())
    gate.check("negative:gp1-unsupported", negative_gp1_unsupported())
    gate.check("negative:event-without-owner",
               negative_event_without_owner(doc, provenance_map))
    gate.check("negative:unreached-status-missing", negative_unreached_status_missing())
    gate.check("negative:first-frame-promoted", negative_first_frame_promoted())
    gate.check("negative:unmodelled-bit-rejected", negative_unmodelled_bit())

    (evidence / "vram_display.json").write_bytes(vram.frontier_bytes(doc))
    (evidence / "vram_display.sha256").write_text(
        f"{doc_sha}  vram_display.json\n", encoding="utf-8", newline="\n")
    assert_public_safe(gate, "vram_display", doc)

    readiness = "UNREACHED" if not doc["vram_frontier_reached"] else "REACHED"
    verdict_doc = {
        "schema": "openrecomp-phase18-vram-verdict-v1",
        "stage": STAGE,
        "vram_display_status": readiness,
        "gp0_write_count": doc["gp0_write_count"],
        "gp1_write_count": doc["gp1_write_count"],
        "dma_access_count": doc["dma_access_count"],
        "explicit_not_reached": doc.get("explicit_not_reached", False),
        "first_frame_ready": "NO",
        "no_frame_promoted": True,
        "basis": doc.get("basis", "authentic graphics traffic reached"),
        "promotes_no_proof_marker": True,
    }
    write_json(evidence / "vram_verdict.json", verdict_doc)
    assert_public_safe(gate, "vram_verdict", verdict_doc)

    display_doc = {
        "schema": "openrecomp-phase18-display-state-v1",
        "stage": STAGE,
        "model": {
            "vram_width": vram.VRAM_WIDTH,
            "vram_height": vram.VRAM_HEIGHT,
            "bpp": 16,
            "hres_map": {str(k): v for k, v in vram.DISPLAY_MODE_HRES.items()},
            "gp0_mutation_commands": [vram.hex32(vram.GP0_FILL_RECTANGLE),
                                      vram.hex32(vram.GP0_CPU_TO_VRAM_COPY),
                                      vram.hex32(vram.GP0_VRAM_TO_VRAM_COPY)],
            "primitive_rasterisation": "NOT_MODELLED",
        },
        "positive_controls": positive,
        "controlled_model_path": control,
        "authentic_display_events": doc["events"],
        "promotes_no_proof_marker": True,
    }
    write_json(evidence / "display_state.json", display_doc)
    assert_public_safe(gate, "display_state", display_doc)

    negative_doc = {
        "schema": "openrecomp-phase18-negative-tests-v1",
        "stage": STAGE,
        "unknown_gp0_not_noop": unknown_control,
        "primitive_not_modelled": primitive_control,
        "vram_coord_out_of_range_rejected": negative_vram_coord_out_of_range(),
        "vram_address_out_of_range_rejected": negative_vram_address_out_of_range(),
        "vram_address_unaligned_rejected": negative_vram_address_unaligned(),
        "vram_unaligned_region_rejected": negative_vram_unaligned(),
        "region_out_of_range_rejected": negative_region_out_of_range(),
        "display_start_out_of_range_rejected": negative_display_start_out_of_range(),
        "gp1_unsupported_rejected": negative_gp1_unsupported(),
        "event_without_owner_rejected": negative_event_without_owner(
            doc, provenance_map),
        "unreached_status_missing_rejected": negative_unreached_status_missing(),
        "first_frame_promoted_rejected": negative_first_frame_promoted(),
        "unmodelled_bit_rejected": negative_unmodelled_bit(),
        "controlled_model_path": control,
        "promotes_no_proof_marker": True,
    }
    write_json(evidence / "negative_tests.json", negative_doc)
    assert_public_safe(gate, "negative_tests", negative_doc)

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase18-result-v1",
        "stage": STAGE,
        "status": "PASS",
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "authority_commit": contract.PHASE17_TERMINAL_COMMIT,
        "authority_tree": contract.PHASE17_TERMINAL_TREE,
        "vram_display_frontier": {
            "status": readiness,
            "gp0_write_count": doc["gp0_write_count"],
            "gp1_write_count": doc["gp1_write_count"],
            "dma_access_count": doc["dma_access_count"],
            "frontier_sha256": doc_sha,
        },
        "continuation": {
            "executed_instruction_count": rr["executed_instruction_count"],
            "continuation_executed_count": rr["continuation_executed_count"],
            "stop_reason": rr["stop_reason"],
        },
        "controlled_model_path": {
            "gp0_word_count": control["gp0_word_count"],
            "gp1_word_count": control["gp1_word_count"],
            "mutation_count": control["mutation_count"],
            "vram_digest": control["vram_digest"],
        },
        "markers": {
            contract.BOOTSTRAP_MARKER: "PASS",
            "OPENRECOMP_P18_01": "PASS",
            "OPENRECOMP_P18_02": "PASS",
            "OPENRECOMP_P18_03": "PASS",
            "OPENRECOMP_P18_04": "PASS",
            "OPENRECOMP_P18_05": "PASS",
            STAGE_MARKER: "PASS",
            FRONTIER_MARKER: "PASS",
            contract.INITIALIZATION_MARKER: "NOT_PROVEN",
            contract.FRAME_MARKER: "NOT_PROVEN",
            contract.PLAYABILITY_MARKER: "NOT_PROVEN",
            contract.GENERAL_MARKER: "NOT_PROVEN",
            contract.FIRST_FRAME_READY_MARKER: "NO",
        },
        "next_stage": NEXT_STAGE,
    })

    for marker in (contract.BOOTSTRAP_MARKER, "OPENRECOMP_P18_01", "OPENRECOMP_P18_02",
                   "OPENRECOMP_P18_03", "OPENRECOMP_P18_04", "OPENRECOMP_P18_05",
                   STAGE_MARKER, FRONTIER_MARKER):
        gate.mark(marker)
    gate.mark(contract.INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(contract.FRAME_MARKER, "NOT_PROVEN")
    gate.mark(contract.PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(contract.GENERAL_MARKER, "NOT_PROVEN")
    gate.mark(contract.FIRST_FRAME_READY_MARKER, "NO")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase18/evidence/P18-06"))
