from __future__ import annotations

import ctypes
from pathlib import Path
from typing import Callable


HostCallback = ctypes.CFUNCTYPE(
    ctypes.c_int,
    ctypes.c_char_p,
    ctypes.POINTER(ctypes.c_uint64),
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_uint64),
    ctypes.POINTER(ctypes.c_int),
)


class NativeAOTError(RuntimeError):
    pass


class NativeAOTModule:
    def __init__(self, path: str | Path):
        self.lib = ctypes.CDLL(str(Path(path).resolve()))
        self._callback = None

        self.lib.openrecomp_set_host_callback.argtypes = [HostCallback]
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

    def set_host_callback(
        self,
        callback: Callable[[str, list[int]], tuple[bool, int | None]],
    ) -> None:
        def thunk(symbol_ptr, args_ptr, argc, out_ptr, has_ptr):
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

        self._callback = HostCallback(thunk)
        self.lib.openrecomp_set_host_callback(self._callback)

    def run(self) -> None:
        if not self.lib.openrecomp_run():
            raw = self.lib.openrecomp_error()
            message = raw.decode("utf-8", errors="replace") if raw else "unknown AOT failure"
            raise NativeAOTError(message)

    @property
    def observed_state(self) -> int:
        return int(self.lib.openrecomp_observed_state())

    @property
    def function_return(self) -> int | None:
        if not self.lib.openrecomp_function_has_return():
            return None
        return int(self.lib.openrecomp_function_return())

    @property
    def operations(self) -> int:
        return int(self.lib.openrecomp_operations())

    def state_snapshot(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for i in range(self.lib.openrecomp_state_count()):
            raw = self.lib.openrecomp_state_name(i)
            if raw is None:
                raise NativeAOTError(f"state name missing at index {i}")
            result[raw.decode("ascii")] = int(self.lib.openrecomp_state_value(i))
        return dict(sorted(result.items()))

    def memory(self, address: int, size: int) -> bytes:
        if size < 0:
            raise NativeAOTError("negative memory read")
        buffer = (ctypes.c_uint8 * max(1, size))()
        if not self.lib.openrecomp_memory_read(address, size, buffer):
            raise NativeAOTError(f"memory read failed at 0x{address:x} size={size}")
        return bytes(buffer[:size])
