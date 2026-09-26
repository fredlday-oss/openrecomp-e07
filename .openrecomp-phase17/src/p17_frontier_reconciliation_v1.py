#!/usr/bin/env python3
"""P17-03 authenticated reconciliation of historical Phase-16 addresses."""
from __future__ import annotations

import hashlib
import json
import pathlib
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
TITLE_DECODE = ROOT / ".openrecomp-phase17/evidence/P17-02/title_decode.json"
P16_REPLAY = ROOT / ".openrecomp-phase16/evidence/P16-07/title_replay.json"
P16_TRANSITION = ROOT / ".openrecomp-phase16/evidence/P16-06/title_exec_transition.json"

TARGETS = ("0x8004ff54", "0x80050110")
CLASSES = {
    "AUTHENTIC_BYTES_REACHABLE",
    "AUTHENTIC_BYTES_PRESENT_NOT_REACHABLE",
    "OUTSIDE_TITLE_IMAGE",
    "MODELLED_CONSTANT",
    "UNRESOLVED",
}


def digest_projection(doc: dict[str, Any]) -> str:
    body = {k: v for k, v in doc.items() if k != "projection_digest"}
    # Match the authenticated P17-02 projection digest algorithm exactly.
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()


def load_json(path: pathlib.Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"missing evidence: {path.name}")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"malformed evidence: {path.name}") from exc
    if not isinstance(doc, dict):
        raise ValueError(f"evidence is not an object: {path.name}")
    return doc


def validate_projection(title: dict[str, Any]) -> None:
    expected_digest = title.get("projection_digest")
    if not isinstance(expected_digest, str) or digest_projection(title) != expected_digest:
        raise ValueError("P17-02 projection digest mismatch")
    if title.get("schema") != "openrecomp-phase17-title-decode-v1":
        raise ValueError("unexpected P17-02 schema")
    modelled = title.get("modelled_addresses")
    if not isinstance(modelled, dict):
        raise ValueError("missing modelled address projection")
    if any(not isinstance(modelled.get(address), dict) for address in TARGETS):
        raise ValueError("missing modelled target")


def reconcile() -> dict[str, Any]:
    title = load_json(TITLE_DECODE)
    validate_projection(title)
    expected_digest = title["projection_digest"]
    modelled = title.get("modelled_addresses")
    if not isinstance(modelled, dict):
        raise ValueError("missing modelled address projection")

    prior: dict[str, Any] = {}
    for path in (P16_REPLAY, P16_TRANSITION):
        doc = load_json(path)
        sections = [doc]
        for key in ("title_replay", "transition_proof"):
            value = doc.get(key)
            if isinstance(value, dict):
                sections.append(value)
        for section in sections:
            for key in ("title_main_target", "title_frontier_pc"):
                if key in section:
                    prior[key] = section[key]

    addresses: dict[str, Any] = {}
    for address in TARGETS:
        record = modelled.get(address)
        if not isinstance(record, dict):
            raise ValueError(f"missing modelled record: {address}")
        if record.get("in_authenticated_text") and record.get("decoded") and record.get("reachable"):
            classification = "AUTHENTIC_BYTES_REACHABLE"
        elif record.get("in_authenticated_text") and record.get("decoded"):
            classification = "AUTHENTIC_BYTES_PRESENT_NOT_REACHABLE"
        elif record.get("in_authenticated_text") is False:
            classification = "OUTSIDE_TITLE_IMAGE"
        else:
            classification = "UNRESOLVED"
        if classification not in CLASSES:
            raise ValueError(f"invalid classification: {address}")
        addresses[address] = {
            "address": address,
            "classification": classification,
            "authenticated_text": bool(record.get("in_authenticated_text")),
            "decoded": bool(record.get("decoded")),
            "reachable": bool(record.get("reachable")),
            "decode_class": record.get("decode_class"),
            "op": record.get("op"),
            "block_start": record.get("block_start"),
            "phase16_modelled": address in ("0x8004ff54", "0x80050110"),
        }
    result = {
        "schema": "openrecomp-phase17-frontier-reconciliation-v1",
        "stage": "P17-03",
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "source": {
            "p17_02_projection_digest": expected_digest,
            "p17_02_schema": title["schema"],
            "phase16_evidence": ["P16-06/title_exec_transition.json", "P16-07/title_replay.json"],
            "phase16_note": "Historical Phase-16 evidence is read-only and unchanged.",
        },
        "historical_phase16_values": prior,
        "addresses": addresses,
        "classification_set": sorted(CLASSES),
        "claims": {
            "authentic_title_entry": "0x800380a0",
            "initialization": "NOT_PROVEN",
            "frame": "NOT_PROVEN",
            "playability": "NOT_PROVEN",
            "general_compatibility": "NOT_PROVEN",
            "first_frame_ready": "NO",
        },
    }
    result["projection_digest"] = digest_projection(result)
    return result
