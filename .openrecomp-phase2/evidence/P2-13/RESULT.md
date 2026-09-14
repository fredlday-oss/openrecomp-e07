# P2-13 — Runtime-host boundary V1

VERDICT: `PASS`

STAGE MARKER: `OPENRECOMP_P2_13=PASS`
GATE MARKER: `OPENRECOMP_RUNTIME_HOST_BOUNDARY_V1=PASS tests=80`

## Baseline

| Item | Value |
| --- | --- |
| Stage | `OPENRECOMP_P2_13_RUNTIME_HOST_BOUNDARY_V1` |
| Branch | `phase2/opencode-v1` |
| Starting commit | `aa9939a73addde9e029111a1c6b0a6a783dda8cc` (`aa9939a phase2: complete P2-12 MIPS32 direct CFG stress`; `HEAD` at stage start) |
| Phase-1 freeze | tag `openrecomp-phase1-pass` -> `46c2f971e1a42cf49bd936bad94697b81bf31002` (unchanged) |
| Prior gates | P2-12 `96`, P2-11 `77`, P2-10 `108`, P2-09 `120`, P2-08 `169`, P2-07 `106`, P2-06 `134`, P2-05 `104`, P2-04 `61`, P2-03 `67`, P2-02 `82`, P2-01 `49` |

## Bounded acceptance contract

1. **Feature proven**: the deterministic host-call boundary between generated host
   code and runtime services. A synthetic/original MIPS32 fixture computes a
   value and hands it to a runtime-mediated transfer; explicit P2-06 evidence
   identifies the site as `EXTERNAL_OR_RUNTIME_MEDIATED` with a runtime-service
   mechanism; P2-07 emits a call into the P2-08 host-call boundary with the
   ABI-assigned service id; the runtime-support service dispatches
   deterministically and records the call.
2. **Inputs/fixture**: five synthetic MIPS32 instructions (20 bytes); no
   commercial ROM/ELF/game bytes.
3. **Structural stages involved**: P2-01..P2-09 (see table).
4. **Semantics exercised**: `addiu` guest arithmetic; a runtime-mediated
   indirect call (`jr`) classified from explicit evidence; ABI service identity,
   argument and result transfer.
5. **Runtime involvement**: `or_rt_host_call` (generated C) and the P2-08
   `RuntimeServiceTable` / `RuntimeState` contract (in-process).
6. **Expected observable**: guest `r4 = 42`; declared service result `84`;
   continuation `r5 = 92`; native runtime record `calls=1`,
   `last_service=1`, `last_arg=42`, `last_result=84`.
7. **Independent derivation**: guest arithmetic derived by a tiny evaluator over
   the fixture words up to the call site, combined with the fixture-declared
   (declarative) service semantics `x -> 2x`. The native result is never used to
   derive the expectation.
8. **Failure cases**: unsupported declared service fails closed natively; a
   host-call rule without external evidence is rejected at emission; an
   undeclared service is rejected; a host call without a runtime ABI is
   rejected; unknown/arity failures in the ABI contract; malformed call
   operations; malformed input.
9. **Reproducibility**: two independent `/Brepro` builds; a level is claimed
   only when byte identity is observed.
10. **Scope/non-claims**: proves only this bounded synthetic fixture. Not full
    MIPS32 support, not PS2 support and not guest/host equivalence.

## Objective

Prove the runtime-host boundary: deterministic host-call ABI, with unsupported
service handling failing closed.

## Files created/modified

| File | Change |
| --- | --- |
| `tools/test_runtime_host_boundary_v1.py` | New dedicated P2-13 gate (80 checks), with deterministic evidence output. |
| `tools/test_mips32_direct_cfg_v1.py` | One obsolete cross-stage guard replaced (count unchanged at 96). |
| `SOURCE_SHA256SUMS.txt` | 122 -> 123 entries: new P2-13 gate entry and the updated P2-12 gate entry. |
| `.openrecomp-phase2/evidence/P2-13/` | This evidence bundle. |
| `.openrecomp-phase2/{STATE,HANDOFF,STAGE_QUEUE}.md` | P2-13 PASS; P2-13 COMPLETE, P2-14 NEXT. |

No implementation source (`openrecomp/*.py`) was modified; the stage reuses the
existing emitter host-call seam (P2-08) and the generic runtime ABI.

