# OpenRecomp Phase 3 State

PHASE=3
BASELINE_TAG=openrecomp-phase2-pass
BASELINE_COMMIT=01b1d7cba8c931fca95d041389cfb1902b7c89fe
BASELINE_TREE=6513eefa5ef59b7d0e127f0179c6fc6c21fdac78
CURRENT_STAGE=P3-99
LAST_PASSED_STAGE=P3-91
STATUS=ACTIVE
FINAL_VERDICT=NOT_PROVEN
COREMARK_STATUS=NOT_PROVEN
QUEUE_FREEZE=FROZEN
QUEUE_FREEZE_STAGES=P3-05..P3-99

## Phase-2 frozen boundary identities

- Tag `openrecomp-phase2-pass` (annotated, object
  `1a7f241b69d9500095fe84db16520ec1001db1aa`) resolves to commit
  `01b1d7cba8c931fca95d041389cfb1902b7c89fe`, tree
  `6513eefa5ef59b7d0e127f0179c6fc6c21fdac78`.
- Freeze commits: `b935699991bdcbea518e5f6fbbd69ecb45bc12cf` (close) and
  `01b1d7cba8c931fca95d041389cfb1902b7c89fe` (verification-context
  correction, untracks 28 context files while keeping their bytes on disk).
- Phase-2 terminal markers on the frozen tree:
  `OPENRECOMP_P2_99=PASS`,
  `OPENRECOMP_PHASE2_FINAL_VERDICT_V1=PASS tests=202`,
  `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS`.
- Frozen integrity identities:
  - `SOURCE_SHA256SUMS.txt` sha256
    `76f77bbc97780afe9c2b41a0cb89b5323ab22450c4b2a368dd03fb4d7bbe1095`
    (134 manifest entries)
  - `.openrecomp-phase2/evidence/P2-99/RESULT.json` sha256
    `880d25961949b0dc9aedaca78ca60d2dac54bbffeb6fd61e63045acd6394d8df`
  - `tools/test_phase2_final_verdict_v1.py` sha256
    `8d6a42d5e335fb7d7612bb222adca19be0e5290a26a8cc65e63b8be0b9e64e21`
  - terminal P2-99 gate stdout sha256
    `66913e5752a9e2b7e399513710b4dce05efce9a714335c3b9908c0e30ea38c28`
  - frozen P2-90 capture
    `.openrecomp-phase2/evidence/P2-90/p2_90_run1.txt` sha256
    `74e9eadaf0e17ca4a97790e4239f40883cc745cd9817c172f7fa6e2663ce1ee7`
- Frozen verification-context files (28, present on disk, intentionally
  untracked): canonical manifest sha256
  `40e4f23a35f40c5d25da630467d46f5e8ad8409a40efff8412892217447a8349`.
  27 are UTF-16LE stdout/regression captures rejected by the strict-UTF-8
  Phase-1 public-safety-scan gate when tracked; one is
  `tools/test_build_package_reproducibility_v1.py`, whose package content
  policy test contains the literal private-key rejection needle. The official
  Phase-2 verification was performed with these files untracked; the freeze
  preserves that condition.
- Phase-1 boundary remains `openrecomp-phase1-pass` =
  `46c2f971e1a42cf49bd936bad94697b81bf31002`.
- Documented pre-existing untracked residue intentionally outside the frozen
  tree: `.openrecomp-phase2/backups/`, `.openrecomp-phase2/scratch/`,
  `artifacts/mips32_translation_v1/`,
  `artifacts/mips32_translation_evidence_closure_v1/` (275 files, manifest
  sha256 `18e503bf3425c44e72ffc0303d8c71a9f0b2a3ad85062f548519f730919c1f8a`).

## Queue freeze record (P3-04 boundary)

- Frozen contract: `.openrecomp-phase3/STAGE_QUEUE.md` `## Queue freeze`, rows
  `P3-05` .. `P3-99` exactly as listed, effective before any P3-05
  implementation work.
- Rules (see the queue section): no renumber/insert/merge/split/silent
  redefinition; a change requires a genuine technical dependency, must fail
  closed with an explicit blocker record, and must be documented in the
  reconciliation log with the forcing evidence.
- No stage status changed at the freeze: `P3-05` is the executing stage and
  `P3-06` .. `P3-99` stay `QUEUED` until their own gates pass.
- The freeze is a control-plane record only: no capability claim, no change to
  the frozen Phase-1/Phase-2 boundaries and no promotion of CoreMark.

## Stage ledger

| ID | Stage | Status | Evidence |
| --- | --- | --- | --- |
| P3-00 | Phase-3 boundary | `PASS` | `.openrecomp-phase3/evidence/P3-00/` |
| P3-01 | CoreMark MIPS32 fixture acquisition/build | `PASS` | `.openrecomp-phase3/evidence/P3-01/` |
| P3-02 | ELF ingestion + section/data image | `PASS` | `.openrecomp-phase3/evidence/P3-02/` |
| P3-03 | MIPS32 decode expansion | `PASS` | `.openrecomp-phase3/evidence/P3-03/` |
| P3-04 | CoreMark reachable MIPS32 semantics | `PASS` | `.openrecomp-phase3/evidence/P3-04/` |
| P3-05 | ProgramModel/CFG/functions/call graph/translation units | `PASS` | `.openrecomp-phase3/evidence/P3-05/` |
| P3-06 | Static data/global reconstruction | `PASS` | `.openrecomp-phase3/evidence/P3-06/` |
| P3-07 | Host emission for CoreMark semantics | `PASS` | `.openrecomp-phase3/evidence/P3-07/` |
| P3-08 | Native build + generic runtime execution | `PASS` | `.openrecomp-phase3/evidence/P3-08/` |
| P3-09 | Independent MIPS32 reference + equivalence | `PASS` | `.openrecomp-phase3/evidence/P3-09/` |
| P3-10 | Reproducible package + whole regression | `PASS` | `.openrecomp-phase3/evidence/P3-10/` |
| P3-90 | Phase-3 whole regression | `PASS` | `.openrecomp-phase3/evidence/P3-90/` |
| P3-91 | Evidence index + limitations | `PASS` | `.openrecomp-phase3/evidence/P3-91/` |
| P3-99 | Final verdict | `ACTIVE` | - |

## P3-00 acceptance criteria

1. Phase-2 frozen tag `openrecomp-phase2-pass` resolves to the recorded commit
   and tree, and the Phase-3 branch descends from that boundary.
2. Phase-2 final evidence is unchanged: the frozen integrity identities above
   re-verify on disk and in Git.
3. `python tools/test_phase2_final_verdict_v1.py` (verify-only) still passes
   with `OPENRECOMP_P2_99=PASS` and
   `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS`, byte-identical to the
   recorded terminal stdout.
