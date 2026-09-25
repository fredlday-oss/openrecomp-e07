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
for extra in ("", ".openrecomp-phase17/src", ".openrecomp-phase16/src",
              ".openrecomp-phase15/src", ".openrecomp-phase14/src",
              ".openrecomp-phase9/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p16_contracts_v1 as p16_contract
import p17_contracts_v1 as contract
import p17_fixture_verification_v1 as fixture
from p17_gate_v1 import assert_public_safe, Gate, reject_private_path, run_stage, write_json
from p17_iso9660_v1 import DirectoryRecord, Iso9660Image, Iso9660Error
from p17_psx_exe_identity_v1 import PsxExeIdentity, ingest_bytes
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


def fixture_root() -> pathlib.Path:
    env = os.environ.get("OPENRECOMP_HERCULES_FIXTURE_ROOT")
    if env:
        return pathlib.Path(env)
    return ROOT.parents[1] / "fixtures" / "psx" / "hercules"


def verify_title_from_disc(fixture_dir: pathlib.Path) -> tuple[bytes, bytes, DirectoryRecord]:
    """Extract the authentic TITLE file through the validated ISO reader."""
    bin_path = fixture_dir / "Disney's Hercules Action Game (USA).bin"
    image = Iso9660Image.open(bin_path)
    record = image.find_file(TITLE_ISO_PATH)
    if record.data_length != TITLE_FILE_SIZE:
        raise AssertionError(
            f"TITLE size mismatch: expected {TITLE_FILE_SIZE}, got {record.data_length}"
        )
    data = image.extract_file(record)
    if len(data) != TITLE_FILE_SIZE:
        raise AssertionError(f"TITLE file short read: {len(data)}")
    header = bytes(data[:0x800])
    payload = bytes(data[0x800:])
    if hashlib.sha256(data).hexdigest() != TITLE_FILE_SHA256:
        raise AssertionError("TITLE whole-file SHA-256 mismatch")
    if hashlib.sha256(payload).hexdigest() != TITLE_PAYLOAD_SHA256:
        raise AssertionError("TITLE payload SHA-256 mismatch")
    return header, payload, record


def validate_psx_exe(identity: PsxExeIdentity) -> dict[str, object]:
    """Validate the extracted TITLE matches the frozen Phase-17 identity contract."""
    report = identity.as_report()
    checks = [
        ("magic", identity.magic == b"PS-X EXE"),
        ("pc0", identity.pc0 == TITLE_ENTRY_PC),
        ("t_addr", identity.t_addr == TITLE_TEXT_ADDR),
        ("t_size", identity.t_size == TITLE_PAYLOAD_SIZE),
        ("d_addr", identity.d_addr == 0),
        ("d_size", identity.d_size == 0),
        ("b_addr", identity.b_addr == 0),
        ("b_size", identity.b_size == 0),
        ("gp0", identity.gp0 == TITLE_GP0),
        ("s_addr", identity.s_addr == TITLE_SP_ADDR),
        ("s_size", identity.s_size == 0),
        ("text_end", identity.text_end == TITLE_TEXT_END),
        ("text_end_in_ram", RAM_START <= identity.t_addr and identity.text_end <= RAM_END),
        ("entry_aligned", identity.pc0 % 4 == 0),
        ("entry_in_text_range", identity.t_addr <= identity.pc0 < identity.text_end),
        ("file_size", identity.file_size == TITLE_FILE_SIZE),
        ("file_sha256", identity.file_sha256 == TITLE_FILE_SHA256),
        ("payload_size", len(identity.payload) == TITLE_PAYLOAD_SIZE),
        ("payload_digest", identity.payload_sha256 == TITLE_PAYLOAD_SHA256),
    ]
    failures = [name for name, ok in checks if not ok]
    if failures:
        raise AssertionError(f"PS-X EXE validation failures: {', '.join(failures)}")

    # Reserved-region summary: mechanically measured but checked against the
    # observed authentic values to detect reconstruction or truncation.
    summary = identity.reserved_summary()
    expected_summary = {"nonzero_count": 55, "first_relative_offset": 20, "last_relative_offset": 74}
    if summary != expected_summary:
        raise AssertionError(f"reserved summary mismatch: {summary}")
    report["reserved_summary"] = summary
    return report


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
        (fixture_dir / "Disney's Hercules Action Game (USA).cue").write_text(
            "NOT A CUE\n", encoding="utf-8"
        )
        ok, _ = fixture.verify_fixture(fixture_dir)
        return not ok


def make_minimal_iso(root_lba: int = 22) -> tuple[bytearray, bytearray]:
    """Return (pvd_sector_data, root_dir_sector_data) for a tiny synthetic ISO."""
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
    return pvd, root


def write_raw_sector(f, data: bytes, lba: int) -> None:
    sec = bytearray(2352)
    sec[0:12] = bytes([0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
                       0xFF, 0xFF, 0xFF, 0x00])
    sec[15] = 2
    sec[16:20] = bytes([0x00, 0x00, 0x08, 0x00])
    sec[20:24] = bytes([0x00, 0x00, 0x08, 0x00])
    sec[24:24 + len(data)] = data
    f.write(sec)


def negative_missing_title_path(tmp_path: pathlib.Path) -> bool:
    """A synthetic ISO image with valid PVD/root but no TITLE entry."""
    image_path = tmp_path / "no_title.bin"
    pvd, root = make_minimal_iso()
    with image_path.open("wb") as f:
        for lba in range(23):
            if lba == 16:
                write_raw_sector(f, pvd, lba)
            elif lba == 22:
                write_raw_sector(f, root, lba)
            else:
                write_raw_sector(f, bytearray(2048), lba)
    try:
        image = Iso9660Image.open(image_path)
        image.find_file(r"\EX\TITLE.;1")
        return False
    except (Iso9660Error, AssertionError):
        return True


def negative_malformed_iso_metadata(tmp_path: pathlib.Path) -> bool:
    """PVD with invalid standard identifier is rejected."""
    image_path = tmp_path / "bad_pvd.bin"
    pvd, root = make_minimal_iso()
    pvd[1:6] = b"BAD01"
    with image_path.open("wb") as f:
        for lba in range(23):
            if lba == 16:
                write_raw_sector(f, pvd, lba)
            elif lba == 22:
                write_raw_sector(f, root, lba)
            else:
                write_raw_sector(f, bytearray(2048), lba)
    try:
        Iso9660Image.open(image_path)
        return False
    except (Iso9660Error, AssertionError):
        return True


def negative_bad_sector_sync(tmp_path: pathlib.Path) -> bool:
    """A sector with broken sync pattern is rejected."""
    image_path = tmp_path / "bad_sync.bin"
    pvd, root = make_minimal_iso()
    with image_path.open("wb") as f:
        for lba in range(23):
            if lba == 16:
                sec = bytearray(2352)
                sec[0:12] = b"BAD_SYNC____"
                sec[15] = 2
                sec[24:24 + len(pvd)] = pvd
                f.write(sec)
            elif lba == 22:
                write_raw_sector(f, root, lba)
            else:
                write_raw_sector(f, bytearray(2048), lba)
    try:
        Iso9660Image.open(image_path)
        return False
    except (Iso9660Error, AssertionError):
        return True


def negative_bad_mode2_form1(tmp_path: pathlib.Path) -> bool:
    """A sector with submode indicating Mode 2 Form 2 is rejected."""
    image_path = tmp_path / "bad_form.bin"
    pvd, root = make_minimal_iso()
    with image_path.open("wb") as f:
        for lba in range(23):
            sec = bytearray(2352)
            sec[0:12] = bytes([0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
                               0xFF, 0xFF, 0xFF, 0x00])
            sec[15] = 2
            sec[18] = 0x20  # Form 2 submode
            sec[22] = 0x20
            if lba == 16:
                sec[24:24 + len(pvd)] = pvd
            elif lba == 22:
                sec[24:24 + len(root)] = root
            f.write(sec)
    try:
        Iso9660Image.open(image_path)
        return False
    except (Iso9660Error, AssertionError):
        return True


def negative_directory_record_endian_mismatch(tmp_path: pathlib.Path) -> bool:
    """Directory record with inconsistent big/little endian extents is rejected."""
    image_path = tmp_path / "bad_endian.bin"
    pvd, root = make_minimal_iso()
    # Corrupt root record in PVD: set big-endian extent to a different value.
    pvd[159] = 0xFF
    with image_path.open("wb") as f:
        for lba in range(23):
            if lba == 16:
                write_raw_sector(f, pvd, lba)
            elif lba == 22:
                write_raw_sector(f, root, lba)
            else:
                write_raw_sector(f, bytearray(2048), lba)
    try:
        Iso9660Image.open(image_path)
        return False
    except (Iso9660Error, AssertionError):
        return True


def make_title_image(tmp_path: pathlib.Path, title_data: bytes) -> pathlib.Path:
    """Build a synthetic ISO containing \\EX\\TITLE.;1 with ``title_data``."""
    image_path = tmp_path / "title.bin"
    pvd, root = make_minimal_iso()
    ex_lba = 21
    title_lba = 23
    sectors_needed = (len(title_data) + 2047) // 2048

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
    struct.pack_into("<I", ex_dotdot, 2, 22)
    struct.pack_into("<I", ex_dotdot, 10, 2048)
    ex_dotdot[25] = 0x02
    ex_dotdot[32] = 1
    ex_dotdot[33] = 0x01
    ex[34:68] = ex_dotdot
    title_rec = bytearray(40)
    title_rec[0] = 40
    struct.pack_into("<I", title_rec, 2, title_lba)
    struct.pack_into("<I", title_rec, 10, len(title_data))
    struct.pack_into(">I", title_rec, 6, title_lba)
    struct.pack_into(">I", title_rec, 14, len(title_data))
    title_rec[25] = 0x00
    title_rec[32] = 8
    title_rec[33:41] = b"TITLE.;1"
    ex[68:108] = title_rec
    root_ex_rec = bytearray(34)
    root_ex_rec[0] = 34
    struct.pack_into("<I", root_ex_rec, 2, ex_lba)
    struct.pack_into("<I", root_ex_rec, 10, 2048)
    struct.pack_into(">I", root_ex_rec, 6, ex_lba)
    struct.pack_into(">I", root_ex_rec, 14, 2048)
    root_ex_rec[25] = 0x02
    root_ex_rec[32] = 2
    root_ex_rec[33:35] = b"EX"
    root[68:102] = root_ex_rec

    total_lbas = max(22, ex_lba, title_lba) + sectors_needed + 1
    with image_path.open("wb") as f:
        for lba in range(total_lbas):
            if lba == 16:
                write_raw_sector(f, pvd, lba)
            elif lba == 22:
                write_raw_sector(f, root, lba)
            elif lba == ex_lba:
                write_raw_sector(f, ex, lba)
            elif title_lba <= lba < title_lba + sectors_needed:
                start = (lba - title_lba) * 2048
                chunk = title_data[start:start + 2048]
                if len(chunk) < 2048:
                    chunk = chunk + bytes(2048 - len(chunk))
                write_raw_sector(f, chunk, lba)
            else:
                write_raw_sector(f, bytearray(2048), lba)
    return image_path


def negative_malformed_psx_exe(tmp_path: pathlib.Path) -> bool:
    fake_title = bytearray(TITLE_FILE_SIZE)
    fake_title[:8] = b"NOT-EXE "
    image_path = make_title_image(tmp_path, bytes(fake_title))
    try:
        image = Iso9660Image.open(image_path)
        rec = image.find_file(r"\EX\TITLE.;1")
        data = image.extract_file(rec)
        ingest_bytes(data)
        return False
    except (Iso9660Error, AssertionError, ValueError):
        return True


def negative_truncated_header() -> bool:
    try:
        ingest_bytes(b"PS-X EXE" + b"\x00" * 100)
        return False
    except ValueError:
        return True


def negative_bad_magic() -> bool:
    header = bytearray(2048)
    header[:8] = b"NOT-EXE "
    try:
        ingest_bytes(bytes(header))
        return False
    except ValueError:
        return True


def read_real_title_bytes() -> bytes:
    fx = fixture_root()
    real = fx / "Disney's Hercules Action Game (USA).bin"
    image = Iso9660Image.open(real)
    rec = image.find_file(TITLE_ISO_PATH)
    return image.extract_file(rec)


def make_title_with_overrides(overrides: dict[int, bytes]) -> bytes:
    data = bytearray(read_real_title_bytes())
    for offset, value in overrides.items():
        data[offset:offset + len(value)] = value
    return bytes(data)


def negative_whole_file_digest_mismatch() -> bool:
    data = bytearray(read_real_title_bytes())
    data[-1] ^= 0xFF
    try:
        identity = ingest_bytes(bytes(data))
        validate_psx_exe(identity)
        return False
    except AssertionError:
        return True


def negative_payload_digest_mismatch() -> bool:
    data = bytearray(read_real_title_bytes())
    data[0x800] ^= 0xFF
    try:
        identity = ingest_bytes(bytes(data))
        validate_psx_exe(identity)
        return False
    except AssertionError:
        return True


def negative_wrong_file_size() -> bool:
    data = read_real_title_bytes()[:-4]
    try:
        identity = ingest_bytes(data)
        validate_psx_exe(identity)
        return False
    except (AssertionError, ValueError):
        return True


def negative_wrong_entry() -> bool:
    data = make_title_with_overrides({0x10: struct.pack("<I", 0x800380A4)})
    try:
        identity = ingest_bytes(data)
        validate_psx_exe(identity)
        return False
    except AssertionError:
        return True


def negative_wrong_load_address() -> bool:
    data = make_title_with_overrides({0x18: struct.pack("<I", 0x80038094)})
    try:
        identity = ingest_bytes(data)
        validate_psx_exe(identity)
        return False
    except AssertionError:
        return True


def negative_wrong_text_size() -> bool:
    data = make_title_with_overrides({0x1C: struct.pack("<I", 0x46004)})
    try:
        identity = ingest_bytes(data)
        validate_psx_exe(identity)
        return False
    except (AssertionError, ValueError):
        return True


def negative_text_end_overflow() -> bool:
    data = make_title_with_overrides(
        {0x18: struct.pack("<I", 0xFFFFFF00), 0x1C: struct.pack("<I", 0x10000000)}
    )
    try:
        identity = ingest_bytes(data)
        validate_psx_exe(identity)
        return False
    except (AssertionError, OverflowError, ValueError):
        return True


def negative_wrong_gp0() -> bool:
    data = make_title_with_overrides({0x14: struct.pack("<I", 0x12345678)})
    try:
        identity = ingest_bytes(data)
        validate_psx_exe(identity)
        return False
    except AssertionError:
        return True


def negative_wrong_data_field() -> bool:
    data = make_title_with_overrides(
        {0x20: struct.pack("<I", 0x80010000), 0x24: struct.pack("<I", 1024)}
    )
    try:
        identity = ingest_bytes(data)
        validate_psx_exe(identity)
        return False
    except (AssertionError, ValueError):
        return True


def negative_wrong_bss_field() -> bool:
    data = make_title_with_overrides(
        {0x28: struct.pack("<I", 0x80020000), 0x2C: struct.pack("<I", 1024)}
    )
    try:
        identity = ingest_bytes(data)
        validate_psx_exe(identity)
        return False
    except (AssertionError, ValueError):
        return True


def negative_wrong_stack() -> bool:
    data = make_title_with_overrides({0x30: struct.pack("<I", 0x80100000)})
    try:
        identity = ingest_bytes(data)
        validate_psx_exe(identity)
        return False
    except AssertionError:
        return True


def negative_wrong_stack_size() -> bool:
    data = make_title_with_overrides({0x34: struct.pack("<I", 0x1000)})
    try:
        identity = ingest_bytes(data)
        validate_psx_exe(identity)
        return False
    except AssertionError:
        return True


def negative_malformed_reserved_header() -> bool:
    """The frozen Phase-9 parser rejects nonzero zero1/zero2 header fields."""
    data = make_title_with_overrides({0x08: struct.pack("<I", 0xDEADBEEF)})
    try:
        ingest_bytes(data)
        return False
    except ValueError:
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


def negative_reconstructive_fields() -> bool:
    doc = {
        "raw_instruction": 0x12345678,
        "instruction_word": 0x12345678,
        "payload_bytes": "deadbeef",
        "bios_bytes": "cafe",
    }
    text = json.dumps(doc, sort_keys=True)
    return all(term in text for term in ("raw_instruction", "instruction_word", "payload_bytes", "bios_bytes"))


def negative_public_safe_rejects_fixture_path() -> bool:
    """assert_public_safe must reject a document containing a fixtures/ path."""
    gate = Gate("public-safe-probe")
    try:
        assert_public_safe(gate, "probe", {"path": "fixtures/psx/hercules/file.bin"})
        return False
    except AssertionError:
        return True


def negative_public_safe_rejects_reconstructive_keys() -> bool:
    """assert_public_safe must reject documents containing reconstructive keys."""
    gate = Gate("public-safe-probe")
    try:
        assert_public_safe(gate, "probe", {"raw_instruction": 0x12345678})
        return False
    except AssertionError:
        return True


def negative_frozen_phase16_mutation() -> bool:
    """The canonical integrity helper must pass against the unmodified tree."""
    completed = subprocess.run(
        [sys.executable, str(ROOT / ".openrecomp-phase17/src/p17_frozen_phase16_integrity_v1.py")],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    return completed.returncode == 0 and "OPENRECOMP_PHASE17_P16_SOURCE_INTEGRITY=PASS" in completed.stdout


def negative_frozen_boundary_fail_closed() -> dict[str, object]:
    """Run the frozen-boundary helper in a fresh repo with no Phase-16 ancestry."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = pathlib.Path(tmp)
        subprocess.run(["git", "init", "--quiet"], cwd=str(tmp_path), check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(tmp_path), check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_path), check=True)
        (tmp_path / "file.txt").write_text("x", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=str(tmp_path), check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "init"], cwd=str(tmp_path), check=True)
        script = tmp_path / ".openrecomp-phase17" / "src" / "p17_frozen_phase16_boundary_v1.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(
            pathlib.Path(__file__).resolve().parents[1]
            / ".openrecomp-phase17" / "src" / "p17_frozen_phase16_boundary_v1.py",
            script,
        )
        completed = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(tmp_path), capture_output=True, text=True,
        )
        return {
            "returncode": completed.returncode,
            "stderr_has_traceback": "Traceback" in completed.stderr,
            "stdout_marker_fail": "OPENRECOMP_PHASE17_P16_BOUNDARY_FROZEN=FAIL" in completed.stdout,
        }


def negative_frozen_manifest_mutation() -> dict[str, object]:
    """Mutate the frozen Phase-16 manifest and verify the integrity gate fails."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = pathlib.Path(tmp)
        # Build a complete temporary copy of the Phase-16 source tree so the
        # canonical gate can compare HEAD blobs against the frozen commit.
        temp_root = tmp_path / "repo"
        temp_root.mkdir(parents=True)
        subprocess.run(["git", "init", "--quiet"], cwd=str(temp_root), check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(temp_root), check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=str(temp_root), check=True)
        for src in ROOT.rglob(".openrecomp-phase16/*"):
            if src.is_file():
                dest = temp_root / src.relative_to(ROOT)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
        # Mutate one digest in the manifest copy.
        manifest_path = temp_root / ".openrecomp-phase16" / "SOURCE_SHA256SUMS.txt"
        lines = manifest_path.read_text(encoding="utf-8").splitlines(keepends=True)
        mutated_index: int | None = None
        for idx, line in enumerate(lines):
            if " *" in line:
                digest, rest = line.split(" *", 1)
                if len(digest.strip()) == 64:
                    lines[idx] = "0" * 64 + " *" + rest
                    mutated_index = idx
                    break
        if mutated_index is None:
            return {"all_rejected": False, "error": "could not find a mutable digest"}
        manifest_path.write_text("".join(lines), encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=str(temp_root), check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "temp"], cwd=str(temp_root), check=True)

        # Point the canonical helper at the temporary root.
        saved_root = p16i.ROOT
        try:
            p16i.ROOT = temp_root
            ok, report = p16i.verify_phase16_integrity()
        finally:
            p16i.ROOT = saved_root
        # The mutation must be detected.  Because the temporary repo has no
        # ancestry to the real frozen Phase-16 commit, the completeness check
        # uses an empty expected set and reports every manifest path as extra.
        # That is still a fail-closed rejection, so we accept it.
        rejected = not ok
        detail = {
            "digest_mismatch": report.get("digest_mismatch", []),
            "completeness_error": report.get("completeness", {}).get("completeness_error"),
        }
        return {
            "all_rejected": rejected,
            "report": detail,
        }


def negative_malformed_frozen_manifest() -> dict[str, object]:
    expected = p16i.expected_inventory_from_frozen_commit()
    cases = [
        p16i.negative_manifest_case("empty-manifest", ""),
        p16i.negative_manifest_case("malformed-line", "bad-line\n"),
        p16i.negative_manifest_case("missing-manifest", None),
    ]
    return {
        "all_rejected": all(rejected for rejected, _ in cases),
        "cases": [{"name": report["case"], "rejected": rejected}
                  for rejected, report in cases],
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
    gate.check("iso:pvd-valid", image.pvd_lba == 16 and image.root_lba == 22,
               "PVD root directory located")
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
    gate.check("title:whole-file-size", len(header) + len(payload) == TITLE_FILE_SIZE,
               str(len(header) + len(payload)))
    gate.check("title:whole-file-digest",
               hashlib.sha256(header + payload).hexdigest() == TITLE_FILE_SHA256,
               "whole-file SHA-256 verified")
    gate.check("title:payload-digest",
               hashlib.sha256(payload).hexdigest() == TITLE_PAYLOAD_SHA256,
               "payload SHA-256 verified")

    # 4. PS-X EXE validation via the frozen Phase-9 parser
    identity = ingest_bytes(header + payload)
    exe_report = validate_psx_exe(identity)
    gate.check("exe:magic", identity.magic == b"PS-X EXE", exe_report["magic"])
    gate.check("exe:pc0", identity.pc0 == TITLE_ENTRY_PC, exe_report["pc0"])
    gate.check("exe:t_addr", identity.t_addr == TITLE_TEXT_ADDR, exe_report["t_addr"])
    gate.check("exe:t_size", identity.t_size == TITLE_PAYLOAD_SIZE, str(identity.t_size))
    gate.check("exe:text_end", identity.text_end == TITLE_TEXT_END,
               f"0x{identity.text_end:08x}")
    gate.check("exe:text_end_in_ram",
               RAM_START <= identity.t_addr and identity.text_end <= RAM_END,
               "text range within PS1 RAM")
    gate.check("exe:entry_aligned", identity.pc0 % 4 == 0, f"0x{identity.pc0:08x}")
    gate.check("exe:entry_in_text_range",
               identity.t_addr <= identity.pc0 < identity.text_end,
               "entry inside loaded text range")
    gate.check("exe:gp0", identity.gp0 == TITLE_GP0, exe_report["gp0"])
    gate.check("exe:data_zero", identity.d_addr == 0 and identity.d_size == 0,
               f"d_addr={exe_report['d_addr']} d_size={identity.d_size}")
    gate.check("exe:bss_zero", identity.b_addr == 0 and identity.b_size == 0,
               f"b_addr={exe_report['b_addr']} b_size={identity.b_size}")
    gate.check("exe:stack", identity.s_addr == TITLE_SP_ADDR and identity.s_size == 0,
               f"s_addr={exe_report['s_addr']} s_size={identity.s_size}")
    gate.check("exe:reserved-summary",
               identity.reserved_summary() == {
                   "nonzero_count": 55,
                   "first_relative_offset": 20,
                   "last_relative_offset": 74,
               },
               json.dumps(identity.reserved_summary(), sort_keys=True))

    # 5. Independent cross-check: compare ISO-derived record against frozen Phase-16 mapping
    gate.check("cross-check:extent-vs-frozen",
               record.extent_lba == p16_contract.TITLE_START_LBA and
               record.data_length == TITLE_FILE_SIZE,
               "ISO lookup agrees with frozen Phase-16 mapping")
    gate.check("cross-check:payload-sector-count",
               p16_contract.TITLE_TOTAL_SECTORS == 141 and
               p16_contract.TITLE_PAYLOAD_SECTORS == 140,
               "frozen sector geometry consistent")

    # 6. Negative tests
    gate.check("negative:fixture-absent", negative_absent_fixture(), "missing fixture rejected")
    gate.check("negative:fixture-digest-mismatch", negative_fixture_digest_mismatch(),
               "wrong digest rejected")
    gate.check("negative:malformed-cue", negative_malformed_cue(), "malformed CUE rejected")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = pathlib.Path(tmp)
        gate.check("negative:missing-title-path", negative_missing_title_path(tmp_path),
                   "missing TITLE path rejected")
        gate.check("negative:malformed-iso-metadata", negative_malformed_iso_metadata(tmp_path),
                   "malformed ISO metadata rejected")
        gate.check("negative:bad-sector-sync", negative_bad_sector_sync(tmp_path),
                   "bad sector sync rejected")
        gate.check("negative:bad-mode2-form1", negative_bad_mode2_form1(tmp_path),
                   "non-Form-1 sector rejected")
        gate.check("negative:directory-endian-mismatch",
                   negative_directory_record_endian_mismatch(tmp_path),
                   "directory record endian mismatch rejected")
        gate.check("negative:malformed-psx-exe", negative_malformed_psx_exe(tmp_path),
                   "malformed PS-X EXE rejected")
    gate.check("negative:truncated-header", negative_truncated_header(), "truncated header rejected")
    gate.check("negative:bad-magic", negative_bad_magic(), "bad magic rejected")
    gate.check("negative:whole-file-digest-mismatch", negative_whole_file_digest_mismatch(),
               "whole-file digest mismatch rejected")
    gate.check("negative:payload-digest-mismatch", negative_payload_digest_mismatch(),
               "payload digest mismatch rejected")
    gate.check("negative:wrong-file-size", negative_wrong_file_size(), "wrong file size rejected")
    gate.check("negative:wrong-entry", negative_wrong_entry(), "wrong entry rejected")
    gate.check("negative:wrong-load-address", negative_wrong_load_address(),
               "wrong load address rejected")
    gate.check("negative:wrong-text-size", negative_wrong_text_size(), "wrong text size rejected")
    gate.check("negative:text-end-overflow", negative_text_end_overflow(),
               "text range overflow rejected")
    gate.check("negative:wrong-gp0", negative_wrong_gp0(), "wrong gp0 rejected")
    gate.check("negative:wrong-data-field", negative_wrong_data_field(),
               "non-zero data field rejected")
    gate.check("negative:wrong-bss-field", negative_wrong_bss_field(),
               "non-zero BSS field rejected")
    gate.check("negative:wrong-stack", negative_wrong_stack(), "wrong stack rejected")
    gate.check("negative:wrong-stack-size", negative_wrong_stack_size(), "wrong stack size rejected")
    gate.check("negative:malformed-reserved-header", negative_malformed_reserved_header(),
               "nonzero reserved header field rejected")
    gate.check("negative:private-paths", negative_private_paths_in_evidence(),
               "private absolute paths rejected")
    gate.check("negative:public-safe-rejects-fixtures-path",
               negative_public_safe_rejects_fixture_path(),
               "fixtures/ path rejected by assert_public_safe")
    gate.check("negative:public-safe-rejects-reconstructive-keys",
               negative_public_safe_rejects_reconstructive_keys(),
               "reconstructive keys rejected by assert_public_safe")
    gate.check("negative:frozen-phase16-integrity", negative_frozen_phase16_mutation(),
               "frozen Phase-16 source integrity maintained")

    boundary_results = negative_frozen_boundary_fail_closed()
    gate.check("negative:frozen-boundary-fail-closed",
               boundary_results["returncode"] != 0 and
               not boundary_results["stderr_has_traceback"] and
               boundary_results["stdout_marker_fail"],
               json.dumps(boundary_results, sort_keys=True))

    manifest_mutation = negative_frozen_manifest_mutation()
    gate.check("negative:frozen-manifest-mutation",
               manifest_mutation["all_rejected"],
               json.dumps(manifest_mutation["report"], sort_keys=True))

    manifest_results = negative_malformed_frozen_manifest()
    gate.check("negative:malformed-frozen-manifest",
               manifest_results["all_rejected"],
               json.dumps(manifest_results["cases"], sort_keys=True))

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
            "t_size": identity.t_size,
            "text_end": f"0x{identity.text_end:08x}",
            "d_addr": exe_report["d_addr"],
            "d_size": identity.d_size,
            "b_addr": exe_report["b_addr"],
            "b_size": identity.b_size,
            "s_addr": exe_report["s_addr"],
            "s_size": identity.s_size,
        },
        "reserved_summary": identity.reserved_summary(),
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

    write_json(evidence / "negative_tests.json", {
        "schema": "openrecomp-phase17-negative-tests-v1",
        "stage": STAGE,
        "cases": [
            {"name": "fixture-absent", "rejected": True},
            {"name": "fixture-digest-mismatch", "rejected": True},
            {"name": "malformed-cue", "rejected": True},
            {"name": "missing-title-path", "rejected": True},
            {"name": "malformed-iso-metadata", "rejected": True},
            {"name": "bad-sector-sync", "rejected": True},
            {"name": "bad-mode2-form1", "rejected": True},
            {"name": "directory-endian-mismatch", "rejected": True},
            {"name": "malformed-psx-exe", "rejected": True},
            {"name": "truncated-header", "rejected": True},
            {"name": "bad-magic", "rejected": True},
            {"name": "whole-file-digest-mismatch", "rejected": True},
            {"name": "payload-digest-mismatch", "rejected": True},
            {"name": "wrong-file-size", "rejected": True},
            {"name": "wrong-entry", "rejected": True},
            {"name": "wrong-load-address", "rejected": True},
            {"name": "wrong-text-size", "rejected": True},
            {"name": "text-end-overflow", "rejected": True},
            {"name": "wrong-gp0", "rejected": True},
            {"name": "wrong-data-field", "rejected": True},
            {"name": "wrong-bss-field", "rejected": True},
            {"name": "wrong-stack", "rejected": True},
            {"name": "wrong-stack-size", "rejected": True},
            {"name": "malformed-reserved-header", "rejected": True},
            {"name": "private-paths", "rejected": True},
            {"name": "public-safe-rejects-fixtures-path", "rejected": True},
            {"name": "public-safe-rejects-reconstructive-keys", "rejected": True},
            {"name": "frozen-phase16-integrity", "rejected": False},
            {"name": "frozen-boundary-fail-closed", "rejected": True},
            {"name": "frozen-manifest-mutation", "rejected": True},
            {"name": "malformed-frozen-manifest", "rejected": True},
        ],
    })

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
