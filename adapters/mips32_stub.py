from .interface import ArchitectureInfo
info=ArchitectureInfo(
    "mips32-stub",32,"little",
    tuple([f"r{i}" for i in range(32)]),
    "CANDIDATE ONLY: o32-style boundary placeholder; no instruction semantics implemented"
)
def decode(address, word):
    raise NotImplementedError("CANDIDATE adapter: interface seam only in E07 V1")
def branch_targets(insn): return []
