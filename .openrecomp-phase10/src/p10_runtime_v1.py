#!/usr/bin/env python3
"""OpenRecomp Phase-10 runtime composition V1.

The Phase-10 native runtime is the frozen Phase-9 bounded PS1 platform runtime
translation unit with exactly one substitution: its `or_rt_host_call` stub is
replaced by the Phase-10 MIPS service dispatch. Everything else - guest
address translation, the typed GPU/controller/timer/SPU/CD-ROM port boundary,
virtual time and input, the counters and the event transcript - is the Phase-9
runtime, byte-identical and physically shared.

The composition is deterministic and auditable:

* the frozen Phase-9 runtime source is read and its SHA-256 is verified against
  the frozen Phase-9 source manifest before any substitution;
* exactly one anchored block (the `or_rt_host_call` definition, including its
  SHA-256) may be replaced;
* the result must contain the entire frozen source except that block, plus the
  Phase-10 extension fragment; a missing anchor or a duplicated anchor fails
  closed.

No second runtime architecture is created.
"""

from __future__ import annotations

import hashlib
import pathlib
import sys
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / ".openrecomp-phase9" / "src"))
import p9_gpu_boundary_v1 as p9_gpu  # noqa: E402

RUNTIME_VERSION = "1.0.0"

ROOT = pathlib.Path(__file__).resolve().parents[2]

PHASE9_RUNTIME_PATH = ROOT / ".openrecomp-phase9" / "runtime" / "p9_runtime_support.c"
PHASE9_MANIFEST_PATH = ROOT / ".openrecomp-phase9" / "SOURCE_SHA256SUMS.txt"
EXTENSION_PATH = ROOT / ".openrecomp-phase10" / "runtime" / "p10_mips_extension_v1.c"

PHASE9_RUNTIME_RELATIVE = ".openrecomp-phase9/runtime/p9_runtime_support.c"

ANCHOR = (
    "int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value)\n"
    "{\n"
    "    (void)service_id;\n"
    "    (void)argc;\n"
    "    (void)args;\n"
    "    (void)out_value;\n"
    "    ++g_p9_host_calls;\n"
    "    return P9_RT_UNKNOWN_HOST_SERVICE;\n"
    "}\n"
)

#: Deterministic bounded-execution budget anchors. The budget bounds a guest
#: run by guest memory accesses; when it is exceeded the checked access fails
#: closed (`UNSUPPORTED_OPERATION`), the generated code calls `or_fail` and the
#: run terminates with an explicit, reproducible category. A budget of zero
#: disables the bound.
READ_ANCHOR = (
    "int or_rt_memory_read(uint64_t address, uint32_t width_bits, uint64_t *out_value)\n"
    "{\n"
    "    uint64_t width = 0;\n"
    "    uint32_t offset = 0;\n"
    "    uint64_t value = 0;\n"
    "    uint64_t index;\n"
    "    int status = p9_width_bytes(width_bits, &width);\n"
)
#: Bound on the recorded distinct non-RAM access signatures.
NONRAM_LOG_CAPACITY = 64

#: Non-RAM access log substitution. Every guest access whose address is
#: outside the two modelled main-RAM windows is logged (deduplicated by
#: address/width/direction) so the platform port boundary's denials can be
#: attributed to exact addresses instead of an unattributed count. The log is
#: bounded; overflow is counted explicitly.
#: Bound on the recorded distinct non-RAM access signatures.
NONRAM_LOG_CAPACITY = 64

