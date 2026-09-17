# OpenRecomp Phase 3 Handoff

STATUS: Phase 3 `ACTIVE` — P3-00 (Phase-3 boundary) `PASS`; P3-01 (CoreMark
MIPS32 fixture acquisition/build) `PASS`; P3-02 (ELF ingestion + section/data
image) `PASS`; P3-03 (MIPS32 decode expansion) `PASS`; P3-04 (CoreMark
reachable MIPS32 semantics) `PASS`; P3-05
(ProgramModel/CFG/functions/call graph/translation units on the real ELF)
`PASS`; P3-06 (static data/global reconstruction) `PASS`; P3-07 (host emission
for CoreMark semantics) `PASS`; P3-08 (native build + generic runtime
execution) `PASS`; P3-09 (independent MIPS32 reference + equivalence) is
`ACTIVE`. The remaining
Phase-3 queue (`P3-05` .. `P3-99`) was frozen at the
P3-04 `PASS` boundary before any P3-05 implementation work; the frozen contract
is `STAGE_QUEUE.md` `## Queue freeze` (no renumber/insert/merge/split/silent
redefinition; a change requires a genuine technical dependency, fails closed
and is documented). The Phase-2 terminal state is frozen at tag
`openrecomp-phase2-pass` (annotated, object
`1a7f241b69d9500095fe84db16520ec1001db1aa`) =
`01b1d7cba8c931fca95d041389cfb1902b7c89fe`, tree
`6513eefa5ef59b7d0e127f0179c6fc6c21fdac78`, with
`OPENRECOMP_P2_99=PASS`,
`OPENRECOMP_PHASE2_FINAL_VERDICT_V1=PASS tests=202` and
`OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS`.

## P3-08 outcome (PASS)

Markers: `OPENRECOMP_P3_08=PASS`,
`OPENRECOMP_PHASE3_NATIVE_RUNTIME_V1=PASS tests=54`; terminal marker reserved
as `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN`.

- New Phase-3 gate only; no shared layer, frozen adapter, Phase-1/Phase-2
  file, gate or frozen manifest was modified.
- `tools/test_phase3_native_runtime_v1.py` re-emits and pins the P3-07
  translation, builds it with the Phase-2 deterministic build pipeline
  (`clang-cl.exe` LLVM 22.1.8 + `lld-link.exe`, `/Brepro`, two isolated runs,
  `EXECUTABLE_REPRODUCIBLE`), executes the native program three times with
  byte-identical stdout and checks CoreMark's published validation CRCs.
- `.openrecomp-phase3/SOURCE_SHA256SUMS.txt`: grown additively to seventeen
  entries; the earlier gates expect 17 entries and keep byte-identical stdout.
- Native observable: `exit_status=0`, `steps=394997250`, `pc=0x00004564`,
  `hi=0x0000000d`, `lo=0x00000000`, `uart_bytes=499`,
  `state_fnv1a64=0x5eef5d92fab65dad`, `failed=0`; executable sha256
  `9b36d6df3a3715f98a7ba41f00b63617af755fc29f42e1dc5d744b5e728445af`.
  UART contains `Correct operation validated.` with `seedcrc 0xe9f5`,
  `crclist 0xe714`, `crcmatrix 0x1fd7`, `crcstate 0x8e3a`, `crcfinal 0xd340`.
- Runtime negatives: divide by zero, taken `teq` (code preserved), unaligned
  indirect target, out-of-region write: all failed closed with the exact
  expected deterministic message.
- Official runs byte-identical (raw sha256
  `5ac6d2ca2c9f630dda7ab11259d000098c0d819da43e84e494f04400f7ddc3cd`); all
  regressions (P2-99, P3-00..P3-07, Phase-1 host gates, public safety) exit 0
  with empty stderr and unchanged stdout. Evidence under
  `.openrecomp-phase3/evidence/P3-08/`.
- CoreMark is executed natively with its own validation CRCs, but equivalence
  against an independent reference is not yet proven (P3-09).

## P3-07 outcome (PASS)

Markers: `OPENRECOMP_P3_07=PASS`,
`OPENRECOMP_PHASE3_HOST_EMISSION_V1=PASS tests=67`; terminal marker reserved as
`OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN`.

- New Phase-3 files only; no shared layer, frozen adapter, Phase-1/Phase-2
  file, gate or frozen manifest was modified.
- `.openrecomp-phase3/src/p3_host_emit_v1.py`: deterministic whole-image
  translation. 3479 emitted cases (one per decodable word), 620 delay slots,
  567 direct targets, 4 runtime-mediated indirect sites (`0x1958`, `0x3130`,
  `0x3830`, `0x39a0`), exact semantics for all 46 ops present, true delay-slot
  protocol, P2-08 ABI memory access, host calls for the UART/exit windows, and
  fail-closed UNPREDICTABLE states.
