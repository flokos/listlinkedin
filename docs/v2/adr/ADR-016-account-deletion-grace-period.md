# ADR-016: Account deletion with a 30-day grace period

- Status: Accepted (2026-10-29, decided by the user before task 3.2)
- Changes: the account-deletion flow of task 1.7 ([04 Ownership rules](../04-DOMAIN-MODEL.md#ownership-rules),
  [09](../09-API-DESIGN.md#session-and-account)). Related: [ADR-003](ADR-003-immutable-revision-snapshots.md),
  [07 Immutability](../07-REVISION-SPEC.md#immutability)

## Context

Task 1.7 deleted an account at once: its lists first, then the user row. Revisions (phase 3)
record their author as a foreign key to the user. Deleting the row would have to change
revisions that account wrote on other people's lists (`SET NULL`), which the immutability
trigger otherwise forbids; PR #23 allowed exactly that update as an exception. The user
preferred to keep the accounts and give people a way back, the way many services do, with the
personal data erased after a grace period.

## Decision

Deleting an account (`DELETE /api/v2/me/`, still type-to-confirm) **schedules** its erasure:

1. **At once:** `deleted_at` and `sessions_revoked_at` are set. Every session ends (the session
   hash includes `sessions_revoked_at`). The account counts as signed out everywhere except
   `GET /api/v2/session/` and `POST /api/v2/me/restore/`. The lists it owns are hidden from
   everyone (unknown in v1 and v2, short URLs 404, not writable), it disappears from member
   lists, and it can't be added to lists.
2. **For 30 days:** signing in works and leads to "Your account is being deleted" with
   **Restore my account**, which clears `deleted_at` and brings everything back as it was.
   Sessions from before the deletion stay ended.
3. **After 30 days:** `purge_deleted_accounts` (daily 03:40) deletes the lists it owns (with
   links, short URLs and their history), removes its memberships and email addresses, and
   replaces its personal data: email `deleted-<id>@deleted.invalid`, no name, an unusable
   password, `is_active = false`. The **row stays**, anonymous, so revisions it wrote keep an
   author ("Deleted account") without ever being changed. The email address is free again.

## Alternatives considered

- **Immediate hard delete (task 1.7)**: no way back after a mistake, and revisions need the
  `SET NULL` exception to immutability.
- **Keep the row with the author's name visible after deletion**: people expect their personal
  data to go when they delete their account (GDPR right to erasure).
- **Store the author id without a foreign key**: revisions never change, but the database can't
  guarantee the id belongs to an account, and the deleted person's id stays in others' history.

## Consequences

- Deletion is reversible for 30 days and the erasure is explained in the confirmation dialog
  ("Everything is erased after 30 days; until then, sign in to restore your account").
- Every read of a list filters out lists whose owner is being deleted (`OWNER_ACTIVE`), and
  member reads and add-by-email skip such accounts.
- With PR #23 merged, the trigger's `created_by_id` exception is no longer needed: no user row
  is deleted any more. It is removed in the first PR that has both.
- Groups (phase 4) join the same flow: hidden at once, deleted at erasure.
