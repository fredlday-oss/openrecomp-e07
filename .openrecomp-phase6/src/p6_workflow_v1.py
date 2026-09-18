#!/usr/bin/env python3
"""Phase-6 reusable deterministic ROM-to-native workflow (P6-12).

One deterministic command/workflow that accepts a local ROM path and:

1. inventories the image (container, mapper, mirroring, PRG/CHR, vectors) by
   metadata and hashes only, never copying, storing or echoing ROM bytes;
2. classifies mapper/platform support against the audited `MMC1_SUBSET_V1`
   boundary and the explicit variant ledger;
3. recovers the documented reachable CPU/control-flow frontier from the
   power-on fixed-last-bank frame and reports the bounded candidate traversal;
4. classifies undocumented opcodes and unresolved indirect targets;
5. statically recompiles the region only when the bounded supported subset
   permits it (contiguous, fully documented, no runtime-bank ambiguity, no
   undeclared indirect sites);
6. generates the native host program and MMC1 runtime support sources into the
   caller-owned workspace, recording only deterministic hashes;
7. builds the native target through the shared Phase-2 pipeline when the
   toolchain is available;
8. reports exact fail-closed blockers with explicit classifications for
   unsupported container, mapper, MMC1 variant, opcode, control-flow,
   code/data-boundary, bank-state, toolchain, build and platform/runtime
   conditions.

Fail-closed rules:

* the source ROM is never copied, packaged or written by this module;
* unsupported mapper/hardware paths terminate with explicit reasons;
* indirect targets are never guessed; the only accepted indirect site is the
  declared `$02FF` page-wrap run-exit thunk mapped to the `p6.exit` service;
* runtime-bank ambiguity (reachable code in the mapper-switched window) blocks
  translation until bank-state evidence exists;
* native execution is only ever the generated host executable running through
  the typed runtime ABI; original guest CPU code is never executed on the host.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
from typing import Any, Iterable, Sequence

ROOT = pathlib.Path(__file__).resolve().parents[2]
for entry in (str(ROOT), str(ROOT / "tools"),
              str(ROOT / ".openrecomp-phase5" / "src"),
              str(ROOT / ".openrecomp-phase6" / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import adapters.nes6502 as nes_adapter  # noqa: E402
import p5_frontier_v1 as frozen_frontier  # noqa: E402
import p6_cartridge_v1 as cartridge_module  # noqa: E402
import p6_emit_v1 as emit_module  # noqa: E402
import p6_frontier_v1 as p6_frontier  # noqa: E402
import p6_ines_v1 as ingestion  # noqa: E402
import p6_mapper1_variant_v1 as variant_module  # noqa: E402
from openrecomp.frontends import nes6502 as bridge  # noqa: E402

WORKFLOW_ID = "p6_rom_to_native_v1"
DEFAULT_PLAN = (0x00, 0x01, 0x80)
DEFAULT_BUDGET = 20000
DEFAULT_RUNS = 3
DEFAULT_TIMEOUT = 600
LOW_WINDOW_BASE = 0x8000
FIXED_WINDOW_BASE = 0xC000
EXIT_THUNK_POINTER = 0x02FF
DEFAULT_WORKSPACE = ROOT / ".openrecomp-phase6" / "build" / "p6-workflow"

PRIVATE_ROM = pathlib.Path(r"D:\OpenRecomp\Roms\phase1\nes\primary\tmnt.nes")
PRIVATE_SHA256 = "2a9345e608ec0c57470dc6658ce8199ddea9c18076134d9ef2a56f91b0a066d1"
PRIVATE_SIZE = 262160

BLOCKER_CODES = (
    "BLOCKED_UNSUPPORTED_CONTAINER",
    "BLOCKED_UNSUPPORTED_MAPPER",
    "BLOCKED_UNSUPPORTED_MMC1_VARIANT",
    "BLOCKED_UNSUPPORTED_OPCODE",
    "BLOCKED_UNRESOLVED_INDIRECT_CONTROL_FLOW",
    "BLOCKED_CODE_DATA_BOUNDARY",
    "BLOCKED_BANK_STATE_UNRESOLVED",
    "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE",
    "BLOCKED_BY_MISSING_EXTERNAL_TOOLCHAIN",
    "BLOCKED_NATIVE_BUILD_FAILED",
    "BLOCKED_NATIVE_EXECUTION_FAILED",
    "NOT_TESTED",
)


class P6WorkflowError(ValueError):
    """Fail-closed workflow invocation error."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(document: Any) -> str:
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def _display_path(path: pathlib.Path) -> str:
    try:
        relative = path.resolve().relative_to(ROOT)
        return relative.as_posix()
    except ValueError:
        return str(path)


