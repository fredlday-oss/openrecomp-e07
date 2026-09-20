# P9-06 result: PS1 GPU/runtime boundary

Status: `PASS` (102 checks)

Markers:

- `OPENRECOMP_P9_06=PASS`
- `OPENRECOMP_PHASE9_GPU_BOUNDARY_V1=PASS tests=102`
- `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)
- `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase9_gpu_v1.py`.

## Implementation

- `.openrecomp-phase9/src/p9_io_discovery_v1.py` - bounded, deterministic,
  non-guessing discovery of guest load/store accesses to PS1 I/O ranges. The
  base (and stored value) register is reconstructed only from immediate
  operations in the same basic-block window (8 records); memory-sourced or
  computed values stay unknown. This shared module is reused by P9-07, P9-08
  and P9-09.
- `.openrecomp-phase9/src/p9_gpu_boundary_v1.py` - clean GPU platform adapter
  boundary: exact GP0/GP1 write ports (`0x1f801810`/`0x1f801814`, 32-bit),
  documented coarse GP0/GP1 command-class tables, deterministic typed event
  transcript with digest, explicit unknown-command blockers, and explicitly
  labelled contract stubs for GPU reads (`contract-stub-not-hardware-accurate`).
  No GPU emulation and no rendering.

## Public fixture GPU behaviour (exact)

The bounded discovery finds exactly two reachable GPU accesses:

| Site | Op | Address | Value | Command class |
|---|---|---|---|---|
| `0x80010054` | `sw` | `0x1f801810` (GP0) | `0x000000a0` | `NOP` |
| `0x8001005c` | `sw` | `0x1f801814` (GP1) | `0x00000000` | `RESET_GPU` |

The adapter records both events with transcript digest
`b190376ba5775e91e2b3c4acd1e1ef6665fb2e50d978f65b3b9a6bebe655fe54`; the
transcript is stable across replay. Unit checks additionally prove
`0xA0000000` classifies as `CPU_TO_VRAM_COPY`, `0x10000000` as an explicit
`UNKNOWN_COMMAND` blocker, and the GP0/GP1 reads return the labelled stubs.

## Private fixture scan (metadata only)

The same bounded discovery over the private Hercules reachable frontier finds
0 GPU-range accesses within its same-block immediate window; the result is
recorded with an explicit note that unresolved accesses are not guessed. No
payload bytes are present in the evidence; the fixture is explicitly
`is_pass_criterion: false`.

## Official runs

Command `python .openrecomp-phase9/src/p9_stage_runner_v1.py --stage P9-06
--script tools/test_phase9_gpu_v1.py --evidence-dir
.openrecomp-phase9/evidence/P9-06 --tests-json p9_06_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 3321 bytes (LF), sha256
`880bc4f9a83539f1f7759e7cbc37f7ce15dd74fe262217e127b527b3c645bf01`.

Sidecar identities:

- `p9_06_tests.json` `f683f37c623b13e3e236ac3e720865f8ef65faebb1b6229fac5869fd9e4bd22f`;
- `public_gpu.json` `a4635fd65dc22461244ecf72a6d57ec08a4e1df25591ac4bf67eae2d0cab26ac`;
- `private_gpu.json` `71c58cabde0b463a187206b846aa96a1b196d79a3f537a710c4f1dbdcb9852f4`;
- `official_runs.json` `9650aa779b449db09e694b01190dd1816ba02844fed26891a37a751ef36bf4fd`;
- `determinism.json` `5c5ebd651ae546d91c6a2755997e3002dbf983791f6c5b6d5bd2e2312f38c482`;
- `run1.txt` = `run2.txt` `880bc4f9a83539f1f7759e7cbc37f7ce15dd74fe262217e127b527b3c645bf01`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Claim-ledger delta

`BOUNDED`: a non-emulating GPU platform adapter boundary exists; the public
fixture's two reachable GPU writes are discovered and classified exactly, and
unknown GPU commands are explicit blockers. No GPU rendering, VRAM behaviour,
DMA or display output is claimed.

## Next stage

`P9-07` - input/timer/event boundary: classify controller, timer, event and
interrupt requirements, and add deterministic virtual-time/input/event
interfaces as required.
