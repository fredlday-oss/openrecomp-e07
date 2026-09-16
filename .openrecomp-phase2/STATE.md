# OpenRecomp Phase 2 State

PHASE=2
BASELINE_TAG=openrecomp-phase1-pass
BASELINE_COMMIT=46c2f97
CURRENT_STAGE=P2-99
LAST_PASSED_STAGE=P2-99
STATUS=COMPLETE
FINAL_VERDICT=PASS

## Stage ledger

| ID | Stage | Status | Evidence |
| --- | --- | --- | --- |
| P2-00 | Baseline + control plane | `PASS` | `.openrecomp-phase2/evidence/P2-00/RESULT.md` |
| P2-01 | Shared program model V1 | `PASS` | `.openrecomp-phase2/evidence/P2-01/RESULT.md` |
| P2-02 | CFG construction V1 | `PASS` | `.openrecomp-phase2/evidence/P2-02/RESULT.md` |
| P2-03 | Function discovery V1 | `PASS` | `.openrecomp-phase2/evidence/P2-03/RESULT.md` |
| P2-04 | Call-graph recovery V1 | `PASS` | `.openrecomp-phase2/evidence/P2-04/RESULT.md` |
| P2-05 | Translation units V1 | `PASS` | `.openrecomp-phase2/evidence/P2-05/RESULT.md` |
| P2-06 | Indirect-control-flow classification V1 | `PASS` | `.openrecomp-phase2/evidence/P2-06/RESULT.md` |
| P2-07 | Host emitter V1 | `PASS` | `.openrecomp-phase2/evidence/P2-07/RESULT.md` |
| P2-08 | Generic runtime ABI V1 | `PASS` | `.openrecomp-phase2/evidence/P2-08/RESULT.md` |
| P2-09 | Deterministic build pipeline | `PASS` | `.openrecomp-phase2/evidence/P2-09/RESULT.md` |
| P2-10 | Tiny MIPS32 end-to-end proof | `PASS` | `.openrecomp-phase2/evidence/P2-10/RESULT.md` |
| P2-11 | MIPS32 calls/stack/memory | `PASS` | `.openrecomp-phase2/evidence/P2-11/RESULT.md` |
| P2-12 | MIPS32 direct CFG stress | `PASS` | `.openrecomp-phase2/evidence/P2-12/RESULT.md` |
| P2-13 | Runtime-host boundary | `PASS` | `.openrecomp-phase2/evidence/P2-13/RESULT.md` |
| P2-14 | Larger MIPS32 open fixture | `PASS` | `.openrecomp-phase2/evidence/P2-14/RESULT.md` |
| P2-20 | NES6502 program bridge | `PASS` | `.openrecomp-phase2/evidence/P2-20/RESULT.md` |
| P2-21 | NES6502 host emitter path | `PASS` | `.openrecomp-phase2/evidence/P2-21/RESULT.md` |
| P2-22 | NES runtime bridge | `PASS` | `.openrecomp-phase2/evidence/P2-22/RESULT.md` |
| P2-23 | NES end-to-end proof | `PASS` | `.openrecomp-phase2/evidence/P2-23/RESULT.md` |
| P2-30 | Cross-architecture neutrality audit | `PASS` | `.openrecomp-phase2/evidence/P2-30/RESULT.md` |
| P2-40 | Generic runtime integration audit | `PASS` | `.openrecomp-phase2/evidence/P2-40/RESULT.md` |
| P2-50 | Build/package reproducibility | `PASS` | `.openrecomp-phase2/evidence/P2-50/RESULT.md` |
| P2-90 | Whole-project regression | `PASS` | `.openrecomp-phase2/evidence/P2-90/RESULT.md` |
| P2-91 | Evidence index + limitations | `PASS` | `.openrecomp-phase2/evidence/P2-91/RESULT.md` |
| P2-99 | Final verdict | `PASS` | `.openrecomp-phase2/evidence/P2-99/RESULT.md` |

## P2-99 result (PASS) — Phase 2 closed

Stage: `OPENRECOMP_PHASE2_FINAL_VERDICT_V1`. Branch: `phase2/opencode-v1`.
`HEAD` remains at `2fc27bf` (P2-14 boundary) with the audited Phase-2 work in the
working tree; the Phase-1 tag `openrecomp-phase1-pass` was re-verified unchanged
at `46c2f971e1a42cf49bd936bad94697b81bf31002`. P2-99 is a verification and
closure stage: it adds no architecture feature, runtime functionality or
compatibility claim.

Final verdict markers issued by this stage:

- Stage marker: `OPENRECOMP_P2_99=PASS`
- Gate marker: `OPENRECOMP_PHASE2_FINAL_VERDICT_V1=PASS`
- Final marker: `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS`

- New deterministic terminal gate `tools/test_phase2_final_verdict_v1.py`. It
  re-verifies the completed-stage matrix, the Phase-1 boundary, the P2-91
  evidence index, a terminal whole-project P2-90 regression re-run (22 gates,
  361 audit checks, 1990 gate checks, 0 failures), the P2-91 evidence-closure
  gate (882 checks), source integrity, the legal/content policy and the
  claim/limitation consistency, and emits the final verdict only when every
  required invariant passes. Two official runs produced byte-identical stdout;
  the `--run-regression` run additionally re-executed the P2-90 whole-project
  audit on the terminal tree and preserved the six frozen P2-90 capture files
  byte-identically.
- Terminal-state contract transition (documented, with replacement coverage):
  the P2-90 regression gate and the P2-91 closure gate previously required the
  final marker to be `NOT_PROVEN` and rejected `CURRENT_STAGE=P2-99`. Those
  gates now accept the P2-99 stage state and the terminal `PASS` value only when
  the P2-99 verdict evidence exists, declares PASS, pins the live P2-99 gate by
  SHA-256 and the control plane states the terminal markers; an unauthorized
  final-PASS claim still fails both gates. Pre-terminal stdout of both gates is
  unchanged (the P2-91 closure gate reproduces its recorded `tests=882` stdout
  byte-identically).
- Bounded final claim (issued): OpenRecomp has demonstrated an
  architecture-neutral static-recompilation pipeline capable of taking
  supported synthetic guest programs through decoding, program modelling,
  control-flow recovery, translation, native host compilation, generic runtime
  execution, deterministic observable equivalence, and reproducible packaging
  across the audited NES6502 and MIPS32 paths.
- The verdict does not imply arbitrary NES ROM compatibility, arbitrary MIPS32
  executable compatibility, commercial-game compatibility, complete NES
  hardware emulation, cycle accuracy, PS1/PS2/Xbox compatibility,
  universal-console support or arbitrary future-architecture compatibility; all
  of those remain `NOT_PROVEN`/`OUT_OF_SCOPE` in
  `.openrecomp-phase2/evidence/P2-91/PHASE2_LIMITATIONS.md` and
  `PHASE2_CLAIM_MATRIX.md` with the final-marker claim classified `PROVEN` at
  its documented boundary.
- Section ordering note: the `P2-91 result` and earlier stage-result sections
  below are historical stage-time records; the terminal verdict is this
  section, `HANDOFF.md` and `.openrecomp-phase2/evidence/P2-99/`.

## P2-91 result (PASS)

Stage: `OPENRECOMP_PHASE2_EVIDENCE_CLOSURE_V1`. Branch: `phase2/opencode-v1`.
Closure/documentation/evidence stage: no architecture feature was added and no
compatibility claim was broadened. `HEAD` remains at `2fc27bf` (P2-14 boundary)
with the P2-91 work in the working tree; the Phase-1 tag `openrecomp-phase1-pass`
is unchanged at `46c2f971e1a42cf49bd936bad94697b81bf31002`.

- New deterministic closure gate `tools/test_phase2_evidence_closure_v1.py`:
  882 checks pass (assessment index completeness and reference validity,
  limitations coverage, claim-matrix consistency, terminology consistency,
  host-path recurrence prevention, premature-final-verdict prevention, the
  P2-90 regression capture validation, source integrity and the legal/content
  policy). Two consecutive full gate runs produced byte-identical stdout
  (`gate_determinism.txt`, `p2_91_run1.txt`, `p2_91_run2.txt`).
- Authoritative Phase-2 evidence index: `PHASE2_EVIDENCE_INDEX.md` +
  `PHASE2_EVIDENCE_INDEX.json` cover all 23 completed stages (P2-00,
  P2-01..P2-14, P2-20..P2-23, P2-30, P2-40, P2-50, P2-90) with PASS marker,
  gate marker, check count, evidence directory, principal RESULT, fixture/input
  identity, generated/executable/package identity, deterministic-run identity
  and claim boundary. Every indexed identity is re-verified against frozen
  stage evidence; every indexed reference resolves.
- `PHASE2_LIMITATIONS.md` bounds 13 proven/bounded-proven claims and 10
  unproven/out-of-scope claims; `PHASE2_CLAIM_MATRIX.md` maps the same 23-key
  claim vocabulary (18 audited P2-90 claims unchanged + 5 P2-91 closure claims)
  to evidence and boundaries.
- Host-path resolution (the nine P2-90 occurrences): seven are historical
  absolute-path evidence that must remain frozen (six hash-pinned), two are
  safely relocatable toolchain-detection metadata with host-neutral derivatives
  (`portable_derivatives/`); zero are regenerable-without-gate-change, zero are
  genuine portability defects. No frozen evidence file was modified; no new
  absolute host path exists in Phase-2 evidence, control-plane narrative,
  shared sources or release packages.
- P2-90 whole-project regression rerun (after all P2-91 changes): `PASS`,
  361 audit checks, 22 gates, 1990 gate checks, 0 failures, stdout content
  identical to the frozen P2-90 capture (LF content sha256 `00675593...`; the
  recorded capture `74e9eada...` remains byte-identical). The six frozen P2-90
  capture files were preserved byte-identically around the rerun; the only
  regeneration delta is the expected manifest-count line (132 -> 133).
