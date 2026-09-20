# OpenRecomp Phase 8 Acceleration Policy

This policy is mandatory from P8-00.

## 1. One serial implementation frontier

There is exactly one mutating implementation frontier. No other agent,
background agent, or parallel implementation modifies the same tree.

Parallel work is allowed only while read-only/non-mutating: reference-vector
generation, test-case design, evidence review, documentation drafting, manifest
preparation, and static analysis of frozen artifacts.

## 2. Fast gate versus terminal gate

- A **fast gate** is a stage's official gate and its direct dependency gates.
  Target runtime: seconds to a few minutes. It verifies the stage contract,
  source integrity, provenance, and the specific regression made necessary by
  changed code.
- A **terminal gate** is the expensive whole-project audit: P8-90 (frozen
  Phase-1..Phase-7 regression plus all Phase-8 official gates), P8-91 and
  P8-99. It may be slow and is not optimized at the expense of audit strength.
- Long differential/reference campaigns belong to stage closure where actually
  needed, P8-90, P8-91, and P8-99. A 15-minute regression is never part of the
  normal edit/test loop.

## 3. Immutable-hash analysis cache

Deterministic analysis products may be cached where safe. A cache entry is
accepted only if its key matches exactly; a matching filename is never
sufficient.

Cache key:

```
cache_key = sha256(utf8(canonical_json({
  "schema": "openrecomp-phase8-analysis-cache-v1",
  "product": "<product name, e.g. elf-inventory>",
  "input_sha256": "<fixture ELF SHA-256>",
  "input_size_bytes": <int>,
  "analysis_config": <canonical configuration object for the product>,
  "frontend_sha256": {"<relative module path>": "<SHA-256>", ...},
  "semantic_model": {"<version string key>": "<version>", ...},
  "producer_sha256": "<SHA-256 of the producing module/gate>"
})))
```

Rules:

1. Every product records its key and the exact key inputs in the cache entry
   (`key_inputs`), so a verifier can recompute the key independently.
2. A cache hit is verified against its recomputed key; a stale entry is
   rejected and recomputed, never silently reused.
3. Cache entries live under `.openrecomp-phase8/cache/` (untracked). Committed
   evidence records product hashes and cache keys, not the cache payloads.
4. Official stage evidence is regenerated from the analysis itself at least
   once; a stage may not claim PASS from cached products alone.
5. Candidate products: ELF inventory, decoded instruction map, reachable
   frontier, ProgramModel, CFG, function recovery, translation-unit inventory,
   immutable memory-image analysis.

## 4. Incremental native build

1. Generated source files have stable names and recorded content hashes.
2. Development loops may reuse object files keyed by (source content hash,
   compiler identity, flags) in an untracked build directory under
   `.openrecomp-phase8/build/`. A content-hash mismatch forces a rebuild.
3. Ninja or an equivalent incremental driver may be used where compatible with
   the existing build path. `sccache` or an equivalent compiler cache may be
   used only if it does not weaken reproducibility evidence.
4. Official gates always demonstrate the audited path: a fresh, isolated,
   deterministic build through the existing `openrecomp.build_pipeline`
   boundary (or an equivalent recorded clean build), independent of any
   incremental cache.
5. Unchanged generated source is not regenerated unnecessarily, but a
   regeneration must always reproduce byte-identical output.
