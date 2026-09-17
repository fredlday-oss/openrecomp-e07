#!/usr/bin/env python3
"""OpenRecomp Phase-3 CoreMark MIPS32 fixture gate (P3-01).

P3-01 acquires the authoritative CoreMark source at a pinned commit, builds a
legally clean MIPS32 ELF from it with a provenance-recorded toolchain, and
characterises the result.  The deterministic gate:

* verifies the pinned upstream CoreMark source hashes (and the upstream
  ``coremark.md5`` reference list, recording the one upstream entry that is
  stale at this commit) plus the vendored P3 port files;
* verifies the recorded toolchain acquisition (official Zig 0.13.0 Windows
  archive, published SHA-256, pinned executable SHA-256) and rebuilds the ELF
  twice in isolated build roots, requiring byte-identical executables;
* characterises the ELF: class/endian/machine/type/flags/entry, sections,
  program headers, ``.text``/``.rodata``/``.data``/``.bss`` sizes, symbol and
  relocation counts, imported/external requirements, executable instruction
  count;
* decodes every executable word through the existing bounded OpenRecomp MIPS32
  adapter (``adapters.mips32``) and records the exact instruction/opcode
  inventory plus the unsupported-encoding inventory that defines the
  evidence-supported later Phase-3 stages.  Nothing in OpenRecomp is modified
  to make the ELF pass.

On success it emits::

    OPENRECOMP_P3_01=PASS
    OPENRECOMP_PHASE3_COREMARK_MIPS32_FIXTURE_V1=PASS tests=<count>

Usage:

    python tools/test_phase3_coremark_fixture_v1.py
    python tools/test_phase3_coremark_fixture_v1.py --zig .openrecomp-phase3/tools/zig/zig.exe
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import pathlib
import struct
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters import mips32  # noqa: E402

EVIDENCE_ROOT = ROOT / ".openrecomp-phase3" / "evidence"
DEFAULT_EVIDENCE_DIR = EVIDENCE_ROOT / "P3-01"

STAGE = "P3-01"
STAGE_MARKER = "OPENRECOMP_P3_01"
FEATURE_MARKER = "OPENRECOMP_PHASE3_COREMARK_MIPS32_FIXTURE_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF"

COREMARK_REPO = "https://github.com/eembc/coremark"
COREMARK_COMMIT = "1f483d5b8316753a742cbf5590caf5bd0a4e4777"
COREMARK_LICENSE = (
    "Apache License 2.0 per the upstream source-file headers; repository "
    "LICENSE.md is the EEMBC CoreMark Acceptable Use Agreement covering the "
    "COREMARK trademark and result reporting. No public CoreMark score is "
    "produced or published by this stage."
)
UPSTREAM_DIR = ROOT / ".openrecomp-phase3" / "external" / "coremark"
PORT_DIR = ROOT / ".openrecomp-phase3" / "ports" / "coremark_mips32"

UPSTREAM_SHA256 = {
    "coremark.h": "42642b9a06c7ed2b3bd9eda971b7c3868c4f5d27bf7ef6c4bba11291a0c2598a",
    "core_list_join.c": "ca00e4e010ece47d7f040cb92aa50a95345a00d3171b59d088f6b243be06ce7b",
    "core_main.c": "17884c93c5b94378eb0ff02b4df3725756cf2addb9b8cbcaa6200a4649ff5ca7",
    "core_matrix.c": "ecdff717b5a5c4907d221a606760e25499899cbf617582c05d40db71c91351e4",
    "core_state.c": "f4b84bb0a3452c45a4daa664ab502bfdccbd31cb57d93e9ac490c60937717a4e",
    "core_util.c": "a3fbfcb9bb943b638624b8ece01c5836dd56a96d7bcde2697b248d077447327f",
    "coremark.md5": "dad92861212f8f012e75974e23ea97f7a275a375e0d3bc1d3b216423ba6b6306",
    "LICENSE.md": "9577b9c846f61fd69a0d8ac965998c6450c7d8969f71f0bb4a931b91aebad28a",
    "README.md": "5581fb67dc1609cbd1865f150dbcb1050d96c602987792456850eb96eb0dd08c",
    "barebones/core_portme.h": "4a789446774e9327126768b2379d7619f8ffd11d9a2afecc37126565486aac5a",
    "barebones/ee_printf.c": "535ba1feaa731d69e6f45117b9a79ef58291619248505c67aec916571612abdc",
}
UPSTREAM_MD5 = {
    "core_list_join.c": "9007fe7861b60ee6f210d156b62974c8",
    "core_main.c": "4a9e6dadce1ac3866381021fbe843fc9",
    "core_matrix.c": "5fa21a0f7c3964167c9691db531ca652",
    "core_state.c": "fb49e7605c125306575a83f14f5798ac",
    "core_util.c": "45540ba2145adea1ec7ea2c72a1fbbcb",
}
UPSTREAM_MD5_STALE = {
    "coremark.h": {
        "listed_md5": "8ca974c013b380dc7f0d6d1afb76eb2d",
        "actual_md5": "b0ec69b6c8e75853d06accb3b1bcf534",
        "note": (
            "The upstream coremark.md5 reference list does not match the "
            "pinned commit (or the v1.01 tag); the other five listed entries "
            "match exactly. Observed upstream inconsistency, not patched."
        ),
    }
}
PORT_FILES = {
    "p3_ee_printf.c": "derived from upstream barebones/ee_printf.c; only the "
                      "uart_send_char stub is replaced (documented in-file)",
    "p3_port_support.c": "OpenRecomp-original platform hooks",
    "p3_start.S": "OpenRecomp-original freestanding entry stub",
    "p3_mips32.ld": "OpenRecomp-original linker script",
}

ZIG_ARCHIVE = "zig-windows-x86_64-0.13.0.zip"
ZIG_URL = f"https://ziglang.org/download/0.13.0/{ZIG_ARCHIVE}"
ZIG_ARCHIVE_SHA256 = "d859994725ef9402381e557c60bb57497215682e355204d754ee3df75ee3c158"
ZIG_ARCHIVE_SIZE = 79163968
ZIG_VERSION = "0.13.0"
ZIG_EXE_SHA256 = "2e44af5bbf7a72ef8cbdae370284687c95d65a19affa469d2ad0364d905b8e84"
ZIG_DEFAULT = ROOT / ".openrecomp-phase3" / "tools" / "zig" / "zig.exe"

BUILD_ROOT_REL = ".openrecomp-phase3/build/P3-01"
ELF_NAME = "coremark_mips32_O1.elf"
EXPECTED_ELF_SHA256 = "16a0a0aa0f62344d8c0f309b755450f09c330e7c5a7c355785662d7a141f7669"
EXPECTED_ELF_SIZE = 31184

COMMON_FLAGS = [
    "cc", "--target=mipsel-linux-musl",
    "-march=mips32", "-mabi=32", "-msoft-float", "-mno-abicalls", "-G0",
    "-ffreestanding", "-fno-builtin", "-fno-stack-protector",
    "-fomit-frame-pointer", "-fno-pic", "-O1",
    "-nostdlib", "-static",
    "-DTOTAL_DATA_SIZE=2000",
    "-DITERATIONS=1000",
    "-DHAS_FLOAT=0", "-DHAS_TIME_H=0", "-DUSE_CLOCK=0",
    "-DHAS_STDIO=0", "-DHAS_PRINTF=0",
    "-DMEM_METHOD=0", "-DMAIN_HAS_NOARGC=1",
    '-DCOMPILER_VERSION="zig-cc-0.13.0-clang-18.1.5"',
    '-DFLAGS_STR="-O1-march=mips32-mabi=32-msoft-float-fno-pic"',
    '-DMEM_LOCATION="Static"',
]
COMMON_INCLUDES = (
    ".openrecomp-phase3/external/coremark",
    ".openrecomp-phase3/external/coremark/barebones",
    ".openrecomp-phase3/ports/coremark_mips32",
)
C_SOURCES = (
    ".openrecomp-phase3/external/coremark/core_list_join.c",
    ".openrecomp-phase3/external/coremark/core_main.c",
    ".openrecomp-phase3/external/coremark/core_matrix.c",
    ".openrecomp-phase3/external/coremark/core_state.c",
    ".openrecomp-phase3/external/coremark/core_util.c",
    ".openrecomp-phase3/ports/coremark_mips32/p3_ee_printf.c",
    ".openrecomp-phase3/ports/coremark_mips32/p3_port_support.c",
)
ASM_SOURCES = (".openrecomp-phase3/ports/coremark_mips32/p3_start.S",)
LINK_SCRIPT = ".openrecomp-phase3/ports/coremark_mips32/p3_mips32.ld"

EXPECTED_SECTIONS = {
    ".text": 13948,
    ".rodata": 1864,
    ".data": 40,
    ".bss": 18416,
    ".MIPS.abiflags": 24,
    ".reginfo": 24,
}
EXPECTED_ENTRY = 0x4650
EXPECTED_TEXT_ADDRESS = 0x1000
EXPECTED_INSTRUCTION_WORDS = 3487
EXPECTED_SUPPORTED = 3397
EXPECTED_UNSUPPORTED = 90
EXPECTED_UNSUPPORTED_HISTOGRAM = {
    "movz": 35,
    "movn": 12,
    "mul (SPECIAL2 funct 0x02)": 22,
    "divu": 4,
    "teq": 4,
    "swl": 2,
    "swr": 2,
    "jalr": 1,
    "alignment-padding (0x04170001)": 8,
}

SPECIAL_NAMES = {
    0x09: "jalr", 0x0A: "movz", 0x0B: "movn", 0x0C: "syscall", 0x0D: "break",
    0x1A: "div", 0x1B: "divu",
    0x30: "tge", 0x31: "tgeu", 0x32: "tlt", 0x33: "tltu", 0x34: "teq",
    0x35: "tge", 0x36: "tne",
}
SPECIAL2_NAMES = {
    0x00: "madd", 0x01: "maddu", 0x02: "mul (SPECIAL2 funct 0x02)",
    0x04: "msub", 0x05: "msubu", 0x20: "clz", 0x21: "clo",
}
OPCODE_NAMES = {
    0x01: "regimm", 0x02: "j", 0x03: "jal", 0x04: "beq", 0x05: "bne",
    0x06: "blez", 0x07: "bgtz", 0x08: "addi", 0x09: "addiu", 0x0A: "slti",
    0x0B: "sltiu", 0x0C: "andi", 0x0D: "ori", 0x0E: "xori", 0x0F: "lui",
    0x11: "cop1", 0x14: "beql", 0x15: "bnel", 0x16: "blezl", 0x17: "bgtzl",
    0x1C: "special2", 0x20: "lb", 0x21: "lh", 0x23: "lw", 0x24: "lbu",
    0x25: "lhu", 0x28: "sb", 0x29: "sh", 0x2A: "swl", 0x2B: "sw",
    0x2E: "swr", 0x2F: "cache", 0x31: "lwc1", 0x35: "ldc1", 0x39: "swc1",
    0x3D: "sdc1",
}

RESULTS: list[dict[str, str]] = []
FINDINGS: dict[str, Any] = {}


def check(label: str, condition: bool) -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        print(f"FAIL: {label}", flush=True)
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}", flush=True)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def md5_file(path: pathlib.Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def section(name: str, function, *args) -> None:
    print(f"\n--- {name} ---", flush=True)
    function(*args)


class ElfView:
    """Minimal ELF32 view (OpenRecomp-original, stdlib only)."""

    def __init__(self, data: bytes):
        self.data = data
        (
            self.e_type, self.e_machine, self.e_version, self.e_entry,
            self.e_phoff, self.e_shoff, self.e_flags, self.e_ehsize,
            self.e_phentsize, self.e_phnum, self.e_shentsize, self.e_shnum,
            self.e_shstrndx,
        ) = struct.unpack_from("<HHIIIIIHHHHHH", data, 0x10)
        if data[:4] != b"\x7fELF":
            raise ValueError("missing ELF magic")
        self.elf_class = data[4]
        self.encoding = data[5]
        self.osabi = data[7]
        self.sections = self._sections()
        self.program_headers = self._program_headers()
        self.symbols = self._symbols()
        self.relocation_count = sum(
            1 for item in self.sections if item["type"] in (4, 9)
        )
        self.section_names = {item["name"] for item in self.sections}

    def _cstr(self, table_offset: int, offset: int) -> str:
        end = self.data.index(b"\0", table_offset + offset)
        return self.data[table_offset + offset:end].decode("ascii", errors="replace")

    def _sections(self) -> list[dict[str, Any]]:
        header = self.e_shoff + self.e_shstrndx * self.e_shentsize
        shstr_off = struct.unpack_from("<I", self.data, header + 0x10)[0]
        sections = []
        for index in range(self.e_shnum):
            offset = self.e_shoff + index * self.e_shentsize
            fields = struct.unpack_from("<IIIIIIIIII", self.data, offset)
            sections.append({
                "name": self._cstr(shstr_off, fields[0]),
                "type": fields[1],
                "flags": fields[2],
                "addr": fields[3],
                "offset": fields[4],
                "size": fields[5],
                "link": fields[6],
                "info": fields[7],
                "entsize": fields[9],
            })
        return sections

    def _program_headers(self) -> list[dict[str, Any]]:
        headers = []
        for index in range(self.e_phnum):
            offset = self.e_phoff + index * self.e_phentsize
            fields = struct.unpack_from("<IIIIIIII", self.data, offset)
            headers.append({
                "type": fields[0], "offset": fields[1], "vaddr": fields[2],
                "paddr": fields[3], "filesz": fields[4], "memsz": fields[5],
                "flags": fields[6], "align": fields[7],
            })
        return headers

    def _symbols(self) -> list[dict[str, Any]]:
        symtab = next((item for item in self.sections if item["name"] == ".symtab"), None)
        if symtab is None:
            return []
        strtab = self.sections[symtab["link"]]
        names_off = strtab["offset"]
        symbols = []
        count = symtab["size"] // 16
        for index in range(count):
            offset = symtab["offset"] + index * 16
            name_off, value, size, info, other, shndx = struct.unpack_from(
                "<IIIBBH", self.data, offset)
            symbols.append({
                "name": self._cstr(names_off, name_off),
                "value": value, "size": size, "info": info,
                "shndx": shndx,
            })
        return symbols

    def section(self, name: str) -> dict[str, Any] | None:
        return next((item for item in self.sections if item["name"] == name), None)

    def executable_segments(self) -> list[dict[str, Any]]:
        return [item for item in self.program_headers
                if item["type"] == 1 and item["flags"] & 0x1]


def describe_encoding(word: int) -> str:
    """P3-authoritative naming of an encoding for the unsupported inventory.

    Classification of *support* is decided only by ``adapters.mips32``; this
    helper only names encodings the bounded adapter rejects.
    """
    if word == 0x04170001:
        return "alignment-padding (0x04170001)"
    opcode = (word >> 26) & 0x3F
    rt = (word >> 16) & 0x1F
    funct = word & 0x3F
    if opcode == 0:
        return SPECIAL_NAMES.get(funct, f"special:funct=0x{funct:02x}")
    if opcode == 0x1C:
        return SPECIAL2_NAMES.get(funct, f"special2:funct=0x{funct:02x}")
    if opcode == 0x01:
        names = {0x00: "bltz", 0x01: "bgez", 0x02: "bltzl", 0x03: "bgezl",
                 0x08: "tgei", 0x09: "tgeiu", 0x0A: "tlti", 0x0B: "tltiu",
                 0x0C: "teqi", 0x0E: "tnei", 0x10: "bltzal", 0x11: "bgezal",
                 0x12: "bltzall", 0x13: "bgezall", 0x1F: "synci"}
        return names.get(rt, f"regimm:rt=0x{rt:02x}")
    return OPCODE_NAMES.get(opcode, f"opcode=0x{opcode:02x}")


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------
def audit_provenance() -> None:
    check("provenance:upstream-dir", UPSTREAM_DIR.is_dir())
    recorded_lines = None
    for relative, expected in UPSTREAM_SHA256.items():
        path = UPSTREAM_DIR / relative
        check(f"provenance:upstream-exists:{relative}", path.is_file())
        check(f"provenance:upstream-sha256:{relative}", sha256_file(path) == expected)
    check("provenance:upstream-md5-file",
          (UPSTREAM_DIR / "coremark.md5").is_file())
    for relative, expected in UPSTREAM_MD5.items():
        check(f"provenance:upstream-md5:{relative}",
              md5_file(UPSTREAM_DIR / relative) == expected)
    stale = UPSTREAM_MD5_STALE["coremark.h"]
    check("provenance:upstream-md5-stale-recorded",
          md5_file(UPSTREAM_DIR / "coremark.h") == stale["actual_md5"]
          and stale["listed_md5"] != stale["actual_md5"])
    lines = [line.split() for line in
             (UPSTREAM_DIR / "coremark.md5").read_text(encoding="utf-8").splitlines()
             if line.split()]
    recorded_lines = len(lines)
    check("provenance:upstream-md5-entry-count", recorded_lines == 6)
    for relative, note in PORT_FILES.items():
        check(f"provenance:port-file:{relative}", (PORT_DIR / relative).is_file())
    check("provenance:license-recorded",
          (UPSTREAM_DIR / "LICENSE.md").is_file() and "Apache" in COREMARK_LICENSE)
    FINDINGS["provenance"] = {
        "repository": COREMARK_REPO,
        "commit": COREMARK_COMMIT,
        "license": COREMARK_LICENSE,
        "upstream_files": {
            relative: sha256_file(UPSTREAM_DIR / relative)
            for relative in sorted(UPSTREAM_SHA256)
        },
        "upstream_md5_reference_entries": recorded_lines,
        "upstream_md5_stale": UPSTREAM_MD5_STALE,
        "port_files": {
            relative: {"sha256": sha256_file(PORT_DIR / relative), "note": note}
            for relative, note in sorted(PORT_FILES.items())
        },
    }


def audit_toolchain(zig: pathlib.Path) -> None:
    check("toolchain:zig-exists", zig.is_file())
    check("toolchain:zig-sha256", sha256_file(zig) == ZIG_EXE_SHA256)
    version = subprocess.run([str(zig), "version"], capture_output=True, text=True)
    check("toolchain:zig-version",
          version.returncode == 0 and version.stdout.strip() == ZIG_VERSION)
    check("toolchain:archive-recorded",
          ZIG_ARCHIVE_SHA256 != "" and ZIG_ARCHIVE_SIZE == 79163968)
    ld = subprocess.run([str(zig), "ld.lld", "--version"], capture_output=True, text=True)
    check("toolchain:lld-pinned",
          ld.returncode == 0 and "LLD 18.1.6" in ld.stdout)
    FINDINGS["toolchain"] = {
        "compiler": f"zig cc {ZIG_VERSION} (clang 18.1.5, mipsel-linux-musl target)",
        "linker": ld.stdout.strip().splitlines()[0] if ld.stdout else "",
        "archive": {
            "url": ZIG_URL,
            "file": ZIG_ARCHIVE,
            "sha256": ZIG_ARCHIVE_SHA256,
            "size": ZIG_ARCHIVE_SIZE,
        },
        "zig_executable_sha256": sha256_file(zig),
        "flags": COMMON_FLAGS[1:] + ["-include stddef.h"] + list(COMMON_INCLUDES),
        "link": ["ld.lld", "-m", "elf32ltsmip", "-T", LINK_SCRIPT,
                 "--strip-debug", "--build-id=none"],
    }


# ---------------------------------------------------------------------------
# Build (two isolated roots)
# ---------------------------------------------------------------------------
def build(root_rel: str, zig: pathlib.Path) -> tuple[pathlib.Path, list[list[str]]]:
    root = ROOT / root_rel
    if root.exists():
        import shutil
        shutil.rmtree(root)
    (root / "obj").mkdir(parents=True)
    cache = root / "zig-cache"
    cache.mkdir()
    env = dict(os.environ)
    env["ZIG_LOCAL_CACHE_DIR"] = str(cache)
    env["ZIG_GLOBAL_CACHE_DIR"] = str(cache / "global")

    common = list(COMMON_FLAGS) + [f"-I{path}" for path in COMMON_INCLUDES]

    commands: list[list[str]] = []
    objects: list[str] = []
    for index, source in enumerate(C_SOURCES):
        obj_rel = f"{root_rel}/obj/{index:02d}_{pathlib.Path(source).name}.o"
        commands.append([str(zig)] + common + ["-include", "stddef.h", "-c", source, "-o", obj_rel])
        objects.append(obj_rel)
    for source in ASM_SOURCES:
        obj_rel = f"{root_rel}/obj/90_{pathlib.Path(source).name}.o"
        commands.append([str(zig)] + common + ["-c", source, "-o", obj_rel])
        objects.append(obj_rel)
    elf_rel = f"{root_rel}/{ELF_NAME}"
    link = [str(zig), "ld.lld", "-m", "elf32ltsmip", "-T", LINK_SCRIPT,
            "--strip-debug", "--build-id=none", "-o", elf_rel] + objects
    for command in commands:
        completed = subprocess.run(command, cwd=str(ROOT), capture_output=True,
                                   text=True, env=env)
        if completed.returncode != 0:
            raise RuntimeError(f"compile failed: {command[:6]}: {completed.stderr[:400]}")
    completed = subprocess.run(link, cwd=str(ROOT), capture_output=True,
                               text=True, env=env)
    if completed.returncode != 0:
        raise RuntimeError(f"link failed: {completed.stderr[:400]}")
    return ROOT / elf_rel, commands + [link]


def audit_build(zig: pathlib.Path) -> bytes:
    root_a = f"{BUILD_ROOT_REL}/candidate-a"
    root_b = f"{BUILD_ROOT_REL}/candidate-b"
    elf_a, commands_a = build(root_a, zig)
    elf_b, commands_b = build(root_b, zig)
    data_a = elf_a.read_bytes()
    data_b = elf_b.read_bytes()
    check("build:elf-exists", elf_a.is_file() and elf_b.is_file())
    check("build:independent-roots", root_a != root_b)
    check("build:byte-identical", data_a == data_b)
    check("build:expected-elf-sha256", sha256_bytes(data_a) == EXPECTED_ELF_SHA256)
    check("build:expected-elf-size", len(data_a) == EXPECTED_ELF_SIZE)
    FINDINGS["build"] = {
        "root_a": root_a,
        "root_b": root_b,
        "sha256": sha256_bytes(data_a),
        "size": len(data_a),
        "classification": "EXECUTABLE_REPRODUCIBLE",
        "compile_commands": commands_a,
    }
    (EVIDENCE_DIR / "build_reproducibility.json").write_bytes(
        (json.dumps({
            "sha256": sha256_bytes(data_a),
            "size": len(data_a),
            "byte_identical_across_roots": data_a == data_b,
            "compile_commands": commands_a,
            "link_command": commands_a[-1],
        }, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return data_a


# ---------------------------------------------------------------------------
# ELF characterisation and instruction inventory
# ---------------------------------------------------------------------------
def audit_characterisation(data: bytes) -> dict[str, Any]:
    elf = ElfView(data)
    check("elf:class-32", elf.elf_class == 1)
    check("elf:little-endian", elf.encoding == 1)
    check("elf:machine-mips", elf.e_machine == 8)
    check("elf:type-executable", elf.e_type == 2)
    check("elf:flags-o32-arch32",
          (elf.e_flags & 0x00001000) and (elf.e_flags & 0x50000000) == 0x50000000)
    check("elf:flags-non-pic", not (elf.e_flags & 0x2) and not (elf.e_flags & 0x4))
    check("elf:entry-expected", elf.e_entry == EXPECTED_ENTRY)
    start = next((symbol for symbol in elf.symbols if symbol["name"] == "_start"), None)
    check("elf:entry-is-_start", start is not None and start["value"] == elf.e_entry)

    for name, size in EXPECTED_SECTIONS.items():
        section_data = elf.section(name)
        check(f"elf:section:{name}", section_data is not None and section_data["size"] == size)
    text = elf.section(".text")
    check("elf:text-address", text is not None and text["addr"] == EXPECTED_TEXT_ADDRESS)
    check("elf:no-dynamic-section", ".dynamic" not in elf.section_names)
    check("elf:no-dynamic-program-header",
          all(item["type"] != 2 for item in elf.program_headers))
    check("elf:no-relocations", elf.relocation_count == 0)

    undefined = [symbol for symbol in elf.symbols
                 if symbol["shndx"] == 0 and symbol["name"]]
    check("elf:no-undefined-symbols", not undefined)
    function_symbols = [symbol for symbol in elf.symbols
                        if (symbol["info"] & 0xF) == 2 and symbol["size"] > 0]

    executable = elf.executable_segments()
    check("elf:single-executable-segment", len(executable) == 1)
    code = data[text["offset"]:text["offset"] + text["size"]]
    words = struct.unpack(f"<{len(code) // 4}I", code)
    check("elf:instruction-word-count", len(words) == EXPECTED_INSTRUCTION_WORDS)

    supported = collections.Counter()
    unsupported = collections.Counter()
    unsupported_sites: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for index, word in enumerate(words):
        address = text["addr"] + index * 4
        try:
            instruction = mips32.decode(address, word)
            supported[instruction["op"]] += 1
        except mips32.DecodeError:
            name = describe_encoding(word)
            unsupported[name] += 1
            if len(unsupported_sites[name]) < 8:
                unsupported_sites[name].append(
                    {"address": address, "word": word})
    check("inventory:supported-count", sum(supported.values()) == EXPECTED_SUPPORTED)
    check("inventory:unsupported-count", sum(unsupported.values()) == EXPECTED_UNSUPPORTED)
    check("inventory:unsupported-histogram",
          dict(unsupported) == EXPECTED_UNSUPPORTED_HISTOGRAM)
    check("inventory:divu-teq-pairs",
          unsupported["divu"] == 4 and unsupported["teq"] == 4)
    check("inventory:padding-encodings",
          unsupported["alignment-padding (0x04170001)"] == 8)
    check("inventory:indirect-jalr", unsupported["jalr"] == 1)
    check("inventory:unaligned-stores",
          unsupported["swl"] == 2 and unsupported["swr"] == 2)
    check("inventory:conditional-moves",
          unsupported["movz"] == 35 and unsupported["movn"] == 12)
    check("inventory:mul", unsupported["mul (SPECIAL2 funct 0x02)"] == 22)

    characterisation = {
        "class": "ELF32",
        "endianness": "little",
        "machine": "EM_MIPS (0x8)",
        "type": "ET_EXEC",
        "flags": f"0x{elf.e_flags:08x}",
        "flags_interpretation": "EF_MIPS_ABI_O32 | EF_MIPS_ARCH_32 | EF_MIPS_NOREORDER (non-PIC)",
        "entry": f"0x{elf.e_entry:08x}",
        "entry_symbol": "_start",
        "sections": [
            {"name": item["name"], "type": item["type"], "addr": f"0x{item['addr']:x}",
             "size": item["size"]}
            for item in elf.sections
        ],
        "program_headers": [
            {"type": item["type"], "vaddr": f"0x{item['vaddr']:x}",
             "filesz": item["filesz"], "memsz": item["memsz"],
             "flags": item["flags"]}
            for item in elf.program_headers
        ],
        "sizes": {name: size for name, size in EXPECTED_SECTIONS.items()},
        "symbol_count": len(elf.symbols),
        "function_symbol_count": len(function_symbols),
        "relocation_count": elf.relocation_count,
        "undefined_symbol_count": len(undefined),
        "executable_instruction_count_estimate": len(words),
        "imported_external_requirements": "none (static, freestanding, no dynamic section)",
        "instruction_histogram": dict(sorted(supported.items(), key=lambda kv: (-kv[1], kv[0]))),
        "unsupported_histogram": dict(sorted(unsupported.items(), key=lambda kv: (-kv[1], kv[0]))),
        "unsupported_sites_first": {
            name: sites for name, sites in sorted(unsupported_sites.items())
        },
    }
    (EVIDENCE_DIR / "elf_characterisation.json").write_bytes(
        (json.dumps(characterisation, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    (EVIDENCE_DIR / "instruction_inventory.json").write_bytes(
        (json.dumps({
            "supported": dict(sorted(supported.items(), key=lambda kv: (-kv[1], kv[0]))),
            "unsupported": dict(sorted(unsupported.items(), key=lambda kv: (-kv[1], kv[0]))),
            "unsupported_sites": {
                name: sites for name, sites in sorted(unsupported_sites.items())
            },
        }, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    FINDINGS["characterisation"] = {
        "entry": f"0x{elf.e_entry:08x}",
        "symbol_count": len(elf.symbols),
        "instruction_words": len(words),
        "supported": sum(supported.values()),
        "unsupported": sum(unsupported.values()),
        "unsupported_histogram": dict(unsupported),
    }
    return characterisation


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="P3-01 CoreMark MIPS32 fixture gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase3/evidence/P3-01")
    parser.add_argument("--zig", type=str,
                        default=os.environ.get("OPENRECOMP_ZIG", str(ZIG_DEFAULT)))
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    zig = pathlib.Path(args.zig)

    print("=== P3-01 CoreMark MIPS32 Fixture Gate ===", flush=True)
    failure: str | None = None
    status = "PASS"
    try:
        section("provenance", audit_provenance)
        section("toolchain", audit_toolchain, zig)
        print("\n--- build ---", flush=True)
        data = audit_build(zig)
        section("characterisation", audit_characterisation, data)
    except Exception as exc:  # noqa: BLE001 - fail closed without traceback
        failure = f"{type(exc).__name__}: {exc}"
        status = "FAIL"

    passed = sum(1 for item in RESULTS if item["status"] == "PASS")
    failed = sum(1 for item in RESULTS if item["status"] == "FAIL") + (1 if failure else 0)
    result = {
        "stage": STAGE,
        "stage_name": FEATURE_MARKER,
        "status": status,
        "tests": passed,
        "passed": passed,
        "failed": failed,
        "markers": {
            "stage": f"{STAGE_MARKER}={status}",
            "gate": f"{FEATURE_MARKER}={status} tests={passed}",
            "terminal": f"{TERMINAL_MARKER}=NOT_PROVEN",
        },
        "checks": sorted(RESULTS, key=lambda item: item["check"]),
        "findings": FINDINGS,
        "failure": failure,
    }
    (EVIDENCE_DIR / "p3_01_tests.json").write_bytes(
        (json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    (EVIDENCE_DIR / "source_provenance.json").write_bytes(
        (json.dumps(FINDINGS.get("provenance", {}), indent=2, sort_keys=True) + "\n").encode("utf-8"))
    (EVIDENCE_DIR / "toolchain_identity.json").write_bytes(
        (json.dumps(FINDINGS.get("toolchain", {}), indent=2, sort_keys=True) + "\n").encode("utf-8"))

    print("\n=== RESULT ===")
    if status == "PASS":
        print(f"{STAGE_MARKER}=PASS")
        print(f"{FEATURE_MARKER}=PASS tests={passed}")
        print(f"{TERMINAL_MARKER}=NOT_PROVEN")
        return 0
    print(f"{STAGE_MARKER}=FAIL ({failure})")
    print(f"{FEATURE_MARKER}=FAIL")
    print(f"{TERMINAL_MARKER}=NOT_PROVEN")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
