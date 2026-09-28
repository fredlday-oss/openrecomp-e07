#!/usr/bin/env python3
"""OpenRecomp Phase-18 P18-07 first-frame assessment.

This is an assessment and gatekeeping stage. It fabricates no traffic, injects
no command stream, mutates no VRAM and renders no image. It consumes the
committed P18-02..P18-06 evidence read-only, evaluates an ordered causal-link
chain, and promotes only the exact property that the evidence mechanically
proves.

Because P18-04 (GP0/GP1), P18-05 (DMA / ordering table) and P18-06
(VRAM / display) each established their frontier as UNREACHED, the honest
primary outcome is:

    FIRST_FRAME_READY=NO
    OPENRECOMP_PHASE18_HERCULES_FRAME_PROOF=NOT_PROVEN

Anti-vacuity: an assessment that can only ever answer NO proves nothing, so the
promotion logic is shown to be capable of promoting - a fully satisfied link
vector yields YES *inside the control namespace only*, and the authentic verdict
can never be influenced by that control.

No title-specific constant, no injected traffic, no raw payload bytes and no
private absolute paths enter the evidence.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]

SCHEMA = "openrecomp-phase18-first-frame-assessment-v1"
LEDGER_SCHEMA = "openrecomp-phase18-causal-link-ledger-v1"
CONTROLS_SCHEMA = "openrecomp-phase18-promotion-controls-v1"

FIRST_FRAME_READY_MARKER = "FIRST_FRAME_READY"

#: Evidence classes that may never establish a link (control/probe/synthetic).
NON_AUTHENTIC_EVIDENCE_CLASSES = frozenset({
    "CONTROL", "PROBE", "SYNTHETIC", "CONTROL_DERIVED", "PROBE_DERIVED",
})

ESTABLISHED = "ESTABLISHED"
UNREACHED = "UNREACHED"
NOT_PROVEN = "NOT_PROVEN"
ALLOWED_VERDICTS = frozenset({ESTABLISHED, UNREACHED, NOT_PROVEN})

#: The ordered causal-link chain.  A link is ESTABLISHED only on authentic,
#: deterministic evidence; control-derived evidence may prove a model is
#: genuine but can never establish a link.
LINKS: tuple[tuple[str, str, str], ...] = (
    ("L1", "authenticated execution",
     "P18-02 continuation + P18-03 causal transcript, per-PC provenance"),
    ("L2", "authentic GPU command operations (GP0/GP1)",
     "P18-04 frontier gp0_write_count / gp1_write_count"),
    ("L3", "authentic GPU DMA / ordering-table operations",
     "P18-05 frontier dma_access_count"),
    ("L4", "deterministic GPU state (decoded command semantics)",
     "P18-04 command decode, bounded and provenance-bound"),
    ("L5", "deterministic VRAM effects",
     "P18-06 vram_display_status, mutation digest"),
    ("L6", "valid display configuration",
     "P18-06 display-state evidence (display enable / start / mode writes)"),
    ("L7", "coherent displayable framebuffer",
     "P18-06 framebuffer descriptor + digest"),
)

LINK_IDS = tuple(link[0] for link in LINKS)

#: Frozen digests of the frontier documents this stage hash-verifies, as
#: declared by the P18-07 contract (the P18-04 digest is the repaired one).
EXPECTED_FRONTIER_DIGESTS: dict[str, str] = {
    "P18-04/gpu_command_frontier.json":
        "a009003b644122a011a4a53a9ceeae1d2e4a560a462fc28ef2c3ac9dd4b2bfe9",
    "P18-05/dma_frontier.json":
        "f0251b43b8d60ac8c101df71d59cd28441615e1ab58c7036dce98933450fa5c1",
    "P18-06/vram_display.json":
        "2848c231c0351638485931e8dfd064abf7ba990d7a9fab178c3730d94e084e5e",
}

#: Documents read (all must be present, parseable and public-safe).
EVIDENCE_FILES: tuple[tuple[str, str], ...] = (
    ("p18_02_result", "P18-02/RESULT.json"),
    ("p18_02_continuation", "P18-02/continuation.json"),
    ("p18_03_result", "P18-03/RESULT.json"),
    ("gpu_frontier", "P18-04/gpu_command_frontier.json"),
    ("gpu_decode", "P18-04/command_decode.json"),
    ("dma_frontier", "P18-05/dma_frontier.json"),
    ("ot_model", "P18-05/ordering_table_model.json"),
    ("vram", "P18-06/vram_display.json"),
    ("vram_verdict", "P18-06/vram_verdict.json"),
    ("display", "P18-06/display_state.json"),
)


class FirstFrameAssessmentError(ValueError):
    """Fail-closed assessment error carrying a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return _sha256_bytes(data)


def hex32(value: int) -> str:
    return f"0x{value:08x}"


