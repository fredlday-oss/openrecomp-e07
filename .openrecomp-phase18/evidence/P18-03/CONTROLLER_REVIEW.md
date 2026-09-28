# P18-03 Controller Review

Stage: P18-03 - Causal Device Transcript
Controller: main (OpenRecomp autonomous controller)
Branch: agent/phase18-p18-03 (worker lane), integrated to phase18/ps1-first-frame-frontier-v1
Reviewed against: committed contract `.openrecomp-phase18/contracts/P18-03.md`

## Provenance of this work

The bounded implementation worker (deepseek-v4-pro) timed out during its own
evidence run and returned no result. Its worktree was preserved per policy and
the controller completed validation itself: the module and gate were inspected,
the canonical gate was re-run once on a clean evidence dir (after stopping two
orphaned gate processes the timed-out worker had left racing the same dir), and
an independent fresh-private-root reproduction was executed.

## Independent reproduction performed

- Official gate (canonical, single uncontended run):
  `python3 .openrecomp-phase18/src/p18_stage_runner_v1.py --stage P18-03
  --script tools/test_phase18_causal_transcript_v1.py --evidence-dir
  .openrecomp-phase18/evidence/P18-03 --tests-json p18_03_tests.json`
  -> runner_status PASS, exit 0, empty stderr, byte-identical dual-run stdout
  (raw and LF), identical evidence artifacts.
- Checks: 56/56 PASS, 0 FAIL. Source integrity: 17 entries PASS.
- Independent fresh/private-root reproduction:
  `OPENRECOMP_P18_PRIVATE_BUILD_ROOT=/tmp/p1803-repro-build python3
  tools/test_phase18_causal_transcript_v1.py --evidence-dir /tmp/p1803-repro-ev`
  -> 56/56 PASS, exit 0. All artifacts (RESULT.json, causal_transcript.json,
  causal_transcript.sha256, category_coverage.json, negative_tests.json,
  p18_03_tests.json) byte-identical (sha256 MATCH) to the official evidence.
- Causal transcript digest
  `1eabe6c7b5c5263a61da8f91534f89b7a92c38916cdc482f3792b807dd10d6d6`
  reproduced exactly.

## What the stage mechanically establishes

- A second fail-closed overlay on top of the P18-02 overlay makes the frozen
  P17-06R runtime emit, alongside every MMIO event, a causal device-state
  snapshot (store, address, width, value-as-produced, owning PC, and GPU
  command-FIFO depth before/after). The snapshot is emitted by the runtime,
  never reconstructed in Python, and matches the event stream 1:1.
- Every event binds to sequence, guest PC, authenticated owner provenance
  digest, decoded instruction verified by an independent fresh decode of the
  authenticated private word, event type/class, address/register, value,
  width, and causal device state. The raw word is never emitted.
- Reached categories (BIOS_DISPATCH 2, GPUSTAT_READ 6, INTERRUPT_ACCESS 8,
  TIMER_ACCESS 4; 20 events, 18 causal snapshots) and unreached categories
  (GP0/GP1, DMA, OT, CD-ROM, SPU, PAD, SIO, MMIO, VRAM_MUTATION) are listed
  explicitly; an unreached category is never silently a valid no-op.
- BIT-26 state model remains in force; zero read model absent; the causal
  functions contain no guest PC constant; no title-specific constants.

## Negative / fail-closed controls (all present and passing)

- event without authenticated owner rejected;
- event without provenance rejected;
- causal snapshot count mismatch rejected;
- causal log overflow rejected;
- tampered fresh-decode record rejected;
- zero-fill poll not exited (state model disabled -> poll retained);
- unmodelled GPUSTAT bit rejected;
- overlay anchor fail-closed controls (P18-02 and P18-03).

## Proof boundary

- Promotes NO frame/initialization/playability property. `FIRST_FRAME_READY=NO`;
  all `OPENRECOMP_PHASE18_*` claim markers NOT_PROVEN.
- GP0/GP1 command semantics, DMA/ordering-table traversal, VRAM mutation and
  display configuration remain for P18-04..P18-06 (no GP0/GP1/DMA traffic was
  reached in this bounded execution).
- Phase-17 frozen authority unchanged; Phase 1-17 namespaces untouched.

## Verdict

ACCEPTED. The stage passes its bounded contract with independent reproduction.
next_stage: P18-04.
