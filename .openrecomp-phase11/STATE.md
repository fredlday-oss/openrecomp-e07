# OpenRecomp Phase 11 State

## Mission

Advance the exact audited private Hercules fixture (`SLUS_005.29`, legally
obtained, outside version control) beyond the Phase-10 milestone A and
establish the strongest reproducibly proven playability milestone possible,
through the existing OpenRecomp architecture. No second PS1 frontend, MIPS
decoder, CFG pipeline, host emitter or runtime is created; only
evidence-demonstrated gaps are extended.

## Baseline

- Phase-10 terminal commit `8961682aa36e14db979e8e8dbe88e04fa2b4c87a`, tree
  `4a58d9238d76a490560c588bb470fd9e6a58cafe`, branch
  `phase10/ps1-commercial-game-native-v1`.
- Phase-10 terminal verdict
  `OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=PASS` bounded to the
  exact private fixture and the demonstrated milestone A only.
- Inherited permanent Phase-10 non-claims (never promoted by Phase 11):
  `OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN`,
  `OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN`.
- Phase-11 work branch: `phase11/ps1-playability-v1`.

## Claim markers

- `OPENRECOMP_PHASE11_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN` (promote only
  if milestone B is actually proven)
- `OPENRECOMP_PHASE11_HERCULES_FRAME_PROOF=NOT_PROVEN` (promote only if
  milestone D is actually proven)
- `OPENRECOMP_PHASE11_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN` (promote only if
  milestone G is actually proven)
- `OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)

## Terminal status

STATUS=IN_PROGRESS
FINAL_VERDICT=PENDING
OPENRECOMP_PHASE11_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN
OPENRECOMP_PHASE11_HERCULES_FRAME_PROOF=NOT_PROVEN
OPENRECOMP_PHASE11_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN
OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN

## Inherited frontier (from Phase 10)

- milestone A: translated native execution begins (PROVEN, `P10-05`/`P10-11`);
- 110 translated functions; deterministic native run; original MIPS machine
  code never executes;
- first fail-closed event: an executed unresolved indirect jump inside the
  initialisation path;
- the reached loop is a served busy-poll loop (GPU status and timer1 counter
  read exactly one-to-one, 109035 each), not a frame loop;
- 65536 recorded GPU events, all GP1 status reads returning the audited
  `GPUSTAT_STUB` `0x14802000`; zero GP0/GP1 command writes;
- the GPU status stub A/B experiment shows identical access traffic, so GPU
  status polling is not the causal blocker;
- interrupt/DMA/memory-control behaviour remains fail-closed;
- CD-ROM reached register-level command traffic only; no disc-data path;
- controller data port never touched; SPU configuration only;
- milestones B .. G remain NOT_PROVEN.

## Stage status

| Stage | Status |
|---|---|
| P11-00 | PASS |
| P11-01 | PENDING |
| P11-02 | PENDING |
| P11-03 | PENDING |
| P11-04 | PENDING |
| P11-05 | PENDING |
| P11-06 | PENDING |
| P11-07 | PENDING |
| P11-08 | PENDING |
| P11-09 | PENDING |
| P11-10 | PENDING |
| P11-11 | PENDING |
| P11-12 | PENDING |
| P11-90 | PENDING |
| P11-91 | PENDING |
| P11-99 | PENDING |

## Stage records

### P11-00 — Phase-11 boundary + control plane

PASS (482 checks). Gate `tools/test_phase11_boundary_v1.py` run twice through
the Phase-11 stage runner with byte-identical stdout (17748 bytes LF, sha256
`5bb0760d...`), empty stderr and exit 0.

- frozen Phase-10 terminal boundary verified: commit
  `8961682aa36e14db979e8e8dbe88e04fa2b4c87a`, tree
  `4a58d9238d76a490560c588bb470fd9e6a58cafe`, 25 frozen control/terminal
  hashes, the 135-file Phase-10 evidence index verified file-by-file, all 16
  Phase-10 stage records `PASS` with `failed=0` and terminal counts `P10-90`
  155 / `P10-91` 323 / `P10-99` 166 (2277 recorded checks), the frozen
  Phase-9 and Phase-10 source manifests unchanged, and the inherited tag
  reconciliations intact;
- private fixture/disc identity re-verified exactly (`SLUS_005.29`
  `c230ff5c...`, CUE `beea454d...`, BIN `2ce144ba...`, ISO9660 space size
  174087, root extent LBA 22, boot extent byte-identical to the executable);
- frozen structure and emission identities reproduced live (3433 neutral
  instructions, 739 blocks, 110 functions, program fingerprint `a047a52f...`,
  image unit `77a34044...`, no guest payload bytes, no opcode dispatch);
- milestone A reproduced live: two isolated builds byte-identical, two native
  runs byte-identical, `failed=1`, `error=unresolved indirect jump`,
  reads 982859, writes 799023, denied 11, host calls 79, access count 2000005
  against budget 2000000, RAM digest `0x18131c6ef356df7d`, GPU status 109035
  and timer1 109035, and the crt0-observable register values;
- inherited non-claims re-verified: B..G not established, zero GPU command
  writes, GPU status polling non-causal (A/B identical traffic), no disc data
  path, no controller access, no frame loop;
- Phase-11 control plane, policies, evidence schema and frozen queue
  (`P11-01` .. `P11-99`), source manifest and stage runner created;
- no substantive compatibility implementation; all four claim markers remain
  unpromoted;
- evidence: `.openrecomp-phase11/evidence/P11-00/`.

## Working-tree residue (preserve untouched)

Tracked Phase-3 evidence files under `.openrecomp-phase3/evidence/P3-00/` are
modified by a historical verification-context re-run, and untracked residue
exists under `.openrecomp-phase2/`, `.openrecomp-phase3/`, `artifacts/` and
`tools/test_build_package_reproducibility_v1.py`. This residue predates Phase
10 and must never be committed, deleted or altered by Phase-11 work.

## Open blockers

- none recorded yet.
