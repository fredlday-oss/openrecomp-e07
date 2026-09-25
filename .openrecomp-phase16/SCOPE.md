# OpenRecomp Phase 16 Scope

## Mission

Advance OpenRecomp autonomously from the frozen Phase-15 terminal checkpoint
(`5cec005d45e8361e5ea132731661b13a72a5ed13`) to establish:

1. Authentic CD-ROM sector delivery required by the Hercules TITLE overlay load path.
2. Exact machine-readable reconstruction of the `A0:0x43 Exec` contract.
3. Authentic TITLE overlay executable mapping from the private disc image.
4. Clean, deterministic control transfer across the `A0:0x43 Exec` boundary into the TITLE overlay at `0x800380A0`.
5. Controlled causality ablation proving that execution depends on authentic CD delivery.
6. Bounded deterministic replay of early TITLE execution.
7. Measurement and classification of the first post-TITLE semantic frontier (GPU commands, OT initialization, DMA2).

## Non-Goals

- Making the commercial game fully playable or interactive.
- Implementing speculative CD-ROM controller hardware beyond what the reached fixture executes.
- Implementing generic CPU interrupts or asynchronous IRQ delivery without live evidence.
- Promoting `FIRST_FRAME_READY=YES` or frame proof without fulfilling the explicit frame proof contract.
- Fabricating guest payloads or preloading RAM outside the authentic CD-ROM loader path.
