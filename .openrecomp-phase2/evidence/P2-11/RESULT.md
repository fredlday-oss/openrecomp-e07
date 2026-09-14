# P2-11 — MIPS32 calls/stack/memory V1

VERDICT: `PASS`

STAGE MARKER: `OPENRECOMP_P2_11=PASS`
GATE MARKER: `OPENRECOMP_MIPS32_CALLS_MEMORY_V1=PASS tests=77`

## Baseline

| Item | Value |
| --- | --- |
| Stage | `OPENRECOMP_P2_11_MIPS32_CALLS_STACK_MEMORY_V1` |
| Branch | `phase2/opencode-v1` |
| Starting commit | `62044d38feec255fbcceb72754e890e7b644c35e` (`62044d3 phase2: complete P2-10 tiny MIPS32 end-to-end proof`; `HEAD` at stage start) |
| Phase-1 freeze | tag `openrecomp-phase1-pass` -> `46c2f971e1a42cf49bd936bad94697b81bf31002` (unchanged) |
| Prior gates | P2-10 `108`, P2-09 `120`, P2-08 `169`, P2-07 `106`, P2-06 `134`, P2-05 `104`, P2-04 `61`, P2-03 `67`, P2-02 `82`, P2-01 `49` |

## Bounded acceptance contract

1. **Fixture**: one synthetic/original MIPS32 fixture with two functions, an
   o32-style stack frame (`$sp` adjust, `$ra` save/restore, local slot) and
   `lw`/`sw` through the generic runtime ABI memory boundary. No commercial
   ROM/ELF/game bytes.
2. **Pipeline**: the fixture must traverse the real P2-01..P2-09 components, not
   a parallel path. P2-08 is APPLIED because the load/store boundary is used.
3. **Emitter extension**: additive and opt-in. `HostLoad`/`HostStore` are only
   emittable when `HostEmitterConfig.runtime_abi` is configured; otherwise the
   emitter fails closed. Guest addresses are never treated as host pointers.
4. **Expected observable**: derived independently of the generated host code by
   a true-MIPS32 reference interpreter (delay slots, `jal`/`jr $ra`, `lw`/`sw`
   with a bounded little-endian RAM), an explicit mathematical derivation and a
   RAM checksum. The native result is never used to derive the expectation.
5. **Reproducibility**: two independent `/Brepro` builds; a reproducibility
   level is claimed only when byte identity is actually observed.
6. **Fail closed**: out-of-range runtime memory access, external direct calls,
   missing semantics rules, missing runtime ABI, malformed/misaligned/empty
   input and unsupported opcodes must fail closed with no guessed behavior.
7. **Scope**: proves only this bounded synthetic fixture. It is not full MIPS32
   support, not PS2 support and not a guest/host equivalence proof. P2-12 was
   not started.

## Objective

Extend the P2-10 tiny end-to-end proof to multiple functions, a stack frame and
checked guest loads/stores through the real Phase-2 pipeline:

```text
synthetic MIPS32 fixture
-> adapters.mips32 decode -> P2-01 ProgramModel -> P2-02 CFG
-> P2-03 function discovery (two functions, one direct call)
-> P2-04 call graph (internal direct edge) -> P2-05 translation units
-> P2-06 indirect-control-flow classification (two RETURN_LIKE sites)
-> P2-07 host emitter (additive HostLoad/HostStore via or_rt_memory_*)
-> P2-09 deterministic build -> native executable -> expected vs actual
```

## Files created/modified

| File | Change |
| --- | --- |
| `openrecomp/host_emitter.py` | Additive, opt-in `HostLoad`/`HostStore` operations and `or_rt_memory_read`/`or_rt_memory_write` emission, gated on `HostEmitterConfig.runtime_abi`. Default output unchanged. |
| `tools/test_mips32_calls_memory_v1.py` | New dedicated P2-11 gate (77 checks), with deterministic evidence output. |
| `tools/test_mips32_end_to_end_v1.py` | One obsolete control-plane guard replaced (see "Cross-stage test adjustment"). |
| `SOURCE_SHA256SUMS.txt` | 120 -> 121 entries: new P2-11 gate entry, and the P2-10 gate entry updated for its evidence-backed modification. |
| `.openrecomp-phase2/evidence/P2-11/` | This evidence bundle. |
| `.openrecomp-phase2/{STATE,HANDOFF,STAGE_QUEUE}.md` | P2-11 PASS; P2-11 COMPLETE, P2-12 NEXT. |

