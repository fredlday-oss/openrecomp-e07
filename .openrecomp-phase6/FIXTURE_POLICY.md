# OpenRecomp Phase 6 Fixture Policy

Phase 6 separates exactly two fixture classes. They must never be mixed in any
artifact.

## 1. Private local compatibility fixture

Classification: `PRIVATE_LOCAL_COMPATIBILITY_FIXTURE`

| Field | Value |
| --- | --- |
| Source path | `D:\OpenRecomp\Roms\phase1\nes\primary\tmnt.nes` |
| File size | 262160 bytes |
| SHA-256 | `2a9345e608ec0c57470dc6658ce8199ddea9c18076134d9ef2a56f91b0a066d1` |
| MD5 (recorded only) | `d60c64b46f9a6b5ee6a78bfe2fee7d48` |
| Container | iNES / NES 2.0 signature (`flags7 & 0x0C == 0x08`) |
| PRG ROM | 8 x 16 KiB = 128 KiB |
| CHR ROM | 16 x 8 KiB = 128 KiB |
| Mapper | 1 (MMC1 family) |
| Mirroring | horizontal |
| Trainer | none |
| Battery | no |
| Four-screen | no |

Rules:

- The bytes are never committed, copied into the repository, evidence bundle,
  package, ZIP, fixture directory, generated source, Git object database or any
  public artifact.
- It is never uploaded or redistributed.
- Recorded facts are limited to: source path, size, hashes, iNES metadata,
  mapper/mirroring/PRG/CHR inventory, and derived control-flow / instruction /
  compatibility evidence that does not reproduce copyrighted program data
  unnecessarily (counts, opcode histograms, addresses of control-flow roots,
  bank-state classifications, stop reasons), never program bytes.
- The private image must not become the public Phase-6 proof fixture.
- No general NES or commercial-game compatibility claim may be derived from
  it.
- If it requires unsupported mapper/hardware/runtime behaviour, Phase 6 fails
  closed and classifies the missing capability precisely instead of guessing.
- MMC1 board wiring beyond what the audited public fixture and cartridge
  metadata prove is never inferred from private-image behaviour.

Deterministic hashes of the private image are re-verified by the P6-00 boundary
gate without copying the file.

## 2. Public / audited fixture

The public Phase-6 terminal proof is based only on a legally redistributable
NES fixture:

- original NES program authored for Phase 6, licensed Apache-2.0 (same license
  as this repository), using MMC1/mapper 1 within the bounded supported subset;
- source `.asm` plus an original deterministic Phase-6 assembler under
  `.openrecomp-phase6/fixture/` and `.openrecomp-phase6/src/`;
- recorded: provenance, license, exact source revision (tree hash), toolchain
  and build flags, ROM SHA-256, PRG/CHR sizes, mapper, mirroring, reset/NMI/IRQ
  vectors and MMC1 register/bank configuration;
- exercises bank switching, CHR switching, mirroring, input and graphics
  behaviour sufficient to exercise the supported MMC1 contract;
- no third-party ROM bytes, no console-derived assets, no proprietary SDK
  material.

The public package (P6-12) contains only these redistributable artifacts.
`*.nes`, `*.fds`, `*.unf`, `*.unif` and ROM-derived binary copies are excluded
from version control by `.gitignore` and are scanned for by the Phase-6 gates.

## 3. Separation rules

1. Evidence directories record private-fixture facts only as hashes/metadata/
   derived analysis, never bytes.
2. The P6-12 workflow/package builds only from public fixture sources and
   regenerates the public ROM deterministically.
3. The P6-91 claim ledger keeps the legal public NROM proof (Phase 5), the
   legal public MMC1 proof (Phase 6), the private TMNT compatibility
   observations and general NES compatibility status as separate sections.
4. `PRIVATE_LOCAL_COMPATIBILITY_FIXTURE` never appears in the package or in any
   file intended for redistribution.
5. The reusable workflow never packages or embeds the source ROM it is given.
