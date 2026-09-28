# P18-04 Controller Review

Stage: P18-04 - GPU Command Frontier
Controller: main (OpenRecomp autonomous controller)
Branch: agent/phase18-p18-04 (worker lane), integrated to phase18/ps1-first-frame-frontier-v1
Reviewed against: committed contract `.openrecomp-phase18/contracts/P18-04.md`

## Provenance of this work

Bounded implementation worker (deepseek-v4-pro) delivered a clean candidate commit
after the P18-03 rework pattern. Controller inspected the module and gate, integrated
the lane by fast-forward, ran the authoritative dual gate itself, and then ran an
independent fresh-private-root reproduction.

## Independent reproduction performed

- Worker candidate: f22e0ae68c5139fc3c07f0815ba39cde7c41c587, base 8c031f3 confirmed ancestor,
  clean tree, no frozen Phase 1-17 paths touched.
- Controller authoritative dual gate:
  `python3 .openrecomp-phase18/src/p18_stage_runner_v1.py --stage P18-04 --script
  tools/test_phase18_gpu_command_frontier_v1.py --evidence-dir
  .openrecomp-phase18/evidence/P18-04 --tests-json p18_04_tests.json`
  -> runner_status PASS, exit 0, empty stderr both runs, markers present both,
  tests_json present both, raw and LF stdout byte-identical.
- Fresh-root reproduction executed by the controller on the worker lane with a
  private build root; all P18-04 evidence artifacts byte-identical to the official
  controller evidence set.

## What the stage mechanically establishes

- Establishes the GPU command frontier as a real, evidence-backed state rather than
  an assumed one: the continuation executes 8270 instructions (8192 continuation
  budget, stop CONTINUATION_BUDGET_REACHED) with zero GP0 and zero GP1 writes and an
  empty FIFO tap.
- Proves the reachable-not-reached distinction: the generated runtime contains a
  genuine state-driven GP0/GP1 write path gated on exactly 0x1f801810/0x1f801814
  with a single write gate, both literals present, and a write function free of any
  guest-PC constant; the frontier is therefore a real unreached state, not a missing
  code path.
- Proves the path, tap and classifier are genuine via a controlled probe compiled
  against the official generated source, driving the generated GPU write entry points
  and producing real GP0/GP1 frontier events (GP0=1, GP1=1; classes POLYGON and
  GP1_CONTROL).
- Records that no reached instruction materialises the 0x1f80 window high half
  (759 reached PCs examined against 103424 records; zero high-half sites).
- Unknown command words classify UNKNOWN and are never silently a no-op; all
  fail-closed controls pass.

## Proof boundary

- Promotes NO frame/initialization/playability property. `FIRST_FRAME_READY=NO`;
  all `OPENRECOMP_PHASE18_*` claims NOT_PROVEN.
- GP0/GP1 command semantics remain unexercised on the authentic path: no GP0/GP1
  write was reached during the bounded continuation. Decoding and applying real
  command semantics remains for P18-05..P18-06, gated on authentic traffic.
- The controlled probe is explicitly an evidence class PRIVATE_FIXTURE_BOUNDED and
  is not counted as authentic-execution proof.
- Phase-17 frozen authority unchanged; Phase 1-17 namespaces untouched.

## Verdict

ACCEPTED. The stage passes its bounded contract with independent reproduction.
next_stage: P18-05.
