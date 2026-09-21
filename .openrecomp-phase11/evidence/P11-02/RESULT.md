# P11-02 result: dynamic indirect-control frontier

Status: `PASS` (1466 checks)

Markers:

- `OPENRECOMP_P11_02=PASS`
- `OPENRECOMP_PHASE11_INDIRECT_V1=PASS tests=1466`
- `OPENRECOMP_PHASE11_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE11_HERCULES_FRAME_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE11_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase11_indirect_v1.py`.

## Exact BIOS vector classification

Every reachable indirect-control site (calls and jumps) is classified against
the audited BIOS jump-table convention: the vector base is a resolved constant
in the source register and the function index is a constant written to `$t1`
in the transfer's delay slot (`p10_bios_boundary_v1`).

19 sites are classified: 1 resolved service and 18 documented-but-unimplemented
indices that stay fail-closed and are never renamed.

| Site | Vector | Index | Documented name |
|---|---|---|---|
| `0x80026ccc` | A0 | `0x2b` | memset (resolved) |
| `0x80026cdc` | A0 | `0x30` | srand |
| `0x80026cec` | A0 | `0x3f` | printf |
| `0x80015b84` | A0 | `0x43` | DoExecute |
| `0x80015b94` | A0 | `0x44` | FlushCache |
| `0x8001b424` | A0 | `0x49` | GPU_cw |
| `0x80015ba4` | A0 | `0x70` | _bu_init |
| `0x80026c74` | B0 | `0x3f` | puts |
| `0x80015edc`, `0x80015eec`, `0x80015f3c`, `0x80015fa4`, `0x80026e24`, `0x80026e34`, `0x80026ebc`, `0x80026f74` | B0 | `0x12`, `0x13`, `0x5b`, `0x57`, `0x4a`, `0x4b`, `0x56`, `0x57` | identifiers only |
| `0x80015f4c` | C0 | `0x02` | SysEnqIntRP |
| `0x80015f5c` | C0 | `0x03` | SysDeqIntRP |
| `0x800161e0` | C0 | `0x0a` | identifier only |

The causal site is exactly:

| Item | Value |
|---|---|
| site | `0x80026ccc` (`jr $t2`) |
| source | `$t2` = `0x000000a0` (evidence `addiu@0x80026cc8`) |
| delay slot | `addiu $t1, $zero, 43` at `0x80026cd0` (evidence `index-addiu@0x80026cd0`) |
| neutral op | `jump_bios_a0_2b` |
| service | `ps1.bios.A0.2b` |
| shared classifier | `EXTERNAL_OR_RUNTIME_MEDIATED` / `EXTERNAL_RUNTIME_EVIDENCE` / `ps1.bios.A0` / `PROVEN` |

Invalid proof claims (a `RESOLVED` status with an external basis, and a
`BOUNDED_CANDIDATES` status without bounded evidence) are rejected by the
shared classifier.

## Documented service and runtime closure

The resolved site is emitted as an explicit host call through the shared
generic runtime ABI (`HostCallOperation` with the audited argument registers
`$a0`/`$a1`/`$a2` and the documented return register `$v0`). The runtime is the
composed Phase-10 runtime with two anchored substitutions (a dispatcher
declaration and the host-call fallback) plus the appended Phase-11 BIOS
fragment; the frozen Phase-9 source stays verbatim and the generated
service-id macro matches the declared numeric id (`8`).

Documented semantics implemented (`ps1.bios.A0.2b` memset, public PS1 BIOS
function documentation): fill `len` bytes at `dst` with `fillbyte & 0xff`;
refuse (return 0) when `dst == 0`, `len == 0` or `len > 0x7fffffff`; otherwise
return `dst`. Every byte is written through the frozen checked guest memory
boundary, so out-of-range destinations fail closed and every access is counted
by the deterministic budget. No BIOS image is loaded, executed or emulated.

Public synthetic native fixtures verify the contract:

| Fixture | Result |
|---|---|
| `memset(dst, 0xab, 8)` | `failed=0`; `$v0` = dst; bytes 0..7 = `0xab`; sentinel at +8 untouched |
| `memset(0, 0xab, 8)` | `failed=0`; `$v0` = 0; no writes |
| `memset(dst, 0xab, 0)` | `failed=0`; `$v0` = 0; no writes |
| `memset(0x10000000, 0xab, 8)` | fail-closed: `runtime host service ps1.bios.A0.2b failed` |
| A0 index `0x99` (unimplemented) | fail-closed: `unresolved indirect jump`, no service call |