4. The Phase-3 control plane exists (STATE, HANDOFF, STAGE_QUEUE, SCOPE,
   CONTROL_POLICY, evidence/) and is deterministic.
5. CoreMark has not been treated as proven or supported:
   `COREMARK_STATUS=NOT_PROVEN`.

## P3-00 result (PASS)

Stage: `OPENRECOMP_PHASE3_BOUNDARY_V1`. Evidence:
`.openrecomp-phase3/evidence/P3-00/`. Gate:
`tools/test_phase3_boundary_v1.py`.

Markers issued:

- Stage marker: `OPENRECOMP_P3_00=PASS`
- Gate marker: `OPENRECOMP_PHASE3_BOUNDARY_V1=PASS tests=61`
- Terminal marker (reserved): `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN`

Verified on the frozen tree (commit
`01b1d7cba8c931fca95d041389cfb1902b7c89fe`):

- Tag `openrecomp-phase2-pass` (annotated) resolves to the recorded
  commit/tree; branch `phase3/mips32-real-elf-v1` descends from that boundary
  (`merge-base` is the boundary commit).
- Frozen Phase-2 evidence re-verified byte-for-byte on disk:
  `SOURCE_SHA256SUMS.txt` (134 entries), `P2-99/RESULT.json`, the P2-99 gate,
  `P2-99/run1.txt` and `run2.txt`, the frozen P2-90 capture, the LF-normalized
  terminal P2-99 capture, and the six restored P2-90 capture files.
- `python tools/test_phase2_final_verdict_v1.py` (verify-only) still passes:
  exit 0, empty stderr, stdout byte-identical to the four recorded official
  terminal runs (raw sha256
  `66913e5752a9e2b7e399513710b4dce05efce9a714335c3b9908c0e30ea38c28`).
- Frozen verification context preserved: the 28 recorded context files exist
  on disk with manifest sha256
  `40e4f23a35f40c5d25da630467d46f5e8ad8409a40efff8412892217447a8349` and
  remain untracked.
- Phase-3 control plane complete and deterministic (no host paths, timestamps
  or process identity); CoreMark `NOT_PROVEN`; queue reserves the terminal
  marker.
- Worktree has no unexpected untracked paths: only the documented Phase-2
  residue, the frozen verification-context files and the Phase-3 control
  plane.
- Two consecutive official gate runs produced byte-identical stdout
  (2675 bytes, raw sha256
  `a039bbffa55afd786e7b44427c5aafe0b09aff6f8309e1e6c643ad812b5b7c73`,
  LF sha256
  `02664e80d78ae03d66767c472fcc8a2cc65b0fb90cf2efdb3cbbf3c6b5efff7c`) with
  empty stderr.

## P3-01 result (PASS)

Stage: `OPENRECOMP_PHASE3_COREMARK_MIPS32_FIXTURE_V1`. Evidence:
`.openrecomp-phase3/evidence/P3-01/`. Gate:
`tools/test_phase3_coremark_fixture_v1.py` (76 checks).

Markers issued:

- Stage marker: `OPENRECOMP_P3_01=PASS`
- Gate marker: `OPENRECOMP_PHASE3_COREMARK_MIPS32_FIXTURE_V1=PASS tests=76`
- Terminal marker (reserved): `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN`

CoreMark source pinned at `eembc/coremark`
`1f483d5b8316753a742cbf5590caf5bd0a4e4777` (Apache-2.0 code; upstream
`LICENSE.md` is the EEMBC acceptable-use agreement; no public score). Built
with `zig cc` 0.13.0 (clang 18.1.5, LLD 18.1.6) targeting
`mipsel-linux-musl`, soft-float, non-PIC, `-O1`, static freestanding. Two
isolated builds are byte-identical: ELF sha256
`16a0a0aa0f62344d8c0f309b755450f09c330e7c5a7c355785662d7a141f7669`,
31184 bytes, `EXECUTABLE_REPRODUCIBLE`.

Characterisation: ELF32 little-endian `EM_MIPS` `ET_EXEC`, O32 ABI,
MIPS32 ISA, entry `0x4650` = `_start`; `.text` 13948, `.rodata` 1864,
`.data` 40, `.bss` 18416; 3487 instruction words; no dynamic section, zero
relocations, zero undefined symbols.

Unsupported-encoding inventory (90 words, exact): `movz` 35, `movn` 12,
`mul` 22, `divu` 4, `teq` 4, `swl` 2, `swr` 2, `jalr` 1, alignment
padding `0x04170001` 8. This defines the evidence-supported later stages;
OpenRecomp was not modified to make the ELF pass.

Determinism: two consecutive official gate runs byte-identical (stdout raw
sha256 `81eede03...`, empty stderr).

## P3-02 result (PASS)

Stage: `OPENRECOMP_PHASE3_MIPS32_ELF_INGESTION_V1`. Evidence:
`.openrecomp-phase3/evidence/P3-02/`. Gate:
`tools/test_phase3_elf_ingestion_v1.py` (197 checks).

Markers issued:

- Stage marker: `OPENRECOMP_P3_02=PASS`
- Gate marker: `OPENRECOMP_PHASE3_MIPS32_ELF_INGESTION_V1=PASS tests=197`
- Terminal marker (reserved): `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN`

Implementation (new files only; no tracked file, Phase-2 file or frozen
manifest was modified):

- `.openrecomp-phase3/src/p3_elf_image_v1.py` — architecture-neutral fail-closed
  ELF32 ingestion (identification/header/program/section tables, section-name
  tables, bounds, integer overflow, alignment, load-range overlap, allocated
  section containment, `SHT_NOBITS` handling, dynamic/relocation rejection) and
  the sparse deterministic `GuestImage` with bounds-checked read/write.
- `.openrecomp-phase3/src/p3_target_mips32_v1.py` — MIPS32 O32 target policy
  (machine/type/ABI/ISA/non-PIC/text/entry); MIPS-specific validation stays out
  of the neutral parser.
- `tools/test_phase3_elf_ingestion_v1.py` — the P3-02 gate.
- `.openrecomp-phase3/SOURCE_SHA256SUMS.txt` — Phase-3 source manifest
  registering the Phase-3 gates and P3-02 sources; root
  `SOURCE_SHA256SUMS.txt` (sha256 `76f77bbc...`, 134 entries) stays frozen and
  fully verified.

CoreMark ingestion proof (fixture sha256 `16a0a0aa...`, 31184 bytes):
parsed identity exactly matches P3-01 (ELF32 LE `EM_MIPS` `ET_EXEC`, flags
`0x50001001`, entry `0x4650`, 8 program headers, 12 sections, 4 `PT_LOAD`
segments, 563 symbols, 0 undefined, 0 relocations, no dynamic/interp);
`.text`/`.rodata`/`.data` reconstructed bytes equal direct file slices; the
sparse load map is `0x0`+308 `r--`, `0x1000`+13948 `r-x`, `0x4680`+1912 `r--`,
`0x4e00` filesz 40 / memsz 18464 `rw-` with a 18424-byte zero-fill tail;
loaded-image identity `e072b38d...`.

