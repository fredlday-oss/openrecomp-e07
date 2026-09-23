# P11-91 — evidence closure and bounded proof matrix

`PASS` (385 checks).

The official gate `tools/test_phase11_evidence_closure_v1.py` ran twice
through the Phase-11 stage runner with byte-identical stdout (23157 raw
bytes, SHA-256 `3eedfc0e...`), empty stderr, exit 0 and byte-identical JSON
sidecars.

## Scope

The gate verifies, as already-committed deterministic evidence, every
completed Phase-11 stage: `P11-00` through `P11-07`, `P11-RC` and `P11-90`.
For each stage it checks:

- the evidence directory and (except `P11-90`, which has none) its
  `RESULT.md` exist;
- `official_runs.json` records byte-identical raw/LF stdout across both
  runs, exit 0 both times, empty stderr both times, no `FAIL:` line, and the
  stage's own `OPENRECOMP_P11_xx=PASS` marker present in both runs;
- `determinism.json` records identical sidecar artifacts across both runs,
  and the recorded gate script has no uncommitted working-tree diff (`P11-02`
  and `P11-03` legitimately diverge from their own original recorded gate
  hash only through the later authorized `B0:0x57` `GetB0Table` metadata
  enrichment documented in `P11-90`'s `whole_regression.json`; every other
  stage's gate hash is required to be byte-identical to its original
  record);
- the stage's own tests JSON reports `PASS` with zero failures, handling
  both the `P11-00`..`P11-06` schema (`status`/`failed`/`passed`) and the
  `P11-07`/`P11-RC`/`P11-90` schema (`summary.passed`/`summary.failed`).

It then cross-checks the exact pinned facts recorded by those stages
directly from their committed JSON (fixture identity hashes; the `P11-01`
causal site `0x80026ccc` / `ps1.bios.A0.2b` / block 9424; the `P11-05`
required GP0 write `0x0002a244` classified known `NOP` and the frontier
move to `0x8001882c` / `0x8001a7dc`; the `P11-06` `EXACT_CONSTANT_TARGET`
resolution of `0x8001a7dc`; the `P11-07` `B0:0x57` `GetB0Table` public
contract, the exact caller site `0x80015fa4` / block `468341` /
`BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE`, and the zero implementation delta;
the `P11-RC` `QUEUE_RECONCILIATION_REQUIRED` decision and the authorized
route `P11-RC -> P11-90 -> P11-91 -> P11-99`; and the `P11-90` reconciled
claims `C=PROVEN_PRIVATE_FIXTURE_BOUNDED` /
`general_ps1_compatibility=NOT_PROVEN_PERMANENT` with `P11-08`..`P11-12`
recorded unexecuted and unassigned).

It verifies `STATE.md` and `STAGE_QUEUE.md` still record the four reserved
claim markers `NOT_PROVEN`, the promoted
`OPENRECOMP_PHASE11_HERCULES_GPU_COMMAND_PROOF=PROVEN` marker, every
completed stage as `PASS` in the stage-status table, every unexecuted stage
(`P11-08`..`P11-12`) as `NOT EXECUTED — no stage verdict assigned`, and the
authorized terminal route. It re-runs the Phase-11 source-integrity manifest
and requires `PASS`.

## Produced evidence

- `evidence_index.json` — file-level index (185 files) of every file under
  `P11-00` through `P11-90`, with per-file SHA-256 and per-stage summary
  records (gate, tests JSON, checks passed, stdout hash);
- `proof_matrix.json` — the bounded milestone matrix `A` (inherited proven)
  through `G` (not proven), highest proven milestone `C`
  (private-fixture bounded), the exact unresolved frontier (`B0:0x57`
  `GetB0Table` at `0x80015fa4`, block `468341`, required entry
  `B0:0x5b ChangeClearPAD`, `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE`,
  architectural/evidentiary cause), the deliberate exclusions
  (`P11-08`..`P11-12`), the permanent non-claim, and the four claim markers
  reserved at this stage;
- `claim_ledger.json` — every claim keyed to its supporting stage evidence,
  the reserved non-claims, the permanent non-claim, and per-stage checks;
- `safety_scan.json` — the tracked-evidence private-payload and host-path
  scan result (zero violations).

## Bounded decision

No new runtime, BIOS, translation, emission or device behavior is added.
No milestone is promoted. The four reserved markers remain `NOT_PROVEN`; the
already-promoted `OPENRECOMP_PHASE11_HERCULES_GPU_COMMAND_PROOF=PROVEN`
(milestone C) is verified unchanged. `P11-99` may now issue the final
bounded terminal verdict from this closed evidence base.