No P2-01..P2-10 implementation source other than the additive emitter change was
modified. No prior test was weakened (see the explained adjustment below).

### Cross-stage test adjustment (explained, with replacement coverage)

`tools/test_mips32_end_to_end_v1.py` (P2-10) contained
`no-p2-11-evidence-directory`, which asserted that
`.openrecomp-phase2/evidence/P2-11/` must **not** exist. That guard encoded
cross-stage build state ("P2-11 has not started") rather than a P2-10 property,
and it necessarily fails once the authorized P2-11 stage writes its required
evidence. It was replaced with `no-p2-11-memory-emission-in-p2-10`, a genuine
P2-10 property that remains true: the P2-10 bounded fixture's generated host
source contains no `or_rt_memory_read`/`or_rt_memory_write`. The test count is
unchanged at 108. The committed P2-10 semantic evidence and observable are
unmodified; only this gate's stdout hash changed
(`5327f11c...` -> `347da29f2a3ede17719ea3c10f8fcf7ac1dd5a0c1bb849eace0b12f19fe0d8aa`).

## Fixture

- architecture: `mips32-bounded-v1`, little-endian, instruction width 4 bytes
- entry `0x1000` (`fn_1000`), leaf `0x1088` (`fn_1088`)
- 16 instructions, 64 bytes; SHA-256
  `4ce3fdab7f9e622648eb74eff676fd79712c2043b8e35e752e84e26712e6d309`
- synthetic/original; constructed deterministically in the gate

```text
0x1000  0x241d0100  addiu sp, r0, 0x100      ; sp = 0x100
0x1004  0x27bdfff8  addiu sp, sp, -8          ; sp = 0x0f8 (stack frame)
0x1008  0xafbf0004  sw ra, 4(sp)              ; save $ra
0x100c  0x24040015  addiu r4, r0, 21
0x1010  0xafa40000  sw r4, 0(sp)              ; spill local
0x1014  0x0c000422  jal 0x1088                ; direct call
0x1018  0x00000000  nop (delay slot)
0x101c  0x8fa50000  lw r5, 0(sp)              ; reload local
0x1020  0x8fbf0004  lw ra, 4(sp)              ; restore $ra = 0
0x1024  0x00a22821  addu r5, r5, r2           ; r5 = 21 + leaf result
0x1028  0x27bd0008  addiu sp, sp, 8            ; pop frame
0x102c  0x03e00008  jr ra
0x1030  0x00000000  nop (delay slot)
0x1088  0x24020015  addiu r2, r0, 21          ; leaf
0x108c  0x03e00008  jr ra
0x1090  0x00000000  nop (delay slot)
```

Guest instructions exercised: `addiu`, `addu`, `sw`, `lw`, `jal`, `jr`, `nop`.
The o32 save/restore of `$ra` makes the structural host call/return model and
true MIPS32 `$ra` linkage agree on the observable.

## Independent expected observable

1. **Explicit derivation.** `sp = 0x100`; frame `sp = 0x0f8`; store `$ra = 0`
   at `0x0fc` and `r4 = 21` at `0x0f8`; `jal 0x1088` sets `$ra = 0x101c`; the
   leaf sets `r2 = 21` and returns; `lw r5 <- mem[0x0f8] = 21`;
   `lw ra <- mem[0x0fc] = 0`; `r5 = 21 + 21 = 42`; `sp = 0x100`; `jr ra` with
   `$ra = 0` halts.
2. **Tiny independent reference interpreter.** True MIPS32 semantics with
   delay slots, `jal`/`jr $ra` linkage, `lw`/`sw` and a bounded little-endian
   RAM; written from the ISA description, not from the generated host code.
   Result: `r2=21 r4=21 r5=42 sp=256 ra=0`, RAM checksum `409079371`.
3. **RAM checksum.** `ram_checksum = fold(ram) with c = c*31 + byte (mod 2^32)`
   over the 4096-byte runtime RAM equals `409079371` in both the reference and
   the native execution, proving the store reached the runtime memory boundary.

## Pipeline stages traversed

