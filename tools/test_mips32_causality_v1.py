#!/usr/bin/env python3
# Phase 7 causality gate: mutating a single immediate changes the observable result.
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import os
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from mips32_oracle_v1 import simulate

_ROOT = _TOOLS.parent
_ELF = _ROOT / 'artifacts' / 'mips32_translation_v1' / 'TRANSLATION_FIXTURE.elf'
_CLOSURE = _ROOT / 'artifacts' / 'mips32_translation_evidence_closure_v1'

# Mutation: ELF byte offset 84 is the immediate LSB of the first instruction
# addiu r2,r0,7.  Changing 0x07 to 0x11 makes it addiu r2,r0,17 -> r2=55.
_MUT_OFFSET = 84
_MUT_ORIGINAL_BYTE = 0x07
_MUT_NEW_BYTE = 0x11
_CANON_R2 = 45
_MUT_R2 = 55


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    if not _ELF.exists():
        from build_mips32_translation_fixture import build
        build(_ELF)

    canon_bytes = _ELF.read_bytes()
    canon_sha = _sha256(canon_bytes)

    actual_byte = canon_bytes[_MUT_OFFSET]
    if actual_byte != _MUT_ORIGINAL_BYTE:
        print(
            f'FAIL: ELF byte {_MUT_OFFSET} = 0x{actual_byte:02x}, '
            f'expected 0x{_MUT_ORIGINAL_BYTE:02x}',
            file=sys.stderr,
        )
        return 1

    mut_bytes = bytearray(canon_bytes)
    mut_bytes[_MUT_OFFSET] = _MUT_NEW_BYTE
    mut_bytes = bytes(mut_bytes)
    mut_sha = _sha256(mut_bytes)

    canon_result = simulate(str(_ELF))
    cr2 = canon_result['r2']
    cr3 = canon_result['r3']
    cops = canon_result['operations']
    print(f'Canon: r2={cr2} r3={cr3} ops={cops}')

    with tempfile.NamedTemporaryFile(suffix='.elf', delete=False) as tf:
        tf.write(mut_bytes)
        tmp_path = tf.name
    try:
        mut_result = simulate(tmp_path)
    finally:
        os.unlink(tmp_path)
    mr2 = mut_result['r2']
    mr3 = mut_result['r3']
    mops = mut_result['operations']
    print(f'Mut:   r2={mr2} r3={mr3} ops={mops}')

    if canon_result['r2'] != _CANON_R2:
        print(f'FAIL: canon r2={cr2} expected {_CANON_R2}')
        verdict = 'CAUSALITY_FAIL'
    elif mut_result['r2'] != _MUT_R2:
        print(f'FAIL: mut r2={mr2} expected {_MUT_R2}')
        verdict = 'CAUSALITY_FAIL'
    elif canon_result['r2'] == mut_result['r2']:
        print('FAIL: mutation did not change observable result')
        verdict = 'CAUSALITY_FAIL'
    else:
        verdict = 'CAUSALITY_PASS'

    _CLOSURE.mkdir(parents=True, exist_ok=True)
    result = {
        'status': verdict,
        'canon_sha256': canon_sha,
        'mut_sha256': mut_sha,
        'mut_description': 'ELF byte 84: 0x07->0x11 (addiu r2,r0,7 -> addiu r2,r0,17)',
        'canon_r2': canon_result['r2'],
        'mut_r2': mut_result['r2'],
        'canon_r3': canon_result['r3'],
        'mut_r3': mut_result['r3'],
    }
    (_CLOSURE / 'CAUSALITY_RESULT.json').write_text(
        json.dumps(result, indent=2), encoding='utf-8'
    )
    print(verdict)
    return 0 if verdict == 'CAUSALITY_PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
