#!/usr/bin/env python3
"""OpenRecomp Phase-11 execution-trace support V1.

Builds the Phase-11 trace emission set (frozen Phase-10 composition plus the
opt-in host-emitter instrumentation and the appended trace fragment), runs the
generated native program deterministically, parses the observable record and
indexes the trace against the frozen structural image.

Everything here is analysis-side: no guest machine code is executed, the guest
image is inert data and the trace contains only guest addresses, counts and
digests.
"""

from __future__ import annotations

import hashlib
import pathlib
import shutil
import subprocess
from typing import Any

import p11_emission_v1 as emission
from openrecomp import build_pipeline as bp

ROOT = pathlib.Path(__file__).resolve().parents[2]

TRACE_VERSION = "1.1.0"

BUILD_WORKSPACE = ROOT / ".openrecomp-phase11" / "build" / "p11-trace"

TRACE_SCALAR_KEYS = (
    "fixture", "failed", "error", "exit_status",
    "registers", "memory",
    "gpu_events", "gpu", "input_events", "input", "spu_events", "spu",
    "gpu_write_events", "gpu_gp0_writes", "gpu_gp1_writes",
    "gpu_known_writes", "gpu_blocker_writes",
    "cdrom_events", "cdrom",
    "reads", "writes", "denied", "host_calls",
    "p10_access_budget", "p10_access_count", "p10_budget_denials",
    "p10_service_calls", "p10_service_failures",
    "nonram_signatures", "nonram_overflow",
    "trace_block_events", "trace_function_events", "trace_block_digest",
    "trace_distinct_blocks", "trace_block_overflow",
    "trace_distinct_functions", "trace_function_overflow",
    "trace_ring_count", "trace_ring_capacity", "trace_first_count",
    "trace_failure_count", "trace_failure_site", "trace_failure_function",
    "trace_failure_source", "trace_failure_message", "trace_failure_block_index",
    "trace_current_function", "trace_failure_before_count", "trace_failure_after_count",
    "bound_budget", "bound_reached", "bound_denials",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_driver_output(stdout: str) -> dict[str, Any]:
    """Parse the Phase-11 observable driver output into a deterministic record."""
    record: dict[str, Any] = {"register_file": {}, "nonram": {}, "gpu_writes": [],
                              "trace_first": [], "trace_last": [],
                              "trace_before": [], "trace_after": [],
                              "trace_block_counts": {}, "trace_function_counts": {}}
    for line in stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.startswith("r") and key[1:].isdigit():
            record["register_file"][key] = value
        elif key in TRACE_SCALAR_KEYS:
            record[key] = value
        elif key.startswith("nonram_") and key not in ("nonram_signatures", "nonram_overflow"):
            address, width, is_write, reason, count = value.split(",")
            record["nonram"][f"{address}:{width}:{is_write}:{reason}"] = count
        elif key.startswith("gpu_write_"):
            sequence, service, direction, width, flags, address, event_value, command = value.split(",")
            record["gpu_writes"].append({
                "sequence": int(sequence),
                "service": int(service),
                "direction": int(direction),
                "width_bits": int(width),
                "flags": int(flags),
                "address": address,
                "value": event_value,
                "command": command,
            })
        elif key.startswith("trace_first_"):
            record["trace_first"].append(value)
        elif key.startswith("trace_last_"):
            record["trace_last"].append(value)
        elif key.startswith("trace_before_"):
            record["trace_before"].append(value)
        elif key.startswith("trace_after_"):
            record["trace_after"].append(value)
        elif key.startswith("trace_block_"):
            address, count = value.split(",")
            record["trace_block_counts"][address] = int(count)
        elif key.startswith("trace_function_"):
            address, count = value.split(",")
            record["trace_function_counts"][address] = int(count)
    return record


class StructureIndex:
    """Deterministic address -> structure index over the frozen neutral model."""

    def __init__(self, structure: Any) -> None:
        self.block_by_address: dict[int, dict[str, Any]] = {}
        self.block_by_terminal: dict[int, dict[str, Any]] = {}
        self.function_by_address: dict[int, dict[str, Any]] = {}
        self.function_by_id: dict[str, dict[str, Any]] = {}
        for unit in structure.units.units:
            function = {
                "function_id": unit.function_id,
                "unit_id": unit.unit_id,
                "entry_address": unit.entry_address,
            }
            self.function_by_address[unit.entry_address] = function
            self.function_by_id[unit.function_id] = function
            for block in unit.blocks:
                terminal = block.instructions[-1]
                metadata = terminal.metadata or {}
                record = {
                    "block_id": block.id,
                    "function_id": unit.function_id,
                    "entry_address": block.entry_address,
                    "terminal_op": terminal.op,
                    "terminal_address": terminal.address,
                    "terminal_flow": terminal.flow.value,
                    "direct_target": terminal.direct_target,
                    "operands": dict(metadata.get("operands") or {}),
                    "adapter_fields": dict(metadata.get("adapter_fields") or {}),
                    "delay_slot": dict(metadata.get("delay_slot") or {}) or None,
                    "successors": [
                        {
                            "kind": successor.kind.value,
                            "target_block": successor.target_block,
                            "target_address": (
                                f"0x{successor.target_address:08x}"
                                if successor.target_address is not None else None
                            ),
                            "resolved": successor.resolved,
                        }
                        for successor in block.successors
                    ],
                }
                self.block_by_address[block.entry_address] = record
                self.block_by_terminal[terminal.address] = record

    def block(self, address: int) -> dict[str, Any] | None:
        return self.block_by_address.get(address)

    def block_containing(self, address: int) -> dict[str, Any] | None:
        """The block whose terminal instruction is at ``address``, if any."""
        return self.block_by_terminal.get(address)

    def function(self, address: int) -> dict[str, Any] | None:
        return self.function_by_address.get(address)

    def describe_sequence(self, addresses: list[int]) -> list[dict[str, Any]]:
        described: list[dict[str, Any]] = []
        for address in addresses:
            block = self.block(address)
            described.append(
                {
                    "address": f"0x{address:08x}",
                    "block_id": block["block_id"] if block else None,
                    "function_id": block["function_id"] if block else None,
                    "terminal_op": block["terminal_op"] if block else None,
                    "in_image": block is not None,
                }
            )
        return described


def build_trace_program(
    structure: Any,
    contract: dict[str, Any],
    flat: bytes,
    fixture_sha256: str,
    *,
    workspace: pathlib.Path | None = None,
    run_count: int = 2,
) -> dict[str, Any]:
    """Build the Phase-11 trace emission set natively (no guest code executed)."""
    build_set = emission.build_trace_build_set(structure, contract, flat, fixture_sha256)
    target = workspace or BUILD_WORKSPACE
    if target.exists():
        shutil.rmtree(target)
    comparison = bp.build_generated_host(
        lambda: build_set["files"][emission.PROGRAM_NAME],
        support_sources=(
            bp.BuildSource(emission.IMAGE_NAME, bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
                           build_set["files"][emission.IMAGE_NAME].encode("utf-8")),
            bp.BuildSource(emission.SUPPORT_NAME, bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
                           build_set["files"][emission.SUPPORT_NAME].encode("utf-8")),
            bp.BuildSource(emission.DRIVER_NAME, bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
                           build_set["files"][emission.DRIVER_NAME].encode("utf-8")),
        ),
        config=bp.BuildConfig(fixture_id="p11-trace", smoke_test=False, run_count=run_count),
        workspace=target,
        keep_workspace=True,
    )
    executables = [target / f"run{index}" / "program.exe" for index in range(1, run_count + 1)]
    return {
        "build_set": build_set,
        "workspace": target,
        "executables": executables,
        "build_status": [run.manifest.build_status.value for run in comparison.runs],
        "build_reproducible": len({sha256_bytes(path.read_bytes()) for path in executables}) == 1,
        "executable_sha256": sha256_bytes(executables[0].read_bytes()),
    }


def run_trace_program(executable: pathlib.Path, *, budget: int | None = None,
                      block_budget: int | None = None, timeout: int = 1800) -> dict[str, Any]:
    command = [str(executable)]
    if budget is not None or block_budget is not None:
        command.append(str(budget if budget is not None else 0))
    if block_budget is not None:
        command.append(str(block_budget))
    completed = subprocess.run(command, capture_output=True, timeout=timeout)
    stdout = completed.stdout
    return {
        "returncode": completed.returncode,
        "stderr_bytes": len(completed.stderr),
        "stdout_sha256": sha256_bytes(stdout),
        "stdout_bytes": len(stdout),
        "parsed": parse_driver_output(stdout.decode("utf-8")),
        "stdout": stdout,
    }


def _cycle_from_window(window: list[str], maximum: int = 64, threshold: float = 0.9) -> list[str] | None:
    """The smallest dominant period of a deterministic execution window.

    The window is not required to end exactly on a cycle boundary: the smallest
    period ``p`` for which at least ``threshold`` of the adjacent pairs match is
    reported, together with the most common phase of that period.
    """
    values = list(window)
    if len(values) < 3 * maximum:
        return None
    for length in range(2, maximum + 1):
        matches = sum(1 for index in range(len(values) - length) if values[index] == values[index + length])
        if matches >= threshold * (len(values) - length):
            tail = values[-length:]
            if values[-2 * length : -length] == tail:
                return tail
            best = None
            best_score = -1
            for start in range(len(values) - 2 * length + 1):
                candidate = values[start : start + length]
                score = sum(
                    1
                    for offset in range(length)
                    if values[start + offset] == values[-length + offset]
                )
                if score > best_score:
                    best_score = score
                    best = candidate
            return best
    return None


def analyze_trace(parsed: dict[str, Any], index: StructureIndex,
                  unresolved_sites: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Derive the deterministic causal frontier from one trace record."""
    failure_site = parsed.get("trace_failure_site")
    failure_site_value = int(failure_site, 16) if isinstance(failure_site, str) else 0
    failure_block = index.block_containing(failure_site_value) or index.block(failure_site_value)
    site_record = None
    if unresolved_sites:
        for item in unresolved_sites:
            if item.get("site") == failure_site_value:
                site_record = item
                break
    failure_index = int(parsed.get("trace_failure_block_index", "0"))
    first = parsed.get("trace_first", [])
    last = parsed.get("trace_last", [])
    before = parsed.get("trace_before", [])
    after = parsed.get("trace_after", [])
    pre_failure = [value for value in first[: min(len(first), failure_index)]]
    failure_source = parsed.get("trace_failure_source")
    failure_source_value = int(failure_source, 16) if isinstance(failure_source, str) else None

    cycle = _cycle_from_window(last)
    cycle_addresses = [int(value, 16) for value in (cycle or [])]
    cycle_blocks = index.describe_sequence(cycle_addresses) if cycle_addresses else []
    cycle_iterations = None
    if cycle:
        counts = parsed.get("trace_block_counts", {})
        per_iteration = [counts.get(value, 0) for value in cycle]
        cycle_iterations = min(per_iteration) if per_iteration else None

    hottest = sorted(
        ((int(address, 16), count) for address, count in parsed.get("trace_block_counts", {}).items()),
        key=lambda item: (-item[1], item[0]),
    )[:16]
    hottest_blocks = []
    for address, count in hottest:
        block = index.block(address)
        hottest_blocks.append(
            {
                "address": f"0x{address:08x}",
                "count": count,
                "block_id": block["block_id"] if block else None,
                "function_id": block["function_id"] if block else None,
                "terminal_op": block["terminal_op"] if block else None,
            }
        )
    hottest_functions = sorted(
        ((int(address, 16), count) for address, count in parsed.get("trace_function_counts", {}).items()),
        key=lambda item: (-item[1], item[0]),
    )[:8]

    loop_predicate = None
    loop_branches: list[dict[str, Any]] = []
    if cycle_blocks:
        cycle_addresses_set = set(cycle_addresses)
        back_edges: list[dict[str, Any]] = []
        for item in cycle_blocks:
            block = index.block(int(item["address"], 16))
            if block is None or block["terminal_flow"] != "BRANCH":
                continue
            loop_branches.append(
                {
                    "block_id": block["block_id"],
                    "function_id": block["function_id"],
                    "terminal_address": f"0x{block['terminal_address']:08x}",
                    "terminal_op": block["terminal_op"],
                    "direct_target": (
                        f"0x{block['direct_target']:08x}" if block["direct_target"] is not None else None
                    ),
                    "operands": block["operands"],
                }
            )
            target = block["direct_target"]
            if target in cycle_addresses_set and target < block["entry_address"]:
                back_edges.append(block)
        governing = back_edges[-1] if back_edges else None
        if governing is not None:
            loop_predicate = {
                "block_id": governing["block_id"],
                "function_id": governing["function_id"],
                "terminal_address": f"0x{governing['terminal_address']:08x}",
                "terminal_op": governing["terminal_op"],
                "terminal_flow": governing["terminal_flow"],
                "direct_target": (
                    f"0x{governing['direct_target']:08x}"
                    if governing["direct_target"] is not None else None
                ),
                "operands": governing["operands"],
                "delay_slot": governing["delay_slot"],
                "successors": governing["successors"],
                "selection": "last conditional back edge inside the detected cycle",
            }

    return {
        "trace_version": TRACE_VERSION,
        "failure": {
            "site": f"0x{failure_site_value:08x}",
            "message": parsed.get("trace_failure_message"),
            "source_value": (
                f"0x{failure_source_value:08x}" if failure_source_value is not None else None
            ),
            "function_entry": f"0x{int(parsed.get('trace_failure_function', '0'), 16):08x}",
            "function_id": failure_block["function_id"] if failure_block else None,
            "block_id": failure_block["block_id"] if failure_block else None,
            "terminal_op": failure_block["terminal_op"] if failure_block else None,
            "block_index": failure_index,
            "failure_count": int(parsed.get("trace_failure_count", "0")),
            "site_classification": site_record,
        },
        "before_failure": {
            "block_entries": failure_index,
            "window": index.describe_sequence([int(value, 16) for value in before]),
            "distinct_blocks_before_failure": len({value for value in pre_failure}),
        },
        "after_failure": {
            "block_entries": int(parsed.get("trace_block_events", "0")) - failure_index,
            "window": index.describe_sequence([int(value, 16) for value in after]),
        },
        "repeating_loop": {
            "detected": cycle is not None,
            "cycle_length": len(cycle or []),
            "cycle": index.describe_sequence(cycle_addresses),
            "iterations_lower_bound": cycle_iterations,
            "predicate": loop_predicate,
            "branches": loop_branches,
        },
        "hottest_blocks": hottest_blocks,
        "hottest_functions": [
            {
                "address": f"0x{address:08x}",
                "count": count,
                "function_id": (index.function(address) or {}).get("function_id"),
            }
            for address, count in hottest_functions
        ],
        "totals": {
            "block_events": int(parsed.get("trace_block_events", "0")),
            "function_events": int(parsed.get("trace_function_events", "0")),
            "distinct_blocks": int(parsed.get("trace_distinct_blocks", "0")),
            "distinct_functions": int(parsed.get("trace_distinct_functions", "0")),
            "block_digest": parsed.get("trace_block_digest"),
        },
    }