| Stage | Status | Evidence |
| --- | --- | --- |
| P2-01 ProgramModel | APPLIED | Two functions `fn_1000@0x1000`, `fn_1088@0x1088`. |
| P2-02 CFG | APPLIED | 5 blocks; `CALL_RETURN` continuation at `0x1018`; two unresolved `INDIRECT` return edges. Fingerprint `99c4c440a085cdd860e622c5dff1b39a07d35936c4aaae76a498d6b9d4d5f358`. |
| P2-03 Function discovery | APPLIED | Both functions discovered from the program entry and the proven direct-call target; unreachable post-return delay slots preserved unowned. Fingerprint `f8c2c964bedc0da11f490f0f311c571f69729a86dfd2d940e957551b3155ef94`. |
| P2-04 Call graph | APPLIED | 2 nodes, 1 `INTERNAL_DIRECT` edge `fn_1000 -> fn_1088`. Fingerprint `29faef8a3135004e201a755175d7053fffd785cb90728a6dd0c28b58d8165620`. |
| P2-05 Translation units | APPLIED | `tu_fn_1000`, `tu_fn_1088`; internal call edge preserved. Fingerprint `ad11840f28c455a42686d83a244e2e309cbd328fa2fd745db0add4091a8094d1`. |
| P2-06 Indirect control flow | APPLIED | Two `jr ra` sites (`0x102c`, `0x108c`) classified `RETURN_LIKE` with `STRUCTURAL_RETURN_EVIDENCE`, `targets=[]`; no guessed targets. Fingerprint `5ca0b7c3625206bad3c9833b63e91d445d2f6be9a445276a1e7bb7c6cac926a0`. |
| P2-07 Host emitter | APPLIED | Emits two functions, the internal call, and additive `HostLoad`/`HostStore` through `or_rt_memory_read`/`or_rt_memory_write`. Generated source `4637ba676e99ba74e0c1708f100ba81b9506f1689fbee3d736364a6f821ceaf3`. |
| P2-08 Generic runtime ABI | APPLIED | Checked 32-bit memory read/write through the ABI boundary; out-of-range access fails closed at runtime (`failed=1`, no host out-of-bounds write). |
| P2-09 Deterministic build pipeline | APPLIED | Two independent `/Brepro` builds; `EXECUTABLE_REPRODUCIBLE`. |

## Host-emitter extension (additive, opt-in)

- New `HostLoad(dest, base, offset)` and `HostStore(source, base, offset)`.
- Emitted only when `runtime_abi` is configured; the address is
  `(base + offset) & or_mask(word_bits)` and the access width is explicit
  (`32u`). No pointer casts, no `memcpy`, no direct guest-to-host pointer.
- Failure of the runtime memory boundary executes `or_fail(...)` and returns.
- `runtime_abi=None` output is unchanged and all P2-07/P2-08 tests still pass.

## Deterministic native build

| Item | Value |
| --- | --- |
| runtime-support source | `413e68e44b233d9938905e1aceb2630f5a839609b8256c0a13d74e4d1bbc243e` |
| `generated.obj` | `4953a149ba34dac442cb055760f09ee984da67f222d60ef56df6a53d96983bd1` |
| `runtime_support.obj` | `b51f5f47e2d3351f686e69b5717e6d83f89fe3b2ad78e8dac3c06ffc1277112d` |
| `program.exe` | `bd719060f38793a349271358e121730206f0799d67bd771c1a8ca6a31eba27c6` |
| build manifest | `68d256081e507386f41122922df1b396619a2b9f3faaef38ff508cfffac2bbf0` |
| compiler / linker | clang-cl 22.1.8 / lld-link 22.1.8, target `x86_64-pc-windows-msvc` |
| flags | `/c /Brepro /Od /std:c11 /nologo` and `/Brepro /nologo` |
| independent builds | 2 (isolated directories; source regenerated per run) |
| reproducibility | source IDENTICAL, manifest IDENTICAL, objects IDENTICAL, executable IDENTICAL -> `EXECUTABLE_REPRODUCIBLE` |

No binary post-processing, no timestamp editing and no post-link normalization.

## Native execution and comparison

```text
expected:  failed=0, regs 0,21,256,0,21,42, ram_checksum=409079371
actual:    failed=0, regs 0,21,256,0,21,42, ram_checksum=409079371
returncode: 0;  secondary run identical
EXPECTED == ACTUAL: YES
guest registers: r2=21 r4=21 r5=42 sp=256 ra=0
```

`r5 = 42` requires the spill store and reload to have round-tripped through the
runtime memory boundary, so the call/stack/memory path is exercised end to end.

## Runtime memory failure (fail closed)

A second synthetic fixture sets `sp = 0x1000` and stores at `0(sp)`, which is
outside the 4096-byte runtime RAM. The generated code calls the checked boundary,
which returns a failure; the program reports `failed=1` and there is no host
out-of-bounds write. See `runtime_memory_failure.txt`.

