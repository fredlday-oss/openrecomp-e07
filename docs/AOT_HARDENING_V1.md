# OpenRecomp AOT hardening V1

**Frontier:** `OPENRECOMP_AOT_HARDENING_V1`  
**Status:** **PASS — bounded compiler-quality hardening**

This frontier hardens the existing normalized IR V1 portable C backend without expanding guest-architecture claims. It preserves the same IR V1, Module Image V1 and Core API boundaries while adding stricter generated-code, runtime-fault and sanitizer gates.

## Warning-clean generated C

The established RV32I E07 and bounded MIPS32 AOT workloads are now compiled by both GCC and Clang with:

```text
-std=c11 -O2 -Wall -Wextra -Werror
```

The generator was changed rather than suppressing warnings. It now avoids unused call-result temporaries, explicitly marks unused argument/value storage where appropriate, emits helpers only when their semantics are required, and lowers normalized unsigned comparisons through a warning-stable helper.

A valid trap-only hardening fixture exposed one remaining unused-helper edge case during the first CI run. The generator was corrected so the common mask helper remains live through the exported observed-state boundary rather than weakening `-Werror`.

## Positive operation corpus

The dedicated hardening fixture is synthetic normalized IR V1 and is independent of RV32I or MIPS32 opcode decoding. It runs in both little- and big-endian module configurations and exercises the current portable backend families, including:

- state reads/writes and constants;
- `add`, `sub`, `mul`, `and`, `or`, `xor`, `shl`, `lshr`, `ashr`;
- `eq`, `ne`, `ult`, `ule`, `ugt`, `uge`, `slt`, `sle`, `sgt`, `sge`;
- `zext`, `sext`, `trunc`, `bitcast` and `select`;
- aligned loads/stores and signed loads;
- direct calls;
- direct branches/jumps and bounded indirect jumps;
- returns and a deliberately unreachable trap block.

For each endian configuration the Core API `ReferenceExecutor` and native AOT modules compiled by both GCC and Clang must agree on observed state, function return, operation count, state snapshot and observable memory.

The established hardening result is:

```text
AOT_HARDENING_POSITIVE=2147483672
```

## Deterministic runtime fault equivalence

Nine valid IR/Module test programs intentionally trigger deterministic runtime failures. Each case must fail in both the Core API reference path and the generated AOT path with the same normalized fault category under both GCC and Clang.

The current cases are:

```text
memory-oob       -> memory-fault
misalignment     -> misalignment
operation-limit  -> operation-limit
shift-count      -> shift-count
trap             -> trap
indirect-target  -> indirect-target
call-depth       -> call-depth
host-failure     -> host-failure
host-void        -> host-void
```

The gate reports:

```text
AOT_HARDENING_FAULT_CASES=9
OPENRECOMP_AOT_HARDENING_FAULT_EQUIVALENCE=PASS
```

This compares deterministic failure classes rather than requiring implementation-specific exception/error strings to be byte-identical.

## ASan and UBSan

The generated little- and big-endian positive hardening modules are also compiled as standalone executables under both GCC and Clang with AddressSanitizer and UndefinedBehaviorSanitizer enabled:

```text
-fsanitize=address,undefined -fno-omit-frame-pointer
```

The CI run requires the executable to complete successfully with leak detection and halt-on-error enabled. The current gates are:

```text
OPENRECOMP_AOT_HARDENING_GCC_SANITIZERS=PASS
OPENRECOMP_AOT_HARDENING_CLANG_SANITIZERS=PASS
```

## Final gate

A successful hardening run ends with:

```text
OPENRECOMP_AOT_HARDENING_WARNING_CLEAN=PASS
OPENRECOMP_AOT_HARDENING_FAULT_EQUIVALENCE=PASS
OPENRECOMP_AOT_HARDENING_V1=PASS
```

The existing dual-architecture AOT workflow separately continues to require exact RV32I and MIPS32 Core API/AOT equivalence and GCC/Clang behavioral parity.

## Claim boundary

This frontier establishes a bounded compiler-quality hardening PASS for the current portable C backend and clean synthetic fixtures. It does **not** establish:

- arbitrary RV32I or MIPS32 binary support;
- full MIPS32 ISA/ABI coverage;
- Windows or macOS compiler/runtime parity;
- a frozen or stable third-party native-module ABI;
- production optimization correctness across arbitrary programs;
- WebAssembly compilation of the portable C AOT path;
- a release-quality production compiler pipeline;
- proprietary console executable support.

Those remain separate validation frontiers.