BSS/NOBITS proof: `.bss` (`0x4e30`, 18416) is `SHT_NOBITS` with
`file_size=0`; its declared file range (offset 20008, end 38424) crosses the
31184-byte EOF and the file bytes at that offset are non-zero, yet the image is
exactly 18416 zeros (`c7d9a612...`), identical to `zeros_sha256`.

Fail-closed proof: 47 synthetic malformed fixtures (truncated header, wrong
class/endian/machine, out-of-bounds/overflowing tables and ranges, malformed
section-name tables, overlapping load ranges, `NOBITS` misuse, dynamic/
relocation/interpreter forms, alignment and entry failures) each rejected with
the exact expected deterministic classification; 3 positive synthetic cases
including `NOBITS` whose declared offset points at non-zero file bytes
(ingested as zeros) and `NOBITS` beyond EOF.

Determinism: two consecutive official gate runs byte-identical (stdout raw
sha256 `f24f4cef...`, 7344 bytes, empty stderr); two isolated evidence runs
produced byte-identical artifact sets including `RESULT.json`.

Regressions: P3-00 `PASS tests=61` (stdout unchanged `a039bbff...`); P3-01
`PASS tests=76` (stdout unchanged `81eede03...`); P2-99 `PASS tests=202`
(stdout unchanged `66913e57...`); Phase-1 host gates `PASS=44 FAIL=0
SKIPPED=2`; public safety `PASS`; source integrity verified 134 root manifest
entries plus the Phase-3 manifest.

Claim boundary: P3-02 proves safe deterministic ingestion and guest image
construction only. Instruction support, translation, execution and any
arbitrary ELF/MIPS32/console compatibility remain unproven; the P3-01
unsupported-encoding inventory is still assigned to P3-03/P3-04 and
`COREMARK_STATUS=NOT_PROVEN`.

## P3-03 result (PASS)

Stage: `OPENRECOMP_PHASE3_COREMARK_DECODE_FRONTIER_V1`. Evidence:
`.openrecomp-phase3/evidence/P3-03/`. Gate:
`tools/test_phase3_decode_frontier_v1.py` (201 checks).

Markers issued:

- Stage marker: `OPENRECOMP_P3_03=PASS`
- Gate marker: `OPENRECOMP_PHASE3_COREMARK_DECODE_FRONTIER_V1=PASS tests=201`
- Terminal marker (reserved): `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN`

Implementation (no tracked file, Phase-2 file, root manifest or frozen
evidence was modified):

- `.openrecomp-phase3/src/p3_decode_mips32_v1.py` — additive fail-closed
  decode/classification layer. The bounded adapter (`adapters/mips32.py`) stays
  untouched because it is hash-pinned by the root manifest and the P3-01
  inventory gate; the Phase-3 layer decodes the P3-01 unsupported classes
  (`movz`, `movn`, `mul`, `div`/`divu`, trap family incl. `teq`, `swl`, `swr`,
  `jalr` and same-family forms) with exact operands while keeping their
  execution/translation semantics explicitly unsupported. Reserved encodings
  in REGIMM/SPECIAL/SPECIAL2 spaces are `RESERVED_ENCODING`, everything
  unnamed is fail-closed `UNKNOWN_ENCODING`.
- `.openrecomp-phase3/src/p3_code_frontier_v1.py` — deterministic reachability
  and frontier engine: direct control flow with delay slots from the ELF entry
  point, never treating every word as reachable code, never inventing indirect
  targets, stopping flow at invalid encodings and unresolvable delay slots.
- `tools/test_phase3_decode_frontier_v1.py` — the P3-03 gate.
- `.openrecomp-phase3/SOURCE_SHA256SUMS.txt` — extended to the eight Phase-3
  source/gate files (manifest sha256 `79bc827d...`).
- Documented contract growth: `tools/test_phase3_elf_ingestion_v1.py`'s
  expected Phase-3 manifest entry set was extended from five to those eight
  files (additive; stdout still byte-identical to the recorded P3-02 capture
  `f24f4cef...`, all entries still verified).

CoreMark decode frontier (fixture `16a0a0aa...`, 31184 bytes; `.text` 3487
words, entry `0x4650`): all 3487 words classified and reachability discovered
from the entry. Totals: decoded 3479 (supported 3397, recognized-unsupported
82), reserved 8, unknown 0; reachable 2178 (supported 2123, unsupported 55,
invalid 0); unreachable 1309 = 8 non-code padding + 1301 unreached code (687
words in 22 dead standalone functions, 614 words behind three unresolved
`jr $at` jump-table sites in `core_state_transition`/`ee_printf`). Unsupported
histogram (total/reachable/unreachable): `movz` 35/21/14, `movn` 12/9/3,
`mul` 22/15/7, `divu` 4/3/1, `teq` 4/3/1, `swl` 2/2/0, `swr` 2/2/0,
`jalr` 1/0/1. Control flow: 96 direct calls, 198 conditional branches, 70
jumps, 24 returns, 391 delay slots; indirect sites 4 (three reachable
`jr $at` jump tables plus the single `jalr $ra,$t9` at `0x1958`, which is in
dead code) with no target invented.

Padding re-evaluation: the eight `0x04170001` words are proven unreachable
non-code alignment padding from three independent evidence elements
(reachability, reserved REGIMM `rt=0x17` encoding, exact function-symbol gap
position), not inherited from P3-01; see
`.openrecomp-phase3/evidence/P3-03/padding_invalid_classification.md`.

Negative coverage: 21 reserved/unknown/malformed decode panels, 8 exact
operand panels, 8 input-validation panels and 13 synthetic reachability
fixtures (delay-slot fall-through suppression, direct/indirect calls,
branches, returns, boundary successors, fail-closed invalid encodings and
control-transfer-in-delay-slot).

Determinism: two consecutive official gate runs byte-identical (stdout raw
sha256 `15e20a2c...`, 7910 bytes, empty stderr); an isolated evidence-directory
run produced byte-identical artifacts for all 9 gate-produced files including
`RESULT.json` (`deterministic_run.json`).

Regressions: P3-00 `PASS tests=61` (`a039bbff...`); P3-01 `PASS tests=76`
(`81eede03...`); P3-02 `PASS tests=197` (`f24f4cef...` after the documented
manifest-set extension); P2-99 `PASS tests=202` (`66913e57...`); Phase-1 host
gates `PASS=44 FAIL=0 SKIPPED=2` (`2a9d1bba...`); public safety `PASS`
(`ad022ff1...`); root manifest verified (134 entries) and Phase-3 manifest
verified (8 entries).

