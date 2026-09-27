# Controller Review — P18-01 (GPUSTAT polling model investigation)

## Decision
ACCEPT and INTEGRATE.

## Scope checked
- Base authority: Phase-17 terminal commit
  d7cc5d09eebde398ca6ff3f3dad8dd5841913b69 (tree
  ad3aa822e5a02905ebc25477f7b6c69d0bffa055), re-verified from live Git by
  p18_frozen_phase17_authority_v1.py during the official gate.
- Additive only: three new Phase-18 modules, one new tools gate, one contract,
  P18-01 evidence, control-doc updates. No Phase-1..17 namespace touched.

## Independent verification performed
1. Official gate run (twice, via the deterministic stage runner): PASS,
   zero FAIL, empty stderr, exit 0.
2. Dual-run comparison: byte-identical stdout (raw and LF) and identical
   evidence artifacts.
3. Fresh-root reproduction (/tmp clone, private root empty): all six evidence
   artifacts byte-identical to the committed copies.
4. Adversarial checks: unmodelled-bit rejection, tampered-provenance rejection,
   unknown-owner rejection, and the synthetic anti-hardcoding control (a
   synthetic loop testing bit 19 is derived as bit 19, proving the tested bit is
   read from the guest instruction and not from the Hercules constant).

## Findings
- The authentic poll condition is derived, not assumed: PC 0x8001a9fc, loop
  lw; nop; and; beq, single-bit mask 0x04000000 (bit 26), branch back to the
  load, exit requires bit 26 set. The owning-instruction provenance digest was
  recomputed and equals the digest recorded in the committed P17-06R
  transcript.
- The guest-tested bit agrees with two independent emulator references
  (DuckStation GPUSTATReg::gpu_idle bit 26; PCSX-Redux GPUSTATUS_IDLE
  0x04000000 "CMD ready"). No title-specific value was introduced.
- The minimum state model (STATE_DRIVEN_BIT26) makes the exit reachable exactly
  when the modelled GPU reports command-ready; under ZERO_FILL_RECORDED the
  exit is mathematically unreachable. This localises the Phase-17 frontier
  cause to the constant-zero read model.

## Defects found and repaired during review
- The first synthetic anti-hardcoding control placed the mask-defining lui
  outside the authenticated search window, so the control failed closed
  (POLL_MASK_DEFINITION_NOT_FOUND). Repaired by placing the lui inside the
  window. This is a test-fixture fix only; no production semantics changed.

## Boundaries preserved
- No proof marker promoted. FIRST_FRAME_READY=NO;
  OPENRECOMP_PHASE18_HERCULES_INITIALIZATION_PROOF / FRAME_PROOF /
  PLAYABILITY_PROOF / GENERAL_PS1_COMPATIBILITY all NOT_PROVEN.
- P18-01 does not run the guest past the poll and produces no frame evidence.
  The runtime escape is deferred to P18-02.

## Evidence
- .openrecomp-phase18/evidence/P18-01/poll_condition.json
- .openrecomp-phase18/evidence/P18-01/model.json
- .openrecomp-phase18/evidence/P18-01/simulation.json
- .openrecomp-phase18/evidence/P18-01/negative_tests.json
- .openrecomp-phase18/evidence/P18-01/RESULT.json
- .openrecomp-phase18/evidence/P18-01/p18_01_tests.json (48 checks, 0 failed)
- .openrecomp-phase18/evidence/P18-01/determinism.json, official_runs.json

## Next stage
P18-02 — authentic execution escape from the polling frontier.
