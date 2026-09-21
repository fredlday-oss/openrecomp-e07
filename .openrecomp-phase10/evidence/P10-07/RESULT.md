# P10-07 result: Hercules GPU command execution frontier

Status: `PASS` (58 checks)

Markers:

- `OPENRECOMP_P10_07=PASS`
- `OPENRECOMP_PHASE10_GPU_FRONTIER_V1=PASS tests=58`
- `OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase10_gpu_v1.py`.

## Exact GPU frontier reached

| Observable | Value |
|---|---|
| GPU events recorded | 65536 (at the configured transcript capacity) |
| direction | 65536 reads, **0 writes** |
| port | `0x1f801814` (GP1 status/control read) only |
| access width | 32 bits, all events |
| value | `0x14802000` (the audited boundary contract stub), all 65536 reads |
| blocked GPU events | 0 |
| unknown GPU commands | 0 |
| GP0 reads / writes | 0 / 0 |
| transfer classes (CPU<->VRAM, VRAM<->VRAM, VRAM->CPU) | 0 |
| DMA-controller traffic | not observed |
| VRAM state | not modelled by the Phase-9 boundary (no digest is fabricated) |

Reads and writes are separated before classification, so a status value is
never misread as a command. The GP1 polling saturates the transcript, so the
recorded stream is a capped prefix and the true polling count is a lower bound.

## Implemented subset

Exactly one operation, justified by the dynamic record and aligned with the
audited Phase-9 boundary:

| Operation | Behaviour |
|---|---|
| GP1 status read (`0x1f801814` read) | returns the audited Phase-9 boundary contract stub `GPUSTAT_STUB` (`0x14802000`) |

The frozen Phase-9 runtime returned `0` for that read, which contradicted its
own audited boundary constant. The A/B comparison (stub `0` in the `P10-05`
record vs the stub now) shows the recorded traffic is **identical** either way
(reads, writes, denied, access count, budget denials, first error) - only the
status value differs - so the change introduces no behavioural assumption.

Explicitly not implemented: GP0 command execution, VRAM state, GP1 control
state, rendering, framebuffer/VRAM digests, DMA-controller behaviour. Unknown
GP0/GP1 commands remain fail-closed (proved natively).

## Public synthetic evidence (native)

| Fixture | Result |
|---|---|
| GP0 `NOP` write + GP1 status read | `failed=0`, `denied=0`, 1 write event class `NOP`, 1 status read |
| GP0 `POLYGON` write + GP1 status read | `failed=0`, `denied=0`, 1 write event class `POLYGON` |
| unknown GP0 command (`0x1f000000`) | `failed=1`, `denied=1`, 1 blocked event, class `UNKNOWN_COMMAND` - fail-closed |

Independent classifier vectors are re-checked against the audited Phase-9 GPU
boundary (`POLYGON`, `CPU_TO_VRAM_COPY`, `RESET_GPU`, unknown-command
negatives).

## Front

- **GPU command stream reached: NO.** GP1 status polling is reached and served,
  but no GP0/GP1 command write occurs anywhere in the recorded run.
- **GPU-side blocker: none.** Every GPU access is a served read of a modelled
  port (`0` blocked events, `0` unknown commands, `0` GPU-attributable denials);
  the A/B experiment shows the polling is not conditioned on the status value.
- **Denial attribution** (11 denials total): 1 controller/interrupt BLOCKER
  (`I_MASK` write at `0x1f801074`), 1 CD-ROM BLOCKER (unknown command `0x80` at
  `0x1f801801`), 0 GPU, 0 SPU, 9 unrecorded (addresses inside the I/O window
  outside the modelled ports, or outside the modelled windows).
- **First remaining blocker**: the executed unresolved indirect jump (control
  flow), which precedes any GPU command write; the GPU is not the blocker. The
  deterministic access budget is subsequently reached and bounds further
  progress.
- **Milestone C is NOT established** and is not claimed.

## Limitations recorded

- per-access guest PC / translated function / call-flow provenance is not
  observable (the generated program carries no access hook); nothing is guessed
  in its place;
- per-device transcripts are printed as separate blocks, so cross-device
  ordering is not observable;
- the transcript is capped at the configured capacity and both the GPU and the
  controller streams saturate it;
- the deterministic access budget bounds memory accesses, not execution: a
  guest loop that performs no memory access after truncation cannot be
  interrupted (observed as a hang while probing ordering at a smaller budget).
  This is a hardening item for `P10-08`/`P10-12`.

## Documented divergence

`P10-07` advanced the Phase-10 runtime composition (the diagnostic event
capacity and the GPU status-read stub are now anchored substitutions). Stages
`P10-03` and `P10-05` recorded the earlier composition; their gates still pass
unchanged (they assert dynamic composition identity, not a recorded count), and
their recorded observables remain historically accurate for the composition
they were produced with. No earlier stage assumption or identity was falsified,
so no earlier stage is re-issued (per the standing instruction).

## Official runs

Command `python .openrecomp-phase10/src/p10_stage_runner_v1.py --stage P10-07
--script tools/test_phase10_gpu_v1.py --evidence-dir
.openrecomp-phase10/evidence/P10-07 --tests-json p10_07_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 2036 bytes (LF), sha256
`97519d67d0f4ec2c19d5e6768f69d8545f1c4c1bd3b16d1cfd63cc460cfd1b2a`; generated
evidence sidecars byte-identical across both runs.

Sidecar identities:

- `gpu_frontier.json` `e60c4dc20089bcb7d70d11247ecaadd44b750437c14e3bea3f4fce452632d73a`;
- `p10_07_tests.json` `dca6c73fee3bee538900c092efa610d3e3ae08862a57d432c131c11e5e50ce6a`;
- `official_runs.json` `d501d137cf21c98b74c4e7f2d414d0200bd08f83d958d9844d0160209e79ff5a`;
- `determinism.json` `10371a617365a1bbf5cfb9a8cef3ec4df408e54291d8063c49b47ee0ff86aa51`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Public safety

The committed record contains port addresses, direction/width histograms,
command class names, counts, a status value, a write-value digest and digests
only. No raw command payloads, no textures, sprites, palettes, framebuffer
captures, VRAM dumps or any other reconstructive commercial content.

## Claim-ledger delta

`PROVEN`: the exact GPU access classification, the served subset, the
fail-closed unknown-command behaviour and the non-GPU nature of the current
blocker. `BOUNDED` (private only): the capped polling transcript. GPU command
execution, VRAM state, milestone C, rendering, playability and general PS1
compatibility remain `NOT_PROVEN`.

## Next stage

`P10-08` - interrupt / DMA / timing frontier, prioritizing the dependencies
exposed here: the `I_MASK` blocker, the unrecorded denials, the CD-ROM unknown
command, and the deterministic-time/bounded-execution behaviour.
