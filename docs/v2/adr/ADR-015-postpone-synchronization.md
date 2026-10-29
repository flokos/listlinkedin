# ADR-015: Postpone list synchronization (synced copies and merges)

- Status: Accepted (2026-10-29, during phase 1)
- Postpones the implementation of: [ADR-004](ADR-004-three-way-merge.md) and the
  synchronization parts of [ADR-005](ADR-005-child-ordering-policy.md). Both stay as the
  design baseline; neither is superseded.
- Related: [08-SYNCHRONIZATION-SPEC.md](../08-SYNCHRONIZATION-SPEC.md),
  [17 Phase 6](../17-IMPLEMENTATION-ROADMAP.md#phase-6-synchronization-postponed)

## Context

Synchronization (a "synced copy" that pulls changes from its source list through a reviewed
three-way merge) is the most complex and riskiest part of V2 ([18](../18-RISKS-AND-MITIGATIONS.md)).
While phase 1 was being built, the product owner decided the feature needs more thinking
before it is built: the user-facing model, the review UX and whether synced copies are wanted
at all in this form.

## Decision

- **Not part of the V2 release:** branches ("Make a synced copy"), sync status, preview and
  apply, exclusions, detach, the merge engine (`versioning/domain/merge.py`), the Review
  updates page, and the `ListBranch`, `BranchExclusion` and `SyncRecord` tables. Roadmap
  phase 6 and the branch half of task 5.1 are postponed, and phase 9 no longer depends on them.
- **Still in V2:** revisions and history (phase 3), and **forks** ("Make a copy"). A fork is an
  independent list copied once, with no sync relationship. It is not affected.
- **Kept as the design baseline:** [08](../08-SYNCHRONIZATION-SPEC.md), ADR-004, the sync
  sections of 04, 05, 09, 11, 12 and 15. They are marked "postponed" and are not edited
  otherwise, so the thinking done so far isn't lost. Revisit them before resuming.
- **Kept in the schema and code because they cost nothing and change nothing:**
  - `SharedList.allow_branch`, which defaults to `false` and isn't offered in the UI;
  - `Action.BRANCH` in the policy;
  - the `branched` and `merged` revision kinds, which stay reserved;
  - `SharedLink.source_link_id` and `forked_from_id`, which record a copy's provenance.

  Branch tables and endpoints are **not** created until the feature is resumed.
- **Resuming** needs a new ADR that accepts or replaces this design, plus an updated phase 6
  in the roadmap.

## Alternatives considered

- **Build it as planned:** high cost and risk for a feature whose shape is now in doubt.
- **Delete the design:** loses careful work (36 specified scenarios, baselines, idempotency)
  that a later decision can reuse or reject explicitly.
- **Drop forks as well:** forks are simple, independent copies and don't depend on any of
  the open questions.

## Consequences

- V2 ships sooner and with less risk. Risks 11–15 ([18](../18-RISKS-AND-MITIGATIONS.md)) are
  dormant.
- Tasks 2.1 and 3.x keep building tombstones, `source_link_id` and immutable snapshots, which
  history and restore need anyway. They also keep synchronization possible later without a
  data migration.
- The CLAUDE.md invariant on synchronization applies again only once the feature is resumed.
