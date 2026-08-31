"""Public Python reference API for OpenRecomp Core API V1."""

from .executor import ExecutionResult, ReferenceExecutor
from .module import ExecutionLimits, MemorySegment, ModuleError, ModuleImage
from .runtime import (
    CallbackHostBinding,
    CoreRuntimeError,
    GuestMemory,
    GuestState,
    HostBinding,
)

__all__ = [
    "CallbackHostBinding",
    "CoreRuntimeError",
    "ExecutionLimits",
    "ExecutionResult",
    "GuestMemory",
    "GuestState",
    "HostBinding",
    "MemorySegment",
    "ModuleError",
    "ModuleImage",
    "ReferenceExecutor",
]

__version__ = "1.0.0"
