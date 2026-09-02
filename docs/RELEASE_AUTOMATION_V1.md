# OpenRecomp Release Automation V1

`OPENRECOMP_RELEASE_AUTOMATION_V1` replaces version-specific required-status naming with a stable release metadata contract while preserving the published v0.2.0 evidence.

## Stable required context

The permanent GitHub Actions job name is:

```text
Release metadata
```

Future release versions update release data, not the required-status context. The legacy `Release v0.2 metadata` workflow remains present during migration so branch protection is never weakened or left waiting for a deleted check.

## Release metadata contract

`release/metadata.json` binds the current public milestone to:

- `VERSION`;
- the `vX.Y.Z` tag name;
- candidate/published state;
- the published release commit when applicable;
- the matching changelog heading;
- version-derived release notes and release checklist paths;
- release-specific evidence strings that must remain present;
- unresolved placeholders that are forbidden.

`tools/verify_release_metadata.py` validates this manifest and emits:

```text
OPENRECOMP_RELEASE_VERSION=<version>
OPENRECOMP_RELEASE_STATE=<candidate|published>
OPENRECOMP_RELEASE_TAG=v<version>
OPENRECOMP_RELEASE_METADATA=PASS
```

For a `published` release, the workflow fetches full history and tags and requires the protected tag to peel to the exact `release_commit` recorded in the manifest. That commit must also be an ancestor of the reviewed source.

For a `candidate` release, `release_commit` must be `null` and the proposed tag must not already exist. This allows a future release-preparation PR to pass before its immutable tag is created.

## Future release sequence

For a future `X.Y.Z` release:

1. create a dedicated release-preparation branch;
2. update `VERSION` to `X.Y.Z`;
3. add `docs/RELEASE_VX_Y_Z.md` and `docs/RELEASE_CHECKLIST_VX_Y_Z.md`;
4. add `## [X.Y.Z] - YYYY-MM-DD` to `CHANGELOG.md` while retaining `## Unreleased` above it;
5. update `release/metadata.json` with `state: candidate`, tag `vX.Y.Z`, `release_commit: null`, and release-specific evidence text;
6. require the stable `Release metadata` check and the rest of protected CI to pass, then merge;
7. create the immutable annotated `vX.Y.Z` tag at the intended release commit and publish the GitHub Release;
8. in a protected follow-up PR, set `state: published` and record that exact release commit; the generic gate then verifies the tag-to-commit binding.

Do not move or rewrite an existing release tag. Corrections after publication use a new version.

## Safe ruleset migration from v0.2

Migration must not delete the legacy check before branch protection has switched to the stable context.

1. Merge the PR that introduces `Release metadata` while the existing `Release v0.2 metadata` context is still required.
2. In the `Protect main` ruleset, add `Release metadata` as an additional required GitHub Actions status check and keep `Release v0.2 metadata` required.
3. Exercise both contexts on a small protected PR and require both to pass.
4. Remove only `Release v0.2 metadata` from the ruleset, keeping `Release metadata` required.
5. After that ruleset change is verified live, remove the obsolete version-specific workflow in a separate protected PR. The historical v0.2 verifier may remain as release-specific archival validation if useful.

This ordering prevents a required-check deadlock and never creates a protection gap.

## Scope

Release Automation V1 changes release metadata validation and CI orchestration only. It does not alter IR V1, Module Image V1, Core API semantics, guest frontends, Native AOT ABI V1, Unreal runtime behavior, or the published `v0.2.0` tag/release contents.