- `tools/test_phase3_host_emit_v1.py`: the P3-07 gate (67 checks).
- `.openrecomp-phase3/SOURCE_SHA256SUMS.txt`: grown additively to sixteen
  entries; P3-02..P3-06 expected 16 entries additively with unchanged stdout.
- Evidence carries the generated `coremark_program.c` and
  `coremark_support.c`; the emitted `g_image` initializer and region table are
  parsed back and equal the P3-02 guest image window and segment permissions.
- Emission determinism: two independent emissions byte-identical; official
  runs byte-identical (raw sha256
  `d7986967dbf9fb2021e86dab7902c18d294a6b52e606a0cabad13907bd317746`, empty
  stderr, exit 0).
- Regressions re-run and unchanged: P2-99 `PASS tests=202` (`66913e57...`),
  P3-00 `PASS tests=61` (`a039bbff...`), P3-01 `PASS tests=76`
  (`81eede03...`), P3-02 `PASS tests=197` (`f24f4cef...`), P3-03
  `PASS tests=201` (`15e20a2c...`), P3-04 `PASS tests=126` (`412544a4...`),
  P3-05 `PASS tests=202` (`12bf87d7...`), P3-06 `PASS tests=123`
  (`23d2f1c2...`), Phase-1 host gates `PASS=44 FAIL=0 SKIPPED=2`
  (`2a9d1bba...`), public safety `PASS` (`ad022ff1...`). Evidence under
  `.openrecomp-phase3/evidence/P3-07/`.
- CoreMark remains `NOT_PROVEN`; the generated code has not been built or
  executed yet.

## P3-06 outcome (PASS)

Markers: `OPENRECOMP_P3_06=PASS`,
`OPENRECOMP_PHASE3_STATIC_DATA_V1=PASS tests=123`; terminal marker reserved as
`OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN`.

- New Phase-3 files only; no shared layer, frozen adapter, Phase-1/Phase-2
  file, gate or frozen manifest was modified.
- `.openrecomp-phase3/src/p3_static_data_v1.py`: fail-closed static-data model
  (`.rodata` `0x46b0`+1864, `.data` `0x4e00`+40, `.bss` `0x4e30`+18416 exact
  zero-fill, the two read-only metadata sections) plus block-local
  exact-constant global analysis recording provenance for every formation and
  classifying every access (`RESOLVED_STATIC`, `RESOLVED_OUTSIDE_IMAGE`,
  `RESOLVED_REGION_UNCLASSIFIED`, `CROSS_SECTION_ACCESS`, `RUNTIME_BASE`);
  read-only loads propagate exact values and read-only stores fail closed.
- `tools/test_phase3_static_data_v1.py`: the P3-06 gate (123 checks).
- `.openrecomp-phase3/SOURCE_SHA256SUMS.txt`: grown additively to fourteen
  entries; P3-02/P3-03/P3-04/P3-05 expected 14 entries additively and their
  stdout is unchanged.
- Access model: 283 provenance-recorded constant formations (25 with uses);
  505 accesses = 10 `RESOLVED_STATIC` (3 `.data` loads of
  `default_num_contexts`; 5 `.bss` loads and 2 `.bss` stores of the p3 timer /
  UART counters), 2 `RESOLVED_OUTSIDE_IMAGE` UART stores (`0x10000000`,
  `0x10000008`), 493 `RUNTIME_BASE` with no address claim. No resolved access
  targets a seed global and no store resolves into a read-only section.
- GP/SP: `_start` sets `$28 = _gp = 0xcdf0` and `$29 = 0x9620` (stack top)
  with immediate-chain provenance; zero reachable `$28` memory bases; `$28` is
  reused as a scratch register at `0x2dc8`, `0x3108`, `0x3558`, `0x3564`;
  `GP_STATUS=NOT_REQUIRED_BY_REACHABLE_CODE`.
- Seed chain: `.rodata` table `0x4c50` materialised at `0x33e8`, index bounded
  to five entries by `sltiu`/`beq` at `0x33d4`/`0x33d8`, five seed pointers
  `0x5600/0x5604/0x4e10/0x4e14/0x5608`, two-level `get_seed_32` load shape,
  initial values `0, 0, 0x66, 0x3e8, 0` matching the P3-04 fixture constants.
- Determinism: two consecutive official runs byte-identical (4294 bytes raw,
  raw sha256
  `23d2f1c25ccf6d7e25b6f3ea7d86a0b6e9cd378a56c65f98ae053aa69b8f1c97`, LF
  sha256 `c4a1d4ff9a0b4fc96266188c0e0422837274b2d5218d8239278c4d0c9e5521ad`,
  empty stderr, exit 0).
