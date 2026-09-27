# HUMAN_REVIEW_REQUIRED — P17-05R through P17-07R proof gap

Status update (controller): P17-04R Revision 4 was independently re-verified and integrated by fast-forward to `0ab4e7eb2ed4393cec7f61a79705d2c44bbc4441`; see `.openrecomp-phase17/evidence/P17-04R/CONTROLLER_REVIEW.md`. P17-05R was accepted and integrated; P17-06R and P17-07R were also implemented and accepted. **P17-07R was independently reviewed by the controller and integrated by fast-forward from `2701415` to `b553f70163fbd660252a3fcdaa77eee672af0f48`; see `.openrecomp-phase17/evidence/P17-07R/CONTROLLER_REVIEW.md`.** The P17-04/P17-05/P17-06/P17-07 bullets below are historical. **P17-90 was independently reviewed and integrated by fast-forward from `c784fc75b0dbed7f7e4c66d23a40a53b8ab818f2` to `53528956b3276e8bc3f954dc141049bb7ab7c74b`; see `.openrecomp-phase17/evidence/P17-90/CONTROLLER_REVIEW.md`.** **P17-91 was independently reviewed by the controller and integrated; see `.openrecomp-phase17/evidence/P17-91/CONTROLLER_REVIEW.md`.** The remaining fail-closed stop covers P17-99; the controller stopped before running it.

Reason: review of the implemented stages found that the historical P17-04 through P17-07 gates are metadata/projection checks, not sufficient mechanical proof of the requested runtime behavior:

- P17-04 emits a block inventory and a C inventory of addresses/counts; it does not emit executable guest code or establish that the active build executes it.
- P17-05 validates JSON causality fields against frozen evidence; it does not invoke a live A0:0x43 dispatch path or perform a real emission-ablation execution test.
- P17-06 advances through authenticated record addresses and stops on a control-flow classification, but does not execute the authentic decoded instruction semantics or maintain a checked authenticated instruction-word source. Its PASS cannot establish the exact authentic semantic frontier.
- P17-07 (historical, superseded) derived all device observations from an empty synthetic transcript and therefore could not prove that the authentic prefix encountered or did not encounter device activity. **This is now replaced by P17-07R**, which binds every observation to the committed, digest-verified P17-06R transcript and to a provenance map the gate rebuilds itself from the read-only fixture bytes, and which the controller independently re-verified (dual fresh-root runs byte-identical, 8340-record re-derivation reproduced, 16 controller-authored tamper cases all fail closed).

These are architectural proof gaps, not a genuine unsupported guest frontier. The historical commits/evidence are preserved; no prior-phase files were modified and no terminal Phase-17 marker is promoted. The required next action is human review and redesign of P17-04/P17-06 around a mechanically authenticated executable representation, real dispatch/ablation, and checked device transcript semantics.

Verified before stop:
- controller branch phase17/ps1-title-overlay-recompile-v1
- the historical P17-07 implementation was integrated before the review stop; the fail-closed classification is committed separately
- Phase-17 source manifest passes
- canonical frozen Phase-16 integrity passes
- legacy Phase-16 native LF/CRLF mismatch remains classified PRE_EXISTING_FAIL
- P17-07 runner had dual-run PASS, but that PASS is not accepted as mission proof for the reasons above (historical P17-07; superseded by the controller-reviewed P17-07R)
- P17-07R accepted conclusion is bounded: the observed device frontier is dominated by a zero-returning GPUSTAT polling loop, which does not prove a rendered frame or general GPU behaviour
- required NOT_PROVEN markers remain preserved
