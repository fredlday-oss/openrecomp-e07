# OpenRecomp Phase 17 Handoff

## Summary
Phase 17 advances from the completed Phase-16 checkpoint (`a0c26e882ca65cfc84cbec78f7e787509a4992a3`). `P17-00` established the control plane and frozen baseline. `P17-01` authenticates the Hercules disc fixture and ingests the bounded PS-X EXE. `P17-02` now authenticates the TITLE payload and emits a fail-closed, non-reconstructive decode/direct-control-flow projection with deterministic evidence.

## Completed
- `P17-00` bootstrap gate passes with dual-run determinism.
- `P17-01` title ingestion gate passes with dual-run determinism.
- ISO 9660 reader validates sync, mode, Form-1 subheader, directory-record endian fields, and file geometry.
- Frozen Phase-16 boundary and canonical integrity gates remain intact.
- Public-safe evidence contains no private absolute paths, fixture bytes, or reconstructive payload material.
- `P17-02` authoritative dual-run gate passes from the controller at commit `30a0b5a6effd3c84ab45782c998fba46e57a27da`.
- P17-02 evidence is deterministic across official runs and repeated controller invocations; source integrity and canonical frozen Phase-16 integrity pass.

## Invariants
1. Commit `a0c26e882ca65cfc84cbec78f7e787509a4992a3` is the immutable ancestor.
2. Phase-1 through Phase-16 files and evidence are frozen.
3. No guest binary bytes committed to Git.
4. The P17-01 `TITLE_PAYLOAD_DECODING_POLICY_V1=NOT_DECODED` marker remains historical to P17-01; P17-02 has authenticated decode evidence under `TITLE_IR_CONTRACT_V1=PASS`.

## Next Action
P17-05R implementation completed by the worker (controller review pending): authenticates the main-EXE payload region (`SLUS_005.29`) from source bytes (SHA-256 -> PS-X EXE header -> file offset -> guest load address -> instruction word -> fresh decode -> emitted record), extends the P17-04R authenticated record set with the 6 main-EXE records reachable from the recorded frontier entry `0x80011af0`, resumes the recorded P17-04R frontier state (37 TITLE instructions, delay slot `0x80038130`) and continues real authenticated guest execution (6 newly authenticated main-EXE instructions, bound 4096) to the typed frontier `stop_reason=PC_NOT_IN_AUTHENTICATED_TABLE`, `last_successfully_executed_pc=0x8004ffc0`, `attempted_frontier_pc=0x80026cc8`, `frontier_pc=0x80026cc8`. next_stage = P17-06R. Do not promote any proof marker beyond P17-05R.

## Previous action (P17-04R Revision 4)
P17-04R Revision 4 implementation completed and verified: authenticated private TITLE word → fresh decode → SemanticRecord binding; authentic JAL pending-transfer semantics with the delay-slot instruction attempted and the transfer applied only afterwards (or a fail-closed stop at the authentic delay-slot PC); persisted private build artifacts (generated source/headers, full private authenticated mapping, compiled shared object/executable, build metadata) under the configured private build root; separated implemented vs exercised semantic vocabulary derived from the actual execution trace; linkage-level exclusion of the Phase-16 hand-authored `TITLE_TRANSITION_CODE` / `p16_emission_v1` / `p16_record_title_transition` machinery; and deterministic official reruns. next_stage = P17-05R. Remaining stages (P17-05R onward) require a replacement contract and human review. Do not run P17-90/P17-91/P17-99 as proof-promoting gates or promote the bounded frontier marker beyond P17-04R.

