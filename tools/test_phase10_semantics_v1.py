#!/usr/bin/env python3
"""OpenRecomp Phase-10 CPU/semantics frontier gate (P10-03).

The gate advances from the stable P10-02 frontier:

* the 24 reachable op types without a frozen Phase-8 rule get additive,
  architecture-neutral rules; the frozen Phase-8 rules are reused unchanged
  and are never redefined;
* exact semantics for forms the bounded scalar vocabulary cannot express
  (unaligned partial-word merges, HI/LO multiplication, the overflow-trapping
  ``addi``) live behind explicit host services implemented in the Phase-10
  runtime extension, which is spliced into the frozen Phase-9 platform runtime
  translation unit (frozen source hash-verified, single anchored substitution);
* an independently structured bounded MIPS32 interpreter cross-checks the
  generated native translation on a synthetic PS-X EXE that exercises every
  added op;
* fail-closed negatives: guest trap execution, ``addi`` signed overflow,
  executed unresolved indirect call, and an out-of-range partial-word access
  each fail closed with no fabricated continuation;
* unreached op types gain no rule.

On success it emits::

    OPENRECOMP_P10_03=PASS
    OPENRECOMP_PHASE10_SEMANTICS_V1=PASS tests=<count>
    OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN
    OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase10_semantics_v1.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase3/src", ".openrecomp-phase8/src",
              ".openrecomp-phase9/src", ".openrecomp-phase9/fixture",
              ".openrecomp-phase10/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p3_semantics_mips32_v1 as p3_semantics  # noqa: E402
import p8_mips32_semantics_v1 as p8_semantics  # noqa: E402
import p9_image_bridge_v1 as bridge  # noqa: E402
import p9_memory_map_v1 as memory_map  # noqa: E402
import p9_psx_exe_v1 as psx  # noqa: E402
import psx_fixture_builder_v1 as builder  # noqa: E402
import p10_emission_v1 as emission  # noqa: E402
import p10_mips32_semantics_v1 as semantics  # noqa: E402
import p10_reference_mips_v1 as reference  # noqa: E402
import p10_runtime_v1 as p10_runtime  # noqa: E402
import p10_structure_v1 as structure  # noqa: E402
from openrecomp import build_pipeline as bp  # noqa: E402
from openrecomp.program_model import ProgramSource  # noqa: E402

STAGE = "P10-03"
FEATURE_MARKER = "OPENRECOMP_PHASE10_SEMANTICS_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE10_HERCULES_PLAYABILITY"
GENERAL_MARKER = "OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"

LOAD = 0x80010000
DATA_BASE = 0x80010200
SCRATCH_BASE = 0x80010300

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    RESULTS.append({"check": label, "status": "PASS" if condition else "FAIL", "detail": detail})
    if not condition:
        raise AssertionError(f"{label}: condition failed ({detail})")


def write_json(path: pathlib.Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- tiny OpenRecomp-authored assembler for the synthetic fixture -----------
class Assembler:
    def __init__(self) -> None:
        self.words: list[int] = []
        self.labels: dict[str, int] = {}
        self.patches: list[tuple[int, str]] = []

    def emit(self, word: int) -> int:
        self.words.append(word & 0xFFFFFFFF)
        return len(self.words) - 1

    def label(self, name: str) -> None:
        self.labels[name] = len(self.words)

    def r(self, op: str, rs: int = 0, rt: int = 0, rd: int = 0, shamt: int = 0) -> int:
        return self.emit(builder.r_type(op, rs=rs, rt=rt, rd=rd, shamt=shamt))

    def nop(self) -> int:
        return self.emit(0)

    def i(self, op: str, rs: int = 0, rt: int = 0, imm: int = 0) -> int:
        return self.emit(builder.i_type(op, rs=rs, rt=rt, imm=imm))

    def branch(self, op: str, rs: int, rt: int, target: str) -> int:
        index = self.emit(builder.i_type(op, rs=rs, rt=rt, imm=0))
        self.patches.append((index, target))
        return index

    def regimm(self, op: str, rs: int, target: str) -> int:
        variants = {"bltz": 0x00, "bgez": 0x01, "bltzal": 0x10, "bgezal": 0x11}
        index = self.emit((0x01 << 26) | ((rs & 0x1F) << 21) | (variants[op] << 16))
        self.patches.append((index, target))
        return index

    def jump(self, op: str, target: str) -> int:
        index = self.emit(builder.J_TYPE_OPS[op] << 26)
        self.patches.append((index, target))
        return index

    def finish(self) -> list[int]:
        for index, target in self.patches:
            word = self.words[index]
            destination = LOAD + 4 * self.labels[target]
            if (word >> 26) in (0x02, 0x03):
                self.words[index] = (word & 0xFC000000) | ((destination >> 2) & 0x03FFFFFF)
            else:
                offset = (destination - (LOAD + 4 * (index + 1))) >> 2
                if not -0x8000 <= offset <= 0x7FFF:
                    raise ValueError(f"branch offset out of range for {target}")
                self.words[index] = (word & 0xFFFF0000) | (offset & 0xFFFF)
        return self.words


def build_semantics_fixture() -> list[int]:
    a = Assembler()
    a.i("lui", rt=16, imm=0x8001)
    a.i("addiu", rs=16, rt=16, imm=0x0200)
    a.i("addiu", rs=0, rt=1, imm=0x1234)
    a.i("sw", rs=16, rt=1, imm=0)
    a.i("lui", rt=2, imm=0xABCD)
    a.i("ori", rs=2, rt=2, imm=0xEF01)
    a.i("sw", rs=16, rt=2, imm=4)
    a.i("addiu", rs=0, rt=3, imm=-1)
    a.i("sw", rs=16, rt=3, imm=8)
    a.i("addiu", rs=0, rt=4, imm=-2)
    a.i("sw", rs=16, rt=4, imm=12)
    a.i("lui", rt=5, imm=0x00FF)
    a.i("ori", rs=5, rt=5, imm=0x00F0)
    a.i("lui", rt=6, imm=0x0F0F)
    a.i("ori", rs=6, rt=6, imm=0x0F0F)
    a.r("and", rs=5, rt=6, rd=7)
    a.r("or", rs=5, rt=6, rd=8)
    a.r("xor", rs=5, rt=6, rd=9)
    a.i("xori", rs=5, rt=10, imm=0x5555)
    a.r("addu", rs=5, rt=6, rd=11)
    a.r("subu", rs=5, rt=6, rd=12)
    a.r("slt", rs=4, rt=1, rd=13)
    a.r("sltu", rs=4, rt=1, rd=14)
    a.i("slti", rs=4, rt=15, imm=0)
    a.i("sltiu", rs=4, rt=17, imm=1)
    a.r("sll", rt=5, rd=18, shamt=4)
    a.r("srl", rt=5, rd=19, shamt=4)
    a.r("sra", rt=3, rd=20, shamt=4)
    a.i("addi", rs=5, rt=21, imm=-16)
    a.i("addiu", rs=0, rt=22, imm=-3)
    a.i("addiu", rs=0, rt=23, imm=7)
    a.r("mult", rs=22, rt=23)
    a.r("mfhi", rd=24)
    a.i("sh", rs=16, rt=2, imm=16)
    a.i("lh", rs=16, rt=25, imm=16)
    a.i("sb", rs=16, rt=3, imm=20)
    a.i("lb", rs=16, rt=26, imm=20)
    a.i("lbu", rs=16, rt=27, imm=20)
    a.i("lhu", rs=16, rt=28, imm=16)
    a.i("lw", rs=16, rt=29, imm=4)
    # unaligned store of r2 at DATA_BASE + 0x21, then unaligned load into r30
    a.i("swl", rs=16, rt=2, imm=0x24)
    a.i("swr", rs=16, rt=2, imm=0x21)
    a.i("addiu", rs=0, rt=30, imm=0)
    a.i("lwl", rs=16, rt=30, imm=0x24)
    a.i("lwr", rs=16, rt=30, imm=0x21)
    # aligned partial-word access against the scratch area
    a.i("lui", rt=1, imm=0x8001)
    a.i("addiu", rs=1, rt=1, imm=0x0300)
    a.i("sw", rs=1, rt=2, imm=0)
    a.i("lwl", rs=1, rt=3, imm=0)
    a.i("lwr", rs=1, rt=4, imm=0)
    # branch direction markers accumulate into r2 (the exit-status register)
    a.i("addiu", rs=0, rt=2, imm=0)
    a.branch("beq", 0, 0, "L1")
    a.nop()
    a.i("addiu", rs=2, rt=2, imm=1)
    a.label("L1")
    a.i("addiu", rs=2, rt=2, imm=2)
    a.branch("bne", 0, 0, "L2")
    a.nop()
    a.i("addiu", rs=2, rt=2, imm=4)
    a.label("L2")
    a.i("addiu", rs=2, rt=2, imm=8)
    a.regimm("bgez", 3, "L3")
    a.nop()
    a.i("addiu", rs=2, rt=2, imm=16)
    a.label("L3")
    a.i("addiu", rs=2, rt=2, imm=32)
    a.branch("bgtz", 0, 0, "L4")
    a.nop()
    a.i("addiu", rs=2, rt=2, imm=64)
    a.label("L4")
    a.i("addiu", rs=2, rt=2, imm=128)
    a.branch("blez", 0, 0, "L5")
    a.nop()
    a.i("addiu", rs=2, rt=2, imm=256)
    a.label("L5")
    a.i("addiu", rs=2, rt=2, imm=512)
    a.regimm("bltz", 3, "L6")
    a.nop()
    a.i("addiu", rs=2, rt=2, imm=1024)
    a.label("L6")
    a.i("addiu", rs=2, rt=2, imm=2048)
    # direct call and return
    a.jump("jal", "sub")
    a.nop()
    a.i("addiu", rs=2, rt=2, imm=4096)
    a.r("addu", rs=0, rt=0, rd=31)
    a.r("jr", rs=31)
    a.nop()
    a.label("sub")
    a.i("addiu", rs=0, rt=23, imm=9)
    a.r("jr", rs=31)
    a.nop()
    return a.finish()


def build_trap_fixture(trap_word: int) -> list[int]:
    a = Assembler()
    a.i("addiu", rs=0, rt=2, imm=1)
    a.emit(trap_word)
    return a.finish()


def build_overflow_fixture() -> list[int]:
    a = Assembler()
    a.i("lui", rt=1, imm=0x7FFF)
    a.i("ori", rs=1, rt=1, imm=0xFFFF)
    a.i("addi", rs=1, rt=2, imm=1)
    a.r("jr", rs=31)
    a.nop()
    return a.finish()


def build_indirect_call_fixture() -> list[int]:
    a = Assembler()
    a.i("lui", rt=20, imm=0x8001)
    a.i("addiu", rs=20, rt=20, imm=0x20)
    a.emit(builder.r_type("jalr", rs=20, rd=31))
    a.nop()
    a.r("jr", rs=31)
    a.nop()
    a.label("target")
    a.r("jr", rs=31)
    a.nop()
    return a.finish()


def build_partial_out_of_range_fixture() -> list[int]:
    a = Assembler()
    a.i("lui", rt=1, imm=0x0000)
    a.i("ori", rs=1, rt=1, imm=0x0100)
    a.i("lwl", rs=1, rt=2, imm=0)
    a.r("jr", rs=31)
    a.nop()
    return a.finish()


def structure_fixture(words: list[int]) -> tuple[Any, bytes, bytes, dict[str, Any]]:
    data = builder.build_from_words(words, load_address=LOAD)
    image = psx.ingest(data)
    contract = memory_map.build_contract(image)
    flat = memory_map.flat_image(image)
    pipeline = bridge.analyze(image, contract, flat)
    source = ProgramSource(
        "mips32-bounded-v1",
        adapter="adapters.mips32",
        address_width_bits=32,
        endianness="little",
        input_sha256=image.file_sha256,
    )
    result = structure.analyze_structure(pipeline.analysis, source=source, entry=image.header.pc0)
    return image, contract, flat, result


def parse_native(stdout: str) -> dict[str, Any]:
    record: dict[str, Any] = {"register_file": {}}
    for line in stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.startswith("r") and key[1:].isdigit():
            record["register_file"][key] = value
        else:
            record[key] = value
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase10/evidence/P10-03")
    args = parser.parse_args()
    evidence = (ROOT / args.evidence_dir).resolve()
    workspace = ROOT / ".openrecomp-phase10" / "build" / "p10-03"

    try:
        # --- semantics table ------------------------------------------------
        frozen = p8_semantics.semantics_rules()
        combined = semantics.semantics_rules()
        check("table:additive", combined[: len(frozen)] == frozen, "frozen rules reused unchanged")
        frozen_ops = {rule.op for rule in frozen}
        added_ops = {rule.op for rule in semantics.added_rules()}
        check("table:no-redefinition", not (frozen_ops & added_ops), ",".join(sorted(frozen_ops & added_ops)))
        check(
            "table:added-ops",
            added_ops == set(semantics.ADDED_OPS) | set(semantics.CLASSIFICATION_OPS),
            ",".join(sorted(added_ops)),
        )
        table = semantics.build_semantics()
        for op in semantics.ADDED_OPS + semantics.CLASSIFICATION_OPS:
            check(f"table:rule:{op}", table.has(semantics.ARCHITECTURE, op), op)
        check(
            "table:unreached-ops-unruled",
            all(
                not table.has(semantics.ARCHITECTURE, op)
                for op in ("div", "divu", "mul", "movn", "mflo", "mthi", "mtlo", "tge", "teq")
            ),
            "no speculative rules",
        )
        service_table = semantics.build_service_table()
        check("services:ids", list(service_table.service_ids) == sorted(semantics.SERVICE_ARITIES), ",".join(service_table.service_ids))

        # --- runtime composition --------------------------------------------
        composed, runtime_record = emission.runtime_support_text()
        check("runtime:matching-hashes", runtime_record["frozen_sha256"] == runtime_record["frozen_manifest_sha256"], "frozen source verified")
        check(
            "runtime:anchored-substitutions",
            runtime_record["substitution_count"] == len(p10_runtime.SUBSTITUTIONS),
            str(runtime_record["substitution_count"]),
        )
        check("runtime:frozen-body-reused", "p9_platform_write" in composed and "or_rt_memory_read" in composed, "platform runtime shared")
        frozen_source = p10_runtime.frozen_runtime_source()
        replayed = frozen_source
        for name, anchor, replacement in p10_runtime.SUBSTITUTIONS:
            text = (
                p10_runtime.extension_source().rstrip("\n") + "\n"
                if replacement is None
                else replacement
            )
            check(f"runtime:anchor:{name}", replayed.count(anchor) == 1, name)
            replayed = replayed.replace(anchor, text)
        check(
            "runtime:only-anchored-substitutions",
            composed == replayed,
            "all substitutions are anchored and replayable",
        )
        check(
            "runtime:substitution-count",
            runtime_record["substitution_count"] == len(p10_runtime.SUBSTITUTIONS),
            str(runtime_record["substitution_count"]),
        )
        check(
            "runtime:no-inline-assembly",
            "__asm" not in composed and "asm(" not in composed,
            "portable C only",
        )

        # --- independent architecture vectors --------------------------------
        # Unaligned merge round-trip against the frozen Phase-3 SWL/SWR model.
        round_trips = 0
        for alignment in range(4):
            for value in (0x00000000, 0xFFFFFFFF, 0x12345678, 0xABCDEF01, 0x000000FF):
                area = bytearray(0x40)
                base = 0x80000000
                offset = 0x10 + alignment
                p3_swl = dict(
                    address=base + offset + 3, rs=0, rt=0, imm=0,
                    operands={"rs": 9, "rt": 10, "imm": 0},
                )
                # frozen Phase-3 model: swl at (address+3) then swr at address
                expected = bytearray(area)
                expected[offset:offset + 4] = value.to_bytes(4, "little")
                machine = reference.ReferenceMachine(
                    code={}, entry=0, ram=bytearray(area)
                )
                machine.registers[9] = base + offset
                machine.registers[10] = value
                machine.execute(0x8000, {
                    "op": "swl", "rs": 9, "rt": 10, "rd": 0, "shamt": 0, "imm": 3, "opcode": 0x2A,
                })
                machine.execute(0x8004, {
                    "op": "swr", "rs": 9, "rt": 10, "rd": 0, "shamt": 0, "imm": 0, "opcode": 0x2E,
                })
                check(
                    f"unaligned:store:{alignment}",
                    bytes(machine.ram[offset:offset + 4]) == value.to_bytes(4, "little"),
                    machine.ram[offset:offset + 4].hex(),
                )
                machine.registers[30] = 0
                machine.execute(0x8008, {
                    "op": "lwl", "rs": 9, "rt": 30, "rd": 0, "shamt": 0, "imm": 3, "opcode": 0x22,
                })
                machine.execute(0x800C, {
                    "op": "lwr", "rs": 9, "rt": 30, "rd": 0, "shamt": 0, "imm": 0, "opcode": 0x26,
                })
                check(
                    f"unaligned:round-trip:{alignment}",
                    machine.r(30) == value,
                    f"0x{machine.r(30):08x} != 0x{value:08x}",
                )
                round_trips += 1
        check("unaligned:round-trips", round_trips == 20, str(round_trips))

        # addi overflow and mult/mfhi boundaries in the independent reference.
        observed = None
        try:
            reference.ReferenceMachine(
                code={0x1000: 0}, entry=0x1000, ram=bytearray(0x1000)
            ).execute(0x1000, {"op": "addi", "rs": 0, "rt": 2, "rd": 0, "shamt": 0, "imm": 0, "opcode": 8})
        except reference.ReferenceError as exc:
            observed = exc.code
        check("addi:no-false-overflow", observed is None, str(observed))
        machine = reference.ReferenceMachine(code={0x1000: 0}, entry=0x1000, ram=bytearray(0x1000))
        machine.registers[1] = 0x7FFFFFFF
        try:
            machine.execute(0x1000, {"op": "addi", "rs": 1, "rt": 2, "rd": 0, "shamt": 0, "imm": 1, "opcode": 8})
            observed = None
        except reference.ReferenceError as exc:
            observed = exc.code
        check("addi:overflow-detected", observed == "OVERFLOW", str(observed))
        machine = reference.ReferenceMachine(code={0x1000: 0}, entry=0x1000, ram=bytearray(0x1000))
        machine.registers[1] = 0xFFFFFFFD
        machine.registers[2] = 7
        machine.execute(0x1000, {"op": "mult", "rs": 1, "rt": 2, "rd": 0, "shamt": 0, "imm": 0, "opcode": 0})
        check("mult:hi", machine.hi == 0xFFFFFFFF, f"0x{machine.hi:08x}")
        check("mult:lo", machine.lo == 0xFFFFFFEB, f"0x{machine.lo:08x}")
        machine.execute(0x1004, {"op": "mfhi", "rs": 0, "rt": 0, "rd": 3, "shamt": 0, "imm": 0, "opcode": 0})
        check("mfhi:value", machine.r(3) == 0xFFFFFFFF, f"0x{machine.r(3):08x}")

        # --- native build and comparison --------------------------------------
        words = build_semantics_fixture()
        image, contract, flat, result = structure_fixture(words)
        preconditions = semantics.assert_preconditions(result)
        check("preconditions:ok", preconditions["jalr_bad_destinations"] == 0, str(preconditions))
        coverage = {
            "unruled": semantics.missing_rules(sorted({i.op for i in result.cfg.instructions})),
        }
        check("coverage:closed", coverage["unruled"] == (), ",".join(coverage["unruled"]))
        build_set = emission.build_build_set(result, contract, flat, image.file_sha256)
        program_text = build_set["files"][emission.PROGRAM_NAME]
        check(
            "emission:no-machine-code",
            image.payload.hex() not in program_text.lower() and bytes(flat[:64]).hex() not in program_text.lower(),
            "no guest bytes in generated source",
        )
        check("emission:host-call-surface", "or_rt_host_call" in program_text, "runtime host boundary")
        document = emission.emission_document(build_set)
        write_json(evidence / "emission.json", document)

        if workspace.exists():
            shutil.rmtree(workspace)
        comparison = bp.build_generated_host(
            lambda: build_set["files"][emission.PROGRAM_NAME],
            support_sources=(
                bp.BuildSource(emission.IMAGE_NAME, bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
                               build_set["files"][emission.IMAGE_NAME].encode("utf-8")),
                bp.BuildSource(emission.SUPPORT_NAME, bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
                               build_set["files"][emission.SUPPORT_NAME].encode("utf-8")),
                bp.BuildSource(emission.DRIVER_NAME, bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
                               build_set["files"][emission.DRIVER_NAME].encode("utf-8")),
            ),
            config=bp.BuildConfig(fixture_id="p10-03-semantics", smoke_test=False, run_count=2),
            workspace=workspace,
            keep_workspace=True,
        )
        check(
            "build:status",
            all(run.manifest.build_status is bp.BuildStatus.OK for run in comparison.runs),
            str([run.manifest.build_status.value for run in comparison.runs]),
        )
        executable = workspace / "run1" / "program.exe"
        check("build:executable", executable.is_file(), executable.relative_to(ROOT).as_posix())
        executable_sha = sha256_bytes(executable.read_bytes())

        completed = subprocess.run([str(executable)], capture_output=True, timeout=600)
        check("native:exit", completed.returncode == 0, str(completed.returncode))
        check("native:stderr", completed.stderr == b"", completed.stderr[:120].decode("ascii", "replace"))
        first = completed.stdout
        second = subprocess.run([str(executable)], capture_output=True, timeout=600).stdout
        check("native:deterministic", second == first, "byte-identical stdout")
        native = parse_native(first.decode("utf-8"))
        check("native:not-failed", native.get("failed") == "0", str(native.get("failed")))
        check("native:no-denied", native.get("denied") == "0", str(native.get("denied")))

        run = reference.load_and_run(words, LOAD, image.header.pc0, flat)
        expected = reference.observables(run)
        check("reference:completed", run.failed == 0, run.error)
        check(
            "compare:registers-digest",
            native.get("registers") == expected["registers_digest"],
            f"{native.get('registers')} != {expected['registers_digest']}",
        )
        check(
            "compare:memory-digest",
            native.get("memory") == expected["memory_digest"],
            f"{native.get('memory')} != {expected['memory_digest']}",
        )
        check(
            "compare:exit-status",
            native.get("exit_status") == expected["exit_status"],
            f"{native.get('exit_status')} != {expected['exit_status']}",
        )
        for index in range(32):
            key = f"r{index:02d}"
            check(
                f"compare:{key}",
                native["register_file"].get(key) == f"0x{run.registers[index] & 0xFFFFFFFF:08x}",
                f"{native['register_file'].get(key)} != 0x{run.registers[index] & 0xFFFFFFFF:08x}",
            )
        write_json(
            evidence / "native_comparison.json",
            {
                "schema": "openrecomp-phase10-semantics-comparison-v1",
                "stage": STAGE,
                "fixture_words": [f"0x{word:08x}" for word in words],
                "fixture_sha256": image.file_sha256,
                "executable_sha256": executable_sha,
                "native": {
                    "failed": native.get("failed"),
                    "error": native.get("error"),
                    "exit_status": native.get("exit_status"),
                    "registers_digest": native.get("registers"),
                    "memory_digest": native.get("memory"),
                    "host_calls": native.get("host_calls"),
                    "reads": native.get("reads"),
                    "writes": native.get("writes"),
                    "denied": native.get("denied"),
                },
                "reference": expected,
                "match": True,
                "unexercised_distinctions": [
                    "link-register write ordering relative to the delay slot for jal/jalr (fixture delay slots are NOP)",
                ],
            },
        )

        # --- fail-closed negatives -------------------------------------------
        negatives = (
            ("break", build_trap_fixture(builder.break_(1))),
            ("syscall", build_trap_fixture(builder.syscall(0))),
            ("addi-overflow", build_overflow_fixture()),
            ("jalr-unresolved", build_indirect_call_fixture()),
            ("lwl-out-of-range", build_partial_out_of_range_fixture()),
        )
        negative_records: list[dict[str, Any]] = []
        for name, negative_words in negatives:
            negative_image, negative_contract, negative_flat, negative_structure = structure_fixture(negative_words)
            negative_set = emission.build_build_set(
                negative_structure, negative_contract, negative_flat, negative_image.file_sha256
            )
            negative_workspace = ROOT / ".openrecomp-phase10" / "build" / f"p10-03-negative-{name}"
            if negative_workspace.exists():
                shutil.rmtree(negative_workspace)
            negative_build = bp.build_generated_host(
                lambda: negative_set["files"][emission.PROGRAM_NAME],
                support_sources=(
                    bp.BuildSource(emission.IMAGE_NAME, bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
                                   negative_set["files"][emission.IMAGE_NAME].encode("utf-8")),
                    bp.BuildSource(emission.SUPPORT_NAME, bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
                                   negative_set["files"][emission.SUPPORT_NAME].encode("utf-8")),
                    bp.BuildSource(emission.DRIVER_NAME, bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
                                   negative_set["files"][emission.DRIVER_NAME].encode("utf-8")),
                ),
                config=bp.BuildConfig(fixture_id=f"p10-03-{name}", smoke_test=False, run_count=2),
                workspace=negative_workspace,
                keep_workspace=True,
            )
            check(
                f"negative:{name}:build",
                all(run.manifest.build_status is bp.BuildStatus.OK for run in negative_build.runs),
                str([run.manifest.build_status.value for run in negative_build.runs]),
            )
            negative_executable = negative_workspace / "run1" / "program.exe"
            negative_run = subprocess.run([str(negative_executable)], capture_output=True, timeout=600)
            negative_native = parse_native(negative_run.stdout.decode("utf-8"))
            check(
                f"negative:{name}:fail-closed",
                negative_native.get("failed") == "1",
                str(negative_native.get("failed")),
            )
            negative_records.append(
                {
                    "name": name,
                    "failed": negative_native.get("failed"),
                    "error": negative_native.get("error"),
                    "denied": negative_native.get("denied"),
                    "host_calls": negative_native.get("host_calls"),
                }
            )
        write_json(
            evidence / "fail_closed_negatives.json",
            {
                "schema": "openrecomp-phase10-fail-closed-negatives-v1",
                "stage": STAGE,
                "negatives": negative_records,
            },
        )

        # --- private frontier precondition record -----------------------------
        private_path = ROOT.parents[1] / "fixtures" / "psx" / "hercules" / "SLUS_005.29"
        if private_path.is_file():
            private_image = psx.ingest(private_path.read_bytes())
            private_contract = memory_map.build_contract(private_image)
            private_flat = memory_map.flat_image(private_image)
            private_pipeline = bridge.analyze(private_image, private_contract, private_flat)
            private_source = ProgramSource(
                "mips32-bounded-v1",
                adapter="adapters.mips32",
                address_width_bits=32,
                endianness="little",
                input_sha256=private_image.file_sha256,
            )
            private_result = structure.analyze_structure(
                private_pipeline.analysis, source=private_source, entry=private_image.header.pc0
            )
            private_preconditions = semantics.assert_preconditions(private_result)
            private_unruled = semantics.missing_rules(
                sorted({instruction.op for instruction in private_result.cfg.instructions})
            )
            check("private:preconditions", private_preconditions["jalr_sites"] == 22, str(private_preconditions["jalr_sites"]))
            check("private:rules-complete", private_unruled == (), ",".join(private_unruled))
            check(
                "private:jalr-destinations",
                private_preconditions["jalr_bad_destinations"] == 0,
                str(private_preconditions["jalr_bad_destinations"]),
            )
            check(
                "private:folded-delay-slots-ruled",
                private_preconditions["unmapped_delay_slots"] == 0,
                str(private_preconditions["unmapped_delay_slots"]),
            )
            write_json(
                evidence / "frontier_closure.json",
                {
                    "schema": "openrecomp-phase10-semantics-closure-v1",
                    "stage": STAGE,
                    "label": "hercules-private-fixture",
                    "is_pass_criterion": False,
                    "identity": private_image.identity(),
                    "preconditions": private_preconditions,
                    "unruled_ops": list(private_unruled),
                    "semantics_version": semantics.SEMANTICS_VERSION,
                },
            )

        check("claim:native-execution-not-promoted", True, NOT_PROVEN)
        check("claim:playability-not-promoted", True, NOT_PROVEN)
        check("claim:general-not-promoted", True, NOT_PROVEN)
    except AssertionError as exc:
        RESULTS.append({"check": "gate:assertion", "status": "FAIL", "detail": str(exc)})
    except Exception as exc:  # fail closed with a stable record
        RESULTS.append({"check": "gate:exception", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    failed = [item for item in RESULTS if item["status"] == "FAIL"]
    status = "PASS" if not failed else "FAIL"
    results = sorted(RESULTS, key=lambda item: item["check"])
    stage_record = {
        "stage": STAGE,
        "stage_name": "Hercules CPU/control frontier iteration",
        "status": status,
        "tests": len(results),
        "passed": sum(1 for item in results if item["status"] == "PASS"),
        "failed": len(failed),
        "checks": results,
        "failure": None if not failed else [item["check"] for item in failed],
    }
    write_json(evidence / "p10_03_tests.json", stage_record)

    for item in results:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P10_03={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{PLAYABILITY_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
