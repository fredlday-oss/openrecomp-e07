# OpenRecomp Development Update — 2 October 2026

## Expanding the multi-architecture recompilation framework

OpenRecomp is progressing beyond its original PlayStation-focused research into additional 8-bit and 16-bit home-computer platforms. Recent local experiments have exercised Z80, 6510 and Motorola 68000 translation and runtime paths, alongside the existing RV32I and MIPS32 work.

This is a **development update**, not a new release or a claim of general compatibility. The title-specific results below describe reported, bounded local experiments. They do not automatically extend the repository's published v0.2.0 proofs or establish support for other titles on the same systems.

## Recent experiment milestones

| System / architecture | Current bounded result | Remaining boundary |
| --- | --- | --- |
| **ZX Spectrum / Z80** | *Manic Miner* has been recompiled into a native Windows application using SDL3; all 20 caverns have been individually validated. | A complete uninterrupted playthrough and general ZX Spectrum compatibility are not established. |
| **Commodore 64 / 6510** | *Double Dragon* has reached its combat-engine execution path using a hybrid of native and interpreted execution; the reported run covered 688,582 instructions and 54 validation gates. | Continuous gameplay, full native execution and general C64 compatibility are not proven. |
| **Amiga / Motorola 68000** | Initial P-00–P-99 experiment milestones are complete, demonstrating the 68000-to-native-Windows translation pipeline and basic platform infrastructure. *Batman: The Movie* is the next title under evaluation. | Full graphics, audio and commercial-title playability remain unproven. |
| **PlayStation / MIPS family** | Ongoing bounded work on executable ingestion, control flow, BIOS/runtime behaviour and hardware execution frontiers. | First-frame readiness, complete commercial-title playability and general PS1 compatibility remain unproven. |
| **NES / 6502 family** | Bounded translation and validation foundations. | Full platform runtime and general game compatibility are not established. |
| **Game Boy / SM83** | Experimental CPU foundation. | Complete system runtime and commercial-game compatibility are not established. |

The repository's published [technical status](../TECHNICAL_STATUS.md), [platform boundaries](../PLATFORMS.md) and [evidence model](../EVIDENCE_MODEL.md) remain the authority for *publicly reproducible* claims. Further experiment-specific artifacts and reproduction instructions will be published separately when they are ready for external review.

## What carries across platforms

The objective is to reuse infrastructure without conflating CPU support with whole-system support:

- Architecture-specific decoding and semantic translation feed the common IR/module pipeline where implemented.
- Native code generation is paired with explicit runtime and host-service interfaces.
- Deterministic gates, reproducibility checks and fail-closed handling make unresolved behaviour visible.
- Graphics, audio, memory mapping, timing, input and platform services still require system-specific implementation and validation.

A passing gate proves only its stated contract. A single-title demonstration is not evidence that an entire console or software library works.

## Potential next targets

We are exploring the **Sega Master System**, **Game Gear** and **Mega Drive / Genesis** as possible subsequent platforms. They offer opportunities to reuse the existing Z80 and Motorola 68000 work while testing additional video, audio and multi-processor runtime behaviour. These are **proposed targets**, not implemented or committed compatibility milestones.

## Near-term priorities

1. Continue the PlayStation execution and playability investigation without weakening its existing assurance boundaries.
2. Consolidate reproducible evidence and documentation for the newer home-computer experiments.
3. Demonstrate complete, independently validated title-specific execution paths before broadening platform claims.
4. Keep core translation reusable and isolate system-specific hardware services.

OpenRecomp remains an open-source research and development framework, not a universal game recompiler. Commercial game binaries, firmware, keys and proprietary assets are not distributed in this repository; any title-specific experiments require appropriately obtained software.

— Fred Day, OpenRecomp
