#!/usr/bin/env python3
"""Phase-17 P17-04R Revision 4 linkage-level handwritten-substitute exclusion.

The active native artifact built by the official run must not link to, import,
resolve, reference, or execute through the historical handwritten
title-transition/execution machinery.  This module inspects the *actual built
binary* (nm / readelf / objdump symbol, dynamic-symbol, relocation and
DT_NEEDED surfaces) instead of trusting metadata flags or generated-C literals.
"""

from __future__ import annotations

import hashlib
import pathlib
import subprocess
from typing import Any, Iterable, Sequence

# Forbidden historical handwritten title-transition machinery references.
FORBIDDEN_LINKED_SYMBOL_TOKENS: tuple[str, ...] = (
    "TITLE_TRANSITION_CODE",
    "p16_emission_v1",
    "p16_record_title_transition",
)

INSPECTION_METHOD = (
    "nm -a / nm -D / readelf -sW / readelf -rW / readelf -dW / objdump -T "
    "symbol, dynamic-symbol, relocation and DT_NEEDED inspection"
)

PROBES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("nm_all", ("nm", "-a")),
    ("nm_dynamic", ("nm", "-D")),
    ("readelf_symbols", ("readelf", "-sW")),
    ("readelf_relocations", ("readelf", "-rW")),
    ("readelf_dynamic", ("readelf", "-dW")),
    ("objdump_dynamic_symbols", ("objdump", "-T")),
)


class LinkageInspectionError(RuntimeError):
    """The linkage inspection could not be completed."""


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _tool_version(tool: str) -> str:
    try:
        completed = subprocess.run([tool, "--version"], capture_output=True, text=True)
    except OSError:
        return "UNAVAILABLE"
    lines = (completed.stdout or completed.stderr).strip().splitlines()
    return lines[0] if lines else "UNAVAILABLE"


def tool_versions() -> dict[str, str]:
    return {tool: _tool_version(tool) for tool in ("nm", "readelf", "objdump")}


def inspect_artifact(path: pathlib.Path) -> dict[str, Any]:
    """Run every linkage probe against one built artifact."""
    if not path.is_file():
        raise LinkageInspectionError(f"artifact missing: {path.name}")
    surfaces: dict[str, dict[str, Any]] = {}
    for name, base in PROBES:
        completed = subprocess.run([*base, str(path)], capture_output=True, text=True)
        surfaces[name] = {
            "returncode": completed.returncode,
            "output": completed.stdout or "",
            "stderr_tail": completed.stderr.strip().splitlines()[-1] if completed.stderr.strip() else "",
        }
    return {"artifact": path.name, "surfaces": surfaces}


def _forbidden_hits(inspection: dict[str, Any],
                    tokens: Sequence[str]) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for surface, data in sorted(inspection["surfaces"].items()):
        text = data["output"]
        for token in tokens:
            if token in text:
                hits.append({"artifact": inspection["artifact"], "surface": surface, "token": token})
    return hits


def linkage_exclusion_report(paths: Iterable[pathlib.Path],
                             tokens: Sequence[str] = FORBIDDEN_LINKED_SYMBOL_TOKENS) -> dict[str, Any]:
    """Public-safe linkage inspection summary and digest for the built artifacts."""
    artifacts: dict[str, Any] = {}
    hits: list[dict[str, str]] = []
    transcript_parts: list[str] = []
    total_symbol_lines = 0
    for path in paths:
        inspection = inspect_artifact(pathlib.Path(path))
        hits.extend(_forbidden_hits(inspection, tokens))
        probe_summary: dict[str, Any] = {}
        for surface, data in sorted(inspection["surfaces"].items()):
            lines = len([line for line in data["output"].splitlines() if line.strip()])
            total_symbol_lines += lines
            probe_summary[surface] = {"returncode": data["returncode"], "line_count": lines}
            transcript_parts.append(
                f"{inspection['artifact']}|{surface}|{data['returncode']}|{_sha256_text(data['output'])}"
            )
        artifacts[inspection["artifact"]] = probe_summary
    return {
        "schema": "openrecomp-phase17-linkage-exclusion-v1",
        "inspection_method": INSPECTION_METHOD,
        "tool_versions": tool_versions(),
        "forbidden_tokens": list(tokens),
        "artifacts": artifacts,
        "inspected_line_count": total_symbol_lines,
        "forbidden_hits": hits,
        "forbidden_hit_count": len(hits),
        "excluded": not hits,
        "inspection_digest": _sha256_text("\n".join(sorted(transcript_parts))),
    }
