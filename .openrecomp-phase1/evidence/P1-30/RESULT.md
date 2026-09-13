# OPENRECOMP Phase 1 - P1-30 Evidence

## Architecture specification

NES 6502-family architectural state:
- A/X/Y/SP: i8 (signed 8-bit)
- PC: i16 (signed 16-bit)
- No architectural register pairs
- Flags: N=0x80 V=0x40 B=0x10 D=0x08 I=0x04 Z=0x02 C=0x01
- B flag has no storage (documented)

## Gate verification

### State gate
```
python tools/test_nes6502_state_v1.py
OPENRECOMP_NES6502_STATE_V1=PASS tests=10
```

### Decode gate
```
python tools/test_nes6502_decode_v1.py
OPENRECOMP_NES6502_DECODE_V1=PASS
```

## Harness results

```
python tools/phase1_host_gates_v1.py
OPENRECOMP_PHASE1_HOST_GATES_PASS=38 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
```

## Summary

NES 6502-family architectural state and decoder verified with all gates passing.
