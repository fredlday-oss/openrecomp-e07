# P9-00 result: Phase-9 boundary and acceleration control plane

Status: `PASS` (95 checks)

Markers:

- `OPENRECOMP_P9_00=PASS`
- `OPENRECOMP_PHASE9_BOUNDARY_V1=PASS tests=95`
- `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)
- `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase9_boundary_v1.py`.

## Frozen Phase-8 baseline

- Phase-8 terminal commit
  `61136fc37cf0810e64241addd8f57a91872bc0af`;
- Phase-8 terminal tree
  `f9262497b82fe0027c3b23432ba7bd8cbccdf433`;
- branch `phase8/mips32-end-to-end-native-v1`, descending from the baseline;
- Phase-8 terminal verdict P8-99 `PASS` with all 15 required stages `PASS`
  (`OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=PASS` for the exact
  bounded audited public Phase-8 fixture and behaviour only);
- no annotated Phase-8 terminal tag exists; the state records
  `BASELINE_TAG_STATUS=ABSENT_RECONCILED` and no tag was fabricated.

## Frozen Phase-8 evidence re-verified on disk

| File | SHA-256 |
|---|---|
| `.openrecomp-phase8/evidence/P8-99/RESULT.md` | `b07c3ec76c591df7999599e0fa5f1f43f0a1854462b45da96bc8523b2cb04204` |
| `.openrecomp-phase8/evidence/P8-99/terminal_verdict.json` | `ffe1b89d1284435cbb9dd53318025ee052ad0fa58b1f8a304736a381712dc693` |
| `.openrecomp-phase8/evidence/P8-99/verdict_record.json` | `fa9d62c79ab6399981e1acedbedbd07a149daec2c6ea4bde1dc7aee3a7d52738` |
| `.openrecomp-phase8/evidence/P8-99/p8_99_tests.json` | `ff8ed0a79569b95810527b1a395ece4aec3b6eedba9054f704cd0dfd1bbd7f77` |
| `.openrecomp-phase8/evidence/P8-99/official_runs.json` | `459c5f397681e49cfb6830d8f1687e5923120bb061864f8319a0c8eb15dc333d` |
| `.openrecomp-phase8/STATE.md` | `ef56426db4f17deef78635a35ea8074ef6c7a5f17926cd18f4687f6bea63bcd4` |
| `.openrecomp-phase8/STAGE_QUEUE.md` | `5f1dc76669db00f766afcb55fa5d943b5b3498333cfc9cc8b6e63971ceeb1fbf` |
| `.openrecomp-phase8/HANDOFF.md` | `01abbc46c810b9da697932d34e3be7b18acab88b54a630ed777ab96f4da60c70` |
| `.openrecomp-phase8/SOURCE_SHA256SUMS.txt` | `5ac27eb1f23ae412a14e94c62a80f811b7a1670e53b404356b49595d1f9f4221` |
| `.openrecomp-phase8/CONTROL_POLICY.md` | `50bd69203c78f8ff45439f133a0b4dd01f54e1dcf4175a1886a49d0effff20b7` |
| `.openrecomp-phase8/SCOPE.md` | `82bc03b864b85509c7eb23a5e1aea124edc431f94d412064fa4d076c6b349ca1` |
| `.openrecomp-phase8/ACCELERATION_POLICY.md` | `02a10bc6aaa9c2d4accd8d9e5eab30c6e608c09d7090148e180dc4babc36bf95` |
| `.openrecomp-phase8/EVIDENCE_SCHEMA.md` | `4c7b4473972bed35bbdc0e6df54d642886b6697112361f2a8f04a6a659b86acf` |
| `.openrecomp-phase8/FIXTURE_POLICY.md` | `723e5794c836371ece147af53039a4134b788c1ea9ee9fc5d52a91edc330f879` |
| `.openrecomp-phase8/evidence/README.md` | `7167bc52738c562ff84e48c58f4381dc858a972cb7044f1cb850d4c5302ccd27` |

The Phase-8 source manifest re-verifies unchanged, no tracked file under
`.openrecomp-phase1` .. `.openrecomp-phase8` changed against the baseline
commit outside the documented pre-existing Phase-3 residue
(`.openrecomp-phase3/evidence/P3-00/p3_00_tests.json`,
`.openrecomp-phase3/evidence/P3-00/residue_manifest.txt`), and no new
untracked residue appears in frozen phases.

## Inherited reconciliations

- historical tag `openrecomp-phase6-pass` absent (`ABSENT_RECONCILED`);
- annotated tag `openrecomp-phase7-pass` object
  `b07e0f691262ed3ae0bc2fd6ebb3e3d3c5222800` -> commit
  `2917aa6549ab975cffdeb50120514c1723f7e493` -> tree
  `59529c130d759ceb1ca9e6c65a510fa373656b01` frozen and untouched;
- `phase7/hardening-v2` line outside every baseline.

## Control plane established

- `.openrecomp-phase9/SCOPE.md` - terminal claim
  `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF` (reserved `NOT_PROVEN`), the
  permanent general-PS1 and Hercules-playability non-claims, public versus
  private evidence rules, the 14-point proof boundary and out-of-scope list;
- `.openrecomp-phase9/CONTROL_POLICY.md` - 18 phase rules and stop markers;
- `.openrecomp-phase9/ACCELERATION_POLICY.md` - fast/terminal gate policy, the
  `openrecomp-phase9-analysis-cache-v1` cache key contract, incremental-build
  policy and private-fixture cache handling;
- `.openrecomp-phase9/FIXTURE_POLICY.md` - public/private/synthetic fixture
  policy and the no-BIOS-image boundary;
- `.openrecomp-phase9/EVIDENCE_SCHEMA.md` - determinism and private-fixture
  evidence rules;
- `.openrecomp-phase9/STAGE_QUEUE.md` - frozen rows `P9-00` .. `P9-99` in the
  fixed order;
- `.openrecomp-phase9/STATE.md`, `.openrecomp-phase9/HANDOFF.md`,
  `.openrecomp-phase9/evidence/README.md`, `.openrecomp-phase9/.gitignore`;
- `.openrecomp-phase9/src/p9_source_manifest_v1.py` (manifest helper) and
  `.openrecomp-phase9/src/p9_stage_runner_v1.py` (deterministic two-run stage
  runner);
- `tools/test_phase9_boundary_v1.py` (this gate);
- `.openrecomp-phase9/SOURCE_SHA256SUMS.txt` with 3 entries.

## Toolchains recorded

Python 3.11.9, Git 2.55.0.windows.3, clang/clang-cl 22.1.8
(`ca7933e47d3a3451d81e72ac174dcb5aa28b59d1`), lld-link 22.1.8, Ninja 1.13.2,
CMake 4.4.3, Zig 0.13.0 (`.openrecomp-phase3/tools/zig/zig.exe`). Exact
observed strings are in `toolchains.json`.

## Official runs

Command `python .openrecomp-phase9/src/p9_stage_runner_v1.py --stage P9-00
--script tools/test_phase9_boundary_v1.py --evidence-dir
.openrecomp-phase9/evidence/P9-00 --tests-json p9_00_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 4159 bytes raw, raw sha256
`a3bcefce25373423723eb5fbbeeb433062eb0c28a67c32f8e6fa7d1bde035702`, LF
sha256 `326624b32f642856b47e1f26255dcc976a693f045b4723c8582804fb90a2a152`,
LF stdout 4059 bytes.

