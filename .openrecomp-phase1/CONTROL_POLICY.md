# OPENRECOMP PHASE 1 CONTROL POLICY

## Mission

Prove that OpenRecomp can host multiple guest CPU architectures and platform integrations while preserving existing behavior.

Execution is sequential and evidence-gated:

`audit -> implement -> build -> verify -> evidence -> checkpoint -> next stage`

## Autonomous behavior

OpenCode should continue from one passed stage to the next without asking for confirmation when:
- the next stage is listed in `STAGE_QUEUE.md`;
- required inputs are present;
- planned changes are reversible source changes;
- baseline verification remains healthy;
- no semantic choice lacks evidence.

OpenCode must stop and record a blocker when:
- authoritative CPU/platform semantics conflict;
- required local test assets are absent and cannot be synthesized legally;
- baseline tests fail for reasons unrelated to the current stage;
- the next action would delete/overwrite unrelated work;
- a change would require weakening an existing correctness gate;
- evidence is insufficient to choose among materially different implementations.

## Single-agent rule

No subagents, no parallel architecture workers, no multiple worktrees for simultaneous Phase-1 implementation.

## Evidence rule

For each stage create a compact record when practical:

`.openrecomp-phase1/evidence/<stage-id>/RESULT.md`

It should include:
- stage ID;
- source revision/working-tree state;
- files changed;
- verification commands;
- exact pass/fail results;
- semantic assumptions;
- remaining limitations;
- verdict: `PASS`, `FAIL`, or `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE`.

## Git rule

Do not commit merely because code compiles. Commit only at a coherent passed checkpoint if repository conventions permit it. Never discard unrelated dirty work.

## Context rule

If the session becomes too large or uncertain, write `HANDOFF.md`, preserving exact state, then stop cleanly. A new session can run `/phase1-run`.

## External local ROM policy

Read ROM_PATHS.md before any cartridge/platform compatibility stage.
The configured ROM root is $RomRoot.
ROMs are local verification inputs only and remain outside the Git repository.
The workflow may inspect headers, execute them through local verification paths, and record hashes/results.
It must never copy, modify, or commit the ROM files.