### Cross-stage test adjustment (explained, with replacement coverage)

`tools/test_mips32_direct_cfg_v1.py` (P2-12) contained
`no-p2-13-evidence-directory`, a cross-stage guard asserting P2-13 evidence must
not exist. It necessarily fails once the authorized P2-13 stage writes its
required evidence, and it encoded build state rather than a P2-12 property. It
was replaced with `no-p2-13-host-call-emission-in-p2-12` — a genuine P2-12
property that remains true: the P2-12 bounded fixture's generated host source
contains no host-call invocation (`or_rt_host_call(OR_RT_SERVICE…`) and no
service macro. The test count is unchanged at 96. P2-12 semantics, observable
and committed evidence are otherwise unmodified; only that gate's stdout hash
changed (`d01ec8f0...` ->
`6f19a2742dd8a2ff8688b8712585fa5e2657ed1dd9f9050f510c0d2dde7d0ee9`).

## Fixture

- architecture: `mips32-bounded-v1`, little-endian, instruction width 4 bytes
- entry `0x1000`; runtime-mediated call site `0x1008`
- 5 instructions, 20 bytes; SHA-256
  `7c9ba624b7503ccb31e0cd4b82b2c0316674b2c094945df84524503e34eb19b6`
- synthetic/original; words recorded as constants

```text
0x1000  0x24040015  addiu r4, r0, 21
0x1004  0x24840015  addiu r4, r4, 21        ; r4 = 42
0x1008  0x00800008  jr r4                   ; runtime-mediated host call
0x100c  0x00000000  nop (delay slot)
0x1010  0x24850008  addiu r5, r4, 8         ; r5 = service result + 8
```

The `jr` site is classified `INDIRECT_CALL` (a runtime-mediated call with a
return) by the fixture, with explicit P2-06 evidence. The rule for `jr` declares
the service and the argument/result registers; the emitter never infers a
service identity.

## Independent expected observable

1. **Guest arithmetic**: `r4 = 21 + 21 = 42` (tiny evaluator over the recorded
   fixture words up to the call site).
2. **Declared service semantics**: `demo.double(x) = 2x`, so the service result
   is `84`; the continuation computes `r5 = 84 + 8 = 92`.
3. **ABI-assigned service identity**: `RuntimeServiceTable.numeric_id` assigns
   `1` to `demo.double`; the generated C uses
   `OR_RT_SERVICE_DEMO_DOUBLE` (`UINT64_C(1)`).
4. The native runtime record expected is `calls=1`, `last_service=1`,
   `last_arg=42`, `last_result=84`.

The native result is never used to derive the expected value.

## Pipeline stages traversed

| Stage | Status | Evidence |
| --- | --- | --- |
| P2-01 ProgramModel | APPLIED | One function `fn_1000@0x1000`; `INDIRECT_CALL` instruction with no static target, marked unresolved. |
| P2-02 CFG | APPLIED | `blk_1000` terminal `INDIRECT_CALL` with a `CALL_RETURN` successor to `0x100c`. Fingerprint `a5a4b89b171b3487603b4ba7b46d2fe9779a8fc8f8d83bdff041e6e207f1dd16`. |
| P2-03 Function discovery | APPLIED | `fn_1000`; the unresolved call site is preserved. Fingerprint `350b7ef580a770a77fd7cb7a249d1bb6bf67186aa8ae9878b77d2ade73347d2f`. |
| P2-04 Call graph | APPLIED | One node, no internal edges (the call target is runtime-mediated, not an internal function). |
| P2-05 Translation units | APPLIED | `tu_fn_1000`; one unresolved call site. Fingerprint `a8807b86310bbbc03f06156a31e9ba12f6cb563857c97b1c9f4f70ce6b5f7ca2`. |
| P2-06 Indirect control flow | APPLIED | Site `0x1008` classified `EXTERNAL_OR_RUNTIME_MEDIATED`, basis `EXTERNAL_RUNTIME_EVIDENCE`, mechanism `runtime-service`, `targets=[]`. Without evidence it becomes `UNRESOLVED_INDIRECT_CALL` with no target. Fingerprint `b3317f0439137abc6366b9c84df8c0bda6a38bfb349ca1b1032fdb921c1e4d07`. |
| P2-07 Host emitter | APPLIED | Host call to `or_rt_host_call(OR_RT_SERVICE_DEMO_DOUBLE, 1u, or_call_args, &or_call_result)` with a fail-closed branch, then the continuation. Generated source `8c602b35e47f90d5edf9fd6cad566b4b378c3ffc69574f63b80c48bdb55367ef`. |
| P2-08 Generic runtime ABI | APPLIED | Service identity, argument/result transfer, deterministic dispatch and unknown/arity fail-closed in-process; `abi_c_declarations` supplies the C boundary. |
| P2-09 Deterministic build pipeline | APPLIED | Two independent `/Brepro` builds; `EXECUTABLE_REPRODUCIBLE`. |

