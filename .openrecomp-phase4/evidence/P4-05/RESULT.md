# P4-05 result (PASS)

Stage: `P4-05` Platform Adapter Interface V1 (frozen queue row).
Gate: `tools/test_phase4_platform_adapter_v1.py` (76 checks, sha256
`502f31307f6254e372f1db5a5b60bb7fec1e768cf3b5eaf5240a257d189d2c41`).
Evidence: `.openrecomp-phase4/evidence/P4-05/`.

Markers issued:

- Stage marker: `OPENRECOMP_P4_05=PASS`
- Gate marker: `OPENRECOMP_PHASE4_PLATFORM_ADAPTER_V1=PASS tests=76`
- Terminal marker (reserved): `OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN`
- General compatibility marker (never promoted):
  `OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN`

## Objective (frozen queue)

Define an architecture-neutral platform-adapter contract through which
future platform-specific implementations can provide memory maps, services,
timing, input, graphics/audio hooks or other platform behaviour without
contaminating the recompiler core. Do not claim support for any console
merely because the adapter interface exists.

## Implementation (additive Phase-4 files only)

- `.openrecomp-phase4/src/p4_platform_adapter_v1.py`:
  - `AdapterIdentity` (stable lower-case adapter id, contract-compatible
    version, description) - the only place a platform name may appear;
  - `MemoryMap` (declared guest regions reusing the P4-02 region model and
    its validation) and `TimingProfile` (virtual tick source only);
  - `ServiceProfile`: the subset of the *generic* interface catalog the
    adapter supports, plus declarative aliases and handler bindings;
    platform behaviour is expressed through aliases/handlers, never by adding
    platform names to the core catalog;
  - `PlatformHooks`: optional graphics/audio hooks receiving the P2-08
    `RuntimeFrame`/`RuntimeAudio` contracts; never mandatory;
  - `validate_adapter` / `bind_platform`: fail-closed validation and binding
    that composes the adapter with the P4-02 memory model, the P4-04
    deterministic I/O runtime and the P4-03 mediator, producing a
    `BoundPlatform` with an explicit capabilities document and explicit
    negative compatibility claims (`console_compatibility: false`,
    `arbitrary_binary_compatibility: false`, `cycle_accuracy: false`);
  - `core_contract_document`/fingerprint (`f9a536ba...`).
- `tools/test_phase4_platform_adapter_v1.py` - the P4-05 gate.
- `.openrecomp-phase4/SOURCE_SHA256SUMS.txt` - grown additively to fourteen
  entries.

No frozen Phase-1/Phase-2/Phase-3 file, gate, evidence byte or tag was
modified, and the P4-01..P4-04 modules and catalogs are unchanged.

## Verification highlights

- `contract:*`: name/version, adapter-id pattern, virtual-only timing, the
  five approved generic interfaces (P4-03 base plus P4-04 I/O), optional
  hooks, explicit negative claims, stable fingerprint, and no console or
  renderer/audio-backend tokens in the contract document.
- `base:*` / `reject:*`: base-class defaults (virtual timing, empty input,
  no services, no hooks) and required-method failures.
- `identity:*` / `memory:*` / `timing:*` / `profile:*`: validation positives
  and negatives (bad ids/versions, empty descriptions, empty/overlapping/
  non-region memory maps, host timing, unknown or terminating interface
  bindings, invalid alias targets).
- `validate:*` / `bind:*`: a reference synthetic adapter validates and binds;
  missing identity, invalid memory maps, host timing and unbindable service
  profiles all fail closed at validation and binding.
- `bound:*`: composed memory/IO/mediator binding, exact interface order,
  capabilities document, negative claims, alias-mediated output
  (`synthetic.out` -> generic stream 0), clock/input/read dispatch, unknown
  service fail-closed, document round-trip and no host-path leakage.
- `hooks:*`: graphics/audio hooks record P2-08 frames/audio deterministically
  and remain optional (`graphics_hook`/`audio_hook` false without them).
- `determinism:*` / `containment:*`: identical documents/fingerprints across
  binds; no platform/backend imports and no fixture tokens in the module.

## Determinism

- Two consecutive official gate runs: exit 0, empty stderr, stdout
  byte-identical raw (2631 bytes, `849af7fd...`) and LF (`77309795...`), and
  `p4_05_tests.json` byte-identical across both runs (`50e1bfb5...`).
- Evidence: `official_runs.json`, `determinism.json`.

## Regressions

- P2-08 `PASS tests=169`; P4-01 `PASS tests=156` (`81c96314...`); P4-02
  `PASS tests=113` (`5cfc58f1...`); P4-03 `PASS tests=86` (`cc2f73da...`);
  P4-04 `PASS tests=101` (`e55ad6cb...`).
- `tools/phase1_host_gates_v1.py` `PASS=44 FAIL=0 SKIPPED=2`.
- `tools/public_safety_scan.py` `OPENRECOMP_PUBLIC_SAFETY=PASS`.
- P4-00 `PASS tests=74` (`953312d0...`) with the documented frozen-gate
  boundary-context hygiene (`regression_hygiene.json`).

## Limitations

- V1 admits platform-specific behaviour only through the approved generic
  interfaces (aliases/handlers); adapter-defined interface *names* are not
  part of V1 and are rejected. Extending the catalog beyond the approved
  generic set is out of scope for this phase.
- The contract is defined and exercised with a synthetic reference adapter
  only; no real platform (console or otherwise) is implemented, and the
  bound platform explicitly records `console_compatibility: false`.
- Graphics/audio hooks are boundary slots over the P2-08 frame/audio
  contracts; the reusable abstraction boundary itself is P4-06's frozen
  scope.
- `GENERIC_RUNTIME_STATUS=NOT_PROVEN`; the terminal and general compatibility
  markers stay reserved.

## Next stage

P4-06 - Graphics/audio abstraction boundary.

## Repair record (discovered by P4-06)

`bind_platform` merged every P4-04 deterministic-I/O handler into the
mediator even when the adapter's service profile did not declare those
interfaces, so a minimal-profile adapter failed to bind with
`unknown runtime service` instead of binding with only its declared
interfaces. Discovered during P4-06 boundary-hook binding and repaired at the
source in `p4_platform_adapter_v1.py`: handlers are filtered to the
interfaces present in the bound registry (adapters still receive the
deterministic-I/O handlers for the interfaces they declare). The frozen P4-05
gate was re-run twice after the repair: exit 0, empty stderr, stdout
byte-identical to the official capture (`849af7fd...`, 2631 bytes), same 76
checks; the refreshed module pin is recorded in `determinism.json` and the
old/new hashes and re-run captures in `repair_record.json` /
`repair_run1.txt` / `repair_run2.txt`. No stage contract or claim changed.
