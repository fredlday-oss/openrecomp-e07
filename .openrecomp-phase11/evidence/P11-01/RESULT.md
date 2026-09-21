# P11-01 result: milestone-A progress causality

Status: `PASS` (583 checks)

Markers:

- `OPENRECOMP_P11_01=PASS`
- `OPENRECOMP_PHASE11_CAUSALITY_V1=PASS tests=583`
- `OPENRECOMP_PHASE11_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE11_HERCULES_FRAME_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE11_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase11_causality_v1.py`.

## Additive instrumentation (shared-layer change, opt-in)

`openrecomp/host_emitter.py` gains an optional `HostInstrumentation`
configuration (function-entry, block-entry and indirect-failure hooks). The
default is disabled and the emitter output is byte-identical when disabled:
the live emission still reproduces the frozen program fingerprint
`a047a52f...`. The fail-closed `or_fail` call is always emitted, so the hooks
cannot change guest semantics. Invalid hook names and an empty instrumentation
configuration are rejected.

Live direct-dependency regressions pass: `tools/test_host_emitter_v1.py`
(106), `tools/test_mips32_end_to_end_v1.py` (108),
`tools/test_phase8_translation_v1.py` (30),
`tools/test_phase9_translation_v1.py` (31).

Instrumented emission for the private executable: 110 function hooks, 739
block hooks, 40 indirect-failure hooks, identical `or_fail` count, no guest
payload bytes and no opcode dispatch.

## Trace semantics equivalence

Two isolated builds are byte-identical; two runs are byte-identical. The
instrumented run reproduces the uninstrumented run's guest observables
exactly: `failed=1`, `error=unresolved indirect jump`, reads 982859, writes
799023, denied 11, host calls 79, RAM digest `0x18131c6ef356df7d`, access
count 2000005, 17 non-RAM signatures, GPU/controller event counts and digests,
and the full register file. The trace itself is bounded (block-event ring
4096, first window 256, failure windows 64, 8192-slot count tables) with
explicit overflow counters.

Trace totals: 1,235,093 block entries, 110,190 function entries, 357 distinct
blocks, 90 distinct functions, block-stream digest `0x22f6f7e46b5ca586`.

## Causal frontier

The first fail-closed event is an executed unresolved indirect jump at
`0x80026ccc` in `fn_80026cc8` (block `blk_80026cc8`, terminal op
`jr_indirect`), at block index 9424 (guest access index 9430), and it is the
first of 31 fail-closed indirect events.

The site is a PS1 BIOS A0 jump-table call, classified with the frozen audited
boundary helpers:

| Item | Value |
|---|---|
| source register | `$t2` = `0x000000a0` (resolved constant, evidence `addiu@0x80026cc8`) |
| delay slot | `addiu $t1, $zero, 43` at `0x80026cd0` (evidence `index-addiu@0x80026cd0`) |
| vector | `A0` (`0x000000a0`) |
| function index | `43` (`0x2b`) |
| service id | `ps1.bios.A0.2b` |
| disposition | fail-closed; no BIOS material, no BIOS service implemented |

Pre-failure execution is pure RAM: the crt0 BSS-clear loop
(`blk_800132f8`, 9416 iterations, terminating, guest-intended) then
`blk_8001330c` → `fn_80011af0` → `blk_8001337c` → `fn_800119c8` →
`fn_800132e0` → `blk_800119e0` → the BIOS A0 stub.

Independent deterministic execution-budget bisection over the uninstrumented
build confirms the ordering:

| Budget | Result |
|---|---|
| 9429 | `error=runtime memory read failed`, `nonram_signatures=0` (the 9430th access is denied before the jump) |
| 9430 | `error=unresolved indirect jump`, all device counts 0, `nonram_signatures=0` |
| 400000 | `error=unresolved indirect jump`, all device counts 0, `nonram_signatures=0` |
| 500000 | CD-ROM 38, SPU 5, GPU 1892, timer 1892, 17 signatures |
| 2000000 | full frontier, 5 budget denials |

