# P2-10 — Tiny MIPS32 end-to-end proof V1

VERDICT: `PASS`

STAGE MARKER: `OPENRECOMP_P2_10=PASS`
GATE MARKER: `OPENRECOMP_MIPS32_END_TO_END_V1=PASS tests=108`

## Baseline

| Item | Value |
| --- | --- |
| Stage | `OPENRECOMP_P2_10_TINY_MIPS32_END_TO_END_PROOF_V1` |
| Branch | `phase2/opencode-v1` |
| Starting commit | `161893389cca5a30aa462670f19ecabfc1be679d` (`1618933 phase2: complete P2-09 deterministic build pipeline`; `HEAD` at stage start) |
| Phase-1 freeze | tag `openrecomp-phase1-pass` -> `46c2f971e1a42cf49bd936bad94697b81bf31002` (unchanged) |
| Prior gates | P2-09 `120`, P2-08 `169`, P2-07 `106`, P2-06 `134`, P2-05 `104`, P2-04 `61`, P2-03 `67`, P2-02 `82`, P2-01 `49` |

## Objective

The smallest rigorous deterministic MIPS32 end-to-end proof that exercises the
real Phase-2 pipeline from a synthetic/original guest fixture through generated
native host execution:

```text
fixture bytes -> adapters.mips32 decode -> P2-01 ProgramModel -> P2-02 CFG
-> P2-03 function discovery -> P2-04 call graph -> P2-05 translation units
-> P2-06 indirect-control-flow classification -> P2-07 host emitter
-> P2-09 deterministic build pipeline -> native executable -> execution
-> expected vs actual observable
```

No commercial ROM/ELF/game bytes are used. No second recompilation path was
added: the proof reuses the frozen P2 modules and adds only the dedicated gate
and its evidence.

## Fixture

- architecture: `mips32-bounded-v1` (from `adapters/mips32.info`), little-endian
- instruction width: 4 bytes; base/entry address: `0x1000`
- 13 instructions, 52 bytes; SHA-256
  `b33b597c28eb7f7239ee5079728c7f3e447387d4ed34525c445cf8c1e9234975`
- synthetic/original; constructed deterministically in
  `tools/test_mips32_end_to_end_v1.py`

```text
0x1000  0x24020007  addiu r2, r0, 7
0x1004  0x24030005  addiu r3, r0, 5
0x1008  0x10430002  beq r2, r3, 0x1014
0x100c  0x00000000  nop (delay slot)
0x1010  0x24040003  addiu r4, r0, 3
0x1014  0x24840001  addiu r4, r4, 1
0x1018  0x14820001  bne r4, r2, 0x1020
0x101c  0x00000000  nop (delay slot)
0x1020  0x00822821  addu r5, r4, r2
0x1024  0x00a33023  subu r6, r5, r3
0x1028  0x00c2382a  slt r7, r6, r2
0x102c  0x03e00008  jr r31
0x1030  0x00000000  nop (delay slot)
```

Guest instructions exercised: `addiu`, `beq`, `bne`, `addu`, `subu`, `slt`,
`nop`, `jr`. Guest semantic operations: immediate add, register add, subtract,
signed less-than compare, conditional branch (taken and not-taken), register
copy via `addu rd, rs, r0`, and structural return.

## Independent expected observable

Derived without running the generated native executable:

1. **Explicit mathematical derivation.** `r2=7`, `r3=5`; `beq(7,5)` is false, so
   the delay slot runs and control falls through to `0x1010`: `r4=3`, then
   `r4=r4+1=4`. `bne(4,7)` is true, so after the delay slot control goes to
   `0x1020`: `r5=r4+r2=4+7=11`; `r6=r5-r3=11-5=6`; `slt(6,7)=1` so `r7=1`.
   `jr r31` with `r31=0` halts. Expected guest registers:
   `r2=7 r3=5 r4=4 r5=11 r6=6 r7=1 r31=0`.
2. **Tiny independent reference interpreter.** `reference_execute()` in the gate
   is a separate decoder/interpreter for the documented subset (including
   architectural delay slots) written from the ISA description, not from the
   generated host code. It produces the same register values.
3. **Phase-1 oracle cross-check.** `tools/mips32_oracle_v1.py` (frozen Phase-1
   reference) is run on two reduced synthetic ELF fixtures:
   `taken: r2=5 r3=5 operations=6`, `not_taken: r2=9 r3=9 operations=7`.

Independence boundary: the expected values are computed before the native
executable is built or run, from (1) arithmetic derivation, (2) an independent
interpreter, and (3) the frozen Phase-1 oracle. The native result is never used
to derive the expected result.

