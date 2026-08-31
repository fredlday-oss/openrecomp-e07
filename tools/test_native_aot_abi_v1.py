#!/usr/bin/env python3
from __future__ import annotations

import ctypes
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openrecomp import ModuleImage
from tools.aot_native_module_v1 import (
    NativeAOTApiV1,
    NativeAOTHostV1,
    NativeAOTModule,
    NativeHostCallbackV1,
    OPENRECOMP_NATIVE_AOT_ABI_V1,
    OPENRECOMP_NATIVE_AOT_CAP_DETERMINISTIC_FAULTS,
    OPENRECOMP_NATIVE_AOT_CAP_HOST_CALLS,
    OPENRECOMP_NATIVE_AOT_CAP_MEMORY_READ,
    OPENRECOMP_NATIVE_AOT_CAP_STATE_INSPECTION,
    OPENRECOMP_NATIVE_AOT_ENDIAN_BIG,
    OPENRECOMP_NATIVE_AOT_ENDIAN_LITTLE,
)


def reject(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def decode(raw: bytes | None, field: str) -> str:
    if raw is None:
        raise AssertionError(f"null ABI metadata: {field}")
    return raw.decode("ascii")


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        print("usage: test_native_aot_abi_v1.py <module.so> <module.json> <ir.json> <host-contract.json>", file=sys.stderr)
        return 2

    try:
        so_path, module_path, ir_path, contract_path = map(Path, argv[1:])
        module = ModuleImage.from_files(module_path, ir_path, contract_path)
        lib = ctypes.CDLL(str(so_path.resolve()))

        query = lib.openrecomp_native_aot_query
        query.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
        query.restype = ctypes.POINTER(NativeAOTApiV1)
        api_size = ctypes.sizeof(NativeAOTApiV1)

        api_ptr = query(OPENRECOMP_NATIVE_AOT_ABI_V1, api_size)
        reject(bool(api_ptr), "exact Native AOT ABI V1 query was rejected")
        api = api_ptr.contents
        reject(api.struct_size == api_size, "ABI structure size mismatch")
        reject(api.abi_version == OPENRECOMP_NATIVE_AOT_ABI_V1, "ABI version mismatch")
        print("OPENRECOMP_NATIVE_AOT_ABI_V1_QUERY=PASS")

        reject(not bool(query(0, api_size)), "ABI version 0 was accepted")
        reject(not bool(query(0x00020000, api_size)), "unsupported ABI V2 was accepted")
        print("OPENRECOMP_NATIVE_AOT_ABI_V1_VERSION_REJECTION=PASS")

        reject(not bool(query(OPENRECOMP_NATIVE_AOT_ABI_V1, 0)), "zero API size was accepted")
        reject(not bool(query(OPENRECOMP_NATIVE_AOT_ABI_V1, api_size - 1)), "short API size was accepted")
        reject(not bool(query(OPENRECOMP_NATIVE_AOT_ABI_V1, api_size + 1)), "oversized API size was accepted")
        print("OPENRECOMP_NATIVE_AOT_ABI_V1_SIZE_REJECTION=PASS")

        ir = module.ir
        source = ir["source"]
        expected_endian = (
            OPENRECOMP_NATIVE_AOT_ENDIAN_BIG
            if source["endianness"] == "big"
            else OPENRECOMP_NATIVE_AOT_ENDIAN_LITTLE
        )
        reject(decode(api.module_id, "module_id") == module.manifest["module_id"], "module_id metadata mismatch")
        reject(decode(api.module_format_version, "module_format_version") == module.manifest["module_format_version"], "module format metadata mismatch")
        reject(decode(api.ir_version, "ir_version") == ir["ir_version"], "IR version metadata mismatch")
        reject(decode(api.host_contract_version, "host_contract_version") == module.host_contract["contract_version"], "host contract metadata mismatch")
        reject(decode(api.source_architecture, "source_architecture") == source["architecture"], "source architecture metadata mismatch")
        reject(decode(api.source_input_sha256, "source_input_sha256") == source["input_sha256"], "source hash metadata mismatch")
        reject(api.source_address_bits == source["address_bits"], "source address width metadata mismatch")
        reject(api.source_endianness == expected_endian, "source endianness metadata mismatch")

        required_caps = (
            OPENRECOMP_NATIVE_AOT_CAP_STATE_INSPECTION
            | OPENRECOMP_NATIVE_AOT_CAP_MEMORY_READ
            | OPENRECOMP_NATIVE_AOT_CAP_DETERMINISTIC_FAULTS
        )
        reject((api.capability_flags & required_caps) == required_caps, "required ABI capabilities missing")
        has_host_cap = bool(api.capability_flags & OPENRECOMP_NATIVE_AOT_CAP_HOST_CALLS)
        reject(has_host_cap == bool(ir["required_host_symbols"]), "host-call capability does not match module requirements")
        print("OPENRECOMP_NATIVE_AOT_ABI_V1_METADATA=PASS")

        def dummy_host(_user_data, _symbol, _args, _argc, out_value, out_has_value):
            out_value[0] = 0
            out_has_value[0] = 0
            return 1

        callback = NativeHostCallbackV1(dummy_host)
        bad_version = NativeAOTHostV1(
            ctypes.sizeof(NativeAOTHostV1),
            0x00020000,
            None,
            callback,
        )
        reject(not api.set_host(ctypes.byref(bad_version)), "host with unsupported ABI version was accepted")

        short_host = NativeAOTHostV1(
            ctypes.sizeof(NativeAOTHostV1) - 1,
            OPENRECOMP_NATIVE_AOT_ABI_V1,
            None,
            callback,
        )
        reject(not api.set_host(ctypes.byref(short_host)), "host with short structure was accepted")

        valid_host = NativeAOTHostV1(
            ctypes.sizeof(NativeAOTHostV1),
            OPENRECOMP_NATIVE_AOT_ABI_V1,
            None,
            callback,
        )
        reject(bool(api.set_host(ctypes.byref(valid_host))), "valid V1 host binding was rejected")
        reject(bool(api.set_host(None)), "host unbind was rejected")
        print("OPENRECOMP_NATIVE_AOT_ABI_V1_HOST_NEGOTIATION=PASS")

        for legacy_symbol in (
            "openrecomp_run",
            "openrecomp_set_host_callback",
            "openrecomp_state_value",
            "openrecomp_memory_read",
        ):
            try:
                getattr(lib, legacy_symbol)
            except AttributeError:
                continue
            raise AssertionError(f"private legacy symbol is externally visible: {legacy_symbol}")
        print("OPENRECOMP_NATIVE_AOT_ABI_V1_PRIVATE_SURFACE=PASS")

        native = NativeAOTModule(so_path, require_abi_v1=True)
        reject(native.using_abi_v1, "NativeAOTModule did not select ABI V1")
        metadata = native.abi_metadata
        reject(metadata["module_id"] == module.manifest["module_id"], "loader module metadata mismatch")
        reject(metadata["source_architecture"] == source["architecture"], "loader architecture metadata mismatch")
        print("OPENRECOMP_NATIVE_AOT_ABI_V1_LOADER=PASS")

        print(f"NATIVE_AOT_ABI_MODULE_ID={module.manifest['module_id']}")
        print("OPENRECOMP_NATIVE_AOT_ABI_V1=PASS")
        return 0
    except (OSError, ValueError, AssertionError) as exc:
        print(f"OPENRECOMP_NATIVE_AOT_ABI_V1=FAIL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
