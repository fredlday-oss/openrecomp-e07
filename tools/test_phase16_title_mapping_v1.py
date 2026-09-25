#!/usr/bin/env python3
"""Deterministic P16-02 Authentic TITLE fixture mapping gate."""

from __future__ import annotations

import hashlib
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase16/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p16_contracts_v1 as contract
from p16_gate_v1 import assert_public_safe, run_stage, write_json
from p16_title_mapping_v1 import MAPPING

STAGE = "P16-02"


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    fixture_dir = root.parents[1] / "fixtures" / "psx" / "hercules"
    bin_path = fixture_dir / "Disney's Hercules Action Game (USA).bin"
    gate.check("bin:exists", bin_path.is_file(), str(bin_path.name))

    # 1. ISO9660 Directory structure verification
    with bin_path.open("rb") as f:
        # PVD at LBA 16
        f.seek(16 * 2352 + 24)
        pvd = f.read(2048)
        gate.check("iso:pvd-id", pvd[1:6] == b"CD001", "CD001 standard identifier")
        root_dir = pvd[156:156 + 34]
        root_lba = int.from_bytes(root_dir[2:6], "little")

        # Root directory at LBA 22
        f.seek(root_lba * 2352 + 24)
        root_data = f.read(2048)
        ex_lba = None
        offset = 0
        while offset < len(root_data):
            rlen = root_data[offset]
            if rlen == 0:
                offset += 1
                continue
            entry = root_data[offset : offset + rlen]
            fid_len = entry[32]
            fid = entry[33 : 33 + fid_len].decode("ascii", errors="replace")
            if fid == "EX":
                ex_lba = int.from_bytes(entry[2:6], "little")
                break
            offset += rlen
        gate.check("iso:ex-dir-found", ex_lba == 87, f"EX dir LBA={ex_lba}")

        # EX directory at LBA 87
        f.seek(ex_lba * 2352 + 24)
        ex_data = f.read(2048)
        title_lba = None
        title_size = None
        offset = 0
        while offset < len(ex_data):
            rlen = ex_data[offset]
            if rlen == 0:
                offset += 1
                continue
            entry = ex_data[offset : offset + rlen]
            fid_len = entry[32]
            fid = entry[33 : 33 + fid_len].decode("ascii", errors="replace")
            if fid.startswith("TITLE"):
                title_lba = int.from_bytes(entry[2:6], "little")
                title_size = int.from_bytes(entry[10:14], "little")
                break
            offset += rlen
        gate.check("iso:title-file-found", title_lba == 88, f"TITLE LBA={title_lba}")
        gate.check("iso:title-file-size", title_size == 288768, f"TITLE size={title_size}")

    # 2. Extract header and payload using MAPPING
    header, payload = MAPPING.extract_header_and_payload(bin_path)
    gate.check("header:size", len(header) == 2048, str(len(header)))
    gate.check("payload:size", len(payload) == 286720, str(len(payload)))

    payload_hash = hashlib.sha256(payload).hexdigest()
    gate.check("payload:hash", payload_hash == contract.TITLE_PAYLOAD_SHA256, payload_hash)

    full_file = header + payload
    file_hash = hashlib.sha256(full_file).hexdigest()
    gate.check("file:hash", file_hash == MAPPING.file_sha256, file_hash)

    # 3. Verify PS-X EXE header fields
    magic = header[:8]
    gate.check("header:magic", magic == b"PS-X EXE", str(magic))
    pc0, gp0, t_addr, t_size, _, _, _, _, sp_addr, _ = struct.unpack("<10I", header[16:56])
    gate.check("header:pc0", pc0 == contract.TITLE_ENTRY_PC, f"0x{pc0:08x}")
    gate.check("header:t_addr", t_addr == contract.TITLE_TEXT_ADDR, f"0x{t_addr:08x}")
    gate.check("header:t_size", t_size == contract.TITLE_PAYLOAD_SIZE, str(t_size))
    gate.check("header:sp_addr", sp_addr == contract.TITLE_SP_ADDR, f"0x{sp_addr:08x}")

    # 4. Verify opcode at 0x800380a0 and reconcile historical discrepancy
    pc0_word = struct.unpack("<I", payload[8:12])[0]
    gate.check("payload:entry-word", pc0_word == contract.TITLE_FIRST_INSTR_WORD, f"0x{pc0_word:08x}")

    # Historical recon claimed 0x27bdffd8; prove it is at 0x80038ab4
    offset_27bd = payload.find(bytes.fromhex("d8ffbd27"))
    gate.check("discrepancy:historical-recon-reconciled", offset_27bd == 2588, f"offset={offset_27bd}")

    # 5. Output stage evidence
    mapping_doc = MAPPING.to_dict()
    write_json(evidence / "title_mapping.json", mapping_doc)
    assert_public_safe(gate, "title-mapping", mapping_doc, b"")

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase16-result-v1",
        "stage": STAGE,
        "status": "PASS",
        "evidence_class": "REPRESENTATIVE_TEST_RECORD",
        "markers": {
            contract.TITLE_FIXTURE_MAPPING_MARKER: "PASS",
            "OPENRECOMP_P16_02": "PASS",
            contract.INITIALIZATION_MARKER: "NOT_PROVEN",
            contract.FRAME_MARKER: "NOT_PROVEN",
            contract.PLAYABILITY_MARKER: "NOT_PROVEN",
            contract.GENERAL_MARKER: "NOT_PROVEN",
        },
        "next_stage": "P16-03",
    })

    gate.mark(contract.TITLE_FIXTURE_MAPPING_MARKER)
    gate.mark("OPENRECOMP_P16_02")
    gate.mark(contract.INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(contract.FRAME_MARKER, "NOT_PROVEN")
    gate.mark(contract.PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(contract.GENERAL_MARKER, "NOT_PROVEN")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase16/evidence/P16-02"))
