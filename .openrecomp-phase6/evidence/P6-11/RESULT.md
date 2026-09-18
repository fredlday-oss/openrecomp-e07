# P6-11 Evidence-Driven Platform Expansion - Result

Verdict: `PASS` (deterministic zero-platform-delta determination)

## Baseline

- Branch `phase6/nes-compat-v1` at the P6-10 boundary commit
  `226faaf92aab32b8baaf27878724c14d4e439c9d`, tree
  `23890109dd84f51c7103f8a676e7a8a4a04d7c1b` (Phase-5 frozen boundary
  `e8d3627a622d0ca3196b117c5112f29fabdb49e7`; tag object
  `b5d6832ba2374b810f4c24500ed9093a9481fd8d`, tree
  `468fb9788350de393d3de2ca9471b7d874ee8dc9`).

## Objective (frozen queue)

Add only PPU/APU/input/timing/runtime behaviour demonstrated necessary by the
private compatibility evidence and/or the public proof fixture. Every addition
requires an explicit deterministic reference test. No broad full-hardware
implementation by assumption.

## Determination (why zero platform delta is the evidence-justified outcome)

The frozen outcome is conditional: it authorises additions only when current
evidence demonstrates that they are necessary. At this boundary no platform
behaviour is demonstrated necessary, so the justified addition set is empty.

- The P6-10 private pipeline is re-derived in process and reproduces the
  committed P6-10 evidence byte-for-byte:
  `tmnt_pipeline.json` sha256
  `0b8c9014fa11f9e363f1cfb1c569048f786b8baec2117769adb862b375a3ebdc`,
  `blockers.json` sha256
  `6b8b789cb691da742c270b81c98849bbda952642ad393cc5a4af230bc97e41c5`.
- Every P6-10 blocker classifies without a platform requirement:
  - `frontier`: `translation_control_flow` - documented-control-flow walk
    fails closed at `0xc570` (undocumented 6502 opcode `0x7c`) after a `jsr`
    from `0xC56D`; the private image declares no code/data boundary evidence.
  - `indirect_control_flow`: `translation_control_flow` - unresolved
    `jmp ($E2)` sites at `0x86E8`, `0x8956`, `0x8F3C`; runtime jump-table
    targets are never guessed.
  - `bank_state`: `translation_reachability_control_flow` - 1048 candidate
    instructions reach the mapper-switched `$8000-$BFFF` window under the
    power-on PRG bank only; runtime bank-state evidence is required.
  - `runtime_platform`: `platform_behaviour_not_yet_observable` -
    `NOT_TESTED`; PPU/APU/input/timing requirements beyond the bounded
    Phase-5/6 platform model cannot be assessed until translation completes.
  - `mapper`: `mapper_blocker_closed` - `SUPERSEDED`; no requirement.
- The platform layer is never reached: translation, native build and native
  execution are all `NOT_ATTEMPTED`; the neutral structure attempt fails closed
  for missing data spans. No observed platform deficiency exists, and the only
  explicit runtime-platform record is `NOT_TESTED`, which cannot justify an
  addition.
- The only executable artefact, the public MMC1 proof fixture, retains exact
  P6-09 native/reference equivalence and the unchanged runtime support identity
  (`c15980d4...`), so the public fixture demonstrates no missing platform
  behaviour either.
- The `0x7C` instruction and the unresolved indirect-control-flow sites are
  recorded as translation/control-flow blockers, not platform blockers.

## Changes (additive)

- `tools/test_phase6_evidence_expansion_v1.py`: new P6-11 gate implementing the
  deterministic re-derivation, blocker classification, zero-delta decision,
  platform-source pins, fail-closed sensitivity checks and hygiene checks.
- `.openrecomp-phase6/SOURCE_SHA256SUMS.txt`: adds the new gate identity.
- `.openrecomp-phase6/STATE.md`, `STAGE_QUEUE.md`, `HANDOFF.md`: stage
  bookkeeping.
- No `.openrecomp-phase6/src/` module was added or modified: all 19 Phase-6
  source identities are pinned to the P6-10 boundary and verified unchanged
  (`platform:src-unchanged`). No PPU/APU/input/timing/runtime behaviour, no
  CPU semantics and no indirect targets were implemented.

## Official gate

