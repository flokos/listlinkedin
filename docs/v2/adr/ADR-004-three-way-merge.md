# ADR-004: Three-way merge with a branch-level baseline

- Status: Accepted (2026-10-28, V2 planning)
- Related: [08-SYNCHRONIZATION-SPEC.md](../08-SYNCHRONIZATION-SPEC.md)

## Context

Branches (synced copies) must receive parent changes without losing local changes. The prompt
specifies BASE/PARENT/CHILD three-way merging, field-level merging, ACCEPT, KEEP_LOCAL and
EXCLUDE decisions, persistent exclusions, previews, idempotent application and correct
baseline advancement, and it explicitly says not to recreate Git. Line-based diff3 is the
classic three-way algorithm, but its behaviour is subtle even for text [R17], and a list of
identified links isn't text.

## Decision

- Merge **by identity, not by position or line**. Parent and base links are matched by `id`,
  child links by `source_link_id`. Each link is classified with per-field three-way rules over
  `url`, `title`, `description` and `icon`. Order, fetched metadata and list settings are not
  merged.
- A **pure engine** (`versioning/domain/merge.py`) computes a plan from immutable snapshots
  (BASE = the parent at `ListBranch.base_revision`, PARENT = the parent head, CHILD = the child
  head) plus exclusions and pending re-inclusions.
- Decisions per item: ACCEPT, KEEP_LOCAL and EXCLUDE, with the semantics table in the spec.
  Conflicts have no default. **Every item must be decided** in an apply.
- A successful apply moves the **whole branch baseline** to the parent revision that was
  previewed. That is exact, because nothing in that revision remains undecided.
- Safety: a preview fingerprint (inputs plus engine version), change ids derived from it,
  `If-Match` on the child head, a required `Idempotency-Key` with a `SyncRecord`, and the child
  row lock during apply. The parent is only ever read.
- Re-inclusion after removing an exclusion uses a two-way comparison, because the base
  advanced while the link was ignored.

## Alternatives considered

- **Per-link baselines** (a state row per child link). This allows partial merges ("decide
  later"), but adds a table and a lot of state to keep consistent. Deferred until partial
  merges are wanted.
- **diff3 over a serialized list.** Identity is lost, and position noise turns into
  conflicts.
- **CRDTs or automatic merging.** These remove user control, and the prompt requires explicit
  decisions and previews.
- **Two-way merge (child vs parent).** It can't tell who changed what, so every difference
  would become a conflict.

## Consequences

- Deterministic, exhaustively testable behaviour (36 scenarios plus properties).
- Users must decide all items in one go (with sensible defaults). Partial merges are a later
  enhancement.
- An engine change invalidates open previews through `engine_version`, which is safe and
  slightly inconvenient.
