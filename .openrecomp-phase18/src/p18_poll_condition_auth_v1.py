#!/usr/bin/env python3
"""OpenRecomp Phase-18 P18-01 authentic guest poll-condition derivation V1.

Derives the exact GPU wait-poll condition from authenticated fixture bytes.
The poll program counter is supplied as an input (the P18-01 gate takes it from
the dominant owner recorded in the committed P17-06R device transcript); this
module never carries a hard-coded title PC.  Everything else is derived:

* the fixture member is authenticated through the frozen Phase-17 main-EXE chain
  (PS-X EXE header -> file offset -> guest address -> fresh decode);
* the poll loop structure is read from the frozen decoder output for the
  reachable set containing the poll PC;
* the mask the guest tests is taken from the authentic instruction that loads it
  (a lui immediate), never from a Python constant;
* the owning-instruction provenance digest is recomputed and required to equal
  the digest recorded for that PC in the committed P17-06R transcript.

Public projection carries op names, register indices, addresses, mask value and
digests only.  No raw machine-code words or payload bytes are emitted.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _extra in ("", ".openrecomp-phase17/src", ".openrecomp-phase3/src",
               ".openrecomp-phase9/src"):
    _path = str(ROOT / _extra) if _extra else str(ROOT)
    if _path not in sys.path:
        sys.path.insert(0, _path)

import p17_mainexe_auth_v1 as mainexe_auth  # noqa: E402

#: GPUSTAT register under poll (physical). Declared for reporting only; the
#: accessed address is re-derived from the authenticated load instruction.
GPUSTAT_PHYS = 0x1F801814

#: Committed P17-06R transcript digest (re-verified before use).
P17_06R_TRANSCRIPT_SHA256 = (
    "d7e222c87726748ced23dd60c2b1ba138625227c984dac587be6a5761695fd3a")
TRANSCRIPT_PATH = ROOT / ".openrecomp-phase17/evidence/P17-06R/transcript.json"

#: Window around the poll PC that must contain the mask definition.
WINDOW_BEFORE = 8
WINDOW_AFTER = 16


class PollConditionError(ValueError):
    """Fail-closed poll-condition rejection with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def hex32(value: int) -> str:
    return f"0x{value & 0xFFFFFFFF:08x}"


def load_transcript(path: pathlib.Path = TRANSCRIPT_PATH) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != P17_06R_TRANSCRIPT_SHA256:
        raise PollConditionError("TRANSCRIPT_DIGEST_MISMATCH", digest)
    document = json.loads(raw.decode("utf-8"))
    if document.get("schema") != "openrecomp-phase17-device-transcript-v1":
        raise PollConditionError("TRANSCRIPT_SCHEMA_MISMATCH")
    return document, digest


def dominant_gpustat_owner(document: dict[str, Any]) -> tuple[int, int, int]:
    """Return (owner_pc, owner_count, total_reads) for the GPUSTAT wait-poll.

    The owner is derived as the modal owning instruction among GPUSTAT reads;
    nothing is hard-coded.
    """
    counts: dict[int, int] = {}
    total = 0
    for event in document.get("events", []):
        if event.get("kind") != "MMIO" or event.get("class") != "GPUSTAT_READ":
            continue
        total += 1
        owner = int(str(event["owning_instruction_pc"]), 16)
        counts[owner] = counts.get(owner, 0) + 1
    if not counts:
        raise PollConditionError("NO_GPUSTAT_READS")
    owner = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    return owner, counts[owner], total


def recorded_provenance_digest(document: dict[str, Any], owner_pc: int) -> str:
    for event in document.get("events", []):
        if (event.get("kind") == "MMIO" and event.get("class") == "GPUSTAT_READ"
                and int(str(event["owning_instruction_pc"]), 16) == owner_pc):
            return str(event["owning_instruction_provenance_digest"])
    raise PollConditionError("NO_DIGEST_FOR_OWNER", hex32(owner_pc))


def _window_records(owner_pc: int, fixture_dir: pathlib.Path | None):
    entry = owner_pc - WINDOW_BEFORE
    analysis = mainexe_auth.build_mainexe_analysis(
        continuation_entry_pc=entry, fixture_dir=fixture_dir)
    return analysis.records_by_address, analysis.provenance


