# OpenRecomp IR V1.1 integer division/remainder semantics

Status: **FROZEN-FOR-IMPLEMENTATION — supported additive feature**

This document defines the additive `integer-divrem-v1` feature for normalized IR wire version `1.1.0`. Frozen IR V1.0 remains unchanged and continues to reject unknown versions/features rather than guessing.

IR V1.1 is the supported architecture-neutral contract for future guest `div`/`divu` lowering where the guest behavior is defined and can be represented without overclaiming architecture-specific edge cases.

## Portable operations

IR V1.1 adds four `binop.kind` values: `udiv`, `urem`, `sdiv`, and `srem`. Operands and result have the same fixed-width integer type. Modules using any of these operations must include `integer-divrem-v1` in `required_features`.

## Exact total semantics

All arithmetic is performed at the declared integer width. Unsigned division and remainder use the ordinary quotient/remainder for non-zero divisors. Signed division truncates toward zero. Signed remainder is `dividend - quotient * divisor`.

The portable IR deliberately defines deterministic edge results:

| case | quotient | remainder |
| --- | --- | --- |
| divisor = 0 | all-ones bit pattern | dividend bit pattern |
| signed MIN / -1 | signed MIN bit pattern | 0 |

These edge results follow the RISC-V M-extension integer model and avoid host-language undefined behavior in generated C.

## MIPS32 bounded lowering

MIPS32 `div`/`divu` write quotient to LO and remainder to HI. The first MIPS32 proof is intentionally narrower than the portable IR contract: only a rights-safe synthetic little-endian fixture is claimed; executed divisors are non-zero; signed MIN / -1 is excluded; divide-by-zero and signed-overflow MIPS32 behavior are not claimed.

The independent MIPS32 reference rejects those edge inputs for this bounded profile rather than borrowing the IR's deterministic edge policy and misrepresenting it as MIPS behavior.

Future MIPS32 expansion should use this V1.1 feature instead of adding a MIPS-specific division primitive or silently changing frozen IR V1.0. Existing MIPS32 Expansion V1 remains frozen and may continue to reject `div/divu`; broader support should be introduced through a separately evidence-gated profile or real-ELF frontend revision.

## Compatibility

The checked-in `1.0.0` schema, validator, Core executor and portable-C backend files are not modified by this frontier. V1.1 tooling derives the additive schema delta, reuses the frozen V1 semantic/type validator through a semantics-preserving surrogate for the four new same-typed binops, and supplies separate V1.1 Core/AOT adapters. A V1.0 consumer therefore continues to reject V1.1 modules fail-closed.

## Promotion evidence

The feature was promoted only after PR #27 merged and the complete push-triggered OpenRecomp workflow matrix reproduced on merged `main` commit:

`1175923d4d69d973a4c9239c101bb5ed54b419dd`

The merged-main matrix completed **17/17 workflows successfully**. The dedicated `IR V1.1 divrem semantics V1` run was `33743580855` and reproduced:

- frozen IR V1 and MIPS32 regression behavior unchanged;
- 10/10 direct V1.1 div/rem edge-semantic tests;
- 3/3 fail-closed feature/validation tests;
- deterministic MIPS32 frontend and Module Image generation;
- independent defined-domain MIPS32 reference agreement with Core V1.1;
- GCC and Clang Native AOT agreement;
- checksum `2168317302`;
- Core/AOT operation count `44`.

Merged-main evidence artifact:

- artifact ID: `9888711615`
- SHA-256: `6c51688ddf244e0ce6c0ec9ddf1e0f11dc9969d2713280ab740540ac85b9d005`

## Evidence boundary

The supported contract claim is architecture-neutral and bounded to the implemented V1.1 feature semantics and evidence paths. It does **not** claim that MIPS32 divide-by-zero or signed-overflow behavior is deterministic, does not promote arbitrary MIPS32 ISA coverage, and does not change the frozen IR V1.0 contract.
