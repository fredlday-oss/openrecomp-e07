# Funding and milestone scope

OpenRecomp is one codebase with multiple evidence tracks. Funding applications and milestone plans should distinguish the reusable open core from optional host integrations so completed work is not presented as future work and a host-specific demonstration does not become a dependency of the architecture-neutral project.

## Open-core milestone track

The open-core track contains the reusable infrastructure that is intended to stand independently of any proprietary engine or commercial game:

- clean RV32I reference/validation path;
- normalized versioned IR and Module Image contracts;
- Core API reference runtime and deterministic validation;
- bounded second-guest MIPS32 frontend work, including the completed multi-fixture Expansion V1 evidence, with broader ISA/ABI generalization remaining future work;
- common portable AOT translation and compiler hardening;
- reproducibility, adversarial testing, CI, documentation and clean redistributable examples.

This is the appropriate primary scope for open-infrastructure funding. It can be evaluated and developed without Unreal Engine.

## Host-integration and portability track

The Native AOT ABI, Linux/Windows portability work and Unreal Engine integration demonstrate that the open core can be consumed by materially different hosts and toolchains. They are useful interoperability evidence, but they are not prerequisites for the IR/Core/MIPS32 milestones and should be presented as a separate integration track when a funding program is focused on open infrastructure.

Unreal Engine is therefore a consumer of OpenRecomp through the versioned Native AOT ABI, not part of the required core architecture.

## Existing work versus proposed work

Applications should identify which milestones are already implemented and which work remains. A completed proof can support feasibility, but it should not be budgeted again as an uncompleted deliverable.

For MIPS32 specifically, applications written after Expansion V1 should not describe “add several logic/memory/branch/multiply fixtures” as wholly future work. The completed expansion is feasibility evidence; proposed second-guest work should instead identify the additional ISA/ABI/generalization gaps that remain CANDIDATE.

If separate funders support different tracks, the scopes should remain non-overlapping and explicit. For example, core architecture/generalization work and host-specific interoperability work can be described separately rather than implying that the same deliverable is funded twice.

## Roadmap interpretation

`docs/ROADMAP.md` describes intended next-phase work, not a historical schedule. Some host-integration and second-guest expansion work was completed earlier than its originally anticipated roadmap phase. The remaining roadmap should therefore be read as hardening, generalization, reproducibility and packaging work around the current evidence baseline rather than as a claim that every listed feature is still unimplemented.
