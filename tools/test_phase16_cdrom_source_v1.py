#!/usr/bin/env python3
"""Deterministic P16-03 CD-ROM sector delivery source gate."""

from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase16/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p16_cdrom_v1 as cdrom
import p16_contracts_v1 as contract
from p16_gate_v1 import assert_public_safe, run_stage, write_json

STAGE = "P16-03"

C_EXTENSION = ROOT / ".openrecomp-phase16" / "runtime" / "p16_cdrom_extension_v1.c"

C_HARNESS = r"""
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

enum {
    P9_RT_OK = 0,
    P9_RT_MEMORY_OUT_OF_RANGE = 1,
    P9_RT_MEMORY_WIDTH_UNSUPPORTED = 2,
    P9_RT_UNSUPPORTED_OPERATION = 13,
    P9_RT_UNKNOWN_HOST_SERVICE = 100
};

static unsigned char g_p9_ram[0x200000];

static int p9_translate_ram(uint64_t address, uint64_t width, uint32_t *out_offset)
{
    if (address >= UINT64_C(0x80000000) && address + width <= UINT64_C(0x80200000)) {
        *out_offset = (uint32_t)(address - UINT64_C(0x80000000));
        return 1;
    }
    return 0;
}

#include "p16_cdrom_extension_v1.c"

int main(int argc, char **argv)
{
    int s;
    const char *bin_path;
    if (argc < 2) {
        printf("Usage: %s <bin_path>\n", argv[0]);
        return 1;
    }
    bin_path = argv[1];

    /* 1. neg_no_path: read without path set */
    s = p16_cdrom_read_user_sectors(88u, 1u, 0x80034e80u);
    printf("neg_no_path s=%d\n", s);

    /* 2. Set valid path */
    p16_cdrom_set_disc_path(bin_path);

    /* 3. neg_out_of_bounds_lba */
    s = p16_cdrom_read_user_sectors(200000u, 1u, 0x80034e80u);
    printf("neg_oob_lba s=%d\n", s);

    /* 4. neg_out_of_range_ram */
    s = p16_cdrom_read_user_sectors(88u, 1u, 0x70000000u);
    printf("neg_oob_ram s=%d\n", s);

    /* 5. pos_read_sector_88 */
    s = p16_cdrom_read_user_sectors(88u, 1u, 0x80034000u);
    printf("pos_sec88 s=%d magic=%.8s\n", s, (char*)(g_p9_ram + 0x34000));

    /* 6. pos_read_payload (140 sectors into 0x80038098) */
    s = p16_cdrom_read_user_sectors(89u, 140u, 0x80038098u);
    printf("pos_payload s=%d sectors=%llu bytes=%llu\n",
           s, (unsigned long long)p16_cdrom_sectors_delivered(),
           (unsigned long long)p16_cdrom_bytes_delivered());

    /* Print counters */
    printf("calls=%llu failures=%llu\n",
           (unsigned long long)p16_cdrom_read_calls(),
           (unsigned long long)p16_cdrom_read_failures());

    return 0;
}
"""