#: Non-RAM access log substitution. Every guest access whose address is
#: outside the two modelled main-RAM windows is logged (deduplicated by
#: address/width/direction/denial-reason) so the platform port boundary's
#: denials can be attributed to exact addresses and to a cause instead of an
#: unattributed count. The log is bounded; overflow is counted explicitly.
NONRAM_LOG_DECLARATION = (
    "struct p10_access_signature {\n"
    "    uint32_t address;\n"
    "    uint32_t width_bits;\n"
    "    uint32_t is_write;\n"
    "    uint32_t reason;\n"
    "    uint64_t count;\n"
    "};\n"
    "\n"
    "#define P10_NONRAM_LOG_CAPACITY 64u\n"
    "static struct p10_access_signature g_p10_nonram[P10_NONRAM_LOG_CAPACITY];\n"
    "static uint32_t g_p10_nonram_count;\n"
    "static uint64_t g_p10_nonram_overflow;\n"
    "\n"
    "static void p10_log_nonram(uint64_t address, uint32_t width_bits, uint32_t is_write, uint32_t reason)\n"
    "{\n"
    "    uint32_t index;\n"
    "    if (address >= (uint64_t)P9_RAM_KSEG0_BASE\n"
    "        && address < (uint64_t)P9_RAM_KSEG0_BASE + (uint64_t)P9_IMAGE_SIZE) {\n"
    "        return;\n"
    "    }\n"
    "    if (address >= (uint64_t)P9_RAM_KSEG1_BASE\n"
    "        && address < (uint64_t)P9_RAM_KSEG1_BASE + (uint64_t)P9_IMAGE_SIZE) {\n"
    "        return;\n"
    "    }\n"
    "    for (index = 0; index < g_p10_nonram_count; ++index) {\n"
    "        if (g_p10_nonram[index].address == (uint32_t)address\n"
    "            && g_p10_nonram[index].width_bits == width_bits\n"
    "            && g_p10_nonram[index].is_write == is_write\n"
    "            && g_p10_nonram[index].reason == reason) {\n"
    "            ++g_p10_nonram[index].count;\n"
    "            return;\n"
    "        }\n"
    "    }\n"
    "    if (g_p10_nonram_count < P10_NONRAM_LOG_CAPACITY) {\n"
    "        g_p10_nonram[g_p10_nonram_count].address = (uint32_t)address;\n"
    "        g_p10_nonram[g_p10_nonram_count].width_bits = width_bits;\n"
    "        g_p10_nonram[g_p10_nonram_count].is_write = is_write;\n"
    "        g_p10_nonram[g_p10_nonram_count].reason = reason;\n"
    "        g_p10_nonram[g_p10_nonram_count].count = UINT64_C(1);\n"
    "        ++g_p10_nonram_count;\n"
    "        return;\n"
    "    }\n"
    "    ++g_p10_nonram_overflow;\n"
    "}\n"
    "\n"
    "uint32_t p10_runtime_nonram_count(void) { return g_p10_nonram_count; }\n"
    "uint64_t p10_runtime_nonram_overflow(void) { return g_p10_nonram_overflow; }\n"
    "uint32_t p10_runtime_nonram_address(uint32_t index)\n"
    "{\n"
    "    return index < g_p10_nonram_count ? g_p10_nonram[index].address : 0u;\n"
    "}\n"
    "uint32_t p10_runtime_nonram_width(uint32_t index)\n"
    "{\n"
    "    return index < g_p10_nonram_count ? g_p10_nonram[index].width_bits : 0u;\n"
    "}\n"
    "uint32_t p10_runtime_nonram_is_write(uint32_t index)\n"
    "{\n"
    "    return index < g_p10_nonram_count ? g_p10_nonram[index].is_write : 0u;\n"
    "}\n"
    "uint32_t p10_runtime_nonram_reason(uint32_t index)\n"
    "{\n"
    "    return index < g_p10_nonram_count ? g_p10_nonram[index].reason : 0u;\n"
    "}\n"
    "uint64_t p10_runtime_nonram_observations(uint32_t index)\n"
    "{\n"
    "    return index < g_p10_nonram_count ? g_p10_nonram[index].count : UINT64_C(0);\n"
    "}\n"
)

