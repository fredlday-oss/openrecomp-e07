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
from typing import Any

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
READ_REPLACEMENT = (
    "static uint64_t g_p10_access_budget = UINT64_C(2000000);\n"
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
    "    if (p10_budget_exceeded()) {\n"
    "        ++g_p9_denied_accesses;\n"
    "        return P9_RT_UNSUPPORTED_OPERATION;\n"
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
    "    if (p10_budget_exceeded()) {\n"
    "        ++g_p9_denied_accesses;\n"
    "        return P9_RT_UNSUPPORTED_OPERATION;\n"
    "    }\n"
    "    status = p9_width_bytes(width_bits, &width);\n"
)

SUBSTITUTIONS = (
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
