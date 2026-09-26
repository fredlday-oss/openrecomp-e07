#!/usr/bin/env python3
"""OpenRecomp Phase-17 P17-02 TITLE decode and structure-analysis V1.

Authenticate the frozen Hercules TITLE PS-X EXE payload, run the frozen
Phase-3 code-frontier analysis unchanged, and derive a bounded, fail-closed
basic-block projection directly from the frontier without using the frozen
Phase-10 structure conversion.

The module keeps all raw words, operands, and payload bytes in the in-memory
analysis object but exposes only a public projection that is safe to record:
addresses, ranges, counts, classes, and deterministic digests.  No host code is
emitted and no guest code is executed.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import struct
import sys
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable

ROOT = pathlib.Path(__file__).resolve().parents[2]

for extra in ("", ".openrecomp-phase17/src", ".openrecomp-phase3/src",
              ".openrecomp-phase9/src"):
    sys_path_extra = str(ROOT / extra) if extra else str(ROOT)
    if sys_path_extra not in sys.path:
        sys.path.insert(0, sys_path_extra)

import p3_code_frontier_v1 as frontier
import p3_decode_mips32_v1 as decode_v1
import p9_memory_map_v1 as memory_map
import p9_psx_exe_v1 as psx
import p17_contracts_v1 as contract
import p17_fixture_verification_v1 as fixture
import p17_iso9660_v1 as iso9660
import p17_psx_exe_identity_v1 as p17_psx

TITLE_ISO_PATH = r"\EX\TITLE.;1"

TITLE_FILE_SHA256 = "39013ea19589015872a211c23d8c23ae8ecee7bc5093d996f51cf206775f1b68"
TITLE_PAYLOAD_SHA256 = "fe1925b5dd7c7190802dbe37b162759467fdbbf95b707edb9c6bb1626b961ccc"
TITLE_FILE_SIZE = 288768
TITLE_PAYLOAD_SIZE = 286720
TITLE_ENTRY_PC = 0x800380A0
TITLE_TEXT_ADDR = 0x80038098
TITLE_TEXT_END = 0x8007E098


class TitleDecodeError(ValueError):
    """Fail-closed P17-02 rejection with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass
class TitleDecodeAnalysis:
    """In-memory analysis object; raw records are retained for later stages."""

    fixture_dir: pathlib.Path
    identity: p17_psx.PsxExeIdentity
    p9_image: psx.PsxExeImage
    contract: dict[str, Any]
    flat_image: bytes
    frontier: dict[str, Any]
    blocks: dict[int, "BasicBlock"]
    block_order: tuple[int, ...]
    projection: dict[str, Any] = field(default_factory=dict)
    records_by_address: dict[int, dict[str, Any]] = field(default_factory=dict)
    delay_by_owner: dict[int, int] = field(default_factory=dict)

    @property
    def records(self) -> list[dict[str, Any]]:
        return self.frontier["records"]

    @property
    def reachable_addresses(self) -> list[int]:
        return self.frontier["reachable_addresses"]


@dataclass
class BasicBlock:
    start: int
    addresses: tuple[int, ...]
    terminator: str | None
    successors: tuple["BlockEdge", ...]


@dataclass(frozen=True)
class BlockEdge:
    kind: str
    target_pc: int | None
    target_class: str


@dataclass(frozen=True)
class AddressClassification:
    address: int
    in_authenticated_text: bool
    decoded: bool
    decode_class: str | None
    op: str | None
    reachable: bool
    block_start: int | None
    block_member: bool
    control_flow_class: str | None
    delay_slot_owner: int | None


def fixture_root() -> pathlib.Path:
    env = os.environ.get("OPENRECOMP_HERCULES_FIXTURE_ROOT")
    if env:
        return pathlib.Path(env)
    return ROOT.parents[1] / "fixtures" / "psx" / "hercules"


