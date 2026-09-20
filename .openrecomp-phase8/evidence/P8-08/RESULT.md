# P8-08 result: deterministic native execution

Status: `PASS` (26 checks)

Markers:

- `OPENRECOMP_P8_08=PASS`
- `OPENRECOMP_PHASE8_NATIVE_EXECUTION_V1=PASS tests=26`
- `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase8_native_execution_v1.py`.

## Native execution

The emission set was rebuilt through the existing deterministic pipeline
(`EXECUTABLE_REPRODUCIBLE`) and the generated native program was executed
three times; all three stdout streams are byte-identical. Exit code 0 and
empty stderr for every execution.

## Bounded observable record (agreed boundary)

- fixture identity: `0a90f477...` (matches the frozen P8-01 ELF);
- `failed=0`, `error=` empty;
- exit value: `exit_status=0x00000000` (`$v0` at the return boundary);
- full 32-register guest file at the boundary, e.g. `r01=0x10000000`,
  `r08=0x000024c0` (`.rodata` base), `r29=0x00006710` (stack top),
  `r31=0x00000000`; register-file digest `0x7ee0f4a187050726` (recomputed
  independently in the gate and equal);
- guest memory digest `0x231c4a49e79c5e56` (FNV-1a 64 over the full image);
- output transcript: 33 bytes, digest `0xca6dcb87f8ac9814`, equal to the
  independently computed FNV-1a 64 of `69c4e0d86a7b0430d8cdb78070b4c55a\n`,
  the FIPS-197 AES-128 known-answer ciphertext line (the known answer is
  therefore present in the observed native output);
- event counts: reads 1136, writes 681, host calls 33
  (`host_calls == transcript_len`, one output service call per byte),
  denied accesses 0.

## Official runs

Command `python tools/test_phase8_native_execution_v1.py`, exit 0, empty
stderr, both runs byte-identical: stdout 1028 bytes, raw sha256
`ead0ca26a6b64842a43ac0c552fd63e66ef0e8d72279a8f9ba27e7057a49ea2e`, LF
sha256 `9675a2f26625852fe1263d88fd3abaa7131916b7790251d176495df937d6e8bc`.

Sidecar identities: `native_execution.json`
`790a58ac82bbf393f999baeb3852be5b8b139cb81fe8c888b1b70f3fa6173202`,
`p8_08_tests.json`
`c7486c0c036b6772cfb53787d4694a019973e1c0f2b994b6dfe7f6cdbe7b9ceb`.

## Claim-ledger delta

- New evidence: the generated native program executes deterministically with
  a stable, bounded observable record and the fixture's known-answer output.
- Equivalence against an independently structured MIPS32 reference is not yet
  established; the terminal marker remains reserved `NOT_PROVEN`.

## Limitations

- The observable record is bounded to this fixture and this contract; it is
  not a general execution or equivalence claim.
- Determinism is demonstrated on one host/toolchain; no cross-platform claim
  is made.

## Next stage

P8-09: build an independently structured MIPS32 reference path, execute the
frozen ELF under it, and compare every observable against the native result;
any intentional difference must be explicitly characterized and bounded.