def evidence_root(root: pathlib.Path | None = None) -> pathlib.Path:
    base = pathlib.Path(root) if root is not None else ROOT
    return base / ".openrecomp-phase18" / "evidence"


def read_document(path: pathlib.Path) -> tuple[bytes, dict[str, Any], str]:
    """Read a JSON document fail-closed.

    Missing -> FRONTIER_EVIDENCE_MISSING; unparsable -> FRONTIER_EVIDENCE_UNPARSABLE.
    """
    if not path.is_file():
        raise FirstFrameAssessmentError("FRONTIER_EVIDENCE_MISSING", str(path.name))
    data = path.read_bytes()
    digest = _sha256_bytes(data)
    try:
        document = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FirstFrameAssessmentError("FRONTIER_EVIDENCE_UNPARSABLE",
                                        f"{path.name}: {exc}") from exc
    if not isinstance(document, dict):
        raise FirstFrameAssessmentError("FRONTIER_EVIDENCE_UNPARSABLE",
                                        f"{path.name}: not an object")
    return data, document, digest


def load_evidence(root: pathlib.Path | None = None,
                  *, verify_digests: bool = True) -> dict[str, Any]:
    """Load every consumed document and hash-verify the frozen frontiers."""
    base = evidence_root(root)
    loaded: dict[str, Any] = {"_root": base}
    for key, relative in EVIDENCE_FILES:
        path = base / relative
        data, document, digest = read_document(path)
        loaded[key] = document
        loaded[key + "_sha256"] = digest
        loaded[key + "_path"] = relative
        expected = EXPECTED_FRONTIER_DIGESTS.get(relative)
        if verify_digests and expected is not None and digest != expected:
            raise FirstFrameAssessmentError(
                "FRONTIER_DIGEST_MISMATCH", f"{relative}: {digest} != {expected}")
    return loaded


def _citation(source: str, field: str, value: Any,
              evidence_class: str = "AUTHENTIC") -> dict[str, Any]:
    return {"source": source, "field": field, "value": value,
            "evidence_class": evidence_class}


def _continuation_metrics(evidence: dict[str, Any]) -> dict[str, Any]:
    result = evidence["p18_02_result"]
    cont = result.get("continuation", {})
    return {
        "status": result.get("status"),
        "executed_instruction_count": cont.get("executed_instruction_count", 0),
        "distinct_executed_pc_count": cont.get("distinct_executed_pc_count", 0),
        "stop_reason": cont.get("stop_reason"),
    }


