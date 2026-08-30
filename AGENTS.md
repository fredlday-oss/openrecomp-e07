# AGENTS.md — E07 V1.1
- Synthetic/original inputs only.
- Fail closed without traceback for malformed ELF/IR.
- IR schema and host contract are executable gates.
- Every guest memory access is bounds checked.
- Preserve PROVEN vs CANDIDATE.
- `direct_call_graph` means direct calls only; unresolved `jalr`/tail calls are separate.
- Verify `SOURCE_SHA256SUMS.txt` before execution; generated files use the per-run manifest.
- Never add proprietary/console assets, keys, firmware, SDK material or console-derived formats.