Claim boundary: P3-03 proves deterministic decode/classification of the
audited CoreMark executable frontier and identifies the exact semantic and
control-flow gaps only. No unsupported instruction executes correctly, CoreMark
does not translate or run, and no arbitrary MIPS32/console compatibility is
claimed. `COREMARK_STATUS=NOT_PROVEN`.

## P3-04 result (PASS)

Stage: `OPENRECOMP_PHASE3_COREMARK_REACHABLE_SEMANTICS_V1`. Evidence:
`.openrecomp-phase3/evidence/P3-04/`. Gate:
`tools/test_phase3_reachable_semantics_v1.py` (126 checks).

Control-plane reconciliation (documented in `STAGE_QUEUE.md`): the pre-P3-04
queue assigned P3-04 to the ProgramModel/CFG/functions/call
graph/translation-units stage; the P3-03 frontier evidence made the reachable
semantic frontier the next bounded stage, so P3-04 is the reachable-semantics
stage and the structure stage moved to P3-05 with the later provisional stage
IDs shifted by one. No completed stage evidence is affected.

Markers issued:

- Stage marker: `OPENRECOMP_P3_04=PASS`
- Gate marker: `OPENRECOMP_PHASE3_COREMARK_REACHABLE_SEMANTICS_V1=PASS tests=126`
- Terminal marker (reserved): `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN`

Implementation (new Phase-3 files only; no tracked file, Phase-2 file, gate or
frozen manifest was modified; `git diff` and `git diff --cached` are empty):

- `.openrecomp-phase3/src/p3_semantics_mips32_v1.py` — exact fail-closed
  MIPS32 semantics for the P3-01 bounded class (`movz`, `movn`, `mul`,
  `divu`, `teq`, `swl`, `swr`, `jalr`): `$zero` writes discarded, signed
  32x32 product low half, unsigned quotient/remainder with divide-by-zero
  refusal, taken-trap refusal with the encoded trap code preserved,
  little-endian partial-word store merging within the aligned word, `jalr`
  target latched from `GPR[rs]` with link `address + 8` and unaligned-target
  refusal, HI/LO marked architecturally UNPREDICTABLE after `mul`. The frozen
  decode layer (`p3_decode_mips32_v1`) and the frontier engine
  (`p3_code_frontier_v1`) are untouched: the 82 words remain
  `RECOGNIZED_UNSUPPORTED` and semantic support is an explicit overlay, never
  inferred from decoding.
- `tools/test_phase3_reachable_semantics_v1.py` — the P3-04 gate.
- `.openrecomp-phase3/SOURCE_SHA256SUMS.txt` — grown additively from eight to
  ten entries (new semantics module and gate registered).
- Documented contract growth: the P3-02 and P3-03 gates now expect the
  ten-entry registry (8 -> 10, additive); both still pass with stdout
  byte-identical to their recorded captures.

Frontier result (fixture `16a0a0aa...`, `.text` 3487 words, entry `0x4650`):
82 recognized-unsupported words = 55 reachable + 27 unreachable; the exact
per-site table (address, raw encoding, mnemonic, operands, reachability,
containing function, implementation status) is
`reachable_unsupported_before.json` / `reachable_unsupported_after.json`. All
82 sites are semantically implemented and covered; the reachable semantic gap
is zero (2178/2178 reachable words semantically supported). The recomputed
reachability hash is unchanged (`c62d54838cbc5fcc7b0ff83cdc9b2f0f47b8851c5e4023ae2ca6d629c8f76edf`),
the three `jr $at` jump tables and the dead `jalr` at `0x1958` stay
unresolved with no target invented, and the eight `0x04170001` words stay
reserved non-code padding.

Verification: 459 differential vectors (boundary, fixture-derived and
deterministic pseudo-random operands) plus 24 compiler-idiom `swl`+`swr`
composition checks against an independently written in-gate model; all 82
audited sites executed on both models with no `UNSUPPORTED_INSTRUCTION`
result; 16 fail-closed negatives (unsupported op, divide-by-zero, taken trap,
unaligned `jalr` target, unpredictable HI/LO read, memory faults, unsupported
endianness, malformed records); the HI/LO dependency analysis proves all six
reachable `mfhi`/`mflo` reads are defined by `multu`/`divu` and none depends
on `mul`.

Exception frontier: the six reachable div/trap sites are each classified with
explicit evidence instead of assumption — `0x1f60`/`0x1f64` (fixture seeds
`0, 0, 0x66, 0x3e8, 0`; `execs = 7` through the `movz` at `0x1ee4`; popcount
divisor 3), `0x2044`/`0x2048` (the `beq $2,$0` at `0x2038` dominates the
fall-through path, and the auto-calibration block is not entered because
`iterations = 0x3e8`), `0x2370`/`0x2374` (the pure `time_in_secs` callee
returns the same nonzero value proven at `0x2350`). No site is left as an
unresolved runtime requirement, and the model still fails closed if any
condition were ever true.

Determinism: two consecutive official runs byte-identical (stdout raw sha256
`412544a413bbe3e55e688bc45e379dccfe4e8b4ebdc299211ccba2a832e39b36`, 5202
bytes, empty stderr); every evidence artifact is byte-identical across the
two runs.

Regressions: P3-00 `PASS tests=61` (`a039bbff...` unchanged), P3-01
`PASS tests=76` (`81eede03...`), P3-02 `PASS tests=197` (`f24f4cef...`),
P3-03 `PASS tests=201` (`15e20a2c...`), P2-99 `PASS tests=202`
(`66913e57...`), Phase-1 host gates `PASS=44 FAIL=0 SKIPPED=2`
(`2a9d1bba...`), public safety `PASS`; root manifest verified (134 entries)
and frozen Phase-2 tracked tree unchanged.

Claim boundary: P3-04 proves only that the audited reachable MIPS32 semantic
frontier in the P3-01 classes is implemented and verified for the CoreMark
path. CoreMark is not translated or executed, the unresolved jump tables are
not recovered, and no arbitrary MIPS32/PS1/PS2 compatibility is claimed.
`COREMARK_STATUS=NOT_PROVEN`.

## P3-05 result (PASS)

Stage: `OPENRECOMP_PHASE3_PROGRAM_STRUCTURE_V1`. Evidence:
`.openrecomp-phase3/evidence/P3-05/`. Gate:
`tools/test_phase3_structure_v1.py` (202 checks).

Markers issued:

- Stage marker: `OPENRECOMP_P3_05=PASS`
- Gate marker: `OPENRECOMP_PHASE3_PROGRAM_STRUCTURE_V1=PASS tests=202`
- Terminal marker (reserved): `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN`

Implementation (new Phase-3 files only; no shared layer, frozen adapter,
Phase-1/Phase-2 file, gate or frozen manifest was modified):