So the first failure precedes every device access: the entire device-visible
frontier of Phase 10 (CD-ROM command traffic, SPU configuration, the
GPU-status/timer1 busy-poll loop) executes **after** the first fail-closed
event, with the BIOS call's effect missing.

Post-failure loops:

| Loop | Location | Evidence |
|---|---|---|
| RAM word-fill loop | `blk_80011c14` in `fn_80011bcc` | 458,711 entries; terminal `bne` |
| GPU/timer poll cycle | 14 blocks in `fn_80015810` / `fn_80015ff8` | 54,501 iterations; governing back edge `blk_800158a8` (`bgtz`); 109,035 GPU status and 109,035 timer1 reads |

The pre-failure loop is the guest's own terminating BSS-clear loop; the
persistent loops are entered only after the fail-closed event. The causal
frontier is therefore **missing runtime behaviour at the BIOS A0 vector**, not
the guest loops and not the GPU status value (consistent with the Phase-10 A/B
result).

## Analysis cache

The frozen Phase-10 provenance-keyed cache is reused with an extended
Phase-11 provenance document (executable/CUE/BIN hashes, analysis, semantics,
runtime and device-contract versions, trace-configuration digest, scripted
input identity). A trace-configuration change, a scripted-input change and an
executable change each produce a different key and a cache miss.

## Official runs

Command `python .openrecomp-phase11/src/p11_stage_runner_v1.py --stage P11-01
--script tools/test_phase11_causality_v1.py --evidence-dir
.openrecomp-phase11/evidence/P11-01 --tests-json p11_01_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 22496 bytes raw / 21907 bytes
LF, sha256 (LF) `4e9fb85d59b46c39b402a6b7439141bd86fa234838bfd8c39e84a01313b6e822`;
generated evidence sidecars byte-identical across both runs.

Sidecar identities:

- `instrumentation.json` `37323faa3fbe6b6ce4ee5a1b533374d06116b2d0fac895afe25fca81f3eb2333`;
- `trace_execution.json` `fd514dffb6a7b0586006ee77d83d0da4af42d472f77b3e456947ec8c05fbede2`;
- `causality.json` `c8174a34bdf4916d1131917b36c8ad53c5f0b672bbd80ce1bac66622cbd34d20`;
- `cache.json` `1398539d7abd74e61e6b75c315592b512d5873339b69e6873ff04a669b09a1ca`;
- `p11_01_tests.json` `a9cb415fe5f3b63964fae1ed25e6da07246042bf000611c47bedae2713a31330`;
- `official_runs.json` `1da1ca7293d00adf4111f8fc983ee22cf69afca667ec876373766f085034ac1d`;
- `determinism.json` `a95ba7ddc3a2a8a96c49524fef9bd078ad84c27f221039a41f87cd33bfe13e5b`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Public safety

The committed record contains addresses, block/function identifiers, counts,
classifications, register values, digests and gate results only. The
public-safety scan (payload hex, base64, printable ASCII runs, string length)
passes on all four sidecars. No payload bytes, no disassembly excerpts, no
strings, no sectors, no framebuffer or VRAM content and no absolute host paths
are present.

## Claim-ledger delta

`PROVEN`: the additive instrumentation contract, the trace semantics
equivalence, the exact first fail-closed frontier, the BIOS A0 vector
classification of the causal site and the temporal ordering (failure before
all device traffic). `BOUNDED` (private only): the single-fixture trace.
Initialization completion, GPU command stream, frames, title/menu, gameplay,
playability and general PS1 compatibility remain `NOT_PROVEN`.

## Next stage

`P11-02` - dynamic indirect-control frontier: classify the exact causal site
with evidence (`EXTERNAL_OR_RUNTIME_MEDIATED`, mechanism `ps1.bios.A0`) and
determine whether serving the proven BIOS A0 call moves the frontier, without
guessing a target or inventing BIOS behaviour.
