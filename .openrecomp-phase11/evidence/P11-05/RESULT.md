# P11-05 — GPU command-stream frontier

Status: **PASS**

`OPENRECOMP_P11_05=PASS`

`OPENRECOMP_PHASE11_GPU_COMMAND_STREAM_V1=PASS tests=294`

`OPENRECOMP_PHASE11_HERCULES_GPU_COMMAND_PROOF=PROVEN`

`OPENRECOMP_PHASE11_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN`

`OPENRECOMP_PHASE11_HERCULES_FRAME_PROOF=NOT_PROVEN`

`OPENRECOMP_PHASE11_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN`

`OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN`

## Result

The documented `A0:0x49` `GPU_cw(command)` boundary is implemented as a
one-argument, void host service. It passes the 32-bit command through
`or_rt_memory_write(P9_GP0_ADDR, 32, command)`, so the frozen Phase-9 GP0
classifier and event recorder remain the only GPU command boundary. No raw
port bypass, renderer, VRAM mutation, DMA, interrupt delivery or unrelated GPU
state was added.

Milestone C is promoted for this exact private fixture: execution produces a
genuine typed GP0 write, in deterministic order, and the frozen classifier
identifies its opcode `0x00` as the known `NOP` class. This does not establish
initialization completion, a valid frame or playability.

## Preserved diagnostic conclusion

The temporary provenance instrumentation was removed. The bounded conclusion
is retained in `diagnostic.json` without payload bytes, raw instruction words,
reconstructive disassembly or private paths:

- classification: `GUEST_VALUE_CONFIRMED`;
- BIOS vector site: `0x8001b424`, vector `A0`, index `0x49`;
- `$t2 = 0x000000a0` is defined at `0x8001b420` by the same-block immediate
  arithmetic definition and is not a native/reference divergence;
- `$a0 = 0x0002a244` is the stable RAM-derived runtime argument in both native
  and reference execution;
- initial word `0x8002a244`, runtime mask `0x00ffffff`, zero overlapping writes
  before the call;
- no CPU, translation, ABI, memory or runtime-state defect was found.

## Controlled causal A/B

Both variants use access budget 1,500,000 and block budget 8,000,000. The
prefix comparison is bounded at block 468286.

| Observable at the causal prefix | A: fail closed | B: typed `GPU_cw` |
|---|---:|---:|
| block events | 468287 | 468287 |
| block digest | `0xa9fd6af484ceb63b` | `0xa9fd6af484ceb63b` |
| host calls | 39 | 40 |
| service calls | 39 | 40 |
| checked accesses | 506048 | 506049 |
| non-RAM signatures | 1 | 2 |
| typed GP0 writes | 0 | 1 |

Registers, RAM digest, RAM read/write counters, input, SPU, CD-ROM, denied
accesses, service failures, budget denials and trace block stream are identical
at the prefix. The only B deltas are the documented void service call, its one
checked GP0 access, its one non-RAM signature and its one known typed NOP event.

The B variant moves the first failure from `0x8001b424` at block 468286 to:

| Field | New exact frontier |
|---|---|
| site | `0x8001882c` |
| operation | unresolved indirect call (`jalr`) |
| source value | `0x8001a7dc` |
| block | `blk_80018824` |
| function | `fn_800187b0` (entry context `0x8001b3f4`) |
| block index | 468323 |

The full run records one GP0 command write before the existing bounded device
polling transcript fills. It later reaches the unchanged access-budget failure
(`runtime memory write failed`); that post-frontier state is not interpreted as
GPU semantics.

## Public synthetic coverage

Original public fixtures prove:

- two opcode-`0x00` words are submitted in exact order and independently
  classified as known `NOP`, with the second word proving classification is
  by the high byte rather than whole-word equality;
- the void BIOS contract preserves the return register and resumes at the
  caller continuation;
- opcode `0x03` is recorded as a typed blocker and rejected fail closed;
- zero-argument/null-argument invocation returns unsupported operation,
  preserves the output sentinel and records no GPU event;
- RAM remains unchanged and no renderer, VRAM mutation, DMA, interrupt,
  controller, SPU, CD-ROM or other GPU state is fabricated.

## Regression and determinism

The frozen P11-04 gate was run unchanged through the stage runner in the
P11-05 evidence directory: **851/851 checks PASS**, two byte-identical runs,
empty stderr and exit 0. Its LF-normalized stdout remains 30792 bytes with
SHA-256 `448c9dcbda12e210c8c157d80e43f0e4e8c236eac34c9344a98733c9f9ac803b`.
Frozen P11-04 evidence and all Phase-9/Phase-10 sources were not modified.

The P11-05 gate ran twice through the Phase-11 stage runner:

- 294/294 checks PASS;
- exit 0 and empty stderr for both runs;
- byte-identical raw and LF-normalized stdout;
- LF stdout SHA-256
  `7a860bea311a4795280121cf8a207de60b33b350f540b90b1068eae708ac50a8`;
- all four generated JSON sidecars are byte-identical.

See `determinism.json`, `official_runs.json`, `p11_05_tests.json`,
`diagnostic.json`, `causal_ab.json`, `frontier.json`, and the nested
`p11-04-regression/` evidence.

## Next action

P11-06 starts from the exact unresolved indirect call at `0x8001882c`. It must
first establish the target provenance and its relationship, if any, to the
newly demonstrated GPU/DMA/VRAM path. No target or GPU behavior is inferred
from the pointer value alone.
