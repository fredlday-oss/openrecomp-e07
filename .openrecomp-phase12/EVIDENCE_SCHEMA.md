# OpenRecomp Phase 12 Evidence Schema

Each stage writes `.openrecomp-phase12/evidence/<STAGE>/RESULT.md` plus
machine-readable sidecars (`RESULT.json`, `<stage>_tests.json`,
`official_runs.json`, `determinism.json` and stage-specific records).

## Required record

- verdict, frozen stage objective, and the exact stage marker/gate marker;
- baseline commit, tree, branch and audited HEAD/tree;
- exact changed files and whether each change is additive;
- official commands, exit codes, empty-stderr result, stdout byte count, raw
  SHA-256 and LF-normalized SHA-256 for two official runs;
- source, toolchain, flags, build-product identities and provenance;
- fixture identity (SHA-256, size, PS-X EXE header metadata, CUE/BIN identity)
  where applicable;
- independent/reference comparison where applicable;
- milestone classification where applicable;
- negative and fail-closed coverage;
- frozen-boundary and relevant regression results;
- claim-ledger deltas, limitations and unproven areas;
- tracked/untracked side effects and an evidence-file index;
- exact next stage or the specific blocker.

## Determinism rules

1. UTF-8 and LF line endings only.
2. No timestamps, absolute host paths, process identities, UUIDs or unstable
   ordering in committed evidence.
3. Official `PASS` requires two byte-identical stdout streams, empty stderr,
   exit 0 and no `FAIL:` line.
4. Compilation, disassembly or self-comparison alone is not equivalence.
5. Unknown semantics, targets, aliases, KSEG mappings, services, GPU commands,
   CD-ROM commands and ABI states fail closed.
6. Generated executables, toolchains, upstream source trees, disc images and
   build products remain untracked and are represented only by reproducible
   provenance, metadata and hashes.
7. Every gate emits its stage marker, gate marker, both reserved Phase-12 claim
   markers and any claim markers it evaluates.
8. Evidence directories are never reused for a different stage identity.

## Private-fixture evidence rules

1. The private Hercules fixture contributes only non-reconstructive metadata:
   hashes, sizes, filenames, header fields, offsets, region classifications,
   instruction/control-flow counts, MMIO access classifications, file/sector
   access classifications, bounded transcripts, function/block identifiers,
   state digests, diagnostics and the identity of the first unresolved blocker.
2. No payload bytes, disassembly excerpts, strings, jump tables, sectors, file
   contents, framebuffer content, VRAM content, textures, palettes or
   reconstructive derived data are committed, in any encoding.
3. A stage that touches the private fixture must include a public-safety check
   proving the committed evidence contains no private binary material and no
   private host path.
4. Private-fixture results are labelled `PRIVATE_FIXTURE_BOUNDED` and never
   promote a general compatibility or playability marker.