## Host-call boundary behavior

- Emitted call (single declared service):
  `or_rt_host_call(OR_RT_SERVICE_DEMO_DOUBLE, 1u, or_call_args, &or_call_result)`,
  with `or_fail("runtime host service demo.double failed"); return;` on failure.
- The argument array and result pointer are host-local; no guest address is
  treated as a host pointer and no pointer cast appears in the generated source.
- The service identity comes from the explicit semantic rule and the ABI
  declaration; the C side uses the ABI-assigned numeric macro.

## Deterministic native build

| Item | Value |
| --- | --- |
| runtime-support source | `0edc0a18500c0059a6b0ff6314c657a679bef1569af337c5dd22874f80ad25cb` |
| `generated.obj` | `5323be22f2c393ce959ff75ed3285c559ec97c38ab8c0f7eae403f08096869ba` |
| `runtime_support.obj` | `07f9021a18029a53dc3d1dc1d86a332036871085983b21f3d6d1f4f05a47eb7d` |
| `program.exe` | `8ab94ab0f186e33778ddb6464f31c492045e6b612abeb523547b2aaa92a940a1` |
| build manifest | `bf75f08f6602ea100ae6156f3ed7856c8d65020bb910a4d0916ca185ee0c3ddc` |
| compiler / linker | clang-cl 22.1.8 / lld-link 22.1.8, target `x86_64-pc-windows-msvc` |
| flags | `/c /Brepro /Od /std:c11 /nologo` and `/Brepro /nologo` |
| independent builds | 2 (isolated directories; source regenerated per run) |
| reproducibility | source IDENTICAL, manifest IDENTICAL, objects IDENTICAL, executable IDENTICAL -> `EXECUTABLE_REPRODUCIBLE` |

No binary post-processing, no timestamp editing and no post-link normalization.

## Native execution and comparison

```text
expected:  failed=0, error=, calls=1, last_service=1, last_arg=42, last_result=84,
           reg[0]=0, reg[1]=84, reg[2]=92
actual:    identical
returncode: 0;  secondary run identical
EXPECTED == ACTUAL: YES
```

`reg[1]` is guest `r4` (service result 84) and `reg[2]` is guest `r5`
(continuation 92), proving the service result crossed back into the guest and the
continuation executed.

## Unsupported service fails closed (native)

A variant fixture declares `demo.missing` at build time (so the emitter and ABI
accept it) but the runtime-support does not implement it. The boundary returns a
failure; the generated code calls `or_fail` and stops:

```text
failed=1
error=runtime host service demo.missing failed
calls=1
last_service=1
reg[0]=0
reg[1]=42
reg[2]=0
```

The continuation (`reg[2] = 92`) did not run, so no unsupported behavior was
silently continued.

## Fail-closed coverage

- unsupported declared service at runtime -> `failed=1`, error recorded, no
  continuation
- host-call rule without explicit external evidence -> `HostEmitterError`
- undeclared service -> `HostEmitterError`
- host call without a configured runtime ABI -> `HostEmitterError`
- ABI unknown service -> `UNKNOWN_HOST_SERVICE`; arity mismatch -> `HOST_CALL_ARITY`
- malformed `HostCallOperation` (empty service, non-tuple args, non-register
  result) -> `HostEmitterError`
- service table without a handler -> `RuntimeAbiError`
- unsupported opcode -> adapter `DecodeError`; misaligned entry / empty region ->
  `CFGError`
- no guessed indirect targets and no `BOUNDED_CANDIDATES` promotion anywhere

## Tests / coverage

