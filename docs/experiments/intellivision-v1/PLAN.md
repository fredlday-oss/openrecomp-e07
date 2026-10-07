# OpenRecomp Intellivision / CP1610 Feasibility V1

## Status

**CANDIDATE / experiment**

This experiment evaluates whether the Intellivision CP1610 architecture and minimum platform services can be represented through OpenRecomp's existing architecture-neutral IR, portable AOT path, deterministic evidence model and explicit host/runtime boundary.

It does **not** claim general Intellivision compatibility, commercial-title playability, complete STIC emulation, EXEC/GROM redistribution, or support for arbitrary cartridges.

## Primary objective

Establish an evidence-backed vertical slice:

```text
CP1610 machine-code fixture
    ↓
fail-closed CP1610 frontend
    ↓
Normalized OpenRecomp IR V1
    ↓
reference execution + portable AOT
    ↓
deterministic architectural comparison
```

Only after CPU semantic parity is established should the experiment advance into cartridge mapping and Intellivision platform/runtime work.

## Rights boundary

No copyrighted Mattel/Intellivision ROM, EXEC ROM, GROM image, commercial cartridge image, proprietary manual dump or other non-redistributable binary may be committed.

Public fixtures must be original synthetic programs, permissively licensed homebrew material, or other inputs with clearly documented redistribution rights.

User-supplied firmware or cartridge material, if later used for local validation, remains outside the public repository and is represented in evidence only by permitted metadata/hashes.

## V1 milestones

### I16-00 — Experiment boundary

- Create experiment documentation and directory layout.
- Record legal/rights firewall.
- Define evidence vocabulary and fail-closed policy.
- No compatibility claim.

**Exit:** documentation review PASS.

### I16-01 — CP1610 architectural inventory

Document the minimum architectural contract required by the frontend:

- registers and program counter;
- status/flag behaviour;
- instruction word encoding;
- addressing forms;
- arithmetic/logic semantics;
- branches and calls/returns;
- memory access width and masking;
- cycle/timing information where it affects externally observable behaviour;
- unsupported/reserved encodings.

**Exit:** inventory complete enough to build test vectors without relying on a game image.

### I16-02 — Decoder skeleton

Add a CP1610 decoder that:

- accepts bounded machine-word fixtures;
- produces explicit decoded operations;
- rejects malformed, truncated and unsupported input fail-closed;
- never silently maps unknown opcodes to NOP.

**Exit:** positive and negative decode tests PASS.

### I16-03 — Semantic micro-fixtures

Create original synthetic CP1610 fixtures covering at minimum:

- register transfer;
- arithmetic;
- logic;
- compare/status effects;
- load/store;
- conditional branch;
- unconditional control flow;
- call/return behaviour;
- edge values and wraparound.

Reference expected register/memory outcomes explicitly.

**Exit:** deterministic semantic fixture suite PASS.

### I16-04 — OpenRecomp IR bridge

Lower the supported CP1610 subset into Normalized OpenRecomp IR V1.

Requirements:

- unsupported semantics remain explicit;
- control-flow targets are validated;
- no architecture-specific behaviour leaks silently through generic IR operations;
- any required new IR capability is separately justified rather than hidden in the frontend.

**Exit:** CP1610 fixture results agree across direct/reference and IR paths.

### I16-05 — Portable AOT parity

Run the same bounded fixtures through the portable AOT backend.

Compare:

- terminal registers;
- memory writes;
- return/stop condition;
- operation count where meaningful;
- deterministic evidence hashes.

**Exit:** reference == IR == AOT for the documented subset on the validated host(s).

### I16-06 — Cartridge ingestion boundary

Introduce a separate Intellivision cartridge/container layer.

Initial scope:

- deterministic raw fixture ingestion;
- explicit mapping metadata;
- bounds validation;
- no assumption that every Intellivision cartridge uses one universal mapping;
- unsupported mapping modes fail closed.

Commercial cartridge support remains NOT PROVEN.

**Exit:** synthetic cartridge mapping fixtures PASS.

### I16-07 — Minimum platform memory map

Model only the platform regions necessary for the first platform fixture.

Keep CPU translation separate from platform services.

Potential regions include:

- system RAM;
- scratchpad RAM;
- STIC register window;
- GRAM/GROM-facing boundary;
- EXEC-facing boundary;
- cartridge address ranges.

Firmware-dependent behaviour must remain an explicit dependency.

**Exit:** deterministic read/write trace for an original platform fixture.

### I16-08 — STIC observation model

Before native rendering, define a deterministic observable STIC state sufficient to compare:

- register writes;
- BACKTAB-visible state;
- MOB state;
- colour/priority attributes;
- collision state where implemented;
- frame boundary events.

This is an evidence layer, not yet a claim of pixel-perfect rendering.

**Exit:** deterministic STIC trace fixtures PASS.

### I16-09 — SDL3 host slice

Use the shared SDL3 host-runtime direction for:

- video presentation;
- keyboard/controller mapping;
- eventual audio output.

The SDL3 layer must consume explicit guest/platform state and must not contain reimplemented game logic.

**Exit:** original visual fixture renders through the host boundary.

### I16-10 — First redistributable software target

Select a homebrew/public-domain/permissively redistributable Intellivision program with clear rights.

Run it as a separate benchmark from the synthetic architecture suite.

**Exit classifications:**

- PASS_BOUNDED if the declared target behaviour is reproduced;
- FRONTIER_FOUND if unsupported CPU/platform semantics are reached;
- BLOCKED_RIGHTS if redistribution/validation rights cannot be established;
- FAIL if a supported semantic produces an incorrect result.

## Evidence requirements

Every promoted milestone should record:

- source HEAD;
- fixture SHA-256 values;
- exact invocation;
- deterministic result;
- supported/unsupported instruction coverage;
- first unresolved frontier when applicable;
- whether execution used reference, IR and/or AOT paths;
- host/compiler versions when native compilation is involved.

A milestone PASS proves only its stated contract.

## Initial non-goals

V1 does not require:

- arbitrary commercial game compatibility;
- Intellivoice;
- ECS;
- JLP;
- pixel-perfect STIC timing;
- cycle-perfect emulation;
- complete EXEC replacement;
- redistribution of proprietary firmware;
- automatic decompilation of every cartridge format.

## Promotion target

The experiment may be described as **CP1610 bounded support** only after I16-05 passes with published deterministic fixtures.

It may be described as **bounded Intellivision platform support** only after platform-level execution is independently evidenced beyond CPU-only fixtures.

Until then, public wording remains **Intellivision / CP1610 feasibility research**.
