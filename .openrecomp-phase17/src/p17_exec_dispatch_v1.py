#!/usr/bin/env python3
"""P17-05 authenticated A0:0x43 Exec dispatch causality."""
from __future__ import annotations
import hashlib
import json
import pathlib
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
EMISSION = ROOT / ".openrecomp-phase17/evidence/P17-04/title_emission.json"
P16 = ROOT / ".openrecomp-phase16/evidence/P16-06/title_exec_transition.json"
ENTRY = "0x800380a0"

def digest(doc: dict[str, Any]) -> str:
    body = {k:v for k,v in doc.items() if k != "emission_digest"}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()

def load(path):
    try: d=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError) as e: raise ValueError("evidence unavailable") from e
    if not isinstance(d,dict): raise ValueError("evidence object required")
    return d

def verify_emission(doc):
    if doc.get("schema") != "openrecomp-phase17-title-emission-v1": raise ValueError("emission schema")
    if doc.get("emission_digest") != digest(doc): raise ValueError("emission digest")
    if doc.get("source",{}).get("entry_pc") != ENTRY: raise ValueError("emission entry")
    if doc.get("active_build",{}).get("phase16_hand_authored_title_guest_flow") != "EXCLUDED": raise ValueError("hand-authored flow active")
    if not doc.get("emitted_blocks"): raise ValueError("no emitted blocks")
    if not any(b.get("emitted_block") == doc.get("entry_block") for b in doc["emitted_blocks"]): raise ValueError("entry block missing")

def dispatch():
    emission=load(EMISSION); verify_emission(emission)
    old=load(P16).get("transition_proof",{})
    required={"exec_payload_verified":1,"transition_dispatched":1,"transition_target":ENTRY,"exec_pc0":ENTRY,"title_entry_called":1}
    if any(old.get(k)!=v for k,v in required.items()): raise ValueError("frozen Exec causality mismatch")
    return {"schema":"openrecomp-phase17-exec-dispatch-causality-v1","stage":"P17-05","evidence_class":"PRIVATE_FIXTURE_BOUNDED","source":{"emission_digest":emission["emission_digest"],"p16_transition_schema":"openrecomp-phase16-title-exec-transition-v1"},"exec_contract":{"service":"A0:0x43","verified":True,"dispatch_target":ENTRY,"emitted_entry":ENTRY,"transition_target":old["transition_target"],"title_entry_called":old["title_entry_called"]},"causality":["verified_exec_payload","authenticated_emission","emitted_entry_0x800380a0","dispatch_target_0x800380a0","phase16_transition_target_0x800380a0"],"ablation":{"emission_present":True,"without_emission":"DISPATCH_REJECTED_AUTHENTIC_TITLE_EXECUTION_ABSENT"},"claims":{"execution":"DEFERRED_TO_P17_06","initialization":"NOT_PROVEN","frame":"NOT_PROVEN","playability":"NOT_PROVEN","general_compatibility":"NOT_PROVEN","first_frame_ready":"NO"}}
