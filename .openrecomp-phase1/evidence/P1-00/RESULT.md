# P1-00 — Repository/baseline audit and deterministic verification inventory

VERDICT: `PASS`

## Source revision and working-tree state

- Branch: `main`, `HEAD = bd5f02fcd21cf42a3d1e24a67c9a285825462b76`, 4 commits ahead of `origin/main`.
- Tracked tree before this stage: only `AGENTS.md` modified (pre-existing Phase-1 control block, added by the installer; backed up at `.openrecomp-phase1/backups/AGENTS.md.20260912-202047.bak`).
- Tracked tree after this stage: `AGENTS.md`, `SOURCE_SHA256SUMS.txt`, `tools/wasm_run.js` modified; `tools/phase1_host_gates_v1.py` added.
- Untracked residue that predates this stage and was deliberately left untouched:
  `.opencode/`, `.openrecomp-phase1/`, `artifacts/mips32_translation_v1/`,
  `artifacts/mips32_translation_evidence_closure_v1/` (+ `.zip`),
  and root build leftovers `generated.win.obj`, `mips32.a.exp`, `mips32.a.lib`, `mips32.a.obj`, `mips32.abi.a.obj`.
- No commit was created (repository convention: commit only at a coherent passed checkpoint; the operator has not requested commits in this session).

## Repository shape (audited)

| Layer | Location | Role |
| --- | --- | --- |
| Legacy E07 proof IR (0.1.1) | `schema/ir.schema.json`, `tools/make_ir.py`, `tools/translate.py` | RV32I fixture path used by `RUN.sh` |
| Architecture seam | `adapters/interface.py`, `adapters/riscv32.py`, `adapters/mips32.py`, `adapters/mips32_stub.py` | `ArchitectureInfo` + `decode`/`branch_targets`(/`is_control_flow`) |
| Normalized IR V1 | `schema/openrecomp-ir-v1.schema.json`, `tools/validate_ir_v1.py`, `docs/IR_SPEC_V1.md` | architecture-neutral wire contract, `ir_version = 1.0.0` |
| Module Image V1 | `schema/openrecomp-module-v1.schema.json`, `openrecomp/module.py`, `tools/package_ir_v1_module.py` | memory segments, initial state, limits, provenance |
| Core API V1 | `openrecomp/runtime.py`, `openrecomp/executor.py`, `tools/run_core_api_v1.py` | `GuestState`, `GuestMemory`, `HostBinding`, `ReferenceExecutor` |
| Portable C AOT + ABI V1 | `tools/aot_c_backend_v1.py`, `tools/native_aot_abi_v1.py`, `include/openrecomp/native_aot_abi_v1.h` | generated C, native module boundary |
| Guest frontends | `tools/bridge_rv32i_ir_v1.py`, `tools/mips32_frontend_v1.py`, `tools/mips32_expansion_frontend_v1.py`, `tools/translate_mips32_elf_v1.py` | per-architecture lowering into IR V1 |
| Host integration | `integrations/unreal/**`, `tools/verify_unreal_*` | optional Unreal consumer of ABI V1 |

## Established-path terminology reconciliation (important)

`AGENTS.md` and the Phase-1 control text require preserving the "PS2/R5900 path".
A repository-wide search (`r5900|ps2|playstation|emotion engine|mips64|ee_core`, case-insensitive, excluding `artifacts/` and `.git/`) matches **only `AGENTS.md` itself**.

Finding: **this repository contains no PS2/R5900 implementation.** The established guest paths are:

1. RV32I synthetic E07 fixture (`checksum=122010428`, `return a0=48`, `operations=3866`) — classified PROVEN;
2. bounded MIPS32 vertical slice + five Expansion V1 fixtures — classified PASS/bounded.

MIPS32 is the ISA family R5900 belongs to, so the "preserve R5900" obligation is interpreted here as:
**preserve the existing RV32I/E07 and MIPS32 evidence paths byte-for-byte in observable results**, and never weaken their gates.
All later stages must keep those published numbers unchanged. No R5900-specific claim may be made from Phase-1 work.

## Baseline defect found and repaired

`tools/wasm_run.js` was **empty at HEAD**.

Evidence:

- `git show 2edb212 --raw -- tools/wasm_run.js` → `:100644 100644 4daa8e8 e69de29 M tools/wasm_run.js`
  (`e69de29` is the empty blob). The published 6-line runner was deleted by commit `2edb212`
  ("mips32: correct and independently verify first translation proof"), which is unrelated to the WebAssembly runner.
- The same commit regenerated `SOURCE_SHA256SUMS.txt`, so the integrity manifest recorded the *empty* file's hash
  (`e3b0c442…b855`) and `RUN.sh` step `[0/10] sha256sum -c` could no longer detect the truncation.
- Consequence: `RUN.sh` step `[7/10]` could not pass — `WASM_CHECKSUM` would be empty and the runner would exit 0
  without printing it, producing `FAIL: host checksum mismatch native=122010428 wasm=`.
- The later commit `bd5f02f` restored the three Python files that `2edb212` had also created empty
  (`tools/mips32_oracle_v1.py`, `tools/test_mips32_causality_v1.py`, `tools/test_mips32_equivalence_v1.py`)
  but did **not** restore `tools/wasm_run.js`.

