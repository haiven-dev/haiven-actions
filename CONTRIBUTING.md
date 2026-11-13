# Contributing to Haiven Actions

Thank you for improving Haiven's public, reusable GitHub Actions. Contributions
must remain safe for public consumption and must not disclose private
repositories, internal identifiers, credentials, or other non-public details.

## Before opening a pull request

1. Create a branch named `<type>/<short-kebab-case-description>`, such as
   `fix/validate-target-branch`.
2. Use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/)
   for commit messages and pull-request titles, as described in
   [Commits](#commits).
3. Add or update focused tests for behavior changes. Run the checks documented
   in `docs/<action-name>.md` for the action you changed.
4. Update `docs/<action-name>.md` for changes to the action's inputs, outputs,
   caller permissions, policy assumptions, or examples.
5. Use the commit type that describes the caller-visible effect so release
   automation can place the change in the correct changelog section.

## Commits

Commit messages and pull-request titles take this form:

```
<type>(<optional scope>)<optional !>: <description>
```

- The type is one of `feat`, `fix`, `docs`, `deps`, `style`, `refactor`,
  `perf`, `test`, `build`, `ci`, `chore`, `revert`, or `wip`.
- A breaking change puts `!` immediately before the colon, in the commit
  **and** the pull-request title:
  `feat(promotion-pr)!: rename the token input`. A breaking change is a major
  version bump (a minor bump while the version is `0.x`). Callers pin these
  actions, so mark every change that can break a caller.
- The subject line is 10 to 150 characters.
- Write the description in the imperative, starting lowercase. Proper nouns
  and acronyms keep their case: `fix: validate the GitHub API response`.

## Pull requests

**One concern per pull request.** Do not bundle features, fixes, and refactors
unless they are tightly coupled; a refactor riding along with a fix hides the
fix.

Every pull request should explain what changed, why it changed, how it was
verified, and any security or compatibility implications. A human reviewer must
approve it before merge; an agent's review does not count as that approval. The
pull-request author performs the merge after all required checks and reviews
pass.

## Merge policy

This repository uses **merge commits** for pull requests. Do not squash-merge or
rebase-merge. Each commit in the pull request must therefore follow the commit
format above and form a coherent part of the change.

Update a topic branch by rebasing it onto `main`; do not merge `main` into the
topic branch. If a published branch must be rebased, update it with
`git push --force-with-lease`, never an unguarded force push.

## Action design and security

- Keep each action's implementation and tests under `actions/<action-name>/`,
  and its caller documentation in `docs/<action-name>.md`, linked from the root
  `README.md`.
- Give workflows and actions only the GitHub token permissions they require.
  Document those permissions for callers.
- Pin third-party actions to reviewed full commit SHAs. Avoid mutable tags in
  tests and examples.
- Treat action inputs and GitHub event data as untrusted. Do not interpolate
  them into shell source; pass them through environment variables or arguments
  and quote them appropriately.
- Keep developer-facing automation portable across Linux, macOS, and Windows,
  unless the action explicitly documents a narrower platform contract.

Report suspected vulnerabilities privately as described in
[SECURITY.md](SECURITY.md).

## Releases

Releases follow [Semantic Versioning 2.0.0](https://semver.org/). Each released
version must have a `v<version>` Git tag, a GitHub release, and a corresponding
entry in [CHANGELOG.md](CHANGELOG.md). Release automation writes the changelog
from commit types; do not edit it by hand. Release automation is not configured
yet; do not cut a version until a reviewed pull request adds it. Callers should
reference a reviewed full commit SHA rather than a mutable version tag.