- Regressions re-run and unchanged: P2-99 `PASS tests=202` (`66913e57...`),
  P3-00 `PASS tests=61` (`a039bbff...`), P3-01 `PASS tests=76`
  (`81eede03...`), P3-02 `PASS tests=197` (`f24f4cef...`), P3-03
  `PASS tests=201` (`15e20a2c...`), P3-04 `PASS tests=126` (`412544a4...`),
  P3-05 `PASS tests=202` (`12bf87d7...`), Phase-1 host gates
  `PASS=44 FAIL=0 SKIPPED=2` (`2a9d1bba...`), public safety `PASS`
  (`ad022ff1...`). Evidence under `.openrecomp-phase3/evidence/P3-06/`.
- CoreMark remains `NOT_PROVEN`; nothing is translated or executed.

## P3-05 outcome (PASS)

Markers: `OPENRECOMP_P3_05=PASS`,
`OPENRECOMP_PHASE3_PROGRAM_STRUCTURE_V1=PASS tests=202`; terminal marker
reserved as `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN`.

- New Phase-3 files only; no shared layer, frozen adapter, Phase-1/Phase-2
  file, gate or frozen manifest was modified.
- `.openrecomp-phase3/src/p3_structure_v1.py`: fail-closed bridge from the
  frozen P3-03 frontier records into the shared Phase-2 neutral types. Only
  `REACHABLE` words become instructions; flow is a pure function of the frozen
  record; invalid encodings, unsupported control transfers, missing/forbidden
  targets, missing delay slots, inconsistent traps, duplicate records and
  non-tiling regions fail closed with stable codes. `PROVEN` is the shared
  model's structural classification (exact decode plus reachability from the
  proven entry through resolved direct edges), not a runtime or semantics
  claim.
- `tools/test_phase3_structure_v1.py`: the P3-05 gate (202 checks).
- `.openrecomp-phase3/SOURCE_SHA256SUMS.txt`: grown additively to twelve
  entries; the P3-02/P3-03/P3-04 gates' expected entry set grew 10 -> 12
  additively and their stdout is unchanged.
- Structure (fixture `16a0a0aa...`, entry `0x4650`): 2178 neutral
  instructions (NORMAL 1787, BRANCH 198, CALL 96, JUMP 70, RETURN 24,
  INDIRECT_JUMP 3); 615 blocks; 770 edges (198 `BRANCH_TAKEN`, 198
  `BRANCH_NOT_TAKEN`, 96 `CALL_RETURN`, 205 `FALLTHROUGH`, 70 `JUMP`, 3
  unresolved `INDIRECT`); 26 PROVEN functions; 96-edge all-internal direct
  call graph; 26 translation units (entry `tu_fn_4650`); three reachable
  `jr $at` jump tables stay unresolved, the dead `jalr` at `0x1958` and the
  eight padding words stay outside the model.
- Delay-slot policy: the shared layers have no delay-slot concept, so delay
  slots are NORMAL instructions with the relationship recorded separately;
  call delay slots are the `CALL_RETURN` continuation, branch delay slots the
  `BRANCH_NOT_TAKEN` successor, and the 97 jump/return/indirect-jump delay
  slots are explicit orphan blocks (never attributed, never given an invented
  predecessor). The `ProgramModel` covers 2081 owned instructions; the CFG
  covers all 2178.
- Determinism: two consecutive official runs byte-identical (7819 bytes, raw
  sha256 `12bf87d7b5ec57dcf637c940bfb0bfc483cd03c548291cbed21b9af9cbe29573`,
  LF sha256
  `f8948ea8ab651267d22c624bbb950fa0973c7fe82dd4f5f93606754ac60f7e39`, empty
  stderr, exit 0); a second isolated ingestion/frontier/structure build
  reproduces every fingerprint and artifact hash.
- Regressions re-run and unchanged: P2-99 `PASS tests=202` (`66913e57...`),
  P3-00 `PASS tests=61` (`a039bbff...`), P3-01 `PASS tests=76`
  (`81eede03...`), P3-02 `PASS tests=197` (`f24f4cef...`), P3-03
  `PASS tests=201` (`15e20a2c...`), P3-04 `PASS tests=126` (`412544a4...`),
  Phase-1 host gates `PASS=44 FAIL=0 SKIPPED=2` (`2a9d1bba...`), public safety
  `PASS` (`ad022ff1...`). Evidence under `.openrecomp-phase3/evidence/P3-05/`.
- CoreMark remains `NOT_PROVEN`; nothing is translated or executed.

## P3-04 outcome (PASS)

