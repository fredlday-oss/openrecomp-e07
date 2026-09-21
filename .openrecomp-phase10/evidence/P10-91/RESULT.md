# P10-91 result: evidence closure and proof matrix

Status: `PASS` (323 checks)

Markers:

- `OPENRECOMP_P10_91=PASS`
- `OPENRECOMP_PHASE10_EVIDENCE_CLOSURE_V1=PASS tests=323`
- `OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase10_evidence_closure_v1.py`.

## Stage-record closure

All fourteen completed stage records (`P10-00` .. `P10-12`, `P10-90`) exist
with `RESULT.md`, a machine-readable tests record, two byte-identical official
runs, empty stderr, exit 0, the reserved markers present, and every sidecar hash
recorded in `official_runs.json` matching the file on disk.

`P10-00` was re-issued during this stage: its committed tests record held the
earlier 112-check revision while the official stdout capture and the current
gate hold 192 checks, so the recorded tests-record hash did not match the
committed file. The re-issued stdout capture is byte-identical (raw 7305 bytes
`497ef9f9...`, LF 7108 bytes `c1c4ed3b...`) and the record is now consistent;
the re-issue is documented in the `P10-00` record.

## Evidence index

135 committed Phase-10 evidence files indexed (excluding this stage's own
generated sidecars and the post-index terminal stage), 663483 bytes, exact
SHA-256 and size per entry; the committed index equals the live index.

## Proof matrix

- exact private fixture identity: executable (129024 bytes), CUE (101 bytes,
  one `MODE2/2352` track, `INDEX 01 00:00:00`), referenced BIN (409452624
  bytes), ISO9660 volume (PVD LBA 16, 174087 sectors, root extent LBA 22) and
  the `SYSTEM.CNF` boot relationship (boot target `SLUS_005.29`, boot extent
  byte-identical to the executable);
- native execution state: guest entry `0x800132e8`, 982859 reads / 799023
  writes / 11 denied / 79 host calls, access budget 2000000 with 2000005
  accesses and 5 budget denials, termination `UNRESOLVED_INDIRECT_JUMP`,
  deterministic;
- highest demonstrated milestone: **A**; milestones B..G not established;
- frontiers: structure (739 blocks, 209 internal / 22 unresolved call edges,
  110 units, first unresolved indirect site `0x80013e7c`), semantics (0 unruled
  reachable ops, 3 trap sites, 22 `jalr` sites), BIOS (3 B0 vector calls, 19
  unresolved, fail-closed, no BIOS image), I/O (1107 static access sites, 4
  dynamically observed devices), GPU (65536 GP1 status reads, zero command
  writes, zero unknown commands, no GPU-side blocker), timing (218112 served
  observations; denial reconciliation 11 = 6 platform + 5 budget), disc
  (`READ_N` 4 / `SET_MODE` 4 / `SET_LOCATION` 1 / unknown `0x80` 1, no data
  path), controller/SPU/game loop (controller not reached, SPU 5 events, served
  busy-poll loop, no frame loop);
- deliberate exclusions and unresolved blockers recorded explicitly.

## Claim ledger

- classes `PROVEN` / `BOUNDED` / `NOT_PROVEN` / `NOT_TESTED` with 36 classified
  claims;
- reserved markers unpromoted: native-execution proof `NOT_PROVEN`, playability
  `NOT_PROVEN`; permanent general PS1 compatibility `NOT_PROVEN`;
- milestones B..G, BIOS emulation, GPU rendering, SPU synthesis, CD-ROM
  reading, controller consumption, interrupt delivery, DMA transfer and
  cycle-accurate timing all `NOT_PROVEN`; arbitrary PS-X EXE compatibility and
  the unimplemented devices `NOT_TESTED`.

## Public safety

The index scan finds no private payload hex/base64/ASCII run, no absolute host
path and no non-text evidence file; the Phase-10 source manifest verifies
(`=PASS entries=34`).

## Official runs

Command `python .openrecomp-phase10/src/p10_stage_runner_v1.py --stage P10-91
--script tools/test_phase10_evidence_closure_v1.py --evidence-dir
.openrecomp-phase10/evidence/P10-91 --tests-json p10_91_tests.json`, exit 0,
empty stderr, both runs byte-identical: raw stdout 11212 bytes sha256
`2b09fb02c33e2459fb2f3f088d23bf75f0bc014d052f420e026d4d808fb44cd4`, LF capture
10884 bytes sha256
`07497098fc322610dc1c200b370ab989ca2b6f576448fd33c84ea6d09e287074`; both
generated sidecars byte-identical across the runs.

Sidecar identities:

- `evidence_index.json` `640575858d5c548fbb8c4604ca1744c1f60e6e00414962c9daa73908ff206213`;
- `proof_matrix.json` `aaf543ab6f4e4e343a447f29785797996a6e12c9276ecba6439524f57b7fd5db`;
- `claim_ledger.json` `7ff2425771d23840e8630ba6fc2254fa6159a442963be6726926bd6b195e5371`;
- `p10_91_tests.json` `26a9965e5367c6547b440b6aea8c0686fe5ae3f9fbbbe2c79f787f8bcba64689`;
- `official_runs.json` `5f5b4a0dc355a0e9f1c0c7c60f4619d54c3e7afdfe57bad0a1fd3db72f1b8c3c`;
- `determinism.json` `8911b8e21d55a3406f0eff147a4520952f1d0e50180ff09caa3b1b66121fe2d2`;
- `run1.txt` = `run2.txt` `07497098fc322610dc1c200b370ab989ca2b6f576448fd33c84ea6d09e287074`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Claim-ledger delta

None promoted. The terminal native-execution proof and the playability marker
stay `NOT_PROVEN` for `P10-99` to decide; the permanent general PS1
compatibility marker stays `NOT_PROVEN`. The highest demonstrated milestone
remains `A`.

## Next stage

`P10-99` - final bounded verdict.
