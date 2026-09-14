# P2-09 — Deterministic build pipeline V1

VERDICT: `PASS`

STAGE MARKER: `OPENRECOMP_P2_09=PASS`
GATE MARKER: `OPENRECOMP_DETERMINISTIC_BUILD_V1=PASS tests=120`

## Baseline

| Item | Value |
| --- | --- |
| Stage | `OPENRECOMP_P2_09_DETERMINISTIC_BUILD_PIPELINE_V1` |
| Branch | `phase2/opencode-v1` |
| Starting commit | `10971b76090746081cb29ca3405f96da7f143011` (`10971b7 phase2: complete P2-08 generic runtime ABI v1`; `HEAD` at stage start) |
| Phase-1 freeze | tag `openrecomp-phase1-pass` -> `46c2f971e1a42cf49bd936bad94697b81bf31002` (verified unchanged) |
| Prior gates | P2-08 `169`, P2-07 `106`, P2-06 `134`, P2-05 `104`, P2-04 `61`, P2-03 `67`, P2-02 `82`, P2-01 `49` |

## Objective

Implement and validate a deterministic build pipeline that turns P2-07/P2-08
generated host source plus the bounded Generic Runtime ABI into reproducible
native build artifacts with explicit provenance: generated source SHA-256 ->
deterministic build manifest -> compiler invocation -> object -> link ->
executable -> artifact hashes -> reproducibility classification. P2-09 is a
reproducibility/build-evidence stage. It is **not** the end-to-end guest
equivalence stage and does not implement P2-10.

## Files added

| File | Role |
| --- | --- |
| `openrecomp/build_pipeline.py` | Neutral P2-09 pipeline: `BuildPipeline` concepts `BuildConfig`, `BuildSource`, `BuildInput`, `BuildArtifact`, `BuildArtifactKind`, `BuildToolchain`, `ToolchainIdentity`, `BuildManifest`, `BuildRun`, `BuildComparison`, `BuildReproducibility`, `BuildStatus`, `BuildError`; entry points `build_generated_host`, `build_generated_host_from`, `discover_toolchain`, `compare_runs`, `verify_artifact_hashes`. |
| `tools/test_build_pipeline_v1.py` | Deterministic 120-check gate with optional `--json`, `--manifest-out` and output-only `--evidence-dir`. |
| `.openrecomp-phase2/evidence/P2-09/*` | This evidence bundle (manifest, run reports, hashes, PE/COFF inspection, regressions). |

## Files modified

| File | Change |
| --- | --- |
| `SOURCE_SHA256SUMS.txt` | Registered `tools/test_build_pipeline_v1.py` via `update_sums.py` (118 -> 119 entries). Exactly one added line; no existing hash changed. |
| `.openrecomp-phase2/STATE.md`, `HANDOFF.md` | Stage transition (P2-09 PASS -> P2-10). |
| `.openrecomp-phase2/STAGE_QUEUE.md` | Control-plane status only: P2-09 `COMPLETE`, P2-10 `NEXT`. |

No P2-00..P2-08 implementation source was modified. No prior test was weakened.

## Build manifest

- schema: `openrecomp-build-manifest-v1`, manifest version `1.0.0`,
  pipeline version `1.0.0`, stage `P2-09`.
- Records: source fixture identity; generated-source and support-source names +
  SHA-256; runtime ABI name/version; compiler identity/version/target; linker
  identity/version/target; exact ordered compile commands; exact link command;
  canonical ordered inputs/outputs; object and executable SHA-256; build status;
  reproducibility classification; deterministic config.
- Canonical serialization (sorted keys, fixed separators) and SHA-256
  fingerprint. The validator rejects unknown keys, missing keys, forbidden
  nondeterministic fields (timestamp/pid/uuid/hostname/username/path/cwd/temp/
  mtime/object-id), unsafe names, missing/duplicate names and ABI mismatches.
- The manifest contains no wall-clock timestamp, temporary directory, evidence
  directory, repository path, username, hostname, process id, random UUID or
  Python object identity.

## Toolchain (detected, never assumed)

| Item | Value |
| --- | --- |
| Compiler | `clang-cl.exe`, `clang version 22.1.8 (https://github.com/llvm/llvm-project ca7933e47d3a3451d81e72ac174dcb5aa28b59d1)` |
| Compiler target | `x86_64-pc-windows-msvc` |
| Linker | `lld-link.exe`, `LLD 22.1.8 (https://github.com/llvm/llvm-project ca7933e47d3a3451d81e72ac174dcb5aa28b59d1)` |
| Compile flags | `/c /Brepro /Od /std:c11 /nologo` |
| Link flags | `/Brepro /nologo` |