Markers: `OPENRECOMP_P3_04=PASS`,
`OPENRECOMP_PHASE3_COREMARK_REACHABLE_SEMANTICS_V1=PASS tests=126`; terminal
marker reserved as `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN`.

- Control-plane reconciliation (documented in `STAGE_QUEUE.md`): P3-04 is the
  reachable-semantics stage; the ProgramModel/CFG/functions/call
  graph/translation-units work moved to P3-05 and the later provisional stage
  IDs shifted by one (static data P3-06, host emission P3-07, native
  build/runtime P3-08, independent reference P3-09, package P3-10).
- New Phase-3 files only; no tracked file, Phase-2 file, root manifest or
  frozen evidence was modified (`git diff`/`git diff --cached` empty). No
  commit was requested, so all Phase-3 additions remain untracked.
- `.openrecomp-phase3/src/p3_semantics_mips32_v1.py`: exact fail-closed MIPS32
  semantics for the P3-01 bounded class (`movz`, `movn`, `mul`, `divu`,
  `teq`, `swl`, `swr`, `jalr`) with `$zero` write discard, signed 32x32
  product low half, unsigned quotient/remainder + divide-by-zero refusal,
  trap refusal with preserved code, little-endian partial-word store merging,
  `jalr` link `address + 8` + unaligned-target refusal, and HI/LO marked
  UNPREDICTABLE after `mul`. Decode and control-flow layers stay untouched;
  the 82 words keep their frozen `RECOGNIZED_UNSUPPORTED` classification and
  semantics is an explicit overlay.
- `tools/test_phase3_reachable_semantics_v1.py`: the P3-04 gate (126 checks).
- `.openrecomp-phase3/SOURCE_SHA256SUMS.txt`: grown additively to ten entries
  (manifest sha256 `e4db427b...`); the P3-02 and P3-03 gates were extended
  8 -> 10 additively and still emit byte-identical stdout to their recorded
  captures.
- Exact frontier table: 82 recognized-unsupported words = 55 reachable + 27
  unreachable, each with address, word, mnemonic, operands, reachability,
  containing function and implementation status
  (`reachable_unsupported_before.json`, `reachable_unsupported_after.json`).
  Reachable semantic gap after P3-04 is zero; 2178/2178 reachable words are
  semantically supported. Reachability hash unchanged
  (`c62d5483...`); the three `jr $at` jump tables, the dead `jalr` at `0x1958`
  and the eight padding words are unchanged and unresolved.
- Reference verification: 459 differential vectors plus 24 compiler-idiom
  `swl`+`swr` composition checks against an independently written in-gate
  model; every one of the 82 sites executed on both models; 16 fail-closed
  negatives (unsupported op, divide-by-zero, taken trap, unaligned `jalr`,
  unpredictable HI/LO read, memory faults, unsupported endianness, malformed
  records).
- Exception frontier: all six reachable div/trap sites classified with
  evidence (fixture seed values and the `movz` default; dominance of the
  `beq $2,$0` guards; pure same-argument `time_in_secs`; non-entered
  auto-calibration block) — zero unresolved runtime requirements, and the
  model still fails closed if any condition were ever true.
- Determinism: two official runs byte-identical (stdout raw sha256
  `412544a413bbe3e55e688bc45e379dccfe4e8b4ebdc299211ccba2a832e39b36`, 5202
  bytes, empty stderr); evidence artifacts byte-identical across runs.
- Regressions re-run and unchanged: P3-00 `PASS tests=61` (`a039bbff...`),
  P3-01 `PASS tests=76` (`81eede03...`), P3-02 `PASS tests=197`
  (`f24f4cef...`), P3-03 `PASS tests=201` (`15e20a2c...`), P2-99
  `PASS tests=202` (`66913e57...`), Phase-1 host gates
  `PASS=44 FAIL=0 SKIPPED=2` (`2a9d1bba...`), public safety `PASS`; frozen
  Phase-2 tracked tree unchanged and frozen P2-99 identities re-verified.
- CoreMark remains `NOT_PROVEN`; nothing is translated or executed.

## P3-03 outcome (PASS)

Markers: `OPENRECOMP_P3_03=PASS`,
`OPENRECOMP_PHASE3_COREMARK_DECODE_FRONTIER_V1=PASS tests=201`; terminal
marker reserved as `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN`.

- New Phase-3 files only; no tracked file, Phase-2 file, root manifest or
  frozen evidence was modified (`git diff`/`git diff --cached` empty). No
  commit was requested, so all Phase-3 additions remain untracked.
