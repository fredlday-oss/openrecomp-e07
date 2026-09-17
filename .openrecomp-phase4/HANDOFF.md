# OpenRecomp Phase 4 Handoff

STATUS: Phase 4 `ACTIVE` — P4-00 (Phase-4 boundary) `PASS`; P4-01 (Generic
Runtime ABI V1) `PASS`; P4-02 (Guest memory/runtime model) is the executing
stage. The frozen
Phase-4 queue (`P4-01` .. `P4-99`) is frozen by `.openrecomp-phase4/STAGE_QUEUE.md`
(`## Queue freeze`) at the P4-00 `PASS` boundary, before any P4-01
implementation work. Phase 3 is complete and frozen at annotated tag
`openrecomp-phase3-pass` (object
`ac31524504b1b5cc63aabcfd5132a3eb4275e8e9`) =
`e16e4b29b90f379615f1af97e47747cd1d531796`, tree
`a940f0d84a32adaf191f7ff2bebfb24cc855cde0`, with
`OPENRECOMP_P3_99=PASS`,
`OPENRECOMP_PHASE3_FINAL_VERDICT_V1=PASS tests=46` and
`OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=PASS` for the bounded audited claim.

Phase 4 objective (`NOT_PROVEN` until P4-99): make the bounded Phase-3
real-ELF recompilation path reusable as an architecture-neutral generic
runtime / platform layer with explicit generated-code <-> runtime,
guest-memory, runtime-service, deterministic-I/O/timing/input,
platform-adapter and graphics/audio-boundary contracts, and a materially more
demanding legally clean fixture executed end-to-end through the generic
runtime.

Reserved markers:

- `OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN` (P4-99 may issue PASS
  for the bounded claim only)
- `OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN` (never promoted)

## P4-01 outcome (PASS)

Markers: `OPENRECOMP_P4_01=PASS`,
`OPENRECOMP_PHASE4_RUNTIME_ABI_V1=PASS tests=156`; terminal and general
compatibility markers reserved as `NOT_PROVEN`.

- New files: `.openrecomp-phase4/src/p4_runtime_abi_v1.py` (executable
  generated-code <-> runtime ABI V1 contract, extending the frozen P2-08
  `openrecomp.runtime_abi`), deterministic
  `.openrecomp-phase4/contracts/generated_runtime_abi_v1.json`,
  `.openrecomp-phase4/ports/generated_runtime_abi_v1.h`, the declared
  instance profile
  `.openrecomp-phase4/ports/generated_runtime_abi_v1_profile_mips32_o32.json`,
  and `tools/test_phase4_runtime_abi_v1.py`; the Phase-4 manifest grew
  additively to six entries.
- The contract covers execution state, calls, returns/exits, faults, memory
  service boundaries, typed/versioned services and deterministic observable
  state; the frozen Phase-3 generated instance is verified compliant
  (`coremark_program.c` `5199e2f0...`, `coremark_support.c` `c5c69054...`);
  negative sources are rejected; the core surface has no fixture/platform
  tokens.
- Two official runs byte-identical raw (`81c96314...`, 6199 bytes) and LF,
  empty stderr, exit 0; `p4_01_tests.json` identical across runs
  (`64da953d...`).
- Regressions: P2-08 `PASS tests=169`, Phase-1 host gates
  `PASS=44 FAIL=0 SKIPPED=2`, public safety `PASS`, P4-00 boundary
  `PASS tests=74` with byte-identical stdout (`953312d0...`) using the
  documented frozen-gate boundary-context hygiene
  (`evidence/P4-01/regression_hygiene.json`).
- Evidence: `.openrecomp-phase4/evidence/P4-01/`.

## P4-00 outcome (PASS)

Markers: `OPENRECOMP_P4_00=PASS`,
`OPENRECOMP_PHASE4_BOUNDARY_V1=PASS tests=74`; terminal and general
compatibility markers reserved as `NOT_PROVEN`.

