# P1-23 — Master System deterministic headless proof

VERDICT: `PASS`

## Source revision and working-tree state

- `HEAD = bd5f02fcd21cf42a3d1e24a67c9a285825462b76`, branch `main` (unchanged).
- No commit created. Synthetic ROMs only; no commercial bytes involved.

## Files changed

| File | Change |
| --- | --- |
| `tools/sms_headless_v1.py` | Added: `SmsReferenceZ80` (Z80 reference bridged to the P1-22 `SmsMachine` memory map + port decode), synthetic SMS ROM programs (mapper init via LDIR, VDP register/VRAM protocol, PSG latch, RAM + conditional branch; a two-bank paging program; a VDP status-read program), reference/Core-API runners. |
| `tools/test_sms_headless_v1.py` | Added: 6-test deterministic gate `OPENRECOMP_SMS_HEADLESS_V1=PASS` with the differential proof. |
| `tools/sms_platform_v1.py` | Added the flat `port_trace` surface (last-write view of the port space, the comparison surface for the Core API's flat port segment). P1-22 pins unchanged. |
| `tools/phase1_host_gates_v1.py` | Registered gate `sms-headless-v1` (area "master-system"). |
| `SOURCE_SHA256SUMS.txt` | Regenerated via `python update_sums.py`. |

## Proof structure

One synthetic 16 KiB SMS ROM (entry 0x0000, documented boot pattern:
DI; IM 1; SP=0xDFF0; mapper init table 00 00 01 02 LDIR-ed to
$fffc-$ffff; VDP register 1 = 0xE4 via the documented two-byte control
protocol; VRAM write address 0x0000 + 4 data-port writes; PSG latch/data
via port $7f; RAM store + readback; CP + conditional JR; HALT) runs twice:

1. through the machine-backed Z80 reference oracle;
2. through the P1-21 frontend -> normalized IR V1 -> Module Image V1 ->
   the architecture-neutral Core API `ReferenceExecutor`.

Required identical: all 20 CPU state slots (incl. shadow set, IX/IY/SP),
IFF1/IFF2/IM/halted, system RAM (excluding the control mirror window), the
$fffc-$ffff write-through mirror, the untouched ROM window, and the flat
256-byte port segment vs the machine's `port_trace`.

Platform protocol results are pinned on the reference side with the same
guest code: VDP VRAM[0..3] = 11 22 33 44, VDP register 1 = 0xE4, address
auto-increment to 4, PSG register 0 = 0x0F, mapper fffc=0 slots=[0,1,2],
RAM mirror (0xE000 == 0xC000).

Additional pins:
- guest-code slot-2 paging on a two-bank ROM (LD (0xFFFF),A -> bank 1
  marker read through the mapper; write-through mirror byte);
- guest-code VDP status read (VBlank flag returned, documented
  read-and-reset of the status flags, second-byte latch cleared);
- fail-closed guest ROM write (`LD (0x8000),A` raises
  `SMSPlatformError` under the documented write protect);
- determinism: reference run twice byte-identical, frontend IR/sidecar
  byte-identical across two converts, Core API state identical.

## Documented boundary (recorded in the module docstring)

The CPU frontend exposes I/O as a flat 256-byte port segment; the platform
port protocol (VDP two-byte control words, data-port buffer lag, PSG
latch, status read-and-reset) is applied by the platform layer
(`SmsMachine`), never by the CPU model. Interrupt dispatch is a
between-instructions platform concern and stays out of the proof (same
documented split as P1-15); the reference models DI/IM/RETN/IFF surfaces.

## Verification

```text
python tools/test_sms_headless_v1.py
OPENRECOMP_SMS_HEADLESS_V1=PASS tests=6
(differential: a=0x1 f=0x42 hl=0xc000 sp=0xdff0 b=0x1 im=1 halted=1)
(run twice: output sha256 60D6A42CC494FD1F543B8267B495A6514AFCCECD7984978CE59CD1C58CD81794)

python tools/sms_headless_v1.py
SMS_HEADLESS_REFERENCE_A=0x1 F=0x42 HL=0xc000 SP=0xdff0 B=0x1 IM=1 HALTED=1
SMS_HEADLESS_VRAM_0003=11223344
SMS_HEADLESS_VDP_REG1=0xe4
SMS_HEADLESS_PSG_REG0=0xf
SMS_HEADLESS_MAPPER_FFFC=0x0 SLOTS=[0, 1, 2]
OPENRECOMP_SMS_HEADLESS_REFERENCE=PASS
SMS_HEADLESS_PAGING_A=0x1 SLOT2=1
OPENRECOMP_SMS_HEADLESS_PAGING=PASS

python tools/phase1_host_gates_v1.py
OPENRECOMP_PHASE1_HOST_GATES_PASS=35 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
```

## Semantic assumptions / limitations

- VDP cycle timing, display rendering, audio synthesis, interrupt dispatch
  and the pause/NMI path remain deferred (documented); the VDP model is a
  deterministic register/VRAM/CRAM/latch surface.
- The differential compares the CPU-visible flat port bytes on the Core
  API side and the protocol results on the reference side; both are driven
  by identical guest code.
- `SmsReferenceZ80` keeps the decode stream in sync with the mapper
  (full re-materialization when a control register at $fff8-$ffff is
  written); instruction fetch always sees the current paging state.

## Next

P1-24 (Z80/SMS regression + differential audit), then P1-30..P1-35
(6502/NES), P1-90/91/99.
