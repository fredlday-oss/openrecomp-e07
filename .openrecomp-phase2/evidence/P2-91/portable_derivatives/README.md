# Portable host-path derivatives (P2-91)

These files are **derivatives**, not replacements. They exist so that the
toolchain-detection metadata recorded by P2-07 and P2-08 is available in a
host-neutral form. The frozen originals remain the authoritative historical
evidence and are byte-pinned by the P2-91 closure gate.

| Derivative | Frozen original | Original SHA-256 | Transformation |
| --- | --- | --- | --- |
| `P2-07_native_compile.portable.txt` | `.openrecomp-phase2/evidence/P2-07/native_compile.txt` | `96f80ec6d271f5a282f345a5449f174ef702895365ddcca0c28b6f38f507b028` | detected compiler executable path replaced by `<host-compiler-path>` |
| `P2-08_determinism.portable.txt` | `.openrecomp-phase2/evidence/P2-08/determinism.txt` | `f5903884e47c8a9cd928bc075206046249efaea0155b2bfd5be164ea498e28b3` | detected compiler executable path replaced by `<host-compiler-path>` |

Notes:

- Both derivatives add a short header identifying the frozen original and the
  single transformation; all other bytes are preserved verbatim.
- No frozen evidence file was modified by P2-91.
- These derivatives contain no absolute local host path and are scanned by
  `tools/test_phase2_evidence_closure_v1.py` on every run.
