#!/usr/bin/env python3
"""OpenRecomp Phase-17 P17-05R main-EXE payload authentication and mapping V1.

The P17-02 projection is a bounded direct-control-flow projection over the
authenticated TITLE payload alone.  The authentic TITLE execution therefore
legitimately leaves the authenticated table when the recorded frontier transfers
from 0x8003812c (delay slot 0x80038130) to 0x80011af0: that address lies below
the TITLE payload, inside the main game executable SLUS_005.29.

This module authenticates the destination region directly from the read-only
private fixture member and establishes, for every newly executable address, the
chain

    source artifact SHA-256
      -> PS-X EXE header fields (t_addr / t_size / entry / GP)
      -> file offset
      -> guest load address
      -> 32-bit instruction word
      -> fresh decode
      -> emitted execution record

No address is accepted without recomputing this chain from the source bytes; the
continuation entry is supplied by the recorded P17-04R frontier state and must
fall inside the authenticated main-EXE text, otherwise the build fails closed.
Nothing in this module hard-codes the frontier.

Public evidence derived here carries hashes, counts, offsets and addresses only:
no raw payload bytes, no BIOS bytes, no private absolute paths.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import struct
import sys
from dataclasses import dataclass, field
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _extra in ("", ".openrecomp-phase17/src", ".openrecomp-phase3/src",
               ".openrecomp-phase9/src"):
    _path = str(ROOT / _extra) if _extra else str(ROOT)
    if _path not in sys.path:
        sys.path.insert(0, _path)

import p3_code_frontier_v1 as frontier_engine
import p9_psx_exe_v1 as p9
import p17_fixture_verification_v1 as fixture_verification
import p17_psx_exe_identity_v1 as p17_psx

# Fixture member holding the main game executable (read-only private fixture).
MAINEXE_FIXTURE_MEMBER = "SLUS_005.29"

# Authenticated fixture identity of the main-EXE member.  This binds payload
# authentication to the P17-01 fixture manifest rather than a new ad-hoc constant.
MAINEXE_FILE_SHA256 = fixture_verification.EXPECTED_SLUS_SHA256
MAINEXE_FILE_SIZE = fixture_verification.EXPECTED_SIZES["slus"]

# PS-X EXE header size (text file offset base).
HEADER_SIZE = p9.HEADER_SIZE
PSX_RAM_KSEG0_BASE = p9.PSX_RAM_KSEG0_BASE
PSX_RAM_KSEG0_END = p9.PSX_RAM_KSEG0_END

MASK32 = 0xFFFFFFFF


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class MainExeAuthError(ValueError):
    """Fail-closed main-EXE authentication rejection with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class MainExeProvenance:
    """Authenticated provenance chain for one reachable main-EXE guest PC.

    asdict() intentionally carries only hashes/offsets/addresses so documents
    built from it stay public-safe; the raw instruction word never appears here.
    """

    guest_pc: int
    payload_offset: int
    file_offset: int
    mainexe_file_sha256: str
    mainexe_payload_sha256: str
    t_addr: int
    t_size: int

    def asdict(self) -> dict[str, Any]:
        return {
            "guest_pc": f"0x{self.guest_pc:08x}",
            "payload_offset": self.payload_offset,
            "file_offset": self.file_offset,
            "mainexe_text_addr": f"0x{self.t_addr:08x}",
            "mainexe_text_size": self.t_size,
            "mainexe_file_sha256": self.mainexe_file_sha256,
            "mainexe_payload_sha256": self.mainexe_payload_sha256,
        }

    def digest(self) -> str:
        return _sha256_bytes(json.dumps(self.asdict(), sort_keys=True).encode("utf-8"))


def fixture_root() -> pathlib.Path:
    """Resolve the read-only private fixture root (env override honoured)."""
    env = os.environ.get("OPENRECOMP_HERCULES_FIXTURE_ROOT")
    if env:
        return pathlib.Path(env)
    return ROOT.parents[1] / "fixtures" / "psx" / "hercules"


def mainexe_member_path(fixture_dir: pathlib.Path | None = None) -> pathlib.Path:
    base = fixture_dir if fixture_dir is not None else fixture_root()
    return base / MAINEXE_FIXTURE_MEMBER


