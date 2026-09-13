# OPENRECOMP Phase 1 — P1-90 Evidence

Stage: `P1-90` — whole-project regression + architecture-boundary audit

Revision: working tree at HEAD `bd5f02f` (no commit created; additive untracked files).

## 1. Whole-project regression (authoritative manual run)

The full Phase-1 host harness was run twice on the same tree (manual run,
recorded by the operator; not re-run by the agent):

```text
RUN 1: EXIT=0  TIME=00:06:23.8981181
       OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
       OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
RUN 2: EXIT=0  TIME=00:06:21.1210213
       OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
       OPENRECOMP_PHASE1_HOST_GATES_V1=PASS

RUN1 SHA256: 3fbb23d3d0174a7efe381d70a1636987c4355e5b9837d67c8dcb3e158a67f594
RUN2 SHA256: 3fbb23d3d0174a7efe381d70a1636987c4355e5b9837d67c8dcb3e158a67f594

OPENRECOMP_P1_90_HARNESS_DETERMINISM=PASS
OPENRECOMP_P1_90_NO_RUN2_SIDE_EFFECTS=PASS
```

A repository-status snapshot taken immediately before Run 2 and immediately
after Run 2 compared with no differences (`Compare-Object`), proving the
harness has no side effects on the working tree.

The two skipped gates are the unchanged toolchain-gated
`e07-hardened-end-to-end` (`bash`+`clang`+`gcc`+`node`) and `external-repro-v1`
(`bash`+`clang`+`gcc`+`node`+POSIX) gates; `clang`/`gcc` are absent on this host
and a skip is never counted as a pass.

The established paths remain green inside the 44 passing gates:
`ir-v1-spec`, `core-api-v1`, `arch-harness-mips32-v1`,
`arch-harness-riscv32-v1`, `mips32-frontend-v1`, `mips32-expansion-v1-negative`,
`mips32-microtests-v1`, `mips32-causality-v1`, `mips32-equivalence-v1`
(the published RV32I/E07 and MIPS32 numbers are unchanged).

## 2. Architecture-boundary audit (read-only)

All checks are by inspection of the actual imports/uses; every command below is
read-only.

| Boundary rule | Result |
| --- | --- |
| Core API (`openrecomp/`) stays architecture-neutral | PASS — no reference to `sm83`/`z80`/`nes6502`/platform modules, and no platform terms (`ppu`/`apu`/`vdp`/`psg`/`mapper`/`oam`/`nametable`/`joypad`/`controller`) |
| Adapters do not depend on the Core API | PASS — no `openrecomp` import in `adapters/` |
| Adapters do not depend on platform/frontend code | PASS — `adapters/` imports neither platform nor frontend modules |
| MIPS32/R5900 does not depend on SM83/Z80/NES platform code | PASS — no cross-imports; no PS2/R5900 implementation exists in-tree (the established path is RV32I/E07 + MIPS32) |
| SM83 CPU semantics separate from GB/GBC platform | PASS — `adapters/sm83.py` imports only `.interface`; `tools/gb_platform_v1.py` builds on the CPU reference (platform → CPU, never the reverse) |
| Z80 CPU semantics separate from SMS platform | PASS — same pattern (`adapters/z80.py` vs `tools/sms_platform_v1.py`) |
| NES6502 CPU semantics separate from NES platform | PASS — `adapters/nes6502.py` imports only `.interface`; `tools/nes6502_frontend_v1.py` imports only `adapters.nes6502`; `tools/nes_rom_v1.py`/`nes_platform_v1.py`/`nes_headless_v1.py` import no adapter |
| No cross-architecture frontend imports | PASS — each frontend imports only its own adapter (`sm83_frontend_v1` → `adapters.sm83`; `z80_frontend_v1` → `adapters.z80`; `nes6502_frontend_v1` → `adapters.nes6502`); the only NES-chain mentions of other architectures are docstring citations |
| Platform memory-map/mapper/PPU/APU/controller behavior outside the Core API | PASS — platform behavior lives in `tools/*_platform_v1.py` and the headless harnesses, never in `openrecomp/` |
| Unsupported behavior remains fail-closed | PASS — every chain gate exercises fail-closed rejections (undocumented opcodes/mappers, malformed headers, disabled/expansion I/O, out-of-region targets, CHR-ROM writes, four-screen VRAM); all green in the 44/0/2 run |
| No commercial ROM bytes entered the repository | PASS — `git ls-files` contains no `.nes/.gb/.gbc/.sms/.rom/.bin/.iso/.sfc/.z64`; `public-safety-scan` and `public-safety-missing-file-test` pass; local ROMs are read for metadata/hashes only and remain outside version control |
| Existing RV32I/E07 + MIPS32 behavior remains passing | PASS — see §1 |

### Corrected NES6502 boundary (explicit)

```
adapters.nes6502.STATE_SLOTS = {
    'cpu:a': 'i8', 'cpu:x': 'i8', 'cpu:y': 'i8', 'cpu:sp': 'i8', 'cpu:pc': 'i16',
}
adapters.nes6502.REGISTER_PAIRS = ()
```

- A/X/Y/SP are 8-bit CPU state; PC is 16-bit.
- The stack effective address is `$0100 | SP` (verified in
  `tools/nes6502_frontend_v1.py` push/pop helpers: `0x0100 | zext(sp)`), matching
  the documented page-1 stack.
- `AX` is **not** an architectural register pair (`REGISTER_PAIRS == ()`); the
  P1-30 state test pins this.

## 3. Verdict

`PASS`
