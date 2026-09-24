# OpenRecomp Phase 14 Fixture Policy

## Private fixture

The legally obtained Hercules fixture is used locally only. The private fixture
root is `fixtures/psx/hercules` with the primary executable `SLUS_005.29`. Never
commit commercial executable payloads, disc images, proprietary game assets,
BIOS ROM contents or reconstructed private binary blobs.

Phase-14 evidence may contain bounded, non-reconstructive derived information
only: hashes, addresses, instruction semantics classifications, argument
classifications, service identities, patched-region digests, counts and
deterministic test/evidence output. Raw instruction words and payload bytes are
never committed.

## Synthetic fixtures

Public synthetic fixtures are project-authored and safe to commit. The Phase-14
C0/B0 service surface is exercised through public synthetic direct-dispatch
drivers and the private bounded execution.

## Synthetic BIOS objects

Phase 14 extends the versioned Phase-12 synthetic window (`P12_SYNTH_BASE =
0x1F000000`, size `0x2000`) with a project-owned C0 jump table, a synthetic
exception-handler object and a synthetic early-card IRQ handler object. These are
implementation-defined synthetic objects:

- they are **never** presented as recovered BIOS addresses;
- values such as `0x00000200`, `0x00000C80`, `0x00000E00`, `0x00000E28` and
  `0x00000E3C` are not used, because they would resemble real BIOS layout;
- every access is bounds-checked against the window and unknown offsets fail
  closed;
- the synthetic continuation identity is derived only from these objects and is
  never accepted from an arbitrary guest pointer.

## BIOS images

No BIOS image is loaded, executed, emulated or committed. Documented BIOS
service semantics are recorded as identifiers plus the documented public
signature/refusal rule.
