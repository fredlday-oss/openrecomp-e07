#!/usr/bin/env python3
"""OpenRecomp Phase-16 A0:0x43 Exec contract definition and validation V1.

Mechanically models the exact contract of A0:0x43 Exec reached by Hercules:
- Call site: 0x80012CB4 (jal 0x80015B80) inside title_handoff_and_exec (0x80012C18)
- Wrapper site: 0x80015B80 (jump to A0 vector index 0x43)
- Vector site: 0x80015B84 (jr t2 with t2=0xA0, t1=0x43)
- Arguments: a0 = struct EXEC* (0x80034E80), a1 = 0, a2 = 0
- Consumed header fields: pc0, t_addr, t_size, sp_addr
- Target entry PC: 0x800380A0
- Destination RAM: [0x80038098, 0x8007E098)
- Size: 286,720 bytes (140 Mode 2 Form 1 sectors)
- Return semantics: does not return (control transferred to pc0)
"""

from __future__ import annotations

import dataclasses
import struct
from typing import Any

from p16_contracts_v1 import (
    EXEC_CALL_SITE,
    EXEC_INDIRECT_SITE,
    EXEC_STRUCT_ADDR,
    EXEC_WRAPPER_SITE,
    TITLE_ENTRY_PC,
    TITLE_FIRST_INSTR_WORD,
    TITLE_GP0,
    TITLE_PAYLOAD_SHA256,
    TITLE_PAYLOAD_SIZE,
    TITLE_SP_ADDR,
    TITLE_TEXT_ADDR,
)


@dataclasses.dataclass(frozen=True)
class ExecContract:
    call_site: int = EXEC_CALL_SITE
    wrapper_site: int = EXEC_WRAPPER_SITE
    indirect_site: int = EXEC_INDIRECT_SITE
    struct_addr: int = EXEC_STRUCT_ADDR
    expected_pc0: int = TITLE_ENTRY_PC
    expected_t_addr: int = TITLE_TEXT_ADDR
    expected_t_size: int = TITLE_PAYLOAD_SIZE
    expected_sp_addr: int = TITLE_SP_ADDR
    expected_gp0: int = TITLE_GP0
    expected_payload_sha256: str = TITLE_PAYLOAD_SHA256
    expected_first_word: int = TITLE_FIRST_INSTR_WORD

    def validate_struct_exec(self, raw_bytes: bytes) -> tuple[bool, str]:
        """Validate an authentic 60-byte struct EXEC from guest memory."""
        if len(raw_bytes) < 40:
            return False, f"struct EXEC too small: {len(raw_bytes)} < 40"
        pc0, gp0, t_addr, t_size, d_addr, d_size, b_addr, b_size, sp_addr, sp_size = struct.unpack(
            "<10I", raw_bytes[:40]
        )
        if pc0 != self.expected_pc0:
            return False, f"pc0 mismatch: 0x{pc0:08x} != 0x{self.expected_pc0:08x}"
        if t_addr != self.expected_t_addr:
            return False, f"t_addr mismatch: 0x{t_addr:08x} != 0x{self.expected_t_addr:08x}"
        if t_size != self.expected_t_size:
            return False, f"t_size mismatch: {t_size} != {self.expected_t_size}"
        if sp_addr != self.expected_sp_addr:
            return False, f"sp_addr mismatch: 0x{sp_addr:08x} != 0x{self.expected_sp_addr:08x}"
        return True, "VALID"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "openrecomp-phase16-exec-contract-v1",
            "call_site": f"0x{self.call_site:08x}",
            "wrapper_site": f"0x{self.wrapper_site:08x}",
            "indirect_site": f"0x{self.indirect_site:08x}",
            "struct_addr": f"0x{self.struct_addr:08x}",
            "consumed_fields": {
                "pc0": f"0x{self.expected_pc0:08x}",
                "gp0": f"0x{self.expected_gp0:08x}",
                "t_addr": f"0x{self.expected_t_addr:08x}",
                "t_size": self.expected_t_size,
                "sp_addr": f"0x{self.expected_sp_addr:08x}",
            },
            "payload_sha256": self.expected_payload_sha256,
            "entry_word": f"0x{self.expected_first_word:08x}",
            "transfer_semantics": "SYNCHRONOUS_TRANSFER_TO_PC0",
            "fail_closed_on_mismatch": True,
        }


CONTRACT = ExecContract()
