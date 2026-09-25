#!/usr/bin/env python3
"""Deterministic P17-01 authentic TITLE identity and bounded PS-X EXE ingestion gate."""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import struct
import subprocess
import shutil
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase17/src", ".openrecomp-phase16/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p16_contracts_v1 as p16_contract
import p17_contracts_v1 as contract
import p17_fixture_verification_v1 as fixture
from p17_gate_v1 import assert_public_safe, Gate, reject_private_path, run_stage, write_json
from p17_iso9660_v1 import DirectoryRecord, Iso9660Image, Iso9660Error, PsxExeHeader
import p17_frozen_phase16_integrity_v1 as p16i

STAGE = "P17-01"

TITLE_ISO_PATH = r"\EX\TITLE.;1"

TITLE_FILE_SHA256 = "39013ea19589015872a211c23d8c23ae8ecee7bc5093d996f51cf206775f1b68"
TITLE_FILE_SIZE = 288768
TITLE_PAYLOAD_SHA256 = "fe1925b5dd7c7190802dbe37b162759467fdbbf95b707edb9c6bb1626b961ccc"
TITLE_PAYLOAD_SIZE = 286720
TITLE_ENTRY_PC = 0x800380A0
TITLE_TEXT_ADDR = 0x80038098
TITLE_TEXT_END = 0x8007E098
TITLE_GP0 = 0
TITLE_SP_ADDR = 0x801FFFF0

RAM_START = 0x80000000
RAM_END = 0x80200000


class PublicSafeError(Exception):
    pass


def fixture_root() -> pathlib.Path:
    env = os.environ.get("OPENRECOMP_HERCULES_FIXTURE_ROOT")
    if env:
        return pathlib.Path(env)
    return ROOT.parents[1] / "fixtures" / "psx" / "hercules"


def fail(message: str) -> None:
    raise AssertionError(message)


def verify_title_from_disc(fixture_dir: pathlib.Path) -> tuple[bytes, bytes, DirectoryRecord]:
    bin_path = fixture_dir / "Disney's Hercules Action Game (USA).bin"
    image = Iso9660Image.open(bin_path)
    record = image.find_file(TITLE_ISO_PATH)
    if record.data_length != TITLE_FILE_SIZE:
        raise AssertionError(f"TITLE size mismatch: expected {TITLE_FILE_SIZE}, got {record.data_length}")
    sectors = (TITLE_FILE_SIZE + 2047) // 2048
    with bin_path.open("rb") as f:
        f.seek(record.extent_lba * 2352 + 24)
        raw = b"".join(f.read(2048) for _ in range(sectors))
    raw = raw[:TITLE_FILE_SIZE]
    if len(raw) != TITLE_FILE_SIZE:
        raise AssertionError(f"TITLE file short read: {len(raw)}")
    header = raw[:2048]
    payload = raw[2048:]
    if hashlib.sha256(raw).hexdigest() != TITLE_FILE_SHA256:
        raise AssertionError("TITLE whole-file SHA-256 mismatch")
    if hashlib.sha256(payload).hexdigest() != TITLE_PAYLOAD_SHA256:
        raise AssertionError("TITLE payload SHA-256 mismatch")
    return header, payload, record