def structural_validate(identity: p17_psx.PsxExeIdentity) -> None:
    """Fail closed unless the PS-X EXE header is self-consistent with geometry.

    The header fields are re-derived from the source bytes, not trusted blindly:
    the text section must exactly fill the file after the header and live inside
    PS1 KSEG0 RAM, and the entry must lie inside the text section.
    """
    t_addr = identity.t_addr
    t_size = identity.t_size
    if identity.magic != p9.MAGIC:
        raise MainExeAuthError("MAINEXE_MAGIC_MISMATCH", repr(identity.magic))
    if t_size <= 0 or t_size % 4:
        raise MainExeAuthError("MAINEXE_TEXT_SIZE_INVALID", f"t_size={t_size}")
    if identity.file_size != HEADER_SIZE + t_size:
        raise MainExeAuthError(
            "MAINEXE_TEXT_GEOMETRY_MISMATCH",
            f"file_size={identity.file_size} header+t_size={HEADER_SIZE + t_size}",
        )
    if len(identity.payload) != t_size:
        raise MainExeAuthError("MAINEXE_PAYLOAD_SIZE_MISMATCH", f"{len(identity.payload)}")
    if t_addr % 4 or not (PSX_RAM_KSEG0_BASE <= t_addr < PSX_RAM_KSEG0_END):
        raise MainExeAuthError("MAINEXE_TEXT_ADDR_OUTSIDE_RAM", f"0x{t_addr:08x}")
    if t_addr + t_size > PSX_RAM_KSEG0_END:
        raise MainExeAuthError("MAINEXE_TEXT_EXCEEDS_RAM", f"0x{t_addr + t_size:08x}")
    pc0 = identity.pc0
    if pc0 % 4 or not (t_addr <= pc0 < t_addr + t_size):
        raise MainExeAuthError("MAINEXE_ENTRY_OUTSIDE_TEXT", f"0x{pc0:08x}")


def load_mainexe_identity(
    fixture_dir: pathlib.Path | None = None,
) -> tuple[p17_psx.PsxExeIdentity, bytes]:
    """Read and authenticate the fixture member, returning (identity, bytes)."""
    path = mainexe_member_path(fixture_dir)
    if not path.is_file():
        raise MainExeAuthError("MAINEXE_MEMBER_MISSING", path.name)
    data = path.read_bytes()
    if len(data) != MAINEXE_FILE_SIZE:
        raise MainExeAuthError("MAINEXE_FILE_SIZE_MISMATCH", f"{len(data)}")
    if _sha256_bytes(data) != MAINEXE_FILE_SHA256:
        raise MainExeAuthError("MAINEXE_FILE_SHA256_MISMATCH")
    try:
        identity = p17_psx.ingest_bytes(data)
    except Exception as exc:  # frozen Phase-9 parser rejection
        raise MainExeAuthError(
            "MAINEXE_HEADER_REJECTED",
            f"{type(exc).__name__}: {exc}",
        ) from exc
    if identity.file_sha256 != MAINEXE_FILE_SHA256:
        raise MainExeAuthError("MAINEXE_FILE_SHA256_MISMATCH")
    structural_validate(identity)
    return identity, data


def guest_to_file_offset(
    identity: p17_psx.PsxExeIdentity,
    guest_addr: int,
    *,
    header_size: int | None = None,
) -> int:
    """Map an authenticated guest load address to its source file offset."""
    base = HEADER_SIZE if header_size is None else header_size
    if guest_addr & 3:
        raise MainExeAuthError("MAINEXE_GUEST_ADDRESS_UNALIGNED", f"0x{guest_addr:08x}")
    if not (identity.t_addr <= guest_addr < identity.t_addr + identity.t_size):
        raise MainExeAuthError(
            "MAINEXE_GUEST_ADDRESS_OUTSIDE_TEXT",
            f"0x{guest_addr:08x} text=0x{identity.t_addr:08x}+0x{identity.t_size:x}",
        )
    return base + (guest_addr - identity.t_addr)


def file_offset_to_guest(
    identity: p17_psx.PsxExeIdentity,
    file_offset: int,
    *,
    header_size: int | None = None,
) -> int:
    """Inverse of guest_to_file_offset (fail closed)."""
    base = HEADER_SIZE if header_size is None else header_size
    payload_offset = file_offset - base
    if payload_offset < 0 or payload_offset + 4 > identity.t_size:
        raise MainExeAuthError("MAINEXE_FILE_OFFSET_OUTSIDE_TEXT", f"0x{file_offset:x}")
    return identity.t_addr + payload_offset


