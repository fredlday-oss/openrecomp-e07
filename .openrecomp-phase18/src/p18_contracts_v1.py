#!/usr/bin/env python3
"""OpenRecomp Phase-18 contract definitions and markers V1.

Phase 18 begins from the frozen Phase-17 terminal authority:

  tag:    openrecomp-phase17-pass
  commit: d7cc5d09eebde398ca6ff3f3dad8dd5841913b69
  tree:   ad3aa822e5a02905ebc25477f7b6c69d0bffa055

Phase 18 creates its own appropriately named markers. Historical Phase-17
markers are preserved verbatim and are never rewritten.
"""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]

CONTRACTS_VERSION = "1.0.0"

# --- Frozen predecessor boundary (Phase 17 terminal authority) -------------
PHASE17_TERMINAL_COMMIT = "d7cc5d09eebde398ca6ff3f3dad8dd5841913b69"
PHASE17_TERMINAL_TREE = "ad3aa822e5a02905ebc25477f7b6c69d0bffa055"
PHASE17_TERMINAL_TAG = "openrecomp-phase17-pass"
PHASE17_TERMINAL_MARKER = "OPENRECOMP_PHASE17_TERMINAL_V1"
PHASE17_TERMINAL_MARKER_VALUE = "PASS"

# Phase 17 branch that Phase 18 forks from (must also resolve to the frozen
# terminal commit while the fork point is intact).
PHASE17_BRANCH = "phase17/ps1-title-overlay-recompile-v1"

# Inherited prior-phase anchors that Phase-17 itself froze.
PHASE16_BASE_COMMIT = "a0c26e882ca65cfc84cbec78f7e787509a4992a3"
PHASE16_BASE_TREE = "7f70357c14636d56c4c8bd000f5092f7052a1425"

# --- Fixture provenance inherited unchanged from Phase 16/17 ---------------
FIXTURE_BIN_SHA256 = "2ce144ba0e1fed6952ad80976814e3033fec6cddfb5e17cdf0294517ea311365"
FIXTURE_CUE_SHA256 = "beea454de356689cdaa06702f4ed76a5474fd125a7460619ee678c1ae8725df2"
FIXTURE_SLUS_SHA256 = "c230ff5cd14bdfa392f5d5765c9c907b631875aaaa7844792b38b9ac54930f6f"

# --- Phase 18 stage markers ------------------------------------------------
BOOTSTRAP_MARKER = "OPENRECOMP_P18_00"

# --- Phase 18 claim markers (created fresh; do NOT reuse Phase-17 names) ----
INITIALIZATION_MARKER = "OPENRECOMP_PHASE18_HERCULES_INITIALIZATION_PROOF"
FRAME_MARKER = "OPENRECOMP_PHASE18_HERCULES_FRAME_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE18_HERCULES_PLAYABILITY_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE18_GENERAL_PS1_COMPATIBILITY"
FIRST_FRAME_READY_MARKER = "FIRST_FRAME_READY"

# --- Historical Phase-17 claim markers, preserved (never promoted) ---------
PRESERVED_PHASE17_CLAIM_MARKERS = {
    "OPENRECOMP_PHASE17_HERCULES_INITIALIZATION_PROOF": "NOT_PROVEN",
    "OPENRECOMP_PHASE17_HERCULES_FRAME_PROOF": "NOT_PROVEN",
    "OPENRECOMP_PHASE17_HERCULES_PLAYABILITY_PROOF": "NOT_PROVEN",
    "OPENRECOMP_PHASE17_GENERAL_PS1_COMPATIBILITY": "NOT_PROVEN",
    "FIRST_FRAME_READY": "NO",
}

# --- Phase-18 namespace ----------------------------------------------------
PHASE18_NAMESPACE = ".openrecomp-phase18"
FROZEN_NAMESPACES = tuple(f".openrecomp-phase{n}" for n in range(1, 18))
