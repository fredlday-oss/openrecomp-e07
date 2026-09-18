# P6-13 Second Private TMNT Compatibility Run - Result

Verdict: `PASS` (deterministic private compatibility observation; execution not
reached; exact remaining frontier recorded)

## Baseline

- Branch `phase6/nes-compat-v1` at the P6-12 boundary commit
  `80a6b7f7e01a733971bb19a6912ea57a017d5688`, tree
  `976503703a47caf0573d262a3f045db635caab1c`, descending from the Phase-5
  frozen boundary `e8d3627a622d0ca3196b117c5112f29fabdb49e7` (tag object
  `b5d6832ba2374b810f4c24500ed9093a9481fd8d`, tree
  `468fb9788350de393d3de2ca9471b7d874ee8dc9`).

## Objective (frozen queue)

Re-run the complete local pipeline through the P6-12 reusable workflow. Record
whether generated native execution is reached. If not, produce the exact
remaining compatibility frontier. TMNT playability is not required for Phase-6
PASS; no ROM bytes may be copied, committed, embedded or packaged.

## Changes (additive)

- `tools/test_phase6_private_workflow_v1.py`: new P6-13 gate running the
  private image through the frozen P6-12 workflow, recording every requested
  progress category, anchoring the frontier byte-for-byte to the committed
  P6-10/P6-12 evidence and re-deriving the in-memory MMC1 runtime support
  identity without writing ROM-derived source.
- `.openrecomp-phase6/SOURCE_SHA256SUMS.txt`: adds the new gate identity.
- `.openrecomp-phase6/STATE.md`, `STAGE_QUEUE.md`, `HANDOFF.md`: stage
  bookkeeping.
- No `.openrecomp-phase6/src/`, frozen gate or frozen evidence file was
  modified.

## Official gate