- `.openrecomp-phase3/src/p3_structure_v1.py` — fail-closed bridge from the
  frozen P3-03 frontier records to the shared Phase-2 neutral types. Only
  `REACHABLE` words become `DecodedInstruction`s; flow is a pure function of
  the frozen record (`movz`/`divu`/`teq` etc. stay NORMAL continuations,
  `jr $ra` is RETURN, the three `jr $at` sites are unresolved INDIRECT_JUMP
  with no target, `syscall`/`break` would be TRAP); inconsistent records,
  unknown terminators, unsupported control transfers, invalid encodings and
  malformed regions fail closed with stable codes.
- `tools/test_phase3_structure_v1.py` — the P3-05 gate (202 checks).
- `.openrecomp-phase3/SOURCE_SHA256SUMS.txt` — grown additively from ten to
  twelve entries (new bridge module and gate registered).
- Documented contract growth: the P3-02/P3-03/P3-04 gates now expect the
  twelve-entry registry (10 -> 12, additive); all entries verified and stdout
  byte-identical to their recorded captures.

Structure on the real ELF (fixture `16a0a0aa...`, `.text` 3487 words, entry
`0x4650`): the P3-03 frontier reproduced exactly (2178 reachable, 1309
unreachable, 391 delay slots, reachability hash `c62d5483...`). Neutral
instructions 2178 (NORMAL 1787, BRANCH 198, CALL 96, JUMP 70, RETURN 24,
INDIRECT_JUMP 3); CFG 615 blocks / 770 edges (198 BRANCH_TAKEN, 198
BRANCH_NOT_TAKEN, 96 CALL_RETURN, 205 FALLTHROUGH, 70 JUMP, 3 unresolved
INDIRECT); 26 PROVEN functions; 96-edge all-internal direct call graph; 26
translation units with entry unit `tu_fn_4650`. The three reachable `jr $at`
sites stay unresolved with no invented target; the dead `jalr` at `0x1958`
and the eight padding words stay outside the structural model. Fingerprints:
program model `8ed487c0...`, CFG `c9029a0d...`, call graph `9462f40c...`,
unit set `44c8b895...`, discovery `cf307c18...`.

Delay-slot policy: the shared layers have no MIPS32 delay-slot concept, so
delay slots are ordinary NORMAL instructions with their relationship recorded
separately in `cfg_structure.json`; call delay slots are the `CALL_RETURN`
continuation, branch delay slots are the `BRANCH_NOT_TAKEN` successor, and the
97 jump/return/indirect-jump delay slots are explicit orphan blocks never
attributed to a function and never given an invented predecessor. The
`ProgramModel` therefore covers the 2081 owned instructions while the CFG
covers all 2178; this is recorded as a limitation, not an execution claim.

`PROVEN` basis: exact decode plus reachability from the proven ELF entry
through resolved direct edges (the shared model's structural classification,
not a runtime or semantics claim).

Verification: 202 checks including exact P3-03/P3-04 cross-checks, CFG edge
targets equal to decoded targets, round-trips of all four shared containers
byte-identical, and 27 fail-closed negative/synthetic panels. Determinism: two
consecutive official runs byte-identical (7819 bytes, raw sha256
`12bf87d7...`, LF sha256 `f8948ea8...`, empty stderr, exit 0). Regressions all
exit 0 with empty stderr and byte-identical stdout: P2-99 `PASS tests=202`
(`66913e57...`), P3-00 `PASS tests=61` (`a039bbff...`), P3-01 `PASS tests=76`
(`81eede03...`), P3-02 `PASS tests=197` (`f24f4cef...`), P3-03 `PASS tests=201`
(`15e20a2c...`), P3-04 `PASS tests=126` (`412544a4...`), Phase-1 host gates
`PASS=44 FAIL=0 SKIPPED=2` (`2a9d1bba...`), public safety `PASS`
(`ad022ff1...`); root manifest verified (134 entries).

Claim boundary: P3-05 proves only that the frozen Phase-2 structural layers run
deterministically on the audited CoreMark reachable frontier and recover the
direct structure exactly. CoreMark is not translated or executed, indirect
targets are not resolved, true delay-slot execution semantics are not modelled,
and no arbitrary MIPS32/PS1/PS2 compatibility is claimed.
`COREMARK_STATUS=NOT_PROVEN`.

## P3-06 result (PASS)

Stage: `OPENRECOMP_PHASE3_STATIC_DATA_V1`. Evidence:
`.openrecomp-phase3/evidence/P3-06/`. Gate:
`tools/test_phase3_static_data_v1.py` (123 checks).

Markers issued:

- Stage marker: `OPENRECOMP_P3_06=PASS`
- Gate marker: `OPENRECOMP_PHASE3_STATIC_DATA_V1=PASS tests=123`
- Terminal marker (reserved): `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN`

Implementation (new Phase-3 files only; no shared layer, frozen adapter,
Phase-1/Phase-2 file, gate or frozen manifest was modified):

- `.openrecomp-phase3/src/p3_static_data_v1.py` — fail-closed static-data
  model (sections, zero-fill, hashes, symbol-annotated layout) and a
  block-local exact-constant global access analysis that records every
  constant formation with provenance and classifies every reachable memory
  access as `RESOLVED_STATIC`, `RESOLVED_OUTSIDE_IMAGE`,
  `RESOLVED_REGION_UNCLASSIFIED`, `CROSS_SECTION_ACCESS` or `RUNTIME_BASE`.
  Loads from read-only file-backed sections propagate exact image values;
  stores into read-only static sections fail closed.
- `tools/test_phase3_static_data_v1.py` — the P3-06 gate.
- `.openrecomp-phase3/SOURCE_SHA256SUMS.txt` — grown additively from twelve
  to fourteen entries; the P3-02/P3-03/P3-04/P3-05 gates now expect fourteen
  entries (additive) and still emit byte-identical stdout.

Static data model (fixture `16a0a0aa...`): `.rodata` `0x46b0`+1864,
`.data` `0x4e00`+40, `.bss` `0x4e30`+18416 exact zero-fill, the two read-only
metadata sections, every section hash cross-checked against the P3-02
evidence. Seed symbol layout `seed1/2` `0x5600`/`0x5604`, `seed3/4`
`0x4e10`/`0x4e14`, `seed5` `0x5608`; `static_memblk` `0x4e30`+2000;
`p3_stack` `0x5620`+16384; `_gp = 0xcdf0`.

Global access model: 283 provenance-recorded constant formations (25 with
recorded uses). Of 505 reachable memory accesses, 10 are `RESOLVED_STATIC`
(3 `.data` loads of `default_num_contexts`; `p3_tick`,
`p3_start_time_val`, `p3_stop_time_val`, `p3_uart_byte_count` in `.bss` —
5 loads and 2 stores), 2 are `RESOLVED_OUTSIDE_IMAGE` UART stores
(`0x10000000`, `0x10000008`) and 493 are `RUNTIME_BASE` with no address
claim. No resolved access targets a seed and no store resolves into a
read-only section.