def _read_word_u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise TitleDecodeError("READ_OUTSIDE_PAYLOAD", f"offset={offset}")
    return struct.unpack_from("<I", data, offset)[0]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _verify_title_identity(title_data: bytes) -> None:
    if len(title_data) != TITLE_FILE_SIZE:
        raise TitleDecodeError("TITLE_SIZE_MISMATCH", f"{len(title_data)} != {TITLE_FILE_SIZE}")
    if _sha256_bytes(title_data) != TITLE_FILE_SHA256:
        raise TitleDecodeError("TITLE_FILE_SHA256_MISMATCH")
    payload = title_data[0x800:]
    if len(payload) != TITLE_PAYLOAD_SIZE:
        raise TitleDecodeError("TITLE_PAYLOAD_SIZE_MISMATCH", f"{len(payload)}")
    if _sha256_bytes(payload) != TITLE_PAYLOAD_SHA256:
        raise TitleDecodeError("TITLE_PAYLOAD_SHA256_MISMATCH")


def _verify_identity_matches(identity: p17_psx.PsxExeIdentity) -> None:
    checks = [
        ("magic", identity.magic == b"PS-X EXE"),
        ("pc0", identity.pc0 == TITLE_ENTRY_PC),
        ("t_addr", identity.t_addr == TITLE_TEXT_ADDR),
        ("t_size", identity.t_size == TITLE_PAYLOAD_SIZE),
        ("text_end", identity.text_end == TITLE_TEXT_END),
        ("file_sha256", identity.file_sha256 == TITLE_FILE_SHA256),
        ("payload_sha256", identity.payload_sha256 == TITLE_PAYLOAD_SHA256),
        ("file_size", identity.file_size == TITLE_FILE_SIZE),
        ("payload_size", len(identity.payload) == TITLE_PAYLOAD_SIZE),
    ]
    failures = [name for name, ok in checks if not ok]
    if failures:
        raise TitleDecodeError("TITLE_IDENTITY_MISMATCH", ",".join(failures))


def _extract_title_from_disc(fixture_dir: pathlib.Path) -> bytes:
    fixture_ok, _ = fixture.verify_fixture(fixture_dir)
    if not fixture_ok:
        raise TitleDecodeError("FIXTURE_VERIFICATION_FAILED")
    image = iso9660.Iso9660Image.open(fixture_dir / "Disney's Hercules Action Game (USA).bin")
    record = image.find_file(TITLE_ISO_PATH)
    if record.data_length != TITLE_FILE_SIZE:
        raise TitleDecodeError("TITLE_FILE_SIZE_MISMATCH", f"{record.data_length}")
    data = image.extract_file(record)
    _verify_title_identity(data)
    return data


def _make_read_word(contract: dict[str, Any], flat: bytes) -> Callable[[int], int]:
    def read_word(address: int) -> int:
        return memory_map.read_u32(contract, flat, address)
    return read_word


def _derive_basic_blocks(frontier: dict[str, Any]) -> dict[int, BasicBlock]:
    records = {r["address"]: r for r in frontier["records"]}
    reachable = set(frontier["reachable_addresses"])
    delay_by_owner = {d["owner"]: d["delay"] for d in frontier["delay_slots"]}
    delay_owners = set(delay_by_owner.values())
    entry = frontier["entry"]
    entry_is_control = records[entry].get("control_flow", False)
    if entry_is_control and entry not in delay_by_owner:
        # Entry is a control transfer with no valid delay slot already resolved
        # by the frozen analysis; keep as the sole leader.
        pass

    leaders: set[int] = {entry}

    control_categories = ("conditional-branches", "jumps", "direct-calls")
    for cat in control_categories:
        for site in frontier["control_flow"][cat]:
            target = site.get("target")
            if target is not None and target in reachable and target not in delay_owners:
                leaders.add(target)
            if cat in ("conditional-branches", "direct-calls"):
                cont = site["site"] + 8
                if cont in reachable and cont not in delay_owners:
                    leaders.add(cont)
    for site in frontier["control_flow"]["indirect-calls"]:
        cont = site["site"] + 8
        if cont in reachable and cont not in delay_owners:
            leaders.add(cont)

    # Resolve any leader that is a delay slot by discarding it; a delay slot
    # is never an independent instruction leader.
    for leader in list(leaders):
        if leader in delay_owners:
            leaders.discard(leader)

    # If a leader would fall in the middle of a block (not a leader already and
    # is an owned delay slot), it has been discarded above.

    starts = sorted(leaders)
    blocks: dict[int, BasicBlock] = {}
    for start in starts:
        if start not in reachable:
            continue
        if start in delay_owners:
            continue
        addrs: list[int] = []
        pc = start
        terminator: str | None = None
        while pc in reachable:
            addrs.append(pc)
            record = records[pc]
            if record["decode_class"] in decode_v1.CLASS_INVALID:
                terminator = "unknown/reserved-frontier"
                break
            if record.get("control_flow"):
                delay = delay_by_owner.get(pc)
                if delay is not None:
                    addrs.append(delay)
                terminator = record.get("terminator")
                break
            pc += 4
            if pc in leaders or pc in delay_owners:
                break
        if not addrs:
            continue
        blocks[start] = BasicBlock(
            start=start,
            addresses=tuple(addrs),
            terminator=terminator,
            successors=_block_successors(start, addrs, records, frontier, reachable, delay_owners),
        )

    _validate_partition(blocks, reachable, delay_owners)
    return blocks


