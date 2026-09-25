# OpenRecomp Phase 15 Fixture Policy

## Private fixture

The legally obtained Hercules fixture is used locally only. The private fixture
root is `fixtures/psx/hercules` with the primary executable `SLUS_005.29`. Never
commit commercial executable payloads, disc images, proprietary game assets,
BIOS ROM contents or reconstructed private binary blobs.

Phase-15 evidence may contain bounded, non-reconstructive derived information
only: hashes, addresses, instruction semantics classifications, argument
classifications, service identities, MMIO access classifications, counts and
deterministic test/evidence output. Raw instruction words and payload bytes are
never committed.

## Synthetic fixtures

Public synthetic fixtures are project-authored and safe to commit. The Phase-15
MMIO model is exercised through public synthetic unit drivers and the private
bounded execution.

## MMIO model

The Phase-15 interrupt/MMIO layer is a bounded, project-owned register model.
Values such as the GPUSTAT contract stub `0x14802000` and the initial
`I_STAT`/`I_MASK` value `0x0000` are documented project contract values, not
recovered hardware state. Every modelled register is bounds-checked by address
and width; unknown addresses and unsupported widths fail closed.

## BIOS images

No BIOS image is loaded, executed, emulated or committed. Documented BIOS
service semantics are recorded as identifiers plus the documented public
signature/refusal rule.
