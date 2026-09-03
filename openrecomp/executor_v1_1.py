from __future__ import annotations

from typing import Any

from .divrem_v1 import DIVREM_KINDS, divrem_result
from .executor import ReferenceExecutor
from .runtime import TYPE_BITS


class ReferenceExecutorV11(ReferenceExecutor):
    """IR V1.1 reference executor; V1.0 behavior is inherited unchanged."""

    def _execute_instruction(
        self,
        insn: dict[str, Any],
        values: dict[str, tuple[int, str]],
        depth: int,
    ) -> None:
        if insn.get("op") != "binop" or insn.get("kind") not in DIVREM_KINDS:
            return super()._execute_instruction(insn, values, depth)

        self._step()
        lhs, _ = self._value(insn["lhs"], values)
        rhs, _ = self._value(insn["rhs"], values)
        bits = TYPE_BITS[insn["result_type"]]
        result = divrem_result(insn["kind"], lhs, rhs, bits)
        values[insn["result"]] = (result, insn["result_type"])
