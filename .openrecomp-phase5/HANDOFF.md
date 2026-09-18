# OpenRecomp Phase 5 Handoff

STATUS: Phase 5 `ACTIVE` - P5-00 (Phase-5 boundary) and P5-01 (NES/iNES
ingestion and inventory) are `PASS`; P5-02 (2A03/6502 decode + reachable
instruction frontier) is the active stage. Phase 4 is complete and frozen at
annotated tag `openrecomp-phase4-pass` (object
`e7eaab18fee267b3d7962db13835c9e14dd77fc2`) =
`b3c71fb690f00b4811e8ec30c28f7725141295d0`, tree
`f2ca3080915aa68f403526b89dfc17454687aed6`, with
`OPENRECOMP_P4_99=PASS`,
`OPENRECOMP_PHASE4_FINAL_VERDICT_V1=PASS tests=79` and
`OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=PASS` (bounded audited claim only);
`OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN` and
`COREMARK_STATUS=NOT_PROVEN` remain permanent.

Phase 5 objective (reserved `NOT_PROVEN` until P5-99): prove the bounded NES /
2A03 static-recompilation path on a legally clean public iNES fixture through
the frozen Phase-4 generic runtime and platform-adapter contracts, with
independent reference equivalence, and record the private TMNT image only as a
non-redistributed compatibility observation.

Reserved markers:

- `OPENRECOMP_PHASE5_NES_PLATFORM_PROOF=NOT_PROVEN` (P5-99 may issue PASS for
  the bounded claim only)
- `OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY=NOT_PROVEN` (never promoted)

## Firm constraints carried into Phase 5

- Never mutate the frozen Phase-1/Phase-2/Phase-3/Phase-4 histories, tags,
  evidence, gates or verdicts. Phase-5 work is additive under
  `.openrecomp-phase5/` plus new `tools/test_phase5_*` gates.
- Never commit, copy, embed or package the private TMNT image bytes or any
  ROM-derived binary copy (`FIXTURE_POLICY.md`, `CONTROL_POLICY.md` rule 10).
- The public proof fixture is an original Apache-2.0 NES program authored for
  Phase 5 with full recorded provenance.
- Fail closed on unsupported mappers/opcodes/hardware; never guess.
- Never execute original guest CPU code directly on the host.

## P5-01 outcome (PASS)

Markers: `OPENRECOMP_P5_01=PASS`,
`OPENRECOMP_PHASE5_INGESTION_INVENTORY_V1=PASS tests=53`; terminal and
general markers reserved as `NOT_PROVEN`.

- Original Apache-2.0 public fixture authored and built deterministically:
  NROM-128 mapper 0, 16 KiB PRG, 8 KiB original CHR, vectors
  NMI `$C196` / RESET `$C000` / IRQ `$C1F7`, ROM SHA-256 `272c94cd...`
  (24592 bytes); all 231 assembled instructions cross-check against the frozen
  `adapters.nes6502` decoder.
- New `.openrecomp-phase5/src/p5_ines_v1.py` fail-closed ingestion/inventory
  layer; exact-size validation, NES 2.0 sub-field inventory, extended-size
  rejection, mapper/submapper classification, NROM-only vector extraction.
- Private TMNT inventoried by metadata/hash only: mapper 1, 128 KiB PRG,
  128 KiB CHR, horizontal mirroring, `BLOCKED_UNSUPPORTED_MAPPER`; frozen
  `make_mapper` fails closed.
- Negative coverage: bad magic, truncated, oversized, zero PRG, NES 2.0
  extended size and PRG-size MSB all fail closed without traceback.
- Two official runs byte-identical raw (`6a895e0b...`, 2074 bytes) and LF
  (`89a39695...`), empty stderr, exit 0; `p5_01_tests.json` identical
  (`e2734be9...`).
- Evidence: `.openrecomp-phase5/evidence/P5-01/`.

## P5-00 outcome (PASS)