def _block_successors(
    start: int,
    addrs: list[int],
    records: dict[int, dict[str, Any]],
    frontier: dict[str, Any],
    reachable: set[int],
    delay_owners: set[int],
) -> tuple[BlockEdge, ...]:
    edges: list[BlockEdge] = []
    last_addr = addrs[-1]
    last_record = records[last_addr]

    if last_record["decode_class"] in decode_v1.CLASS_INVALID:
        edges.append(BlockEdge("frontier", last_addr, "unknown/reserved-encoding"))
        return tuple(edges)

    terminator = last_record.get("terminator")
    if terminator is None:
        fallthrough = last_addr + 4
        if fallthrough in reachable:
            edges.append(BlockEdge("fallthrough", fallthrough, "in-image"))
        else:
            edges.append(BlockEdge("fallthrough", fallthrough, "out-of-image"))
        return tuple(edges)

    if terminator == decode_v1.TERM_CONDITIONAL_BRANCH:
        target = last_record["target"]
        edges.append(BlockEdge("branch-taken", target, _target_class(target, reachable, delay_owners)))
        not_taken = last_addr + 8
        edges.append(BlockEdge("branch-not-taken", not_taken, _target_class(not_taken, reachable, delay_owners)))
    elif terminator == decode_v1.TERM_JUMP:
        target = last_record["target"]
        edges.append(BlockEdge("jump", target, _target_class(target, reachable, delay_owners)))
    elif terminator == decode_v1.TERM_DIRECT_CALL:
        target = last_record["target"]
        edges.append(BlockEdge("direct-call", target, _target_class(target, reachable, delay_owners)))
        return_addr = last_addr + 8
        edges.append(BlockEdge("call-return", return_addr, _target_class(return_addr, reachable, delay_owners)))
    elif terminator == decode_v1.TERM_RETURN:
        edges.append(BlockEdge("return", None, "unresolved"))
    elif terminator == decode_v1.TERM_INDIRECT_CALL:
        edges.append(BlockEdge("indirect-call", None, "unresolved"))
        return_addr = last_addr + 8
        edges.append(BlockEdge("call-return", return_addr, _target_class(return_addr, reachable, delay_owners)))
    elif terminator == decode_v1.TERM_INDIRECT_JUMP:
        edges.append(BlockEdge("indirect-jump", None, "unresolved"))
    elif terminator == decode_v1.TERM_UNSUPPORTED_CONTROL:
        edges.append(BlockEdge("unsupported-control", None, "unsupported"))
    elif terminator == decode_v1.TERM_EXTERNAL_TRAP:
        edges.append(BlockEdge("external-trap", None, "trap"))
    else:
        raise TitleDecodeError("UNKNOWN_TERMINATOR", f"0x{last_addr:08x} {terminator!r}")

    return tuple(edges)


