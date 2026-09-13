# OpenRecomp Phase 1 — Evidence Index and Limitations

This index is the navigation record for the Phase-1 multi-architecture proof.
It lists every stage, its verdict and evidence, the executable gate markers, the
reproducible verification commands, and the consolidated limitations. Phase-1
completion is defined only by `.openrecomp-phase1/SCOPE.md`.

Last updated at stage `P1-91`.

## Stage ledger

| Stage | Name | Verdict | Evidence |
| --- | --- | --- | --- |
| P1-00 | Repository/baseline audit + deterministic verification inventory | PASS | `.openrecomp-phase1/evidence/P1-00/RESULT.md` |
| P1-01 | Architecture-neutral frontend contract | PASS | `.openrecomp-phase1/evidence/P1-01/RESULT.md` |
| P1-02 | Multi-architecture core scaffolding without R5900 regression | PASS | `.openrecomp-phase1/evidence/P1-02/RESULT.md` |
| P1-03 | Shared architecture test/evidence harness | PASS | `.openrecomp-phase1/evidence/P1-03/RESULT.md` |
| P1-10 | SM83 architectural state (registers, flags, PC/SP) | PASS | `.openrecomp-phase1/evidence/P1-10/RESULT.md` |
| P1-11 | SM83 base + CB decoder/classifier | PASS | `.openrecomp-phase1/evidence/P1-11/RESULT.md` |
| P1-12 | SM83 documented instruction semantics | PASS | `.openrecomp-phase1/evidence/P1-12/RESULT.md` |
| P1-13 | SM83 control flow + IR/lowering | PASS | `.openrecomp-phase1/evidence/P1-13/RESULT.md` |
| P1-14 | Game Boy ROM ingestion + memory/platform contract | PASS | `.openrecomp-phase1/evidence/P1-14/RESULT.md` |
| P1-15 | Game Boy deterministic headless proof | PASS | `.openrecomp-phase1/evidence/P1-15/RESULT.md` |
| P1-16 | Game Boy Color bounded platform-mode proof | PASS | `.openrecomp-phase1/evidence/P1-16/RESULT.md` |
| P1-17 | SM83/GB/GBC regression + differential audit | PASS | `.openrecomp-phase1/evidence/P1-17/RESULT.md` |
| P1-20 | Z80 architectural state + decoder | PASS | `.openrecomp-phase1/evidence/P1-20/RESULT.md` |
| P1-21 | Z80 semantics + control flow + IR/lowering | PASS | `.openrecomp-phase1/evidence/P1-21/RESULT.md` |
| P1-22 | Master System ROM/banking/I-O platform contract | PASS | `.openrecomp-phase1/evidence/P1-22/RESULT.md` |
| P1-23 | Master System deterministic headless proof | PASS | `.openrecomp-phase1/evidence/P1-23/RESULT.md` |
| P1-24 | Z80/SMS regression + differential audit | PASS | `.openrecomp-phase1/evidence/P1-24/RESULT.md` |
| P1-30 | NES 6502-family architectural state + decoder | PASS | `.openrecomp-phase1/evidence/P1-30/RESULT.md` |
| P1-31 | NES 6502-family semantics + interrupts/control flow + IR/lowering | PASS | `.openrecomp-phase1/evidence/P1-31/RESULT.md` |
| P1-32 | NES ROM ingestion + NROM/mapper abstraction | PASS | `.openrecomp-phase1/evidence/P1-32/RESULT.md` |
| P1-33 | NES CPU-facing PPU/APU/controller contracts | PASS | `.openrecomp-phase1/evidence/P1-33/RESULT.md` |
| P1-34 | NES deterministic headless proof | PASS | `.openrecomp-phase1/evidence/P1-34/RESULT.md` |
| P1-35 | 6502/NES regression + differential audit | PASS | `.openrecomp-phase1/evidence/P1-35/RESULT.md` |
| P1-90 | Whole-project regression + architecture-boundary audit | PASS | `.openrecomp-phase1/evidence/P1-90/RESULT.md` |
| P1-91 | Phase-1 evidence index + limitations report | PASS | `.openrecomp-phase1/evidence/P1-91/RESULT.md` |
| P1-99 | Final Phase-1 verdict | PASS | `.openrecomp-phase1/evidence/P1-99/RESULT.md` |

## Executable gate markers

Shared/core:

- `OPENRECOMP_IR_V1_SPEC=PASS`, `OPENRECOMP_IR_V1_VALID=PASS`
- `OPENRECOMP_CORE_API_V1_TESTS=PASS`
- `PASS: shared adapter interface is real`
- `OPENRECOMP_FRONTEND_CONTRACT_V1=PASS`
- `OPENRECOMP_FRONTEND_SCAFFOLD_V1=PASS`
- `OPENRECOMP_ARCH_HARNESS_V1=PASS` (MIPS32, RV32I, SM83 fixtures)

Game Boy / Game Boy Color (SM83):

- `OPENRECOMP_SM83_STATE_V1=PASS`, `OPENRECOMP_SM83_DECODE_V1=PASS`,
  `OPENRECOMP_SM83_SEMANTICS_V1=PASS`, `OPENRECOMP_SM83_LOWERING_V1=PASS`
- `OPENRECOMP_GB_ROM_V1=PASS`, `OPENRECOMP_GB_HEADLESS_V1=PASS`,
  `OPENRECOMP_GB_MODE_V1=PASS`
