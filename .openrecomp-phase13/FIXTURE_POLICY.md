# OpenRecomp Phase 13 Fixture Policy

## Private fixture

The legally obtained Hercules fixture is used locally only. The private fixture
root is `fixtures/psx/hercules` with the primary executable `SLUS_005.29`. Never
commit commercial executable payloads, disc images, proprietary game assets,
BIOS ROM contents or reconstructed private binary blobs.

Phase-13 evidence may contain bounded derived information only: hashes,
addresses, instruction words where repository policy allows, argument
classifications, service identities, callback provenance, counts and
deterministic test/evidence output.

## Synthetic fixtures

Public synthetic fixtures are project-authored and safe to commit. The Phase-13
C0/B0 service surface is exercised through public synthetic direct-dispatch
drivers and the private bounded execution.

## Synthetic controlled BIOS objects

The callback slots `0x8002ED84`/`0x8002ED88` are populated by the guest from the
documented B0 table entry `0x5B` plus the documented offsets `+0x884`/`+0x894`.
Under the versioned Phase-12 synthetic B0 model (`P12_SYNTH_BASE = 0x1F000000`,
entry `0x5B` -> `+0x1000`) these resolve to the project-owned synthetic addresses
`0x1F001884`/`0x1F001894`. They are mediated as typed internal services
(`ps1.bios.internal.pad_start_hook` / `ps1.bios.internal.pad_stop_hook`) and are
never presented as recovered BIOS addresses, never derived from the fixture and
never granted general indirect-execution permission. Unknown synthetic offsets,
null/unwritten slots, unaligned targets, guest-data targets and unregistered
indirect targets fail closed.

## BIOS images

No BIOS image is loaded, executed, emulated or committed. Documented BIOS
service semantics are recorded as identifiers plus the documented public
signature/refusal rule.