- `.openrecomp-phase3/src/p3_decode_mips32_v1.py`: additive fail-closed
  decode/classification layer over the frozen bounded adapter. The adapter is
  left untouched (hash-pinned by the root manifest and P3-01 gate); the P3-01
  classes (`movz`, `movn`, `mul`, `div`/`divu`, trap family incl. `teq`,
  `swl`, `swr`, `jalr`, plus same-family `lwl`/`lwr`/`addi`/branch-likely
  forms) are decoded with exact operands but remain `RECOGNIZED_UNSUPPORTED`
  (decode support never implies semantic support); reserved/unknown encodings
  are fail-closed `RESERVED_ENCODING`/`UNKNOWN_ENCODING`.
- `.openrecomp-phase3/src/p3_code_frontier_v1.py`: deterministic reachability +
  control-flow frontier engine (direct branches/jumps/calls/returns with MIPS32
  delay slots from the ELF entry; delay slots are entered but never generate
  fall-through; indirect targets never invented; flow stops at invalid
  encodings and unresolvable delay slots).
- `tools/test_phase3_decode_frontier_v1.py`: the P3-03 gate (201 checks).
- `.openrecomp-phase3/SOURCE_SHA256SUMS.txt`: extended to eight Phase-3
  source/gate files, manifest sha256
  `79bc827dbc9842654864a21a36e358b8926308f6daab1a27ab3e99efbcd29eb9`.
- Documented contract growth: `tools/test_phase3_elf_ingestion_v1.py` expected
  entry set extended 5 -> 8 (additive; every entry still verified; stdout
  still byte-identical to the recorded P3-02 capture `f24f4cef...`). This is
  the intentional stage-grown-manifest contract, recorded here and in the
  P3-03 `RESULT.md`/`STATE.md`.
- CoreMark frontier (fixture `16a0a0aa...`, `.text` 3487 words, entry
  `0x4650`): decoded 3479 (supported 3397, recognized-unsupported 82),
  reserved 8, unknown 0; reachable 2178 (supported 2123, unsupported 55,
  invalid 0); unreachable 1309 = 8 non-code padding + 1301 unreached code (687
  words in 22 dead standalone functions, 614 behind three unresolved `jr $at`
  jump-table sites in `core_state_transition`/`ee_printf`). Exact unsupported
  histogram total/reachable/unreachable: `movz` 35/21/14, `movn` 12/9/3,
  `mul` 22/15/7, `divu` 4/3/1, `teq` 4/3/1, `swl` 2/2/0, `swr` 2/2/0,
  `jalr` 1/0/1. Control flow: 96 direct calls, 198 conditional branches, 70
  jumps, 24 returns; indirect sites 4 (three reachable `jr $at` (resolve
  register `$at`) plus the single `jalr $ra,$t9` at `0x1958`, which is inside
  dead code) with no target invented.
- Padding re-evaluated from evidence: the eight `0x04170001` words are
  unreachable reserved-encoding alignment padding proven by reachability +
  reserved REGIMM `rt=0x17` + exact symbol-gap position
  (`padding_invalid_classification.md`); nothing inherited from P3-01.
- Negative coverage: 21 reserved/unknown/malformed decode panels, 8 exact
  operand panels, 8 input-validation panels, 13 synthetic reachability
  fixtures (incl. the delay-slot fall-through suppression regression).
- Determinism: two official gate runs byte-identical (stdout raw sha256
  `15e20a2c9a6e4eba629e67ceb14b70db8bf367c9ffe1d69473be57e7a8091878`, 7910
  bytes, empty stderr); isolated evidence-directory run byte-identical for all
  9 gate artifacts including `RESULT.json` (`deterministic_run.json`).
- Regressions re-run and unchanged: P3-00 `PASS tests=61` (`a039bbff...`),
  P3-01 `PASS tests=76` (`81eede03...`), P3-02 `PASS tests=197`
  (`f24f4cef...`), P2-99 `PASS tests=202` (`66913e57...`), Phase-1 host gates
  `PASS=44 FAIL=0 SKIPPED=2` (`2a9d1bba...`), public safety `PASS`
  (`ad022ff1...`). Evidence under `.openrecomp-phase3/evidence/P3-03/`.
- CoreMark remains `NOT_PROVEN`; no execution/translation semantics were
  added.

## P3-02 outcome (PASS)

Markers: `OPENRECOMP_P3_02=PASS`,
`OPENRECOMP_PHASE3_MIPS32_ELF_INGESTION_V1=PASS tests=197`; terminal
marker reserved as `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN`.

- New files only; no tracked file, Phase-2 file, gate or frozen manifest was
  modified (`git diff` and `git diff --cached` are empty). No commit was
  requested, so the Phase-3 additions remain untracked working-tree files.
