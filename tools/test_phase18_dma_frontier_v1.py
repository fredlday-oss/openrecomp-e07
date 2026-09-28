#!/usr/bin/env python3
"""Deterministic P18-05 DMA / ordering-table frontier gate.

P18-05 establishes mechanically whether authentic DMA-channel or ordering-table
activity is reached by the P18-04 continuation, and if not, certifies the DMA
frontier as explicitly NOT REACHED with evidence:

  * the generated runtime contains a genuine DMA-window tap gated on exactly
    0x1f801080..0x1f8010ff, reduced through the shared physical-address reducer
    the GPU path uses (so "unreached" is a real frontier state rather than a
    missing implementation);
  * the continuation records zero DMA-window accesses; the DMA tap is empty;
  * every DMA channel is reported explicitly NOT_REACHED - never a silent noop;
  * a bounded ordering-table traversal model is exercised by positive and
    negative controls (alignment, cycle, depth, termination);
  * a controlled probe compiles against the official generated runtime source
    and drives the generated DMA entry points, producing real DMA-frontier
    events (so the model is genuine and the frontier is genuinely unreached).

If DMA traffic ever occurs, the capture outcome is used instead: every reached
access must bind to its authenticated owner and be decoded.

It promotes NO proof marker: FIRST_FRAME_READY stays NO and the Phase-18 claim
markers stay NOT_PROVEN.
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
import p17_side_effects_exec_v1 as side
from p18_gate_v1 import Gate, assert_public_safe, run_stage, write_json

STAGE = "P18-05"
NEXT_STAGE = "P18-06"

STAGE_MARKER = "OPENRECOMP_P18_05"
FRONTIER_MARKER = "OPENRECOMP_PHASE18_DMA_OT_FRONTIER"

PUBLIC_SCAN_FILES = ("RESULT.json", "dma_frontier.json", "dma_verdict.json",
                     "ordering_table_model.json", "negative_tests.json")
FORBIDDEN_TERMS = ("raw_instruction", "instruction_word", "payload_bytes",
                   "bios_bytes")

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


def _raises(fn, exc_type=Exception, code: str | tuple[str, ...] | None = None) -> bool:
    try:
        fn()
        return False
    except exc_type as exc:
        if code is None:
            return True
        allowed = (code,) if isinstance(code, str) else code
        return getattr(exc, "code", None) in allowed


# --- Negative controls -----------------------------------------------------

def negative_address_out_of_window() -> bool:
    tap = dma.DmaFrontierTap()
    return _raises(lambda: tap.record_access(0x1F801070, store=True, width=4,
                                             value=0, owner_pc=0x80030000),
                   dma.DmaFrontierError, "DMA_ADDRESS_NOT_IN_WINDOW")


def negative_madr_unaligned() -> bool:
    return _raises(lambda: dma.decode_register(2, "MADR", 0x2, store=True),
                   dma.DmaFrontierError, "DMA_MADR_UNALIGNED")


def negative_sync_mode_reserved() -> bool:
    return _raises(lambda: dma.decode_chcr(0x00030000),
                   dma.DmaFrontierError, "DMA_SYNC_MODE_UNSUPPORTED")


def negative_ot_start_invalid() -> bool:
    return _raises(lambda: dma.traverse_ordering_table(lambda addr: 0, 0),
                   dma.DmaFrontierError, "OT_START_INVALID")


def negative_ot_unaligned_start() -> bool:
    return _raises(lambda: dma.traverse_ordering_table(lambda addr: 0, 0x0010002),
                   dma.DmaFrontierError, "OT_NODE_UNALIGNED")


def negative_ot_cycle() -> bool:
    start = 0x00100000
    other = 0x00100010
    table = {start: _ot_header(0, other, False),
             other: _ot_header(0, start, False)}
    return _raises(lambda: dma.traverse_ordering_table(lambda a: table[a], start),
                   dma.DmaFrontierError, "OT_CYCLE_DETECTED")


def negative_ot_bound() -> bool:
    start = 0x00100000
    table = {start + 16 * i: _ot_header(0, start + 16 * (i + 1), False)
             for i in range(8)}
    return _raises(
        lambda: dma.traverse_ordering_table(lambda a: table[a], start, max_nodes=4),
        dma.DmaFrontierError, "OT_TRAVERSAL_BOUND_EXCEEDED")


def negative_ot_command_bound() -> bool:
    """A chain whose declared command counts exceed the model bound fails closed.

    Nodes are 0x1000 bytes apart so a node's 255 declared command words never
    overlap another node header; the reader returns a command word for any
    non-header address.  The chain declares 18 * 255 = 4590 commands, above the
    model's 4096 command bound.
    """
    start = 0x00100000
    stride = 0x1000
    headers = {start + stride * i: _ot_header(0xFF, start + stride * (i + 1), False)
               for i in range(18)}

    def reader(addr: int) -> int:
        return headers.get(addr, 0x00000000)

    return _raises(lambda: dma.traverse_ordering_table(reader, start),
                   dma.DmaFrontierError, "OT_COMMAND_BOUND_EXCEEDED")


def negative_event_without_owner(document: dict[str, Any],
                                 provenance_map: dict[int, str]) -> bool:
    forged = dict(document)
    events = [dict(event) for event in forged["events"]]
    events.append({
        "sequence": len(events),
        "channel": 2,
        "channel_name": "GPU",
        "register": "MADR",
        "physical_address": dma.hex32(0x1F8010A0),
        "access": "WRITE",
        "width": 4,
        "owner_pc": "0x80030000",
        "owner_provenance_digest": "0" * 64,
        "value_digest": "0" * 64,
        "madr": "0x00100000",
    })
    forged["events"] = events
    return _raises(lambda: dma.validate_dma_frontier(forged, provenance_map),
                   dma.DmaFrontierError, "EVENT_WITHOUT_PROVENANCE")


def negative_unreached_status_missing() -> bool:
    document = {
        "schema": "openrecomp-phase18-dma-frontier-v1",
        "events": [],
        "channels": [{"index": i} for i in range(dma.DMA_CHANNEL_COUNT)],
    }
    return _raises(lambda: dma.validate_dma_frontier(document, {}),
                   dma.DmaFrontierError, "UNREACHED_STATUS_MISSING")


def negative_unmodelled_bit() -> bool:
    model = state_model.GpuStatModel()
    return _raises(lambda: model.consume_mask(1 << 28),
                   state_model.GpuStatModelError, "UNMODELLED_GPUSTAT_BIT")


def _ot_header(count: int, next_address: int, terminated: bool) -> int:
    value = ((count & 0xFF) << dma.HEADER_COUNT_SHIFT) | (next_address & 0xFFFFFC)
    if terminated:
        value |= dma.END_OF_LIST_BIT
    return value & 0xFFFFFFFF


def ordering_table_positive() -> dict[str, Any]:
    """Positive control for the bounded OT traversal model.

    A three-node chain with one command per node and a terminating third node;
    header words carry the next pointer and command count, and each command word
    is classified with the P18-04 GP0 classifier.
    """
    a, b, c = 0x00100000, 0x00100010, 0x00100020
    table = {
        a: _ot_header(1, b, False),
        a + 4: 0x28000000,          # POLYGON command word
        b: _ot_header(1, c, False),
        b + 4: 0x60000000,          # RECTANGLE command word
        c: _ot_header(1, 0, True),
        c + 4: 0x00000000,          # NOP command word
    }
    result = dma.traverse_ordering_table(lambda addr: table[addr], a)
    classes = [command["class"] for node in result["nodes"]
               for command in node["commands"]]
    ok = (result["node_count"] == 3
          and result["command_count"] == 3
          and result["termination"] == "END_OF_LIST_BIT"
          and result["nodes"][0]["address"] == dma.hex32(a)
          and result["nodes"][2]["terminated"] is True
          and result["nodes"][2]["command_count"] == 1
          and classes == ["POLYGON", "RECTANGLE", "NOP"]
          and result["unsupported_command_count"] == 0)
    return {"node_count": result["node_count"],
            "command_count": result["command_count"],
            "termination": result["termination"],
            "classes": classes,
            "nodes": result["nodes"],
            "ok": ok}


# --- Controlled write-path proof -------------------------------------------

def controlled_dma_path(run_analysis) -> dict[str, Any]:
    """Prove the DMA window tap + decoder are genuine on the generated source.

    The authentic continuation never materialises the DMA window, so no DMA
    access is reachable.  This control compiles a tiny probe against the
    official generated runtime source and drives the generated DMA entry points
    (the very hooks the emitted memory-access sites call) with channel-2
    MADR/BCR/CHCR words.  Real DMA-frontier events must appear, bound to an
    authenticated owner.  The probe is built in a throwaway private directory.
    """
    provenance_map = side.provenance_digest_map(run_analysis)
    run_dir = _run_dirs_holder["dir"]
    work = dma.private_build_root() / "dma-path-control"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)
    for name in ("or_side_effects_v1.h", "or_side_effects_v1.c"):
        (work / name).write_bytes((run_dir / name).read_bytes())

    owner_pc = min(provenance_map)
    probe_lines = [
        "#include <stdio.h>",
        "#include <stdint.h>",
        "int main(void) {",
        "    uint32_t ef[5];",
        "    uint32_t i;",
        f"    uint32_t owner = 0x{owner_pc:08x}u;",
        "    ef[0] = 1u; ef[1] = 0x1f8010a0u; ef[2] = 4u; ef[3] = 0x00100000u; ef[4] = owner;",
        "    or_p18_dma_write(ef[0], ef[1], ef[2], ef[3], ef[4]);",
        "    ef[1] = 0x1f8010a4u; ef[3] = 0x00000010u;",
        "    or_p18_dma_write(ef[0], ef[1], ef[2], ef[3], ef[4]);",
        "    ef[1] = 0x1f8010a8u; ef[3] = 0x00020401u;",
        "    or_p18_dma_write(ef[0], ef[1], ef[2], ef[3], ef[4]);",
        "    ef[0] = 0u; ef[1] = 0x1f8010a8u;",
        "    (void)or_p18_dma_read(0x1f8010a8u, ef);",
        '    printf("P18D_COUNT %u\\n", (unsigned)or_p18d_count());',
        '    printf("P18D_OVERFLOW %u\\n", (unsigned)or_p18d_overflow());',
        '    printf("P18D_DMA_TOTAL %u\\n", (unsigned)or_p18d_dma_total());',
        "    for (i = 0u; i < or_p18d_count(); i++) {",
        '        printf("P18D_DMA %u %u 0x%08x 0x%08x 0x%08x\\n",',
        "               (unsigned)or_p18d_store(i), (unsigned)or_p18d_width(i),",
        "               (unsigned)or_p18d_addr(i), (unsigned)or_p18d_value(i),",
        "               (unsigned)or_p18d_owner(i));",
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
    parsed = dma._parse_dma_lines(completed.stdout)
    document, digest = dma.build_dma_frontier(
        {"p18d_dma": parsed}, (work / "or_side_effects_v1.c").read_text(encoding="utf-8"),
        provenance_map)
    return {
        "dma_access_count": document["dma_access_count"],
        "dma_reached": document["dma_reached"],
        "channels": [c["index"] for c in document["channels"] if c["status"] == "REACHED"],
        "frontier_sha256": digest,
        "ok": (document["dma_reached"]
               and 2 in document["reached_channels"]
               and document["dma_access_count"] >= 3
               and all(event["owner_provenance_digest"] in set(provenance_map.values())
                       for event in document["events"])),
    }


# --- Gate body -------------------------------------------------------------

def body(gate: Gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    stale = evidence / "p18_05_tests.json"
    if stale.is_file():
        stale.unlink()

    # 1. Authority + frozen history.
    ok, out = run_authority()
    gate.check("authority:phase17-frozen", ok, out)
    untouched, offenders = phase17_evidence_untouched()
    gate.check("frozen:phase1-17-untouched", untouched, ",".join(offenders[:5]))

    # 2. Fixture integrity (fail-closed) + committed transcript digest.
    fx = dma.fixture_root()
    fixture.verify_fixture_with_callback(
        fx, lambda label, condition, detail="": gate.check(label, condition, str(detail)))
    transcript_doc, digest = poll_auth.load_transcript()
    gate.check("source:transcript-digest",
               digest == poll_auth.P17_06R_TRANSCRIPT_SHA256, "P17-06R transcript digest")

    # 3. DMA register-window constants are the PS1 hardware map.
    gate.check("dma:window-start", dma.DMA_WINDOW_START == 0x1F801080, "0x1f801080")
    gate.check("dma:window-end", dma.DMA_WINDOW_END == 0x1F8010FF, "0x1f8010ff")
    gate.check("dma:channel-count", dma.DMA_CHANNEL_COUNT == 8, "8 channels")
    gate.check("dma:gpu-channel", dma.channel_name(2) == "GPU", "channel 2 = GPU")
    gate.check("dma:otc-channel", dma.channel_name(6) == "OTC", "channel 6 = OTC")

    # 4. Overlay anchor fail-closed controls (synthetic, no fixture needed).
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

    # 5. Primary execution: dual official runs, each with its own discovery.
    private_root = dma.private_build_root()

    def _fresh_run(label: str):
        gens = private_root / f"{label}-discovery"
        if gens.exists():
            shutil.rmtree(gens)
        gens.mkdir(parents=True, exist_ok=False)
        run_analysis = dma.continuation_analysis()
        manifest, observations, run_analysis = dma.run_continuation(
            gens, run_analysis)
        run_dir = dma.official_run_dir(label)
        if run_dir.exists():
            shutil.rmtree(run_dir)
        run_dir.mkdir(parents=True, exist_ok=False)
        final = dma.emit_continuation(run_dir, run_analysis)
        return manifest, observations, run_analysis, final, run_dir

    manifests = []
    observations = []
    analyses = []
    finals = []
    run_dirs = []
    for label in causal.OFFICIAL_RUN_LABELS:
        m, obs, a, final, run_dir = _fresh_run(label)
        manifests.append(m)
        observations.append(obs)
        analyses.append(a)
        finals.append(final)
        run_dirs.append(run_dir)

    run_analysis = analyses[-1]
    manifest = manifests[-1]
    rr = manifest["runtime_result"]
    _run_dirs_holder["dir"] = run_dirs[-1]
    generated_runtime = (run_dirs[-1] / "or_side_effects_v1.c").read_text(encoding="utf-8")

    # 6. DMA window tap is genuine + window-gated (frontier-unreached proof).
    path = dma.dma_path_discipline(generated_runtime)
    gate.check("dma-path:present", path["dma_window_tap_present"],
               json.dumps(path, sort_keys=True))
    gate.check("dma-path:gated-on-window",
               path["window_gate_count"] == 1
               and path["window_start_literal_count"] >= 1
               and path["window_end_literal_count"] >= 1)

    # 7. DMA frontier document from this execution.
    provenance_map = side.provenance_digest_map(run_analysis)
    dma_doc, dma_sha = dma.build_dma_frontier(rr, generated_runtime, provenance_map)
    gate.check("dma-frontier:schema",
               dma_doc["schema"] == "openrecomp-phase18-dma-frontier-v1")
    gate.check("dma-frontier:validated", True, dma_sha)
    gate.check("dma-frontier:path-in-document",
               dma_doc["write_path"]["dma_window_tap_present"])
    gate.check("dma-frontier:all-channels-listed",
               len(dma_doc["channels"]) == dma.DMA_CHANNEL_COUNT)

    # 8. Executed instruction set is authenticated (unchanged from P18-04).
    executed_pcs = [int(str(pc), 16) for pc in rr["distinct_executed_pcs"]]
    gate.check("continuation:executed-pcs-have-provenance",
               all(pc in provenance_map for pc in executed_pcs),
               json.dumps({"executed": len(executed_pcs)}, sort_keys=True))
    gate.check("continuation:typed-stop-reason",
               rr["stop_reason"] in side.ALLOWED_STOP_REASONS, rr["stop_reason"])

    # 9. Window materialisation over the reached set (title-free).
    materialisation = dma.dma_window_materialisation(run_analysis, executed_pcs)

    # 10. The two legitimate outcomes.
    if not dma_doc["dma_reached"]:
        gate.check("dma-frontier:not-reached", dma_doc["dma_access_count"] == 0,
                   json.dumps({"dma_accesses": dma_doc["dma_access_count"]}))
        gate.check("dma-frontier:explicit-not-reached",
                   dma_doc.get("dma_status") == "NOT_REACHED"
                   and dma_doc.get("explicit_not_reached") is True)
        gate.check("dma-frontier:no-events", len(dma_doc["events"]) == 0)
        gate.check("dma-frontier:no-reached-channels",
                   dma_doc["reached_channels"] == [])
    else:
        gate.check("dma-frontier:events-non-empty", len(dma_doc["events"]) >= 1)
        gate.check("dma-frontier:events-decoded",
                   all("register" in event and "channel" in event
                       for event in dma_doc["events"]))
        gate.check("dma-frontier:events-authenticated",
                   all(event["owner_provenance_digest"] in set(provenance_map.values())
                       for event in dma_doc["events"]))

    # 11. Controlled DMA-path proof (genuine model, genuine unreached state).
    control = controlled_dma_path(run_analysis)
    gate.check("control:dma-path-reaches-window", control["ok"],
               json.dumps(control, sort_keys=True))
    if not dma_doc["dma_reached"]:
        gate.check("control:contrast-with-unreached-frontier",
                   control["dma_reached"] and 2 in control["channels"],
                   json.dumps({"control_channels": control["channels"]}, sort_keys=True))

    # 12. Dual-run determinism.
    gate.check("determinism:manifest-identical", finals[0] == finals[1])
    gate.check("determinism:dma-identical",
               manifests[0]["runtime_result"]["p18d_dma"]
               == manifests[1]["runtime_result"]["p18d_dma"])
    gate.check("determinism:frontier-identical",
               dma.build_dma_frontier(
                   finals[0]["runtime_result"], generated_runtime, provenance_map)[1]
               == dma_sha)
    gate.check("determinism:regions-identical",
               [r["entry_pc"] for r in analyses[0].region_log]
               == [r["entry_pc"] for r in analyses[1].region_log])

    # 13. Causal transcript remains valid (P18-03 carries forward).
    causal_doc, causal_sha = causal.build_causal_transcript(manifest, run_analysis,
                                                            provenance_map)
    causal.validate_causal_transcript(causal_doc, provenance_map)
    gate.check("causal:validated", True, causal_sha)

    # 14. Ordering-table model positive control + negative controls.
    ot_positive = ordering_table_positive()
    gate.check("ot-model:positive-chain", ot_positive["ok"],
               json.dumps({k: ot_positive[k] for k in ("node_count",
                                                       "command_count", "termination",
                                                       "classes")}, sort_keys=True))
    gate.check("negative:address-out-of-window", negative_address_out_of_window())
    gate.check("negative:madr-unaligned", negative_madr_unaligned())
    gate.check("negative:sync-mode-reserved", negative_sync_mode_reserved())
    gate.check("negative:ot-start-invalid", negative_ot_start_invalid())
    gate.check("negative:ot-unaligned-start", negative_ot_unaligned_start())
    gate.check("negative:ot-cycle", negative_ot_cycle())
    gate.check("negative:ot-bound", negative_ot_bound())
    gate.check("negative:ot-command-bound", negative_ot_command_bound())
    gate.check("negative:event-without-owner",
               negative_event_without_owner(dma_doc, provenance_map))
    gate.check("negative:unreached-status-missing", negative_unreached_status_missing())
    gate.check("negative:unmodelled-bit-rejected", negative_unmodelled_bit())

    # 15. Evidence documents.
    (evidence / "dma_frontier.json").write_bytes(dma.frontier_bytes(dma_doc))
    (evidence / "dma_frontier.sha256").write_text(
        f"{dma_sha}  dma_frontier.json\n", encoding="utf-8", newline="\n")
    assert_public_safe(gate, "dma_frontier", dma_doc)

    readiness = "UNREACHED" if not dma_doc["dma_reached"] else "REACHED"
    if not dma_doc["dma_reached"]:
        basis = "no reached instruction materialises the DMA register window"
    else:
        basis = "DMA traffic reached and decoded"
    verdict_doc = {
        "schema": "openrecomp-phase18-dma-verdict-v1",
        "stage": STAGE,
        "dma_frontier_status": readiness,
        "dma_access_count": dma_doc["dma_access_count"],
        "reached_channels": dma_doc["reached_channels"],
        "explicit_not_reached": dma_doc.get("explicit_not_reached", False),
        "write_path": path,
        "window_materialisation": materialisation,
        "basis": basis,
        "promotes_no_proof_marker": True,
    }
    write_json(evidence / "dma_verdict.json", verdict_doc)
    assert_public_safe(gate, "dma_verdict", verdict_doc)

    ot_doc = {
        "schema": "openrecomp-phase18-ordering-table-model-v1",
        "stage": STAGE,
        "model": {
            "end_of_list_bit": dma.hex32(dma.END_OF_LIST_BIT),
            "next_addr_mask": dma.hex32(dma.NEXT_ADDR_MASK),
            "max_nodes": dma.OT_MAX_NODES,
            "checks": ["alignment", "cycle", "depth-bound", "termination-bit"],
        },
        "positive_control": ot_positive,
        "dma_access_events": dma_doc["events"],
        "unknown_is_never_a_noop": True,
        "promotes_no_proof_marker": True,
    }
    write_json(evidence / "ordering_table_model.json", ot_doc)
    assert_public_safe(gate, "ordering_table_model", ot_doc)

    negative_doc = {
        "schema": "openrecomp-phase18-negative-tests-v1",
        "stage": STAGE,
        "address_out_of_window_rejected": negative_address_out_of_window(),
        "madr_unaligned_rejected": negative_madr_unaligned(),
        "sync_mode_reserved_rejected": negative_sync_mode_reserved(),
        "ot_start_invalid_rejected": negative_ot_start_invalid(),
        "ot_unaligned_start_rejected": negative_ot_unaligned_start(),
        "ot_cycle_rejected": negative_ot_cycle(),
        "ot_bound_rejected": negative_ot_bound(),
        "ot_command_bound_rejected": negative_ot_command_bound(),
        "event_without_owner_rejected": negative_event_without_owner(
            dma_doc, provenance_map),
        "unreached_status_missing_rejected": negative_unreached_status_missing(),
        "unmodelled_bit_rejected": negative_unmodelled_bit(),
        "controlled_dma_path": control,
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
        "dma_frontier": {
            "status": readiness,
            "dma_access_count": dma_doc["dma_access_count"],
            "reached_channels": dma_doc["reached_channels"],
            "window_materialisation_sites": materialisation["window_high_half_site_count"],
            "frontier_sha256": dma_sha,
        },
        "continuation": {
            "executed_instruction_count": rr["executed_instruction_count"],
            "continuation_executed_count": rr["continuation_executed_count"],
            "stop_reason": rr["stop_reason"],
        },
        "controlled_dma_path": {
            "dma_access_count": control["dma_access_count"],
            "dma_reached": control["dma_reached"],
            "channels": control["channels"],
        },
        "markers": {
            contract.BOOTSTRAP_MARKER: "PASS",
            "OPENRECOMP_P18_01": "PASS",
            "OPENRECOMP_P18_02": "PASS",
            "OPENRECOMP_P18_03": "PASS",
            "OPENRECOMP_P18_04": "PASS",
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

    gate.mark(contract.BOOTSTRAP_MARKER)
    gate.mark("OPENRECOMP_P18_01")
    gate.mark("OPENRECOMP_P18_02")
    gate.mark("OPENRECOMP_P18_03")
    gate.mark("OPENRECOMP_P18_04")
    gate.mark(STAGE_MARKER)
    gate.mark(FRONTIER_MARKER)
    gate.mark(contract.INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(contract.FRAME_MARKER, "NOT_PROVEN")
    gate.mark(contract.PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(contract.GENERAL_MARKER, "NOT_PROVEN")
    gate.mark(contract.FIRST_FRAME_READY_MARKER, "NO")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase18/evidence/P18-05"))
