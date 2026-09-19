# P6-99 Final Phase-6 Verdict - Result

Verdict: `PASS` (terminal marker issued for the bounded audited public MMC1
claim only; general NES compatibility permanently `NOT_PROVEN`)

## Baseline

- Branch `phase6/nes-compat-v1` at the P6-91 boundary commit
  `69cb116f87be0a0ac444097c940bfc2ba50716bc`, tree
  `5336b865367ce49bc58128d5a87344fd41d5bff5`, descending from the Phase-5
  frozen boundary `e8d3627a622d0ca3196b117c5112f29fabdb49e7` (tag object
  `b5d6832ba2374b810f4c24500ed9093a9481fd8d`, tree
  `468fb9788350de393d3de2ca9471b7d874ee8dc9`).

## Objective (frozen queue)

Issue `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=PASS` only if the exact audited
public MMC1 static-recompilation claim is proven. Always retain
`OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`. The PASS must not
imply all MMC1 boards/revisions, all NES games, commercial-game compatibility,
cycle accuracy, full PPU/APU accuracy, FDS compatibility or arbitrary 6502
compatibility.

## Official gate

- Runner: `python .openrecomp-phase6/src/p6_stage_runner_v1.py --stage P6-99
  --script tools/test_phase6_final_verdict_v1.py --evidence-dir
  .openrecomp-phase6/evidence/P6-99 --tests-json p6_99_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical:
  - stdout: 3750 bytes raw, raw sha256
    `d7e96e11d94202fff91380dc4020e5523aa7d87dacfb3f05ee35cbf469d3a365`,
    LF sha256
    `4fafd3842eb1df3d7f44f166cec6bd064d28e71121fffdb882e7ca1969c2978a`.
  - `p6_99_tests.json` sha256
    `e7e462f15ca64a2d8db130ec664ac309d5ebfef1c128fd392111d19e4be30ea4`,
    `tests=108`; both runs produced the same tests-json hash.
- Terminal markers: `OPENRECOMP_P6_99=PASS`,
  `OPENRECOMP_PHASE6_FINAL_VERDICT_V1=PASS tests=108`,
  `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=PASS`,
  `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`.

## Claim asserted

`OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=PASS` asserts exactly the bounded
audited public MMC1 static-recompilation platform claim rooted in the
`MMC1_SUBSET_V1` profile and the original Apache-2.0 public proof fixture:
deterministic MMC1 serial/PRG/CHR/mirroring behaviour, static recompilation,
reproducible native build, deterministic native execution and exact
independent-reference equivalence, plus the reusable workflow demonstrated end
to end on that fixture.

## Claim explicitly not asserted

- general NES compatibility (permanent
  `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`);
- all MMC1 boards, revisions or wiring variants (only variant V-001);
- all NES games or commercial-game compatibility;
- cycle accuracy;
- full PPU or full APU accuracy;
- Famicom Disk System compatibility;
- arbitrary 6502 compatibility;
- any compatibility derived from the private TMNT image, which is not playable
  and remains `UNPROVEN` with its exact blockers recorded.

## Verified identities

- Public MMC1 proof fixture ROM sha256 `9e10dce5...` (64 KiB PRG, 32 KiB CHR,
  mapper 1/submapper 0).
- Host program `6c1ccac5...`; MMC1 runtime support `c15980d4...`; native
  executable `0ba034bd...` with `EXECUTABLE_REPRODUCIBLE` classification.
- Native observables: `failed=0`, `exit=1`, `steps=82731`, `pc=0xC089`,
  `frames=9`, `nmi=6`, `clock=241746`, `mmc1_regs=1F070703`, transcript
  `0101010101010000`, nine-frame transcript.
- Independent reference equivalence: all three plans (`p6_08`, `all_buttons`,
  `mixed_bits`) `equivalent=true` with zero mismatches.
- Platform expansion decision `NO_ADDITION_JUSTIFIED` with empty additions.
- Workflow `p6_rom_to_native_v1`: public pipeline `COMPLETED`, zero blockers,
  no ROM copied.
- Whole regression: P5-90 reconstruction byte-identical (`e487dbc0...`) and
  all 14 Phase-6 stage gates byte-identical to their official captures.
- Evidence index: 181 files indexed; claim record counts Phase-5 7/4,
  Phase-6 11/5, private observations 4 with 4 blockers, general 8 unproven /
  9 unsupported / 8 not tested.
- Source integrity: Phase-6 manifest verified entry-wise; root/Phase-3
  manifest identities; P3-99/P4-99/P5-99 records and gate hashes verified;
  private image identity `2a9345e6...` / 262160 bytes.

## Scope guard and fail-closed coverage

The gate re-verifies the claim scope and rejects (fails closed) any promotion
of general NES compatibility, any promotion of the private compatibility
status, any promotion of the general compatibility marker, and any demotion of
the bounded public MMC1 claim from `PROVEN`. Evidence hygiene verifies that no
private ROM bytes appear in any P6-99 evidence file while the private identity
is recorded by hash only.

## Terminal state

- `STATE.md`: `CURRENT_STAGE=P6-99`, `LAST_PASSED_STAGE=P6-99`,
  `STATUS=COMPLETE`, `MMC1_PLATFORM_STATUS=PROVEN`, `FINAL_VERDICT=PASS`,
  terminal marker `PASS`, general marker `NOT_PROVEN`.
- `STAGE_QUEUE.md`: row `P6-99` `COMPLETE`; terminal marker issued `PASS` for
  the bounded claim only; general marker never promoted.
- `HANDOFF.md`: Phase-6 terminal outcome recorded; no further Phase-6 stage
  remains.
- Terminal tag: **not created**. The frozen Phase-6 control policy does not
  require a terminal tag; the terminal boundary is the P6-99 verdict commit,
  recorded in `STATE.md`/`HANDOFF.md`/this evidence.

## Limitations (retained)

- The private TMNT image remains not playable; its four exact blockers
  (undocumented `0x7C` at `0xC570`, unresolved `jmp ($E2)` at
  `0x86E8`/`0x8956`/`0x8F3C`, 1048 power-on low-window candidates,
  `NOT_TESTED` runtime platform) remain unresolved and are not patched.
- The workflow supports the bounded MMC1 subset only; runtime-bank execution,
  unsupported variants and non-supported mappers fail closed.
- Timing is a documented base-cost model; graphics/audio observables are
  bounded state views.
- Two Phase-1 host checks remain `SKIPPED_TOOLCHAIN_UNAVAILABLE` (external
  POSIX/gcc toolchains), exactly as frozen.

## Repository side effects

- Tracked additive changes: new verdict gate, manifest entry, control-plane
  terminal updates, P6-99 evidence. Scratch artifacts remain ignored; no ROM
  copy exists.

## Evidence index

`RESULT.md`, `p6_99_tests.json`, `official_runs.json`, `determinism.json`,
`terminal_verdict.json`, `verdict_record.json`, `run1.txt`, `run2.txt`,
`run1.err.txt`, `run2.err.txt`, `changed_files.txt`.

## Next stage

None. Phase 6 is COMPLETE at the terminal `PASS` boundary for the bounded
audited public MMC1 claim; general NES compatibility remains `NOT_PROVEN`.
