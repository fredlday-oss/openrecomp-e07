# Phase 1 Session Handoff

STATUS: `COMPLETE` (written 2026-09-13; P1-99 PASS; Phase 1 final verdict emitted)

## Phase-1 outcome

- OVERALL_VERDICT: `OPENRECOMP_PHASE1_MULTIARCH_PROOF=PASS`
- CURRENT_STAGE: `P1-99` (`PASS`), LAST_PASSED_STAGE: `P1-99`.
- Every required `SCOPE.md` item is covered by a PASS stage with evidence:
  P1-00..P1-03, P1-10..P1-17, P1-20..P1-24, P1-30..P1-35, P1-90, P1-91,
  P1-99. Evidence index: `.openrecomp-phase1/evidence/INDEX.md`.

## Final verification (authoritative)

```text
python tools/phase1_host_gates_v1.py   (full harness, run twice)
RUN1 EXIT=0 TIME=00:06:23.8981181  RUN2 EXIT=0 TIME=00:06:21.1210213
OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
RUN1/RUN2 SHA256=3fbb23d3d0174a7efe381d70a1636987c4355e5b9837d67c8dcb3e158a67f594
OPENRECOMP_P1_90_HARNESS_DETERMINISM=PASS
OPENRECOMP_P1_90_NO_RUN2_SIDE_EFFECTS=PASS
```

The two skipped gates (`e07-hardened-end-to-end`, `external-repro-v1`) require
`clang`/`gcc` (and POSIX for the reviewer gate), which are absent on this host.
A skip is never counted as a pass.

## What Phase 1 now supports

- Architecture-neutral frontend contract / decoded-instruction boundary /
  CFG / IR V1 lowering / deterministic harness (shared/core).
- Game Boy + Game Boy Color (SM83): full documented base+CB decode, semantics,
  control flow, IR, ROM/MBC1 ingestion, timer/joypad/interrupt contracts, GBC
  mode selection, headless differential proof.
- Master System (Z80): full documented decode/semantics/control flow, Sega
  mapper + memory map + VDP/PSG/controller port contracts, headless proof.
- NES (6502 family): 151 official opcodes, documented semantics (NES 2A03 has
  no decimal mode), reset/IRQ/NMI entry, iNES/NES 2.0 ingestion, NROM mapper,
  CPU PPU/APU/controller contracts, headless proof.
- Established RV32I/E07 + MIPS32 paths remain green (no PS2/R5900 code exists
  in this tree).

## Run/test commands

```text
python update_sums.py                      # after tools/*.py, adapters/*.py, contracts/*.json, schemas/*.json edits
python tools/phase1_host_gates_v1.py       # full harness (~6m20s); --only <substr> for one chain
python tools/test_nes_regression_v1.py     # per-architecture audit pattern
```

## Changed files (working tree, uncommitted; HEAD bd5f02f)

All NES stage files (P1-30..P1-35): `adapters/nes6502.py`,
`tools/nes6502_reference_v1.py`, `tools/test_nes6502_state_v1.py`,
`tools/test_nes6502_decode_v1.py`, `tools/test_nes6502_semantics_v1.py`,
`tools/nes6502_frontend_v1.py`, `tools/test_nes6502_lowering_v1.py`,
`tools/nes_rom_v1.py`, `tools/test_nes_rom_v1.py`, `tools/nes_platform_v1.py`,
`tools/test_nes_platform_v1.py`, `tools/nes_headless_v1.py`,
`tools/test_nes_headless_v1.py`, `tools/test_nes_regression_v1.py`,
`tools/phase1_host_gates_v1.py`, `SOURCE_SHA256SUMS.txt`, plus all earlier-stage
files listed in `STATE.md`.

## Git status (short)

Branch `main`, HEAD `bd5f02f`, no commit created this session; nothing
destructive run. Untracked pre-existing residue left untouched: `artifacts/…`,
`generated.win.obj`, `mips32.a.*`, `.opencode/`, `AUTO_CONTINUE_STATE.md`.

## Limitations / non-claims

See `.openrecomp-phase1/evidence/INDEX.md` ("Limitations report"). Phase 1 is a
bounded proof, not cycle-perfect or universal commercial-game compatibility.

## Local-only assets (never copied into the repository)

`D:\OpenRecomp\roms\phase1\{gameboy,gameboy-color,master-system,nes}\primary\*`;
metadata/hashes/results only. NES primary `2a9345e6...` (mapper 1, NES 2.0).
