# OpenRecomp v0.2.0

**Release type:** public research/developer milestone  
**Release date:** 2026-09-01  
**Version:** `0.2.0`

OpenRecomp v0.2.0 freezes the first reviewer-oriented public milestone of the architecture-neutral recompilation pipeline. It is intentionally a bounded evidence release rather than a claim of general binary compatibility or a production-quality optimizing compiler.

## What this release establishes

The release includes the hardened E07 RV32I proof, normalized IR V1, Module Image V1, Core API V1, a bounded MIPS32 second-guest vertical slice, the common portable-C AOT backend, compiler/fault/sanitizer hardening, Native AOT ABI V1, Windows x64 portability, and an optional Unreal host integration.

Evidence provenance is explicit:

| Area | v0.2.0 status |
| --- | --- |
| E07 RV32I synthetic fixture | **PROVEN** — fresh-clone hardened proof |
| Native / WebAssembly equivalence | **PASS** |
| Normalized IR V1 | **FROZEN-FOR-IMPLEMENTATION** |
| RV32I -> IR V1 bridge | **PASS** — checksum `122010428` |
| Module Image / Core API V1 | **PASS** — checksum `122010428`, `a0=48`, 3,866 operations |
| MIPS32 synthetic vertical slice | **PASS** — checksum `1950232098`, `v0=31`, 100 operations, 7 delay slots lowered |
| Portable C AOT backend | **PASS** — bounded RV32I + MIPS32 equivalence |
| AOT hardening | **PASS** — `-Werror`, 9 fault-equivalence classes, GCC/Clang ASan+UBSan smoke |
| Native AOT ABI V1 | **FROZEN-FOR-PORTABILITY-TESTING** |
| Linux + Windows x64 Native AOT | **PASS** — GCC/Clang/MSVC/clang-cl bounded fixtures |
| Unreal Native AOT host core | **PASS** — reproducible Windows compiler/module CI matrix |
| UE5.8 Native AOT PIE | **PASS — local runtime evidence** — bounded synthetic RV32I module |
| General MIPS32 support | **CANDIDATE** |
| macOS / Windows ARM64 / Windows x86 ABI parity | **CANDIDATE** |
| Release-quality production compiler/plugin pipeline | **CANDIDATE** |

See [`PROOF_STATUS.md`](PROOF_STATUS.md) for the full definitions and claim boundaries.

## Reproduce the core proof

From a fresh clone of the release tag:

```bash
./RUN.sh
```

The hardened E07 proof must finish with:

```text
PASS: E07 V1.1 HARDENED END-TO-END
```

The dedicated GitHub Actions workflows additionally validate IR V1, Core API V1, MIPS32, portable-C AOT translation, AOT hardening, Windows portability, the engine-independent Unreal Native AOT host core, public safety and documentation links.

For release metadata consistency, run:

```bash
python3 tools/verify_release_v0_2_0.py
```

Expected marker:

```text
OPENRECOMP_V0_2_RELEASE_METADATA=PASS
```

## Key deterministic results

RV32I / E07:

```text
checksum   = 122010428
return a0  = 48
operations = 3866
```

MIPS32 vertical slice:

```text
checksum   = 1950232098
return v0  = 31
operations = 100
delay slots lowered = 7
```

The current Windows x64 AOT proof reproduces those established Core/Linux reference results under both MSVC and clang-cl.

## Public native-module boundary

Native AOT ABI V1 is the first frozen host-facing binary contract. Finished proof modules expose the versioned discovery symbol:

```text
openrecomp_native_aot_query
```

The V1 binary layout is frozen for portability testing. Incompatible layout or signature changes require a new ABI version rather than silently changing V1.

## Unreal evidence boundary

Unreal Engine is an optional host integration and is not required by the OpenRecomp core.

The engine-independent Native AOT host core is reproducible in Windows CI. A separate UE5.8 Windows x64 PIE run loaded the synthetic RV32I AOT DLL through Native AOT ABI V1 and reproduced observed state `48`, checksum `122010428` and `3866` operations. Because hosted project CI does not contain UE5.8, that result is deliberately labelled **PASS — local runtime evidence** rather than an unqualified reproducible runtime proof.

## Development and rights provenance

OpenRecomp uses a human-led process that may include material automated and AI-assisted development/review. Generated output is not accepted as evidence by itself; status claims require executable tests, runtime evidence or explicit review. See [`../DEVELOPMENT_PROCESS.md`](../DEVELOPMENT_PROCESS.md).

Public fixtures are original synthetic, homebrew or otherwise clearly redistributable. This release does not contain commercial game binaries/assets, console firmware/keys, proprietary SDK content, authentication logs or proprietary console executables.

## Not claimed by v0.2.0

This release does not establish arbitrary RV32I binaries, full MIPS32 ISA/ABI support, general console compatibility, macOS or non-x64 Windows Native AOT portability, packaged Unreal deployment, arbitrary optimization correctness, or a release-quality production compiler/plugin pipeline.

## Release artifact policy

The authoritative release is the tagged source tree plus GitHub-hosted workflow evidence. Generated native binaries are test artifacts, not universal redistributable OpenRecomp binaries. Reviewers should rebuild from the tagged source and compare observable results rather than expecting compiler-produced binaries to be byte-identical across toolchains.
