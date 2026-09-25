#!/usr/bin/env python3
"""OpenRecomp Phase-16 private-fixture analysis V1.

Builds the private-fixture structural analysis with Phase 16 BIOS services installed
(including C0:0x0A ChangeClearRCnt) and Phase 16 internal indirect targets admitted
(including 0x8001aa14 -> 0x8001a31c, 0x8001a0c0).
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for extra in ("", ".openrecomp-phase3/src", ".openrecomp-phase8/src",
              ".openrecomp-phase9/src", ".openrecomp-phase9/fixture",
              ".openrecomp-phase10/src", ".openrecomp-phase11/src",
              ".openrecomp-phase12/src", ".openrecomp-phase13/src",
              ".openrecomp-phase14/src", ".openrecomp-phase15/src",
              ".openrecomp-phase16/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p9_image_bridge_v1 as bridge  # noqa: E402
import p9_memory_map_v1 as memory_map  # noqa: E402
import p9_psx_exe_v1 as psx  # noqa: E402
import p10_structure_v1 as p10_structure  # noqa: E402
import p11_bios_v1 as p11_bios  # noqa: E402
import p11_dynamic_v1 as dynamic  # noqa: E402
import p11_structure_v1 as structure_bridge  # noqa: E402
import p13_pad_hook_v1 as pad_hook  # noqa: E402
from tools import test_phase11_gpu_closure_v1 as p11_06  # noqa: E402
from tools import test_phase11_gpu_v1 as p11_05  # noqa: E402

import p16_services_v1 as services16  # noqa: E402
import p16_surface_v1 as surface16  # noqa: E402

ANALYSIS_VERSION = "1.0.0"


def build_phase16_private(
    fixture_root: pathlib.Path,
    extra_a0: tuple[int, ...] = surface16.EXTRA_A0,
    extra_c0: tuple[int, ...] = surface16.EXTRA_C0,
    extra_b0: tuple[int, ...] = surface16.EXTRA_B0,
    p14_b0: tuple[int, ...] = surface16.P14_B0,
    p14_a0: tuple[int, ...] = surface16.P14_A0,
    p15_a0: tuple[int, ...] = surface16.P15_A0,
    p15_b0: tuple[int, ...] = surface16.P15_B0,
    internal_targets: dict[int, tuple[int, ...]] | None = None,
) -> dict[str, Any]:
    if internal_targets is None:
        internal_targets = surface16.INTERNAL_TARGETS

    tables = services16.install_phase16_services(
        extra_a0=extra_a0,
        extra_c0=extra_c0,
        extra_b0=extra_b0,
        p14_b0=p14_b0,
        p14_a0=p14_a0,
        p15_a0=p15_a0,
        p15_b0=p15_b0,
    )
    image = psx.ingest((fixture_root / p11_05.fixture.PRIMARY_EXECUTABLE).read_bytes())
    contract = memory_map.build_contract(image)
    flat = memory_map.flat_image(image)
    pipeline = bridge.analyze(image, contract, flat)
    source = p11_05.source_for(image.file_sha256)
    base = p10_structure.analyze_structure(
        pipeline.analysis, source=source, entry=image.header.pc0
    )
    read_word = lambda address: memory_map.read_u32(contract, flat, address)
    target_entries = tuple(sorted({
        target for values in (internal_targets or {}).values() for target in values
    }))
    merged_a, extension_a, extra_a = dynamic.extend_analysis(
        pipeline.analysis, read_word, image.header.t_addr,
        image.header.t_addr + image.header.t_size, (p11_05.PROVEN_METHOD_POINTER,),
    )
    merged_b, extension_b, extra_b = dynamic.extend_analysis(
        pipeline.analysis, read_word, image.header.t_addr,
        image.header.t_addr + image.header.t_size,
        (p11_05.PROVEN_METHOD_POINTER, p11_06.TARGET_VALUE) + target_entries,
    )
    common = {"source": source, "entry": image.header.pc0, "services": tables}
    observations_a = {p11_05.DRIVER_METHOD_SITE: (p11_05.PROVEN_METHOD_POINTER,)}
    observations_b = {
        p11_05.DRIVER_METHOD_SITE: (p11_05.PROVEN_METHOD_POINTER,),
        p11_06.TARGET_SITE: (p11_06.TARGET_VALUE,),
    }
    if internal_targets:
        observations_b = dict(observations_b)
        observations_b.update(internal_targets)
    injected_base = pad_hook.inject_records(pipeline.analysis)
    injected_a = pad_hook.inject_records(merged_a)
    injected_b = pad_hook.inject_records(merged_b)
    result_a, sites_a, _ = structure_bridge.analyze_structure_with_overlays(
        injected_base,
        dynamic_observations=observations_a,
        extensions=extra_a, merged_analysis=injected_a, **common,
    )
    result_b, sites_b, _ = structure_bridge.analyze_structure_with_overlays(
        injected_base,
        dynamic_observations=observations_b,
        extensions=extra_b, merged_analysis=injected_b, **common,
    )
    result_a = pad_hook.reclassify(result_a, sites_a, injected_a, observations_a)
    result_b = pad_hook.reclassify(result_b, sites_b, injected_b, observations_b)
    return {
        "image": image, "contract": contract, "flat": flat, "base": base,
        "result_a": result_a, "result_b": result_b,
        "sites_a": p11_bios.resolved_sites(sites_a),
        "sites_b": p11_bios.resolved_sites(sites_b),
        "site_document_b": sites_b, "merged_b": merged_b,
        "pad_hook": pad_hook.document(),
        "internal_targets": dict(internal_targets or {}),
    }
