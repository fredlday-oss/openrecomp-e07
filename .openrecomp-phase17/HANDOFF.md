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
P17-04R Revision 3 implementation completed and verified: authenticated private TITLE word → fresh decode → SemanticRecord binding, MIPS branch/JR/JALR delay-slot timing, reusable persistent guest-state execution interface, active-path exclusion of Phase-16 hand-authored TITLE_TRANSITION_CODE and the rejected P17-04 address-inventory path, and deterministic official reruns. Remaining stages (P17-05R onward) require a replacement contract and human review. Do not run P17-90/P17-91/P17-99 as proof-promoting gates or promote the bounded frontier marker beyond P17-04R.

## Exact handoff checkpoint
- Branch: `phase17/ps1-title-overlay-recompile-v1`; P17-04R Revision 3 implementation commit pending on this worker branch directly atop base `52e51d12d9eb5907e62c8de803c4f656b841d909`.
- Changed files: `.openrecomp-phase17/src/p17_title_exec_emit_v1.py`, `tools/test_phase17_title_exec_emission_v1.py`, `.openrecomp-phase17/SOURCE_SHA256SUMS.txt`, `.openrecomp-phase17/STATE.md`, `.openrecomp-phase17/HANDOFF.md`, and generated P17-04R evidence under `.openrecomp-phase17/evidence/P17-04R/`. Phase-1 through Phase-16 files and historical P17-04 through P17-07 `RESULT.json` records are untouched.
- Verification from worker: `python3 tools/test_phase17_title_exec_emission_v1.py --evidence-dir .openrecomp-phase17/evidence/P17-04R` reports `OPENRECOMP_P17_04R=PASS` and all 57 checks pass; `python3 .openrecomp-phase17/src/p17_stage_runner_v1.py --stage P17-04R --script tools/test_phase17_title_exec_emission_v1.py --evidence-dir .openrecomp-phase17/evidence/P17-04R --tests-json p17_04r_tests.json --runs 2` reports `runner_status: PASS`, identical stdout/artifacts, empty stderr, and zero exit status; `sha256sum -c .openrecomp-phase17/SOURCE_SHA256SUMS.txt` passes all Phase-17 source entries; `python3 .openrecomp-phase17/src/p17_frozen_phase16_integrity_v1.py` reports `OPENRECOMP_PHASE17_P16_SOURCE_INTEGRITY=PASS`; `git diff --check` is clean and no Phase-1 through Phase-16 files are modified.
- Unresolved evidence: P17-05R (live Exec dispatch/ablation), P17-06R (verified first-frame frontier), P17-07R (checked device transcript), and all later terminal proof claims remain unproven. The mandated `NOT_PROVEN` proof fields are preserved.
