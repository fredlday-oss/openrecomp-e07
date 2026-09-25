#!/usr/bin/env python3
"""OpenRecomp Phase-16 BIOS service surface V1.

Extends the frozen Phase-15 typed BIOS vector boundary with the documented BIOS
services Phase 16 proves necessary to reach authentic CD-ROM execution and
TITLE overlay dispatch:

* ``ps1.bios.C0.0A`` ChangeClearRCnt(t, flag): documented root counter auto-clear
  mode configuration (PSX-SPX C(0Ah)).

Installs the Phase-16 surface by first installing the pinned Phase-15 surface,
then adding only the selected documented Phase-16 additions.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for extra in (".openrecomp-phase10/src", ".openrecomp-phase11/src",
              ".openrecomp-phase12/src", ".openrecomp-phase13/src",
              ".openrecomp-phase14/src", ".openrecomp-phase15/src"):
    sys.path.insert(0, str(ROOT / extra))

import p11_bios_v1 as p11_bios  # noqa: E402
import p13_services_v1 as services13  # noqa: E402
import p15_services_v1 as services15  # noqa: E402

SERVICES_VERSION = "1.0.0"

DOCUMENTED_C0_SERVICES_ADDITIONS: dict[int, dict[str, Any]] = {
    0x0A: {
        "name": "ChangeClearRCnt",
        "signature": ["t", "flag"],
        "returns": "previous flag value in $v0",
        "result_register": 2,
        "refusal": "target outside range (0..3), flag not 0/1, or missing result slot",
        "semantics": "record auto-clear flag for root counter t (0..3)",
        "source": "public PS1 BIOS documentation (PSX-SPX Kernel: C(0Ah) ChangeClearRCnt(t, flag))",
    }
}

DOCUMENTED_INDEX_NAMES_ADDITIONS: dict[tuple[str, int], str] = {
    ("C0", 0x0A): "ChangeClearRCnt",
}


def install_phase16_services(
    extra_a0: tuple[int, ...] = (),
    extra_c0: tuple[int, ...] = (0x02, 0x03, 0x0A),
    extra_b0: tuple[int, ...] = (),
    p14_b0: tuple[int, ...] = (0x12, 0x13, 0x14, 0x3d, 0x3f, 0x47),
    p14_a0: tuple[int, ...] = (0x3e, 0x44),
    p15_a0: tuple[int, ...] = (0x13, 0x43, 0x72),
    p15_b0: tuple[int, ...] = (0x17, 0x18, 0x19),
    p16_c0: tuple[int, ...] = (0x0A,),
) -> dict[str, dict[int, dict[str, Any]]]:
    for index in p16_c0:
        if index not in DOCUMENTED_C0_SERVICES_ADDITIONS:
            raise KeyError(f"no documented Phase-16 C0 addition for 0x{index:02x}")
        services13.DOCUMENTED_C0_SERVICES[index] = DOCUMENTED_C0_SERVICES_ADDITIONS[index]
        p11_bios.DOCUMENTED_C0_SERVICES[index] = DOCUMENTED_C0_SERVICES_ADDITIONS[index]
    services13.DOCUMENTED_INDEX_NAMES_ADDITIONS.update(DOCUMENTED_INDEX_NAMES_ADDITIONS)
    p11_bios.DOCUMENTED_INDEX_NAMES.update(DOCUMENTED_INDEX_NAMES_ADDITIONS)

    tables = services15.install(
        extra_a0=extra_a0,
        extra_c0=extra_c0,
        extra_b0=extra_b0,
        p14_b0=p14_b0,
        p14_a0=p14_a0,
        p15_a0=p15_a0,
        p15_b0=p15_b0,
    )
    p11_bios.VECTOR_TABLES["C0"] = p11_bios.DOCUMENTED_C0_SERVICES
    tables["C0"] = p11_bios.DOCUMENTED_C0_SERVICES
    return tables


def service_tables() -> dict[str, dict[int, dict[str, Any]]]:
    return {
        "A0": p11_bios.DOCUMENTED_A0_SERVICES,
        "B0": p11_bios.DOCUMENTED_B0_SERVICES,
        "C0": p11_bios.DOCUMENTED_C0_SERVICES,
    }


def service_surface_document() -> dict[str, Any]:
    base = services15.service_surface_document()
    base["schema"] = "openrecomp-phase16-bios-service-surface-v1"
    base["services_version"] = SERVICES_VERSION
    base["c0_additions_p16"] = {
        f"0x{index:02x}": {
            "service_id": f"ps1.bios.C0.{index:02x}",
            "name": document["name"],
            "signature": document["signature"],
            "result_register": document["result_register"],
            "semantics": document["semantics"],
            "source": document["source"],
        }
        for index, document in sorted(DOCUMENTED_C0_SERVICES_ADDITIONS.items())
    }
    base["third_party_code_imported"] = "NO"
    return base
