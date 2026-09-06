# Codex Findings Reproduction

1. **Decode of instruction at 0x1008**: REPRODUCED. The instruction bytes `21 10 43 00` decode to `addu r2, r2, r3` (not `addu r3, r2, r3` as stated in the previous expectation).
2. **Actual final r2/r3 state from the canonical guest bytes**: REPRODUCED. Independent manual and oracle verification yields `r2=45` and `r3=8`.
3. **Current native result**: REPRODUCED.
4. **Current +20 → +30 mutation result**: REPRODUCED.
5. **Unsupported-opcode behavior**: REPRODUCED. The previous pipeline allowed unsupported instructions to fail with deep tracebacks or allowed them through if the frontend parser matched superficially.
6. **Malformed-ELF behavior**: REPRODUCED. 
7. **41-byte executable-region behavior**: REPRODUCED. Alignment checks were missing.
8. **Out-of-contract ORI acceptance**: REPRODUCED. The frontend previously accepted out-of-contract memory, logic, and branch instructions.
9. **Existing microtest weakness**: REPRODUCED. Microtests relied solely on process exit codes rather than asserting semantic machine states.
10. **Current provenance/build reproducibility**: REPRODUCED. Critical scratch scripts were absent, meaning native C compilation and ELF generation lacked tracked provenance.