- `.openrecomp-phase3/src/p3_elf_image_v1.py`: architecture-neutral fail-closed
  ELF32 ingestion plus the sparse deterministic `GuestImage` with
  bounds-checked access; `.openrecomp-phase3/src/p3_target_mips32_v1.py`:
  MIPS32 O32 target policy layer; `tools/test_phase3_elf_ingestion_v1.py`:
  the P3-02 gate.
- `.openrecomp-phase3/SOURCE_SHA256SUMS.txt`: Phase-3 source manifest for the
  three Phase-3 gates and the two P3-02 source modules. The frozen root
  `SOURCE_SHA256SUMS.txt` is unchanged (`76f77bbc...`, 134 entries) and every
  entry re-verifies.
- CoreMark ingestion (fixture `16a0a0aa...`, 31184 bytes) matches the P3-01
  characterisation exactly; `.text`/`.rodata`/`.data` reconstructed bytes equal
  direct file slices; load map `0x0`+308 `r--`, `0x1000`+13948 `r-x`,
  `0x4680`+1912 `r--`, `0x4e00` filesz 40 / memsz 18464 `rw-` with a 18424-byte
  zero-fill tail; loaded-image identity
  `e072b38dd1404a243fa61c4dd7d17b7d7d50f268650318756a4ef9629c1d88d4`.
- BSS/NOBITS proof: `.bss` (`0x4e30`, 18416) has `file_size=0`; its declared
  file range (offset 20008, end 38424) crosses the 31184-byte EOF and the file
  bytes there are non-zero, yet the image is exactly 18416 zeros
  (`c7d9a612...`), equal to the zeros hash.
- 47 synthetic malformed fixtures are each rejected with the exact expected
  deterministic classification (no traceback); 3 positive synthetic cases
  cover `NOBITS` declared over non-zero file bytes and `NOBITS` beyond EOF.
- Determinism: two consecutive official gate runs byte-identical (stdout raw
  sha256 `f24f4cef...`, 7344 bytes, empty stderr); two isolated evidence runs
  produced byte-identical artifact sets including `RESULT.json`.
- Regressions re-run and unchanged: P3-00 `PASS tests=61` (`a039bbff...`),
  P3-01 `PASS tests=76` (`81eede03...`), P2-99 `PASS tests=202`
  (`66913e57...`), Phase-1 host gates `PASS=44 FAIL=0 SKIPPED=2`, public
  safety `PASS`. Evidence under `.openrecomp-phase3/evidence/P3-02/`.
- CoreMark remains `NOT_PROVEN`; no instruction semantics, translation or
  execution were added.

## P3-01 outcome (PASS)

Markers: `OPENRECOMP_P3_01=PASS`,
`OPENRECOMP_PHASE3_COREMARK_MIPS32_FIXTURE_V1=PASS tests=76`; terminal
marker reserved as `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN`.

- CoreMark pinned at `eembc/coremark`
  `1f483d5b8316753a742cbf5590caf5bd0a4e4777`; upstream sources retained
  verbatim (LF blobs) under `.openrecomp-phase3/external/coremark/` with
  recorded sha256; five of six upstream `coremark.md5` entries reproduce and
  the stale upstream `coremark.h` entry is recorded, not patched.
- Toolchain `zig cc` 0.13.0 (clang 18.1.5, LLD 18.1.6,
  `mipsel-linux-musl`), acquired from the official URL with published-hash
  verification; no toolchain binary is committed.
- Fixture ELF sha256
  `16a0a0aa0f62344d8c0f309b755450f09c330e7c5a7c355785662d7a141f7669`
  (31184 bytes), byte-identical across two isolated build roots,
  `EXECUTABLE_REPRODUCIBLE`.
- Inventory: 3487 instruction words; 3397 supported by the bounded
  OpenRecomp adapter; 90 unsupported (`movz` 35, `movn` 12, `mul` 22,
  `divu` 4, `teq` 4, `swl` 2, `swr` 2, `jalr` 1, `0x04170001` padding 8).
- Two consecutive official gate runs byte-identical (stdout raw sha256
  `81eede03...`), empty stderr; evidence under
  `.openrecomp-phase3/evidence/P3-01/`.
- Control-plane maintenance during P3-01: the P3-00 gate now scopes its
  determinism/manifest check to the five governance files (build inputs,
  toolchain caches, external sources and evidence are out of scope) and its
  untracked allowlist admits `tools/test_phase3_*`; P3-00 still re-passes
  with unchanged stdout (`a039bbff...`).
- No OpenRecomp source was modified; no Phase-2 file, gate or evidence was
  touched; the CoreMark build is not committed.

## P3-00 outcome (PASS)

Markers: `OPENRECOMP_P3_00=PASS`,
`OPENRECOMP_PHASE3_BOUNDARY_V1=PASS tests=61`; terminal marker reserved as
`OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN`.

