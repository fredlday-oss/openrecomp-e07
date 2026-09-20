# P9-10 result: native build and deterministic execution

Status: `PASS` (49 checks)

Markers:

- `OPENRECOMP_P9_10=PASS`
- `OPENRECOMP_PHASE9_NATIVE_EXECUTION_V1=PASS tests=49`
- `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)
- `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase9_native_v1.py`.

## Implementation

- `.openrecomp-phase9/src/p9_emission_v1.py` - deterministic four-file
  emission set: `program.c` (existing architecture-neutral emitter output),
  `p9_image_v1.c` (2 MiB RAM window as inert zero-initialized data plus
  deterministic non-zero chunks, explicit region table and platform port map),
  `p9_runtime_support.c` (composed with the generated contract declarations)
  and `p9_driver.c`.
- `.openrecomp-phase9/runtime/p9_runtime_support.c` - OpenRecomp-authored
  bounded PS1 platform runtime: explicit KSEG0/KSEG1 RAM translation, the
  typed GPU/controller/timer/SPU/CD-ROM port dispatch with deterministic event
  recording, virtual input/time, interrupt and unknown-command/register
  blockers, and access counters.
- `.openrecomp-phase9/runtime/p9_observable_driver.c` - observable driver
  (exit status, 32 registers and digest, RAM digest, typed event counts and
  digests, counters).
- `.openrecomp-phase9/src/p9_reference_psx_v1.py` - independently structured
  PS-X EXE reference interpreter with its own loader, decoder/interpreter,
  RAM/address model and platform port model (no OpenRecomp emitter/semantics/
  memory-map/boundary/emission imports).

The guest image is inert data; `program.c` contains no machine code.

## Emission identities

| File | Bytes | SHA-256 |
|---|---|---|
| `program.c` | 7581 | `5b4326639cdb1c84534a3d4c923dd2c6cb51f45670b67179ea5cebbd246bf2e2` |
| `p9_image_v1.c` | 4266 | `30d4be5d15f3552a295d49bb10841b7bde18b3d02dd1dd6bf8a19038ef6c1d4f` |
| `p9_runtime_support.c` | 18677 | `17be91b8c06254f401059ca31d4593a1440bb2b337305f177738d0c5a06813c6` |
| `p9_driver.c` | 7895 | `147a16d981efeec5a8126fe7b01f8c2859af57f2db1f85a1d6c90eef522b8691` |

Emission is deterministic (two builds, identical hashes); the program
fingerprint equals its SHA-256.

## Native build and execution

- clean build through `openrecomp.build_pipeline` (2 isolated runs, both
  `OK`); executable SHA-256
  `5c016be2f043760ef6ac1a7c37c60bbe335c271f307b8e05275f75e0ee2ceb9d`;
- execution is byte-identical across repeated runs; driver stdout 888 bytes,
  SHA-256 `4bd85bb401f52efc54f277e7e69f4ba67d336bbb0bc32cf8c7200c6c0d1f94e6`.

Native observable record (identical to the reference):

| Observable | Value |
|---|---|
| `failed` / `error` | 0 / empty |
| `exit_status` | `0x00000002` |
| registers digest | `0x17f2292e1363f17f` |
| memory digest | `0x28d892afac2d8496` |
| GPU events / digest | 2 / `0x6a326cbc723c24b1` |
| input events / digest | 2 / `0xe35ba7548adde99a` |
| SPU events / digest | 1 / `0x55788edbf95cf3ea` |
| CD-ROM events / digest | 1 / `0x0dc54fdf2d1b3c3c` |
| reads / writes / denied / host calls | 1 / 4 / 0 / 0 |

## Independent reference equivalence

The reference executed 40 steps and matches on every compared observable and
all 32 registers with `excluded_observables: []` and no mismatches
(`equivalence.json`). The reference implements the same bounded contract with
its own independent structure.

## Official runs

Command `python .openrecomp-phase9/src/p9_stage_runner_v1.py --stage P9-10
--script tools/test_phase9_native_v1.py --evidence-dir
.openrecomp-phase9/evidence/P9-10 --tests-json p9_10_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 1385 bytes (LF), sha256
`caa9746a21ae1d2dc49378f6d4dbfc8d29f34e96a90949c6f3ed07cf0b32b565`.

Sidecar identities:

- `p9_10_tests.json` `7ce2a36d5476aa97dc9cd5831425fcbd701ef38f3c24245276b6e995e5de972a`;
- `emission.json` `984666240d3f6ec02973fb720cac5d57af6210da6cbb4aa25f1c7f195ea06f97`;
- `native_execution.json` `6b332695c6f1a74c5d0fca4a6acb5266dc07deaec7262cc1d4a6f355fdf02b5c`;
- `reference.json` `69a51a42811b0cf4afbfaeb05d8d7479172dac25475aa0f94f55328b820f90d0`;
- `equivalence.json` `11a3596fffd6d14bc4d2486bc038750c9db1371217b75bbd2122df5288c9b1c`;
- `official_runs.json` `09947fc5b8efba4d85569431c7c5b6d4b3933b0df02e245ca35046f71016e68e`;
- `determinism.json` `0f849a537f539213b0236a3ccc63e6217d52709399b005518f4791851e8e8f23`;
- `run1.txt` = `run2.txt` `caa9746a21ae1d2dc49378f6d4dbfc8d29f34e96a90949c6f3ed07cf0b32b565`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Evidence-hygiene adjustment (P9-12 preparation)

The `build:executable` check detail recorded the absolute build path. It now
records the repository-relative path. Check labels, their count and the
official stdout are unchanged (`caa9746a...`); the affected sidecar hashes were
refreshed. No semantic evidence changed.

## Claim-ledger delta

`PROVEN` (bounded): the original public PS1 fixture is recompiled through the
existing architecture-neutral path to native host code and executes
deterministically with the PS1 platform runtime adapter, with full observable
agreement against an independently structured reference. This claim is exact
to the audited fixture, toolchain and observable contract only; it does not
extend to any other program or to hardware-accurate console behaviour.

## Next stage

`P9-11` - private Hercules validation: run the private fixture through the
complete bounded path, record the exact reachable frontier and first
unresolved blocker, and record that private-fixture success does not imply
public/general compatibility.
