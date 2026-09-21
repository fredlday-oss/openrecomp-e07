# P10-12 result: hardening and reproducibility

Status: `PASS` (56 checks)

Markers:

- `OPENRECOMP_P10_12=PASS`
- `OPENRECOMP_PHASE10_HARDENING_V1=PASS tests=56`
- `OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase10_hardening_v1.py`.

## Malformed inputs reject deterministically

12 synthesised malformed PS-X EXE containers reject with their exact stable
codes (`INPUT_TOO_SMALL`, `BAD_MAGIC`, `EMPTY_PAYLOAD`,
`MISALIGNED_PAYLOAD_SIZE`, `TRUNCATED_PAYLOAD`, `MISALIGNED_LOAD_ADDRESS`,
`LOAD_ADDRESS_OUTSIDE_RAM`, `MISALIGNED_ENTRY`, `ENTRY_OUTSIDE_PAYLOAD`,
`MISALIGNED_STACK`, `STACK_OUTSIDE_RAM`, `MISALIGNED_GP`) - the negatives are
built in memory and never read from a disc or an external fixture.

Malformed trap records reject with `NOT_A_TRAP_RECORD`, `TRAP_HAS_DELAY_SLOT`
and `TRAP_HAS_TARGET`; a structure record whose control transfer has no delay
slot still fails closed with `CONTROL_WITHOUT_DELAY_SLOT`; a malformed BIOS
analysis keeps its target explicit (`INDIRECT_TARGET_UNRESOLVED`) and invents no
service.

## Fail-closed behaviour (live native evidence)

| Negative | Result |
|---|---|
| executed `break` | `failed=1`, `error="guest trap is unsupported"` |
| unknown GP0 command | `failed=1`, `denied=1`, `error="runtime memory write failed"` |

Unresolved indirect calls/jumps, unknown BIOS calls, unknown MMIO and unknown
device commands are covered by the committed stage evidence (`P10-03`,
`P10-04`, `P10-07`, `P10-08`, `P10-09`) and remain fail-closed.

## Immutable-hash analysis cache

`.openrecomp-phase10/src/p10_analysis_cache_v1.py` keys every entry by a
canonical provenance document, never by a filename:

- hit for exactly the stored provenance;
- **miss** for a change in any of: executable SHA-256, CUE SHA-256, referenced
  BIN SHA-256, PS-X EXE identity digest, frontend version, semantic-model
  version, runtime version, disc-model version, analysis-configuration digest
  (9 invalidations tested);
- missing provenance fields reject with `PROVENANCE_MISSING_FIELD`;
- a corrupted entry rejects with `CACHE_ENTRY_CORRUPT` instead of being used.

Because the key is content-derived, a renamed or rebuilt input can never hit a
stale entry.

## Public-safety scan

117 committed Phase-10 evidence files were scanned (the stage's own directory
is excluded because it is written while the gate runs):

- no private payload hex, no base64 sample and no ASCII payload run appears in
  any committed evidence file;
- no absolute host path (`<drive>:\`, `/Users/`, `/home/...`) appears in any
  committed evidence file.

The Phase-10 source manifest verifies (`=PASS entries=32`), and the generated
Hercules program contains no guest payload bytes, no opcode dispatch and no
image include; the guest image is emitted as inert data.

## Clean rebuild and cross-stage reproducibility

A clean rebuild of the Hercules native program (two isolated build directories,
both `OK`, executable SHA-256 recorded) reproduces **every** committed
cross-stage observable exactly:

| Observable | Value |
|---|---|
| reads / writes | 982859 / 799023 |
| denied / host calls | 11 / 79 |
| access budget / access count / budget denials | 2000000 / 2000005 / 5 |
| failed / error | 1 / `unresolved indirect jump` |
| GPU / input / SPU / CD-ROM events | 65536 / 65536 / 5 / 38 |
| registers | `$gp` `0x8002ed78`, `$fp` `0x80200000`, `$sp` `0x801ffe00` |

Both official runs produce byte-identical stdout and byte-identical generated
sidecars.

## Bounded-execution limitation (recorded, mitigated, not resolved)

The deterministic access budget bounds memory accesses, **not** execution: a
post-truncation guest loop that performs no memory access cannot be
interrupted. This was observed as a hang while probing ordering at a smaller
budget during `P10-07` reconnaissance.

Mitigation: every official gate runs with the default budget (2000000) and a
bounded host timeout; any future bounded run must verify termination. A hard,
deterministic step bound would require an emitter-level per-block hook, which is
a shared-layer change and is deliberately not made here.

## Official runs

Command `python .openrecomp-phase10/src/p10_stage_runner_v1.py --stage P10-12
--script tools/test_phase10_hardening_v1.py --evidence-dir
.openrecomp-phase10/evidence/P10-12 --tests-json p10_12_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 2046 bytes (LF), sha256
`5ddd24b3816a60c8ba55381adf8778450b830be363081e0dff81c5c6cd3a552d`; generated
evidence sidecars byte-identical across both runs.

Sidecar identities:

- `hardening.json` `defe7f88c08883a19e85d03fa182104f4ee5c415f4aa68d6200b9bb1cf81839a`;
- `p10_12_tests.json` `9e565c6872ff3006c8c95495ffbb4e89d9e18f242276927dfc85eacefb331bbe`;
- `official_runs.json` `8c8d074fc72e2d47fce7c1da61c28b5f8292a70994605bd76452f11ff5585f7d`;
- `determinism.json` `a18801ed14dd190034c50949381596424cc0d4f42702b38daec2d44a513b6003`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

One gate-internal correction was needed and applied before the official runs:
the public-safety scan now excludes the stage directory it is writing, so the
scan is deterministic across runs. No earlier stage evidence is affected.

## Public safety

The committed record contains rejection codes, counts, digests, cache keys and
scan results only. No payload bytes, no toolchain binaries, no build products
and no disc material.

## Claim-ledger delta

`PROVEN`: the deterministic rejection of malformed inputs, the live fail-closed
negatives, the identity-bound analysis cache, the clean-rebuild reproducibility
and the public-safety closure of the committed evidence. `BOUNDED` (private
only): the reproducibility chain. Playability and general PS1 compatibility
remain `NOT_PROVEN`.

## Next stage

`P10-90` - whole-project regression.
