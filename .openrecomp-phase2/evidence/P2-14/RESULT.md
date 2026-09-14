# P2-14 — Larger MIPS32 open fixture V1

VERDICT: `PASS`

STAGE MARKER: `OPENRECOMP_P2_14=PASS`
GATE MARKER: `OPENRECOMP_MIPS32_LARGER_FIXTURE_V1=PASS tests=82`

## Baseline

| Item | Value |
| --- | --- |
| Stage | `OPENRECOMP_P2_14_MIPS32_LARGER_OPEN_FIXTURE_V1` |
| Branch | `phase2/opencode-v1` |
| Starting commit | `c32a766a0b6499a239fcd4af351a73f1c172a1be` (`c32a766 phase2: complete P2-13 runtime host boundary`; `HEAD` at stage start) |
| Phase-1 freeze | tag `openrecomp-phase1-pass` -> `46c2f971e1a42cf49bd936bad94697b81bf31002` (unchanged) |
| Prior gates | P2-13 `80`, P2-12 `96`, P2-11 `77`, P2-10 `108`, P2-09 `120`, P2-08 `169`, P2-07 `106`, P2-06 `134`, P2-05 `104`, P2-04 `61`, P2-03 `67`, P2-02 `82`, P2-01 `49` |

## Bounded acceptance contract

1. **Behavior proven**: the full Phase-2 pipeline on a larger synthetic/open
   MIPS32 program, with **deterministic recompilation** (two independent
   structural pipeline runs produce identical fingerprints and byte-identical
   emitted source; P2-09 performs two independent builds) and **replay**
   (repeated native execution produces byte-identical stdout).
2. **Input**: one synthetic/original 4-function, 57-instruction fixture
   (228 bytes); no commercial ROM/ELF/game bytes.
3. **Applicable stages**: P2-01..P2-09 (see table); no runtime host service is
   used, so P2-08 is exercised only through the always-declared memory boundary.
4. **Semantics exercised**: `addiu`, `addu`, `slt`, `lw`, `sw`, `beq`, `bne`,
   `j`, `jal`, `jr`, `nop`; a counted loop, nested calls, nested stack frames,
   memory-resident accumulator and maximum tracking, and structural returns.
5. **Runtime involvement**: `or_rt_memory_read`/`or_rt_memory_write` through the
   generic runtime ABI; no host service is invoked.
6. **Expected observable**: `total = sum(4i+1, i=1..20) = 860`,
   `best = max(4i+1) = 81`, observable `total + best = 941` in `r6`/`r10`,
   `i = 20`, restored `sp = 0x400` and `ra = 0`.
7. **Independent derivation**: explicit mathematical derivation plus a tiny
   independent true-MIPS32 reference interpreter (delay slots, `jal`/`jr $ra`,
   `lw`/`sw`, bounded RAM). The native result is never used to derive the
   expectation.
8. **Failure cases**: missing semantics rule, guest memory without a runtime
   ABI, external direct call target, unsupported opcode, misaligned entry, empty
   region, and evidence-free indirect returns remaining fail-closed.
9. **Reproducibility**: two independent `/Brepro` builds; a level is claimed
   only when byte identity is observed.
10. **Scope/non-claims**: proves only this bounded synthetic fixture. Not full
    MIPS32 support, not PS2 support and not guest/host equivalence.

## Objective

Prove a larger synthetic/open MIPS32 program with deterministic recompilation
and replay.

## Files created/modified

| File | Change |
| --- | --- |
| `tools/test_mips32_larger_fixture_v1.py` | New dedicated P2-14 gate (82 checks), with deterministic evidence output. |
| `tools/test_runtime_host_boundary_v1.py` | One obsolete cross-stage guard replaced (count unchanged at 80). |
| `SOURCE_SHA256SUMS.txt` | 123 -> 124 entries: new P2-14 gate entry and the updated P2-13 gate entry. |
| `.openrecomp-phase2/evidence/P2-14/` | This evidence bundle. |
| `.openrecomp-phase2/{STATE,HANDOFF,STAGE_QUEUE}.md` | P2-14 PASS; P2-14 COMPLETE, P2-20 NEXT. |