GP/SP model: `_start` sets `$28 = _gp = 0xcdf0` and `$29 = 0x9620` (stack
top) with provenance; no reachable instruction uses `$28` as a memory base
and the register is reused as a general scratch register at four sites, so
`GP_STATUS=NOT_REQUIRED_BY_REACHABLE_CODE`. Seed chain: the `.rodata` table
base `0x4c50` materialised at `0x33e8`, the `sltiu`/`beq` guard bounding the
index to five entries, the five statically known seed pointers and the
two-level `get_seed_32` load shape; initial seed values `0, 0, 0x66, 0x3e8, 0`
match the P3-04 fixture constants.

Verification: 123 checks including exact P3-02/P3-04 cross-checks and 9
fail-closed negatives. Determinism: two consecutive official runs
byte-identical (4294 bytes raw, raw sha256 `23d2f1c2...`, LF sha256
`c4a1d4ff...`, empty stderr, exit 0). Regressions all exit 0 with empty
stderr and byte-identical stdout: P2-99 `PASS tests=202` (`66913e57...`),
P3-00 `PASS tests=61` (`a039bbff...`), P3-01 `PASS tests=76`
(`81eede03...`), P3-02 `PASS tests=197` (`f24f4cef...`), P3-03
`PASS tests=201` (`15e20a2c...`), P3-04 `PASS tests=126` (`412544a4...`),
P3-05 `PASS tests=202` (`12bf87d7...`), Phase-1 host gates
`PASS=44 FAIL=0 SKIPPED=2` (`2a9d1bba...`), public safety `PASS`
(`ad022ff1...`); root manifest verified (134 entries).

Claim boundary: P3-06 proves only the static-data reconstruction and the
reachable global access model of the audited image. CoreMark is not
translated or executed, the 493 runtime-base accesses stay unresolved, no
alias analysis is performed, and no arbitrary MIPS32/PS1/PS2 compatibility
is claimed. `COREMARK_STATUS=NOT_PROVEN`.

## P3-07 result (PASS)

Stage: `OPENRECOMP_PHASE3_HOST_EMISSION_V1`. Evidence:
`.openrecomp-phase3/evidence/P3-07/`. Gate:
`tools/test_phase3_host_emit_v1.py` (68 checks).

Markers issued:

- Stage marker: `OPENRECOMP_P3_07=PASS`
- Gate marker: `OPENRECOMP_PHASE3_HOST_EMISSION_V1=PASS tests=68`
- Terminal marker (reserved): `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN`

Implementation (new Phase-3 files only; no shared layer, frozen adapter,
Phase-1/Phase-2 file, gate or frozen manifest was modified):

- `.openrecomp-phase3/src/p3_host_emit_v1.py` — deterministic whole-image
  emitter: one case per decodable word (3479), exact semantics for all 46 ops
  present, true delay-slot protocol, runtime-mediated indirect dispatch, P2-08
  ABI memory access and host calls for the two external windows, fail-closed
  UNPREDICTABLE states, and the host support with the FNV-1a 64 observable.
- `tools/test_phase3_host_emit_v1.py` — the P3-07 gate.
- `.openrecomp-phase3/SOURCE_SHA256SUMS.txt` — grown additively from fourteen
  to sixteen entries; the P3-02..P3-06 gates now expect sixteen entries
  (additive) and still emit byte-identical stdout.
- Evidence includes the generated `coremark_program.c` (1073923 bytes,
  fingerprint `5199e2f0...` at the boundary emission) and `coremark_support.c`
  (7946 bytes), plus the emission model, coverage, negatives and determinism
  records.

Emission facts: 3479 cases (eight reserved padding words excluded), 620 control
transfers each with an emitted non-control delay slot, 567 direct targets all
emitted, 4 indirect sites (`0x1958`, `0x3130`, `0x3830`, `0x39a0`)
runtime-mediated with no static target. The emitted `g_image` initializer and
region table equal the P3-02 guest image window and segment permissions
byte-for-byte.

Verification: 67 checks including 11 fail-closed negatives and emission
determinism (two independent emissions byte-identical). Official runs: two
consecutive runs byte-identical (raw sha256
`26b871bfe1f4b6dec0fcc1d2c7d9b058ed2bb4939c93a40f90103253a76a41a6`, empty
stderr, exit 0). Regressions all exit 0 with empty stderr and byte-identical
stdout: P2-99 `PASS tests=202` (`66913e57...`), P3-00 `PASS tests=61`
(`a039bbff...`), P3-01 `PASS tests=76` (`81eede03...`), P3-02
`PASS tests=197` (`f24f4cef...`), P3-03 `PASS tests=201` (`15e20a2c...`),
P3-04 `PASS tests=126` (`412544a4...`), P3-05 `PASS tests=202`
(`12bf87d7...`), P3-06 `PASS tests=123` (`23d2f1c2...`), Phase-1 host gates
`PASS=44 FAIL=0 SKIPPED=2` (`2a9d1bba...`), public safety `PASS`
(`ad022ff1...`).

Claim boundary: P3-07 proves only deterministic host-code generation for the
audited image. Nothing is built or executed yet (P3-08), equivalence is not yet
proven (P3-09), and no arbitrary MIPS32/PS1/PS2 compatibility is claimed.
`COREMARK_STATUS=NOT_PROVEN`.

## P3-08 result (PASS)

Stage: `OPENRECOMP_PHASE3_NATIVE_RUNTIME_V1`. Evidence:
`.openrecomp-phase3/evidence/P3-08/`. Gate:
`tools/test_phase3_native_runtime_v1.py` (55 checks).

Markers issued:

- Stage marker: `OPENRECOMP_P3_08=PASS`
- Gate marker: `OPENRECOMP_PHASE3_NATIVE_RUNTIME_V1=PASS tests=55`
- Terminal marker (reserved): `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN`

Implementation (new Phase-3 gate only; no shared layer, frozen adapter,
Phase-1/Phase-2 file, gate or frozen manifest was modified):

- `tools/test_phase3_native_runtime_v1.py` — re-emits and pins the P3-07
  translation, builds it with the Phase-2 deterministic build pipeline
  (`clang-cl.exe` LLVM 22.1.8 + `lld-link.exe`, `/Brepro`, two isolated runs),
  executes it repeatedly through the P2-08 generic runtime ABI, checks
  CoreMark's published validation CRCs and runs four fail-closed runtime
  negatives.
- `.openrecomp-phase3/SOURCE_SHA256SUMS.txt` — grown additively from sixteen
  to seventeen entries; the earlier gates expect seventeen entries and still
  emit byte-identical stdout.

