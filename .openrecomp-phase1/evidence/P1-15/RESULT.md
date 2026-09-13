# P1-15 — Game Boy deterministic headless proof

VERDICT: `PASS`

## Source revision and working-tree state

- `HEAD = bd5f02fcd21cf42a3d1e24a67c9a285825462b76`, branch `main` (unchanged).
- Modified: `tools/sm83_frontend_v1.py`, `tools/sm83_reference_v1.py`,
  `tools/test_sm83_semantics_v1.py`, `tools/phase1_host_gates_v1.py`,
  `SOURCE_SHA256SUMS.txt` (regenerated with `update_sums.py`).
- Added: `tools/gb_platform_v1.py`, `tools/test_gb_headless_v1.py`.
- No commit created. No commercial ROM bytes were copied, embedded or
  committed; all CPU/platform fixtures are synthetic and original. The only
  commercial ROM involvement is metadata-only (filename, byte size, SHA-256,
  header fields, classifier output) per `ROM_PATHS.md`.

## Deliverables

| File | Role |
| --- | --- |
| `tools/gb_platform_v1.py` | bounded documented platform contract: ROM-only memory map (incl. WRAM echo), timer (DIV/TIMA/TMA/TAC), joypad (JOYP), interrupt contract (IE/IF/IME/vectors/priority/EI delay/RETI), HALT wake, platform-driven reference execution driver, entry-stub region extraction |
| `tools/test_gb_headless_v1.py` | 14-test deterministic gate `OPENRECOMP_GB_HEADLESS_V1=PASS` |

## Documented facts implemented (gbdev.io Pan Docs, fetched and quoted in tests)

- Interrupts: IE 0xFFFF / IF 0xFF0F (bits 0-4; unused bits read 1, writes
  masked); IME modified only by ei/di/reti/servicing; `ei` delayed by one
  instruction; servicing = IF bit acknowledged + IME=0 + PC pushed (like a
  call) + jump to the vector; priority bit 0 (VBlank) … bit 4 (Joypad);
  vectors 0x0040/0x0048/0x0050/0x0058/0x0060.
- HALT: wakes on `(IE & IF) != 0` regardless of IME; with IME=1 the handler
  is called before the instruction after the halt; with IME=0 execution
  resumes after the halt without servicing. The documented "halt bug" (halt
  executed with IME=0 while an interrupt is already pending) is **not
  modelled and fails closed**.
- Timer: DIV increments at 16384 Hz and any write resets it; TIMA increments
  at the TAC-selected rate (1024/16/64/256 T-cycles) when enabled (TAC bit
  2); overflow loads TMA and requests the timer interrupt (IF bit 2). TAC
  writes mask 0x07, unused bits read 1. Documented obscure timer behaviour
  (TAC-write increment, TIMA/DIV interplay) is out of scope and recorded.
- Joypad: JOYP bit 5 selects the button group and bit 4 the d-pad group
  (active low); the low nibble is read-only, pressed = 0; neither group
  selected reads 0xF; upper bits read 1.
- Memory map: ROM 0x0000-0x7FFF (ROM-only: 32 KiB; writes are documented
  no-effect bus writes), VRAM/OAM/HRAM plain memory, WRAM echo 0xE000-0xFDFF
  bidirectional, documented-unusable 0xFEA0-0xFEFF fails closed, cartridge
  RAM without a RAM mapper fails closed, unmodelled I/O (PPU/APU/serial,
  deferred) fails closed.

## Established-path repair recorded in this stage

`ld (a16), a` (0xEA) was executed as a 16-bit SP store by **both** the P1-12
reference and the P1-13 lowering (only `ld (a16), sp`/0x08 was handled). The
P1-12 coverage sweep never pinned 0xEA, so the two implementations agreed on
the wrong semantics. Fixed both to the documented 8-bit store and added three
new pins to `tools/test_sm83_semantics_v1.py`
(`ld-a16-a-store`, `ld-a16-a-store-no-clobber`, `ld-a-a16-load`); the P1-12
gate now reports 65 tests (was 62) and the P1-13 differential gate still
passes unchanged. No test was weakened or deleted.

## Verification

```text
python tools/test_gb_headless_v1.py
OPENRECOMP_GB_HEADLESS_V1=PASS tests=14

python tools/test_sm83_semantics_v1.py
OPENRECOMP_SM83_SEMANTICS_V1=PASS tests=65

python tools/test_sm83_lowering_v1.py
OPENRECOMP_SM83_LOWERING_V1=PASS tests=8

python tools/phase1_host_gates_v1.py
OPENRECOMP_PHASE1_HOST_GATES_PASS=27 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
```

Gate determinism: two runs of `test_gb_headless_v1.py` produce byte-identical
output (`sha256 = 7F611E0EAF7A3D525E2DD97819299CD439F6166C55559D1C7C8A5C96582CDD71`).

