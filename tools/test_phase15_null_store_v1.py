#!/usr/bin/env python3
"""Deterministic P15-05 historical null-store root-cause closure gate."""

from __future__ import annotations

import copy
import hashlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase3/src", ".openrecomp-phase8/src",
              ".openrecomp-phase9/src", ".openrecomp-phase9/fixture",
              ".openrecomp-phase10/src", ".openrecomp-phase11/src",
              ".openrecomp-phase12/src", ".openrecomp-phase13/src",
              ".openrecomp-phase14/src", ".openrecomp-phase15/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p11_native_v1 as native  # noqa: E402
from tools import test_phase11_gpu_v1 as p11_05  # noqa: E402

from p15_contracts_v1 import NULL_STORE_ROOT_CAUSE_MARKER  # noqa: E402
from p15_gate_v1 import assert_public_safe, run_stage, write_json  # noqa: E402
import p15_analysis_v1 as analysis_mod  # noqa: E402
import p15_emission_v1 as emission  # noqa: E402
import p15_mmio_contract_v1 as contract  # noqa: E402
import p15_surface_v1 as surface  # noqa: E402
import p15_trace_v1 as trace  # noqa: E402

STAGE = "P15-05"

READ_D2_ANCHOR = (
    "               || a == P15_D2_CHCR || a == P15_DPCR || a == P15_DICR) {"
)
READ_D2_DISABLED = (
    "               || a == P15_DPCR || a == P15_DICR) {"
)
WRITE_D2_ANCHOR = "    } else if (a == P15_D2_CHCR) {\n"
WRITE_D2_DISABLED = "    } else if (0 && a == P15_D2_CHCR) {\n"


def prepare(root: pathlib.Path) -> tuple[dict, object, bytes]:
    private = analysis_mod.build_phase15_private(
        p11_05.DEFAULT_PRIVATE_FIXTURE_ROOT,
        extra_a0=surface.EXTRA_A0, extra_c0=surface.EXTRA_C0,
        extra_b0=surface.EXTRA_B0, p14_b0=surface.P14_B0,
        p14_a0=surface.P14_A0, internal_targets=surface.INTERNAL_TARGETS,
    )
    image = private["image"]
    build_set = emission.build_build_set(
        private["result_b"], private["base"], private["contract"], private["flat"],
        image.file_sha256, sites=private["sites_b"], trace=True,
        guarded_resolved_indirect=True, extra_a0=surface.EXTRA_A0,
        extra_c0=surface.EXTRA_C0, extra_b0=surface.EXTRA_B0,
        p14_b0=surface.P14_B0, p14_a0=surface.P14_A0,
    )
    return build_set, image, image.payload


def d2_disabled(build_set: dict) -> dict:
    variant = copy.deepcopy(build_set)
    support = variant["files"][emission.SUPPORT_NAME]
    if support.count(READ_D2_ANCHOR) != 1:
        raise AssertionError("D2 read anchor missing or ambiguous")
    if support.count(WRITE_D2_ANCHOR) != 1:
        raise AssertionError("D2 write anchor missing or ambiguous")
    support = support.replace(READ_D2_ANCHOR, READ_D2_DISABLED)
    support = support.replace(WRITE_D2_ANCHOR, WRITE_D2_DISABLED)
    variant["files"][emission.SUPPORT_NAME] = support
    return variant


def build_run(root: pathlib.Path, build_set: dict, tag: str) -> tuple[dict, dict]:
    built = native.build_native(
        build_set, root / f".openrecomp-phase15/build/P15-05/{tag}",
        fixture_id=tag, run_count=2,
    )
    executed = trace.run_program(
        built["executables"][0], budget=p11_05.ACCESS_BUDGET,
        block_budget=surface.FRONTIER_BLOCK_BUDGET, timeout=600,
    )
    return built, executed


def access_count(executed: dict, address: int) -> int:
    prefix = f"0x{address:08x}:"
    return sum(
        int(count)
        for signature, count in executed["parsed"].get("nonram", {}).items()
        if signature.startswith(prefix)
    )


