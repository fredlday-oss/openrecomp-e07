#!/usr/bin/env python3
"""OpenRecomp Phase-18 P18-06 VRAM mutation / display state V1.

P18-04 established the GP0/GP1 command frontier as UNREACHED and P18-05
established the DMA / ordering-table frontier as UNREACHED.  P18-06 asks the
VRAM/display question mechanically: *does* any authentic graphics command mutate
VRAM or the display configuration - and if so, what deterministic evidence does
it produce?

What this module does, none of it title-specific and none of it fabricating
traffic:

1. It re-uses the P18-02..P18-05 composed fail-closed overlay stack and the
   P18-04 GP0/GP1 word tap, so the words it analyses are exactly the words the
   emitted runtime's genuine, window-gated GPU write path received.
2. It adds a deterministic Python-side VRAM (1024x512x16bpp) and display-state
   model that applies the PS1 GP0 commands that mutate VRAM (fill-rectangle,
   CPU-to-VRAM copy, VRAM-to-VRAM copy) and the GP1 display-control commands
   (display enable, display start, display ranges, display mode).  Primitive
   rasterisation is explicitly NOT modelled and is never silently applied.
3. It derives framebuffer geometry from the display-area start and the display
   mode, and reports VRAM mutation as a deterministic digest plus a bounded
   region descriptor.

Every out-of-range, unaligned or unsupported input fails closed with a stable
error code.  The module promotes no proof marker: FIRST_FRAME_READY stays NO and
the Phase-18 claim markers stay NOT_PROVEN.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for _extra in ("", ".openrecomp-phase18/src", ".openrecomp-phase17/src",
               ".openrecomp-phase3/src", ".openrecomp-phase9/src"):
    _path = str(ROOT / _extra) if _extra else str(ROOT)
    if _path not in sys.path:
        sys.path.insert(0, _path)

import p18_dma_frontier_v1 as p18d  # noqa: E402
import p18_gpu_command_frontier_v1 as p18g  # noqa: E402

STAGE = "P18-06"
NEXT_STAGE = "P18-07"

#: PS1 VRAM geometry: 1024 x 512 pixels, 16 bits per pixel (1 MiB).
VRAM_WIDTH = 1024
VRAM_HEIGHT = 512
VRAM_BYTES_PER_PIXEL = 2
VRAM_SIZE = VRAM_WIDTH * VRAM_HEIGHT * VRAM_BYTES_PER_PIXEL

#: GP0 command bytes that mutate VRAM.
GP0_FILL_RECTANGLE = 0x02
GP0_VRAM_TO_VRAM_COPY = 0x80
GP0_CPU_TO_VRAM_COPY = 0xA0
GP0_VRAM_TO_CPU_COPY = 0xC0

#: GP1 display-control command bytes.
GP1_DISPLAY_ENABLE = 0x03
GP1_DISPLAY_AREA_START = 0x05
GP1_HORIZONTAL_RANGE = 0x06
GP1_VERTICAL_RANGE = 0x07
GP1_DISPLAY_MODE = 0x08

#: Display-mode horizontal resolution field (bits 0-1).
DISPLAY_MODE_HRES = {0: 256, 1: 320, 2: 512, 3: 640}

#: Primitive families whose rasterisation this stage does not model.
PRIMITIVE_MASKS = ((0xE0, 0x20, "POLYGON"), (0xE0, 0x40, "LINE"),
                   (0xE0, 0x60, "RECTANGLE"))


class VramDisplayError(ValueError):
    """Fail-closed P18-06 rejection with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hex32(value: int) -> str:
    return f"0x{value & 0xFFFFFFFF:08x}"


def _decode_xy(word: int) -> tuple[int, int]:
    value = word & 0xFFFFFFFF
    return value & 0xFFFF, (value >> 16) & 0xFFFF


def vram_address(byte_offset: int) -> int:
    """Validate a byte offset into the 1 MiB VRAM and return it.

    This is the byte-addressed form of the coordinate check: it rejects an
    address outside `0x000000..0x0FFFFF` as VRAM_ADDRESS_OUT_OF_RANGE and an
    address that does not land on a 16-bit pixel boundary as
    VRAM_ADDRESS_UNALIGNED.  Both fail closed; neither is ever rounded.
    """
    if isinstance(byte_offset, bool) or not isinstance(byte_offset, int):
        raise VramDisplayError("VRAM_ADDRESS_NOT_INTEGER", repr(byte_offset))
    if not (0 <= byte_offset < VRAM_SIZE):
        raise VramDisplayError("VRAM_ADDRESS_OUT_OF_RANGE", hex(byte_offset))
    if byte_offset % VRAM_BYTES_PER_PIXEL:
        raise VramDisplayError("VRAM_ADDRESS_UNALIGNED", hex(byte_offset))
    return byte_offset


