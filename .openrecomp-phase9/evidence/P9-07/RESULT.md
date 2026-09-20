# P9-07 result: PS1 input/timer/event boundary

Status: `PASS` (64 checks)

Markers:

- `OPENRECOMP_P9_07=PASS`
- `OPENRECOMP_PHASE9_INPUT_TIMER_V1=PASS tests=64`
- `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)
- `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase9_input_timer_v1.py`.

## Implementation

`.openrecomp-phase9/src/p9_input_timer_v1.py` defines deterministic
virtual-input and virtual-time interfaces plus explicit classifications:

- controller ports (JOY_DATA/JOY_STAT/JOY_MODE/JOY_CTRL/JOY_BAUD) with a fixed
  deterministic virtual input source and a labelled `JOY_STAT` contract stub;
- timer 0/1/2 counter/mode/target ports with the explicit virtual-clock policy
  `counter-read-returns-tick-then-advances`;
- interrupt ports (I_STAT/I_MASK) classified as `not-modelled`: every access
  is recorded as an explicit blocker, never guessed;
- out-of-range ports fail closed (`NOT_AN_INPUT_TIMER_PORT`).

No interrupt delivery, controller serial protocol or hardware timing accuracy
is claimed.

## Public fixture behaviour (exact)

The bounded discovery finds exactly two reachable accesses:

| Site | Op | Direction | Address | Range |
|---|---|---|---|---|
| `0x80010030` | `lw` | read | `0x1f801040` (JOY_DATA) | joy |
| `0x80010048` | `lw` | read | `0x1f801100` (TIMER0 counter) | timer0 |

The adapter returns the deterministic virtual input `0x00000000` (no buttons)
and the virtual time tick `0x00000000`, then advances the clock to 1; the
transcript digest is
`819ac68be90b08a33e07656812a22e729e67fd3206dc027c46bd9f4738c67dd5` and is
stable across replay. Unit checks pin the tick sequence `0,1,2`, the
interrupt read/write blockers and the config-write recording.

## Private fixture scan (metadata only)

The same bounded discovery over the private Hercules reachable frontier finds
0 joy/timer/interrupt-range accesses in its same-block immediate window. The
result is recorded with an explicit non-guessing note. No payload bytes are
present in the evidence; the fixture is explicitly `is_pass_criterion: false`.

## Official runs

Command `python .openrecomp-phase9/src/p9_stage_runner_v1.py --stage P9-07
--script tools/test_phase9_input_timer_v1.py --evidence-dir
.openrecomp-phase9/evidence/P9-07 --tests-json p9_07_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 2476 bytes (LF), sha256
`b247339144277b85eb61f5054f95ad2e77ab593360043c5ea2afc110fd9eeb9b`.

Sidecar identities:

- `p9_07_tests.json` `b0ca8fd10b637dc8c6d136c0fe6e3d58947d8a8b659f2b54b3a2798639a581c7`;
- `public_input_timer.json` `91a76ae9a131c993c6fd4a9f3583aea203eafe84880f33b3d349c12c432804c7`;
- `private_input_timer.json` `5434b3850664e036283e8e932df46210db74651eab777e239f039755c7383c1f`;
- `official_runs.json` `06ab3df58d667c107dfd7e4d2effc1f2b5b45bc40806bf6941e6aadddec75b32`;
- `determinism.json` `9edd7e8c4e6bd2c4a1e54ac96474423aae7de4f348b1e9cb820100add73279eb`;
- `run1.txt` = `run2.txt` `b247339144277b85eb61f5054f95ad2e77ab593360043c5ea2afc110fd9eeb9b`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Documented fixture correction (P9-10 preparation)

The public fixture was corrected to initialize `$sp` itself at entry (see the
P9-03 correction record); the two access sites shift by 8 bytes to
`0x80010030` and `0x80010048`. The transcript digest is unchanged
(`819ac68b...`). The official runs were re-issued; the official stdout
identity is unchanged (`b2473391...`).

## Claim-ledger delta

`BOUNDED`: deterministic virtual input/time interfaces exist for the bounded
fixture; controller and timer requirements are classified and served; interrupt
delivery is explicitly not modelled. No hardware-accurate input/timer
behaviour, serial protocol or event scheduling is claimed.

## Next stage

`P9-08` - SPU/audio boundary: classify reachable audio/SPU interactions,
establish an explicit audio service/runtime contract, and fail closed on
unsupported behaviour.
