# Haiven Actions

This repository publishes reusable GitHub Actions for Haiven repositories.
Its contents are public and may execute with caller-provided GitHub tokens, so
changes must keep permissions narrow and behavior easy to audit.

## How work is done here

Read [CONTRIBUTING.md](CONTRIBUTING.md) before making changes. In particular:

- **Stay on task.** Do what the task asks and nothing more; if its scope is
  unclear, ask rather than guess. Build for today, not a plausible future.
  Keep diffs small, match the surrounding code, and comment only the *why*.
  Write a new idea down for later instead of adding it to the current change.
- **Know who decides.** Making code, data, or documentation public, deciding
  what a feature does and who it is for, and giving anyone outside Haiven
  access to code, credentials, or user data go to the engineering manager
  before anything depends on them. Every commit here is public.
- **Use Conventional Commits** for commits and pull-request titles, with `!`
  before the colon for a breaking change.
- **Include tests and caller-facing documentation** with behavior changes, in
  the same pull request.
- **A human approves every pull request, and its author merges it.** An agent's
  own review does not count as that approval, and an agent does not merge on
  someone else's behalf.

Report suspected vulnerabilities through the private process in
[SECURITY.md](SECURITY.md), not in a public issue.

## Repository-specific rules

- Keep each reusable action's implementation and tests under
  `actions/<action-name>/`.
- Document every action input, output, required caller permission, and material
  repository-policy assumption in `docs/<action-name>.md`, linked from the root
  `README.md`. Do not add a separate README under `actions/<action-name>/`.
- Pin third-party actions to reviewed full commit SHAs in examples and tests.
- Never commit credentials, tokens, private repository names, or other
  non-public organization details.
- Preserve portable behavior across Linux, macOS, and Windows unless an action
  explicitly documents a narrower platform contract.
