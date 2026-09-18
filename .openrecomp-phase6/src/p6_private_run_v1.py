#!/usr/bin/env python3
"""Phase-6 private TMNT compatibility pipeline run (P6-10).

Re-runs the audited public pipeline stages against the private local
compatibility image (`PRIVATE_LOCAL_COMPATIBILITY_FIXTURE`) now that the MMC1
subset exists, using only the existing private path and recording only hashes,
metadata, counts, addresses, classifications and stop reasons:

1. ingestion: iNES/NES 2.0 inventory plus the MMC1 subset classification
   (supported profile: 8 x 16 KiB PRG, 16 x 8 KiB CHR, no PRG-RAM/battery);
2. cartridge service: the P6-07 `P6Mmc1Cartridge` power-on mapper state;
3. reference platform: the P6-09 independent MMC1 platform power-on state and
   reset-vector readback;
4. frontier: the frozen documented-control-flow walk fails closed at the first
   undecodable reachable address, and a bounded candidate traversal records how
   far it reaches and why it stops;
5. structure: the shared Phase-2 neutral structure attempt fails closed for the
   private image because no code/data span evidence exists;
6. emission/runtime: host translation is not attempted without a complete
   reachable instruction set (no fabricated targets); MMC1 runtime support
   generation is deterministic and is recorded by hash only, never stored;
7. native build/execution: not attempted because no host translation exists.

No ROM bytes or ROM-derived binary copies are returned, stored, echoed or
written to evidence. TMNT playability is not required for Phase-6 PASS.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys
from typing import Any, Iterable

ROOT = pathlib.Path(__file__).resolve().parents[2]
for entry in (str(ROOT), str(ROOT / "tools"),
              str(ROOT / ".openrecomp-phase5" / "src"),
              str(ROOT / ".openrecomp-phase6" / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import adapters.nes6502 as nes_adapter  # noqa: E402
import nes_rom_v1 as frozen_rom  # noqa: E402
import p5_bus_v1 as p5_bus  # noqa: E402
import p5_frontier_v1 as frozen_frontier  # noqa: E402
import p6_cartridge_v1 as cartridge_module  # noqa: E402
import p6_emit_v1 as emit_module  # noqa: E402
import p6_frontier_v1 as p6_frontier  # noqa: E402
import p6_ines_v1 as ingestion  # noqa: E402
import p6_mapper1_variant_v1 as variant_module  # noqa: E402
import p6_private_fixture_v1 as private_fixture  # noqa: E402
import p6_reference_v1 as reference_module  # noqa: E402
import p6_structure_v1 as structure_module  # noqa: E402

PRIVATE_ROM = private_fixture.PRIVATE_ROM
PIPELINE_PLAN = (0x00, 0x01, 0x80)
FRONTIER_BUDGET = 20000
FIXED_BANK_ORIGIN = 0xC000
LOW_WINDOW_BASE = 0x8000


class PrivateRunError(ValueError):
    """Fail-closed private pipeline run error."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _metadata(inventory: dict[str, Any]) -> dict[str, Any]:
    prg_bytes = int(inventory["prg_bytes"])
    chr_bytes = int(inventory["chr_bytes"])
    prg_banks = prg_bytes // 0x4000
    chr_banks = chr_bytes // 0x2000
    if prg_banks <= 0 or chr_banks <= 0:
        raise PrivateRunError("private PRG/CHR sizes are not bank aligned")
    return {
        "fixture": "private_tmnt",
        "rom_sha256": inventory["image_sha256"],
        "prg_size": prg_bytes,
        "prg_banks": prg_banks,
        "chr_size": chr_bytes,
        "chr_banks": chr_banks,
        "fixed_bank_origin": FIXED_BANK_ORIGIN,
        "fixed_bank_index": prg_banks - 1,
    }