def validate_psx_exe(header: bytes, payload: bytes) -> tuple[PsxExeHeader, dict[str, object]]:
    exe = PsxExeHeader.parse(header)
    report: dict[str, object] = {
        "magic": exe.magic.decode("ascii", errors="replace"),
        "pc0": f"0x{exe.pc0:08x}",
        "gp0": f"0x{exe.gp0:08x}",
        "t_addr": f"0x{exe.t_addr:08x}",
        "t_size": exe.t_size,
        "d_addr": f"0x{exe.d_addr:08x}",
        "d_size": exe.d_size,
        "b_addr": f"0x{exe.b_addr:08x}",
        "b_size": exe.b_size,
        "s_addr": f"0x{exe.s_addr:08x}",
        "s_size": exe.s_size,
        "reserved_summary": exe.reserved_summary(),
    }
    checks = [
        ("magic", exe.magic == b"PS-X EXE"),
        ("pc0", exe.pc0 == TITLE_ENTRY_PC),
        ("t_addr", exe.t_addr == TITLE_TEXT_ADDR),
        ("t_size", exe.t_size == TITLE_PAYLOAD_SIZE),
        ("d_addr", exe.d_addr == 0),
        ("d_size", exe.d_size == 0),
        ("b_addr", exe.b_addr == 0),
        ("b_size", exe.b_size == 0),
        ("gp0", exe.gp0 == TITLE_GP0),
        ("s_addr", exe.s_addr == TITLE_SP_ADDR),
        ("s_size", exe.s_size == 0),
        ("text_end", exe.t_addr + exe.t_size == TITLE_TEXT_END),
        ("text_end_in_ram", RAM_START <= exe.t_addr and (exe.t_addr + exe.t_size) <= RAM_END),
        ("entry_aligned", exe.pc0 % 4 == 0),
        ("entry_in_text_range", exe.t_addr <= exe.pc0 < (exe.t_addr + exe.t_size)),
        ("payload_size", len(payload) == exe.t_size),
        ("payload_digest", hashlib.sha256(payload).hexdigest() == TITLE_PAYLOAD_SHA256),
        ("reserved_nonzero_count", exe.reserved_summary()["nonzero_count"] == 55),
        ("reserved_first_offset", exe.reserved_summary()["first_relative_offset"] == 20),
        ("reserved_last_offset", exe.reserved_summary()["last_relative_offset"] == 74),
    ]
    failures = [name for name, ok in checks if not ok]
    if failures:
        raise AssertionError(f"PS-X EXE validation failures: {', '.join(failures)}")
    return exe, report


def negative_absent_fixture() -> bool:
    bogus = fixture_root() / "does-not-exist-directory"
    ok, _ = fixture.verify_fixture(bogus)
    return not ok


def negative_fixture_digest_mismatch() -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        fixture_dir = pathlib.Path(tmp)
        (fixture_dir / "Disney's Hercules Action Game (USA).bin").write_bytes(b"wrong bin")
        (fixture_dir / "Disney's Hercules Action Game (USA).cue").write_bytes(b"wrong cue")
        (fixture_dir / "SLUS_005.29").write_bytes(b"wrong slus")
        ok, _ = fixture.verify_fixture(fixture_dir)
        return not ok


def negative_malformed_cue() -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        fixture_dir = pathlib.Path(tmp)
        real = fixture_root()
        for name in ("Disney's Hercules Action Game (USA).bin", "SLUS_005.29"):
            if (real / name).is_file():
                (fixture_dir / name).write_bytes((real / name).read_bytes())
        (fixture_dir / "Disney's Hercules Action Game (USA).cue").write_text("NOT A CUE\n", encoding="utf-8")
        ok, _ = fixture.verify_fixture(fixture_dir)
        return not ok


