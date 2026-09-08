# Verify OpenRecomp

If you are evaluating OpenRecomp's scope, legitimacy or technical claims, start with the [`Public Credibility & Evidence Pack V1`](docs/PUBLIC_CREDIBILITY_EVIDENCE_PACK_V1.md).

The shortest independent technical path is:

```bash
bash EXTERNAL_REPRO_V1.sh
```

on the supported Linux x86-64 reviewer environment. A successful run ends with:

```text
OPENRECOMP_EXTERNAL_REPRO_V1=PASS
```

The authoritative evidence labels and limitations are in [`docs/PROOF_STATUS.md`](docs/PROOF_STATUS.md). General MIPS32 support remains **CANDIDATE**; passing bounded synthetic MIPS32 fixtures is not a claim of arbitrary-binary, full-ISA, console or commercial-game compatibility.

Project development is human-led and may use AI/automated assistance, but generated output is not proof. See [`DEVELOPMENT_PROCESS.md`](DEVELOPMENT_PROCESS.md).
