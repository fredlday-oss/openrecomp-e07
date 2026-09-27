# OpenRecomp Phase 18 Stage Queue

Every stage terminates `PASS`, `PASS_NOT_REQUIRED` or `FAIL`. A stage `PASS`
does not by itself promote a target proof marker.

Phase-18 stages are named `P18-xx` to keep the namespace distinct from Phase-17.

## Reconciled queue

```text
P18-00
```

Only `P18-00` is admitted at the time this queue is frozen. Later `P18-xx`
rows are authored by their own stage contract when the preceding stage's
frontier warrants them; they are not pre-declared here as if they had been
executed.

## Conceptual (non-binding) progression

The master prompt sketches a conceptual progression only:

```text
P18-00  Phase bootstrap / authority / provenance
P18-01  GPUSTAT polling model investigation
P18-02  Authentic execution escape from polling frontier
P18-03  GPU/DMA/MMIO causal transcript
P18-04  GP0/GP1 command frontier
P18-05  Ordering-table / DMA-chain frontier
P18-06  VRAM mutation / display-state frontier
P18-07  First-frame evidence assessment
P18-90  Integrated regression
P18-91  Independent reproduction
P18-99  Terminal Phase 18 closure
```

These rows are conceptual only. Each is admitted, renamed or dropped by its own
contract after inspecting the live repository frontier.

| Stage | Objective | Marker | Status |
|---|---|---|---|
| P18-00 | Phase-18 bootstrap: frozen authority, provenance, control plane, imported-recon inventory, frontier analysis | `OPENRECOMP_P18_00=PASS` | PASS |
| P18-01 | GPUSTAT polling-model investigation: authenticate the exact poll condition, minimum state-driven bit-26 model, fail-closed controls, deterministic simulation | `OPENRECOMP_P18_01=PASS` | PASS |
| P18-02 | Authentic poll exit / execution continuation: state-driven GPUSTAT read, bound-exit poll geometry, authenticated continuation, causal transcript, fail-closed controls | `OPENRECOMP_P18_02=PASS` | PASS |

Claim markers (created by Phase 18; `NOT_PROVEN`/`NO` at P18-00):

- `OPENRECOMP_PHASE18_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN`;
- `OPENRECOMP_PHASE18_HERCULES_FRAME_PROOF=NOT_PROVEN`;
- `OPENRECOMP_PHASE18_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN`;
- `OPENRECOMP_PHASE18_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN`;
- `FIRST_FRAME_READY=NO`.

Historical Phase-17 claim markers preserved unchanged (never promoted by
Phase 18):

- `OPENRECOMP_PHASE17_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN`;
- `OPENRECOMP_PHASE17_HERCULES_FRAME_PROOF=NOT_PROVEN`;
- `OPENRECOMP_PHASE17_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN`;
- `OPENRECOMP_PHASE17_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN`;
- `FIRST_FRAME_READY=NO`.

## Frontier carried into Phase 18

The accepted Phase-17 runtime conclusion is a bounded checked device frontier
dominated by a zero-returning GPUSTAT wait-poll: 1586 of 1590 recorded device
events are repeated `GPUSTAT_READ` accesses to `0x1f801814` from
`0x8001a9fc`, every one zero under `ZERO_FILL_RECORDED`. **This is not a
frame, not initialization proof and not a general GPU capability claim.**