def _source_classification(digest: str) -> str:
    if digest == PRIVATE_SHA256:
        return "PRIVATE_LOCAL_COMPATIBILITY_FIXTURE"
    return "LOCAL_USER_SUPPLIED_ROM"


def _blocker(code: str, stage: str, classification: str,
             detail: str) -> dict[str, str]:
    return {"code": code, "stage": stage, "classification": classification,
            "detail": detail}


def _validate_plan(plan: Sequence[int]) -> tuple[int, ...]:
    if not plan:
        raise P6WorkflowError("input plan is empty")
    values = tuple(plan)
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 0xFF:
            raise P6WorkflowError("input plan values must be 8-bit integers")
    return values


def _validate_positive(name: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise P6WorkflowError(f"{name} must be a positive integer")
    return value


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
        if not LOW_WINDOW_BASE <= address <= 0xFFFF:
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
                 if LOW_WINDOW_BASE <= address < FIXED_WINDOW_BASE)
    high = sorted(address for address in visited if address >= FIXED_WINDOW_BASE)
    opcode_histogram: dict[str, int] = {}
    mode_histogram: dict[str, int] = {}
    for instruction in visited.values():
        opcode_histogram[instruction["op"]] = (
            opcode_histogram.get(instruction["op"], 0) + 1)
        mode = nes_adapter.OPCODES[instruction["word"]][1]
        mode_histogram[mode] = mode_histogram.get(mode, 0) + 1
    return {
        "claim": "CANDIDATE / NOT PROVEN",
        "basis": "power-on MMC1 frame (fixed last bank at $C000-$FFFF, PRG "
                 "register bank in the $8000-$BFFF window); documented static "
                 "control flow only, indirect jumps never guessed",
        "budget": budget,
        "instructions": len(visited),
        "bytes": len(covered),
        "low_window_instructions": len(low),
        "fixed_window_instructions": len(high),
        "low_window_range": [low[0], low[-1]] if low else None,
        "distinct_opcode_forms": len(opcode_histogram),
        "opcode_histogram": dict(sorted(opcode_histogram.items())),
        "mode_histogram": dict(sorted(mode_histogram.items())),
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


def _classify_indirect_site(site: dict[str, Any]) -> dict[str, Any]:
    pointer = site.get("pointer", site.get("indirect"))
    resolved = pointer == EXIT_THUNK_POINTER
    return {
        "address": site["address"],
        "instruction": site["instruction"],
        "pointer": pointer,
        "classification": ("DECLARED_RUN_EXIT_SERVICE" if resolved
                           else "UNRESOLVED_INDIRECT_JUMP"),
        "targets": [],
    }


def _contiguous_region(image: bytes,
                       reached: dict[str, Any]) -> tuple[int, int] | None:
    covered = sorted(set(int(value) for value in reached["covered_bytes"]))
    if not covered:
        return None
    start, end = covered[0], covered[-1] + 1
    if covered != list(range(start, end)):
        return None
    try:
        linear = frozen_frontier.linear_decode(image, start, end)
    except frozen_frontier.FrontierError:
        return None
    if set(linear) != set(int(value) for value in reached["reachable_addresses"]):
        return None
    for instruction in linear.values():
        if instruction["address"] < start or (
                instruction["address"] + instruction["length"] > end):
            return None
    return start, end


def _parse_observable(stdout: str) -> tuple[dict[str, str], list[str]]:
    fields: dict[str, str] = {}
    frames: list[str] = []
    for line in stdout.splitlines():
        if line.startswith("frame["):
            frames.append(line)
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            fields[key] = value
    return fields, frames


def _emit_error_classification(message: str) -> tuple[str, str]:
    if "unresolved indirect site" in message:
        return ("BLOCKED_UNRESOLVED_INDIRECT_CONTROL_FLOW",
                "unresolved_indirect_control_flow")
    if "run-exit thunk" in message:
        return ("BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE",
                "declared_run_exit_missing")
    return ("BLOCKED_UNSUPPORTED_OPCODE", "unsupported_opcode")


def _finalize(document: dict[str, Any]) -> dict[str, Any]:
    blockers = document["blockers"]
    if document["native_execution"]["status"] == "EXECUTED":
        document["status"] = "COMPLETED"
        document["stop_reason"] = "native execution reached"
    else:
        document["status"] = "FAIL_CLOSED"
        if blockers:
            first = blockers[0]
            document["stop_reason"] = (
                f"{first['code']} ({first['stage']}): {first['detail']}")
        else:
            document["stop_reason"] = "workflow did not reach native execution"
    return document


def run(path: pathlib.Path | str = PRIVATE_ROM, *,
        plan: Sequence[int] = DEFAULT_PLAN,
        budget: int = DEFAULT_BUDGET,
        workspace: pathlib.Path | str | None = None,
        build: bool = True,
        run_count: int = DEFAULT_RUNS,
        timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    plan_values = _validate_plan(plan)
    budget_value = _validate_positive("frontier budget", budget)
    runs_value = _validate_positive("native run count", run_count)
    location = pathlib.Path(path)
    if not location.is_file():
        raise P6WorkflowError("ROM path is not present")
    try:
        data = location.read_bytes()
    except OSError as exc:
        raise P6WorkflowError(f"cannot read ROM image: {exc}") from exc
    digest = sha256_bytes(data)
    source_classification = _source_classification(digest)
    workspace_path = pathlib.Path(workspace) if workspace is not None else DEFAULT_WORKSPACE

    document: dict[str, Any] = {
        "workflow": WORKFLOW_ID,
        "stage": "P6-12",
        "status": "FAIL_CLOSED",
        "input": {
            "source_path": _display_path(location),
            "source_classification": source_classification,
            "image_sha256": digest,
            "image_size": len(data),
            "source_rom_copied": False,
        },
        "inventory": {"status": "REJECTED"},
        "mapper_platform": {"status": "NOT_ATTEMPTED"},
        "frontier": {"documented_status": "NOT_ATTEMPTED"},
        "opcode_frontier": {"status": "NOT_ATTEMPTED", "unsupported": []},
        "indirect_control_flow": {"status": "NOT_ATTEMPTED", "sites": []},
        "translation": {"status": "NOT_ATTEMPTED"},
        "generated_sources": {"status": "NOT_GENERATED"},
        "native_build": {"status": "NOT_ATTEMPTED"},
        "native_execution": {"status": "NOT_ATTEMPTED"},
        "platform_runtime": {"status": "NOT_TESTED"},
        "blockers": [],
        "stop_reason": "",
        "public_claim": ("none; private local analysis must not enter any public "
                         "package" if source_classification
                         == "PRIVATE_LOCAL_COMPATIBILITY_FIXTURE"
                         else "bounded audited public MMC1 workflow result only"),
    }
    blockers = document["blockers"]

    try:
        inventory = ingestion.ingest(data, source_label="workflow")
    except ingestion.P6IngestionError as exc:
        document["inventory"] = {
            "status": "REJECTED",
            "container": "unreadable",
            "reason": str(exc),
        }
        blockers.append(_blocker(
            "BLOCKED_UNSUPPORTED_CONTAINER", "ingestion",
            "unsupported_container",
            f"iNES/NES 2.0 ingestion rejected the image: {exc}"))
        return _finalize(document)

    document["inventory"] = {
        "status": "OK",
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
    }

    classification = inventory["phase6"]
    ledger_variant = variant_module.classify_variant(inventory)
    platform: dict[str, Any] = {
        "status": classification["status"],
        "classification": classification,
        "variant": ledger_variant,
        "cartridge": {"status": classification["status"]},
    }
    document["mapper_platform"] = platform
    if classification["status"] == "BLOCKED_UNSUPPORTED_MAPPER":
        blockers.append(_blocker(
            "BLOCKED_UNSUPPORTED_MAPPER", "mapper_platform",
            "unsupported_mapper",
            f"mapper {classification['mapper']} is outside the audited "
            "MMC1/mapper-1 platform path; no hardware behaviour is inferred"))
        return _finalize(document)
    if classification["status"] != "SUPPORTED_MMC1":
        reasons = ", ".join(classification["reasons"]) or "no reasons recorded"
        blockers.append(_blocker(
            "BLOCKED_UNSUPPORTED_MMC1_VARIANT", "mapper_platform",
            "unsupported_mmc1_variant",
            f"mapper-1 image is outside the supported subset: {reasons}"))
        return _finalize(document)

    try:
        cartridge = cartridge_module.P6Mmc1Cartridge(data, inventory)
    except cartridge_module.P6CartridgeError as exc:
        platform["cartridge"] = {"status": "FAIL_CLOSED", "error": str(exc)}
        blockers.append(_blocker(
            "BLOCKED_UNSUPPORTED_MMC1_VARIANT", "mapper_platform",
            "unsupported_mmc1_variant",
            f"MMC1 cartridge construction failed closed: {exc}"))
        return _finalize(document)
    platform["cartridge"] = {
        "status": "SUPPORTED_MMC1",
        "prg_banks_16k": classification["prg_banks_16k"],
        "chr_banks_8k": classification["chr_banks_8k"],
        "power_on_registers": cartridge.mapper_state()["registers"],
        "power_on_prg_window": [
            cartridge.mapper_state()["prg_window_8000_bank"],
            cartridge.mapper_state()["prg_window_c000_bank"],
        ],
        "power_on_chr_mode": cartridge.mapper_state()["chr_mode"],
        "power_on_mirroring": cartridge.mapper_state()["mirroring"],
        "prg_ram_enabled": cartridge.mapper_state()["prg_ram_enabled"],
    }

    prg_banks = classification["prg_banks_16k"]
    metadata = {
        "fixture": "workflow-local-rom",
        "rom_sha256": digest,
        "prg_size": inventory["prg_bytes"],
        "chr_size": inventory["chr_bytes"],
        "prg_banks": prg_banks,
        "chr_banks": classification["chr_banks_8k"],
        "fixed_bank_origin": FIXED_WINDOW_BASE,
        "cpu_origin": FIXED_WINDOW_BASE,
        "vectors": inventory["vectors"],
    }

    image = p6_frontier.build_mmc1_cpu_image(data, metadata)
    roots = [inventory["vectors"]["reset"], inventory["vectors"]["nmi"],
             inventory["vectors"]["irq"]]
    candidate = _candidate_walk(image, roots, budget_value)
    document["frontier"] = {
        "documented_status": "FAIL_CLOSED",
        "documented_error": "",
        "candidate": candidate,
        "code_region": None,
        "contiguous": False,
    }

    reached: dict[str, Any] | None = None
    documented_error = ""
    try:
        reached = frozen_frontier.reachable_frontier(image, roots)
        document["frontier"]["documented_status"] = "OK"
    except frozen_frontier.FrontierError as exc:
        documented_error = str(exc)
        document["frontier"]["documented_error"] = documented_error

    indirect_source = (reached["indirect_sites"] if reached is not None
                       else candidate["indirect_sites"])
    indirect_sites = [_classify_indirect_site(item)
                      for item in indirect_source]
    unresolved_sites = [item for item in indirect_sites
                        if item["classification"] == "UNRESOLVED_INDIRECT_JUMP"]
    document["indirect_control_flow"] = {
        "status": "UNRESOLVED" if unresolved_sites else "RESOLVED",
        "sites": indirect_sites,
    }

    if reached is None:
        stop = candidate["stop"] or {}
        address = int(stop.get("address", 0))
        document["opcode_frontier"] = {
            "status": "BLOCKED_UNSUPPORTED_OPCODE",
            "documented_forms": candidate["distinct_opcode_forms"],
            "unsupported": [{
                "address": address,
                "kind": stop.get("kind"),
                "reason": stop.get("reason"),
            }],
        }
        blockers.append(_blocker(
            "BLOCKED_UNSUPPORTED_OPCODE", "opcode_frontier",
            "unsupported_opcode",
            f"documented-control-flow walk fails closed at 0x{address:04x} "
            f"({stop.get('reason', 'no reachable stop recorded')}) after "
            f"{candidate['instructions']} candidate instructions; no "
            "code/data boundary evidence is declared"))
        if unresolved_sites:
            blockers.append(_blocker(
                "BLOCKED_UNRESOLVED_INDIRECT_CONTROL_FLOW",
                "indirect_control_flow",
                "unresolved_indirect_control_flow",
                "unresolved indirect jump sites at "
                + ", ".join(f"0x{item['address']:04x}"
                            for item in unresolved_sites)
                + " through zero-page pointer(s) "
                + ", ".join(sorted({f"0x{int(item['pointer'] or 0):04x}"
                                    for item in unresolved_sites}))
                + "; runtime jump-table targets must not be guessed"))
        if candidate["low_window_instructions"]:
            blockers.append(_blocker(
                "BLOCKED_BANK_STATE_UNRESOLVED", "bank_state",
                "bank_state_unresolved",
                f"{candidate['low_window_instructions']} candidate instructions "
                "reach the mapper-switched $8000-$BFFF window under the "
                "power-on PRG bank only; runtime bank-state evidence is "
                "required to resolve the actual bank sequence"))
        document["translation"] = {
            "status": "NOT_ATTEMPTED",
            "reason": "no complete documented reachable instruction set exists; "
                      "fabricating translation units or indirect targets is not "
                      "permitted",
        }
        document["generated_sources"] = {
            "status": "NOT_GENERATED",
            "reason": "translation is blocked; no ROM-derived source is written",
        }
        blockers.append(_blocker(
            "NOT_TESTED", "runtime_platform", "platform_runtime_not_tested",
            "PPU/APU/input/timing requirements beyond the bounded Phase-5/6 "
            "platform model cannot be assessed until translation completes"))
        return _finalize(document)

    document["opcode_frontier"] = {
        "status": "SUPPORTED",
        "documented_forms": len(reached["opcode_histogram"]),
        "reachable_instructions": reached["reachable_instructions"],
        "reachable_bytes": reached["reachable_bytes"],
        "unsupported": [],
    }
    if unresolved_sites:
        blockers.append(_blocker(
            "BLOCKED_UNRESOLVED_INDIRECT_CONTROL_FLOW",
            "indirect_control_flow", "unresolved_indirect_control_flow",
            "unresolved indirect jump sites at "
            + ", ".join(f"0x{item['address']:04x}"
                        for item in unresolved_sites)
            + " through zero-page pointer(s) "
            + ", ".join(sorted({f"0x{int(item['pointer'] or 0):04x}"
                                for item in unresolved_sites}))
            + "; runtime jump-table targets must not be guessed"))
    if reached["indirect_sites"]:
        unknown = [item for item in reached["indirect_sites"]
                   if item.get("indirect") != EXIT_THUNK_POINTER]
        if unknown:
            blockers.append(_blocker(
                "BLOCKED_UNRESOLVED_INDIRECT_CONTROL_FLOW",
                "indirect_control_flow", "unresolved_indirect_control_flow",
                "documented frontier records indirect site(s) at "
                + ", ".join(f"0x{int(item['address']):04x}" for item in unknown)
                + " that are not the declared $02FF run-exit thunk"))

    region = _contiguous_region(image, reached)
    low_window = [address for address in reached["reachable_addresses"]
                  if LOW_WINDOW_BASE <= address < FIXED_WINDOW_BASE]
    document["frontier"]["code_region"] = list(region) if region else None
    document["frontier"]["contiguous"] = region is not None
    document["frontier"]["low_window_reachable"] = low_window

    if low_window:
        blockers.append(_blocker(
            "BLOCKED_BANK_STATE_UNRESOLVED", "bank_state",
            "bank_state_unresolved",
            f"{len(low_window)} reachable instructions execute in the "
            "mapper-switched $8000-$BFFF window under the power-on PRG bank "
            "only; runtime bank-state evidence is required to resolve the "
            "actual bank sequence"))
    if region is None:
        blockers.append(_blocker(
            "BLOCKED_CODE_DATA_BOUNDARY", "translation",
            "code_data_boundary_missing",
            "the documented reachable bytes do not form one contiguous, "
            "unambiguously decodable code region; code/data boundary evidence "
            "is required"))
    if blockers:
        document["translation"] = {
            "status": "NOT_ATTEMPTED",
            "reason": "translation preconditions are not satisfied; indirect "
                      "targets, bank state and code/data boundaries are never "
                      "fabricated",
        }
        document["generated_sources"] = {
            "status": "NOT_GENERATED",
            "reason": "translation is blocked; no ROM-derived source is written",
        }
        blockers.append(_blocker(
            "NOT_TESTED", "runtime_platform", "platform_runtime_not_tested",
            "PPU/APU/input/timing requirements beyond the bounded Phase-5/6 "
            "platform model cannot be assessed until translation completes"))
        return _finalize(document)

    region_start, region_end = region
    try:
        instructions = bridge.bridge_region(image, entry=region_start,
                                            end=region_end)
    except bridge.NES6502BridgeError as exc:
        blockers.append(_blocker(
            "BLOCKED_UNSUPPORTED_OPCODE", "translation", "unsupported_opcode",
            f"neutral bridging failed closed for region "
            f"0x{region_start:04x}-0x{region_end:04x}: {exc}"))
        document["translation"] = {
            "status": "NOT_ATTEMPTED",
            "reason": "neutral bridging failed closed",
        }
        document["generated_sources"] = {"status": "NOT_GENERATED"}
        blockers.append(_blocker(
            "NOT_TESTED", "runtime_platform", "platform_runtime_not_tested",
            "PPU/APU/input/timing requirements beyond the bounded Phase-5/6 "
            "platform model cannot be assessed until translation completes"))
        return _finalize(document)

    try:
        program = emit_module.emit_host_program(instructions, metadata)
        support = emit_module.emit_support(data, metadata, plan_values)
    except emit_module.P6EmitError as exc:
        code, classification_name = _emit_error_classification(str(exc))
        blockers.append(_blocker(
            code, "translation", classification_name,
            f"host emission failed closed: {exc}"))
        document["translation"] = {
            "status": "NOT_ATTEMPTED",
            "reason": "host emission failed closed",
        }
        document["generated_sources"] = {"status": "NOT_GENERATED"}
        blockers.append(_blocker(
            "NOT_TESTED", "runtime_platform", "platform_runtime_not_tested",
            "PPU/APU/input/timing requirements beyond the bounded Phase-5/6 "
            "platform model cannot be assessed until translation completes"))
        return _finalize(document)

    program_sha256 = sha256_bytes(program.encode("utf-8"))
    support_sha256 = sha256_bytes(support.encode("utf-8"))
    document["translation"] = {
        "status": "TRANSLATED",
        "region": [region_start, region_end],
        "instructions": len(instructions),
        "indirect_exit_service": emit_module.EXIT_SERVICE_NAME,
    }
    document["generated_sources"] = {
        "status": "GENERATED",
        "host_program_sha256": program_sha256,
        "host_program_bytes": len(program.encode("utf-8")),
        "support_sha256": support_sha256,
        "support_bytes": len(support.encode("utf-8")),
        "input_plan": list(plan_values),
        "written": [],
    }

    if not build:
        document["native_build"] = {
            "status": "NOT_ATTEMPTED",
            "reason": "native build disabled by the caller",
        }
        document["native_execution"] = {
            "status": "NOT_ATTEMPTED",
            "reason": "native build disabled by the caller",
        }
        blockers.append(_blocker(
            "NOT_TESTED", "platform_runtime", "platform_runtime_not_tested",
            "native build/execution disabled by the caller; the bounded "
            "platform model was not exercised"))
        return _finalize(document)

    if workspace_path.exists() and not workspace_path.is_dir():
        raise P6WorkflowError("workspace exists and is not a directory")
    generated_dir = workspace_path / "generated"
    if generated_dir.exists():
        shutil.rmtree(generated_dir)
    generated_dir.mkdir(parents=True)
    (generated_dir / "generated.c").write_text(program, encoding="utf-8",
                                               newline="\n")
    (generated_dir / "p6_nes_support.c").write_text(support, encoding="utf-8",
                                                    newline="\n")
    written = ["generated/generated.c", "generated/p6_nes_support.c"]
    document["generated_sources"]["written"] = written

    build_dir = workspace_path / "build"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    try:
        comparison = emit_module.build_native(
            program, support, fixture_id="p6-12-workflow",
            workspace=build_dir)
    except Exception as exc:  # noqa: BLE001 - deterministic classification
        message = f"{type(exc).__name__}: {exc}"
        if "was not found" in message or "not found" in message or "lld-link" in message:
            document["native_build"] = {
                "status": "TOOLCHAIN_UNAVAILABLE",
                "classification": "TOOLCHAIN_UNAVAILABLE",
                "reason": message,
            }
            blockers.append(_blocker(
                "BLOCKED_BY_MISSING_EXTERNAL_TOOLCHAIN", "native_build",
                "toolchain_missing",
                f"native build toolchain unavailable: {message}"))
        else:
            document["native_build"] = {
                "status": "FAILED",
                "classification": "BUILD_FAILED",
                "reason": message,
            }
            blockers.append(_blocker(
                "BLOCKED_NATIVE_BUILD_FAILED", "native_build",
                "native_build_failed",
                f"native build failed closed: {message}"))
        document["native_execution"] = {
            "status": "NOT_ATTEMPTED",
            "reason": "no native executable was produced",
        }
        blockers.append(_blocker(
            "NOT_TESTED", "platform_runtime", "platform_runtime_not_tested",
            "PPU/APU/input/timing requirements beyond the bounded Phase-5/6 "
            "platform model cannot be assessed without a native executable"))
        return _finalize(document)

    document["native_build"] = {
        "status": "BUILT",
        "classification": comparison.classification.name,
        "executable_reproducible": bool(comparison.executable_reproducible),
        "manifest_reproducible": bool(comparison.manifest_reproducible),
        "executable_sha256": sha256_bytes(
            (build_dir / "run1" / "program.exe").read_bytes()),
        "runs": len(comparison.runs),
        "toolchain": {
            "compiler": comparison.runs[0].manifest.toolchain.compiler.identity,
            "linker": comparison.runs[0].manifest.toolchain.linker.identity,
        },
    }

    executable = build_dir / "run1" / "program.exe"
    if not executable.is_file():
        blockers.append(_blocker(
            "BLOCKED_NATIVE_BUILD_FAILED", "native_build",
            "native_build_failed", "native executable is missing"))
        document["native_execution"] = {
            "status": "NOT_ATTEMPTED",
            "reason": "no native executable was produced",
        }
        blockers.append(_blocker(
            "NOT_TESTED", "platform_runtime", "platform_runtime_not_tested",
            "PPU/APU/input/timing requirements beyond the bounded Phase-5/6 "
            "platform model cannot be assessed without a native executable"))
        return _finalize(document)

    outputs: list[str] = []
    fields: dict[str, str] = {}
    frames: list[str] = []
    try:
        for _index in range(runs_value):
            completed = subprocess.run([str(executable)], capture_output=True,
                                       text=True, encoding="utf-8",
                                       errors="replace", timeout=timeout)
            if completed.returncode != 0 or completed.stderr != "":
                raise P6WorkflowError(
                    "native execution did not complete cleanly")
            outputs.append(completed.stdout)
    except (OSError, subprocess.SubprocessError, P6WorkflowError) as exc:
        document["native_execution"] = {
            "status": "FAILED",
            "reason": f"{type(exc).__name__}: {exc}",
        }
        blockers.append(_blocker(
            "BLOCKED_NATIVE_EXECUTION_FAILED", "native_execution",
            "native_execution_failed",
            f"native execution failed closed: {exc}"))
        blockers.append(_blocker(
            "NOT_TESTED", "runtime_platform", "platform_runtime_not_tested",
            "PPU/APU/input/timing requirements beyond the bounded Phase-5/6 "
            "platform model cannot be assessed without a native execution"))
        return _finalize(document)

    if len(set(outputs)) != 1:
        document["native_execution"] = {
            "status": "FAILED",
            "reason": "native executions were not byte-identical",
        }
        blockers.append(_blocker(
            "BLOCKED_NATIVE_EXECUTION_FAILED", "native_execution",
            "native_execution_failed",
            "native executions were not byte-identical; nondeterministic "
            "behaviour fails closed"))
        blockers.append(_blocker(
            "NOT_TESTED", "runtime_platform", "platform_runtime_not_tested",
            "PPU/APU/input/timing requirements beyond the bounded Phase-5/6 "
            "platform model cannot be assessed without a deterministic native "
            "execution"))
        return _finalize(document)

    fields, frames = _parse_observable(outputs[0])
    document["native_execution"] = {
        "status": "EXECUTED",
        "runs": runs_value,
        "fields": fields,
        "frames": frames,
        "guest_code_executed_on_host": False,
        "note": "only the generated host executable runs, through the typed "
                "runtime ABI; the original 6502 image is never executed on the "
                "host",
    }
    document["platform_runtime"] = {
        "status": "BOUNDED_NES_PLATFORM_MODEL_ACTIVE",
        "reason": "the bounded Phase-5/6 CPU/PPU/APU/input/timing model "
                  "executed deterministically; no further platform behaviour "
                  "is demonstrated necessary by this run",
    }
    return _finalize(document)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase-6 reusable ROM-to-native workflow")
    parser.add_argument("--rom", required=True)
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--plan", default=",".join(f"{value:02X}"
                                                   for value in DEFAULT_PLAN))
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    parser.add_argument("--no-build", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        plan = tuple(int(item, 16) for item in args.plan.split(",") if item)
    except ValueError:
        sys.stdout.buffer.write(canonical(
            {"workflow": WORKFLOW_ID, "status": "FAIL_CLOSED",
             "error": "input plan must be comma-separated hex"}).encode("utf-8"))
        return 2

    try:
        report = run(args.rom, plan=plan, budget=args.budget,
                     workspace=args.workspace, build=not args.no_build,
                     run_count=args.runs)
    except P6WorkflowError as exc:
        sys.stdout.buffer.write(canonical(
            {"workflow": WORKFLOW_ID, "stage": "P6-12",
             "status": "FAIL_CLOSED",
             "classification": "INPUT_ERROR",
             "error": str(exc)}).encode("utf-8"))
        return 2
    sys.stdout.buffer.write(canonical(report).encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