Repair (non-destructive, restores a published file, weakens nothing):

1. `tools/wasm_run.js` restored byte-for-byte from `da0b535:tools/wasm_run.js`.
   `git hash-object tools/wasm_run.js` = `4daa8e88316f73c311096a2fd8a76e4d0da72ffe`, i.e. identical to the pre-`2edb212` blob.
2. `SOURCE_SHA256SUMS.txt` regenerated with the repository's own `update_sums.py`.
   The diff is exactly one line: the empty-file hash for `tools/wasm_run.js` replaced by
   `b973c3c52712937d59a15f2e50c405830be9882b5c457c05b1248b12405613ca`. Entry count stays 65 (+1 new tool = 66).

Verification of the repair:

| Check | Command | Result |
| --- | --- | --- |
| blob identity | `git hash-object tools/wasm_run.js` | `4daa8e8…` == historical published blob → PASS |
| syntax | `node --check tools/wasm_run.js` | exit 0 → PASS |
| functional | synthetic 47-byte hand-assembled WebAssembly module exporting `run_fixture` returning `122010428`, run through `node tools/wasm_run.js` | stdout `WASM_CHECKSUM=122010428`, rc 0 → PASS |
| regression guard | new built-in gate `wasm-runner-intact` in `tools/phase1_host_gates_v1.py` | PASS (non-empty, keeps `run_fixture` + `WASM_CHECKSUM=`, LF endings) |

The functional probe used a module written by the harness author from the WebAssembly binary encoding
(no compiler needed), so it is synthetic/original input and adds no third-party asset.

## Deterministic verification inventory

Canonical machine-readable inventory: `host_gates_run1.json` (key `inventory`), produced by:

```powershell
python tools/phase1_host_gates_v1.py --json .openrecomp-phase1/evidence/P1-00/host_gates_run1.json
```

### Runnable on this host (all PASS)

| Gate id | Command | Marker |
| --- | --- | --- |
| source-integrity | built-in: verifies all `SOURCE_SHA256SUMS.txt` entries | `verified 66 manifest entries` |
| wasm-runner-intact | built-in: guards the restored runner | `sha256=b973c3c5…` |
| ir-v1-spec | `python tools/test_ir_v1.py` | `OPENRECOMP_IR_V1_SPEC=PASS` |
| ir-v1-minimal-example | `python tools/validate_ir_v1.py examples/ir-v1/minimal.json` | `OPENRECOMP_IR_V1_VALID=PASS` |
| core-api-v1 | `python tools/test_core_api_v1.py` | `OPENRECOMP_CORE_API_V1_TESTS=PASS` |
| adapter-seam | `python tools/check_adapter_seam.py` | `PASS: shared adapter interface is real` |
| mips32-frontend-v1 | `python tools/test_mips32_frontend_v1.py` | `OPENRECOMP_MIPS32_FRONTEND_V1_TESTS=PASS` |
| mips32-expansion-v1-negative | `python tools/test_mips32_expansion_v1.py` | `OPENRECOMP_MIPS32_EXPANSION_NEGATIVE_TESTS=PASS` |
| mips32-microtests-v1 | `python tools/test_mips32_microtests_v1.py` | `0 failed` (10 passed) |
| mips32-causality-v1 | `python tools/test_mips32_causality_v1.py` | `CAUSALITY_PASS` |
| mips32-equivalence-v1 | `python tools/test_mips32_equivalence_v1.py` | `EQUIVALENCE_PASS` |
| public-safety-scan | `python tools/public_safety_scan.py` | `OPENRECOMP_PUBLIC_SAFETY=PASS` |
| public-safety-missing-file-test | `python tools/test_public_safety_scan.py` | `OPENRECOMP_PUBLIC_SAFETY_MISSING_FILE_TEST=PASS` |
| doc-links | `python tools/check_markdown_links.py` | `OPENRECOMP_DOC_LINKS=PASS` |
| release-metadata-tests | `python tools/test_release_metadata.py` | `OPENRECOMP_RELEASE_AUTOMATION_V1_TESTS=PASS` |
| release-v0_2_0-metadata | `python tools/verify_release_v0_2_0.py` | `OPENRECOMP_V0_2_RELEASE_METADATA=PASS` |

Gates are executed with `cwd=<repo root>` and `PYTHONPATH=<repo root>`, matching `RUN.sh`/`EXTERNAL_REPRO_V1.sh`.

### Toolchain-gated on this host (explicitly SKIPPED, never counted as PASS)

| Gate id | Command | Missing |
| --- | --- | --- |
| e07-hardened-end-to-end | `bash RUN.sh` | `clang`, `gcc` (also needs the RV32I/wasm32 clang targets) |
| external-repro-v1 | `bash EXTERNAL_REPRO_V1.sh` | `clang`, `gcc`, POSIX reviewer environment (Ubuntu 24.04 reference) |