Markers: `OPENRECOMP_P5_00=PASS`,
`OPENRECOMP_PHASE5_BOUNDARY_V1=PASS tests=80`; terminal and general markers
reserved as `NOT_PROVEN`.

- Branch `phase5/nes-platform-v1` descends from the frozen Phase-4 boundary
  commit `b3c71fb...`; tag object `e7eaab18...`, tree `f2ca3080...`.
- The Phase-4 final verdict gate independently re-passed twice in the
  reconstructed pre-verdict context with byte-identical stdout to the recorded
  official capture (2609 bytes raw `903308ca...`, LF `79c6f395...`,
  `tests=79`) and regenerated the committed `p4_99_tests.json`
  (`f13cf891...`).
- Phase-5 control plane established and deterministic; queue `P5-01` ..
  `P5-99` frozen; `NES_PLATFORM_STATUS=NOT_PROVEN`; no NES capability claimed.
- ROM safety verified: private fixture 262160 bytes / SHA-256 `2a9345e6...`
  present outside the worktree, no ROM image or private copy anywhere in the
  repository, `.gitignore` ROM rules effective; public/private separation
  recorded in `FIXTURE_POLICY.md`.
- Two official runs byte-identical raw (`825932c5...`, 3025 bytes) and LF
  (`79bdbf3c...`), empty stderr, exit 0; `p5_00_tests.json` identical
  (`4b87897f...`).
- Evidence: `.openrecomp-phase5/evidence/P5-00/`.

## P5-02 outcome (PASS)

Markers: `OPENRECOMP_P5_02=PASS`,
`OPENRECOMP_PHASE5_DECODE_FRONTIER_V1=PASS tests=33`; terminal and general
markers reserved as `NOT_PROVEN`.

- Exact reachable frontier from RESET `$C000` / NMI `$C196` / IRQ `$C1F7`:
  230 instructions / 508 bytes; one dead padding NOP at `$C0A7`; zero
  reachable undocumented opcodes.
- One unresolved indirect site: `$C0FD jmp ($02FF)` (declared run-exit
  service thunk); one BRK at `$C0A6` with documented continuation `$C0A8`;
  9 dynamic `rts`/`rti` return sites recorded, never guessed.
- 2A03 decimal accounting: `sed`/`cld` reachable, arithmetic `binary_only_2a03`
  (exact semantics proven in P5-03).
- Frozen `tools/nes6502_frontend_v1.convert` exercised on the real code region
  `[$C000,$C1FD)`: 231 instructions / 45 blocks, deterministic; undocumented
  0x03 rejected fail-closed.
- Two official runs byte-identical raw (`76767a3b...`, 1531 bytes) and LF
  (`27de3c27...`), empty stderr, exit 0; `p5_02_tests.json` identical
  (`2eb8ef8c...`).
- Evidence: `.openrecomp-phase5/evidence/P5-02/`.

## P5-03 outcome (PASS)

Markers: `OPENRECOMP_P5_03=PASS`,
`OPENRECOMP_PHASE5_CPU_SEMANTICS_V1=PASS tests=46`; terminal and general
markers reserved as `NOT_PROVEN`.

- 181 differential vectors (all 151 official opcode forms plus edge cases)
  compare the frozen translation path against the frozen independent
  reference with exact final-state and full-64KiB-memory agreement; zero
  failures.
- Every reachable public-fixture (mnemonic, mode) pair is covered; flag,
  stack, branch, page-crossing, zero-page wrap, RMW, BRK/RTI, JMP-indirect
  page-wrap and 2A03 binary-only ADC/SBC behaviour are explicitly exercised.
- Documented reset/IRQ/NMI entry (vector, push order, flags) verified with
  explicit expected values.
- Two official runs byte-identical raw (`11055196...`, 2513 bytes) and LF
  (`42c5cb65...`), empty stderr, exit 0; `p5_03_tests.json` identical
  (`aa46976f...`).
- Evidence: `.openrecomp-phase5/evidence/P5-03/`.

