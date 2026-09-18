#!/usr/bin/env python3
"""Phase-5 bounded APU/input/timing/interrupt platform boundary (P5-07).

A deterministic virtual platform driving the P5-05 CPU bus and P5-06 PPU for
the audited public fixture:

* controller input plan: one controller-0 byte per virtual frame, applied at
  frame starts and recorded in the platform transcript;
* virtual frame timing: 29780 virtual clock units per frame with a 2273-unit
  vblank window (documented NTSC nominal), instruction costs from the
  documented base-cycle table. Page-cross and taken-branch penalties are NOT
  modelled - this is a bounded deterministic model, not cycle accuracy;
* vblank/NMI: the vblank flag is set at frame start and cleared at window end
  (or earlier by a PPUSTATUS read); an NMI is queued at frame start when
  PPUCTRL bit 7 is set and delivered by the driver at the next instruction
  boundary;
* IRQ: a documented asserted line interface with explicit acknowledgment; the
  audited fixture uses software BRK only, so hardware IRQ delivery remains a
  bounded interface, not a compatibility claim;
* APU: register latches and status are owned by the P5-05 bus; this module
  only records accesses required by the fixture and makes no audio claim.

Every access and event is recorded in a deterministic transcript with a
canonical digest.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
from typing import Any, Iterable

ROOT = pathlib.Path(__file__).resolve().parents[2]
for entry in (str(ROOT), str(ROOT / "tools"), str(ROOT / ".openrecomp-phase5" / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

FRAME_CLOCK_UNITS = 29780
VBLANK_CLOCK_UNITS = 2273

_MODE_KIND_COST = {
    ("impl", "impl"): 2,
    ("impl", "ctrl"): 2,
    ("acc", "acc"): 2,
    ("imm", "read"): 2,
    ("zp", "read"): 3,
    ("zp", "write"): 3,
    ("zp", "rmw"): 5,
    ("zpx", "read"): 4,
    ("zpx", "write"): 4,
    ("zpx", "rmw"): 6,
    ("zpy", "read"): 4,
    ("zpy", "write"): 4,
    ("abs", "read"): 4,
    ("abs", "write"): 4,
    ("abs", "rmw"): 6,
    ("absx", "read"): 4,
    ("absx", "write"): 5,
    ("absx", "rmw"): 7,
    ("absy", "read"): 4,
    ("absy", "write"): 5,
    ("ind", "ctrl"): 5,
    ("indx", "read"): 6,
    ("indx", "write"): 6,
    ("indy", "read"): 6,
    ("indy", "write"): 6,
    ("rel", "ctrl"): 2,
}

_SPECIAL_COST = {
    "brk": 7,
    "jsr": 6,
    "rts": 6,
    "rti": 6,
    "jmp": None,
    "impl": None,
    "acc": None,
}

_IMPLIED_TWO = frozenset({
    0x0A, 0x2A, 0x4A, 0x6A,
    0x18, 0xD8, 0x58, 0xB8,
    0xCA, 0x88, 0xE8, 0xC8,
    0xEA, 0x38, 0xF8, 0x78,
    0xAA, 0xA8, 0xBA, 0x8A, 0x9A, 0x98,
})
_IMPLIED_THREE = frozenset({0x08, 0x28, 0x48, 0x68})


def _build_cost_table() -> dict[int, int]:
    import adapters.nes6502 as nes_adapter

    table: dict[int, int] = {}
    for opcode, (mnemonic, mode, kind) in sorted(nes_adapter.OPCODES.items()):
        if opcode in _IMPLIED_TWO:
            table[opcode] = 2
            continue
        if opcode in _IMPLIED_THREE:
            table[opcode] = 3
            continue
        if mnemonic == "brk":
            table[opcode] = 7
            continue
        if mnemonic in ("jsr", "rts", "rti"):
            table[opcode] = 6
            continue
        if mnemonic == "jmp":
            table[opcode] = 3 if mode == "abs" else 5
            continue
        if opcode in nes_adapter.BRANCHES:
            table[opcode] = 2
            continue
        cost = _MODE_KIND_COST.get((mode, kind))
        if cost is None:
            raise ValueError(
                f"no documented base cost for {mnemonic} {mode} ({kind})")
        table[opcode] = cost
    if len(table) != len(nes_adapter.OPCODES):
        raise ValueError("cost table does not cover every official opcode")
    return table


INSTRUCTION_COST = _build_cost_table()


class P5PlatformError(ValueError):
    """Fail-closed platform error."""


def cost_of(opcode: int) -> int:
    if isinstance(opcode, bool) or not isinstance(opcode, int):
        raise P5PlatformError(f"opcode {opcode!r} is not an integer")
    cost = INSTRUCTION_COST.get(opcode)
    if cost is None:
        raise P5PlatformError(
            f"opcode 0x{opcode:02x} has no documented cost (unsupported or "
            "undocumented opcode fails closed)")
    return cost


class P5Platform:
    """Deterministic virtual frame/vblank/input/interrupt scheduler."""

    def __init__(
        self,
        bus,
        *,
        input_plan: Iterable[int],
        frame_units: int = FRAME_CLOCK_UNITS,
        vblank_units: int = VBLANK_CLOCK_UNITS,
    ) -> None:
        if isinstance(frame_units, bool) or not isinstance(frame_units, int) or frame_units <= 0:
            raise P5PlatformError("frame_units must be a positive integer")
        if isinstance(vblank_units, bool) or not isinstance(vblank_units, int) or not (
                0 < vblank_units < frame_units):
            raise P5PlatformError("vblank_units must be inside (0, frame_units)")
        plan = []
        for item in input_plan:
            if isinstance(item, bool) or not isinstance(item, int) or not (0 <= item <= 0xFF):
                raise P5PlatformError(f"input plan value 0x{item!r} is outside 8 bits")
            plan.append(item)
        if not plan:
            raise P5PlatformError("input plan must not be empty")
        self.bus = bus
        self.input_plan = tuple(plan)
        self.frame_units = frame_units
        self.vblank_units = vblank_units
        self.clock = 0
        self.frame_index = 0
        self.next_frame_start = 0
        self.next_vblank_end = vblank_units
        self.pending_nmi = 0
        self.nmi_delivered = 0
        self.irq_line = False
        self.irq_pending = False
        self.irq_delivered = 0
        self.frames: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.instructions = 0
        self.tile_digest = None

    # -- driver interface ---------------------------------------------------
    def begin_instruction(self, opcode: int) -> None:
        cost = cost_of(opcode)
        target = self.clock + cost
        while self.next_frame_start <= target:
            self._frame_start(self.next_frame_start)
        while self.next_vblank_end <= target:
            self._vblank_end(self.next_vblank_end)
        self.clock = target
        self.instructions += 1

    def _frame_start(self, at: int) -> None:
        plan_value = self.input_plan[
            min(self.frame_index, len(self.input_plan) - 1)]
        self.bus.controllers.set_controller(0, plan_value)
        ppu = self.bus.ppu
        ppu.set_vblank(True)
        nmi_enabled = ppu.nmi_enabled()
        if nmi_enabled:
            self.pending_nmi += 1
        digest = ppu.digest()
        self.frames.append({
            "index": self.frame_index,
            "clock": at,
            "input": plan_value,
            "nmi_queued": bool(nmi_enabled),
            "tile_space_sha256": hashlib.sha256(ppu.tile_space()).hexdigest(),
            "ppu_digest": digest,
        })
        self.events.append({"kind": "frame_start", "frame": self.frame_index,
                            "clock": at, "input": plan_value,
                            "nmi_queued": bool(nmi_enabled)})
        self.frame_index += 1
        self.next_frame_start += self.frame_units
        self.next_vblank_end = at + self.vblank_units

    def _vblank_end(self, at: int) -> None:
        self.bus.ppu.set_vblank(False)
        self.events.append({"kind": "vblank_end", "clock": at})
        self.next_vblank_end += self.frame_units

    def take_nmi(self) -> bool:
        if self.pending_nmi <= 0:
            return False
        self.pending_nmi -= 1
        self.nmi_delivered += 1
        self.events.append({"kind": "nmi_delivered", "clock": self.clock})
        return True

    def set_irq_line(self, asserted: bool) -> None:
        asserted = bool(asserted)
        self.irq_line = asserted
        if asserted:
            self.irq_pending = True
            self.events.append({"kind": "irq_asserted", "clock": self.clock})
        else:
            self.irq_pending = False
            self.events.append({"kind": "irq_cleared", "clock": self.clock})

    def take_irq(self) -> bool:
        if not self.irq_pending:
            return False
        self.irq_pending = False
        self.irq_delivered += 1
        self.events.append({"kind": "irq_delivered", "clock": self.clock})
        return True

    # -- transcript ---------------------------------------------------------
    def to_document(self) -> dict[str, Any]:
        return {
            "frame_units": self.frame_units,
            "vblank_units": self.vblank_units,
            "clock": self.clock,
            "instructions": self.instructions,
            "frame_count": self.frame_index,
            "nmi_queued_total": sum(1 for item in self.frames if item["nmi_queued"]),
            "nmi_delivered": self.nmi_delivered,
            "pending_nmi": self.pending_nmi,
            "irq_delivered": self.irq_delivered,
            "irq_line": self.irq_line,
            "input_plan": list(self.input_plan),
            "frames": self.frames,
            "events": self.events,
        }

    def digest(self) -> str:
        text = json.dumps(self.to_document(), indent=2, sort_keys=True) + "\n"
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


def timing_document() -> dict[str, Any]:
    return {
        "frame_units": FRAME_CLOCK_UNITS,
        "vblank_units": VBLANK_CLOCK_UNITS,
        "instruction_costs": "documented base cycles per official opcode",
        "page_cross_penalty": "not modelled",
        "taken_branch_penalty": "not modelled",
        "cycle_accuracy": False,
        "input": "one controller-0 byte per virtual frame from the declared plan",
        "nmi": "queued at vblank start when PPUCTRL bit 7 is set; delivered by "
               "the driver at the next instruction boundary",
        "irq": "explicit asserted-line interface with acknowledgment; the "
               "fixture uses software BRK only",
        "apu": "register latches/status only; no audio equivalence claim",
        "cost_table_sha256": hashlib.sha256(
            ("\n".join(f"{opcode:02x} {cost}" for opcode, cost in
                       sorted(INSTRUCTION_COST.items())) + "\n").encode("utf-8")
        ).hexdigest(),
    }


__all__ = [
    "FRAME_CLOCK_UNITS",
    "INSTRUCTION_COST",
    "P5Platform",
    "P5PlatformError",
    "VBLANK_CLOCK_UNITS",
    "cost_of",
    "timing_document",
]
