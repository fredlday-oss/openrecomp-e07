# OpenRecomp Unreal Engine 5.8 interoperability proof

This integration demonstrates deterministic translated state driving a visible Unreal Engine host object while keeping runtime validation separate from presentation.

## Deterministic workload

Input sequence:

```text
{1,1,3,0,2,3,1,0}
```

Expected final state:

```text
x=15
y=6
frame=8
rgba=ff3aa7ff
```

## Authoritative runtime validation

```text
OPENRECOMP_GATE_B PASS x=15 y=6 rgba=ff3aa7ff frame=8
```

Status: **PROVEN-RUNTIME**

## Visual replay

```text
OPENRECOMP_DEMO PASS x=15 y=6 rgba=ff3aa7ff frame=8
```

Status: **PASS / presentation evidence**

The visual replay uses the same deterministic transition logic for presentation and does not replace the authoritative Gate B validation.

The public repository intentionally excludes Unreal `Saved/`, `Intermediate/`, `Binaries/`, launcher logs, authentication metadata and machine-local build output.