def _target_class(target: int, reachable: set[int], delay_owners: set[int]) -> str:
    if target & 3:
        return "misaligned"
    if target in delay_owners:
        return "delay-slot-target"
    if target in reachable:
        return "in-image"
    return "out-of-image"


def _validate_partition(blocks: dict[int, BasicBlock], reachable: set[int], delay_owners: set[int]) -> None:
    covered: set[int] = set()
    for block in blocks.values():
        for addr in block.addresses:
            if addr in covered:
                raise TitleDecodeError("BLOCK_OVERLAP", f"0x{addr:08x}")
            covered.add(addr)
    expected = set(reachable)
    if covered != expected:
        missing = sorted(expected - covered)
        extra = sorted(covered - expected)
        raise TitleDecodeError(
            "BLOCK_PARTITION_MISMATCH",
            f"missing={len(missing)} extra={len(extra)}",
        )
    for block in blocks.values():
        for edge in block.successors:
            if edge.target_class == "delay-slot-target":
                raise TitleDecodeError("TARGET_INTO_DELAY_SLOT",
                                       f"0x{block.start:08x} -> 0x{edge.target_pc:08x}")


def _classify_address(
    pc: int,
    analysis: TitleDecodeAnalysis,
) -> AddressClassification:
    records = analysis.records_by_address
    record = records.get(pc)
    in_text = TITLE_TEXT_ADDR <= pc < TITLE_TEXT_END and pc % 4 == 0
    if record is None:
        return AddressClassification(
            address=pc,
            in_authenticated_text=in_text,
            decoded=False,
            decode_class=None,
            op=None,
            reachable=False,
            block_start=None,
            block_member=False,
            control_flow_class=None,
            delay_slot_owner=None,
        )
    reachable = record["reachability"] == frontier.REACHABLE
    block_start = None
    block_member = False
    for start, block in analysis.blocks.items():
        if pc in block.addresses:
            block_start = start
            block_member = True
            break
    delay_slot_owner = None
    for owner, delay in analysis.delay_by_owner.items():
        if delay == pc:
            delay_slot_owner = owner
            break
    return AddressClassification(
        address=pc,
        in_authenticated_text=in_text,
        decoded=True,
        decode_class=record["decode_class"],
        op=record["op"],
        reachable=reachable,
        block_start=block_start,
        block_member=block_member,
        control_flow_class=record.get("terminator"),
        delay_slot_owner=delay_slot_owner,
    )


