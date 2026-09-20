# P9-99 result: final bounded verdict

Status: `PASS` (156 checks)

Markers issued:

- `OPENRECOMP_P9_99=PASS`
- `OPENRECOMP_PHASE9_FINAL_VERDICT_V1=PASS tests=156`
- `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=PASS` (exact bounded audited
  public fixture and behaviour only)
- `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)
- `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase9_final_verdict_v1.py`.

## Audit performed

- frozen Phase-8 baseline commit
  `61136fc37cf0810e64241addd8f57a91872bc0af`, tree
  `f9262497b82fe0027c3b23432ba7bd8cbccdf433`, branch
  `phase8/mips32-end-to-end-native-v1`; all fifteen frozen Phase-8 terminal
  evidence/control-plane hashes re-verified; P8-99 terminal decision `PASS`;
- all fifteen required Phase-9 stage records (`P9-00` .. `P9-12`, `P9-90`,
  `P9-91`) present with `RESULT.md`, two byte-identical official runs, empty
  stderr, exit 0, `PASS` tests records and their exact gate markers;
- the P9-90 whole-regression record: 13 Phase-9 gates re-run live, the frozen
  P8-90/P8-91/P8-99 terminal audits re-run with byte-identical stdout,
  3113 total re-verified tests;
- the P9-91 evidence index (141 entries) and claim ledger (13 `PROVEN`,
  3 `BOUNDED`, 10 `NOT_PROVEN`, 1 `NOT_TESTED`) with both permanent
  non-claims and the terminal claim reserved at P9-91;
- public fixture identity: OpenRecomp-authored `openrecomp-authored-ps1-v1`,
  SHA-256
  `17466bc17edde54f4d371ae22281b9fb31cd9114c3c293aa7da103751c32c3da`,
  2240 bytes;
- deterministic emission set and reproducible native executable
  `5c016be2f043760ef6ac1a7c37c60bbe335c271f307b8e05275f75e0ee2ceb9d`;
- native/reference agreement with `excluded_observables: []` and no
  mismatches: exit `0x00000002`, registers digest `0x17f2292e1363f17f`, RAM
  digest `0x28d892afac2d8496`, GPU 2 / `0x6a326cbc723c24b1`, input 2 /
  `0xe35ba7548adde99a`, SPU 1 / `0x55788edbf95cf3ea`, CD-ROM 1 /
  `0x0dc54fdf2d1b3c3c`, reads 1, writes 4, denied 0, host calls 0;
- private Hercules boundary: `is_pass_criterion: false`, bounded execution
  `NOT_ATTEMPTED_BLOCKED_BY_FIRST_UNRESOLVED`, first blocker `break` at
  `0x80013390`;
- scope guards present in SCOPE, STATE, STAGE_QUEUE and CONTROL_POLICY;
  queue rows all `PASS`;
- public-safety: no private payload material and no absolute host paths in
  the committed Phase-9 evidence.

## Verdict boundary

The terminal marker is `PASS` for the exact bounded audited public fixture and
behaviour only. It does not authorize general PS1 compatibility, arbitrary
PS-X EXE support, BIOS emulation, GPU rendering, SPU synthesis, CD-ROM disc
reading, controller protocol, interrupt delivery, COP0/GTE execution, PS2 or
commercial-game compatibility, cycle accuracy, or any claim beyond the audited
evidence. `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` and
`OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` are permanent.

## Official runs

Command `python .openrecomp-phase9/src/p9_stage_runner_v1.py --stage P9-99
--script tools/test_phase9_final_verdict_v1.py --evidence-dir
.openrecomp-phase9/evidence/P9-99 --tests-json p9_99_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 227 bytes (LF), sha256
`21479187b12990445fb4f7cbad01db692fc19500c045b5ce4b74140e9f2732de`.

Sidecar identities:

- `p9_99_tests.json` `1e911be47fe8e953eec4632ade35697c931db94ce63557655632702388b7d9f4`;
- `terminal_verdict.json` `5d4c70008436925c3c986a4166376bc322400c119ea3ea24df234ba2eca4d783`;
- `verdict_record.json` `96337230b155694ba9f150bb5b6201388ad74279956c11ced296bfc736b7dcae`;
- `official_runs.json` `11e4adb9d5ab533bcea949ef7104ca51933e2475472540c0cb96933d6b5c1842`;
- `determinism.json` `532c0769b803b13f96a55f8f933bab1fe92a829a22c04f26f8ce7037cd1374f0`;
- `run1.txt` = `run2.txt` `21479187b12990445fb4f7cbad01db692fc19500c045b5ce4b74140e9f2732de`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Terminal state

Phase 9 is COMPLETE for the exact bounded audited public claim:
`OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=PASS`. Both permanent
non-claims remain `NOT_PROVEN`.
