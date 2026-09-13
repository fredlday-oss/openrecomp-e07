# P2-00 — Phase-2 baseline + control plane

VERDICT: `PASS`

SUCCESS MARKER: `OPENRECOMP_P2_00=PASS`

## Baseline

| Item | Value |
| --- | --- |
| Working copy | `D:\OpenRecomp\worktrees\phase2-opencode` |
| Branch | `phase2/opencode-v1` |
| `HEAD` | `46c2f971e1a42cf49bd936bad94697b81bf31002` |
| Phase-1 freeze tag | `openrecomp-phase1-pass` (annotated tag object `8dbbd79ac3c7104bfa0374aecf2d9093be89c6c7`) |
| Tag dereference | `openrecomp-phase1-pass^{commit}` = `46c2f971e1a42cf49bd936bad94697b81bf31002` |
| Ancestry | `git merge-base --is-ancestor 46c2f97 HEAD` -> exit 0 (HEAD equals the freeze; `git log 46c2f97..HEAD` is empty) |
| Phase-1 verdict | `OPENRECOMP_PHASE1_MULTIARCH_PROOF=PASS` |
| Manifest (`SOURCE_SHA256SUMS.txt`) | pre-stage `ffe8ad063c28658cffdf2e3705f0449c210f1bc738d4d933fc513454b4fd8822`; post-stage `27825e43e44ee4b20c44a44adb6dfaccae30691c837cb7cb092b884263749ad5` |

The Phase-2 branch starts strictly from the frozen Phase-1 boundary. No commit was
created. No Phase-1 semantic source file was changed by P2-00.

## Objective

Establish the Phase-2 baseline without changing guest semantics: verify the freeze,
verify descent, inventory reusable infrastructure, and identify coupling blockers
for the P2-01 persistent architecture-neutral program representation.

## Changes

Only one tracked file changed, and it is not semantic source:

| File | Change |
| --- | --- |
| `SOURCE_SHA256SUMS.txt` | 5 recorded hashes corrected (see "Baseline defect repaired"). Line count unchanged at 109 entries. |
| `AGENTS.md` | Pre-existing Phase-2 control block added by the installer (carried in; not changed by this stage's work). |
| `.openrecomp-phase2/**` | New Phase-2 control/evidence directory (untracked). |

No `tools/*.py`, `adapters/*.py`, `contracts/*.json`, `schema/*.json`, `openrecomp/*.py`
or any other guest-semantics file was modified. `git diff` on the semantic tree is empty.

## Baseline defect repaired (non-semantic)

While verifying the freeze, the `source-integrity` host gate failed on the pristine
checkout for 5 manifest entries. Investigation showed this is a deterministic,
pre-existing manifest inconsistency, not a code defect:

- `.gitattributes` pins `*.py` to `text eol=lf`, so a clean checkout stores LF.
- `SOURCE_SHA256SUMS.txt` was generated from a working tree that held CRLF bytes
  for 3 of the files, and stale bytes for the other 2.
- For `tools/test_mips32_causality_v1.py`, `tools/mips32_frontend_v1.py` and
  `tools/build_mips32_translation_fixture.py` the recorded hash equals the SHA-256 of
  the CRLF form of the committed blob.
- For `tools/mips32_oracle_v1.py` and `tools/test_mips32_equivalence_v1.py` the
  recorded hash matches neither the LF nor the CRLF form of any revision in history,
  i.e. the manifest captured working-tree bytes that were never committed.
- The mismatch exists at the freeze commit `46c2f97` and at its parent `bd5f02f`.

The committed content is functionally correct: all 7 MIPS32 gates pass against it
(see below). Repair was therefore limited to regenerating the manifest with the
repository's own `update_sums.py`, exactly the P1-00 precedent for a gate that had
silently become unstable. The change is integrity-strengthening and semantic-preserving;
no guest source byte changed.

Repair evidence:

```text
python update_sums.py
changed manifest lines = 5 (address-ordered reinsertion; 109 entries before and after)
```

Old -> new hashes:

```text
tools/test_mips32_causality_v1.py       154127aa... -> fe9a8c98...
tools/mips32_frontend_v1.py             2b31eabd... -> 9da3f3f9...
tools/mips32_oracle_v1.py               6a5a4a56... -> f16734ef...
tools/test_mips32_equivalence_v1.py     8f3a75ed... -> 4f6c91c0...
tools/build_mips32_translation_fixture.py ef5fa2be... -> 808de0d7...
```

## Commands and results (win32 / PowerShell 5.1 / Python 3.14.6)

```text
git rev-parse HEAD
  46c2f971e1a42cf49bd936bad94697b81bf31002
git rev-parse "openrecomp-phase1-pass^{commit}"
  46c2f971e1a42cf49bd936bad94697b81bf31002
git merge-base --is-ancestor 46c2f971e1a42cf49bd936bad94697b81bf31002 HEAD
  exit 0
git log --oneline 46c2f97..HEAD
  (empty)

python tools/phase1_host_gates_v1.py --only mips32          (pre-repair; exercises 4 of the 5 files)
  PASS source-integrity?  -> FAIL (5 integrity mismatches)
  PASS wasm-runner-intact
  PASS arch-harness-mips32-v1
  PASS mips32-frontend-v1
  PASS mips32-expansion-v1-negative
  PASS mips32-microtests-v1
  PASS mips32-causality-v1
  PASS mips32-equivalence-v1
  OPENRECOMP_PHASE1_HOST_GATES_PASS=7 FAIL=1

python update_sums.py                                        (repair)

python tools/phase1_host_gates_v1.py --only source-integrity --only wasm-runner-intact
  PASS source-integrity  verified 109 manifest entries
  PASS wasm-runner-intact sha256=b973c3c52712937d59a15f2e50c405830be9882b5c457c05b1248b12405613ca
  OPENRECOMP_PHASE1_HOST_GATES_PASS=2 FAIL=0 SKIPPED=0
  OPENRECOMP_PHASE1_HOST_GATES_V1=PASS

python tools/phase1_host_gates_v1.py --json .openrecomp-phase2/evidence/P2-00/host_gates.json
  OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
  OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
```

## Deterministic markers / hashes

| Artifact | SHA-256 |
| --- | --- |
| `.openrecomp-phase2/evidence/P2-00/host_gates.json` | `dc063ef0a3ab0bce4eb98a3ba82ba53be10ba8fcf286629ceaf7f5e9f6ba6d68` |
| `SOURCE_SHA256SUMS.txt` (post-repair) | `27825e43e44ee4b20c44a44adb6dfaccae30691c837cb7cb092b884263749ad5` |

Full-suite summary: `44 PASS / 0 FAIL / 2 SKIPPED`, Python `3.14.6`, 46 gates;
only skipped gates are the toolchain-gated `e07-hardened-end-to-end` and
`external-repro-v1` (missing `clang`/`gcc`, and POSIX for the reviewer gate).
A skip is never counted as a pass. This reproduces the Phase-1 recorded result
exactly (`P1-90`: `44 PASS / 0 FAIL / 2 documented toolchain skips`).

## Reusable components for P2-01 and later (architecture-neutral unless noted)

| Layer | Location | Reuse |
| --- | --- | --- |
| Adapter seam | `adapters/interface.py`, `adapters/*.py` | `ArchitectureInfo` + `decode(address, word)` / `branch_targets(insn)` / optional `is_control_flow`; fail-closed decoders. Directly feeds a persistent decoded-instruction layer. |
| Frontend scaffold | `openrecomp/frontends/scaffold.py` | `IRBuilder` / `validate_decode`; fail-closed assembly of normalized IR + sidecar. Reusable as the emitter target of the P2-01 representation. |
| Normalized IR V1 | `schema/openrecomp-ir-v1.schema.json`, `tools/validate_ir_v1.py`, `docs/IR_SPEC_V1.md` | Frozen architecture-neutral execution IR (`ir_version=1.0.0`). Consume unchanged; do not extend. |
| Module Image V1 | `schema/openrecomp-module-v1.schema.json`, `openrecomp/module.py`, `tools/package_ir_v1_module.py`, `tools/validate_module_v1.py` | Deterministic packaging with IR/contract/source hashes. Reuse unchanged. |
| Core API runtime | `openrecomp/runtime.py`, `openrecomp/executor.py` | `GuestState`, `GuestMemory`, `HostBinding`, `ReferenceExecutor`; architecture-neutral execution and bounds checking. |
| Portable C AOT | `tools/aot_c_backend_v1.py` | Consumes IR V1 + Module Image only; no guest ISA knowledge. Reuse unchanged. |
| Native AOT ABI V1 | `include/openrecomp/native_aot_abi_v1.h`, `tools/native_aot_abi_v1.py`, `tools/aot_native_module_v1.py` | Versioned native module boundary. |
| Deterministic evidence machinery | `tools/arch_harness_v1.py`, `tools/phase1_host_gates_v1.py`, `.openrecomp-phase2/EVIDENCE_SCHEMA.md` | Descriptor-driven decode matrix + chain recipes; gate registry with `--json`/`--only`. Extend additively. |
| ELF/ROM ingestion | `tools/elf_loader.py`, `tools/mips32_elf_loader.py`, `tools/provenance.py`, `tools/gb_rom_loader_v1.py`, `tools/nes_rom_v1.py` | Validated fail-closed ingestion and source provenance. |
| Per-arch frontends | `tools/mips32_frontend_v1.py`, `tools/mips32_expansion_frontend_v1.py`, `tools/bridge_rv32i_ir_v1.py`, `tools/sm83_frontend_v1.py`, `tools/z80_frontend_v1.py`, `tools/nes6502_frontend_v1.py` | Reference consumers of the neutral layers; migration targets for the P2-01 representation. |
| NES6502 path | `adapters/nes6502.py`, `tools/nes_rom_v1.py`, `tools/nes_platform_v1.py`, `tools/nes_headless_v1.py` | Secondary-architecture proof path (P2-20..P2-23). |
| Deterministic serialization | `_serialize` helpers in `arch_harness_v1.py` / `check_frontend_contract_v1.py`; sorted-key JSON | Pattern for P2-01 canonical byte encoding. |

## Architecture/platform coupling blockers for P2-01

1. **No intermediate program model.** Every frontend lowers decoded words straight to
   final IR V1 with ad-hoc per-frontend logic. Block/function discovery and CFG
   construction live inside each frontend (e.g. `tools/mips32_frontend_v1.py`
   `_function_ranges`/`_collect_leaders`/`_convert_function`; analogous code in the
   SM83/Z80/6502 frontends). There is no shared, inspectable decoded-instruction →
   block → function representation between the adapter seam and IR V1. P2-01 must
   introduce this as a new, versioned, architecture-neutral layer.
2. **Function/block ownership is fixture-declared, not recovered.** E.g. MIPS32
   reads `meta["functions"]` ranges. Genuine deterministic block/function recovery is
   P2-02/P2-03 and does not exist in the neutral layer.
3. **Call-graph data is not in IR V1.** `direct_call_graph` and
   `unresolved_indirect_calls` exist only in the legacy RV32I proof IR
   (`schema/ir.schema.json`, `tools/make_ir.py`, `RUN.sh`). Per `AGENTS.md`,
   `direct_call_graph` must mean direct calls only, with unresolved `jalr`/tail calls
   kept separate. The P2-01 representation must carry direct-call edges and
   unresolved indirect sites explicitly.
4. **No provenance classification per unit.** IR V1 has no PROVEN/CANDIDATE marker at
   instruction/block/function granularity; the P2-01 schema must preserve discovery
   method, source bytes/offsets and PROVEN vs CANDIDATE without promoting model
   confidence to evidence.
5. **Frozen-version boundary.** IR V1 is pinned to `ir_version=1.0.0` and Module Image
   V1 to `1.0.0`. The persistent representation must be a *new* versioned schema, never
   an in-place extension of the frozen contracts.
6. **Address-model narrowness.** IR V1 allows `address_bits ∈ {32,64}` only, so
   8/16-bit guests are modeled at 32 with zero-extension (frontend-contract
   `narrow_address_rule`). The program representation must keep guest-native widths
   (PC/IP/database pointer widths) distinct from the IR address type to avoid
   architecture leakage.
7. **Architecture-specific state must stay per-adapter.** Delay slots, HI/LO, `$ra`,
   flags/prefixes, zero registers and link conventions are frontend-only obligations
   (`contracts/frontend_contract_v1.json`). The neutral representation must not encode
   them; it must parameterize on adapter descriptors.
8. **Schema integrity gap (pre-existing).** `update_sums.py` globs
   `schemas/*.json` while the directory is `schema/`, so `schema/*.json` is not
   covered by `SOURCE_SHA256SUMS.txt`. Recorded as a carry-forward finding; not
   changed in P2-00 to keep the stage minimal and non-semantic.
9. **Serialized-CFG absence.** Control flow is embedded in IR V1 terminators; there is
   no standalone explicit CFG artifact (P2-04). P2-01 should persist blocks/edges in a
   form from which the P2-04 CFG and IR V1 lowering both derive, rather than storing
   IR terminators as the source of truth.

## Future integration point (Phase-2 concurrency rule)

A separate PC advances the real PS2/R5900 evidence frontier independently. That work
is not present in this branch and was neither duplicated nor anticipated. This branch
starts from `46c2f97` / `openrecomp-phase1-pass` and contains no R5900/PS2 code.

Integration obligation for P2-01+: the persistent program representation and its
adapter descriptor must be parameterized enough to accept later R5900 evidence
(64-bit GPRs, branch-likely delay slots, load-delay, HI/LO 128-bit, MMI) through the
existing adapter/frontend seam without adding exact-site PS2 classifiers or
reconstructing unmerged commits. No interface may assume 32-bit-only or MIPS-classic
semantics; unresolved PS2 semantics remain `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE`.

## Limitations / repository side effects

- `e07-hardened-end-to-end` and `external-repro-v1` remain toolchain-gated
  (`clang`/`gcc`, POSIX) and are skipped, never counted as pass.
- Running the MIPS32 gates materialized untracked build residue in this worktree:
  `artifacts/mips32_translation_v1/` and `artifacts/mips32_translation_evidence_closure_v1/`.
  These are generated test outputs (also present as pre-existing residue in the source
  checkout) and were left in place, untouched.
- The `update_sums.py` `schema/` coverage gap is documented above and deferred.
- No commit was created. The working tree changes are `AGENTS.md` (installer),
  `SOURCE_SHA256SUMS.txt` (this repair), and the untracked `.openrecomp-phase2/`.

## Next stage

P2-00 is PASS. Advance to P2-01 (persistent architecture-neutral program/function/
block/instruction representation with deterministic serialization). P2-01 must keep
frozen IR V1 / Module Image V1 unchanged and route new representation output through
the existing validator/scaffold, per the blockers above.
