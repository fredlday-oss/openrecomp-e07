# CODEX INDEPENDENT REVIEW

Review scope: primary Antigravity tree `D:\OpenRecomp\openrecomp-e07`, implementation commit `cb87b56e4a5ce13bb1bab0e6d140cb1e2af1a98a`, plus its untracked `artifacts/mips32_translation_v1/` evidence as observed on 2026-09-06. The primary tree was inspected read-only. Tests that produced files ran in a disposable copy, not in the primary tree.

## Verdict

CODEX_REVIEW_FAIL

`MIPS32_FIRST_TRANSLATION_GO` is not supported. The claimed reference, native result, equivalence result, and mutation result are numerically wrong for the submitted guest bytes. The translation path also emits tracebacks for malformed/unsupported inputs, silently ignores trailing executable bytes, accepts instructions outside its stated semantic contract, and lacks semantic microtests and reproducible host-execution evidence.

## Semantic Findings

1. **The claimed expected answer is wrong.** The word at guest address `0x1008` is `0x00431021`, which decodes as `addu r2,r2,r3`, not an instruction writing `r3`. The word at `0x1010` is `0x00401021`, which leaves `r2` unchanged because it adds `$zero`. The correct execution is:

   - `r2=7`, `r3=8`;
   - `addu r2,r2,r3` makes `r2=15`;
   - the write to `r0` is discarded;
   - `addu r2,r2,r0` leaves `r2=15`;
   - `beq r2,r3,+2` is not taken because `15 != 8`;
   - its delay slot makes `r2=25`;
   - fallthrough makes `r2=45`;
   - `jr r31` executes its `nop` delay slot and exits through the bounded return mapping.

   Thus the correct final state is at least `r2=45`, `r3=8`, `r0=0`, not `r2=37`, `r3=15` as stated in `REFERENCE_EXPECTATION.md:8-25` and `RESULT.md:43-56`.

2. **The generated IR and C reflect the actual guest bytes, not the claimed answer.** `ir.json` writes the `0x1008` sum to `gpr:r2`; `fixture_translated.c` then computes and exposes `45`. Independent native execution of that C returned `OBSERVED=45`, `r2=45`, `r3=8`, with 25 normalized operations. This is positive evidence for guest-to-host derivation, but it disproves the submitted equivalence verdict.

3. **`$zero` handling is correct for the fixture.** Reads are lowered to the constant zero and writes are omitted. The generated IR contains no `gpr:r0` state slot. The independent run retained `r0=0`.

4. **The used branch PC and delay-slot mapping is correct.** The branch at `0x1014` targets `PC+4+(2<<2)=0x1020`, its false continuation is `0x101c`, the comparison is captured before the delay instruction, and the delay instruction appears before the IR branch terminator. An independent taken-branch fixture also produced the mathematically expected native result `41`, confirming target and always-executed delay-slot behavior for this bounded `beq` form.

5. **Sign extension, zero extension, and 32-bit wrap are implemented correctly in the reused frontend/backend, but the submitted microtests do not prove them.** An independent ELF using `lui`, `ori`, and `addiu` produced native state `r2=0` after `0xffffffff+1`, `r3=0xffffffff` after `addiu ...,-1`, and `r4=65535` after `ori r4,r0,0xffff`.

6. **Decoder target arithmetic passed 32 independent formula checks.** Signed branch displacement and pseudo-direct jump target formulas agreed at ordinary and wrap-boundary addresses. However, `adapters.mips32.decode` accepts an instruction address of `0x100000000`; the adapter itself does not enforce its advertised 32-bit address width. The current ELF loader prevents that address from this path, so this is a boundary defect rather than the cause of the fixture failure.

