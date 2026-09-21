# OpenRecomp Phase 10 Evidence

Each completed Phase-10 stage writes `.openrecomp-phase10/evidence/<STAGE>/`
with:

- `RESULT.md` - the human-readable record;
- `<stage>_tests.json` - the machine-readable gate result;
- `official_runs.json` - two official runs with byte-identical stdout, empty
  stderr and exit 0, plus sidecar hashes;
- `determinism.json` - the stage runner's determinism record;
- `run1.txt`, `run2.txt` - LF-normalized official stdout captures;
- `run1.err.txt`, `run2.err.txt` - stderr captures (must be empty);
- stage-specific sidecars (baseline, toolchains, fixture/disc identity,
  frontier records, milestone records, emission/native observables, reference
  comparison, ...).

Rules:

1. Evidence is deterministic: UTF-8, LF endings, sorted keys, no timestamps,
   no absolute host paths, no process identities.
2. `PASS` requires exit 0, empty stderr, byte-identical stdout across two
   official runs, and no `FAIL:` line.
3. Private-fixture evidence contains only non-reconstructive metadata: no
   payload bytes, no disassembly excerpts, no strings, no jump tables, no
   sectors or disc file contents.
4. Generated executables, toolchains, build roots and disc images stay
   untracked under `.openrecomp-phase10/build/`, `.openrecomp-phase10/cache/`
   or `.openrecomp-phase10/external/` and are represented by hashes only.
5. Evidence directories are never reused for a different stage identity.
