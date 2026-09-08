# OpenRecomp Public Credibility & Evidence Pack V1

**Project:** OpenRecomp  
**Maintainer:** Fred Day (`fredlday-oss`)  
**Repository:** https://github.com/fredlday-oss/openrecomp-e07  
**Public milestone:** v0.2.0  
**Purpose:** give an external reviewer a short, verifiable route from project identity to scope, evidence, reproduction and limitations.

## What OpenRecomp is

OpenRecomp is an open-source, architecture-neutral static recompilation framework with deterministic validation and explicit host interfaces. It separates binary analysis, normalized/versioned IR, module packaging, reference execution, ahead-of-time translation and host integration.

The project is research/developer infrastructure. It is **not** presented as a production compiler, a general console emulator, or proof of arbitrary commercial-game compatibility.

## Maintainer and development record

OpenRecomp is currently maintained by Fred Day through the public GitHub account `fredlday-oss`. Repository history, commits, pull requests, Actions runs and evidence files provide the public development record.

Development is human-led and may use automated or AI-assisted tools. Machine-generated output is never accepted as proof by itself; evidence status is based on executable tests, reproducible results, runtime evidence or explicit review. See [`../DEVELOPMENT_PROCESS.md`](../DEVELOPMENT_PROCESS.md).

## Evidence vocabulary

- **PROVEN** — current evidence directly validates the stated path and is reproducible at the stated project scope.
- **PASS** — a bounded validation/test completed successfully.
- **CANDIDATE** — an implementation/direction exists but has not crossed the required proof gate.
- **PASS — local runtime evidence** — observed locally with recorded provenance, but not independently reproducible in project-controlled hosted CI.

The authoritative definitions and boundaries are in [`PROOF_STATUS.md`](PROOF_STATUS.md).

## Current headline status

| Claim | Current status | Boundary |
| --- | --- | --- |
| E07 RV32I synthetic path | **PROVEN** | Fresh-clone hardened synthetic proof |
| Native / WebAssembly equivalence | **PASS** | E07 bounded evidence |
| Normalized OpenRecomp IR V1 | **FROZEN-FOR-IMPLEMENTATION** | Mechanically validated contract |
| RV32I -> IR V1 bridge | **PASS** | checksum `122010428`, `a0=48` |
| MIPS32 synthetic vertical slice | **PASS** | bounded synthetic subset |
| MIPS32 expanded synthetic suite | **PASS** | five bounded little/big-endian fixtures |
| External Reproducibility V1 | **PASS** | Linux x86-64 clean-reviewer path |
| Native AOT ABI Linux + Windows x64 | **PASS** | bounded fixtures and compiler matrix |
| UE5.8 runtime/package results | **PASS — local runtime evidence** | not hosted-CI Unreal proof |
| General MIPS32 frontend/ISA support | **CANDIDATE** | not full ISA/o32 ABI/arbitrary binaries |
| Release-quality production pipeline | **CANDIDATE** | broader deployment evidence outstanding |

This summary must be read with [`PROOF_STATUS.md`](PROOF_STATUS.md); it is intentionally not a compatibility claim.

## Fastest independent verification

The strongest public reviewer entry point is Linux x86-64. From a clean checkout, with the documented prerequisites installed, run:

```bash
bash EXTERNAL_REPRO_V1.sh
```

Expected marker:

```text
OPENRECOMP_EXTERNAL_REPRO_V1=PASS
```

The command writes `evidence/external-repro-v1/RESULT.json`, `RESULT.sha256` and `RESULT.md`. Hosted CI runs the reviewer command twice at the same source commit and requires byte-identical semantic `RESULT.json` evidence. Full prerequisites, inclusions and exclusions are documented in [`EXTERNAL_REPRO_V1.md`](EXTERNAL_REPRO_V1.md).

For the focused hardened E07 RV32I proof, run `./RUN.sh`. Expected marker:

```text
PASS: E07 V1.1 HARDENED END-TO-END
```

## Concrete bounded results

### RV32I / E07

```text
checksum   = 122010428
return a0  = 48
operations = 3866
```

### MIPS32 vertical slice

```text
checksum   = 1950232098
return v0  = 31
operations = 100
delay slots lowered = 7
```

### MIPS32 Expansion V1

```text
logic-shift        checksum=435263539   operations=72  delay_slots=1
memory-width       checksum=4257846410  operations=60  delay_slots=1
branches-calls     checksum=2065440492  operations=75  delay_slots=9
mult-hilo          checksum=768371589   operations=44  delay_slots=1
big-endian-memory  checksum=938211822   operations=24  delay_slots=1
```

These are synthetic validation fixtures. They do **not** establish arbitrary RV32I/MIPS32 executable or commercial-game support.

## Evidence map

Start here:

1. [`../README.md`](../README.md) — overview, architecture, status and entry points.
2. [`PROOF_STATUS.md`](PROOF_STATUS.md) — authoritative labels and explicit claim boundaries.
3. [`EXTERNAL_REPRO_V1.md`](EXTERNAL_REPRO_V1.md) — one-command independent Linux reproduction path.
4. [`ARCHITECTURE.md`](ARCHITECTURE.md) and [`IR_SPEC_V1.md`](IR_SPEC_V1.md) — architecture and normalized IR contract.
5. [`MIPS32_VERTICAL_SLICE_V1.md`](MIPS32_VERTICAL_SLICE_V1.md) and [`MIPS32_EXPANSION_V1.md`](MIPS32_EXPANSION_V1.md) — bounded MIPS32 evidence.
6. [`NATIVE_AOT_ABI_V1.md`](NATIVE_AOT_ABI_V1.md) — public native-module boundary.
7. [`RELEASE_V0_2_0.md`](RELEASE_V0_2_0.md) — bounded public milestone.
8. [`../DEVELOPMENT_PROCESS.md`](../DEVELOPMENT_PROCESS.md) — human/automation/AI evidence policy.
9. GitHub Actions — public execution history for project-controlled CI gates.

## Rights and preservation boundary

Public tests/examples use original synthetic, homebrew or otherwise clearly redistributable inputs. The repository is designed not to contain commercial game binaries/assets, console BIOS/firmware or keys, proprietary SDK material, authentication logs or proprietary console executable content.

OpenRecomp's preservation relevance is methodological: deterministic binary analysis/translation and reproducible validation may contribute useful techniques to software preservation. That does not grant rights to redistribute third-party software, and preservation applicability must be evaluated separately for each input and rights context.

## Explicit non-claims

OpenRecomp does not currently claim arbitrary RV32I or MIPS32 executable support; complete MIPS32 ISA or o32 ABI coverage; general console or commercial-game compatibility; production-quality optimizing-compiler status; Unreal Engine hosted-CI runtime reproducibility; macOS/Windows ARM64/Windows x86 Native AOT parity; that AI/automated output constitutes technical evidence; or that crowdfunding guarantees any future component will become PROVEN.

## Funding versus existing evidence

Existing PASS/PROVEN results are completed/public evidence and must not be presented as work that still requires funding. Funding is intended for future engineering and evidence closure. General MIPS32 support remains **CANDIDATE** despite the bounded MIPS32 fixture suite passing its defined gates. See [`FUNDING_SCOPE.md`](FUNDING_SCOPE.md).

## Five-minute external-review sequence

1. Read this page and [`PROOF_STATUS.md`](PROOF_STATUS.md).
2. Inspect public GitHub Actions history.
3. Run `bash EXTERNAL_REPRO_V1.sh` on a clean supported Linux environment if independent execution is required.
4. Compare the generated semantic evidence with the documented bounded results.

This route is designed to make OpenRecomp's strongest claims independently checkable while making its limitations equally visible.