No implementation source (`openrecomp/*.py`) was modified; the stage reuses the
existing pipeline, emitter and runtime ABI.

### Cross-stage test adjustment (explained, with replacement coverage)

`tools/test_runtime_host_boundary_v1.py` (P2-13) contained
`no-p2-14-evidence-directory`, a cross-stage guard asserting P2-14 evidence must
not exist. It necessarily fails once the authorized P2-14 stage writes its
required evidence, and it encoded build state rather than a P2-13 property. It
was replaced with `no-guest-memory-access-in-p2-13` — a genuine P2-13 property
that remains true: the P2-13 bounded fixture's generated host source performs no
guest memory access (`or_rt_memory_read(or_addr` / `or_rt_memory_write(or_addr`
absent). The test count is unchanged at 80. P2-13 semantics, observable and
committed evidence are otherwise unmodified; only that gate's stdout hash
changed (`8617ed85...` ->
`cf94b655d95dba72840823a9212b0d022d577bf7c73f9fe58fc8e864e464597f`).

## Fixture

- architecture: `mips32-bounded-v1`, little-endian, instruction width 4 bytes
- entry `0x1000`; functions `main@0x1000`, `outer@0x1084`, `inner@0x10ac`,
  `bigger@0x10c0`
- 57 instructions, 228 bytes; SHA-256
  `1c233f56528cb3fe20a7b806ce40e8bef6fc66a8cf8c0fd15d8b7b49bce547eb`
- synthetic/original; assembled deterministically by a two-pass assembler inside
  the gate (recorded words are cross-checked against the assembler output)

Program shape:

```text
main:  frame; total=0; best=0; i=0; N=20
loop:  while i < N:
           i += 1
           total += outer(i)
           best = bigger(best, outer(i))
after: r6 = total + best; r10 = r6; restore sp/ra; return
outer(x): frame; r2 = inner(x) + x; restore sp/ra; return      (4x + 1)
inner(x): r2 = 3x + 1; return
bigger(a,b): r2 = max(a,b); return
```

## Independent expected observable

1. **Explicit derivation.** `outer(x) = inner(x) + x = (3x + 1) + x = 4x + 1`.
   `total = Σ_{i=1..20}(4i + 1) = 4·210 + 20 = 860`;
   `best = max(4i + 1) = 81`; observable `= total + best = 941`.
2. **Tiny independent reference interpreter.** True MIPS32 with delay slots,
   `jal`/`jr $ra`, `lw`/`sw` and a bounded little-endian RAM. It executes 800
   steps and produces `r6 = r10 = 941`, `i = 20`, `sp = 0x400`, `ra = 0`.
3. The native result is never used to derive the expected value.

Note: the saved-`$ra` bytes in the runtime RAM differ between the structural
host call model and true MIPS32 (the host model does not link `$ra` on `jal`).
The register observable is unaffected because every function restores `$ra`
before its structural return; the RAM checksum is therefore **not** part of the
observable. This is an explicit, documented limitation carried from P2-11.

## Pipeline stages traversed

| Stage | Status | Evidence |
| --- | --- | --- |
| P2-01 ProgramModel | APPLIED | Four functions `fn_1000`, `fn_1084`, `fn_10ac`, `fn_10c0`. |
| P2-02 CFG | APPLIED | 18 blocks; loop conditional (`blk_1020`), back jump (`blk_1054 -> loop`), three call continuations, five unresolved return edges. Fingerprint `428351e6f2702c9843a1829e46aa75209d05f22ac9af19c5121cb9246563127d`. |
| P2-03 Function discovery | APPLIED | Four functions; six unreachable delay-slot blocks preserved unowned. Fingerprint `f8f14c28185f357938d2d6cf191c2d1c5fa2b2576e1ef1b113563b3982686570`. |
| P2-04 Call graph | APPLIED | Three `INTERNAL_DIRECT` edges: `fn_1000 -> fn_1084`, `fn_1000 -> fn_10c0`, `fn_1084 -> fn_10ac`. Fingerprint `a5f513d18158ea74d34aebde5117af284e16dead64d6ed2e8b81712bc46d00ac`. |
| P2-05 Translation units | APPLIED | Four units with call edges per unit `[2, 1, 0, 0]`. Fingerprint `54cad08cddac2b9cce69eb49736b127735c6e07b5287f41b88f40d5be2358f84`. |
| P2-06 Indirect control flow | APPLIED | Five `RETURN_LIKE` `jr ra` sites, no guessed targets; without evidence all remain `UNRESOLVED_INDIRECT_JUMP`. Fingerprint `31e2d41971c428688d23f23a626ad77e637824a8b1216c0bcffdba7e861b2b71`. |
| P2-07 Host emitter | APPLIED | Four prototypes/definitions, three internal calls, loop back-edge `goto`, `lw`/`sw` through the P2-08 boundary, fail-closed memory branches. Generated source `25d8d85ff88d2009443a6c67db40855df5e0876cb2b0aef8505d12d500204203`. |
| P2-08 Generic runtime ABI | APPLIED | Checked 32-bit memory read/write for the accumulator and `$ra` save/restore. |
| P2-09 Deterministic build pipeline | APPLIED | Two independent `/Brepro` builds; `EXECUTABLE_REPRODUCIBLE`. |

