# External Reproducibility V1

`OPENRECOMP_EXTERNAL_REPRO_V1` is a bounded, Linux-first reviewer path for reproducing the most important open-core evidence from a clean checkout without Unreal Engine, proprietary SDKs, commercial binaries, firmware, keys or local hand-curated state.

It is intentionally narrower than the complete GitHub Actions matrix. The purpose is to give an external reviewer one stable proof command and one deterministic machine-readable result rather than asking them to reconstruct many workflow steps by hand.

## Supported reviewer environment

The V1 reference environment is Linux x86-64. Hosted CI uses Ubuntu 24.04 with:

- Python 3.12;
- `jsonschema` 4.26.0;
- Node.js 22;
- Clang/LLVM + LLD with RV32I and WebAssembly target support;
- GCC;
- Bash, Git, `sha256sum` and `cmp`.

The proof command does not install system packages or modify tracked repository files. Missing prerequisites fail closed with a concise diagnostic.

## One proof command

From a clean checkout at the commit to be reviewed:

```bash
bash EXTERNAL_REPRO_V1.sh
```

A successful run ends with:

```text
OPENRECOMP_EXTERNAL_REPRO_V1=PASS
```

and writes the bounded reviewer result to:

```text
evidence/external-repro-v1/RESULT.json
evidence/external-repro-v1/RESULT.sha256
evidence/external-repro-v1/RESULT.md
```

`RESULT.json` is the semantic evidence record. It includes the exact source commit, the digest of `SOURCE_SHA256SUMS.txt`, the established RV32I and MIPS32 results, frozen-contract classifications, the included/excluded scope and the public-safety result. `RESULT.sha256` authenticates that JSON record.

`ENVIRONMENT.txt` records tool versions for diagnostic provenance. It is deliberately not part of the deterministic semantic-result comparison because compiler/package patch versions may differ between otherwise-valid reviewer machines.

## What V1 reproduces

The gate executes and cross-checks:

- the hardened E07 synthetic RV32I proof, including source-integrity validation, native/WebAssembly parity and adversarial rejection;
- RV32I normalization to IR V1, Module Image V1 and Core API V1;
- RV32I portable-C Native AOT modules under both GCC and Clang;
- the bounded MIPS32 vertical slice through the same IR/Module/Core/AOT boundary;
- all five MIPS32 Expansion V1 synthetic fixtures through an independent machine-code reference, Core API and GCC/Clang Native AOT paths;
- deterministic code/module generation where the existing contracts require it;
- Native AOT ABI V1 loading for the included Linux modules;
- the tracked-file public-safety scan;
- absence of tracked-tree mutation by the reviewer gate itself.

The established bounded semantic results remain:

```text
RV32I E07             checksum=122010428   a0=48   operations=3866
MIPS32 vertical slice checksum=1950232098  v0=31   operations=100

logic-shift           checksum=435263539   operations=72  delay_slots=1
memory-width          checksum=4257846410  operations=60  delay_slots=1
branches-calls        checksum=2065440492  operations=75  delay_slots=9
mult-hilo             checksum=768371589   operations=44  delay_slots=1
big-endian-memory     checksum=938211822   operations=24  delay_slots=1
```

## Determinism model

Hosted CI runs the full reviewer command twice from regenerated `build/` and `evidence/` state on the same source commit. The two `RESULT.json` files and their SHA-256 records must be byte-identical.

This is a semantic reproducibility claim, not a claim that compiler-produced native binaries are byte-identical across unrelated compiler versions or operating systems. Environment/tool versions are therefore recorded separately from the deterministic result.

## Explicit exclusions

External Reproducibility V1 does **not** establish:

- Unreal Engine runtime or packaged-build execution;
- Windows compiler/runtime parity;
- macOS, Windows ARM64, Windows x86 or other host parity;
- Unreal Shipping configuration parity;
- arbitrary RV32I or MIPS32 executable support;
- general console compatibility;
- production-quality optimizing-compiler status.

Those remain separate evidence gates and must not be inferred from this reviewer path.

## Hosted CI

`.github/workflows/external-repro-v1.yml` recreates the bounded reviewer environment, runs the one-command gate twice, verifies the deterministic result and uploads only the public-safe reviewer evidence.