- Source integrity: `PASS`, 133 manifest entries; the manifest delta is exactly
  additive (removing the closure-gate line reproduces the P2-90 manifest
  `1bf21db5...`). Legal/content policy clean.
- The final marker remains `NOT_PROVEN`: P2-91 does not claim
  `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS`; the final verdict is
  reserved for P2-99.

## P2-90 result (PASS)

Stage: `OPENRECOMP_PHASE2_WHOLE_REGRESSION_AUDIT_V1`. Branch: `phase2/opencode-v1`.
`HEAD` at `2fc27bf` (P2-14 boundary); Phase-1 tag `openrecomp-phase1-pass` verified
unchanged at `46c2f971e1a42cf49bd936bad94697b81bf31002`.

- New deterministic audit gate `tools/test_phase2_whole_regression_v1.py`: it re-runs
  every applicable completed Phase-2 gate (P2-01..P2-14, P2-20..P2-23, P2-30, P2-40,
  P2-50 and the NES platform contract), the Phase-1 host gates, source integrity, and
  audits cross-stage evidence consistency, source/manifest correspondence and the
  asset/legal/content policy. 361 audit checks, 22 executed gates, 1990 gate checks,
  zero failures. No `openrecomp/*.py` implementation source, gate or test was modified.
- Two consecutive full audit runs produced byte-identical stdout
  (`sha256 74e9eadaf0e17ca4a97790e4239f40883cc745cd9817c172f7fa6e2663ce1ee7`) and empty
  stderr; both emitted `OPENRECOMP_P2_90=PASS`,
  `OPENRECOMP_PHASE2_WHOLE_REGRESSION_V1=PASS tests=361 gates=22 gate_tests=1990` and
  preserved `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=NOT_PROVEN`.
- Every gate reproduces its recorded marker and test count; recorded stdout hash claims
  reproduce under the capture convention used to record them (utf-8 LF/CRLF,
  utf-16le-BOM CRLF, or with the frozen evidence-dir prefix reconstructed for
  path-printing gates). Every recorded identity (fixtures, generated sources, objects,
  executables, package archives, fingerprints) matches the frozen evidence and the
  fresh runs; the seven frozen stdout captures over P2-10..P2-14 reproduce with exactly
  the documented one-line cross-stage guard deltas.
- Corrections applied before the official runs (see
  `.openrecomp-phase2/evidence/P2-90/corrections_report.md`): stale P2-50 archive and
  source-state claims in STATE/HANDOFF were replaced with the evidence-derived values
  (`fa72b5d169ad...`, `1c1dac0ea994...`, `71847f9d7ffd...`,
  `5d93971b102b24e56b2c98bf4c6b6486f58e6c174700af1c77cf969f85024c54`); the P2-20-session
  P2-14 guard replacement (`no-p2-20-evidence-directory` ->
  `no-nes6502-dependency-in-p2-14`, count unchanged at 82) is now documented with the
  current P2-14 stdout hash `197a6c5e...`; the gate-block source-integrity count was
  corrected to 132 manifest entries.
- Bounded evidence-hygiene limitation documented, not rewritten: nine frozen evidence
  files in P2-00/P2-07/P2-08/P2-40/P2-50 contain host-environment identifiers
  (working-copy/compiler/interpreter paths). They are pinned by the hash-pinned PASS
  evidence of those stages; no new occurrences are permitted and P2-90-owned artifacts
  are host-path-free. Sanitization is deferred to P2-91.
- Expected manifest-count deltas: re-running the P2-50 gate on the P2-90 tree
  reproduces every recorded package/payload/identity hash; only
  `changed_files.txt`, `input_hashes.txt` and `source_integrity.txt` differ, and exactly
  by the addition of the P2-90 gate to `SOURCE_SHA256SUMS.txt` (131 -> 132 entries).
- Phase-1 host gates: `PASS=44 FAIL=0 SKIPPED=2`; source integrity verified 132
  manifest entries (P2-90 gate registered via `update_sums.py`; no existing entry
  changed relative to the pre-P2-90 P2-50 state).
- The final verdict marker remains `NOT_PROVEN`; P2-90 does not claim
  `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS` (reserved for P2-99).

## P2-50 result (PASS)

Stage: `OPENRECOMP_BUILD_PACKAGE_REPRODUCIBILITY_V1`. Branch: `phase2/opencode-v1`.
`HEAD` at `2fc27bf` (P2-14 boundary); Phase-1 tag `openrecomp-phase1-pass` verified
unchanged at `46c2f971e1a42cf49bd936bad94697b81bf31002`.

- New architecture-neutral packaging module `openrecomp/release_package.py`
  (`openrecomp-release-package-v1`): canonical release manifest, byte-deterministic
  store-only ZIP container (fixed 1980-01-01 metadata, sorted names, no extra fields, no
  directory entries), explicit artifact -> source-state provenance, content/legal-asset
  policy and fail-closed verification. New deterministic gate
  `tools/test_build_package_reproducibility_v1.py`: 174 checks pass with the full
  regression run; two consecutive full gate runs produced byte-identical stdout+stderr
  (`sha256 0616da411e9b3b12e485b43056981e5fc269565ac932d556912ff9e82e63c92d`).
- Three representative targets: synthetic NES/NROM end-to-end fixture (P2-23,
  `dfadcbe7...`), synthetic 4-function MIPS32/non-NES fixture (P2-14, `1c233f56...`) and
  the shared runtime/build pipeline through the P2-08 generic runtime ABI (P2-40,
  `9323f245...`).
- Per target: two independent clean build roots, two isolated P2-09 runs each; generated
  source, runtime support source, normalized compile/link command lines, build manifests,
  objects and executables are byte-identical across roots/runs; P2-09 classification
  `EXECUTABLE_REPRODUCIBLE`; no binary post-processing and no normalization.
- Reproduced prior-stage identities exactly: P2-40 exe `96676bec...`, P2-14 exe
  `1e81bf8c...`, P2-23 exe `5afd387d...` (all matching their committed evidence).
- Deterministic release packages assembled independently from each root are
  byte-identical and self-verifying: `generic-runtime-pipeline` archive
  `fa72b5d169ad...`, `mips32-larger` archive `1c1dac0ea994...`, `nes-nrom-end-to-end` archive
  `71847f9d7ffd...`; exact entry sets (generated.c, runtime_support.c, build_manifest.json,
  program.exe, release_manifest.json, SHA256SUMS.txt), fixed archive metadata, empty
  content-policy and host-needle findings.
- Repeated runtime observations from the independently built executables are
  byte-identical and equal the declared expected observables (4 executions per target);
  returncodes 0.
- Nondeterminism audit: COFF object `TimeDateStamp` = 0, PE executable `TimeDateStamp`
  content-derived by `/Brepro` and identical across roots, PE debug directory contains
  exactly one `Repro (0x10)` `/Brepro` marker (objects none), no host-path/secret needles;
  classification `BYTE_DETERMINISTIC_NO_NORMALIZATION` for all three targets.
- Source-state provenance: canonical source-state fingerprint
  `5d93971b102b24e56b2c98bf4c6b6486f58e6c174700af1c77cf969f85024c54`; recorded pipeline
  source files re-verified against the working tree at package time.
- Regressions re-run and passed: P2-01..P2-14, P2-20..P2-23, P2-30, P2-40, NES platform,
  Phase-1 host gates (`PASS=44 FAIL=0 SKIPPED=2`) and source integrity (131 manifest
  entries; the new gate was added via `update_sums.py`, no existing entry changed).
- Fail-closed packaging coverage: unsafe/absolute/hidden/reserved names, forbidden
  extensions, console-image magic, absolute/temp paths, private-key/credential content,
  duplicate/empty packages, provenance/artifact mismatches, tampered archives, extra or
  removed entries, reordered/non-canonical manifests, checksum tamper and source-state
  tamper all reject.
- No existing `openrecomp/*.py` implementation source or existing test was modified; no
  P2-90 started; final marker remains `NOT_PROVEN`.

## P2-40 result (PASS)

Stage: `OPENRECOMP_GENERIC_RUNTIME_INTEGRATION_V1`. Branch: `phase2/opencode-v1`.
`HEAD` at `2fc27bf` (P2-14 boundary); Phase-1 tag `openrecomp-phase1-pass` verified
unchanged at `46c2f971e1a42cf49bd936bad94697b81bf31002`.

- New deterministic audit gate `tools/test_generic_runtime_integration_v1.py`
  (181/181 checks pass with the full regression run; two full runs byte-identical,
  stdout sha256 `405c90d1c867495b3ac568a62b0d7c7e9234ca5ef469cdc2510d307b8d148228`).
  No `openrecomp/*.py` implementation source was modified.
- Audited generic runtime modules: `openrecomp/runtime_abi.py`, `openrecomp/runtime.py`,
  `openrecomp/module.py`, `openrecomp/host_emitter.py`, `openrecomp/build_pipeline.py`.
  Architecture-specific boundary modules reviewed: `openrecomp/frontends/nes_runtime.py`,
  `openrecomp/frontends/nes6502.py`, Phase-1 headless platform layers.
- Static isolation: no prohibited platform imports, identifiers/strings, service names
  or NES/GB/SMS bus-address literals in the audited generic modules; no host-state
  imports in `runtime_abi`/`runtime`. Scanner self-test detects a planted leak and does
  not flag clean generic source.
- Contract classification: all 21 runtime concepts assigned to one of
  architecture-neutral contract (13), platform adapter (5), architecture/frontend (3) or
  host implementation (4) responsibility; bound-vs-assumption analysis recorded.
- Generic memory proven non-NES: 16-bit space does not wrap and does not NES-mirror
  (`0x800` reading does not alias 0), 20-bit and 24-bit segments are not truncated,
  widths {8,16,32,64}, explicit endianness, 64-bit overflow fail-closed.
