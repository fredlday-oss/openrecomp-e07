# P2-07 — Deterministic host emitter V1

VERDICT: `PASS`

STAGE MARKER: `OPENRECOMP_P2_07=PASS`
GATE MARKER: `OPENRECOMP_HOST_EMITTER_V1=PASS tests=106`

## Baseline

| Item | Value |
| --- | --- |
| Stage | `OPENRECOMP_P2_07_HOST_EMITTER_V1` |
| Branch | `phase2/opencode-v1` |
| Starting commit | `f9f2662b90c165a967fa943070e79688ff8198b1` (`f9f2662 phase2: complete P2-06 indirect control flow classification`; `HEAD` at stage start) |
| Phase-1 freeze | tag `openrecomp-phase1-pass` -> `46c2f971e1a42cf49bd936bad94697b81bf31002` (verified unchanged) |
| Prior gates | P2-06 `134`, P2-05 `104`, P2-04 `61`, P2-03 `67`, P2-02 `82`, P2-01 `49` |

Pre-flight: branch correct; `HEAD` equals the P2-06 boundary; the Phase-1 tag resolves
to the frozen commit; only the excluded untracked residue
(`.openrecomp-phase2/backups/`, `artifacts/mips32_translation_v1/`,
`artifacts/mips32_translation_evidence_closure_v1/`) was present and was left untouched.

## Objective

Implement the first deterministic host-code emitter for OpenRecomp. Consume the frozen
structural pipeline (`TranslationUnitSet` + `IndirectControlFlowSet`) and generate
deterministic, portable C for a deliberately bounded, explicitly proven subset of guest
semantics. Emit only what is proven; fail closed on everything else. No full MIPS32
recompilation, no IR lowering, no generic runtime ABI (P2-08), no guest execution.

## Files added

| File | Role |
| --- | --- |
| `openrecomp/host_emitter.py` | Neutral P2-07 emitter: `HostEmitter`, `HostEmitterConfig`, `HostTranslation`, `HostTranslationSet`, `HostEmitterError`, `HostSemantics`, `HostInstructionSemantics`, the operand/operation vocabulary, `emit_host_translation`, `emit_host_translation_from`. |
| `tools/test_host_emitter_v1.py` | Deterministic 106-check gate with optional `--json` and an optional native compile/run check. |
| `.openrecomp-phase2/evidence/P2-07/*` | This evidence bundle, including synthetic generated-C fixtures. |

## Files modified

| File | Change |
| --- | --- |
| `SOURCE_SHA256SUMS.txt` | Registered `tools/test_host_emitter_v1.py` via `update_sums.py` (116 -> 117 entries). No existing hash changed. |
| `.openrecomp-phase2/STATE.md`, `HANDOFF.md` | Stage transition (P2-07 PASS -> P2-08). |
| `.openrecomp-phase2/STAGE_QUEUE.md` | Control-plane status only: P2-07 `COMPLETE`, P2-08 `NEXT`. |

No P2-00..P2-06 implementation source, and no P2-00..P2-06 evidence, was modified. The
frozen IR V1 / Module Image V1 / Core API / AOT ABI, the CFG builder, function discovery,
the call graph, the translation-unit layer and the indirect-control-flow classifier are
untouched. No prior test was weakened.

## Public API

```python
emit_host_translation(translation_units: TranslationUnitSet,
                      classification: IndirectControlFlowSet, *,
                      config: HostEmitterConfig) -> HostTranslationSet
emit_host_translation_from(units: Iterable[TranslationUnit],
                           classification: IndirectControlFlowSet, *,
                           source: ProgramSource,
                           config: HostEmitterConfig) -> HostTranslationSet
```

`HostEmitterConfig(semantics, entry_function, word_bits=32, register_names=(),
unsupported_indirect_policy=BOUNDARY)`. `HostTranslationSet` exposes `translations`,
`register_names`, `source_text`, `translation_for(function_id)`, `to_document()`,
`serialize()` and `fingerprint()`.

## Semantic seam (no guessing)