- Runner: `python .openrecomp-phase6/src/p6_stage_runner_v1.py --stage P6-11
  --script tools/test_phase6_evidence_expansion_v1.py --evidence-dir
  .openrecomp-phase6/evidence/P6-11 --tests-json p6_11_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical:
  - stdout: 2871 bytes raw, raw sha256
    `627a8ce1d3e00800535e34a8a7e71b8f7d77bb5b7a744f090177a286b333a870`,
    LF sha256
    `d428bb64f0f6cf1a09e754c327fb9fea2a9d27b375384ec2919d65ed9348dc8f`.
  - `p6_11_tests.json` sha256
    `bffc7358ec66bc654d6d3b734cfd742ed21e63785ea25d2c180f10ccaf1e16df`,
    `tests=56`; both runs produced the same tests-json hash.
- Markers: `OPENRECOMP_P6_11=PASS`,
  `OPENRECOMP_PHASE6_PLATFORM_EXPANSION_V1=PASS tests=56`,
  `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`.

## Decision record

- `decision = NO_ADDITION_JUSTIFIED`; `additions = []`;
  `platform_requirement_evidence = []`.
- Control-flow blockers: `frontier`, `indirect_control_flow`, `bank_state`.
- Platform preservation: 19/19 pinned Phase-6 sources unchanged; private
  runtime support identity `2e3fa4ba...` reproduced; MMC1 cartridge and
  reference platform power-on state `(0, 7)` PRG windows reproduced.

## Independent / reference comparison

- The frozen P6-09 independent MMC1 reference equivalence gate re-ran as the
  explicit deterministic reference test of the currently proven platform:
  `OPENRECOMP_P6_09=PASS`,
  `OPENRECOMP_PHASE6_MMC1_REFERENCE_EQUIVALENCE_V1=PASS tests=100`, exit 0,
  empty stderr, stdout sha256 raw
  `0144086e742cdc5441a5a10d1d7da8f5f8d1012281e2769fd5515d66c7f6952a`
  (identical to the recorded P6-09 official capture), LF
  `dcfbcb016a2a4bd3be64fc88e296fe7fcbef5ddd3a33deac23323b9758f8bb72`.

## Negative / fail-closed coverage

The gate's decision logic rejects synthetically justified expansion evidence:
`platform-requirement-ppu`, `platform-requirement-runtime`,
`runtime-platform-demonstrated`, `unclassified-blocker`; it rejects anchor
tampering (`anchor-mismatch`), a missing pinned platform source
(`platform-source-missing`), a changed pinned platform source
(`platform-source-changed`) and a missing private path (`missing-private-path`).
Evidence hygiene verifies no private ROM bytes or first/last 16 KiB PRG bank
bytes appear in any P6-11 evidence file.

## Regressions

- `tools/test_nes_rom_v1.py` (`PASS tests=12`), `tools/test_nes_platform_v1.py`
  (`PASS tests=10`), `tools/test_phase6_mmc1_inventory_v1.py`
  (`PASS tests=85`, stdout `2bfd8a5e...`), `tools/test_phase6_mmc1_variant_v1.py`
  (`PASS tests=61`, stdout `315fd5ea...`) and
  `tools/test_phase6_mmc1_reference_equiv_v1.py` (`PASS tests=100`, stdout
  `0144086e...`): all exit 0 with empty stderr (scratch evidence only; frozen
  committed evidence untouched).

## Claim ledger deltas

- New platform capabilities: none (no addition justified).
- No mapper, CPU, indirect-control-flow or platform semantics were added or
  promoted. The `0x7C` and indirect-control-flow blockers remain explicit and
  unresolved.
- Terminal marker remains `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN`;
  general compatibility remains
  `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`.

## Limitations

- Extended PPU/APU/input/timing requirements remain `NOT TESTED` because
  translation is not reached; this stage proves only that no addition is
  justified yet, not that none will ever be.
- The private image remains not playable; no compatibility claim is derived
  from this analysis.
- No general NES compatibility, no MMC1 board-variant coverage, no cycle or
  full PPU/APU accuracy is claimed.

## Repository side effects

- Tracked additive changes: new gate, manifest entry, updated control plane,
  P6-11 evidence. Scratch/build artifacts remain ignored; no ROM copy exists in
  the repository or evidence.

## Evidence index

`RESULT.md`, `p6_11_tests.json`, `official_runs.json`, `determinism.json`,
`platform_expansion.json`, `platform_sources.json`, `regressions.json`,
`run1.txt`, `run2.txt`, `run1.err.txt`, `run2.err.txt`, `changed_files.txt`.

## Next stage

P6-12 - Reusable ROM-to-native workflow.