`/Brepro` is passed **directly** to the compiler and linker. No binary
post-processing, no manual COFF timestamp editing and no post-link normalization
is performed. If no supported toolchain were present the pipeline would still
produce deterministic source/manifest evidence and classify the result
`TOOLCHAIN_UNAVAILABLE`; that path is tested.

## Independent build runs

- Two builds are performed in isolated, distinct directories (`run1`, `run2`).
- Generated source is regenerated for every run by the emitter callable; the
  artifacts are never copied between runs.
- A cross-root check additionally builds under two different absolute roots and
  confirms identical hashes.

## Reproducibility results

```text
source reproducible:     IDENTICAL
manifest reproducible:   IDENTICAL
object reproducible:     IDENTICAL
executable reproducible: IDENTICAL
classification:          EXECUTABLE_REPRODUCIBLE
```

Exact SHA-256 values (identical in both independent runs):

| Artifact | SHA-256 |
| --- | --- |
| `generated.c` | `b75d7656517de8a75c5730fa22b7ea69dff9292be20a6f73d0bd49cf64705e24` |
| `runtime_support.c` | `df4ab710fb2705bd26d3e021b6e706acbbcd4dd61a62926b057737a43b1bcb02` |
| `generated.obj` | `fc4524095d8ce2196cf3e67e8d4c53cfc63cefc2cd5fe59cf9592ceb227b5764` |
| `runtime_support.obj` | `51910f332e91f26492a61b9168a3ce7566667b13c9de6da7157b021a83d153d8` |
| `program.exe` | `de03764e429a6e31d46037c72cd08db126fab18f2838b037b8ecee7deea81368` |

## PE/COFF inspection (actual inspected bytes)

`llvm-readobj --file-headers` (binaries not modified):

| Artifact | Run 1 `TimeDateStamp` | Run 2 `TimeDateStamp` | Identical |
| --- | --- | --- | --- |
| `generated.obj` | `0x0` | `0x0` | yes |
| `runtime_support.obj` | `0x0` | `0x0` | yes |
| `program.exe` | `0x974E5A9` | `0x974E5A9` | yes |

Other checked fields are identical across runs: `COFF-x86-64`,
`IMAGE_FILE_MACHINE_AMD64 (0x8664)`, `ImageBase 0x140000000`. The object
timestamp is zeroed by `clang-cl /Brepro`; the executable timestamp is the
deterministic value produced by `lld-link /Brepro` (not zero, but byte-identical
across independent runs). No timestamp was manually zeroed.

## Execution smoke test

Bounded synthetic build/execution smoke test only — **not** guest/host
equivalence.

```text
expected observable: 42 0
run 1 observed: 42 0 returncode=0 PASS
run 2 observed: 42 0 returncode=0 PASS
result: PASS
```

## Tests / coverage

```text
python tools/test_build_pipeline_v1.py
OPENRECOMP_DETERMINISTIC_BUILD_V1=PASS tests=120
```

Coverage includes: toolchain identity/version/target and explicit flags;
unsupported-compiler fail-closed; independent directories and source
regeneration; build status and reproducibility booleans; canonical manifest
serialization, sorted keys, schema/version/stage; ordered inputs/outputs; exact
compile/link commands; no forbidden fields; no repository/build-root/username/
hostname/drive-letter/Python-identity leakage; manifest round-trip; artifact
hash verification; smoke test; cross-root identity; PE/COFF timestamp
inspection; binary leakage; **evidence-path independence** (two evidence roots,
corresponding-file byte identity, manifest identity, text encoding, path
non-leakage, and unchanged source/object/executable hashes, classification, ABI
version, toolchain and arguments); and fail-closed paths: ABI mismatch,
configuration contradictions, bad source hash, source hash mismatch, malformed
manifest (forbidden field, missing key, unknown key, ABI mismatch, invalid
JSON), duplicate output, unsafe/absolute source names, failed compilation,
over-strong reproducibility claim, single-run comparison, artifact
present-without-hash, and evidence destination colliding with a file.

### Evidence-path independence tests (new)