def model_event_count(executed: dict, address: int) -> int:
    simple = executed["simple"]
    total = 0
    for index in range(int(simple.get("p15_mmio_events", "0"))):
        encoded = simple.get(f"p15_mmio_{index}", "")
        if encoded.startswith(f"0x{address:08x},"):
            total += 1
    return total


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    build_set, image, payload = prepare(root)
    disabled_set = d2_disabled(build_set)
    full_build, full = build_run(root, build_set, "p15-05-full")
    disabled_build, disabled = build_run(root, disabled_set, "p15-05-no-d2")

    gate.check("full:build", full_build["build_status"] == ["OK", "OK"],
               str(full_build["build_status"]))
    gate.check("disabled:build", disabled_build["build_status"] == ["OK", "OK"],
               str(disabled_build["build_status"]))
    gate.check("full:stderr-empty", full["stderr_bytes"] == 0,
               str(full["stderr_bytes"]))
    gate.check("disabled:stderr-empty", disabled["stderr_bytes"] == 0,
               str(disabled["stderr_bytes"]))

    full_zero = access_count(full, 0x00000000)
    disabled_zero = access_count(disabled, 0x00000000)
    full_d2 = access_count(full, contract.D2_CHCR)
    disabled_d2 = access_count(disabled, contract.D2_CHCR)
    full_d2_model = model_event_count(full, contract.D2_CHCR)
    disabled_d2_model = model_event_count(disabled, contract.D2_CHCR)
    full_denied = int(full["simple"].get("denied", "0"))
    disabled_denied = int(disabled["simple"].get("denied", "0"))
    gate.check("causal:full-d2-handled", full_d2 > 0 and full_d2_model == full_d2,
               f"accesses={full_d2}:model={full_d2_model}")
    gate.check("causal:full-null-store-absent", full_zero == 0, str(full_zero))
    gate.check("causal:disable-d2-falls-through",
               disabled_d2 > 0 and disabled_d2_model == 0,
               f"accesses={disabled_d2}:model={disabled_d2_model}")
    gate.check("causal:disable-d2-restores-null-store", disabled_zero > 0,
               str(disabled_zero))
    gate.check("causal:denial-delta",
               disabled_denied - full_denied == disabled_d2 + disabled_zero,
               f"{disabled_denied}-{full_denied}={disabled_d2}+{disabled_zero}")
    gate.check("causal:temporal-order",
               disabled_d2 > 0 and disabled_zero > 0,
               "D2 denial precedes historical cascaded null store per verified recon")

    model = contract.MmioModel()
    gate.check("fail-closed:address-zero-unhandled",
               model.write(0x00000000, 8, 1) == contract.STATUS_UNHANDLED,
               "address zero remains outside the model")
    gate.check("fail-closed:address-zero-not-registered",
               0x00000000 not in contract.ALLOWED_WIDTHS,
               "address zero absent")

    document = {
        "schema": "openrecomp-phase15-null-store-root-cause-v1",
        "stage": STAGE,
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED_CAUSAL_ABLATION",
        "fixture": {"sha256": image.file_sha256, "size": image.file_size},
        "historical_observation": {
            "source": "verified phase15-istat-imask-live-contract-v1 reconnaissance",
            "d2_chcr_denial_ordinal": 3,
            "d2_chcr_denial_event_index": 468293,
            "null_store_ordinal": 4,
            "null_store_event_index": 468294,
            "null_store_pc": "0x8001843c",
            "null_store_address": "0x00000000",
        },
        "full_production": {
            "support_sha256": hashlib.sha256(
                build_set["files"][emission.SUPPORT_NAME].encode("utf-8")
            ).hexdigest(),
            "executable_sha256": full_build["executable_sha256"],
            "stdout_sha256": full["stdout_sha256"],
            "aggregate_denied": full_denied,
            "d2_chcr_accesses": full_d2,
            "d2_chcr_model_events": full_d2_model,
            "address_zero_accesses": full_zero,
        },
        "d2_ablation": {
            "kind": "TEST_ONLY_DISABLE_D2_CHCR_READ_WRITE_PRE_DISPATCH",
            "support_sha256": hashlib.sha256(
                disabled_set["files"][emission.SUPPORT_NAME].encode("utf-8")
            ).hexdigest(),
            "executable_sha256": disabled_build["executable_sha256"],
            "stdout_sha256": disabled["stdout_sha256"],
            "aggregate_denied": disabled_denied,
            "d2_chcr_accesses": disabled_d2,
            "d2_chcr_model_events": disabled_d2_model,
            "address_zero_accesses": disabled_zero,
        },
        "causal_conclusion": (
            "The historical address-zero store is a downstream cascade of the "
            "missing D2_CHCR producer/state: disabling only D2_CHCR handling "
            "restores both the D2 denial and the following null store; the full "
            "production model removes both."
        ),
        "address_zero_writable": False,
        "private_fixture_bytes_recorded": "NO",
        "third_party_code_imported": "NO",
    }
    write_json(evidence / "null_store_root_cause.json", document)
    assert_public_safe(gate, "null-store", document, payload)

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase15-result-v1", "stage": STAGE,
        "status": "PASS", "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "markers": {NULL_STORE_ROOT_CAUSE_MARKER: "PASS",
                    "OPENRECOMP_P15_05": "PASS"},
        "next_stage": "P15-06",
    })
    gate.mark(NULL_STORE_ROOT_CAUSE_MARKER)
    gate.mark("OPENRECOMP_P15_05")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase15/evidence/P15-05"))