## Frontier movement (private fixture)

| Run | Access budget | Block budget | First failure | Clean progress |
|---|---|---|---|---|
| P11-01 (before) | 2000000 | n/a | `0x80026ccc` (memset) | 9424 block entries |
| P11-02 (after) | 1500000 | 8000000 | `0x80026cec` (printf) | 468147 block entries |

The resolution removes the first fail-closed event and moves the frontier to
the next exact blocker: the documented A0 `0x3f` printf vector call at
`0x80026cec` in `fn_80026ce8`, reached after 468147 block entries (a gain of
458723 entries, ~49.7x). The instrumented run reproduces the uninstrumented
run's observables exactly (reads 636971, writes 721775, denied 11, host calls
81, RAM digest `0x18131c6ef356df7d`, device counts/digests, register file);
`p10_service_failures=0`.

Recorded frontier facts: 966069 block entries, block-stream digest
`0x2e874f4475dc4486`, 357 distinct blocks, 90 distinct functions, 29
fail-closed indirect events, GPU status and timer1 polling 109035 each,
CD-ROM 38, SPU 5.

## Deterministic bounded execution

The default access budget plus an explicit 8,000,000 block-entry budget
terminates the run deterministically (`bound_reached=1`, 8,000,001 block
entries, 4,261,313 accesses with 2,261,313 budget denials), closing the
recorded Phase-10 gap where a post-truncation guest loop with no memory access
could not be interrupted. The bound is host-side, explicit, recorded and does
not change guest semantics; a second identical run is byte-identical.

## Documented divergence

The Phase-11 trace fragment advanced between `P11-01` and `P11-02`: it now also
enforces the deterministic block-entry budget (the recorded `P11-01` evidence
remains historically accurate for the composition it was produced with, and
its gate assertions are unchanged). No earlier stage assumption or identity was
falsified.

## Official runs

Command `python .openrecomp-phase11/src/p11_stage_runner_v1.py --stage P11-02
--script tools/test_phase11_indirect_v1.py --evidence-dir
.openrecomp-phase11/evidence/P11-02 --tests-json p11_02_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 54255 bytes raw / 52783 bytes
LF, sha256 (LF) `dc4640b4c1ed40cad2f7478227b6de3f504e628e4f694edccfebbd16d1e651bf`;
generated evidence sidecars byte-identical across both runs.

Sidecar identities:

- `frontier.json` `393b4c3a6e2bb25832ca10df702d5d0ad9a6835f00910a11218374d506d64ef9`;
- `cache.json` `68d65e1bf1048f640670d445fbbfef8001fde7d17f1fabb72fbdcd84e3f3c04e`;
- `p11_02_tests.json` `874b4b30d758a10793befbdd4c3dbba100e711a01d682b63cf74aa5c09225f03`;
- `official_runs.json` `39146af4f747da0ee02883e2ffc9f4bd066be26b8cb91e2461def76146629ecc`;
- `determinism.json` `e413447f27051edbd1bc4d23f153bc2104d61751f1e456ac81016ae030c3fe44`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Public safety

The committed record contains addresses, identifiers, counts, classifications,
documented function names, digests and gate results only. The public-safety
scan (payload hex, base64, printable ASCII runs, string length) passes on both
sidecars. No payload bytes, no disassembly excerpts, no strings, no sectors, no
framebuffer or VRAM content and no absolute host paths are present.

## Claim-ledger delta

`PROVEN`: the exact BIOS vector classification of all 19 reachable indirect
sites, the causal-site resolution, the documented memset service contract
(synthetic), the frontier movement and the deterministic block budget.
`BOUNDED` (private only): the single-fixture frontier. Initialization
completion, GPU command stream, frames, title/menu, gameplay, playability and
general PS1 compatibility remain `NOT_PROVEN`.

## Next stage

`P11-03` - event / interrupt / DMA progress contract. The remaining BIOS
surface is exactly enumerated: `A0:0x3f` printf, `A0:0x30` srand, `A0:0x44`
FlushCache, `A0:0x49` GPU_cw, `A0:0x70` _bu_init, `A0:0x43` DoExecute,
`B0:0x12`/`0x13`/`0x3f`/`0x4a`/`0x4b`/`0x56`/`0x57` and `C0:0x02`/`0x03`/`0x0a`;
the interrupt/event services (`C0:0x02`/`0x03`) and the root-counter service
(`C0:0x0a`) determine whether interrupt delivery, timers or DMA are required.
