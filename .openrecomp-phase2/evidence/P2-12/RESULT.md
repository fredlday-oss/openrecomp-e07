# P2-12 — MIPS32 direct CFG stress V1

VERDICT: `PASS`

STAGE MARKER: `OPENRECOMP_P2_12=PASS`
GATE MARKER: `OPENRECOMP_MIPS32_DIRECT_CFG_V1=PASS tests=96`

## Baseline

| Item | Value |
| --- | --- |
| Stage | `OPENRECOMP_P2_12_MIPS32_DIRECT_CFG_STRESS_V1` |
| Branch | `phase2/opencode-v1` |
| Starting commit | `6cb5ff40eca30eaeb383333c10bcf50165a167ce` (`6cb5ff4 phase2: complete P2-11 MIPS32 calls stack and memory`; `HEAD` at stage start) |
| Phase-1 freeze | tag `openrecomp-phase1-pass` -> `46c2f971e1a42cf49bd936bad94697b81bf31002` (unchanged) |
| Prior gates | P2-11 `77`, P2-10 `108`, P2-09 `120`, P2-08 `169`, P2-07 `106`, P2-06 `134`, P2-05 `104`, P2-04 `61`, P2-03 `67`, P2-02 `82`, P2-01 `49` |

## Bounded acceptance contract

1. **Fixture**: one synthetic/original MIPS32 fixture containing a counted loop
   with a backward branch and both branch outcomes, conditional branches to the
   dispatch targets, a direct `jal` call with `jr $ra` returns, an o32 `$ra`
   save/restore (checked `sw`/`lw`), and a bounded indirect dispatch (`jr r5`).
   No commercial ROM/ELF/game bytes.
2. **Pipeline**: the fixture must traverse the real P2-01..P2-09 components.
3. **Bounded switch / direct-table proof**: the dispatch's finite exact target
   set is supplied by explicit P2-06 `EXACT_TARGET_SET` evidence; P2-07 lowers it
   to a `switch` with a fail-closed `default`. The emitter never guesses an
   indirect target, never promotes `BOUNDED_CANDIDATES`, and fails closed when
   evidence is absent.
4. **Expected observable**: derived independently of the generated host code by
   a true-MIPS32 reference interpreter (delay slots, `jal`/`jr $ra`, `lw`/`sw`,
   bounded RAM) plus the explicit derivation.
5. **Reproducibility**: two independent `/Brepro` builds; a level is claimed only
   when byte identity is observed.
6. **Fail closed**: out-of-set runtime dispatch target, bounded candidates,
   missing evidence, missing semantics rules, external calls and malformed input.
7. **Scope**: proves only this bounded synthetic fixture; not full MIPS32, not
   PS2, not guest/host equivalence. P2-13 was not started.

## Objective

Stress the direct control-flow path (branches, loops, calls, returns) and prove
the bounded switch/direct-table lowering where explicit evidence exists.

## Files created/modified

| File | Change |
| --- | --- |
| `tools/test_mips32_direct_cfg_v1.py` | New dedicated P2-12 gate (96 checks), with deterministic evidence output. |
| `tools/test_mips32_calls_memory_v1.py` | One obsolete cross-stage guard replaced (count unchanged at 77). |
| `SOURCE_SHA256SUMS.txt` | 121 -> 122 entries: new P2-12 gate entry and the updated P2-11 gate entry. |
| `.openrecomp-phase2/evidence/P2-12/` | This evidence bundle. |
| `.openrecomp-phase2/{STATE,HANDOFF,STAGE_QUEUE}.md` | P2-12 PASS; P2-12 COMPLETE, P2-13 NEXT. |

No implementation source (`openrecomp/*.py`) was modified for P2-12; the stage
reuses the existing pipeline and the P2-11 emitter memory extension.

### Cross-stage test adjustment (explained, with replacement coverage)

`tools/test_mips32_calls_memory_v1.py` (P2-11) contained
`no-p2-12-evidence-directory`, a cross-stage guard asserting that P2-12 evidence
must not exist. It necessarily fails once the authorized P2-12 stage writes its
required evidence, and it encoded build state rather than a P2-11 property. It
was replaced with `no-p2-12-switch-emission-in-p2-11` — a genuine P2-11 property
that remains true: the P2-11 bounded fixture's generated host source contains no
`switch (` dispatch lowering. The test count is unchanged at 77. P2-11 semantics,
observable and committed evidence are otherwise unmodified; only that gate's
stdout hash changed
(`c0b39d65...` -> `35e92fa780eb842ee060edd747fd33d3e919699e7a753ccf864d88fb157e9b81`).