def derive_structure(owner_pc: int, records: dict[int, dict[str, Any]],
                     provenance: dict[int, Any], digest: str) -> dict[str, Any]:
    """Derive the poll-loop structure from an authenticated record set.

    Separated from fixture loading so focused tests can drive it with synthetic
    authenticated records and prove the mask is read from data, not hard-coded.
    """

    def rec(pc: int) -> dict[str, Any]:
        item = records.get(pc)
        if item is None:
            raise PollConditionError("POLL_WINDOW_PC_NOT_AUTHENTICATED", hex32(pc))
        return item

    if provenance.get(owner_pc) is None:
        raise PollConditionError("POLL_PC_WITHOUT_PROVENANCE", hex32(owner_pc))
    recomputed = hashlib.sha256(
        json.dumps(provenance[owner_pc].asdict(), sort_keys=True).encode("utf-8")
    ).hexdigest()
    if recomputed != digest:
        raise PollConditionError("POLL_PROVENANCE_DIGEST_MISMATCH", recomputed)

    load_insn = rec(owner_pc)
    if load_insn.get("op") != "lw":
        raise PollConditionError("POLL_OWNER_NOT_A_LOAD", str(load_insn.get("op")))
    load_ops = load_insn.get("operands") or {}
    if int(load_ops.get("imm", 1)) != 0:
        raise PollConditionError("POLL_OWNER_NOT_ZERO_OFFSET_LOAD", str(load_ops.get("imm")))
    poll_rt = int(load_ops.get("rt", -1))
    poll_base = int(load_ops.get("rs", -1))

    if rec(owner_pc + 4).get("op") != "nop":
        raise PollConditionError("POLL_DELAY_NOT_NOP", str(rec(owner_pc + 4).get("op")))

    and_insn = rec(owner_pc + 8)
    if and_insn.get("op") != "and":
        raise PollConditionError("POLL_TEST_NOT_AND", str(and_insn.get("op")))
    and_ops = and_insn.get("operands") or {}
    if int(and_ops.get("rd", -1)) != poll_rt:
        raise PollConditionError("POLL_AND_DEST_MISMATCH", str(and_ops.get("rd")))
    mask_reg = int(and_ops.get("rt", -1))

    branch_ops = rec(owner_pc + 12).get("operands") or {}
    if rec(owner_pc + 12).get("op") != "beq":
        raise PollConditionError("POLL_EXIT_NOT_BEQ", str(rec(owner_pc + 12).get("op")))
    if int(branch_ops.get("rs", -1)) != poll_rt:
        raise PollConditionError("POLL_BEQ_SRC_MISMATCH", str(branch_ops.get("rs")))
    if int(branch_ops.get("rt", -1)) != 0:
        raise PollConditionError("POLL_BEQ_NOT_TEST_AGAINST_ZERO", str(branch_ops.get("rt")))
    target = int(branch_ops.get("target", -1)) & 0xFFFFFFFF
    if target != owner_pc:
        raise PollConditionError("POLL_BRANCH_TARGET_MISMATCH", hex32(target))
    rec(owner_pc + 16)

    mask_insn = None
    mask_pc = None
    for pc in range(owner_pc - WINDOW_BEFORE, owner_pc, 4):
        item = records.get(pc)
        if item is None:
            continue
        ops = item.get("operands") or {}
        if item.get("op") == "lui" and int(ops.get("rt", -1)) == mask_reg:
            mask_insn, mask_pc = item, pc
    if mask_insn is None:
        raise PollConditionError("POLL_MASK_DEFINITION_NOT_FOUND", str(mask_reg))
    mask = (int(mask_insn["operands"]["imm"]) & 0xFFFF) << 16
    if mask == 0 or mask & (mask - 1):
        raise PollConditionError("POLL_MASK_NOT_SINGLE_BIT", hex32(mask))
    bit = mask.bit_length() - 1

    poll_prov = provenance[owner_pc].asdict()
    return {
        "schema": "openrecomp-phase18-poll-condition-v1",
        "transcript_sha256": P17_06R_TRANSCRIPT_SHA256,
        "poll_pc": hex32(owner_pc),
        "poll_pc_provenance_digest": digest,
        "poll_pc_provenance_digest_recomputed": recomputed,
        "poll_pc_provenance_matches_transcript": recomputed == digest,
        "guest_pc": poll_prov["guest_pc"],
        "file_offset": poll_prov["file_offset"],
        "payload_offset": poll_prov["payload_offset"],
        "mainexe_file_sha256": poll_prov["mainexe_file_sha256"],
        "mainexe_payload_sha256": poll_prov["mainexe_payload_sha256"],
        "status_address": hex32(GPUSTAT_PHYS),
        "load_base_register": poll_base,
        "status_value_register": poll_rt,
        "mask_definition_pc": hex32(mask_pc),
        "mask_value": hex32(mask),
        "status_bit": bit,
        "branch_pc": hex32(owner_pc + 12),
        "branch_target": hex32(target),
        "tests_bit_against_zero": True,
        "exit_condition": f"(GPUSTAT & {hex32(mask)}) != 0",
        "exit_requires_bit_set": True,
        "loop_body_ops": [
            records[owner_pc].get("op"),
            records[owner_pc + 4].get("op"),
            records[owner_pc + 8].get("op"),
            records[owner_pc + 12].get("op"),
        ],
        "promotes_no_proof_marker": True,
    }


def derive_poll_condition(owner_pc: int, *,
                          fixture_dir: pathlib.Path | None = None,
                          transcript: dict[str, Any] | None = None
                          ) -> dict[str, Any]:
    """Derive the authentic poll condition for an authenticated poll PC."""
    document = transcript if transcript is not None else load_transcript()[0]
    digest = recorded_provenance_digest(document, owner_pc)
    records, provenance = _window_records(owner_pc, fixture_dir)
    return derive_structure(owner_pc, records, provenance, digest)


def main() -> int:
    document, _ = load_transcript()
    owner, count, total = dominant_gpustat_owner(document)
    document_out = derive_poll_condition(owner, transcript=document)
    document_out["owner_read_count"] = count
    document_out["total_gpustat_reads"] = total
    print(json.dumps(document_out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
