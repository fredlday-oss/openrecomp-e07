# Phase 1 Scope — Multi-Architecture Proof

Phase 1 is complete when OpenRecomp proves reusable guest-architecture support across SM83, Z80, and 6502-family frontends plus bounded platform integration for Game Boy/Game Boy Color, Master System, and NES.

This is **not** a promise of cycle-perfect or universal commercial-game compatibility.

## Shared/core completion

Required:
- architecture-neutral frontend contract;
- architecture-neutral decoded-instruction representation or equivalent boundary;
- architecture-neutral CFG/basic-block handoff;
- architecture-neutral IR/lowering handoff;
- deterministic architecture test harness;
- existing PS2/R5900 regression behavior preserved;
- fail-closed unsupported-instruction handling.

## Game Boy / Game Boy Color

Required:
- SM83 register/flag model;
- complete documented base and CB-prefixed instruction decode;
- verified documented instruction semantics;
- branches/calls/returns/interrupt control-flow classification;
- OpenRecomp IR/lowering integration;
- GB ROM ingestion and memory-map contract;
- baseline no-MBC cartridge support and a clean mapper interface;
- bounded MBC1 support if evidence/tests are available;
- timer/interrupt/joypad contracts sufficient for deterministic headless tests;
- GBC mode/configuration separation sufficient to prove GB vs GBC platform selection;
- synthetic/open test ROM or equivalent deterministic CPU/platform trace proof.

Deferred from Phase 1 unless already easy and evidence-backed:
- cycle-perfect PPU/APU;
- exhaustive MBC family;
- broad game compatibility.

## Master System

Required:
- Z80 architectural frontend;
- documented instruction decoding/semantics required by the selected test corpus;
- interrupt/control-flow integration;
- ROM ingestion;
- baseline Sega banking/memory contract;
- I/O/VDP port abstraction sufficient for deterministic platform tests;
- synthetic/open test proof.

Deferred:
- cycle-perfect VDP/audio;
- exhaustive regional/peripheral quirks.

## NES

Required:
- 6502-family frontend matching the NES CPU's documented behavior;
- documented official opcode semantics required for proof;
- interrupt/reset/NMI control-flow integration;
- iNES/NES 2.0 ingestion boundary;
- NROM/Mapper 0 baseline and mapper interface;
- CPU-facing PPU/APU/controller register contracts sufficient for deterministic tests;
- synthetic/open test proof.

Deferred:
- exhaustive unofficial opcodes unless required by tests;
- large mapper library;
- cycle-perfect PPU/APU;
- broad game compatibility.

## Final Phase-1 verdict

Use exactly:

`OPENRECOMP_PHASE1_MULTIARCH_PROOF=PASS`

only if every required stage is passed and the final regression audit confirms existing functionality was not regressed.
