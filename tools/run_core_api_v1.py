#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openrecomp import HostBinding, ModuleImage, ReferenceExecutor
from openrecomp.runtime import CoreRuntimeError

MASK32 = 0xFFFFFFFF


class E07ReferenceHost(HostBinding):
    """Contract-driven E07 host used only for the Core API equivalence proof."""

    def __init__(self, contract: dict):
        self.contract = contract
        if contract["system"]["wall_clock"] or contract["system"]["randomness"]:
            raise CoreRuntimeError("E07 proof host requires deterministic system services")
        self.tick_count = contract["system"].get("tick_start", 0) & MASK32
        self.graphics_calls = 0
        self.audio_calls = 0
        self.input_calls = 0
        self.system_calls = 0
        self.framebuffer = bytearray(
            contract["graphics"]["width"]
            * contract["graphics"]["height"]
            * contract["graphics"]["channels"]
        )
        self.audio_buffer = [0] * contract["audio"]["sample_count"]

    @property
    def contract_version(self) -> str:
        return self.contract["contract_version"]

    @property
    def symbols(self) -> frozenset[str]:
        return frozenset({"host_graphics", "host_audio", "host_input", "host_system"})

    def call(self, symbol: str, args: list[int]) -> int | None:
        if symbol == "host_graphics":
            if len(args) != 3:
                raise CoreRuntimeError("host_graphics arity mismatch")
            self.graphics_calls = (self.graphics_calls + 1) & MASK32
            x, y, value = args
            width = self.contract["graphics"]["width"]
            height = self.contract["graphics"]["height"]
            channels = self.contract["graphics"]["channels"]
            if channels != 3:
                raise CoreRuntimeError("E07 proof host requires RGB graphics")
            if x < width and y < height:
                index = (y * width + x) * channels
                byte = value & 0xFF
                self.framebuffer[index] = byte
                self.framebuffer[index + 1] = (byte ^ self.contract["graphics"]["xor_g"]) & 0xFF
                self.framebuffer[index + 2] = (byte ^ self.contract["graphics"]["xor_b"]) & 0xFF
            return None

        if symbol == "host_audio":
            if len(args) != 1:
                raise CoreRuntimeError("host_audio arity mismatch")
            self.audio_calls = (self.audio_calls + 1) & MASK32
            sample = args[0]
            step = self.contract["audio"]["sample_step"]
            for index in range(len(self.audio_buffer)):
                self.audio_buffer[index] = (sample + index * step) & 0xFFFF
            return None

        if symbol == "host_input":
            if len(args) != 1:
                raise CoreRuntimeError("host_input arity mismatch")
            self.input_calls = (self.input_calls + 1) & MASK32
            values = self.contract["input"]["values"]
            if not values:
                raise CoreRuntimeError("host input script is empty")
            return values[args[0] % len(values)] & MASK32

        if symbol == "host_system":
            if len(args) != 2:
                raise CoreRuntimeError("host_system arity mismatch")
            self.system_calls = (self.system_calls + 1) & MASK32
            result = (
                args[0]
                + args[1]
                + self.contract["system"]["deterministic_bias"]
                + self.tick_count
            ) & MASK32
            self.tick_count = (self.tick_count + 1) & MASK32
            return result

        raise CoreRuntimeError(f"unknown E07 host symbol {symbol}")

    def snapshot(self) -> dict:
        return {
            "tick_count": self.tick_count,
            "graphics_calls": self.graphics_calls,
            "audio_calls": self.audio_calls,
            "input_calls": self.input_calls,
            "system_calls": self.system_calls,
        }

    def proof_result(self, observed_state: int, operations: int) -> dict:
        h = (
            observed_state
            ^ self.tick_count
            ^ (self.graphics_calls << 4)
            ^ (self.audio_calls << 8)
            ^ (self.input_calls << 12)
            ^ (self.system_calls << 16)
        ) & MASK32
        for byte in self.framebuffer:
            h = ((h * 16777619) ^ byte) & MASK32
        for sample in self.audio_buffer:
            h = ((h * 16777619) ^ (sample & 0xFFFF)) & MASK32
        audio_bytes = b"".join((sample & 0xFFFF).to_bytes(2, "little") for sample in self.audio_buffer)
        return {
            "return_a0": observed_state & MASK32,
            "tick_count": self.tick_count,
            "graphics_calls": self.graphics_calls,
            "audio_calls": self.audio_calls,
            "input_calls": self.input_calls,
            "system_calls": self.system_calls,
            "checksum": h,
            "operations": operations,
            "framebuffer_sha256": hashlib.sha256(bytes(self.framebuffer)).hexdigest(),
            "audio_payload_sha256": hashlib.sha256(audio_bytes).hexdigest(),
        }


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        print(
            "usage: run_core_api_v1.py <module-v1.json> <ir-v1.json> <host-contract.json> <out-result.json>",
            file=sys.stderr,
        )
        return 2
    try:
        module = ModuleImage.from_files(argv[1], argv[2], argv[3])
        host = E07ReferenceHost(module.host_contract)
        execution = ReferenceExecutor(module, host).run()
        result = host.proof_result(execution.observed_state, execution.operations)
        Path(argv[4]).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, KeyError, ValueError, CoreRuntimeError) as exc:
        print(f"OPENRECOMP_CORE_API_V1_RUNTIME=FAIL: {exc}", file=sys.stderr)
        return 2

    print(f"CORE_API_V1_CHECKSUM={result['checksum']}")
    print(f"CORE_API_V1_RETURN_A0={result['return_a0']}")
    print("OPENRECOMP_CORE_API_V1_RUNTIME=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
