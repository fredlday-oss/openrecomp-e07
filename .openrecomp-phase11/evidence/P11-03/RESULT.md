# P11-03 result: event / interrupt / DMA progress contract

Status: `PASS` (1329 checks)

Markers:

- `OPENRECOMP_P11_03=PASS`
- `OPENRECOMP_PHASE11_EVENT_CONTRACT_V1=PASS tests=1329`
- `OPENRECOMP_PHASE11_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE11_HERCULES_FRAME_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE11_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase11_event_contract_v1.py`.

## Determination: no event behaviour is proven necessary

| Question | Answer |
|---|---|
| interrupt delivery required | `NOT_PROVEN` |
| interrupt acknowledgement required | `NOT_PROVEN` |
| DMA completion required | `NOT_PROVEN` |
| timer transition required | `NOT_PROVEN` |
| memory-control state required | `NOT_PROVEN` |
| another event source required | `NOT_PROVEN` |
| implementation delta | **zero** |

Deterministic execution-budget bisection over the instrumented build places the
first fail-closed event at guest access index **506040**. At that budget:

| Observable | Value |
|---|---|
| error | `unresolved indirect call` |
| GPU / controller / CD-ROM / SPU events | `0` / `0` / `0` / `0` |
| non-RAM access signatures | `0` |
| reads / writes | 81 / 505959 |

The entire 506040-access progress to the frontier is **RAM-only**: the guest
never touches a device port, an interrupt register, a DMA register, a timer
register or a memory-control register. An event source that is never accessed
cannot be the causal blocker, so no event behaviour is proven necessary and
nothing is implemented. The causal A/B for events is correspondingly not
applicable; the causal service A/B is: serving `A0:0x2b` moved the frontier to
block 468147 and serving `A0:0x3f` moved it to block 468281.

The event-relevant documented services are statically reachable but stay
fail-closed and are not dynamically reached before the frontier:

| Vector | Index | Documented name |
|---|---|---|
| C0 | `0x02` | SysEnqIntRP |
| C0 | `0x03` | SysDeqIntRP |
| C0 | `0x0a` | identifier only |
| B0 | `0x12`, `0x13`, `0x4a`, `0x4b` | identifiers only |

## Documented printf service (prerequisite, evidence-required)

`ps1.bios.A0.3f` printf(fmt, arg1, arg2) is served as a bounded documented
subset (`%%`, `%c`, `%s`, `%d`, `%i`, `%u`, `%x`, `%X`, `%o` with flags, width
and precision). The host has no console, so the formatted text is consumed and
discarded; the documented return value is the character count. Malformed or
unsupported conversions, an over-long format or string, or more varargs than
the declared surface fail closed.

Public synthetic native fixtures:

| Fixture | Result |
|---|---|
| `printf("%08x,%08x", 0x1a2b3c4d, 0xdeadbeef)` | `failed=0`, returns 17 |
| `printf("%d", 42)` | returns 2 |
| `printf("x%dy", -7)` | returns 4 |
| `printf("%s", "abc")` | returns 3 |
| `printf("%c", 0x41)` | returns 1 |
| `printf("%d %d %d", 1, 2)` | fail-closed (`runtime host service ps1.bios.A0.3f failed`) |
| `printf("%q", 1)` | fail-closed (unsupported conversion) |

## New exact frontier

| Item | Value |
|---|---|
| site | `0x80016204` (`jalr $v0`) in `fn_800161ec` |
| message | `unresolved indirect call` |
| source pointer | `0x80016384` |
| block index | 468281 (27 fail-closed indirect events total) |

The call is a driver-method dispatch: the function loads a structure pointer
from the global at `0x80029644` (value `0x80029624`), loads the method pointer
from field offset 12 (`0x80016384`) and calls it. The pointer is a
**statically initialized image value**: the word `0x80016384` occurs exactly
once in the loaded image (at `0x80029630`) and the target starts with a
function prologue (`addiu $sp,$sp,-24`), but the static CFG never discovered it
because it is only reachable through this indirect call. This is the exact
input for the next stage (P11-04): translate the proven target, resolve the
site with explicit evidence, and fail closed on any other pointer value.

## Frontier movement

| Stage | First fail-closed event | Clean progress |
|---|---|---|
| P11-01 | `0x80026ccc` (memset) | 9424 block entries |
| P11-02 | `0x80026cec` (printf) | 468147 block entries |
| P11-03 | `0x80016204` (driver method call) | 468281 block entries |

Frontier-run observables (access budget 1500000, block budget 8000000):
reads 636986, writes 721766, denied 10, host calls 83, access count 1500004,
4 budget denials, RAM digest `0x4552e679a9de06bc`, 966047 block entries, block
digest `0xe114354a5b3e89c8`, GPU/controller events 65536, CD-ROM 38, SPU 5,
17 non-RAM signatures, `p10_service_failures=0`.

## Official runs

Command `python .openrecomp-phase11/src/p11_stage_runner_v1.py --stage P11-03
--script tools/test_phase11_event_contract_v1.py --evidence-dir
.openrecomp-phase11/evidence/P11-03 --tests-json p11_03_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 49662 bytes raw / 48327 bytes
LF, sha256 (LF) `b682cbcb76d81a870284d49724f620892fdf4bba2f620ef3a6f6bf5f23945429`;
generated evidence sidecars byte-identical across both runs.

Sidecar identities:

- `event_contract.json` `480ae71daeae71658d69628933ff2e0e8713a7f029cd6357df5fa7568257c51e`;
- `frontier.json` `6d3b62b28a07c26437ff529f9dc874d173fbd838bff63295bbe40b3b71fab764`;
- `p11_03_tests.json` `55be79d1a2940b1502f855c1eafeaca88faea664964268c9bc5053dc18817757`;
- `official_runs.json` `f31df8aea4e832b7156eb002b285a1d2c192b4680201241bd85ce6a97c02f085`;
- `determinism.json` `6771b3347addcc515eca777f7a17175244a4fdb9f2955617eb0ba79b1f71334d`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Public safety

The committed record contains addresses, identifiers, counts, classifications,
documented function names, digests and gate results only. The public-safety
scan (payload hex, base64, printable ASCII runs, string length) passes on both
sidecars. No payload bytes, no disassembly excerpts, no strings, no sectors, no
framebuffer or VRAM content and no absolute host paths are present.

## Claim-ledger delta

`PROVEN`: the RAM-only progress to the frontier, the zero-delta event
determination, the documented printf service contract (synthetic) and the
pointer provenance of the next blocker. `BOUNDED` (private only): the
single-fixture frontier. Initialization completion, GPU command stream, frames,
title/menu, gameplay, playability and general PS1 compatibility remain
`NOT_PROVEN`.

## Next stage

`P11-04` - milestone B: initialization completion. The exact next blocker is
the driver-method indirect call at `0x80016204` with the statically proven
target `0x80016384`; resolving it (and the remaining 17 BIOS vector sites) is
the prerequisite for reaching a post-initialization boundary. If initialization
cannot be proven complete, the stage must classify the exact remaining blocker
without promoting milestone B.
