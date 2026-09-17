#!/usr/bin/env python3
"""OpenRecomp Phase-3 MIPS32 code-reachability and control-flow frontier V1.

Static, fail-closed discovery of the executable frontier of an ingested guest
image starting from the ELF entry point:

* every 4-byte-aligned word of the executable region is classified through
  :mod:`p3_decode_mips32_v1`; reachability is *not* assumed for all words;
* direct control flow (conditional branches, jumps, direct calls, returns) is
  followed with MIPS32 delay-slot semantics; a delay slot is entered but never
  allowed to generate its own fall-through successor;
* indirect control flow (``jalr``, ``jr`` through a register, jump tables) is
  classified as an unresolved frontier site; targets are never invented;
* reserved/unknown encodings and unresolvable successors stop flow and are
  recorded as frontier gaps rather than guessed;
* trap instructions (``teq`` and the trap family) are decoded and recorded as
  an exception-transfer semantic gap; the non-trapping fall-through path
  continues because exception delivery is explicitly out of scope.

The engine is deterministic (sorted outputs, no host state) and works on an
abstract word reader so it can be exercised on synthetic fixtures as well as
the audited CoreMark image.  It adds no execution semantics.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Callable

import p3_decode_mips32_v1 as decode_v1

MASK32 = 0xFFFFFFFF

REACHABLE = "REACHABLE"
UNREACHABLE = "UNREACHABLE"

PADDING_NON_CODE = "PADDING_NON_CODE"
UNREACHED_CODE = "UNREACHED_CODE"


class FrontierError(ValueError):
    """Fail-closed frontier-engine rejection with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def _validate_region(start: int, end: int, entry: int) -> None:
    if start < 0 or end > MASK32 or start & 3 or end & 3:
        raise FrontierError("INVALID_REGION", f"start=0x{start:x} end=0x{end:x}")
    if end <= start:
        raise FrontierError("EMPTY_REGION", f"start=0x{start:x} end=0x{end:x}")
    if entry & 3 or not (start <= entry < end):
        raise FrontierError("INVALID_ENTRY", f"entry=0x{entry:x}")


def _site(record: dict[str, Any]) -> dict[str, Any]:
    site = {"site": record["address"], "op": record["op"]}
    if record["target"] is not None:
        site["target"] = record["target"]
    if record["link"]:
        site["link"] = True
    if record["operands"]:
        site["operands"] = dict(record["operands"])
    return site


