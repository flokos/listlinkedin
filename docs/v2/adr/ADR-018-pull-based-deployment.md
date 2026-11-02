# ADR-018: Continuous deployment of GitHub Releases, pulled by the server

- Status: Accepted (2026-11-01, decided by the user)
- Changes: how production is upgraded ([deployment](../../deployment.md#upgrades)). Related:
  [ADR-017](ADR-017-production-on-oci-always-free.md)

## Context

Production is one host (ADR-017) upgraded by hand with the steps in "Upgrades". The user wants
releases to deploy themselves. SSH to the host is open only to administrator addresses, and
GitHub-hosted runners use thousands of changing addresses. Deploying every pull request to
production would put unreviewed code on the live site, and the Always Free VM has no room for
preview stacks.

## Decision

- **Trigger:** publishing a GitHub Release (a `vX.Y.Z` tag on `main`). Pull requests keep
  running CI only.
- **Mechanism:** the host pulls. `listlinkedin-deploy.timer` runs `lli-auto-deploy`
  ([infra/terraform/host/auto-deploy.sh](../../../infra/terraform/host/auto-deploy.sh)) every 5
  minutes. It reads the latest release from GitHub's public API and runs the "Upgrades" steps:
  build while the old version serves, back up, `up --wait`, check `/healthz`.
- **On failure** it re-tags the previous images (kept as `:rollback`), checks out the previous
  commit and, once the backup was taken, restores it, as "Rolling back" describes. Every
  outcome is mailed to `MODERATION_EMAIL`.
- **It deploys nothing automatically** that is not a `vX.Y.Z` tag on `main`, that is older
  than the running version, or whose release notes contain `[manual-deploy]`. A skipped or
  failed tag is reported once; `sudo lli-auto-deploy <tag>` deploys it by hand.

Not chosen: a self-hosted runner (GitHub advises against them on public repositories, and it
costs memory on the VM); GitHub Actions over SSH (port 22 open to GitHub's ranges, or OCI
Bastion, which the deployer group can't use).

## Consequences

- No inbound access and no server credentials in GitHub. Publishing a release is the
  deployment approval.
- A release goes live up to about 5 minutes after it is published, plus the build.
- GitHub doesn't show the deployment; the mail and `/var/lib/listlinkedin/deploy-<tag>.log` do.
- Images are still built on the host from the tag, as before.
- A failed migration costs what was written between the backup and the failure (seconds).
