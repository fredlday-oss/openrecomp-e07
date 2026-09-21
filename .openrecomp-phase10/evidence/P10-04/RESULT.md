# P10-04 result: Hercules BIOS frontier

Status: `PASS` (51 checks)

Markers:

- `OPENRECOMP_P10_04=PASS`
- `OPENRECOMP_PHASE10_BIOS_V1=PASS tests=51`
- `OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase10_bios_v1.py`.

## Exact classification of the inherited frontier

The 22 reachable indirect-call sites classify as:

| Class | Count |
|---|---|
| `BIOS_VECTOR_CALL` | 3 |
| `INDIRECT_TARGET_UNRESOLVED` | 19 |
| `RESOLVED_INTERNAL_CALL` | 0 |

The three BIOS calls resolve exactly (bounded backwards slice, no guessed
target):

| Site | Target | Vector | Function index | Service |
|---|---|---|---|---|
| `0x80015fa4` | `0x000000b0` | B0 | `0x57` | `ps1.bios.B0.57` |
| `0x80026ebc` | `0x000000b0` | B0 | `0x56` | `ps1.bios.B0.56` |
| `0x80026f74` | `0x000000b0` | B0 | `0x57` | `ps1.bios.B0.57` |

Each site is preceded by `addiu $t2, $zero, 0xb0` and carries the function
index as a constant write to `$t1` in its delay slot (`0x56` once, `0x57`
twice), which is the observed call convention: `$t2` = vector base, `$t1` =
function index.

Thirteen of the nineteen unresolved sites are *proven* non-constant: the
bounded slice reaches the target register's writer and finds a memory load
(`slice-writer:lw@…`). The remaining six are explicitly
`slice-crossed-control-flow` - the bounded window cannot resolve them. No
target is guessed and none of the nineteen is claimed resolvable.

## Typed service boundary

The Phase-9 typed BIOS/service boundary is reused unchanged: three vector
services (`A0`/`B0`/`C0`), no service implemented, unknown-service policy
`fail-closed`, `bios_image: none`.

Observed services (`ps1.bios.B0.56`, `ps1.bios.B0.57`) are recorded as
identifiers only with `implemented: false` and `disposition: FAIL_CLOSED`,
`semantics_determined: false`. Their meaning, argument behaviour and return
values are NOT determined: doing so would require BIOS documentation or a BIOS
image, neither of which is available or permitted here.

## Public synthetic evidence

- accepted forms: `0xB0`/`A0`/`C0` constants, the KSEG0 form `0x800000b0`
  (materialised as a `lui` + `addiu` pair), and a call with no constant index
  in the delay slot (classified, but with no service id);
- `RESOLVED_INTERNAL_CALL` with `EXACT_TARGET` disposition is produced when a
  constant target equals a known internal function entry (and only then);
- fail-closed forms: a constant target outside the image
  (`UNRESOLVED_CONSTANT_TARGET`) and a memory-loaded target
  (`INDIRECT_TARGET_UNRESOLVED` with `slice-writer:lw` evidence).

## Native fail-closed behaviour

Two synthetic fixtures were emitted, built (2 isolated runs each, both `OK`)
and executed:

| Fixture | Result |
|---|---|
| BIOS vector call (`jalr` to `0xb0`) | `failed=1` (unresolved indirect call stub) |
| read of the low BIOS table window (`lw` at `0x000000b0`) | `failed=1` (memory access outside the guest RAM window) |

No BIOS image is loaded or executed, no BIOS function is emulated, and the low
BIOS window is not mapped into guest RAM.

## Official runs

Command `python .openrecomp-phase10/src/p10_stage_runner_v1.py --stage P10-04
--script tools/test_phase10_bios_v1.py --evidence-dir
.openrecomp-phase10/evidence/P10-04 --tests-json p10_04_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 1822 bytes (LF), sha256
`b057354048573135f1fc486d3ad8145d5b1afb1f4bcd050b26ef812e204b2dd3`; generated
evidence sidecars byte-identical across both runs.

Sidecar identities:

- `bios_classification.json` `fea6db18e70682fa0ec08d3aa79f687e6343c2ab20c6e065d8e503aca954240b`;
- `bios_native_negatives.json` `d9960c33c872f60335061560594481b5a7d4f2d70b08a2e0e35243cd9b407d10`;
- `p10_04_tests.json` `55c6065a5f50108b22bcbe47a1b5c27b946a0b4ddf8339abd9e5ffe062e5ab5a`;
- `official_runs.json` `43b4e35d6816e0e93a189d6aa5477c60c16d27b9761a04d8e226b10338a825b8`;
- `determinism.json` `31eea69f8ab598bc34273575a1195aedddebea731779edf6ac48ab895cc32229`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Public safety

The committed BIOS record contains addresses, vector identifiers, function
indices, service identifiers, classification names and counts only. No payload
bytes, no disassembly excerpts, no BIOS material and no reconstructive derived
data.

## Claim-ledger delta

`PROVEN`: the exact constant-resolution classification, the BIOS call
convention evidence and the fail-closed boundary policy. `BOUNDED` (private
only): the observed service identifiers. BIOS semantics, native execution,
playability and general PS1 compatibility remain `NOT_PROVEN`.

## Next stage

`P10-05` - native execution entry for Hercules.
