# P1-24 — Z80/SMS regression + differential audit

VERDICT: `PASS`

## Source revision and working-tree state

- `HEAD = bd5f02fcd21cf42a3d1e24a67c9a285825462b76`, branch `main` (unchanged).
- No commit created. No ROM bytes involved.

## Files changed

| File | Change |
| --- | --- |
| `tools/test_sms_regression_v1.py` | Added: 15-test deterministic audit gate `OPENRECOMP_Z80_SMS_REGRESSION_V1=PASS`. |
| `tools/phase1_host_gates_v1.py` | Registered gate `z80-sms-regression-v1` (area "z80"). |
| `SOURCE_SHA256SUMS.txt` | Regenerated via `python update_sums.py`. |

## Audit scope

Every P1-20..P1-23 gate script plus the architecture-boundary gates, each
run twice with byte-identical output required:

- `test_z80_state_v1.py`, `test_z80_decode_v1.py`,
  `test_z80_semantics_v1.py`, `test_z80_lowering_v1.py`,
  `test_sms_platform_v1.py`, `test_sms_headless_v1.py`,
  `check_frontend_contract_v1.py` (frontend contract gate);
- `arch_harness_v1.py examples/sm83-v1/arch-harness-v1.json` (shared
  architecture harness, boundary audit).

Frozen regression markers re-pinned:

- P1-21 differentials: `a=0x7 f=0x42 hl=0xd233 sp=0xff00 ix=0xc800
  halted=1`; block-I/O differential (INIR/OTIR flags + 8-bit port mask);
  `tests=86` (semantics), `tests=14` (lowering);
- P1-22: `tests=30` (platform contract);
- P1-23 differential: `a=0x1 f=0x42 hl=0xc000 sp=0xdff0 b=0x1 im=1
  halted=1`; `tests=6`.

## Verification

```text
python tools/test_sms_regression_v1.py
OPENRECOMP_Z80_SMS_REGRESSION_V1=PASS tests=15
(run twice: output sha256 6EDE98FCF1232BB55538B388FF7DA3DC3E164A60AF98713584098C63682E7F17)

python tools/phase1_host_gates_v1.py
OPENRECOMP_PHASE1_HOST_GATES_PASS=36 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
```

## Established-path reconciliation

The RV32I E07 and MIPS32 published numbers remain untouched and all their
host gates still pass inside the harness (mips32-frontend-v1,
mips32-expansion-v1-negative, mips32-microtests-v1, mips32-causality-v1,
mips32-equivalence-v1, core-api-v1, ir-v1-spec, adapter-seam,
frontend-contract-v1, frontend-scaffold-v1, arch-harness-mips32-v1 /
riscv32-v1). The SM83/GB/GBC chain gates (sm83-state/decode/semantics/
lowering, gb-rom/headless/mode, sm83-gb-gbc-regression-v1) also remain
green — no cross-architecture regression.

## Next

P1-30..P1-35 (6502-family / NES), then P1-90/91/99.
