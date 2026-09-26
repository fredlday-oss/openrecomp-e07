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
HUMAN_REVIEW_REQUIRED. Reopen P17-04 through P17-07 before any terminal verdict: the historical gate PASS records are insufficient to establish emitted executable guest code, live Exec dispatch/ablation, authentic instruction execution, or device observations. See `.openrecomp-phase17/REVIEW_REQUIRED.md`. Do not run P17-90/P17-91/P17-99 as proof-promoting gates or promote the bounded frontier marker. Controller must be clean after this classification is committed; source checksum and canonical frozen integrity must remain PASS.

## Exact handoff checkpoint
- Branch: `phase17/ps1-title-overlay-recompile-v1`; review-stop classification commit: `62f716e933eda7a8b4e6aaad35ccc038615a01cc`. This handoff checkpoint is committed after that classification.
- Review-stop changed files: `.openrecomp-phase17/STATE.md`, `.openrecomp-phase17/STAGE_QUEUE.md`, `.openrecomp-phase17/HANDOFF.md`, `.openrecomp-phase17/REVIEW_REQUIRED.md`. The P17-04 through P17-07 candidate implementations and their historical evidence remain committed and untouched.
- Verification from controller: `sha256sum -c .openrecomp-phase17/SOURCE_SHA256SUMS.txt` passed all Phase-17 source entries; `python3 .openrecomp-phase17/src/p17_frozen_phase16_integrity_v1.py` reported canonical frozen Phase-16 source integrity PASS and classified the legacy native CRLF/LF gate as PRE_EXISTING_FAIL. P17-06 and P17-07 official dual-run runners each reported identical stdout/artifacts, empty stderr, and zero exit status; these are historical gate outcomes, not proof of guest execution.
- Unresolved evidence: no executable TITLE guest-code emission from P17-02 records, no live A0:0x43 dispatch and ablation, no semantically executed/digested guest state or verified first frontier, and no checked device transcript. The recorded `0x800380bc` value is from an address-walk and MUST NOT be reported as an authentic execution frontier.
- Exact next action: obtain human review of a replacement P17-04/P17-05/P17-06/P17-07 contract that authenticates the executable representation, runs actual guest semantics with verified inputs, and proves live dispatch and transcript causality. No further proof-state promotion before those gates are replaced and verified.