- Runner: `python .openrecomp-phase6/src/p6_stage_runner_v1.py --stage P6-13
  --script tools/test_phase6_private_workflow_v1.py --evidence-dir
  .openrecomp-phase6/evidence/P6-13 --tests-json p6_13_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical:
  - stdout: 3261 bytes raw, raw sha256
    `404dd00bbda65374ba750367ffcf29aaf923e423d6e6ac5419be09213ff23db2`,
    LF sha256
    `5cf90e87f72be3c260768ddfe502ab7a67d4d4c2eab40fe466354e3bb81a5896`.
  - `p6_13_tests.json` sha256
    `c9e815d6140af86c0af600ee7227a9733ff52254eb1fb9891b9cfffbfc5d902d`,
    `tests=66`; both official runs produced the same tests-json hash.
- Markers: `OPENRECOMP_P6_13=PASS`,
  `OPENRECOMP_PHASE6_PRIVATE_COMPAT_RUN2_V1=PASS tests=66`,
  `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`.

## Recorded compatibility fields

- Ingestion result: `SUPPORTED_MMC1`; container `nes2.0`, mapper 1/submapper 0,
  horizontal mirroring, 8 x 16 KiB PRG (SHA-256 `2fbc367a...`) and 16 x 8 KiB
  CHR (SHA-256 `f9e354d5...`), no PRG-RAM/battery/trainer/four-screen; vectors
  NMI `$C3A3` / RESET `$FFD8` / IRQ `$C412` from the power-on fixed last bank.
- Mapper state: `SUPPORTED_MMC1`, variant profile
  `discrete_mmc1_chr_rom_no_wram`; power-on registers `0C 00 00 00`, PRG
  windows `(0, 7)`, CHR mode 0, one-screen lower, PRG-RAM disabled.
- Reachable/static frontier: the documented-control-flow walk fails closed;
  the bounded candidate traversal reaches 1250 instructions / 2711 bytes
  (202 fixed bank, 1048 power-on low window), 42 opcode forms, 11 pending at
  stop; no contiguous code region exists.
- Opcode frontier: `BLOCKED_UNSUPPORTED_OPCODE` at `0xC570` - undocumented
  6502 opcode `0x7C`, reached after a `jsr` at `0xC56D`.
- Indirect-control-flow frontier: `UNRESOLVED` - `jmp ($E2)` at `0x86E8`,
  `0x8956` and `0x8F3C`; runtime jump-table targets are never guessed.
- Bank-state frontier: 1048 candidate instructions execute in the
  mapper-switched `$8000-$BFFF` window under the power-on PRG bank only.
- Translation progress: `NOT_ATTEMPTED`.
- Generated-source progress: `NOT_GENERATED`; no ROM-derived source was
  written (workspace empty). The MMC1 runtime support identity was re-derived
  in memory only: sha256 `2e3fa4ba...`, identical to the P6-10 record.
- Native-build progress: `NOT_ATTEMPTED`.
- Runtime/platform progress: `NOT_TESTED` (cannot be assessed until
  translation completes).
- Exact stop reason:
  `BLOCKED_UNSUPPORTED_OPCODE (opcode_frontier): documented-control-flow walk
  fails closed at 0xc570 (0xc570: undocumented 6502 opcode 0x7c) after 1250
  candidate instructions; no code/data boundary evidence is declared`.
- Native execution reached: **no**.
- Meaningful interactive behaviour reached: **no** (no generated host
  program, no native executable, no input plan exercised).
- Public claim: `none`; this analysis must not enter any public package.

## Independent / cross-check anchors

- `.openrecomp-phase6/evidence/P6-10/tmnt_pipeline.json` sha256
  `0b8c9014...` and `P6-10/blockers.json` sha256 `6b8b789c...` verified
  unchanged; the workflow's candidate counts, stop site and indirect sites are
  byte-equal to the P6-10 record.
- `.openrecomp-phase6/evidence/P6-12/blockers.json` sha256 `b5cb9ef4...`
  verified unchanged; the workflow's private blocker ledger and stop reason
  are byte-equal to the P6-12 recording.
- The same translation/control-flow blockers remain exactly: unsupported
  opcode, unresolved indirect control flow, bank-state ambiguity and the
  `NOT_TESTED` runtime platform. No blocker was silently patched or guessed.
- The frozen P6-09 independent MMC1 reference equivalence gate re-ran as a
  regression: `PASS tests=100`, stdout `0144086e...` identical to the recorded
  official capture.

## Negative / fail-closed coverage

Missing private path, empty plan and non-positive budget all fail closed with
`P6WorkflowError` without traceback; workspace inventory is empty; evidence
hygiene verifies that no private ROM bytes and no first/last 16 KiB PRG bank
bytes appear in any P6-13 evidence file.

## Regressions

- `tools/test_nes_rom_v1.py` (`PASS tests=12`), `tools/test_nes_platform_v1.py`
  (`PASS tests=10`), `tools/test_phase6_mmc1_inventory_v1.py`
  (`PASS tests=85`, stdout `2bfd8a5e...`), `tools/test_phase6_mmc1_variant_v1.py`
  (`PASS tests=61`, stdout `315fd5ea...`) and
  `tools/test_phase6_mmc1_reference_equiv_v1.py` (`PASS tests=100`, stdout
  `0144086e...`): all exit 0 with empty stderr (scratch evidence only; frozen
  committed evidence untouched).

## Claim ledger deltas

- No new capability: this stage observes the same bounded private frontier as
  P6-10/P6-11 through the reusable workflow. No mapper, CPU, indirect-target or
  platform semantics were added or promoted.
- Terminal marker remains `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN`;
  general compatibility remains
  `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`.

## Limitations

- TMNT is not playable and no interactive behaviour is reached; no
  compatibility claim is derived from the private observation.
- Runtime platform behaviour beyond the bounded model remains `NOT TESTED`.
- No general NES compatibility, no MMC1 board-variant coverage, no cycle or
  full PPU/APU accuracy, no FDS or arbitrary-6502 support is claimed.

## Repository side effects

- Tracked additive changes: new gate, manifest entry, updated control plane,
  P6-13 evidence. Scratch/build artifacts remain ignored; no ROM copy exists in
  the repository, evidence or workspace.

## Evidence index

`RESULT.md`, `p6_13_tests.json`, `official_runs.json`, `determinism.json`,
`private_workflow.json`, `frontier_record.json`, `anchors.json`,
`regressions.json`, `run1.txt`, `run2.txt`, `run1.err.txt`, `run2.err.txt`,
`changed_files.txt`.

## Next stage

P6-90 - Whole regression.
