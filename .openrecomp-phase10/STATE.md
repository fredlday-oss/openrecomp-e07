# OpenRecomp Phase 10 State

## Mission

Advance Disney's Hercules (`SLUS_005.29`, private legally obtained fixture)
from the frozen Phase-9 private frontier into deterministic native execution
through the existing OpenRecomp architecture, reusing the PS-X EXE ingestion,
PS1 image/memory contract, existing MIPS32 decode/semantics, shared
ProgramModel/CFG/function/call-graph/TU stack, architecture-neutral translation,
host emitter, generic runtime ABI and the Phase-9 PS1 platform boundaries.

No second PS1 frontend, MIPS decoder, CFG pipeline, host emitter or parallel
runtime architecture is created.

## Baseline

- Phase-9 terminal commit `08c639d9032a364163f2985432744be420d402eb`, tree
  `900dccf06ce3d5df7b499a9f05a6ceea060114d7`, branch
  `phase8/mips32-end-to-end-native-v1`.
- Phase-9 terminal verdict `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=PASS`
  for the exact bounded audited public fixture and behaviour only.
- Phase-10 work branch `phase10/ps1-commercial-game-native-v1`.
- Inherited permanent Phase-9 non-claims (never promoted by Phase 10):
  `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN`,
  `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN`.

## Claim markers

- reserved terminal marker (never promoted before `P10-99`):
  `OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=NOT_PROVEN`
- reserved playability marker (promotable only at `P10-99` with milestone G):
  `OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN`
- permanent general marker: `OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN`

## Starting frontier (inherited from Phase 9)

- 4068 reachable words (3972 supported, 96 recognized-unsupported, 0 invalid);
- 3 exception sites, 22 indirect calls, 18 indirect jumps, 3 external traps;
- first unresolved blocker `break` (external trap) at `0x80013390`;
- structure failure `CONTROL_WITHOUT_DELAY_SLOT`;
- BIOS discovery: 3 B0 candidates, 19 `INDIRECT_TARGET_UNKNOWN`;
- statically discoverable I/O-range accesses: 0;
- bounded execution `NOT_ATTEMPTED_BLOCKED_BY_FIRST_UNRESOLVED`.

## Fixture control

- private fixture directory discovered repository-relative; CUE and BIN
  filenames discovered from the directory, never assumed;
- CUE is the authoritative disc-image entry point;
- only non-reconstructive metadata is recorded; no payload bytes, no disc
  sectors, no reconstructive derived data;
- the fixture and the disc are never committed, copied or packaged.

## Stage status

| Stage | Status |
|---|---|
| P10-00 | PASS |
| P10-01 .. P10-12 | QUEUED |
| P10-90, P10-91, P10-99 | QUEUED |

## Stage records

### P10-00 — Phase-10 boundary + fixture/control plane

PASS (192 checks). Gate `tools/test_phase10_boundary_v1.py` run twice through
`.openrecomp-phase10/src/p10_stage_runner_v1.py` with byte-identical stdout
(7108 bytes LF, sha256 `c1c4ed3b...`), empty stderr and exit 0.

- frozen Phase-9 terminal boundary verified: commit
  `08c639d9032a364163f2985432744be420d402eb`, tree
  `900dccf06ce3d5df7b499a9f05a6ceea060114d7`, P9-99 terminal `PASS` for
  `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=PASS`, all 15 required
  Phase-9 stage records `PASS`, 16 frozen Phase-9 file hashes unchanged, no
  `openrecomp-phase9*` tag and the inherited Phase-6/7/8 reconciliations
  intact;
- Phase-10 branch `phase10/ps1-commercial-game-native-v1` descends exactly
  from the Phase-9 terminal commit; only the documented pre-existing Phase-3
  evidence residue differs in the Phase-1..9 trees;
- private fixture/disc identity verified: `SLUS_005.29` (129024 bytes,
  `c230ff5c...`), discovered CUE (101 bytes, `beea454d...`) with one
  `MODE2/2352` track and one referenced BIN (409452624 bytes,
  `2ce144ba...`), ISO9660 PVD at LBA 16, `SYSTEM.CNF;1` declaring
  `BOOT = cdrom:SLUS_005.29;1`, and boot extent LBA 23 byte-identical to the
  primary executable;
- inherited frontier reproduced exactly: 4068 reachable words, `break` at
  `0x80013390`, `CONTROL_WITHOUT_DELAY_SLOT`,
  `NOT_ATTEMPTED_BLOCKED_BY_FIRST_UNRESOLVED`;
- control plane, policies, evidence schema, frozen queue (`P10-01` ..
  `P10-99`), source manifest and stage runner created;
- no substantive compatibility implementation; all four claim markers remain
  unpromoted.
- evidence: `.openrecomp-phase10/evidence/P10-00/`.

## Open blockers

- none at the P10-00 boundary.
