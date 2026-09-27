#!/usr/bin/env python3
"""OpenRecomp Phase-18 imported-reconnaissance inventory V1.

Inventories the imported historical PC reconnaissance as reference/hypothesis
material ONLY. It records public-safe metadata (category names, per-set file
counts, total size, and the digest of the transfer INDEX document). It never
records the private import root paths, never reads imported bytes into evidence
and never treats an imported result as proof.

The import INDEX evidence policy is explicit: imported files MUST NOT
automatically be treated as authoritative OpenRecomp proof.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess

#: The import lives outside the repository and is referenced by a logical name
#: only. The concrete path is resolved at runtime for local inspection and is
#: never written into evidence.
IMPORT_PARENT_ENV = "OPENRECOMP_IMPORT_RECON_ROOT"

#: Controller worktree root (…/.openrecomp-phase18/src -> …).
WORKTREE_ROOT = pathlib.Path(__file__).resolve().parents[2]
#: The import lives beside the worktrees (…/OpenRecomp/imported-recon/…).
DEFAULT_IMPORT_ROOT = WORKTREE_ROOT.parents[1] / "imported-recon" / "pc-phase1-17"

MARKER = "OPENRECOMP_PHASE18_IMPORT_RECON_INVENTORY"

#: Public-safe campaign themes surfaced by the inventory (derived from directory
#: names, which are not private). These are hypotheses, not proof.
THEME_KEYWORDS = {
    "gpustat_status": ("gpustat", "rootcounter"),
    "dma_ordering_table": ("dma2", "ot-population", "drawotag", "first-dma"),
    "first_frame": ("first-frame", "clearimage", "post-timer"),
    "initialization": ("targeted-init", "init-", "init_", "bu-init", "post-b0"),
    "gpu_geometry": ("gpu", "gte", "texture", "primitive"),
    "interrupt_timer": ("interrupt", "istat", "imask", "timer", "vsync"),
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def import_root() -> pathlib.Path:
    import os
    env = os.environ.get(IMPORT_PARENT_ENV)
    if env:
        return pathlib.Path(env)
    return DEFAULT_IMPORT_ROOT


def inventory() -> dict[str, object]:
    root = import_root()
    document: dict[str, object] = {
        "schema": "openrecomp-phase18-import-recon-inventory-v1",
        "import_present": root.is_dir(),
        "source_sets": [],
        "theme_hits": {},
        "authority": "REFERENCE_HYPOTHESIS_ONLY",
        "evidence_policy": "IMPORTED_RESULTS_REQUIRE_INDEPENDENT_AUTHENTICATION",
    }
    if not root.is_dir():
        return document

    files = [p for p in root.rglob("*") if p.is_file()]
    total_bytes = sum(p.stat().st_size for p in files)
    document["file_count"] = len(files)
    document["total_bytes"] = total_bytes

    index = root / "INDEX.md"
    if index.is_file():
        document["index_sha256"] = _sha256_bytes(index.read_bytes())

    # Per top-level source set: public-safe count + size only.
    sets: list[dict[str, object]] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        set_files = [p for p in entry.rglob("*") if p.is_file()]
        sets.append({
            "category": entry.name,
            "file_count": len(set_files),
            "total_bytes": sum(p.stat().st_size for p in set_files),
        })
    document["source_sets"] = sets

    # Theme hits are counts of directories whose names match a campaign theme.
    lowered = [p.name.lower() for p in root.rglob("*") if p.is_dir()]
    themes: dict[str, int] = {}
    for theme, keywords in THEME_KEYWORDS.items():
        themes[theme] = sum(
            1 for name in lowered if any(kw in name for kw in keywords))
    document["theme_hits"] = themes
    return document


def main() -> int:
    document = inventory()
    print(f"{MARKER}={'PASS' if document['import_present'] else 'ABSENT'}")
    print(json.dumps({k: v for k, v in document.items()
                      if k != "source_sets"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