def read_authenticated_word(
    identity: p17_psx.PsxExeIdentity,
    guest_addr: int,
    *,
    file_bytes: bytes | None = None,
    header_size: int | None = None,
) -> int:
    """Read the 32-bit guest word through the full mapping chain.

    When file_bytes is provided the word at the mapped file offset must equal the
    word at the corresponding payload offset; otherwise the mapping (and any
    wrong offset or inconsistent header) fails closed.
    """
    file_offset = guest_to_file_offset(identity, guest_addr, header_size=header_size)
    payload_offset = guest_addr - identity.t_addr
    if payload_offset + 4 > len(identity.payload):
        raise MainExeAuthError("MAINEXE_PAYLOAD_OFFSET_OUT_OF_RANGE", f"0x{guest_addr:08x}")
    payload_word = struct.unpack_from("<I", identity.payload, payload_offset)[0]
    if file_bytes is not None:
        if file_offset + 4 > len(file_bytes):
            raise MainExeAuthError("MAINEXE_FILE_OFFSET_OUT_OF_RANGE", f"0x{file_offset:x}")
        file_word = struct.unpack_from("<I", file_bytes, file_offset)[0]
        if file_word != payload_word:
            raise MainExeAuthError(
                "MAINEXE_FILE_OFFSET_MISMATCH",
                f"guest=0x{guest_addr:08x} file_off=0x{file_offset:x}",
            )
    return payload_word


@dataclass
class MainExeAnalysis:
    """Authenticated main-EXE map plus its bounded reachable continuation set."""

    identity: p17_psx.PsxExeIdentity
    file_sha256: str
    payload_sha256: str
    file_bytes: bytes = field(repr=False, default=b"")
    frontier: dict[str, Any] = field(default_factory=dict)
    records_by_address: dict[int, dict[str, Any]] = field(default_factory=dict)
    delay_by_owner: dict[int, int] = field(default_factory=dict)
    provenance: dict[int, MainExeProvenance] = field(default_factory=dict)
    continuation_entry_pc: int = 0

    @property
    def reachable_addresses(self) -> list[int]:
        return list(self.frontier["reachable_addresses"])

    @property
    def reachable_count(self) -> int:
        return len(self.frontier["reachable_addresses"])

    def read_word(self, guest_addr: int) -> int:
        return read_authenticated_word(
            self.identity, guest_addr, file_bytes=self.file_bytes or None
        )


def build_mainexe_analysis(
    continuation_entry_pc: int,
    *,
    fixture_dir: pathlib.Path | None = None,
    identity: p17_psx.PsxExeIdentity | None = None,
    file_bytes: bytes | None = None,
    expected_payload_sha256: str | None = None,
    header_size: int | None = None,
) -> MainExeAnalysis:
    """Authenticate the main-EXE text and discover the bounded continuation set.

    Every reachable address carries a MainExeProvenance chain entry and every
    read is re-checked against the mapped source file offset.  The continuation
    entry must map through the authenticated header; otherwise the build fails
    closed before any record is produced.
    """
    if identity is None:
        identity, file_bytes = load_mainexe_identity(fixture_dir)
    elif file_bytes is None:
        path = mainexe_member_path(fixture_dir)
        file_bytes = path.read_bytes() if path.is_file() else b""
    structural_validate(identity)
    if expected_payload_sha256 is not None and identity.payload_sha256 != expected_payload_sha256:
        raise MainExeAuthError(
            "MAINEXE_PAYLOAD_SHA256_MISMATCH",
            f"live={identity.payload_sha256} expected={expected_payload_sha256}",
        )

    # The continuation entry must be inside the authenticated text section; this
    # is where an altered t_addr/t_size or a wrong file offset fails closed.
    guest_to_file_offset(identity, continuation_entry_pc, header_size=header_size)

    t_addr = identity.t_addr
    text_end = t_addr + identity.t_size

    def read_word(address: int) -> int:
        return read_authenticated_word(
            identity, address, file_bytes=file_bytes or None, header_size=header_size
        )

    result = frontier_engine.analyze(read_word, t_addr, text_end, continuation_entry_pc)
    reachable = sorted(result["reachable_addresses"])
    records_by_address = {rec["address"]: rec for rec in result["records"]}
    delay_by_owner = {item["owner"]: item["delay"] for item in result["delay_slots"]}

    provenance: dict[int, MainExeProvenance] = {}
    for pc in reachable:
        file_offset = guest_to_file_offset(identity, pc, header_size=header_size)
        provenance[pc] = MainExeProvenance(
            guest_pc=pc,
            payload_offset=pc - t_addr,
            file_offset=file_offset,
            mainexe_file_sha256=identity.file_sha256,
            mainexe_payload_sha256=identity.payload_sha256,
            t_addr=t_addr,
            t_size=identity.t_size,
        )
    for owner, delay in delay_by_owner.items():
        if delay not in records_by_address:
            raise MainExeAuthError(
                "MAINEXE_DELAY_SLOT_RECORD_MISSING",
                f"owner=0x{owner:08x} delay=0x{delay:08x}",
            )

    return MainExeAnalysis(
        identity=identity,
        file_sha256=identity.file_sha256,
        payload_sha256=identity.payload_sha256,
        file_bytes=file_bytes or b"",
        frontier=result,
        records_by_address=records_by_address,
        delay_by_owner=delay_by_owner,
        provenance=provenance,
        continuation_entry_pc=continuation_entry_pc,
    )


