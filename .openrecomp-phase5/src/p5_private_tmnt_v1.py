#!/usr/bin/env python3
"""Phase-5 private TMNT compatibility analysis (P5-11).

Private, non-redistributed analysis of the local compatibility image
(`PRIVATE_LOCAL_COMPATIBILITY_FIXTURE`): hashes, iNES metadata, cartridge
inventory, the candidate SxROM fixed-bank vector frame and a bounded candidate
instruction frontier, plus the precise fail-closed blockers.

No ROM bytes are copied, stored, packaged or echoed. The candidate frontier is
an analysis artifact only: it is NOT the public proof fixture, it does not
claim mapper-1 execution, and the stated reset/NMI/IRQ vector frame is the
documented SxROM power-on fixed-bank frame (the last PRG bank at
$C000-$FFFF); the $8000-$BFFF switchable bank and all MMC1 banking are
unresolved without a mapper model.
"""
from __future__ import annotations

import pathlib
import sys
from collections import Counter
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for entry in (str(ROOT), str(ROOT / "tools"), str(ROOT / ".openrecomp-phase5" / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import adapters.nes6502 as nes_adapter  # noqa: E402
import nes_rom_v1 as frozen_rom  # noqa: E402
import p5_ines_v1 as ingestion  # noqa: E402

PRIVATE_ROM = pathlib.Path(r"D:\OpenRecomp\Roms\phase1\nes\primary\tmnt.nes")
FRONTIER_BUDGET = 20000


class PrivateAnalysisError(ValueError):
    """Fail-closed private analysis error."""


def analyse(path: pathlib.Path = PRIVATE_ROM) -> dict[str, Any]:
    if not path.is_file():
        raise PrivateAnalysisError("private compatibility fixture is not present")
    data = path.read_bytes()
    inventory = ingestion.ingest(data, source_label="private_tmnt").to_document()

    prg_offset = 16 + int(inventory["trainer_bytes"])
    prg_bytes = int(inventory["prg_bytes"])
    prg = data[prg_offset:prg_offset + prg_bytes]
    if len(prg) != prg_bytes:
        raise PrivateAnalysisError("private PRG segment is truncated")
    if len(prg) < 0x4000:
        raise PrivateAnalysisError("private PRG is smaller than one bank")

    last_bank = prg[-0x4000:]
    vectors = {
        "nmi": int.from_bytes(last_bank[0x3FFA:0x3FFC], "little"),
        "reset": int.from_bytes(last_bank[0x3FFC:0x3FFE], "little"),
        "irq": int.from_bytes(last_bank[0x3FFE:0x4000], "little"),
    }

    image = bytearray(0x10000)
    image[0xC000:0x10000] = last_bank
    pending = [vectors["nmi"], vectors["reset"], vectors["irq"]]
    visited: dict[int, dict] = {}
    histogram: Counter = Counter()
    outside_targets: set[int] = set()
    stop_reason = "budget"
    truncated = False
    while pending:
        address = pending.pop()
        if address in visited:
            continue
        if not (0xC000 <= address <= 0xFFFF):
            outside_targets.add(address)
            continue
        if len(visited) >= FRONTIER_BUDGET:
            truncated = True
            stop_reason = "budget"
            break
        try:
            instruction = nes_adapter.decode_full(bytes(image), address)
        except nes_adapter.NES6502Error as exc:
            stop_reason = f"decode: 0x{address:04x}: {exc}"
            break
        visited[address] = instruction
        mnemonic, mode, kind = nes_adapter.OPCODES[instruction["word"]]
        histogram[(mnemonic, mode, kind)] += 1
        op = instruction["op"]
        if op == "brk":
            pending.append((address + 2) & 0xFFFF)
        elif op in ("rts", "rti"):
            pass
        elif op == "jmp":
            if "indirect" not in instruction:
                pending.append(instruction["target"])
        elif op == "jsr":
            pending.append(instruction["a16"])
            pending.append((address + instruction["length"]) & 0xFFFF)
        elif op in {name for name, _flag, _taken in nes_adapter.BRANCHES.values()}:
            pending.append(instruction["target"])
            pending.append((address + instruction["length"]) & 0xFFFF)
        else:
            pending.append((address + instruction["length"]) & 0xFFFF)

    try:
        frozen_rom.make_mapper(data)
        mapper_fail_closed = False
        mapper_error = ""
    except frozen_rom.NESROMError as exc:
        mapper_fail_closed = True
        mapper_error = str(exc)

    p5_cartridge_fail_closed = False
    try:
        import p5_bus_v1 as bus_module
        bus_module.P5Cartridge(data, inventory)
    except bus_module.P5BusError:
        p5_cartridge_fail_closed = True

    return {
        "stage": "P5-11",
        "classification": "PRIVATE_LOCAL_COMPATIBILITY_FIXTURE",
        "source_path": str(path),
        "image_sha256": inventory["image_sha256"],
        "image_size": inventory["actual_size"],
        "container": inventory["container"],
        "mapper": inventory["mapper"],
        "submapper": inventory["submapper"],
        "mirroring": inventory["mirroring"],
        "prg_bytes": inventory["prg_bytes"],
        "chr_bytes": inventory["chr_bytes"],
        "chr_is_ram": inventory["chr_is_ram"],
        "battery": inventory["battery"],
        "trainer_bytes": inventory["trainer_bytes"],
        "prg_sha256": inventory["prg_sha256"],
        "chr_sha256": inventory["chr_sha256"],
        "nes2_fields": inventory["nes2_fields"],
        "execution_status": inventory["execution_status"],
        "mapper_fail_closed": mapper_fail_closed,
        "mapper_error": mapper_error,
        "p5_cartridge_fail_closed": p5_cartridge_fail_closed,
        "candidate_frame": {
            "basis": "documented SxROM power-on fixed-bank frame: last PRG bank "
                     "at $C000-$FFFF; the $8000-$BFFF switchable bank and all "
                     "MMC1 banking are unresolved without a mapper model",
            "claim": "CANDIDATE / NOT PROVEN",
            "bank_sha256": __import__("hashlib").sha256(last_bank).hexdigest(),
            "vectors": vectors,
        },
        "candidate_frontier": {
            "claim": "CANDIDATE / NOT PROVEN",
            "instructions": len(visited),
            "distinct_opcode_forms": len(histogram),
            "opcode_histogram": [
                {"mnemonic": key[0], "mode": key[1], "kind": key[2], "count": count}
                for key, count in sorted(histogram.items())
            ],
            "outside_bank_targets": sorted(outside_targets),
            "truncated": truncated,
            "stop_reason": stop_reason,
        },
        "blockers": [
            {
                "code": "BLOCKED_UNSUPPORTED_MAPPER",
                "detail": "mapper 1 (MMC1/SxROM) banking is not implemented; "
                          "PRG bank modes, CHR banking and mirroring control "
                          "are unresolved",
            },
            {
                "code": "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE",
                "detail": "control-flow targets outside the fixed bank need an "
                          "MMC1 bank-switch model: "
                          + ", ".join(f"0x{value:04x}" for value in sorted(outside_targets)),
            },
            {
                "code": "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE",
                "detail": f"candidate frontier stopped at {stop_reason}",
            },
        ],
        "public_claim": "none; this analysis must not enter the public package",
    }


__all__ = ["FRONTIER_BUDGET", "PRIVATE_ROM", "PrivateAnalysisError", "analyse"]
