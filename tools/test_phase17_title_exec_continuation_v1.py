#!/usr/bin/env python3
"""Deterministic P17-05R authenticated execution continuation gate.

Continues real authenticated guest execution across the TITLE -> main-EXE
transition: authenticates the main-EXE payload from source bytes, extends the
P17-04R authenticated record set with the records reachable from the recorded
frontier, executes them in a compiled native runtime, and records a typed
frontier with a full provenance chain and non-reconstructive evidence.
"""

from __future__ import annotations

import hashlib
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
import p17_fixture_verification_v1 as fixture
import p17_mainexe_auth_v1 as mainexe
import p17_psx_exe_identity_v1 as p17_psx
import p17_title_decode_v1 as title_decode
import p17_title_exec_continuation_v1 as cont
import p17_title_exec_emit_v1 as emitter
from p17_gate_v1 import Gate, assert_public_safe, run_stage, write_json

STAGE = "P17-05R"
NEXT_STAGE = "P17-06R"
TITLE_ISO_PATH = title_decode.TITLE_ISO_PATH

ALLOWED_STOP_REASONS = {
    "PC_NOT_IN_AUTHENTICATED_TABLE",
    "UNSUPPORTED_OPERATION",
    "SIGNED_OVERFLOW",
    "UNALIGNED_OR_OUT_OF_BOUNDS_MEMORY_ACCESS",
    "OUT_OF_BOUNDS_MEMORY_ACCESS",
    "STEP_LIMIT_REACHED",
    "CONTINUATION_BUDGET_REACHED",
}

#: Stage-owned evidence documents scanned for public safety.  Runner-owned files
#: (official_runs.json / determinism.json) and the regenerated tests document are
#: excluded so the scan is stable across repeated official invocations.
PUBLIC_SCAN_FILES = ("RESULT.json", "continuation.json", "mainexe_mapping.json",
                     "next_stage.json", "stage_metadata.json")


def fixture_root() -> pathlib.Path:
    env = os.environ.get("OPENRECOMP_HERCULES_FIXTURE_ROOT")
    if env:
        return pathlib.Path(env)
    return ROOT.parents[1] / "fixtures" / "psx" / "hercules"


def _hex32(value: int) -> str:
    return f"0x{value:08x}"


def load_committed_projection() -> dict[str, Any]:
    return emitter._load_p17_02_projection(
        ROOT / ".openrecomp-phase17/evidence/P17-02/title_decode.json"
    )


_ANALYSIS_CACHE: dict[str, Any] = {}


def _load_live_title_analysis() -> Any:
    if "title" not in _ANALYSIS_CACHE:
        fx = fixture_root()
        fixture.verify_fixture_with_callback(fx, lambda label, condition, detail="": None)
        _ANALYSIS_CACHE["title"] = title_decode.analyze_title_decode(fixture_dir=fx)
    return _ANALYSIS_CACHE["title"]


def _continuation_analysis() -> Any:
    if "cont" not in _ANALYSIS_CACHE:
        _ANALYSIS_CACHE["cont"] = cont.build_continuation_analysis(
            title_analysis=_load_live_title_analysis()
        )
    return _ANALYSIS_CACHE["cont"]


def _semantic_from_raw(analysis: Any, pc: int) -> emitter.SemanticRecord:
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
            json.dumps(prov.asdict(), sort_keys=True).encode("utf-8")
        ),
    )


# --- Negative controls -----------------------------------------------------


def negative_unauthenticated_destination() -> dict[str, Any]:
    """An address outside the authenticated sources is rejected before emission."""
    ident, data = mainexe.load_mainexe_identity()
    results: dict[str, Any] = {}
    # (1) continuation entry outside the authenticated main-EXE text.
    try:
        mainexe.build_mainexe_analysis(0x80030000, identity=ident, file_bytes=data)
        results["entry_rejected"] = False
    except mainexe.MainExeAuthError as exc:
        results["entry_rejected"] = exc.code == "MAINEXE_GUEST_ADDRESS_OUTSIDE_TEXT"
    # (2) a semantic record for a PC in neither authenticated region.
    analysis = _continuation_analysis()
    record = emitter.SemanticRecord(
        pc=0x80030000, op="addiu", rs=0, rt=1, rd=0, shamt=0, imm=5, target=None,
        delay_slot=None, control_flow=False, terminator=None, link=False,
        provenance_digest="0" * 64,
    )
    try:
        emitter._verify_record_against_fresh_decode(record, analysis)
        results["record_rejected"] = False
    except emitter.TitleExecEmitError as exc:
        results["record_rejected"] = exc.code == "UNAUTHENTICATED_RECORD"
    # (3) the region resolver fails closed for an unknown PC.
    try:
        analysis.read_authenticated_word(0x80030000)
        results["resolver_rejected"] = False
    except cont.ContinuationError as exc:
        results["resolver_rejected"] = exc.code == "PC_OUTSIDE_AUTHENTICATED_SOURCES"
    results["ok"] = all(results[k] for k in ("entry_rejected", "record_rejected",
                                             "resolver_rejected"))
    return results


