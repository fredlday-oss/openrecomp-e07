#!/usr/bin/env python3
"""SM83 frontend: control flow + lowering into normalized IR V1 (P1-13).

Converts a bounded synthetic SM83 code region into architecture-neutral
normalized IR V1 using the shared scaffolding
(`openrecomp/frontends/scaffold.py`) and the documented decode + state model
(`adapters/sm83.py`). The independent machine-code reference semantics live
in `tools/sm83_reference_v1.py` (P1-12); the P1-13 differential proof runs the
same fixture through both and requires identical final state.

Control-flow model (documented SM83 behaviour):

- one IR function per converted program region (the guest stack is modelled
  in guest memory, exactly like hardware: CALL/RST push the 16-bit return
  address high-byte-first at SP-2/SP-1; RET pops it);
- static targets (jp/jr/call/rst) become `jump`/`branch` terminators to the
  leader block at that guest address (targets outside the declared region or
  the decoded stream fail closed);
- `ret`, `reti`, `jp (hl)` become `indirect_jump` terminators whose candidate
  set is every block of the function;
- conditional forms branch on the documented flag bits of F;
- HALT and STOP terminate the converted program by setting `platform:halted`
  and returning (the reference stops identically, so final state compares);
- EI/DI lower to `platform:ime` writes; the documented one-instruction EI
  delay is only observable through interrupt servicing, which is platform
  behaviour (P1-14), so differential fixtures exclude EI/DI (documented in
  the report);
- a leader target that lands inside an instruction (or an instruction that
  overlaps the region boundary) raises `SM83FrontendError` — fail closed;
- optional `meta["data_ranges"]` declares `[start, end)` spans of documented
  non-code data (e.g. the cartridge header fields at 0x0104..0x014F): bytes
  inside a span are never decoded, and control flow may never target or fall
  through into a span (fail closed); without the key, behaviour is unchanged;
- every guest address is carried zero-extended in i32 per the frontend
  contract's narrow-address rule; all 16-bit arithmetic wraps in i16.

The frontend is single-pass deterministic: identical fixture bytes produce
byte-identical IR/sidecar/report.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from adapters import sm83  # noqa: E402
from adapters.sm83 import SM83Error, decode_full, is_control_flow  # noqa: E402
from openrecomp.frontends.scaffold import IRBuilder, ScaffoldError  # noqa: E402

FRONTEND_VERSION = "1.0.0"
IR_VERSION = "1.0.0"

COND_MASK = {"nz": 0x80, "z": 0x80, "nc": 0x10, "c": 0x10}
COND_NEGATE = {"nz": True, "z": False, "nc": True, "c": False}

CONTROL_OPS = frozenset(
    {"jp", "jr", "call", "ret", "reti", "rst", "jp_hl", "halt", "stop"}
)
UNCONDITIONAL_NO_FALLTHROUGH = frozenset({"jp", "jr", "call", "ret", "reti", "rst", "jp_hl"})


class SM83FrontendError(ValueError):
    """Fail-closed frontend rejection."""


class _Context:
    def __init__(self, builder: IRBuilder, meta: dict, memory_image: bytes) -> None:
        self.builder = builder
        self.meta = meta
        self.code = memory_image
        self.counter = 0

    def tmp(self, tag: str) -> str:
        self.counter += 1
        return f"%t{self.counter}_{tag}"


class _Cfg:
    def __init__(self, instructions: dict[int, dict], leaders: set[int]) -> None:
        self.instructions = instructions
        self.leaders = leaders
        self.block_by_address: dict[int, str] = {}

    def block_id(self, address: int) -> str:
        block_id = self.block_by_address.get(address)
        if block_id is None:
            raise SM83FrontendError(f"0x{address:x}: control-flow target is not a decoded block leader")
        return block_id


def _validated_data_ranges(meta: dict, start: int, end: int) -> list[tuple[int, int]]:
    """Validate optional declared data spans inside the code region.

    Real cartridge images interleave documented data with code (the header
    fields at 0x0104..0x014F are data, not instructions), so the platform
    layer may declare data spans. Rules (fail closed):

    - each range is a [start, end) pair of ints inside the code region;
    - ranges are sorted and non-overlapping;
    - no instruction is decoded inside a range; control flow may never target
      or fall through into a range.

    Without the key, behaviour is unchanged (P1-13 contract).
    """
    ranges = meta.get("data_ranges")
    if ranges is None:
        return []
    if not isinstance(ranges, list):
        raise SM83FrontendError("data_ranges must be a list of [start, end) pairs")
    parsed: list[tuple[int, int]] = []
    for item in ranges:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise SM83FrontendError("each data range must be a [start, end) pair")
        range_start, range_end = item
        if (
            isinstance(range_start, bool)
            or isinstance(range_end, bool)
            or not isinstance(range_start, int)
            or not isinstance(range_end, int)
            or not (start <= range_start < range_end <= end)
        ):
            raise SM83FrontendError(f"data range [{range_start!r}, {range_end!r}) is invalid for [{start:#x}, {end:#x})")
        parsed.append((range_start, range_end))
    parsed.sort()
    for (s1, e1), (s2, e2) in zip(parsed, parsed[1:]):
        if s2 < e1:
            raise SM83FrontendError(f"data ranges overlap: [{s1:#x}, {e1:#x}) and [{s2:#x}, {e2:#x})")
    return parsed


def _inside_data(address: int, ranges: list[tuple[int, int]]) -> bool:
    return any(range_start <= address < range_end for range_start, range_end in ranges)


def _decode_region(code: bytes, meta: dict) -> tuple[dict[int, dict], set[int]]:
    """Linear decode of the bounded region with leader collection.

    Every byte of the declared region outside the declared data spans must
    decode as an instruction (fail closed). HALT/STOP end their block but do
    not stop the sweep, so vector tables before the entry address decode as
    ordinary blocks.
    """
    start = meta["region_start"]
    end = meta["region_end"]
    entry = meta["entry_address"]
    if not (0 <= start < end <= len(code)):
        raise SM83FrontendError("code region is outside the memory image")
    if not (start <= entry < end):
        raise SM83FrontendError("entry address is outside the code region")
    ranges = _validated_data_ranges(meta, start, end)
    if _inside_data(start, ranges):
        raise SM83FrontendError("the code region starts inside a declared data range")
    if _inside_data(entry, ranges):
        raise SM83FrontendError("the entry address lies inside a declared data range")

    instructions: dict[int, dict] = {}
    leaders: set[int] = {start, entry}
    spans: list[tuple[int, int]] = []
    cursor = start
    for range_start, range_end in ranges:
        if range_start > cursor:
            spans.append((cursor, range_start))
        cursor = range_end
    if cursor < end:
        spans.append((cursor, end))
    for span_start, span_end in spans:
        pc = span_start
        while pc < span_end:
            try:
                insn = decode_full(code, pc)
            except SM83Error as exc:
                raise SM83FrontendError(f"decode rejected: {exc}") from exc
            instructions[pc] = insn
            if insn["op"] in CONTROL_OPS:
                for target in sm83.branch_targets(insn):
                    if not (start <= target < end):
                        raise SM83FrontendError(f"0x{pc:x}: control-flow target 0x{target:x} leaves the region")
                    if _inside_data(target, ranges):
                        raise SM83FrontendError(f"0x{pc:x}: control-flow target 0x{target:x} is inside a declared data range")
                    leaders.add(target)
                conditional = "cond" in insn
                needs_fallthrough = (
                    conditional
                    or insn["op"] in ("call", "rst")
                    or (insn["op"] not in UNCONDITIONAL_NO_FALLTHROUGH and insn["op"] not in ("halt", "stop"))
                )
                if needs_fallthrough:
                    fallthrough = pc + insn["length"]
                    if fallthrough >= end:
                        raise SM83FrontendError(f"0x{pc:x}: fallthrough leaves the region")
                    if _inside_data(fallthrough, ranges) or fallthrough == span_end and span_end < end:
                        raise SM83FrontendError(f"0x{pc:x}: fallthrough enters a declared data range")
                    leaders.add(fallthrough)
            pc += insn["length"]
            if pc > span_end:
                raise SM83FrontendError(
                    f"0x{pc - insn['length']:x}: instruction overlaps the code/data boundary at 0x{span_end:x}"
                )
    return instructions, leaders


def _build_cfg(instructions: dict[int, dict], leaders: set[int]) -> _Cfg:
    cfg = _Cfg(instructions, leaders)
    ordered = sorted(leaders)
    for index, leader in enumerate(ordered):
        cfg.block_by_address[leader] = f"b_{leader:04x}"
    return cfg


class _FunctionLowerer:
    """Lowers one program region into a single IR function."""

    def __init__(self, ctx: _Context, cfg: _Cfg, function, entry: int) -> None:
        self.ctx = ctx
        self.cfg = cfg
        self.builder = ctx.builder
        self.function = function
        self.blocks: dict[int, object] = {}
        self.helper_counter = 0
        ordered = [entry] + sorted(address for address in cfg.leaders if address != entry)
        self.ordered_leaders = ordered
        for address in ordered:
            self.blocks[address] = function.add_block(cfg.block_id(address), address)
        self.all_block_ids = [cfg.block_id(address) for address in ordered]

    # -- helpers --------------------------------------------------------
    def _helper_block(self, address: int):
        self.helper_counter += 1
        return self.function.add_block(f"b_{address:04x}_h{self.helper_counter}", address)

    def _r8(self, block, name: str) -> dict:
        ctx = self.ctx
        if name == "(hl)":
            address = self._pair16(block, "hl")
            address32 = self._address(block, address)
            result = ctx.tmp("mem")
            block.load(result, "i8", width_bits=8, signed=False, address=address32, alignment=1)
            return block.value(result)
        if name == "a":
            result = ctx.tmp("a")
            block.read_state(result, "cpu:a")
        else:
            result = ctx.tmp(name)
            block.read_state(result, f"cpu:{name}")
        return block.value(result)

    def _set_r8(self, block, name: str, value: dict) -> None:
        if name == "(hl)":
            address = self._address(block, self._pair16(block, "hl"))
            block.store(width_bits=8, address=address, value=value, alignment=1)
        else:
            block.write_state(f"cpu:{name}", value)

    def _pair16(self, block, name: str) -> dict:
        if name == "sp":
            result = self.ctx.tmp("sp")
            block.read_state(result, "cpu:sp")
            return block.value(result)
        high, low = sm83.PAIR_PARTS[name]
        high8 = self._r8(block, high)
        low8 = self._r8(block, low)
        high16 = self.ctx.tmp("hi16")
        low16 = self.ctx.tmp("lo16")
        block.cast(high16, "i16", "zext", high8)
        block.cast(low16, "i16", "zext", low8)
        shifted = self.ctx.tmp("hi_shl")
        block.binop(shifted, "i16", "shl", block.value(high16), block.const(8, "i16"))
        combined = self.ctx.tmp("pair")
        block.binop(combined, "i16", "or", block.value(shifted), block.value(low16))
        return block.value(combined)

    def _set_pair16(self, block, name: str, value16: dict) -> None:
        if name == "sp":
            block.write_state("cpu:sp", value16)
            return
        high, low = sm83.PAIR_PARTS[name]
        high8 = self.ctx.tmp("hi8")
        low8 = self.ctx.tmp("lo8")
        block.cast(high8, "i8", "trunc", block.value(self._shr16(block, value16, 8)))
        block.cast(low8, "i8", "trunc", value16)
        block.write_state(f"cpu:{high}", block.value(high8))
        block.write_state(f"cpu:{low}", block.value(low8))

    def _shr16(self, block, value16: dict, amount: int) -> str:
        result = self.ctx.tmp("shr")
        block.binop(result, "i16", "lshr", value16, block.const(amount, "i16"))
        return result

    def _address(self, block, value16: dict) -> dict:
        result = self.ctx.tmp("addr")
        block.zext_to_address(result, value16)
        return block.value(result)

    def _const8(self, block, value: int) -> dict:
        return block.const(value & 0xFF, "i8")

    def _const16(self, block, value: int) -> dict:
        return block.const(value & 0xFFFF, "i16")

    def _bool(self, block, value8: dict) -> dict:
        """i8 -> i1 via != 0."""
        result = self.ctx.tmp("bool")
        block.compare(result, "ne", value8, self._const8(block, 0))
        return block.value(result)

    def _trunc_i1(self, block, value8: dict) -> dict:
        result = self.ctx.tmp("bit")
        block.cast(result, "i1", "trunc", value8)
        return block.value(result)

    def _zext_i8(self, block, value_i1: dict) -> dict:
        result = self.ctx.tmp("z")
        block.cast(result, "i8", "zext", value_i1)
        return block.value(result)

    def _shl8(self, block, value8: dict, amount: int) -> str:
        result = self.ctx.tmp("shl")
        block.binop(result, "i8", "shl", value8, self._const8(block, amount))
        return result

    def _assemble_flags(self, block, z: dict, n: dict, h: dict, c: dict, keep: dict) -> None:
        ctx = self.ctx
        z8 = ctx.tmp("fz")
        n8 = ctx.tmp("fn")
        h8 = ctx.tmp("fh")
        c8 = ctx.tmp("fc")
        block.cast(z8, "i8", "zext", z)
        block.cast(n8, "i8", "zext", n)
        block.cast(h8, "i8", "zext", h)
        block.cast(c8, "i8", "zext", c)
        zs = self._shl8(block, block.value(z8), 7)
        ns = self._shl8(block, block.value(n8), 6)
        hs = self._shl8(block, block.value(h8), 5)
        cs = self._shl8(block, block.value(c8), 4)
        zn = ctx.tmp("fzn")
        hc = ctx.tmp("fhc")
        allbits = ctx.tmp("fbits")
        block.binop(zn, "i8", "or", block.value(zs), block.value(ns))
        block.binop(hc, "i8", "or", block.value(hs), block.value(cs))
        block.binop(allbits, "i8", "or", block.value(zn), block.value(hc))
        final = ctx.tmp("fnew")
        block.binop(final, "i8", "or", block.value(allbits), keep)
        block.write_state("cpu:f", block.value(final))

    def _set_flags(self, block, z: dict, n: dict, h: dict, c: dict) -> None:
        self._assemble_flags(block, z, n, h, c, self._const8(block, 0))

    def _const_i1(self, block, value: bool) -> dict:
        result = self.ctx.tmp("ci1")
        block.const_result(result, "i1", 1 if value else 0)
        return block.value(result)

    def _read_f(self, block) -> dict:
        result = self.ctx.tmp("f")
        block.read_state(result, "cpu:f")
        return block.value(result)

    def _flag_bit(self, block, mask: int) -> dict:
        masked = self.ctx.tmp("fmask")
        block.binop(masked, "i8", "and", self._read_f(block), self._const8(block, mask))
        return self._bool(block, block.value(masked))

    def _condition(self, block, cond: str) -> dict:
        value = self._flag_bit(block, COND_MASK[cond])
        if not COND_NEGATE[cond]:
            return value
        result = self.ctx.tmp("cond")
        block.compare(result, "eq", value, self._const_i1(block, False))
        return block.value(result)

    def _push(self, block, value16: dict) -> None:
        ctx = self.ctx
        sp = self._pair16(block, "sp")
        sp1 = ctx.tmp("sp1")
        sp2 = ctx.tmp("sp2")
        block.binop(sp1, "i16", "sub", sp, self._const16(block, 1))
        high8 = ctx.tmp("hi8")
        low8 = ctx.tmp("lo8")
        block.cast(high8, "i8", "trunc", block.value(self._shr16(block, value16, 8)))
        block.cast(low8, "i8", "trunc", value16)
        block.store(width_bits=8, address=self._address(block, block.value(sp1)), value=block.value(high8), alignment=1)
        block.binop(sp2, "i16", "sub", block.value(sp1), self._const16(block, 1))
        block.store(width_bits=8, address=self._address(block, block.value(sp2)), value=block.value(low8), alignment=1)
        block.write_state("cpu:sp", block.value(sp2))

    def _pop(self, block) -> dict:
        ctx = self.ctx
        sp = self._pair16(block, "sp")
        sp1 = ctx.tmp("sp1")
        sp2 = ctx.tmp("sp2")
        block.binop(sp1, "i16", "add", sp, self._const16(block, 1))
        lo = ctx.tmp("lo")
        hi = ctx.tmp("hi")
        block.load(lo, "i8", width_bits=8, signed=False, address=self._address(block, sp), alignment=1)
        block.load(hi, "i8", width_bits=8, signed=False, address=self._address(block, block.value(sp1)), alignment=1)
        block.binop(sp2, "i16", "add", block.value(sp1), self._const16(block, 1))
        block.write_state("cpu:sp", block.value(sp2))
        hi16 = ctx.tmp("hi16")
        lo16 = ctx.tmp("lo16")
        block.cast(hi16, "i16", "zext", block.value(hi))
        block.cast(lo16, "i16", "zext", block.value(lo))
        shifted = ctx.tmp("hi_shl")
        block.binop(shifted, "i16", "shl", block.value(hi16), self._const16(block, 8))
        combined = ctx.tmp("pop16")
        block.binop(combined, "i16", "or", block.value(shifted), block.value(lo16))
        return block.value(combined)

    # -- 8-bit ALU (i16-precise flags) ----------------------------------
    def _alu16(self, block, kind: str, operand8: dict):
        """ADD/ADC/SUB/SBC/CP with exact Z/N/H/C via i16 arithmetic."""
        ctx = self.ctx
        a = self._r8(block, "a")
        a16 = ctx.tmp("a16")
        v16 = ctx.tmp("v16")
        block.cast(a16, "i16", "zext", a)
        block.cast(v16, "i16", "zext", operand8)
        a_low = ctx.tmp("alow")
        v_low = ctx.tmp("vlow")
        block.cast(a_low, "i8", "trunc", block.value(a16))
        block.cast(v_low, "i8", "trunc", block.value(v16))
        a_nib = ctx.tmp("anib")
        v_nib = ctx.tmp("vnib")
        block.binop(a_nib, "i8", "and", block.value(a_low), self._const8(block, 0x0F))
        block.binop(v_nib, "i8", "and", block.value(v_low), self._const8(block, 0x0F))
        nib16a = ctx.tmp("nib16a")
        nib16b = ctx.tmp("nib16b")
        block.cast(nib16a, "i16", "zext", block.value(a_nib))
        block.cast(nib16b, "i16", "zext", block.value(v_nib))

        if kind in ("add", "adc", "sub", "sbc", "cp"):
            carry = self._flag_bit(block, sm83.FLAG_C)
            carry16 = ctx.tmp("c16")
            block.cast(carry16, "i16", "zext", carry)
        if kind in ("add", "adc"):
            nib_sum = ctx.tmp("nibsum")
            block.binop(nib_sum, "i16", "add", block.value(nib16a), block.value(nib16b))
            if kind == "adc":
                nib_sum2 = ctx.tmp("nibsum2")
                block.binop(nib_sum2, "i16", "add", block.value(nib_sum), block.value(carry16))
            else:
                nib_sum2 = nib_sum
            sum16 = ctx.tmp("sum16")
            block.binop(sum16, "i16", "add", block.value(a16), block.value(v16))
            if kind == "adc":
                sum16b = ctx.tmp("sum16b")
                block.binop(sum16b, "i16", "add", block.value(sum16), block.value(carry16))
            else:
                sum16b = sum16
            h = ctx.tmp("hflag")
            c = ctx.tmp("cflag")
            block.compare(h, "ugt", block.value(nib_sum2), block.const(0x0F, "i16"))
            block.compare(c, "ugt", block.value(sum16b), block.const(0xFF, "i16"))
            result8 = ctx.tmp("res8")
            block.cast(result8, "i8", "trunc", block.value(sum16b))
            z = ctx.tmp("zflag")
            block.compare(z, "eq", block.value(result8), self._const8(block, 0))
            self._set_flags(block, block.value(z), self._const_i1(block, False), block.value(h), block.value(c))
            if kind != "cp":
                block.write_state("cpu:a", block.value(result8))
            return
        if kind in ("sub", "sbc", "cp"):
            nib_diff = ctx.tmp("nibdiff")
            block.binop(nib_diff, "i16", "sub", block.value(nib16a), block.value(nib16b))
            if kind == "sbc":
                nib_diff2 = ctx.tmp("nibdiff2")
                block.binop(nib_diff2, "i16", "sub", block.value(nib_diff), block.value(carry16))
            else:
                nib_diff2 = nib_diff
            diff16 = ctx.tmp("diff16")
            block.binop(diff16, "i16", "sub", block.value(a16), block.value(v16))
            if kind == "sbc":
                diff16b = ctx.tmp("diff16b")
                block.binop(diff16b, "i16", "sub", block.value(diff16), block.value(carry16))
            else:
                diff16b = diff16
            h = ctx.tmp("hflag")
            c = ctx.tmp("cflag")
            block.compare(h, "slt", block.value(nib_diff2), block.const(0, "i16"))
            block.compare(c, "slt", block.value(diff16b), block.const(0, "i16"))
            result8 = ctx.tmp("res8")
            block.cast(result8, "i8", "trunc", block.value(diff16b))
            z = ctx.tmp("zflag")
            block.compare(z, "eq", block.value(result8), self._const8(block, 0))
            self._set_flags(block, block.value(z), self._const_i1(block, True), block.value(h), block.value(c))
            if kind != "cp":
                block.write_state("cpu:a", block.value(result8))
            return
        raise SM83FrontendError(f"unsupported ALU kind {kind}")

    # -- CB-page ---------------------------------------------------------
    def _shift_op(self, block, insn: dict, op: str) -> None:
        ctx = self.ctx
        value = self._r8(block, insn["r"])
        result = ctx.tmp("res")
        carry_out = ctx.tmp("cout")
        carry_in = self._flag_bit(block, sm83.FLAG_C)
        if op == "rlc":
            high = ctx.tmp("hi")
            block.binop(high, "i8", "lshr", value, self._const8(block, 7))
            block.cast(carry_out, "i1", "trunc", block.value(high))
            shifted = self._shl8(block, value, 1)
            block.binop(result, "i8", "or", block.value(shifted), block.value(high))
        elif op == "rrc":
            low = ctx.tmp("lo")
            block.binop(low, "i8", "and", value, self._const8(block, 1))
            block.cast(carry_out, "i1", "trunc", block.value(low))
            shifted = ctx.tmp("shr")
            block.binop(shifted, "i8", "lshr", value, self._const8(block, 1))
            low7 = self._shl8(block, block.value(low), 7)
            block.binop(result, "i8", "or", block.value(shifted), block.value(low7))
        elif op == "rl":
            high = ctx.tmp("hi")
            block.binop(high, "i8", "lshr", value, self._const8(block, 7))
            block.cast(carry_out, "i1", "trunc", block.value(high))
            shifted = self._shl8(block, value, 1)
            cin8 = self._zext_i8(block, carry_in)
            block.binop(result, "i8", "or", block.value(shifted), cin8)
        elif op == "rr":
            low = ctx.tmp("lo")
            block.binop(low, "i8", "and", value, self._const8(block, 1))
            block.cast(carry_out, "i1", "trunc", block.value(low))
            shifted = ctx.tmp("shr")
            block.binop(shifted, "i8", "lshr", value, self._const8(block, 1))
            cin7 = self._shl8(block, self._zext_i8(block, carry_in), 7)
            block.binop(result, "i8", "or", block.value(shifted), block.value(cin7))
        elif op == "sla":
            high = ctx.tmp("hi")
            block.binop(high, "i8", "lshr", value, self._const8(block, 7))
            block.cast(carry_out, "i1", "trunc", block.value(high))
            block.binop(result, "i8", "shl", value, self._const8(block, 1))
        elif op == "sra":
            low = ctx.tmp("lo")
            block.binop(low, "i8", "and", value, self._const8(block, 1))
            block.cast(carry_out, "i1", "trunc", block.value(low))
            block.binop(result, "i8", "ashr", value, self._const8(block, 1))
        elif op == "srl":
            low = ctx.tmp("lo")
            block.binop(low, "i8", "and", value, self._const8(block, 1))
            block.cast(carry_out, "i1", "trunc", block.value(low))
            block.binop(result, "i8", "lshr", value, self._const8(block, 1))
        elif op == "swap":
            carry_out = ctx.tmp("cout")
            block.const_result(carry_out, "i1", 0)
            low = ctx.tmp("lo")
            high = ctx.tmp("hi")
            block.binop(low, "i8", "and", value, self._const8(block, 0x0F))
            block.binop(high, "i8", "lshr", value, self._const8(block, 4))
            low4 = self._shl8(block, block.value(low), 4)
            block.binop(result, "i8", "or", block.value(low4), block.value(high))
        else:
            raise SM83FrontendError(f"unsupported CB op {op}")
        self._set_r8(block, insn["r"], block.value(result))
        z = ctx.tmp("z")
        block.compare(z, "eq", block.value(result), self._const8(block, 0))
        self._set_flags(block, block.value(z), self._const_i1(block, False), self._const_i1(block, False), block.value(carry_out))

    # -- instruction lowering -------------------------------------------
    def lower_instruction(self, block, insn: dict) -> None:
        op = insn["op"]
        ctx = self.ctx
        if op == "nop":
            return
        if op == "ld":
            self._lower_ld(block, insn)
        elif op == "ldh":
            self._lower_ldh(block, insn)
        elif op == "inc":
            self._lower_incdec(block, insn, increment=True)
        elif op == "dec":
            self._lower_incdec(block, insn, increment=False)
        elif op in ("add", "adc", "sub", "sbc", "and", "xor", "or", "cp"):
            if op in ("and", "xor", "or"):
                self._lower_logical(block, insn, op)
            else:
                operand = self._r8(block, insn["r"]) if "r" in insn else self._const8(block, insn["imm8"])
                self._alu16(block, op, operand)
        elif op == "add_hl":
            self._lower_add_hl(block, insn)
        elif op == "add_sp":
            self._lower_add_sp(block, insn)
        elif op == "ld_hl_sp":
            self._lower_ld_hl_sp(block, insn)
        elif op == "ld_sp_hl":
            block.write_state("cpu:sp", self._pair16(block, "hl"))
        elif op == "push":
            self._push(block, self._pair16(block, insn["pair"]))
        elif op == "pop":
            value = self._pop(block)
            if insn["pair"] == "af":
                high8 = ctx.tmp("hi8")
                low8 = ctx.tmp("lo8")
                block.cast(high8, "i8", "trunc", block.value(self._shr16(block, value, 8)))
                block.cast(low8, "i8", "trunc", value)
                masked = ctx.tmp("fmask")
                block.binop(masked, "i8", "and", block.value(low8), self._const8(block, sm83.FLAG_WRITE_MASK))
                block.write_state("cpu:a", block.value(high8))
                block.write_state("cpu:f", block.value(masked))
            else:
                self._set_pair16(block, insn["pair"], value)
        elif op in ("rlca", "rrca", "rla", "rra"):
            self._lower_rotate_a(block, op)
        elif op == "daa":
            self._lower_daa(block)
        elif op == "cpl":
            a = ctx.tmp("cpla")
            block.binop(a, "i8", "xor", self._r8(block, "a"), self._const8(block, 0xFF))
            block.write_state("cpu:a", block.value(a))
            kept = ctx.tmp("kept")
            block.binop(kept, "i8", "and", self._read_f(block), self._const8(block, 0x90))
            zn = ctx.tmp("zn")
            block.binop(zn, "i8", "or", block.value(kept), self._const8(block, 0x60))
            block.write_state("cpu:f", block.value(zn))
        elif op == "scf":
            kept = ctx.tmp("kept")
            block.binop(kept, "i8", "and", self._read_f(block), self._const8(block, sm83.FLAG_Z))
            f = ctx.tmp("f")
            block.binop(f, "i8", "or", block.value(kept), self._const8(block, sm83.FLAG_C))
            block.write_state("cpu:f", block.value(f))
        elif op == "ccf":
            kept = ctx.tmp("kept")
            block.binop(kept, "i8", "and", self._read_f(block), self._const8(block, sm83.FLAG_Z))
            c = self._flag_bit(block, sm83.FLAG_C)
            neg = ctx.tmp("negc")
            block.compare(neg, "eq", c, self._const_i1(block, False))
            c8 = self._zext_i8(block, block.value(neg))
            c4 = self._shl8(block, c8, 4)
            f = ctx.tmp("f")
            block.binop(f, "i8", "or", block.value(kept), block.value(c4))
            block.write_state("cpu:f", block.value(f))
        elif op == "bit":
            value = self._r8(block, insn["r"])
            mask = ctx.tmp("mask")
            block.binop(mask, "i8", "and", value, self._const8(block, 1 << insn["n"]))
            z = ctx.tmp("z")
            block.compare(z, "eq", block.value(mask), self._const8(block, 0))
            keep_c = ctx.tmp("keepc")
            block.binop(keep_c, "i8", "and", self._read_f(block), self._const8(block, sm83.FLAG_C))
            self._assemble_flags(block, block.value(z), self._const_i1(block, False), self._const_i1(block, True), self._const_i1(block, False), block.value(keep_c))
        elif op in ("res", "set"):
            value = self._r8(block, insn["r"])
            result = ctx.tmp("res")
            if op == "res":
                mask = self._const8(block, (~(1 << insn["n"])) & 0xFF)
                block.binop(result, "i8", "and", value, mask)
            else:
                mask = self._const8(block, 1 << insn["n"])
                block.binop(result, "i8", "or", value, mask)
            self._set_r8(block, insn["r"], block.value(result))
        elif op in ("rlc", "rrc", "rl", "rr", "sla", "sra", "srl", "swap"):
            self._shift_op(block, insn, op)
        elif op == "di":
            block.write_state("platform:ime", self._const_i1(block, False))
        elif op == "ei":
            block.write_state("platform:ime", self._const_i1(block, True))
        else:
            raise SM83FrontendError(f"0x{insn['address']:x}: {op} cannot be lowered as a simple instruction")

    def _lower_ld(self, block, insn: dict) -> None:
        ctx = self.ctx
        dst = insn["dst"]
        if dst == "sp":
            block.write_state("cpu:sp", self._const16(block, insn["imm16"]))
        elif dst in ("bc", "de", "hl"):
            self._set_pair16(block, dst, self._const16(block, insn["imm16"]))
        elif dst == "(a16)":
            if insn.get("src") == "sp":
                address = block.const(insn["a16"], "i32")
                sp16 = self._pair16(block, "sp")
                high8 = ctx.tmp("hi8")
                low8 = ctx.tmp("lo8")
                block.cast(high8, "i8", "trunc", block.value(self._shr16(block, sp16, 8)))
                block.cast(low8, "i8", "trunc", sp16)
                addr1 = ctx.tmp("addr1")
                block.binop(addr1, "i32", "add", address, block.const(1, "i32"))
                block.store(width_bits=8, address=address, value=block.value(low8), alignment=1)
                block.store(width_bits=8, address=block.value(addr1), value=block.value(high8), alignment=1)
            else:
                # documented 8-bit store `ld (a16), a`
                address = block.const(insn["a16"], "i32")
                block.store(width_bits=8, address=address, value=self._r8(block, "a"), alignment=1)
        elif dst in ("(bc)", "(de)", "(hl)", "(hl+)", "(hl-)"):
            value = self._const8(block, insn["imm8"]) if "imm8" in insn else self._r8(block, insn["src"])
            base = self._pair16(block, "hl") if dst.startswith("(hl") else self._pair16(block, dst[1:3])
            block.store(width_bits=8, address=self._address(block, base), value=value, alignment=1)
            if dst in ("(hl+)", "(hl-)"):
                updated = ctx.tmp("hl2")
                block.binop(updated, "i16", "add" if dst == "(hl+)" else "sub", base, self._const16(block, 1))
                self._set_pair16(block, "hl", block.value(updated))
        elif insn.get("src") == "(a16)":
            address = block.const(insn["a16"], "i32")
            low = ctx.tmp("lo")
            block.load(low, "i8", width_bits=8, signed=False, address=address, alignment=1)
            self._set_r8(block, dst, block.value(low))
        elif insn.get("src") in ("(bc)", "(de)", "(hl)", "(hl+)", "(hl-)"):
            base = self._pair16(block, "hl") if insn["src"].startswith("(hl") else self._pair16(block, insn["src"][1:3])
            value = ctx.tmp("v")
            block.load(value, "i8", width_bits=8, signed=False, address=self._address(block, base), alignment=1)
            self._set_r8(block, dst, block.value(value))
            if insn["src"] in ("(hl+)", "(hl-)"):
                updated = ctx.tmp("hl2")
                block.binop(updated, "i16", "add" if insn["src"] == "(hl+)" else "sub", base, self._const16(block, 1))
                self._set_pair16(block, "hl", block.value(updated))
        elif "imm8" in insn:
            self._set_r8(block, dst, self._const8(block, insn["imm8"]))
        else:
            self._set_r8(block, dst, self._r8(block, insn["src"]))

    def _lower_ldh(self, block, insn: dict) -> None:
        ctx = self.ctx
        if "a8" in insn:
            addr16 = ctx.tmp("addr16")
            block.binop(addr16, "i16", "or", block.const(0xFF00, "i16"), self._const16(block, insn["a8"]))
        else:
            c16 = ctx.tmp("c16")
            block.cast(c16, "i16", "zext", self._r8(block, "c"))
            addr16 = ctx.tmp("addr16")
            block.binop(addr16, "i16", "or", block.const(0xFF00, "i16"), block.value(c16))
        address = self._address(block, block.value(addr16))
        if insn["dir"] == "store":
            block.store(width_bits=8, address=address, value=self._r8(block, "a"), alignment=1)
        else:
            value = ctx.tmp("v")
            block.load(value, "i8", width_bits=8, signed=False, address=address, alignment=1)
            block.write_state("cpu:a", block.value(value))

    def _lower_incdec(self, block, insn: dict, *, increment: bool) -> None:
        ctx = self.ctx
        name = insn["r"]
        if name in ("bc", "de", "hl", "sp"):
            value = self._pair16(block, name)
            updated = ctx.tmp("v2")
            block.binop(updated, "i16", "add" if increment else "sub", value, self._const16(block, 1))
            self._set_pair16(block, name, block.value(updated))
            return
        before = self._r8(block, name)
        updated = ctx.tmp("v2")
        block.binop(updated, "i8", "add" if increment else "sub", before, self._const8(block, 1))
        self._set_r8(block, name, block.value(updated))
        z = ctx.tmp("z")
        h = ctx.tmp("h")
        block.compare(z, "eq", block.value(updated), self._const8(block, 0))
        nib = ctx.tmp("nib")
        block.binop(nib, "i8", "and", before, self._const8(block, 0x0F))
        block.compare(h, "eq", block.value(nib), self._const8(block, 0x0F if increment else 0x00))
        keep_c = ctx.tmp("keepc")
        block.binop(keep_c, "i8", "and", self._read_f(block), self._const8(block, sm83.FLAG_C))
        n_flag = self._const_i1(block, False) if increment else self._const_i1(block, True)
        self._assemble_flags(block, block.value(z), n_flag, block.value(h), self._const_i1(block, False), block.value(keep_c))

    def _lower_logical(self, block, insn: dict, op: str) -> None:
        ctx = self.ctx
        a = self._r8(block, "a")
        operand = self._r8(block, insn["r"]) if "r" in insn else self._const8(block, insn["imm8"])
        result = ctx.tmp("res")
        block.binop(result, "i8", op, a, operand)
        block.write_state("cpu:a", block.value(result))
        z = ctx.tmp("z")
        block.compare(z, "eq", block.value(result), self._const8(block, 0))
        h = self._const_i1(block, True) if op == "and" else self._const_i1(block, False)
        self._set_flags(block, block.value(z), self._const_i1(block, False), h, self._const_i1(block, False))

    def _lower_add_hl(self, block, insn: dict) -> None:
        ctx = self.ctx
        hl = self._pair16(block, "hl")
        value = self._pair16(block, insn["pair"])
        hl_low11 = ctx.tmp("hl11")
        v_low11 = ctx.tmp("v11")
        block.binop(hl_low11, "i16", "and", hl, self._const16(block, 0x0FFF))
        block.binop(v_low11, "i16", "and", value, self._const16(block, 0x0FFF))
        low_sum = ctx.tmp("lowsum")
        block.binop(low_sum, "i16", "add", block.value(hl_low11), block.value(v_low11))
        h = ctx.tmp("h")
        block.compare(h, "ugt", block.value(low_sum), self._const16(block, 0x0FFF))
        total = ctx.tmp("total")
        block.binop(total, "i16", "add", hl, value)
        c = ctx.tmp("c")
        block.compare(c, "ult", block.value(total), hl)
        self._set_pair16(block, "hl", block.value(total))
        keep_z = ctx.tmp("keepz")
        block.binop(keep_z, "i8", "and", self._read_f(block), self._const8(block, sm83.FLAG_Z))
        self._assemble_flags(block, self._const_i1(block, False), self._const_i1(block, False), block.value(h), block.value(c), block.value(keep_z))

    def _add_sp_flags(self, block, sp: dict, rel16: dict) -> None:
        ctx = self.ctx
        sp8 = ctx.tmp("sp8")
        r8 = ctx.tmp("r8")
        block.cast(sp8, "i8", "trunc", sp)
        block.cast(r8, "i8", "trunc", rel16)
        sp_nib = ctx.tmp("spnib")
        r_nib = ctx.tmp("rnib")
        block.binop(sp_nib, "i8", "and", block.value(sp8), self._const8(block, 0x0F))
        block.binop(r_nib, "i8", "and", block.value(r8), self._const8(block, 0x0F))
        nib16a = ctx.tmp("nib16a")
        nib16b = ctx.tmp("nib16b")
        block.cast(nib16a, "i16", "zext", block.value(sp_nib))
        block.cast(nib16b, "i16", "zext", block.value(r_nib))
        low_a = ctx.tmp("low_a")
        low_b = ctx.tmp("low_b")
        block.cast(low_a, "i16", "zext", block.value(sp8))
        block.cast(low_b, "i16", "zext", block.value(r8))
        nib_sum = ctx.tmp("nibsum")
        low_sum = ctx.tmp("lowsum")
        block.binop(nib_sum, "i16", "add", block.value(nib16a), block.value(nib16b))
        block.binop(low_sum, "i16", "add", block.value(low_a), block.value(low_b))
        h = ctx.tmp("h")
        c = ctx.tmp("c")
        block.compare(h, "ugt", block.value(nib_sum), self._const16(block, 0x0F))
        block.compare(c, "ugt", block.value(low_sum), self._const16(block, 0xFF))
        self._set_flags(block, self._const_i1(block, False), self._const_i1(block, False), block.value(h), block.value(c))

    def _rel16(self, block, rel: int) -> dict:
        ctx = self.ctx
        result = ctx.tmp("rel16")
        block.const_result(result, "i16", rel & 0xFFFF)
        return block.value(result)

    def _lower_add_sp(self, block, insn: dict) -> None:
        ctx = self.ctx
        sp = self._pair16(block, "sp")
        rel16 = self._rel16(block, insn["rel"])
        self._add_sp_flags(block, sp, rel16)
        total = ctx.tmp("total")
        block.binop(total, "i16", "add", sp, rel16)
        block.write_state("cpu:sp", block.value(total))

    def _lower_ld_hl_sp(self, block, insn: dict) -> None:
        ctx = self.ctx
        sp = self._pair16(block, "sp")
        rel16 = self._rel16(block, insn["rel"])
        self._add_sp_flags(block, sp, rel16)
        total = ctx.tmp("total")
        block.binop(total, "i16", "add", sp, rel16)
        self._set_pair16(block, "hl", block.value(total))

    def _lower_rotate_a(self, block, op: str) -> None:
        ctx = self.ctx
        a = self._r8(block, "a")
        carry_in = self._flag_bit(block, sm83.FLAG_C)
        result = ctx.tmp("res")
        carry_out = ctx.tmp("cout")
        if op == "rlca":
            high = ctx.tmp("hi")
            block.binop(high, "i8", "lshr", a, self._const8(block, 7))
            block.cast(carry_out, "i1", "trunc", block.value(high))
            shifted = self._shl8(block, a, 1)
            block.binop(result, "i8", "or", block.value(shifted), block.value(high))
        elif op == "rrca":
            low = ctx.tmp("lo")
            block.binop(low, "i8", "and", a, self._const8(block, 1))
            block.cast(carry_out, "i1", "trunc", block.value(low))
            shifted = ctx.tmp("shr")
            block.binop(shifted, "i8", "lshr", a, self._const8(block, 1))
            low7 = self._shl8(block, block.value(low), 7)
            block.binop(result, "i8", "or", block.value(shifted), block.value(low7))
        elif op == "rla":
            high = ctx.tmp("hi")
            block.binop(high, "i8", "lshr", a, self._const8(block, 7))
            block.cast(carry_out, "i1", "trunc", block.value(high))
            shifted = self._shl8(block, a, 1)
            cin8 = self._zext_i8(block, carry_in)
            block.binop(result, "i8", "or", block.value(shifted), cin8)
        else:
            low = ctx.tmp("lo")
            block.binop(low, "i8", "and", a, self._const8(block, 1))
            block.cast(carry_out, "i1", "trunc", block.value(low))
            shifted = ctx.tmp("shr")
            block.binop(shifted, "i8", "lshr", a, self._const8(block, 1))
            cin7 = self._shl8(block, self._zext_i8(block, carry_in), 7)
            block.binop(result, "i8", "or", block.value(shifted), block.value(cin7))
        block.write_state("cpu:a", block.value(result))
        self._set_flags(block, self._const_i1(block, False), self._const_i1(block, False), self._const_i1(block, False), block.value(carry_out))

    def _lower_daa(self, block) -> None:
        ctx = self.ctx
        a = self._r8(block, "a")
        a16 = ctx.tmp("a16")
        block.cast(a16, "i16", "zext", a)
        c_flag = self._flag_bit(block, sm83.FLAG_C)
        n_flag = self._flag_bit(block, sm83.FLAG_N)
        h_flag = self._flag_bit(block, sm83.FLAG_H)
        gt99 = ctx.tmp("gt99")
        block.compare(gt99, "ugt", block.value(a16), self._const16(block, 0x99))
        c_or_99 = ctx.tmp("cor99")
        block.binop(c_or_99, "i1", "or", c_flag, block.value(gt99))
        low_nib = ctx.tmp("lownib")
        block.binop(low_nib, "i16", "and", block.value(a16), self._const16(block, 0x0F))
        gt9 = ctx.tmp("gt9")
        block.compare(gt9, "ugt", block.value(low_nib), self._const16(block, 0x09))
        h_or_9 = ctx.tmp("hor9")
        block.binop(h_or_9, "i1", "or", h_flag, block.value(gt9))
        add60 = ctx.tmp("add60")
        block.select(add60, "i16", block.value(c_or_99), self._const16(block, 0x60), self._const16(block, 0))
        step1 = ctx.tmp("step1")
        block.binop(step1, "i16", "add", block.value(a16), block.value(add60))
        add06 = ctx.tmp("add06")
        block.select(add06, "i16", block.value(h_or_9), self._const16(block, 0x06), self._const16(block, 0))
        add_result = ctx.tmp("addres")
        block.binop(add_result, "i16", "add", block.value(step1), block.value(add06))
        sub60 = ctx.tmp("sub60")
        block.select(sub60, "i16", c_flag, self._const16(block, 0x60), self._const16(block, 0))
        n_step1 = ctx.tmp("nstep1")
        block.binop(n_step1, "i16", "sub", block.value(a16), block.value(sub60))
        sub06 = ctx.tmp("sub06")
        block.select(sub06, "i16", h_flag, self._const16(block, 0x06), self._const16(block, 0))
        sub_result = ctx.tmp("subres")
        block.binop(sub_result, "i16", "sub", block.value(n_step1), block.value(sub06))
        final16 = ctx.tmp("final16")
        block.select(final16, "i16", n_flag, block.value(sub_result), block.value(add_result))
        final8 = ctx.tmp("final8")
        block.cast(final8, "i8", "trunc", block.value(final16))
        block.write_state("cpu:a", block.value(final8))
        c_new = ctx.tmp("cnew")
        block.select(c_new, "i1", n_flag, c_flag, block.value(c_or_99))
        z = ctx.tmp("z")
        block.compare(z, "eq", block.value(final8), self._const8(block, 0))
        keep_n = ctx.tmp("keepn")
        block.binop(keep_n, "i8", "and", self._read_f(block), self._const8(block, sm83.FLAG_N))
        self._assemble_flags(block, block.value(z), self._const_i1(block, False), self._const_i1(block, False), block.value(c_new), block.value(keep_n))

    # -- terminators -----------------------------------------------------
    def lower_terminator(self, block, insn: dict) -> None:
        op = insn["op"]
        ctx = self.ctx
        next_pc = (insn["address"] + insn["length"]) & 0xFFFF
        if op == "halt":
            block.write_state("platform:halted", self._const_i1(block, True))
            block.ret()
        elif op == "stop":
            block.write_state("platform:halted", self._const_i1(block, True))
            block.ret()
        elif op == "jp":
            target = self.cfg.block_id(insn["target"])
            if "cond" in insn:
                cond = self._condition(block, insn["cond"])
                block.branch(cond, target, self.cfg.block_id(next_pc))
            else:
                block.jump(target)
        elif op == "jr":
            target = self.cfg.block_id(insn["target"])
            if "cond" in insn:
                cond = self._condition(block, insn["cond"])
                block.branch(cond, target, self.cfg.block_id(next_pc))
            else:
                block.jump(target)
        elif op == "call":
            if "cond" in insn:
                cond = self._condition(block, insn["cond"])
                helper = self._helper_block(insn["address"])
                block.branch(cond, helper.block_id, self.cfg.block_id(next_pc))
                self._push(helper, self._const16(helper, next_pc))
                helper.jump(self.cfg.block_id(insn["target"]))
            else:
                self._push(block, self._const16(block, next_pc))
                block.jump(self.cfg.block_id(insn["target"]))
        elif op == "rst":
            self._push(block, self._const16(block, next_pc))
            block.jump(self.cfg.block_id(insn["vector"]))
        elif op == "ret":
            if "cond" in insn:
                cond = self._condition(block, insn["cond"])
                helper = self._helper_block(insn["address"])
                block.branch(cond, helper.block_id, self.cfg.block_id(next_pc))
                target = self._pop(helper)
                address = self._address(helper, target)
                helper.indirect_jump(address, list(self.all_block_ids))
            else:
                target = self._pop(block)
                address = self._address(block, target)
                block.indirect_jump(address, list(self.all_block_ids))
        elif op == "reti":
            target = self._pop(block)
            address = self._address(block, target)
            block.indirect_jump(address, list(self.all_block_ids))
        elif op == "jp_hl":
            target = self._pair16(block, "hl")
            address = self._address(block, target)
            block.indirect_jump(address, list(self.all_block_ids))
        else:
            raise SM83FrontendError(f"0x{insn['address']:x}: {op} is not a documented SM83 terminator")


def convert(memory_image: bytes, meta: dict, contract: dict) -> tuple[dict, dict, dict]:
    if meta.get("architecture") != "sm83-gb":
        raise SM83FrontendError("frontend requires the sm83-gb architecture profile")
    if contract.get("memory", {}).get("oob_policy") != "deterministic fault":
        raise SM83FrontendError("host memory contract must fail closed")
    if contract.get("system", {}).get("wall_clock") or contract.get("system", {}).get("randomness"):
        raise SM83FrontendError("host contract must remain deterministic")
    if len(memory_image) != 1 << 16:
        raise SM83FrontendError("the SM83 memory image must be exactly 64 KiB")

    instructions, leaders = _decode_region(memory_image, meta)
    if not instructions:
        raise SM83FrontendError("the code region contains no instructions")
    undecoded = leaders - set(instructions)
    if undecoded:
        raise SM83FrontendError(
            "branch target outside the decoded stream: " + ", ".join(f"0x{a:x}" for a in sorted(undecoded))
        )
    cfg = _build_cfg(instructions, leaders)

    input_sha256 = hashlib.sha256(memory_image).hexdigest()
    builder = IRBuilder(
        module_id="openrecomp.sm83.synthetic.region-v1",
        architecture="sm83-gb",
        adapter="openrecomp.sm83-frontend-v1",
        address_bits=32,
        endianness="little",
        input_sha256=input_sha256,
        host_contract_version=contract["contract_version"],
    )
    for slot_id, type_name in sm83.STATE_SLOTS.items():
        builder.declare_state_slot(slot_id, type_name)
    builder.declare_state_slot("platform:ime", "i1")
    builder.declare_state_slot("platform:halted", "i1")

    function = builder.add_function("main", meta["entry_address"], return_type=None)
    ctx = _Context(builder, meta, memory_image)
    lowerer = _FunctionLowerer(ctx, cfg, function, meta["entry_address"])

    ordered = sorted(leaders)
    ranges = _validated_data_ranges(meta, meta["region_start"], meta["region_end"])
    for index, leader in enumerate(ordered):
        block = lowerer.blocks[leader]
        end = ordered[index + 1] if index + 1 < len(ordered) else meta["region_end"]
        for range_start, _range_end in ranges:
            if leader < range_start < end:
                end = range_start
        pc = leader
        terminated = False
        while pc < end:
            insn = instructions[pc]
            if is_control_flow(insn) or insn["op"] in ("halt", "stop"):
                lowerer.lower_terminator(block, insn)
                terminated = True
                break
            lowerer.lower_instruction(block, insn)
            pc += insn["length"]
        if not terminated:
            if end in cfg.block_by_address:
                block.jump(cfg.block_id(end))
            else:
                if any(range_start == end for range_start, _range_end in ranges):
                    raise SM83FrontendError(f"0x{leader:x}: block falls through into a declared data range")
                raise SM83FrontendError(f"0x{leader:x}: block reaches the region end without a terminator")

    memory_size = contract["memory"]["size_bytes"]
    initial_state = dict(meta["initial_state"])
    ir, sidecar = builder.build(
        entry_function="main",
        memory_size_bytes=memory_size,
        initial_state=initial_state,
        observe_state_slot=meta["observe_state_slot"],
        max_operations=meta["max_operations"],
    )
    sidecar["memory_segments"] = [
        {"name": "guest-memory", "guest_address": 0, "data_hex": memory_image.hex()}
    ]
    report = {
        "architecture": "sm83-gb",
        "frontend_version": FRONTEND_VERSION,
        "source_input_sha256": input_sha256,
        "functions": 1,
        "instructions": len(instructions),
        "blocks": len(ordered),
        "source_region": [meta["region_start"], meta["region_end"]],
    }
    return ir, sidecar, report


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 6:
        print(
            "usage: sm83_frontend_v1.py <fixture.json> <host-contract.json> <out-ir.json> <out-sidecar.json> <out-report.json>",
            file=sys.stderr,
        )
        return 2
    try:
        meta = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        contract = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        memory_image = bytes.fromhex(meta["memory_image_hex"])
        ir, sidecar, report = convert(memory_image, meta, contract)
        _write_json(Path(argv[3]), ir)
        _write_json(Path(argv[4]), sidecar)
        _write_json(Path(argv[5]), report)
    except (OSError, json.JSONDecodeError, KeyError, ValueError, SM83Error, SM83FrontendError, ScaffoldError) as exc:
        print(f"OPENRECOMP_SM83_FRONTEND_V1=FAIL: {exc}", file=sys.stderr)
        return 2
    print(f"SM83_FRONTEND_INSTRUCTIONS={report['instructions']}")
    print(f"SM83_FRONTEND_BLOCKS={report['blocks']}")
    print("OPENRECOMP_SM83_FRONTEND_V1=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
