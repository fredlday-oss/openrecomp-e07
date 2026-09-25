#!/usr/bin/env python3
"""Deterministic P16-01 Exec contract reconstruction gate."""

from __future__ import annotations

import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase16/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p16_contracts_v1 as contract
from p16_exec_contract_v1 import CONTRACT
from p16_gate_v1 import assert_public_safe, run_stage, write_json

STAGE = "P16-01"


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    # 1. Read SLUS_005.29 fixture binary
    fixture_dir = root.parents[1] / "fixtures" / "psx" / "hercules"
    slus_path = fixture_dir / "SLUS_005.29"
    gate.check("slus:file-exists", slus_path.is_file(), str(slus_path.name))
    slus_data = slus_path.read_bytes()
    t_addr, t_size = struct.unpack("<2I", slus_data[24:32])
    text = slus_data[2048:]

    def read_word(addr: int) -> int:
        offset = addr - t_addr
        return struct.unpack("<I", text[offset : offset + 4])[0]

    # 2. Mechanically verify Exec call site at 0x80012cb4
    # 0x80012cb4: jal 0x80015b80
    w_jal = read_word(0x80012CB4)
    gate.check("exec:call-site-jal", (w_jal >> 26) == 3 and ((w_jal & 0x03FFFFFF) << 2 | 0x80000000) == 0x80015B80,
               f"0x{w_jal:08x}")
    # 0x80012cac: addiu a0, s1, 4 (where s1 = 0x80034e7c, so a0 = 0x80034e80)
    w_a0 = read_word(0x80012CAC)
    gate.check("exec:arg-a0-struct", w_a0 == 0x26240004, f"0x{w_a0:08x}")
    # 0x80012cb0: addu a1, zero, zero (a1 = 0)
    w_a1 = read_word(0x80012CB0)
    gate.check("exec:arg-a1-zero", w_a1 == 0x00002821, f"0x{w_a1:08x}")
    # 0x80012cb8: addu a2, zero, zero (a2 = 0)
    w_a2 = read_word(0x80012CB8)
    gate.check("exec:arg-a2-zero", w_a2 == 0x00003021, f"0x{w_a2:08x}")

    # 3. Mechanically verify wrapper at 0x80015b80
    # 0x80015b80: addiu t2, zero, 160 (0xA0)
    w_w0 = read_word(0x80015B80)
    gate.check("wrapper:addiu-a0", w_w0 == 0x240A00A0, f"0x{w_w0:08x}")
    # 0x80015b84: jr t2
    w_w1 = read_word(0x80015B84)
    gate.check("wrapper:jr-t2", w_w1 == 0x01400008, f"0x{w_w1:08x}")
    # 0x80015b88: addiu t1, zero, 67 (0x43)
    w_w2 = read_word(0x80015B88)
    gate.check("wrapper:addiu-43", w_w2 == 0x24090043, f"0x{w_w2:08x}")

    # 4. Mechanically verify predecessor steps in 0x80012c18
    # 0x80012c74: jal 0x80026cf8 (memcpy)
    w_memcpy = read_word(0x80012C74)
    gate.check("prep:jal-memcpy", (w_memcpy >> 26) == 3 and ((w_memcpy & 0x03FFFFFF) << 2 | 0x80000000) == 0x80026CF8,
               f"0x{w_memcpy:08x}")
    # 0x80012c94: jal 0x80015b90 (FlushCache)
    w_flush = read_word(0x80012C94)
    gate.check("prep:jal-flushcache", (w_flush >> 26) == 3 and ((w_flush & 0x03FFFFFF) << 2 | 0x80000000) == 0x80015B90,
               f"0x{w_flush:08x}")
    # 0x80012ca4: jal 0x80015bc0 (SetSp)
    w_setsp = read_word(0x80012CA4)
    gate.check("prep:jal-setsp", (w_setsp >> 26) == 3 and ((w_setsp & 0x03FFFFFF) << 2 | 0x80000000) == 0x80015BC0,
               f"0x{w_setsp:08x}")

    # 5. Verify against authentic Sector 88 header from BIN fixture
    bin_path = fixture_dir / "Disney's Hercules Action Game (USA).bin"
    gate.check("bin:file-exists", bin_path.is_file(), str(bin_path.name))
    with bin_path.open("rb") as f:
        f.seek(88 * 2352 + 24)
        sec88_user = f.read(2048)
    gate.check("sec88:magic", sec88_user[:8] == b"PS-X EXE", sec88_user[:8].decode("ascii", errors="replace"))

    valid_struct, err_msg = CONTRACT.validate_struct_exec(sec88_user[16:56])
    gate.check("sec88:struct-exec-valid", valid_struct, err_msg)

    # 6. Save contract evidence
    contract_doc = CONTRACT.to_dict()
    write_json(evidence / "exec_contract.json", contract_doc)
    assert_public_safe(gate, "exec-contract", contract_doc, b"")

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase16-result-v1",
        "stage": STAGE,
        "status": "PASS",
        "evidence_class": "REPRESENTATIVE_TEST_RECORD",
        "markers": {
            contract.EXEC_CONTRACT_MARKER: "PASS",
            "OPENRECOMP_P16_01": "PASS",
            contract.INITIALIZATION_MARKER: "NOT_PROVEN",
            contract.FRAME_MARKER: "NOT_PROVEN",
            contract.PLAYABILITY_MARKER: "NOT_PROVEN",
            contract.GENERAL_MARKER: "NOT_PROVEN",
        },
        "next_stage": "P16-02",
    })

    gate.mark(contract.EXEC_CONTRACT_MARKER)
    gate.mark("OPENRECOMP_P16_01")
    gate.mark(contract.INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(contract.FRAME_MARKER, "NOT_PROVEN")
    gate.mark(contract.PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(contract.GENERAL_MARKER, "NOT_PROVEN")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase16/evidence/P16-01"))