- Non-NES exercise: synthetic/original 11-instruction MIPS32 fixture
  (`9323f245...`) -> P2-01..P2-09 -> generated host C (`c0a76e0f...`) that uses only the
  generic `or_rt_memory_read/write`, `or_rt_host_call` boundary -> native executable
  (`96676bec...`, `EXECUTABLE_REPRODUCIBLE`) with three synthetic services
  (`synthetic.frame.submit`, `synthetic.audio.submit`, `synthetic.input.poll`). The
  independent Python reference observable equals the native observable exactly (frame
  and audio payloads submitted through the generic contracts, input poll 141,
  17-bit/20-bit addresses, memory checksum).
- NES path exercised through the same generic contracts: controller bits via `$4016`,
  `RuntimeFrame`/`RuntimeAudio` via generic host-call dispatch, arity/format/mapper/
  PPU/expansion fail-closed; both adapters share `RuntimeServiceTable.dispatch` unchanged.
- Fail-closed native: declared-but-unsupported service -> `failed=1`, continuation not
  executed; emitter rejects missing ABI/undeclared service/no-evidence host calls.
- Backend extension points (GB/GBC/SMS/RT64-like) documented with
  `abi_changes_required=none` for all four.
- Regressions re-run and passed: P2-01..P2-14, P2-20..P2-23, P2-30, runtime ABI, host
  emitter, deterministic build, NES platform, Phase-1 host gates
  (`PASS=44 FAIL=0 SKIPPED=2`) and source integrity (130 manifest entries; the new gate
  was added via `update_sums.py`, no existing entry changed).
- No corrections to generic runtime code were required; no architecture leakage found.

## P2-30 result (PASS)

Stage: `OPENRECOMP_P2_30_CROSS_ARCHITECTURE_NEUTRALITY_V1`.
Branch: `phase2/opencode-v1`. Phase-1 tag `openrecomp-phase1-pass` verified unchanged at
`46c2f971e1a42cf49bd936bad94697b81bf31002`.

- New audit gate `tools/test_cross_architecture_neutrality_v1.py` (14 deterministic checks).
  No existing `openrecomp/*.py` implementation source modified.
- Shared modules audited: `openrecomp/program_model.py`, `cfg.py`, `functions.py`,
  `call_graph.py`, `translation_units.py`, `indirect_control_flow.py`, `host_emitter.py`,
  `runtime_abi.py`, `build_pipeline.py`.
- Architecture-specific boundary modules reviewed: `openrecomp/frontends/nes6502.py`,
  `openrecomp/frontends/nes_runtime.py`.
- Static import isolation: shared modules contain no imports from `adapters.*`,
  `adapters.nes6502`, `adapters.mips32`, `openrecomp.frontends.nes6502`, or
  `openrecomp.frontends.nes_runtime`.
- Static symbol isolation: shared modules contain no prohibited NES/6502/MIPS-specific
  constants, address layouts, register names, opcode tables, or platform symbols.
- Adapter isolation: NES-specific frontends import only from shared `openrecomp.*` modules
  and their own adapter (`adapters.nes6502`); no sibling-frontend or unrelated-adapter
  dependencies.
- Non-NES path exercised: synthetic/original 8-instruction MIPS32 fixture traversed
  P2-01 -> P2-02 -> P2-03 -> P2-04 -> P2-05 -> P2-06 -> P2-07; generated host source
  SHA-256 `be52ef25060e22f8c4677c2e87a2e89180f82ae88833c4d910ec11fe1881b9f6`;
  byte-identical across two emissions; contains no NES terms.
- Determinism: two consecutive full gate runs produced byte-identical stdout
  (`sha256 49a2a255e714d17ab00d224dc3f6f218df8eb0e00d26d60ecfc71c89404abb54`).
- Source integrity passed: `python tools/phase1_host_gates_v1.py --only source-integrity`
  verified 129 manifest entries.
- Relevant regressions re-run and passed: P2-01..P2-14, P2-20..P2-23, runtime ABI,
  host emitter, deterministic build, Phase-1 host gates and source integrity.
- No corrections were required; no architecture leakage was found in shared layers.

## P2-05 result (PASS)

Stage: `OPENRECOMP_P2_05_TRANSLATION_UNITS_V1`.
Starting commit: `ea954d6306352fe63ed438cc43f107fe168471d4` (P2-04 boundary).
Branch: `phase2/opencode-v1`. Phase-1 tag `openrecomp-phase1-pass` verified unchanged at
`46c2f971e1a42cf49bd936bad94697b81bf31002`.

- Module `openrecomp/translation_units.py`: `build_translation_units(discovery, *,
  call_graph=None)` / `build_translation_units_from(...)` -> `TranslationUnitSet`;
  `TranslationUnitSet` contains exactly one `TranslationUnit` (`unit_id = "tu_" +
  function.id`) per P2-03 `FunctionUnit`.
- Structural package only: canonical block order (entry first, then `(entry_address,
  id)`), verbatim instructions/successors, P2-04 call edges per caller, unresolved
  call/jump sites, external targets without invented callees, `entry_sources` +
  `EntryBasis` provenance, and residual `shared_blocks` / `suppressed_entries` /
  `unowned_blocks` / `unowned_control_flow` evidence.
- Deterministic canonical serialization/fingerprint; round-trip byte identity;
  arbitrary-precision addresses (64-bit and >64-bit fixtures).
- No IR lowering; no architecture-specific semantics; no invented targets; no discarded
  unowned evidence; fail closed with `TranslationUnitError`.
- `tools/test_translation_units_v1.py`: 104 deterministic checks.
- No P2-01/P2-02/P2-03/P2-04 source modified.

## P2-06 result (PASS)

Stage: `OPENRECOMP_P2_06_INDIRECT_CONTROL_FLOW_CLASSIFICATION_V1`.
Starting commit: `ce9cd4fc3aa87cbe9009c39abd52c5de083080e1` (P2-05 boundary).
Branch: `phase2/opencode-v1`. Phase-1 tag `openrecomp-phase1-pass` verified unchanged at
`46c2f971e1a42cf49bd936bad94697b81bf31002`.

- Module `openrecomp/indirect_control_flow.py`: `classify_indirect_control_flow(units, *,
  evidence=())` / `classify_indirect_control_flow_from(...)` -> `IndirectControlFlowSet`.
- Categories: `RESOLVED`, `BOUNDED_CANDIDATES`, `EXTERNAL_OR_RUNTIME_MEDIATED`,
  `RETURN_LIKE`, `UNRESOLVED_INDIRECT_CALL`, `UNRESOLVED_INDIRECT_JUMP`,
  `UNSUPPORTED_OR_MALFORMED`. Proof bases: `EXACT_CONSTANT_TARGET`, `EXACT_TARGET_SET`,
  `ADAPTER_EVIDENCE`, `BOUNDED_CANDIDATE_EVIDENCE`, `EXTERNAL_RUNTIME_EVIDENCE`,
  `STRUCTURAL_RETURN_EVIDENCE`, `NONE`.
- Unknown remains unknown: no target is inferred from metadata, nearby code, opcode or
  reason strings; `RESOLVED` requires PROVEN evidence; bounded candidates are never
  promoted. Each classification preserves function/block/instruction/site provenance, the
  original `UnresolvedSite`, `provenance`, `targets`/`target_functions`, mechanism/detail
  and `evidence`.
- Deterministic canonical serialization/fingerprint; round-trip byte identity;
  arbitrary-precision addresses (64-bit and >64-bit). No IR lowering; no host emission;
  no architecture-specific semantics.
- `tools/test_indirect_control_flow_v1.py`: 134 deterministic checks.
- P2-05 `TranslationUnitSet` is read without mutation; unowned control flow is preserved
  as residual evidence (`IndirectControlFlowSet.unowned_control_flow`) and not classified.
- No P2-00..P2-05 implementation or evidence modified.

## P2-07 result (PASS)

Stage: `OPENRECOMP_P2_07_HOST_EMITTER_V1`.
Starting commit: `f9f2662b90c165a967fa943070e79688ff8198b1` (P2-06 boundary).
Branch: `phase2/opencode-v1`. Phase-1 tag `openrecomp-phase1-pass` verified unchanged at
`46c2f971e1a42cf49bd936bad94697b81bf31002`.

- Module `openrecomp/host_emitter.py`: `emit_host_translation(translation_units,
  classification, *, config)` / `emit_host_translation_from(...)` -> `HostTranslationSet`,
  generating deterministic portable C (C99; only `<stdint.h>`/`<stddef.h>`).
- Emits only explicitly proven semantics: a `HostInstructionSemantics` rule must exist for
  the exact `(architecture, op)` pair; the bounded vocabulary is const/copy/add/sub/mul/
  and/or/xor/shl/lshr/ashr/signed+unsigned compare with explicit 8/16/32/64-bit masking.
- Direct fallthrough, conditional branch, jump, internal call, return and P2-06
  `RETURN_LIKE` are emitted; `RESOLVED` single targets are direct and finite sets use a
  `switch` with a fail-closed default.
- Fail closed: unsupported op, external direct call, unresolved/bounded/external
  indirect sites, unsupported/malformed classification, non-local edges, traps,
  un-normalized shifts and malformed input. `BOUNDED_CANDIDATES` are never promoted and no
  indirect target is guessed. Policy `BOUNDARY` (default) or `REJECT`.
- Deterministic identifiers/ordering/declarations/helpers; no absolute path, timestamp or
  Python identity; no IR lowering; no runtime ABI (P2-08); no guest execution.
- `tools/test_host_emitter_v1.py`: 106 deterministic checks (incl. an optional native
  compile+run of a synthetic 8-bit fixture: observed `44 0` == expected).
- No P2-00..P2-06 implementation or evidence modified.

## P2-08 result (PASS)

Stage: `OPENRECOMP_P2_08_GENERIC_RUNTIME_ABI_V1`.
Starting commit: `30b4321011b963efce19b321c72b97f886ba2b3d` (P2-07 boundary).
Branch: `phase2/opencode-v1`. Phase-1 tag `openrecomp-phase1-pass` verified unchanged at
`46c2f971e1a42cf49bd936bad94697b81bf31002`.