Build: `EXECUTABLE_REPRODUCIBLE`; `program.exe` sha256
`c80ecc4b88c09aa05e913c935d18834373a0920910ee781fa51d3764ef3dd1b6`; manifest
`e3eb9651...`; no host path or identity leakage.

Execution: `exit_status=0`, `steps=394997250`, `pc=0x00004564`,
`hi=0x0000000d`, `lo=0x00000000`, `uart_bytes=499`,
`state_fnv1a64=0x78651c29dd149ab1`, `failed=0`; three replays byte-identical
(stdout sha256 `7347b5fd...`). The UART stream contains CoreMark's
`Correct operation validated.` line with the published validation CRCs
(`seedcrc 0xe9f5`, `crclist 0xe714`, `crcmatrix 0x1fd7`, `crcstate 0x8e3a`,
`crcfinal 0xd340`).

Runtime negatives: divide by zero, taken `teq` (code preserved), unaligned
indirect target and an out-of-region write each produced the exact expected
deterministic failure with `failed=1`.

Verification: 54 checks. Official runs: two consecutive runs byte-identical
(raw sha256 `cdc7abbfc3d12d02f197fb0b99e1c7f4ef55f1dc62debb288387ff121225bb9d`,
empty stderr, exit 0). Regressions all exit 0 with empty stderr and
byte-identical stdout: P2-99 (`66913e57...`), P3-00 (`a039bbff...`), P3-01
(`81eede03...`), P3-02 (`f24f4cef...`), P3-03 (`15e20a2c...`), P3-04
(`412544a4...`), P3-05 (`12bf87d7...`), P3-06 (`23d2f1c2...`), P3-07
(`26b871bf...`), Phase-1 host gates (`2a9d1bba...`), public safety
(`ad022ff1...`).

Claim boundary: P3-08 proves reproducible native build and deterministic
execution with CoreMark's own validation, not equivalence against an
independent reference (P3-09); no arbitrary MIPS32/PS1/PS2 compatibility is
claimed. `COREMARK_STATUS=NOT_PROVEN`.

## P3-09 result (PASS)

Stage: `OPENRECOMP_PHASE3_REFERENCE_EQUIVALENCE_V1`. Evidence:
`.openrecomp-phase3/evidence/P3-09/`. Gate:
`tools/test_phase3_reference_equivalence_v1.py` (39 checks).

Markers issued:

- Stage marker: `OPENRECOMP_P3_09=PASS`
- Gate marker: `OPENRECOMP_PHASE3_REFERENCE_EQUIVALENCE_V1=PASS tests=39`
- Terminal marker (reserved): `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN`

Implementation (new Phase-3 files only; no shared layer, frozen adapter,
Phase-1/Phase-2 file, gate or frozen manifest was modified):

- `.openrecomp-phase3/src/p3_reference_mips32_v1.py` — independent ELF32
  loader, independent raw-word decoder and interpreter for the audited op set
  with exact MIPS32 semantics, delay slots, HI/LO, region-checked memory, the
  two MMIO windows and the documented FNV-1a 64 observable digest.
- `tools/test_phase3_reference_equivalence_v1.py` — the P3-09 gate.
- `.openrecomp-phase3/SOURCE_SHA256SUMS.txt` — grown additively from seventeen
  to nineteen entries; the earlier gates expect nineteen entries and still emit
  byte-identical stdout.

Independent loader: image sha256 `3eecfc95...` equals the P3-07 host image
exactly; the regions and the 3479-word op histogram equal the frozen P3-02/
P3-03 evidence.

Full-run equivalence (394,997,250 steps): every observable field equals the
P3-08 native values — `exit_status=0`, `pc=0x00004564`, `hi=0x0000000d`,
`lo=0`, `uart_bytes=499`, `state_fnv1a64=0x78651c29dd149ab1`, no failure. The
reference UART stream carries CoreMark's validation CRCs and
`Correct operation validated.`; final reference image sha256 `67a14938...`,
final register dump sha256 `21cd49e7...`. Five synthetic runtime negatives plus
malformed-ELF rejection prove the reference's fail-closed paths.

Determinism: two independent gate invocations byte-identical (raw sha256
`722a4cd87bc6eb0fa6ef513aadfe3b7e1198156fd54314b8df1838c158a0a4d2`, 1742 bytes,
empty stderr); all evidence artifacts deterministic. Regressions all exit 0
with empty stderr and byte-identical stdout: P2-99 (`66913e57...`), P3-00
(`a039bbff...`), P3-01 (`81eede03...`), P3-02 (`f24f4cef...`), P3-03
(`15e20a2c...`), P3-04 (`412544a4...`), P3-05 (`12bf87d7...`), P3-06
(`23d2f1c2...`), P3-07 (`26b871bf...`), P3-08 (`cdc7abbf...`), Phase-1 host
gates (`2a9d1bba...`), public safety (`ad022ff1...`).

Claim boundary: P3-09 proves deterministic observable equivalence for this one
audited CoreMark MIPS32 program between the native host execution and an
independent reference. No arbitrary MIPS32/PS1/PS2 compatibility is claimed and
the terminal marker stays `NOT_PROVEN` until the remaining frozen stages pass.
`COREMARK_STATUS=NOT_PROVEN`.

## P3-10 result (PASS)

Stage: `OPENRECOMP_PHASE3_PACKAGE_REGRESSION_V1`. Evidence:
`.openrecomp-phase3/evidence/P3-10/`. Gate:
`tools/test_phase3_package_regression_v1.py` (20 checks).

Markers issued:

- Stage marker: `OPENRECOMP_P3_10=PASS`
- Gate marker: `OPENRECOMP_PHASE3_PACKAGE_REGRESSION_V1=PASS tests=20`
- Terminal marker (reserved): `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN`

Implementation (new Phase-3 files only; no shared layer, frozen adapter,
Phase-1/Phase-2 file, gate or frozen manifest was modified):

- `.openrecomp-phase3/src/p3_package_v1.py` — deterministic ZIP builder and
  verifier with a fail-closed content policy.
- `tools/test_phase3_package_regression_v1.py` — the P3-10 gate.
- `.openrecomp-phase3/SOURCE_SHA256SUMS.txt` — grown additively from nineteen
  to twenty-one entries; the earlier gates expect twenty-one entries and still
  emit byte-identical stdout.

Package: `phase3_package_v1.zip` 5482951 bytes, sha256 `cf9ab795...`, manifest
fingerprint `9050a117...`, 287 tracked files (5376636 raw bytes) covering the
control plane, sources, gates, port files, generated host code and tracked
evidence through P3-09. Two builds from the same tracked state are
byte-identical; the manifest verifies member-by-member; the content policy
rejects compiled/guest artifacts, host paths/timestamps/UUIDs in evidence and
sensitive markers. Host-specific command records are excluded by design and
remain tracked evidence.

