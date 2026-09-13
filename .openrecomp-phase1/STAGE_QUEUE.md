# Phase 1 Stage Queue

Status vocabulary: `PENDING`, `ACTIVE`, `PASS`, `FAIL`, `BLOCKED`.

Execute in order unless a stage explicitly says otherwise.

| ID | Stage | Initial |
|---|---|---|
| P1-00 | Repository/baseline audit and deterministic verification inventory | PENDING |
| P1-01 | Extract/document architecture-neutral OpenRecomp frontend contract | PENDING |
| P1-02 | Multi-architecture core scaffolding without R5900 regression | PENDING |
| P1-03 | Shared architecture test/evidence harness | PENDING |
| P1-10 | SM83 architectural state: registers, flags, PC/SP | PENDING |
| P1-11 | SM83 base + CB decoder/classifier | PENDING |
| P1-12 | SM83 documented instruction semantics | PENDING |
| P1-13 | SM83 control flow + OpenRecomp IR/lowering | PENDING |
| P1-14 | Game Boy ROM ingestion + memory/platform contract | PENDING |
| P1-15 | Game Boy deterministic headless proof | PENDING |
| P1-16 | Game Boy Color bounded platform-mode proof | PENDING |
| P1-17 | SM83/GB/GBC regression + differential audit | PENDING |
| P1-20 | Z80 architectural state + decoder | PENDING |
| P1-21 | Z80 semantics + control flow + IR/lowering | PENDING |
| P1-22 | Master System ROM/banking/I-O platform contract | PENDING |
| P1-23 | Master System deterministic headless proof | PENDING |
| P1-24 | Z80/SMS regression + differential audit | PENDING |
| P1-30 | NES 6502-family architectural state + decoder | PENDING |
| P1-31 | NES 6502-family semantics + interrupts/control flow + IR/lowering | PENDING |
| P1-32 | NES ROM ingestion + NROM/mapper abstraction | PENDING |
| P1-33 | NES CPU-facing PPU/APU/controller contracts | PENDING |
| P1-34 | NES deterministic headless proof | PENDING |
| P1-35 | 6502/NES regression + differential audit | PENDING |
| P1-90 | Whole-project regression and architecture-boundary audit | PENDING |
| P1-91 | Phase-1 evidence index and limitations report | PENDING |
| P1-99 | Final Phase-1 verdict | PENDING |

## Stage execution contract

For each stage:
1. inspect existing implementation and tests first;
2. identify exact required evidence;
3. record pre-change baseline relevant to the area;
4. implement the smallest coherent change;
5. build/run focused tests;
6. run relevant existing regressions;
7. create/update evidence result;
8. update `STATE.md`;
9. continue to the next stage if PASS.

Do not mark a platform stage PASS from decoder coverage alone.