- `OPENRECOMP_SM83_GB_GBC_REGRESSION_V1=PASS`

Master System (Z80):

- `OPENRECOMP_Z80_STATE_V1=PASS`, `OPENRECOMP_Z80_DECODE_V1=PASS`,
  `OPENRECOMP_Z80_SEMANTICS_V1=PASS`, `OPENRECOMP_Z80_LOWERING_V1=PASS`
- `OPENRECOMP_SMS_PLATFORM_V1=PASS`, `OPENRECOMP_SMS_HEADLESS_V1=PASS`
- `OPENRECOMP_Z80_SMS_REGRESSION_V1=PASS`

NES (6502 family):

- `OPENRECOMP_NES6502_STATE_V1=PASS`, `OPENRECOMP_NES6502_DECODE_V1=PASS`,
  `OPENRECOMP_NES6502_SEMANTICS_V1=PASS`, `OPENRECOMP_NES6502_LOWERING_V1=PASS`
- `OPENRECOMP_NES_ROM_V1=PASS`, `OPENRECOMP_NES_PLATFORM_V1=PASS`,
  `OPENRECOMP_NES_HEADLESS_V1=PASS`, `OPENRECOMP_NES_REGRESSION_V1=PASS`

Established paths and safety (must not regress):

- `OPENRECOMP_MIPS32_FRONTEND_V1_TESTS=PASS`,
  `OPENRECOMP_MIPS32_EXPANSION_NEGATIVE_TESTS=PASS`, `0 failed`,
  `CAUSALITY_PASS`, `EQUIVALENCE_PASS`
- `OPENRECOMP_PUBLIC_SAFETY=PASS`,
  `OPENRECOMP_PUBLIC_SAFETY_MISSING_FILE_TEST=PASS`
- `OPENRECOMP_DOC_LINKS=PASS`
- `OPENRECOMP_RELEASE_AUTOMATION_V1_TESTS=PASS`,
  `OPENRECOMP_V0_2_RELEASE_METADATA=PASS`

## Reproducible verification

```text
python update_sums.py
python tools/phase1_host_gates_v1.py
```

P1-90 authoritative result (full harness run twice, identical output):

```text
RUN1 EXIT=0 TIME=00:06:23.8981181  RUN2 EXIT=0 TIME=00:06:21.1210213
OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
RUN1/RUN2 SHA256=3fbb23d3d0174a7efe381d70a1636987c4355e5b9837d67c8dcb3e158a67f594
OPENRECOMP_P1_90_HARNESS_DETERMINISM=PASS
OPENRECOMP_P1_90_NO_RUN2_SIDE_EFFECTS=PASS
```

To run a single architecture chain, use `--only <substring>` (e.g.
`--only nes6502`, `--only nes-`, `--only z80`, `--only sm83`, `--only gb-`,
`--only sms-`).

## Limitations report (consolidated)

Phase 1 is a bounded multi-architecture proof, not a promise of cycle-perfect or
universal commercial-game compatibility. The following are explicitly deferred
and/or fail closed.

Cross-cutting:

- No cycle counts / cycle timing are modelled for any architecture.
- Undocumented/unofficial opcodes fail closed (SM83, Z80, NES 6502). The NES
  synthetic halt uses the undocumented KIL/JAM byte `0x02` as a test-harness
  convention only; no real KIL semantics are claimed.
- Interrupt **timing** (delays, hijacking, cycle-accurate dispatch) is deferred;
  interrupt **entry mechanics** and vectors are modelled.
- `e07-hardened-end-to-end` and `external-repro-v1` are toolchain-gated
  (`bash`/`clang`/`gcc`, and POSIX for the reviewer gate) and are skipped on this
  host; a skip is never counted as a pass.
- No PS2/R5900 implementation exists in this tree; the established regression
  targets are the published RV32I/E07 and MIPS32 results, which remain green.

Game Boy / Game Boy Color:

- MBC1 is supported; other documented MBCs are classified but fail closed.
- Cycle-perfect PPU/APU, exhaustive MBC support and broad game compatibility
  are deferred.

Master System:

- Cycle-perfect VDP/audio, BIOS ROM, cartridge RAM, 3D glasses, light phaser,
  FM unit and TH-pin interaction are deferred.
- The CPU/VDP/PSG/controller protocol is deterministic, not cycle-accurate.

NES:

- Only NROM (mapper 0) banking is implemented; all other mappers classify but
  fail closed.
- Cycle-perfect PPU/APU, sprite-0/overflow timing, OAM decay, DPCM read
  conflicts and four-screen VRAM are not modelled (four-screen fails closed).
- NMI is not generated by PPU vblank timing; the reference exposes explicit
  `nmi()`/`irq()`/`reset()` entry surfaces.

Assets policy:

- No commercial ROM/BIOS/firmware bytes are committed. Local ROMs under
  `D:\OpenRecomp\roms\phase1` are external verification inputs; only
  metadata/hashes/results are recorded.

## Final-verdict procedure

Emit exactly `OPENRECOMP_PHASE1_MULTIARCH_PROOF=PASS` only if every required
stage in `SCOPE.md` is PASS and the P1-90 regression audit confirms no
regression. See `.openrecomp-phase1/evidence/P1-99/RESULT.md`.
