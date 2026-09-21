# P10-08 result: interrupt / DMA / timing frontier

Status: `PASS` (42 checks)

Markers:

- `OPENRECOMP_P10_08=PASS`
- `OPENRECOMP_PHASE10_TIMING_FRONTIER_V1=PASS tests=42`
- `OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase10_timing_v1.py`.

## Exact non-RAM frontier and full denial attribution

The deterministic non-RAM access log (17 signatures, no overflow) resolves the
`P10-07` open item: every one of the 11 denials is now attributed to an exact
address and a cause.

| Address | W | Dir | Observations | Class | Disposition |
|---|---|---|---|---|---|
| `0x1f801074` | 16 | read | 1 | audited interrupt, blocked | fail-closed (I_MASK read) |
| `0x1f8010a8` | 32 | write | 1 | outside audited | fail-closed (DMA channel-2 configuration) |
| `0x00000000` | 8 | write | 1 | outside audited | fail-closed (low/null window) |
| `0x1f801020` | 32 | write | 2 | outside audited | fail-closed (memory-control delay) |
| `0x1f801801` | 8 | write | 10 (9 served, 1 blocked) | audited CD-ROM, blocked | fail-closed for the unknown command |
| `0x14802000` | 32 | read | 1 | budget denied | bounded-execution budget (stub value used as an address) |
| `0x1f801800/802/803` | 8 | r/w | 15/8/2/3 | audited CD-ROM | served |
| SPU `0x1f801daa/db0/db2/db8/dba` | 16 | r/w | 5 | audited SPU | served |
| `0x1f801814` | 32 | read | 109035 | audited GPU | served (status) |
| `0x1f801110` | 32 | read | 109035 | audited timer1 | served (virtual time) |

Reconciliation (exact): platform denials 6 (`I_MASK` 1, DMA 1, null 1,
memory-control 2, CD-ROM unknown command 1) + budget denials 5 = 11 = the
runtime's denied counter. The logged budget-denied observations (1) are a
subset of the budget-denial counter, because budget denials also hit RAM
accesses, which are not part of the non-RAM log.

Served observations: 218112 (GPU status 109035 + timer1 109035 + CD-ROM 37 +
SPU 5; the CD-ROM command port has 9 served + 1 blocked).

## Timing abstraction (explicit, not cycle accurate)

| Property | Value |
|---|---|
| counter read | returns `tick & 0xffff` and advances the tick by one |
| tick origin | zero at runtime initialisation |
| resolution | one tick per counter read (read-driven, not clock-driven) |
| cycle accuracy | **not claimed** |
| wall-clock dependency | none |
| wrap | 65536 counter reads before wrap |

Public synthetic evidence: three consecutive timer1 counter reads return
`0x0000`, `0x0001`, `0x0002` with `failed=0` and `denied=0`.

The GPU status reads and the timer1 counter reads are exactly one-to-one
(109035 each), which identifies a single polling loop whose two probes are both
served deterministically.

## Dispositions (nothing new implemented)

| Interaction | Required? | Implemented | Disposition |
|---|---|---|---|
| timer counter reads | yes | already served by the Phase-9 runtime | served |
| interrupt mask read | not proven | no | fail-closed |
| DMA channel-2 (GPU) configuration | not proven | no | fail-closed (a DMA channel cannot be modelled without VRAM/transfer state; accepting the write would invent transfer behaviour) |
| memory-control delay writes | not proven | no | fail-closed (delay registers affect timing only; there is no timing model in which accepting them would mean anything) |
| low-address write | not proven | no | fail-closed |
| corrupted pointer read | no | no | symptom of the control-flow failure |

No interrupt is required for progress: there is no interrupt-status read, no
interrupt-dependent wait and no interrupt acknowledgement anywhere in the
recorded run. DMA is *attempted once* (channel-2 configuration) but no transfer
request, completion wait or DMA-driven GPU path is proven.

Public synthetic native negatives confirm the fail-closed behaviour is
deterministic: interrupt-mask read, DMA channel-2 write and memory-control
delay write each produce `failed=1`, `denied=1`.

## Bounded execution (limitation recorded)

The deterministic access budget bounds memory accesses, not execution: a
post-truncation guest loop that performs no memory access cannot be
interrupted (observed as a hang while probing ordering at a smaller budget
during `P10-07` reconnaissance). Every official gate therefore runs with the
default budget (2000000) and a bounded host timeout. This is
recorded as a hardening item for `P10-12`; no hang is claimed to be resolved.

## Official runs

Command `python .openrecomp-phase10/src/p10_stage_runner_v1.py --stage P10-08
--script tools/test_phase10_timing_v1.py --evidence-dir
.openrecomp-phase10/evidence/P10-08 --tests-json p10_08_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 1661 bytes (LF), sha256
`749e3c6e6afa76b3d1fc0dec453934ee4cc1800bb982b864ee1b8b5b7db95703`; generated
evidence sidecars byte-identical across both runs.

Sidecar identities:

- `timing_frontier.json` `a2dc8506a5444be019662cb5ae9042483c74b8993ecc9af1a191c5cf1d735eb2`;
- `p10_08_tests.json` `ab9c7b340a7a004ec70f77b69084897006faedac921844afd34a751f882a394f`;
- `official_runs.json` `d34070973bb42401df26209c57d8b925dd8bd1274b560ff6ced23d40da31ee32`;
- `determinism.json` `d2d452e23ed7ec4eeea47762f0ea1244057a9e8f6d1bc7493011af058351f341`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Public safety

The committed record contains addresses, widths, directions, counts, class
names, reconciliation totals and digests only. No raw command payloads, no
device transcripts, no payload bytes and no disc material.

## Claim-ledger delta

`PROVEN`: the interrupt/DMA/timing frontier classification, the exact denial
reconciliation, the deterministic timer contract and the fail-closed
dispositions. `BOUNDED` (private only): the observed counts. Interrupt
delivery, DMA transfers, memory-control timing, cycle accuracy, rendering,
playability and general PS1 compatibility remain `NOT_PROVEN`.

## Next stage

`P10-09` - disc / CD-ROM / streaming frontier, using the already verified CUE
and the CD-ROM access evidence: index/status writes, parameter writes and 10
command writes (9 served, 1 unknown command `0x80` blocked).
