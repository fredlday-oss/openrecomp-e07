# P11-00 result: Phase-11 boundary + control plane

Status: `PASS` (482 checks)

Markers:

- `OPENRECOMP_P11_00=PASS`
- `OPENRECOMP_PHASE11_BOUNDARY_V1=PASS tests=482`
- `OPENRECOMP_PHASE11_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE11_HERCULES_FRAME_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE11_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase11_boundary_v1.py`.

## Frozen Phase-10 boundary

| Item | Value |
|---|---|
| terminal commit | `8961682aa36e14db979e8e8dbe88e04fa2b4c87a` |
| terminal tree | `4a58d9238d76a490560c588bb470fd9e6a58cafe` |
| terminal branch | `phase10/ps1-commercial-game-native-v1` |
| Phase-11 branch | `phase11/ps1-playability-v1` (descends from the terminal commit) |
| terminal verdict | `OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=PASS` |
| inherited playability | `OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN` |
| inherited general | `OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` |

Frozen Phase-10 integrity: 25 frozen control/terminal/evidence hashes verified,
the 135-file Phase-10 evidence index verified file-by-file, all 16 Phase-10
stage records `PASS` with `failed=0` (terminal counts `P10-90` 155,
`P10-91` 323, `P10-99` 166), total 2277 recorded stage checks, and the frozen
Phase-9 and Phase-10 source manifests both verify unchanged.

Inherited non-establishment (all re-verified from the frozen sidecars):
milestones B, C, D, E, F and G are not established; zero GPU command writes;
the GPU status-stub A/B experiment shows identical access traffic (not the
causal blocker); the disc data path was not reached; the controller data port
was not reached; no frame loop was reached.

## Private fixture and Milestone A reproduction

Fixture identity re-verified: `SLUS_005.29` (129024 bytes,
`c230ff5c...`), the discovered CUE (`beea454d...`, one `MODE2/2352` track) and
the referenced BIN (`2ce144ba...`), ISO9660 space size 174087 sectors, root
extent LBA 22, `SYSTEM.CNF` boot target `SLUS_005.29` and a boot extent
byte-identical to the executable.

Frozen structure reproduced live: 3433 neutral instructions, 739 blocks, 110
functions, 110 translation units, 889 edges, 209 internal call edges, 22
unresolved call edges, 635 folded delay slots, 328 non-nop delay slots, 3
exception sites. Frozen emission reproduced live: program fingerprint
`a047a52f...` (520039 bytes), image unit `77a34044...` (750534 bytes), no
guest payload bytes and no opcode dispatch in the generated program.

Live compressed rebuild and two native runs (`.openrecomp-phase11/build/p11-00-repro`,
untracked) reproduce milestone A: byte-identical build product across two
isolated builds, byte-identical stdout across two runs, `failed=1`,
`error=unresolved indirect jump`, reads 982859, writes 799023, denied 11,
host calls 79, access count 2000005 against budget 2000000 (5 budget denials),
17 non-RAM signatures, RAM digest `0x18131c6ef356df7d`, GPU status reads
109035 and timer1 reads 109035, and the crt0-observable register values
(`$gp` `0x8002ed78`, `$fp` `0x80200000`, `$sp` `0x801ffe00`).

The rebuilt executable hash is `22285c26...` and its stdout hash
`99040628...`; these differ from the historical `P10-05` capture because the
Phase-10 runtime composition advanced between `P10-05` and the terminal
composition (event transcript capacity and GPU status stub, documented by
`P10-07`/`P10-08`). The milestone-A observables asserted here are the
composition-independent ones.

Recorded observation (no claim depends on it): the committed `P10-05`
`native_entry.json` `translated_trace.file_sha256` map records the frozen
Phase-9 driver hash while the committed `P10-05` `emission.json` records the
Phase-10 driver composition. The P11-00 gate attests the live rebuild instead
of the historical file-hash map and rewrites no Phase-10 evidence.

## Phase-11 control plane

Created `.openrecomp-phase11/` with `STATE.md`, `HANDOFF.md`,
`STAGE_QUEUE.md`, `CONTROL_POLICY.md`, `SCOPE.md`, `FIXTURE_POLICY.md`,
`EVIDENCE_SCHEMA.md`, `evidence/README.md`, the source manifest and the
deterministic stage runner, plus the `tools/test_phase11_boundary_v1.py` gate.
The frozen queue rows `P11-00` .. `P11-99` are present and reserved.

Toolchains verified present: python, git, clang-cl, lld-link.

## Official runs

Command `python .openrecomp-phase11/src/p11_stage_runner_v1.py --stage P11-00
--script tools/test_phase11_boundary_v1.py --evidence-dir
.openrecomp-phase11/evidence/P11-00 --tests-json p11_00_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 18236 bytes raw / 17748 bytes LF,
sha256 (LF) `5bb0760de329ae71efdcb856f8cecf271b6a2196cae625e35ef7ba5e9f3b6904`;
generated evidence sidecars byte-identical across both runs.

Sidecar identities:

- `baseline.json` `4980615662c45e0e7c19193f5a2399d7502676db6049bba9891dfe98249cdac5`;
- `fixture_identity.json` `3daf28e628c4a945069fbd39a218038b996792fecfe60f409e98a40def445c4f`;
- `frontier.json` `0c693ce4a7821d3f48c5bc2a2d0e43b2eab0b82a1c327c972f0c72607c0865e8`;
- `milestone_inheritance.json` `13c79feb37177b3d08f3b907339ec8c4d73ce7bc5c44a430c5ec2e2bd43f82f1`;
- `p11_00_tests.json` `736bfb1de1e08a9cc448d340597f88c5011dc53e294c5c4cbfb9bd7e0927f83a`;
- `official_runs.json` `12b99ae85d9d012e81ec8ed9da5929c5a114ec79a969b4f6f9b7c2d45d3d02a2`;
- `determinism.json` `8227d41182b91899ff9d172f7edb953c2a537261233ec23fe7c5c160b2a83c7b`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Public safety

The committed record contains hashes, sizes, addresses, counts, classifications,
function/block identifiers, register values, state digests and gate results
only. The gate's public-safety scan (payload hex, base64, printable ASCII runs,
string length) passes on all four sidecars. No payload bytes, no disassembly
excerpts, no strings, no sectors, no framebuffer or VRAM content and no
absolute host paths are present.

## Claim-ledger delta

`PROVEN`: the Phase-10 boundary and integrity chain, the fixture identity, the
frozen structure/emission identity and the live milestone-A reproduction.
`BOUNDED` (private only): the milestone-A observables. Initialization
completion, GPU command stream, frames, title/menu, gameplay, playability and
general PS1 compatibility remain `NOT_PROVEN`.

## Next stage

`P11-01` - milestone-A progress causality: deterministic execution-budget
bisection and trace analysis to identify the exact causal frontier that stops
the guest from advancing beyond the first fail-closed event.