## Fail-closed coverage

- guest memory access without a configured runtime ABI -> `HostEmitterError`
- missing `lw`/`sw` semantics rule -> `HostEmitterError`
- external direct `jal` target -> `HostEmitterError` (no invented callee)
- malformed `HostLoad`/`HostStore` operands -> `HostEmitterError`
- unsupported opcode -> adapter `DecodeError`
- misaligned entry / empty region -> `CFGError`
- runtime out-of-range memory access -> explicit failure flag (no silent
  continuation, no host out-of-bounds access)

## Tests / coverage

```text
python tools/test_mips32_calls_memory_v1.py
OPENRECOMP_MIPS32_CALLS_MEMORY_V1=PASS tests=77
```

Coverage: fixture identity/two-function/non-contiguity; decode addresses/ops/
`jal` target/memory flow; ProgramModel functions; CFG blocks, call continuation
and unresolved return edges; function discovery (two functions, unowned
post-return delay slots); call-graph nodes/direction/kind; translation units and
internal call edge; two `RETURN_LIKE` sites with no targets; host emission
(declarations, internal call, memory read/write, ABI declarations, width,
fail-closed branches, no hard-coded result, no pointer casts); independent
reference registers/derivation/RAM checksum; deterministic two-build
reproducibility and manifest non-leakage; native execution stability,
`expected == actual`, RAM checksum and guest register mapping; runtime OOB
fail-closed; and the fail-closed rejections above.

## Upstream regression totals

```text
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
PASS source-integrity  verified 121 manifest entries
```

## Source integrity

`SOURCE_SHA256SUMS.txt` 120 -> 121 entries via `update_sums.py`:
`tools/test_mips32_calls_memory_v1.py` added
(`906b3b5898eda23715a2dd36aaed345900da174343fb95846949f2191168cef8`) and
`tools/test_mips32_end_to_end_v1.py` updated for the explained guard change
(`b207f94bb2cdbf449469a5bdf3021f644e8ab1996f4a6ee0cd3c4999b43586c1`). No
unrelated hash changed.

## Determinism

- P2-11 gate stdout, two consecutive runs, byte-identical:
  `sha256 c0b39d658ef9f12cc056bbfcae30e945670944f51f3d12a86a0f2a4e21e0c168`.
- Fixture `4ce3fdab...`; generated source `4637ba67...`; manifest `68d25608...`;
  executable `bd719060...`; all stable across runs.

## Phase-2 marker decision

`OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=NOT_PROVEN` is **unchanged**.
`STAGE_QUEUE.md` reserves the final marker for the `P2-99 Final verdict` outcome,
not for any single intermediate stage. The narrower proven claim is
`OPENRECOMP_MIPS32_CALLS_MEMORY_V1=PASS` for this one bounded synthetic fixture.

## Known limitations

- Proves only this 16-instruction synthetic fixture; not full MIPS32 support, not
  PS2 support and not guest/host equivalence.
- Call/return is modeled structurally (host function call/return); the fixture's
  o32 `$ra` save/restore makes that model agree with true MIPS32 for this case.
  General `$ra` dataflow is not recovered.
- The neutral CFG/emitter do not model delay slots as first-class semantics; the
  fixture uses `nop` delay slots and unreachable post-return delay slots remain
  unowned residual evidence.
- Loads/stores are `lw`/`sw` at word width; sub-word and misaligned accesses are
  not covered.
- Emitted functions remain void with no argument/return ABI.
- `openrecomp/*.py` remain outside `SOURCE_SHA256SUMS.txt` (pre-existing
  `update_sums.py` glob gap).
- Toolchain-gated Phase-1 gates remain skipped on this host.

## Explicit non-claims

No arbitrary MIPS32 equivalence, full MIPS32 support, full PS2 support,
commercial-game recompilation or console compatibility. P2-12 and later stages
were not started. The final `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS`
marker is not claimed.

## Boundary rule

No P2-11 git commit was created. The coherent P2-11 changes are left in the
working tree for independent review and boundary commit.

## Final verdict

`PASS` — a synthetic/original multi-function MIPS32 fixture with a stack frame,
direct call, and checked `lw`/`sw` traverses the real Phase-2 pipeline to a
reproducible native executable whose independently derived expected observable
(including a runtime RAM checksum) exactly matches the actual native observable,
with out-of-range memory access failing closed.

OPENRECOMP_P2_11=PASS
OPENRECOMP_MIPS32_CALLS_MEMORY_V1=PASS tests=77