- Module `openrecomp/runtime_abi.py`: first architecture-neutral generic runtime ABI V1
  (`RuntimeAbiVersion`, `RuntimeMemory`, `RuntimeService`/`RuntimeServiceTable`,
  `RuntimeHostCallRequest`/`RuntimeHostCallRecord`, `RuntimeInputSnapshot`, `RuntimeFrame`,
  `RuntimeAudio`, `RuntimeFailure`/`RuntimeFailureCode`/`RuntimeResult`,
  `RuntimeConfig`/`RuntimeAbiConfig`, `RuntimeState`, `abi_c_declarations`/`abi_c_source`).
- Versioned ABI `openrecomp-generic-runtime-abi 1.0.0`; incompatible versions are detected
  and rejected with `ABI_VERSION_MISMATCH`.
- Bounded guest address space: checked read/write, explicit 8/16/32/64-bit width, explicit
  little/big endianness, and deterministic failures for out-of-range, unsupported width,
  unsupported endianness, segment overlap and 64-bit `address+width` overflow. Guest
  addresses are never host pointers; byte access returns immutable `bytes` copies.
- Host calls: stable service identity plus deterministic argument/result representation;
  unknown services, arity mismatch and handler failure all fail closed. No console API is
  invented.
- Generic input (ordered digital/analog channels with canonicalization), frame
  (geometry/format/checksum) and audio (format/rate/channels/frames/checksum) contracts;
  no controller layout, graphics backend or audio backend is assumed.
- Explicit failure/trap model with stable codes; `RuntimeState` is deterministic (no
  wall-clock/random/pid/address/filesystem/locale/environment dependence) with a
  configuration-seeded RNG hook and canonical serialization/fingerprint.
- Bounded P2-07 emitter integration: `HostEmitterConfig.runtime_abi` (default null) plus an
  explicit `HostCallOperation` rule. A host call is emitted only for a declared service on
  an explicitly external/runtime-mediated P2-06 site; undeclared services, missing config
  and non-external sites fail closed. Default (`runtime_abi=None`) output is byte-identical
  to P2-07, so fail-closed behavior and the bounded semantic subset are preserved.
- `tools/test_runtime_abi_v1.py`: 169 deterministic checks (incl. an optional native
  compile+run of a synthetic host-call fixture: observed `42 0` == expected).
- No P2-00..P2-07 implementation source modified except the additive/opt-in
  `host_emitter.py` change; no prior test weakened; no P2-09 started.

## P2-09 result (PASS)

Stage: `OPENRECOMP_P2_09_DETERMINISTIC_BUILD_PIPELINE_V1`.
Starting commit: `10971b76090746081cb29ca3405f96da7f143011` (P2-08 boundary).
Branch: `phase2/opencode-v1`. Phase-1 tag `openrecomp-phase1-pass` verified unchanged at
`46c2f971e1a42cf49bd936bad94697b81bf31002`.

- Module `openrecomp/build_pipeline.py`: deterministic build pipeline with canonical
  `openrecomp-build-manifest-v1` serialization, explicit toolchain provenance, isolated
  independent runs and an honest reproducibility classification
  (`SOURCE_REPRODUCIBLE` / `MANIFEST_REPRODUCIBLE` / `OBJECT_REPRODUCIBLE` /
  `EXECUTABLE_REPRODUCIBLE` / `FUNCTIONALLY_REBUILT_BUT_BINARY_DIFFERS` /
  `TOOLCHAIN_UNAVAILABLE`; no claim may exceed observed artifact equality).
- Toolchain detected, never assumed: `clang-cl.exe` 22.1.8 (target
  `x86_64-pc-windows-msvc`) + `lld-link.exe` 22.1.8, with `/Brepro` passed directly to
  both. No binary post-processing and no manual COFF timestamp editing.
- Two genuinely independent builds in distinct directories, regenerating the generated
  source each run, produced byte-identical source, object and executable hashes
  (`generated.c b75d7656...`, `generated.obj fc452409...`, `runtime_support.obj
  51910f33...`, `program.exe de03764e...`); inspected COFF `TimeDateStamp` is `0x0` for
  both objects and `0x974E5A9` for both executables; classification
  `EXECUTABLE_REPRODUCIBLE`.
- The manifest records no timestamp, temporary directory, absolute path, username,
  hostname, pid, UUID or Python identity, and the validator rejects such fields.
- `tools/test_build_pipeline_v1.py`: 120 deterministic checks, including output-only
  `--evidence-dir` generation and evidence-path independence (two evidence roots
  byte-identical; the destination path never influences manifest, source, artifacts,
  classification or gate stdout). Optional native build/execution smoke test observed
  `42 0` (bounded synthetic smoke test, not equivalence).
- Fail closed: source hash mismatch, ABI mismatch, malformed manifest, duplicate output,
  unsafe/absolute names, unsupported compiler, failed compile/link, missing artifact,
  artifact-hash mismatch, over-strong reproducibility claim.
- No P2-00..P2-08 implementation source modified; no prior test weakened; no P2-10 started.

## P2-10 result (PASS)

Stage: `OPENRECOMP_P2_10_TINY_MIPS32_END_TO_END_PROOF_V1`.
Starting commit: `161893389cca5a30aa462670f19ecabfc1be679d` (P2-09 boundary).
Branch: `phase2/opencode-v1`. Phase-1 tag `openrecomp-phase1-pass` verified unchanged at
`46c2f971e1a42cf49bd936bad94697b81bf31002`.

- Dedicated gate `tools/test_mips32_end_to_end_v1.py` (108 deterministic checks). No second
  recompilation path was added; the proof reuses the frozen Phase-2 modules.
- Synthetic/original 13-instruction MIPS32 fixture (52 bytes, SHA-256
  `b33b597c28eb7f7239ee5079728c7f3e447387d4ed34525c445cf8c1e9234975`): `addiu`/`beq`/`nop`
  (delay slot)/`addiu`/`bne`/`nop`/`addu`/`subu`/`slt`/`jr r31`/`nop`. No commercial
  ROM/ELF/game bytes.
- Real pipeline traversal: adapter decode -> P2-01 ProgramModel -> P2-02 CFG (6 blocks;
  taken/not-taken/fallthrough/indirect edges) -> P2-03 function discovery (`fn_1000`;
  `blk_1030` preserved unowned) -> P2-04 call graph (1 node, 0 edges) -> P2-05 translation
  units (`tu_fn_1000`) -> P2-06 classification (`jr r31` at `0x102c` = `RETURN_LIKE`,
  `STRUCTURAL_RETURN_EVIDENCE`, no guessed targets; fails closed as `UNRESOLVED_INDIRECT_JUMP`
  without evidence) -> P2-07 host emission (generated source
  `8570ea4a11321118a3fff270e0dc9756d2a4ee7a52421ece1d2d892384118fbb`) -> P2-09 deterministic
  build. P2-08 is `NOT_APPLICABLE_FOR_FIXTURE` (no host service/runtime-mediated call).
- Independent expected observable (mathematical derivation + tiny independent reference
  interpreter + Phase-1 `mips32_oracle_v1` cross-check on reduced synthetic ELF fixtures)
  equals the actual native observable exactly (`r5=11 r6=6 r7=1`; stdout
  `failed=0` + register dump); returncode `0`; secondary execution identical.
- Two independent `/Brepro` builds: generated source, objects and executable byte-identical
  (`program.exe f94c95d2e86fca83f56e5e87a98bccaa1e2a4ced3fd9222aef29608592810f4e`);
  classification `EXECUTABLE_REPRODUCIBLE`; no binary post-processing.
- No P2-01..P2-09 implementation source modified; no prior test weakened; P2-11 not started.
- Final marker `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF` remains `NOT_PROVEN` (the
  control plane reserves the final marker for the P2-99 final verdict).

## P2-11 result (PASS)

Stage: `OPENRECOMP_P2_11_MIPS32_CALLS_STACK_MEMORY_V1`.
Starting commit: `62044d38feec255fbcceb72754e890e7b644c35e` (P2-10 boundary).
Branch: `phase2/opencode-v1`. Phase-1 tag `openrecomp-phase1-pass` verified unchanged at
`46c2f971e1a42cf49bd936bad94697b81bf31002`.

- Dedicated gate `tools/test_mips32_calls_memory_v1.py` (77 deterministic checks); one
  synthetic/original multi-function MIPS32 fixture (16 instructions, 64 bytes, SHA-256
  `4ce3fdab...`) with an o32-style stack frame, a direct `jal` call and checked `lw`/`sw`.
- Additive, opt-in P2-07 extension: `HostLoad`/`HostStore` emitted as checked
  `or_rt_memory_read`/`or_rt_memory_write` calls, gated on `HostEmitterConfig.runtime_abi`.
  Guest addresses are never host pointers; default (`runtime_abi=None`) output is unchanged
  and P2-07/P2-08 gates still pass.
- Real pipeline traversal: P2-01 two functions -> P2-02 CFG (call continuation + unresolved
  return edges) -> P2-03 discovery (direct-call target becomes a function) -> P2-04 call
  graph (`fn_1000 -> fn_1088`, `INTERNAL_DIRECT`) -> P2-05 two translation units -> P2-06
  two `RETURN_LIKE` `jr ra` sites with no guessed targets -> P2-07 emission -> P2-08
  memory boundary -> P2-09 deterministic build.
- Independent expected observable (true-MIPS32 reference interpreter with delay slots and
  `jal`/`jr $ra`, explicit derivation, RAM checksum `409079371`) equals the actual native
  observable exactly (`r5=42 r2=21 sp=256 ra=0`); returncode `0`; stable across runs.
- Two independent `/Brepro` builds: source, objects and executable byte-identical
  (`program.exe bd719060...`); `EXECUTABLE_REPRODUCIBLE`; no binary post-processing.
- Runtime out-of-range memory access fails closed (`failed=1`, no host OOB write); external
  direct calls, missing rules, missing runtime ABI and malformed input fail closed.
