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

## P5-07 outcome (PASS)

Markers: `OPENRECOMP_P5_07=PASS`,
`OPENRECOMP_PHASE5_TIMING_INPUT_V1=PASS tests=34`; terminal and general
markers reserved as `NOT_PROVEN`.

- New deterministic virtual platform (`p5_platform_v1.py`): documented base
  instruction-cost table (all 151 opcodes), 29780-unit virtual frames with a
  2273-unit vblank window, per-frame controller input plan, NMI queueing and
  delivery, asserted-line IRQ interface, APU-latch consistency with the
  frozen platform.
- 300000-NOP schedule verified against independently computed expectations;
  transcripts deterministic; fail-closed on undocumented costs and invalid
  timing/input configuration.
- Two official runs byte-identical raw (`062678b9...`, 1572 bytes) and LF
  (`dd9087ae...`), empty stderr, exit 0; `p5_07_tests.json` identical
  (`ca98795c...`).
- P5-06's Phase-4 regression had refreshed the frozen P4-06 sidecar
  (`phase4_entries` 30 -> 32); restored to the committed bytes and recorded in
  the P5-07 RESULT. P5-07 regressions write to scratch evidence only.
- Evidence: `.openrecomp-phase5/evidence/P5-07/`.

## P5-08 outcome (PASS)

Markers: `OPENRECOMP_P5_08=PASS`,
`OPENRECOMP_PHASE5_HOST_EMIT_V1=PASS tests=48`; terminal and general markers
reserved as `NOT_PROVEN`.

- New deterministic 6502 C emitter (`p5_emit_v1.py`, 231 switch cases, typed
  `or_rt_*` ABI only, declared `p5.exit` service binding, fail-closed on
  undeclared indirect sites/undocumented opcodes) and bounded NES C runtime
  support (`p5_support_v1.py`).
- Reproducible native build through the shared Phase-2 pipeline; three
  identical runs: `failed=0`, `exit=1`, `steps=90904`, `nmi=8`, `frames=11`,
  `clock=298327`, exact digests and 11-frame transcript recorded.
- No original guest code executes on the host; NMI entry is generated host
  logic at instruction boundaries.
- Two official runs byte-identical raw (`96004f12...`, 1958 bytes) and LF
  (`732ad767...`), empty stderr, exit 0; `p5_08_tests.json` identical
  (`edb65ad5...`).
- Evidence: `.openrecomp-phase5/evidence/P5-08/`.

## P5-09 outcome (PASS)

Markers: OPENRECOMP_P5_09=PASS,
OPENRECOMP_PHASE5_NATIVE_EXECUTION_V1=PASS tests=40; terminal and general
markers reserved as NOT_PROVEN.

- Four declared controller plans executed natively (none / A / RIGHT / A+RIGHT)
  over 11 virtual frames: every build reproducible, every run deterministic,
  all ailed=0 exit=1 frames=11 nmi=8.
- Guest per-frame transcript equals the exact bit-reversed plan bytes; A/RIGHT
  observables change exactly as documented; nametable graphics uneffected by
  input; all plans pairwise distinct.
- Two official runs byte-identical raw (3b6f4b79..., 1814 bytes) and LF
  (7c1aeca9...), empty stderr, exit 0; p5_09_tests.json identical
  (ad3501b...).
- Evidence: .openrecomp-phase5/evidence/P5-09/.

## P5-10 outcome (PASS)

Markers: `OPENRECOMP_P5_10=PASS`,
`OPENRECOMP_PHASE5_REFERENCE_EQUIVALENCE_V1=PASS tests=37`; terminal and
general markers reserved as `NOT_PROVEN`.

- Native vs frozen independent reference: exact equality on every compared
  field, all three digests, the full 11-line frame transcript, the guest
  transcript word and the exit state for all four declared plans.
- Scheduling-tamper sensitivity checks pass (NMI cost and frame length).
- Two official runs byte-identical raw (`077e99f2...`, 1489 bytes) and LF
  (`1a1a6262...`), empty stderr, exit 0; `p5_10_tests.json` identical
  (`2fb08384...`).
- Evidence: `.openrecomp-phase5/evidence/P5-10/`.

## P5-11 outcome (PASS, private analysis only)

Markers: `OPENRECOMP_P5_11=PASS`,
`OPENRECOMP_PHASE5_PRIVATE_COMPAT_V1=PASS tests=31`; terminal and general
markers reserved as `NOT_PROVEN`.

- Private `PRIVATE_LOCAL_COMPATIBILITY_FIXTURE` analysed by metadata/hash
  only: 262160 bytes, SHA-256 `2a9345e6...`, mapper 1 (MMC1), 128 KiB
  PRG/CHR, horizontal mirroring.
- Fail-closed classification: frozen mapper and P5 cartridge both block
  mapper 1; no banking behaviour guessed.
- Candidate fixed-bank frame (`CANDIDATE / NOT PROVEN`): vectors NMI `$C3A3`,
  RESET `$FFD8`, IRQ `$C412`; bounded candidate frontier 351 instructions,
  59 opcode forms, stop at `0xc570` undocumented 0x7C, out-of-bank targets
  `$864C`/`$901E` requiring MMC1 banking.
- Two official runs byte-identical raw (`24a1bad9...`, 1328 bytes) and LF
  (`5f604ff4...`), empty stderr, exit 0; `p5_11_tests.json` identical
  (`8ab307ad...`).
- Evidence: `.openrecomp-phase5/evidence/P5-11/`; no ROM bytes in evidence.

## P5-12 outcome (PASS)

Markers: `OPENRECOMP_P5_12=PASS`,
`OPENRECOMP_PHASE5_PACKAGE_V1=PASS tests=190`; terminal and general markers
reserved as `NOT_PROVEN`.

- Deterministic public package `phase5_nes_package_v1.zip`: 169 members,
  SHA-256 `8c5ab401...`, manifest fingerprint `213bdf1e...`, two builds
  byte-identical; UTF-8/LF-only; private TMNT bytes/probe and P5-11 evidence
  excluded and checked.
- Self-contained rebuild from packaged generated sources reproduces the
  canonical P5-08 observable exactly.
- Two official runs byte-identical raw (`32e4daf7...`, 9812 bytes) and LF
  (`b5f02035...`), empty stderr, exit 0; `p5_12_tests.json` identical
  (`5a6e89f7...`).
- Evidence: `.openrecomp-phase5/evidence/P5-12/`; package at
  `.openrecomp-phase5/package/phase5_nes_package_v1.zip`.

## Exact next action

Execute P5-90 (Phase-5 whole regression): re-verify the frozen
Phase-1/2/3/4 chain and re-run every Phase-1..Phase-5 required gate from the
audited tree with the documented frozen-boundary hygiene (restore committed
Phase-4 sidecars before re-running P5-00/P5-06 regressions, then restore
again), requiring byte-identical deterministic stdout; then proceed to P5-91.
