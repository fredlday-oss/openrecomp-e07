# OpenRecomp Phase 16 Evidence Schema

Every stage in `.openrecomp-phase16/evidence/P16-xx/` produces:
1. `RESULT.json`:
   - `schema`: `"openrecomp-phase16-result-v1"`
   - `stage`: `"P16-xx"`
   - `status`: `"PASS"` | `"FAIL"`
   - `evidence_class`: `"REPRESENTATIVE_TEST_RECORD"` | `"PRIVATE_FIXTURE_BOUNDED"`
   - `markers`: dictionary of stage and claim markers
2. `determinism.json`:
   - Dual-run reproducibility verification (`run1_sha256 == run2_sha256`, empty stderr).
3. Stage-specific JSON documents recording non-reconstructive metadata.
4. `run1.txt`, `run2.txt`, `run1.err.txt`, `run2.err.txt`.

Public-Safety Rules:
- No private host paths containing user directories.
- No raw machine code instructions or raw payload hex.
- No committed copyrighted game bytes.
