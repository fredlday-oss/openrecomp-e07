#!/usr/bin/env python3
"""Z80 frontend: control flow + lowering into normalized IR V1 (P1-21).

Converts a bounded synthetic Z80 code region into architecture-neutral
normalized IR V1 using the shared scaffolding
(`openrecomp/frontends/scaffold.py`) and the documented decode + state model
(`adapters/z80.py`). The independent machine-code reference semantics live in
`tools/z80_reference_v1.py`; the P1-21 differential proof runs the same
fixture through both and requires identical final state.

Control-flow model (documented Z80 behaviour):

- one IR function per converted program region (the guest stack is modelled
  in guest memory, exactly like hardware);
- static targets (jp/jr/call/rst/djnz) become `jump`/`branch` terminators to
  the leader block at that guest address (targets outside the declared region
  or the decoded stream fail closed);
- `ret`, `retn`, `reti`, `jp (hl)/(ix)/(iy)` become `indirect_jump`
  terminators whose candidate set is every block of the function;
- conditional forms branch on the documented flag bits of F
  (S/Z/P/V/C for the 8 Z80 conditions);
- repeating block ops (LDIR/CPIR/...) lower to a self-looping helper block
  with the documented internal-repeat condition (BC!=0 / B!=0 / Z==0);
- the INI/OUTI block-I/O families decrement B only (C is preserved) and set
  Z = (B == 0), P/V = (B != 0), N = 1 for the -d variants and 0 otherwise;
  S/H/C are documented-undefined and preserved (Zilog manual primary,
  z80-heaven secondary documentation);
- HALT terminates the converted program by setting `platform:halted` and
  returning (the reference stops identically, so final state compares);
- EI/DI lower to `platform:iff1`/`platform:iff2` writes; the documented
  one-instruction EI delay is only observable through interrupt servicing,
  which is platform behaviour (P1-22), so differential fixtures exclude
  IFF-observable sequences between EI and the next instruction (documented);
- the deterministic port model: IN/OUT access a 256-byte port space mapped
  at guest memory offset 0x10000; port addresses mask to 8 bits, matching
  the reference (the reference keeps the identical model in a separate
  bytearray; the differential compares both);
- a leader target that lands inside an instruction (or an instruction that
  overlaps the region boundary) raises `Z80FrontendError` — fail closed;
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

from adapters import z80  # noqa: E402
from adapters.z80 import Z80Error, decode_full, is_control_flow  # noqa: E402
from openrecomp.frontends.scaffold import IRBuilder, ScaffoldError  # noqa: E402

FRONTEND_VERSION = "1.0.0"
PORT_BASE = 0x10000

COND_MASK = {
    "nz": 0x40, "z": 0x40, "nc": 0x01, "c": 0x01,
    "po": 0x04, "pe": 0x04, "p": 0x80, "m": 0x80,
}
COND_NEGATE = {
    "nz": True, "z": False, "nc": True, "c": False,
    "po": True, "pe": False, "p": True, "m": False,
}

CONTROL_OPS = frozenset({"jp", "jr", "call", "ret", "retn", "reti", "rst", "djnz", "jp_ind"})
BLOCK_OPS = frozenset({
    "ldi", "ldd", "ldir", "lddr", "cpi", "cpd", "cpir", "cpdr",
    "ini", "ind", "inir", "indr", "outi", "outd", "otir", "otdr",
})

# F bit positions (documented; X/Y pinned 0 by the model).
SHIFT_S, SHIFT_Z, SHIFT_H, SHIFT_PV, SHIFT_N, SHIFT_C = 7, 6, 4, 2, 1, 0


class Z80FrontendError(ValueError):
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
            raise Z80FrontendError(f"0x{address:x}: control-flow target is not a decoded block leader")
        return block_id


def _validated_data_ranges(meta: dict, start: int, end: int) -> list[tuple[int, int]]:
    ranges = meta.get("data_ranges")
    if ranges is None:
        return []
    if not isinstance(ranges, list):
        raise Z80FrontendError("data_ranges must be a list of [start, end) pairs")
    parsed: list[tuple[int, int]] = []
    for item in ranges:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise Z80FrontendError("each data range must be a [start, end) pair")
        range_start, range_end = item
        if (
            isinstance(range_start, bool)
            or isinstance(range_end, bool)
            or not isinstance(range_start, int)
            or not isinstance(range_end, int)
            or not (start <= range_start < range_end <= end)
        ):
            raise Z80FrontendError(f"data range [{range_start!r}, {range_end!r}) is invalid for [{start:#x}, {end:#x})")
        parsed.append((range_start, range_end))
    parsed.sort()
    for (s1, e1), (s2, e2) in zip(parsed, parsed[1:]):
        if s2 < e1:
            raise Z80FrontendError(f"data ranges overlap: [{s1:#x}, {e1:#x}) and [{s2:#x}, {e2:#x})")
    return parsed


def _inside_data(address: int, ranges: list[tuple[int, int]]) -> bool:
    return any(range_start <= address < range_end for range_start, range_end in ranges)


def _decode_region(code: bytes, meta: dict) -> tuple[dict[int, dict], set[int]]:
    start = meta["region_start"]
    end = meta["region_end"]
    entry = meta["entry_address"]
    if not (0 <= start < end <= len(code)):
        raise Z80FrontendError("code region is outside the memory image")
    if not (start <= entry < end):
        raise Z80FrontendError("entry address is outside the code region")
    ranges = _validated_data_ranges(meta, start, end)
    if _inside_data(start, ranges):
        raise Z80FrontendError("the code region starts inside a declared data range")
    if _inside_data(entry, ranges):
        raise Z80FrontendError("the entry address lies inside a declared data range")

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
            except Z80Error as exc:
                raise Z80FrontendError(f"decode rejected: {exc}") from exc
            instructions[pc] = insn
            if insn["op"] in CONTROL_OPS:
                for target in z80.branch_targets(insn):
                    if not (start <= target < end):
                        raise Z80FrontendError(f"0x{pc:x}: control-flow target 0x{target:x} leaves the region")
                    if _inside_data(target, ranges):
                        raise Z80FrontendError(f"0x{pc:x}: control-flow target 0x{target:x} is inside a declared data range")
                    leaders.add(target)
                conditional = "cond" in insn or insn["op"] == "djnz"
                needs_fallthrough = conditional or insn["op"] in ("call", "rst")
                if needs_fallthrough:
                    fallthrough = pc + insn["length"]
                    if fallthrough >= end:
                        raise Z80FrontendError(f"0x{pc:x}: fallthrough leaves the region")
                    if _inside_data(fallthrough, ranges) or fallthrough == span_end and span_end < end:
                        raise Z80FrontendError(f"0x{pc:x}: fallthrough enters a declared data range")
                    leaders.add(fallthrough)
            elif insn["op"] in BLOCK_OPS:
                # Repeating block ops loop internally; their exit is a leader.
                fallthrough = pc + insn["length"]
                if fallthrough >= end:
                    raise Z80FrontendError(f"0x{pc:x}: block-op fallthrough leaves the region")
                if _inside_data(fallthrough, ranges):
                    raise Z80FrontendError(f"0x{pc:x}: block-op fallthrough enters a declared data range")
                leaders.add(fallthrough)
            pc += insn["length"]
            if pc > span_end:
                raise Z80FrontendError(
                    f"0x{pc - insn['length']:x}: instruction overlaps the code/data boundary at 0x{span_end:x}"
                )
    return instructions, leaders


def _build_cfg(instructions: dict[int, dict], leaders: set[int]) -> _Cfg:
    cfg = _Cfg(instructions, leaders)
    for leader in sorted(leaders):
        cfg.block_by_address[leader] = f"b_{leader:04x}"
    return cfg


PAIR_PARTS = {"af": ("a", "f"), "bc": ("b", "c"), "de": ("d", "e"), "hl": ("h", "l")}


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

    def _helper_block(self, address: int):
        self.helper_counter += 1
        return self.function.add_block(f"b_{address:04x}_h{self.helper_counter}", address)

    # -- value helpers ---------------------------------------------------
    def _r8(self, block, name: str) -> dict:
        ctx = self.ctx
        if name == "(hl)":
            result = ctx.tmp("mem")
            block.load(result, "i8", width_bits=8, signed=False, address=self._address(block, self._pair16(block, "hl")), alignment=1)
            return block.value(result)
        if name in ("(ix+d)", "(iy+d)"):
            result = ctx.tmp("mem")
            block.load(result, "i8", width_bits=8, signed=False, address=self._address(block, self._index_address(block, name[1:3])), alignment=1)
            return block.value(result)
        result = ctx.tmp(name)
        block.read_state(result, f"cpu:{name}")
        return block.value(result)

    def _set_r8(self, block, name: str, value: dict) -> None:
        if name == "(hl)":
            block.store(width_bits=8, address=self._address(block, self._pair16(block, "hl")), value=value, alignment=1)
        elif name in ("(ix+d)", "(iy+d)"):
            block.store(width_bits=8, address=self._address(block, self._index_address(block, name[1:3])), value=value, alignment=1)
        else:
            block.write_state(f"cpu:{name}", value)

    def _index_address(self, block, base: str) -> dict:
        ctx = self.ctx
        d = self.ctx.current_d
        reg = ctx.tmp("ixr")
        block.read_state(reg, f"cpu:{base}")
        disp = ctx.tmp("disp")
        block.const_result(disp, "i16", d & 0xFFFF)
        result = ctx.tmp("ea")
        block.binop(result, "i16", "add", block.value(reg), block.value(disp))
        return block.value(result)

    def _pair16(self, block, name: str) -> dict:
        ctx = self.ctx
        if name in ("sp", "ix", "iy"):
            result = ctx.tmp(name)
            block.read_state(result, f"cpu:{name}")
            return block.value(result)
        high, low = PAIR_PARTS[name]
        high16 = ctx.tmp("hi16")
        low16 = ctx.tmp("lo16")
        block.cast(high16, "i16", "zext", self._r8(block, high))
        block.cast(low16, "i16", "zext", self._r8(block, low))
        shifted = ctx.tmp("hi_shl")
        block.binop(shifted, "i16", "shl", block.value(high16), block.const(8, "i16"))
        combined = ctx.tmp("pair")
        block.binop(combined, "i16", "or", block.value(shifted), block.value(low16))
        return block.value(combined)

    def _set_pair16(self, block, name: str, value16: dict) -> None:
        if name in ("sp", "ix", "iy"):
            block.write_state(f"cpu:{name}", value16)
            return
        high, low = PAIR_PARTS[name]
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

    def _port_address(self, block, value16: dict) -> dict:
        ctx = self.ctx
        masked = ctx.tmp("pmask")
        block.binop(masked, "i16", "and", value16, self._const16(block, 0xFF))
        addr = ctx.tmp("paddr")
        block.binop(addr, "i32", "or", block.const(PORT_BASE, "i32"), self._address(block, block.value(masked)))
        return block.value(addr)

    def _const8(self, block, value: int) -> dict:
        return block.const(value & 0xFF, "i8")

    def _const16(self, block, value: int) -> dict:
        return block.const(value & 0xFFFF, "i16")

    def _const_i1(self, block, value: bool) -> dict:
        result = self.ctx.tmp("ci1")
        block.const_result(result, "i1", 1 if value else 0)
        return block.value(result)

    def _bool(self, block, value8: dict) -> dict:
        result = self.ctx.tmp("bool")
        block.compare(result, "ne", value8, self._const8(block, 0))
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

    def _shl8(self, block, value8: dict, amount: int) -> str:
        result = self.ctx.tmp("shl")
        block.binop(result, "i8", "shl", value8, self._const8(block, amount))
        return result

    def _f_byte(self, block, bits: list[tuple[dict, int]]) -> dict:
        ctx = self.ctx
        acc = ctx.tmp("facc")
        block.const_result(acc, "i8", 0)
        for value, shift in bits:
            v8 = ctx.tmp("fb")
            block.cast(v8, "i8", "zext", value)
            if shift:
                shifted = ctx.tmp("fs")
                block.binop(shifted, "i8", "shl", block.value(v8), self._const8(block, shift))
            else:
                shifted = v8
            combined = ctx.tmp("fc")
            block.binop(combined, "i8", "or", block.value(acc), block.value(shifted))
            acc = combined
        return block.value(acc)

    def _write_f(self, block, bits: list[tuple[dict, int]]) -> None:
        block.write_state("cpu:f", self._f_byte(block, bits))

    def _set_flags(self, block, s, z, h, pv, n, c) -> None:
        self._write_f(block, [(s, SHIFT_S), (z, SHIFT_Z), (h, SHIFT_H), (pv, SHIFT_PV), (n, SHIFT_N), (c, SHIFT_C)])

    def _parity(self, block, value8: dict) -> dict:
        ctx = self.ctx
        v1 = ctx.tmp("px1")
        block.binop(v1, "i8", "lshr", value8, self._const8(block, 1))
        x1 = ctx.tmp("pxor1")
        block.binop(x1, "i8", "xor", value8, block.value(v1))
        v2 = ctx.tmp("px2")
        block.binop(v2, "i8", "lshr", block.value(x1), self._const8(block, 2))
        x2 = ctx.tmp("pxor2")
        block.binop(x2, "i8", "xor", block.value(x1), block.value(v2))
        v4 = ctx.tmp("px4")
        block.binop(v4, "i8", "lshr", block.value(x2), self._const8(block, 4))
        x4 = ctx.tmp("pxor4")
        block.binop(x4, "i8", "xor", block.value(x2), block.value(v4))
        low = ctx.tmp("plow")
        block.binop(low, "i8", "and", block.value(x4), self._const8(block, 1))
        result = ctx.tmp("peven")
        block.compare(result, "eq", block.value(low), self._const8(block, 0))
        return block.value(result)

    def _szp(self, block, value8: dict) -> tuple[dict, dict, dict]:
        ctx = self.ctx
        s = ctx.tmp("sflag")
        block.compare(s, "slt", value8, self._const8(block, 0))
        z = ctx.tmp("zflag")
        block.compare(z, "eq", value8, self._const8(block, 0))
        return block.value(s), block.value(z), self._parity(block, value8)

    def _overflow_add(self, block, a8: dict, b8: dict, result8: dict) -> dict:
        ctx = self.ctx
        ax = ctx.tmp("oax")
        bx = ctx.tmp("obx")
        block.binop(ax, "i8", "xor", a8, result8)
        block.binop(bx, "i8", "xor", b8, result8)
        both = ctx.tmp("oboth")
        block.binop(both, "i8", "and", block.value(ax), block.value(bx))
        masked = ctx.tmp("omask")
        block.binop(masked, "i8", "and", block.value(both), self._const8(block, 0x80))
        return self._bool(block, block.value(masked))

    def _overflow_sub(self, block, a8: dict, b8: dict, result8: dict) -> dict:
        ctx = self.ctx
        ab = ctx.tmp("oab")
        ar = ctx.tmp("oar")
        block.binop(ab, "i8", "xor", a8, b8)
        block.binop(ar, "i8", "xor", a8, result8)
        both = ctx.tmp("oboth")
        block.binop(both, "i8", "and", block.value(ab), block.value(ar))
        masked = ctx.tmp("omask")
        block.binop(masked, "i8", "and", block.value(both), self._const8(block, 0x80))
        return self._bool(block, block.value(masked))

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

    # -- 8-bit ALU ---------------------------------------------------------
    def _alu8(self, block, kind: str, operand8: dict) -> None:
        ctx = self.ctx
        a = self._r8(block, "a")
        if kind in ("add", "adc"):
            carry = self._flag_bit(block, z80.FLAG_C)
            carry8 = ctx.tmp("c8")
            block.cast(carry8, "i8", "zext", carry)
            mid = ctx.tmp("mid")
            block.binop(mid, "i8", "add", a, operand8)
            if kind == "adc":
                result = ctx.tmp("res")
                block.binop(result, "i8", "add", block.value(mid), block.value(carry8))
            else:
                result = mid
            res8 = block.value(result)
            a_nib = ctx.tmp("anib")
            b_nib = ctx.tmp("bnib")
            block.binop(a_nib, "i8", "and", a, self._const8(block, 0x0F))
            block.binop(b_nib, "i8", "and", operand8, self._const8(block, 0x0F))
            nib_sum = ctx.tmp("nibsum")
            block.binop(nib_sum, "i8", "add", block.value(a_nib), block.value(b_nib))
            if kind == "adc":
                nib_sum2 = ctx.tmp("nibsum2")
                block.binop(nib_sum2, "i8", "add", block.value(nib_sum), block.value(carry8))
                nib_total = block.value(nib_sum2)
            else:
                nib_total = block.value(nib_sum)
            h = ctx.tmp("hflag")
            block.compare(h, "ugt", nib_total, self._const8(block, 0x0F))
            c = ctx.tmp("cflag")
            if kind == "adc":
                block.compare(c, "ult", res8, block.value(mid))
            else:
                block.compare(c, "ult", res8, a)
            s, z, pv = self._szp(block, res8)
            block.write_state("cpu:a", res8)
            self._set_flags(block, s, z, block.value(h), self._overflow_add(block, a, operand8, res8), self._const_i1(block, False), block.value(c))
            return
        if kind in ("sub", "cp", "sbc"):
            carry = self._flag_bit(block, z80.FLAG_C)
            carry8 = ctx.tmp("c8")
            block.cast(carry8, "i8", "zext", carry)
            mid = ctx.tmp("mid")
            block.binop(mid, "i8", "sub", a, operand8)
            if kind == "sbc":
                result = ctx.tmp("res")
                block.binop(result, "i8", "sub", block.value(mid), block.value(carry8))
            else:
                result = mid
            res8 = block.value(result)
            a_nib = ctx.tmp("anib")
            b_nib = ctx.tmp("bnib")
            block.binop(a_nib, "i8", "and", a, self._const8(block, 0x0F))
            block.binop(b_nib, "i8", "and", operand8, self._const8(block, 0x0F))
            nib_diff = ctx.tmp("nibdiff")
            block.binop(nib_diff, "i8", "sub", block.value(a_nib), block.value(b_nib))
            if kind == "sbc":
                nib_diff2 = ctx.tmp("nibdiff2")
                block.binop(nib_diff2, "i8", "sub", block.value(nib_diff), block.value(carry8))
                nib_total = block.value(nib_diff2)
            else:
                nib_total = block.value(nib_diff)
            h = ctx.tmp("hflag")
            block.compare(h, "slt", nib_total, self._const8(block, 0))
            c = ctx.tmp("cflag")
            block.compare(c, "slt", res8, self._const8(block, 0))
            s, z, pv = self._szp(block, res8)
            if kind != "cp":
                block.write_state("cpu:a", res8)
            self._set_flags(block, s, z, block.value(h), self._overflow_sub(block, a, operand8, res8), self._const_i1(block, True), block.value(c))
            return
        result = ctx.tmp("res")
        block.binop(result, "i8", kind, a, operand8)
        res8 = block.value(result)
        block.write_state("cpu:a", res8)
        s, z, pv = self._szp(block, res8)
        h = self._const_i1(block, True) if kind == "and" else self._const_i1(block, False)
        self._set_flags(block, s, z, h, pv, self._const_i1(block, False), self._const_i1(block, False))

    def _neg(self, block) -> None:
        ctx = self.ctx
        a = self._r8(block, "a")
        zero = self._const8(block, 0)
        result = ctx.tmp("res")
        block.binop(result, "i8", "sub", zero, a)
        res8 = block.value(result)
        a_nib = ctx.tmp("anib")
        block.binop(a_nib, "i8", "and", a, self._const8(block, 0x0F))
        neg_nib = ctx.tmp("nnib")
        block.binop(neg_nib, "i8", "sub", zero, block.value(a_nib))
        h = ctx.tmp("hflag")
        block.compare(h, "slt", block.value(neg_nib), self._const8(block, 0))
        c = ctx.tmp("cflag")
        block.compare(c, "ne", a, self._const8(block, 0))
        s, z, pv = self._szp(block, res8)
        block.write_state("cpu:a", res8)
        self._set_flags(block, s, z, block.value(h), self._overflow_sub(block, zero, a, res8), self._const_i1(block, True), block.value(c))

    def _inc8(self, block, name: str) -> None:
        ctx = self.ctx
        before = self._r8(block, name)
        result = ctx.tmp("res")
        block.binop(result, "i8", "add", before, self._const8(block, 1))
        res8 = block.value(result)
        self._set_r8(block, name, res8)
        s, z, pv = self._szp(block, res8)
        nib = ctx.tmp("nib")
        block.binop(nib, "i8", "and", before, self._const8(block, 0x0F))
        h = ctx.tmp("hflag")
        block.compare(h, "eq", block.value(nib), self._const8(block, 0x0F))
        overflow = ctx.tmp("ovf")
        block.compare(overflow, "eq", before, self._const8(block, 0x7F))
        self._set_flags(block, s, z, block.value(h), block.value(overflow), self._const_i1(block, False), self._flag_bit(block, z80.FLAG_C))

    def _dec8(self, block, name: str) -> None:
        ctx = self.ctx
        before = self._r8(block, name)
        result = ctx.tmp("res")
        block.binop(result, "i8", "sub", before, self._const8(block, 1))
        res8 = block.value(result)
        self._set_r8(block, name, res8)
        s, z, pv = self._szp(block, res8)
        nib = ctx.tmp("nib")
        block.binop(nib, "i8", "and", before, self._const8(block, 0x0F))
        h = ctx.tmp("hflag")
        block.compare(h, "eq", block.value(nib), self._const8(block, 0x00))
        overflow = ctx.tmp("ovf")
        block.compare(overflow, "eq", before, self._const8(block, 0x80))
        self._set_flags(block, s, z, block.value(h), block.value(overflow), self._const_i1(block, True), self._flag_bit(block, z80.FLAG_C))

    def _daa(self, block) -> None:
        ctx = self.ctx
        a = self._r8(block, "a")
        c_flag = self._flag_bit(block, z80.FLAG_C)
        h_flag = self._flag_bit(block, z80.FLAG_H)
        n_flag = self._flag_bit(block, z80.FLAG_N)
        low_nib = ctx.tmp("lnib")
        block.binop(low_nib, "i8", "and", a, self._const8(block, 0x0F))
        gt9 = ctx.tmp("gt9")
        block.compare(gt9, "ugt", block.value(low_nib), self._const8(block, 0x09))
        h_or_9 = ctx.tmp("hor9")
        block.binop(h_or_9, "i1", "or", h_flag, block.value(gt9))
        gt99 = ctx.tmp("gt99")
        block.compare(gt99, "ugt", a, self._const8(block, 0x99))
        c_or_99 = ctx.tmp("cor99")
        block.binop(c_or_99, "i1", "or", c_flag, block.value(gt99))
        six = ctx.tmp("six")
        block.select(six, "i8", block.value(h_or_9), self._const8(block, 0x06), self._const8(block, 0x00))
        sixty = ctx.tmp("sixty")
        block.select(sixty, "i8", block.value(c_or_99), self._const8(block, 0x60), self._const8(block, 0x00))
        corr = ctx.tmp("corr")
        block.binop(corr, "i8", "or", block.value(six), block.value(sixty))
        added = ctx.tmp("added")
        subbed = ctx.tmp("subbed")
        block.binop(added, "i8", "add", a, block.value(corr))
        block.binop(subbed, "i8", "sub", a, block.value(corr))
        final8 = ctx.tmp("final8")
        block.select(final8, "i8", n_flag, block.value(subbed), block.value(added))
        block.write_state("cpu:a", block.value(final8))
        s, z, pv = self._szp(block, block.value(final8))
        carry = ctx.tmp("carry")
        block.select(carry, "i1", n_flag, c_flag, block.value(c_or_99))
        self._set_flags(block, s, z, self._const_i1(block, False), pv, n_flag, block.value(carry))

    def _rotate_a(self, block, op: str) -> None:
        ctx = self.ctx
        a = self._r8(block, "a")
        carry_in = self._flag_bit(block, z80.FLAG_C)
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
            cin8 = ctx.tmp("cin8")
            block.cast(cin8, "i8", "zext", carry_in)
            block.binop(result, "i8", "or", block.value(shifted), block.value(cin8))
        else:
            low = ctx.tmp("lo")
            block.binop(low, "i8", "and", a, self._const8(block, 1))
            block.cast(carry_out, "i1", "trunc", block.value(low))
            shifted = ctx.tmp("shr")
            block.binop(shifted, "i8", "lshr", a, self._const8(block, 1))
            cin8 = ctx.tmp("cin8")
            block.cast(cin8, "i8", "zext", carry_in)
            cin7 = self._shl8(block, block.value(cin8), 7)
            block.binop(result, "i8", "or", block.value(shifted), block.value(cin7))
        block.write_state("cpu:a", block.value(result))
        # documented: only H/N/C change; S/Z/P/V preserved
        self._write_f(block, [
            (self._flag_bit(block, z80.FLAG_S), SHIFT_S),
            (self._flag_bit(block, z80.FLAG_Z), SHIFT_Z),
            (self._flag_bit(block, z80.FLAG_PV), SHIFT_PV),
            (block.value(carry_out), SHIFT_C),
        ])

    def _cb_op(self, block, insn: dict, op: str) -> None:
        ctx = self.ctx
        name = insn["r"]
        value = self._r8(block, name)
        carry_in = self._flag_bit(block, z80.FLAG_C)
        if op == "bit":
            mask = ctx.tmp("mask")
            block.binop(mask, "i8", "and", value, self._const8(block, 1 << insn["n"]))
            z = ctx.tmp("zflag")
            block.compare(z, "eq", block.value(mask), self._const8(block, 0))
            self._write_f(block, [
                (self._flag_bit(block, z80.FLAG_S), SHIFT_S),
                (block.value(z), SHIFT_Z),
                (self._const_i1(block, True), SHIFT_H),
                (block.value(z), SHIFT_PV),
                (self._flag_bit(block, z80.FLAG_C), SHIFT_C),
            ])
            return
        if op == "res":
            result = ctx.tmp("res")
            block.binop(result, "i8", "and", value, self._const8(block, (~(1 << insn["n"])) & 0xFF))
            self._set_r8(block, name, block.value(result))
            return
        if op == "set":
            result = ctx.tmp("res")
            block.binop(result, "i8", "or", value, self._const8(block, 1 << insn["n"]))
            self._set_r8(block, name, block.value(result))
            return
        result = ctx.tmp("res")
        carry_out = ctx.tmp("cout")
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
            cin8 = ctx.tmp("cin8")
            block.cast(cin8, "i8", "zext", carry_in)
            block.binop(result, "i8", "or", block.value(shifted), block.value(cin8))
        elif op == "rr":
            low = ctx.tmp("lo")
            block.binop(low, "i8", "and", value, self._const8(block, 1))
            block.cast(carry_out, "i1", "trunc", block.value(low))
            shifted = ctx.tmp("shr")
            block.binop(shifted, "i8", "lshr", value, self._const8(block, 1))
            cin8 = ctx.tmp("cin8")
            block.cast(cin8, "i8", "zext", carry_in)
            cin7 = self._shl8(block, block.value(cin8), 7)
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
        else:
            raise Z80FrontendError(f"unsupported CB op {op}")
        self._set_r8(block, name, block.value(result))
        s, z, pv = self._szp(block, block.value(result))
        self._set_flags(block, s, z, self._const_i1(block, False), pv, self._const_i1(block, False), block.value(carry_out))

    # -- 16-bit arithmetic -----------------------------------------------
    def _add16(self, block, dst: str, pair: str) -> None:
        ctx = self.ctx
        value = self._pair16(block, dst)
        operand = self._pair16(block, pair)
        result = ctx.tmp("res")
        block.binop(result, "i16", "add", value, operand)
        self._set_pair16(block, dst, block.value(result))
        low11a = ctx.tmp("l11a")
        low11b = ctx.tmp("l11b")
        block.binop(low11a, "i16", "and", value, self._const16(block, 0x0FFF))
        block.binop(low11b, "i16", "and", operand, self._const16(block, 0x0FFF))
        low_sum = ctx.tmp("lowsum")
        block.binop(low_sum, "i16", "add", block.value(low11a), block.value(low11b))
        h = ctx.tmp("hflag")
        block.compare(h, "ugt", block.value(low_sum), self._const16(block, 0x0FFF))
        c = ctx.tmp("cflag")
        block.compare(c, "ult", block.value(result), value)
        # documented ADD: preserve S/Z/PV, N cleared
        self._write_f(block, [
            (self._flag_bit(block, z80.FLAG_S), SHIFT_S),
            (self._flag_bit(block, z80.FLAG_Z), SHIFT_Z),
            (block.value(h), SHIFT_H),
            (self._flag_bit(block, z80.FLAG_PV), SHIFT_PV),
            (block.value(c), SHIFT_C),
        ])

    def _adc_sbc_hl(self, block, pair: str, adc: bool) -> None:
        ctx = self.ctx
        value = self._pair16(block, "hl")
        operand = self._pair16(block, pair)
        carry = self._flag_bit(block, z80.FLAG_C)
        carry16 = ctx.tmp("c16")
        block.cast(carry16, "i16", "zext", carry)
        mid = ctx.tmp("mid")
        result = ctx.tmp("res")
        if adc:
            block.binop(mid, "i16", "add", value, operand)
            block.binop(result, "i16", "add", block.value(mid), block.value(carry16))
        else:
            block.binop(mid, "i16", "sub", value, operand)
            block.binop(result, "i16", "sub", block.value(mid), block.value(carry16))
        self._set_pair16(block, "hl", block.value(result))
        low11a = ctx.tmp("l11a")
        low11b = ctx.tmp("l11b")
        block.binop(low11a, "i16", "and", value, self._const16(block, 0x0FFF))
        block.binop(low11b, "i16", "and", operand, self._const16(block, 0x0FFF))
        low_sum = ctx.tmp("lowsum")
        if adc:
            block.binop(low_sum, "i16", "add", block.value(low11a), block.value(low11b))
            low_sum2 = ctx.tmp("lowsum2")
            block.binop(low_sum2, "i16", "add", block.value(low_sum), block.value(carry16))
            low_total = block.value(low_sum2)
        else:
            block.binop(low_sum, "i16", "sub", block.value(low11a), block.value(low11b))
            low_sum2 = ctx.tmp("lowsum2")
            block.binop(low_sum2, "i16", "sub", block.value(low_sum), block.value(carry16))
            low_total = block.value(low_sum2)
        h = ctx.tmp("hflag")
        if adc:
            block.compare(h, "ugt", low_total, self._const16(block, 0x0FFF))
        else:
            block.compare(h, "slt", low_total, self._const16(block, 0))
        c = ctx.tmp("cflag")
        if adc:
            block.compare(c, "ult", block.value(result), value)
        else:
            block.compare(c, "slt", block.value(result), self._const16(block, 0))
        s = ctx.tmp("sflag")
        z = ctx.tmp("zflag")
        block.compare(s, "slt", block.value(result), self._const16(block, 0))
        block.compare(z, "eq", block.value(result), self._const16(block, 0))
        pv = ctx.tmp("pvflag")
        if adc:
            xa = ctx.tmp("xa")
            xb = ctx.tmp("xb")
            block.binop(xa, "i16", "xor", value, block.value(result))
            block.binop(xb, "i16", "xor", operand, block.value(result))
            both = ctx.tmp("xboth")
            block.binop(both, "i16", "and", block.value(xa), block.value(xb))
        else:
            xa = ctx.tmp("xa")
            xb = ctx.tmp("xb")
            block.binop(xa, "i16", "xor", value, operand)
            block.binop(xb, "i16", "xor", value, block.value(result))
            both = ctx.tmp("xboth")
            block.binop(both, "i16", "and", block.value(xa), block.value(xb))
        masked = ctx.tmp("xmask")
        block.binop(masked, "i16", "and", block.value(both), self._const16(block, 0x8000))
        block.compare(pv, "ne", block.value(masked), self._const16(block, 0))
        n = self._const_i1(block, False) if adc else self._const_i1(block, True)
        self._set_flags(block, block.value(s), block.value(z), block.value(h), block.value(pv), n, block.value(c))

    # -- simple instructions ----------------------------------------------
    def _lower_ld(self, block, insn: dict) -> None:
        ctx = self.ctx
        dst = insn.get("dst")
        src = insn.get("src")
        if dst in ("sp", "bc", "de", "hl", "ix", "iy") and "imm16" in insn:
            self._set_pair16(block, dst, self._const16(block, insn["imm16"]))
        elif dst in ("bc", "de", "hl", "sp") and src == "(a16)":
            value = ctx.tmp("v")
            block.load(value, "i16", width_bits=16, signed=False, address=block.const(insn["a16"], "i32"), alignment=1)
            self._set_pair16(block, dst, block.value(value))
        elif dst in ("ix", "iy") and src == "(a16)":
            value = ctx.tmp("v")
            block.load(value, "i16", width_bits=16, signed=False, address=block.const(insn["a16"], "i32"), alignment=1)
            block.write_state(f"cpu:{dst}", block.value(value))
        elif dst == "(a16)" and src in ("bc", "de", "hl", "sp", "ix", "iy"):
            address = block.const(insn["a16"], "i32")
            value16 = self._pair16(block, src)
            high8 = ctx.tmp("hi8")
            low8 = ctx.tmp("lo8")
            block.cast(high8, "i8", "trunc", block.value(self._shr16(block, value16, 8)))
            block.cast(low8, "i8", "trunc", value16)
            addr1 = ctx.tmp("addr1")
            block.binop(addr1, "i32", "add", address, block.const(1, "i32"))
            block.store(width_bits=8, address=address, value=block.value(low8), alignment=1)
            block.store(width_bits=8, address=block.value(addr1), value=block.value(high8), alignment=1)
        elif dst == "(a16)" and src == "a":
            block.store(width_bits=8, address=block.const(insn["a16"], "i32"), value=self._r8(block, "a"), alignment=1)
        elif dst in ("i", "r"):
            block.write_state(f"cpu:{dst}", self._r8(block, "a"))
        elif src in ("i", "r"):
            value = ctx.tmp("v")
            block.read_state(value, f"cpu:{src}")
            block.write_state("cpu:a", block.value(value))
            s, z, pv = self._szp(block, block.value(value))
            iff2 = ctx.tmp("iff2")
            block.read_state(iff2, "platform:iff2")
            self._set_flags(block, s, z, self._const_i1(block, False), block.value(iff2), self._const_i1(block, False), self._flag_bit(block, z80.FLAG_C))
        elif src == "(a16)":
            value = ctx.tmp("v")
            block.load(value, "i8", width_bits=8, signed=False, address=block.const(insn["a16"], "i32"), alignment=1)
            self._set_r8(block, dst, block.value(value))
        elif dst == "(bc)":
            block.store(width_bits=8, address=self._address(block, self._pair16(block, "bc")), value=self._r8(block, "a"), alignment=1)
        elif dst == "(de)":
            block.store(width_bits=8, address=self._address(block, self._pair16(block, "de")), value=self._r8(block, "a"), alignment=1)
        elif src == "(bc)":
            value = ctx.tmp("v")
            block.load(value, "i8", width_bits=8, signed=False, address=self._address(block, self._pair16(block, "bc")), alignment=1)
            self._set_r8(block, dst, block.value(value))
        elif src == "(de)":
            value = ctx.tmp("v")
            block.load(value, "i8", width_bits=8, signed=False, address=self._address(block, self._pair16(block, "de")), alignment=1)
            self._set_r8(block, dst, block.value(value))
        elif dst in ("b", "c", "d", "e", "h", "l", "a", "(hl)", "(ix+d)", "(iy+d)"):
            value = self._const8(block, insn["imm8"]) if "imm8" in insn else self._r8(block, src)
            self._set_r8(block, dst, value)
        else:
            raise Z80FrontendError(f"0x{insn['address']:x}: unsupported ld form {insn}")

    def _lower_in(self, block, insn: dict) -> None:
        ctx = self.ctx
        if insn.get("src") == "(c)":
            value = ctx.tmp("v")
            block.load(value, "i8", width_bits=8, signed=False, address=self._port_address(block, self._pair16(block, "bc")), alignment=1)
            self._set_r8(block, insn["dst"], block.value(value))
            s, z, pv = self._szp(block, block.value(value))
            self._set_flags(block, s, z, self._const_i1(block, False), pv, self._const_i1(block, False), self._flag_bit(block, z80.FLAG_C))
        else:
            a = self._r8(block, "a")
            port16 = ctx.tmp("p16")
            block.cast(port16, "i16", "zext", a)
            port16b = ctx.tmp("p16b")
            block.binop(port16b, "i16", "shl", block.value(port16), self._const16(block, 8))
            with_n = ctx.tmp("pwithn")
            block.binop(with_n, "i16", "or", block.value(port16b), self._const16(block, insn["port_n"]))
            value = ctx.tmp("v")
            block.load(value, "i8", width_bits=8, signed=False, address=self._port_address(block, block.value(with_n)), alignment=1)
            block.write_state("cpu:a", block.value(value))

    def _lower_out(self, block, insn: dict) -> None:
        ctx = self.ctx
        if insn.get("dst") == "(c)":
            block.store(width_bits=8, address=self._port_address(block, self._pair16(block, "bc")), value=self._r8(block, insn["src"]), alignment=1)
        else:
            a = self._r8(block, "a")
            port16 = ctx.tmp("p16")
            block.cast(port16, "i16", "zext", a)
            port16b = ctx.tmp("p16b")
            block.binop(port16b, "i16", "shl", block.value(port16), self._const16(block, 8))
            with_n = ctx.tmp("pwithn")
            block.binop(with_n, "i16", "or", block.value(port16b), self._const16(block, insn["port_n"]))
            block.store(width_bits=8, address=self._port_address(block, block.value(with_n)), value=a, alignment=1)

    def _swap_slots(self, block, a_slot: str, b_slot: str) -> None:
        ctx = self.ctx
        a = ctx.tmp("sa")
        b = ctx.tmp("sb")
        block.read_state(a, a_slot)
        block.read_state(b, b_slot)
        block.write_state(a_slot, block.value(b))
        block.write_state(b_slot, block.value(a))

    def _lower_exx(self, block) -> None:
        for high, low in (("b", "c"), ("d", "e"), ("h", "l")):
            self._swap_slots(block, f"cpu:{high}", f"cpu:{high}2")
            self._swap_slots(block, f"cpu:{low}", f"cpu:{low}2")

    def _lower_ex_af(self, block) -> None:
        self._swap_slots(block, "cpu:a", "cpu:a2")
        self._swap_slots(block, "cpu:f", "cpu:f2")

    def _lower_ex_sp(self, block, insn: dict) -> None:
        ctx = self.ctx
        sp = self._pair16(block, "sp")
        reg = self._pair16(block, insn["src"])
        lo = ctx.tmp("lo")
        hi = ctx.tmp("hi")
        block.load(lo, "i8", width_bits=8, signed=False, address=self._address(block, sp), alignment=1)
        addr1 = ctx.tmp("addr1")
        block.binop(addr1, "i16", "add", sp, self._const16(block, 1))
        block.load(hi, "i8", width_bits=8, signed=False, address=self._address(block, block.value(addr1)), alignment=1)
        reg_low = ctx.tmp("rlo")
        reg_high = ctx.tmp("rhi")
        block.cast(reg_low, "i8", "trunc", reg)
        block.cast(reg_high, "i8", "trunc", block.value(self._shr16(block, reg, 8)))
        block.store(width_bits=8, address=self._address(block, sp), value=block.value(reg_low), alignment=1)
        block.store(width_bits=8, address=self._address(block, block.value(addr1)), value=block.value(reg_high), alignment=1)
        hi16 = ctx.tmp("hi16")
        lo16 = ctx.tmp("lo16")
        block.cast(hi16, "i16", "zext", block.value(hi))
        block.cast(lo16, "i16", "zext", block.value(lo))
        shifted = ctx.tmp("hi_shl")
        block.binop(shifted, "i16", "shl", block.value(hi16), self._const16(block, 8))
        combined = ctx.tmp("swapped")
        block.binop(combined, "i16", "or", block.value(shifted), block.value(lo16))
        self._set_pair16(block, insn["src"], block.value(combined))

    def _lower_ex_de_hl(self, block) -> None:
        de = self._pair16(block, "de")
        hl = self._pair16(block, "hl")
        self._set_pair16(block, "de", hl)
        self._set_pair16(block, "hl", de)

    def _rrd_rld(self, block, *, right: bool) -> None:
        ctx = self.ctx
        a = self._r8(block, "a")
        value = ctx.tmp("mem")
        block.load(value, "i8", width_bits=8, signed=False, address=self._address(block, self._pair16(block, "hl")), alignment=1)
        a_hi = ctx.tmp("ahi")
        a_low = ctx.tmp("alo")
        block.binop(a_hi, "i8", "and", a, self._const8(block, 0xF0))
        block.binop(a_low, "i8", "and", a, self._const8(block, 0x0F))
        mem_hi = ctx.tmp("mhi")
        mem_low = ctx.tmp("mlo")
        block.binop(mem_hi, "i8", "lshr", block.value(value), self._const8(block, 4))
        block.binop(mem_low, "i8", "and", block.value(value), self._const8(block, 0x0F))
        if right:
            # RRD: A = (A&F0)|(mem&0F); mem = ((A&0F)<<4)|(mem>>4)
            new_a = ctx.tmp("newa")
            block.binop(new_a, "i8", "or", block.value(a_hi), block.value(mem_low))
            a_shl = self._shl8(block, block.value(a_low), 4)
            new_mem = ctx.tmp("newmem")
            block.binop(new_mem, "i8", "or", block.value(a_shl), block.value(mem_hi))
        else:
            # RLD: A = (A&F0)|(mem>>4); mem = ((mem&0F)... (mem<<4)|(A&0F)
            new_a = ctx.tmp("newa")
            block.binop(new_a, "i8", "or", block.value(a_hi), block.value(mem_hi))
            mem_shl = self._shl8(block, block.value(value), 4)
            new_mem = ctx.tmp("newmem")
            block.binop(new_mem, "i8", "or", block.value(mem_shl), block.value(a_low))
        block.store(width_bits=8, address=self._address(block, self._pair16(block, "hl")), value=block.value(new_mem), alignment=1)
        block.write_state("cpu:a", block.value(new_a))
        s, z, pv = self._szp(block, block.value(new_a))
        self._set_flags(block, s, z, self._const_i1(block, False), pv, self._const_i1(block, False), self._flag_bit(block, z80.FLAG_C))

    def _incdec8_raw(self, block, name: str, delta: int) -> None:
        ctx = self.ctx
        before = self._r8(block, name)
        updated = ctx.tmp("v2")
        block.binop(updated, "i8", "add" if delta > 0 else "sub", before, self._const8(block, abs(delta)))
        block.write_state(f"cpu:{name}", block.value(updated))

    def _incdec16(self, block, name: str, delta: int) -> None:
        ctx = self.ctx
        updated = ctx.tmp("v2")
        block.binop(updated, "i16", "add" if delta > 0 else "sub", self._pair16(block, name), self._const16(block, abs(delta)))
        self._set_pair16(block, name, block.value(updated))

    def _bc_zero(self, block, tag: str) -> dict:
        ctx = self.ctx
        low = ctx.tmp(tag + "lo")
        high = ctx.tmp(tag + "hi")
        block.compare(low, "eq", self._r8(block, "c"), self._const8(block, 0))
        block.compare(high, "eq", self._r8(block, "b"), self._const8(block, 0))
        both = ctx.tmp(tag + "z")
        block.binop(both, "i1", "and", block.value(low), block.value(high))
        return block.value(both)

    def _bc_nonzero(self, block) -> dict:
        ctx = self.ctx
        low = ctx.tmp("bc_lo")
        high = ctx.tmp("bc_hi")
        block.compare(low, "ne", self._r8(block, "c"), self._const8(block, 0))
        block.compare(high, "ne", self._r8(block, "b"), self._const8(block, 0))
        both = ctx.tmp("bc_nz")
        block.binop(both, "i1", "or", block.value(low), block.value(high))
        return block.value(both)

    def _lower_block_op(self, block, insn: dict) -> None:
        ctx = self.ctx
        op = insn["op"]
        helper = self._helper_block(insn["address"])
        direction = -1 if op.endswith(("d", "dr")) else 1
        base = op[0]
        next_pc = (insn["address"] + insn["length"]) & 0xFFFF
        if base == "l":
            value = ctx.tmp("v")
            helper.load(value, "i8", width_bits=8, signed=False, address=self._address(helper, self._pair16(helper, "hl")), alignment=1)
            helper.store(width_bits=8, address=self._address(helper, self._pair16(helper, "de")), value=helper.value(value), alignment=1)
            self._incdec16(helper, "hl", direction)
            self._incdec16(helper, "de", direction)
            self._incdec16(helper, "bc", -1)
            self._write_f(helper, [
                (self._flag_bit(helper, z80.FLAG_S), SHIFT_S),
                (self._flag_bit(helper, z80.FLAG_Z), SHIFT_Z),
                (self._const_i1(helper, False), SHIFT_H),
                (self._bc_nonzero(helper), SHIFT_PV),
                (self._const_i1(helper, False), SHIFT_N),
                (self._flag_bit(helper, z80.FLAG_C), SHIFT_C),
            ])
        elif base == "c":
            value = ctx.tmp("v")
            helper.load(value, "i8", width_bits=8, signed=False, address=self._address(helper, self._pair16(helper, "hl")), alignment=1)
            self._alu8(helper, "cp", helper.value(value))
            self._incdec16(helper, "hl", direction)
            self._incdec16(helper, "bc", -1)
            # P/V = BC != 0 (overrides the CP parity); other CP flags kept
            pv = self._bc_nonzero(helper)
            pv8 = ctx.tmp("pv8")
            helper.cast(pv8, "i8", "zext", pv)
            pv2 = self._shl8(helper, helper.value(pv8), SHIFT_PV)
            keep = ctx.tmp("keep")
            helper.binop(keep, "i8", "and", self._read_f(helper), helper.const(0xFF ^ z80.FLAG_PV, "i8"))
            final = ctx.tmp("final")
            helper.binop(final, "i8", "or", helper.value(keep), helper.value(pv2))
            helper.write_state("cpu:f", helper.value(final))
        elif base == "i":
            value = ctx.tmp("v")
            helper.load(value, "i8", width_bits=8, signed=False, address=self._port_address(helper, self._pair16(helper, "bc")), alignment=1)
            helper.store(width_bits=8, address=self._address(helper, self._pair16(helper, "hl")), value=helper.value(value), alignment=1)
            self._incdec8_raw(helper, "b", -1)
            self._incdec16(helper, "hl", direction)
            z = ctx.tmp("zflag")
            pv = ctx.tmp("pvflag")
            helper.compare(z, "eq", self._r8(helper, "b"), self._const8(helper, 0))
            helper.compare(pv, "ne", self._r8(helper, "b"), self._const8(helper, 0))
            self._write_f(helper, [
                (self._flag_bit(helper, z80.FLAG_S), SHIFT_S),
                (helper.value(z), SHIFT_Z),
                (self._flag_bit(helper, z80.FLAG_H), SHIFT_H),
                (helper.value(pv), SHIFT_PV),
                (self._const_i1(helper, direction == -1), SHIFT_N),
                (self._flag_bit(helper, z80.FLAG_C), SHIFT_C),
            ])
        else:  # out family
            value = ctx.tmp("v")
            helper.load(value, "i8", width_bits=8, signed=False, address=self._address(helper, self._pair16(helper, "hl")), alignment=1)
            helper.store(width_bits=8, address=self._port_address(helper, self._pair16(helper, "bc")), value=helper.value(value), alignment=1)
            self._incdec8_raw(helper, "b", -1)
            self._incdec16(helper, "hl", direction)
            z = ctx.tmp("zflag")
            pv = ctx.tmp("pvflag")
            helper.compare(z, "eq", self._r8(helper, "b"), self._const8(helper, 0))
            helper.compare(pv, "ne", self._r8(helper, "b"), self._const8(helper, 0))
            self._write_f(helper, [
                (self._flag_bit(helper, z80.FLAG_S), SHIFT_S),
                (helper.value(z), SHIFT_Z),
                (self._flag_bit(helper, z80.FLAG_H), SHIFT_H),
                (helper.value(pv), SHIFT_PV),
                (self._const_i1(helper, direction == -1), SHIFT_N),
                (self._flag_bit(helper, z80.FLAG_C), SHIFT_C),
            ])
        repeat = ctx.tmp("repeat")
        if base in ("l", "c"):
            helper.compare(repeat, "eq", self._bc_zero(helper, "r"), self._const_i1(helper, False))
        else:
            b_nonzero = ctx.tmp("rbnz")
            helper.compare(b_nonzero, "ne", self._r8(helper, "b"), helper.const(0, "i8"))
            repeat = b_nonzero
        if base == "c":
            z_flag = self._flag_bit(helper, z80.FLAG_Z)
            not_z = ctx.tmp("rnotz")
            helper.compare(not_z, "eq", z_flag, self._const_i1(helper, False))
            combined = ctx.tmp("rcomb")
            helper.binop(combined, "i1", "and", helper.value(repeat), helper.value(not_z))
            repeat = combined
        if op.endswith(("ir", "dr")):
            block.jump(helper.block_id)
            helper.branch(helper.value(repeat), helper.block_id, self.cfg.block_id(next_pc))
        else:
            block.jump(helper.block_id)
            helper.jump(self.cfg.block_id(next_pc))

    # -- main dispatch ------------------------------------------------------
    def lower_instruction(self, block, insn: dict) -> None:
        op = insn["op"]
        ctx = self.ctx
        if op == "nop":
            return
        if op == "ld":
            self._lower_ld(block, insn)
        elif op in ("add", "adc", "sub", "sbc", "and", "xor", "or", "cp"):
            operand = self._const8(block, insn["imm8"]) if "imm8" in insn else self._r8(block, insn["r"])
            self._alu8(block, op, operand)
        elif op == "neg":
            self._neg(block)
        elif op == "daa":
            self._daa(block)
        elif op == "cpl":
            a = ctx.tmp("cpla")
            block.binop(a, "i8", "xor", self._r8(block, "a"), self._const8(block, 0xFF))
            block.write_state("cpu:a", block.value(a))
            self._write_f(block, [
                (self._flag_bit(block, z80.FLAG_S), SHIFT_S),
                (self._flag_bit(block, z80.FLAG_Z), SHIFT_Z),
                (self._const_i1(block, True), SHIFT_H),
                (self._flag_bit(block, z80.FLAG_PV), SHIFT_PV),
                (self._const_i1(block, True), SHIFT_N),
                (self._flag_bit(block, z80.FLAG_C), SHIFT_C),
            ])
        elif op == "scf":
            self._write_f(block, [
                (self._flag_bit(block, z80.FLAG_S), SHIFT_S),
                (self._flag_bit(block, z80.FLAG_Z), SHIFT_Z),
                (self._flag_bit(block, z80.FLAG_PV), SHIFT_PV),
                (self._const_i1(block, True), SHIFT_C),
            ])
        elif op == "ccf":
            carry = self._flag_bit(block, z80.FLAG_C)
            neg_c = ctx.tmp("negc")
            block.compare(neg_c, "eq", carry, self._const_i1(block, False))
            self._write_f(block, [
                (self._flag_bit(block, z80.FLAG_S), SHIFT_S),
                (self._flag_bit(block, z80.FLAG_Z), SHIFT_Z),
                (carry, SHIFT_H),
                (self._flag_bit(block, z80.FLAG_PV), SHIFT_PV),
                (block.value(neg_c), SHIFT_C),
            ])
        elif op in ("rlca", "rrca", "rla", "rra"):
            self._rotate_a(block, op)
        elif op in ("rlc", "rrc", "rl", "rr", "sla", "sra", "srl", "bit", "res", "set"):
            self._cb_op(block, insn, op)
        elif op == "rrd":
            self._rrd_rld(block, right=True)
        elif op == "rld":
            self._rrd_rld(block, right=False)
        elif op == "inc":
            name = insn["r"]
            if name in ("bc", "de", "hl", "sp", "ix", "iy"):
                self._incdec16(block, name, 1)
            else:
                self._inc8(block, name)
        elif op == "dec":
            name = insn["r"]
            if name in ("bc", "de", "hl", "sp", "ix", "iy"):
                self._incdec16(block, name, -1)
            else:
                self._dec8(block, name)
        elif op == "add_hl":
            self._add16(block, "hl", insn["pair"])
        elif op == "add_r16":
            self._add16(block, insn["dst"], insn["pair"])
        elif op == "adc_hl":
            self._adc_sbc_hl(block, insn["pair"], True)
        elif op == "sbc_hl":
            self._adc_sbc_hl(block, insn["pair"], False)
        elif op == "push":
            self._push(block, self._pair16(block, insn["pair"]))
        elif op == "pop":
            value = self._pop(block)
            if insn["pair"] == "af":
                high8 = ctx.tmp("hi8")
                low8 = ctx.tmp("lo8")
                block.cast(high8, "i8", "trunc", block.value(self._shr16(block, value, 8)))
                block.cast(low8, "i8", "trunc", value)
                block.write_state("cpu:a", block.value(high8))
                block.write_state("cpu:f", block.value(low8))
            else:
                self._set_pair16(block, insn["pair"], value)
        elif op == "in":
            self._lower_in(block, insn)
        elif op == "out":
            self._lower_out(block, insn)
        elif op in BLOCK_OPS:
            self._lower_block_op(block, insn)
        elif op == "ex":
            if insn.get("dst") == "(sp)":
                self._lower_ex_sp(block, insn)
            else:
                self._lower_ex_de_hl(block)
        elif op == "exx":
            self._lower_exx(block)
        elif op == "ex_af":
            self._lower_ex_af(block)
        elif op == "ld_sp_r16":
            block.write_state("cpu:sp", self._pair16(block, insn["reg"]))
        elif op == "di":
            block.write_state("platform:iff1", self._const_i1(block, False))
            block.write_state("platform:iff2", self._const_i1(block, False))
        elif op == "ei":
            block.write_state("platform:iff1", self._const_i1(block, True))
            block.write_state("platform:iff2", self._const_i1(block, True))
        elif op == "im":
            value = ctx.tmp("im8")
            block.const_result(value, "i8", insn["mode"])
            block.write_state("platform:im", block.value(value))
        else:
            raise Z80FrontendError(f"0x{insn['address']:x}: {op} cannot be lowered as a simple instruction")

    # -- terminators -----------------------------------------------------
    def lower_terminator(self, block, insn: dict) -> None:
        op = insn["op"]
        next_pc = (insn["address"] + insn["length"]) & 0xFFFF
        if op == "halt":
            block.write_state("platform:halted", self._const_i1(block, True))
            block.ret()
        elif op == "jp":
            target = self.cfg.block_id(insn["target"])
            if "cond" in insn:
                block.branch(self._condition(block, insn["cond"]), target, self.cfg.block_id(next_pc))
            else:
                block.jump(target)
        elif op == "jr":
            target = self.cfg.block_id(insn["target"])
            if "cond" in insn:
                block.branch(self._condition(block, insn["cond"]), target, self.cfg.block_id(next_pc))
            else:
                block.jump(target)
        elif op == "djnz":
            self._incdec8_raw(block, "b", -1)
            nonzero = self.ctx.tmp("bnz")
            block.compare(nonzero, "ne", self._r8(block, "b"), self._const8(block, 0))
            block.branch(block.value(nonzero), self.cfg.block_id(insn["target"]), self.cfg.block_id(next_pc))
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
                helper.indirect_jump(self._address(helper, target), list(self.all_block_ids))
            else:
                target = self._pop(block)
                block.indirect_jump(self._address(block, target), list(self.all_block_ids))
        elif op == "retn":
            target = self._pop(block)
            iff2 = self.ctx.tmp("iff2")
            block.read_state(iff2, "platform:iff2")
            block.write_state("platform:iff1", block.value(iff2))
            block.indirect_jump(self._address(block, target), list(self.all_block_ids))
        elif op == "reti":
            target = self._pop(block)
            block.indirect_jump(self._address(block, target), list(self.all_block_ids))
        elif op == "jp_ind":
            target = self._pair16(block, insn["reg"])
            block.indirect_jump(self._address(block, target), list(self.all_block_ids))
        else:
            raise Z80FrontendError(f"0x{insn['address']:x}: {op} is not a documented Z80 terminator")


def convert(memory_image: bytes, meta: dict, contract: dict) -> tuple[dict, dict, dict]:
    if meta.get("architecture") != "z80-sms":
        raise Z80FrontendError("frontend requires the z80-sms architecture profile")
    if contract.get("memory", {}).get("oob_policy") != "deterministic fault":
        raise Z80FrontendError("host memory contract must fail closed")
    if contract.get("system", {}).get("wall_clock") or contract.get("system", {}).get("randomness"):
        raise Z80FrontendError("host contract must remain deterministic")
    if len(memory_image) != 1 << 16:
        raise Z80FrontendError("the Z80 memory image must be exactly 64 KiB")

    instructions, leaders = _decode_region(memory_image, meta)
    if not instructions:
        raise Z80FrontendError("the code region contains no instructions")
    undecoded = leaders - set(instructions)
    if undecoded:
        raise Z80FrontendError(
            "branch target outside the decoded stream: " + ", ".join(f"0x{a:x}" for a in sorted(undecoded))
        )
    cfg = _build_cfg(instructions, leaders)

    input_sha256 = hashlib.sha256(memory_image).hexdigest()
    builder = IRBuilder(
        module_id="openrecomp.z80.synthetic.region-v1",
        architecture="z80-sms",
        adapter="openrecomp.z80-frontend-v1",
        address_bits=32,
        endianness="little",
        input_sha256=input_sha256,
        host_contract_version=contract["contract_version"],
    )
    for slot_id, type_name in {
        "cpu:a": "i8", "cpu:f": "i8", "cpu:b": "i8", "cpu:c": "i8",
        "cpu:d": "i8", "cpu:e": "i8", "cpu:h": "i8", "cpu:l": "i8",
        "cpu:a2": "i8", "cpu:f2": "i8", "cpu:b2": "i8", "cpu:c2": "i8",
        "cpu:d2": "i8", "cpu:e2": "i8", "cpu:h2": "i8", "cpu:l2": "i8",
        "cpu:ix": "i16", "cpu:iy": "i16", "cpu:sp": "i16",
        "cpu:i": "i8", "cpu:r": "i8",
        "platform:iff1": "i1", "platform:iff2": "i1",
        "platform:im": "i8", "platform:halted": "i1",
    }.items():
        builder.declare_state_slot(slot_id, type_name)

    function = builder.add_function("main", meta["entry_address"], return_type=None)
    ctx = _Context(builder, meta, memory_image)
    ctx.current_d = 0
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
            ctx.current_d = insn.get("d", 0)
            if is_control_flow(insn) or insn["op"] == "halt":
                lowerer.lower_terminator(block, insn)
                terminated = True
                break
            lowerer.lower_instruction(block, insn)
            if insn["op"] in BLOCK_OPS:
                terminated = True  # block-op lowering emits its own jump to the helper
                break
            pc += insn["length"]
        if not terminated:
            if end in cfg.block_by_address:
                block.jump(cfg.block_id(end))
            else:
                if any(range_start == end for range_start, _range_end in ranges):
                    raise Z80FrontendError(f"0x{leader:x}: block falls through into a declared data range")
                raise Z80FrontendError(f"0x{leader:x}: block reaches the region end without a terminator")

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
        {"name": "guest-memory", "guest_address": 0, "data_hex": memory_image.hex()},
        {"name": "guest-ports", "guest_address": PORT_BASE, "data_hex": bytes(256).hex()},
    ]
    report = {
        "architecture": "z80-sms",
        "frontend_version": FRONTEND_VERSION,
        "source_input_sha256": input_sha256,
        "functions": 1,
        "instructions": len(instructions),
        "blocks": len(ordered),
        "source_region": [meta["region_start"], meta["region_end"]],
    }
    return ir, sidecar, report


def main(argv: list[str]) -> int:
    if len(argv) != 6:
        print(
            "usage: z80_frontend_v1.py <fixture.json> <host-contract.json> <out-ir.json> <out-sidecar.json> <out-report.json>",
            file=sys.stderr,
        )
        return 2
    try:
        meta = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        contract = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        memory_image = bytes.fromhex(meta["memory_image_hex"])
        ir, sidecar, report = convert(memory_image, meta, contract)
        Path(argv[3]).write_text(json.dumps(ir, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        Path(argv[4]).write_text(json.dumps(sidecar, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        Path(argv[5]).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, KeyError, ValueError, Z80Error, Z80FrontendError, ScaffoldError) as exc:
        print(f"OPENRECOMP_Z80_FRONTEND_V1=FAIL: {exc}", file=sys.stderr)
        return 2
    print(f"Z80_FRONTEND_INSTRUCTIONS={report['instructions']}")
    print(f"Z80_FRONTEND_BLOCKS={report['blocks']}")
    print("OPENRECOMP_Z80_FRONTEND_V1=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
