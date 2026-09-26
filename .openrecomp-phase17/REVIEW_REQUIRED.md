# HUMAN_REVIEW_REQUIRED — P17-04 through P17-07 proof gap

The controller stopped fail-closed before P17-90/P17-91/P17-99.

Reason: review of the implemented stages found that the historical P17-04 through P17-07 gates are metadata/projection checks, not sufficient mechanical proof of the requested runtime behavior:

- P17-04 emits a block inventory and a C inventory of addresses/counts; it does not emit executable guest code or establish that the active build executes it.
- P17-05 validates JSON causality fields against frozen evidence; it does not invoke a live A0:0x43 dispatch path or perform a real emission-ablation execution test.
- P17-06 advances through authenticated record addresses and stops on a control-flow classification, but does not execute the authentic decoded instruction semantics or maintain a checked authenticated instruction-word source. Its PASS cannot establish the exact authentic semantic frontier.
- P17-07 derives all device observations from an empty synthetic transcript and therefore cannot prove that the authentic prefix encountered or did not encounter device activity.

These are architectural proof gaps, not a genuine unsupported guest frontier. The historical commits/evidence are preserved; no prior-phase files were modified and no terminal Phase-17 marker is promoted. The required next action is human review and redesign of P17-04/P17-06 around a mechanically authenticated executable representation, real dispatch/ablation, and checked device transcript semantics.

Verified before stop:
- controller branch phase17/ps1-title-overlay-recompile-v1
- current HEAD includes P17-07 historical implementation, with uncommitted fail-closed state classification
- Phase-17 source manifest passes
- canonical frozen Phase-16 integrity passes
- legacy Phase-16 native LF/CRLF mismatch remains classified PRE_EXISTING_FAIL
- P17-07 runner had dual-run PASS, but that PASS is not accepted as mission proof for the reasons above
- required NOT_PROVEN markers remain preserved
