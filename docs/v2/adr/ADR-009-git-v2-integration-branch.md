# ADR-009: Git: `v2` integration branch, CI guard, rulesets

- Status: Accepted (2026-10-28. User decision on publication and protection)
- Related: [16-GIT-WORKFLOW.md](../16-GIT-WORKFLOW.md)

## Context

V1 lives on `main` and must stay independently available and fixable. V2 is a long
development effort with many PRs. The repository is on GitHub, public, with one admin and,
before this decision, no branch protection or rulesets. `gh pr create` and the GitHub UI
default PRs to the default branch (`main`), which makes PRs into the wrong branch likely. The
prompt forbids changing the default branch for this purpose.

## Decision

- A long-lived **`v2`** branch, created from `main` at `fb5f901`. All V2 work branches from
  `v2`, and **all V2 PRs target `v2`**. Feature PRs are squash-merged.
- **Rulesets** on `main` and `v2`: no deletion, no force-push, PR required (0 approvals),
  `checks` status required. Bypass: the Admin role in pull-request mode.
- **CI guard** in `v2`'s `ci.yml`: fail `checks` on PRs into `main` unless the head is `v2` of
  this repository. It is blocking because `main` requires `checks`. Pushes to `v2` also run CI.
- **V1 fixes** land on `main` first and are ported with `git cherry-pick -x`. `main` is never
  merged wholesale into `v2` except in the reviewed reconciliation before the release.
- **Release:** tag `v1.0.0` and create `release/v1`, then PR `v2 → main` with a merge commit.
- CLAUDE.md on `v2` encodes these rules for every coding-agent session.

## Alternatives considered

- **A separate repository or fork for V2:** splits history and issues, complicates porting.
  The prompt prefers a branch.
- **Changing the default branch to `v2`:** forbidden by the prompt, and it would mislead V1
  users.
- **Classic branch protection:** superseded by rulesets, which layer and can be inspected
  through the API.
- **A PR template only:** GitHub reads templates only from the default branch, so it can't
  live on `v2` alone (optional on `main`).
- **Periodic automatic merges of `main` into `v2`:** risk merging V1 changes that don't fit V2.
  The prompt says to review them.

## Consequences

- Direct pushes to `main` and `v2` stop for everyone, including the admin. Every change is a PR.
- A V2 PR opened against `main` by mistake shows a failed, required `checks` run with a clear
  message.
- Admins can still deliberately bypass at merge time, and can disable rulesets if needed.