## Fixture

- architecture: `mips32-bounded-v1`, little-endian, instruction width 4 bytes
- entry `0x1000` (`fn_1000`), leaf `0x1080` (`fn_1080`), dispatch `0x1054`
- 35 instructions, 140 bytes; SHA-256
  `2e3309f310a6f23c145ba7b95a22f10e3d81f32ec19afb966a9044395c066c84`
- synthetic/original; words are recorded constants and re-derived by a local
  encoder inside the gate (cross-checked field by field)

```text
0x1000  0x241d0100  addiu sp, r0, 0x100
0x1004  0x27bdfff8  addiu sp, sp, -8
0x1008  0xafbf0004  sw ra, 4(sp)
0x100c  0x24020000  addiu r2, r0, 0
0x1010  0x24030000  addiu r3, r0, 0
0x1014  0x24080001  addiu r8, r0, 1
0x1018  0x24630001  addiu r3, r3, 1        (loop: i += 1)
0x101c  0x00431021  addu r2, r2, r3        (acc += i)
0x1020  0x28640005  slti r4, r3, 5
0x1024  0x1480fffc  bne r4, r0, 0x1018     (back edge)
0x1028  0x00000000  nop (delay slot)
0x102c  0x24440000  addiu r4, r2, 0        (arg = acc)
0x1030  0x0c000420  jal 0x1080             (direct call)
0x1034  0x00000000  nop (delay slot)
0x1038  0x8fbf0004  lw ra, 4(sp)           (restore ra)
0x103c  0x24090001  addiu r9, r0, 1
0x1040  0x1100000a  beq r8, r0, 0x106c     (structural edge to case B; not taken)
0x1044  0x00000000  nop (delay slot)
0x1048  0x11200004  beq r9, r0, 0x105c     (structural edge to case A; not taken)
0x104c  0x00000000  nop (delay slot)
0x1050  0x2405105c  addiu r5, r0, 0x105c   (selector = case A)
0x1054  0x00a00008  jr r5                  (bounded dispatch)
0x1058  0x00000000  nop (delay slot)
0x105c  0x24060064  addiu r6, r0, 100      (case A)
0x1060  0x00c23021  addu r6, r6, r2
0x1064  0x0800041d  j 0x1074
0x1068  0x00000000  nop (delay slot)
0x106c  0x240600c8  addiu r6, r0, 200      (case B)
0x1070  0x00c23021  addu r6, r6, r2
0x1074  0x24c70005  addiu r7, r6, 5        (end)
0x1078  0x03e00008  jr ra
0x107c  0x00000000  nop (delay slot)
0x1080  0x24420005  addiu r2, r2, 5        (leaf)
0x1084  0x03e00008  jr ra
0x1088  0x00000000  nop (delay slot)
```

The two not-taken branches are structural reachability edges for the dispatch
targets (the neutral CFG gives an indirect jump no resolved edges). At runtime
both are not taken and control reaches the `jr r5` bounded switch, which
dispatches to case A. This is documented and deterministic.

## Independent expected observable

1. **Explicit derivation.** Loop `i` runs 1..5, `acc = 15`; `jal` leaf adds 5 so
   `r2 = 20`; `$ra` restored to `0`; both structural branches are not taken;
   `r5 = 0x105c`; the bounded switch dispatches to case A:
   `r6 = 100 + 20 = 120`; `j end`; `r7 = 120 + 5 = 125`; `jr $ra` (`$ra = 0`)
   halts. `sp = 0x100 - 8 = 248`.
2. **Tiny independent reference interpreter.** True MIPS32 with delay slots,
   `jal`/`jr $ra` linkage, `lw`/`sw`, bounded little-endian RAM.
   Result: `r2=20 r3=5 r4=15 r5=0x105c r6=120 r7=125 r8=1 r9=1 sp=248 ra=0`.

## Pipeline stages traversed

