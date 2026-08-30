from dataclasses import dataclass
from typing import Protocol, Iterable

@dataclass(frozen=True)
class ArchitectureInfo:
    architecture_id: str
    bits: int
    endianness: str
    registers: tuple[str, ...]
    calling_convention: str

class ArchitectureAdapter(Protocol):
    info: ArchitectureInfo
    def decode(self, address: int, word: int) -> dict: ...
    def branch_targets(self, insn: dict) -> Iterable[int]: ...
