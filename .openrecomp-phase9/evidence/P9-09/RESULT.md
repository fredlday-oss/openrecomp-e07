# P9-09 result: PS1 CD-ROM/file-service boundary

Status: `PASS` (73 checks)

Markers:

- `OPENRECOMP_P9_09=PASS`
- `OPENRECOMP_PHASE9_CDROM_BOUNDARY_V1=PASS tests=73`
- `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)
- `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase9_cdrom_v1.py`.

## Implementation

`.openrecomp-phase9/src/p9_cdrom_boundary_v1.py` defines the explicit bounded
disc/file-service contract:

- the four CD-ROM ports (INDEX_STATUS `0x1f801800`, COMMAND `0x1f801801`,
  PARAMETER `0x1f801802`, INTERRUPT_ENABLE `0x1f801803`) and the documented
  32-entry command-class table;
- typed deterministic event recording with `disc_image: none` and
  `file_service: none`; no disc bytes, file system or streaming exists in the
  repository or evidence;
- unknown commands become explicit blockers; out-of-range ports fail closed
  (`NOT_A_CDROM_PORT`); reads return labelled stubs.

## Public fixture behaviour (exact)

The bounded discovery finds exactly one reachable CD-ROM access: `sb` at site
`0x80010084` writing `0x00000019` to `0x1f801801` (COMMAND). The adapter
classifies it as `TEST` (`0x19`) with no blocker and no disc image; the
transcript digest is
`d4be001509bd7e6a41730f5d90c77d81a2f64a098af7af46e3dab6654ce17fdb` and is
stable across replay. Unit checks pin the index/parameter/status registers,
the unknown-command blocker and the fail-closed port range.

## Private fixture scan (metadata only)

The same bounded discovery over the private Hercules reachable frontier finds
0 CD-ROM-range accesses in its same-block immediate window. No payload bytes
are present in the evidence; the fixture is explicitly `is_pass_criterion:
false`.

## Official runs

Command `python .openrecomp-phase9/src/p9_stage_runner_v1.py --stage P9-09
--script tools/test_phase9_cdrom_v1.py --evidence-dir
.openrecomp-phase9/evidence/P9-09 --tests-json p9_09_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 2507 bytes (LF), sha256
`649d838c00639b22a07b40b70539a11e4a011d232586e4b6c2299199d48cca1d`.

Sidecar identities:

- `p9_09_tests.json` `242c030c9a1e003ff674077a2aea12fff63df22105fb5ea6464c9eedd0e5110b`;
- `public_cdrom.json` `2bb3dfafee3ae5294a676e8f73001d3da0d542b1190e9590c014b3e001067a9e`;
- `private_cdrom.json` `80ce039200fd804e1824bca137f264ad1fa3d6180bdbb976c0c46f515891d520`;
- `official_runs.json` `7479a5a4e8388209558f5bb78aff98dfa12c15ba5c8b0ce3d5a5ba6b3892efb2`;
- `determinism.json` `89de1ae0e1743de93e223c1053ba71f7daf65a1bd01935501068d5bf20e6b4cc`;
- `run1.txt` = `run2.txt` `649d838c00639b22a07b40b70539a11e4a011d232586e4b6c2299199d48cca1d`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Documented fixture correction (P9-10 preparation)

The public fixture was corrected to initialize `$sp` itself at entry (see the
P9-03 correction record); the CD-ROM access site shifts by 8 bytes to
`0x80010084`. The transcript digest is unchanged (`d4be0015...`). The official
runs were re-issued; the official stdout identity is unchanged
(`649d838c...`).

## Claim-ledger delta

`BOUNDED`: an explicit bounded disc/file-service contract exists; the public
fixture's single reachable CD-ROM command write is classified and recorded
deterministically; unknown commands fail closed. No disc reading, file system,
streaming or hardware-accurate CD-ROM behaviour is claimed.

## Next stage

`P9-10` - native build and deterministic execution: emit native host code
through the existing architecture-neutral path, build reproducibly, run
repeatedly with byte-identical deterministic observables, and compare against
an independently structured reference.
