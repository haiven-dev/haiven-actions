# Keeping a promotion pull request open

`actions/promotion-pr` keeps exactly one open pull request that promotes a
long-lived source branch such as `sdk-dev` into a target branch such as `dev`
or `main`. Each run:

1. fetches both branches and lists every non-merge commit the source carries
   that the target lacks, oldest first;
2. groups those commits by conventional-commit type under **Breaking changes**
   (`type!:` or `type(scope)!:`), **Features**, **Bug fixes**, and **Other
   changes** (everything else, including non-conventional subjects);
3. opens the pull request when none is open, or refreshes the description of the
   open one, but only when the source has something to promote: a non-merge
   commit the target lacks, or merge commits that would change the target's
   files when merged (a conflict resolution, for example).

The generated list sits between `<!-- promotion-pr:begin -->` and
`<!-- promotion-pr:end -->`. Only that block is regenerated, so text reviewers
add outside it is kept. An open source-to-target pull request someone opened by
hand is adopted: the block is appended to its description and its title is left
alone. When the target already contains the source, the run does nothing. It
also does nothing after a back-merge that leaves the source ahead only by merge
commits that change no files, so a `main` into `dev` back-merge does not open an
empty `dev` into `main` pull request. The file check runs
`git merge-tree --write-tree origin/<target> origin/<source>` and compares the
tree a real merge would produce with the target's tree. Commits that land on the
target after the back-merge therefore do not count as a difference, and neither
does a history with more than one merge base, such as a hotfix branch merged
into both branches or a criss-cross back-merge. A merge that would conflict
counts as something to promote. When only file-changing merge commits remain, the
description says so and points to the Files changed tab. A list longer than
50,000 characters is truncated with a pointer to the Commits tab, keeping the
description under GitHub's limit.

The action never versions, tags, or releases anything, and never merges.

## Caller

The caller owns the push triggers, checkout, and token scopes. Run on pushes to
both branches so the list stays current when either side moves. The file check
needs git 2.38 or newer, which GitHub-hosted runners provide; with an older git
it fails the run with an error instead of guessing. Pin this public action and
its dependencies to reviewed full commit SHAs:

Protect the promotion merge method with a branch ruleset on the target branch.
For a `dev` to `main` promotion, target `main`, require a pull request, and set
the required merge type to **Merge** only. This prevents squash and rebase on
`main` without disabling those methods for every branch in the repository.
Apply the same rule to `dev` when the back-merge into `dev` must also preserve
commit identity. Do not enable **Require linear history** on either target,
because linear history rejects merge commits. Keep required reviews, status
checks, resolved conversations, and any merge queue authoritative.

```yaml
name: Promotion PR

on:
  push:
    branches: [sdk-dev, main]
  workflow_dispatch:

concurrency:
  group: promotion-pr-${{ github.repository }}-sdk-dev-main
  cancel-in-progress: false

permissions: {}

jobs:
  promotion-pr:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@<reviewed-full-commit-sha>
        with:
          fetch-depth: 0
      - uses: haiven-dev/haiven-actions/actions/promotion-pr@<reviewed-full-commit-sha>
        with:
          token: ${{ github.token }}
          source-branch: sdk-dev
          target-branch: main
          title: "chore: promote sdk-dev into main"
          note: >-
            Merge with a **merge commit**, not squash or rebase, so the target
            holds each commit and the next list starts where this one ends.
```

A push runs the workflow file of the branch it lands on, so the caller has to
exist on both branches before both sides trigger it.

## Inputs

| Input | Required | Purpose |
| --- | --- | --- |
| `token` | yes | Token with pull-request write access in the caller repository. |
| `source-branch` | yes | Branch whose commits are promoted (the pull-request head). |
| `target-branch` | yes | Branch they are promoted into (the pull-request base). |
| `title` | no | Title for a newly opened pull request; defaults to `chore: promote <source> into <target>`. |
| `note` | no | Paragraph placed after the generated commit list. |

## Choosing the token

Pass either the caller's `GITHUB_TOKEN` or a token minted from a GitHub App.

- **`GITHUB_TOKEN`** needs `pull-requests: write` in the caller, and opening a
  new pull request also needs the repository setting that allows GitHub Actions
  to create pull requests. A pull request opened with `GITHUB_TOKEN` does not
  start `pull_request` workflows, so it suits repositories whose checks already
  run on branch pushes.
- **A GitHub App** opens a pull request that does start `pull_request`
  workflows, so required checks run on it. Mint the token in a preceding step
  and pass that step's output to the action:

  ```yaml
  - uses: actions/create-github-app-token@<reviewed-full-commit-sha>
    id: app-token
    with:
      app-id: ${{ vars.PROMOTION_APP_ID }}
      private-key: ${{ secrets.PROMOTION_APP_PRIVATE_KEY }}
  - uses: haiven-dev/haiven-actions/actions/promotion-pr@<reviewed-full-commit-sha>
    with:
      token: ${{ steps.app-token.outputs.token }}
      source-branch: sdk-dev
      target-branch: dev
  ```

  The app needs pull-requests write access to the repository.

The caller should grant only the scopes its chosen token path needs.
`contents: read` is always required for checkout and fetch.

## Testing

`actions/promotion-pr/test-promotion-pr.py` builds real origin and clone
repositories under temporary paths containing spaces and non-ASCII characters
and replaces the GitHub API with a local fake. This repository runs it on
Linux, macOS, and Windows.