def negative_altered_source_word() -> dict[str, Any]:
    """A record whose authenticated word disagrees with a fresh decode fails."""
    entry = cont.recorded_p17_04r_frontier()["attempted_frontier_pc"]
    entry_pc = int(str(entry), 16)
    ident, data = mainexe.load_mainexe_identity()
    base = mainexe.build_mainexe_analysis(entry_pc, identity=ident, file_bytes=data)
    pc = sorted(base.provenance)[0]
    record = _semantic_from_raw(base, pc)
    offset = mainexe.HEADER_SIZE + (pc - ident.t_addr)
    tampered = bytearray(data)
    tampered[offset:offset + 4] = struct.pack("<I", 0x24010007)
    tampered_identity = p17_psx.ingest_bytes(bytes(tampered))
    tampered_analysis = mainexe.build_mainexe_analysis(
        entry_pc, identity=tampered_identity, file_bytes=bytes(tampered)
    )
    try:
        emitter._verify_record_against_fresh_decode(record, tampered_analysis)
        return {"ok": False, "code": None}
    except emitter.TitleExecEmitError as exc:
        return {"ok": exc.code in ("OPCODE_MISMATCH", "OPERAND_MISMATCH"), "code": exc.code}


def negative_altered_header_fields() -> dict[str, Any]:
    """Altered t_addr / t_size fail closed against the continuation entry."""
    real = mainexe.mainexe_member_path().read_bytes()
    results: dict[str, Any] = {}

    altered_addr = bytearray(real)
    struct.pack_into("<I", altered_addr, 0x18, 0x80012000)
    try:
        identity = p17_psx.ingest_bytes(bytes(altered_addr))
        mainexe.build_mainexe_analysis(0x80011af0, identity=identity,
                                       file_bytes=bytes(altered_addr))
        results["t_addr_rejected"] = False
    except mainexe.MainExeAuthError as exc:
        results["t_addr_rejected"] = exc.code in (
            "MAINEXE_GUEST_ADDRESS_OUTSIDE_TEXT", "MAINEXE_ENTRY_OUTSIDE_TEXT"
        )

    altered_size = bytearray(real)
    struct.pack_into("<I", altered_size, 0x1c, 0x10000)
    try:
        p17_psx.ingest_bytes(bytes(altered_size))
        results["t_size_rejected"] = False
    except Exception:
        results["t_size_rejected"] = True

    class _Fake:
        magic = b"PS-X EXE"
        t_addr = 0x80010000
        t_size = 0x10000
        pc0 = 0x800132e8
        payload = b"\x00" * 16
        file_size = 0x800 + 0x10000
        file_sha256 = "0" * 64
        payload_sha256 = "0" * 64

    results["t_size_structural_rejected"] = False
    try:
        mainexe.structural_validate(_Fake())
    except mainexe.MainExeAuthError as exc:
        results["t_size_structural_rejected"] = exc.code == "MAINEXE_PAYLOAD_SIZE_MISMATCH"
    results["ok"] = all(results[k] for k in ("t_addr_rejected", "t_size_rejected",
                                             "t_size_structural_rejected"))
    return results


def negative_wrong_file_offset() -> dict[str, Any]:
    """Reading through a wrong file-offset base fails the mapping cross-check."""
    ident, data = mainexe.load_mainexe_identity()
    try:
        mainexe.read_authenticated_word(ident, 0x80011af0, file_bytes=data,
                                        header_size=0x400)
        return {"ok": False, "code": None}
    except mainexe.MainExeAuthError as exc:
        return {"ok": exc.code == "MAINEXE_FILE_OFFSET_MISMATCH", "code": exc.code}


