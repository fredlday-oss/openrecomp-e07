# P9-02 result: PS1 executable image and memory-map contract

Status: `PASS` (128 checks)

Markers:

- `OPENRECOMP_P9_02=PASS`
- `OPENRECOMP_PHASE9_MEMORY_MAP_V1=PASS tests=128`
- `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)
- `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase9_memory_map_v1.py`.

## Implementation

`.openrecomp-phase9/src/p9_memory_map_v1.py` builds an explicit bounded PS1
guest address-space contract from a validated PS-X EXE image:

- 2 MiB main RAM (`0x80000000..0x80200000`), cached KSEG0 and uncached KSEG1
  (`0xA0000000..0xA0200000`) mirrors, both enabled and translating to the same
  RAM;
- named regions with explicit permissions: `load_text` (rwx), optional `bss`
  (rw), `ram_free` (rw, the gap between image end and the stack) and `stack`
  (rw, an explicit bounded 16 KiB window below the PS-X EXE initial SP,
  documented because the header `s_size` is zero);
- explicit classifications for every other segment: KUSEG RAM mirror
  (recognized, disabled for the bounded V1 with a recorded reason),
  scratchpad (unsupported, not modelled), I/O ports (platform-service
  boundary, unclaimed until P9-05..P9-09), BIOS (absent; no BIOS image is
  loaded, executed or emulated) and KSEG2 (unsupported privileged);
- deterministic 2 MiB flat RAM image with the payload mapped at its load
  address, plus deterministic non-zero chunking (zero gaps under 16 bytes
  merged) with a hard 4096-chunk limit;
- fail-closed translation with stable codes: `UNSUPPORTED_SEGMENT_KUSEG`,
  `UNSUPPORTED_SEGMENT_SCRATCHPAD`, `UNSUPPORTED_SEGMENT_BIOS`,
  `UNSUPPORTED_SEGMENT_KSEG2`, `PLATFORM_SERVICE_UNCLAIMED`,
  `UNMAPPED_ADDRESS`, `STACK_OVERLAPS_IMAGE`, `IMAGE_CHUNK_LIMIT`.

There is no silent address masking: every translation is an explicit
segment decision, and unsupported segments raise instead of being masked.

## Synthetic coverage

- contract fields: RAM base/size/end/permissions, image size and SHA-256,
  entry, load address, text end, initial GP, stack model/pointer;
- flat image: payload bytes at the load offset, zero-filled BSS and gaps;
- regions: `load_text` rwx, `bss` rw, `stack` rw at
  `0x801fbff0+0x4000`, `ram_free` at `0x80020100+0x1dbef0`, sorted by base,
  every named region inside RAM;
- segments: 7 exact classifications, every disabled segment carries a reason;
- translation: KSEG0 and KSEG1 translate to the same RAM offset; word reads
  through both mirrors agree; KUSEG/scratchpad/I/O/BIOS/KSEG2/unmapped
  addresses fail closed with the expected codes;
- negatives: stack/image overlap (`STACK_OVERLAPS_IMAGE`) and chunk-limit
  (`IMAGE_CHUNK_LIMIT`) both fail closed;
- determinism: two contract builds produce the same digest.

## Private fixture contract summary (non-reconstructive metadata only)

The private Hercules fixture maps to: `load_text` `0x80010000`+126976,
`ram_free` `0x8002f000`+1888240, `stack` `0x801fbff0`+16384; 44 deterministic
image chunks; flat-image SHA-256
`7d13f5f4f6c4dd321ddd01da627dc656dc1531163f8cca674a5febcf3aa87010`; contract
digest `4566f740a10ca4fdc6fb6d1046662c2e8619c6c8648f025f91dcd6ab95f6bf54`.
No payload bytes are present in the evidence; the fixture is explicitly
`is_pass_criterion: false`.

## Official runs

Command `python .openrecomp-phase9/src/p9_stage_runner_v1.py --stage P9-02
--script tools/test_phase9_memory_map_v1.py --evidence-dir
.openrecomp-phase9/evidence/P9-02 --tests-json p9_02_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 4256 bytes (LF), sha256
`a8999d9d41bc705b7039ec6f68c229539d0cac358e385bc29c4d263de288b00e`.

Sidecar identities:

- `p9_02_tests.json` `ea8e1410fae027cb8da605e4888dd6a3ddf241605714e75a22d894f3d37225a2`;
- `memory_contract.json` `98829fa64d318cba7e1c4272daee83bcfe71d36198cfcc53154b999677de0317`;
- `private_contract.json` `3717e60568b7e92cac8227e58114da586bd91cf93d7a8059f71bf29514c63432`;
- `official_runs.json` `4ef7bb2c67b31a4032db0798edef8ee40e05c0394a93d2cea71bfc191841fc64`;
- `determinism.json` `017739cf3066f79d236bc262833d076bcab089afe03909e265d7f2b58136a569`;
- `run1.txt` = `run2.txt` `a8999d9d41bc705b7039ec6f68c229539d0cac358e385bc29c4d263de288b00e`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Claim-ledger delta

`BOUNDED`: explicit PS1 address-space contract for the bounded V1 form above,
proven on original synthetic fixtures and summarized (metadata only) for the
private fixture. No execution, translation, platform service or GPU/SPU/CD-ROM
behaviour is claimed.

## Next stage

`P9-03` - feed the reachable executable code into the existing Phase-8 MIPS32
decode/ProgramModel/CFG/function/call-graph/TU stack and record exact counts;
unresolved indirect control flow fails closed.
