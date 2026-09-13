#!/usr/bin/env python3
"""NES 6502 frontend: control flow + lowering into normalized IR V1 (P1-31).

Converts a bounded synthetic NMOS 6502 code region into architecture-neutral
normalized IR V1 using the shared scaffolding
(`openrecomp/frontends/scaffold.py`) and the documented decode + state model
(`adapters/nes6502.py`). The independent machine-code reference semantics live
in `tools/nes6502_reference_v1.py`; the P1-31 differential proof runs the same
fixture through both and requires identical final state and memory.

Control-flow model (documented NES 6502 behaviour):

- one IR function per converted program region (the guest stack is modelled in
  guest memory, exactly like hardware);
- `jmp abs`, `jsr` and the eight conditional branches have static targets that
  become leaders; conditional branches and `jsr` also create a fallthrough
  leader;
- `jmp (indirect)` applies the documented NMOS page-boundary bug (the high byte
  of the vector is read from the same page as the low byte);
- `rts`, `rti`, `jmp (indirect)` and the `brk` vector become `indirect_jump`
  terminators whose candidate set is every block of the function;
- `brk` pushes PC+2 and P (with B set), sets I and jumps through the IRQ vector
  at 0xFFFE; `rti` pulls P (B ignored, unused set) and PC; `rts` pulls PC+1;
- flag writes only touch the documented bits: N/V/D/I/Z/C are stored, the
  unused bit is always 1 and the B flag has no storage;
- the NES 2A03 has no decimal mode, so ADC/SBC lower to binary arithmetic and
  D is preserved, never consumed;
- the undocumented KIL/JAM opcode (0x02) is used only as the synthetic
  test-harness halt convention (`adapters/nes6502.HALT_OPCODE`): it writes
  `platform:halted` and `cpu:pc`, then returns;
- a leader target that lands inside an instruction (or an instruction that
  overlaps the region boundary) raises `NES6502FrontendError` — fail closed;
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

from adapters.nes6502 import (  # noqa: E402
    FLAG_B,
    FLAG_C,
    FLAG_D,
    FLAG_I,
    FLAG_N,
    FLAG_UNUSED,
    FLAG_V,
    FLAG_Z,
    HALT_OPCODE,
    NES6502Error,
    decode_full,
    is_control_flow,
)
from openrecomp.frontends.scaffold import IRBuilder, ScaffoldError  # noqa: E402

FRONTEND_VERSION = "1.0.0"

SHIFT_C, SHIFT_Z, SHIFT_I, SHIFT_D, SHIFT_B, SHIFT_U, SHIFT_V, SHIFT_N = 0, 1, 2, 3, 4, 5, 6, 7

# op -> (tested flag mask, taken-when-set)
COND_MASK = {
    "bpl": (FLAG_N, False), "bmi": (FLAG_N, True),
    "bvc": (FLAG_V, False), "bvs": (FLAG_V, True),
    "bcc": (FLAG_C, False), "bcs": (FLAG_C, True),
    "bne": (FLAG_Z, False), "beq": (FLAG_Z, True),
}

BRANCH_OPS = frozenset(COND_MASK)
TERMINATOR_OPS = frozenset({"jmp", "jsr", "rts", "rti", "brk", "halt"}) | BRANCH_OPS


class NES6502FrontendError(ValueError):
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
            raise NES6502FrontendError(f"0x{address:x}: control-flow target is not a decoded block leader")
        return block_id


def _validated_data_ranges(meta: dict, start: int, end: int) -> list[tuple[int, int]]:
    ranges = meta.get("data_ranges")
    if ranges is None:
        return []
    if not isinstance(ranges, list):
        raise NES6502FrontendError("data_ranges must be a list of [start, end) pairs")
    parsed: list[tuple[int, int]] = []
    for item in ranges:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise NES6502FrontendError("each data range must be a [start, end) pair")
        range_start, range_end = item
        if (
            isinstance(range_start, bool)
            or isinstance(range_end, bool)
            or not isinstance(range_start, int)
            or not isinstance(range_end, int)
            or not (start <= range_start < range_end <= end)
        ):
            raise NES6502FrontendError(f"data range [{range_start!r}, {range_end!r}) is invalid for [{start:#x}, {end:#x})")
        parsed.append((range_start, range_end))
    parsed.sort()
    for (s1, e1), (s2, e2) in zip(parsed, parsed[1:]):
        if s2 < e1:
            raise NES6502FrontendError(f"data ranges overlap: [{s1:#x}, {e1:#x}) and [{s2:#x}, {e2:#x})")
    return parsed


def _inside_data(address: int, ranges: list[tuple[int, int]]) -> bool:
    return any(range_start <= address < range_end for range_start, range_end in ranges)


def _decode_one(code: bytes, pc: int) -> dict:
    if code[pc] == HALT_OPCODE:
        return {"address": pc, "word": HALT_OPCODE, "op": "halt", "length": 1}
    return decode_full(code, pc)


def _decode_region(code: bytes, meta: dict) -> tuple[dict[int, dict], set[int]]:
    start = meta["region_start"]
    end = meta["region_end"]
    entry = meta["entry_address"]
    if not (0 <= start < end <= len(code)):
        raise NES6502FrontendError("code region is outside the memory image")
    if not (start <= entry < end):
        raise NES6502FrontendError("entry address is outside the code region")
    ranges = _validated_data_ranges(meta, start, end)
    if _inside_data(start, ranges):
        raise NES6502FrontendError("the code region starts inside a declared data range")
    if _inside_data(entry, ranges):
        raise NES6502FrontendError("the entry address lies inside a declared data range")

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
                insn = _decode_one(code, pc)
            except NES6502Error as exc:
                raise NES6502FrontendError(f"decode rejected: {exc}") from exc
            instructions[pc] = insn
            op = insn["op"]
            if op == "halt":
                pc += insn["length"]
                continue
            if is_control_flow(insn):
                static_targets = []
                if op in BRANCH_OPS or op == "jsr" or (op == "jmp" and "indirect" not in insn):
                    if isinstance(insn.get("target"), int):
                        static_targets.append(insn["target"])
                for target in static_targets:
                    if not (start <= target < end):
                        raise NES6502FrontendError(f"0x{pc:x}: control-flow target 0x{target:x} leaves the region")
                    if _inside_data(target, ranges):
                        raise NES6502FrontendError(f"0x{pc:x}: control-flow target 0x{target:x} is inside a declared data range")
                    leaders.add(target)
                needs_fallthrough = op in BRANCH_OPS or op == "jsr"
                if needs_fallthrough:
                    fallthrough = pc + insn["length"]
                    if fallthrough >= end:
                        raise NES6502FrontendError(f"0x{pc:x}: fallthrough leaves the region")
                    if _inside_data(fallthrough, ranges) or fallthrough == span_end and span_end < end:
                        raise NES6502FrontendError(f"0x{pc:x}: fallthrough enters a declared data range")
                    leaders.add(fallthrough)
                if op == "brk":
                    # BRK pushes PC+2, so the instruction after the padding byte
                    # is a legitimate RTI return target (a leader).
                    resume = pc + 2
                    if resume < end and not _inside_data(resume, ranges):
                        leaders.add(resume)
            pc += insn["length"]
            if pc > span_end:
                raise NES6502FrontendError(
                    f"0x{pc - insn['length']:x}: instruction overlaps the code/data boundary at 0x{span_end:x}"
                )
    return instructions, leaders


def _build_cfg(instructions: dict[int, dict], leaders: set[int]) -> _Cfg:
    cfg = _Cfg(instructions, leaders)
    for leader in sorted(leaders):
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

    def _helper_block(self, address: int):
        self.helper_counter += 1
        return self.function.add_block(f"b_{address:04x}_h{self.helper_counter}", address)

    # -- constant / value helpers ----------------------------------------
    def _const8(self, block, value: int) -> dict:
        return block.const(value & 0xFF, "i8")

    def _const16(self, block, value: int) -> dict:
        return block.const(value & 0xFFFF, "i16")

    def _const_i1(self, block, value: bool) -> dict:
        result = self.ctx.tmp("ci1")
        block.const_result(result, "i1", 1 if value else 0)
        return block.value(result)

    def _bool8(self, block, value8: dict) -> dict:
        result = self.ctx.tmp("bool")
        block.compare(result, "ne", value8, self._const8(block, 0))
        return block.value(result)

    def _r8(self, block, name: str) -> dict:
        result = self.ctx.tmp(name)
        block.read_state(result, f"cpu:{name}")
        return block.value(result)

    def _write_r8(self, block, name: str, value: dict) -> None:
        block.write_state(f"cpu:{name}", value)

    def _zext16(self, block, value8: dict) -> dict:
        result = self.ctx.tmp("z16")
        block.cast(result, "i16", "zext", value8)
        return block.value(result)

    def _shr16(self, block, value16: dict, amount: int) -> dict:
        result = self.ctx.tmp("shr")
        block.binop(result, "i16", "lshr", value16, self._const16(block, amount))
        return block.value(result)

    def _trunc8(self, block, value: any) -> dict:
        result = self.ctx.tmp("t8")
        block.cast(result, "i8", "trunc", value)
        return block.value(result)

    def _address(self, block, value16: dict) -> dict:
        result = self.ctx.tmp("addr")
        block.zext_to_address(result, value16)
        return block.value(result)

    def _load8(self, block, address32: dict, tag: str = "mem") -> dict:
        result = self.ctx.tmp(tag)
        block.load(result, "i8", width_bits=8, signed=False, address=address32, alignment=1)
        return block.value(result)

    def _store8(self, block, address32: dict, value8: dict) -> None:
        block.store(width_bits=8, address=address32, value=value8, alignment=1)

    def _load16(self, block, address32: dict, tag: str = "mem16") -> dict:
        result = self.ctx.tmp(tag)
        block.load(result, "i16", width_bits=16, signed=False, address=address32, alignment=1)
        return block.value(result)

    # -- flags ------------------------------------------------------------
    def _flag_bit(self, block, mask: int) -> dict:
        p = self._read_p(block)
        masked = self.ctx.tmp("fmask")
        block.binop(masked, "i8", "and", p, self._const8(block, mask))
        return self._bool8(block, block.value(masked))

    def _read_p(self, block) -> dict:
        result = self.ctx.tmp("p")
        block.read_state(result, "cpu:p")
        return block.value(result)

    def _f_byte(self, block, bits: list[tuple[dict, int]]) -> dict:
        acc = self.ctx.tmp("facc")
        block.const_result(acc, "i8", 0)
        for value, shift in bits:
            v8 = self.ctx.tmp("fb")
            block.cast(v8, "i8", "zext", value)
            if shift:
                shifted = self.ctx.tmp("fs")
                block.binop(shifted, "i8", "shl", block.value(v8), self._const8(block, shift))
            else:
                shifted = v8
            combined = self.ctx.tmp("fc")
            block.binop(combined, "i8", "or", block.value(acc), block.value(shifted))
            acc = combined
        return block.value(acc)

    def _write_p(self, block, *, n=None, z=None, c=None, v=None, d=None, i=None) -> None:
        bits = [
            (n if n is not None else self._flag_bit(block, FLAG_N), SHIFT_N),
            (v if v is not None else self._flag_bit(block, FLAG_V), SHIFT_V),
            (self._const_i1(block, True), SHIFT_U),
            (self._const_i1(block, False), SHIFT_B),
            (d if d is not None else self._flag_bit(block, FLAG_D), SHIFT_D),
            (i if i is not None else self._flag_bit(block, FLAG_I), SHIFT_I),
            (z if z is not None else self._flag_bit(block, FLAG_Z), SHIFT_Z),
            (c if c is not None else self._flag_bit(block, FLAG_C), SHIFT_C),
        ]
        block.write_state("cpu:p", self._f_byte(block, bits))

    def _nz(self, block, value8: dict) -> tuple[dict, dict]:
        n = self.ctx.tmp("nflag")
        z = self.ctx.tmp("zflag")
        block.compare(n, "slt", value8, self._const8(block, 0))
        block.compare(z, "eq", value8, self._const8(block, 0))
        return block.value(n), block.value(z)

    def _set_nz(self, block, value8: dict) -> None:
        n, z = self._nz(block, value8)
        self._write_p(block, n=n, z=z)

    # -- operands ---------------------------------------------------------
    def _zp_pointer(self, block, zp_addr8: dict, tag: str) -> dict:
        lo = self._load8(block, self._address(block, self._zext16(block, zp_addr8)), tag + "_lo")
        next_addr = self.ctx.tmp(tag + "_n")
        block.binop(next_addr, "i8", "add", zp_addr8, self._const8(block, 1))
        hi = self._load8(block, self._address(block, self._zext16(block, block.value(next_addr))), tag + "_hi")
        hi16 = self._zext16(block, hi)
        shifted = self.ctx.tmp(tag + "_sh")
        block.binop(shifted, "i16", "shl", hi16, self._const16(block, 8))
        combined = self.ctx.tmp(tag + "_ptr")
        block.binop(combined, "i16", "or", block.value(shifted), self._zext16(block, lo))
        return block.value(combined)

    def _operand_address(self, block, insn: dict) -> dict:
        if "zp" in insn:
            addr16 = self._const16(block, insn["zp"])
        elif "zp,x" in insn:
            idx = self.ctx.tmp("zpx")
            block.binop(idx, "i8", "add", block.const(insn["zp,x"], "i8"), self._r8(block, "x"))
            addr16 = self._zext16(block, block.value(idx))
        elif "zp,y" in insn:
            idx = self.ctx.tmp("zpy")
            block.binop(idx, "i8", "add", block.const(insn["zp,y"], "i8"), self._r8(block, "y"))
            addr16 = self._zext16(block, block.value(idx))
        elif "abs" in insn:
            addr16 = self._const16(block, insn["abs"])
        elif "abs,x" in insn:
            addr = self.ctx.tmp("absx")
            block.binop(addr, "i16", "add", self._const16(block, insn["abs,x"]), self._zext16(block, self._r8(block, "x")))
            addr16 = block.value(addr)
        elif "abs,y" in insn:
            addr = self.ctx.tmp("absy")
            block.binop(addr, "i16", "add", self._const16(block, insn["abs,y"]), self._zext16(block, self._r8(block, "y")))
            addr16 = block.value(addr)
        elif "indirect,x" in insn:
            idx = self.ctx.tmp("indx")
            block.binop(idx, "i8", "add", block.const(insn["indirect,x"], "i8"), self._r8(block, "x"))
            addr16 = self._zp_pointer(block, block.value(idx), "indx")
        elif "indirect,y" in insn:
            ptr = self._zp_pointer(block, block.const(insn["indirect,y"], "i8"), "indy")
            addr = self.ctx.tmp("indy")
            block.binop(addr, "i16", "add", ptr, self._zext16(block, self._r8(block, "y")))
            addr16 = block.value(addr)
        else:
            raise NES6502FrontendError(f"0x{insn['address']:x}: unsupported addressing form {insn}")
        return self._address(block, addr16)

    def _read_operand(self, block, insn: dict) -> dict:
        if "imm8" in insn:
            return block.const(insn["imm8"], "i8")
        return self._load8(block, self._operand_address(block, insn), "opd")

    def _write_operand(self, block, insn: dict, value8: dict) -> None:
        if "imm8" in insn:
            raise NES6502FrontendError(f"0x{insn['address']:x}: immediate operand cannot be a destination")
        self._store8(block, self._operand_address(block, insn), value8)

    # -- stack ------------------------------------------------------------
    def _push8(self, block, value8: dict) -> None:
        sp = self._r8(block, "sp")
        base = self.ctx.tmp("spbase")
        block.binop(base, "i16", "or", self._const16(block, 0x0100), self._zext16(block, sp))
        self._store8(block, self._address(block, block.value(base)), value8)
        new_sp = self.ctx.tmp("spd")
        block.binop(new_sp, "i8", "sub", sp, self._const8(block, 1))
        self._write_r8(block, "sp", block.value(new_sp))

    def _pop8(self, block) -> dict:
        sp = self._r8(block, "sp")
        new_sp = self.ctx.tmp("spi")
        block.binop(new_sp, "i8", "add", sp, self._const8(block, 1))
        self._write_r8(block, "sp", block.value(new_sp))
        base = self.ctx.tmp("spbase")
        block.binop(base, "i16", "or", self._const16(block, 0x0100), self._zext16(block, block.value(new_sp)))
        return self._load8(block, self._address(block, block.value(base)), "pop")

    def _push16(self, block, value16: dict) -> None:
        hi = self._trunc8(block, self._shr16(block, value16, 8))
        lo = self._trunc8(block, value16)
        self._push8(block, hi)
        self._push8(block, lo)

    def _pop16(self, block) -> dict:
        lo = self._pop8(block)
        hi = self._pop8(block)
        hi16 = self._zext16(block, hi)
        shifted = self.ctx.tmp("popsh")
        block.binop(shifted, "i16", "shl", hi16, self._const16(block, 8))
        combined = self.ctx.tmp("pop16")
        block.binop(combined, "i16", "or", block.value(shifted), self._zext16(block, lo))
        return block.value(combined)

    # -- ALU --------------------------------------------------------------
    def _ov_add(self, block, a8: dict, b8: dict, r8: dict) -> dict:
        x1 = self.ctx.tmp("oax")
        x2 = self.ctx.tmp("obx")
        block.binop(x1, "i8", "xor", a8, r8)
        block.binop(x2, "i8", "xor", b8, r8)
        both = self.ctx.tmp("oboth")
        block.binop(both, "i8", "and", block.value(x1), block.value(x2))
        return self._bool8(block, self._mask(block, block.value(both), 0x80))

    def _ov_sub(self, block, a8: dict, b8: dict, r8: dict) -> dict:
        x1 = self.ctx.tmp("oab")
        x2 = self.ctx.tmp("oar")
        block.binop(x1, "i8", "xor", a8, b8)
        block.binop(x2, "i8", "xor", a8, r8)
        both = self.ctx.tmp("oboth")
        block.binop(both, "i8", "and", block.value(x1), block.value(x2))
        return self._bool8(block, self._mask(block, block.value(both), 0x80))

    def _adc(self, block, operand8: dict) -> None:
        a = self._r8(block, "a")
        carry = self._flag_bit(block, FLAG_C)
        a16 = self._zext16(block, a)
        o16 = self._zext16(block, operand8)
        c16 = self._zext16(block, carry)
        t = self.ctx.tmp("adct")
        block.binop(t, "i16", "add", a16, o16)
        res16 = self.ctx.tmp("adc16")
        block.binop(res16, "i16", "add", block.value(t), c16)
        res8 = self._trunc8(block, block.value(res16))
        c_out = self.ctx.tmp("adcc")
        block.compare(c_out, "ugt", block.value(res16), self._const16(block, 0xFF))
        n, z = self._nz(block, res8)
        self._write_r8(block, "a", res8)
        self._write_p(block, n=n, z=z, c=block.value(c_out), v=self._ov_add(block, a, operand8, res8))

    def _sbc(self, block, operand8: dict) -> None:
        a = self._r8(block, "a")
        carry = self._flag_bit(block, FLAG_C)
        borrow = self.ctx.tmp("sbcb")
        block.compare(borrow, "eq", carry, self._const_i1(block, False))
        a16 = self._zext16(block, a)
        o16 = self._zext16(block, operand8)
        b16 = self._zext16(block, block.value(borrow))
        t = self.ctx.tmp("sbct")
        block.binop(t, "i16", "sub", a16, o16)
        res16 = self.ctx.tmp("sbc16")
        block.binop(res16, "i16", "sub", block.value(t), b16)
        res8 = self._trunc8(block, block.value(res16))
        c_out = self.ctx.tmp("sbcc")
        block.compare(c_out, "sge", block.value(res16), self._const16(block, 0))
        n, z = self._nz(block, res8)
        self._write_r8(block, "a", res8)
        self._write_p(block, n=n, z=z, c=block.value(c_out), v=self._ov_sub(block, a, operand8, res8))

    def _cmp(self, block, register: str, operand8: dict) -> None:
        value = self._r8(block, register)
        res = self.ctx.tmp("cmp")
        block.binop(res, "i8", "sub", value, operand8)
        res8 = block.value(res)
        n, z = self._nz(block, res8)
        c_out = self.ctx.tmp("cmpc")
        block.compare(c_out, "uge", value, operand8)
        self._write_p(block, n=n, z=z, c=block.value(c_out))

    def _shift(self, block, kind: str, value8: dict) -> tuple[dict, dict]:
        """Return (result8, carry_i1) for the documented shift/rotate."""
        ctx = self.ctx
        if kind == "asl":
            c = self._bool8(block, self._mask(block, value8, 0x80))
            res = ctx.tmp("asl")
            block.binop(res, "i8", "shl", value8, self._const8(block, 1))
            return block.value(res), c
        if kind == "lsr":
            c = self._bool8(block, self._mask(block, value8, 0x01))
            res = ctx.tmp("lsr")
            block.binop(res, "i8", "lshr", value8, self._const8(block, 1))
            return block.value(res), c
        carry = self._flag_bit(block, FLAG_C)
        c8 = ctx.tmp("cin")
        block.cast(c8, "i8", "zext", carry)
        if kind == "rol":
            c = self._bool8(block, self._mask(block, value8, 0x80))
            shifted = ctx.tmp("rols")
            block.binop(shifted, "i8", "shl", value8, self._const8(block, 1))
            res = ctx.tmp("rol")
            block.binop(res, "i8", "or", block.value(shifted), block.value(c8))
            return block.value(res), c
        # ror
        c = self._bool8(block, self._mask(block, value8, 0x01))
        shifted = ctx.tmp("rors")
        block.binop(shifted, "i8", "lshr", value8, self._const8(block, 1))
        c7 = ctx.tmp("cin7")
        block.binop(c7, "i8", "shl", block.value(c8), self._const8(block, 7))
        res = ctx.tmp("ror")
        block.binop(res, "i8", "or", block.value(shifted), block.value(c7))
        return block.value(res), c

    def _mask(self, block, value8: dict, mask: int) -> dict:
        result = self.ctx.tmp("band")
        block.binop(result, "i8", "and", value8, self._const8(block, mask))
        return block.value(result)

    # -- instruction dispatch --------------------------------------------
    def lower_instruction(self, block, insn: dict) -> None:
        op = insn["op"]
        if op == "nop":
            return
        if op == "lda":
            value = self._read_operand(block, insn)
            self._write_r8(block, "a", value)
            self._set_nz(block, value)
        elif op == "ldx":
            value = self._read_operand(block, insn)
            self._write_r8(block, "x", value)
            self._set_nz(block, value)
        elif op == "ldy":
            value = self._read_operand(block, insn)
            self._write_r8(block, "y", value)
            self._set_nz(block, value)
        elif op == "sta":
            self._write_operand(block, insn, self._r8(block, "a"))
        elif op == "stx":
            self._write_operand(block, insn, self._r8(block, "x"))
        elif op == "sty":
            self._write_operand(block, insn, self._r8(block, "y"))
        elif op in ("tax", "tay", "txa", "tya", "tsx"):
            source = {"tax": "a", "tay": "a", "txa": "x", "tya": "y", "tsx": "sp"}[op]
            dest = {"tax": "x", "tay": "y", "txa": "a", "tya": "a", "tsx": "x"}[op]
            value = self._r8(block, source)
            self._write_r8(block, dest, value)
            self._set_nz(block, value)
        elif op == "txs":
            self._write_r8(block, "sp", self._r8(block, "x"))
        elif op == "pha":
            self._push8(block, self._r8(block, "a"))
        elif op == "php":
            p = self._read_p(block)
            tagged = self.ctx.tmp("php")
            block.binop(tagged, "i8", "or", p, self._const8(block, FLAG_B | FLAG_UNUSED))
            self._push8(block, block.value(tagged))
        elif op == "pla":
            value = self._pop8(block)
            self._write_r8(block, "a", value)
            self._set_nz(block, value)
        elif op == "plp":
            raw = self._pop8(block)
            self._write_p_from_stack(block, raw)
        elif op in ("and", "ora", "eor"):
            operand = self._read_operand(block, insn)
            result = self.ctx.tmp("logic")
            block.binop(result, "i8", {"and": "and", "ora": "or", "eor": "xor"}[op], self._r8(block, "a"), operand)
            value = block.value(result)
            self._write_r8(block, "a", value)
            self._set_nz(block, value)
        elif op == "bit":
            operand = self._read_operand(block, insn)
            z = self.ctx.tmp("bitz")
            andv = self.ctx.tmp("bita")
            block.binop(andv, "i8", "and", self._r8(block, "a"), operand)
            block.compare(z, "eq", block.value(andv), self._const8(block, 0))
            n = self._bool8(block, self._mask(block, operand, 0x80))
            v = self._bool8(block, self._mask(block, operand, 0x40))
            self._write_p(block, n=n, v=v, z=block.value(z))
        elif op == "adc":
            self._adc(block, self._read_operand(block, insn))
        elif op == "sbc":
            self._sbc(block, self._read_operand(block, insn))
        elif op == "cmp":
            self._cmp(block, "a", self._read_operand(block, insn))
        elif op == "cpx":
            self._cmp(block, "x", self._read_operand(block, insn))
        elif op == "cpy":
            self._cmp(block, "y", self._read_operand(block, insn))
        elif op in ("inc", "dec"):
            address = self._operand_address(block, insn)
            value = self._load8(block, address, "rmw")
            result = self.ctx.tmp("rmwr")
            block.binop(result, "i8", "add" if op == "inc" else "sub", value, self._const8(block, 1))
            new_value = block.value(result)
            self._store8(block, address, new_value)
            self._set_nz(block, new_value)
        elif op in ("inx", "iny", "dex", "dey"):
            reg = {"inx": "x", "iny": "y", "dex": "x", "dey": "y"}[op]
            delta = 1 if op in ("inx", "iny") else -1
            result = self.ctx.tmp("incdec")
            block.binop(result, "i8", "add" if delta > 0 else "sub", self._r8(block, reg), self._const8(block, abs(delta)))
            value = block.value(result)
            self._write_r8(block, reg, value)
            self._set_nz(block, value)
        elif op in ("asl", "lsr", "rol", "ror"):
            if insn.get("dst") == "a":
                value = self._r8(block, "a")
                result, carry = self._shift(block, op, value)
                self._write_r8(block, "a", result)
            else:
                address = self._operand_address(block, insn)
                value = self._load8(block, address, "shf")
                result, carry = self._shift(block, op, value)
                self._store8(block, address, result)
            n, z = self._nz(block, result)
            self._write_p(block, n=n, z=z, c=carry)
        elif op == "clc":
            self._write_p(block, c=self._const_i1(block, False))
        elif op == "sec":
            self._write_p(block, c=self._const_i1(block, True))
        elif op == "cli":
            self._write_p(block, i=self._const_i1(block, False))
        elif op == "sei":
            self._write_p(block, i=self._const_i1(block, True))
        elif op == "clv":
            self._write_p(block, v=self._const_i1(block, False))
        elif op == "cld":
            self._write_p(block, d=self._const_i1(block, False))
        elif op == "sed":
            self._write_p(block, d=self._const_i1(block, True))
        else:
            raise NES6502FrontendError(f"0x{insn['address']:x}: {op} cannot be lowered as a simple instruction")

    def _write_p_from_stack(self, block, raw8: dict) -> None:
        cleaned = self.ctx.tmp("plp")
        block.binop(cleaned, "i8", "or", raw8, self._const8(block, FLAG_UNUSED))
        masked = self.ctx.tmp("plpm")
        block.binop(masked, "i8", "and", block.value(cleaned), self._const8(block, 0xFF & ~FLAG_B))
        block.write_state("cpu:p", block.value(masked))

    # -- terminators -------------------------------------------------------
    def _next_pc(self, insn: dict) -> int:
        return (insn["address"] + insn["length"]) & 0xFFFF

    def lower_terminator(self, block, insn: dict) -> None:
        op = insn["op"]
        next_pc = self._next_pc(insn)
        if op == "halt":
            result = self.ctx.tmp("haltpc")
            block.const_result(result, "i16", insn["address"] & 0xFFFF)
            block.write_state("cpu:pc", block.value(result))
            block.write_state("platform:halted", self._const_i1(block, True))
            block.ret()
        elif op == "jmp":
            if "indirect" in insn:
                pointer = self._const16(block, insn["indirect"])
                lo = self._load8(block, self._address(block, pointer), "jlo")
                masked = self.ctx.tmp("jhi_addr")
                block.binop(masked, "i16", "and", pointer, self._const16(block, 0xFF00))
                next = self.ctx.tmp("jhi_next")
                block.binop(next, "i16", "add", pointer, self._const16(block, 1))
                low8 = self.ctx.tmp("jhi_low")
                block.binop(low8, "i16", "and", block.value(next), self._const16(block, 0x00FF))
                hi_addr = self.ctx.tmp("jhi")
                block.binop(hi_addr, "i16", "or", block.value(masked), block.value(low8))
                hi = self._load8(block, self._address(block, block.value(hi_addr)), "jhi_v")
                hi16 = self._zext16(block, hi)
                shifted = self.ctx.tmp("jsh")
                block.binop(shifted, "i16", "shl", hi16, self._const16(block, 8))
                target16 = self.ctx.tmp("jt")
                block.binop(target16, "i16", "or", block.value(shifted), self._zext16(block, lo))
                block.indirect_jump(self._address(block, block.value(target16)), list(self.all_block_ids))
            else:
                block.jump(self.cfg.block_id(insn["target"]))
        elif op in BRANCH_OPS:
            mask, taken_when_set = COND_MASK[op]
            flag = self._flag_bit(block, mask)
            condition = flag
            if not taken_when_set:
                negated = self.ctx.tmp("notcond")
                block.compare(negated, "eq", flag, self._const_i1(block, False))
                condition = block.value(negated)
            block.branch(condition, self.cfg.block_id(insn["target"]), self.cfg.block_id(next_pc))
        elif op == "jsr":
            self._push16(block, self._const16(block, (insn["address"] + 2) & 0xFFFF))
            block.jump(self.cfg.block_id(insn["target"]))
        elif op == "rts":
            popped = self._pop16(block)
            plus1 = self.ctx.tmp("rts")
            block.binop(plus1, "i16", "add", popped, self._const16(block, 1))
            block.indirect_jump(self._address(block, block.value(plus1)), list(self.all_block_ids))
        elif op == "rti":
            raw = self._pop8(block)
            self._write_p_from_stack(block, raw)
            target16 = self._pop16(block)
            block.indirect_jump(self._address(block, target16), list(self.all_block_ids))
        elif op == "brk":
            self._push16(block, self._const16(block, (insn["address"] + 2) & 0xFFFF))
            p = self._read_p(block)
            tagged = self.ctx.tmp("brkp")
            block.binop(tagged, "i8", "or", p, self._const8(block, FLAG_B | FLAG_UNUSED))
            self._push8(block, block.value(tagged))
            seti = self.ctx.tmp("brki")
            block.binop(seti, "i8", "or", p, self._const8(block, FLAG_I))
            block.write_state("cpu:p", block.value(seti))
            vector = self._load16(block, self._address(block, self._const16(block, 0xFFFE)), "brkv")
            block.indirect_jump(self._address(block, vector), list(self.all_block_ids))
        else:
            raise NES6502FrontendError(f"0x{insn['address']:x}: {op} is not a documented 6502 terminator")


def convert(memory_image: bytes, meta: dict, contract: dict) -> tuple[dict, dict, dict]:
    if meta.get("architecture") != "nes6502":
        raise NES6502FrontendError("frontend requires the nes6502 architecture profile")
    if contract.get("memory", {}).get("oob_policy") != "deterministic fault":
        raise NES6502FrontendError("host memory contract must fail closed")
    if contract.get("system", {}).get("wall_clock") or contract.get("system", {}).get("randomness"):
        raise NES6502FrontendError("host contract must remain deterministic")
    if len(memory_image) != 1 << 16:
        raise NES6502FrontendError("the 6502 memory image must be exactly 64 KiB")

    instructions, leaders = _decode_region(memory_image, meta)
    if not instructions:
        raise NES6502FrontendError("the code region contains no instructions")
    for extra in meta.get("extra_leaders", []) or []:
        if isinstance(extra, bool) or not isinstance(extra, int) or not (meta["region_start"] <= extra < meta["region_end"]):
            raise NES6502FrontendError(f"extra leader 0x{extra!r} is outside the code region")
        leaders.add(extra)
    undecoded = leaders - set(instructions)
    if undecoded:
        raise NES6502FrontendError(
            "branch target outside the decoded stream: " + ", ".join(f"0x{a:x}" for a in sorted(undecoded))
        )
    cfg = _build_cfg(instructions, leaders)

    input_sha256 = hashlib.sha256(memory_image).hexdigest()
    builder = IRBuilder(
        module_id="openrecomp.nes6502.synthetic.region-v1",
        architecture="nes6502",
        adapter="openrecomp.nes6502-frontend-v1",
        address_bits=32,
        endianness="little",
        input_sha256=input_sha256,
        host_contract_version=contract["contract_version"],
    )
    for slot_id, type_name in {
        "cpu:a": "i8", "cpu:x": "i8", "cpu:y": "i8", "cpu:sp": "i8",
        "cpu:pc": "i16", "cpu:p": "i8",
        "platform:halted": "i1",
    }.items():
        builder.declare_state_slot(slot_id, type_name)

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
            if insn["op"] in TERMINATOR_OPS:
                lowerer.lower_terminator(block, insn)
                terminated = True
                break
            lowerer.lower_instruction(block, insn)
            pc += insn["length"]
            if pc > end:
                raise NES6502FrontendError(
                    f"0x{pc - insn['length']:x}: instruction overlaps the code/data boundary at 0x{end:x}"
                )
        if not terminated:
            if end in cfg.block_by_address:
                block.jump(cfg.block_id(end))
            else:
                if any(range_start == end for range_start, _range_end in ranges):
                    raise NES6502FrontendError(f"0x{leader:x}: block falls through into a declared data range")
                raise NES6502FrontendError(f"0x{leader:x}: block reaches the region end without a terminator")

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
    ]
    report = {
        "architecture": "nes6502",
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
            "usage: nes6502_frontend_v1.py <fixture.json> <host-contract.json> <out-ir.json> <out-sidecar.json> <out-report.json>",
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
    except (OSError, json.JSONDecodeError, KeyError, ValueError, NES6502Error, NES6502FrontendError, ScaffoldError) as exc:
        print(f"OPENRECOMP_NES6502_FRONTEND_V1=FAIL: {exc}", file=sys.stderr)
        return 2
    print(f"NES6502_FRONTEND_INSTRUCTIONS={report['instructions']}")
    print(f"NES6502_FRONTEND_BLOCKS={report['blocks']}")
    print("OPENRECOMP_NES6502_FRONTEND_V1=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
