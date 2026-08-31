#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from validate_ir_v1 import load_and_validate


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fail(message: str) -> None:
    raise ValueError(message)


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        print(
            "usage: package_ir_v1_module.py <ir-v1.json> <execution-sidecar.json> <host-contract.json> <out-module.json>",
            file=sys.stderr,
        )
        return 2

    try:
        ir_path = Path(argv[1])
        sidecar_path = Path(argv[2])
        contract_path = Path(argv[3])
        out_path = Path(argv[4])

        ir_bytes = ir_path.read_bytes()
        contract_bytes = contract_path.read_bytes()
        ir = load_and_validate(ir_path)
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        contract = json.loads(contract_bytes)

        if sidecar["source_input_sha256"] != ir["source"]["input_sha256"]:
            fail("sidecar/source input hash mismatch")
        if contract["contract_version"] != ir["host_contract_version"]:
            fail("IR/host contract version mismatch")
        if sidecar["memory_size_bytes"] != contract["memory"]["size_bytes"]:
            fail("sidecar/host memory-size mismatch")

        segments = []
        for segment in sorted(sidecar["memory_segments"], key=lambda s: (s["guest_address"], s["name"])):
            data = bytes.fromhex(segment["data_hex"])
            segments.append(
                {
                    "name": segment["name"],
                    "guest_address": segment["guest_address"],
                    "data_hex": data.hex(),
                    "data_sha256": sha256(data),
                }
            )

        provenance = {
            "producer": ir["source"]["adapter"],
            "source_input_sha256": ir["source"]["input_sha256"],
        }
        source_ir_hash = sidecar.get("source_legacy_ir_sha256")
        if source_ir_hash is not None:
            if not isinstance(source_ir_hash, str) or len(source_ir_hash) != 64:
                fail("invalid source legacy IR SHA-256")
            provenance["source_ir_sha256"] = source_ir_hash

        module = {
            "module_format_version": "1.0.0",
            "module_id": ir["module_id"],
            "ir": {
                "version": ir["ir_version"],
                "sha256": sha256(ir_bytes),
                "source_input_sha256": ir["source"]["input_sha256"],
            },
            "host_contract": {
                "version": contract["contract_version"],
                "sha256": sha256(contract_bytes),
            },
            "memory": {
                "size_bytes": sidecar["memory_size_bytes"],
                "segments": segments,
            },
            "initial_state": [
                {"slot": slot, "value": value}
                for slot, value in sorted(sidecar["initial_state"].items())
            ],
            "entry": {
                "function": ir["entry_function"],
                "observe_state_slot": sidecar["entry_state_slot"],
            },
            "limits": {
                "max_operations": sidecar["max_operations"],
                "max_call_depth": 1024,
            },
            "provenance": provenance,
        }

        out_path.write_text(json.dumps(module, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        print(f"OPENRECOMP_MODULE_V1_PACKAGE=FAIL: {exc}", file=sys.stderr)
        return 2

    print("OPENRECOMP_MODULE_V1_PACKAGE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
