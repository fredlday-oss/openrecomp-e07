# OPENRECOMP Phase 1 — P1-35 Evidence

Stage: `P1-35` — 6502/NES regression + differential audit

Revision: working tree at HEAD `bd5f02f` (no commit created; additive untracked files).

## Scope delivered

- `tools/test_nes_regression_v1.py` (`OPENRECOMP_NES_REGRESSION_V1=PASS`):
  executable audit of the whole 6502/NES chain:
  - runs every NES gate script twice and requires byte-identical output:
    `test_nes6502_state_v1.py`, `test_nes6502_decode_v1.py`,
    `test_nes6502_semantics_v1.py`, `test_nes6502_lowering_v1.py`,
    `test_nes_rom_v1.py`, `test_nes_platform_v1.py`,
    `test_nes_headless_v1.py`, plus the frontend-contract boundary gate;
  - re-pins the frozen NES markers (state 10, semantics 102, lowering 12,
    rom 12, platform 10, headless 7) and the frozen headless differential
    result (`a=0xc6 x=0x0 sp=0xfd p=0xa4 pc=0x8032`) and platform protocol
    result (`ppuctrl=0x7e ppumask=0x1e vram=1122 oam_dma=1 controller=0x41
    apu=0x1f`).
- No new semantics; this gate only re-pins frozen evidence.

## Files changed (this stage)

Added:
- `tools/test_nes_regression_v1.py`

Modified:
- `tools/phase1_host_gates_v1.py` (registered `nes-regression-v1`, area `nes`)
- `SOURCE_SHA256SUMS.txt` (regenerated with `python update_sums.py`)

## Verification commands and results

```text
python tools/test_nes_regression_v1.py
OPENRECOMP_NES_REGRESSION_V1=PASS tests=16
(8 chain/boundary scripts run twice byte-identical + 8 frozen markers)

python tools/phase1_host_gates_v1.py
OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
```

No pre-existing gate was weakened or removed.

## Semantic assumptions / documented sources

- This is a determinism/regression audit only; all semantic sources are those
  recorded in the P1-30..P1-34 evidence records.

## Limitations / deferred

- Unofficial opcodes, cycle timing, non-NROM mappers and cycle-perfect
  PPU/APU remain deferred per SCOPE and fail closed.

## Verdict

`PASS`
