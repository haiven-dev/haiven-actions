# Repository setup

An organization owner should apply these settings to the public
`haiven-dev/haiven-actions` repository:

1. Keep visibility public and the default branch set to `main`.
2. Enable GitHub Actions with read-only default workflow-token permissions.
3. Enable private vulnerability reporting so the process in `SECURITY.md` is
   available to external reporters.
4. Require pull requests for `main`, at least one approval, resolved review
   threads, and all three CI matrix jobs. Block force pushes and branch
   deletion.
5. Keep third-party Actions dependencies pinned to reviewed full commit SHAs.

Caller repositories have their own independent requirements. They must allow
this public action through any organization or repository Actions allow-list,
check out full history, grant the selected token pull-request write access, and
pin `haiven-dev/haiven-actions` to a reviewed full commit SHA.