| Stage | Status | Evidence |
| --- | --- | --- |
| P2-01 ProgramModel | APPLIED | Two functions `fn_1000@0x1000`, `fn_1080@0x1080`. |
| P2-02 CFG | APPLIED | 14 blocks; loop back edge `blk_1018 -> blk_1018`; branch edges to both dispatch targets; `CALL_RETURN` continuation at `0x1034`; unresolved `INDIRECT` dispatch edge. Fingerprint `8c288d4190fd6ad10ffcad27c2ed2e92c48dbef91adb1d610346743d875946e1`. |
| P2-03 Function discovery | APPLIED | Both functions; four unreachable post-return/post-jump delay slots preserved unowned. Fingerprint `a7bbc09af85ea215ef30307793b268a6c8b7abb3385e2efaf0a71c12fa311d74`. |
| P2-04 Call graph | APPLIED | `fn_1000 -> fn_1080` `INTERNAL_DIRECT`. Fingerprint `55a0b6e30b556e27a6f16bc1a30075bf62cad700c40d8e679a4413d551b20c6c`. |
| P2-05 Translation units | APPLIED | `tu_fn_1000`, `tu_fn_1080`. Fingerprint `00475b0e94487229a2a53933a0da52cf65ee4fbcb15e67d614002f49f8fdf486`. |
| P2-06 Indirect control flow | APPLIED | Dispatch `0x1054` = `RESOLVED`/`EXACT_TARGET_SET` targets `(0x105c, 0x106c)`; two `RETURN_LIKE` `jr ra` sites. Fingerprint `a9b418af2c13693f0f4e2889921307fc77c754ab795fc647309597320ce849df`. |
| P2-07 Host emitter | APPLIED | Loop branch emission, direct call, `switch` with two cases and a fail-closed `default`, `sw`/`lw` through the P2-08 boundary. Generated source `36ba17c8a1edcd22148c9789abe9348f68e9b6cd02912a9a94481de93a3009c9`. |
| P2-08 Generic runtime ABI | APPLIED | Checked 32-bit memory read/write for the `$ra` save/restore. |
| P2-09 Deterministic build pipeline | APPLIED | Two independent `/Brepro` builds; `EXECUTABLE_REPRODUCIBLE`. |

## Bounded switch / direct-table proof

- Evidence: `EXACT_TARGET_SET` targets `{0x105c, 0x106c}` for the `jr r5` at
  `0x1054`; no target is inferred from the fixture and none is guessed.
- Lowering: `switch ((uint64_t)(g_r[6])) { case UINT64_C(4188): goto bb_blk_105c;
  case UINT64_C(4204): goto bb_blk_106c; default: or_fail(...); return; }`.
- Runtime: selector `0x105c` takes case A; native result `r6 = 120` proves the
  switch path (a fall-through/default would have produced a different or failed
  result).
- Negative: `BOUNDED_CANDIDATES` is never promoted (boundary or `REJECT`);
  without evidence the site is `UNRESOLVED_INDIRECT_JUMP` (boundary or `REJECT`).

## Deterministic native build

| Item | Value |
| --- | --- |
| runtime-support source | `5eeb0d37d34a1f20b2646519f7dac43e196d3bfe736fbf714f4c64fefeb3512a` |
| `generated.obj` | `14e89f593abe203b55e23498cdcaa6a029bd842eddc7d8109a043652e0df3da6` |
| `runtime_support.obj` | `6b22d290f6215ac75f3b6768721db420199507000376878b02e62b24832b725f` |
| `program.exe` | `3d92fc274ddb94190292fb9630243f7b064a42733406ecaf7cab2d85a5f2f266` |
| build manifest | `45ad066d75d2be84753214d143dc3084769965afb7b6f41d85e4bb1045d13eac` |
| compiler / linker | clang-cl 22.1.8 / lld-link 22.1.8, target `x86_64-pc-windows-msvc` |
| flags | `/c /Brepro /Od /std:c11 /nologo` and `/Brepro /nologo` |
| independent builds | 2 (isolated directories; source regenerated per run) |
| reproducibility | source IDENTICAL, manifest IDENTICAL, objects IDENTICAL, executable IDENTICAL -> `EXECUTABLE_REPRODUCIBLE` |

No binary post-processing, no timestamp editing and no post-link normalization.

## Native execution and comparison

```text
expected:  failed=0, error=, regs 0,20,248,5,0,15,4188,120,125,1,1
actual:    identical
returncode: 0;  secondary run identical
EXPECTED == ACTUAL: YES
guest registers: r2=20 r3=5 r4=15 r5=0x105c r6=120 r7=125 r8=1 r9=1 sp=248 ra=0
```

## Fail-closed coverage

- out-of-set runtime dispatch target (`r5 = 0x2000`) -> switch `default` ->
  explicit failure (`failed=1`, `error=indirect target outside proven set`)