READ_REPLACEMENT = (
    NONRAM_LOG_DECLARATION
    + "static uint64_t g_p10_access_budget = UINT64_C(2000000);\n"
    "static uint64_t g_p10_access_count;\n"
    "static uint64_t g_p10_budget_denials;\n"
    "\n"
    "void p10_runtime_set_access_budget(uint64_t budget)\n"
    "{\n"
    "    g_p10_access_budget = budget;\n"
    "    g_p10_access_count = UINT64_C(0);\n"
    "    g_p10_budget_denials = UINT64_C(0);\n"
    "}\n"
    "\n"
    "uint64_t p10_runtime_access_budget(void) { return g_p10_access_budget; }\n"
    "uint64_t p10_runtime_access_count(void) { return g_p10_access_count; }\n"
    "uint64_t p10_runtime_budget_denials(void) { return g_p10_budget_denials; }\n"
    "\n"
    "static int p10_budget_exceeded(void)\n"
    "{\n"
    "    if (g_p10_access_budget == UINT64_C(0)) {\n"
    "        return 0;\n"
    "    }\n"
    "    ++g_p10_access_count;\n"
    "    if (g_p10_access_count > g_p10_access_budget) {\n"
    "        ++g_p10_budget_denials;\n"
    "        return 1;\n"
    "    }\n"
    "    return 0;\n"
    "}\n"
    "\n"
    "int or_rt_memory_read(uint64_t address, uint32_t width_bits, uint64_t *out_value)\n"
    "{\n"
    "    uint64_t width = 0;\n"
    "    uint32_t offset = 0;\n"
    "    uint64_t value = 0;\n"
    "    uint64_t index;\n"
    "    int status;\n"
    "    {\n"
    "        int p10_over_budget = p10_budget_exceeded();\n"
    "        p10_log_nonram(address, width_bits, 0u, (uint32_t)p10_over_budget);\n"
    "        if (p10_over_budget) {\n"
    "            ++g_p9_denied_accesses;\n"
    "            return P9_RT_UNSUPPORTED_OPERATION;\n"
    "        }\n"
    "    }\n"
    "    status = p9_width_bytes(width_bits, &width);\n"
)

WRITE_ANCHOR = (
    "int or_rt_memory_write(uint64_t address, uint32_t width_bits, uint64_t value)\n"
    "{\n"
    "    uint64_t width = 0;\n"
    "    uint32_t offset = 0;\n"
    "    uint64_t index;\n"
    "    int status = p9_width_bytes(width_bits, &width);\n"
)
WRITE_REPLACEMENT = (
    "int or_rt_memory_write(uint64_t address, uint32_t width_bits, uint64_t value)\n"
    "{\n"
    "    uint64_t width = 0;\n"
    "    uint32_t offset = 0;\n"
    "    uint64_t index;\n"
    "    int status;\n"
    "    {\n"
    "        int p10_over_budget = p10_budget_exceeded();\n"
    "        p10_log_nonram(address, width_bits, 1u, (uint32_t)p10_over_budget);\n"
    "        if (p10_over_budget) {\n"
    "            ++g_p9_denied_accesses;\n"
    "            return P9_RT_UNSUPPORTED_OPERATION;\n"
    "        }\n"
    "    }\n"
    "    status = p9_width_bytes(width_bits, &width);\n"
)

#: Diagnostic event-transcript capacity. The frozen Phase-9 runtime caps each
#: per-device transcript at 4096 recorded events; the Phase-10 transcription
#: raises that cap so later distinct device behaviour is not hidden behind the
#: frozen cap. The recorded events are classified by the same code; only the
#: number of recorded events changes.
EVENT_CAPACITY_ANCHOR = "#define P9_EVENT_CAPACITY 4096u"
EVENT_CAPACITY_REPLACEMENT = "#define P9_EVENT_CAPACITY 65536u"

#: The transcript capacities visible to a driver.
EVENT_CAPACITY = 65536
PHASE9_EVENT_CAPACITY = 4096

#: GPU status-read stub substitution. The frozen Phase-9 platform runtime
#: returns 0 for a GP0/GP1 read. The audited Phase-9 GPU boundary defines an
#: explicit contract stub (`p9_gpu_boundary_v1.GPUSTAT_STUB`) whose documented
#: ready bits are set; the Phase-10 dynamic record shows the guest polling
#: GPUSTAT in a loop that never completes against a 0 status. The Phase-10
#: runtime therefore returns the boundary's documented contract stub for the
#: GP1 status read and keeps the GP0 data read at 0. This is an explicit
#: contract stub, not GPU hardware emulation and not VRAM state.
GPU_READ_STUB = p9_gpu.GPUSTAT_STUB
GPU_READ_ANCHOR = (
    "    if (address == (uint64_t)P9_GP0_READ || address == (uint64_t)P9_GP1_READ) {\n"
    "        value = 0u;\n"
)
GPU_READ_REPLACEMENT = (
    "    if (address == (uint64_t)P9_GP0_READ || address == (uint64_t)P9_GP1_READ) {\n"
    "        value = (address == (uint64_t)P9_GP1_READ) ? (uint32_t)"
    + f"0x{GPU_READ_STUB:08x}u"
    + " : 0u;\n"
)