Whole regression: all thirteen gates (P2-99, P3-00..P3-09, Phase-1 host gates,
public safety) exit 0 with empty stderr and stdout byte-identical to their
recorded captures, including a full P3-09 independent reference re-execution.

Determinism: two consecutive official runs byte-identical (raw sha256
`84dcd13981007d77d12811018eb7ea375f1e907391fa32ac2ebc8703febf2b1e`, 1713 bytes,
empty stderr). The terminal marker remains reserved and `NOT_PROVEN`.

Claim boundary: P3-10 proves reproducible packaging and whole-regression
coherence. It adds no new capability claim and does not promote the terminal
marker. `COREMARK_STATUS=NOT_PROVEN`.

## P3-90 result (PASS)

Stage: `OPENRECOMP_PHASE3_WHOLE_REGRESSION_V1`. Evidence:
`.openrecomp-phase3/evidence/P3-90/`. Gate:
`tools/test_phase3_whole_regression_v1.py` (30 checks).

Markers issued:

- Stage marker: `OPENRECOMP_P3_90=PASS`
- Gate marker: `OPENRECOMP_PHASE3_WHOLE_REGRESSION_V1=PASS tests=30`
- Terminal marker (reserved): `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN`

New Phase-3 file only (`tools/test_phase3_whole_regression_v1.py`); the
manifest grew additively from twenty-one to twenty-two entries and the earlier
gates still emit byte-identical stdout.

Audit results: the frozen Phase-2 boundary identities (tag/commit/tree, P2-99
result/gate/capture hashes, Phase-1 tag) and the fixture/inventory identities
re-verified; the committed P3-10 package verifies (sha256 `cf9ab795...`,
fingerprint `9050a117...`, 287 entries) against its boundary record; all
thirteen gates (P2-99, P3-00..P3-09, Phase-1 host gates, public safety) pass
with empty stderr and stdout byte-identical to their recorded captures,
including the full P3-09 independent reference re-execution. The P3-10 gate is
verified by its committed boundary capture/package record instead of being
re-run (it performs this audit by design).

Determinism: two consecutive official runs byte-identical (raw sha256
`5d86ba0564a30e28d8fdffc890e9e93afb17481c03991a5c4a10e6e054697bea`, 2052 bytes,
empty stderr). The terminal marker remains reserved and `NOT_PROVEN`.

Claim boundary: P3-90 adds no capability claim; the terminal verdict is issued
only by P3-99 after P3-91 records limitations. `COREMARK_STATUS=NOT_PROVEN`.

## P3-91 result (PASS)

Stage: `OPENRECOMP_PHASE3_EVIDENCE_INDEX_V1`. Evidence:
`.openrecomp-phase3/evidence/P3-91/`. Gate:
`tools/test_phase3_evidence_index_v1.py` (50 checks).

Markers issued:

- Stage marker: `OPENRECOMP_P3_91=PASS`
- Gate marker: `OPENRECOMP_PHASE3_EVIDENCE_INDEX_V1=PASS tests=50`
- Terminal marker (reserved): `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN`

New Phase-3 gate only (`tools/test_phase3_evidence_index_v1.py`); the manifest
grew additively from twenty-two to twenty-three entries and the earlier gates
still emit byte-identical stdout.

Index: 346 evidence files (10495633 bytes; 314 tracked, 32 untracked
platform-line-ending/current-stage captures), each with stage, path, size,
sha256 and tracked status; the six control-plane file hashes; the frozen
Phase-1/Phase-2 boundary identities; the P3-10 package identity. Every stage
`P3-00 .. P3-90` carries its result record and every JSON evidence file is
tracked.

Claim record: the reserved terminal marker and `COREMARK_STATUS=NOT_PROVEN`,
nine bounded proven statements, eight explicit unproven areas (arbitrary
MIPS32, PS1, PS2, game/commercial compatibility, cycle accuracy/console
emulation, self-modifying code, `-O2`, runtime equivalence beyond the audited
observable) and eight limitations with evidence and impact (shared-layer
delay-slot approximation, unresolved indirect sites at the shared-layer
boundary, runtime-base alias unknowns, fail-closed UNPREDICTABLE states,
recorded-toolchain dependence, single audited fixture, CoreMark not supported,
package boundary snapshot).

Determinism: two consecutive official runs byte-identical (raw sha256
`98a4b3dffd5959eadf8fb25241c84f0777ca646ebcfe8471ba7ad71b3e13d8c2`, 2046 bytes,
empty stderr); boundary regressions unchanged. The terminal verdict remains
reserved for P3-99. `COREMARK_STATUS=NOT_PROVEN`.

## P3-09 image-fidelity correction record

The P3-09 independent ELF loader compared its flat load image with the host
runtime image and found a genuine cross-stage contradiction: the P3-07 emitter
had built `g_image` from the allocated sections instead of the PT_LOAD region
bytes, so the 308-byte read-only ELF header region (`0x0..0x134`) was zero in
the host program (the audited guest never reads it, so execution was
unaffected). Repaired at the source within P3-09: the emitter now embeds the
exact P3-02 load image (region bytes plus zero-fill), and the P3-07 gate gained
an explicit `emission:image-equals-load-image` check (68 checks). The P3-07 and
P3-08 gates were re-run on the corrected sources and re-passed; their evidence,
captures and this control plane were regenerated with the new hashes (program
`5199e2f0...`, support `c5c69054...`, image
`3eecfc957c4ed147544d2aa98c6e4f4d7aac41957e531cdfe01c2555ff0a91ae`, executable
`c80ecc4b...`, manifest `e3eb9651...`, state digest `0x78651c29dd149ab1`). No
execution observable changed (steps `394997250`, PC `0x00004564`, HI
`0x0000000d`, LO `0`, UART 499 bytes, exit status 0); the state digest now
equals the independent reference exactly. This is recorded as a stage-internal
repair, not a false PASS: the original stages passed their stated contracts and
the contradiction was found and fixed by the stage that owns equivalence.

## Claim boundary

Phase 3 adds no Phase-2 claim. Phase 2 remains the proven bounded
end-to-end framework result. The Phase-3 terminal marker is reserved and
currently `NOT_PROVEN`; no arbitrary MIPS32/commercial/console compatibility
is claimed at any Phase-3 stage until the bounded real-ELF claim is proven with
independent evidence.

## Next exact action

P3-91 is `PASS`. Advance to P3-99 (final verdict, frozen queue row): re-verify
the complete audited tree (source integrity, frozen boundary, package,
whole-regression audit and the P3-91 index/claim record) and issue the terminal
Phase-3 verdict for the bounded claim on this tree. The verdict is issued only
if every check passes; otherwise the terminal marker stays `NOT_PROVEN` and
P3-99 fails closed. Record evidence under `.openrecomp-phase3/evidence/P3-99/`
and update the control plane, preserving `COREMARK_STATUS=NOT_PROVEN` (the
bounded proof is not general CoreMark support).
