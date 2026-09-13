# OPENRECOMP Phase 1 State

PACKAGE: `OPENRECOMP_PHASE1_OPENCODE_QWEN14B_V1`

PHASE: `PHASE_1_MULTIARCH_PROOF`

CURRENT_STAGE: `P1-99`

CURRENT_STATUS: `PASS`

LAST_PASSED_STAGE: `P1-99`

OVERALL_VERDICT: `OPENRECOMP_PHASE1_MULTIARCH_PROOF=PASS`

## Stage ledger

| ID | Stage | Status | Evidence |
| --- | --- | --- | --- |
| P1-00 | Repository/baseline audit + deterministic verification inventory | `PASS` | `.openrecomp-phase1/evidence/P1-00/RESULT.md` |
| P1-01 | Extract/document architecture-neutral frontend contract | `PASS` | `.openrecomp-phase1/evidence/P1-01/RESULT.md` |
| P1-02 | Multi-architecture core scaffolding without regression | `PASS` | `.openrecomp-phase1/evidence/P1-02/RESULT.md` |
| P1-03 | Shared architecture test/evidence harness | `PASS` | `.openrecomp-phase1/evidence/P1-03/RESULT.md` |
| P1-10 | SM83 architectural state: registers, flags, PC/SP | `PASS` | `.openrecomp-phase1/evidence/P1-10/RESULT.md` |
| P1-11 | SM83 base + CB decoder/classifier | `PASS` | `.openrecomp-phase1/evidence/P1-11/RESULT.md` |
| P1-12 | SM83 documented instruction semantics | `PASS` | `.openrecomp-phase1/evidence/P1-12/RESULT.md` |
| P1-13 | SM83 control flow + OpenRecomp IR/lowering | `PASS` | `.openrecomp-phase1/evidence/P1-13/RESULT.md` |
| P1-14 | Game Boy ROM ingestion + memory/platform contract | `PASS` | `.openrecomp-phase1/evidence/P1-14/RESULT.md` |
| P1-15 | Game Boy deterministic headless proof | `PASS` | `.openrecomp-phase1/evidence/P1-15/RESULT.md` |
| P1-16 | Game Boy Color bounded platform-mode proof | `PASS` | `.openrecomp-phase1/evidence/P1-16/RESULT.md` |
| P1-17 | SM83/GB/GBC regression + differential audit | `PASS` | `.openrecomp-phase1/evidence/P1-17/RESULT.md` |
| P1-20 | Z80 architectural state + decoder | `PASS` | `.openrecomp-phase1/evidence/P1-20/RESULT.md` |
| P1-21 | Z80 semantics + control flow + IR/lowering | `PASS` | `.openrecomp-phase1/evidence/P1-21/RESULT.md` |
| P1-22 | Master System ROM/banking/I-O platform contract | `PASS` | `.openrecomp-phase1/evidence/P1-22/RESULT.md` |
| P1-23 | Master System deterministic headless proof | `PASS` | `.openrecomp-phase1/evidence/P1-23/RESULT.md` |
| P1-24 | Z80/SMS regression + differential audit | `PASS` | `.openrecomp-phase1/evidence/P1-24/RESULT.md` |
| P1-30 | NES 6502-family architectural state + decoder | `PASS` | `.openrecomp-phase1/evidence/P1-30/RESULT.md` |
| P1-31 | NES 6502-family semantics + interrupts/control flow + IR/lowering | `PASS` | `.openrecomp-phase1/evidence/P1-31/RESULT.md` |
| P1-32 | NES ROM ingestion + NROM/mapper abstraction | `PASS` | `.openrecomp-phase1/evidence/P1-32/RESULT.md` |
| P1-33 | NES CPU-facing PPU/APU/controller contracts | `PASS` | `.openrecomp-phase1/evidence/P1-33/RESULT.md` |
| P1-34 | NES deterministic headless proof | `PASS` | `.openrecomp-phase1/evidence/P1-34/RESULT.md` |
| P1-35 | 6502/NES regression + differential audit | `PASS` | `.openrecomp-phase1/evidence/P1-35/RESULT.md` |
| P1-90 | Whole-project regression + architecture-boundary audit | `PASS` | `.openrecomp-phase1/evidence/P1-90/RESULT.md` |
| P1-91 | Phase-1 evidence index + limitations report | `PASS` | `.openrecomp-phase1/evidence/INDEX.md`, `.openrecomp-phase1/evidence/P1-91/RESULT.md` |
| P1-99 | Final Phase-1 verdict | `PASS` | `.openrecomp-phase1/evidence/P1-99/RESULT.md` |