- Cross-stage test adjustment: `tools/test_mips32_end_to_end_v1.py`'s obsolete guard
  `no-p2-11-evidence-directory` was replaced by `no-p2-11-memory-emission-in-p2-10` (count
  unchanged at 108, replacement coverage added; reason in the P2-11 evidence). P2-10
  semantics/observable unchanged; its gate stdout hash changed accordingly.
- No P2-12 implementation started; final marker remains `NOT_PROVEN`.

## P2-12 result (PASS)

Stage: `OPENRECOMP_P2_12_MIPS32_DIRECT_CFG_STRESS_V1`.
Starting commit: `6cb5ff40eca30eaeb383333c10bcf50165a167ce` (P2-11 boundary).
Branch: `phase2/opencode-v1`. Phase-1 tag `openrecomp-phase1-pass` verified unchanged at
`46c2f971e1a42cf49bd936bad94697b81bf31002`.

- Dedicated gate `tools/test_mips32_direct_cfg_v1.py` (96 deterministic checks). No
  `openrecomp/*.py` implementation source was modified; the stage reuses the existing
  pipeline and the P2-11 opt-in memory emission.
- Synthetic/original 35-instruction MIPS32 fixture (140 bytes,
  `2e3309f3...`): counted loop with a backward branch and both outcomes, conditional
  branches, a direct `jal` call with `jr ra` returns, o32 `$ra` save/restore, and a bounded
  indirect dispatch (`jr r5`).
- Real pipeline traversal: P2-01 two functions -> P2-02 CFG (14 blocks; loop back edge;
  branch, call and unresolved indirect edges) -> P2-03 discovery (unowned delay slots
  preserved) -> P2-04 call graph `fn_1000 -> fn_1080` -> P2-05 two units -> P2-06 dispatch
  `RESOLVED`/`EXACT_TARGET_SET` targets `(0x105c, 0x106c)` plus two `RETURN_LIKE` sites ->
  P2-07 emission (switch with two cases and fail-closed default; loop/call/memory) -> P2-08
  memory boundary -> P2-09 deterministic build.
- Independent expected observable (true-MIPS32 reference interpreter with delay slots and
  `jal`/`jr $ra`) equals the actual native observable (`acc=15`, `r2=20`, case A `r6=120`,
  `r7=125`, `sp=248`, `ra=0`); returncode `0`; stable across runs.
- Two independent `/Brepro` builds byte-identical (`program.exe 3d92fc27...`);
  `EXECUTABLE_REPRODUCIBLE`; no binary post-processing.
- Bounded dispatch: an out-of-set runtime selector (`0x2000`) hits the switch default and
  fails closed (`failed=1`); `BOUNDED_CANDIDATES` are never promoted; evidence-free
  indirect control flow is `UNRESOLVED_INDIRECT_JUMP` (boundary or `REJECT`).
- Cross-stage test adjustment: `tools/test_mips32_calls_memory_v1.py`'s obsolete guard
  `no-p2-12-evidence-directory` replaced by `no-p2-12-switch-emission-in-p2-11` (count
  unchanged at 77, replacement coverage; reason in P2-12 evidence). P2-11
  semantics/observable unchanged; its gate stdout hash changed accordingly.
- No P2-13 implementation started; final marker remains `NOT_PROVEN`.

## P2-13 result (PASS)

Stage: `OPENRECOMP_P2_13_RUNTIME_HOST_BOUNDARY_V1`.
Starting commit: `aa9939a73addde9e029111a1c6b0a6a783dda8cc` (P2-12 boundary).
Branch: `phase2/opencode-v1`. Phase-1 tag `openrecomp-phase1-pass` verified unchanged at
`46c2f971e1a42cf49bd936bad94697b81bf31002`.

- Dedicated gate `tools/test_runtime_host_boundary_v1.py` (80 deterministic checks). No
  `openrecomp/*.py` implementation source was modified; the stage reuses the existing P2-08
  host-call seam and the generic runtime ABI.
- Synthetic/original 5-instruction MIPS32 fixture (20 bytes, `7c9ba624...`): guest computes
  `r4=42`, a runtime-mediated `jr r4` site classified `INDIRECT_CALL` with explicit P2-06
  `EXTERNAL_OR_RUNTIME_MEDIATED` evidence (mechanism `runtime-service`), and a continuation
  `r5 = result + 8`.
- Real pipeline traversal: P2-01 -> P2-02 CFG (`CALL_RETURN` continuation) -> P2-03 ->
  P2-04 -> P2-05 (unresolved call site preserved) -> P2-06 (no guessed targets) -> P2-07
  host-call emission (`or_rt_host_call(OR_RT_SERVICE_DEMO_DOUBLE, ...)`) -> P2-08 ABI
  (`RuntimeServiceTable` id 1, macro, known/unknown/arity dispatch) -> P2-09 deterministic
  build.
- Independent expected observable (guest arithmetic + declarative service `x -> 2x`):
  `r4=84`, `r5=92`, runtime record `calls=1 last_service=1 last_arg=42 last_result=84`;
  actual native output identical; returncode 0; stable across runs.
- Two independent `/Brepro` builds byte-identical (`program.exe 8ab94ab0...`);
  `EXECUTABLE_REPRODUCIBLE`; no binary post-processing; no guest→host pointers.
- Unsupported declared service fails closed natively: `failed=1`,
  `error=runtime host service demo.missing failed`, continuation not executed. A host-call
  rule without external evidence, an undeclared service, a missing runtime ABI and malformed
  call operations are all rejected.
- Cross-stage test adjustment: `tools/test_mips32_direct_cfg_v1.py`'s obsolete guard
  `no-p2-13-evidence-directory` replaced by `no-p2-13-host-call-emission-in-p2-12` (count
  unchanged at 96, replacement coverage; reason in P2-13 evidence). P2-12
  semantics/observable unchanged; its gate stdout hash changed accordingly.
- No P2-14 implementation started; final marker remains `NOT_PROVEN`.

## P2-14 result (PASS)

Stage: `OPENRECOMP_P2_14_MIPS32_LARGER_OPEN_FIXTURE_V1`.
Starting commit: `c32a766a0b6499a239fcd4af351a73f1c172a1be` (P2-13 boundary).
Branch: `phase2/opencode-v1`. Phase-1 tag `openrecomp-phase1-pass` verified unchanged at
`46c2f971e1a42cf49bd936bad94697b81bf31002`.

- Dedicated gate `tools/test_mips32_larger_fixture_v1.py` (82 deterministic checks). No
  `openrecomp/*.py` implementation source was modified; the stage reuses the existing
  pipeline, emitter and runtime ABI.
- Synthetic/original 4-function, 57-instruction MIPS32 fixture (228 bytes,
  `1c233f56...`): `main` loops `i = 1..20`, accumulates `outer(i) = 4i + 1` in a
  memory-resident accumulator, tracks the maximum with `bigger`, and returns
  `total + best = 941`; `outer` calls `inner` with a nested frame.
- Real pipeline traversal: P2-01 four functions -> P2-02 CFG (18 blocks; loop conditional,
  back jump, three call continuations) -> P2-03 discovery (unowned delay slots preserved) ->
  P2-04 call graph (3 `INTERNAL_DIRECT` edges) -> P2-05 four units (call edges `[2,1,0,0]`)
  -> P2-06 five `RETURN_LIKE` sites with no guessed targets -> P2-07 emission
  (`25d8d85f...`) -> P2-08 memory boundary -> P2-09 deterministic build.
- Deterministic recompilation: two independent structural runs produce identical
  fingerprints and byte-identical source (`recompilation.txt`).
- Deterministic replay: three native executions produce byte-identical stdout
  (`replay.txt`, `5a44a08c...`).
- Independent expected observable (true-MIPS32 reference interpreter 800 steps + derivation)
  equals the actual native observable (`total=860`, `best=81`, observable `941`); returncode
  `0`.
- Two independent `/Brepro` builds byte-identical (`program.exe 1e81bf8c...`);
  `EXECUTABLE_REPRODUCIBLE`; no binary post-processing.
- Cross-stage test adjustment: `tools/test_runtime_host_boundary_v1.py`'s obsolete guard
  `no-p2-14-evidence-directory` replaced by `no-guest-memory-access-in-p2-13` (count
  unchanged at 80, replacement coverage; reason in P2-14 evidence). P2-13
  semantics/observable unchanged; its gate stdout hash changed accordingly.
- No P2-20 implementation started; final marker remains `NOT_PROVEN`.

## P2-20 result (PASS)

Stage: `OPENRECOMP_P2_20_NES6502_PROGRAM_BRIDGE_V1`.
Starting commit: `2fc27bfd80ef36b62ab3dc854562bbb4d0ce82db` (P2-14 boundary).
Branch: `phase2/opencode-v1`. Phase-1 tag `openrecomp-phase1-pass` verified unchanged at
`46c2f971e1a42cf49bd936bad94697b81bf31002`.

- New architecture-aware bridge `openrecomp/frontends/nes6502.py` and dedicated gate
  `tools/test_nes6502_program_bridge_v1.py` (86 deterministic checks). No existing
  `openrecomp/*.py` implementation source modified.
- Synthetic/original 15-instruction NES6502 fixture (26 bytes,
  `0a236023c59fd5363d0ebdd6ffb18d9b4e792ebeaa11a72ca513b183539fa398`): entry `0x8000`,
  counted loop, indexed store, direct `jsr`/`rts`, direct `jmp`, and indirect
  `jmp ($0300)` whose target is a runtime value and is never inferred.
- Real pipeline traversal through the same shared layers as MIPS32: P2-01 ProgramModel
  (`architecture=nes6502`, 15 instructions) -> P2-02 CFG (8 blocks; loop back edge,
  call continuation, direct jump, unresolved indirect jump) -> P2-03 function discovery
  (`fn_8000`, `fn_8018`; unowned blocks `blk_8011`, `blk_8015` preserved) -> P2-04 call
  graph (one `INTERNAL_DIRECT` edge) -> P2-05 two translation units -> P2-06 one
  `UNRESOLVED_INDIRECT_JUMP` site at `0x8012` with no guessed targets.
