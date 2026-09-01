# OpenRecomp v0.2.0 release checklist

This checklist defines the publication gate for `v0.2.0`. A checked item must be backed by repository state, CI, or an explicitly identified local evidence source.

## Repository freeze

- [ ] `VERSION` is exactly `0.2.0`.
- [ ] `CHANGELOG.md` contains a dated `0.2.0` section and a new empty `Unreleased` section.
- [ ] `docs/RELEASE_V0_2_0.md` matches the current proof taxonomy.
- [ ] No proof-critical schema, guest frontend, Core API, AOT semantics, Native AOT ABI V1 layout, E07 golden output or Unreal proof source changes are hidden inside the release-only PR.
- [ ] Public-safety and documentation-link gates pass.

## Fresh-clone evidence

- [ ] `./RUN.sh` ends with `PASS: E07 V1.1 HARDENED END-TO-END`.
- [ ] IR V1 specification workflow passes.
- [ ] Core API V1 workflow passes.
- [ ] MIPS32 vertical slice V1 workflow passes.
- [ ] IR V1 portable C AOT workflow passes.
- [ ] AOT hardening V1 workflow passes.
- [ ] AOT Windows portability V1 workflow passes.
- [ ] Unreal Native AOT host-core workflow passes.
- [ ] Public safety workflow passes, including its missing-tracked-file regression.
- [ ] Documentation links workflow passes.
- [ ] Release metadata workflow passes.

## Claim audit

- [ ] RV32I E07 remains bounded to the clean synthetic proof fixture.
- [ ] MIPS32 remains a bounded vertical-slice PASS, not general MIPS32 support.
- [ ] Native AOT ABI V1 remains `FROZEN-FOR-PORTABILITY-TESTING`.
- [ ] UE5.8 PIE results remain labelled `PASS — local runtime evidence` unless a reproducible UE CI environment is added.
- [ ] Unreal is described as an optional host consumer, not an open-core dependency.
- [ ] Development-process disclosure remains present.
- [ ] Rights firewall and clean-input policy remain present.

## Publication

After the release PR is merged and the exact merge commit is confirmed:

- [ ] Create annotated tag `v0.2.0` at the exact release merge commit.
- [ ] Push the tag without moving it afterward.
- [ ] Create the GitHub Release from tag `v0.2.0` using `docs/RELEASE_V0_2_0.md` as the release-note basis.
- [ ] Confirm the GitHub-generated source archive resolves to the tagged tree.
- [ ] Re-run or inspect tag-triggered/release-adjacent validation if available.
- [ ] Record the final tag commit SHA in the release discussion/notes if useful for reviewers.

The tag must never be moved to make later changes appear part of v0.2.0. Post-release fixes belong in a later version.
