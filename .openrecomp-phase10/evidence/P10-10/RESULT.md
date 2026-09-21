# P10-10 result: controller / SPU / game-loop frontier

Status: `PASS` (36 checks)

Markers:

- `OPENRECOMP_P10_10=PASS`
- `OPENRECOMP_PHASE10_INPUT_SPU_FRONTIER_V1=PASS tests=36`
- `OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase10_input_spu_v1.py`.

## Controller frontier

| Observable | Value |
|---|---|
| controller-window accesses | **0** |
| timer1 counter reads | 109035 |
| interrupt-port accesses | 1 (`I_MASK` read, blocked/fail-closed) |
| recorded input events | 65536 (capped; the exact split comes from the non-RAM log) |

The guest never touches the controller data port
(`0x1f801040`-`0x1f80104f`), so no scripted input can be consumed in the
recorded frontier. That is recorded as
`NOT_REACHED_BY_THE_PRIVATE_FRONTIER`, not implemented speculatively.

Public synthetic evidence proves the deterministic scripted-input contract that
already exists in the Phase-9 boundary: the fixture writes the button pattern
`0xc1f3` to the controller data port and reads it back unchanged
(`failed=0`, `denied=0`, read-back `0x0000c1f3`, no SPU events). Input is
therefore deterministic *and* currently unused.

## SPU frontier

| Address | W | Dir | Value class | Audited class |
|---|---|---|---|---|
| `0x1f801daa` | 16 | write | `control_enable_cd_audio_and_transfer` (`0xc001`) | `spu_control` |
| `0x1f801db0` | 16 | write | `volume_max` (`0x3fff`) | `spu_cd_audio` |
| `0x1f801db2` | 16 | write | `volume_max` (`0x3fff`) | `spu_cd_audio` |
| `0x1f801db8` | 16 | read | `zero` | `spu_cd_audio` |
| `0x1f801dba` | 16 | read | `zero` | `spu_cd_audio` |

Five events: one SPU control write, two CD-audio volume writes at maximum, two
status reads. No voice setup, no SPU RAM transfer (0 transfer-port accesses)
and no blocked SPU event. Audio output is therefore **not required** by the
evidence and is not implemented.

Public synthetic evidence: two CD-audio volume writes are served
(`failed=0`, `denied=0`, 2 SPU events).

## Game-loop frontier

| Question | Answer |
|---|---|
| frame loop reached | **no** |
| vsync or interrupt-driven wait reached | **no** |
| busy-poll loop reached and served | yes (GPU status and timer1 counter read exactly one-to-one, 109035 each, both served) |
| interrupt-driven progress required | no |
| controller-input-driven progression | no |

So the private frontier reaches a *served busy-poll loop*, not a frame or event
loop. No frame-level observable exists yet, and milestone C or beyond is not
established.

## Implementation

Nothing is implemented at P10-10: the reached controller/SPU/loop behaviour is
already served by the Phase-9 boundaries, no scripted input is consumed, no
audio output is required and no frame loop is reached. The unserved
interactions (SPU RAM transfer, interrupt delivery) remain fail-closed.

## Limitations

- the per-device transcript prefix is capped, so exact input-address counts come
  from the non-RAM access log rather than the event stream;
- no frame loop is reached, so there is no frame-level observable;
- the guest's failure remains an executed unresolved indirect jump, whose exact
  site is not observable.

## Official runs

Command `python .openrecomp-phase10/src/p10_stage_runner_v1.py --stage P10-10
--script tools/test_phase10_input_spu_v1.py --evidence-dir
.openrecomp-phase10/evidence/P10-10 --tests-json p10_10_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 1310 bytes (LF), sha256
`4660005febdc28be08fd320f90581fdc39768707eecbae55b3dbb501ed0bce51`; generated
evidence sidecars byte-identical across both runs.

Sidecar identities:

- `input_spu_frontier.json` `2b697b82813aa14af1f0744e76cb0d534a0dc3a4263544a10e0b6bb5b35bb538`;
- `p10_10_tests.json` `2c85a7da70699738a6f403146cbb1661d4b14e19aad519f958a352264fbe7aee`;
- `official_runs.json` `ab5d0b20c3f0b8d5a4465812ca79414e59c0a22878f9da96c574383d18fe31cd`;
- `determinism.json` `393fcb9b27fbd7339d602973119009dcfed680543656f35dce2f2ef69e5017d6`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Public safety

The committed record contains register addresses, widths, directions, value
classes, counts and digests only. No audio data, no controller payloads, no
payload bytes and no disc material.

## Claim-ledger delta

`PROVEN`: the controller/SPU/game-loop classification, the deterministic
scripted-input contract (synthetic) and the served busy-poll loop. `BOUNDED`
(private only): the observed register traffic. Controller-driven progression,
audio output, frame loops, playability and general PS1 compatibility remain
`NOT_PROVEN`.

## Next stage

`P10-11` - highest evidence-supported milestone.