## Latest verification

Host: win32, PowerShell 5.1, Python 3.14.6, jsonschema 4.26.0, Node v22.23.2, git 2.55.0.windows.3.
`clang`/`gcc` are absent; MSVC Build Tools 18 (14.44.35207 / 14.51.36231) are reachable through `setuptools._distutils`.

```text
python tools/phase1_host_gates_v1.py   (P1-90 authoritative manual run, x2)
RUN1 EXIT=0 TIME=00:06:23.8981181  RUN2 EXIT=0 TIME=00:06:21.1210213
OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
RUN1/RUN2 SHA256=3fbb23d3d0174a7efe381d70a1636987c4355e5b9837d67c8dcb3e158a67f594
(identical output; Run-2 repository-status snapshot unchanged)
OPENRECOMP_P1_90_HARNESS_DETERMINISM=PASS
OPENRECOMP_P1_90_NO_RUN2_SIDE_EFFECTS=PASS

python tools/test_z80_state_v1.py
OPENRECOMP_Z80_STATE_V1=PASS tests=6

python tools/test_z80_decode_v1.py
OPENRECOMP_Z80_DECODE_V1=PASS tests=14
(base 256/256; ED 65/65 documented + 191 rejected; CB 248/248 + 8 SLL rejected;
DD/FD index forms + DDCB/FDCB (ix+d)/(iy+d) 31/31; IXH/IXL splits fail closed)

python tools/test_z80_semantics_v1.py
OPENRECOMP_Z80_SEMANTICS_V1=PASS tests=86
(documented flag rules incl. DAA/NEG/BIT/rotates/16-bit ops; block-I/O family
per z80-heaven: Z=B==0, P/V=B!=0, N by direction, C flag+register preserved,
S/H preserved; OUTD/OTDR direction fixed; 8-bit port mask; full coverage sweep
base 252/252, ED 65/65, CB 248/248, DDCB/FDCB 62/62)

python tools/test_z80_lowering_v1.py
OPENRECOMP_Z80_LOWERING_V1=PASS tests=14
(differential proofs: reference == Core API on identical final CPU state +
64 KiB memory + 256-byte ports; fixture 1 a=0x07 f=0x42 hl=0xd233 sp=0xff00
ix=0xc800 halted=1 blocks=8; fixture 3 block-I/O: INIR x3 + OTIR x2 with
BC>0xFF port masking, f=0x40 b=0 c=0x37 hl=0xd002)

python tools/test_sms_platform_v1.py
OPENRECOMP_SMS_PLATFORM_V1=PASS tests=30
(synthetic ROMs only: header/classification/Sega mapper/reset state/bank
shift/mirroring/write-through/VDP protocol/PSG/controller ports/fail-closed;
local SMS ROM metadata-only: The Ninja sha256=56015cea..., sms-export 8 banks)

python tools/test_sms_headless_v1.py
OPENRECOMP_SMS_HEADLESS_V1=PASS tests=6
(synthetic SMS ROM differential: reference == Core API on CPU state + RAM +
control mirrors + flat ports; a=0x1 f=0x42 hl=0xc000 sp=0xdff0 b=0x1 im=1
halted=1; VDP VRAM 11223344 reg1=0xe4; PSG reg0=0x0f; guest-code slot-2
paging + VDP status read + ROM write-protect fail closed)

python tools/test_sms_regression_v1.py
OPENRECOMP_Z80_SMS_REGRESSION_V1=PASS tests=15
(P1-24 audit: 7 chain gates + sm83 arch harness run twice byte-identical;
7 frozen Z80/SMS markers re-pinned)

python tools/test_nes6502_state_v1.py
OPENRECOMP_NES6502_STATE_V1=PASS tests=10

python tools/test_nes6502_decode_v1.py
OPENRECOMP_NES6502_DECODE_V1=PASS

python tools/test_nes6502_semantics_v1.py
OPENRECOMP_NES6502_SEMANTICS_V1=PASS tests=102
(151/151 official opcodes execute; undocumented fail closed; documented
addressing modes, branches, JMP-indirect page bug, JSR/RTS, BRK/RTI,
reset/IRQ/NMI; ADC/SBC proven binary with D set per NESdev 2A03)

python tools/test_nes6502_lowering_v1.py
OPENRECOMP_NES6502_LOWERING_V1=PASS tests=12
(differential reference == Core API on A/X/Y/SP/P/PC + 64 KiB memory;
137/137 non-control official opcodes lowered; 15 control-flow forms)

python tools/test_nes_rom_v1.py
OPENRECOMP_NES_ROM_V1=PASS tests=12
(synthetic iNES/NES 2.0 ingestion + NROM mapping; unsupported mappers fail
closed; local NES ROM metadata-only: mapper=1, prg=131072, chr=131072, nes2=1)

python tools/test_nes_platform_v1.py
OPENRECOMP_NES_PLATFORM_V1=PASS tests=10
(CPU bus/RAM mirrors, PPU register protocol + read buffer + palette mirrors,
nametable arrangement, OAMDMA, controller shift protocol, APU latches,
fail-closed disabled/expansion/CHR-ROM/four-screen access)

python tools/test_nes_headless_v1.py
OPENRECOMP_NES_HEADLESS_V1=PASS tests=7
(differential: a=0xc6 x=0x0 sp=0xfd p=0xa4 pc=0x8032; platform: ppuctrl=0x7e
 ppumask=0x1e vram=1122 oam_dma=1 controller=0x41 apu=0x1f; nrom 16k mirror
 vs 32k identity; reset/irq/nmi; fail-closed $4018)

python tools/test_nes_regression_v1.py
OPENRECOMP_NES_REGRESSION_V1=PASS tests=16
(8 chain/boundary scripts run twice byte-identical + 8 frozen markers)

python tools/phase1_host_gates_v1.py
OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS

python tools/check_frontend_contract_v1.py
OPENRECOMP_FRONTEND_CONTRACT_CHECKS=20 PROBES=13 CHAIN_PROOFS=2 FAIL=0
OPENRECOMP_FRONTEND_CONTRACT_V1=PASS

python tools/test_frontend_scaffold_v1.py
OPENRECOMP_FRONTEND_SCAFFOLD_V1=PASS tests=28

python tools/test_sm83_state_v1.py
OPENRECOMP_SM83_STATE_V1=PASS tests=8

python tools/test_sm83_decode_v1.py
OPENRECOMP_SM83_DECODE_V1=PASS tests=7

python tools/test_sm83_semantics_v1.py
OPENRECOMP_SM83_SEMANTICS_V1=PASS tests=62

python tools/test_sm83_lowering_v1.py
OPENRECOMP_SM83_LOWERING_V1=PASS tests=8
(differential proof: reference == Core API, a=0x07 f=0xc0 hl=0x1334 sp=0xff0a ops=681, 64 KiB memory identical)

python tools/test_gb_rom_v1.py
OPENRECOMP_GB_ROM_V1=PASS tests=8
(synthetic ROMs only: header/classification/MBC1 mapper; no commercial ROM bytes)

python tools/test_gb_headless_v1.py
OPENRECOMP_GB_HEADLESS_V1=PASS tests=14
(differential: ROM -> map -> frontend -> IR V1 -> Core API == reference;
a=0x07 f=0xc0 b=0x13 c=0x34 hl=0x1334 sp=0xff0c halted=1 operations=594 blocks=7,
64 KiB memory identical; timer/joypad/interrupt/HALT contracts per Pan Docs;
local GB ROM metadata-only evidence: SML2 sha256=5450dce1..., mapper=mbc1 dmg)

python tools/test_sm83_semantics_v1.py
OPENRECOMP_SM83_SEMANTICS_V1=PASS tests=65
(P1-15 repair: `ld (a16), a` (0xEA) was a 16-bit SP store in both reference and
lowering; fixed to the documented 8-bit store + 3 new pins, 62 -> 65 tests)

python tools/test_gb_mode_v1.py
OPENRECOMP_GB_MODE_V1=PASS tests=11
(documente GB vs GBC mode selection: header 0x143 bit 7 + hardware model;
KEY1/VBK/SVBK CGB-only surfaces fail closed on dmg; VRAM/WRAM banking;
armed-STOP speed switch + double-speed timer rates; local GBC ROM metadata-only:
Return of the Ninja sha256=ebe140f2..., mapper=mbc5 cgb-only)

python tools/test_sm83_regression_v1.py
OPENRECOMP_SM83_GB_GBC_REGRESSION_V1=PASS tests=16
(P1-17 audit: 9 chain gates x2 byte-identical + 7 frozen markers re-pinned)

python tools/phase1_host_gates_v1.py
OPENRECOMP_PHASE1_HOST_GATES_PASS=29 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS

python tools/arch_harness_v1.py examples/mips32-v1/arch-harness-v1.json
OPENRECOMP_ARCH_HARNESS_V1=PASS   (decode positive=35 negative=4; chain checksum=1950232098)

python tools/arch_harness_v1.py examples/riscv32-v1/arch-harness-v1.json
OPENRECOMP_ARCH_HARNESS_V1=PASS   (decode positive=10 negative=3; chain observed_state=22)

python tools/arch_harness_v1.py examples/sm83-v1/arch-harness-v1.json
OPENRECOMP_ARCH_HARNESS_V1=PASS   (decode positive=87 negative=13; decode-only)
```