- Branch `phase4/generic-runtime-v1` descends from the frozen Phase-3 boundary
  commit `e16e4b2...`; tag object `ac315245...`, tree `a940f0d8...`.
- The frozen P3-99 final-verdict gate independently re-passed with
  byte-identical stdout (raw `953ec70c...`, LF `4974d03f...`, exit 0, empty
  stderr) in the reconstructed Phase-3 verification context (temporary
  `phase3/p4-00-verification-context` branch; untracked Phase-4 material held
  outside the worktree and restored; committed verdict record preserved).
  Frozen evidence unchanged: root manifest `76f77bbc...` (134), Phase-3
  manifest `a7d0953c...` (24), P3-99 `RESULT.json` `c893250b...`, gate
  `ba581490...`, fixture `16a0a0aa...`.
- Two consecutive official gate runs of
  `tools/test_phase4_boundary_v1.py` (74 checks, sha256 `5be5c7d2...`)
  byte-identical raw and LF (3186 bytes, raw `953312d0...`, empty stderr,
  exit 0) with `p4_00_tests.json` byte-identical across runs
  (`1c86cebd...`).
- Frozen queue `P4-01` .. `P4-99` recorded and consistent with the STATE
  ledger; `GENERIC_RUNTIME_STATUS=NOT_PROVEN`; no runtime capability claimed.
- Re-run artifacts deliberately left uncommitted:
  `.openrecomp-phase3/evidence/P3-00/p3_00_tests.json` (commit count 12 -> 13)
  and `.openrecomp-phase3/evidence/P3-00/residue_manifest.txt` (rebuilt
  binary hashes). The committed Phase-3 evidence is unchanged.
- Evidence: `.openrecomp-phase4/evidence/P4-00/`
  (`RESULT.md`, `p4_00_tests.json`, `official_runs.json`, `determinism.json`,
  `p3_99_reverify_stdout.txt`, `control_plane_manifest.txt`,
  `changed_files.txt`, `run1.txt`/`run2.txt` and empty stderr captures).

## Frozen boundary identities

- Phase-3 tag object: `ac31524504b1b5cc63aabcfd5132a3eb4275e8e9`
- Phase-3 commit: `e16e4b29b90f379615f1af97e47747cd1d531796`
- Phase-3 tree: `a940f0d84a32adaf191f7ff2bebfb24cc855cde0`
- Phase-3 source manifest sha256: `a7d0953c...` (24 entries)
- Root source manifest sha256: `76f77bbc...` (134 entries, frozen)
- P3-99 RESULT.json sha256: `c893250b...`
- P3-99 gate sha256: `ba581490...`
- P3-99 official stdout: 2498 bytes, raw `953ec70c...`, LF `4974d03f...`
- Phase-2 boundary: `openrecomp-phase2-pass` =
  `01b1d7cba8c931fca95d041389cfb1902b7c89fe`
- Phase-1 boundary: `openrecomp-phase1-pass` =
  `46c2f971e1a42cf49bd936bad94697b81bf31002`

## Exact next action

Execute P4-02 (Guest memory/runtime model): implement and verify explicit
guest memory regions and access semantics (code/data/BSS/stack/heap where
applicable, permissions, bounds, alignment, endian handling and deterministic
fault behaviour) on top of the P4-01 ABI boundary, with invalid/unmapped
accesses failing closed. Add its sources and gate to
`.openrecomp-phase4/SOURCE_SHA256SUMS.txt`, run the official gate twice with
deterministic evidence, run the required regressions (P2-08, Phase-1 host
gates, public safety, and P4-00/P4-01 using the documented frozen-gate
boundary-context hygiene), update the control plane and commit the P4-02
boundary.

## Constraints

Do not modify, rewrite or mutate the frozen Phase-1/Phase-2/Phase-3 evidence,
gates, control planes, verdicts, histories or tags. Do not treat CoreMark as a
supported target. Do not commit proprietary ROM/BIOS/firmware/SDK material or
console assets. Backends (RT64/SDL/Vulkan/Direct3D) are never mandatory to the
core.