def analyze(
    read_word: Callable[[int], int],
    start: int,
    end: int,
    entry: int,
) -> dict[str, Any]:
    """Classify the region and discover reachable code from ``entry``."""
    _validate_region(start, end, entry)
    addresses = list(range(start, end, 4))
    records: dict[int, dict[str, Any]] = {}
    for address in addresses:
        word = read_word(address)
        if not isinstance(word, int) or word < 0 or word > MASK32:
            raise FrontierError("INVALID_WORD", f"address=0x{address:x} word={word!r}")
        records[address] = decode_v1.classify(address, word)

    reachable: set[int] = set()
    processed: set[int] = set()
    queued: set[int] = {entry}
    queue: list[int] = [entry]
    delay_owner: dict[int, list[int]] = defaultdict(list)
    delay_slots: list[dict[str, int]] = []
    control_flow: dict[str, list[dict[str, Any]]] = {
        "conditional-branches": [],
        "jumps": [],
        "direct-calls": [],
        "returns": [],
        "indirect-calls": [],
        "indirect-jumps": [],
        "unsupported-control-transfers": [],
    }
    unresolved: list[dict[str, Any]] = []
    exception_sites: list[dict[str, Any]] = []
    diagnostics: dict[str, list[dict[str, Any]]] = {
        "target-into-delay-slot": [],
        "delay-slot-reached-by-fallthrough": [],
    }

    def push(target: int, successor_kind: str, origin: int) -> None:
        if target & 3 or target < start or target >= end:
            unresolved.append({
                "site": origin,
                "kind": "successor-outside-image",
                "successor_kind": successor_kind,
                "target": target,
            })
            return
        if target in delay_owner:
            diagnostics["target-into-delay-slot"].append({
                "site": origin,
                "successor_kind": successor_kind,
                "target": target,
                "delay_owners": sorted(delay_owner[target]),
            })
        if target not in queued:
            queued.add(target)
            queue.append(target)

    while queue:
        address = queue.pop()
        if address in processed:
            continue
        processed.add(address)
        reachable.add(address)
        record = records[address]
        if decode_v1.is_invalid(record):
            unresolved.append({
                "site": address,
                "kind": "reserved-encoding" if record["decode_class"] == decode_v1.CLASS_RESERVED
                        else "unknown-encoding",
                "detail": record["reason"],
            })
            continue
        if record["exception_transfer"]:
            exception_sites.append({
                "site": address,
                "op": record["op"],
                "note": (
                    "exception delivery not modelled; flow stopped"
                    if record["control_flow"] else
                    "exception delivery not modelled; non-trapping path followed"
                ),
            })
        if not record["control_flow"]:
            fallthrough = address + 4
            if fallthrough in delay_owner:
                diagnostics["delay-slot-reached-by-fallthrough"].append({
                    "site": address,
                    "target": fallthrough,
                })
            push(fallthrough, "fallthrough", address)
            continue

        delay_unresolved = False
        if record["delay_slot"]:
            delay = address + 4
            if delay >= end:
                unresolved.append({
                    "site": address,
                    "kind": "delay-slot-outside-image",
                    "successor_kind": "delay-slot",
                })
                delay_unresolved = True
            else:
                delay_record = records[delay]
                delay_owner[delay].append(address)
                if delay_record["decode_class"] in decode_v1.CLASS_INVALID:
                    unresolved.append({
                        "site": address,
                        "kind": "delay-slot-unclassified",
                        "successor_kind": "delay-slot",
                        "detail": delay_record["reason"],
                    })
                    delay_unresolved = True
                elif delay_record["control_flow"]:
                    unresolved.append({
                        "site": address,
                        "kind": "control-transfer-in-delay-slot",
                        "successor_kind": "delay-slot",
                        "detail": delay_record["op"],
                    })
                    delay_unresolved = True
                else:
                    reachable.add(delay)
                    delay_slots.append({"owner": address, "delay": delay})
            if delay_unresolved:
                # Architecturally undefined/unresolvable delay slot: fail closed
                # and do not guess any successor of this transfer.
                continue

        terminator = record["terminator"]
        if terminator == decode_v1.TERM_CONDITIONAL_BRANCH:
            control_flow["conditional-branches"].append(_site(record))
            push(record["target"], "conditional-branch-target", address)
            push(address + 8, "conditional-branch-not-taken", address)
        elif terminator == decode_v1.TERM_JUMP:
            control_flow["jumps"].append(_site(record))
            push(record["target"], "jump-target", address)
        elif terminator == decode_v1.TERM_DIRECT_CALL:
            control_flow["direct-calls"].append(_site(record))
            push(record["target"], "direct-call-target", address)
            push(address + 8, "direct-call-return", address)
        elif terminator == decode_v1.TERM_RETURN:
            control_flow["returns"].append(_site(record))
        elif terminator == decode_v1.TERM_INDIRECT_CALL:
            control_flow["indirect-calls"].append(_site(record))
            unresolved.append({
                "site": address,
                "kind": "indirect-call",
                "op": record["op"],
                "resolve_register": record["operands"].get("rs"),
                "note": "target not statically resolved; return continuation followed",
            })
            push(address + 8, "indirect-call-return", address)
        elif terminator == decode_v1.TERM_INDIRECT_JUMP:
            control_flow["indirect-jumps"].append(_site(record))
            unresolved.append({
                "site": address,
                "kind": "indirect-jump",
                "op": record["op"],
                "resolve_register": record["operands"].get("rs"),
                "note": "target not statically resolved",
            })
        elif terminator == decode_v1.TERM_UNSUPPORTED_CONTROL:
            control_flow["unsupported-control-transfers"].append(_site(record))
            unresolved.append({
                "site": address,
                "kind": "unsupported-control-transfer",
                "op": record["op"],
                "note": "control-flow semantics not supported by this stage; flow stopped",
            })
        elif terminator == decode_v1.TERM_EXTERNAL_TRAP:
            unresolved.append({
                "site": address,
                "kind": "external-trap",
                "op": record["op"],
                "note": "exception/trap delivery not modelled; flow stopped",
            })
        else:
            raise FrontierError("UNKNOWN_TERMINATOR", f"0x{address:x} {terminator!r}")

    unreachable = [address for address in addresses if address not in reachable]

    def sorted_records(predicate) -> list[dict[str, Any]]:
        output = []
        for address in sorted(records):
            record = records[address]
            if not predicate(record):
                continue
            enriched = dict(record)
            enriched["reachability"] = REACHABLE if address in reachable else UNREACHABLE
            output.append(enriched)
        return output

    words = sorted_records(lambda record: True)
    class_counts = Counter(record["decode_class"] for record in records.values())
    reachable_records = [record for record in words if record["reachability"] == REACHABLE]
    unreachable_records = [record for record in words if record["reachability"] == UNREACHABLE]
    unsupported_total = Counter(
        record["op"] for record in words
        if record["decode_class"] == decode_v1.CLASS_RECOGNIZED_UNSUPPORTED)
    unsupported_reachable = Counter(
        record["op"] for record in reachable_records
        if record["decode_class"] == decode_v1.CLASS_RECOGNIZED_UNSUPPORTED)
    unsupported_unreachable = Counter(
        record["op"] for record in unreachable_records
        if record["decode_class"] == decode_v1.CLASS_RECOGNIZED_UNSUPPORTED)
    supported_total = Counter(
        record["op"] for record in words
        if record["decode_class"] == decode_v1.CLASS_SUPPORTED)
    supported_reachable = Counter(
        record["op"] for record in reachable_records
        if record["decode_class"] == decode_v1.CLASS_SUPPORTED)

    for key in control_flow:
        control_flow[key].sort(key=lambda item: item["site"])
    unresolved.sort(key=lambda item: (item["site"], item["kind"]))
    for key in diagnostics:
        diagnostics[key].sort(key=lambda item: (item["site"], item["target"]))

    return {
        "region": {"start": start, "end": end, "words": len(addresses)},
        "entry": entry,
        "records": words,
        "reachable_addresses": sorted(reachable),
        "unreachable_addresses": unreachable,
        "delay_slots": sorted(delay_slots, key=lambda item: item["delay"]),
        "control_flow": control_flow,
        "unresolved": unresolved,
        "exception_sites": sorted(exception_sites, key=lambda item: item["site"]),
        "diagnostics": diagnostics,
        "summary": {
            "total_words": len(addresses),
            "decoded_words": sum(
                class_counts[cls] for cls in (
                    decode_v1.CLASS_SUPPORTED, decode_v1.CLASS_RECOGNIZED_UNSUPPORTED)),
            "supported_words": class_counts[decode_v1.CLASS_SUPPORTED],
            "recognized_unsupported_words": class_counts[decode_v1.CLASS_RECOGNIZED_UNSUPPORTED],
            "reserved_encoding_words": class_counts[decode_v1.CLASS_RESERVED],
            "unknown_encoding_words": class_counts[decode_v1.CLASS_UNKNOWN],
            "invalid_words": class_counts[decode_v1.CLASS_RESERVED] + class_counts[decode_v1.CLASS_UNKNOWN],
            "reachable_words": len(reachable),
            "unreachable_words": len(unreachable),
            "reachable_supported_words": sum(
                1 for record in reachable_records
                if record["decode_class"] == decode_v1.CLASS_SUPPORTED),
            "reachable_unsupported_words": sum(
                1 for record in reachable_records
                if record["decode_class"] == decode_v1.CLASS_RECOGNIZED_UNSUPPORTED),
            "reachable_invalid_words": sum(
                1 for record in reachable_records
                if record["decode_class"] in decode_v1.CLASS_INVALID),
            "supported_histogram": dict(sorted(supported_total.items())),
            "supported_reachable_histogram": dict(sorted(supported_reachable.items())),
            "unsupported_histogram": dict(sorted(unsupported_total.items())),
            "unsupported_reachable_histogram": dict(sorted(unsupported_reachable.items())),
            "unsupported_unreachable_histogram": dict(sorted(unsupported_unreachable.items())),
            "control_flow_site_counts": {
                key: len(value) for key, value in sorted(control_flow.items())
            },
            "unresolved_site_counts": dict(sorted(Counter(
                item["kind"] for item in unresolved).items())),
            "exception_site_count": len(exception_sites),
        },
    }


def unreachable_classification(
    records: list[dict[str, Any]],
    function_ranges: list[tuple[int, int]],
) -> list[dict[str, Any]]:
    """Classify unreachable words as padding/non-code or unreached code.

    ``function_ranges`` is symbol-assisted diagnostic input only: a word is
    padding/non-code only when it is simultaneously (a) unreachable from the
    entry by direct discovery, (b) an invalid/reserved encoding and (c) outside
    every function symbol range.  Anything else stays ``UNREACHED_CODE``.
    """
    classified: list[dict[str, Any]] = []
    for record in records:
        if record["reachability"] != UNREACHABLE:
            continue
        address = record["address"]
        in_function = any(start <= address < end for start, end in function_ranges)
        invalid = record["decode_class"] in decode_v1.CLASS_INVALID
        if invalid and not in_function:
            code_class = PADDING_NON_CODE
            reason = "unreachable reserved encoding outside every function symbol range"
        else:
            code_class = UNREACHED_CODE
            reason = "unreachable decoded code word"
        classified.append({
            "address": address,
            "word": record["word"],
            "decode_class": record["decode_class"],
            "op": record["op"],
            "code_class": code_class,
            "in_function_symbol_range": in_function,
            "reason": reason,
        })
    return classified