def _candidate_walk(image: bytes, roots: Iterable[int],
                    budget: int) -> dict[str, Any]:
    pending = list(roots)
    visited: dict[int, dict] = {}
    predecessor: dict[int, dict] = {}
    indirect_sites: list[dict[str, Any]] = []
    interrupt_sites: list[int] = []
    dynamic_returns: list[dict[str, Any]] = []
    outside_targets: set[int] = set()
    stop: dict[str, Any] | None = None
    while pending:
        address = pending.pop()
        if address in visited:
            continue
        if not FIXED_BANK_ORIGIN <= address <= 0xFFFF and not (
                LOW_WINDOW_BASE <= address < FIXED_BANK_ORIGIN):
            outside_targets.add(address)
            continue
        if len(visited) >= budget:
            stop = {"address": address, "reason": "budget", "kind": "budget",
                    "predecessor": predecessor.get(address)}
            break
        try:
            instruction = nes_adapter.decode_full(image, address)
        except nes_adapter.NES6502Error as exc:
            stop = {"address": address, "reason": str(exc),
                    "kind": "undocumented_opcode",
                    "predecessor": predecessor.get(address)}
            break
        visited[address] = instruction
        if instruction["op"] == "brk":
            interrupt_sites.append(address)
        if instruction["op"] in ("rts", "rti"):
            dynamic_returns.append({"address": address,
                                    "instruction": instruction["op"]})
        targets, unresolved = frozen_frontier.successors(instruction, address)
        if unresolved:
            indirect_sites.append({
                "address": address,
                "instruction": instruction["op"],
                "pointer": instruction.get("indirect"),
            })
        for target in targets:
            if target not in visited:
                predecessor.setdefault(target, {
                    "address": address,
                    "instruction": instruction["op"],
                })
            pending.append(target)

    covered: set[int] = set()
    for address, instruction in visited.items():
        covered.update(range(address, address + instruction["length"]))
    low = sorted(address for address in visited
                 if LOW_WINDOW_BASE <= address < FIXED_BANK_ORIGIN)
    high = sorted(address for address in visited
                  if address >= FIXED_BANK_ORIGIN)
    opcode_histogram: dict[str, int] = {}
    for instruction in visited.values():
        opcode_histogram[instruction["op"]] = (
            opcode_histogram.get(instruction["op"], 0) + 1)
    return {
        "claim": "CANDIDATE / NOT PROVEN",
        "basis": "power-on MMC1 image (fixed last bank at $C000-$FFFF, PRG "
                 "register 0 bank in the $8000-$BFFF window); documented static "
                 "control flow only, indirect jumps never guessed",
        "budget": budget,
        "instructions": len(visited),
        "bytes": len(covered),
        "low_window_instructions": len(low),
        "fixed_window_instructions": len(high),
        "low_window_range": [low[0], low[-1]] if low else None,
        "distinct_opcode_forms": len(opcode_histogram),
        "opcode_histogram": dict(sorted(opcode_histogram.items())),
        "indirect_sites": sorted(indirect_sites,
                                 key=lambda item: item["address"]),
        "interrupt_sites": sorted(interrupt_sites),
        "dynamic_returns": sorted(dynamic_returns,
                                  key=lambda item: item["address"]),
        "outside_targets": sorted(outside_targets),
        "pending_at_stop": len(pending),
        "stop": stop,
        "truncated": bool(stop and stop["kind"] == "budget"),
    }