Expected native stdout (canonical register dump):
`failed=0`, `reg[0]=0`, `reg[1]=7`, `reg[2]=5`, `reg[3]=0`, `reg[4]=4`,
`reg[5]=11`, `reg[6]=6`, `reg[7]=1`.

## Pipeline stages traversed

| Stage | Status | Evidence |
| --- | --- | --- |
| P2-01 ProgramModel | APPLIED | One function `fn_1000@0x1000`; source metadata (architecture, 32-bit width, little-endian, fixture SHA-256) recorded. |
| P2-02 CFG | APPLIED | 6 blocks; branch taken/not-taken, fallthrough and unresolved indirect edges; no phantom/missing edges. Fingerprint `d5b1836baff0d23b496062b4028e8cdc5a42365816bec7a82f8eae4c2c87e114`. |
| P2-03 Function discovery | APPLIED | Single `fn_1000`; ownership `blk_1000/100c/1014/101c/1020`; `blk_1030` (post-return delay slot) preserved as unowned residual. Fingerprint `c51494362101c6b68f6ef538f22f370fcf1cdca595672b43789df66b729ca595`. |
| P2-04 Call graph | APPLIED | One node `fn_1000`, zero edges (truthful: the fixture has no calls). Fingerprint `b4f4c6d4e46321ab2841196bb5e554e86454cf1ab5ccb54321c2906cfc36e31c`. |
| P2-05 Translation units | APPLIED | One unit `tu_fn_1000`; unowned block preserved. Fingerprint `5560c00386b8650ebbc840ec9bb94e5a4c2a61598346157654456e1fb8a6aace`. |
| P2-06 Indirect control flow | APPLIED | Exactly one `INDIRECT_JUMP` site `0x102c` (`jr r31`) classified `RETURN_LIKE` with `STRUCTURAL_RETURN_EVIDENCE`, `targets=[]`. Without evidence it fails closed as `UNRESOLVED_INDIRECT_JUMP` with no invented target. Fingerprint `4cf534f6052806e7e062b05a6cda04c420f6541e49219f05dbdc98902cacd791`. |
| P2-07 Host emitter | APPLIED | Deterministic portable C emitted with explicit `(architecture, op)` semantics rules. Generated source SHA-256 `8570ea4a11321118a3fff270e0dc9756d2a4ee7a52421ece1d2d892384118fbb`. No final observable hard-coded. |
| P2-08 Generic runtime ABI | NOT_APPLICABLE_FOR_FIXTURE | The fixture requires no host service or runtime-mediated operation; no external call exists. `runtime_abi=None`; the generated C contains no `or_rt_*` surface. |
| P2-09 Deterministic build pipeline | APPLIED | Two independent `/Brepro` builds; manifest `openrecomp-build-manifest-v1`; `EXECUTABLE_REPRODUCIBLE`. |

## Generated host source

- SHA-256 `8570ea4a11321118a3fff270e0dc9756d2a4ee7a52421ece1d2d892384118fbb`
- register file order: `r0 r2 r3 r31 r4 r5 r6 r7`
- repeated emission from identical structural input is byte-identical
- contains `or_mask(32u)`, add/sub, signed compare, branch `goto`s and
  `return;` for the `RETURN_LIKE` site
- does **not** contain the final observable literals (`UINT64_C(11)` /
  `UINT64_C(6)` absent)

## Deterministic native build

| Item | Value |
| --- | --- |
| runtime-support source | `12db122f2e390c9989dcd514f98d71b23bff90c877a6bff998bc84f78b033c81` |
| `generated.obj` | `26a41c3e84b8cb2c997bdf11a9f305a36e1aad2c4a1121b18c8fa9fbea5013a7` |
| `runtime_support.obj` | `8c01d6d2a8722cf2cc24f2015b94ee6401dd5fab148626c0438ac0a818547050` |
| `program.exe` | `f94c95d2e86fca83f56e5e87a98bccaa1e2a4ced3fd9222aef29608592810f4e` |
| build manifest | `cd4ebe292c94025394549f5d566208da7331eb1900c7b7d08d0f88e3701b887c` |
| compiler | `clang-cl.exe` 22.1.8, target `x86_64-pc-windows-msvc` |
| linker | `lld-link.exe` (LLD 22.1.8) |
| compile flags | `/c /Brepro /Od /std:c11 /nologo` |
| link flags | `/Brepro /nologo` |
| independent builds | 2 (isolated directories; source regenerated per run) |
| reproducibility | source IDENTICAL, manifest IDENTICAL, objects IDENTICAL, executable IDENTICAL -> `EXECUTABLE_REPRODUCIBLE` |

No binary post-processing, no timestamp editing and no post-link normalization
were used.

