#!/usr/bin/env python3
"""Deterministic P18-01 GPUSTAT polling-model investigation gate.

P18-01 answers, mechanically, why authentic execution does not leave the
GPUSTAT wait-poll observed at the end of Phase 17, and whether a faithful
state-driven GPUSTAT model (not a title-specific constant) explains the loop.

It:
  * re-derives the exact guest poll condition from authenticated fixture bytes;
  * establishes the exact status bit involved (from the guest instruction, and
    cross-checked against two independent emulator references);
  * builds the minimum defensible GPUSTAT state model for that bit;
  * runs a deterministic poll-loop simulation showing the exit is reachable
    exactly when the modelled device state reports command-ready, and is NOT
    reachable under the ZERO_FILL_RECORDED read model;
  * fails closed when guest code consumes a status bit the model does not cover.

It promotes NO proof marker.  It does not run the guest past the poll (that is
P18-02) and produces no frame evidence: FIRST_FRAME_READY stays NO and the
Phase-18 claim markers stay NOT_PROVEN.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
from dataclasses import dataclass

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase18/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p18_contracts_v1 as contract
import p18_gpustat_state_model_v1 as state_model
import p18_gpustat_reference_v1 as reference
import p18_poll_condition_auth_v1 as poll_auth
from p18_gate_v1 import Gate, assert_public_safe, run_stage, write_json
import p18_frozen_phase17_authority_v1 as authority

STAGE = "P18-01"
NEXT_STAGE = "P18-02"

STAGE_MARKER = "OPENRECOMP_P18_01"
EXIT_CREDIT_MARKER = "OPENRECOMP_PHASE18_GPUSTAT_EXIT_CREDIT_V1"
MODEL_MARKER = "OPENRECOMP_PHASE18_GPUSTAT_MODEL"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True,
                          text=True).stdout.strip()


def run_authority() -> tuple[bool, str]:
    completed = subprocess.run(
        [sys.executable, ".openrecomp-phase18/src/p18_frozen_phase17_authority_v1.py"],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    ok = (completed.returncode == 0
          and "OPENRECOMP_PHASE18_P17_AUTHORITY_FROZEN=PASS" in completed.stdout)
    return ok, completed.stdout.strip() if not ok else "authority-ok"


def phase17_evidence_untouched() -> tuple[bool, list[str]]:
    changed = git("diff", "--name-only", f"{contract.PHASE17_TERMINAL_COMMIT}..HEAD",
                  "--", *contract.FROZEN_NAMESPACES).splitlines()
    dirty = git("status", "--porcelain", "--", *contract.FROZEN_NAMESPACES).splitlines()
    return (not changed and not dirty), changed + dirty


def simulate_poll(model, mask: int, state, *, max_iterations: int = 16):
    """Deterministically evaluate the derived poll loop against a model."""
    iterations = 0
    while iterations < max_iterations:
        iterations += 1
        value = model.value(state)
        if (value & mask) != 0:
            return {"escaped": True, "iterations": iterations, "observed": value}
        # State is unchanged while the guest merely re-reads the register.
    return {"escaped": False, "iterations": iterations, "observed": model.value(state)}


class ZeroFillModel:
    """The Phase-17 declared read model: every read returns zero."""

    def value(self, state) -> int:  # noqa: ARG002 - deliberately state-independent
        return 0


@dataclass(frozen=True)
class _SyntheticProvenance:
    """Minimal provenance stub for the data-driven seam test."""

    guest_pc: str = "0x80020000"
    payload_offset: int = 0
    file_offset: int = 0
    mainexe_text_addr: str = "0x80020000"
    mainexe_text_size: int = 4
    mainexe_file_sha256: str = "synthetic"
    mainexe_payload_sha256: str = "synthetic"

    def asdict(self) -> dict:
        return {
            "guest_pc": self.guest_pc,
            "payload_offset": self.payload_offset,
            "file_offset": self.file_offset,
            "mainexe_text_addr": self.mainexe_text_addr,
            "mainexe_text_size": self.mainexe_text_size,
            "mainexe_file_sha256": self.mainexe_file_sha256,
            "mainexe_payload_sha256": self.mainexe_payload_sha256,
        }


def _synthetic_digest(prov: _SyntheticProvenance) -> str:
    return hashlib.sha256(json.dumps(prov.asdict(), sort_keys=True).encode("utf-8")).hexdigest()


def synthetic_records(mask_reg: int, mask_imm: int, *, pc: int = 0x80020000):
    records = {
        pc: {"op": "lw", "operands": {"rs": 5, "rt": 7, "imm": 0}},
        pc + 4: {"op": "nop", "operands": {}},
        pc + 8: {"op": "and", "operands": {"rs": 7, "rt": mask_reg, "rd": 7}},
        pc + 12: {"op": "beq", "operands": {"rs": 7, "rt": 0, "target": pc}},
        pc + 16: {"op": "nop", "operands": {}},
        pc - 8: {"op": "lui", "operands": {"rt": mask_reg, "imm": mask_imm}},
    }
    prov = _SyntheticProvenance(guest_pc=f"0x{pc:08x}")
    return records, {pc: prov}, _synthetic_digest(prov)


def negative_tampered_digest() -> bool:
    """A poll PC whose recomputed provenance digest disagrees must fail closed."""
    document, _ = poll_auth.load_transcript()
    owner, _, _ = poll_auth.dominant_gpustat_owner(document)
    records, provenance = poll_auth._window_records(owner, None)
    try:
        poll_auth.derive_structure(owner, records, provenance, "0" * 64)
    except poll_auth.PollConditionError as err:
        return err.code == "POLL_PROVENANCE_DIGEST_MISMATCH"
    return False


def negative_unknown_owner() -> bool:
    """An owner PC with no recorded digest must fail closed."""
    document, _ = poll_auth.load_transcript()
    try:
        poll_auth.recorded_provenance_digest(document, 0xDEADBEEF)
    except poll_auth.PollConditionError as err:
        return err.code == "NO_DIGEST_FOR_OWNER"
    return False


def negative_unmodelled_bit() -> bool:
    model = state_model.GpuStatModel()
    try:
        model.consume_mask(1 << 28)
    except state_model.GpuStatModelError as err:
        return err.code == "UNMODELLED_GPUSTAT_BIT"
    return False


def negative_modelled_bit_accepted() -> bool:
    model = state_model.GpuStatModel()
    try:
        model.consume_mask(1 << 26)
        return True
    except state_model.GpuStatModelError:
        return False


def negative_hardcoded_pc_path() -> bool:
    """A synthetic poll that tests a DIFFERENT bit must derive that bit.

    This is the anti-hardcoding control: if the derivation were wired to the
    Hercules constant 0x04000000, a synthetic loop testing bit 19 would not be
    reported as bit 19.
    """
    records, provenance, digest = synthetic_records(mask_reg=9, mask_imm=0x0008)
    derived = poll_auth.derive_structure(0x80020000, records, provenance, digest)
    return derived["status_bit"] == 19 and derived["mask_value"] == "0x00080000"


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    # 1. Frozen authority preserved.
    ok, out = run_authority()
    gate.check("authority:phase17-frozen", ok, out)
    untouched, offenders = phase17_evidence_untouched()
    gate.check("frozen:phase1-17-untouched", untouched, ",".join(offenders[:5]))

    # 2. Fixture integrity (fail-closed).
    document, digest = poll_auth.load_transcript()
    gate.check("source:transcript-digest", digest == poll_auth.P17_06R_TRANSCRIPT_SHA256,
               "P17-06R transcript digest")

    # 3. Derive the exact guest poll condition from authenticated bytes.
    owner, count, total = poll_auth.dominant_gpustat_owner(document)
    condition = poll_auth.derive_poll_condition(owner, transcript=document)
    condition["owner_read_count"] = count
    condition["total_gpustat_reads"] = total
    gate.check("poll:derived", condition["schema"] == "openrecomp-phase18-poll-condition-v1",
               condition["poll_pc"])
    gate.check("poll:owner-is-modal-owner", condition["poll_pc"] == f"0x{owner:08x}",
               condition["poll_pc"])
    gate.check("poll:provenance-reverified",
               condition["poll_pc_provenance_matches_transcript"] is True,
               condition["poll_pc_provenance_digest"])
    gate.check("poll:loop-structure",
               condition["loop_body_ops"] == ["lw", "nop", "and", "beq"],
               json.dumps(condition["loop_body_ops"]))
    gate.check("poll:exit-requires-bit-set", condition["exit_requires_bit_set"] is True,
               condition["exit_condition"])
    gate.check("poll:single-bit-mask", condition["status_bit"] == 26,
               str(condition["status_bit"]))

    # 4. Cross-check the guest-tested bit against independent references.
    gate.check("reference:independent-agreement",
               reference.agrees_with_mask(int(condition["mask_value"], 16)),
               f"guest mask {condition['mask_value']} vs reference "
               f"{hex(reference.reference_mask())}")

    # 5. Minimum state model.
    model = state_model.GpuStatModel()
    idle = state_model.GpuState(command_pending=False)
    busy = state_model.GpuState(command_pending=True)
    mask = int(condition["mask_value"], 16)
    model.consume_mask(mask)
    gate.check("model:idle-reports-ready", model.value(idle) == mask,
               hex(model.value(idle)))
    gate.check("model:busy-reports-not-ready", model.value(busy) == 0,
               hex(model.value(busy)))
    gate.check("model:matches-independent-impl",
               model.value(idle) == state_model.reference_value(idle)
               and model.value(busy) == state_model.reference_value(busy),
               "cross-check")

    # 6. Poll-loop simulation: exit reachable exactly under faithful state.
    pos = simulate_poll(model, mask, idle)
    busy_run = simulate_poll(model, mask, busy)
    zero_run = simulate_poll(ZeroFillModel(), mask, idle)
    gate.check("sim:positive-exit-reachable", pos["escaped"] is True
               and pos["iterations"] == 1, json.dumps(pos))
    gate.check("sim:busy-does-not-exit", busy_run["escaped"] is False,
               json.dumps(busy_run))
    gate.check("sim:zerofill-cannot-exit", zero_run["escaped"] is False,
               json.dumps(zero_run))
    gate.check("sim:exit-credit-is-state-driven",
               pos["escaped"] and not busy_run["escaped"] and not zero_run["escaped"],
               "exit depends on modelled state, not a constant")

    # 7. Fail-closed coverage of unmodelled bits.
    gate.check("negative:unmodelled-bit-rejected", negative_unmodelled_bit(),
               "bit 28 rejected")
    gate.check("positive:modelled-bit-accepted", negative_modelled_bit_accepted(),
               "bit 26 accepted")
    gate.check("negative:tampered-provenance-digest", negative_tampered_digest(),
               "digest mismatch rejected")
    gate.check("negative:unknown-owner", negative_unknown_owner(), "no digest -> reject")
    gate.check("negative:no-hardcoded-pc", negative_hardcoded_pc_path(),
               "synthetic loop derives its own bit")

    # 8. Claim boundaries unchanged.
    gate.check("claims:first-frame-not-ready",
               contract.PRESERVED_PHASE17_CLAIM_MARKERS["FIRST_FRAME_READY"] == "NO",
               "FIRST_FRAME_READY=NO")

    # 9. Evidence documents.
    poll_doc = {
        "schema": "openrecomp-phase18-gpustat-poll-condition-v1",
        "stage": STAGE,
        "transcript_sha256": condition["transcript_sha256"],
        "source": {
            "mainexe_file_sha256": condition["mainexe_file_sha256"],
            "mainexe_payload_sha256": condition["mainexe_payload_sha256"],
            "guest_pc": condition["guest_pc"],
            "file_offset": condition["file_offset"],
            "payload_offset": condition["payload_offset"],
        },
        "condition": condition,
        "derivation": "POLL_CONDITION_FROM_AUTHENTICATED_FIXTURE_BYTES",
        "promotes_no_proof_marker": True,
    }
    write_json(evidence / "poll_condition.json", poll_doc)
    assert_public_safe(gate, "poll_condition", poll_doc)

    model_doc = {
        "schema": "openrecomp-phase18-gpustat-model-v1",
        "stage": STAGE,
        "model": "STATE_DRIVEN_BIT26",
        "modelled_bits": {str(k): v for k, v in model.coverage.items()},
        "unmodelled_observed_bits": {str(k): v
                                     for k, v in state_model.UNMODELLED_OBSERVED_BITS.items()},
        "reference_sources": list(reference.REFERENCE_SOURCES),
        "reference_ready_mask": hex(reference.reference_mask()),
        "idle_value": hex(model.value(idle)),
        "busy_value": hex(model.value(busy)),
        "fail_closed_bit": hex(1 << 28),
        "not_hardcoded": (
            "The tested bit is read from the authenticated lui that defines the "
            "mask register; the synthetic control proves a different bit is derived."
        ),
        "promotes_no_proof_marker": True,
    }
    write_json(evidence / "model.json", model_doc)
    assert_public_safe(gate, "model", model_doc)

    sim_doc = {
        "schema": "openrecomp-phase18-poll-simulation-v1",
        "stage": STAGE,
        "mask": hex(mask),
        "positive_idle": pos,
        "busy_state": busy_run,
        "zerofill_model": zero_run,
        "conclusion": (
            "Under the faithful state-driven model the poll exits once and only "
            "once the GPU reports command-ready (bit 26 set); under the Phase-17 "
            "ZERO_FILL_RECORDED model the exit is unreachable."
        ),
        "does_not_run_guest_past_poll": True,
        "promotes_no_proof_marker": True,
    }
    write_json(evidence / "simulation.json", sim_doc)
    assert_public_safe(gate, "simulation", sim_doc)

    negatives = {
        "schema": "openrecomp-phase18-negative-tests-v1",
        "stage": STAGE,
        "unmodelled_bit_rejected": negative_unmodelled_bit(),
        "tampered_provenance_rejected": negative_tampered_digest(),
        "unknown_owner_rejected": negative_unknown_owner(),
        "no_hardcoded_pc": negative_hardcoded_pc_path(),
    }
    write_json(evidence / "negative_tests.json", negatives)
    assert_public_safe(gate, "negative_tests", negatives)

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase18-result-v1",
        "stage": STAGE,
        "status": "PASS",
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "authority_commit": contract.PHASE17_TERMINAL_COMMIT,
        "authority_tree": contract.PHASE17_TERMINAL_TREE,
        "poll_condition": {
            "poll_pc": condition["poll_pc"],
            "status_address": condition["status_address"],
            "status_bit": condition["status_bit"],
            "mask_value": condition["mask_value"],
            "exit_condition": condition["exit_condition"],
            "owner_read_count": count,
            "total_gpustat_reads": total,
        },
        "markers": {
            contract.BOOTSTRAP_MARKER: "PASS",
            STAGE_MARKER: "PASS",
            EXIT_CREDIT_MARKER: "YES",
            MODEL_MARKER: "STATE_DRIVEN_BIT26",
            contract.INITIALIZATION_MARKER: "NOT_PROVEN",
            contract.FRAME_MARKER: "NOT_PROVEN",
            contract.PLAYABILITY_MARKER: "NOT_PROVEN",
            contract.GENERAL_MARKER: "NOT_PROVEN",
            contract.FIRST_FRAME_READY_MARKER: "NO",
        },
        "next_stage": NEXT_STAGE,
    })

    gate.mark(contract.BOOTSTRAP_MARKER)
    gate.mark(STAGE_MARKER)
    gate.mark(EXIT_CREDIT_MARKER, "YES")
    gate.mark(MODEL_MARKER, "STATE_DRIVEN_BIT26")
    gate.mark(contract.INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(contract.FRAME_MARKER, "NOT_PROVEN")
    gate.mark(contract.PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(contract.GENERAL_MARKER, "NOT_PROVEN")
    gate.mark(contract.FIRST_FRAME_READY_MARKER, "NO")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase18/evidence/P18-01"))
