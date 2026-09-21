#!/usr/bin/env python3
"""OpenRecomp Phase-11 native build/run helpers V1.

Builds one emission set with the frozen reproducible build pipeline and runs it
with the explicit deterministic bounded-execution budgets. Nothing here
executes original guest machine code: the guest image is inert data and all
executed guest semantics are generated C.
"""

from __future__ import annotations

import hashlib
import pathlib
import shutil
import subprocess
from typing import Any

import p11_trace_v1 as trace
from openrecomp import build_pipeline as bp

ROOT = pathlib.Path(__file__).resolve().parents[2]

NATIVE_VERSION = "1.0.0"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_native(
    build_set: dict[str, Any],
    workspace: pathlib.Path,
    *,
    fixture_id: str,
    run_count: int = 2,
    program_name: str | None = None,
) -> dict[str, Any]:
    """Build one emission set through the frozen reproducible build pipeline."""
    import p11_emission_v1 as emission

    name = program_name or emission.PROGRAM_NAME
    if workspace.exists():
        shutil.rmtree(workspace)
    comparison = bp.build_generated_host(
        lambda: build_set["files"][name],
        support_sources=tuple(
            bp.BuildSource(
                source_name,
                bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
                build_set["files"][source_name].encode("utf-8"),
            )
            for source_name in (emission.IMAGE_NAME, emission.SUPPORT_NAME, emission.DRIVER_NAME)
        ),
        config=bp.BuildConfig(fixture_id=fixture_id, smoke_test=False, run_count=run_count),
        workspace=workspace,
        keep_workspace=True,
    )
    executables = [workspace / f"run{index}" / "program.exe" for index in range(1, run_count + 1)]
    return {
        "workspace": workspace,
        "build_status": [run.manifest.build_status.value for run in comparison.runs],
        "executables": executables,
        "build_reproducible": len({sha256_bytes(path.read_bytes()) for path in executables}) == 1,
        "executable_sha256": sha256_bytes(executables[0].read_bytes()),
        "toolchain": comparison.runs[0].manifest.toolchain.to_document(),
    }


def run_native(
    executable: pathlib.Path,
    *,
    access_budget: int | None = None,
    block_budget: int | None = None,
    timeout: int = 1800,
) -> dict[str, Any]:
    """Run one generated native program with explicit deterministic budgets."""
    return trace.run_trace_program(
        executable, budget=access_budget, block_budget=block_budget, timeout=timeout
    )


def observable_snapshot(parsed: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: parsed.get(key) for key in keys}
