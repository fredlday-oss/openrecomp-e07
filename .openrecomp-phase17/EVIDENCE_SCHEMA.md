# OpenRecomp Phase 17 Evidence Schema

Every stage in `.openrecomp-phase17/evidence/P17-xx/` produces:
1. `RESULT.json`:
   - `schema`: `"openrecomp-phase17-result-v1"`
   - `stage`: `"P17-xx"`
   - `status`: `"PASS"` | `"FAIL"`
   - `evidence_class`: `"REPRESENTATIVE_TEST_RECORD"` | `"PRIVATE_FIXTURE_BOUNDED"`
   - `markers`: dictionary of stage and claim markers
2. `determinism.json`:
   - Dual-run reproducibility verification (`run1_sha256 == run2_sha256`, empty stderr).
3. Stage-specific JSON documents recording non-reconstructive metadata.
4. `run1.txt`, `run2.txt`, `run1.err.txt`, `run2.err.txt`.

P17-01 additionally records:
- `title_ingestion.json`: non-reconstructive ISO 9660 path, extent, PS-X EXE header metadata, reserved-region summary, and payload decoding state.
- `negative_tests.json`: summary of deterministic rejection cases.

Public-Safety Rules:
- No private host paths containing user directories.
- No raw machine code instructions or raw payload hex.
- No committed copyrighted game bytes.
- No reconstructive payload metadata (e.g. `payload_bytes`, `raw_instruction`, `bios_bytes`).
