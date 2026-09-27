# OpenRecomp Phase 18 Evidence Schema

Every stage in `.openrecomp-phase18/evidence/P18-xx/` produces:

1. `RESULT.json`:
   - `schema`: `"openrecomp-phase18-result-v1"`
   - `stage`: `"P18-xx"`
   - `status`: `"PASS"` | `"FAIL"`
   - `evidence_class`: `"REPRESENTATIVE_TEST_RECORD"` |
     `"PRIVATE_FIXTURE_BOUNDED"`
   - `markers`: dictionary of stage and claim markers
   - `next_stage`: the successor stage
2. `determinism.json`: dual-run reproducibility verification.
3. Stage-specific JSON documents recording non-reconstructive metadata.
4. `run1.txt`, `run2.txt`, `run1.err.txt`, `run2.err.txt`.
5. `official_runs.json`: emitted by the stage runner.

## Public-Safety Rules

- No private host paths containing user directories.
- No raw machine code instructions or raw payload hex.
- No committed copyrighted game bytes.
- No reconstructive payload metadata (`payload_bytes`, `raw_instruction`,
  `bios_bytes`, `instruction_word`).
- Public projection values are restricted to safe scalars and nested structures
  of safe scalars.

## Imported reconnaissance

Imported historical reconnaissance is reference/hypothesis material only and is
never authoritative proof. Phase-18 evidence records import **inventory
metadata** (counts, digests, category names) and never the private absolute
import paths or any imported bytes.