`evidence-file-set-complete`, `evidence-file-set-identical`,
`evidence-cross-directory-identity`, `evidence-manifest-identical`,
`evidence-manifest-matches-gate`, `evidence-run-reports-distinct`,
`evidence-text-utf8-clean`, `evidence-no-output-root-leak`,
`evidence-no-repo-path-leak`, `evidence-no-temp-root-leak`,
`evidence-no-username-leak`, `evidence-no-hostname-leak`,
`evidence-manifest-semantics-unchanged`, `evidence-artifact-hashes-unchanged`,
`evidence-input-hashes-unchanged`, `evidence-classification-unchanged`,
`evidence-abi-version-unchanged`, `evidence-compiler-unchanged`,
`evidence-linker-unchanged`, `evidence-compile-args-unchanged`,
`evidence-link-args-unchanged`, `reject:evidence-destination-is-file`.

## Determinism

- Normal gate stdout, two consecutive runs, byte-identical:
  `sha256 db055b5cd622a7ef188901ef8da65898e2dac0cacb03c0ee2fb6caeec5b3e273`.
- Two independently generated evidence sets in different absolute roots are
  byte-identical file-for-file (`P2_09_EVIDENCE_CROSS_DIRECTORY=PASS`).
- `build_manifest.json` is byte-identical across roots
  (`22d8fd9bac9bca61c8f2920b6274a6076a518e59082e5f7965cee1dad348df77`);
  `P2_09_MANIFEST_CROSS_DIRECTORY=PASS`.

## Text encoding

All P2-09 evidence is valid UTF-8 without UTF-8/UTF-16 BOM and without NUL
bytes: `P2_09_TEXT_ENCODING=PASS`. Evidence was generated by Python UTF-8 byte
writes and captured via Python `subprocess` (never PowerShell `>` redirects).

## Path / identity leakage

`P2_09_PATH_LEAKAGE=PASS`. Checked: generated source, canonical manifest, all
evidence text, and object/executable raw bytes (plus `llvm-strings` in the gate)
against the evidence roots, build roots, repository path, username and
hostname. Absence from strings is bounded evidence, not a universal proof.

## Upstream regression totals

```text
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
PASS source-integrity  verified 119 manifest entries
```

The two toolchain-gated Phase-1 gates (`e07-hardened-end-to-end`,
`external-repro-v1`) remain unexecutable on this host and are never counted as
pass.

## Source integrity

`SOURCE_SHA256SUMS.txt` 118 -> 119 entries via `update_sums.py`; the single
added entry is `tools/test_build_pipeline_v1.py`
(`e6e5f258fd89024ec1338476c8a6b9964e3817df749ec9bb1e00539de0e2c5ae`). No
existing hash changed. `openrecomp/build_pipeline.py` remains outside the
manifest under the pre-existing `update_sums.py` glob gap; its hash
(`1e7181ac42fabb0642f845d8070b7699ea2825452e652144c402176ef15fdfc7`) is
recorded here and in `changed_files.txt`.

## Known limitations

- The build pipeline builds a bounded synthetic generated host fixture plus a
  synthetic runtime-support source; it is not an end-to-end guest
  recompilation.
- Object/executable reproducibility is demonstrated on this host's
  clang-cl/lld-link pair. Other toolchains may require different deterministic
  flags and are classified honestly (no stronger claim than evidence).
- The smoke test executes one synthetic host-call result; it is not
  guest/host equivalence.
- `openrecomp/*.py` remain outside `SOURCE_SHA256SUMS.txt` (pre-existing
  `update_sums.py` glob gap).
- Toolchain-gated Phase-1 gates remain skipped on this host.

## Explicit non-claims

P2-09 does not claim full MIPS32 recompilation, IR lowering, guest/host
equivalence, console compatibility, AOT integration, whole-game recompilation or
RT64 integration. P2-10 (Tiny MIPS32 end-to-end proof) was **not** started. The
final `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS` marker is not claimed and
remains `NOT_PROVEN`.

## Boundary rule

No P2-09 git commit was created. The coherent P2-09 changes are left in the
working tree for independent review and boundary commit.

## Final verdict

`PASS` — the deterministic build pipeline produces canonical build manifests
with explicit provenance, performs two genuinely independent isolated builds
that regenerate the source, uses `clang-cl`/`lld-link` `/Brepro` directly with
no binary post-processing, and observes byte-identical source, object and
executable hashes with an honest `EXECUTABLE_REPRODUCIBLE` classification; all
text evidence is UTF-8; no path/identity leakage was found; and all mandatory
upstream regressions and source integrity pass.

OPENRECOMP_P2_09=PASS
OPENRECOMP_DETERMINISTIC_BUILD_V1=PASS tests=120
