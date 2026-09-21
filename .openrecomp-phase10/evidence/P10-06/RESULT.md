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
`b3de2d29f63932c81106fa2cc3babb714eba38051153b84b35b6e169c0fc3ad2`.

| Device class | Observed events | Capped | Required |
|---|---|---|---|
| GPU (GP0/GP1) | 4096 | yes (capacity) | yes |
| Controller / SIO | 4096 | yes (capacity) | yes |
| SPU | 5 | no | yes |
| CD-ROM | 38 | no | yes |
| denied (outside the audited window) | 11 | n/a | unresolved, address not observable |

The run consumed 982859 reads + 799023 writes + 11 denied + 8235 device events
within the explicit 2000000 access budget (not reached) and terminated at an
executed unresolved indirect jump. Unmodelled devices and unknown commands stay
fail-closed.

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
empty stderr, both runs byte-identical: stdout 1074 bytes (LF), sha256
`fa23465700331282fea63cbfadc450ff42f4d80578df2d280c0ba34b21da0243`; generated
evidence sidecars byte-identical across both runs.

Sidecar identities:

- `io_discovery.json` `f9d3ef9025f700e1ed50a94aa5e67ac97cf5d67b7a61efbda919319994d11739`;
- `p10_06_tests.json` `e7c521f4c3a8b3b03f01c323d337792cec2e142476e3b607af8a624291f1751f`;
- `official_runs.json` `1921c18af334b33e57c12df36b6b5acbe18f5243a7dd68b6101b60a738166f6a`;
- `determinism.json` `3273eca5df76e0ea0dcba3bbb0399cef39e71b2fbbd8817cb459476eae80eec3`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

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