## Exact handoff checkpoint
- next_stage: P17-06R
- base_commit: `36be03b5756726a20ecd69735b41cb5eba795155`; worker branch `agent/deepseek-phase17-p17-05r-r1`.
- resulting_candidate_commit: `PENDING_FINAL_COMMIT` (`git rev-parse agent/deepseek-phase17-p17-05r-r1`).
- P17-05R changed files: `.openrecomp-phase17/src/p17_mainexe_auth_v1.py` (new), `.openrecomp-phase17/src/p17_title_exec_continuation_v1.py` (new), `.openrecomp-phase17/src/p17_title_exec_emit_v1.py` (multi-region word resolver hook; default behaviour unchanged), `tools/test_phase17_title_exec_continuation_v1.py` (new), `.openrecomp-phase17/SOURCE_SHA256SUMS.txt`, `.openrecomp-phase17/STATE.md`, `.openrecomp-phase17/HANDOFF.md`, `.openrecomp-phase17/STAGE_QUEUE.md`, and regenerated P17-05R evidence under `.openrecomp-phase17/evidence/P17-05R/`.
- P17-05R verification: `python3 tools/test_phase17_title_exec_continuation_v1.py --evidence-dir .openrecomp-phase17/evidence/P17-05R` reports `OPENRECOMP_P17_05R=PASS`; the stage runner reports `runner_status: PASS` with identical stdout/artifacts, empty stderr and zero exit status from two fresh private build roots.
- P17-04R handoff checkpoint (historical): next_stage `P17-05R`; base_commit `937e5fa0a8e353808620b82b0203ab608e2d8cf4`; worker branch `agent/kimi-phase17-p17-04r-rev4`.
- Changed files: `.openrecomp-phase17/src/p17_title_exec_emit_v1.py`, `.openrecomp-phase17/src/p17_linkage_exclusion_v1.py` (new), `.openrecomp-phase17/src/p17_stage_runner_v1.py`, `tools/test_phase17_title_exec_emission_v1.py`, `tools/test_phase17_persistence_v1.py` (new), `.openrecomp-phase17/SOURCE_SHA256SUMS.txt`, `.openrecomp-phase17/STATE.md`, `.openrecomp-phase17/HANDOFF.md`, and regenerated P17-04R evidence under `.openrecomp-phase17/evidence/P17-04R/`. Phase-1 through Phase-16 files and historical P17-04 through P17-07 `RESULT.json` records are untouched.
- Verification from worker: `python3 tools/test_phase17_title_exec_emission_v1.py --evidence-dir .openrecomp-phase17/evidence/P17-04R` reports `OPENRECOMP_P17_04R=PASS` and `OPENRECOMP_P17_04R_REV4=PASS` with every check PASS; `python3 .openrecomp-phase17/src/p17_stage_runner_v1.py --stage P17-04R --script tools/test_phase17_title_exec_emission_v1.py --evidence-dir .openrecomp-phase17/evidence/P17-04R --tests-json p17_04r_tests.json --runs 2` reports `runner_status: PASS`, identical stdout/artifacts, empty stderr, and zero exit status; `sha256sum -c .openrecomp-phase17/SOURCE_SHA256SUMS.txt` passes all Phase-17 source entries; `python3 .openrecomp-phase17/src/p17_frozen_phase16_integrity_v1.py` reports `OPENRECOMP_PHASE17_P16_SOURCE_INTEGRITY=PASS`; `git diff --check` is clean and no Phase-1 through Phase-16 files are modified.
- Unresolved evidence: P17-05R (live Exec dispatch/ablation), P17-06R (verified first-frame frontier), P17-07R (checked device transcript), and all later terminal proof claims remain unproven. The mandated `NOT_PROVEN` proof fields are preserved.

## Controller closure — P17-04R (Revision 4)
- Decision: ACCEPT and INTEGRATE. Integrated by fast-forward to `0ab4e7eb2ed4393cec7f61a79705d2c44bbc4441` (no rebase/cherry-pick).
- Independent controller verification: canonical dual reruns, zero non-PASS, stdout byte-identical, regenerated evidence byte-identical to the committed evidence; persisted private artifacts hash-matched after process exit. See `.openrecomp-phase17/evidence/P17-04R/CONTROLLER_REVIEW.md`.
- Rejected alternative `agent/deepseek-phase17-p17-04r-rev5` (`83cacff`): committed `linkage_exclusion.inspection_digest` does not reproduce from its own committed source; REVISE required.
- Remaining: replacement stages P17-05R / P17-06R / P17-07R and terminal gates P17-90 / P17-91 / P17-99. `NOT_PROVEN` markers unchanged.