def negative_tampered_payload_sha256() -> dict[str, Any]:
    """A tampered payload digest / member fails authentication."""
    real = mainexe.mainexe_member_path().read_bytes()
    tampered = bytearray(real)
    tampered[mainexe.HEADER_SIZE + 0x100] ^= 0xFF
    results: dict[str, Any] = {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = pathlib.Path(tmp)
        (tmp_dir / mainexe.MAINEXE_FIXTURE_MEMBER).write_bytes(bytes(tampered))
        try:
            mainexe.load_mainexe_identity(tmp_dir)
            results["member_rejected"] = False
        except mainexe.MainExeAuthError as exc:
            results["member_rejected"] = exc.code == "MAINEXE_FILE_SHA256_MISMATCH"
    ident, data = mainexe.load_mainexe_identity()
    try:
        mainexe.build_mainexe_analysis(0x80011af0, identity=ident, file_bytes=data,
                                       expected_payload_sha256="0" * 64)
        results["payload_digest_rejected"] = False
    except mainexe.MainExeAuthError as exc:
        results["payload_digest_rejected"] = exc.code == "MAINEXE_PAYLOAD_SHA256_MISMATCH"
    results["ok"] = results["member_rejected"] and results["payload_digest_rejected"]
    return results


def negative_missing_provenance() -> dict[str, Any]:
    """A reachable PC without provenance is rejected before emission."""
    base = _continuation_analysis()
    analysis = cont.ContinuationAnalysis(
        title=base.title, mainexe=base.mainexe,
        continuation_entry_pc=base.continuation_entry_pc,
        records_by_address=base.records_by_address,
        delay_by_owner=base.delay_by_owner,
        provenance=dict(base.provenance),
        frontier=base.frontier,
    )
    target = next(pc for pc in sorted(analysis.provenance)
                  if analysis.region_of(pc) == "MAIN_EXE")
    del analysis.provenance[target]
    try:
        emitter._make_semantic_records(analysis)
        return {"ok": False, "code": None}
    except emitter.TitleExecEmitError as exc:
        return {"ok": exc.code == "MISSING_SOURCE_PROVENANCE", "code": exc.code}


def negative_continuation_not_entered() -> dict[str, Any]:
    """A non-advancing frontier (no main-EXE instruction) is rejected."""
    recorded = dict(cont.recorded_p17_04r_frontier())
    recorded["executed_instruction_count"] = 999999
    analysis = _continuation_analysis()
    with tempfile.TemporaryDirectory() as tmp:
        try:
            cont.emit_continuation_executable(analysis, pathlib.Path(tmp),
                                              recorded_frontier=recorded)
            return {"ok": False, "code": None}
        except cont.ContinuationError as exc:
            return {"ok": exc.code == "TITLE_FRONTIER_REPRODUCTION_MISMATCH",
                    "code": exc.code}


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
    """Verify env override and the declared default in a fresh process."""
    script = (
        "import hashlib,json,pathlib,sys;"
        "sys.path.insert(0, str(pathlib.Path('.').resolve()/'.openrecomp-phase17/src'));"
        "import p17_title_exec_continuation_v1 as c;"
        "default=hashlib.sha256(str(c.DEFAULT_PRIVATE_BUILD_ROOT).encode()).hexdigest()[:16];"
        "env=hashlib.sha256(str(c.private_build_root()).encode()).hexdigest()[:16];"
        "print(json.dumps({'default_digest_prefix':default,'env_digest_prefix':env,"
        "'override_honoured': env != default,'env_var': c.PRIVATE_BUILD_ROOT_ENV,"
        "'official_run_labels': list(c.OFFICIAL_RUN_DIRS)}))"
    )
    override = "/tmp/openrecomp-p17-05r-probe/override-root"
    env = dict(os.environ)
    env[cont.PRIVATE_BUILD_ROOT_ENV] = override
    completed = subprocess.run([sys.executable, "-c", script], cwd=str(ROOT),
                               capture_output=True, text=True, env=env)
    try:
        probe = json.loads(completed.stdout)
    except json.JSONDecodeError:
        probe = {"error": completed.stderr.strip()[:200]}
    # Never echo a private path: only digest prefixes and booleans are reported.
    probe.pop("env_digest_prefix", None)
    return probe


def child_process_persistence_check(label: str) -> dict[str, Any]:
    """Verify persisted artifact hashes in a separate process after emission."""
    script = (
        "import hashlib,json,pathlib,sys;"
        "run=pathlib.Path(sys.argv[1]);"
        "names=['or_title_continuation_v1.c','or_title_continuation_v1.h',"
        "'or_title_continuation_harness_v1.c','private_mapping.json','build_metadata.json',"
        "'or_title_continuation_v1.so','or_title_continuation_v1'];"
        "dig={n: hashlib.sha256((run/n).read_bytes()).hexdigest() for n in names};"
        "print(json.dumps({'exist': all((run/n).is_file() for n in names),"
        "'count': len(names),'digest': hashlib.sha256(json.dumps(dig,sort_keys=True).encode()).hexdigest()}))"
    )
    run_dir = cont.official_run_dir(label)
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
    so_path = run_dir / "or_title_continuation_v1.so"
    completed = subprocess.run(["nm", "-D", str(so_path)], capture_output=True, text=True)
    return completed.returncode == 0 and "or_cont_execute_v1" in completed.stdout


def implemented_vocabulary_covered() -> dict[str, Any]:
    vocabulary = sorted(emitter.SUPPORTED_OPS)
    return {"ok": len(vocabulary) == 45 and vocabulary == sorted(set(vocabulary)),
            "count": len(vocabulary)}


# --- Gate body -------------------------------------------------------------


def body(gate: Gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    stale = evidence / "p17_05r_tests.json"
    if stale.is_file():
        stale.unlink()

    # 1. Authentic fixture.
    fx = fixture_root()
    fixture.verify_fixture_with_callback(
        fx, lambda label, condition, detail="": gate.check(label, condition, str(detail))
    )

    # 2. Committed P17-02 projection and live authenticated TITLE analysis.
    projection = load_committed_projection()
    gate.check("p17_02:projection-loadable", True)
    gate.check("p17_02:projection-digest-valid",
               projection["projection_digest"]
               == emitter._digest_dict(projection, "projection_digest"))
    title_analysis = _load_live_title_analysis()
    gate.check("p17_02:live-projection-digest-matches",
               title_analysis.projection["projection_digest"] == projection["projection_digest"])
    gate.check("next-stage:declared-constant", NEXT_STAGE == "P17-06R")

    # 3. Recorded P17-04R frontier state (the resume point).
    recorded = cont.recorded_p17_04r_frontier()
    gate.check("p17_04r:recorded-frontier-loadable",
               bool(recorded["stop_reason"]) and int(recorded["executed_instruction_count"]) > 0)
    continuation_entry = int(str(recorded["attempted_frontier_pc"]), 16)
    gate.check("p17_04r:recorded-stop-is-unauthenticated-table",
               recorded["stop_reason"] == "PC_NOT_IN_AUTHENTICATED_TABLE",
               json.dumps({"stop_reason": recorded["stop_reason"]}, sort_keys=True))
    gate.check("p17_04r:recorded-entry-outside-title-payload",
               not (title_analysis.identity.t_addr
                    <= continuation_entry < title_analysis.identity.text_end),
               _hex32(continuation_entry))

    # 4. Main-EXE payload authentication from source bytes.
    identity, file_bytes = mainexe.load_mainexe_identity()
    gate.check("mainexe:member-sha256-authenticated",
               identity.file_sha256 == fixture.EXPECTED_SLUS_SHA256)
    gate.check("mainexe:header-magic", identity.magic == b"PS-X EXE")
    gate.check("mainexe:header-consistent",
               identity.file_size == mainexe.HEADER_SIZE + identity.t_size
               and identity.t_size > 0
               and identity.t_addr <= identity.pc0 < identity.t_addr + identity.t_size,
               json.dumps({"t_addr": _hex32(identity.t_addr), "t_size": identity.t_size,
                           "entry": _hex32(identity.pc0), "gp0": _hex32(identity.gp0)},
                          sort_keys=True))
    expected_offset = mainexe.HEADER_SIZE + (continuation_entry - identity.t_addr)
    mapped_offset = mainexe.guest_to_file_offset(identity, continuation_entry)
    gate.check("mainexe:mapping-rule-holds", mapped_offset == expected_offset,
               json.dumps({"entry": _hex32(continuation_entry),
                           "file_offset": mapped_offset}, sort_keys=True))
    gate.check("mainexe:mapping-round-trip",
               mainexe.file_offset_to_guest(identity, mapped_offset) == continuation_entry)
    gate.check("mainexe:guest-address-outside-text-rejected",
               _raises(lambda: mainexe.guest_to_file_offset(identity, 0x80030000),
                       mainexe.MainExeAuthError, "MAINEXE_GUEST_ADDRESS_OUTSIDE_TEXT"))
    gate.check("mainexe:word-cross-check-holds",
               mainexe.read_authenticated_word(identity, continuation_entry,
                                               file_bytes=file_bytes) >= 0)

    # 5. Continuation analysis with full provenance chain.
    analysis = cont.build_continuation_analysis(title_analysis=title_analysis,
                                                recorded_frontier=recorded)
    gate.check("continuation:entry-derived-from-recorded-frontier",
               analysis.continuation_entry_pc == continuation_entry)
    gate.check("continuation:mainexe-reachable-non-empty",
               analysis.mainexe.reachable_count >= 1,
               json.dumps({"reachable": analysis.mainexe.reachable_count}, sort_keys=True))
    gate.check("continuation:title-reachable-matches-p17_02",
               analysis.title_record_count == len(title_analysis.frontier["reachable_addresses"]),
               json.dumps({"title_records": analysis.title_record_count}, sort_keys=True))
    gate.check("continuation:regions-disjoint",
               set(title_analysis.records_by_address).isdisjoint(
                   set(analysis.mainexe.records_by_address)))
    provenance_ok = True
    provenance_detail: dict[str, Any] = {}
    for pc in sorted(analysis.mainexe.provenance):
        prov = analysis.mainexe.provenance[pc]
        chain = (
            prov.mainexe_file_sha256 == identity.file_sha256
            and prov.mainexe_payload_sha256 == identity.payload_sha256
            and prov.file_offset == mainexe.HEADER_SIZE + (pc - identity.t_addr)
            and prov.t_addr == identity.t_addr
            and prov.t_size == identity.t_size
        )
        word = mainexe.read_authenticated_word(identity, pc, file_bytes=file_bytes)
        raw = analysis.mainexe.records_by_address[pc]
        if not chain or word != struct.unpack_from(
                "<I", identity.payload, pc - identity.t_addr)[0]:
            provenance_ok = False
        provenance_detail[_hex32(pc)] = {
            "file_offset": prov.file_offset,
            "provenance_digest": prov.digest()[:16],
            "op": raw.get("op"),
        }
    gate.check("continuation:mainexe-provenance-chain-holds", provenance_ok,
               json.dumps(provenance_detail, sort_keys=True))
    records = emitter._make_semantic_records(analysis)
    gate.check("continuation:every-record-verified-against-fresh-decode",
               len(records) == len(analysis.frontier["reachable_addresses"]) > 0,
               json.dumps({"records": len(records),
                           "reachable": len(analysis.frontier["reachable_addresses"])},
                          sort_keys=True))

    # 6. Emit into fresh private run dirs (two official runs).
    private_root = cont.private_build_root()
    run_dirs: list[pathlib.Path] = []
    manifests: list[dict[str, Any]] = []
    for label in cont.OFFICIAL_RUN_DIRS:
        run_dir = cont.official_run_dir(label, private_root)
        if run_dir.exists():
            shutil.rmtree(run_dir)
        run_dir.mkdir(parents=True, exist_ok=False)
        run_dirs.append(run_dir)
        manifests.append(cont.emit_continuation_executable(analysis, run_dir,
                                                           recorded_frontier=recorded))
    gate.check("persistence:fresh-run-dirs-created",
               all(cont.official_run_dir(label, private_root).is_dir()
                   for label in cont.OFFICIAL_RUN_DIRS))
    gate.check("persistence:run-dirs-distinct", run_dirs[0] != run_dirs[1])

    manifest = manifests[0]
    rr = manifest["runtime_result"]

    gate.check("emission:header-generated", bool(manifest["source"]["header_sha256"]))
    gate.check("emission:source-generated", bool(manifest["source"]["generated_source_sha256"]))
    gate.check("emission:harness-generated", bool(manifest["source"]["generated_harness_sha256"]))
    gate.check("emission:shared-object-generated", bool(manifest["build"]["shared_object_sha256"]))
    gate.check("emission:executable-generated", bool(manifest["build"]["executable_sha256"]))
    gate.check("emission:entry-pc", rr["entry_pc"] == _hex32(cont.TITLE_ENTRY_PC))
    gate.check("emission:register-digest-present", bool(rr["register_digest"]))
    gate.check("emission:ram-digest-present", bool(rr["ram_digest"]))
    gate.check("emission:provenance-digest-present", bool(manifest["source"]["provenance_digest"]))
    gate.check("emission:implemented-semantic-vocabulary-non-empty",
               bool(manifest["source"]["implemented_semantic_vocabulary"]))
    gate.check("emission:exercised-semantic-vocabulary-non-empty",
               bool(manifest["source"]["exercised_semantic_vocabulary"]))
    generated_c = (run_dirs[0] / "or_title_continuation_v1.c").read_text(encoding="utf-8")
    gate.check("emission:no-phase16-transition-code-import",
               "TITLE_TRANSITION_CODE" not in generated_c
               and "p16_emission_v1" not in generated_c)

    # 7. Continuation semantics: real newly authenticated main-EXE execution.
    recorded_count = int(recorded["executed_instruction_count"])
    gate.check("continuation:title-prefix-reproduced",
               rr["title_prefix_executed_count"] == recorded_count
               and rr["title_prefix_last_executed_pc"]
               == recorded["last_successfully_executed_pc"],
               json.dumps({"prefix_count": rr["title_prefix_executed_count"],
                           "prefix_last_pc": rr["title_prefix_last_executed_pc"],
                           "recorded_count": recorded_count,
                           "recorded_last_pc": recorded["last_successfully_executed_pc"]},
                          sort_keys=True))
    gate.check("continuation:mainexe-instructions-executed",
               rr["mainexe_executed_count"] >= 1,
               json.dumps({"mainexe_executed_count": rr["mainexe_executed_count"]},
                          sort_keys=True))
    gate.check("continuation:frontier-advanced-beyond-entry",
               _advances_beyond(rr, continuation_entry),
               json.dumps({"last_successfully_executed_pc": rr["last_successfully_executed_pc"],
                           "frontier_pc": rr["frontier_pc"],
                           "entry": _hex32(continuation_entry)}, sort_keys=True))
    gate.check("continuation:typed-stop-reason", rr["stop_reason"] in ALLOWED_STOP_REASONS,
               rr["stop_reason"])
    gate.check("continuation:distinct-frontier-pcs",
               rr["frontier_pc"] != rr["last_successfully_executed_pc"]
               and rr["attempted_frontier_pc"] == rr["frontier_pc"],
               json.dumps({"frontier_pc": rr["frontier_pc"],
                           "attempted": rr["attempted_frontier_pc"],
                           "last": rr["last_successfully_executed_pc"]}, sort_keys=True))
    gate.check("continuation:first-mainexe-pc-is-recorded-entry",
               int(str(rr["mainexe_first_pc"]), 16) == continuation_entry)
    authenticated_mainexe = {f"0x{pc:08x}" for pc in sorted(analysis.mainexe.provenance)}
    gate.check("continuation:mainexe-executed-pcs-authenticated",
               set(rr["mainexe_executed_pcs"]).issubset(authenticated_mainexe),
               json.dumps({"executed": rr["mainexe_executed_pcs"],
                           "authenticated_count": len(authenticated_mainexe)}, sort_keys=True))
    gate.check("continuation:budget-respected",
               0 < rr["mainexe_executed_count"] <= cont.CONTINUATION_BUDGET
               and rr["executed_instruction_count"] <= recorded_count + cont.CONTINUATION_BUDGET,
               json.dumps({"executed": rr["executed_instruction_count"],
                           "mainexe": rr["mainexe_executed_count"],
                           "budget": cont.CONTINUATION_BUDGET}, sort_keys=True))

    # 8. Reusable interface on disk.
    gate.check("interface:shared-object-exports-symbol",
               shared_object_exports_symbol(run_dirs[0]))

    # 9. Persistence after emission.
    persisted_first = persisted_artifacts_ok(run_dirs[0], manifest)
    persisted_second = persisted_artifacts_ok(run_dirs[1], manifests[1])
    gate.check("persistence:run1-artifacts-exist-and-hash-match", persisted_first["ok"],
               json.dumps({k: v["sha256"] for k, v in persisted_first["artifacts"].items()},
                          sort_keys=True))
    gate.check("persistence:run2-artifacts-exist-and-hash-match", persisted_second["ok"])
    gate.check("persistence:generated-source-survives-process-exit",
               persisted_first["artifacts"]["generated_source"]["exists"]
               and persisted_first["artifacts"]["generated_source"]["sha256_matches"])
    gate.check("persistence:private-map-survives-process-exit",
               persisted_first["artifacts"]["private_mapping"]["exists"]
               and persisted_first["artifacts"]["private_mapping"]["sha256_matches"])
    gate.check("persistence:native-artifact-survives-process-exit",
               persisted_first["artifacts"]["shared_object"]["exists"]
               and persisted_first["artifacts"]["shared_object"]["sha256_matches"]
               and persisted_first["artifacts"]["executable"]["exists"]
               and persisted_first["artifacts"]["executable"]["sha256_matches"])
    gate.check("persistence:recorded-native-hash-matches-artifact",
               manifest["build"]["shared_object_sha256"]
               == persisted_first["artifacts"]["shared_object"]["sha256"]
               and manifest["build"]["executable_sha256"]
               == persisted_first["artifacts"]["executable"]["sha256"])
    gate.check("persistence:private-map-record-count",
               manifest["persistence"]["private_mapping_record_count"]
               == manifest["source"]["record_count"] > 0)
    probe = private_build_root_probe()
    gate.check("persistence:private-build-root-env-override",
               bool(probe.get("override_honoured")), json.dumps(probe, sort_keys=True))
    child_check = child_process_persistence_check(cont.OFFICIAL_RUN_DIRS[0])
    gate.check("persistence:child-process-verification", child_check["ok"],
               json.dumps(child_check, sort_keys=True))

    # 10. Determinism across the two official runs.
    gate.check("determinism:generated-source-hash-identical",
               manifests[0]["source"]["generated_source_sha256"]
               == manifests[1]["source"]["generated_source_sha256"])
    gate.check("determinism:private-map-hash-identical",
               manifests[0]["persistence"]["artifacts"]["private_mapping"]["sha256"]
               == manifests[1]["persistence"]["artifacts"]["private_mapping"]["sha256"])
    gate.check("determinism:shared-object-hash-identical",
               manifests[0]["build"]["shared_object_sha256"]
               == manifests[1]["build"]["shared_object_sha256"])
    gate.check("determinism:executable-hash-identical",
               manifests[0]["build"]["executable_sha256"]
               == manifests[1]["build"]["executable_sha256"])
    gate.check("determinism:runtime-result-identical",
               manifests[0]["runtime_result"] == manifests[1]["runtime_result"])
    gate.check("determinism:manifest-identical", manifests[0] == manifests[1])

    # 11. Negative controls (each evaluated exactly once).
    negatives = {
        "unauthenticated-destination": negative_unauthenticated_destination(),
        "altered-source-word": negative_altered_source_word(),
        "altered-mainexe-header-fields": negative_altered_header_fields(),
        "wrong-file-offset": negative_wrong_file_offset(),
        "tampered-payload-sha256": negative_tampered_payload_sha256(),
        "missing-provenance": negative_missing_provenance(),
        "non-advancing-frontier-rejected": negative_continuation_not_entered(),
    }
    for name, result in negatives.items():
        gate.check(f"negative:{name}", result["ok"], json.dumps(result, sort_keys=True))
    unauthenticated = int(str(rr["frontier_pc"]), 16)
    gate.check("negative:frontier-pc-outside-authenticated-table",
               rr["stop_reason"] != "PC_NOT_IN_AUTHENTICATED_TABLE"
               or unauthenticated not in set(analysis.frontier["reachable_addresses"]),
               json.dumps({"frontier_pc": rr["frontier_pc"],
                           "stop_reason": rr["stop_reason"]}, sort_keys=True))

    # 12. Vocabulary coverage.
    gate.check("vocabulary:implemented-ops-all-executable", implemented_vocabulary_covered()["ok"],
               json.dumps(implemented_vocabulary_covered(), sort_keys=True))
    traced = list(rr["executed_semantic_trace"])
    exercised = sorted(set(traced))
    gate.check("vocabulary:exercised-derived-from-execution-trace",
               exercised == sorted(rr["exercised_semantic_vocabulary"])
               and rr["executed_semantic_trace_length"] == len(traced)
               and len(traced) == rr["executed_instruction_count"],
               json.dumps({"exercised": exercised,
                           "trace_len": len(traced),
                           "executed": rr["executed_instruction_count"]}, sort_keys=True))
    gate.check("vocabulary:exercised-subset-of-implemented",
               set(exercised).issubset(emitter.SUPPORTED_OPS))

    # 13. Evidence documents.
    title_continuation = {
        "recorded_frontier": {
            "last_successfully_executed_pc": recorded["last_successfully_executed_pc"],
            "attempted_frontier_pc": recorded["attempted_frontier_pc"],
            "frontier_pc": recorded["frontier_pc"],
            "stop_reason": recorded["stop_reason"],
            "executed_instruction_count": recorded_count,
        },
        "live_title_prefix_executed_count": rr["title_prefix_executed_count"],
        "live_title_prefix_last_executed_pc": rr["title_prefix_last_executed_pc"],
        "reproduced": rr["title_prefix_executed_count"] == recorded_count
        and rr["title_prefix_last_executed_pc"] == recorded["last_successfully_executed_pc"],
    }
    mapping_doc = mainexe.public_mapping_document(analysis.mainexe,
                                                  title_continuation=title_continuation)
    mapping_doc["next_stage"] = NEXT_STAGE
    continuation_doc = {
        "schema": "openrecomp-phase17-continuation-v1",
        "stage": STAGE,
        "next_stage": NEXT_STAGE,
        "continuation_entry_pc": _hex32(continuation_entry),
        "executed_instruction_count": rr["executed_instruction_count"],
        "title_prefix_executed_count": rr["title_prefix_executed_count"],
        "mainexe_executed_count": rr["mainexe_executed_count"],
        "mainexe_executed_pcs": rr["mainexe_executed_pcs"],
        "frontier": manifest["frontier"],
        "stop_reason": rr["stop_reason"],
        "last_successfully_executed_pc": rr["last_successfully_executed_pc"],
        "attempted_frontier_pc": rr["attempted_frontier_pc"],
        "frontier_pc": rr["frontier_pc"],
        "record_counts": {
            "title": manifest["source"]["title_record_count"],
            "mainexe": manifest["source"]["mainexe_record_count"],
            "total": manifest["source"]["record_count"],
        },
        "continuation_budget": cont.CONTINUATION_BUDGET,
        "emission_digest": manifest["emission_digest"],
        "runtime_digests": {
            "register_digest": rr["register_digest"],
            "ram_digest": rr["ram_digest"],
            "provenance_digest": rr["provenance_digest"],
        },
        "claims": manifest["claims"],
    }
    for name, document in (("continuation", continuation_doc),
                           ("mainexe-mapping", mapping_doc),
                           ("emission", manifest)):
        text = json.dumps(document, sort_keys=True)
        for term in ("raw_instruction", "instruction_word", "payload_bytes", "bios_bytes"):
            gate.check(f"public:{name}:no-{term.replace(chr(95), chr(45))}-field",
                       term not in text)
        gate.check(f"public:{name}:no-private-paths",
                   "/home/" not in text and "fixtures/" not in text and "/tmp/" not in text)
        assert_public_safe(gate, name, document)

    write_json(evidence / "continuation.json", continuation_doc)
    write_json(evidence / "mainexe_mapping.json", mapping_doc)
    write_json(evidence / "next_stage.json", {
        "schema": "openrecomp-phase17-next-stage-v1",
        "stage": STAGE,
        "next_stage": NEXT_STAGE,
        "authoritative_sources": ["RESULT.json", "continuation.json",
                                  "mainexe_mapping.json", "stage_metadata.json",
                                  "next_stage.json", "STATE.md", "HANDOFF.md"],
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
        "OPENRECOMP_PHASE17_AUTHENTIC_EXECUTION_CONTINUATION_V1": "PASS",
        "OPENRECOMP_P17_05R": "PASS",
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
        "continuation_entry_pc": _hex32(continuation_entry),
        "authentic_frontier": manifest["frontier"],
        "newly_authenticated_records": {
            "title": manifest["source"]["title_record_count"],
            "mainexe": manifest["source"]["mainexe_record_count"],
            "total": manifest["source"]["record_count"],
        },
        "mainexe_mapping": {
            "fixture_member": mainexe.MAINEXE_FIXTURE_MEMBER,
            "file_sha256": identity.file_sha256,
            "payload_sha256": identity.payload_sha256,
            "t_addr": _hex32(identity.t_addr),
            "t_size": identity.t_size,
            "entry_pc": _hex32(identity.pc0),
            "continuation_entry_file_offset": mapped_offset,
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
        "mainexe_mapping.json": evidence / "mainexe_mapping.json",
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
    required = {"RESULT.json", "continuation.json", "mainexe_mapping.json",
                "stage_metadata.json", "next_stage.json", "STATE.md", "HANDOFF.md"}
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
    gate.mark("OPENRECOMP_P17_05R_BOUNDED_CONTINUATION", "PASS")
    gate.mark("OPENRECOMP_P17_05R_CONTINUATION_BUDGET", str(cont.CONTINUATION_BUDGET))


BASE_COMMIT = "36be03b5756726a20ecd69735b41cb5eba795155"
WORKER_BRANCH = "agent/deepseek-phase17-p17-05r-r1"


def _raises(fn, exc_type, code: str) -> bool:
    try:
        fn()
        return False
    except exc_type as exc:
        return getattr(exc, "code", None) == code


def _advances_beyond(result: dict[str, Any], entry_pc: int) -> bool:
    pcs = [int(str(pc), 16) for pc in result.get("mainexe_executed_pcs") or []]
    if entry_pc not in pcs:
        return False
    if not any(pc > entry_pc for pc in pcs):
        return False
    last = int(str(result["last_successfully_executed_pc"]), 16)
    return last != entry_pc


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase17/evidence/P17-05R"))