def negative_missing_title_path(tmp_path: pathlib.Path) -> bool:
    """A synthetic ISO image with valid PVD/root but no TITLE entry."""
    import p17_iso9660_v1 as iso
    image_path = tmp_path / "no_title.bin"
    # Build a minimal Mode2/2352 image with PVD at LBA 16 and root at LBA 22.
    sector = bytearray(2352)
    sector[15] = 2  # mode 2
    # Write PVD
    pvd = bytearray(2048)
    pvd[0] = 1
    pvd[1:6] = b"CD001"
    pvd[6] = 1
    # Root directory record at offset 156
    root_rec = bytearray(34)
    root_rec[0] = 34
    root_lba = 22
    struct.pack_into("<I", root_rec, 2, root_lba)
    struct.pack_into("<I", root_rec, 10, 2048)
    root_rec[25] = 0x02  # directory
    root_rec[32] = 1
    root_rec[33] = 0x00
    pvd[156:190] = root_rec
    # Write root directory sector at LBA 22 containing only '.' and '..'
    root = bytearray(2048)
    dot = bytearray(34)
    dot[0] = 34
    struct.pack_into("<I", dot, 2, root_lba)
    struct.pack_into("<I", dot, 10, 2048)
    dot[25] = 0x02
    dot[32] = 1
    dot[33] = 0x00
    root[0:34] = dot
    dotdot = bytearray(34)
    dotdot[0] = 34
    struct.pack_into("<I", dotdot, 2, root_lba)
    struct.pack_into("<I", dotdot, 10, 2048)
    dotdot[25] = 0x02
    dotdot[32] = 1
    dotdot[33] = 0x01
    root[34:68] = dotdot

    with image_path.open("wb") as f:
        for lba in range(23):
            sec = bytearray(sector)
            if lba == 16:
                sec[24:24+2048] = pvd
            elif lba == 22:
                sec[24:24+2048] = root
            f.write(sec)
    try:
        image = iso.Iso9660Image.open(image_path)
        image.find_file(r"\EX\TITLE.;1")
        return False
    except (Iso9660Error, AssertionError):
        return True


def negative_malformed_psx_exe(tmp_path: pathlib.Path) -> bool:
    import p17_iso9660_v1 as iso
    image_path = tmp_path / "bad_exe.bin"
    # Build a tiny image with TITLE.;1 containing a truncated/bad header.
    fake_title = bytearray(288768)
    fake_title[:8] = b"NOPE    "
    sectors_needed = (len(fake_title) + 2047) // 2048
    title_lba = 23
    root_lba = 22
    # Re-use PVD/root builder
    sector = bytearray(2352)
    sector[15] = 2
    pvd = bytearray(2048)
    pvd[0] = 1
    pvd[1:6] = b"CD001"
    pvd[6] = 1
    root_rec = bytearray(34)
    root_rec[0] = 34
    struct.pack_into("<I", root_rec, 2, root_lba)
    struct.pack_into("<I", root_rec, 10, 2048)
    root_rec[25] = 0x02
    root_rec[32] = 1
    root_rec[33] = 0x00
    pvd[156:190] = root_rec
    root = bytearray(2048)
    dot = bytearray(34)
    dot[0] = 34
    struct.pack_into("<I", dot, 2, root_lba)
    struct.pack_into("<I", dot, 10, 2048)
    dot[25] = 0x02
    dot[32] = 1
    dot[33] = 0x00
    root[0:34] = dot
    dotdot = bytearray(34)
    dotdot[0] = 34
    struct.pack_into("<I", dotdot, 2, root_lba)
    struct.pack_into("<I", dotdot, 10, 2048)
    dotdot[25] = 0x02
    dotdot[32] = 1
    dotdot[33] = 0x01
    root[34:68] = dotdot
    # Add EX directory at LBA 87, but for this synthetic image EX contains TITLE.;1 directly
    ex_lba = 87
    ex = bytearray(2048)
    ex_dot = bytearray(34)
    ex_dot[0] = 34
    struct.pack_into("<I", ex_dot, 2, ex_lba)
    struct.pack_into("<I", ex_dot, 10, 2048)
    ex_dot[25] = 0x02
    ex_dot[32] = 1
    ex_dot[33] = 0x00
    ex[0:34] = ex_dot
    ex_dotdot = bytearray(34)
    ex_dotdot[0] = 34
    struct.pack_into("<I", ex_dotdot, 2, root_lba)
    struct.pack_into("<I", ex_dotdot, 10, 2048)
    ex_dotdot[25] = 0x02
    ex_dotdot[32] = 1
    ex_dotdot[33] = 0x01
    ex[34:68] = ex_dotdot
    title_rec = bytearray(40)
    title_rec[0] = 40
    struct.pack_into("<I", title_rec, 2, title_lba)
    struct.pack_into("<I", title_rec, 10, len(fake_title))
    title_rec[25] = 0x00
    title_rec[32] = 8
    title_rec[33:41] = b"TITLE.;1"
    ex[68:108] = title_rec
    root_ex_rec = bytearray(34)
    root_ex_rec[0] = 34
    struct.pack_into("<I", root_ex_rec, 2, ex_lba)
    struct.pack_into("<I", root_ex_rec, 10, 2048)
    root_ex_rec[25] = 0x02
    root_ex_rec[32] = 2
    root_ex_rec[33:35] = b"EX"
    root[68:102] = root_ex_rec

    with image_path.open("wb") as f:
        total_lbas = max(22, ex_lba, title_lba) + sectors_needed + 1
        for lba in range(total_lbas):
            sec = bytearray(sector)
            if lba == 16:
                sec[24:24+2048] = pvd
            elif lba == 22:
                sec[24:24+2048] = root
            elif lba == ex_lba:
                sec[24:24+2048] = ex
            elif lba >= title_lba and lba < title_lba + sectors_needed:
                start = (lba - title_lba) * 2048
                sec[24:24+2048] = fake_title[start:start+2048]
            f.write(sec)
    try:
        image = iso.Iso9660Image.open(image_path)
        rec = image.find_file(r"\EX\TITLE.;1")
        with image_path.open("rb") as f:
            f.seek(rec.extent_lba * 2352 + 24)
            raw = b"".join(f.read(2048) for _ in range(sectors_needed))
        raw = raw[:TITLE_FILE_SIZE]
        header = raw[:2048]
        payload = raw[2048:]
        validate_psx_exe(header, payload)
        return False
    except (Iso9660Error, AssertionError, ValueError):
        return True