- Gate `tools/test_phase3_boundary_v1.py` verified the frozen boundary, the
  unchanged Phase-2 evidence, the preserved verification context, the
  byte-identical P2-99 terminal re-verification, the deterministic Phase-3
  control plane, the worktree residue classification and the
  CoreMark-not-proven state.
- Two consecutive official runs were byte-identical (stdout raw sha256
  `a039bbffa55afd786e7b44427c5aafe0b09aff6f8309e1e6c643ad812b5b7c73`),
  empty stderr; captures and the machine record are under
  `.openrecomp-phase3/evidence/P3-00/`.
- No Phase-2 file, gate or evidence was modified; the P3-00 gate and control
  plane are untracked working-tree additions (no Phase-3 commit was
  requested).

Branch: `phase3/mips32-real-elf-v1` (created from the frozen Phase-2 PASS
tree). Phase-2 branch `phase2/opencode-v1` remains at the first freeze commit
`b935699991bdcbea518e5f6fbbd69ecb45bc12cf`; the verification-context
correction commit lives on the Phase-3 branch history.

## Frozen boundary identities

- Phase-2 commit: `01b1d7cba8c931fca95d041389cfb1902b7c89fe`
- Phase-2 tree: `6513eefa5ef59b7d0e127f0179c6fc6c21fdac78`
- Phase-2 annotated tag object: `1a7f241b69d9500095fe84db16520ec1001db1aa`
- Freeze commits:
  - `b935699991bdcbea518e5f6fbbd69ecb45bc12cf` — `phase2: close end-to-end
    recompilation proof`
  - `01b1d7cba8c931fca95d041389cfb1902b7c89fe` — `phase2: keep
    verification-context files untracked in the freeze`
- `SOURCE_SHA256SUMS.txt` sha256:
  `76f77bbc97780afe9c2b41a0cb89b5323ab22450c4b2a368dd03fb4d7bbe1095`
- `.openrecomp-phase2/evidence/P2-99/RESULT.json` sha256:
  `880d25961949b0dc9aedaca78ca60d2dac54bbffeb6fd61e63045acd6394d8df`
- P2-99 gate sha256:
  `8d6a42d5e335fb7d7612bb222adca19be0e5290a26a8cc65e63b8be0b9e64e21`
- terminal P2-99 stdout sha256:
  `66913e5752a9e2b7e399513710b4dce05efce9a714335c3b9908c0e30ea38c28`
- frozen verification-context manifest sha256 (28 files, untracked):
  `40e4f23a35f40c5d25da630467d46f5e8ad8409a40efff8412892217447a8349`
- Phase-1 tag `openrecomp-phase1-pass` =
  `46c2f971e1a42cf49bd936bad94697b81bf31002` (unchanged)

## Verification performed on the frozen tree

- `python tools/test_phase2_final_verdict_v1.py` (verify-only)
  -> exit 0, empty stderr, `OPENRECOMP_P2_99=PASS`,
  `OPENRECOMP_PHASE2_FINAL_VERDICT_V1=PASS tests=202`,
  `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS`; stdout byte-identical to
  the four recorded official terminal runs
  (`66913e5752a9e2b7e399513710b4dce05efce9a714335c3b9908c0e30ea38c28`)
- `python tools/phase1_host_gates_v1.py`
  -> `OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2`,
  `OPENRECOMP_PHASE1_HOST_GATES_V1=PASS`
- `python tools/public_safety_scan.py` -> `OPENRECOMP_PUBLIC_SAFETY=PASS`

## Freeze correction record

The first freeze commit (`b935699`) tracked every audited Phase-2 file. That
changed the tracked-file context relative to the official Phase-2 verification
and made the frozen gates fail:

- 27 Phase-2 captures are UTF-16LE PowerShell stdout/regression artifacts;
  the Phase-1 `public-safety-scan` gate strictly decodes every tracked `.txt`
  as UTF-8 and rejects them.
- `tools/test_build_package_reproducibility_v1.py` contains the literal
  private-key rejection needle exercised by its own package content policy
  test; the tracked-tree public-safety marker scan rejects it.

The correction commit (`01b1d7c`) removes exactly those 28 files from the
index while leaving their bytes on disk unchanged; they remain hash-pinned by
`SOURCE_SHA256SUMS.txt` and the frozen stage evidence. With that correction
every frozen verification above re-passes, including the full Phase-1 host
gate suite. The tag was moved to the corrected commit before any Phase-3
implementation work began.

## Documented untracked sets

