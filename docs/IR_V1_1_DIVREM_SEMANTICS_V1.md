# OpenRecomp IR V1.1 integer division/remainder semantics

Status: **candidate feature gate**

This document defines the additive `integer-divrem-v1` feature for normalized IR wire version `1.1.0`. Frozen IR V1.0 remains unchanged and continues to reject unknown versions/features rather than guessing.

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

## Compatibility

The checked-in `1.0.0` schema, validator, Core executor and portable-C backend files are not modified by this frontier. V1.1 tooling derives the additive schema delta, reuses the frozen V1 semantic/type validator through a semantics-preserving surrogate for the four new same-typed binops, and supplies separate V1.1 Core/AOT adapters. A V1.0 consumer therefore continues to reject V1.1 modules fail-closed.

## Evidence gate

The candidate gate requires direct edge-semantic tests, feature gating, frozen-V1 rejection, deterministic MIPS32 frontend output, an independent defined-domain MIPS32 reference, repeatable Module Image packaging, Core/reference agreement, deterministic portable-C and Native AOT ABI generation, GCC/Clang execution agreement, and unchanged legacy V1/MIPS32 tests.