- `BOUNDED_CANDIDATES` never promoted -> boundary or `REJECT`
- no dispatch evidence -> `UNRESOLVED_INDIRECT_JUMP` boundary or `REJECT`
- missing semantics rule -> `HostEmitterError`
- external direct call target -> `HostEmitterError` (no invented callee)
- malformed `HostLoad` operands -> `HostEmitterError`
- unsupported opcode -> adapter `DecodeError`
- misaligned entry / empty region -> `CFGError`

## Tests / coverage

```text
python tools/test_mips32_direct_cfg_v1.py
OPENRECOMP_MIPS32_DIRECT_CFG_V1=PASS tests=96
```

Coverage: fixture identity and encoder cross-checks for `addiu`/`sw`/`lw`/
`addu`/`slti`/`bne`/`beq`/`j`/`jal`/`jr`; decode targets and flow; CFG block
count, loop back edge, branch targets, call continuation, jump and fallthrough
edges, unresolved dispatch; two functions with loop ownership and unowned delay
slots; call graph and units; P2-06 dispatch `RESOLVED` targets plus two returns,
no-evidence fail-closed and bounded-not-promoted; switch emission with both cases
and fail-closed default, loop/call/memory/return emission, determinism, no
hard-coded result, no pointer casts; independent reference registers and
derivations; deterministic two-build reproducibility and manifest non-leakage;
native execution stability, `expected == actual`, guest register mapping; runtime
out-of-set dispatch fail-closed; and the fail-closed rejections above.

## Upstream regression totals

```text
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
PASS source-integrity  verified 122 manifest entries
```

## Source integrity

`SOURCE_SHA256SUMS.txt` 121 -> 122 entries via `update_sums.py`:
`tools/test_mips32_direct_cfg_v1.py` added
(`cf3b94cdae2d5649489bca2126d852cf582a5844abbe210fb37e904f41463bfc`) and
`tools/test_mips32_calls_memory_v1.py` updated for the explained guard change
(`ca908ddc538bebc150c6f7c12dfb0c039510c1311d0579ed2ad8b19423a4dae0`). No
unrelated hash changed.

## Determinism

- P2-12 gate stdout, two consecutive runs, byte-identical:
  `sha256 d01ec8f0bd5391684a1f18d6d3d3197b449e67021eae700c053573130a207100`.
- Fixture `2e3309f3...`; generated source `36ba17c8...`; manifest `45ad066d...`;
  executable `3d92fc27...`; all stable across runs.

## Phase-2 marker decision

`OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=NOT_PROVEN` is **unchanged**.
`STAGE_QUEUE.md` reserves the final marker for the `P2-99 Final verdict` outcome,
not for any single intermediate stage. The narrower proven claim is
`OPENRECOMP_MIPS32_DIRECT_CFG_V1=PASS` for this one bounded synthetic fixture.

## Known limitations

- Proves only this 35-instruction synthetic fixture; not full MIPS32 support, not
  PS2 support and not guest/host equivalence.
- The bounded dispatch target set is supplied by explicit evidence; the pipeline
  does not recover indirect targets by analysis.
- Call/return is modeled structurally; the fixture's `$ra` save/restore makes
  that agree with true MIPS32 for this case. General `$ra` dataflow is not
  recovered.
- Delay slots are not first-class CFG semantics; fixtures use `nop` delay slots
  and unreachable delay-slot blocks remain unowned residual evidence.
- Only word-width aligned `lw`/`sw` are covered; emitted functions remain void
  with no argument/return ABI.
- `openrecomp/*.py` remain outside `SOURCE_SHA256SUMS.txt` (pre-existing
  `update_sums.py` glob gap).
- Toolchain-gated Phase-1 gates remain skipped on this host.

## Explicit non-claims

No arbitrary MIPS32 equivalence, full MIPS32 support, full PS2 support,
commercial-game recompilation or console compatibility. P2-13 and later stages
were not started. The final `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS`
marker is not claimed.

## Boundary rule

No P2-12 git commit was created. The coherent P2-12 changes are left in the
working tree for independent review and boundary commit.

## Final verdict

`PASS` — a synthetic/original MIPS32 fixture with a counted loop, conditional
branches, a direct call, `jr $ra` returns and a bounded indirect dispatch
traverses the real Phase-2 pipeline to a reproducible native executable whose
independently derived expected observable exactly matches the actual native
observable, with out-of-set dispatch and evidence-free indirect control flow
failing closed.

OPENRECOMP_P2_12=PASS
OPENRECOMP_MIPS32_DIRECT_CFG_V1=PASS tests=96
