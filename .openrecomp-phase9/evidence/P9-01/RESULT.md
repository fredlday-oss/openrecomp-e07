# P9-01 result: PS-X EXE ingestion

Status: `PASS` (163 checks)

Markers:

- `OPENRECOMP_P9_01=PASS`
- `OPENRECOMP_PHASE9_INGESTION_V1=PASS tests=163`
- `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)
- `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase9_ingestion_v1.py`.

## Implementation

- `.openrecomp-phase9/src/p9_psx_exe_v1.py` - deterministic, fail-closed
  PS-X EXE parser/validator. It parses the 0x800-byte header, validates the
  bounded V1 form (magic, zero fields, payload size/alignment/truncation,
  trailing data, KSEG0 main-RAM load window `0x80000000..0x80200000`, entry
  alignment and containment, BSS structure, stack pointer alignment/range, GP
  alignment) and produces a non-reconstructive identity record. It never
  executes payload bytes and never serializes them.
- `.openrecomp-phase9/fixture/psx_fixture_builder_v1.py` - original
  OpenRecomp-authored deterministic PS-X EXE builder plus restricted MIPS32
  encoders used by the gates and later public fixture. No third-party or
  console-derived material.
- `tools/test_phase9_ingestion_v1.py` - this gate.

The rejection-code set is closed (`ERROR_CODES`, 23 codes) and every
rejection is raised as `PsxExeError` with a stable code.

## Synthetic coverage

- canonical OpenRecomp-authored PS-X EXE round-trip: exact entry PC, load
  address, text end, GP, stack pointer, file/payload SHA-256, payload size,
  header field values, reserved-region hash/counts, `read_u32` per word;
- byte-identical rebuild determinism; nonzero GP recorded exactly; BSS
  positive path (`bss_address=0x80020000`, `bss_size=0x100`) recorded with
  correct RAM span;
- identity record leak check on an ASCII-pattern payload (no hex, base64 or
  ASCII payload run; every string value <= 128 characters);
- 22 malformed/unsupported forms rejected with the expected stable code:
  `INPUT_TOO_SMALL` (empty, short header), `BAD_MAGIC`,
  `NONZERO_RESERVED_HEADER_FIELD` (zero1, zero2), `EMPTY_PAYLOAD`,
  `MISALIGNED_PAYLOAD_SIZE`, `TRUNCATED_PAYLOAD`, `UNSUPPORTED_TRAILING_DATA`,
  `MISALIGNED_LOAD_ADDRESS`, `LOAD_ADDRESS_OUTSIDE_RAM`,
  `PAYLOAD_EXCEEDS_RAM`, `MISALIGNED_ENTRY`, `ENTRY_OUTSIDE_PAYLOAD`,
  `UNSUPPORTED_DATA_SECTION`, `MISALIGNED_BSS_ADDRESS`, `BSS_OUTSIDE_RAM`,
  `BSS_EXCEEDS_RAM`, `MISALIGNED_STACK`, `STACK_OUTSIDE_RAM` (below/above),
  `MISALIGNED_GP`, plus `READ_OUTSIDE_PAYLOAD`.

## Private fixture record (non-reconstructive metadata only)

The private Hercules `SLUS_005.29` fixture was present at the documented
local path and was ingested; the gate recorded only:

- file SHA-256
  `c230ff5cd14bdfa392f5d5765c9c907b631875aaaa7844792b38b9ac54930f6f`,
  129024 bytes;
- payload SHA-256
  `2f48da4c642b25dd9d0b033f77b80a19e5befe34dc19da3194a51998e97c71be`,
  126976 bytes;
- entry PC `0x800132e8`, GP `0x00000000`, load address `0x80010000`,
  text end `0x8002f000`, stack pointer `0x801ffff0`, stack size 0,
  data/BSS absent;
- reserved header region 0x38..0x7ff: SHA-256
  `e6a138356b7e46be030334fdd789fab8cafeee2c85d44b54edafd391427b54fe`,
  55 non-zero bytes in 0x4c..0x82 (content not recorded).

No executable bytes, strings, disassembly or reconstructive derived data are
present in the evidence. The fixture is explicitly marked
`is_pass_criterion: false`; the gate passes on the synthetic coverage alone
and would record `present: false` if the fixture were absent.

## Official runs

Command `python .openrecomp-phase9/src/p9_stage_runner_v1.py --stage P9-01
--script tools/test_phase9_ingestion_v1.py --evidence-dir
.openrecomp-phase9/evidence/P9-01 --tests-json p9_01_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 5840 bytes (LF), sha256
`d7d2850111c8ed9c744dc410b8fcfb3ef91f01c4ca096977b9513c83ea326acc`.

Sidecar identities:

- `p9_01_tests.json` `d02b97190c484c85b020c0d05be9afac38e958b39d6ad3e3d91d46c5c00da4fe`;
- `private_fixture.json` `068b1f19181115cbecf0379b0996224ec0675a6d9c3cf9d8cca0f32ac00676f0`;
- `synthetic_identity.json` `1e4d86617a0461e61de6e604564ac868903b10dd0accffa747fe79a936c62b8d`;
- `official_runs.json` `66845992f3c8498059e8be685429b3edc17d805da4589142424fea999132048b`;
- `determinism.json` `2a08ded47fc9d28a4246af73fe7c0b9c9a8d4723f6b7e10caa913e81f64eef26`;
- `run1.txt` = `run2.txt` `d7d2850111c8ed9c744dc410b8fcfb3ef91f01c4ca096977b9513c83ea326acc`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Claim-ledger delta

`BOUNDED`: PS-X EXE ingestion for the exact bounded V1 container form above,
proven on original synthetic fixtures and exercised on the private fixture
(metadata only). No execution, address-space mapping, translation or platform
service is claimed at this stage.

## Next stage

`P9-02` - PS1 executable image and memory-map contract: map the payload into
an explicit PS1 guest address-space model with named regions, permissions,
stack and explicit KSEG handling; no silent masking and no invented mappings.