def _build_public_projection(analysis: TitleDecodeAnalysis) -> dict[str, Any]:
    frontier = analysis.frontier
    summary = frontier["summary"]
    blocks = analysis.blocks
    block_order = analysis.block_order

    def sorted_hex(addrs: list[int]) -> list[str]:
        return [f"0x{a:08x}" for a in sorted(addrs)]

    control_flow_counts = dict(summary.get("control_flow_site_counts", {}))
    for key in ("conditional-branches", "jumps", "direct-calls", "returns",
                "indirect-calls", "indirect-jumps", "unsupported-control-transfers"):
        control_flow_counts.setdefault(key, 0)

    unresolved_counts = dict(summary.get("unresolved_site_counts", {}))
    for kind in ("unknown-encoding", "reserved-encoding", "indirect-call",
                 "indirect-jump", "successor-outside-image", "external-trap",
                 "delay-slot-outside-image", "delay-slot-unclassified",
                 "control-transfer-in-delay-slot", "unsupported-control-transfer"):
        unresolved_counts.setdefault(kind, 0)

    REACHABLE = "REACHABLE"
    decode_class_counts = Counter(
        r["decode_class"] for r in frontier["records"]
        if r["reachability"] == REACHABLE
    )
    op_counts = Counter(
        r["op"] for r in frontier["records"]
        if r["reachability"] == REACHABLE and r["op"] is not None
    )

    public_blocks = []
    for start in block_order:
        block = blocks[start]
        public_blocks.append({
            "start": f"0x{start:08x}",
            "instruction_count": len(block.addresses),
            "range": {
                "start": f"0x{block.addresses[0]:08x}",
                "end": f"0x{block.addresses[-1]:08x}",
            },
            "terminator": block.terminator,
            "successors": [
                {
                    "kind": e.kind,
                    "target_pc": (f"0x{e.target_pc:08x}" if e.target_pc is not None else None),
                    "target_class": e.target_class,
                }
                for e in block.successors
            ],
        })

    direct_calls = [
        {
            "site": f"0x{s['site']:08x}",
            "target_pc": f"0x{s['target']:08x}",
            "target_class": _target_class(s["target"], set(frontier["reachable_addresses"]),
                                          set(analysis.delay_by_owner.values())),
        }
        for s in sorted(frontier["control_flow"]["direct-calls"], key=lambda x: x["site"])
    ]
    branches = [
        {
            "site": f"0x{s['site']:08x}",
            "target_pc": f"0x{s['target']:08x}",
            "taken_class": _target_class(s["target"], set(frontier["reachable_addresses"]),
                                         set(analysis.delay_by_owner.values())),
        }
        for s in sorted(frontier["control_flow"]["conditional-branches"], key=lambda x: x["site"])
    ]
    jumps = [
        {
            "site": f"0x{s['site']:08x}",
            "target_pc": f"0x{s['target']:08x}",
            "target_class": _target_class(s["target"], set(frontier["reachable_addresses"]),
                                          set(analysis.delay_by_owner.values())),
        }
        for s in sorted(frontier["control_flow"]["jumps"], key=lambda x: x["site"])
    ]
    returns = [
        {"site": f"0x{s['site']:08x}"}
        for s in sorted(frontier["control_flow"]["returns"], key=lambda x: x["site"])
    ]
    delay_slot_owners = [
        {"owner": f"0x{d['owner']:08x}", "delay_slot": f"0x{d['delay']:08x}"}
        for d in sorted(frontier["delay_slots"], key=lambda x: x["owner"])
    ]
    unresolved_indirect = [
        {"site": f"0x{u['site']:08x}", "kind": u["kind"], "op": u.get("op")}
        for u in sorted(frontier["unresolved"], key=lambda x: (x["site"], x["kind"]))
        if u["kind"] in ("indirect-call", "indirect-jump")
    ]
    unsupported_unknown_sites = [
        {"site": f"0x{u['site']:08x}", "kind": u["kind"], "detail": u.get("detail") or u.get("note")}
        for u in sorted(frontier["unresolved"], key=lambda x: (x["site"], x["kind"]))
        if u["kind"] in ("unknown-encoding", "reserved-encoding", "unsupported-control-transfer")
    ]
    trap_sites = [
        {"site": f"0x{e['site']:08x}", "op": e.get("op"), "note": e.get("note")}
        for e in sorted(frontier["unresolved"], key=lambda x: x["site"])
        if e["kind"] == "external-trap"
    ]
    out_of_image = [
        {"site": f"0x{u['site']:08x}", "kind": u["kind"],
         "target_pc": (f"0x{u['target']:08x}" if u.get("target") is not None else None)}
        for u in sorted(frontier["unresolved"], key=lambda x: (x["site"], x["kind"]))
        if u["kind"] == "successor-outside-image"
    ]

    projection = {
        "schema": "openrecomp-phase17-title-decode-v1",
        "stage": "P17-02",
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "provenance": {
            "title_file_sha256": TITLE_FILE_SHA256,
            "title_payload_sha256": TITLE_PAYLOAD_SHA256,
            "guest_text": {"start": f"0x{TITLE_TEXT_ADDR:08x}", "end": f"0x{TITLE_TEXT_END:08x}"},
            "guest_entry_pc": f"0x{TITLE_ENTRY_PC:08x}",
            "file_size": TITLE_FILE_SIZE,
            "payload_size": TITLE_PAYLOAD_SIZE,
        },
        "reachable_summary": {
            "total_words": summary["total_words"],
            "reachable_words": summary["reachable_words"],
            "reachable_supported_words": summary["reachable_supported_words"],
            "reachable_unsupported_words": summary["reachable_unsupported_words"],
            "reachable_invalid_words": summary["reachable_invalid_words"],
            "unreachable_words": summary["unreachable_words"],
            "delay_slot_count": len(frontier["delay_slots"]),
            "exception_site_count": summary["exception_site_count"],
        },
        "decode_class_histogram": dict(sorted(decode_class_counts.items())),
        "reachable_op_histogram": dict(sorted(op_counts.items())),
        "control_flow_counts": control_flow_counts,
        "unresolved_counts": unresolved_counts,
        "basic_blocks": {
            "count": len(public_blocks),
            "blocks": public_blocks,
        },
        "direct_calls": direct_calls,
        "branches": branches,
        "jumps": jumps,
        "returns": returns,
        "delay_slot_owners": delay_slot_owners,
        "unresolved_indirect_flow": unresolved_indirect,
        "unsupported_unknown_sites": unsupported_unknown_sites,
        "trap_sites": trap_sites,
        "out_of_image_successors": out_of_image,
        "modelled_addresses": {},
        "phase16_note": "Phase-16 values were modelled constants; Phase-16 evidence was not rewritten.",
    }
    projection["projection_digest"] = _sha256_bytes(
        json.dumps(projection, sort_keys=True).encode("utf-8")
    )
    return projection