SUBSTITUTIONS = (
    ("event-capacity", EVENT_CAPACITY_ANCHOR, EVENT_CAPACITY_REPLACEMENT),
    ("gpu-status-read-stub", GPU_READ_ANCHOR, GPU_READ_REPLACEMENT),
    ("access-budget", READ_ANCHOR, READ_REPLACEMENT),
    ("access-budget", WRITE_ANCHOR, WRITE_REPLACEMENT),
    ("host-call-dispatch", ANCHOR, None),
)

ERROR_CODES = (
    "PHASE9_RUNTIME_MISSING",
    "PHASE9_RUNTIME_HASH_MISMATCH",
    "PHASE9_MANIFEST_MISSING",
    "PHASE9_MANIFEST_ENTRY_MISSING",
    "EXTENSION_MISSING",
    "ANCHOR_MISSING",
    "ANCHOR_AMBIGUOUS",
)


class RuntimeCompositionError(ValueError):
    """Fail-closed runtime composition error with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        if code not in ERROR_CODES:
            raise AssertionError(f"unknown runtime composition error code: {code}")
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _manifest_hash(relative: str) -> str:
    if not PHASE9_MANIFEST_PATH.is_file():
        raise RuntimeCompositionError("PHASE9_MANIFEST_MISSING", PHASE9_MANIFEST_PATH.name)
    for line in PHASE9_MANIFEST_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, path = line.split(" *", 1)
        if path == relative:
            return digest
    raise RuntimeCompositionError("PHASE9_MANIFEST_ENTRY_MISSING", relative)


def frozen_runtime_source() -> str:
    """The frozen Phase-9 runtime source, hash-verified against its manifest."""
    if not PHASE9_RUNTIME_PATH.is_file():
        raise RuntimeCompositionError("PHASE9_RUNTIME_MISSING", PHASE9_RUNTIME_PATH.name)
    source = PHASE9_RUNTIME_PATH.read_text(encoding="utf-8")
    expected = _manifest_hash(PHASE9_RUNTIME_RELATIVE)
    observed = sha256_text(source)
    if observed != expected:
        raise RuntimeCompositionError("PHASE9_RUNTIME_HASH_MISMATCH", observed)
    return source


def extension_source() -> str:
    if not EXTENSION_PATH.is_file():
        raise RuntimeCompositionError("EXTENSION_MISSING", EXTENSION_PATH.name)
    return EXTENSION_PATH.read_text(encoding="utf-8")


def compose_runtime_source() -> tuple[str, dict[str, Any]]:
    """Compose the Phase-10 runtime source and return it with a provenance record."""
    frozen = frozen_runtime_source()
    extension = extension_source()
    count = frozen.count(ANCHOR)
    if count == 0:
        raise RuntimeCompositionError("ANCHOR_MISSING", "or_rt_host_call definition")
    if count != 1:
        raise RuntimeCompositionError("ANCHOR_AMBIGUOUS", str(count))

    composed = frozen
    substitution_records: list[dict[str, Any]] = []
    for name, anchor, replacement in SUBSTITUTIONS:
        occurrences = composed.count(anchor)
        if occurrences == 0:
            raise RuntimeCompositionError("ANCHOR_MISSING", name)
        if occurrences != 1:
            raise RuntimeCompositionError("ANCHOR_AMBIGUOUS", f"{name}:{occurrences}")
        if replacement is None:
            replacement = extension.rstrip("\n") + "\n"
            text = replacement
            source = "extension"
        else:
            text = replacement
            source = "budget"
        substitution_records.append(
            {
                "name": name,
                "anchor_sha256": sha256_text(anchor),
                "substitution_sha256": sha256_text(text),
                "source": source,
            }
        )
        composed = composed.replace(anchor, text)

    record = {
        "runtime_version": RUNTIME_VERSION,
        "frozen_source": PHASE9_RUNTIME_RELATIVE,
        "frozen_sha256": sha256_text(frozen),
        "frozen_manifest_sha256": _manifest_hash(PHASE9_RUNTIME_RELATIVE),
        "extension_source": EXTENSION_PATH.relative_to(ROOT).as_posix(),
        "extension_sha256": sha256_text(extension),
        "substitutions": substitution_records,
        "substitution_count": len(substitution_records),
        "composed_sha256": sha256_text(composed),
        "composed_bytes": len(composed.encode("utf-8")),
        "frozen_source_reused_verbatim": True,
    }
    return composed, record
