#!/usr/bin/env python3
"""Deterministic P17-06R live BIOS/Exec + device side-effect frontier gate.

Advances real authenticated guest execution beyond the recorded P17-05R
frontier, authenticates every newly reached region from the read-only private
source bytes with the frozen decoder and canonical checked-equality discipline,
captures a deterministic provenance-complete BIOS/device transcript produced by
that execution, and fails closed on every unauthenticated or unproven step.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase17/src", ".openrecomp-phase3/src",
              ".openrecomp-phase9/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p17_contracts_v1 as contract
import p17_device_transcript_v1 as transcript_model
import p17_fixture_verification_v1 as fixture
import p17_mainexe_auth_v1 as mainexe
import p17_psx_exe_identity_v1 as p17_psx
import p17_side_effects_exec_v1 as side
import p17_title_decode_v1 as title_decode
import p17_title_exec_continuation_v1 as cont
import p17_title_exec_emit_v1 as emitter
from p17_gate_v1 import Gate, assert_public_safe, run_stage, write_json

STAGE = "P17-06R"
NEXT_STAGE = "P17-07R"
BASE_COMMIT = "8735bf34ba3884d19a66818d92ddd8004dc87b17"
WORKER_BRANCH = "agent/deepseek-phase17-p17-06r-r1"

#: Stage-owned evidence documents scanned for public safety.  Runner-owned files
#: (official_runs.json / determinism.json) and the regenerated tests document are
#: excluded so the scan is stable across repeated official invocations.
PUBLIC_SCAN_FILES = ("RESULT.json", "continuation.json", "transcript.json",
                     "next_stage.json", "stage_metadata.json")


def fixture_root() -> pathlib.Path:
    env = os.environ.get("OPENRECOMP_HERCULES_FIXTURE_ROOT")
    if env:
        return pathlib.Path(env)
    return ROOT.parents[1] / "fixtures" / "psx" / "hercules"


def _hex32(value: int) -> str:
    return f"0x{value & 0xFFFFFFFF:08x}"


_ANALYSIS_CACHE: dict[str, Any] = {}


def _load_live_title_analysis() -> Any:
    if "title" not in _ANALYSIS_CACHE:
        fx = fixture_root()
        fixture.verify_fixture_with_callback(fx, lambda label, condition, detail="": None)
        _ANALYSIS_CACHE["title"] = title_decode.analyze_title_decode(fixture_dir=fx)
    return _ANALYSIS_CACHE["title"]


def _raises(fn, exc_type=Exception, code: str | tuple[str, ...] | None = None) -> bool:
    try:
        fn()
        return False
    except exc_type as exc:
        if code is None:
            return True
        allowed = (code,) if isinstance(code, str) else code
        return getattr(exc, "code", None) in allowed


# --- Negative controls (fail closed) ---------------------------------------


def negative_unauthenticated_destination(analysis: side.SideEffectsAnalysis) -> dict[str, Any]:
    """An address outside every authenticated source fails closed."""
    results: dict[str, Any] = {
        "outside_text_rejected": _raises(
            lambda: analysis.authenticate_and_extend(0x80030000),
            side.SideEffectsError, "CONTINUATION_ENTRY_OUTSIDE_AUTHENTICATED_TEXT"),
        "unaligned_rejected": _raises(
            lambda: analysis.authenticate_and_extend(0x80026cca),
            side.SideEffectsError, "CONTINUATION_ENTRY_UNALIGNED"),
        "below_ram_rejected": _raises(
            lambda: analysis.authenticate_and_extend(0x00000040),
            side.SideEffectsError, "CONTINUATION_ENTRY_OUTSIDE_AUTHENTICATED_TEXT"),
        "resolver_out_of_range": _raises(
            lambda: analysis.read_authenticated_word(0x80100000),
            cont.ContinuationError, "PC_OUTSIDE_AUTHENTICATED_SOURCES"),
    }
    results["ok"] = all(value for key, value in results.items() if key != "ok")
    return results


def negative_altered_source_word() -> dict[str, Any]:
    """A record whose source word disagrees with a fresh decode fails closed."""
    entry = side._parse_hex(side.recorded_p17_05r_frontier()["attempted_frontier_pc"])
    ident, data = mainexe.load_mainexe_identity()
    base = mainexe.build_mainexe_analysis(entry, identity=ident, file_bytes=data)
    pc = sorted(base.provenance)[0]
    offset = mainexe.HEADER_SIZE + (pc - ident.t_addr)
    tampered = bytearray(data)
    tampered[offset:offset + 4] = struct.pack("<I", 0x24010007)
    tampered_identity = p17_psx.ingest_bytes(bytes(tampered))
    tampered_analysis = mainexe.build_mainexe_analysis(
        entry, identity=tampered_identity, file_bytes=bytes(tampered))
    reference = mainexe.build_mainexe_analysis(entry, identity=ident, file_bytes=data)
    semantic = _semantic_record(reference, pc)
    results = {
        "altered_word_rejected": _raises(
            lambda: emitter._verify_record_against_fresh_decode(semantic, tampered_analysis),
            emitter.TitleExecEmitError, ("OPCODE_MISMATCH", "OPERAND_MISMATCH")),
        "unaltered_word_accepted": not _raises(
            lambda: emitter._verify_record_against_fresh_decode(semantic, reference)),
    }
    results["ok"] = all(value for key, value in results.items() if key != "ok")
    return results


def _semantic_record(analysis: Any, pc: int) -> emitter.SemanticRecord:
    raw = analysis.records_by_address[pc]
    operands = raw.get("operands") or {}
    delay = analysis.delay_by_owner.get(pc)
    prov = analysis.provenance[pc]
    return emitter.SemanticRecord(
        pc=pc,
        op=raw["op"],
        rs=int(operands.get("rs", 0)) & 0x1F,
        rt=int(operands.get("rt", 0)) & 0x1F,
        rd=int(operands.get("rd", 0)) & 0x1F,
        shamt=int(operands.get("shamt", 0)) & 0x1F,
        imm=emitter._sign16(int(operands.get("imm", 0)) & 0xFFFF),
        target=(int(operands["target"]) & 0xFFFFFFFF)
        if operands.get("target") is not None else None,
        delay_slot=(delay & 0xFFFFFFFF) if delay is not None else None,
        control_flow=bool(raw.get("control_flow")),
        terminator=raw.get("terminator"),
        link=bool(raw.get("link")),
        provenance_digest=emitter._sha256_bytes(
            json.dumps(prov.asdict(), sort_keys=True).encode("utf-8")),
    )


def negative_altered_header_and_mapping() -> dict[str, Any]:
    """Altered header geometry / wrong mapping base fails closed."""
    real = mainexe.mainexe_member_path().read_bytes()
    entry = side._parse_hex(side.recorded_p17_05r_frontier()["attempted_frontier_pc"])
    results: dict[str, Any] = {}

    altered_addr = bytearray(real)
    struct.pack_into("<I", altered_addr, 0x18, 0x80012000)
    results["t_addr_rejected"] = _raises(
        lambda: mainexe.build_mainexe_analysis(
            0x80011af0, identity=p17_psx.ingest_bytes(bytes(altered_addr)),
            file_bytes=bytes(altered_addr)),
        mainexe.MainExeAuthError, "MAINEXE_GUEST_ADDRESS_OUTSIDE_TEXT")

    altered_size = bytearray(real)
    struct.pack_into("<I", altered_size, 0x1c, 0x10000)
    results["t_size_rejected"] = _raises(
        lambda: p17_psx.ingest_bytes(bytes(altered_size)), Exception, None)

    ident, data = mainexe.load_mainexe_identity()

    class _Fake:
        magic = b"PS-X EXE"
        t_addr = 0x80010000
        t_size = 0x10000
        pc0 = 0x800132e8
        payload = b"\x00" * 16
        file_size = 0x800 + 0x10000
        file_sha256 = "0" * 64
        payload_sha256 = "0" * 64

    results["t_size_structural_rejected"] = _raises(
        lambda: mainexe.structural_validate(_Fake()),
        mainexe.MainExeAuthError, "MAINEXE_PAYLOAD_SIZE_MISMATCH")
    results["wrong_file_offset"] = _raises(
        lambda: mainexe.read_authenticated_word(ident, entry, file_bytes=data,
                                                header_size=0x400),
        mainexe.MainExeAuthError, "MAINEXE_FILE_OFFSET_MISMATCH")
    results["entry_outside_text"] = _raises(
        lambda: mainexe.guest_to_file_offset(ident, 0x8002f000),
        mainexe.MainExeAuthError, "MAINEXE_GUEST_ADDRESS_OUTSIDE_TEXT")
    results["ok"] = all(value for key, value in results.items() if key != "ok")
    return results


def negative_tampered_payload() -> dict[str, Any]:
    """Tampered member bytes / payload digest fail authentication."""
    real = mainexe.mainexe_member_path().read_bytes()
    tampered = bytearray(real)
    tampered[mainexe.HEADER_SIZE + 0x100] ^= 0xFF
    results: dict[str, Any] = {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = pathlib.Path(tmp)
        (tmp_dir / mainexe.MAINEXE_FIXTURE_MEMBER).write_bytes(bytes(tampered))
        results["member_rejected"] = _raises(
            lambda: mainexe.load_mainexe_identity(tmp_dir),
            mainexe.MainExeAuthError, "MAINEXE_FILE_SHA256_MISMATCH")
    ident, data = mainexe.load_mainexe_identity()
    results["payload_digest_rejected"] = _raises(
        lambda: mainexe.build_mainexe_analysis(
            0x80011af0, identity=ident, file_bytes=data,
            expected_payload_sha256="0" * 64),
        mainexe.MainExeAuthError, "MAINEXE_PAYLOAD_SHA256_MISMATCH")
    results["ok"] = all(value for key, value in results.items() if key != "ok")
    return results


def negative_missing_provenance(analysis: side.SideEffectsAnalysis) -> dict[str, Any]:
    """A reachable PC without provenance is rejected before emission."""
    clone = side.SideEffectsAnalysis(
        base=analysis.base,
        recorded_frontier=analysis.recorded_frontier,
        records_by_address=dict(analysis.records_by_address),
        delay_by_owner=dict(analysis.delay_by_owner),
        provenance=dict(analysis.provenance),
        reachable=set(analysis.reachable),
    )
    target = max(clone.reachable)
    clone.provenance.pop(target)
    results = {
        "record_present_without_provenance": (
            target in clone.records_by_address and target not in clone.provenance),
        "missing_provenance_rejected": _raises(
            lambda: emitter._make_semantic_records(clone),
            emitter.TitleExecEmitError, "MISSING_SOURCE_PROVENANCE"),
    }
    results["ok"] = all(value for key, value in results.items() if key != "ok")
    return results


def negative_device_event_without_provenance(transcript_doc: dict[str, Any],
                                             provenance_map: dict[int, str]) -> dict[str, Any]:
    """A forged device event without an authenticated owner fails closed."""
    events = [dict(event) for event in transcript_doc["events"]]
    forged = transcript_model.mmio_event(
        sequence=len(events), address=0x1F801810, store=True, width=4, value=0,
        owning_instruction_pc=0x80030000, delay_slot_pc=None)
    forged["owning_instruction_provenance_digest"] = "0" * 64
    events.append(forged)
    document = dict(transcript_doc)
    document["events"] = events
    document["event_count"] = len(events)
    results = {
        "forged_event_rejected": _raises(
            lambda: transcript_model.validate_transcript(document, provenance_map),
            transcript_model.TranscriptError, "EVENT_WITHOUT_PROVENANCE"),
        "unprovenanced_attach_rejected": _raises(
            lambda: transcript_model.attach_provenance([forged], provenance_map),
            transcript_model.TranscriptError, "EVENT_WITHOUT_PROVENANCE"),
    }
    results["ok"] = all(value for key, value in results.items() if key != "ok")
    return results


def negative_device_class_forgery(transcript_doc: dict[str, Any],
                                  provenance_map: dict[int, str]) -> dict[str, Any]:
    """A mislabelled device class or non-device address fails closed."""
    results: dict[str, Any] = {}
    raw = transcript_doc["events"]
    if raw:
        events = [dict(event) for event in raw]
        owner = int(str(events[0]["owning_instruction_pc"]), 16)
        events[0]["owning_instruction_provenance_digest"] = provenance_map[owner]
        if events[0]["kind"] == "BIOS_DISPATCH":
            events[0]["vector"] = "B0"
        else:
            events[0]["class"] = "GP0_WRITE"
        document = dict(transcript_doc)
        document["events"] = events
        results["forged_class_rejected"] = _raises(
            lambda: transcript_model.validate_transcript(document, provenance_map),
            transcript_model.TranscriptError, None)
    results["non_device_address"] = transcript_model.classify_device_access(
        0x800380a0, store=True, width=4) is None
    results["fake_bios_vector"] = transcript_model.bios_vector_name(0x000000F0) is None
    results["ok"] = all(value for key, value in results.items() if key != "ok")
    return results


def negative_frontier_tampering() -> dict[str, Any]:
    """A tampered recorded frontier is rejected before any emission."""
    results: dict[str, Any] = {}
    frontier = dict(side.recorded_p17_05r_frontier())
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "RESULT.json"
        document = {
            "schema": "openrecomp-phase17-result-v1",
            "stage": "P17-05R",
            "status": "PASS",
            "authentic_frontier": dict(frontier, stop_reason="CONTINUATION_BUDGET_REACHED"),
        }
        write_json(path, document)
        results["wrong_stop_reason_rejected"] = _raises(
            lambda: side.recorded_p17_05r_frontier(path),
            side.SideEffectsError, "P17_05R_FRONTIER_NOT_TABLE_GAP")

        document["authentic_frontier"] = dict(frontier, attempted_frontier_pc="0x8004ffc0")
        write_json(path, document)
        results["non_advancing_frontier_rejected"] = _raises(
            lambda: side.recorded_p17_05r_frontier(path),
            side.SideEffectsError, "P17_05R_FRONTIER_NOT_ADVANCING")

        document["authentic_frontier"] = dict(frontier)
        document["stage"] = "P17-05"
        write_json(path, document)
        results["wrong_stage_rejected"] = _raises(
            lambda: side.recorded_p17_05r_frontier(path),
            side.SideEffectsError, "P17_05R_EVIDENCE_NOT_ACCEPTED")

        document["stage"] = "P17-05R"
        broken = dict(frontier)
        del broken["attempted_frontier_pc"]
        document["authentic_frontier"] = broken
        write_json(path, document)
        results["missing_field_rejected"] = _raises(
            lambda: side.recorded_p17_05r_frontier(path),
            side.SideEffectsError, "P17_05R_FRONTIER_FIELD_MISSING")
    results["ok"] = all(value for key, value in results.items() if key != "ok")
    return results


def negative_entry_already_authenticated() -> dict[str, Any]:
    """An entry already inside the authenticated set is rejected."""
    frontier = side.recorded_p17_05r_frontier()
    analysis = side.build_side_effects_analysis(recorded_frontier=frontier)
    return {"ok": _raises(lambda: side.build_side_effects_analysis(
        recorded_frontier=dict(frontier, attempted_frontier_pc="0x80011af0")),
        side.SideEffectsError, "CONTINUATION_ENTRY_ALREADY_AUTHENTICATED"),
        "base_records": analysis.record_count > 0}


def negative_continuation_entry_steps() -> dict[str, Any]:
    """A live replay that does not reproduce the P17-05R frontier step fails closed."""
    frontier = side.recorded_p17_05r_frontier()
    recorded_steps = side.recorded_p17_05r_frontier_steps(frontier)
    analysis = side.build_side_effects_analysis(recorded_frontier=frontier)
    analysis.authenticate_and_extend(side._parse_hex(frontier["attempted_frontier_pc"]))
    with tempfile.TemporaryDirectory() as tmp:
        result = _raises(
            lambda: side.emit_side_effects_executable(
                analysis, pathlib.Path(tmp), recorded_frontier=frontier,
                frontier_steps=recorded_steps + 1, allow_entry_stop=True),
            side.SideEffectsError, "CONTINUATION_ENTRY_STEPS_MISMATCH")
    return {"ok": result, "recorded_steps": recorded_steps}


# --- Evidence helpers ------------------------------------------------------


def _declared_next_stage(path: pathlib.Path) -> str | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        try:
            document = json.loads(text)
        except json.JSONDecodeError:
            return None
        value = document.get("next_stage")
        return str(value) if value is not None else None
    for line in text.splitlines():
        stripped = line.strip().lstrip("-*").strip()
        if stripped.lower().startswith("next_stage"):
            return stripped.split(":", 1)[1].strip().strip(chr(96)).strip()
    return None


def working_tree_phase_1_16_changes() -> list[str]:
    completed = subprocess.run(["git", "status", "--porcelain"], cwd=str(ROOT),
                               capture_output=True, text=True)
    pattern = re.compile(r"^\.openrecomp-phase(?:[1-9]|1[0-6])(?:/|$)")
    changes = []
    for line in completed.stdout.splitlines():
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ")[-1].strip()
        if pattern.match(path):
            changes.append(path)
    return changes


def evidence_public_safety(evidence_dir: pathlib.Path) -> dict[str, Any]:
    forbidden_terms = ("raw_instruction", "instruction_word", "payload_bytes", "bios_bytes")
    path_markers = ("/home/", "fixtures/", "/tmp/", "/Users/", ":\\")
    hits: list[str] = []
    files = [evidence_dir / name for name in PUBLIC_SCAN_FILES]
    present = [path for path in files if path.is_file()]
    for path in present:
        text = path.read_text(encoding="utf-8", errors="replace")
        for term in forbidden_terms:
            if term in text:
                hits.append(f"{path.name}:term:{term}")
        for marker in path_markers:
            if marker in text:
                hits.append(f"{path.name}:path:{marker}")
    return {"file_count": len(present), "hits": hits, "ok": not hits}


def private_build_root_probe() -> dict[str, Any]:
    script = (
        "import hashlib,json,pathlib,sys;"
        "sys.path.insert(0, str(pathlib.Path('.').resolve()/'.openrecomp-phase17/src'));"
        "import p17_side_effects_exec_v1 as c;"
        "default=hashlib.sha256(str(c.DEFAULT_PRIVATE_BUILD_ROOT).encode()).hexdigest()[:16];"
        "env=hashlib.sha256(str(c.private_build_root()).encode()).hexdigest()[:16];"
        "print(json.dumps({'default_digest_prefix':default,"
        "'override_honoured': env != default,'env_var': c.PRIVATE_BUILD_ROOT_ENV,"
        "'official_run_labels': list(c.OFFICIAL_RUN_DIRS)}))"
    )
    override = "/tmp/openrecomp-p17-06r-probe/override-root"
    env = dict(os.environ)
    env[side.PRIVATE_BUILD_ROOT_ENV] = override
    completed = subprocess.run([sys.executable, "-c", script], cwd=str(ROOT),
                               capture_output=True, text=True, env=env)
    try:
        probe = json.loads(completed.stdout)
    except json.JSONDecodeError:
        probe = {"error": completed.stderr.strip()[:200]}
    probe.pop("env_digest_prefix", None)
    return probe


def child_process_persistence_check(label: str) -> dict[str, Any]:
    script = (
        "import hashlib,json,pathlib,sys;"
        "run=pathlib.Path(sys.argv[1]);"
        "names=['or_side_effects_v1.c','or_side_effects_v1.h',"
        "'or_side_effects_harness_v1.c','private_mapping.json','build_metadata.json',"
        "'or_side_effects_v1.so','or_side_effects_v1'];"
        "dig={n: hashlib.sha256((run/n).read_bytes()).hexdigest() for n in names};"
        "print(json.dumps({'exist': all((run/n).is_file() for n in names),"
        "'count': len(names),'digest': hashlib.sha256(json.dumps(dig,sort_keys=True).encode()).hexdigest()}))"
    )
    run_dir = side.official_run_dir(label)
    completed = subprocess.run([sys.executable, "-c", script, str(run_dir)],
                               cwd=str(ROOT), capture_output=True, text=True)
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        result = {"exist": False, "count": 0, "digest": "", "error": completed.stderr[:160]}
    result["label"] = label
    result["ok"] = bool(result.get("exist")) and result.get("count") == 7
    return result


def persisted_artifacts_ok(run_dir: pathlib.Path, manifest: dict[str, Any]) -> dict[str, Any]:
    artifacts: dict[str, Any] = {}
    for name, record in manifest["persistence"]["artifacts"].items():
        path = run_dir / record["name"]
        exists = path.is_file()
        digest = emitter._sha256_bytes(path.read_bytes()) if exists else ""
        artifacts[name] = {
            "name": record["name"],
            "exists": exists,
            "sha256_matches": digest == record["sha256"],
            "sha256": digest,
        }
    return {"ok": all(item["exists"] and item["sha256_matches"]
                      for item in artifacts.values()), "artifacts": artifacts}


def shared_object_exports_symbol(run_dir: pathlib.Path) -> bool:
    so_path = run_dir / "or_side_effects_v1.so"
    completed = subprocess.run(["nm", "-D", str(so_path)], capture_output=True, text=True)
    return completed.returncode == 0 and "or_side_execute_v1" in completed.stdout


def implemented_vocabulary_covered() -> dict[str, Any]:
    """Every implemented operation must emit an executable handler."""
    vocabulary = sorted(side.SIDE_SUPPORTED_OPS)
    entry = side._parse_hex(side.recorded_p17_05r_frontier()["attempted_frontier_pc"])
    probe_pc = 0x80010000
    delay_pc = probe_pc + 4
    nop_record = emitter.SemanticRecord(
        pc=delay_pc, op="nop", rs=0, rt=0, rd=0, shamt=0, imm=0, target=None,
        delay_slot=None, control_flow=False, terminator=None, link=False,
        provenance_digest="0" * 64)
    ctx = side.SideEmissionContext(analysis=None)
    ctx.record_by_pc = {delay_pc: nop_record}
    ctx.index_by_pc = {probe_pc: 0, delay_pc: 1}

    class _FakeAnalysis:
        delay_by_owner = {probe_pc: delay_pc}

    ctx.analysis = _FakeAnalysis()
    uncovered: list[str] = []
    for op in vocabulary:
        record = emitter.SemanticRecord(
            pc=probe_pc, op=op, rs=4, rt=5, rd=6, shamt=2, imm=1,
            target=0x80011000, delay_slot=delay_pc,
            control_flow=op in emitter.CONTROL_OPS,
            terminator=None, link=op == "jal", provenance_digest="0" * 64)
        body = "\n".join(side._emit_instruction_side(record, ctx))
        if "UNSUPPORTED_OPERATION" in body:
            uncovered.append(op)
    return {"ok": not uncovered, "count": len(vocabulary), "uncovered": uncovered,
            "entry_pc": _hex32(entry)}


# --- Gate body -------------------------------------------------------------


def body(gate: Gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    stale = evidence / "p17_06r_tests.json"
    if stale.is_file():
        stale.unlink()

    # 1. Authentic fixture.
    fx = fixture_root()
    fixture.verify_fixture_with_callback(
        fx, lambda label, condition, detail="": gate.check(label, condition, str(detail)))

    # 2. Committed P17-02 projection and live authenticated TITLE analysis.
    projection = emitter._load_p17_02_projection(
        ROOT / ".openrecomp-phase17/evidence/P17-02/title_decode.json")
    gate.check("p17_02:projection-loadable", True)
    gate.check("p17_02:projection-digest-valid",
               projection["projection_digest"]
               == emitter._digest_dict(projection, "projection_digest"))
    title_analysis = _load_live_title_analysis()
    gate.check("p17_02:live-projection-digest-matches",
               title_analysis.projection["projection_digest"] == projection["projection_digest"])
    gate.check("next-stage:declared-constant", NEXT_STAGE == "P17-07R")

    # 3. Recorded P17-05R frontier (the derived continuation entry) and steps.
    recorded = side.recorded_p17_05r_frontier()
    recorded_steps = side.recorded_p17_05r_frontier_steps(recorded)
    entry = side._parse_hex(recorded["attempted_frontier_pc"])
    gate.check("p17_05r:recorded-frontier-loadable",
               bool(recorded["stop_reason"]) and int(recorded["mainexe_executed_count"]) >= 1,
               json.dumps({"stop_reason": recorded["stop_reason"]}, sort_keys=True))
    gate.check("p17_05r:recorded-stop-is-unauthenticated-table",
               recorded["stop_reason"] == "PC_NOT_IN_AUTHENTICATED_TABLE")
    gate.check("p17_05r:recorded-frontier-steps-loadable", recorded_steps == 78,
               json.dumps({"recorded_steps": recorded_steps}, sort_keys=True))

    # 4. Continuation entry derived from the recorded frontier (not hard-coded).
    identity, file_bytes = mainexe.load_mainexe_identity()
    gate.check("continuation:entry-derived-from-recorded-frontier",
               entry == side._parse_hex(recorded["attempted_frontier_pc"])
               and entry != side._parse_hex(recorded["last_successfully_executed_pc"]))
    gate.check("continuation:entry-inside-mainexe-text",
               identity.t_addr <= entry < identity.t_addr + identity.t_size,
               json.dumps({"entry": _hex32(entry)}, sort_keys=True))
    gate.check("continuation:entry-outside-title-payload",
               not (title_analysis.identity.t_addr
                    <= entry < title_analysis.identity.text_end))
    gate.check("continuation:entry-not-p17_04r-entry",
               entry != side._parse_hex(cont.recorded_p17_04r_frontier()["attempted_frontier_pc"]))
    mapped_offset = mainexe.guest_to_file_offset(identity, entry)
    gate.check("mainexe:mapping-rule-holds",
               mapped_offset == mainexe.HEADER_SIZE + (entry - identity.t_addr),
               json.dumps({"entry": _hex32(entry), "file_offset": mapped_offset},
                          sort_keys=True))
    gate.check("mainexe:mapping-round-trip",
               mainexe.file_offset_to_guest(identity, mapped_offset) == entry)

    # 5. Base authenticated set (P17-05R machinery, unchanged discipline).
    analysis = side.build_side_effects_analysis(title_analysis=title_analysis,
                                                recorded_frontier=recorded)
    base_analysis = side.build_side_effects_analysis(
        title_analysis=title_analysis, recorded_frontier=recorded)
    gate.check("analysis:base-record-count", base_analysis.record_count == 7001,
               json.dumps({"records": base_analysis.record_count}, sort_keys=True))
    gate.check("analysis:base-title-records",
               base_analysis.title_record_count
               == len(title_analysis.frontier["reachable_addresses"]))
    gate.check("analysis:base-mainexe-records", base_analysis.mainexe_record_count == 6)
    gate.check("analysis:entry-not-yet-authenticated", entry not in base_analysis.reachable)

    # 6. Bounded dynamic discovery with the emitted runtime as the authority.
    private_root = side.private_build_root()
    run_dirs: list[pathlib.Path] = []
    manifests: list[dict[str, Any]] = []
    discovery_observations: list[dict[str, Any]] = []
    discovery_analyses: list[side.SideEffectsAnalysis] = []
    for label in side.OFFICIAL_RUN_DIRS:
        # Every official run performs its own discovery from the committed
        # inputs: no discovery state is shared between the two runs.
        run_analysis = side.build_side_effects_analysis(
            title_analysis=title_analysis, recorded_frontier=recorded)
        discovery_dir = side.official_run_dir(f"{label}-discovery", private_root)
        if discovery_dir.exists():
            shutil.rmtree(discovery_dir)
        discovery_dir.mkdir(parents=True, exist_ok=False)
        _, observations, _ = side.discover_continuation(
            run_analysis, discovery_dir, recorded_frontier=recorded,
            frontier_steps=recorded_steps)
        discovery_observations.append({"label": label, "generations": observations})
        run_dir = side.official_run_dir(label, private_root)
        if run_dir.exists():
            shutil.rmtree(run_dir)
        run_dir.mkdir(parents=True, exist_ok=False)
        run_dirs.append(run_dir)
        manifests.append(side.emit_side_effects_executable(
            run_analysis, run_dir, recorded_frontier=recorded,
            frontier_steps=recorded_steps))
        discovery_analyses.append(run_analysis)
    gate.check("discovery:generations-recorded",
               all(len(item["generations"]) >= 2 for item in discovery_observations),
               json.dumps([{"label": item["label"],
                            "generations": len(item["generations"])}
                           for item in discovery_observations], sort_keys=True))
    gate.check("discovery:independent-analyses-agree",
               discovery_analyses[0].record_count == discovery_analyses[1].record_count
               and discovery_analyses[0].region_log == discovery_analyses[1].region_log
               and discovery_analyses[0].title_record_count
               == discovery_analyses[1].title_record_count
               and discovery_analyses[0].mainexe_record_count
               == discovery_analyses[1].mainexe_record_count,
               json.dumps({"records": [item.record_count for item in discovery_analyses],
                           "regions": [len(item.region_log) for item in discovery_analyses]},
                          sort_keys=True))
    analysis = discovery_analyses[-1]
    gate.check("persistence:fresh-run-dirs-created",
               all(side.official_run_dir(label, private_root).is_dir()
                   for label in side.OFFICIAL_RUN_DIRS))
    gate.check("persistence:run-dirs-distinct", run_dirs[0] != run_dirs[1])

    manifest = manifests[0]
    rr = manifest["runtime_result"]

    # 7. Newly authenticated regions: full provenance chain from source bytes.
    gate.check("regions:discovered", len(analysis.region_log) >= 1,
               json.dumps(analysis.region_log, sort_keys=True))
    region_chain_ok = True
    for region in analysis.region_log:
        pc = side._parse_hex(region["entry_pc"])
        if pc not in analysis.reachable:
            region_chain_ok = False
        if region["region"] == "MAIN_EXE":
            expected = mainexe.HEADER_SIZE + (pc - identity.t_addr)
        else:
            expected = analysis._title_file_offset(pc)
        if region["entry_file_offset"] != expected:
            region_chain_ok = False
    gate.check("regions:provenance-chain-holds", region_chain_ok)
    title_identity = analysis.base.title.identity
    provenance_ok = True
    for pc in sorted(analysis.reachable):
        prov = analysis.provenance[pc]
        live_word = analysis.read_authenticated_word(pc)
        if analysis.region_of(pc) == "MAIN_EXE":
            expected_word = struct.unpack_from(
                "<I", identity.payload, pc - identity.t_addr)[0]
            if (prov.file_offset != mainexe.HEADER_SIZE + (pc - identity.t_addr)
                    or prov.mainexe_file_sha256 != identity.file_sha256
                    or prov.mainexe_payload_sha256 != identity.payload_sha256
                    or prov.t_addr != identity.t_addr
                    or prov.t_size != identity.t_size
                    or live_word != expected_word):
                provenance_ok = False
        else:
            expected_word = struct.unpack_from(
                "<I", title_identity.payload, pc - title_identity.t_addr)[0]
            if (prov.file_offset != analysis._title_file_offset(pc)
                    or live_word != expected_word):
                provenance_ok = False
        if analysis.records_by_address[pc]["word"] != live_word:
            provenance_ok = False
    gate.check("regions:every-record-provenance-holds", provenance_ok,
               json.dumps({"records": analysis.record_count}, sort_keys=True))
    semantic_records = emitter._make_semantic_records(analysis)
    gate.check("regions:every-record-verified-against-fresh-decode",
               len(semantic_records) == analysis.record_count > 7000,
               json.dumps({"records": len(semantic_records),
                           "reachable": analysis.record_count}, sort_keys=True))

    # 8. Emission interface / persistence / determinism.
    gate.check("emission:header-generated", bool(manifest["source"]["generated_source_sha256"]))
    gate.check("emission:harness-generated", bool(manifest["source"]["generated_harness_sha256"]))
    gate.check("emission:shared-object-generated", bool(manifest["build"]["shared_object_sha256"]))
    gate.check("emission:executable-generated", bool(manifest["build"]["executable_sha256"]))
    gate.check("emission:entry-pc", rr["entry_pc"] == _hex32(cont.TITLE_ENTRY_PC))
    gate.check("emission:register-digest-present", bool(rr["register_digest"]))
    gate.check("emission:ram-digest-present", bool(rr["ram_digest"]))
    gate.check("emission:provenance-digest-present", bool(manifest["source"]["provenance_digest"]))
    gate.check("emission:implemented-semantic-vocabulary",
               manifest["source"]["implemented_semantic_vocabulary_count"] == len(side.SIDE_SUPPORTED_OPS))
    gate.check("emission:exercised-semantic-vocabulary-non-empty",
               bool(manifest["source"]["exercised_semantic_vocabulary"]))
    generated_c = (run_dirs[0] / "or_side_effects_v1.c").read_text(encoding="utf-8")
    gate.check("emission:no-phase16-transition-code-import",
               "TITLE_TRANSITION_CODE" not in generated_c
               and "p16_emission_v1" not in generated_c)
    gate.check("interface:shared-object-exports-symbol",
               shared_object_exports_symbol(run_dirs[0]))
    persisted_first = persisted_artifacts_ok(run_dirs[0], manifest)
    persisted_second = persisted_artifacts_ok(run_dirs[1], manifests[1])
    gate.check("persistence:run1-artifacts-exist-and-hash-match", persisted_first["ok"],
               json.dumps({k: v["sha256"] for k, v in persisted_first["artifacts"].items()},
                          sort_keys=True))
    gate.check("persistence:run2-artifacts-exist-and-hash-match", persisted_second["ok"])
    gate.check("persistence:private-map-record-count",
               manifest["persistence"]["private_mapping_record_count"]
               == manifest["source"]["record_count"] > 7000)
    probe = private_build_root_probe()
    gate.check("persistence:private-build-root-env-override",
               bool(probe.get("override_honoured")), json.dumps(probe, sort_keys=True))
    child_check = child_process_persistence_check(side.OFFICIAL_RUN_DIRS[0])
    gate.check("persistence:child-process-verification", child_check["ok"],
               json.dumps(child_check, sort_keys=True))
    gate.check("determinism:runtime-result-identical",
               manifests[0]["runtime_result"] == manifests[1]["runtime_result"])
    gate.check("determinism:transcript-identical",
               manifests[0]["transcript"] == manifests[1]["transcript"])
    gate.check("determinism:manifest-identical", manifests[0] == manifests[1])
    gate.check("determinism:shared-object-hash-identical",
               manifests[0]["build"]["shared_object_sha256"]
               == manifests[1]["build"]["shared_object_sha256"])
    gate.check("determinism:executable-hash-identical",
               manifests[0]["build"]["executable_sha256"]
               == manifests[1]["build"]["executable_sha256"])

    # 9. Authentic execution advances strictly beyond the P17-05R frontier.
    post_entry = [int(str(pc), 16) for pc in rr["post_entry_pcs"]]
    gate.check("continuation:p17_05r-frontier-reproduced",
               int(rr["continuation_entry_steps"]) == recorded_steps,
               json.dumps({"live": rr["continuation_entry_steps"],
                           "recorded": recorded_steps}, sort_keys=True))
    gate.check("continuation:entry-executed-first", bool(post_entry) and post_entry[0] == entry,
               json.dumps({"post_entry": rr["post_entry_pcs"][:4]}, sort_keys=True))
    gate.check("continuation:advanced-beyond-entry",
               any(pc > entry for pc in post_entry)
               and int(str(rr["last_successfully_executed_pc"]), 16) != entry,
               json.dumps({"entry": _hex32(entry),
                           "last": rr["last_successfully_executed_pc"],
                           "distinct": rr["distinct_executed_pc_count"]}, sort_keys=True))
    executed_pcs = [int(str(pc), 16) for pc in rr["distinct_executed_pcs"]]
    gate.check("continuation:recorded-frontier-pcs-executed",
               side._parse_hex(recorded["last_successfully_executed_pc"]) in executed_pcs
               and side._parse_hex(recorded["mainexe_first_pc"]) in executed_pcs)
    gate.check("continuation:executed-pcs-all-authenticated",
               all(pc in analysis.reachable for pc in executed_pcs),
               json.dumps({"executed": len(executed_pcs)}, sort_keys=True))
    gate.check("continuation:budget-respected",
               0 <= int(rr["continuation_executed_count"]) <= side.CONTINUATION_BUDGET,
               json.dumps({"continuation_executed": rr["continuation_executed_count"],
                           "budget": side.CONTINUATION_BUDGET}, sort_keys=True))
    gate.check("continuation:typed-stop-reason",
               rr["stop_reason"] in side.ALLOWED_STOP_REASONS, rr["stop_reason"])
    gate.check("continuation:new-regions-executed",
               analysis.region_log[0]["entry_pc"] in rr["distinct_executed_pcs"]
               and any(pc >= side._parse_hex(analysis.region_log[0]["entry_pc"])
                       for pc in executed_pcs))

    # 10. Device/BIOS transcript: deterministic, hashed, provenance-complete.
    transcript_doc = manifest["transcript_document"]
    provenance_map = side.provenance_digest_map(analysis)
    gate.check("transcript:event-count-matches",
               transcript_doc["event_count"] == manifest["transcript"]["event_count"])
    gate.check("transcript:bios-dispatch-recorded",
               int(rr["bios_dispatch_count"]) >= 1,
               json.dumps({"bios_dispatch_count": rr["bios_dispatch_count"],
                           "device_event_count": rr["device_event_count"]}, sort_keys=True))
    events = transcript_doc["events"]
    owners_ok = all(int(str(event["owning_instruction_pc"]), 16) in provenance_map
                    for event in events)
    gate.check("transcript:events-carry-authenticated-owner", owners_ok)
    validated = True
    try:
        transcript_model.validate_transcript(transcript_doc, provenance_map)
    except transcript_model.TranscriptError:
        validated = False
    gate.check("transcript:fail-closed-validation", validated)
    transcript_bytes = transcript_model.canonical_bytes(transcript_doc)
    transcript_sha = transcript_model.sha256_bytes(transcript_bytes)
    gate.check("transcript:hash-matches",
               transcript_sha == manifest["transcript"]["sha256"])
    gate.check("transcript:device-layer-declared",
               transcript_doc["bios_model"]["internals"] == "NOT_MODELED"
               and transcript_doc["bios_model"]["dispatch"] == transcript_model.BIOS_MODEL)
    bios_vectors = {event["vector"] for event in events if event["kind"] == "BIOS_DISPATCH"}
    gate.check("transcript:bios-vectors-modelled", bios_vectors.issubset({"A0", "B0", "C0"}),
               json.dumps(sorted(bios_vectors), sort_keys=True))
    gate.check("transcript:device-event-classes-declared",
               all(event["kind"] in ("BIOS_DISPATCH", "MMIO") for event in events))

    # 11. Negative controls (each evaluated exactly once).
    negatives = {
        "unauthenticated-destination": negative_unauthenticated_destination(analysis),
        "altered-source-word": negative_altered_source_word(),
        "altered-header-and-mapping": negative_altered_header_and_mapping(),
        "tampered-payload": negative_tampered_payload(),
        "missing-provenance": negative_missing_provenance(analysis),
        "device-event-without-provenance": negative_device_event_without_provenance(
            transcript_doc, provenance_map),
        "device-class-forgery": negative_device_class_forgery(transcript_doc, provenance_map),
        "frontier-tampering": negative_frontier_tampering(),
        "entry-already-authenticated": negative_entry_already_authenticated(),
        "frontier-step-mismatch": negative_continuation_entry_steps(),
    }
    for name, result in negatives.items():
        gate.check(f"negative:{name}", result["ok"], json.dumps(result, sort_keys=True))

    # 12. Vocabulary coverage.
    coverage = implemented_vocabulary_covered()
    gate.check("vocabulary:implemented-ops-all-executable", coverage["ok"],
               json.dumps(coverage, sort_keys=True))
    exercised = manifest["source"]["exercised_semantic_vocabulary"]
    gate.check("vocabulary:exercised-subset-of-implemented",
               set(exercised).issubset(side.SIDE_SUPPORTED_OPS))
    gate.check("vocabulary:executed-op-counts-sum",
               sum(manifest["source"]["executed_op_counts"].values())
               == rr["executed_instruction_count"],
               json.dumps({"sum": sum(manifest["source"]["executed_op_counts"].values()),
                           "executed": rr["executed_instruction_count"]}, sort_keys=True))
    gate.check("vocabulary:additional-ops-declared",
               set(manifest["source"]["additional_implemented_semantic_vocabulary"])
               == set(side.ADDITIONAL_OPS))

    # 13. Evidence documents.
    continuation_doc = {
        "schema": "openrecomp-phase17-side-effects-continuation-v1",
        "stage": STAGE,
        "next_stage": NEXT_STAGE,
        "continuation_entry_pc": _hex32(entry),
        "p17_05r_frontier": {
            "last_successfully_executed_pc": recorded["last_successfully_executed_pc"],
            "attempted_frontier_pc": recorded["attempted_frontier_pc"],
            "stop_reason": recorded["stop_reason"],
            "executed_instruction_count": recorded_steps,
        },
        "authenticated_region_log": analysis.region_log,
        "record_counts": {
            "title": analysis.title_record_count,
            "mainexe": analysis.mainexe_record_count,
            "total": analysis.record_count,
        },
        "discovery_observations": discovery_observations,
        "frontier": manifest["frontier"],
        "runtime_digests": {
            "register_digest": rr["register_digest"],
            "ram_digest": rr["ram_digest"],
            "provenance_digest": manifest["source"]["provenance_digest"],
        },
        "bios_dispatch_count": rr["bios_dispatch_count"],
        "device_event_count": rr["device_event_count"],
        "device_event_class_counts": manifest["transcript"]["event_class_counts"],
        "device_traffic_reached": bool(events),
        "device_layer": manifest["device_layer"],
        "transcript_sha256": manifest["transcript"]["sha256"],
        "emission_digest": manifest["emission_digest"],
        "vocabulary": {
            "implemented": manifest["source"]["implemented_semantic_vocabulary_count"],
            "p17_05r_implemented": len(emitter.SUPPORTED_OPS),
            "additional_implemented": manifest["source"]["additional_implemented_semantic_vocabulary"],
            "exercised": manifest["source"]["exercised_semantic_vocabulary_count"],
            "executed_op_counts": manifest["source"]["executed_op_counts"],
        },
        "claims": manifest["claims"],
    }
    for name, document in (("continuation", continuation_doc),
                           ("emission", manifest),
                           ("transcript", transcript_doc)):
        text = json.dumps(document, sort_keys=True)
        for term in ("raw_instruction", "instruction_word", "payload_bytes", "bios_bytes"):
            gate.check(f"public:{name}:no-{term.replace(chr(95), chr(45))}-field",
                       term not in text)
        gate.check(f"public:{name}:no-private-paths",
                   "/home/" not in text and "fixtures/" not in text and "/tmp/" not in text)
        assert_public_safe(gate, name, document)

    write_json(evidence / "continuation.json", continuation_doc)
    (evidence / "transcript.json").write_bytes(transcript_bytes)
    (evidence / "transcript.sha256").write_text(
        f"{transcript_sha}  transcript.json\n", encoding="utf-8", newline="\n")
    write_json(evidence / "next_stage.json", {
        "schema": "openrecomp-phase17-next-stage-v1",
        "stage": STAGE,
        "next_stage": NEXT_STAGE,
        "authoritative_sources": ["RESULT.json", "continuation.json", "transcript.json",
                                  "stage_metadata.json", "next_stage.json", "STATE.md",
                                  "HANDOFF.md"],
    })
    write_json(evidence / "stage_metadata.json", {
        "schema": "openrecomp-phase17-stage-metadata-v1",
        "stage": STAGE,
        "status": "PASS",
        "next_stage": NEXT_STAGE,
        "base_commit": BASE_COMMIT,
        "worker_branch": WORKER_BRANCH,
        "resulting_candidate_commit": "PENDING_FINAL_COMMIT",
        "resulting_candidate_commit_resolver": f"git rev-parse {WORKER_BRANCH}",
    })
    markers = {
        "OPENRECOMP_PHASE17_LIVE_DEVICE_SIDE_EFFECT_FRONTIER_V1": "PASS",
        "OPENRECOMP_P17_06R": "PASS",
        contract.INITIALIZATION_MARKER: "NOT_PROVEN",
        contract.FRAME_MARKER: "NOT_PROVEN",
        contract.PLAYABILITY_MARKER: "NOT_PROVEN",
        contract.GENERAL_MARKER: "NOT_PROVEN",
        contract.FIRST_FRAME_READY_MARKER: "NO",
    }
    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase17-result-v1",
        "stage": STAGE,
        "status": "PASS",
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "base_commit": BASE_COMMIT,
        "worker_branch": WORKER_BRANCH,
        "resulting_candidate_commit": "PENDING_FINAL_COMMIT",
        "resulting_candidate_commit_resolver": f"git rev-parse {WORKER_BRANCH}",
        "continuation_entry_pc": _hex32(entry),
        "p17_05r_frontier": {
            "last_successfully_executed_pc": recorded["last_successfully_executed_pc"],
            "attempted_frontier_pc": recorded["attempted_frontier_pc"],
            "stop_reason": recorded["stop_reason"],
            "executed_instruction_count": recorded_steps,
        },
        "authentic_frontier": manifest["frontier"],
        "newly_authenticated_records": {
            "title": analysis.title_record_count,
            "mainexe": analysis.mainexe_record_count,
            "total": analysis.record_count,
        },
        "newly_authenticated_regions": analysis.region_log,
        "device_transcript": {
            "sha256": manifest["transcript"]["sha256"],
            "event_count": manifest["transcript"]["event_count"],
            "bios_dispatch_count": manifest["transcript"]["bios_dispatch_count"],
            "device_event_count": manifest["transcript"]["device_event_count"],
            "event_class_counts": manifest["transcript"]["event_class_counts"],
            "device_traffic_reached": bool(events),
            "bios_internals": transcript_model.BIOS_INTERNALS,
        },
        "semantic_vocabulary_counts": {
            "implemented": manifest["source"]["implemented_semantic_vocabulary_count"],
            "exercised": manifest["source"]["exercised_semantic_vocabulary_count"],
        },
        "emission_digest": manifest["emission_digest"],
        "markers": markers,
        "next_stage": NEXT_STAGE,
        "proof_boundaries": {
            "HERCULES_INITIALIZATION_PROOF": "NOT_PROVEN",
            "HERCULES_FRAME_PROOF": "NOT_PROVEN",
            "HERCULES_PLAYABILITY_PROOF": "NOT_PROVEN",
            "GENERAL_PS1_COMPATIBILITY": "NOT_PROVEN",
            "FIRST_FRAME_READY": "NO",
        },
    })

    # 14. Cross-file next-stage consistency.
    authoritative = {
        "RESULT.json": evidence / "RESULT.json",
        "continuation.json": evidence / "continuation.json",
        "transcript.json": evidence / "transcript.json",
        "stage_metadata.json": evidence / "stage_metadata.json",
        "next_stage.json": evidence / "next_stage.json",
        "STATE.md": ROOT / ".openrecomp-phase17" / "STATE.md",
        "HANDOFF.md": ROOT / ".openrecomp-phase17" / "HANDOFF.md",
    }
    declared = {}
    for name, path in authoritative.items():
        value = _declared_next_stage(path)
        if value is not None:
            declared[name] = value
    required = set(authoritative)
    mismatched = sorted(name for name, value in declared.items() if value != NEXT_STAGE)
    missing = sorted(required - set(declared))
    gate.check("next-stage:cross-file-consistency", not mismatched and not missing,
               json.dumps({"mismatched": mismatched, "missing": missing}, sort_keys=True))

    # 15. Scope: no Phase 1..16 modifications; frozen Phase-16 integrity.
    phase_changes = working_tree_phase_1_16_changes()
    gate.check("scope:no-phase-1-16-changes", not phase_changes,
               json.dumps(phase_changes, sort_keys=True))
    frozen = subprocess.run(
        [sys.executable, str(ROOT / ".openrecomp-phase17" / "src"
                             / "p17_frozen_phase16_integrity_v1.py")],
        cwd=str(ROOT), capture_output=True, text=True)
    gate.check("scope:phase16-frozen-integrity",
               frozen.returncode == 0
               and "OPENRECOMP_PHASE17_P16_SOURCE_INTEGRITY=PASS" in frozen.stdout)

    # 16. Public safety over committed evidence and the gate stdout.
    evidence_scan = evidence_public_safety(evidence)
    gate.check("public:committed-evidence-clean", evidence_scan["ok"],
               json.dumps(evidence_scan, sort_keys=True))
    stdout_text = json.dumps(gate.results, sort_keys=True)
    stdout_hits = [term for term in ("raw_instruction", "instruction_word",
                                     "payload_bytes", "bios_bytes")
                   if term in stdout_text]
    stdout_hits += [marker for marker in ("/home/", "fixtures/", "/tmp/", "/Users/")
                    if marker in stdout_text]
    gate.check("public:gate-stdout-clean", not stdout_hits,
               json.dumps(stdout_hits, sort_keys=True))

    for key, value in markers.items():
        gate.mark(key, value)
    gate.mark("OPENRECOMP_P17_06R_EXECUTION_BUDGET", str(side.CONTINUATION_BUDGET))
    gate.mark("OPENRECOMP_P17_06R_DEVICE_EVENTS", str(manifest["transcript"]["device_event_count"]))


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase17/evidence/P17-06R"))