## Deterministic recompilation

Two independent structural pipeline runs (decode -> CFG -> discovery -> call
graph -> units -> classification -> emission) produced identical fingerprints
and byte-identical generated source:

```text
cfg       428351e6... identical
functions f8f14c28... identical
callgraph a5f513d1... identical
units     54cad08c... identical
indirect  31e2d419... identical
source    25d8d85f... byte-identical
```

See `recompilation.txt`.

## Deterministic replay

The built native executable was executed three times; stdout was byte-identical
in all runs:

```text
executable sha256: 1e81bf8cd32b60cd5b3acae26c8f9dc23c0f801cf46b0c49ccb348ebc5eb2ab4
run 1/2/3 stdout sha256: 5a44a08c3bc1fd16044fa4309ed128f277586184f6661b6757b68e69a1517baa
returncode: 0
observable r10: 941
```

See `replay.txt`.

## Deterministic native build

| Item | Value |
| --- | --- |
| runtime-support source | `5eeb0d37d34a1f20b2646519f7dac43e196d3bfe736fbf714f4c64fefeb3512a` |
| `generated.obj` | `6a4bc561646f81ada045458b04fd0574dcbed7cf120fd532e291fe0f9c4a0ea1` |
| `runtime_support.obj` | `6b22d290f6215ac75f3b6768721db420199507000376878b02e62b24832b725f` |
| `program.exe` | `1e81bf8cd32b60cd5b3acae26c8f9dc23c0f801cf46b0c49ccb348ebc5eb2ab4` |
| build manifest | `ecd6bf94389f2a56341b82b93e729b561e421b6981e830893770da4cc80c9269` |
| compiler / linker | clang-cl 22.1.8 / lld-link 22.1.8, target `x86_64-pc-windows-msvc` |
| flags | `/c /Brepro /Od /std:c11 /nologo` and `/Brepro /nologo` |
| independent builds | 2 (isolated directories; source regenerated per run) |
| reproducibility | source IDENTICAL, manifest IDENTICAL, objects IDENTICAL, executable IDENTICAL -> `EXECUTABLE_REPRODUCIBLE` |

No binary post-processing, no timestamp editing and no post-link normalization.

## Native execution and comparison

```text
expected:  failed=0, error=, regs 0,941,81,1024,860,0,860,81,941,0,20
actual:    identical
returncode: 0
EXPECTED == ACTUAL: YES
```

`reg[1]` is guest `r10` (observable 941), `reg[2]`/`reg[7]` are `r2`/`r5`
(81), `reg[4]`/`reg[6]` are `r3`/`r4` (860), `reg[10]` is `r9` (20).

## Fail-closed coverage

- missing semantics rule -> `HostEmitterError`
- guest memory without a configured runtime ABI -> `HostEmitterError`
- external direct call target -> `HostEmitterError` (no invented callee)
- evidence-free indirect returns -> `UNRESOLVED_INDIRECT_JUMP`, never guessed
- unsupported opcode -> adapter `DecodeError`; misaligned entry / empty region ->
  `CFGError`

## Tests / coverage