- Deterministic fingerprints: program `0dfbf094...`, CFG `2924881e...`, functions
  `7b83a827...`, call graph `e99dce4b...`, units `d0062fed...`, classification
  `67113cc1...`; two independent `bridge_program` calls produce byte-identical
  serializations.
- Independent Phase-1 reference cross-check: `tools/nes6502_reference_v1.py` trace of 21
  executed instruction addresses is a subset of decoded instructions, executed
  control-flow set equals the model set, final state halted at `0x0202`, `a=15`, `x=1`.
- Shared-layer neutrality verified: `openrecomp/program_model.py`, `cfg.py`, `functions.py`,
  `call_graph.py`, `translation_units.py`, `indirect_control_flow.py` contain no adapter,
  frontend, `nes6502`, `mips` or `6502` imports.
- Fail-closed: undocumented opcode, truncated operands, region past memory,
  entry-not-before-end, entry out of range, non-bytes memory image, and empty region
  selection all raise `NES6502BridgeError`.
- No P2-21 implementation started; final marker remains `NOT_PROVEN`.

## Gates

```text
OPENRECOMP_P2_50=PASS
OPENRECOMP_BUILD_PACKAGE_REPRODUCIBILITY_V1=PASS tests=174
OPENRECOMP_P2_40=PASS
OPENRECOMP_GENERIC_RUNTIME_INTEGRATION_V1=PASS tests=181
OPENRECOMP_P2_30=PASS
OPENRECOMP_CROSS_ARCHITECTURE_NEUTRALITY_V1=PASS tests=14
OPENRECOMP_P2_23=PASS
OPENRECOMP_NES_END_TO_END_V1=PASS tests=50
OPENRECOMP_P2_22=PASS
OPENRECOMP_NES_RUNTIME_BRIDGE_V1=PASS tests=66
OPENRECOMP_P2_21=PASS
OPENRECOMP_NES6502_HOST_EMITTER_V1=PASS tests=74
OPENRECOMP_P2_20=PASS
OPENRECOMP_NES6502_PROGRAM_BRIDGE_V1=PASS tests=86
OPENRECOMP_NES_PLATFORM_V1=PASS tests=10
OPENRECOMP_MIPS32_LARGER_FIXTURE_V1=PASS tests=82
OPENRECOMP_RUNTIME_HOST_BOUNDARY_V1=PASS tests=80
OPENRECOMP_MIPS32_DIRECT_CFG_V1=PASS tests=96
OPENRECOMP_MIPS32_CALLS_MEMORY_V1=PASS tests=77
OPENRECOMP_MIPS32_END_TO_END_V1=PASS tests=108
OPENRECOMP_DETERMINISTIC_BUILD_V1=PASS tests=120
OPENRECOMP_GENERIC_RUNTIME_ABI_V1=PASS tests=169
OPENRECOMP_HOST_EMITTER_V1=PASS tests=106
OPENRECOMP_INDIRECT_CONTROL_FLOW_V1=PASS tests=134
OPENRECOMP_TRANSLATION_UNITS_V1=PASS tests=104
OPENRECOMP_CALL_GRAPH_V1=PASS tests=61
OPENRECOMP_FUNCTION_DISCOVERY_V1=PASS tests=67
OPENRECOMP_CFG_V1=PASS tests=82
OPENRECOMP_PROGRAM_MODEL_V1=PASS tests=49
OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
PASS source-integrity  verified 132 manifest entries
OPENRECOMP_P2_90=PASS
OPENRECOMP_PHASE2_WHOLE_REGRESSION_V1=PASS tests=361 gates=22 gate_tests=1990
OPENRECOMP_P2_91=PASS
OPENRECOMP_PHASE2_EVIDENCE_CLOSURE_V1=PASS tests=882
```

Determinism: two consecutive P2-90 audit runs produced byte-identical stdout
(`sha256 74e9eadaf0e17ca4a97790e4239f40883cc745cd9817c172f7fa6e2663ce1ee7`) and empty
stderr; the audit re-runs every listed Phase-2 gate, the Phase-1 host gates and source
integrity, and verifies frozen captures, recorded identities and recorded stdout hashes.
Two consecutive P2-50 gate runs produced byte-identical stdout+stderr
(`sha256 0616da411e9b3b12e485b43056981e5fc269565ac932d556912ff9e82e63c92d`); the P2-50
gate internally re-runs every listed regression, the Phase-1 host gates and source
integrity, and byte-compares two independent build roots plus two independently assembled
release packages per representative. P2-40 determinism remains unchanged: two consecutive
gate runs produced byte-identical stdout
(`sha256 405c90d1c867495b3ac568a62b0d7c7e9234ca5ef469cdc2510d307b8d148228`). P2-30 determinism remains unchanged: two consecutive gate runs produced
byte-identical stdout
(`sha256 49a2a255e714d17ab00d224dc3f6f218df8eb0e00d26d60ecfc71c89404abb54`).
P2-22 determinism remains unchanged: two consecutive gate runs produced byte-identical stdout
(`sha256 4ae725be384b991c58d5e072930603b93c72c939df89c18f07749ae5c3db7b5c`).
P2-21 determinism remains unchanged: two consecutive gate runs produced byte-identical
stdout (`sha256 e66406e043b9dab859f5cf56ea537f333be7b59619e8c7bbb06bad4fd45f57e4`); two
consecutive native executions produced byte-identical stdout
(`sha256 99848de179b0b120e42eed2e4b68e6e14a2dfa950d1065ac615dd8a845d27f3c`).
P2-20 determinism remains unchanged: two consecutive gate runs produced byte-identical
stdout (`sha256 d104147c5bbc176af44499aed94320e095350f8e9e7f6fafbab8667d33025f03`).
P2-14 deterministic replays produced byte-identical stdout
(`sha256 5a44a08c3bc1fd16044fa4309ed128f277586184f6661b6757b68e69a1517baa`); during the
P2-20 session P2-14's obsolete `no-p2-20-evidence-directory` guard was replaced by the
genuine P2-14 property `no-nes6502-dependency-in-p2-14` (count unchanged at 82; see the
P2-90 corrections report), so P2-14's gate stdout hash is now
`sha256 197a6c5e5c5578ee6fced2eb45b937359bbd612dab8ec11bb4d5c2e6b717da51` and the frozen
pre-adjustment capture `P2-14/p2_14_gate.txt` (`115c2c8a...`) is historical.

## Queue reconciliation note

The completed sequence is `P2-00` baseline, `P2-01` persistent program representation,
`P2-02` basic-block/CFG recovery, `P2-03` function recovery, `P2-04` call-graph recovery,
`P2-05` translation-unit model. The queue originally numbered `P2-04 Direct CFG recovery`,
`P2-05 Indirect-control-flow classification`, `P2-06 Translation-unit model`; it has been
reconciled to the executed sequence.

The indirect-control-flow classification work was assigned to `P2-06` with the original
safety requirement — classify resolvable versus unresolved indirect sites **without
  guessing targets** — and is `PASS`. `P2-07` (Host emitter V1) through `P2-14` (Larger MIPS32
  open fixture) are `PASS`, `P2-20` (NES6502 program bridge) is `PASS`, `P2-21` (NES6502
  host emitter path) is `PASS`, `P2-22` (NES runtime bridge) is `PASS`, and `P2-23` (NES
  end-to-end proof) is `PASS`. `P2-30` (cross-architecture neutrality audit), `P2-40`
  (generic runtime integration audit) and `P2-50` (build/package reproducibility) are
  `PASS`; `P2-90` (whole-project regression and evidence audit) is `PASS`; `P2-91`
  (evidence index + limitations) is `PASS`; `P2-99` (final verdict) is `NEXT`.

This reassignment is a control-plane reconciliation caused by actual execution order. It
does not change the semantics, claims, evidence or PASS status of any frozen prior stage
(`P2-00`..`P2-23`), and it does not alter `ce9cd4f`, `f9f2662`, `30b4321`, `10971b7`,
`1618933`, `62044d3`, `6cb5ff4`, `aa9939a`, `c32a766`, `2fc27bf` or any earlier commit.

## Next exact action

Phase 2 is complete and closed at `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS`.
The terminal verdict was issued by `tools/test_phase2_final_verdict_v1.py` on the
audited tree after the terminal whole-project P2-90 regression re-run, the P2-91
evidence-closure re-run, source integrity, the legal/content policy and the
claim/limitation consistency all passed; evidence is in
`.openrecomp-phase2/evidence/P2-99/`. No further Phase-2 stage remains. Any
future work is a new phase and must not weaken the P2-99 verdict, the P2-90/P2-91
gates, the frozen evidence or the recorded claim boundaries. The Phase-1 tag
`openrecomp-phase1-pass` remains the reference boundary at
`46c2f971e1a42cf49bd936bad94697b81bf31002`.

## Carried-forward findings

- P2-90 proves only that the completed Phase-2 stages still pass together and that their
  cross-stage evidence is internally consistent on the audited tree; it does not upgrade
  any bounded stage claim (synthetic fixtures only; no general NES/MIPS32/console
  compatibility). The claim classification table is
  `.openrecomp-phase2/evidence/P2-90/claim_classification.md`.
- Nine frozen evidence files in P2-00/P2-07/P2-08/P2-40/P2-50 contain absolute
  host-environment identifiers (working-copy/compiler/interpreter paths). P2-91 has
  resolved them: seven are classified as historical absolute-path evidence that must
  remain frozen (six hash-pinned) and two as safely relocatable toolchain-detection
  metadata with host-neutral derivatives; no frozen file was modified, all nine are
  hash-pinned by `.openrecomp-phase2/evidence/P2-91/host_path_occurrences.json`, and the
  P2-91 closure gate fails on any new absolute host path in portable evidence,
  control-plane narrative, shared sources or release packages.