def run(path: pathlib.Path = PRIVATE_ROM,
        plan: tuple[int, ...] = PIPELINE_PLAN,
        budget: int = FRONTIER_BUDGET) -> dict[str, Any]:
    if not path.is_file():
        raise PrivateRunError("private compatibility fixture is not present")
    if not plan:
        raise PrivateRunError("input plan is empty")
    for value in plan:
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 0xFF:
            raise PrivateRunError("input plan values must be 8-bit integers")
    if isinstance(budget, bool) or not isinstance(budget, int) or budget <= 0:
        raise PrivateRunError("frontier budget must be a positive integer")
    data = path.read_bytes()
    inventory = ingestion.ingest(data, source_label="private_tmnt")
    if inventory["phase6"]["status"] != "SUPPORTED_MMC1":
        raise PrivateRunError(
            "private image is not classified SUPPORTED_MMC1")
    metadata = _metadata(inventory)
    image = p6_frontier.build_mmc1_cpu_image(data, metadata)
    roots = [inventory["vectors"]["reset"], inventory["vectors"]["nmi"],
             inventory["vectors"]["irq"]]

    p6_01 = private_fixture.inventory(path)
    ledger_variant = variant_module.classify_variant(inventory)

    try:
        cartridge = cartridge_module.P6Mmc1Cartridge(data, inventory)
        cartridge_status = "SUPPORTED_MMC1"
        cartridge_state = cartridge.mapper_state()
        cartridge_error = ""
    except cartridge_module.P6CartridgeError as exc:
        cartridge_status = "FAIL_CLOSED"
        cartridge_state = {}
        cartridge_error = str(exc)

    reference_platform = reference_module.P6Mmc1ReferencePlatform(data, inventory)
    reference_low, reference_high = reference_platform.prg_window_banks()
    reset_vector = reference_platform.read_memory(0xFFFC) | (
        reference_platform.read_memory(0xFFFD) << 8)

    try:
        frozen_frontier.reachable_frontier(image, roots)
        frontier_status = "OK"
        frontier_error = ""
    except frozen_frontier.FrontierError as exc:
        frontier_status = "FAIL_CLOSED"
        frontier_error = str(exc)

    candidate = _candidate_walk(image, roots, budget)

    try:
        structure_module.build_structure(data, metadata, inventory)
        structure_status = "OK"
        structure_error = ""
    except Exception as exc:  # noqa: BLE001 - deterministic classification
        structure_status = "FAIL_CLOSED"
        structure_error = f"{type(exc).__name__}: {exc}"

    try:
        frozen_rom.make_mapper(data)
        frozen_mapper_status = "OK"
        frozen_mapper_error = ""
    except frozen_rom.NESROMError as exc:
        frozen_mapper_status = "FAIL_CLOSED"
        frozen_mapper_error = str(exc)

    try:
        p5_bus.P5Cartridge(data, inventory)
        p5_bus_status = "OK"
        p5_bus_error = ""
    except p5_bus.P5BusError as exc:
        p5_bus_status = "FAIL_CLOSED"
        p5_bus_error = str(exc)

    support = emit_module.emit_support(data, metadata, plan)
    support_sha256 = _sha256(support.encode("utf-8"))
    del support

    stop = candidate["stop"] or {}
    blockers: list[dict[str, str]] = [
        {
            "code": "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE",
            "stage": "frontier",
            "detail": "documented-control-flow reachable frontier fails closed "
                      f"at 0x{stop.get('address', 0):04x} "
                      f"({stop.get('reason', 'no reachable stop recorded')}) "
                      "after "
                      f"{candidate['instructions']} candidate instructions; the "
                      "private image declares no code/data boundary evidence",
        },
        {
            "code": "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE",
            "stage": "indirect_control_flow",
            "detail": "unresolved indirect jump sites at "
                      + ", ".join(f"0x{item['address']:04x}"
                                  for item in candidate["indirect_sites"])
                      + " through zero-page pointer(s) "
                      + ", ".join(sorted({f"0x{(item['pointer'] or 0):04x}"
                                          for item in candidate["indirect_sites"]}))
                      + "; runtime jump-table targets must not be guessed",
        },
        {
            "code": "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE",
            "stage": "bank_state",
            "detail": f"{candidate['low_window_instructions']} candidate "
                      "instructions reach the mapper-switched "
                      "$8000-$BFFF window under the power-on PRG bank only; "
                      "runtime bank-state evidence is required to resolve the "
                      "actual bank sequence",
        },
        {
            "code": "NOT_TESTED",
            "stage": "runtime_platform",
            "detail": "PPU/APU/input/timing requirements beyond the bounded "
                      "Phase-5/6 platform model cannot be assessed until "
                      "translation completes",
        },
        {
            "code": "SUPERSEDED",
            "stage": "mapper",
            "detail": "the P6-01 blocker BLOCKED_MMC1_MAPPER_NOT_YET_IMPLEMENTED "
                      "no longer applies: the MMC1 subset is implemented and "
                      "differentially verified through P6-09",
        },
    ]

    return {
        "stage": "P6-10",
        "classification": "PRIVATE_LOCAL_COMPATIBILITY_FIXTURE",
        "source_path": str(path),
        "image_sha256": inventory["image_sha256"],
        "image_size": inventory["actual_size"],
        "container": inventory["container"],
        "mapper": inventory["mapper"],
        "submapper": inventory["submapper"],
        "mapper_name": inventory["mapper_name"],
        "mirroring": inventory["mirroring"],
        "prg_bytes": inventory["prg_bytes"],
        "chr_bytes": inventory["chr_bytes"],
        "chr_is_ram": inventory["chr_is_ram"],
        "battery": inventory["battery"],
        "trainer_bytes": inventory["trainer_bytes"],
        "four_screen": inventory["four_screen"],
        "prg_sha256": inventory["prg_sha256"],
        "chr_sha256": inventory["chr_sha256"],
        "nes2_fields": inventory["nes2_fields"],
        "vectors": inventory["vectors"],
        "vectors_source": inventory["vectors_source"],
        "mmc1_classification": inventory["phase6"],
        "variant_classification": ledger_variant,
        "p6_01_recorded_execution_status": p6_01["execution_status"],
        "ingestion": {
            "status": "SUPPORTED_MMC1",
            "execution_status": "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE",
        },
        "cartridge": {
            "status": cartridge_status,
            "error": cartridge_error,
            "prg_banks_16k": inventory["phase6"]["prg_banks_16k"],
            "chr_banks_8k": inventory["phase6"]["chr_banks_8k"],
            "power_on_registers": cartridge_state.get("registers"),
            "power_on_prg_window": [
                cartridge_state.get("prg_window_8000_bank"),
                cartridge_state.get("prg_window_c000_bank"),
            ],
            "power_on_chr_mode": cartridge_state.get("chr_mode"),
            "power_on_mirroring": cartridge_state.get("mirroring"),
            "prg_ram_enabled": cartridge_state.get("prg_ram_enabled"),
        },
        "reference_platform": {
            "power_on_prg_window": [reference_low, reference_high],
            "power_on_chr_banks": reference_platform.chr_banks(),
            "power_on_registers": list(reference_platform.serial.reg),
            "reset_vector_readback": reset_vector,
        },
        "frontier": {
            "frozen_status": frontier_status,
            "frozen_error": frontier_error,
            "candidate": candidate,
        },
        "structure": {
            "status": structure_status,
            "error": structure_error,
        },
        "translation": {
            "status": "NOT_ATTEMPTED",
            "reason": "no complete reachable instruction set exists; fabricating "
                      "translation units or indirect targets is not permitted",
        },
        "runtime_support": {
            "status": "OK",
            "plan": list(plan),
            "support_sha256": support_sha256,
            "note": "generated in memory only for the deterministic hash; no "
                    "generated source is stored or echoed",
        },
        "native_build": {
            "status": "NOT_ATTEMPTED",
            "reason": "no host translation was emitted",
        },
        "native_execution": {
            "status": "NOT_ATTEMPTED",
            "reason": "no native executable exists for the private image",
        },
        "preserved_phase5_boundary": {
            "frozen_mapper_status": frozen_mapper_status,
            "frozen_mapper_error": frozen_mapper_error,
            "p5_bus_status": p5_bus_status,
            "p5_bus_error": p5_bus_error,
        },
        "blockers": blockers,
        "public_claim": "none; this analysis must not enter the public package",
    }


__all__ = [
    "FRONTIER_BUDGET",
    "PIPELINE_PLAN",
    "PRIVATE_ROM",
    "PrivateRunError",
    "run",
]