7. **The new translator does not fail closed without traceback.** It has no exception boundary around ELF loading, JSON parsing, decoding, frontend conversion, or output. Both `INVALID_MAGIC.elf` and `SEGMENT_OUT_OF_FILE.elf` exited 1 with Python tracebacks. An unsupported opcode also exited 1 with a traceback from `adapters.mips32.DecodeError`. This violates `AGENTS.md` directly. See `tools/translate_mips32_elf_v1.py:20-23`, `:48`, and `:70-71`.

8. **Instruction-region framing is not closed.** `tools/translate_mips32_elf_v1.py:30-33` adds only complete four-byte words and silently discards one to three trailing executable bytes. An otherwise-valid ELF whose executable segment size was changed from 40 to 41 bytes translated successfully. Executable segment size/alignment must be rejected when it cannot represent complete MIPS32 instructions.

9. **The stated ISA contract is not enforced.** `MIPS32_SEMANTIC_CONTRACT.md:9-16` limits support to `addiu`, `addu`, `beq`, `jr`, and `nop`, but the translator delegates to the broader legacy vertical-slice frontend without an allowlist. An ELF containing `ori r2,r0,1; jr r31; nop` translated successfully even though `ori` is outside the stage contract. Conversely, the contract calls `jr` a jump-register instruction while the frontend only accepts `jr $ra` and lowers it to a structured return. The bounded contract must match the accepted surface exactly.

10. **The frontend is hard-wired to one synthetic function.** `tools/translate_mips32_elf_v1.py:35-45` declares only the entry address as `fixture_main`; it does not discover functions or represent general `jal` targets. Discontiguous executable regions become one range and are rejected as holes. That is acceptable only if explicitly stated and enforced as a very narrow single-function contract.

11. **Accepted memory instructions would not have correct ELF-backed memory.** The reused frontend accepts `lw`/`sw`, but the new path emits an empty `memory_segments` sidecar and the loader exposes only executable regions. Loads from ELF PT_LOAD data, or from bytes in the executable segment, would observe zero rather than the loaded image. This is another reason the stage must enforce its claimed no-memory allowlist.

## Test Findings

| Check | Independent result |
| --- | --- |
| Repository-supplied microtests | Printed `10 passed, 0 failed`, but checked only translator acceptance/rejection; no state or native behavior was asserted. |
| Baseline fixture byte decode | `r2=45`, `r3=8`, 10 MIPS instructions, 2 executed delay slots. |
| Generated baseline C, clang-cl `/W4 /WX`, native DLL | Build PASS; `openrecomp_run=1`, observed `45`, `r2=45`, `r3=8`, operations `25`. |
| Submitted `+20 -> +30` mutation C | Build PASS; observed `55`, not claimed `47`. |
| Independent `+20 -> +21` causality mutation | ELF hash and generated C changed; native result changed `45 -> 46`. |
| Independent integer-semantics ELF | Native `r2=0`, `r3=4294967295`, `r4=65535`; wrap/sign/zero extension PASS for exercised forms. |
| Independent taken-`beq` delay-slot ELF | Native observed result `41`; target calculation and executed delay slot PASS. |
| Malformed ELF through new translator | Rejected, but with traceback and exit 1: FAIL against fail-closed/no-traceback requirement. |
| Unsupported opcode through new translator | Rejected, but with traceback and exit 1: FAIL against fail-closed/no-traceback requirement. |
| 41-byte executable region | Accepted while the trailing byte was ignored: FAIL. |
| Out-of-contract `ori` | Accepted and lowered: FAIL against the submitted semantic contract. |
| Existing MIPS frontend tests | 7/7 PASS in disposable canonical snapshot. |
| Existing MIPS expansion tests | 7/7 negative/decoder checks PASS. |
| Existing MIPS ELF ingestion corpus | 2 valid accepts plus 12 invalid fail-closed rejections, 14/14 PASS. |
| IR V1 tests | 15/15 PASS. |
| Core API tests | 5/5 PASS. |
| RV32I live regression | Synthetic RV32I ELF built and converted; adversarial corpus PASS; translated native host returned established checksum `122010428`. |
| New translator determinism | Two runs produced identical IR, sidecar, and trace hashes. Behavior is deterministic for this input, although the supplied `DETERMINISM.md` records only one hash per output and is not itself a repeat-run proof. |

