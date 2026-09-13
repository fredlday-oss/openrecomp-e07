# OpenRecomp frontend contract V1

The architecture-neutral frontend contract is the executable boundary every guest architecture must satisfy before its programs can cross the common OpenRecomp layers.

- Machine-readable contract: [`../contracts/frontend_contract_v1.json`](../contracts/frontend_contract_v1.json)
- Enforcement gate: `python tools/check_frontend_contract_v1.py`
- Pass marker: `OPENRECOMP_FRONTEND_CONTRACT_V1=PASS`

The gate is data-driven: every lowering rule in the contract JSON names a probe, and the gate fails if a declared probe has no implementation or an implemented probe is not declared (anti-drift). A skipped check never counts as a pass.

## Boundary

```text
guest executable / clean machine-code fixture
        |
        v
architecture frontend (guest-specific, per-architecture)
   decode -> classify -> lower guest behaviour away
        |
        v
normalized OpenRecomp IR V1   (frozen, architecture-neutral)
        |
        v
Module Image V1 -> Core API V1 reference executor / portable C AOT -> Native AOT ABI V1
```

Everything above normalized IR V1 is a frontend responsibility. Everything below it is architecture-neutral and must never learn a guest-specific rule.

## Adapter surface

Each architecture provides an adapter module (`adapters/<architecture>.py`) exposing:

- `info`: an `ArchitectureInfo` value (`architecture_id`, `bits`, `endianness`, `registers`, `calling_convention`);
- `decode(address: int, word: int) -> dict`: exact decode of one instruction word, raising the adapter's decode error (a `ValueError` subclass, usually `DecodeError`) for any unknown, malformed, misaligned or out-of-range encoding — never a best guess;
- `branch_targets(insn: dict) -> Iterable[int]`: static direct targets, empty when none;
- optionally `is_control_flow(insn: dict) -> bool` for CFG construction.

The adapter's legacy `architecture_id` may name a bounded implementation profile (for example `mips32-bounded-v1`). The authoritative guest identity for the common layers is `ir.source.architecture`, which must equal the registered architecture name.

## Frontend surface

Each architecture provides a frontend (`tools/<architecture>_frontend_v1.py`) whose `convert(...)` produces exactly three documents:

1. normalized IR V1 (validated against `schema/openrecomp-ir-v1.schema.json` plus the semantic checks in `tools/validate_ir_v1.py`);
2. an execution sidecar with the keys declared in the contract (`source_input_sha256`, `memory_size_bytes`, `initial_state`, `memory_segments`, `entry_state_slot`, `max_operations`, plus the declared optional keys) — consumed by `tools/package_ir_v1_module.py`;
3. a deterministic report (producer-defined evidence).

The command-line entry point rejects with exit code 2 and prints `OPENRECOMP_<FRONTEND>_V1=FAIL`, or reports `OPENRECOMP_<FRONTEND>_V1=PASS`.

## Host-contract preconditions

A frontend must reject a host contract that is not deterministic or does not fault closed:

- `memory.oob_policy` must be `"deterministic fault"`;
- `system.wall_clock` and `system.randomness` must be false;
- `host_contract.contract_version == ir.host_contract_version`;
- `host_contract.memory.size_bytes == sidecar.memory_size_bytes`;
- `sidecar.source_input_sha256 == ir.source.input_sha256`.

## Lowering rules (each enforced by a probe)

| Rule | Meaning |
| --- | --- |
| ir-source-identity-must-match-registration | `ir.source` names the registered architecture, an `openrecomp.*` adapter identity, an allowed address width/endianness, and the exact fixture hash |
| ir-vocabulary-is-closed | normalized IR contains no guest mnemonic in any `op`/`kind`/`predicate` field |
| conversion-is-deterministic | identical fixture bytes produce byte-identical IR, sidecar and report |
| host-contract-must-fail-closed | non-faulting `oob_policy` is rejected |
| host-contract-must-be-deterministic | wall clock or randomness is rejected |
| unknown-encoding-rejected | unimplemented encodings raise the adapter decode error |
| undeclared-state-slot-rejected | reads/writes of undeclared slots are rejected by IR validation |
| memory-address-type-must-match-address-bits | every address operand is typed exactly `i<source.address_bits>` |
| shift-count-must-be-normalized | an unnormalized shift count faults deterministically instead of being masked |
| no-division-in-ir-v1 | frozen IR V1 has no division/remainder; guest divides are rejected by the frontend |
| unsupported-feature-rejected | `required_features` outside the supported set is rejected |
| trap-terminator-is-the-fail-closed-exit | unsupported control-flow edges lower to a `trap` terminator that faults with its reason |
| module-integrity-is-enforced | a module whose recorded IR/host-contract hashes do not match the documents is rejected |

## Narrow-address guests

Frozen IR V1 allows `source.address_bits` of 32 or 64 only. Guests with narrower address spaces (SM83, Z80, 6502-family are 16-bit) are modeled with `address_bits = 32`:

- guest addresses are carried zero-extended in `i32`;
- the frontend wraps guest PC/pointer arithmetic to the architectural width before emitting it;
- module memory is sized to the mapped guest address space so an out-of-range access faults deterministically.

## Registered architectures

| Architecture | Adapter legacy id | Classification | Chain proof |
| --- | --- | --- | --- |
| `riscv32-rv32i` | `riscv32-rv32i` | PROVEN | prebuilt IR V1 module executes through Module Image V1 + Core API V1 (`observed_state=22`, `function_return=22`); the full ELF→native/WebAssembly chain is the toolchain-gated `RUN.sh` proof |
| `mips32-le` | `mips32-bounded-v1` | PASS (bounded) | full fixture chain: fixture → frontend → IR V1 → Module Image V1 → Core API V1, matching the published `checksum=1950232098`, `return_v0=31`, `operations=100`, `delay_slots=7` |
| `mips32-stub` | `mips32-stub` | CANDIDATE (interface only) | none — `decode` raises `NotImplementedError` |

## Prohibited

- adding a guest-specific operation to frozen normalized IR V1;
- adding guest-specific behaviour to the Core API reference executor, the portable C AOT backend or Native AOT ABI V1;
- inferring semantics for an undocumented encoding;
- weakening a memory bounds check, alignment policy or execution limit to make a fixture pass;
- committing proprietary ROM, BIOS, key or console-derived binary material.

## Adding a new architecture

1. implement `adapters/<architecture>.py` against the adapter surface;
2. implement `tools/<architecture>_frontend_v1.py` emitting IR V1 + sidecar + report and rejecting non-deterministic host contracts;
3. register the architecture in `contracts/frontend_contract_v1.json` with its `adapter_architecture_id`, `decode_reject_probe` and a `chain_proof` (or an explicit `CANDIDATE-interface-only` classification with no chain proof);
4. add any new lowering rules as contract entries with a probe implemented in `tools/check_frontend_contract_v1.py`;
5. run the gate twice and require byte-identical `--json` output;
6. regenerate `SOURCE_SHA256SUMS.txt` (`python update_sums.py`).