- P2-91 closure findings: the evidence index covers all 23 completed stages with
  re-verified identities and resolving references; the limitations record and claim
  matrix share a 23-key vocabulary (18 P2-90 claims unchanged + 5 closure claims); the
  P2-90 whole-project regression was re-run after all closure changes
  (`PASS tests=361 gates=22 gate_tests=1990`) with stdout content identical to the frozen
  capture and the six frozen P2-90 capture files preserved byte-identically; source
  integrity passes with 133 manifest entries and an exactly additive manifest delta; at
  stage time the final marker remained `NOT_PROVEN` and reserved for P2-99. P2-99 later
  re-ran the whole regression on the terminal tree and issued the authorized verdict
  (`OPENRECOMP_P2_99=PASS`, `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS`).
- P2-40's stdout contains the evidence-dir path it passes to the nested Phase-1 host-gates
  invocation; reproducing its recorded stdout hash requires reconstructing the frozen
  evidence-dir prefix (P2-90 does this explicitly). P2-30/P2-50 recorded stdout hashes
  were captured with a UTF-16LE-BOM CRLF redirection convention; P2-90 verifies both
  conventions.
- The P2-50 gate's `changed_files.txt`, `input_hashes.txt` and `source_integrity.txt`
  are manifest-count dependent; on the P2-90 tree they differ from the frozen P2-50
  recordings exactly by the addition of the P2-90 audit gate to
  `SOURCE_SHA256SUMS.txt` (131 -> 132 entries). All package, payload and executable
  identities still reproduce byte-identically.
- `update_sums.py` globs `schemas/*.json` while the directory is `schema/`, so
  `schema/*.json` (and `openrecomp/*.py`, including `runtime_abi.py`, `build_pipeline.py`
  and `host_emitter.py`) remain outside the integrity manifest (pre-existing; deferred).
- `direct_callees` are provisional structural facts validated across P2-04/P2-05, not ABI
  recovery.
- P2-06 classifies indirect sites but does not recover targets by analysis; unresolved
  sites remain `UNRESOLVED_INDIRECT_CALL` / `UNRESOLVED_INDIRECT_JUMP` and bounded candidate
  sets remain `BOUNDED_CANDIDATES`.
- Unowned control flow is preserved as P2-06 residual evidence and is not classified.
- P2-07 emits only rule-proven semantics; most runtime services remain outside the emitted
  subset. Emitted functions are void with no argument/return ABI.
- P2-08 defines the generic runtime ABI and a bounded host-call seam. The generated C
  contains only boundary declarations (`extern or_rt_*`); no runtime implementation is
  generated, and `RuntimeState` is a deterministic contract surface rather than a guest
  execution engine. P2-13 exercises the seam end-to-end with a declared service and proves
  unsupported-service fail-closed natively.
- P2-09 builds bounded synthetic generated host fixtures on this host's clang-cl/lld-link
  pair. Object/executable reproducibility is demonstrated for that toolchain; other
  toolchains may need different deterministic flags and are classified honestly.
- P2-10/P2-11/P2-12/P2-13/P2-14 prove only bounded synthetic MIPS32 fixtures (13, 16, 35, 5
  and 57 instructions). The neutral CFG/emitter do not model delay slots as first-class
  semantics (fixtures use `nop` delay slots; unreachable delay-slot blocks are unowned
  residual evidence). Call/return is modeled structurally; the fixtures' o32 `$ra`
  save/restore makes that agree with true MIPS32 for those cases, but general `$ra` dataflow
  is not recovered, and saved-`$ra` RAM bytes may differ (so no RAM checksum is part of the
  observable). Only word-width aligned `lw`/`sw` are covered.
- Bounded dispatch target sets and runtime service identities are supplied by explicit
  evidence; the pipeline never recovers or guesses them by analysis.
- The P2-07/P2-08 native compile+run checks, the P2-09 build smoke test and the
  P2-10..P2-14 end-to-end comparisons are bounded synthetic checks, not equivalence proofs.
- Toolchain-gated gates remain unexecutable on this host.
- `STAGE_QUEUE.md` is reconciled to the executed sequence; `P2-01`..`P2-14`,
  `P2-20`..`P2-23`, `P2-30`, `P2-40`, `P2-50`, `P2-90` and `P2-91` are `COMPLETE`, and
  `P2-99` (final verdict) is `NEXT`.
- P2-30 proves only architecture-neutrality of the audited shared Phase-2 layers for the
  supported MIPS32 and NES6502 paths; it does not prove universal future-architecture
  integrability or arbitrary commercial compatibility.
- P2-40 proves only that the audited generic runtime contracts
  (`openrecomp/runtime_abi.py`, `runtime.py`, `module.py`, `host_emitter.py` runtime seam,
  `build_pipeline.py`) are architecture-neutral for the supported Phase-2 paths. It does
  not prove complete generic console emulation, arbitrary future-architecture
  compatibility, complete NES PPU/APU behavior, arbitrary commercial-game runtime
  compatibility, cycle accuracy or full hardware emulation.
- P2-40's non-NES native exercise covers exactly one bounded synthetic 11-instruction
  MIPS32 fixture and its three fixture-declared services plus a gate-local synthetic
  platform adapter. GB/GBC/SMS support is documented as extension points only (no adapter
  implemented), and RT64-like backends remain optional later host-side work.
- P2-40 found no generic-runtime leakage, so no shared runtime code changed. The new audit
  gate was added to `SOURCE_SHA256SUMS.txt` via `update_sums.py` (129 -> 130 entries); no
  existing manifest entry changed.
- P2-50 adds `openrecomp/release_package.py` (new, architecture-neutral; outside the
  `SOURCE_SHA256SUMS.txt` glob set like the other `openrecomp/*.py` modules) and
  `tools/test_build_package_reproducibility_v1.py` (added to `SOURCE_SHA256SUMS.txt` via
  `update_sums.py`, 130 -> 131 entries; no existing entry changed).
- P2-50 proves reproducibility only for the three audited representative fixtures, the
  detected `clang-cl` 22.1.8 / `lld-link` 22.1.8 toolchain on this host and the audited
  canonical ZIP packaging path. Other compilers, operating systems, architectures or
  toolchain versions may require different deterministic flags and are not claimed.
- P2-50 "clean build" means fresh isolated build roots with regenerated sources and no
  artifact reuse; no fresh git checkout is created because the Phase-2 control policy
  forbids parallel worktrees. Package provenance records a canonical source-state list
  (repo-relative file + SHA-256) that is re-verified against the working tree, and the
  tracked pipeline tools/adapters are covered by `SOURCE_SHA256SUMS.txt`.
- P2-50 found no binary nondeterminism: COFF `TimeDateStamp` is 0, the PE
  `TimeDateStamp` is content-derived by `/Brepro`, the PE debug directory holds exactly
  one `Repro (0x10)` marker, and no host-path/secret needles appear in objects or
  executables. No normalization or binary post-processing was applied or needed.
- P2-50 packaging is bounded to generated source, runtime support source, build manifest
  and host executable payloads plus the release manifest and checksums file; it does not
  package objects, caches or any console asset, and no commercial material is involved.
- P2-20 proves only the structural program bridge for a bounded synthetic NES6502 region.
  It does not generate host code, execute translated code, or claim NES equivalence.
- P2-21 proves only that the same bounded synthetic NES6502 fixture can be lowered into an
  executable host program through the shared Phase-2 pipeline. The emitted subset covers
  only the operations exercised by the fixture; the 6502 stack effects of `jsr`/`rts` are
  not modeled. Memory accesses are byte-wide but emitted through the generic runtime ABI
  using the configured 16-bit word width; the fixture runtime support interprets the ABI
  call as a byte access. This is a documented fixture simplification, not a claim about
  general NES memory mapping.

## P2-21 result (PASS)

Stage: `OPENRECOMP_P2_21_NES6502_HOST_EMITTER_V1`.
Starting commit: current P2-20 working tree (no P2-20 boundary commit created).
Branch: `phase2/opencode-v1`. Phase-1 tag `openrecomp-phase1-pass` verified unchanged at
`46c2f971e1a42cf49bd936bad94697b81bf31002`.

- New dedicated gate `tools/test_nes6502_host_emitter_v1.py` (74 deterministic checks). No
  existing `openrecomp/*.py` implementation source modified; the stage reuses the same
  architecture-neutral P2-01..P2-09 pipeline used by MIPS32.
- Synthetic/original 15-instruction NES6502 fixture (26 bytes,
  `0a236023c59fd5363d0ebdd6ffb18d9b4e792ebeaa11a72ca513b183539fa398`): the same region
  proven in P2-20 is now lowered to executable host code.
- Real pipeline traversal: adapter decode -> P2-01 ProgramModel (`architecture=nes6502`)
  -> P2-02 CFG (8 blocks) -> P2-03 function discovery (`fn_8000`, `fn_8018`) -> P2-04
  call graph (one `INTERNAL_DIRECT` edge) -> P2-05 two translation units -> P2-06 one
  `UNRESOLVED_INDIRECT_JUMP` site at `0x8012` (no guessed targets) -> P2-07 host emitter
  (`generated_source.c` `7d42947f...`) -> P2-08 generic runtime ABI (checked byte memory
  boundary) -> P2-09 deterministic build.
- Emitted register file: `a`, `c`, `ea`, `n`, `tmp`, `x`, `z`. Guest A/X registers, C/Z/N
  flag temporaries and an effective-address temporary are the only state exposed to the
  neutral emitter.
- Independent Phase-1 reference cross-check: `tools/nes6502_reference_v1.py` trace of 21
  executed instructions; final reference state `a=15`, `x=1`, halted at `0x0202`. The
  generated native executable fails closed at the unresolved indirect `jmp ($0300)` with
  the same `a=15`, `x=1` observable.
- Deterministic recompilation: two independent structural runs produce identical
  fingerprints and byte-identical generated source. Deterministic replay: two native
  executions produce byte-identical stdout
  (`sha256 99848de179b0b120e42eed2e4b68e6e14a2dfa950d1065ac615dd8a845d27f3c`).
- Two independent `/Brepro` builds: generated source, objects and executable byte-identical
  (`program.exe dbba1e3a...`); classification `EXECUTABLE_REPRODUCIBLE`; no binary
  post-processing.