## Pinned deterministic results

Differential full chain (synthetic ROM-only boot ROM: documented header stub
`nop; jp $0150`, header data span 0x0104..0x014F, real program at 0x0150;
region [0x0100, 0x8000) with declared data span):

- reference == Core API: final CPU state, `platform:halted` and the full
  64 KiB guest memory identical;
- `a=0x07 f=0xc0 b=0x13 c=0x34 hl=0x1334 sp=0xff0c halted=1`,
  `mem[0xC000]=0x5A`, `mem[0xC002]=0x01`, `operations=594`, `blocks=7`.

Interrupt contract (platform-driven reference stepping, deterministic):

- EI delay: after `EI; NOP`, dispatch pushed PC=0x0160 (an immediate EI would
  have pushed 0x015F) — pinned via stack bytes `mem[0xFFFC]=0x60,
  mem[0xFFFD]=0x01`; ISR marker `mem[0xC800]=0x42`; IF acknowledged; RETI
  re-enables IME;
- priority: IE=IF=0x03 dispatches bit 0 first — both handlers write the same
  cell and the bit-1 handler's value (0x22) survives; both IF bits
  acknowledged; the second dispatch occurs immediately after the first RETI;
- HALT wake with IME=0: timer overflow wakes the CPU, execution resumes after
  the halt, IF is **not** cleared (pinned read 0xE4 at 0xFF0F);
- HALT wake with IME=1: handler called before the instruction after the halt
  (pushed PC=0x015D pinned via `mem[0xFFFC]=0x5D, mem[0xFFFD]=0x01`);
- halt bug (IME=0, interrupt already pending at halt execution): fails closed.

Timer contract: DIV +1 per 256 T-cycles and write-reset; TIMA gated by TAC
bit 2; select rates 1024/16 T-cycles; overflow -> TIMA=TMA and IF bit 2
(`read8(0xFF0F)=0xE4`).

Joypad contract: `0xFF` (neither selected), `0xEB` (d-pad selected, Right+Down),
`0xDE` (buttons selected, A), `0xCA` (both), low-nibble writes ignored.

Fail-closed rejections: non-documented entry stub, short ROM, tampered header
checksum, unsupported mapper (MBC5), cartridge-RAM access without a RAM
mapper, unusable-region access, unmodelled I/O access, overlapping /
out-of-region / region-start-inside / control-flow-target-inside data spans.

## Local-only ROM metadata evidence (never bytes)

`D:\OpenRecomp\roms\phase1\gameboy\primary\Super Mario Land 2 - 6 Golden
Coins (USA, Europe).gb`: `sha256=5450dce1bd0c073964c374b5b5b5729dce8d00f2e807892c34af32b8bce1392e`
(matches `ROM_INVENTORY.json`), 524288 bytes, title `MARIOLAND2`,
classifier `mapper=mbc1 cgb_mode=dmg rom_banks=32 ram_banks=1`,
header checksum valid. Header/metadata only.

## Semantic assumptions and boundaries

- Interrupt dispatch is a between-instructions platform-layer concern. The
  Core API path (whole-function execution) is proven for interrupt-free
  execution; the interrupt/timer/HALT contracts are proven by the
  deterministic platform driver stepping the independent P1-12 reference
  oracle (the only step-capable driver). This reconciles the P1-13 note:
  the IR writes `platform:ime` as the CPU's request and the platform driver
  applies the documented one-instruction EI delay.
- The EI-delay proof pins the pushed PC so an immediate-EI regression cannot
  pass silently.
- Unused register bits (JOYP 6-7, TAC 3-7, IF/IE 5-7) read 1 per the Pan Docs
  register diagrams; pinned in the platform tests.
- STOP is treated as HALT by the CPU reference (documented in P1-12); the
  documented DIV-reset-on-STOP is not modelled (limitation).
- Cycle counts are not modelled; timer advances are expressed in T-cycles
  (1 M-cycle = 4 T-cycles), the documented unit of the timer contract.
- PPU/APU/serial I/O remains deferred (SCOPE); unmodelled I/O fails closed.

## Remaining limitations

- MBC1 is the only banked mapper (P1-14); the local ROM is MBC1 and
  classifies cleanly but its execution is out of scope for P1-15.
- Halt bug, timer obscure behaviour: documented, fail closed / out of scope.
- GBC mode selection (0x80/0xC0) is classified in P1-14 and proven as a
  platform-mode selection in P1-16.

## Verdict

`PASS` — the full Game Boy chain (ROM ingestion -> documented memory mapping
-> SM83 frontend -> IR V1 -> Module Image V1 -> Core API) is pinned equal to
the independent reference oracle on identical final state and 64 KiB memory,
and the documented timer/joypad/interrupt/HALT platform contracts are pinned
by deterministic headless tests with fail-closed handling throughout.