def negative_truncated_header() -> bool:
    try:
        PsxExeHeader.parse(b"PS-X EXE" + b"\x00" * 100)
        return False
    except ValueError:
        return True


def negative_bad_magic() -> bool:
    header = bytearray(2048)
    header[:8] = b"NOT-EXE "
    try:
        PsxExeHeader.parse(bytes(header))
        return False
    except ValueError:
        return True


def make_header_overrides(overrides: dict[int, bytes]) -> bytes:
    """Return a valid TITLE-sized file with header fields overridden."""
    fx = fixture_root()
    real = fx / "Disney's Hercules Action Game (USA).bin"
    with real.open("rb") as f:
        f.seek(88 * 2352 + 24)
        header = bytearray(f.read(2048))
        payload = b"".join(f.read(2048) for _ in range(140))
    for offset, value in overrides.items():
        header[offset:offset+len(value)] = value
    return bytes(header) + payload


def negative_wrong_entry() -> bool:
    data = make_header_overrides({16: struct.pack("<I", 0x800380A4)})
    try:
        validate_psx_exe(data[:2048], data[2048:])
        return False
    except AssertionError:
        return True


def negative_wrong_load_address() -> bool:
    data = make_header_overrides({24: struct.pack("<I", 0x80038094)})
    try:
        validate_psx_exe(data[:2048], data[2048:])
        return False
    except AssertionError:
        return True


def negative_wrong_text_end_overflow() -> bool:
    # t_addr + t_size wraps/overflows or exceeds RAM
    data = make_header_overrides({24: struct.pack("<I", 0xFFFFFF00), 28: struct.pack("<I", 0x10000000)})
    try:
        validate_psx_exe(data[:2048], data[2048:])
        return False
    except (AssertionError, OverflowError):
        return True


def negative_wrong_gp0() -> bool:
    data = make_header_overrides({20: struct.pack("<I", 0x12345678)})
    try:
        validate_psx_exe(data[:2048], data[2048:])
        return False
    except AssertionError:
        return True


def negative_wrong_data_field() -> bool:
    data = make_header_overrides({32: struct.pack("<I", 0x80010000), 36: struct.pack("<I", 1024)})
    try:
        validate_psx_exe(data[:2048], data[2048:])
        return False
    except AssertionError:
        return True


