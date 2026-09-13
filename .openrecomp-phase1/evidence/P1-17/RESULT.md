# P1-17 — SM83/GB/GBC regression + differential audit

VERDICT: `PASS`

## Source revision and working-tree state

- `HEAD = bd5f02fcd21cf42a3d1e24a67c9a285825462b76`, branch `main` (unchanged).
- Modified: `tools/phase1_host_gates_v1.py` (one gate), `SOURCE_SHA256SUMS.txt`
  (regenerated).
- Added: `tools/test_sm83_regression_v1.py` (the executable audit gate).
- No commit created. No ROM bytes involved.

## Deliverable

`tools/test_sm83_regression_v1.py` — `OPENRECOMP_SM83_GB_GBC_REGRESSION_V1=PASS`
gate (16 checks): every SM83/GB/GBC gate script plus the frontend-contract
gate and the shared sm83 architecture harness run twice with byte-identical
output required, and the frozen regression markers re-pinned.

## Audit result

```text
python tools/test_sm83_regression_v1.py
PASS audit deterministic x2: test_sm83_state_v1.py
PASS audit deterministic x2: test_sm83_decode_v1.py
PASS audit deterministic x2: test_sm83_semantics_v1.py
PASS audit deterministic x2: test_sm83_lowering_v1.py
PASS audit deterministic x2: test_gb_rom_v1.py
PASS audit deterministic x2: test_gb_headless_v1.py
PASS audit deterministic x2: test_gb_mode_v1.py
PASS audit deterministic x2: check_frontend_contract_v1.py
PASS audit deterministic x2: arch_harness_v1.py examples/sm83-v1/arch-harness-v1.json
PASS frozen marker: a=0x7 f=0xc0 hl=0x1334 sp=0xff0a operations=681      (P1-13 differential)
PASS frozen marker: a=0x7 f=0xc0 hl=0x1334 sp=0xff0c halted=1 operations=594 blocks=7  (P1-15 differential)
PASS frozen marker: tests=65  (sm83 semantics, incl. the P1-15 0xEA repair pins)
PASS frozen marker: tests=8   (sm83 lowering)
PASS frozen marker: tests=8   (gb rom)
PASS frozen marker: tests=14  (gb headless)
PASS frozen marker: tests=11  (gb mode)
OPENRECOMP_SM83_GB_GBC_REGRESSION_V1=PASS tests=16
```

## Full-harness regression

```text
python tools/phase1_host_gates_v1.py
OPENRECOMP_PHASE1_HOST_GATES_PASS=29 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
```

Skipped (never counted as pass, toolchain-gated on this host): `e07-hardened-end-to-end`
and `external-repro-v1` (need clang + gcc + POSIX).

## Differential audit summary

- P1-13 differential (reference == Core API, 64 KiB memory identical):
  `a=0x07 f=0xc0 hl=0x1334 sp=0xff0a operations=681` — unchanged from P1-13.
- P1-15 differential (ROM -> map -> frontend -> IR -> Core API == reference,
  64 KiB memory identical): `a=0x07 f=0xc0 b=0x13 c=0x34 hl=0x1334
  sp=0xff0c halted=1 operations=594 blocks=7` — unchanged from P1-15.
- All seven SM83/GB/GBC gates and the two architecture-boundary checks
  (frontend contract, sm83 harness) produce byte-identical output across
  repeated runs (deterministic audit).

## Established-path check (from the full harness)

RV32I/E07, MIPS32 vertical slice, MIPS32 expansion, causality and equivalence
gates all PASS unchanged — the P1-15/P1-16 platform work did not regress the
established paths (no PS2/R5900 implementation exists in this tree; the
frozen published numbers remain the regression targets).

## Remaining limitations (unchanged, documented in P1-12..P1-16 evidence)

- HALT bug and timer obscure behaviour: documented, fail closed / out of
  scope.
- STOP treated as HALT except the documented CGB armed-stop speed switch.
- MBC2/3/5, battery, RTC: classified, fail closed.
- PPU/APU/serial: deferred (SCOPE).

## Verdict

`PASS` — the SM83/GB/GBC chain is deterministically stable: every gate runs
twice byte-identically, the frozen differential numbers are unchanged, and
the whole-project harness reports 29 PASS / 0 FAIL / 2 SKIPPED with no
regression of the established MIPS32/RV32I paths.
