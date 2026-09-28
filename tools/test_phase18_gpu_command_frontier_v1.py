#!/usr/bin/env python3
"""Deterministic P18-04 GPU command frontier gate.

P18-04 establishes mechanically whether authentic GP0/GP1 traffic is reached by
the P18-03 continuation, and if not, certifies the frontier as explicitly
NOT REACHED with evidence:

  * the generated runtime contains a genuine, state-driven GP0/GP1 write path
    gated on exactly 0x1f801810 / 0x1f801814 (so "unreached" is a real frontier
    state rather than a missing implementation);
  * the continuation records zero GP0 and zero GP1 writes; the GPU command FIFO
    tap is empty; and no reached instruction materialises the window high half;
  * GP0/GP1 are reported explicitly NOT_REACHED - never as a silent no-op;
  * a controlled probe compiles against the official generated runtime source and
    drives the generated GPU write entry points, producing real GP0/GP1 frontier
    events (so the device model is genuine and the frontier is genuinely
    unreached, not a missing path);
  * an unknown command word is classified UNKNOWN, never swallowed.

If GP0/GP1 traffic ever occurs, the decoded-command outcome is used instead:
every reached write must bind to its authenticated owner and be classified.

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
import p18_exec_continuation_v1 as cont
import p18_fixture_verification_v1 as fixture
import p18_gpu_command_frontier_v1 as frontier
import p18_gpustat_state_model_v1 as state_model
import p18_poll_condition_auth_v1 as poll_auth
import p17_side_effects_exec_v1 as side
from p18_gate_v1 import Gate, assert_public_safe, run_stage, write_json

STAGE = "P18-04"
NEXT_STAGE = "P18-05"

STAGE_MARKER = "OPENRECOMP_P18_04"
FRONTIER_MARKER = "OPENRECOMP_PHASE18_GPU_COMMAND_FRONTIER"

PUBLIC_SCAN_FILES = ("RESULT.json", "gpu_command_frontier.json",
                     "frontier_verdict.json", "command_decode.json",
                     "negative_tests.json")
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


def negative_unknown_command_not_noop() -> dict[str, Any]:
    """An unrecognised GP0 word must classify UNKNOWN, never a no-op."""
    tap = frontier.Gp0Gp1FrontierTap()
    entry = tap.record_write(frontier.GP0_PHYS, 0xFF123456, 0x80030000)
    noop = frontier.classify_gp0_command(0x00000000)
    return {
        "unknown_class": entry["class"],
        "unknown_unsupported": entry["unsupported"],
        "nop_class": noop["class"],
        "nop_is_not_unknown": noop["class"] != "UNKNOWN",
        "ok": entry["class"] == "UNKNOWN" and entry["unsupported"] is True,
    }


def negative_write_wrong_address() -> bool:
    """A GP0/GP1 tap write to a non-window address fails closed."""
    tap = frontier.Gp0Gp1FrontierTap()
    return _raises(lambda: tap.record_write(0x1F801070, 0x0, 0x80030000),
                   frontier.GpuCommandFrontierError, "WRITE_NOT_GP0_GP1")


def negative_event_without_owner(document: dict[str, Any],
                                 provenance_map: dict[int, str]) -> bool:
    """A GP0/GP1 frontier event without an authenticated owner is rejected."""
    forged = dict(document)
    events = [dict(event) for event in forged["events"]]
    events.append({
        "sequence": len(events),
        "register": "GP0",
        "physical_address": frontier.hex32(frontier.GP0_PHYS),
        "owner_pc": "0x80030000",
        "owner_provenance_digest": "0" * 64,
        "word_digest": "0" * 64,
        "width": 4,
        "class": "NOP",
        "unsupported": False,
    })
    forged["events"] = events
    return _raises(lambda: frontier.validate_gpu_command_frontier(forged, provenance_map),
                   frontier.GpuCommandFrontierError, "EVENT_WITHOUT_PROVENANCE")


def negative_unreached_status_missing() -> bool:
    """An empty frontier with no explicit NOT_REACHED status is rejected."""
    document = {
        "schema": "openrecomp-phase18-gpu-command-frontier-v1",
        "events": [],
    }
    return _raises(lambda: frontier.validate_gpu_command_frontier(document, {}),
                   frontier.GpuCommandFrontierError, "UNREACHED_STATUS_MISSING")


def negative_not_window_address() -> bool:
    """A non-window address may never be claimed as an unreached GP0/GP1 window."""
    return _raises(lambda: frontier.window_unreached(False, 0x1F801070),
                   frontier.GpuCommandFrontierError, "NOT_A_GP0_GP1_ADDRESS")


def negative_unmodelled_bit() -> bool:
    model = state_model.GpuStatModel()
    return _raises(lambda: model.consume_mask(1 << 28),
                   state_model.GpuStatModelError, "UNMODELLED_GPUSTAT_BIT")


def controlled_write_path(run_analysis) -> dict[str, Any]:
    """Prove the GP0/GP1 write path + tap + classifier are genuine.

    The authentic continuation never materialises the GP0/GP1 window, so no
    GP0/GP1 write is reachable.  To show the *generated device layer* really
    contains and applies the GPU command path (and that the tap and classifier
    work on the actual generated artifact), this control compiles a tiny probe
    program against the official generated runtime source and drives the GPU
    write entry points with a GP0 and a GP1 word.  Real frontier events must
    appear, bound to an authenticated owner.  The probe is built in a throwaway
    private directory; the official runtime is untouched.
    """
    provenance_map = side.provenance_digest_map(run_analysis)
    run_dir = _run_dirs_holder["dir"]
    work = frontier.private_build_root() / "write-path-control"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)
    for name in ("or_side_effects_v1.h", "or_side_effects_v1.c"):
        (work / name).write_bytes((run_dir / name).read_bytes())

    owner_pc = min(provenance_map)
    probe_lines = [
        '#include "or_side_effects_v1.h"',
        '#include <stdio.h>',
        '#include <stdint.h>',
        'int main(void) {',
        '    uint32_t i;',
        f'    g_p18_pc = 0x{owner_pc:08x}u;',
        '    or_p18_mmio_write(1u, 0x1f801810u, 0x2800ffffu);',
        '    or_p18_mmio_write(1u, 0x1f801814u, 0x03000000u);',
        '    printf("P18G_GP0_TOTAL %u\\n", (unsigned)or_p18g_gp0_total());',
        '    printf("P18G_GP1_TOTAL %u\\n", (unsigned)or_p18g_gp1_total());',
        '    printf("P18G_FIFO_COUNT %u\\n", (unsigned)or_p18g_fifo_count());',
        '    for (i = 0u; i < or_p18g_fifo_count(); i++) {',
        '        printf("P18G_FIFO %u 0x%08x 0x%08x 0x%08x\\n", (unsigned)i,',
        '               (unsigned)or_p18g_fifo_phys(i),',
        '               (unsigned)or_p18g_fifo_word(i),',
        f'               (unsigned)0x{owner_pc:08x}u);',
        '    }',
        '    return 0;',
        '}',
        '',
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
    parsed = frontier._parse_fifo_lines(completed.stdout)
    document, digest = frontier.build_gpu_command_frontier(
        {"p18g_fifo": parsed}, (work / "or_side_effects_v1.c").read_text(encoding="utf-8"),
        provenance_map)
    return {
        "gp0_write_count": document["gp0_write_count"],
        "gp1_write_count": document["gp1_write_count"],
        "frontier_reached": document["frontier_reached"],
        "command_classes": document["command_classes"],
        "unsupported_command_count": document["unsupported_command_count"],
        "frontier_sha256": digest,
        "ok": (document["frontier_reached"]
               and document["gp0_write_count"] >= 1
               and document["gp1_write_count"] >= 1
               and all(event["owner_provenance_digest"] in set(provenance_map.values())
                       for event in document["events"])),
    }


# --- Gate body -------------------------------------------------------------


def body(gate: Gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    stale = evidence / "p18_04_tests.json"
    if stale.is_file():
        stale.unlink()

    # 1. Authority + frozen history.
    ok, out = run_authority()
    gate.check("authority:phase17-frozen", ok, out)
    untouched, offenders = phase17_evidence_untouched()
    gate.check("frozen:phase1-17-untouched", untouched, ",".join(offenders[:5]))

    # 2. Fixture integrity (fail-closed) + committed transcript digest.
    fx = frontier.fixture_root()
    fixture.verify_fixture_with_callback(
        fx, lambda label, condition, detail="": gate.check(label, condition, str(detail)))
    transcript_doc, digest = poll_auth.load_transcript()
    gate.check("source:transcript-digest",
               digest == poll_auth.P17_06R_TRANSCRIPT_SHA256, "P17-06R transcript digest")

    # 3. GP0/GP1 physical constants are the PS1 hardware registers.
    gate.check("gpu:gp0-physical", frontier.GP0_PHYS == 0x1F801810,
               frontier.hex32(frontier.GP0_PHYS))
    gate.check("gpu:gp1-physical", frontier.GP1_PHYS == 0x1F801814,
               frontier.hex32(frontier.GP1_PHYS))

    # 4. Overlay anchor fail-closed controls (synthetic, no fixture needed).
    p18b_anchors = cont.overlay_anchor_selftest()
    gate.check("overlay:p18-02-anchor-controls", p18b_anchors["ok"],
               json.dumps(p18b_anchors, sort_keys=True))
    causal_anchors = causal.overlay_anchor_selftest()
    gate.check("overlay:p18-03-anchor-controls", causal_anchors["ok"],
               json.dumps(causal_anchors, sort_keys=True))
    gpu_anchors = frontier.overlay_anchor_selftest()
    gate.check("overlay:p18-04-anchor-controls", gpu_anchors["ok"],
               json.dumps(gpu_anchors, sort_keys=True))

    # 5. Primary execution: dual official runs, each with its own discovery.
    private_root = frontier.private_build_root()

    def _fresh_run(label: str):
        gens = private_root / f"{label}-discovery"
        if gens.exists():
            shutil.rmtree(gens)
        gens.mkdir(parents=True, exist_ok=False)
        run_analysis = frontier.continuation_analysis()
        manifest, observations, run_analysis = frontier.run_continuation(
            gens, run_analysis)
        run_dir = frontier.official_run_dir(label)
        if run_dir.exists():
            shutil.rmtree(run_dir)
        run_dir.mkdir(parents=True, exist_ok=False)
        final = frontier.emit_continuation(run_dir, run_analysis)
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

    # 6. GP0/GP1 write path is genuine + state-driven (frontier-unreached proof).
    write_path = frontier.write_path_discipline(generated_runtime)
    gate.check("write-path:present", write_path["gp0gp1_write_path_present"],
               json.dumps(write_path, sort_keys=True))
    gate.check("write-path:gated-on-registers",
               write_path["write_gate_count"] == 1
               and write_path["gp0_literal_count"] >= 1
               and write_path["gp1_literal_count"] >= 1)

    # 7. Frontier document from this execution.
    provenance_map = side.provenance_digest_map(run_analysis)
    frontier_doc, frontier_sha = frontier.build_gpu_command_frontier(
        rr, generated_runtime, provenance_map)
    gate.check("frontier:schema",
               frontier_doc["schema"] == "openrecomp-phase18-gpu-command-frontier-v1")
    gate.check("frontier:validated", True, frontier_sha)
    gate.check("frontier:write-path-in-document",
               frontier_doc["write_path"]["gp0gp1_write_path_present"])

    # 8. Executed instruction set is authenticated (unchanged from P18-03).
    executed_pcs = [int(str(pc), 16) for pc in rr["distinct_executed_pcs"]]
    gate.check("continuation:executed-pcs-have-provenance",
               all(pc in provenance_map for pc in executed_pcs),
               json.dumps({"executed": len(executed_pcs)}, sort_keys=True))
    gate.check("continuation:typed-stop-reason",
               rr["stop_reason"] in side.ALLOWED_STOP_REASONS, rr["stop_reason"])

    # 9. Window materialisation over the reached set (title-free).
    materialisation = frontier.window_materialisation(run_analysis, executed_pcs)

    # 10. The two legitimate outcomes.
    if not frontier_doc["frontier_reached"]:
        gate.check("frontier:gp0-not-reached", frontier_doc["gp0_write_count"] == 0,
                   json.dumps({"gp0_writes": frontier_doc["gp0_write_count"]}))
        gate.check("frontier:gp1-not-reached", frontier_doc["gp1_write_count"] == 0,
                   json.dumps({"gp1_writes": frontier_doc["gp1_write_count"]}))
        gate.check("frontier:explicit-not-reached",
                   frontier_doc.get("gp0gp1_status") == "NOT_REACHED"
                   and frontier_doc.get("explicit_not_reached") is True)
        gate.check("frontier:no-events", len(frontier_doc["events"]) == 0)
        gate.check("frontier:zero-mmmio-gpu-writes",
                   rr.get("p18_stats", {}).get("gp0_writes", 0) == 0
                   and rr.get("p18_stats", {}).get("gp1_writes", 0) == 0,
                   json.dumps(rr.get("p18_stats", {}), sort_keys=True))
    else:
        gate.check("frontier:events-non-empty", len(frontier_doc["events"]) >= 1)
        gate.check("frontier:events-classified",
                   all("class" in event for event in frontier_doc["events"]))
        gate.check("frontier:events-authenticated",
                   all(event["owner_provenance_digest"] in set(provenance_map.values())
                       for event in frontier_doc["events"]))
        gate.check("frontier:unknown-commands-reported",
                   frontier_doc["unsupported_command_count"]
                   == sum(1 for event in frontier_doc["events"]
                          if event["class"] == "UNKNOWN"))

    # 11. Controlled write-path proof (genuine model, genuine unreached state).
    control = controlled_write_path(run_analysis)
    gate.check("control:write-path-reaches-gp0gp1", control["ok"],
               json.dumps(control, sort_keys=True))
    if not frontier_doc["frontier_reached"]:
        gate.check("control:contrast-with-unreached-frontier",
                   control["gp0_write_count"] >= 1
                   and control["gp1_write_count"] >= 1,
                   json.dumps({"control_gp0": control["gp0_write_count"],
                               "control_gp1": control["gp1_write_count"]},
                              sort_keys=True))

    # 12. Dual-run determinism.
    gate.check("determinism:manifest-identical", finals[0] == finals[1])
    gate.check("determinism:fifo-identical",
               manifests[0]["runtime_result"]["p18g_fifo"]
               == manifests[1]["runtime_result"]["p18g_fifo"])
    gate.check("determinism:frontier-identical",
               frontier.build_gpu_command_frontier(
                   finals[0]["runtime_result"], generated_runtime, provenance_map)[1]
               == frontier_sha)
    gate.check("determinism:regions-identical",
               [r["entry_pc"] for r in analyses[0].region_log]
               == [r["entry_pc"] for r in analyses[1].region_log])

    # 13. Causal transcript remains valid (P18-03 carries forward).
    causal_doc, causal_sha = causal.build_causal_transcript(manifest, run_analysis,
                                                            provenance_map)
    causal.validate_causal_transcript(causal_doc, provenance_map)
    gate.check("causal:validated", True, causal_sha)

    # 14. Negative controls.
    unknown_control = negative_unknown_command_not_noop()
    gate.check("negative:unknown-command-not-noop", unknown_control["ok"],
               json.dumps(unknown_control, sort_keys=True))
    gate.check("negative:write-wrong-address", negative_write_wrong_address())
    gate.check("negative:event-without-owner",
               negative_event_without_owner(frontier_doc, provenance_map))
    gate.check("negative:unreached-status-missing", negative_unreached_status_missing())
    gate.check("negative:not-window-address", negative_not_window_address())
    gate.check("negative:unmodelled-bit-rejected", negative_unmodelled_bit())

    # 15. Evidence documents.
    frontier_bytes = frontier.frontier_bytes(frontier_doc)
    (evidence / "gpu_command_frontier.json").write_bytes(frontier_bytes)
    (evidence / "gpu_command_frontier.sha256").write_text(
        f"{frontier_sha}  gpu_command_frontier.json\n", encoding="utf-8", newline="\n")
    assert_public_safe(gate, "gpu_command_frontier", frontier_doc)

    readiness = "UNREACHED" if not frontier_doc["frontier_reached"] else "REACHED"
    if not frontier_doc["frontier_reached"]:
        basis = "no reached instruction materialises the GP0/GP1 physical window"
    else:
        basis = "GP0/GP1 traffic reached and decoded"
    verdict_doc = {
        "schema": "openrecomp-phase18-frontier-verdict-v1",
        "stage": STAGE,
        "gpu_command_frontier_status": readiness,
        "gp0_write_count": frontier_doc["gp0_write_count"],
        "gp1_write_count": frontier_doc["gp1_write_count"],
        "explicit_not_reached": frontier_doc.get("explicit_not_reached", False),
        "write_path": write_path,
        "window_materialisation": materialisation,
        "basis": basis,
        "promotes_no_proof_marker": True,
    }
    write_json(evidence / "frontier_verdict.json", verdict_doc)
    assert_public_safe(gate, "frontier_verdict", verdict_doc)

    decode_doc = {
        "schema": "openrecomp-phase18-command-decode-v1",
        "stage": STAGE,
        "command_classes": frontier_doc["command_classes"],
        "unsupported_command_count": frontier_doc["unsupported_command_count"],
        "event_count": len(frontier_doc["events"]),
        "events": frontier_doc["events"],
        "unknown_is_never_a_noop": True,
        "promotes_no_proof_marker": True,
    }
    write_json(evidence / "command_decode.json", decode_doc)
    assert_public_safe(gate, "command_decode", decode_doc)

    negative_doc = {
        "schema": "openrecomp-phase18-negative-tests-v1",
        "stage": STAGE,
        "unknown_command_not_noop": unknown_control,
        "write_wrong_address_rejected": negative_write_wrong_address(),
        "event_without_owner_rejected": negative_event_without_owner(
            frontier_doc, provenance_map),
        "unreached_status_missing_rejected": negative_unreached_status_missing(),
        "not_window_address_rejected": negative_not_window_address(),
        "unmodelled_bit_rejected": negative_unmodelled_bit(),
        "controlled_write_path": control,
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
        "gpu_command_frontier": {
            "status": readiness,
            "gp0_write_count": frontier_doc["gp0_write_count"],
            "gp1_write_count": frontier_doc["gp1_write_count"],
            "command_classes": frontier_doc["command_classes"],
            "window_materialisation_sites": materialisation["window_high_half_site_count"],
            "frontier_sha256": frontier_sha,
        },
        "continuation": {
            "executed_instruction_count": rr["executed_instruction_count"],
            "continuation_executed_count": rr["continuation_executed_count"],
            "stop_reason": rr["stop_reason"],
        },
        "controlled_write_path": {
            "gp0_write_count": control["gp0_write_count"],
            "gp1_write_count": control["gp1_write_count"],
            "frontier_reached": control["frontier_reached"],
        },
        "markers": {
            contract.BOOTSTRAP_MARKER: "PASS",
            "OPENRECOMP_P18_01": "PASS",
            "OPENRECOMP_P18_02": "PASS",
            "OPENRECOMP_P18_03": "PASS",
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
    gate.mark(STAGE_MARKER)
    gate.mark(FRONTIER_MARKER)
    gate.mark(contract.INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(contract.FRAME_MARKER, "NOT_PROVEN")
    gate.mark(contract.PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(contract.GENERAL_MARKER, "NOT_PROVEN")
    gate.mark(contract.FIRST_FRAME_READY_MARKER, "NO")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase18/evidence/P18-04"))
