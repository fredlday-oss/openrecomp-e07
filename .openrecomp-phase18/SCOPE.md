# OpenRecomp Phase 18 Scope

## Mission

Advance OpenRecomp autonomously from the frozen Phase-17 terminal authority
(tag `openrecomp-phase17-pass`, commit
`d7cc5d09eebde398ca6ff3f3dad8dd5841913b69`, tree
`ad3aa822e5a02905ebc25477f7b6c69d0bffa055`) toward mechanically defensible
PS1 first-frame evidence.

Phase 18 is **PS1 FIRST-FRAME / GPU EXECUTION FRONTIER V1**. Its purpose is not
merely to produce an image: it is to establish as much of the real causal chain
as the evidence supports:

```text
authenticated guest execution
  -> genuine title/device operations
  -> genuine GPU/DMA/VRAM effects
  -> deterministic display state
  -> first-frame evidence
```

## Non-Goals

- Producing a rendered image for its own sake.
- Hardcoding a GPUSTAT value or any title-specific constant solely to escape a
  polling loop.
- Promoting initialization, frame, playability or general PS1 compatibility
  without the contractually required causal links.
- Rewriting or promoting historical Phase-17 markers.
- Beginning Phase 19.