Skipped (explicitly, never counted as pass): `e07-hardened-end-to-end` (`bash RUN.sh`) and `external-repro-v1`
(`bash EXTERNAL_REPRO_V1.sh`) — both need `clang` + `gcc`; the reviewer gate also needs a POSIX environment.

Determinism: P1-01 contract-gate JSON is byte-identical across two runs
(`sha256 128102F8AC60C13668D27B68DA454668BEA6CC659DB1DC0DE2466F9E37D0C245`).

## Baseline repair recorded in P1-00

`tools/wasm_run.js` was empty at `HEAD` (`bd5f02f`); commit `2edb212` truncated it and regenerated
`SOURCE_SHA256SUMS.txt` around the empty file, silently disabling `RUN.sh` step `[7/10]`
(native/WebAssembly parity). It was restored byte-for-byte from `da0b535:tools/wasm_run.js`
(`git hash-object` = `4daa8e88316f73c311096a2fd8a76e4d0da72ffe`), the sums manifest was regenerated with
`update_sums.py`, and a new fail-closed `wasm-runner-intact` gate now guards against re-truncation.

## Established-path reconciliation

No PS2/R5900 implementation exists in this repository (the only match for `r5900|ps2|playstation|emotion engine`
is the Phase-1 control text inside `AGENTS.md`). The established paths that must not regress are:

- RV32I E07 synthetic fixture: `checksum=122010428`, `return a0=48`, `operations=3866` (PROVEN);
- MIPS32 vertical slice: `checksum=1950232098`, `return v0=31`, `operations=100`, `delay_slots=7`;
- MIPS32 Expansion V1: `logic-shift 435263539/72/1`, `memory-width 4257846410/60/1`,
  `branches-calls 2065440492/75/9`, `mult-hilo 768371589/44/1`, `big-endian-memory 938211822/24/1`.

These published numbers are frozen regression targets for every later stage.

## Current blocker

None.

## Next exact action

Phase 1 complete. Final verdict `OPENRECOMP_PHASE1_MULTIARCH_PROOF=PASS`
recorded at `.openrecomp-phase1/evidence/P1-99/RESULT.md`.

No further required stages remain. Optional follow-on work (explicitly out of
Phase 1) is listed under "Limitations report" in
`.openrecomp-phase1/evidence/INDEX.md`. No commit has been created; the user
may commit the working tree when ready.

## Git status (short)

Modified (P1-31): `adapters/nes6502.py` (completed table-driven official-opcode
decoder; P1-30 tests unchanged), `tools/phase1_host_gates_v1.py` (added
`nes6502-semantics-v1`, `nes6502-lowering-v1`), `SOURCE_SHA256SUMS.txt`.
Added (P1-31): `tools/nes6502_reference_v1.py`, `tools/test_nes6502_semantics_v1.py`,
`tools/nes6502_frontend_v1.py`, `tools/test_nes6502_lowering_v1.py`.
Added (P1-32..P1-35): `tools/nes_rom_v1.py`, `tools/test_nes_rom_v1.py`,
`tools/nes_platform_v1.py`, `tools/test_nes_platform_v1.py`,
`tools/nes_headless_v1.py`, `tools/test_nes_headless_v1.py`,
`tools/test_nes_regression_v1.py`
(`tools/phase1_host_gates_v1.py` and `SOURCE_SHA256SUMS.txt` updated each stage).

