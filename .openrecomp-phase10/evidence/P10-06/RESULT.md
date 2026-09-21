# P10-06 result: dynamic PS1 I/O discovery

Status: `PASS` (26 checks)

Markers:

- `OPENRECOMP_P10_06=PASS`
- `OPENRECOMP_PHASE10_IO_DISCOVERY_V1=PASS tests=26`
- `OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase10_io_v1.py`.

## Dynamic source (from the deterministic P10-05 run)

Input identity: `.openrecomp-phase10/evidence/P10-05/native_entry.json`, SHA-256
`ef7b834293e4e5ff1067c78154ccbbeac218276bea1375000bd380e3cb6c05e9`.

| Device class | Observed events | Capped | Required |
|---|---|---|---|
| GPU (GP0/GP1) | 4096 | yes (capacity) | yes |
| Controller / SIO + timers | 4096 | yes (capacity) | yes |
| SPU | 5 | no | yes |
| CD-ROM | 38 | no | yes |
| denied (outside the audited window) | 11 | n/a | unresolved, address not observable |

The run consumed 982859 reads + 799023 writes + 11 denied + 8235 recorded device
events (1790128 accounted, a lower bound because the per-device transcripts are
capped at 4096) against an explicit 2000000 access budget. The FIRST recorded
fail-closed transition is an executed unresolved indirect jump; the budget was
subsequently exceeded (access count 2000005, 5 budget denials), which bounded
further progress. A fail-closed failure aborts only the current translated
function, so the traffic record includes post-failure progress (documented in
the `P10-05` record). Unmodelled devices and unknown commands stay fail-closed.

## Static source (constant-base scan, re-run at this stage)

1107 reachable memory-access sites classify as:

| Class | Count |
|---|---|
| base register unresolved (memory-loaded pointer) | 769 |
| resolved constant base outside the audited ranges (RAM globals) | 338 |
| resolved constant base inside an audited device range | 0 |

Every unresolved base carries its bounded-slice evidence, and every resolved
address lies inside the 2 MiB guest RAM window. This is the exact complement of
the Phase-9 finding (zero statically discoverable I/O accesses): device
addresses in this game are computed at runtime from loaded pointers, so the
dynamic record is the only evidence source - it is not that no device is used.

## Requirements

- dynamically required and already served by the Phase-9 typed port boundary:
  `cdrom`, `gpu`, `input`, `spu`;
- implemented at Phase 10: nothing (no speculative device work);
- explicitly not required and not implemented: `dma`, `memory_control`,
  `expansion`, `sio`;
- residual policy: unresolved bases, addresses outside the audited ranges and
  every denied access stay explicit and fail closed.

## Audited ranges used (reused unchanged from Phase 9)

`gpu` `0x1f801810`+8, `joy` `0x1f801040`+0x10, `timer0/1/2`
`0x1f801100/110/120`+0x10, `spu` `0x1f801c00`+0x400, `cdrom` `0x1f801800`+4,
`interrupt` `0x1f801070`+8. No device map is invented.

## Official runs

Command `python .openrecomp-phase10/src/p10_stage_runner_v1.py --stage P10-06
--script tools/test_phase10_io_v1.py --evidence-dir
.openrecomp-phase10/evidence/P10-06 --tests-json p10_06_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 1101 bytes (LF), sha256
`154d74b966a32ce7dba34dcc0700ece9ebfaea62243945d6956e773c4bbc923d`; generated
evidence sidecars byte-identical across both runs.

Sidecar identities:

- `io_discovery.json` `88743aff3ccdba227e0ad2de787130190365e6cff580b458a7585bf47d3e687c`;
- `p10_06_tests.json` `99c3303b5a64d97fefd95fb25a1aeedc0db083d45d70b9fbde797ad0e52fad37`;
- `official_runs.json` `3ace2431b73d5377911b62e04bcea60e7ff534de66c17bb6431a730e76e655ea`;
- `determinism.json` `07777c3dbcd78ce72e39925df49e25940be6317364462984a55dddbb56a2ec98`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Re-issue note (documented, not silent)

Re-issued after the `P10-05` evidence correction: a fail-closed failure aborts
only the current translated function, and the run's access count (2000005)
exceeds the budget (2000000), so the budget *was* reached after the first
failure. The classification, the static complement, the requirements and the
gate result are unchanged; the dynamic input identity is the corrected
`P10-05` record, and the gate was re-run twice with byte-identical stdout.

## Public safety

The committed record contains device classification names, counts, addresses of
*audited port ranges*, classification histograms and digests only. No payload
bytes, no disassembly, no device transcripts and no disc material.

## Claim-ledger delta

`PROVEN`: the dynamic device-class discovery and the constant-base static
complement. `BOUNDED` (private only): the observed counts and the denied
residual. GPU command identity, DMA/interrupt/timer behaviour, CD-ROM command
identity, rendering, playability and general PS1 compatibility remain
`NOT_PROVEN`.

## Next stage

`P10-07` - GPU command execution frontier.
