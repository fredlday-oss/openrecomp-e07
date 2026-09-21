# P10-09 result: disc / CD-ROM / streaming frontier

Status: `PASS` (46 checks)

Markers:

- `OPENRECOMP_P10_09=PASS`
- `OPENRECOMP_PHASE10_DISC_FRONTIER_V1=PASS tests=46`
- `OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase10_disc_v1.py`.

## Disc identity re-verified (CUE is authoritative)

| Identity | Value |
|---|---|
| CUE (discovered from the fixture directory, never assumed) | 101 bytes, `beea454de356689cdaa06702f4ed76a5474fd125a7460619ee678c1ae8725df2` |
| referenced BIN | 409452624 bytes, `2ce144ba0e1fed6952ad80976814e3033fec6cddfb5e17cdf0294517ea311365` |
| track layout | single `MODE2/2352` track, `INDEX 01 00:00:00` |
| ISO9660 | 174087 sectors, root extent LBA 22 |
| `SYSTEM.CNF` boot target | `SLUS_005.29`, boot extent SHA-256 equals the executable SHA-256 |
| executable | 129024 bytes, `c230ff5cd14bdfa392f5d5765c9c907b631875aaaa7844792b38b9ac54930f6f` |

All identities match the `P10-00` record exactly, so the disc and the
executable are the same audited target.

## Exact CD-ROM register frontier

| Register | Read | Write |
|---|---|---|
| `INDEX_STATUS` (`0x1f801800`) | 0 | 15 |
| `COMMAND` (`0x1f801801`) | 0 | 10 |
| `PARAMETER` (`0x1f801802`) | 0 | 8 |
| `INTERRUPT_ENABLE` (`0x1f801803`) | 2 | 3 |

Command bytes classified with the audited Phase-9 command table (32 documented
commands):

| Class | Count |
|---|---|
| `READ_N` | 4 |
| `SET_MODE` | 4 |
| `SET_LOCATION` | 1 |
| `UNKNOWN_COMMAND` (`0x80`) | 1 (blocked, fail-closed) |

So the guest does reach a real disc *command* sequence (set location, set mode,
read-N), but the sequence is register-level only.

## Data path assessment

| Capability | Reached |
|---|---|
| sector read (data transfer) | no |
| ISO9660 directory access | no |
| file open/read | no |
| executable overlay load | no |
| resource load | no |
| data streaming | no |
| XA audio streaming | no |
| asynchronous CD event | no |

Evidence: the transcript contains no data-port read, no sector delivery and no
file/streaming operation; only index/status, parameter, command and
interrupt-enable register traffic is present. The boundary accepts the
`READ_N`/`SET_LOCATION`/`SET_MODE` commands without performing any transfer, so
a guest that consumed the drive data would receive the boundary's explicit
contract stub rather than disc bytes - it would not silently receive host
filesystem data.

## Implementation

Nothing is implemented at P10-09: no ISO9660, no sector reads, no streaming, no
XA and no disc data path, because none is reached by the dynamic path.
Implementing them would be speculative. The unknown command `0x80` stays
fail-closed (proved natively).

Public synthetic fixtures: `SET_MODE` and `READ_N` command writes are served
(`failed=0`, `denied=0`); the unknown command `0x80` fails closed (`failed=1`,
`denied=1`); a data-port read returns the boundary contract stub `0x00000000`
(`failed=0`, `denied=0`) and never disc bytes.

## Notes and limitations

- the command sequence suggests a normal disc-read setup, but the fact that no
  data transfer follows means the data path is not exercised in the recorded
  frontier; whether the guest would consume drive data later is not determined;
- command order and cross-register sequencing are not observable (per-device
  event transcripts are printed as a block);
- no disc bytes, sectors, file contents or reconstructed disc data are read or
  committed; only hashes, sizes, metadata, classes and counts are recorded;
- the CUE is never hard-coded: it is discovered from the fixture directory;
- a fixture-encoder correction was made inside this new gate (`ori` operand
  order in the synthetic CD-ROM fixtures); no earlier stage is affected.

## Official runs

Command `python .openrecomp-phase10/src/p10_stage_runner_v1.py --stage P10-09
--script tools/test_phase10_disc_v1.py --evidence-dir
.openrecomp-phase10/evidence/P10-09 --tests-json p10_09_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 1720 bytes (LF), sha256
`0d049cc104c0c28354f76a90560de95f5d52f01cb51ad8dbce1484a2b948b4bd`; generated
evidence sidecars byte-identical across both runs.

Sidecar identities:

- `disc_frontier.json` `9e8715c489a033b717e5b69607d747c4315c99d0fed11234845fcc49b4ca0896`;
- `p10_09_tests.json` `6076196573960e3f068f56faeb448c9c2032f0ee848d0e81fdac20e9e6c158fd`;
- `official_runs.json` `20b0f49ea2a12ff518a25c330e04ad1830139a0a79595179cc83b1ce1240f005`;
- `determinism.json` `69f516c7e2c9d4626d2f0afd5182d04063716638455fbd94ab0b11927b0d2b71`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Public safety

The committed record contains disc metadata, register counts, command class
names, counts and hashes only. No disc bytes, sectors, file contents, game
assets or reconstructed disc data.

## Claim-ledger delta

`PROVEN`: the disc identity relationship, the exact CD-ROM register/command
classification, the absence of a reached data path and the fail-closed unknown
command. `BOUNDED` (private only): the observed command counts. Disc data
transfer, ISO9660, streaming, XA, overlays, playability and general PS1
compatibility remain `NOT_PROVEN`.

## Next stage

`P10-10` - controller / SPU / game-loop frontier.