def evaluate_links(evidence: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Evaluate the ordered link chain from authentic evidence."""
    cont = _continuation_metrics(evidence)
    p18_03 = evidence["p18_03_result"]
    causal = p18_03.get("causal_transcript", {})
    gpu = evidence["gpu_frontier"]
    decode = evidence["gpu_decode"]
    dma = evidence["dma_frontier"]
    ot = evidence["ot_model"]
    vram = evidence["vram"]
    display = evidence["display"]

    dma_events = ot.get("dma_access_events", [])
    authentic_display_events = display.get("authentic_display_events", [])
    vram_events = vram.get("events", [])
    vram_mutations = [e for e in vram_events
                      if str(e.get("mutation", "")).startswith(("FILL", "CPU_TO_VRAM",
                                                                "VRAM_TO_VRAM"))]

    ledger: dict[str, dict[str, Any]] = {}

    # L1 - authenticated execution.
    l1 = (cont["status"] == "PASS" and p18_03.get("status") == "PASS"
          and cont["executed_instruction_count"] >= 1
          and cont["distinct_executed_pc_count"] >= 1
          and bool(cont["stop_reason"])
          and int(causal.get("event_count", 0)) >= 1)
    ledger["L1"] = {
        "id": "L1", "link": LINKS[0][1], "requirement": LINKS[0][2],
        "verdict": ESTABLISHED if l1 else NOT_PROVEN,
        "evidence": [
            _citation("P18-02/RESULT.json", "continuation.executed_instruction_count",
                      cont["executed_instruction_count"]),
            _citation("P18-02/RESULT.json", "continuation.stop_reason",
                      cont["stop_reason"]),
            _citation("P18-03/RESULT.json", "causal_transcript.event_count",
                      causal.get("event_count")),
        ]}

    # L2 - authentic GP0/GP1 command operations.
    l2 = bool(gpu.get("frontier_reached")) and gpu.get("gp0_write_count", 0) >= 1 \
        and gpu.get("gp1_write_count", 0) >= 1
    ledger["L2"] = {
        "id": "L2", "link": LINKS[1][1], "requirement": LINKS[1][2],
        "verdict": ESTABLISHED if l2 else UNREACHED,
        "evidence": [
            _citation("P18-04/gpu_command_frontier.json", "gp0_write_count",
                      gpu.get("gp0_write_count")),
            _citation("P18-04/gpu_command_frontier.json", "gp1_write_count",
                      gpu.get("gp1_write_count")),
            _citation("P18-04/gpu_command_frontier.json", "frontier_reached",
                      bool(gpu.get("frontier_reached"))),
        ]}

    # L3 - authentic GPU DMA / ordering-table operations.
    l3 = bool(dma.get("dma_reached")) and dma.get("dma_access_count", 0) >= 1
    ledger["L3"] = {
        "id": "L3", "link": LINKS[2][1], "requirement": LINKS[2][2],
        "verdict": ESTABLISHED if l3 else UNREACHED,
        "evidence": [
            _citation("P18-05/dma_frontier.json", "dma_access_count",
                      dma.get("dma_access_count")),
            _citation("P18-05/dma_frontier.json", "dma_reached",
                      bool(dma.get("dma_reached"))),
            _citation("P18-05/ordering_table_model.json", "dma_access_events",
                      len(dma_events)),
        ]}

    # L4 - deterministic decoded command semantics on the authentic path.
    decode_events = decode.get("events", [])
    l4 = (int(decode.get("event_count", 0)) >= 1 and len(decode_events) >= 1
          and decode.get("unsupported_command_count", 0) == 0
          and all(e.get("class") not in (None, "UNKNOWN") for e in decode_events))
    ledger["L4"] = {
        "id": "L4", "link": LINKS[3][1], "requirement": LINKS[3][2],
        "verdict": ESTABLISHED if l4 else NOT_PROVEN,
        "evidence": [
            _citation("P18-04/command_decode.json", "event_count",
                      decode.get("event_count")),
            _citation("P18-04/command_decode.json", "command_classes",
                      decode.get("command_classes")),
            _citation("P18-04/command_decode.json", "unsupported_command_count",
                      decode.get("unsupported_command_count")),
        ]}

    # L5 - deterministic VRAM effects on the authentic path.
    l5 = bool(vram.get("vram_frontier_reached")) and len(vram_mutations) >= 1
    ledger["L5"] = {
        "id": "L5", "link": LINKS[4][1], "requirement": LINKS[4][2],
        "verdict": ESTABLISHED if l5 else UNREACHED,
        "evidence": [
            _citation("P18-06/vram_display.json", "vram_frontier_reached",
                      bool(vram.get("vram_frontier_reached"))),
            _citation("P18-06/vram_display.json", "vram_display_status",
                      vram.get("vram_display_status")),
            _citation("P18-06/vram_display.json", "authentic_mutation_count",
                      len(vram_mutations)),
        ]}

    # L6 - valid display configuration written by authentic execution.
    l6 = len(authentic_display_events) >= 1
    ledger["L6"] = {
        "id": "L6", "link": LINKS[5][1], "requirement": LINKS[5][2],
        "verdict": ESTABLISHED if l6 else UNREACHED,
        "evidence": [
            _citation("P18-06/display_state.json", "authentic_display_events",
                      len(authentic_display_events)),
            _citation("P18-06/vram_verdict.json", "vram_display_status",
                      evidence["vram_verdict"].get("vram_display_status")),
        ]}

    # L7 - coherent displayable framebuffer bound to authentic execution.
    authentic_framebuffer = display.get("authentic_framebuffer", {})
    l7 = (bool(authentic_framebuffer)
          and bool(authentic_framebuffer.get("digest"))
          and authentic_framebuffer.get("evidence_class") not in
          NON_AUTHENTIC_EVIDENCE_CLASSES)
    ledger["L7"] = {
        "id": "L7", "link": LINKS[6][1], "requirement": LINKS[6][2],
        "verdict": ESTABLISHED if l7 else NOT_PROVEN,
        "evidence": [
            _citation("P18-06/display_state.json", "authentic_framebuffer",
                      authentic_framebuffer or None),
            _citation("P18-06/vram_display.json", "first_frame_ready",
                      vram.get("first_frame_ready")),
        ]}

    return ledger


def promotion_from_verdicts(verdicts: dict[str, str]) -> str:
    """FIRST_FRAME_READY is YES iff every link is ESTABLISHED."""
    if set(verdicts) != set(LINK_IDS):
        raise FirstFrameAssessmentError("PROMOTION_CHAIN_INCOMPLETE",
                                        "verdict vector does not cover all links")
    return "YES" if all(verdicts[link] == ESTABLISHED for link in LINK_IDS) else "NO"


def promotion_controls(authentic_ledger: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Anti-vacuity and anti-inflation controls, in the control namespace only."""
    authentic = {link: authentic_ledger[link]["verdict"] for link in LINK_IDS}

    all_satisfied = {link: ESTABLISHED for link in LINK_IDS}
    anti_vacuity = {
        "vector": "all-links-satisfied",
        "verdicts": all_satisfied,
        "first_frame_ready": promotion_from_verdicts(all_satisfied),
    }

    def single(milestone: str, link: str) -> dict[str, Any]:
        vector = dict(authentic)
        vector["L1"] = ESTABLISHED
        vector[link] = ESTABLISHED
        return {"vector": milestone, "established_link": link,
                "first_frame_ready": promotion_from_verdicts(vector)}

    anti_inflation = [
        single("first-gp0-write", "L2"),
        single("first-gpu-dma", "L3"),
        single("first-ordering-table-packet", "L3"),
        single("first-primitive", "L4"),
        single("first-vram-mutation", "L5"),
        single("first-display-register-setup", "L6"),
    ]
    return {
        "schema": CONTROLS_SCHEMA,
        "anti_vacuity": anti_vacuity,
        "anti_inflation": anti_inflation,
        "control_namespace_isolated": True,
        "promotes_no_proof_marker": True,
    }


def build_assessment(evidence: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Build the assessment ledger and its deterministic digest."""
    ledger = evaluate_links(evidence)
    authentic_verdicts = {link: ledger[link]["verdict"] for link in LINK_IDS}
    authentic_ready = promotion_from_verdicts(authentic_verdicts)
    controls = promotion_controls(ledger)

    document = {
        "schema": SCHEMA,
        "stage": "P18-07",
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "ledger": {
            "schema": LEDGER_SCHEMA,
            "order": list(LINK_IDS),
            "links": [ledger[link] for link in LINK_IDS],
            "authentic_first_frame_ready": authentic_ready,
        },
        "promotion_controls": controls,
        "first_frame_ready": authentic_ready,
        "first_frame_rule": "YES iff all of L1..L7 are ESTABLISHED",
        "frontier_digests": {
            relative: evidence[_key_for(relative) + "_sha256"]
            for relative in EXPECTED_FRONTIER_DIGESTS
        },
        "promotes_no_proof_marker": authentic_ready == "NO",
    }
    data = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")
    return document, _sha256_bytes(data)


def _key_for(relative: str) -> str:
    for key, rel in EVIDENCE_FILES:
        if rel == relative:
            return key
    raise FirstFrameAssessmentError("FRONTIER_EVIDENCE_MISSING", relative)


def validate_assessment(document: dict[str, Any]) -> None:
    """Fail-closed validation of an assessment document."""
    if document.get("schema") != SCHEMA:
        raise FirstFrameAssessmentError("ASSESSMENT_SCHEMA", str(document.get("schema")))

    ledger = document.get("ledger", {})
    links = ledger.get("links", [])
    if [link.get("id") for link in links] != list(LINK_IDS):
        raise FirstFrameAssessmentError("PROMOTION_CHAIN_INCOMPLETE",
                                        "ledger does not cover L1..L7 in order")

    for link in links:
        verdict = link.get("verdict")
        if verdict not in ALLOWED_VERDICTS:
            raise FirstFrameAssessmentError("LINK_VERDICT_INVALID",
                                            f"{link.get('id')}: {verdict}")
        citations = link.get("evidence", [])
        if not citations:
            raise FirstFrameAssessmentError("LINK_PROVENANCE_MISSING", link.get("id"))
        if verdict == ESTABLISHED:
            authentic = [c for c in citations
                         if c.get("evidence_class") not in NON_AUTHENTIC_EVIDENCE_CLASSES]
            if not authentic:
                raise FirstFrameAssessmentError(
                    "LINK_CONTROL_DERIVED_EVIDENCE_REJECTED", link.get("id"))

    authentic_verdicts = {link["id"]: link["verdict"] for link in links}
    expected_ready = promotion_from_verdicts(authentic_verdicts)
    if document.get("first_frame_ready") != expected_ready:
        raise FirstFrameAssessmentError("CONTROL_VERDICT_CONTAMINATION",
                                        "authentic verdict disagrees with ledger")
    if ledger.get("authentic_first_frame_ready") != expected_ready:
        raise FirstFrameAssessmentError("CONTROL_VERDICT_CONTAMINATION",
                                        "ledger verdict field disagrees")

    controls = document.get("promotion_controls", {})
    if not controls.get("control_namespace_isolated"):
        raise FirstFrameAssessmentError("CONTROL_VERDICT_CONTAMINATION",
                                        "control namespace not isolated")
    if controls.get("anti_vacuity", {}).get("first_frame_ready") != "YES":
        raise FirstFrameAssessmentError("ANTI_VACUITY_FAILED",
                                        "all-satisfied control did not promote")
    for vector in controls.get("anti_inflation", []):
        if vector.get("first_frame_ready") != "NO":
            raise FirstFrameAssessmentError("ANTI_INFLATION_FAILED",
                                            vector.get("vector", ""))


def assessment_bytes(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


if __name__ == "__main__":
    raise SystemExit(0)
