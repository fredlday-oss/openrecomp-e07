# OpenRecomp Phase 7 Fixture Policy

Phase 7 separates exactly two fixture classes. They must never be mixed in any
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
- It is analyzed only in place, by metadata/hash, and recorded facts are
  limited to: source path, size, hashes, iNES metadata, mapper/mirroring/
  PRG/CHR inventory, bank configuration and derived control-flow /
  instruction / classification evidence that does not reproduce copyrighted
  program data unnecessarily (counts, opcode histograms, addresses of
  control-flow roots and sites, bank-state classifications, feasible-target
  classifications, stop reasons), never program bytes.
- The private image must not become the public Phase-7 proof fixture.
- No general NES or commercial-game compatibility claim may be derived from
  it. TMNT playability remains `NOT_PROVEN` unless actual generated-native,
  meaningful interactive execution has been demonstrated.
- If it requires unsupported mapper/hardware/runtime behaviour, Phase 7 fails
  closed and classifies the missing capability precisely instead of guessing.
- MMC1 board wiring beyond what the audited public fixtures and cartridge
  metadata prove is never inferred from private-image behaviour.

Deterministic hashes of the private image are re-verified by the Phase-7
gates without copying the file.

## 2. Public / audited fixtures

The public Phase-7 proof is based only on legally redistributable NES
fixtures:

- original NES programs authored for Phase 7, licensed Apache-2.0 (same
  license as this repository), using only the audited mapper/opcode/control
  flow mechanisms under proof;
- source `.asm` plus an original deterministic Phase-7 assembler under
  `.openrecomp-phase7/fixture/` and `.openrecomp-phase7/src/`;
- recorded: provenance, license, exact source revision (tree hash), toolchain
  and build flags, ROM SHA-256, PRG/CHR sizes, mapper, mirroring,
  reset/NMI/IRQ vectors and bank configuration;
- each fixture exercises exactly the semantic/control-flow form it proves,
  including edge cases, flags, addressing, memory effects, unresolved
  fail-closed cases and negative cases;
- no third-party ROM bytes, no console-derived assets, no proprietary SDK
  material.

The reusable workflow (P7-14) contains only these redistributable artifacts.
`*.nes`, `*.fds`, `*.unf`, `*.unif` and ROM-derived binary copies are excluded
from version control by `.gitignore` and are scanned for by the Phase-7 gates.

## 3. Separation rules

1. Evidence directories record private-fixture facts only as hashes/metadata/
   derived analysis, never bytes.
2. The workflow builds only from public fixture sources and regenerates the
   public ROM deterministically.
3. The P7-91 claim ledger keeps the legal public NROM proof (Phase 5), the
   legal public MMC1 proof (Phase 6), the public Phase-7 translation/
   control-flow proof, the private TMNT observations and general NES
   compatibility as separate sections.
4. `PRIVATE_LOCAL_COMPATIBILITY_FIXTURE` never appears in the package or in
   any file intended for redistribution.
5. The reusable workflow never packages or embeds the source ROM it is given
   and never writes ROM bytes into caller-visible reports.
