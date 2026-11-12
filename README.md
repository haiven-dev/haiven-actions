# Haiven Actions

Public, reusable GitHub Actions for Haiven repositories.

Actions in this repository are intentionally public and must be referenced by
a reviewed full commit SHA. Each action documents its required caller token
permissions and repository policy.

## Actions

### Promotion pull request

[`actions/promotion-pr`](docs/promotion-pr.md) opens or refreshes the pull
request that promotes one long-lived branch into another. Its generated block
groups the commits missing from the target by conventional-commit type while
preserving reviewer-authored text outside the block.

```yaml
- uses: haiven-dev/haiven-actions/actions/promotion-pr@<reviewed-full-commit-sha>
  with:
    token: ${{ github.token }}
    source-branch: sdk-dev
    target-branch: main
```

## Security

Report vulnerabilities through this repository's private security-advisory
flow. See [SECURITY.md](SECURITY.md). Organization owners should also apply the
[repository setup checklist](docs/repository-setup.md) before accepting code.

## License

Licensed under the [MIT License](LICENSE).
