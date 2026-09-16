"""NES6502 -> OpenRecomp shared program-model bridge (P2-20).

`OpenRecomp Phase 2` stage P2-20 deliverable. This module feeds a documented
NES 6502 (2A03/2A07-family) instruction region through the **same** shared,
architecture-neutral Phase-2 layers used by the MIPS32 path:

    adapters.nes6502 decode_full
      -> P2-01 DecodedInstruction / ProgramModel
      -> P2-02 CFG
      -> P2-03 function discovery
      -> P2-04 call graph
      -> P2-05 translation units
      -> P2-06 indirect-control-flow classification

It contains no MIPS or NES platform/runtime behaviour. Per-ISA knowledge lives
only in `adapters/nes6502.py`; this bridge is the only architecture-aware seam,
and the shared layers it calls do not import it.

Flow classification (documented NMOS 6502 control effects, no guessing):

* `jmp` absolute   -> `JUMP` (static direct target);
* `jmp (indirect)` -> `INDIRECT_JUMP`, unresolved (the target is a runtime value
  and is never inferred);
* `jsr` absolute   -> `CALL` (static direct target);
* `rts` / `rti`    -> `RETURN` (a dynamic return, not an indirect jump);
* `brk`            -> `TRAP`;
* the eight conditional branches (`bpl`/`bmi`/`bvc`/`bvs`/`bcc`/`bcs`/`bne`/
  `beq`) -> `BRANCH` (static direct target);
* everything else  -> `NORMAL`.

The resolved 6502 operand fields (`imm8`, `zp`, `abs`, `target`, `indirect`,
...) are preserved verbatim in the neutral instruction metadata under
`adapter_fields` for later emitter stages (P2-21). Undocumented encodings and
truncated operand streams fail closed through the adapter.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from adapters import nes6502 as _nes6502
from openrecomp.call_graph import CallGraph, build_call_graph
from openrecomp.cfg import CFGMode, ControlFlowGraph, EntryPoint, build_cfg
from openrecomp.functions import FunctionDiscoveryResult, discover_functions
from openrecomp.indirect_control_flow import IndirectControlFlowSet, classify_indirect_control_flow
from openrecomp.program_model import (
    DecodedInstruction,
    EvidenceClass,
    InstructionFlow,
    ProgramSource,
    canonical_json,
)
from openrecomp.translation_units import TranslationUnitSet, build_translation_units

NES6502_ARCHITECTURE = "nes6502"
NES6502_ADAPTER = "adapters.nes6502"
NES6502_ADDRESS_BITS = 16
BRIDGE_VERSION = "1.0.0"

_BRANCH_OPS = frozenset(name for name, _flag, _taken in _nes6502.BRANCHES.values())
_RETURN_OPS = frozenset({"rts", "rti"})
_TRAP_OPS = frozenset({"brk"})


class NES6502BridgeError(ValueError):
    """Raised when a NES6502 region cannot be represented safely."""


def classify_flow(decoded: Mapping[str, Any]) -> InstructionFlow:
    """Map a documented 6502 decode result to a neutral `InstructionFlow`."""
    op = decoded.get("op")
    if not isinstance(op, str) or not op:
        raise NES6502BridgeError("decode result must carry a non-empty 'op'")
    if op == "jmp":
        if "indirect" in decoded:
            return InstructionFlow.INDIRECT_JUMP
        if isinstance(decoded.get("target"), int):
            return InstructionFlow.JUMP
        raise NES6502BridgeError("absolute jmp decode result is missing a static target")
    if op == "jsr":
        if not isinstance(decoded.get("target"), int):
            raise NES6502BridgeError("jsr decode result is missing a static target")
        return InstructionFlow.CALL
    if op in _RETURN_OPS:
        return InstructionFlow.RETURN
    if op in _TRAP_OPS:
        return InstructionFlow.TRAP
    if op in _BRANCH_OPS:
        if not isinstance(decoded.get("target"), int):
            raise NES6502BridgeError(f"{op} decode result is missing a static target")
        return InstructionFlow.BRANCH
    return InstructionFlow.NORMAL


def instruction_from_nes6502(
    memory: bytes | bytearray,
    address: int,
    *,
    evidence: EvidenceClass = EvidenceClass.PROVEN,
) -> DecodedInstruction:
    """Bridge one documented 6502 instruction into a neutral instruction.

    `memory` is indexed by absolute guest address (16-bit). Undocumented
    opcodes and truncated operand streams fail closed through the adapter.
    """
    if not isinstance(memory, (bytes, bytearray)):
        raise NES6502BridgeError("memory must be a bytes-like guest image")
    try:
        decoded = _nes6502.decode_full(memory, address)
    except _nes6502.NES6502Error as exc:
        raise NES6502BridgeError(str(exc)) from exc

    flow = classify_flow(decoded)
    unresolved = flow is InstructionFlow.INDIRECT_JUMP
    direct_target = None
    if flow in (InstructionFlow.JUMP, InstructionFlow.CALL, InstructionFlow.BRANCH):
        direct_target = decoded["target"]

    fields = {
        key: value
        for key, value in decoded.items()
        if key not in {"address", "op", "length"}
    }
    return DecodedInstruction(
        address=decoded["address"],
        op=decoded["op"],
        size_bytes=decoded["length"],
        flow=flow,
        direct_target=direct_target,
        unresolved=unresolved,
        evidence=evidence,
        metadata={"adapter_fields": fields},
    )


def bridge_region(
    memory: bytes | bytearray,
    *,
    entry: int,
    end: int,
    evidence: EvidenceClass = EvidenceClass.PROVEN,
) -> tuple[DecodedInstruction, ...]:
    """Linearly decode `[entry, end)` into neutral instructions.

    Every instruction extent must lie inside the region; a truncated or
    undocumented instruction fails closed.
    """
    if not isinstance(memory, (bytes, bytearray)):
        raise NES6502BridgeError("memory must be a bytes-like guest image")
    if isinstance(entry, bool) or not isinstance(entry, int) or not (0 <= entry <= 0xFFFF):
        raise NES6502BridgeError(f"entry 0x{entry:x} is outside the 16-bit guest address space")
    if isinstance(end, bool) or not isinstance(end, int) or not (entry < end <= 0x10000):
        raise NES6502BridgeError(f"region end 0x{end:x} must satisfy 0x{entry:x} < end <= 0x10000")
    if len(memory) < end:
        raise NES6502BridgeError(f"memory image is {len(memory)} bytes but the region ends at 0x{end:x}")

    instructions: list[DecodedInstruction] = []
    address = entry
    while address < end:
        instruction = instruction_from_nes6502(memory, address, evidence=evidence)
        next_address = instruction.address + (instruction.size_bytes or 1)
        if next_address > end:
            raise NES6502BridgeError(
                f"0x{address:x}: {instruction.op} extends past the region end 0x{end:x}"
            )
        instructions.append(instruction)
        address = next_address
    if not instructions:
        raise NES6502BridgeError("region contains no instructions")
    return tuple(instructions)


@dataclass(frozen=True)
class NES6502Program:
    """The shared-structural representation of one NES6502 region."""

    source: ProgramSource
    entry: int
    end: int
    region_sha256: str
    instructions: tuple[DecodedInstruction, ...]
    cfg: ControlFlowGraph
    discovery: FunctionDiscoveryResult
    call_graph: CallGraph
    units: TranslationUnitSet
    classification: IndirectControlFlowSet

    def function_ids(self) -> tuple[str, ...]:
        return tuple(function.id for function in self.discovery.functions)

    def to_document(self) -> dict[str, Any]:
        return {
            "bridge_version": BRIDGE_VERSION,
            "source": self.source.to_document(),
            "entry": self.entry,
            "end": self.end,
            "region_sha256": self.region_sha256,
            "function_ids": list(self.function_ids()),
            "cfg_fingerprint": self.cfg.fingerprint(),
            "functions_fingerprint": self.discovery.fingerprint(),
            "call_graph_fingerprint": self.call_graph.fingerprint(),
            "units_fingerprint": self.units.fingerprint(),
            "classification_fingerprint": self.classification.fingerprint(),
            "instruction_addresses": [instruction.address for instruction in self.instructions],
        }

    def serialize(self) -> bytes:
        return (canonical_json(self.to_document()) + "\n").encode("utf-8")

    def fingerprint(self) -> str:
        return hashlib.sha256(self.serialize()).hexdigest()


def bridge_program(
    memory: bytes | bytearray,
    *,
    entry: int,
    end: int,
    region_boundaries: Iterable[int] = (),
    mode: CFGMode = CFGMode.CLOSED,
    evidence: EvidenceClass = EvidenceClass.PROVEN,
) -> NES6502Program:
    """Run a NES6502 region through the shared Phase-2 structural pipeline."""
    instructions = bridge_region(memory, entry=entry, end=end, evidence=evidence)
    region_bytes = bytes(memory[entry:end])
    source = ProgramSource(
        NES6502_ARCHITECTURE,
        adapter=NES6502_ADAPTER,
        address_width_bits=NES6502_ADDRESS_BITS,
        endianness="little",
        input_sha256=hashlib.sha256(region_bytes).hexdigest(),
    )
    try:
        cfg = build_cfg(
            instructions,
            source=source,
            entries=[EntryPoint(entry, evidence)],
            mode=mode,
            region_boundaries=region_boundaries,
        )
        discovery = discover_functions(cfg, program_entries=[entry])
        call_graph = build_call_graph(discovery)
        units = build_translation_units(discovery, call_graph=call_graph)
        classification = classify_indirect_control_flow(units)
    except (ValueError, KeyError) as exc:
        raise NES6502BridgeError(f"NES6502 region cannot be represented: {exc}") from exc
    return NES6502Program(
        source=source,
        entry=entry,
        end=end,
        region_sha256=hashlib.sha256(region_bytes).hexdigest(),
        instructions=instructions,
        cfg=cfg,
        discovery=discovery,
        call_graph=call_graph,
        units=units,
        classification=classification,
    )


__all__ = [
    "BRIDGE_VERSION",
    "NES6502_ADAPTER",
    "NES6502_ADDRESS_BITS",
    "NES6502_ARCHITECTURE",
    "NES6502BridgeError",
    "NES6502Program",
    "bridge_program",
    "bridge_region",
    "classify_flow",
    "instruction_from_nes6502",
]
