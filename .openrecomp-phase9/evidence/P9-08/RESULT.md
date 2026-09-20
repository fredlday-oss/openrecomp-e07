# P9-08 result: PS1 SPU/audio boundary

Status: `PASS` (60 checks)

Markers:

- `OPENRECOMP_P9_08=PASS`
- `OPENRECOMP_PHASE9_SPU_BOUNDARY_V1=PASS tests=60`
- `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)
- `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase9_spu_v1.py`.

## Implementation

`.openrecomp-phase9/src/p9_spu_boundary_v1.py` defines the explicit audio
service/runtime contract:

- bounded SPU register ranges (voices `0x1f801c00+0x180`, control
  `0x1f801d80+0x40`, transfer `0x1f801da0+0x10`, CD audio `0x1f801db0+0x10`)
  and 21 named control registers;
- typed deterministic event recording with no audio synthesis, reverb, sample
  playback or hardware accuracy (`emulation: none-event-recording`,
  `audio_synthesis: none`);
- labelled read stubs; unknown SPU registers become explicit blockers;
  out-of-range ports fail closed (`NOT_AN_SPU_PORT`).

## Public fixture behaviour (exact)

The bounded discovery finds exactly one reachable SPU access: `sb` at site
`0x8001006c` writing `0x000000c0` to `0x1f801daa` (SPU_CONTROL). The adapter
records a `CONTROL_REGISTER` event with the value `0x000000c0`; the transcript
digest is
`a08d2ee7a1121b31b9d4154da8fc01c3aa9199360d9043a97fbe63f1083acdc7` and is
stable across replay. Unit checks pin voice/transfer classification, the
unknown-register blocker and the labelled read stub.

## Private fixture scan (metadata only)

The same bounded discovery over the private Hercules reachable frontier finds
0 SPU-range accesses in its same-block immediate window. No payload bytes are
present in the evidence; the fixture is explicitly `is_pass_criterion: false`.

## Official runs

Command `python .openrecomp-phase9/src/p9_stage_runner_v1.py --stage P9-08
--script tools/test_phase9_spu_v1.py --evidence-dir
.openrecomp-phase9/evidence/P9-08 --tests-json p9_08_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 1995 bytes (LF), sha256
`90ae1385f17195612d95e861ef3f2708416bbd05fdda195d39c4fa99c302ceb9`.

Sidecar identities:

- `p9_08_tests.json` `05ca6c7bcec3e242a4565a046f5f6a45a4f1cf46c2c1e824b05b8fa10fc4e01c`;
- `public_spu.json` `9b7556db2ecbaa1206e2a07a2d7db79666e78e69220a0f688d8f28945679749e`;
- `private_spu.json` `bddbbd682ed80d1b203a77c4d39349d9fa992bf27f8c18626e404726d9f941b7`;
- `official_runs.json` `035182964681d95b17d6837468179fc1a654687afe5a88e5511897d572cb84c4`;
- `determinism.json` `2271a2e856abdec19d9926cf591bb85a6900b7e89a4a60350cf04385c2e71836`;
- `run1.txt` = `run2.txt` `90ae1385f17195612d95e861ef3f2708416bbd05fdda195d39c4fa99c302ceb9`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Claim-ledger delta

`BOUNDED`: an explicit audio service/runtime contract exists; the public
fixture's single reachable SPU control write is classified and recorded
deterministically; unsupported registers fail closed. No audio synthesis,
voice playback, reverb or hardware-accurate SPU behaviour is claimed.

## Next stage

`P9-09` - CD-ROM/file-service boundary: classify disc/file/streaming
requirements reachable from the fixture, implement only bounded required
services, and keep disc-image bytes outside repository and evidence.
