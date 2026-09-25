# OpenRecomp Phase 17 Scope

## Mission

Advance OpenRecomp autonomously from the frozen Phase-16 terminal checkpoint
(`a0c26e882ca65cfc84cbec78f7e787509a4992a3`) to establish:

1. A clean, additive Phase-17 control plane bound to the exact predecessor commit.
2. Mechanical verification that Phase-1 through Phase-16 files and frozen evidence
   remain unmodified from their terminal commits.
3. Definition of the Phase-17 target markers and claim boundaries.
4. Deterministic dual-run stage-runner behavior for Phase-17 gates.
5. Private-fixture fail-closed checks (fixture present and hash-verified for
   private tests; synthetic-only path available for public tests).
6. Source-manifest discipline for all Phase-17 code and gates.
7. A `P17-00` bootstrap gate that records the boundary and freezes the stage queue.

## Non-Goals

- Decoding or disassembling the TITLE overlay payload.
- Replacing the Phase-16 TITLE execution path.
- Modifying runtime implementation.
- Executing later Phase-17 stages.
- Promoting initialization, frame, playability, or general compatibility claims.
- Committing fixture bytes, sectors, private absolute paths, or reconstructive payload material.