Guest semantics are never inferred from a mnemonic, an address or an opcode. The emitter
requires an explicit `HostInstructionSemantics` rule for the exact
`(architecture, op)` pair from the configured `HostSemantics` table. Each rule declares
the neutral operations emitted and, for control flow, the branch condition or the register
holding an indirect target. Missing rules, flow mismatches, missing adapter fields and
invalid rules all fail closed. The bounded V1 rule vocabulary is
`HostNop`/`HostCopy`/`HostConst`/`HostBinop`/`HostCompare` plus `HostComparison`.

## Bounded guest semantics emitted

Only where an explicit rule is supplied:

- immediate constant load;
- register copy / move;
- integer add, subtract, multiply;
- integer and, or, exclusive-or;
- shift left, logical shift right, arithmetic shift right (with an explicit un-normalized
  shift-count fail boundary);
- signed and unsigned integer compare (`eq`/`ne`/`ult`/`ule`/`ugt`/`uge`/`slt`/`sle`/
  `sgt`/`sge`);
- explicit guest-word-width masking with wraparound for widths 8/16/32/64 (unsigned
  `uint64_t` storage + `or_mask`; arithmetic shift and signed compare via explicit
  `or_ashr`/`or_signed` helpers).

Loads, stores, host calls and all runtime services are outside the bounded V1 subset.

## Control-flow forms emitted

- direct fallthrough (`goto` to the fallthrough successor);
- direct conditional branch (`if (cond) goto taken; else goto not_taken;`);
- direct jump (`goto`);
- direct internal call (`fn_<id>();` then `goto` continuation), with a forward prototype;
- return (`return;`);
- end-of-function without a successor (`return;`).

All control-flow targets must be blocks of the same translation unit; non-local or
unresolved CFG edges fail closed.

## Indirect-control-flow handling (P2-06)

| P2-06 status | Emission |
| --- | --- |
| `RESOLVED` (single target) | direct `goto` (jump) or direct internal call (call) |
| `RESOLVED` (finite exact set) | `switch` on the proven runtime target with a fail-closed `default` |
| `BOUNDED_CANDIDATES` | explicit `or_fail("bounded candidate set is not a resolved target")` boundary (or `REJECT`); **never** promoted to a direct edge |
| `EXTERNAL_OR_RUNTIME_MEDIATED` | explicit fail-closed boundary; **no** internal target is invented |
| `RETURN_LIKE` | `return` (indirect jumps only) |
| `UNRESOLVED_INDIRECT_CALL` | explicit fail-closed boundary (or `REJECT`) |
| `UNRESOLVED_INDIRECT_JUMP` | explicit fail-closed boundary (or `REJECT`) |
| `UNSUPPORTED_OR_MALFORMED` | rejected at generation time |

`HostEmitterConfig.unsupported_indirect_policy` selects `BOUNDARY` (default) or `REJECT`.
Both modes are exercised by the gate.

## Other fail-closed boundaries

An instruction with no proven rule; an external direct call (requires the generic runtime
ABI, deferred to P2-08); a resolved target that is not a block of the unit or not a known
internal function; a guest trap; a shift count that is not normalized at runtime; and
malformed/mismatched P2-06 classification input.

## Host-neutral generation

`openrecomp/host_emitter.py` separates the structural/semantic input, host-source
generation, and runtime-dependent operations. It bakes in no Windows/UI/graphics/audio/
filesystem API, no absolute path, no timestamp and no Python object identity. The
generated C includes only `<stdint.h>` and `<stddef.h>` and uses explicit fixed-width
arithmetic with masking. Exposed runtime surface is limited to `openrecomp_run()`,
`openrecomp_failed()`, `openrecomp_error()` and register accessors — no memory, host-call
callback or generic runtime ABI.

## Deterministic identifiers and ordering

- translation units (functions) ordered by `(entry_address, function_id)`;
- blocks in P2-05 canonical order (entry block first, then `(entry_address, id)`);
- instructions in address order;
- declarations emitted in the same function order, before definitions;
- helper definitions in a fixed order;
- identifiers derive deterministically from stable OpenRecomp ids:
  `fn_<sanitize(function_id)>`, `bb_<sanitize(block_id)>`; register indices derive from
  the labelled names.

## Serialization / fingerprint

