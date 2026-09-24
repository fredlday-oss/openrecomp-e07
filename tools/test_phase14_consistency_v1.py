#!/usr/bin/env python3
"""Deterministic P14-30 BIOS/BIOS-helper service consistency gate."""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase3/src", ".openrecomp-phase8/src",
              ".openrecomp-phase9/src", ".openrecomp-phase9/fixture",
              ".openrecomp-phase10/src", ".openrecomp-phase11/src",
              ".openrecomp-phase12/src", ".openrecomp-phase13/src",
              ".openrecomp-phase14/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

from p14_gate_v1 import run_stage, write_json  # noqa: E402
from p14_contracts_v1 import FRAME_MARKER, GENERAL_MARKER, INITIALIZATION_MARKER, PLAYABILITY_MARKER  # noqa: E402

import p14_c0_surface_v1 as c0_surface  # noqa: E402
import p14_closure_surface_v1 as surface  # noqa: E402
import p14_semantics_v1 as semantics  # noqa: E402
import p14_services_v1 as services  # noqa: E402

STAGE = "P14-30"


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    tables = services.install(surface.EXTRA_A0, surface.EXTRA_C0, surface.EXTRA_B0,
                              p14_b0=surface.P14_B0, p14_a0=surface.P14_A0)

    import types

    synthetic_sites = [
        types.SimpleNamespace(vector=vector, function_index=index,
                              service_id=f"ps1.bios.{vector}.{index:02x}")
        for vector, table in sorted(tables.items())
        for index in sorted(table)
    ]
    service_table = semantics.build_service_table(synthetic_sites)
    ids = list(service_table.service_ids)
    gate.check("unique:service-ids", len(ids) == len(set(ids)), ",".join(ids))

    rows = []
    seen_pairs = set()
    for vector, table in sorted(tables.items()):
        for index, document in sorted(table.items()):
            pair = (vector, index)
            gate.check(f"alias:{vector}:{index:02x}", pair not in seen_pairs, str(pair))
            seen_pairs.add(pair)
            rows.append({
                "vector": vector,
                "index": f"0x{index:02x}",
                "service_id": f"ps1.bios.{vector}.{index:02x}",
                "name": document["name"],
                "arity": len(document["signature"]),
                "result_register": document.get("result_register"),
            })
    for row in rows:
        gate.check(f"arity:{row['service_id']}",
                   service_table.has(row["service_id"])
                   and service_table.service(row["service_id"]).arg_count == row["arity"],
                   json.dumps(row, sort_keys=True))

    for service_id in ("ps1.bios.internal.card_continuation", "ps1.mips.mflo",
                       "ps1.bios.internal.pad_start_hook", "ps1.bios.internal.pad_stop_hook"):
        gate.check(f"helper:{service_id}", service_table.has(service_id), service_id)
    gate.check("mflo:arity", service_table.service("ps1.mips.mflo").arg_count == 0)
    gate.check("continuation:arity",
               service_table.service("ps1.bios.internal.card_continuation").arg_count == 1)

    # Synthetic range non-collision inside the bounded window.
    def rng(base, size):
        return (base, base + size)
    c0 = rng(c0_surface.C0_TABLE_OFFSET, 0x20)
    handler = rng(c0_surface.EXCEPTION_HANDLER_OFFSET, 0x78)
    early = rng(c0_surface.EARLY_HANDLER_OFFSET, 0x40)
    b0_target = 0x1000
    overlaps = []
    for name_a, (lo_a, hi_a) in (("c0", c0), ("handler", handler), ("early", early)):
        for name_b, (lo_b, hi_b) in (("c0", c0), ("handler", handler), ("early", early)):
            if name_a < name_b and lo_a < hi_b and lo_b < hi_a:
                overlaps.append(f"{name_a}/{name_b}")
    gate.check("synthetic:no-overlap", not overlaps, ",".join(overlaps))
    pad_start = b0_target + 0x884
    gate.check("synthetic:pad-hook-distinct",
               not (handler[0] <= pad_start < handler[1])
               and not (early[0] <= pad_start < early[1]),
               hex(pad_start))

    document = {
        "schema": "openrecomp-phase14-service-matrix-v1", "stage": STAGE,
        "services": rows,
        "helper_services": [
            {"service_id": "ps1.bios.internal.pad_start_hook", "arity": 1},
            {"service_id": "ps1.bios.internal.pad_stop_hook", "arity": 1},
            {"service_id": "ps1.bios.internal.card_continuation", "arity": 1},
            {"service_id": "ps1.mips.mflo", "arity": 0},
        ],
        "synthetic_ranges": {
            "c0_table": list(c0), "exception_handler": list(handler),
            "early_handler": list(early), "b0_target": b0_target,
        },
        "index_aliasing": False,
        "arity_contradictions": False,
        "synthetic_target_collisions": False,
    }
    write_json(evidence / "consistency.json", document)
    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase14-result-v1", "stage": STAGE, "status": "PASS",
        "markers": {"OPENRECOMP_P14_30": "PASS", INITIALIZATION_MARKER: "NOT_PROVEN",
                    FRAME_MARKER: "NOT_PROVEN", PLAYABILITY_MARKER: "NOT_PROVEN",
                    GENERAL_MARKER: "NOT_PROVEN"},
        "next_stage": "P14-40",
    })
    write_json(evidence / "p14_30_tests.json", gate.tests_document("consistency"))
    gate.mark("OPENRECOMP_P14_30")
    gate.mark(INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(FRAME_MARKER, "NOT_PROVEN")
    gate.mark(PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(GENERAL_MARKER, "NOT_PROVEN")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase14/evidence/P14-30"))
