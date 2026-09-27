# P17-07R — Controller independent review

Decision: **ACCEPT and INTEGRATE**.

## Authority
- controller branch `phase17/ps1-title-overlay-recompile-v1`; pre-integration HEAD `2701415223dd182a40cf257c849952a6ce63ee08` (clean)
- worker branch `agent/deepseek-phase17-p17-07r-r1`; candidate commit `b553f70163fbd660252a3fcdaa77eee672af0f48`, tree `90aa345018e541420acc558155927c5fde721f0e`
- the candidate is exactly **one** commit on top of `2701415`, whose parent is `2701415`; `2701415` is an ancestor of the controller HEAD
- review was performed in a separate detached worktree (`worktrees/review-p17-07r`) at the candidate; **the candidate was not modified during review**

## What this stage replaces
The historical P17-07 inferred "no event of this class" from a transcript *digest* and hard-coded
`encountered: false` for every observation class, so its `PASS` established no observation. P17-07R
binds every observation to the committed, digest-verified P17-06R device transcript and to a
provenance map the gate rebuilds itself from the read-only fixture bytes with the frozen decoder.

## Diff scope (verified)
`2701415..b553f70` = 18 files, 2167 insertions, 11 deletions:
- modified (4, Phase-17 metadata only): `HANDOFF.md`, `STATE.md`, `STAGE_QUEUE.md`, `SOURCE_SHA256SUMS.txt`
- added (14, all P17-07R-scoped): `src/p17_device_frontier_assessment_v1.py`,
  `tools/test_phase17_device_frontier_assessment_v1.py`, and 12 files under `evidence/P17-07R/`

Independent assertions, all holding:
- **no Phase-1..16 path changed** — `git diff --name-only 2701415..b553f70` matched no frozen path
- **P17-06R evidence byte-untouched** — `git diff --stat 2701415 b553f70 -- .../evidence/P17-06R/` is empty; the committed `transcript.sha256` (`d7e222c8…5fd3a`) still matches `sha256(transcript.json)`
- **historical P17-04..P17-07 evidence not rewritten** — diff over those evidence directories is empty
- every added file is in P17-07R scope; nothing out-of-scope
- the frozen Phase-16 integrity module is untouched (0 phase16-path changes), so the legacy LF/CRLF
  native-manifest boundary is not altered by this candidate

## Independent dual official runs (controller, not the worker's)
Run 1: default private build root. Run 2: fresh isolated root
`private-build/phase17/P17-07R-controller-fresh-20260927T101409Z` via `OPENRECOMP_P17_PRIVATE_BUILD_ROOT`.
Plus a stage-runner pass (`--runs 2`) to regenerate the runner artifacts.

| Requirement | Result |
|---|---|
| exit code 0 | both runs, and runner |
| empty stderr | 0 bytes both runs |
| `P17-07R_CHECKS=93` | yes |
| zero `FAIL:` / `ERROR:` | 0 / 0 (93 `PASS:` lines) |
| stdout byte-identical run1 vs run2 | yes (`b876d450…f9fb66`) |
| stdout matches committed `run1.txt` | yes |
| generated evidence identical run-to-run | yes |
| generated evidence identical to **committed** | yes, full 12-file directory including `official_runs.json` and `determinism.json` |
| runner `runner_status` | `PASS` (artifacts/raw/lf identical, stderr empty, markers present) |

## Independent provenance re-derivation (REQ5)
Written by the controller **without** importing the candidate's `rederived_analysis()` helper, rebuilding
the record set from the read-only fixture with the frozen decoder:

- base record count **7001**
- per-region added records: `0x80026cc8` +3, `0x80011b08` +86, `0x80012e8c` +623, `0x8001a908` +627 — all match committed
- total **8340** = mainexe **1345** + title **6995**
- provenance digests **8340**; full region log structurally equal to the committed log
- poll owner `0x8001a9fc` present in the re-derived provenance map

*Controller note:* a first re-derivation attempt reported MISMATCH. That was a fault in the review
script, not the candidate — it compared `len(analysis.records_by_address)` (the full decoded address
map, 103424) instead of the contract metric `analysis.record_count` (8340). The provenance count matched
8340 even in the faulty run. Corrected against the contract's own metrics, the verdict is MATCH.

## Independent classification (REQ6)
Computed by the controller directly from `P17-06R/transcript.json`, then compared to the candidate
assessment: 1591 events = 1590 MMIO + 1 BIOS dispatch; MMIO classes `GPUSTAT_READ` 1587,
`INTERRUPT_ACCESS` 2, `TIMER_ACCESS` 1; GPUSTAT reads hit `0x1f801814` from 2 owners
(`0x8001a9fc` ×1586, `0x80016018` ×1); **zero** reads returned non-zero; zero `GP0_WRITE`/`GP1_WRITE`;
zero `DMA_ACCESS` events at all.

