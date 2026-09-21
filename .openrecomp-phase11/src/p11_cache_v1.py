#!/usr/bin/env python3
"""OpenRecomp Phase-11 analysis-cache provenance V1.

Reuses the frozen Phase-10 provenance-keyed analysis cache and extends the
provenance document with the Phase-11 components required by the Phase-11
control policy:

* the private executable SHA-256, the CUE SHA-256 and every referenced BIN
  SHA-256 (the authoritative disc entry point plus its tracks);
* the analysis, semantics, runtime and device-contract versions;
* the trace configuration digest (hooks, capacities, trace fragment hash);
* the scripted-input identity (``none`` until deterministic input is defined).

A changed executable, disc, version, trace configuration or input identity
produces a different key and therefore a cache miss; stale entries are never
reused.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
from typing import Any

import p10_analysis_cache_v1 as cache
import p11_emission_v1 as emission
import p10_mips32_semantics_v1 as semantics
import p10_runtime_v1 as runtime

PROVENANCE_VERSION = "1.0.0"

FRONTEND_VERSION = "p9-psx-exe-1.0.0"
DISC_MODEL_VERSION = "p9-cdrom-1.0.0"
DEVICE_CONTRACT_VERSION = "p9-io-1.0.0"


def trace_configuration_digest() -> str:
    document = {
        "provenance_version": PROVENANCE_VERSION,
        "trace_configuration": emission.TRACE_CONFIGURATION,
        "trace_fragment_sha256": emission.sha256_text(emission.trace_fragment_source()[0]),
        "trace_driver_sha256": emission.sha256_text(emission.trace_driver_source()[0]),
    }
    return hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def analysis_config_digest(*, traced: bool) -> str:
    document = {
        "provenance_version": PROVENANCE_VERSION,
        "traced": traced,
        "trace_configuration_digest": trace_configuration_digest() if traced else None,
        "unsupported_indirect_policy": "BOUNDARY",
        "driver": "phase11-trace" if traced else "phase10",
    }
    return hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def build_provenance(
    identity: dict[str, Any],
    *,
    traced: bool,
    scripted_input_identity: str = "none",
) -> dict[str, Any]:
    """The Phase-11 provenance document for one analysis configuration."""
    executable = identity["executable"]
    disc = identity["disc"]
    bins = [entry["sha256"] for entry in disc["bins"]]
    return {
        "executable_sha256": executable["sha256"],
        "cue_sha256": disc["cue"]["cue_sha256"],
        "bin_sha256s": sorted(bins),
        "exe_identity_digest": hashlib.sha256(
            json.dumps(
                {
                    "size": executable["size"],
                    "sha256": executable["sha256"],
                    "boot_target": identity["system_cnf"]["boot_target"],
                    "boot_extent_lba": identity["system_cnf"]["boot_extent_lba"],
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest(),
        "frontend_version": FRONTEND_VERSION,
        "semantic_version": f"p10-mips32-{semantics.SEMANTICS_VERSION}",
        "runtime_version": f"p10-runtime-{runtime.RUNTIME_VERSION}",
        "disc_model_version": DISC_MODEL_VERSION,
        "device_contract_version": DEVICE_CONTRACT_VERSION,
        "analysis_config_digest": analysis_config_digest(traced=traced),
        "trace_configuration_digest": trace_configuration_digest() if traced else "none",
        "scripted_input_identity": scripted_input_identity,
        "provenance_version": PROVENANCE_VERSION,
    }


class Phase11Cache:
    """A Phase-11 provenance-keyed cache over an untracked directory."""

    def __init__(self, root: pathlib.Path) -> None:
        self._cache = cache.AnalysisCache(root)
        self.root = pathlib.Path(root)

    def key(self, provenance: dict[str, Any]) -> str:
        return cache.provenance_digest(provenance)

    def lookup(self, provenance: dict[str, Any]) -> dict[str, Any] | None:
        return self._cache.lookup(provenance)

    def store(self, provenance: dict[str, Any], document: dict[str, Any]) -> str:
        return self._cache.store(provenance, document)