Consequence for Phase 1: the native/WebAssembly parity legs of the RV32I and MIPS32 AOT evidence
**cannot be re-executed on this machine**. They remain valid as previously published CI/local evidence, and every
Phase-1 stage must therefore prove new architectures through the host-runnable layers
(decoder → IR V1 validation → Module Image V1 → Core API V1 `ReferenceExecutor`), plus MSVC-compiled native
AOT where a C compiler is reachable.

### Host toolchain actually present

| Component | Value |
| --- | --- |
| OS / shell | win32, Windows PowerShell 5.1 |
| Python | 3.14.6 (`C:\Python314\python.exe`) |
| jsonschema | 4.26.0 (matches the reference reviewer environment) |
| setuptools | 83.0.0 (provides `setuptools._distutils`, used by existing gates) |
| Node.js | v22.23.2 |
| Git | 2.55.0.windows.3 |
| bash | `C:\Users\Shadow\AppData\Local\Microsoft\WindowsApps\bash.exe` (present, but `RUN.sh` still needs clang/gcc) |
| C compiler | `cl`/`clang-cl`/`clang`/`gcc` **not on PATH**; MSVC Build Tools 18 (`VC\Tools\MSVC` 14.44.35207 and 14.51.36231) **are reachable through `setuptools._distutils`**, which is how `mips32-causality-v1` and `mips32-equivalence-v1` compile and pass here |
| clang / gcc | MISSING |

## Determinism evidence

Two consecutive harness runs on the same tree:

```text
host_gates_run1.json sha256 = 09AEE72151E3006C670502982FB97918C4D9CAC76D2B0982C0983908C61457A5
host_gates_run2.json sha256 = 09AEE72151E3006C670502982FB97918C4D9CAC76D2B0982C0983908C61457A5
DETERMINISTIC_JSON = PASS
DETERMINISTIC_STDOUT (ignoring the line that echoes the caller-supplied --json filename) = PASS
```

The harness emits no timestamps and no absolute paths; keys are sorted.

Final harness summary (both runs):

```text
OPENRECOMP_PHASE1_HOST_GATES_PASS=16 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
```

## Files changed in this stage

| File | Change |
| --- | --- |
| `tools/wasm_run.js` | restored byte-identical to published blob `4daa8e8` (was empty at HEAD) |
| `SOURCE_SHA256SUMS.txt` | regenerated via `update_sums.py`; adds the new tool and the restored runner hash |
| `tools/phase1_host_gates_v1.py` | new: deterministic host-gate runner + verification inventory (this stage's harness) |
| `.openrecomp-phase1/evidence/P1-00/*` | new evidence: `RESULT.md`, `host_gates_run1.json`, `host_gates_run1.txt`, `host_gates_run2.json`, `host_gates_run2.txt` |
| `.openrecomp-phase1/STATE.md` | stage status update |

## Semantic assumptions

None about CPU behaviour. This stage made no architectural/semantic decision; the only judgement calls were
procedural:

1. "Preserve PS2/R5900" is interpreted as preserving the repository's actual established RV32I/E07 + MIPS32 paths,
   because no R5900 code exists (search evidence above).
2. Restoring an accidentally truncated tracked file from its own published history is a repair, not a test weakening:
   it re-enables a gate that had been silently disabled.

## Remaining limitations / carry-forward findings

1. `clang` and `gcc` are absent, so `RUN.sh` and `EXTERNAL_REPRO_V1.sh` cannot be executed here. The RV32I
   native/WebAssembly parity leg is not re-provable on this host; the restored runner is proven functional by the
   synthetic module probe and by blob identity instead.
2. Python here is 3.14.6 while the reference reviewer environment is 3.12. All host-runnable gates pass on 3.14.6,
   but Python-version parity with CI is not proven locally.
3. Committed Windows build residue exists in the tracked tree under
   `artifacts/mips32_translation_correction_v1/**` (`.obj`, `.exe`, and directories literally named
   `OpenRecomp/openrecomp-e07/scratch/harness.obj`). `public_safety_scan.py` only inspects text suffixes, so these
   pass silently. Removing tracked history content is destructive and out of scope; recorded for the operator.
4. Root-level untracked build leftovers (`generated.win.obj`, `mips32.a.*`, `mips32.abi.a.obj`) are not covered by
   `.gitignore`. Left in place (deleting user files is not permitted here); recommend adding ignore rules separately.
5. `.openrecomp-phase1/ROM_PATHS.md` and `CONTROL_POLICY.md` still contain the literal, unsubstituted token
   `$RomRoot`. The effective ROM root is only resolvable from `ROM_INVENTORY.json`
   (`D:\OpenRecomp\roms\phase1`). Must be reconciled before any cartridge/platform stage (P1-14 and later).
6. `ROM_INVENTORY.json` lists commercial cartridge images (GB/GBC/SMS/NES). Per policy they stay outside the
   repository; Phase-1 CPU/platform semantics must be proven with synthetic fixtures first
   (`ROM_PATHS.md` rule 7), and no ROM byte may be copied into the tree.

## Verdict

`PASS` — baseline is healthy and reproducible on this host after repairing the truncated WebAssembly runner;
16 gates PASS, 0 FAIL, 2 explicitly SKIPPED for missing `clang`/`gcc`/POSIX.