def _attach_modelled_addresses(projection: dict[str, Any], analysis: TitleDecodeAnalysis) -> dict[str, Any]:
    for pc in (0x8004FF54, 0x80050110):
        projection["modelled_addresses"][f"0x{pc:08x}"] = _classify_address(pc, analysis).asdict()
    return projection


def analyze_title_decode(
    fixture_dir: pathlib.Path | None = None,
    title_data: bytes | None = None,
) -> TitleDecodeAnalysis:
    """Authenticate and decode TITLE; derive bounded basic blocks from the frontier."""
    if title_data is None:
        if fixture_dir is None:
            fixture_dir = fixture_root()
        title_data = _extract_title_from_disc(fixture_dir)
    else:
        _verify_title_identity(title_data)

    identity = p17_psx.ingest_bytes(title_data)
    _verify_identity_matches(identity)

    p9_image = psx.ingest(title_data)
    contract = memory_map.build_contract(p9_image)
    flat = memory_map.flat_image(p9_image)

    frontier_analysis = frontier.analyze(
        _make_read_word(contract, flat),
        p9_image.header.t_addr,
        p9_image.header.t_addr + p9_image.header.t_size,
        p9_image.header.pc0,
    )

    blocks = _derive_basic_blocks(frontier_analysis)
    block_order = tuple(sorted(blocks))

    analysis = TitleDecodeAnalysis(
        fixture_dir=fixture_dir or pathlib.Path(),
        identity=identity,
        p9_image=p9_image,
        contract=contract,
        flat_image=flat,
        frontier=frontier_analysis,
        blocks=blocks,
        block_order=block_order,
        records_by_address={r["address"]: r for r in frontier_analysis["records"]},
        delay_by_owner={d["owner"]: d["delay"] for d in frontier_analysis["delay_slots"]},
    )

    projection = _build_public_projection(analysis)
    projection = _attach_modelled_addresses(projection, analysis)
    analysis.projection = projection
    return analysis


# Expose AddressClassification as a plain dict helper for tests.
def _address_classification_asdict(self: "AddressClassification") -> dict[str, Any]:
    return {
        "address": f"0x{self.address:08x}",
        "in_authenticated_text": self.in_authenticated_text,
        "decoded": self.decoded,
        "decode_class": self.decode_class,
        "op": self.op,
        "reachable": self.reachable,
        "block_start": (f"0x{self.block_start:08x}" if self.block_start is not None else None),
        "block_member": self.block_member,
        "control_flow_class": self.control_flow_class,
        "delay_slot_owner": (f"0x{self.delay_slot_owner:08x}" if self.delay_slot_owner is not None else None),
    }
AddressClassification.asdict = _address_classification_asdict  # type: ignore[attr-defined]