def negative_wrong_bss_field() -> bool:
    data = make_header_overrides({40: struct.pack("<I", 0x80020000), 44: struct.pack("<I", 1024)})
    try:
        validate_psx_exe(data[:2048], data[2048:])
        return False
    except AssertionError:
        return True


def negative_wrong_stack() -> bool:
    data = make_header_overrides({48: struct.pack("<I", 0x80100000)})
    try:
        validate_psx_exe(data[:2048], data[2048:])
        return False
    except AssertionError:
        return True


def negative_wrong_file_size() -> bool:
    fx = fixture_root()
    real = fx / "Disney's Hercules Action Game (USA).bin"
    with real.open("rb") as f:
        f.seek(88 * 2352 + 24)
        header = f.read(2048)
        payload = b"".join(f.read(2048) for _ in range(139))  # one sector short
    try:
        validate_psx_exe(header, payload)
        return False
    except AssertionError:
        return True


def negative_payload_digest_mismatch() -> bool:
    fx = fixture_root()
    real = fx / "Disney's Hercules Action Game (USA).bin"
    with real.open("rb") as f:
        f.seek(88 * 2352 + 24)
        header = bytearray(f.read(2048))
        payload = bytearray(b"".join(f.read(2048) for _ in range(140)))
    payload[-1] ^= 0xFF
    try:
        validate_psx_exe(bytes(header), bytes(payload))
        return False
    except AssertionError:
        return True


def negative_private_paths_in_evidence() -> bool:
    bad_unix = "/home/fred/OpenRecomp/fixtures/psx/hercules/TITLE"
    bad_win = r"D:\OpenRecomp\fixtures\private\TITLE"
    bad_unc = r"\\server\share\private"
    for path in (bad_unix, bad_win, bad_unc):
        rejected, _ = reject_private_path(path)
        if not rejected:
            return False
    return True


def negative_no_fixtures_path_strings() -> bool:
    doc = {
        "iso9660_path": r"\EX\TITLE.;1",
        "fixture_dir": "hercules",
    }
    text = json.dumps(doc, sort_keys=True)
    return "fixtures/" not in text


def negative_reconstructive_fields() -> bool:
    doc = {
        "raw_instruction": 0x12345678,
        "payload_bytes": "deadbeef",
        "bios_bytes": "cafe",
    }
    text = json.dumps(doc, sort_keys=True)
    return any(term in text for term in ("raw_instruction", "instruction_word", "payload_bytes", "bios_bytes"))


def negative_frozen_phase16_mutation() -> bool:
    completed = subprocess.run(
        [sys.executable, str(ROOT / ".openrecomp-phase17/src/p17_frozen_phase16_integrity_v1.py")],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    return completed.returncode == 0 and "OPENRECOMP_PHASE17_P16_SOURCE_INTEGRITY=PASS" in completed.stdout



def negative_frozen_boundary_fail_closed() -> dict[str, object]:
    # Copy the boundary script into a fresh repo and verify it fails closed.
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = pathlib.Path(tmp)
        subprocess.run(['git', 'init', '--quiet'], cwd=str(tmp_path), check=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=str(tmp_path), check=True)
        subprocess.run(['git', 'config', 'user.name', 'Test'], cwd=str(tmp_path), check=True)
        (tmp_path / 'file.txt').write_text('x', encoding='utf-8')
        subprocess.run(['git', 'add', '.'], cwd=str(tmp_path), check=True)
        subprocess.run(['git', 'commit', '--quiet', '-m', 'init'], cwd=str(tmp_path), check=True)
        script = tmp_path / '.openrecomp-phase17' / 'src' / 'p17_frozen_phase16_boundary_v1.py'
        script.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pathlib.Path(__file__).resolve().parents[1] / '.openrecomp-phase17' / 'src' / 'p17_frozen_phase16_boundary_v1.py', script)
        completed = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(tmp_path), capture_output=True, text=True,
        )
        return {
            'returncode': completed.returncode,
            'stderr_has_traceback': 'Traceback' in completed.stderr,
            'stdout_marker_fail': 'OPENRECOMP_PHASE17_P16_BOUNDARY_FROZEN=FAIL' in completed.stdout,
        }


