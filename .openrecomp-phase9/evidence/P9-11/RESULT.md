# P9-11 result: private Hercules bounded validation

Status: `PASS` (155 checks)

Markers:

- `OPENRECOMP_P9_11=PASS`
- `OPENRECOMP_PHASE9_PRIVATE_VALIDATION_V1=PASS tests=155`
- `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)
- `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase9_hercules_v1.py`.

## Scope and policy

The private Hercules `SLUS_005.29` fixture was run through the complete
bounded Phase-9 path. It is never a public `PASS` criterion on its own; only
non-reconstructive metadata is recorded (hashes, sizes, header fields,
addresses, classifications, counts, diagnostics). No payload bytes,
disassembly, strings or reconstructive derived data are committed. The gate
would record `present: false` and still pass if the fixture were absent.

## Recorded identity

- file SHA-256
  `c230ff5cd14bdfa392f5d5765c9c907b631875aaaa7844792b38b9ac54930f6f`;
- payload SHA-256
  `2f48da4c642b25dd9d0b033f77b80a19e5befe34dc19da3194a51998e97c71be`;
- entry `0x800132e8`, load `0x80010000`, text end `0x8002f000`, stack
  `0x801ffff0`; contract digest `4566f740...`.

## Exact reachable frontier

- 4068 reachable words (3972 supported, 96 recognized-unsupported, 0 invalid);
- 3 exception sites, 22 indirect calls, 18 indirect jumps, 3 external traps;
- first unresolved blocker: `break` (external trap) at `0x80013390`;
- the frozen structure bridge fails closed at that site with
  `CONTROL_WITHOUT_DELAY_SLOT`; no structure, translation or emission is
  fabricated for private code;
- pipeline digest recorded in `private_validation.json`.

## Boundary classifications

- translation closure: 96 reachable recognized-unsupported words in five
  explicit categories (`UNALIGNED_PARTIAL_WORD_LOAD` 34,
  `UNALIGNED_PARTIAL_WORD_STORE` 34, `INDIRECT_CONTROL_FLOW` 22,
  `TRAP_OR_SYSTEM` 3, `OVERFLOW_TRAPPING_ARITHMETIC` 3); no unknown category,
  no reachable COP0/GTE;
- BIOS/service boundary: 3 BIOS B0-table candidates (`0x80015fa4`,
  `0x80026ebc`, `0x80026f74`) and 19 `INDIRECT_TARGET_UNKNOWN` sites; no BIOS
  function implemented;
- GPU/controller/timer/SPU/CD-ROM discovery: 0 reachable I/O-range accesses in
  the bounded same-block window (explicitly not guessed).

## Bounded execution status

`NOT_ATTEMPTED_BLOCKED_BY_FIRST_UNRESOLVED`: the frozen pipeline fails closed
before translation, emission or any native build of private code. No private
code was executed, emitted or committed, and no private-fixture success can
promote the public claim or the permanent non-claims
(`public_claim_promoted`, `general_compatibility_promoted` and
`playability_promoted` are all `false`).

## Public-safety

Every private record was leak-checked (no payload hex, base64 or ASCII runs;
no string value over 128 characters). The evidence contains metadata only.

## Official runs

Command `python .openrecomp-phase9/src/p9_stage_runner_v1.py --stage P9-11
--script tools/test_phase9_hercules_v1.py --evidence-dir
.openrecomp-phase9/evidence/P9-11 --tests-json p9_11_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 6134 bytes (LF), sha256
`b19d5769b17a3e50257ead1c67d23120943ce8e289a23ff863c411f732230ac4`.

Sidecar identities:

- `p9_11_tests.json` `86c69d1a3895080a5043c94e78857fbd2125efadb26fa4f9fd01561c346ccb8e`;
- `private_validation.json` `0af94c30eae69ac440e23a4ee8a1d8706e7c0f6f9b5187ad02b51ae900fbc704`;
- `official_runs.json` `468abffb7ff0be3888c4d223a5465bc7ba191485b25a8887440f5e66884afec8`;
- `determinism.json` `dc85446678adde8f6085f9cb40a9caa1f47081dbeeb5f76916a433f7009102ec`;
- `run1.txt` = `run2.txt` `b19d5769b17a3e50257ead1c67d23120943ce8e289a23ff863c411f732230ac4`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Claim-ledger delta

`BOUNDED` (private only): the private fixture is ingested, mapped and
classified exactly through the bounded path with an explicit first blocker.
Hercules playability and general PS1 compatibility remain `NOT_PROVEN`;
private-fixture results do not extend the public claim.

## Next stage

`P9-12` - hardening and reproducibility: negative malformed-input tests,
cache/stale-evidence tests, clean rebuild and repeated deterministic
execution, and source/evidence manifest re-verification.