`HostTranslationSet.to_document()` records the version, architecture, entry function,
source, word width, register names, per-translation metadata, the source SHA-256, and the
full generated source text; `serialize()` is canonical JSON; `fingerprint()` is the
SHA-256 of the generated C. Two consecutive gate runs produced byte-identical stdout
(`sha256 fb6e6e2c6ba660a5c3df75602a59c0501bf86ca53e0371e4942c0c76108c45d5`). Identical
inputs produce byte-identical C regardless of Python hash/insertion ordering. See
`determinism.txt`.

## Tests / coverage

```text
python tools/test_host_emitter_v1.py
OPENRECOMP_HOST_EMITTER_V1=PASS tests=106
```

Coverage: deterministic output, byte identity and fingerprint; canonical function/block/
instruction ordering; stable identifiers and declarations; direct fallthrough, branch,
jump, call and return emission; return-like emission; exact resolved jump and call
(single and finite set); bounded/external/unresolved/external-direct-call fail-closed
behaviour; reject policy; unsupported instruction and malformed P2-06 input rejection;
resolved-target validation; absence of absolute paths, timestamps and Python identity;
ordering and low-level entry-point equivalence; multiple and empty translation units;
8/16/32/64-bit widths and immediate masking; only portable includes and no P2-08 runtime;
P2-05 input non-mutation; and `HostSemantics`/`HostEmitterConfig` model validation.

## Optional native compilation

A native compiler is detected (never assumed). On this host `clang` was found; the gate
compiled the generated C for a synthetic 8-bit fixture, executed it, and observed
`44 0` (expected `44 0`, i.e. `(200 + 100) mod 2^8 = 44` with no fail-closed boundary).
This is a bounded compile/run check, **not** a guest/host equivalence proof. If no
compiler is available the check is a documented toolchain skip, and the semantic gate
still passes. See `native_compile.txt`.

## Regression gates

```text
OPENRECOMP_HOST_EMITTER_V1=PASS tests=106
OPENRECOMP_INDIRECT_CONTROL_FLOW_V1=PASS tests=134
OPENRECOMP_TRANSLATION_UNITS_V1=PASS tests=104
OPENRECOMP_CALL_GRAPH_V1=PASS tests=61
OPENRECOMP_FUNCTION_DISCOVERY_V1=PASS tests=67
OPENRECOMP_CFG_V1=PASS tests=82
OPENRECOMP_PROGRAM_MODEL_V1=PASS tests=49
OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
PASS source-integrity  verified 117 manifest entries
```

The two toolchain-gated Phase-1 gates (`e07-hardened-end-to-end`,
`external-repro-v1`) remain unexecutable on this host (missing `gcc`, `posix`) and are
never counted as pass.

## Known limitations

- The bounded V1 subset is small and rule-driven; loads, stores, host calls, delay slots,
  calling conventions and runtime services are not emitted.
- A finite resolved target set still requires a runtime target value; the emitter
  dispatches with a `switch` and fails closed outside the proven set.
- The generated entry point is void and has no argument/return ABI (deferred to P2-08).
- The compiled fixture proves only that the generated source compiles and computes one
  synthetic arithmetic result; it is not an equivalence proof.
- `schema/*.json` and `openrecomp/*.py` remain outside `SOURCE_SHA256SUMS.txt`
  (pre-existing `update_sums.py` `schemas/` glob gap); the new files are covered by the
  hashes in `determinism.txt`.
- Toolchain-gated Phase-1 gates remain skipped on this host.

## Explicit non-claims

P2-07 does **not** claim full MIPS32 recompilation, IR lowering, host execution of guest
code, generic runtime ABI or memory/IO contracts, AOT integration, whole-game
recompilation, console compatibility, RT64 integration, or guest/host equivalence. It
does **not** claim `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS`.

## Boundary rule

No P2-07 git commit was created. The coherent P2-07 changes are left in the working tree
for independent review and boundary commit. P2-08 (Generic runtime ABI V1) was **not**
started.

## Final verdict

`PASS` — the first OpenRecomp host emitter generates deterministic, portable C for a
bounded, explicitly proven subset of the structural pipeline; unsupported semantics,
unresolved indirect control flow and bounded candidate sets all fail closed; identifiers,
ordering, declarations and helper definitions are stable; generated source contains no
machine-specific metadata; and all mandatory upstream regressions and source integrity
pass.

OPENRECOMP_P2_07=PASS
OPENRECOMP_HOST_EMITTER_V1=PASS tests=106
