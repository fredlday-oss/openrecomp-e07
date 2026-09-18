# OpenRecomp Phase 5 Stage Queue

Only one stage may be active at a time. The remaining queue (`P5-01` ..
`P5-99`) is frozen at the P5-00 `PASS` boundary; see `## Queue freeze` below.
The freeze is effective before any P5-01 implementation work.

| Stage | Name | Status | Required outcome |
|---|---|---|---|
| P5-00 | Phase-5 boundary | COMPLETE | Verify the exact Phase-4 PASS boundary, rerun the Phase-4 final gate, establish the Phase-5 control plane, ROM safety policy, public/private fixture separation and frozen queue. No NES capability claimed yet |
| P5-01 | NES/iNES ingestion and inventory | COMPLETE | Implement/verify fail-closed iNES/NES 2.0 ingestion sufficient for the selected fixtures; inventory header format, PRG ROM, CHR ROM/RAM, mapper/submapper, mirroring, trainer, battery flag, vectors, reset entry, interrupt vectors and unsupported metadata. Never guess unsupported mapper behaviour |
| P5-02 | 2A03/6502 decode + reachable instruction frontier | COMPLETE | Exercise the existing NES6502 frontend against the real fixture(s); produce an exact reachable/dead/unsupported opcode inventory; account explicitly for NES 2A03 behaviour including the absent normal 6502 decimal-mode arithmetic semantics where applicable. Unsupported or illegal opcodes remain fail closed |
| P5-03 | CPU semantics proof | QUEUED | Verify exact semantics for every instruction required by the reachable public fixture path, including flags, stack, branches, page crossing where relevant, BRK/IRQ/NMI/RESET behaviour, JMP-indirect page-wrap behaviour, zero-page addressing and read/modify/write semantics. Use an independently written reference model for differential vectors |
| P5-04 | ProgramModel / CFG / functions / translation units | QUEUED | Bridge the NES program into the shared architecture-neutral layers. Do not fabricate function boundaries or indirect targets. Represent interrupt/reset roots explicitly |
| P5-05 | NES CPU memory map + mapper model | QUEUED | Implement the bounded platform memory model needed by the audited fixture: 2 KiB internal RAM + mirrors, PPU register window, APU/I/O window, controller ports, cartridge PRG mapping, mapper behaviour required by the fixture, SRAM/PRG-RAM if applicable. Unknown mappings fail closed |
| P5-06 | PPU boundary / deterministic graphics model | QUEUED | Implement a Phase-5-bounded PPU/platform interface sufficient for the public fixture, kept behind the Phase-4 graphics boundary. Record nametable/palette/OAM access, register semantics required by the fixture, frame/vblank timing assumptions and unsupported PPU behaviours. Do NOT claim full PPU or cycle accuracy |
| P5-07 | APU/input/timing/interrupt boundary | QUEUED | Implement the bounded interfaces required by the fixture for controller input, NMI, IRQ if required, vblank/event delivery, frame timing and APU accesses required by the fixture. Audio may remain bounded/unsupported where the fixture does not require observable audio equivalence |
| P5-08 | Host emission + NES platform adapter | QUEUED | Emit deterministic native host code for the proven NES CPU subset and connect it through the Phase-4 runtime/platform adapter interfaces. No direct original 6502 guest execution on the host |
| P5-09 | Native execution of legal NES fixture | QUEUED | Produce and execute the native-host result for the legally clean NES fixture; demonstrate meaningful interactive behaviour through CPU + memory + input + timing + graphics/platform boundaries |
| P5-10 | Independent NES reference equivalence | QUEUED | Run the same bounded fixture through an independently implemented or independently structured NES reference path; compare deterministic observables: CPU state, RAM digest, frame/state digest, controller transcript, interrupt counts, platform/service transcript and exit/final bounded state |
| P5-11 | Private TMNT compatibility run | QUEUED | Use only `D:\OpenRecomp\Roms\phase1\nes\primary\tmnt.nes`; perform a private compatibility analysis/run and record ROM SHA-256, mapper/cartridge metadata, reachable CPU frontier, missing mapper/PPU/APU/runtime requirements, how far the static-recompilation pipeline gets and fail-closed blockers. TMNT is not required to PASS for the public proof |
| P5-12 | Reproducible NES package | QUEUED | Build a reproducible public package using only redistributable artifacts. TMNT ROM bytes must not appear anywhere in the package |
| P5-90 | Phase-5 whole regression | QUEUED | Run Phase-1 + Phase-2 + Phase-3 + Phase-4 + Phase-5 required gates. Require deterministic/byte-identical outputs where applicable |
| P5-91 | Evidence index + compatibility limitations | QUEUED | Create a complete evidence index and claim ledger: PROVEN, BOUNDED, UNPROVEN, UNSUPPORTED, NOT TESTED. Clearly separate the legal public fixture result, the private TMNT compatibility observations and general NES compatibility |
| P5-99 | Final Phase-5 verdict | QUEUED | Issue `OPENRECOMP_PHASE5_NES_PLATFORM_PROOF=PASS` only if the exact bounded public NES static-recompilation claim is supported by the audited tree. Keep `OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`. A PASS must not imply all NES games, all mappers, cycle accuracy, full PPU/APU accuracy, commercial-game compatibility, FDS compatibility or arbitrary 6502 binary compatibility |

## Queue freeze

Frozen at the P5-00 `PASS` boundary, before any P5-01 implementation work.
The rows `P5-01` .. `P5-99` above are the complete frozen contract: stage IDs,
names, ordering and required-outcome scope. The freeze does not change any
stage status: `P5-01` .. `P5-99` remain `QUEUED` until their own gates pass.

Frozen-queue rules:

1. No renumbering, insertion, merging, splitting or silent redefinition of a
   frozen stage is permitted.
2. A frozen stage may change only if a genuine technical dependency makes the
   existing frozen stage technically impossible to execute as written. Such a
   change must fail closed: the stage stops with an explicit
   `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE` /
   `BLOCKED_BY_MISSING_EXTERNAL_TOOLCHAIN` record instead of silently
   adapting, the forcing evidence is captured, and the frozen rows are updated
   explicitly in the reconciliation log below.
3. A stage gate must not silently relax a frozen stage's required outcome; a
   gate that cannot satisfy the frozen contract fails closed.
4. The freeze is a control-plane record only. It adds no capability claim and
   changes no frozen Phase-1/Phase-2/Phase-3/Phase-4 boundary.

## Reconciliation log

- Queue freeze (control-plane only, documented): the P5-00 `PASS` boundary
  froze rows `P5-01` .. `P5-99` exactly as written above. No stage was
  renumbered, inserted, merged, split or redefined by the freeze.

## Success markers

- queue freeze: rows `P5-01` .. `P5-99` are frozen by the `## Queue freeze`
  section above (P5-00 `PASS` boundary, control-plane record)
- `OPENRECOMP_P5_00=PASS`
- terminal Phase-5 marker (reserved at P5-00 .. `P5-91`):
  `OPENRECOMP_PHASE5_NES_PLATFORM_PROOF=NOT_PROVEN`; P5-99 may issue `PASS`
  only for the exact bounded claim recorded in `SCOPE.md`
- general NES compatibility marker (never promoted by Phase 5):
  `OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`

## Terminal state

- Reserved until P5-99: `OPENRECOMP_PHASE5_NES_PLATFORM_PROOF=NOT_PROVEN`.
- `OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY=NOT_PROVEN` is permanent for
  Phase 5: no general NES, mapper, game, commercial-title, cycle-accuracy,
  full-PPU/APU or arbitrary-6502 compatibility is claimed at any Phase-5
  stage.