- Fail-closed: the unresolved indirect jump is emitted as `or_fail("unresolved indirect
  jump"); return;`. Missing semantic rules and missing entry functions are rejected by the
  emitter.
- No P2-22 implementation started; final marker remains `NOT_PROVEN`.

## P2-22 result (PASS)

Stage: `OPENRECOMP_P2_22_NES_RUNTIME_BRIDGE_V1`.
Starting commit: current P2-21 working tree (no P2-21 boundary commit created).
Branch: `phase2/opencode-v1`. Phase-1 tag `openrecomp-phase1-pass` verified unchanged at
`46c2f971e1a42cf49bd936bad94697b81bf31002`.

- New module `openrecomp/frontends/nes_runtime.py`: `NESRuntimeAdapter` connects the
  generic runtime ABI to the NES CPU bus. CPU-visible memory uses `RuntimeMemory`;
  input uses `RuntimeInputSnapshot` mapped to the standard-controller protocol;
  frame/audio use declared host-call services (`nes.frame.submit`, `nes.audio.submit`).
- Dedicated gate `tools/test_nes_runtime_bridge_v1.py` (66 deterministic checks). No
  existing `openrecomp/*.py` implementation source modified; the shared layers are reused
  unchanged.
- Synthetic/original NES6502 fixture (42 bytes,
  `cc57bba3124f264cb6f4ec2b0e83cb82d3a9eeea551d18c098278c7eef827763`): the P2-21
  26-byte core region is preserved unchanged and expanded with controller-probe and
  frame/audio-trigger bytes.
- Memory contract exercised: 2 KiB RAM mirrors, PRG-ROM read and 16 KiB NROM mirror,
  PRG-RAM fail-closed when absent, disabled I/O and expansion-area fail-closed.
- Input contract exercised: generic digital channels map to NES controller bits;
  `$4016`/`$4017` serial reads return the mapped state with documented open-bus bits.
- Frame/audio contracts exercised: services read payloads from guest memory and submit
  deterministic `RuntimeFrame` / `RuntimeAudio` objects through the generic contracts.
- Host-call ABI integration exercised: service ids, numeric ids, macros and generic
  `RuntimeState.host_call` dispatch; arity mismatch fails closed.
- Shared-layer neutrality verified: `openrecomp/program_model.py`, `cfg.py`,
  `functions.py`, `call_graph.py`, `translation_units.py`, `indirect_control_flow.py`,
  `runtime_abi.py`, `host_emitter.py` and `build_pipeline.py` contain no `nes_runtime`,
  `frontends.nes_runtime`, `nes6502` or `adapters.nes6502` imports.
- Fail-closed: unsupported mapper (non-zero), oversized PRG-ROM, disabled I/O registers,
  expansion-area access, PPU register access, unsupported frame/audio format ids and
  host-call arity mismatch all fail deterministically.
- Determinism: two consecutive gate runs produced byte-identical stdout
  (`sha256 4ae725be384b991c58d5e072930603b93c72c939df89c18f07749ae5c3db7b5c`).
- Relevant regressions re-run and passed: P2-01..P2-14, P2-20, P2-21, runtime ABI,
  host emitter, deterministic build, NES platform and source integrity.
## P2-23 result (PASS)

Stage: `OPENRECOMP_NES_END_TO_END_V1`.
Starting commit: current P2-22 working tree (no P2-22 boundary commit created).
Branch: `phase2/opencode-v1`. Phase-1 tag `openrecomp-phase1-pass` verified unchanged at
`46c2f971e1a42cf49bd936bad94697b81bf31002`.

- New dedicated gate `tools/test_nes_end_to_end_v1.py` (50 deterministic checks incl.
  regression re-runs and gate determinism). No existing `openrecomp/*.py` implementation
  source modified; the stage reuses the shared architecture-neutral P2-01..P2-09 pipeline.
- Synthetic/original 59-instruction NES6502 fixture (144 bytes,
  `dfadcbe759121b0705f2a7db3295127b7adceb403a6254897caee85f8a1c44c2`): the P2-21
  26-byte core region and the P2-22 controller-probe bytes are preserved; the previously
  placeholder frame/audio triggers are replaced by real host-call thunks (`svc_frame`,
  `svc_audio`) routed through the generic runtime ABI.
- Real pipeline traversal: adapter decode -> P2-01 ProgramModel -> P2-02 CFG -> P2-03
  function discovery (`fn_8000`) -> P2-04 call graph (1 node, 0 edges) -> P2-05 one
  translation unit -> P2-06 two `EXTERNAL_OR_RUNTIME_MEDIATED` service sites -> P2-07
  host emitter -> P2-08 generic runtime ABI (declared `nes.frame.submit` and
  `nes.audio.submit` services) -> P2-09 deterministic build.
- Generated source fingerprint `9819b40e9909b4056211f6f452297b502b99bc4be4f96fe797cdcdfd6aaf2b78`;
  two independent `/Brepro` builds produced byte-identical source, objects and executable
  (`EXECUTABLE_REPRODUCIBLE`); no binary post-processing.
- Independent reference: `tools/nes6502_reference_v1.py` + `NESRuntimeAdapter`, with the
  same runtime memory/input/frame/audio semantics used by the host support source. The
  reference and the native executable produced byte-identical observable output.
- Observable outputs compared: final guest A/X, controller-derived memory result,
  explicit memory cells, frame count/payload, audio count/payload, failed/error state.
- Determinism: three native executions produced byte-identical stdout
  (`sha256 c53c8ae8606b236c80d7c3fcd10d24da4f00752e15d933dcbdeb2f2882e81f82`); two
  independent full gate runs produced byte-identical stdout
  (`sha256 96dbf5965310bc17a21bfc9fdd38042d30067b1efe7eae41522033dcc2ad1540`).
- Source integrity passed: `python tools/phase1_host_gates_v1.py --only source-integrity`
  verified 128 manifest entries.
- Relevant regressions re-run and passed: P2-01..P2-14, P2-20..P2-22, runtime ABI,
  host emitter, deterministic build, NES platform and source integrity.
- No P2-30 implementation started; final marker remains `NOT_PROVEN`.

## Git status (short)

- P2-14 boundary commit: `2fc27bf` (`phase2: complete P2-14 larger MIPS32 open fixture`);
  `HEAD` at P2-20 start.
- Current uncommitted changes: P2-50 packaging module + gate + evidence
  (`openrecomp/release_package.py`, `tools/test_build_package_reproducibility_v1.py`,
  `.openrecomp-phase2/evidence/P2-50/`), P2-40 audit gate + evidence
  (`tools/test_generic_runtime_integration_v1.py`,
  `.openrecomp-phase2/evidence/P2-40/`), the P2-30 cross-architecture neutrality audit
  gate + evidence (`tools/test_cross_architecture_neutrality_v1.py`,
  `.openrecomp-phase2/evidence/P2-30/`), P2-23 NES end-to-end gate + evidence
  (`tools/test_nes_end_to_end_v1.py`, `.openrecomp-phase2/evidence/P2-23/`), the P2-22
  NES runtime-bridge adapter + gate + evidence (`openrecomp/frontends/nes_runtime.py`,
  `tools/test_nes_runtime_bridge_v1.py`, `.openrecomp-phase2/evidence/P2-22/`), the prior
  P2-21 NES6502 host-emitter gate + evidence (`tools/test_nes6502_host_emitter_v1.py`,
  `.openrecomp-phase2/evidence/P2-21/`), the P2-20 bridge + gate + evidence
  (`openrecomp/frontends/nes6502.py`, `tools/test_nes6502_program_bridge_v1.py`,
  `.openrecomp-phase2/evidence/P2-20/`), plus the prior P2-14 uncommitted changes
  (`tools/test_mips32_larger_fixture_v1.py`, `.openrecomp-phase2/evidence/P2-14/`,
  updated `tools/test_runtime_host_boundary_v1.py`, control-plane updates to
  `.openrecomp-phase2/STAGE_QUEUE.md`, `.openrecomp-phase2/STATE.md`,
  `.openrecomp-phase2/HANDOFF.md`, `SOURCE_SHA256SUMS.txt`).
- Untouched pre-existing untracked residue: `.openrecomp-phase2/backups/`,
  `.openrecomp-phase2/scratch/`, `artifacts/mips32_translation_v1/`,
  `artifacts/mips32_translation_evidence_closure_v1/`.
- No P2-20, P2-21, P2-22, P2-23, P2-30, P2-40 or P2-50 boundary commit created (left for
  independent review).

OPENRECOMP_P2_50=PASS
OPENRECOMP_BUILD_PACKAGE_REPRODUCIBILITY_V1=PASS tests=174
OPENRECOMP_P2_40=PASS
OPENRECOMP_GENERIC_RUNTIME_INTEGRATION_V1=PASS tests=181
OPENRECOMP_P2_30=PASS
OPENRECOMP_CROSS_ARCHITECTURE_NEUTRALITY_V1=PASS tests=14
OPENRECOMP_P2_23=PASS
OPENRECOMP_NES_END_TO_END_V1=PASS tests=50
OPENRECOMP_P2_22=PASS
OPENRECOMP_NES_RUNTIME_BRIDGE_V1=PASS tests=66
OPENRECOMP_P2_21=PASS
OPENRECOMP_NES6502_HOST_EMITTER_V1=PASS tests=74
OPENRECOMP_P2_20=PASS
OPENRECOMP_NES6502_PROGRAM_BRIDGE_V1=PASS tests=86
OPENRECOMP_P2_90=PASS
OPENRECOMP_PHASE2_WHOLE_REGRESSION_V1=PASS tests=361 gates=22 gate_tests=1990
OPENRECOMP_P2_91=PASS
OPENRECOMP_PHASE2_EVIDENCE_CLOSURE_V1=PASS tests=882
OPENRECOMP_P2_99=PASS
OPENRECOMP_PHASE2_FINAL_VERDICT_V1=PASS
OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS
CURRENT_STAGE=P2-99
LAST_PASSED_STAGE=P2-99