Sidecar identities:

- `p9_00_tests.json` `aa488735f80ef1089a655f83324281d94f0824b21eda46895f4316e947ae6391`;
- `baseline.json` `b7f99566ac120def641f991c367d16dc2be336655854d216cc25cb0cde7ab559`;
- `toolchains.json` `634cd2a842a5772be9ae61b8bae6a18cf328fb16927bec6cdeeed8185e5c974f`;
- `official_runs.json` `2d889eac40da70c18eb73ad816efa2b108d9c2cdec22b3344aa264655fd08d62`;
- `determinism.json` `55d5ab1b3ad1f6e16e048c99e54f4b2a9827a7ce8be2f8ded7bbd22286328ca7`;
- `run1.txt` = `run2.txt` `326624b32f642856b47e1f26255dcc976a693f045b4723c8582804fb90a2a152`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Claim-ledger delta

None. P9-00 adds no PS1 capability and promotes no marker. It verifies the
frozen Phase-8 boundary and establishes the Phase-9 control plane only.

## Side effects

New tracked paths: `.openrecomp-phase9/` control plane, evidence and source
manifest; `tools/test_phase9_boundary_v1.py`. No frozen Phase-1 through
Phase-8 file was modified. No private fixture bytes, paths or identifiers are
present in any committed artifact.

## Next stage

`P9-01` - PS-X EXE ingestion, beginning with the private `SLUS_005.29` fixture
metadata (header fields, entry PC, GP, load address, payload size, hashes) and
fail-closed rejection categories. No executable bytes are committed.