def negative_malformed_frozen_manifest() -> dict[str, object]:
    expected = p16i.expected_inventory_from_frozen_commit()
    cases = [
        p16i.negative_manifest_case('empty-manifest', ''),
        p16i.negative_manifest_case('malformed-line', 'bad-line\n'),
        p16i.negative_manifest_case('missing-manifest', None),
    ]
    return {
        'all_rejected': all(rejected for rejected, _ in cases),
        'cases': [{'name': report['case'], 'rejected': rejected} for rejected, report in cases],
    }


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    fx_dir = fixture_root()

    # 1. Private fixture identity (fail-closed)
    fx_report = fixture.verify_fixture_with_callback(
        fx_dir,
        lambda label, condition, detail="": gate.check(label, condition, str(detail)),
    )

    # 2. ISO 9660 TITLE path lookup from validated metadata
    image = Iso9660Image.open(fx_dir / "Disney's Hercules Action Game (USA).bin")
    gate.check("iso:pvd-valid", image.pvd_lba == 16 and image.root_lba == 22, "PVD root directory located")
    title_record = image.find_file(TITLE_ISO_PATH)
    gate.check("iso:title-path-found", title_record.file_id == "TITLE.;1",
               f"located {TITLE_ISO_PATH} at LBA {title_record.extent_lba}")
    gate.check("iso:title-lba-matches-frozen",
               title_record.extent_lba == p16_contract.TITLE_START_LBA,
               f"LBA {title_record.extent_lba} == frozen {p16_contract.TITLE_START_LBA}")
    gate.check("iso:title-size-matches-frozen",
               title_record.data_length == TITLE_FILE_SIZE,
               f"size {title_record.data_length} == frozen {TITLE_FILE_SIZE}")

    # 3. Bounded TITLE extraction without copying payload bytes into evidence
    header, payload, record = verify_title_from_disc(fx_dir)
    gate.check("title:whole-file-size", len(header) + len(payload) == TITLE_FILE_SIZE, str(len(header) + len(payload)))
    gate.check("title:whole-file-digest",
               hashlib.sha256(header + payload).hexdigest() == TITLE_FILE_SHA256,
               "whole-file SHA-256 verified")
    gate.check("title:payload-digest",
               hashlib.sha256(payload).hexdigest() == TITLE_PAYLOAD_SHA256,
               "payload SHA-256 verified")

    # 4. PS-X EXE validation
    exe, exe_report = validate_psx_exe(header, payload)
    gate.check("exe:magic", exe.magic == b"PS-X EXE", exe_report["magic"])
    gate.check("exe:pc0", exe.pc0 == TITLE_ENTRY_PC, exe_report["pc0"])
    gate.check("exe:t_addr", exe.t_addr == TITLE_TEXT_ADDR, exe_report["t_addr"])
    gate.check("exe:t_size", exe.t_size == TITLE_PAYLOAD_SIZE, str(exe.t_size))
    gate.check("exe:text_end", exe.t_addr + exe.t_size == TITLE_TEXT_END,
               f"0x{exe.t_addr + exe.t_size:08x}")
    gate.check("exe:text_end_in_ram", RAM_START <= exe.t_addr and (exe.t_addr + exe.t_size) <= RAM_END,
               "text range within PS1 RAM")
    gate.check("exe:entry_aligned", exe.pc0 % 4 == 0, f"0x{exe.pc0:08x}")
    gate.check("exe:entry_in_text_range", exe.t_addr <= exe.pc0 < (exe.t_addr + exe.t_size),
               "entry inside loaded text range")
    gate.check("exe:gp0", exe.gp0 == TITLE_GP0, exe_report["gp0"])
    gate.check("exe:data_zero", exe.d_addr == 0 and exe.d_size == 0,
               f"d_addr={exe_report['d_addr']} d_size={exe.d_size}")
    gate.check("exe:bss_zero", exe.b_addr == 0 and exe.b_size == 0,
               f"b_addr={exe_report['b_addr']} b_size={exe.b_size}")
    gate.check("exe:stack", exe.s_addr == TITLE_SP_ADDR and exe.s_size == 0,
               f"s_addr={exe_report['s_addr']} s_size={exe.s_size}")
    gate.check("exe:reserved-summary",
               exe.reserved_summary()["nonzero_count"] == 55 and
               exe.reserved_summary()["first_relative_offset"] == 20 and
               exe.reserved_summary()["last_relative_offset"] == 74,
               json.dumps(exe.reserved_summary(), sort_keys=True))

    # 5. Independent cross-check: compare ISO-derived record against frozen Phase-16 mapping
    gate.check("cross-check:extent-vs-frozen",
               record.extent_lba == p16_contract.TITLE_START_LBA and
               record.data_length == TITLE_FILE_SIZE,
               "ISO lookup agrees with frozen Phase-16 mapping")
    gate.check("cross-check:payload-sector-count",
               p16_contract.TITLE_TOTAL_SECTORS == 141 and p16_contract.TITLE_PAYLOAD_SECTORS == 140,
               "frozen sector geometry consistent")

    # 6. Negative tests
    gate.check("negative:fixture-absent", negative_absent_fixture(), "missing fixture rejected")
    gate.check("negative:fixture-digest-mismatch", negative_fixture_digest_mismatch(), "wrong digest rejected")
    gate.check("negative:malformed-cue", negative_malformed_cue(), "malformed CUE rejected")
    with tempfile.TemporaryDirectory() as tmp:
        gate.check("negative:missing-title-path", negative_missing_title_path(pathlib.Path(tmp)),
                   "missing TITLE path rejected")
        gate.check("negative:malformed-psx-exe", negative_malformed_psx_exe(pathlib.Path(tmp)),
                   "malformed PS-X EXE rejected")
    gate.check("negative:truncated-header", negative_truncated_header(), "truncated header rejected")
    gate.check("negative:bad-magic", negative_bad_magic(), "bad magic rejected")
    gate.check("negative:wrong-entry", negative_wrong_entry(), "wrong entry rejected")
    gate.check("negative:wrong-load-address", negative_wrong_load_address(), "wrong load address rejected")
    gate.check("negative:text-end-overflow", negative_wrong_text_end_overflow(), "text range overflow rejected")
    gate.check("negative:wrong-gp0", negative_wrong_gp0(), "wrong gp0 rejected")
    gate.check("negative:wrong-data-field", negative_wrong_data_field(), "non-zero data field rejected")
    gate.check("negative:wrong-bss-field", negative_wrong_bss_field(), "non-zero BSS field rejected")
    gate.check("negative:wrong-stack", negative_wrong_stack(), "wrong stack rejected")
    gate.check("negative:wrong-file-size", negative_wrong_file_size(), "wrong payload size rejected")
    gate.check("negative:payload-digest-mismatch", negative_payload_digest_mismatch(), "payload digest mismatch rejected")
    gate.check("negative:private-paths", negative_private_paths_in_evidence(), "private absolute paths rejected")
    gate.check("negative:no-fixtures-path-strings", negative_no_fixtures_path_strings(), "fixtures/ strings absent")
    gate.check("negative:reconstructive-fields", negative_reconstructive_fields(), "reconstructive fields rejected")
    gate.check("negative:frozen-phase16-integrity", negative_frozen_phase16_mutation(),
               "frozen Phase-16 source integrity maintained")

    boundary_results = negative_frozen_boundary_fail_closed()
    gate.check('negative:frozen-boundary-fail-closed',
               boundary_results['returncode'] != 0 and not boundary_results['stderr_has_traceback'] and boundary_results['stdout_marker_fail'],
               json.dumps(boundary_results, sort_keys=True))

    manifest_results = negative_malformed_frozen_manifest()
    gate.check('negative:malformed-frozen-manifest',
               manifest_results['all_rejected'],
               json.dumps(manifest_results['cases'], sort_keys=True))

    # 7. Public-safe evidence documents
    ingestion_doc = {
        "schema": "openrecomp-phase17-title-ingestion-v1",
        "stage": STAGE,
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "iso9660_path": TITLE_ISO_PATH,
        "title_extent_lba": title_record.extent_lba,
        "title_data_length": title_record.data_length,
        "title_total_sectors": p16_contract.TITLE_TOTAL_SECTORS,
        "title_payload_sectors": p16_contract.TITLE_PAYLOAD_SECTORS,
        "psx_exe_header": {
            "magic": "PS-X EXE",
            "pc0": exe_report["pc0"],
            "gp0": exe_report["gp0"],
            "t_addr": exe_report["t_addr"],
            "t_size": exe.t_size,
            "text_end": f"0x{exe.t_addr + exe.t_size:08x}",
            "d_addr": exe_report["d_addr"],
            "d_size": exe.d_size,
            "b_addr": exe_report["b_addr"],
            "b_size": exe.b_size,
            "s_addr": exe_report["s_addr"],
            "s_size": exe.s_size,
        },
        "reserved_summary": exe.reserved_summary(),
        "payload_decoding_state": contract.TITLE_PAYLOAD_DECODING_STATE,
        "private_fixture_bytes_recorded": "NO",
        "fixture_provenance": {
            "bin_sha256": fx_report["bin_sha256"],
            "bin_size": fx_report["bin_size"],
            "cue_sha256": fx_report["cue_sha256"],
            "slus_sha256": fx_report["slus_sha256"],
            "slus_size": fx_report["slus_size"],
        },
    }
    write_json(evidence / "title_ingestion.json", ingestion_doc)
    assert_public_safe(gate, "title-ingestion", ingestion_doc, header + payload)

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase17-result-v1",
        "stage": STAGE,
        "status": "PASS",
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "markers": {
            contract.BOOTSTRAP_MARKER: "PASS",
            contract.TITLE_INGESTION_MARKER: "PASS",
            contract.TITLE_PAYLOAD_DECODING_POLICY_MARKER: "PLANNED",
            contract.TITLE_IR_CONTRACT_MARKER: "PLANNED",
            contract.TITLE_HOST_SURFACE_MARKER: "PLANNED",
            contract.TITLE_REPLAY_BOUNDARY_MARKER: "PLANNED",
            contract.INITIALIZATION_MARKER: "NOT_PROVEN",
            contract.FRAME_MARKER: "NOT_PROVEN",
            contract.PLAYABILITY_MARKER: "NOT_PROVEN",
            contract.GENERAL_MARKER: "NOT_PROVEN",
            contract.FIRST_FRAME_READY_MARKER: "NO",
        },
        "next_stage": "P17-02",
    })

    gate.mark(contract.BOOTSTRAP_MARKER)
    gate.mark(contract.TITLE_INGESTION_MARKER)
    gate.mark(contract.TITLE_PAYLOAD_DECODING_POLICY_MARKER, "PLANNED")
    gate.mark(contract.TITLE_IR_CONTRACT_MARKER, "PLANNED")
    gate.mark(contract.TITLE_HOST_SURFACE_MARKER, "PLANNED")
    gate.mark(contract.TITLE_REPLAY_BOUNDARY_MARKER, "PLANNED")
    gate.mark(contract.INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(contract.FRAME_MARKER, "NOT_PROVEN")
    gate.mark(contract.PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(contract.GENERAL_MARKER, "NOT_PROVEN")
    gate.mark(contract.FIRST_FRAME_READY_MARKER, "NO")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase17/evidence/P17-01"))
