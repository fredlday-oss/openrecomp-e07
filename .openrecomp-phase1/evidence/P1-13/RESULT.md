# P1-13 — SM83 control flow + OpenRecomp IR/lowering

VERDICT: `PASS`

## Source revision and working-tree state

- `HEAD = bd5f02fcd21cf42a3d1e24a67c9a285825462b76`, branch `main` (unchanged).
- Modified: `tools/phase1_host_gates_v1.py` (one gate), `contracts/frontend_contract_v1.json`
  (sm83-gb classification `IN-PROGRESS-decode-only` -> `PASS-bounded-differential`), `SOURCE_SHA256SUMS.txt` (regenerated).
- Added: `tools/sm83_frontend_v1.py`, `tools/test_sm83_lowering_v1.py`.
- No commit created.

## Deliverables

| File | Role |
| --- | --- |
| `tools/sm83_frontend_v1.py` | SM83 frontend: region decode + CFG + full documented instruction lowering into frozen normalized IR V1 via the shared scaffolding |
| `tools/test_sm83_lowering_v1.py` | 8-test gate: differential proof, determinism, full lowering coverage, terminator coverage, fail-closed rejections |

## Control-flow model (documented, fail closed)

- Linear decode of a declared region (every region byte must decode — a code
  region contains no embedded data); leaders = region start, entry, static
  branch targets, and continuations (fall-throughs; CALL/RST continuations are
  return targets, so they are always leaders).
- One IR function per region; the guest stack lives in guest memory exactly
  like hardware: CALL/RST push the 16-bit return address high-byte-first;
  RET/RETI pop it.
- `jp`/`jr`/`call`/`rst` lower to `jump`/`branch` to the leader block at the
  static target; targets outside the region fail closed.
- `ret`/`reti`/`jp (hl)` lower to `indirect_jump` with the full block set as
  candidates; a return address with no block faults deterministically.
- Conditional forms branch on the documented F flag bits; the taken side of a
  conditional `ret`/`call` uses a synthetic helper block (one terminator per
  block is a frozen-IR rule).
- HALT/STOP set `platform:halted` and return — the reference halts identically,
  so final states compare. EI/DI lower to `platform:ime` writes; the documented
  one-instruction EI delay is only observable through interrupt servicing
  (platform stage P1-14+), so differential fixtures exclude EI/DI (recorded in
  the frontend header).

## Semantic lowering (all documented instructions)

Every documented SM83 instruction lowers to closed-vocabulary IR V1 using the
P1-02 scaffolding: i8 registers as `cpu:*` slots, i16 SP/pairs composed from
halves, addresses zero-extended i16->i32 (narrow-address rule), 8-bit memory
accesses with alignment 1, exact Z/N/H/C computation in i16 arithmetic (add/
adc/sub/sbc/cp), logical/rotate/shift/BIT/RES/SET/SWAP bit-exact paths, DAA as
documented (N preserved, H reset), POP AF masking, 16-bit INC/DEC/ADD HL/ADD
SP with the documented flag rules, and stack push/pop in guest memory.

## Verification

```text
python tools/test_sm83_lowering_v1.py
OPENRECOMP_SM83_LOWERING_V1=PASS tests=8
```

- **Differential proof**: one synthetic program (ALU+flags, rotates, CB page,
  DAA, memory forms, 16-bit arithmetic, stack, call/ret, conditional jump,
  RST->halt) executed by the independent P1-12 reference and by the frontend
  -> IR V1 -> Module Image V1 -> Core API `ReferenceExecutor`:
  `a=0x07 f=0xc0 hl=0x1334 sp=0xff0a`, operations=681, **full 64 KiB guest
  memory byte-identical**, halted flag identical.
- Frontend determinism: IR/sidecar/report byte-identical across two conversions.
- Full lowering coverage: all documented non-control opcodes + all 256 CB
  encodings convert without error.
- Terminator coverage: 9 control-flow forms (jp, jp-cc, jr-cc, call-cc,
  ret-cc, ret, rst, jp (hl), stop) convert.
- Fail-closed rejections: undocumented opcode, out-of-region jump target,
  undocumented byte inside the region, instruction overlapping the region
  boundary.

Full host-gate regression:

```text
python tools/phase1_host_gates_v1.py
OPENRECOMP_PHASE1_HOST_GATES_PASS=25 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
```

`python tools/check_frontend_contract_v1.py` still reports
`CHECKS=20 PROBES=13 CHAIN_PROOFS=2 FAIL=0` with the sm83-gb adapter now
classified `PASS-bounded-differential` in the registration.

## Semantic assumptions

- The recompiled model is *structured control flow*: any program the frontend
  accepts executes identically to the reference for the exercised classes; the
  proof is differential, not cycle-exact (cycles out of scope, as everywhere).
- EI/DI delay and interrupt servicing are deferred to the platform stage
  (P1-14/P1-15) — documented, not guessed.

## Remaining limitations

- Native AOT compilation of SM83 modules is not yet exercised (toolchain
  gates); Core API V1 is the execution reference.
- No ROM ingestion yet (P1-14).

## Verdict

`PASS` — SM83 control flow and the complete documented instruction set lower
into frozen normalized IR V1 and a deterministic differential proof shows the
independent reference and the architecture-neutral Core API path agree on
full CPU state and all 64 KiB of guest memory.
