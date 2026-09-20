#!/usr/bin/env python3
"""OpenRecomp Phase-9 PS1 input/timer/event boundary V1.

The boundary defines deterministic virtual-input and virtual-time interfaces
for the bounded fixtures, plus explicit classifications for controller, timer,
event and interrupt requirements:

* controller ports (JOY_DATA/JOY_STAT/JOY_MODE/JOY_CTRL/JOY_BAUD) with a
  deterministic virtual input source (fixed button state) and explicitly
  labelled contract stubs for status reads;
* timer 0/1/2 counter/mode/target ports with a deterministic virtual clock
  (each counter read returns the current tick and advances it by one);
* interrupt ports (I_STAT/I_MASK) are classified but not modelled: any access
  is an explicit `NOT_MODELLED` blocker, never guessed.

No interrupt delivery, controller protocol, serial timing or hardware accuracy
is claimed. The interfaces are host-side and deterministic.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

INPUT_TIMER_VERSION = "1.0.0"

JOY_DATA = 0x1F801040
JOY_STAT = 0x1F801044
JOY_MODE = 0x1F801048
JOY_CTRL = 0x1F80104A
JOY_BAUD = 0x1F80104E

TIMER_PORTS = {
    "timer0": (0x1F801100, 0x1F801104, 0x1F801108),
    "timer1": (0x1F801110, 0x1F801114, 0x1F801118),
    "timer2": (0x1F801120, 0x1F801124, 0x1F801128),
}
COUNTER_PORTS = {ports[0]: name for name, ports in TIMER_PORTS.items()}
MODE_PORTS = {ports[1]: name for name, ports in TIMER_PORTS.items()}
TARGET_PORTS = {ports[2]: name for name, ports in TIMER_PORTS.items()}

I_STAT = 0x1F801070
I_MASK = 0x1F801074

VIRTUAL_INPUT_DEFAULT = 0x00000000
JOY_STAT_STUB = 0x00000001
STUB_POLICY = "contract-stub-not-hardware-accurate"
CLOCK_POLICY = "counter-read-returns-tick-then-advances"


class InputTimerError(ValueError):
    """Fail-closed input/timer boundary rejection with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass
class InputTimerAdapter:
    """Deterministic virtual input/time adapter with an event transcript."""

    buttons: int = VIRTUAL_INPUT_DEFAULT
    ticks: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)
    blockers: list[dict[str, Any]] = field(default_factory=list)

    def read(self, address: int, width_bits: int) -> dict[str, Any]:
        if width_bits not in (8, 16, 32):
            raise InputTimerError("UNSUPPORTED_WIDTH", str(width_bits))
        if address == JOY_DATA:
            value, kind = self.buttons & 0xFFFF, "VIRTUAL_INPUT"
        elif address == JOY_STAT:
            value, kind = JOY_STAT_STUB, "CONTRACT_STUB"
        elif address in COUNTER_PORTS:
            value, kind = self.ticks & 0xFFFF, "VIRTUAL_TIME"
            self.ticks += 1
        elif address in MODE_PORTS:
            value, kind = 0, "CONTRACT_STUB"
        elif address in TARGET_PORTS:
            value, kind = 0, "CONTRACT_STUB"
        elif address in (I_STAT, I_MASK):
            event = {
                "sequence": len(self.events),
                "direction": "read",
                "address": f"0x{address:08x}",
                "width_bits": width_bits,
                "class": "NOT_MODELLED",
                "blocker": True,
                "reason": "interrupt delivery is not modelled",
            }
            self.events.append(event)
            self.blockers.append(dict(event))
            return event
        else:
            raise InputTimerError("NOT_AN_INPUT_TIMER_PORT", f"0x{address:08x}")
        event = {
            "sequence": len(self.events),
            "direction": "read",
            "address": f"0x{address:08x}",
            "width_bits": width_bits,
            "value": f"0x{value & 0xFFFFFFFF:08x}",
            "class": kind,
            "blocker": False,
        }
        if kind == "CONTRACT_STUB":
            event["stub_policy"] = STUB_POLICY
        self.events.append(event)
        return event

    def write(self, address: int, width_bits: int, value: int) -> dict[str, Any]:
        if width_bits not in (8, 16, 32):
            raise InputTimerError("UNSUPPORTED_WIDTH", str(width_bits))
        if address in (JOY_MODE, JOY_CTRL, JOY_BAUD) or address in MODE_PORTS or address in TARGET_PORTS:
            event = {
                "sequence": len(self.events),
                "direction": "write",
                "address": f"0x{address:08x}",
                "width_bits": width_bits,
                "value": f"0x{value & 0xFFFFFFFF:08x}",
                "class": "RECORDED_CONFIG",
                "blocker": False,
            }
            self.events.append(event)
            return event
        if address == JOY_DATA:
            self.buttons = value & 0xFFFF
            event = {
                "sequence": len(self.events),
                "direction": "write",
                "address": f"0x{address:08x}",
                "width_bits": width_bits,
                "value": f"0x{value & 0xFFFFFFFF:08x}",
                "class": "VIRTUAL_INPUT_SET",
                "blocker": False,
            }
            self.events.append(event)
            return event
        if address in (I_STAT, I_MASK):
            event = {
                "sequence": len(self.events),
                "direction": "write",
                "address": f"0x{address:08x}",
                "width_bits": width_bits,
                "value": f"0x{value & 0xFFFFFFFF:08x}",
                "class": "NOT_MODELLED",
                "blocker": True,
                "reason": "interrupt delivery is not modelled",
            }
            self.events.append(event)
            self.blockers.append(dict(event))
            return event
        raise InputTimerError("NOT_AN_INPUT_TIMER_PORT", f"0x{address:08x}")

    def document(self) -> dict[str, Any]:
        return {
            "boundary_version": INPUT_TIMER_VERSION,
            "virtual_input": {
                "default_buttons": f"0x{self.buttons:04x}",
                "policy": "fixed-deterministic-input-source",
            },
            "virtual_time": {
                "ticks": self.ticks,
                "policy": CLOCK_POLICY,
            },
            "ports": {
                "joy": {
                    "JOY_DATA": f"0x{JOY_DATA:08x}",
                    "JOY_STAT": f"0x{JOY_STAT:08x}",
                    "JOY_MODE": f"0x{JOY_MODE:08x}",
                    "JOY_CTRL": f"0x{JOY_CTRL:08x}",
                    "JOY_BAUD": f"0x{JOY_BAUD:08x}",
                },
                "timers": {
                    name: {
                        "counter": f"0x{ports[0]:08x}",
                        "mode": f"0x{ports[1]:08x}",
                        "target": f"0x{ports[2]:08x}",
                    }
                    for name, ports in sorted(TIMER_PORTS.items())
                },
                "interrupt": {
                    "I_STAT": f"0x{I_STAT:08x}",
                    "I_MASK": f"0x{I_MASK:08x}",
                    "modelled": False,
                },
            },
            "read_stubs": {"JOY_STAT": f"0x{JOY_STAT_STUB:08x}", "policy": STUB_POLICY},
            "interrupt_delivery": "not-modelled",
            "events": list(self.events),
            "event_count": len(self.events),
            "blocker_count": len(self.blockers),
            "transcript_digest": self.transcript_digest(),
        }

    def transcript_digest(self) -> str:
        return hashlib.sha256(
            json.dumps(self.events, sort_keys=True).encode("utf-8")
        ).hexdigest()
