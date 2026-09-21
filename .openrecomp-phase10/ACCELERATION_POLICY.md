# OpenRecomp Phase 10 Acceleration Policy

Phase 10 inherits the Phase-9 acceleration discipline and tightens it for a
private, dynamically driven workload.

1. One serial mutating frontier. Parallel activity is read-only only.
2. Fixed small stage queue (`P10-00` .. `P10-99`) frozen at the P10-00 `PASS`
   boundary. No silent stage insertion, merge, split or redefinition.
3. Targeted intermediate gates. Intermediate stages run their own gate, direct
   dependency gates, source/provenance checks and specifically affected
   regression gates. The expensive whole-project regression is reserved for
   `P10-90`.
4. Test before implementation. For every newly exposed blocker: classify the
   missing behaviour exactly; check whether an existing implementation already
   models it; construct the smallest legal/public reproducer where practical;
   define expected/reference behaviour independently; demonstrate failure for
   the expected reason; implement the smallest reusable fix; rerun targeted
   tests; rerun the Hercules frontier analysis. No speculative compatibility.
5. Fail closed. Unknown behaviour stays explicit.
6. Immutable-hash analysis cache. Cache provenance includes, as applicable, the
   executable SHA-256, CUE SHA-256, BIN SHA-256, frontend version, semantic
   version, analysis configuration, runtime version and disc-model version. A
   cache hit is never accepted merely because filenames are unchanged.
7. Incremental build. Stable generated filenames and content hashes; unchanged
   generated sources are not rebuilt during development. A clean,
   independently audited rebuild is still required before terminal closure.
8. Auto-continue on `PASS`: implement -> official gate -> capture
   stdout/stderr/result evidence -> second deterministic official run -> verify
   identity -> update `STATE.md` / `HANDOFF.md` / `STAGE_QUEUE.md` -> update
   hashes/manifests -> `git status` -> commit -> continue.
9. Stop only for a real reason (see `CONTROL_POLICY.md` stop markers).

## Bounded execution policy

Dynamic advance is bounded by an explicit step budget and an explicit
fail-closed category. Every bounded run records:

- guest entry state and memory-image identity;
- the translated control-flow trace identity (digest, never raw guest bytes);
- counters for services, MMIO, traps, unresolved control flow and reads/writes;
- the exact termination category and first blocker.

Bounded execution never converts an unknown device interaction or an
unresolved indirect target into success.