## P5-04 outcome (PASS)

Markers: `OPENRECOMP_P5_04=PASS`,
`OPENRECOMP_PHASE5_NEUTRAL_STRUCTURE_V1=PASS tests=34`; terminal and general
markers reserved as `NOT_PROVEN`.

- Real fixture bridged into the shared neutral layers: 231 instructions /
  48 blocks / 11 functions / 11 translation units / 7 resolved internal direct
  call edges; pinned fingerprints (`cfg d6dfe7a8...`, `discovery 2839d54f...`,
  `call_graph f0a4381e...`, `units 5523eae9...`, `classification 6bc9b98f...`).
- Explicit roots: RESET `$C000`, NMI `$C196`, IRQ `$C1F7`, documented BRK
  continuation `$C0A8`; every root maps to a neutral function.
- No fabricated boundaries (`boundary_violations` empty; function entries are
  roots plus direct JSR targets) and no fabricated indirect targets (single
  `$C0FD jmp ($02FF)` site stays unresolved with empty targets).
- Reachable relationship to P5-02 exact: all 230 reachable instructions are
  covered plus the one dead padding NOP at `$C0A7`.
- Two official runs byte-identical raw (`937e3c2c...`, 1598 bytes) and LF
  (`bed9d7a5...`), empty stderr, exit 0; `p5_04_tests.json` identical
  (`9d3e924c...`).
- Evidence: `.openrecomp-phase5/evidence/P5-04/`.

## P5-05 outcome (PASS)

Markers: `OPENRECOMP_P5_05=PASS`,
`OPENRECOMP_PHASE5_MEMORY_MAP_V1=PASS tests=21`; terminal and general markers
reserved as `NOT_PROVEN`.

- New original bounded NES CPU bus (`p5_bus_v1.py`): RAM + mirrors, PPU
  register-window routing, APU/IO latches/status, OAM DMA, controller ports,
  NROM cartridge window, fail-closed disabled I/O/expansion/absent PRG-RAM.
- Differentially verified against the frozen independent platform: full RAM
  mirror sweep, all 8192 PPU window addresses, APU/IO, controller transcripts,
  OAM DMA, all 32 KiB of PRG, six fail-closed windows, and a 5000-operation
  mixed script with zero mismatches; final PPU register/latch state equal.
- Two official runs byte-identical raw (`16f49c60...`, 1094 bytes) and LF
  (`2783ea49...`), empty stderr, exit 0; `p5_05_tests.json` identical
  (`46d7ad1a...`).
- Evidence: `.openrecomp-phase5/evidence/P5-05/`.

## P5-06 outcome (PASS)

Markers: `OPENRECOMP_P5_06=PASS`,
`OPENRECOMP_PHASE5_PPU_BOUNDARY_V1=PASS tests=32`; terminal and general
markers reserved as `NOT_PROVEN`.

- New original bounded PPU (`p5_ppu_v1.py`): register semantics, PPU memory
  (CHR/nametable/palette/OAM), vblank event surface, bounded tile-space
  GRAY8 frame observation through the Phase-4 graphics boundary.
- Differentially verified against the frozen PPU: 3000-step register script
  with full state comparison, all 16384 PPU addresses for reads/writes,
  horizontal and vertical mirroring, CHR-ROM write rejection.
- Two official runs byte-identical raw (`d064c0ba...`, 1534 bytes) and LF
  (`25850ae8...`), empty stderr, exit 0; `p5_06_tests.json` identical
  (`2a5bc85f...`).
- Evidence: `.openrecomp-phase5/evidence/P5-06/`.

## Exact next action

Execute P5-07 (APU/input/timing/interrupt boundary): implement the bounded
controller input plan, deterministic virtual-frame timing with the documented
instruction-cost table, vblank/NMI event delivery (PPUCTRL bit 7), optional
IRQ handling, APU latch accesses required by the fixture, and the platform
event transcript. Then proceed to P5-08.