The new microtests are not semantic tests. `tools/test_mips32_microtests_v1.py:74-89` treats return code zero as sufficient for every positive case and never packages, compiles, executes, or examines IR values. In addition:

- `addiu_wrap` starts with `r2=0`, so it translates `0+1`, not a wrap case (`:24`, `:46`);
- `addu_norm` adds two zero-initialized registers (`:25`, `:46`);
- both named branch cases are taken because all registers start at zero; the supposed not-taken case compares `r0` with zero-initialized `r2` (`:27-28`, `:46`);
- `zero_write` never observes the register after the write (`:30`);
- sign extension is accepted syntactically but no resulting value is asserted.

## Causality Review

The submitted mutation is a real semantic mutation: byte offset 112 changes from `0x14` to `0x1e`, changing the instruction at `0x101c` from `addiu r2,r2,20` to `addiu r2,r2,30`. The generated C changes only the corresponding operand from 20 to 30. Therefore the guest-to-host causal chain exists.

The reported causality outcome is nevertheless false. Correct native results are `45 -> 55`, not `37 -> 47` as claimed in `RESULT.md:58-64`. No reusable mutation test or result log is committed; only two unbound executable files and generated sources were present as untracked artifacts. An independent one-unit mutation produced `45 -> 46`, confirming causality without rescuing the incorrect submitted verdict.

## Equivalence Review

`EQUIVALENCE_PASS` fails. The manually derived oracle is independent in method but incorrect in content, and the stage checker never compares it to translated execution. The authoritative byte-level derivation and independent native execution agree on 45, while the submitted documents claim 37.

The final generated host C is genuine static native code and contains no MIPS interpreter loop and no literal expected value 37/47. No emulator was found in the final mechanism. This satisfies two important architectural concerns for the generated C itself.

The submitted `.exe` evidence is not reproducibly bound to that C:

- `PROVENANCE.md:9-13` refers to absent `scratch/build_fixture.py` and `scratch/build_c.py` scripts;
- `TRANSLATION_ARCHITECTURE.md:4,12` says `aot_sanitizer_driver_v1.c` was used, but that harness requires `OPENRECOMP_EXPECTED_STATE` and requires `openrecomp_function_has_return()` to be true;
- the generated MIPS IR has `return_type: null`, and generated C leaves `g_entry_has_return=0`, so that stated harness would fail even for the correct observed state;
- the PE files have no exports, are absent from any per-run manifest, and the documented command exposes only process exit status. A claimed exit status of zero cannot also establish an observable value of 37 without preserved harness output or another observation channel.

Therefore “interpreter used: NO” is supported for the inspected C, while “native observable result: 37”, “hard-coded expected result: NO” for the unbound PE, and use of the named harness are not established.

## Regression Review

No MIPS32 ingestion or RV32I semantic regression was observed in independent live checks. The implementation commit adds two files and does not edit the existing loader, frontend, IR, AOT backend, or RV32I path. Existing MIPS frontend/expansion tests, the MIPS ingestion corpus, IR/Core tests, the RV32I adversarial corpus, and RV32I native checksum all passed in the disposable review snapshot.

That positive result does not validate the new stage's claimed regression evidence: `RESULT.md:72-78` contains only bare `PASS` labels, with no commands, logs, tool versions, or per-run manifest. The new test is not wired into a tracked CI workflow.

Source-integrity handling also regressed operationally on Windows. Literal verification of `SOURCE_SHA256SUMS.txt` fails because checked-out `tools/wasm_run.js` has CRLF bytes while the manifest records the LF blob. After canonical LF normalization, the old manifest verifies, but it covers only 22 files while 71 relevant tracked source/schema/contract files exist; neither new translation tool is covered. No full per-run manifest covers the generated translation artifacts.

