# P10-00 result: Phase-10 boundary + fixture/control plane

Status: `PASS` (192 checks)

Markers:

- `OPENRECOMP_P10_00=PASS`
- `OPENRECOMP_PHASE10_BOUNDARY_V1=PASS tests=192`
- `OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase10_boundary_v1.py`.

## Frozen boundary verified

- Phase-9 terminal commit `08c639d9032a364163f2985432744be420d402eb`, tree
  `900dccf06ce3d5df7b499a9f05a6ceea060114d7`, branch
  `phase8/mips32-end-to-end-native-v1`; the Phase-10 branch
  `phase10/ps1-commercial-game-native-v1` descends from it;
- P9-99 terminal verdict `decision: PASS`,
  `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=PASS`, and the 15 required
  Phase-9 stage records `P9-00` .. `P9-12`, `P9-90`, `P9-91` all `PASS`;
- sixteen frozen Phase-9 terminal/control-plane file hashes verified
  unchanged (`baseline.json`);
- no `openrecomp-phase9*` tag exists (`ABSENT_RECONCILED`); the inherited
  Phase-6/Phase-7/Phase-8 reconciliations verify (absent Phase-6 tag, frozen
  Phase-7 annotated tag object/commit/tree, absent Phase-8 tag);
- the frozen Phase-9 source manifest still verifies (`=PASS entries=35`);
- the only tracked Phase-1..9 working-tree difference from the baseline commit
  is the documented pre-existing Phase-3 evidence residue
  (`.openrecomp-phase3/evidence/P3-00/p3_00_tests.json`,
  `.openrecomp-phase3/evidence/P3-00/residue_manifest.txt`); no new prior
  residue exists.

## Toolchains

`python 3.11.9`, `git 2.55.0.windows.3`, `clang 22.1.8`, `clang-cl 22.1.8`,
`lld-link 22.1.8`, `ninja 1.13.2`, `cmake 4.4.3`, `zig 0.13.0`
(`toolchains.json`).

## Private fixture and disc identity

- executable `SLUS_005.29`, size 129024, SHA-256
  `c230ff5cd14bdfa392f5d5765c9c907b631875aaaa7844792b38b9ac54930f6f`;
  PS-X EXE entry `0x800132e8`, text `0x80010000` + `0x0001f000`, stack
  `0x801ffff0`;
- CUE discovered from the fixture directory (101 bytes, SHA-256
  `beea454de356689cdaa06702f4ed76a5474fd125a7460619ee678c1ae8725df2`),
  single `MODE2/2352` track, `INDEX 01 00:00:00`, one referenced BIN
  (409452624 bytes, SHA-256
  `2ce144ba0e1fed6952ad80976814e3033fec6cddfb5e17cdf0294517ea311365`);
- ISO9660 primary volume descriptor at LBA 16 (system identifier
  `PLAYSTATION`, 174087 sectors, root extent LBA 22); `SYSTEM.CNF;1` at LBA 86
  (67 bytes) declares `BOOT = cdrom:SLUS_005.29;1`;
- the boot extent at LBA 23 (129024 bytes) is byte-identical to the primary
  `SLUS_005.29` fixture (`boot_extent_sha256` equals the executable SHA-256),
  confirming the disc and executable belong to the same target.

Only non-reconstructive metadata is recorded: filenames, sizes, hashes, LBA
and byte extents, header fields and classifications. No payload bytes, no
disassembly, no sectors and no disc file contents.

## Inherited frontier reproduction

The unchanged Phase-9 path (PS-X EXE ingestion -> PS1 memory contract ->
frozen Phase-3 decode/frontier -> frozen Phase-8 neutral-structure bridge)
reproduces the inherited frontier exactly:

| Observable | Inherited | Observed |
|---|---|---|
| reachable words | 4068 | 4068 |
| reachable supported | 3972 | 3972 |
| reachable recognized-unsupported | 96 | 96 |
| reachable invalid | 0 | 0 |
| exception sites | 3 | 3 |
| first blocker | `break` (external trap) `0x80013390` | same |
| structure error | `CONTROL_WITHOUT_DELAY_SLOT` | same |
| bounded execution | `NOT_ATTEMPTED_BLOCKED_BY_FIRST_UNRESOLVED` | same |

`frontier.json` records the full inherited summary, the frozen pipeline digest
and the explicit absence of private-code translation, emission or native
build.

## Control plane

Created under `.openrecomp-phase10/`: `CONTROL_POLICY.md`, `FIXTURE_POLICY.md`,
`EVIDENCE_SCHEMA.md`, `SCOPE.md`, `ACCELERATION_POLICY.md`, `STAGE_QUEUE.md`
(frozen rows `P10-01` .. `P10-99`), `STATE.md`, `HANDOFF.md`,
`SOURCE_SHA256SUMS.txt`, `evidence/README.md`, `src/p10_stage_runner_v1.py`,
`src/p10_source_manifest_v1.py`, `src/p10_fixture_identity_v1.py`,
`src/p10_frontier_v1.py` and `tools/test_phase10_boundary_v1.py`.

## No substantive implementation

P10-00 adds no PS1 compatibility behaviour, no instruction semantics, no
device behaviour and no native execution. All four claim markers remain
unpromoted.

## Public safety

Every committed Phase-10 evidence document was leak-checked against the
private payload (no payload hex, no base64, no ASCII payload run, no string
over 128 characters). No private binary material, no host path and no
reconstructive derived data is present.

## Official runs

Command `python .openrecomp-phase10/src/p10_stage_runner_v1.py --stage P10-00
--script tools/test_phase10_boundary_v1.py --evidence-dir
.openrecomp-phase10/evidence/P10-00 --tests-json p10_00_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 7108 bytes (LF), sha256
`c1c4ed3b50644dbfc6e8e8f0fe3c39dfb47b837f379aefe54bb93aa411b1c7d0`; generated
evidence sidecars byte-identical across both runs.

Sidecar identities:

- `baseline.json` `da68eee88f61ff10c40051fd07ab99d31656a0835b146970ace070038645582a`;
- `fixture_identity.json` `449111519b372126ea0e330b05d6883b369b50b42b97fae79e92432d4dd7e014`;
- `frontier.json` `0b4f1c4905852f6195a030d5860ef99a3675ce09933fc252c7f986b05e5441c2`;
- `toolchains.json` `4367b2b8e507864efc5a29722cf5b8fdb30e0d36979086b9842ce078052b6e8c`;
- `p10_00_tests.json` `df3a366a1657e4076754e090aba95b9db21dcad78ee672fffa56c66fba60c126`;
- `official_runs.json` `cdfef75567aeac59ec3e485557bf8886f98ddb172cc9f733db2f4ab53a44e95a`;
- `determinism.json` `c8ea62b356b56a38e9825db0275f560c2d59a0597f26087ec9d2592119299112`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Claim-ledger delta

`PROVEN` (boundary/control plane only): the frozen Phase-9 boundary, fixture
and disc identity, SYSTEM.CNF boot relationship and the inherited frontier
reproduction. `BOUNDED` (private only): the frontier record. Native execution,
playability and general PS1 compatibility remain `NOT_PROVEN`.

## Next stage

`P10-01` - BREAK semantic classification of the `break` at `0x80013390`.
