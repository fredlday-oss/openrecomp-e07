# OpenRecomp Commercial Evaluation Pilot

## A bounded technical evaluation of legacy software for modern native recompilation

OpenRecomp is an open-source, architecture-neutral static recompilation framework designed to analyse legacy executable software and investigate its translation into modern native implementations, supported by deterministic and reproducible technical evidence.

The **OpenRecomp Commercial Evaluation Pilot** is for rights holders, publishers, developers, preservation organisations and porting specialists that control legacy software and want to investigate whether an existing executable can be progressed toward a modern native implementation.

The pilot is an engineering evaluation. It does **not** promise a completed port, full compatibility or playability.

## What the pilot answers

A pilot is designed to answer practical questions such as:

- Can OpenRecomp ingest and analyse the supplied executable?
- How much of its instruction and control-flow behaviour can be recovered?
- What runtime, platform, graphics, audio, input or service dependencies remain?
- How far can the software currently progress through static translation and native code generation?
- What specific blockers prevent further progress?
- What engineering work would be required to move toward native execution or a modern port?

Unsupported or unresolved behaviour is reported explicitly rather than hidden.

## Potential evaluation work

Depending on the target and agreed scope, an evaluation may include:

- executable and architecture ingestion
- code/data mapping and binary analysis
- instruction decoding
- control-flow and indirect-target recovery
- static translation/recompilation
- runtime and platform dependency analysis
- native code-generation feasibility
- deterministic execution testing
- reproducibility verification
- compatibility-frontier and blocker classification

Source code is not necessarily required for an initial feasibility assessment.

## Deliverables

A commercial pilot can produce a defined set of deliverables such as:

### Feasibility report

A concise technical assessment describing how far the supplied software progressed through OpenRecomp and what has been demonstrated.

### Compatibility frontier

A documented classification of unresolved instructions, control flow, runtime behaviour, services or platform dependencies preventing further progress.

### Reproducible evidence

Where applicable, this can include test results, integrity hashes, deterministic execution records, translation statistics, failure classifications and reproducibility results.

### Modernisation assessment

An engineering assessment describing the work likely to be required to progress from the pilot result toward native execution or a more complete modern implementation.

### Bounded demonstrator

Where technically achievable within the agreed scope, the pilot may also produce a bounded native recompilation demonstration. A working demonstrator is an outcome of successful technical progress and is not guaranteed unless separately agreed.

## Evidence-first results

OpenRecomp is built around explicit evidence rather than assumed compatibility. Findings may therefore be classified as **PROVEN**, **BOUNDED**, **CANDIDATE** or **NOT PROVEN**, with the relevant limits stated alongside the result.

A useful pilot does not require the target software to become playable. Precisely identifying why a legacy executable cannot yet progress further can itself be a valuable engineering result.

## Intellectual property and confidentiality

The customer must own the supplied software or have appropriate authority to provide it for analysis.

The customer retains ownership of its software, trademarks, assets and other intellectual property. Providing software for evaluation does not transfer ownership to OpenRecomp.

OpenRecomp does not require proprietary executables, game data, assets or other copyrighted customer material to be published as part of the public project.

Commercial evaluations may be conducted privately. Publication of customer-specific results, evidence or technical details would be subject to the terms agreed for the engagement.

OpenRecomp's pre-existing open-source framework remains governed by its existing open-source licence. Customer proprietary software does not become open source merely because OpenRecomp is used to analyse it.

## Who the pilot is for

The pilot may be useful for organisations that:

- own or control legacy software
- have executable releases but incomplete or unavailable source/build environments
- maintain back catalogues across obsolete architectures
- perform retro-game ports, remasters or preservation work
- are investigating migration from discontinued hardware
- want an evidence-based assessment before committing to a larger porting project

## How an engagement starts

The first step is a short qualification discussion. No proprietary binary needs to be supplied at this stage.

We establish:

1. the software and original platform to be evaluated;
2. the organisation's authority to provide it;
3. the executable format and CPU architecture, where known;
4. what source code, symbols or technical documentation survive;
5. the desired modern target and intended outcome;
6. confidentiality or third-party licensing constraints; and
7. an appropriate bounded scope, deliverables and schedule.

If the target is suitable, a specific commercial evaluation can then be scoped and quoted before proprietary material is transferred.

## Current OpenRecomp work

OpenRecomp development includes executable ingestion, binary analysis, multiple legacy architectures, control-flow recovery, intermediate representations, native ahead-of-time code generation, deterministic runtime infrastructure, automated validation and reproducible evidence generation.

Current research includes PlayStation-era (PS1) compatibility and static recompilation testing using legally obtained software. No Sony or PlayStation affiliation or endorsement is implied.

## Discuss a pilot

If your organisation controls a legacy executable that no longer has a practical modern build path, OpenRecomp may be able to provide a bounded technical evaluation of its recompilation feasibility.

**Fred Day**  
Independent Developer - OpenRecomp

- GitHub: https://github.com/fredlday-oss/openrecomp-e07
- X: https://x.com/openrecomp

The initial discussion is intended to determine technical suitability and scope before either party commits to a paid engagement.
