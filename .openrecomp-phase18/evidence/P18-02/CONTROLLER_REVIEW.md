# P18-02 Controller Review

Stage: P18-02 - Authentic Poll Exit / Execution Continuation
Controller: main (OpenRecomp autonomous controller)
Branch: phase18/ps1-first-frame-frontier-v1
Reviewed against: committed contract `.openrecomp-phase18/contracts/P18-02.md`

## Independent reproduction performed

- Official gate: `python3 .openrecomp-phase18/src/p18_stage_runner_v1.py --stage P18-02
  --script tools/test_phase18_exec_continuation_v1.py --evidence-dir
  .openrecomp-phase18/evidence/P18-02 --tests-json p18_02_tests.json`
  -> runner_status PASS, exit 0, empty stderr, byte-identical dual-run stdout
  (raw and LF), identical evidence artifacts.
- Checks: 66/66 PASS, 0 FAIL. Recovery note: two detached gate runs were
  found racing the same evidence dir after the host restart; both were
  stopped and the canonical gate re-run once cleanly, so the committed
  evidence is from a single uncontended run (plus the independent
  fresh-root reproduction below).
- Independent fresh/private-root reproduction:
  `OPENRECOMP_P18_PRIVATE_BUILD_ROOT=/tmp/p1802-repro-build python3
  tools/test_phase18_exec_continuation_v1.py --evidence-dir /tmp/p1802-repro-ev`
  -> 66/66 PASS, exit 0. All seven artifacts (RESULT.json, continuation.json,
  gpu_state_model.json, poll_exit.json, transcript.json, transcript.sha256,
  p18_02_tests.json) byte-identical (sha256 MATCH) to the official evidence.
- Transcript digest `c4fa0d67039102ef8e61e70e9610b51e64982202373dbeeb982d60c68f071331`
  reproduced exactly.

## What the stage mechanically establishes

- Derived poll geometry (never hard-coded): owner PC `0x8001a9fc`, branch
  `lw; nop; and; beq`, mask `0x04000000` (bit 26), branch target = poll PC,
  fall-through exit `0x8001aa10`; provenance digest reverified against the
  committed P17-06R transcript.
- The emitted runtime's GPUSTAT read is state-driven: bit 26 set iff the
  modelled command FIFO is empty (`s_p18_gpu_pending == 0`); the literal
  Phase-17 zero read model is absent from the generated source; the value
  function contains no guest PC constant (`gpustat_function_pc_free`).
- Authentic execution enters the poll owner, the branch is taken to the
  fall-through exit (exit_detected true, exit_taken_from `0x8001aa08`), and
  the value the guest consumed at the owner carried bit 26 (`0x04000000`).
- Every executed continuation PC is authenticated and carries a provenance
  digest; five new regions authenticated from source bytes; stop reason
  `CONTINUATION_BUDGET_REACHED` (budget-respecting, typed).
- Device transcript is caused by the current execution; every event carries
  an authenticated owning-instruction provenance digest; not replayed.

## Negative / fail-closed controls (all present and passing)

- zero-fill poll not exited (state model disabled -> poll retained);
- unmodelled GPUSTAT bit (28) rejected;
- tampered poll provenance digest rejected;
- event without authenticated owner rejected;
- unexecuted PC rejected;
- overlay anchor fail-closed: missing include / duplicated loop / missing
  harness END all rejected with stable codes.

## Proof boundary

- Promotes NO frame/initialization/playability property.
  `FIRST_FRAME_READY=NO`; all `OPENRECOMP_PHASE18_*` claim markers NOT_PROVEN.
- GP0 writes 0, no GPU command traffic: GP0/GP1 semantics, DMA/ordering-table
  traversal, VRAM mutation and display configuration remain for P18-03..P18-06.
- Phase-17 frozen authority unchanged; Phase 1-17 namespaces untouched.

## Verdict

ACCEPTED. The stage passes its bounded contract with independent reproduction.
next_stage: P18-03.
