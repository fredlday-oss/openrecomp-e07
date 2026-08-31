from __future__ import annotations

import ctypes
from pathlib import Path
from typing import Callable

OPENRECOMP_NATIVE_AOT_ABI_V1 = 0x00010000
OPENRECOMP_NATIVE_AOT_ENDIAN_LITTLE = 0
OPENRECOMP_NATIVE_AOT_ENDIAN_BIG = 1

OPENRECOMP_NATIVE_AOT_CAP_STATE_INSPECTION = 0x00000001
OPENRECOMP_NATIVE_AOT_CAP_MEMORY_READ = 0x00000002
OPENRECOMP_NATIVE_AOT_CAP_HOST_CALLS = 0x00000004
OPENRECOMP_NATIVE_AOT_CAP_DETERMINISTIC_FAULTS = 0x00000008


class NativeAOTError(RuntimeError):
    pass


NativeHostCallbackV1 = ctypes.CFUNCTYPE(
    ctypes.c_int32,
    ctypes.c_void_p,
    ctypes.c_char_p,
    ctypes.POINTER(ctypes.c_uint64),
    ctypes.c_uint64,
    ctypes.POINTER(ctypes.c_uint64),
    ctypes.POINTER(ctypes.c_uint32),
)


class NativeAOTHostV1(ctypes.Structure):
    pass


NativeAOTHostV1._fields_ = [
    ("struct_size", ctypes.c_uint32),
    ("abi_version", ctypes.c_uint32),
    ("user_data", ctypes.c_void_p),
    ("call", NativeHostCallbackV1),
]

SetHostV1 = ctypes.CFUNCTYPE(ctypes.c_int32, ctypes.POINTER(NativeAOTHostV1))
RunV1 = ctypes.CFUNCTYPE(ctypes.c_int32)
U64V1 = ctypes.CFUNCTYPE(ctypes.c_uint64)
U32V1 = ctypes.CFUNCTYPE(ctypes.c_uint32)
ErrorV1 = ctypes.CFUNCTYPE(ctypes.c_char_p)
StateNameV1 = ctypes.CFUNCTYPE(ctypes.c_char_p, ctypes.c_uint64)
StateValueV1 = ctypes.CFUNCTYPE(ctypes.c_uint64, ctypes.c_uint64)
MemoryReadV1 = ctypes.CFUNCTYPE(
    ctypes.c_int32,
    ctypes.c_uint64,
    ctypes.c_uint64,
    ctypes.POINTER(ctypes.c_uint8),
)


class NativeAOTApiV1(ctypes.Structure):
    _fields_ = [
        ("struct_size", ctypes.c_uint32),
        ("abi_version", ctypes.c_uint32),
        ("capability_flags", ctypes.c_uint64),
        ("module_id", ctypes.c_char_p),
        ("module_format_version", ctypes.c_char_p),
        ("ir_version", ctypes.c_char_p),
        ("host_contract_version", ctypes.c_char_p),
        ("source_architecture", ctypes.c_char_p),
        ("source_input_sha256", ctypes.c_char_p),
        ("source_address_bits", ctypes.c_uint32),
        ("source_endianness", ctypes.c_uint32),
        ("set_host", SetHostV1),
        ("run", RunV1),
        ("observed_state", U64V1),
        ("function_return", U64V1),
        ("function_has_return", U32V1),
        ("operations", U64V1),
        ("error", ErrorV1),
        ("state_count", U64V1),
        ("state_name", StateNameV1),
        ("state_value", StateValueV1),
        ("memory_size", U64V1),
        ("memory_read", MemoryReadV1),
    ]


LegacyHostCallback = ctypes.CFUNCTYPE(
    ctypes.c_int,
    ctypes.c_char_p,
    ctypes.POINTER(ctypes.c_uint64),
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_uint64),
    ctypes.POINTER(ctypes.c_int),
)


