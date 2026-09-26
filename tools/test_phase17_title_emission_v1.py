#!/usr/bin/env python3
"""Deterministic P17-04 authentic TITLE emission gate."""
from __future__ import annotations
import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".openrecomp-phase17/src"))
from p17_gate_v1 import assert_public_safe, run_stage, write_json
import p17_title_emit_v1 as emitter

STAGE = "P17-04"

def body(gate, evidence, root):
    projection = emitter.load_projection()
    manifest = emitter.emit_projection(projection)
    gate.check("positive:authenticated-input-digest", manifest["source"]["p17_02_projection_digest"] == projection["projection_digest"])
    gate.check("positive:entry-emitted", manifest["entry_block"].startswith("title_block_"))
    gate.check("positive:all-blocks-emitted", manifest["block_count"] == projection["basic_blocks"]["count"])
    gate.check("positive:source-provenance-bijection", all(b["source_provenance_count"] == b["instruction_count"] for b in manifest["emitted_blocks"]))
    gate.check("positive:phase16-hand-authored-flow-excluded", manifest["active_build"]["phase16_hand_authored_title_guest_flow"] == "EXCLUDED")
    gate.check("positive:execution-deferred", manifest["active_build"]["execution"] == "DEFERRED_TO_P17_05_AND_P17_06")
    public = json.dumps(manifest, sort_keys=True)
    for forbidden in ("raw_instruction", "instruction_word", "payload_bytes", "bios_bytes"):
        gate.check(f"negative:no-{forbidden}", forbidden not in public)
    gate.check("negative:no-private-paths", "/home/" not in public and "fixtures/" not in public)
    c_source = emitter.c_inventory(manifest)
    gate.check("positive:deterministic-c-inventory", c_source == emitter.c_inventory(manifest))
    gate.check("negative:c-inventory-no-raw-words", "0x" in c_source and "payload" not in c_source.lower())
    with tempfile.TemporaryDirectory() as tmp:
        altered = json.loads(json.dumps(projection))
        altered["projection_digest"] = "0" * 64
        try:
            emitter.emit_projection(emitter.load_projection(pathlib.Path(tmp) / "missing.json"))
        except emitter.TitleEmissionError:
            absent_rejected = True
        else:
            absent_rejected = False
        gate.check("negative:absent-projection-rejected", absent_rejected)
        altered_path = pathlib.Path(tmp) / "tampered.json"
        altered_path.write_text(json.dumps(altered), encoding="utf-8")
        try:
            emitter.load_projection(altered_path)
        except emitter.TitleEmissionError:
            digest_rejected = True
        else:
            digest_rejected = False
        gate.check("negative:digest-mismatch-rejected", digest_rejected)
        malformed = pathlib.Path(tmp) / "malformed.json"
        malformed.write_text("{}", encoding="utf-8")
        try:
            emitter.load_projection(malformed)
        except emitter.TitleEmissionError:
            malformed_rejected = True
        else:
            malformed_rejected = False
        gate.check("negative:malformed-projection-rejected", malformed_rejected)
    assert_public_safe(gate, "title-emission", manifest)
    write_json(evidence / "title_emission.json", manifest)
    write_json(evidence / "emitted_inventory.c.json", {"source": "authenticated-block-records", "sha256": __import__("hashlib").sha256(c_source.encode()).hexdigest(), "block_count": manifest["block_count"]})
    gate.mark("OPENRECOMP_PHASE17_AUTHENTIC_TITLE_EMISSION_V1", "PASS")
    gate.mark("OPENRECOMP_P17_04", "PASS")
    gate.mark("OPENRECOMP_PHASE17_HERCULES_INITIALIZATION_PROOF", "NOT_PROVEN")
    gate.mark("OPENRECOMP_PHASE17_HERCULES_FRAME_PROOF", "NOT_PROVEN")
    gate.mark("OPENRECOMP_PHASE17_HERCULES_PLAYABILITY_PROOF", "NOT_PROVEN")
    gate.mark("OPENRECOMP_PHASE17_GENERAL_PS1_COMPATIBILITY", "NOT_PROVEN")
    gate.mark("FIRST_FRAME_READY", "NO")
    write_json(evidence / "RESULT.json", {"schema":"openrecomp-phase17-result-v1","stage":STAGE,"status":"PASS","evidence_class":"PRIVATE_FIXTURE_BOUNDED","markers":{"OPENRECOMP_PHASE17_AUTHENTIC_TITLE_EMISSION_V1":"PASS","OPENRECOMP_P17_04":"PASS","OPENRECOMP_PHASE17_HERCULES_INITIALIZATION_PROOF":"NOT_PROVEN","OPENRECOMP_PHASE17_HERCULES_FRAME_PROOF":"NOT_PROVEN","OPENRECOMP_PHASE17_HERCULES_PLAYABILITY_PROOF":"NOT_PROVEN","OPENRECOMP_PHASE17_GENERAL_PS1_COMPATIBILITY":"NOT_PROVEN","FIRST_FRAME_READY":"NO"},"next_stage":"P17-05"})

if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase17/evidence/P17-04"))
