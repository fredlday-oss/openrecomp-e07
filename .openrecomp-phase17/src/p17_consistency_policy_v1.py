#!/usr/bin/env python3
"""Narrow, explicitly-scoped consistency policy for P17-90.

Two divergences between the historical committed Phase-17 evidence and a fresh
regeneration were classified as non-semantic. Both classifications are
*mechanically* provable, and both are re-proved by this module's caller at
P17-90 gate time rather than merely asserted here.

1. ``inspection_digest`` (at ``linkage_exclusion.inspection_digest`` in
   ``linkage_exclusion.json`` and its copy inside ``RESULT.json``) is
   path-dependent by construction.  ``p17_linkage_exclusion_v1`` hashes the
   *raw stdout* of six binutils probes, and ``objdump -T`` echoes the absolute
   path of the artifact it was given in its first output line.  The digest
   therefore changes when the private build root changes, even though the
   inspected binary is byte-identical.

   The digest is opaque, so normalising the *document* after the fact cannot
   repair it: the only sound normalisation happens at hash time.  This module
   therefore provides :func:`root_invariant_linkage_digest`, which recomputes
   the identical digest construction with the echoed path prefix replaced by a
   fixed token.  That value is provably independent of the build root while
   still changing on any real change to the inspected binary or its symbols.

2. ``public:committed-evidence-clean`` reports ``file_count`` 9 on a fresh run
   versus 11 in the committed evidence.  The gate scans its evidence directory
   before the stage runner writes ``official_runs.json`` and
   ``determinism.json`` into it.  Those two documents are runner-generated
   records *about* the runs; they are not semantic proof inputs and are not
   consumed as such by any later stage.

This is deliberately not a general-purpose "ignore differences" switch. Every
rule names the exact JSON path it applies to, each is justified by a
re-derivation the gate performs live, and every other differing field is a
hard, fail-closed divergence.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable, Sequence

POLICY_SCHEMA = "openrecomp-phase17-consistency-policy-v1"

MARKER = "OPENRECOMP_PHASE17_CONSISTENCY_POLICY_V1"

#: The fixed token substituted for an echoed absolute artifact path.
PATH_TOKEN = "<BUILD_ROOT>"

#: The two documents the stage runner writes *after* the gate body has already
#: scanned its evidence directory.  Their presence in a committed evidence
#: directory is what turns the gate-time ``file_count`` into the committed one.
RUNNER_GENERATED_DOCUMENTS: tuple[str, ...] = (
    "official_runs.json",
    "determinism.json",
)

#: The 12 evidence documents committed for P17-04R at its certifying commit.
#: This is the "committed" side of the ``file_count`` comparison; the
#: "gate-time" side is whatever the P17-90 gate body has written into its own
#: evidence directory at the moment it scans it.
P17_04R_CERTIFYING_COMMIT = "36be03b5756726a20ecd69735b41cb5eba795155"

P17_04R_COMMITTED_JSON: tuple[str, ...] = (
    "RESULT.json",
    "determinism.json",
    "jal_frontier.json",
    "linkage_exclusion.json",
    "next_stage.json",
    "official_runs.json",
    "p17_04r_tests.json",
    "persistence.json",
    "runtime_result.json",
    "semantic_vocabulary.json",
    "stage_metadata.json",
    "title_exec_emission.json",
)

#: Written by :func:`run_stage` *after* the gate body has run, so it is never
#: part of any ``file_count`` scan the body performs.
P17_04R_TESTS_DOCUMENT = "p17_04r_tests.json"

#: The nine documents present in the P17-04R evidence directory when its gate
#: body reaches the ``public:committed-evidence-clean`` scan, i.e. the committed
#: set minus the runner-generated documents and the trailing tests document.
P17_04R_GATE_TIME_JSON: tuple[str, ...] = tuple(
    name for name in P17_04R_COMMITTED_JSON
    if name not in RUNNER_GENERATED_DOCUMENTS and name != P17_04R_TESTS_DOCUMENT
)

#: Exact JSON paths, relative to a stage's generated evidence, that are allowed
#: to differ between the committed and a freshly generated artifact, together
#: with the mechanical reason the difference carries no semantic content.
CLASSIFIED_PATHS: tuple[dict[str, str], ...] = (
    {
        "json_path": "linkage_exclusion.inspection_digest",
        "class": "PATH_DEPENDENT_BUILD_ROOT",
        "reason": (
            "objdump -T echoes the inspected artifact's absolute path in the "
            "first line of its output, and p17_linkage_exclusion_v1 hashes that "
            "raw output, so inspection_digest is a function of the private build "
            "root. The gate re-derives this live: the built or_title_runtime_v1.so "
            "is byte-identical across build roots, the other five of the six "
            "linkage probes are byte-identical, all twelve probe returncodes and "
            "line counts match, and the digest recomputed with the echoed path "
            "prefix replaced by a fixed token is identical across roots. No "
            "linkage fact is carried by the varying component."
        ),
    },
    {
        "json_path": (
            'checks[].detail where check == "public:committed-evidence-clean" '
            '(member "file_count" only)'
        ),
        "class": "RUNNER_GENERATED_FILE_COUNT",
        "reason": (
            "The gate body scans its evidence directory before the stage runner "
            "writes official_runs.json and determinism.json into it, so a fresh "
            "run reports the gate-time count 9 while the committed record "
            "reports 11, which is exactly 9 plus those two documents. p17_04r_tests.json "
            "is written by run_stage after the body returns and is excluded from "
            "both counts, which is why the committed directory holds 12 files. "
            "All three documents are runner-generated records about the runs, "
            "not semantic proof inputs, and the gate re-derives this decomposition "
            "from the committed tree. The 'hits' member, which carries the "
            "actual public-safety verdict, remains compared strictly and is empty."
        ),
    },
)

# objdump/readelf/nm prefix a header line with the absolute path of the
# inspected artifact, then a colon, then the "file format ..." banner.  Only
# that header line is rewritten; every other line -- which carries the actual
# symbol, relocation or dynamic-section content -- is preserved verbatim, so a
# genuine change in the inspected binary still diverges.  The leaf is matched
# without requiring a file extension, because the runtime executable
# ``or_title_runtime_v1`` is extensionless and its header echoes the same way.
_ECHOED_PATH_PREFIX_RE = re.compile(
    r"^(?P<abs>/[^\s:]*(?::[^\s:]*)*)"
    r"(?P<rest>:[ \t]+file format[^\n]*)$",
    re.MULTILINE,
)

# Probe names whose output begins with an echoed absolute artifact path.
PATH_ECHOING_PROBES: tuple[str, ...] = ("objdump_dynamic_symbols",)


def normalize_probe_output(text: str) -> str:
    """Replace an echoed absolute artifact path with :data:`PATH_TOKEN`.

    Only the ``<path>`` prefix of a header line is rewritten.  The remainder of
    the line is preserved, so a different inspected binary, a different file
    format, or any change in the symbol/relocation content still produces a
    difference.
    """
    if not text:
        return text
    return _ECHOED_PATH_PREFIX_RE.sub(
        lambda match: f"{PATH_TOKEN}{match.group('rest')}", text
    )


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def root_invariant_linkage_digest(paths: Iterable[Any]) -> tuple[str, int]:
    """Recompute the linkage inspection digest with echoed paths normalised.

    Uses the identical construction as
    ``p17_linkage_exclusion_v1.linkage_exclusion_report`` -- the same probe
    order, the same ``artifact|surface|returncode|sha256(output)`` transcript
    and the same ``"\\n".join(sorted(...))`` final hash -- with the single
    difference that each probe's output is passed through
    :func:`normalize_probe_output` *before* being hashed.

    Because the normalisation is applied to the hashed text rather than to the
    finished digest, the result is provably independent of the private build
    root.  Returns ``(digest, transcript_part_count)``.
    """
    import pathlib

    import p17_linkage_exclusion_v1 as linkage

    parts: list[str] = []
    for raw_path in paths:
        path = pathlib.Path(raw_path)
        inspection = linkage.inspect_artifact(path)
        for surface, data in sorted(inspection["surfaces"].items()):
            normalized = (normalize_probe_output(data["output"])
                          if surface in PATH_ECHOING_PROBES else data["output"])
            parts.append(
                f"{inspection['artifact']}|{surface}|{data['returncode']}"
                f"|{_sha256_text(normalized)}"
            )
    return _sha256_text("\n".join(sorted(parts))), len(parts)


def normalized_json(document: Any) -> Any:
    """Return a comparison copy of ``document`` with proven path echoes removed.

    Applied to a whole document this only rewrites absolute ``*.so:`` header
    prefixes.  Semantic fields such as ``inspected_line_count``,
    ``forbidden_hit_count``, ``excluded`` and every proof marker are untouched
    and therefore still compared strictly.
    """
    if isinstance(document, str):
        return normalize_probe_output(document)
    if isinstance(document, list):
        return [normalized_json(item) for item in document]
    if isinstance(document, dict):
        return {key: normalized_json(value) for key, value in document.items()}
    return document


def classify_divergences(left: Any, right: Any, path: str = "") -> list[str]:
    """Return the exact JSON paths at which ``left`` and ``right`` differ.

    Comparison is strict: no field is skipped.  A path is reported only when
    its normalised form also differs, so a purely path-echoed difference does
    not appear as a divergence.
    """
    divergences: list[str] = []
    if isinstance(left, dict) and isinstance(right, dict):
        for key in sorted(set(left) | set(right)):
            child = f"{path}.{key}" if path else str(key)
            if key not in left or key not in right:
                divergences.append(child)
            else:
                divergences.extend(classify_divergences(left[key], right[key], child))
        return divergences
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            divergences.append(f"{path}[len:{len(left)}!={len(right)}]")
            return divergences
        for index, (a, b) in enumerate(zip(left, right)):
            divergences.extend(classify_divergences(a, b, f"{path}[{index}]"))
        return divergences
    if normalized_json(left) != normalized_json(right):
        divergences.append(path or "<root>")
    return divergences


def is_classified(divergent_path: str) -> str | None:
    """Return the classification class for a divergent path, or ``None``.

    A divergence is classified only if it is at (or under) one of the exact
    JSON paths named in :data:`CLASSIFIED_PATHS`.  Anything else returns
    ``None`` so the caller fails closed.
    """
    for entry in CLASSIFIED_PATHS:
        target = entry["json_path"]
        if divergent_path == target or divergent_path.startswith(target):
            return entry["class"]
    return None


def classify_artifact_divergence(committed: Any, generated: Any) -> dict[str, Any]:
    """Compare one artifact pair and classify the result.

    The returned ``unclassified`` list is non-empty for any difference not
    covered by :data:`CLASSIFIED_PATHS`; the caller must treat a non-empty
    ``unclassified`` as a hard failure.
    """
    raw = classify_divergences(committed, generated)
    classified: list[dict[str, str]] = []
    unclassified: list[str] = []
    for entry in raw:
        klass = is_classified(entry)
        if klass is None:
            unclassified.append(entry)
        else:
            classified.append({"json_path": entry, "class": klass})
    return {
        "raw_divergent_paths": raw,
        "classified": classified,
        "unclassified": sorted(unclassified),
        "equivalent_after_normalization": not unclassified,
    }


def file_count_expectation(committed_names: Sequence[str],
                           gate_time_names: Sequence[str]) -> dict[str, Any]:
    """Verify the runner-generated file-count difference exactly.

    The committed evidence directory must equal the gate-time directory plus
    precisely :data:`RUNNER_GENERATED_DOCUMENTS`, with no other addition and no
    other removal.  A missing or extra document is a hard failure.
    """
    committed = set(committed_names)
    gate_time = set(gate_time_names)
    added = sorted(committed - gate_time)
    removed = sorted(gate_time - committed)
    return {
        "gate_time_file_count": len(gate_time),
        "committed_file_count": len(committed),
        "added": added,
        "removed": removed,
        "expected_added": sorted(RUNNER_GENERATED_DOCUMENTS),
        "explained": (added == sorted(RUNNER_GENERATED_DOCUMENTS)
                      and not removed),
    }


def policy_document() -> dict[str, Any]:
    """The public, committed description of what this policy normalises."""
    return {
        "schema": POLICY_SCHEMA,
        "marker": MARKER,
        "path_token": PATH_TOKEN,
        "path_echoing_probes": list(PATH_ECHOING_PROBES),
        "runner_generated_documents": list(RUNNER_GENERATED_DOCUMENTS),
        "normalizes_only": [entry["json_path"] for entry in CLASSIFIED_PATHS],
        "classified_classes": sorted({entry["class"]
                                      for entry in CLASSIFIED_PATHS}),
        "rules": [
            {
                "json_path": entry["json_path"],
                "class": entry["class"],
                "reason": entry["reason"],
            }
            for entry in CLASSIFIED_PATHS
        ],
        "normalisation_timing": (
            "Linkage digests are normalised at hash time by "
            "root_invariant_linkage_digest, not by rewriting a finished digest. A "
            "post-hoc rewrite cannot repair an opaque hash; recomputing the "
            "identical construction over path-normalised probe output can, and "
            "the result is provably root-independent."
        ),
        "fail_closed": (
            "Any divergent JSON path not named above is reported as unclassified "
            "and fails the stage. Comparison of every other field, including "
            "inspected_line_count, forbidden_hit_count, excluded, artifact "
            "digests, record counts and all proof markers, remains strict."
        ),
    }
