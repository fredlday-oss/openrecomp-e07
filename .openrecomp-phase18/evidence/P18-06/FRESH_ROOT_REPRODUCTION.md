# P18-06 fresh-root reproduction

## Purpose
The deterministic dual-run (same private-build root) proves the gate is stable
across repeats.  This record proves P18-06 does not depend on any state left
behind by earlier P18-06 work: the private build root is deleted and rebuilt
from scratch, and the stage is re-run against a clean evidence directory.

## Procedure
```
FRESH=<private-build-root>/phase18/P18-06-fresh-root
rm -rf "$FRESH"                       # asserted absent before the run
OPENRECOMP_P18_PRIVATE_BUILD_ROOT_06="$FRESH" \
  python3 tools/test_phase18_vram_display_v1.py \
    --evidence-dir .openrecomp-phase18/evidence/P18-06-freshroot
```
The override env var is `P18_PRIVATE_BUILD_ROOT_ENV` in
`.openrecomp-phase18/src/p18_vram_display_v1.py`; the official runtime source is
regenerated inside the fresh root, not copied from the previous root.

## Result
- Precondition `FRESH_ROOT_ABSENT=OK` printed before execution.
- Fresh root rebuilt: official-run-1, official-run-1-discovery, official-run-2,
  official-run-2-discovery, vram-path-control.
- Return code 0, `P18-06_CHECKS=71`, `OPENRECOMP_P18_06=PASS`,
  `OPENRECOMP_PHASE18_VRAM_DISPLAY_FRONTIER=PASS`.
- `FIRST_FRAME_READY=NO`; initialization / frame / playability / general
  compatibility all `NOT_PROVEN`.

## Artifact equality vs. the main (non-fresh) run
| artifact | sha256 | match |
|---|---|---|
| RESULT.json | 8c70907596e7fd3286ab25c5abd1d41b587c8ce09fa06ac5196e7e4debd87c3f | identical |
| vram_display.json | 2848c231c0351638485931e8dfd064abf7ba990d7a9fab178c3730d94e084e5e | identical |
| vram_verdict.json | 17632ed9a270f93f7e9892b9d6ef467260e50a8196a4212ba4e3ebf64a28211c | identical |
| display_state.json | af068649776a42e8a4f1aabe5a5dc54358921bc027626fc0ff1a79ba5acd810c | identical |
| negative_tests.json | 31aa898456f9478b3639433764b65f543ecd52c9b1820754fd21a963c5798eee | identical |

VERDICT: the P18-06 result is reproducible from a clean private-build root.