class NativeAOTModule:
    def __init__(self, path: str | Path, *, require_abi_v1: bool = False):
        self.lib = ctypes.CDLL(str(Path(path).resolve()))
        self._callback = None
        self._host = None
        self._api_ptr = None
        self._api = None
        self._using_abi_v1 = False

        try:
            query = self.lib.openrecomp_native_aot_query
        except AttributeError:
            if require_abi_v1:
                raise NativeAOTError("Native AOT ABI V1 query symbol is missing")
            self._configure_legacy()
            return

        query.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
        query.restype = ctypes.POINTER(NativeAOTApiV1)
        api_ptr = query(OPENRECOMP_NATIVE_AOT_ABI_V1, ctypes.sizeof(NativeAOTApiV1))
        if not api_ptr:
            raise NativeAOTError("Native AOT ABI V1 query rejected the required version/size")
        api = api_ptr.contents
        if api.struct_size != ctypes.sizeof(NativeAOTApiV1):
            raise NativeAOTError(
                f"Native AOT ABI V1 structure size mismatch: module={api.struct_size} host={ctypes.sizeof(NativeAOTApiV1)}"
            )
        if api.abi_version != OPENRECOMP_NATIVE_AOT_ABI_V1:
            raise NativeAOTError(f"Native AOT ABI version mismatch: 0x{api.abi_version:08x}")
        for name in (
            "set_host",
            "run",
            "observed_state",
            "function_return",
            "function_has_return",
            "operations",
            "error",
            "state_count",
            "state_name",
            "state_value",
            "memory_size",
            "memory_read",
        ):
            if not getattr(api, name):
                raise NativeAOTError(f"Native AOT ABI V1 missing function pointer: {name}")
        for name in (
            "module_id",
            "module_format_version",
            "ir_version",
            "host_contract_version",
            "source_architecture",
            "source_input_sha256",
        ):
            if not getattr(api, name):
                raise NativeAOTError(f"Native AOT ABI V1 missing metadata: {name}")

        self._api_ptr = api_ptr
        self._api = api
        self._using_abi_v1 = True

    def _configure_legacy(self) -> None:
        self.lib.openrecomp_set_host_callback.argtypes = [LegacyHostCallback]
        self.lib.openrecomp_set_host_callback.restype = None
        self.lib.openrecomp_run.argtypes = []
        self.lib.openrecomp_run.restype = ctypes.c_int
        self.lib.openrecomp_observed_state.argtypes = []
        self.lib.openrecomp_observed_state.restype = ctypes.c_uint64
        self.lib.openrecomp_function_return.argtypes = []
        self.lib.openrecomp_function_return.restype = ctypes.c_uint64
        self.lib.openrecomp_function_has_return.argtypes = []
        self.lib.openrecomp_function_has_return.restype = ctypes.c_int
        self.lib.openrecomp_operations.argtypes = []
        self.lib.openrecomp_operations.restype = ctypes.c_uint64
        self.lib.openrecomp_error.argtypes = []
        self.lib.openrecomp_error.restype = ctypes.c_char_p
        self.lib.openrecomp_state_count.argtypes = []
        self.lib.openrecomp_state_count.restype = ctypes.c_size_t
        self.lib.openrecomp_state_name.argtypes = [ctypes.c_size_t]
        self.lib.openrecomp_state_name.restype = ctypes.c_char_p
        self.lib.openrecomp_state_value.argtypes = [ctypes.c_size_t]
        self.lib.openrecomp_state_value.restype = ctypes.c_uint64
        self.lib.openrecomp_memory_size.argtypes = []
        self.lib.openrecomp_memory_size.restype = ctypes.c_size_t
        self.lib.openrecomp_memory_read.argtypes = [
            ctypes.c_uint64,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_uint8),
        ]
        self.lib.openrecomp_memory_read.restype = ctypes.c_int

    @staticmethod
    def _decode(raw: bytes | None, name: str) -> str:
        if raw is None:
            raise NativeAOTError(f"Native AOT ABI V1 returned null metadata: {name}")
        return raw.decode("ascii")

    @property
    def using_abi_v1(self) -> bool:
        return self._using_abi_v1

    @property
    def abi_metadata(self) -> dict[str, int | str]:
        if not self._using_abi_v1 or self._api is None:
            raise NativeAOTError("module does not expose Native AOT ABI V1 metadata")
        api = self._api
        endianness = {
            OPENRECOMP_NATIVE_AOT_ENDIAN_LITTLE: "little",
            OPENRECOMP_NATIVE_AOT_ENDIAN_BIG: "big",
        }.get(int(api.source_endianness), f"unknown:{int(api.source_endianness)}")
        return {
            "abi_version": int(api.abi_version),
            "struct_size": int(api.struct_size),
            "capability_flags": int(api.capability_flags),
            "module_id": self._decode(api.module_id, "module_id"),
            "module_format_version": self._decode(api.module_format_version, "module_format_version"),
            "ir_version": self._decode(api.ir_version, "ir_version"),
            "host_contract_version": self._decode(api.host_contract_version, "host_contract_version"),
            "source_architecture": self._decode(api.source_architecture, "source_architecture"),
            "source_input_sha256": self._decode(api.source_input_sha256, "source_input_sha256"),
            "source_address_bits": int(api.source_address_bits),
            "source_endianness": endianness,
        }

    def set_host_callback(
        self,
        callback: Callable[[str, list[int]], tuple[bool, int | None]],
    ) -> None:
        if self._using_abi_v1:
            assert self._api is not None

            def thunk(_user_data, symbol_ptr, args_ptr, argc, out_ptr, has_ptr):
                try:
                    if not symbol_ptr:
                        return 0
                    symbol = symbol_ptr.decode("ascii")
                    args = [int(args_ptr[i]) for i in range(int(argc))]
                    ok, value = callback(symbol, args)
                    if not ok:
                        return 0
                    if value is None:
                        has_ptr[0] = 0
                        out_ptr[0] = 0
                    else:
                        has_ptr[0] = 1
                        out_ptr[0] = value & 0xFFFFFFFFFFFFFFFF
                    return 1
                except Exception:
                    return 0

            self._callback = NativeHostCallbackV1(thunk)
            self._host = NativeAOTHostV1(
                ctypes.sizeof(NativeAOTHostV1),
                OPENRECOMP_NATIVE_AOT_ABI_V1,
                None,
                self._callback,
            )
            if not self._api.set_host(ctypes.byref(self._host)):
                raise NativeAOTError("Native AOT ABI V1 rejected host binding")
            return

        def legacy_thunk(symbol_ptr, args_ptr, argc, out_ptr, has_ptr):
            try:
                symbol = symbol_ptr.decode("ascii")
                args = [int(args_ptr[i]) for i in range(argc)]
                ok, value = callback(symbol, args)
                if not ok:
                    return 0
                if value is None:
                    has_ptr[0] = 0
                    out_ptr[0] = 0
                else:
                    has_ptr[0] = 1
                    out_ptr[0] = value & 0xFFFFFFFFFFFFFFFF
                return 1
            except Exception:
                return 0

        self._callback = LegacyHostCallback(legacy_thunk)
        self.lib.openrecomp_set_host_callback(self._callback)

    def clear_host_callback(self) -> None:
        if self._using_abi_v1:
            assert self._api is not None
            if not self._api.set_host(None):
                raise NativeAOTError("Native AOT ABI V1 rejected host unbind")
        else:
            self.lib.openrecomp_set_host_callback(LegacyHostCallback())
        self._callback = None
        self._host = None

    def run(self) -> None:
        ok = self._api.run() if self._using_abi_v1 and self._api is not None else self.lib.openrecomp_run()
        if not ok:
            raw = self._api.error() if self._using_abi_v1 and self._api is not None else self.lib.openrecomp_error()
            message = raw.decode("utf-8", errors="replace") if raw else "unknown AOT failure"
            raise NativeAOTError(message)

    @property
    def observed_state(self) -> int:
        if self._using_abi_v1 and self._api is not None:
            return int(self._api.observed_state())
        return int(self.lib.openrecomp_observed_state())

    @property
    def function_return(self) -> int | None:
        has_return = (
            self._api.function_has_return()
            if self._using_abi_v1 and self._api is not None
            else self.lib.openrecomp_function_has_return()
        )
        if not has_return:
            return None
        if self._using_abi_v1 and self._api is not None:
            return int(self._api.function_return())
        return int(self.lib.openrecomp_function_return())

    @property
    def operations(self) -> int:
        if self._using_abi_v1 and self._api is not None:
            return int(self._api.operations())
        return int(self.lib.openrecomp_operations())

    def state_snapshot(self) -> dict[str, int]:
        result: dict[str, int] = {}
        count = (
            int(self._api.state_count())
            if self._using_abi_v1 and self._api is not None
            else int(self.lib.openrecomp_state_count())
        )
        for i in range(count):
            raw = (
                self._api.state_name(i)
                if self._using_abi_v1 and self._api is not None
                else self.lib.openrecomp_state_name(i)
            )
            if raw is None:
                raise NativeAOTError(f"state name missing at index {i}")
            value = (
                self._api.state_value(i)
                if self._using_abi_v1 and self._api is not None
                else self.lib.openrecomp_state_value(i)
            )
            result[raw.decode("ascii")] = int(value)
        return dict(sorted(result.items()))

    def memory(self, address: int, size: int) -> bytes:
        if size < 0:
            raise NativeAOTError("negative memory read")
        buffer = (ctypes.c_uint8 * max(1, size))()
        ok = (
            self._api.memory_read(address, size, buffer)
            if self._using_abi_v1 and self._api is not None
            else self.lib.openrecomp_memory_read(address, size, buffer)
        )
        if not ok:
            raise NativeAOTError(f"memory read failed at 0x{address:x} size={size}")
        return bytes(buffer[:size])