## Native execution and comparison

```text
expected observable:  failed=0, reg[0..7] = 0,7,5,0,4,11,6,1
actual observable:    failed=0, reg[0..7] = 0,7,5,0,4,11,6,1
returncode:           0
secondary run:        identical stdout (execution stability)
EXPECTED == ACTUAL:   YES
guest registers:      r2=7 r3=5 r4=4 r5=11 r6=6 r7=1 r31=0
```

This is a bounded synthetic build/execution proof, **not** guest/host
equivalence and not full MIPS32 support.

## Fail-closed coverage

Malformed/truncated and empty fixtures, unsupported opcode, branch target
outside the closed region, misaligned entry, empty region, missing semantics
rule, missing entry function, unresolved indirect jump emitted as an explicit
boundary (no `goto`, no guessed target), and fixture tamper detection.

## Tests / coverage

```text
python tools/test_mips32_end_to_end_v1.py
OPENRECOMP_MIPS32_END_TO_END_V1=PASS tests=108
```

Coverage: fixture byte length/SHA/word count/entry alignment; decode addresses,
ops, sizes, branch targets, unresolved `jr`, PROVEN evidence, determinism;
ProgramModel source/function/validation; CFG block entries, taken/not-taken/
fallthrough/indirect edges, determinism, no phantom blocks; function discovery
identity/body/unowned/provenance/determinism; call-graph nodes/edges/
determinism; translation-unit identity/ownership/determinism; indirect-site
count/address/status/no-guessed-targets plus fail-closed without evidence;
host-emission registers/operations/branch/return-like/determinism/no hard-coded
result; independent reference registers and explicit derivation; Phase-1 oracle
cross-check; deterministic native build and two-build reproducibility; manifest
no-leakage; native execution stability, exit code, expected==actual and guest
register mapping; and fail-closed rejections.

## Upstream regression totals

```text
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
PASS source-integrity  verified 120 manifest entries
```

## Source integrity

`SOURCE_SHA256SUMS.txt` 119 -> 120 entries via `update_sums.py`; the single
added entry is `tools/test_mips32_end_to_end_v1.py`
(`888211837132c5d6feda469e2b95357de651f73392c517733116dcd7c6461eaf`). No
existing hash changed.

## Determinism

- P2-10 gate stdout, two consecutive runs, byte-identical:
  `sha256 5327f11c756e57fd23cae7243ae1222c8b2f990dc9884b8a5165787f1829b424`.
- Fixture SHA-256 `b33b597c...`; generated source `8570ea4a...`; manifest
  `cd4ebe29...`; executable `f94c95d2...`; all stable across runs.

## Phase-2 marker decision

`OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=NOT_PROVEN` is **unchanged**. The
control plane (`STAGE_QUEUE.md`) defines the final marker as the
`P2-99 Final verdict` outcome ("Issue final verdict only if all required stages
pass"), not as the condition of P2-10 alone. P2-10 was not specified as the
marker's trigger, so it is not claimed here. The narrower proven claim is
`OPENRECOMP_MIPS32_END_TO_END_V1=PASS` for this one tiny synthetic fixture.

## Known limitations

- Proves only this 13-instruction synthetic fixture; it is not full MIPS32
  support, not PS2 support and not a guest/host equivalence proof.
- The neutral CFG/emitter do not model MIPS delay slots as first-class
  semantics; the fixture uses `nop` delay slots so the structural model is
  semantically equivalent. This limitation is explicit.
- The post-`jr` delay-slot `nop` is unreachable in the neutral CFG and is
  preserved as unowned residual evidence rather than executed.
- Emitted functions remain void with no argument/return ABI.
- `openrecomp/*.py` remain outside `SOURCE_SHA256SUMS.txt` (pre-existing
  `update_sums.py` glob gap).
- Toolchain-gated Phase-1 gates remain skipped on this host.

## Explicit non-claims

No arbitrary MIPS32 equivalence, full MIPS32 support, full PS2 support,
commercial-game recompilation or console compatibility. P2-11 and later stages
were not started. The final `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS`
marker is not claimed.

## Boundary rule

No P2-10 git commit was created. The coherent P2-10 changes are left in the
working tree for independent review and boundary commit.

## Final verdict

`PASS` — a synthetic/original MIPS32 fixture traverses the real Phase-2
pipeline (ProgramModel, CFG, function discovery, call graph, translation units,
indirect-control-flow classification, host emitter, deterministic build) to a
reproducible native executable whose independently derived expected observable
exactly matches the actual native observable.

OPENRECOMP_P2_10=PASS
OPENRECOMP_MIPS32_END_TO_END_V1=PASS tests=108