| Class | Required | Observed | Verdict |
|---|---|---|---|
| `gpu_wait_poll` | ENCOUNTERED | ENCOUNTERED, 1587 reads, dominant `0x8001a9fc`, all zero under `ZERO_FILL_RECORDED` | OK |
| `gpu_writes` | NOT_ENCOUNTERED | NOT_ENCOUNTERED | OK |
| `dma2` | NOT_ENCOUNTERED | NOT_ENCOUNTERED (no DMA access at `0x1f8010a8`) | OK |
| `framebuffer_activity` | NOT_ENCOUNTERED | NOT_ENCOUNTERED | OK |
| `ordering_table_writes` | NOT_ESTABLISHED | NOT_ESTABLISHED | OK |
| `ot_traversal` | NOT_ESTABLISHED | NOT_ESTABLISHED | OK |
| `initialization_predicates` | NOT_ESTABLISHED | NOT_ESTABLISHED | OK |

No `NOT_ESTABLISHED` class was promoted to `NOT_ENCOUNTERED`. The three RAM-store/BIOS-internal classes
stay explicitly undecided, which is the honest reading: the transcript does not instrument guest RAM
stores, so ordering-table writes cannot be observed in either direction.

## Independent tamper controls (REQ7)
Sixteen controller-authored cases, all fail-closed, zero fail-open: dropped event, emptied event list,
inflated `device_event_count`, stage spoofed to `P17-06`, unprovenanced event owner, a zero GPUSTAT read
flipped non-zero, wrong recorded `.sha` digest, missing transcript file, emptied frontier block,
`stop_reason` removed, `last_successfully_executed_pc` removed, continuation entry PC disagreeing with the
transcript, replaced transcript digest, disagreeing `device_event_count`, dropped poll owner from the
provenance map, and an emptied provenance map. The untampered control produces an assessment.

## Marker syntax (REQ8)
All 8 stage/claim markers are exactly `NAME=VALUE`. No `NAME=PASS=PASS` and no `NOT_PROVEN=PASS`
anywhere in the run output. The frozen-integrity line
`OPENRECOMP_PHASE17_P16_SOURCE_INTEGRITY=PASS entries=31 canonical=git-blob` carries trailing detail; it is
emitted by the pre-existing frozen module (not by the P17-07R gate, which only substring-asserts it) and
matches the accepted-stage convention — not a candidate-introduced malformation.

## Integrity re-checks (REQ9)
- canonical frozen Phase-16 integrity: `OPENRECOMP_PHASE17_P16_SOURCE_INTEGRITY=PASS entries=31 canonical=git-blob` (exit 0)
- Phase-17 source integrity: `OPENRECOMP_PHASE17_SOURCE_INTEGRITY=PASS entries=37` (exit 0)
- `sha256sum -c .openrecomp-phase17/SOURCE_SHA256SUMS.txt`: all entries OK
- `git diff --check 2701415 b553f70`: clean
- controller worktree clean before integration
- `LEGACY_PHASE16_NATIVE_GATE=PRE_EXISTING_FAIL` remains classified as pre-existing: the canonical marker
  independently passes and the candidate changes no Phase-16 path

## Defects found by the controller
**None.** Two defects were found and repaired by the worker during its own run, before this review, and
both repairs are visible in the diff and independently confirmed here: the transcript `kind` wire-format
mismatch (the module had compared against runtime-internal `KIND_*` integers instead of the serialized
strings), and a fail-open frontier validation that accepted an emptied `frontier` block (the worker's own
negative control caught it; the module was repaired fail-closed rather than the test relaxed).

## Accepted conclusion (bounded)
The current observed device frontier is **dominated by a zero-returning GPUSTAT polling loop**: 1586 of
1590 device events are repeated `GPUSTAT_READ` accesses to `0x1f801814` from a single instruction at
`0x8001a9fc`, every one returning zero under the declared `ZERO_FILL_RECORDED` model. Under that model
the guest cannot evaluate its poll exit condition, which is the binding constraint on the frontier.

This does **not** prove a rendered frame, does not establish GPU behaviour in general, and does not
advance any proof marker. It establishes a bounded, checked *negative* device frontier.

Proof boundaries preserved and re-verified in the candidate output:
`FIRST_FRAME_READY=NO`; initialization, frame, playability and general PS1 compatibility all `NOT_PROVEN`.

## Integration
Fast-forward only, `2701415223dd182a40cf257c849952a6ce63ee08` → `b553f70163fbd660252a3fcdaa77eee672af0f48`
(tree `90aa345018e541420acc558155927c5fde721f0e`), no merge commit, worktree clean. This review and the
corresponding metadata updates follow as a separate controller commit, matching the P17-05R closure pattern.

next_stage: **P17-90** (not started by this review).