def run_c_harness(bin_path: pathlib.Path) -> str:
    with tempfile.TemporaryDirectory() as temp:
        workspace = pathlib.Path(temp)
        source = workspace / "cd_harness.c"
        source.write_text(C_HARNESS, encoding="utf-8", newline="\n")
        executable = workspace / "cd_harness.exe"
        compiled = subprocess.run(
            ["clang", "-std=c11", "-Wall", "-Wextra", "-O0",
             f"-I{C_EXTENSION.parent}", str(source), "-o", str(executable)],
            capture_output=True, text=True,
        )
        if compiled.returncode != 0:
            raise AssertionError(f"compile failed: {compiled.stderr.strip()}")
        executed = subprocess.run([str(executable), str(bin_path)], capture_output=True, text=True)
        if executed.returncode != 0:
            raise AssertionError(f"harness failed: {executed.stderr.strip()}")
        return executed.stdout


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    fixture_dir = root.parents[1] / "fixtures" / "psx" / "hercules"
    bin_path = fixture_dir / "Disney's Hercules Action Game (USA).bin"
    gate.check("fixture:bin-exists", bin_path.is_file(), str(bin_path.name))

    # 1. Python source unit tests
    src = cdrom.CdromSectorSource(bin_path)
    gate.check("py:total-sectors", src.total_sectors == 174087, str(src.total_sectors))

    sec88 = src.read_user_sector(88)
    gate.check("py:sec88-size", len(sec88) == 2048, str(len(sec88)))
    gate.check("py:sec88-magic", sec88[:8] == b"PS-X EXE", sec88[:8].decode("ascii", errors="replace"))

    payload = src.read_user_sectors(89, 140)
    gate.check("py:payload-size", len(payload) == contract.TITLE_PAYLOAD_SIZE, str(len(payload)))
    payload_hash = hashlib.sha256(payload).hexdigest()
    gate.check("py:payload-hash", payload_hash == contract.TITLE_PAYLOAD_SHA256, payload_hash)

    # Python negative tests
    neg_oob = False
    try:
        src.read_user_sector(200000)
    except cdrom.CdromReadError:
        neg_oob = True
    gate.check("py:neg-oob-sector", neg_oob, "LBA 200000 raised CdromReadError")

    neg_range = False
    try:
        src.read_user_sectors(174080, 20)
    except cdrom.CdromReadError:
        neg_range = True
    gate.check("py:neg-oob-range", neg_range, "Range [174080, 174100) raised CdromReadError")

    # 2. C Runtime extension tests
    c_out = run_c_harness(bin_path)
    gate.check("c:neg-no-path", "neg_no_path s=13" in c_out, "unset path failed closed")
    gate.check("c:neg-oob-lba", "neg_oob_lba s=13" in c_out, "OOB LBA failed closed")
    gate.check("c:neg-oob-ram", "neg_oob_ram s=1" in c_out, "OOB RAM address failed closed")
    gate.check("c:pos-sec88", "pos_sec88 s=0 magic=PS-X EXE" in c_out, "sector 88 delivered")
    gate.check("c:pos-payload", "pos_payload s=0 sectors=141 bytes=288768" in c_out, "payload delivered")
    gate.check("c:counters", "calls=5 failures=3" in c_out, "call/failure counters match")

    observation = {
        "schema": "openrecomp-phase16-cdrom-source-v1",
        "stage": STAGE,
        "evidence_class": "REPRESENTATIVE_TEST_RECORD",
        "fixture_bin_size": bin_path.stat().st_size,
        "total_sectors": src.total_sectors,
        "verified_reads": [
            {"lba": 88, "count": 1, "bytes": 2048, "tag": "PS-X EXE"},
            {"lba": 89, "count": 140, "bytes": 286720, "sha256": payload_hash},
        ],
        "fail_closed_discipline": {
            "unmodeled_lba": "REFUSED_WITH_P9_RT_UNSUPPORTED_OPERATION",
            "untranslated_ram": "REFUSED_WITH_P9_RT_MEMORY_OUT_OF_RANGE",
            "missing_file": "REFUSED_WITH_P9_RT_UNSUPPORTED_OPERATION",
        },
        "private_fixture_bytes_recorded": "NO",
        "third_party_code_imported": "NO",
    }
    write_json(evidence / "cdrom_source.json", observation)
    assert_public_safe(gate, "cdrom-source", observation, b"")

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase16-result-v1",
        "stage": STAGE,
        "status": "PASS",
        "evidence_class": "REPRESENTATIVE_TEST_RECORD",
        "markers": {
            contract.CDROM_SECTOR_SOURCE_MARKER: "PASS",
            "OPENRECOMP_P16_03": "PASS",
            contract.INITIALIZATION_MARKER: "NOT_PROVEN",
            contract.FRAME_MARKER: "NOT_PROVEN",
            contract.PLAYABILITY_MARKER: "NOT_PROVEN",
            contract.GENERAL_MARKER: "NOT_PROVEN",
        },
        "next_stage": "P16-04",
    })

    gate.mark(contract.CDROM_SECTOR_SOURCE_MARKER)
    gate.mark("OPENRECOMP_P16_03")
    gate.mark(contract.INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(contract.FRAME_MARKER, "NOT_PROVEN")
    gate.mark(contract.PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(contract.GENERAL_MARKER, "NOT_PROVEN")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase16/evidence/P16-03"))
