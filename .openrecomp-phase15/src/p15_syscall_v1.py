#!/usr/bin/env python3
"""Exact-site Phase-15 critical-section syscall mediation.

Only the two execution-reached wrapper functions are rewritten.  Their frozen
terminal instructions are the already-proven syscall sites with selectors 1
and 2.  Every source substitution is exact and counted; any source drift fails
closed before native compilation.  No generic exception or syscall dispatcher
is enabled.
"""

from __future__ import annotations

import hashlib
from typing import Any

SYSCALL_VERSION = "1.0.0"

DECLARATION_ANCHOR = "extern const char *or_rt_failure_reason(int code);\n"
DECLARATION_REPLACEMENT = (
    DECLARATION_ANCHOR
    + "extern int p15_critical_syscall(uint32_t selector, uint64_t *out_value);\n"
)

SITES = (
    {"name": "EnterCriticalSection", "function": 0x80015F18,
     "site": 0x80015F1C, "selector": 1},
    {"name": "ExitCriticalSection", "function": 0x80015F28,
     "site": 0x80015F2C, "selector": 2},
)


class Phase15SyscallError(ValueError):
    pass


def _function_text(site: dict[str, Any], *, trace: bool, mediated: bool) -> str:
    function = site["function"]
    selector = site["selector"]
    lines = [f"static void fn_fn_{function:08x}(void) {{"]
    if trace:
        lines.append(f"    p11_trace_function(UINT64_C({function}));")
    lines.append(f"bb_blk_{function:08x}:;")
    if trace:
        lines.append(f"    p11_trace_block(UINT64_C({function}));")
    lines.append(f"    g_r[4] = ((g_r[0]) + (UINT64_C({selector}))) & or_mask(32u);")
    if mediated:
        lines.extend([
            "    {",
            "        uint64_t p15_value = UINT64_C(0);",
            f"        if (p15_critical_syscall(UINT32_C({selector}), &p15_value) != OR_RT_OK) {{",
            "            or_fail(\"phase15 critical syscall failed\");",
            "            return;",
            "        }",
            "        g_r[2] = p15_value & or_mask(32u);",
            "    }",
        ])
    else:
        lines.append("    or_fail(\"guest trap is unsupported\");")
    lines.extend(["    return;", "}", ""])
    return "\n".join(lines)


def compose_program_source(text: str, *, trace: bool) -> tuple[str, dict[str, Any]]:
    if text.count(DECLARATION_ANCHOR) != 1:
        raise Phase15SyscallError("DECLARATION_ANCHOR_MISSING_OR_AMBIGUOUS")
    composed = text.replace(DECLARATION_ANCHOR, DECLARATION_REPLACEMENT)
    substitutions: list[dict[str, Any]] = []
    for site in SITES:
        anchor = _function_text(site, trace=trace, mediated=False)
        replacement = _function_text(site, trace=trace, mediated=True)
        count = composed.count(anchor)
        if count != 1:
            raise Phase15SyscallError(
                f"SITE_ANCHOR_MISSING_OR_AMBIGUOUS:{site['site']:08x}:{count}"
            )
        composed = composed.replace(anchor, replacement)
        substitutions.append({
            "name": site["name"],
            "function": f"0x{site['function']:08x}",
            "site": f"0x{site['site']:08x}",
            "selector": site["selector"],
            "anchor_sha256": hashlib.sha256(anchor.encode()).hexdigest(),
            "replacement_sha256": hashlib.sha256(replacement.encode()).hexdigest(),
        })
    return composed, {
        "schema": "openrecomp-phase15-critical-syscall-composition-v1",
        "version": SYSCALL_VERSION,
        "trace_enabled": trace,
        "substitutions": substitutions,
        "generic_exception_delivery": "NOT_ENABLED",
        "generic_syscall_dispatch": "NOT_ENABLED",
        "composed_sha256": hashlib.sha256(composed.encode()).hexdigest(),
    }
