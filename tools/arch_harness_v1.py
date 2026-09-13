#!/usr/bin/env python3
"""Shared deterministic architecture test/evidence harness (Phase 1 P1-03).

Drives any registered architecture's proof machinery from one machine-readable
fixture descriptor:

- `decode_matrix`: positive decode cases (documented encodings with pinned
  op/fields) plus negative cases (undocumented/malformed encodings that must
  raise the adapter's decode error — fail closed);
- `chains`: named end-to-end recipes executed through the repository's own
  tools and compared against published results:
  - `frontend-fixture-chain`: fixture -> frontend CLI -> IR V1 validation ->
    independent reference -> Module Image V1 -> Core API V1 -> equivalence
    checker (the documented CI sequence);
  - `prebuilt-ir-module`: an existing normalized IR V1 document packaged and
    executed through Module Image V1 + Core API V1.

The harness is deterministic: it emits no timestamps or absolute paths,
requires byte-identical output where the recipe generates twice, and records
its evidence as sorted JSON.

Exit codes: 0 on `OPENRECOMP_ARCH_HARNESS_V1=PASS`, 2 on any failure.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from openrecomp import CallbackHostBinding, ModuleImage, ReferenceExecutor  # noqa: E402

DESCRIPTOR_SCHEMA_VERSION = "1.0.0"


class HarnessError(ValueError):
    """Fail-closed harness violation."""


def _serialize(document: object) -> str:
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run_tool(argv: list[str]) -> str:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    completed = subprocess.run(
        [sys.executable, *argv],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    combined = (completed.stdout or "") + (completed.stderr or "")
    if completed.returncode != 0:
        raise HarnessError(f"{' '.join(argv)} exited {completed.returncode}: {combined.strip()[-400:]}")
    return combined


def _adapter_error(module, entry: dict) -> type:
    attribute = entry.get("error_attribute")
    if attribute is None:
        return ValueError
    error_type = getattr(module, attribute, None)
    if not isinstance(error_type, type) or not issubclass(error_type, ValueError):
        raise HarnessError(f"adapter {entry['module']} does not expose a ValueError-derived {attribute}")
    return error_type


def run_decode_matrix(descriptor: dict) -> dict:
    adapter_entry = descriptor["adapter"]
    module = importlib.import_module(adapter_entry["module"])
    error_type = _adapter_error(module, adapter_entry)
    matrix = descriptor["decode_matrix"]
    address_bits = adapter_entry.get("address_bits", 32)

    positive_checked = 0
    rejected_checked = 0
    problems: list[str] = []
    for case in matrix.get("positive", []):
        address = case["address"]
        word = case["word"]
        if isinstance(address, bool) or not isinstance(address, int) or not (0 <= address < (1 << address_bits)):
            raise HarnessError(f"descriptor: decode case address {address!r} outside {address_bits} bits")
        decoded = module.decode(address, word)
        if decoded.get("address") != address:
            problems.append(f"0x{address:x}: decoded address {decoded.get('address')!r} != case address")
        if decoded.get("op") != case["op"]:
            problems.append(f"0x{address:x}: op {decoded.get('op')!r} != pinned {case['op']!r}")
        for field, expected in sorted(case.get("fields", {}).items()):
            if decoded.get(field) != expected:
                problems.append(
                    f"0x{address:x}: {field} {decoded.get(field)!r} != pinned {expected!r}"
                )
        positive_checked += 1

    for case in matrix.get("negative", []):
        try:
            module.decode(case["address"], case["word"])
        except error_type:
            rejected_checked += 1
        except Exception as exc:  # noqa: BLE001
            problems.append(
                f"0x{case['address']:x} word 0x{case['word']:x}: raised {type(exc).__name__} "
                f"instead of {error_type.__name__}"
            )
        else:
            problems.append(f"0x{case['address']:x} word 0x{case['word']:x}: decode accepted an undocumented encoding")

    if problems:
        raise HarnessError("decode matrix failures: " + "; ".join(problems))
    return {"negative_rejected": rejected_checked, "positive_checked": positive_checked}


def chain_frontend_fixture(descriptor: dict, chain: dict) -> dict:
    proof = chain
    published = proof["published"]
    with tempfile.TemporaryDirectory(prefix="openrecomp-arch-harness-") as temp:
        work = Path(temp)
        paths = {
            "ir": work / "fixture.a.ir.json",
            "sidecar": work / "fixture.a.sidecar.json",
            "frontend": work / "fixture.a.frontend.json",
            "ir_b": work / "fixture.b.ir.json",
            "sidecar_b": work / "fixture.b.sidecar.json",
            "frontend_b": work / "fixture.b.frontend.json",
            "reference": work / "reference.json",
            "module": work / "fixture.a.module.json",
            "core": work / "core.json",
        }
        hex_path = str(Path(proof["fixture_hex"]).as_posix())
        meta_path = str(Path(proof["fixture_meta"]).as_posix())
        contract_path = str(Path(proof["host_contract"]).as_posix())

        def frontend_run(suffix: str) -> str:
            return _run_tool(
                [
                    proof["frontend"], hex_path, meta_path, contract_path,
                    str(paths[f"ir{suffix}"]), str(paths[f"sidecar{suffix}"]), str(paths[f"frontend{suffix}"]),
                ]
            )

        output_a = frontend_run("")
        last_lines = [line for line in output_a.splitlines() if line.strip()]
        if not last_lines or "=PASS" not in last_lines[-1]:
            raise HarnessError("frontend did not report its pass marker")
        frontend_run("_b")
        if paths["ir"].read_bytes() != paths["ir_b"].read_bytes():
            raise HarnessError("frontend IR is not deterministic across two runs")
        if paths["sidecar"].read_bytes() != paths["sidecar_b"].read_bytes():
            raise HarnessError("frontend sidecar is not deterministic across two runs")
        if paths["frontend"].read_bytes() != paths["frontend_b"].read_bytes():
            raise HarnessError("frontend report is not deterministic across two runs")

        output = _run_tool(["tools/validate_ir_v1.py", str(paths["ir"])])
        if "OPENRECOMP_IR_V1_VALID=PASS" not in output:
            raise HarnessError("normalized IR V1 did not validate")
        output = _run_tool([proof["reference"], hex_path, meta_path, str(paths["reference"])])
        if "=PASS" not in output:
            raise HarnessError("independent reference did not report its pass marker")
        output = _run_tool(
            [proof["packager"], str(paths["ir"]), str(paths["sidecar"]), contract_path, str(paths["module"])]
        )
        if "OPENRECOMP_MODULE_V1_PACKAGE=PASS" not in output:
            raise HarnessError("Module Image V1 packaging did not pass")
        output = _run_tool([proof["module_validator"], str(paths["module"]), str(paths["ir"]), contract_path])
        if "OPENRECOMP_MODULE_V1_VALID=PASS" not in output:
            raise HarnessError("Module Image V1 validation did not pass")
        output = _run_tool(
            [proof["core_runner"], str(paths["module"]), str(paths["ir"]), contract_path, meta_path, str(paths["core"])]
        )
        if "=PASS" not in output:
            raise HarnessError("Core API execution did not report its pass marker")
        output = _run_tool(
            [
                proof["equivalence_checker"], meta_path, str(paths["frontend"]), str(paths["ir"]),
                str(paths["module"]), str(paths["reference"]), str(paths["core"]),
            ]
        )
        if "=PASS" not in output:
            raise HarnessError("equivalence check did not pass")

        core = json.loads(paths["core"].read_text(encoding="utf-8"))
        frontend_report = json.loads(paths["frontend"].read_text(encoding="utf-8"))
        module = json.loads(paths["module"].read_text(encoding="utf-8"))

    observed = {key: core[key] for key in sorted(published) if key in core}
    if observed != {key: published[key] for key in observed}:
        raise HarnessError(f"Core API result {observed} does not match published {published}")
    if "delay_slots" in published and frontend_report.get("delay_slots_lowered") != published["delay_slots"]:
        raise HarnessError("frontend delay-slot count does not match the published value")
    if module.get("module_format_version") != "1.0.0":
        raise HarnessError("packaged module is not Module Image V1")
    return observed


def chain_prebuilt_module(descriptor: dict, chain: dict) -> dict:
    proof = chain
    ir_path = ROOT / proof["ir"]
    contract_path = ROOT / proof["host_contract"]
    ir_bytes = ir_path.read_bytes()
    contract_bytes = contract_path.read_bytes()
    ir = json.loads(ir_bytes)
    contract = json.loads(contract_bytes)

    manifest = {
        "module_format_version": "1.0.0",
        "module_id": ir["module_id"],
        "ir": {
            "version": ir["ir_version"],
            "sha256": _digest(ir_bytes),
            "source_input_sha256": ir["source"]["input_sha256"],
        },
        "host_contract": {
            "version": contract["contract_version"],
            "sha256": _digest(contract_bytes),
        },
        "memory": {"size_bytes": contract["memory"]["size_bytes"], "segments": []},
        "initial_state": [],
        "entry": {"function": ir["entry_function"], "observe_state_slot": proof["observe_state_slot"]},
        "limits": {"max_operations": 100, "max_call_depth": 8},
        "provenance": {
            "producer": "openrecomp.arch-harness-v1",
            "source_input_sha256": ir["source"]["input_sha256"],
        },
    }
    module = ModuleImage.from_documents(
        manifest, ir, contract, ir_sha256=_digest(ir_bytes), contract_sha256=_digest(contract_bytes)
    )
    callbacks = {}
    for symbol, spec in proof.get("host_bindings", {}).items():
        if spec["kind"] != "sum_args":
            raise HarnessError(f"unsupported host binding kind {spec['kind']!r}")
        callbacks[symbol] = lambda args: sum(args)
    execution = ReferenceExecutor(module, CallbackHostBinding(contract["contract_version"], callbacks)).run()
    observed = {
        "function_return": execution.function_return,
        "observed_state": execution.observed_state,
        "operations": execution.operations,
    }
    expected = {key: proof["published"][key] for key in observed if key in proof["published"]}
    observed = {key: observed[key] for key in expected}
    if observed != expected:
        raise HarnessError(f"prebuilt module result {observed} does not match published {expected}")
    return observed


CHAIN_KINDS = {
    "frontend-fixture-chain": chain_frontend_fixture,
    "prebuilt-ir-module": chain_prebuilt_module,
}


def validate_descriptor(descriptor: dict) -> None:
    if descriptor.get("schema_version") != DESCRIPTOR_SCHEMA_VERSION:
        raise HarnessError("unsupported descriptor schema version")
    if not isinstance(descriptor.get("architecture"), str) or not descriptor["architecture"]:
        raise HarnessError("descriptor must name an architecture")
    adapter = descriptor.get("adapter")
    if not isinstance(adapter, dict) or not adapter.get("module"):
        raise HarnessError("descriptor must declare adapter.module")
    if not isinstance(adapter.get("address_bits"), int) or not (1 <= adapter["address_bits"] <= 64):
        raise HarnessError(
            "adapter.address_bits must be the guest decode address width (1..64); "
            "the IR address width is governed separately by the frontend contract"
        )
    matrix = descriptor.get("decode_matrix")
    if not isinstance(matrix, dict):
        raise HarnessError("descriptor must declare decode_matrix")
    if not isinstance(matrix.get("positive", []), list) or not isinstance(matrix.get("negative", []), list):
        raise HarnessError("decode_matrix.positive/negative must be lists")
    if not isinstance(descriptor.get("chains", []), list):
        raise HarnessError("descriptor chains must be a list (decode-only descriptors use an empty list)")
    for chain in descriptor["chains"]:
        if chain.get("kind") not in CHAIN_KINDS:
            raise HarnessError(f"unsupported chain kind {chain.get('kind')!r}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("descriptor", help="machine-readable architecture fixture descriptor (JSON)")
    parser.add_argument("--json", help="write the deterministic harness record here")
    args = parser.parse_args(argv[1:])

    try:
        descriptor = json.loads(Path(args.descriptor).read_text(encoding="utf-8"))
        validate_descriptor(descriptor)
        record: dict = {
            "architecture": descriptor["architecture"],
            "chains": [],
            "decode_matrix": run_decode_matrix(descriptor),
            "schema_version": DESCRIPTOR_SCHEMA_VERSION,
            "status": "PASS",
        }
        for chain in descriptor["chains"]:
            record["chains"].append(
                {"kind": chain["kind"], "result": CHAIN_KINDS[chain["kind"]](descriptor, chain)}
            )
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ImportError, AttributeError, HarnessError) as exc:
        print(f"OPENRECOMP_ARCH_HARNESS_V1=FAIL: {exc}", file=sys.stderr)
        return 2

    matrix = record["decode_matrix"]
    print(
        f"PASS decode-matrix positive={matrix['positive_checked']} negative_rejected={matrix['negative_rejected']}"
    )
    for chain in record["chains"]:
        print(f"PASS chain {chain['kind']} {json.dumps(chain['result'], sort_keys=True)}")
    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_serialize(record), encoding="utf-8")
        print(f"OPENRECOMP_ARCH_HARNESS_JSON={out.name}")
    print("OPENRECOMP_ARCH_HARNESS_V1=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
