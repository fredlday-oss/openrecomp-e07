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
| `0x8001005c` | `sw` | `0x1f801810` (GP0) | `0x000000a0` | `NOP` |
| `0x80010064` | `sw` | `0x1f801814` (GP1) | `0x00000000` | `RESET_GPU` |

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

- `p9_06_tests.json` `6adf18a0f0384c02277a893a9f6a08b17f108cf92bfaa82874cf5bf3abca648e`;
- `public_gpu.json` `a2ea5bd2b721d20e987c6b52ee4d4960bf1b55051ebf42282a8f09962ffdfbe2`;
- `private_gpu.json` `71c58cabde0b463a187206b846aa96a1b196d79a3f537a710c4f1dbdcb9852f4`;
- `official_runs.json` `60de299e5e79df46b2ead4e7a96440b0d908a6457c9d531197041a214d68a226`;
- `determinism.json` `38a65d97bd80fdd21bd0469d9951b418717a343bcbdc2509813636592fd028a2`;
- `run1.txt` = `run2.txt` `880bc4f9a83539f1f7759e7cbc37f7ce15dd74fe262217e127b527b3c645bf01`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Documented fixture correction (P9-10 preparation)

The public fixture was corrected to initialize `$sp` itself at entry (see the
P9-03 correction record); the two GPU access sites shift by 8 bytes to
`0x8001005c` and `0x80010064`. The transcript digest is unchanged
(`b190376b...`, events carry port/value but not the access site). The official
runs were re-issued; the official stdout identity is unchanged
(`880bc4f9...`).

## Claim-ledger delta

`BOUNDED`: a non-emulating GPU platform adapter boundary exists; the public
fixture's two reachable GPU writes are discovered and classified exactly, and
unknown GPU commands are explicit blockers. No GPU rendering, VRAM behaviour,
DMA or display output is claimed.

## Next stage

`P9-07` - input/timer/event boundary: classify controller, timer, event and
interrupt requirements, and add deterministic virtual-time/input/event
interfaces as required.