Modified (earlier stages): `AGENTS.md` (pre-existing control block), `SOURCE_SHA256SUMS.txt`, `tools/wasm_run.js`,
`tools/sm83_frontend_v1.py`, `tools/sm83_reference_v1.py`, `tools/test_sm83_semantics_v1.py`,
`tools/phase1_host_gates_v1.py`, `tools/gb_platform_v1.py`, `tools/test_gb_headless_v1.py`,
`tools/test_z80_lowering_v1.py` (P1-21 fixture/pattern repairs + differential #3),
`tools/z80_reference_v1.py` (P1-21 block-I/O documented flag model + OUTD/OTDR direction fix),
`tools/z80_frontend_v1.py` (P1-21 block-I/O lowering + 8-bit port mask),
`tools/test_z80_semantics_v1.py` (P1-21: 79 -> 86 pins),
`tools/sms_platform_v1.py` (P1-22 + P1-23 additive port_trace).
Added: `adapters/z80.py`, `tools/test_z80_state_v1.py`, `tools/test_z80_decode_v1.py`,
`tools/gb_platform_v1.py`, `tools/test_gb_headless_v1.py`, `tools/test_gb_mode_v1.py`,
`tools/test_sm83_regression_v1.py`, `tools/z80_reference_v1.py`, `tools/z80_frontend_v1.py`,
`tools/test_z80_semantics_v1.py`, `tools/test_z80_lowering_v1.py`,
`tools/sms_platform_v1.py`, `tools/test_sms_platform_v1.py` (P1-22),
`tools/sms_headless_v1.py`, `tools/test_sms_headless_v1.py` (P1-23),
`tools/test_sms_regression_v1.py` (P1-24), plus the P1-00..P1-14 files
listed in earlier state.
Untracked pre-existing residue left untouched: `artifacts/mips32_translation_v1/`,
`artifacts/mips32_translation_evidence_closure_v1/` (+`.zip`), `generated.win.obj`, `mips32.a.exp`, `mips32.a.lib`,
`mips32.a.obj`, `mips32.abi.a.obj`, `.opencode/`.
No commit created in this session.

## Local-only verification assets (never copied into the repository)

ROM root `D:\OpenRecomp\roms\phase1` exists and matches `.openrecomp-phase1/ROM_INVENTORY.json`
(exactly one primary image per platform: GB 524288 B, GBC 1048576 B, SMS 131072 B, NES 262160 B).
`ROM_PATHS.md`/`CONTROL_POLICY.md` still contain the unsubstituted literal `$RomRoot`; the effective root is taken
from `ROM_INVENTORY.json`. These are commercial images: metadata/hashes/results may be recorded, bytes may not.

## Important invariants

- single OpenCode agent;
- selected local Qwen 14B model;
- preserve existing PS2/R5900 behavior (in this tree: the RV32I/E07 + MIPS32 published results above);
- deterministic verification is authoritative;
- no proprietary ROM/BIOS committed;
- update this file after every stage.