- Frozen verification-context files (28, must stay untracked; see above).
- Phase-3 verification captures that must stay untracked (32): the
  platform-CRLF stdout captures (`run1.txt`, `run2.txt`,
  `p2_99_reverify_stdout.txt`, the earlier-stage `regression_*.txt` captures
  and P3-03's `RESULT.md`) in the `P3-00` .. `P3-04` evidence directories. `.gitattributes` pins `*.txt`
  and `*.md` to LF, so tracking them would change their bytes relative to the
  raw stdout hashes recorded in their `RESULT.json` / control-plane records.
  Their bytes are preserved on disk and hash-pinned by the stage evidence and
  regression captures. The P3-05 boundary onward writes LF-normalized captures
  and records both raw and LF hashes in `official_runs.json` /
  `regression_summary.json`, so those captures are tracked.
- Frozen verification checks re-run after P3-02:
  - `python tools/test_phase2_final_verdict_v1.py` -> `PASS tests=202`,
    stdout byte-identical (`66913e57...`), empty stderr;
  - `python tools/phase1_host_gates_v1.py` -> `PASS=44 FAIL=0 SKIPPED=2`
    (source integrity: verified 134 entries);
  - `python tools/public_safety_scan.py` -> `OPENRECOMP_PUBLIC_SAFETY=PASS`;
  - `python tools/test_phase3_coremark_fixture_v1.py` -> `PASS tests=76`,
    stdout byte-identical (`81eede03...`);
  - `python tools/test_phase3_boundary_v1.py` -> `PASS tests=61`,
    stdout unchanged (`a039bbff...`);
  - `python tools/test_phase3_elf_ingestion_v1.py` -> `PASS tests=197`,
    stdout byte-identical across runs (`f24f4cef...`).
- Pre-existing untracked residue (275 files):
  `.openrecomp-phase2/backups/`, `.openrecomp-phase2/scratch/`,
  `artifacts/mips32_translation_v1/`,
  `artifacts/mips32_translation_evidence_closure_v1/`;
  residue manifest sha256
  `18e503bf3425c44e72ffc0303d8c71a9f0b2a3ad85062f548519f730919c1f8a`.
- Phase-3 working sets:
  - tracked at the P3-05 boundary: `.openrecomp-phase3/` control plane,
    evidence (`P3-00` .. `P3-05`), P3 port files, P3 source modules
    (`.openrecomp-phase3/src/`: `p3_elf_image_v1.py`,
    `p3_target_mips32_v1.py`, `p3_decode_mips32_v1.py`,
    `p3_code_frontier_v1.py`, `p3_semantics_mips32_v1.py`,
    `p3_structure_v1.py`), the Phase-3 source manifest
    (`.openrecomp-phase3/SOURCE_SHA256SUMS.txt`, 12 entries) and
    `tools/test_phase3_boundary_v1.py`,
    `tools/test_phase3_coremark_fixture_v1.py`,
    `tools/test_phase3_elf_ingestion_v1.py` (documented expected manifest
    entry-set growth 5 -> 8 -> 10 -> 12, additive),
    `tools/test_phase3_decode_frontier_v1.py` (same documented growth),
    `tools/test_phase3_reachable_semantics_v1.py`,
    `tools/test_phase3_structure_v1.py`;
  - intentionally untracked (bytes preserved, hash-pinned by evidence):
    external CoreMark sources (`.openrecomp-phase3/external/coremark/`),
    the toolchain copy (`.openrecomp-phase3/tools/zig/`, 0.13.0
    distribution), build roots (`.openrecomp-phase3/build/`, also
    gitignored), and the platform-line-ending shell captures of the earlier
    evidence directories (`run*.txt`, `regression_*.txt`, `changed_files.txt`
    with CRLF), whose recorded raw hashes only match their on-disk bytes.

## Exact next action

Execute P3-09 (independent MIPS32 reference + equivalence, frozen queue row):

1. Implement an independent MIPS32 reference execution under
   `.openrecomp-phase3/src/` (its own decoder/interpreter, written separately
   from the P3-07 emitter and the P3-04 semantics module) that executes the
   audited ELF from the documented flat-image initial state with the same
   memory/MMIO/observable contract.
2. Prove deterministic observable equivalence with the P3-08 native observable
   (exit status, step count, PC, HI/LO, UART stream, state digest) and record
   the evidence under `.openrecomp-phase3/evidence/P3-09/`.
3. Update `.openrecomp-phase3/SOURCE_SHA256SUMS.txt` for the new Phase-3
   source/gate files and update the control plane.

## Constraints

Do not modify or rewrite Phase-2 evidence, gates, control plane or the P2-99
verdict. Do not treat CoreMark as supported before its stages pass. Do not
commit the CoreMark build output, the CoreMark upstream sources or the
toolchain distribution; they stay untracked, reproducibly regenerated and
hash-pinned by evidence.