## Suspicious / Unproven Claims

- `RESULT.md:19,60` and `PROVENANCE.md:10` give original fixture hash `0f1dc4...`, but the actual ELF, IR provenance, and `fixture_manifest.json` give `c9b60aa0df3f95d7d35bbae92c2a99ccc65646bfb3ee44e7c3fc546146ee6e88`.
- `RESULT.md:43-64` claims original/native/equivalence/causality values `37` and `47`; independent native results are `45` and `55`.
- `RESULT.md:86-87` says fetch bounds, wrapping, sign extension, termination, and unsupported handling were checked with no follow-up. The supplied tests do not assert these semantics, trailing executable bytes are accepted, and error paths expose tracebacks.
- `RESULT.md:68-70,93` calls the microtests semantic correctness evidence. They only assert process acceptance.
- `DETERMINISM.md` labels two single hashes as `DETERMINISM_PASS`; it contains no second-run records or executable hash.
- `PROVENANCE.md` is not reproducible: build scripts are absent, the toolchain version is not exact, generated outputs lack a per-run manifest, and the artifact files were untracked at the stated final commit. The final commit contains only the translator and weak microtest.
- `REFERENCE_EXPECTATION.md` contains corrupted Markdown/control characters and missing register names, in addition to the wrong decode.
- `module.json` is actually the execution sidecar, while `packaged_module.json` is the Module Image V1 object. The naming and evidence list obscure which executable gate was applied.

## Required Fixes

1. Correct the fixture decode and independent reference. For the current bytes, establish `r2=45`, `r3=8`; for the current `+30` mutation establish `55`. Alternatively change the guest words to match a newly derived oracle, then regenerate every downstream artifact.
2. Add an executable independent MIPS32 oracle/checker that does not consume generated IR or generated C. Compare complete state, delay-slot count, selected memory, and termination against native AOT output.
3. Replace acceptance-only microtests with end-to-end assertions for positive/negative immediates, zero extension, wraparound, `$zero` reads/writes, taken and not-taken branches, branch/jump targets, delay slots, `jr $ra`, unsupported encodings, malformed ELF, and instruction-fetch boundaries.
4. Add a top-level exception boundary to `translate_mips32_elf_v1.py` and emit a stable concise failure message with exit 2 and no traceback for expected ELF/JSON/decode/frontend/schema/IO failures.
5. Reject any executable region or entry address that is not four-byte aligned and reject trailing partial instruction bytes. Enforce 32-bit addresses at the adapter boundary.
6. Enforce an explicit ISA allowlist matching `MIPS32_SEMANTIC_CONTRACT.md`, or broaden the contract and add semantic evidence for every accepted operation. State explicitly that only `jr $ra` is supported. Do not accept `lw`/`sw` until ELF memory-image mapping is correct.
7. Preserve and track the exact host harness/build scripts. Bind ELF, IR, sidecar, packaged module, generated C, harness source, compiler identity/flags, native binary, and result log in a per-run SHA-256 manifest. Ensure the harness checks observed state rather than requiring a nonexistent IR function return.
8. Fix the original fixture hash and all provenance text. Remove the corrupted reference Markdown and record exact toolchain versions and commands that exist in the repository.
9. Update the source-integrity manifest to cover the new pipeline and fix `.js` line-ending policy so exact verification succeeds on supported Windows checkouts.
10. Wire the semantic, causality, ingestion, IR/Core, and RV32I regressions into a tracked clean-checkout gate. Do not promote the stage based on generated artifacts that remain untracked.

## Recommendation

Do not accept `MIPS32_FIRST_TRANSLATION_GO`. Keep the stage **CANDIDATE / NO-GO** until the oracle and native results agree, fail-closed behavior is restored, the accepted ISA and fetch boundaries are enforced, semantic tests replace acceptance tests, and the full native evidence chain is reproducible and hash-bound.
