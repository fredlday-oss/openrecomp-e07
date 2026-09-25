# OpenRecomp Phase 17 Handoff

## Summary
Phase 17 initiates from the completed Phase-16 checkpoint (`a0c26e882ca65cfc84cbec78f7e787509a4992a3`), advancing the execution frontier from the authentic CD-ROM TITLE transition to a future TITLE overlay decoding and host-translation policy. `P17-00` establishes the control plane only.

## Invariants
1. Commit `a0c26e882ca65cfc84cbec78f7e787509a4992a3` is the immutable ancestor.
2. Phase-1 through Phase-16 files and evidence are frozen.
3. No guest binary bytes committed to Git.
4. TITLE payload remains `NOT_DECODED` at `P17-00`.
