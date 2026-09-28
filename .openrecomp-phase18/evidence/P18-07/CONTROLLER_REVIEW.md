# P18-07 controller review - First-Frame Assessment

Branch: `phase18/ps1-first-frame-frontier-v1`
Stage: P18-07 (assessment / gatekeeping; fabricates no traffic, renders nothing)
Contract: `.openrecomp-phase18/contracts/P18-07.md`

## Disposition

**ACCEPT.** The stage passes its bounded contract with an independent fresh-root
reproduction and honest proof boundaries.

## What the stage mechanically establishes

- Consumes P18-02..P18-06 evidence read-only and hash-verifies the three frozen
  frontier documents against the contract-declared digests:
  - P18-04 `gpu_command_frontier.json` `a009003b...bfe9` (repaired digest);
  - P18-05 `dma_frontier.json` `f0251b43...fa5c1`;
  - P18-06 `vram_display.json` `2848c231...e5e5`.
  A mismatch, a missing document or an unparsable document fails closed.
- Evaluates the ordered causal-link chain L1..L7 and records a per-link verdict
  with the citing evidence:
  - L1 authenticated execution - **ESTABLISHED** (P18-02 continuation +
    P18-03 causal transcript: 8270 instructions, 759 distinct PCs, typed stop
    reason, 20-event causal transcript);
  - L2 authentic GP0/GP1 - **UNREACHED** (gp0=0, gp1=0);
  - L3 authentic DMA / ordering table - **UNREACHED** (dma_access_count=0, empty
    DMA events);
  - L4 decoded command semantics - **NOT_PROVEN** (zero decoded events);
  - L5 deterministic VRAM effects - **UNREACHED** (frontier not reached);
  - L6 valid display configuration - **UNREACHED** (no authentic display events);
  - L7 coherent displayable framebuffer - **NOT_PROVEN** (no authentic
    framebuffer).
- Applies the exact rule `FIRST_FRAME_READY=YES iff all of L1..L7 are
  ESTABLISHED`; the authentic result is **NO**.

## Anti-vacuity and anti-inflation

- Anti-vacuity: an all-satisfied link vector yields `YES` **in the control
  namespace only**; the gate fails closed if it does not.
- The control namespace is provably isolated: the authentic verdict is derived
  solely from the ledger's authentic link verdicts, and validation rejects any
  control-derived value reaching the authentic field
  (`CONTROL_VERDICT_CONTAMINATION`).
- Anti-inflation: six single-milestone vectors (first GP0 write; first GPU DMA;
  first ordering-table packet; first primitive; first VRAM mutation; first
  display register setup) each yield `NO`, asserted individually.

## Negative controls

Frontier digest mismatch; missing document; unparsable document; incomplete
promotion chain; established link without provenance; established link on
control/synthetic evidence; control-verdict contamination; anti-vacuity that
cannot promote; single-milestone promotion. All fail closed.

## Evidence

- Gate: `tools/test_phase18_first_frame_assessment_v1.py`, 59 checks, exit 0.
- Determinism: dual official runs byte-identical stdout (raw and LF), empty
  stderr, rc=0 both, identical artifacts.
- Fresh root: all seven artifacts byte-identical to the official evidence.
- Assessment digest `85ceec185a8f5a1fafb859f7fa32d81b57e21d4da9397f99dde11dec0818ba6f`.
- One control originally wrote a scratch `broken.json` into the evidence
  directory; it was repaired to use a private temporary directory (and any stray
  artifact removed), then the stage was re-run and re-verified.

## Proof boundary

- `FIRST_FRAME_READY=NO`; `OPENRECOMP_PHASE18_HERCULES_FRAME_PROOF=NOT_PROVEN`;
  initialization / playability / general compatibility remain `NOT_PROVEN`.
- Historical Phase-17 markers preserved verbatim; never promoted.
- No authentic VRAM content, display configuration or framebuffer is claimed.
- Phase 1-17 namespaces untouched; no reset performed.