def _hex32(value: int) -> str:
    return f"0x{value:08x}"


def private_mapping_records(analysis: MainExeAnalysis) -> list[dict[str, Any]]:
    """Full private map (contains the authenticated source word; never public)."""
    entries: list[dict[str, Any]] = []
    for index, pc in enumerate(sorted(analysis.provenance)):
        raw = analysis.records_by_address[pc]
        word = analysis.read_word(pc)
        entries.append({
            "index": index,
            "guest_pc": _hex32(pc),
            "file_offset": analysis.provenance[pc].file_offset,
            "payload_offset": analysis.provenance[pc].payload_offset,
            "authenticated_source_word": f"0x{word:08x}",
            "decoded_record": {
                "op": raw.get("op"),
                "operands": raw.get("operands") or {},
                "control_flow": bool(raw.get("control_flow")),
                "terminator": raw.get("terminator"),
                "link": bool(raw.get("link")),
                "decode_class": raw.get("decode_class"),
            },
            "provenance_digest": analysis.provenance[pc].digest(),
        })
    return entries


def public_mapping_document(
    analysis: MainExeAnalysis,
    *,
    title_continuation: dict[str, Any],
) -> dict[str, Any]:
    """Public-safe main-EXE authentication document (hashes/counts/addresses only)."""
    order = sorted(analysis.provenance)
    ops = sorted({str(analysis.records_by_address[pc].get("op")) for pc in order})
    return {
        "schema": "openrecomp-phase17-mainexe-mapping-v1",
        "stage": "P17-05R",
        "source_artifact": {
            "fixture_member": MAINEXE_FIXTURE_MEMBER,
            "file_sha256": analysis.file_sha256,
            "payload_sha256": analysis.payload_sha256,
            "file_size": analysis.identity.file_size,
            "header": {
                "magic": analysis.identity.magic.decode("ascii"),
                "entry_pc": _hex32(analysis.identity.pc0),
                "gp0": _hex32(analysis.identity.gp0),
                "t_addr": _hex32(analysis.identity.t_addr),
                "t_size": analysis.identity.t_size,
                "text_end": _hex32(analysis.identity.t_addr + analysis.identity.t_size),
                "header_size": HEADER_SIZE,
            },
        },
        "mapping": {
            "rule": "file_offset = header_size + (guest_addr - t_addr)",
            "continuation_entry_pc": _hex32(analysis.continuation_entry_pc),
            "continuation_entry_file_offset": guest_to_file_offset(
                analysis.identity, analysis.continuation_entry_pc
            ),
            "record_count": len(order),
        },
        "title_continuation": title_continuation,
        "records": [
            {
                "guest_pc": _hex32(pc),
                "file_offset": analysis.provenance[pc].file_offset,
                "payload_offset": analysis.provenance[pc].payload_offset,
                "op": analysis.records_by_address[pc].get("op"),
                "provenance_digest": analysis.provenance[pc].digest(),
            }
            for pc in order
        ],
        "reachable_op_vocabulary": ops,
        "reachable_op_vocabulary_count": len(ops),
        "reachable_address_count": len(order),
        "reachable_first_pc": _hex32(order[0]) if order else None,
        "reachable_last_pc": _hex32(order[-1]) if order else None,
        "private_mapping_sha256": _sha256_bytes(
            json.dumps(private_mapping_records(analysis), sort_keys=True).encode("utf-8")
        ),
    }