```text
python tools/test_mips32_larger_fixture_v1.py
OPENRECOMP_MIPS32_LARGER_FIXTURE_V1=PASS tests=82
```

Coverage: deterministic assembler and fixture identity; decode counts/targets;
CFG block count, loop conditional, back jump, call continuations; four
functions, call graph edges/kind, four units with per-unit call edges; five
`RETURN_LIKE` sites and evidence-free fail-closed; host emission (prototypes,
calls, loop back-edge, memory, fail-closed branches, determinism, no hard-coded
observable, no pointer casts); independent reference registers and derivation;
deterministic recompilation (all fingerprints + byte-identical source);
deterministic two-build reproducibility and manifest non-leakage; native
execution, three-replay byte identity, `expected == actual`; and the fail-closed
rejections above.

## Upstream regression totals

```text
OPENRECOMP_RUNTIME_HOST_BOUNDARY_V1=PASS tests=80
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
PASS source-integrity  verified 124 manifest entries
```

## Source integrity

`SOURCE_SHA256SUMS.txt` 123 -> 124 entries via `update_sums.py`:
`tools/test_mips32_larger_fixture_v1.py` added
(`6e32113934e051822d8d278f4949ced683feeb3e0b1c597aa93d566208bf19c5`) and
`tools/test_runtime_host_boundary_v1.py` updated for the explained guard change
(`e45a97ef69b0520aa8db04d9fa3767dfb82675c4c3e909e4280d6e7a2197a076`). No
unrelated hash changed.

## Determinism

- P2-14 gate stdout, two consecutive runs, byte-identical:
  `sha256 115c2c8a69ed3a9ebb33e990ffa9350a970e8c6f2ea258a40187365baaf6d3e9`.
- Fixture `1c233f56...`; generated source `25d8d85f...`; manifest `ecd6bf94...`;
  executable `1e81bf8c...`; replay stdout `5a44a08c...`; all stable.

## Phase-2 marker decision

`OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=NOT_PROVEN` is **unchanged**.
`STAGE_QUEUE.md` reserves the final marker for the `P2-99 Final verdict` outcome,
not for any single intermediate stage. The narrower proven claim is
`OPENRECOMP_MIPS32_LARGER_FIXTURE_V1=PASS` for this one bounded synthetic
fixture.

## Known limitations

- Proves only this 57-instruction synthetic fixture; not full MIPS32 support, not
  PS2 support and not guest/host equivalence.
- The neutral CFG/emitter do not model delay slots as first-class semantics;
  fixtures use `nop` delay slots and unreachable delay-slot blocks are preserved
  as unowned residual evidence.
- Call/return is modeled structurally; saved-`$ra` memory bytes differ from true
  MIPS32, which is why the RAM checksum is not part of the observable. General
  `$ra` dataflow is not recovered.
- Only word-width aligned `lw`/`sw` are covered; emitted functions remain void
  with no argument/return ABI.
- No runtime host service is invoked in this fixture (see P2-13 for the
  runtime-host boundary proof).
- `openrecomp/*.py` remain outside `SOURCE_SHA256SUMS.txt` (pre-existing
  `update_sums.py` glob gap).
- Toolchain-gated Phase-1 gates remain skipped on this host.

## Explicit non-claims

No arbitrary MIPS32 equivalence, full MIPS32 support, full PS2 support,
commercial-game recompilation or console compatibility. P2-20 and later stages
were not started. The final `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS`
marker is not claimed.

## Boundary rule

No P2-14 git commit was created. The coherent P2-14 changes are left in the
working tree for independent review and boundary commit.

## Final verdict

`PASS` — a synthetic/original 4-function, 57-instruction MIPS32 program with a
counted loop, nested calls, nested stack frames and memory-resident accumulation
traverses the real Phase-2 pipeline; two independent recompilations produce
identical structures and byte-identical source; two independent `/Brepro` builds
produce byte-identical artifacts; three native replays produce byte-identical
stdout; and the independently derived expected observable (941) exactly matches
the actual native observable.

OPENRECOMP_P2_14=PASS
OPENRECOMP_MIPS32_LARGER_FIXTURE_V1=PASS tests=82
