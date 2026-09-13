# P1-01 — Extract/document architecture-neutral OpenRecomp frontend contract

VERDICT: `PASS`

## Source revision and working-tree state

- `HEAD = bd5f02fcd21cf42a3d1e24a67c9a285825462b76`, branch `main` (unchanged during this stage).
- Pre-existing modifications carried in: `AGENTS.md` (control block), `SOURCE_SHA256SUMS.txt`, `tools/wasm_run.js` (restored in P1-00).
- No commit created.

## Deliverables

| File | Role |
| --- | --- |
| `contracts/frontend_contract_v1.json` | machine-readable executable contract (single source of truth) |
| `tools/check_frontend_contract_v1.py` | enforcement gate: structural checks + lowering-rule probes + neutral chain proofs |
| `docs/FRONTEND_CONTRACT_V1.md` | human-readable contract |
| `README.md`, `docs/ARCHITECTURE.md` | documentation links (additive only) |
| `tools/phase1_host_gates_v1.py` | new inventory gate `frontend-contract-v1` |

## What the contract requires (extracted from the existing RV32I + MIPS32 implementation, not invented)

1. **Adapter surface**: `ArchitectureInfo` (`architecture_id`, `bits`, `endianness`, `registers`, `calling_convention`), callables `decode(address, word) -> dict` and `branch_targets(insn)`, optional `is_control_flow`, and a `ValueError`-derived decode error. Decoding must fail closed: unknown/misaligned/out-of-range encodings raise, never guess.
2. **Frontend surface**: `convert(...)` emits exactly `(ir_v1, execution_sidecar, report)`; CLI rejects with exit 2 + `OPENRECOMP_<FRONTEND>_V1=FAIL`, or reports `=PASS`.
3. **Host-contract preconditions** (identical in the RV32I bridge and both MIPS32 frontends): `memory.oob_policy == "deterministic fault"`, `system.wall_clock == false`, `system.randomness == false`, version and memory-size equality across contract/IR/sidecar, sidecar/IR source-hash equality.
4. **Lowering rules**: 13 rules, each enforced by a probe implemented in the gate (see table in `docs/FRONTEND_CONTRACT_V1.md`). Notable ones, all source-backed from `schema/openrecomp-ir-v1.schema.json`, `tools/validate_ir_v1.py`, `openrecomp/executor.py`:
   - IR vocabulary is closed (no guest mnemonics leak into `op`/`kind`/`predicate`);
   - conversion is deterministic;
   - address operands must be exactly `i<source.address_bits>`;
   - shift counts must be normalized (the executor faults otherwise);
   - frozen IR V1 has no division — guest divides are rejected by the frontend (MIPS `div/divu` precedent);
   - unsupported control-flow edges lower to `trap` terminators;
   - module integrity hashes are enforced.
5. **Narrow-address rule**: frozen IR V1 allows `address_bits ∈ {32, 64}` only, so SM83/Z80/6502-family guests must be modeled with `address_bits=32` and zero-extended guest addresses (recorded for P1-10+).
6. **Registered architectures**: `riscv32-rv32i` (PROVEN), `mips32-le` (PASS bounded), `mips32-stub` (CANDIDATE interface-only), each with its adapter identity, decode-reject probe and (where present) a chain proof with published results.

## Real finding resolved during this stage

`adapters/mips32.py` advertises legacy `ArchitectureInfo.architecture_id = "mips32-bounded-v1"` while the IR it emits declares `source.architecture = "mips32-le"` (fixture profile). The gate surfaced this as a contract violation. Resolution (non-regressing, no proven code changed):

- registration entries now declare `adapter_architecture_id` (legacy implementation-profile id);
- the authoritative guest identity for the common layers is `ir.source.architecture`, which must equal the registered architecture (enforced by probe `ir-source-identity-must-match-registration`, which also checks the `openrecomp.*` adapter prefix, address width, endianness and fixture hash provenance);
- the rationale is recorded in the contract (`ir_source_identity.note`).

## Verification (all run on this host, win32/Python 3.14.6)

```text
python tools/check_frontend_contract_v1.py
OPENRECOMP_FRONTEND_CONTRACT_CHECKS=20 PROBES=13 CHAIN_PROOFS=2 FAIL=0
OPENRECOMP_FRONTEND_CONTRACT_V1=PASS
```

- structural: adapter-surface, host-contract-preconditions, execution-sidecar-conformance, narrow-address-rule, probes-declared-and-implemented (anti-drift) — PASS
- probes (13): ir-source-identity, ir-vocabulary-closed, conversion-deterministic, host-contract fail-closed + deterministic, unknown-encoding-rejected (all three adapters), undeclared-state-slot, memory-address-type, shift-count-normalized, no-division, unsupported-feature, trap-terminator, module-integrity — PASS
- chain proofs: mips32-le full fixture chain reproduces the published `checksum=1950232098`, `return_v0=31`, `operations=100`, `delay_slots=7`; riscv32-rv32i prebuilt module executes `observed_state=22`, `function_return=22` — PASS
- determinism: two consecutive runs with `--json` produced byte-identical reports (`sha256 128102F8AC60C13668D27B68DA454668BEA6CC659DB1DC0DE2466F9E37D0C245`)

Full host-gate regression after adding `frontend-contract-v1`:

```text
python tools/phase1_host_gates_v1.py
OPENRECOMP_PHASE1_HOST_GATES_PASS=17 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
```

`SOURCE_SHA256SUMS.txt` regenerated with `update_sums.py` (68 entries; manifest now includes `tools/check_frontend_contract_v1.py` and `contracts/frontend_contract_v1.json`). `python tools/check_markdown_links.py` → `OPENRECOMP_DOC_LINKS=PASS`.

## Semantic assumptions

- The contract documents behaviour that the two implemented guest paths already exhibit; nothing was inferred beyond what the schema, validator, executor and frontends actually do.
- The `mips32-bounded-v1` legacy adapter id is treated as a profile name, with `ir.source.architecture` authoritative — matching the frontend's own fixture-profile check (`meta["architecture"] != "mips32-le"` → reject).

## Remaining limitations

- `riscv32-rv32i`'s full ELF→IR→native/WebAssembly chain remains toolchain-gated (`RUN.sh` needs clang/gcc); its Core API leg is proven here via the prebuilt minimal module.
- No third architecture is registered yet; the contract is the acceptance target for SM83 (P1-10+), Z80 (P1-20+) and 6502-family (P1-30+) frontends.

## Verdict

`PASS` — the architecture-neutral frontend contract is extracted, documented, machine-readable and enforced by a deterministic executable gate that both existing architectures satisfy without any change to frozen IR V1 or proven code.