```text
python tools/test_runtime_host_boundary_v1.py
OPENRECOMP_RUNTIME_HOST_BOUNDARY_V1=PASS tests=80
```

Coverage: fixture identity; decode (`jr` as `INDIRECT_CALL`, no static target);
CFG call continuation; function/unit packaging with the unresolved call site;
P2-06 external classification with mechanism and no target, plus fail-closed
without evidence; P2-08 ABI contract (service id, macro, known dispatch, unknown
service, arity, deterministic repeat, `RuntimeState` record, version); host-call
emission, ABI declaration, service macro, result register, fail-closed branch,
continuation, determinism, no pointer casts, no hard-coded result; undeclared
service and no-ABI rejection; independent expected derivation; deterministic
two-build reproducibility and manifest non-leakage; native execution stability,
`expected == actual`, runtime record and register mapping; unsupported-service
native fail-closed; malformed/negative cases; and no next-stage work.

## Upstream regression totals

```text
OPENRECOMP_MIPS32_DIRECT_CFG_V1=PASS tests=96
OPENRECOMP_MIPS32_CALLS_MEMORY_V1=PASS tests=77
OPENRECOMP_MIPS32_END_TO_END_V1=PASS tests=108
OPENRECOMP_DETERMINISTIC_BUILD_V1=PASS tests=120
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
PASS source-integrity  verified 123 manifest entries
```

## Source integrity

`SOURCE_SHA256SUMS.txt` 122 -> 123 entries via `update_sums.py`:
`tools/test_runtime_host_boundary_v1.py` added
(`3c35e22b4aaed5ea744408e10a3a5999c41e6d2a87659f889e1ad9fe9a973754`) and
`tools/test_mips32_direct_cfg_v1.py` updated for the explained guard change
(`f2a15007b475058b8dd152ab7f3bef3b12777a01fa0af91833c03b79dacd9526`). No
unrelated hash changed.

## Determinism

- P2-13 gate stdout, two consecutive runs, byte-identical:
  `sha256 8617ed85d188b99b4d954dcfdd6216c170cbc3ffa9b3ea004244be05dd7feee0`.
- Fixture `7c9ba624...`; generated source `8c602b35...`; manifest `bf75f08f...`;
  executable `8ab94ab0...`; all stable across runs.

## Phase-2 marker decision

`OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=NOT_PROVEN` is **unchanged**.
`STAGE_QUEUE.md` reserves the final marker for the `P2-99 Final verdict` outcome,
not for any single intermediate stage. The narrower proven claim is
`OPENRECOMP_RUNTIME_HOST_BOUNDARY_V1=PASS` for this one bounded synthetic
fixture.

## Known limitations

- Proves only this five-instruction synthetic fixture and one declared service;
  not a general host-service catalog.
- The runtime host-call boundary in generated C is a declaration plus a
  fixture-provided implementation; no platform runtime library is generated.
- The `jr`-based runtime-mediated call is a bounded fixture model; general
  indirect-call target recovery is out of scope and remains fail-closed.
- Emitted functions remain void with no argument/return ABI.
- Only word-width aligned `lw`/`sw` are covered for memory (P2-11).
- `openrecomp/*.py` remain outside `SOURCE_SHA256SUMS.txt` (pre-existing
  `update_sums.py` glob gap).
- Toolchain-gated Phase-1 gates remain skipped on this host.

## Explicit non-claims

No arbitrary MIPS32 equivalence, full MIPS32 support, full PS2 support,
commercial-game recompilation or console compatibility. P2-14 and later stages
were not started. The final `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS`
marker is not claimed.

## Boundary rule

No P2-13 git commit was created. The coherent P2-13 changes are left in the
working tree for independent review and boundary commit.

## Final verdict

`PASS` — a synthetic/original MIPS32 fixture hands a guest-computed value to a
runtime-mediated host call identified by explicit evidence; the generated code
invokes the declared ABI service, the runtime-support dispatches it
deterministically and records the call, the service result returns to the guest
and the continuation executes; an unsupported declared service fails closed
natively with no silent continuation. All upstream regressions, Phase-1 gates
and source integrity pass.

OPENRECOMP_P2_13=PASS
OPENRECOMP_RUNTIME_HOST_BOUNDARY_V1=PASS tests=80