def vram_offset(x: int, y: int) -> int:
    """Byte offset of a 16-bit VRAM pixel (10-bit coordinates)."""
    if not (0 <= x < VRAM_WIDTH and 0 <= y < VRAM_HEIGHT):
        raise VramDisplayError("VRAM_COORD_OUT_OF_RANGE", f"{x},{y}")
    return vram_address((y * VRAM_WIDTH + x) * VRAM_BYTES_PER_PIXEL)


def vram_region_digest(vram: bytearray, x: int, y: int, w: int, h: int) -> str:
    """Deterministic digest of a bounded VRAM region (row-major bytes)."""
    rows: list[bytes] = []
    for row in range(h):
        start = vram_offset(x, y + row)
        rows.append(bytes(vram[start:start + w * VRAM_BYTES_PER_PIXEL]))
    return _sha256_bytes(b"".join(rows))


def derive_framebuffer(display: dict[str, Any]) -> dict[str, Any]:
    """Derive framebuffer geometry from the display-area start and mode."""
    start_x = display.get("display_start_x", 0)
    start_y = display.get("display_start_y", 0)
    x1, x2 = display.get("horizontal_range", (0x200, 0xC00))
    y1, y2 = display.get("vertical_range", (0x10, 0x100))
    width_px = DISPLAY_MODE_HRES.get(display.get("hres_index", 0), 256)
    height_px = max(0, (y2 - y1) // 2)
    if not (0 <= start_x < VRAM_WIDTH and 0 <= start_y < VRAM_HEIGHT):
        raise VramDisplayError("DISPLAY_START_OUT_OF_RANGE", f"{start_x},{start_y}")
    return {
        "start_x": start_x,
        "start_y": start_y,
        "width_px": width_px,
        "height_px": height_px,
        "horizontal_range": [x1, x2],
        "vertical_range": [y1, y2],
        "hres_index": display.get("hres_index", 0),
        "display_enabled": display.get("display_enabled", 0),
        "bpp": 16,
        "interlaced": bool(display.get("interlaced", 0)),
    }


class VramDisplayState:
    """Deterministic PS1 VRAM + display-state model (no title constants)."""

    def __init__(self) -> None:
        self.vram = bytearray(VRAM_SIZE)
        self.display: dict[str, Any] = {
            "display_enabled": 0,
            "display_start_x": 0,
            "display_start_y": 0,
            "horizontal_range": (0x200, 0xC00),
            "vertical_range": (0x10, 0x100),
            "hres_index": 0,
            "interlaced": 0,
        }
        self.mutations: list[dict[str, Any]] = []
        self.display_events: list[dict[str, Any]] = []
        self.unsupported: list[dict[str, Any]] = []

    # --- VRAM helpers -----------------------------------------------------

    def _write_region(self, x: int, y: int, w: int, h: int, filler: Any) -> None:
        if w <= 0 or h <= 0:
            raise VramDisplayError("VRAM_REGION_EMPTY", f"{w}x{h}")
        if x < 0 or y < 0 or x + w > VRAM_WIDTH or y + h > VRAM_HEIGHT:
            raise VramDisplayError("VRAM_REGION_OUT_OF_RANGE",
                                   f"({x},{y})+{w}x{h}")
        for row in range(h):
            start = vram_offset(x, y + row)
            for col in range(w):
                value = filler(col, row) & 0xFFFF
                offset = start + col * VRAM_BYTES_PER_PIXEL
                self.vram[offset] = value & 0xFF
                self.vram[offset + 1] = (value >> 8) & 0xFF

    def _read_pixel(self, x: int, y: int) -> int:
        offset = vram_offset(x, y)
        return self.vram[offset] | (self.vram[offset + 1] << 8)

    # --- GP0 --------------------------------------------------------------

    def apply_gp0(self, words: list[int], *, owner_pc: int | None = None,
                  sequence: int = 0) -> dict[str, Any]:
        """Apply a GP0 packet; returns the mutation/classification record."""
        if not words:
            raise VramDisplayError("GP0_PACKET_EMPTY")
        command = (words[0] >> 24) & 0xFF
        record: dict[str, Any] = {
            "sequence": sequence,
            "command_byte": f"0x{command:02x}",
            "owner_pc": hex32(owner_pc) if owner_pc is not None else None,
            "word_digest": _sha256_bytes(
                b"".join((w & 0xFFFFFFFF).to_bytes(4, "little") for w in words)),
        }
        if command == GP0_FILL_RECTANGLE:
            if len(words) < 4:
                raise VramDisplayError("GP0_PACKET_TRUNCATED", "fill")
            color = words[1] & 0xFFFF
            x, y = _decode_xy(words[2])
            w, h = _decode_xy(words[3])
            self._write_region(x, y, w, h, lambda c, r: color)
            record.update({"mutation": "FILL_RECTANGLE", "x": x, "y": y,
                           "width": w, "height": h,
                           "region_digest": vram_region_digest(self.vram, x, y, w, h)})
        elif command == GP0_CPU_TO_VRAM_COPY:
            if len(words) < 3:
                raise VramDisplayError("GP0_PACKET_TRUNCATED", "cpu-to-vram")
            x, y = _decode_xy(words[1])
            w, h = _decode_xy(words[2])
            size = ((w * h + 1) // 2)
            if len(words) < 3 + size:
                raise VramDisplayError("GP0_PACKET_TRUNCATED", "cpu-to-vram-data")
            data = words[3:3 + size]
            def filler(col: int, row: int) -> int:
                index = row * w + col
                return (data[index // 2] >> (16 * (index & 1))) & 0xFFFF
            self._write_region(x, y, w, h, filler)
            record.update({"mutation": "CPU_TO_VRAM_COPY", "x": x, "y": y,
                           "width": w, "height": h,
                           "region_digest": vram_region_digest(self.vram, x, y, w, h)})
        elif command == GP0_VRAM_TO_VRAM_COPY:
            if len(words) < 4:
                raise VramDisplayError("GP0_PACKET_TRUNCATED", "vram-to-vram")
            sx, sy = _decode_xy(words[1])
            dx, dy = _decode_xy(words[2])
            w, h = _decode_xy(words[3])
            buffer = [[self._read_pixel(sx + c, sy + r) for c in range(w)]
                      for r in range(h)]
            self._write_region(dx, dy, w, h, lambda c, r: buffer[r][c])
            record.update({"mutation": "VRAM_TO_VRAM_COPY", "x": dx, "y": dy,
                           "src_x": sx, "src_y": sy, "width": w, "height": h,
                           "region_digest": vram_region_digest(self.vram, dx, dy, w, h)})
        elif command == GP0_VRAM_TO_CPU_COPY:
            record.update({"mutation": "VRAM_TO_CPU_COPY",
                           "note": "read-only; no VRAM mutation"})
        else:
            for mask, value, name in PRIMITIVE_MASKS:
                if (command & mask) == value:
                    record.update({
                        "mutation": "PRIMITIVE_RASTERISATION_NOT_MODELLED",
                        "class": name,
                        "applied": False,
                        "reason": ("primitive rasterisation is not modelled; the "
                                   "word is never silently treated as a no-op"),
                    })
                    self.unsupported.append({"sequence": sequence,
                                             "class": name,
                                             "reason": "RASTERISATION_NOT_MODELLED"})
                    return record
            classification = p18g.classify_gp0_command(words[0])
            if classification["unsupported"]:
                record.update({"mutation": "UNKNOWN", "class": "UNKNOWN",
                               "applied": False})
                self.unsupported.append({"sequence": sequence,
                                         "class": "UNKNOWN",
                                         "reason": "UNKNOWN_GP0_COMMAND"})
                return record
            record.update({"mutation": "NON_MUTATING",
                           "class": classification["class"], "applied": False})
        self.mutations.append(record)
        return record

    # --- GP1 --------------------------------------------------------------

    def apply_gp1(self, word: int, *, sequence: int = 0) -> dict[str, Any]:
        """Apply one GP1 display-control command word."""
        value = word & 0xFFFFFFFF
        command = (value >> 24) & 0xFF
        payload = value & 0x00FFFFFF
        event: dict[str, Any] = {"sequence": sequence,
                                 "command_byte": f"0x{command:02x}",
                                 "word_digest": _sha256_bytes(value.to_bytes(4, "little"))}
        if command == GP1_DISPLAY_ENABLE:
            self.display["display_enabled"] = payload & 0x1
            event["effect"] = "DISPLAY_ENABLE"
            event["enabled"] = self.display["display_enabled"]
        elif command == GP1_DISPLAY_AREA_START:
            start_x = payload & 0x3FF
            start_y = (payload >> 10) & 0x1FF
            if not (0 <= start_x < VRAM_WIDTH and 0 <= start_y < VRAM_HEIGHT):
                raise VramDisplayError("DISPLAY_START_OUT_OF_RANGE",
                                       f"{start_x},{start_y}")
            self.display["display_start_x"] = start_x
            self.display["display_start_y"] = start_y
            event["effect"] = "DISPLAY_AREA_START"
            event["start_x"] = start_x
            event["start_y"] = start_y
        elif command == GP1_HORIZONTAL_RANGE:
            self.display["horizontal_range"] = (payload & 0xFFF, (payload >> 12) & 0xFFF)
            event["effect"] = "HORIZONTAL_RANGE"
            event["range"] = list(self.display["horizontal_range"])
        elif command == GP1_VERTICAL_RANGE:
            self.display["vertical_range"] = (payload & 0x3FF, (payload >> 10) & 0x3FF)
            event["effect"] = "VERTICAL_RANGE"
            event["range"] = list(self.display["vertical_range"])
        elif command == GP1_DISPLAY_MODE:
            self.display["hres_index"] = payload & 0x3
            self.display["interlaced"] = (payload >> 5) & 0x1
            event["effect"] = "DISPLAY_MODE"
            event["hres_index"] = self.display["hres_index"]
        else:
            raise VramDisplayError("GP1_COMMAND_UNSUPPORTED", f"0x{command:02x}")
        self.display_events.append(event)
        return event

    # --- evidence ---------------------------------------------------------

    def vram_digest(self) -> str:
        return _sha256_bytes(bytes(self.vram))

    def framebuffer_digest(self) -> str:
        fb = derive_framebuffer(self.display)
        clipped_w = min(fb["width_px"], max(0, VRAM_WIDTH - fb["start_x"]))
        clipped_h = min(fb["height_px"], max(0, VRAM_HEIGHT - fb["start_y"]))
        if clipped_w <= 0 or clipped_h <= 0:
            return _sha256_bytes(b"")
        return vram_region_digest(self.vram, fb["start_x"], fb["start_y"],
                                  clipped_w, clipped_h)

    def snapshot(self) -> dict[str, Any]:
        return {
            "vram_size": VRAM_SIZE,
            "vram_digest": self.vram_digest(),
            "framebuffer": derive_framebuffer(self.display),
            "framebuffer_digest": self.framebuffer_digest(),
            "display": {
                "display_enabled": self.display["display_enabled"],
                "display_start_x": self.display["display_start_x"],
                "display_start_y": self.display["display_start_y"],
                "horizontal_range": list(self.display["horizontal_range"]),
                "vertical_range": list(self.display["vertical_range"]),
                "hres_index": self.display["hres_index"],
            },
            "mutation_count": len(self.mutations),
            "mutations": self.mutations,
            "display_event_count": len(self.display_events),
            "display_events": self.display_events,
            "unsupported": self.unsupported,
        }




def build_vram_display(runtime_result: dict[str, Any], generated_source: str,
                       provenance_map: dict[int, str]
                       ) -> tuple[dict[str, Any], str]:
    """Assemble + fail-closed validate the VRAM/display frontier document."""
    if not isinstance(runtime_result.get("p18g_fifo"), dict):
        raise VramDisplayError("GPU_FIFO_MISSING")
    if not isinstance(runtime_result.get("p18d_dma"), dict):
        raise VramDisplayError("DMA_RESULT_MISSING")

    gpu_path = p18g.write_path_discipline(generated_source)
    dma_path = p18d.dma_path_discipline(generated_source)
    if not gpu_path["gp0gp1_write_path_present"]:
        raise VramDisplayError("GPU_WRITE_PATH_ABSENT")
    if not dma_path["dma_window_tap_present"]:
        raise VramDisplayError("DMA_TAP_ABSENT")

    fifo = runtime_result["p18g_fifo"]
    events: list[dict[str, Any]] = []
    for entry in fifo["entries"]:
        phys = entry["physical_address"]
        if phys not in p18g.GP0GP1_PHYS:
            raise VramDisplayError("FIFO_ADDRESS_NOT_GP0_GP1", hex32(phys))
        owner = entry["owner_pc"]
        if owner not in provenance_map:
            raise VramDisplayError("EVENT_WITHOUT_PROVENANCE", hex32(owner))
        events.append({
            "sequence": entry["sequence"],
            "register": "GP0" if phys == p18g.GP0_PHYS else "GP1",
            "physical_address": hex32(phys),
            "owner_pc": hex32(owner),
            "owner_provenance_digest": provenance_map[owner],
            "word_digest": _sha256_bytes((entry["word"] & 0xFFFFFFFF).to_bytes(4, "little")),
        })

    reached = bool(events)
    document: dict[str, Any] = {
        "schema": "openrecomp-phase18-vram-display-frontier-v1",
        "stage": STAGE,
        "next_stage": NEXT_STAGE,
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "vram_size": VRAM_SIZE,
        "gp0_write_count": fifo["gp0_total"],
        "gp1_write_count": fifo["gp1_total"],
        "dma_access_count": runtime_result["p18d_dma"]["dma_total"],
        "vram_frontier_reached": reached,
        "events": events,
        "gpu_write_path": gpu_path,
        "dma_tap": dma_path,
        "promotes_no_proof_marker": True,
        "first_frame_ready": "NO",
    }
    if not reached:
        document["vram_display_status"] = "NOT_REACHED"
        document["explicit_not_reached"] = True
        document["basis"] = ("no authentic GP0/GP1 write was reached, so no "
                             "graphics command can mutate VRAM or display state")
    validate_vram_display(document, provenance_map)
    data = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")
    return document, _sha256_bytes(data)


def validate_vram_display(document: dict[str, Any],
                          provenance_map: dict[int, str]) -> None:
    """Fail-closed re-validation of the VRAM/display frontier document."""
    if document.get("schema") != "openrecomp-phase18-vram-display-frontier-v1":
        raise VramDisplayError("VRAM_DISPLAY_SCHEMA_MISMATCH")
    events = document.get("events")
    if not isinstance(events, list):
        raise VramDisplayError("VRAM_DISPLAY_EVENTS_MISSING")
    digests = set(provenance_map.values())
    for event in events:
        if event["physical_address"] not in (hex32(p18g.GP0_PHYS),
                                             hex32(p18g.GP1_PHYS)):
            raise VramDisplayError("VRAM_DISPLAY_ADDRESS_INVALID",
                                   event["physical_address"])
        if event.get("owner_provenance_digest") not in digests:
            raise VramDisplayError("EVENT_WITHOUT_PROVENANCE",
                                   event.get("owner_pc", "?"))
    if not events and document.get("vram_display_status") != "NOT_REACHED":
        raise VramDisplayError("UNREACHED_STATUS_MISSING")
    if events and document.get("vram_display_status") == "NOT_REACHED":
        raise VramDisplayError("REACHED_MARKED_UNREACHED")
    if document.get("first_frame_ready") != "NO":
        raise VramDisplayError("FIRST_FRAME_READY_PROMOTED")


def frontier_bytes(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


# --------------------------------------------------------------------------
# Drivers (delegating to the P18-05 composed overlay stack)
# --------------------------------------------------------------------------

def fixture_root() -> pathlib.Path:
    return p18d.fixture_root()


def continuation_analysis(*, title_analysis=None, fixture_dir=None):
    return p18d.continuation_analysis(title_analysis=title_analysis,
                                      fixture_dir=fixture_dir)


def run_continuation(generations_dir: pathlib.Path, analysis,
                     *, frontier_steps: int | None = None):
    return p18d.run_continuation(generations_dir, analysis,
                                 frontier_steps=frontier_steps)


def emit_continuation(run_dir: pathlib.Path, analysis,
                      *, frontier_steps: int | None = None):
    return p18d.emit_continuation(run_dir, analysis,
                                  frontier_steps=frontier_steps)


P18_PRIVATE_BUILD_ROOT_ENV = "OPENRECOMP_P18_PRIVATE_BUILD_ROOT_06"
DEFAULT_P18_PRIVATE_BUILD_ROOT = (ROOT.parents[1] / "private-build" / "phase18"
                                  / "P18-06")


def private_build_root() -> pathlib.Path:
    override = os.environ.get(P18_PRIVATE_BUILD_ROOT_ENV)
    if override:
        return pathlib.Path(override)
    return DEFAULT_P18_PRIVATE_BUILD_ROOT


def official_run_dir(label: str) -> pathlib.Path:
    return private_build_root() / label


if __name__ == "__main__":
    raise SystemExit(0)
