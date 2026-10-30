# 12: Authorization

V2 replaces V1's single rule ("anyone reads, the token holder writes") with accounts, roles and
visibility. The rules below are normative and are implemented once, in `sharing/policy.py`
(pure functions plus one queryset filter builder). The API, short URLs, groups, search and
sync all ask the policy and never reimplement it (invariant **A1**). OWASP ranks broken
object-level authorization as the top API risk [R13], so every rule here maps to tests in
[15](15-TEST-STRATEGY.md#authorization-matrix-tests).

## Principals

| Principal | How it is established |
|---|---|
| Anonymous | no session, no token |
| Signed-in user | Django session (allauth headless browser flow, [ADR-007](adr/ADR-007-authentication-and-ownership-migration.md)) |
| **Owner** | `list.owner_id == user.id` (likewise `group.owner_id`) |
| **Editor** / **Viewer** | a `ListMembership` (or `GroupMembership`) row with that role |
| **Legacy token holder** | `Authorization: Bearer <owner token>` whose SHA-256 matches `owner_token_hash` of **that** list ([A3](04-DOMAIN-MODEL.md#invariants)). Only possible while the list is unclaimed |

Roles never inherit across resources. Group roles grant nothing on lists. List roles grant
nothing on other lists, including branches or forks of that list.

## Visibility

| Visibility | Who can view | Discoverable |
|---|---|---|
| `private` | owner, editors, viewers | no |
| `unlisted` | anyone who has the URL or code, plus members | no |
| `public` | anyone | yes: directory, search, public groups, owner attribution |

New lists default to `private` (secure by default). Share is one click in the Share dialog,
which shows the visibility choice first ([11](11-UI-UX-MIGRATION.md#sharing)). Migrated V1
lists are `unlisted`, which is exactly their V1 semantics.

## List permission matrix

✓ = allowed, — = denied. "Can view" means the visibility rule above passes.

| Action | Anonymous | Signed-in, no role | Viewer | Editor | Owner | Legacy token |
|---|---|---|---|---|---|---|
| View content and links | if can view | if can view | ✓ | ✓ | ✓ | ✓ |
| Open a link's short URL `/r/{code}` | if can view | if can view | ✓ | ✓ | ✓ | n/a (redirects carry no token) |
| View revision history | — | — | — | ✓ | ✓ | ✓ |
| Edit content: title, description, add, edit, delete and reorder links, restore a revision | — | — | — | ✓ | ✓ | ✓ |
| Upload images (list image, link icons) | — | — | — | ✓ | ✓ | — (requires an account) |
| Edit tags, slug (`tags` permission since 8.1) | — | — | — | ✓ | ✓ | — |
| Change visibility, expiry, `allow_fork`, `allow_branch` | — | — | — | — | ✓ | — |
| See who has access (members) | — | — | — | ✓ | ✓ | — |
| Manage members (add a verified account by email, change roles, remove) | — | — | — | — | ✓ | — |
| Leave (remove own membership) | — | — | ✓ | ✓ | — | — |
| Delete the list | — | — | — | — | ✓ | ✓ |
| Rotate the legacy token | — | — | — | — | — | ✓ |
| Claim (become owner) | — | ✓ with a valid token | — | — | — | (needs a session too) |
| Fork ("Make a copy") | — | if can view **and** `allow_fork` | same | same | ✓ | — |
| Branch ("Make a synced copy"), *postponed* | — | if can view **and** `allow_branch` | same | same | ✓ | — |
| Preview or apply sync (as child), *postponed* | — | — | — | ✓ on the child **and** can view the parent | same as Editor | — |
| Remove an exclusion | — | — | — | ✓ on the child | ✓ | — |
| Detach a branch, *postponed* | — | — | — | — | ✓ (child owner) | — |
| Create a list | — | ✓ | | | | — (no anonymous creation, [ADR-011](adr/ADR-011-accounts-required-legacy-lists.md)) |
| Report to the operator (`report`, since 9.0) | if can view | if can view | ✓ | ✓ | — | — |

A view-only capability never grants editing. In V2 the share URL (`/l/{code}`) is only ever a
*view* capability. The single exception is the V1 edit link, a separate secret that works only
on legacy lists until they are claimed or expire. Account-owned lists have no edit links:
collaborators are added by account.

## Group permission matrix

| Action | Anonymous / no role | Group Viewer | Group Editor | Group Owner |
|---|---|---|---|---|
| View the group page | if the group's visibility allows | ✓ | ✓ | ✓ |
| Reorder lists, edit title and description, image, tags | — | — | ✓ | ✓ |
| Add a list | — | — | ✓ **and** (list Editor or above, or the list is `public`) | same |
| Remove a list from the group | — | — | ✓ | ✓ |
| Visibility, members, delete | — | — | — | ✓ |
| Report to the operator (`report`, since 9.0) | if the group's visibility allows | ✓ | ✓ | — |

Since 4.1 the group rules live next to the list rules in `sharing/policy.py` (`can_group`,
`can_add_list`, `shown_in_group`), and `groups/selectors.py` applies the display rule in SQL
(`shown_lists_q`, checked equal to `shown_in_group` for every case). An entry the actor isn't
shown can't be removed or moved by them (404, like an absent one). Moving reorders only the
entries the actor sees; hidden ones keep their places. When adding, the group answers first:
someone who can't add to the group never learns whether a list is private.

Rule for adding: you can put a list in a group only if you could share that list yourself. Its
editors may share it, and anyone may share a public list. Nobody can place another person's
unlisted or private list into their group.

## Which lists a group shows to a viewer

For each `GroupList` entry, the list is **shown** to viewer *u* only if at least one of these
is true:

1. *u* can view the list directly by role (owner, editor or viewer of the list).
2. The list is `public`.
3. The list is `unlisted`, the group is **not** `public`, and *u* can view the group. Sharing
   an unlisted group link is like sharing the list links in it, and only the lists' editors
   could have put them there (rule above).

Lists nobody may open are never shown, whatever the rule says: expired lists and lists whose
owner is deleting their account. A legacy edit link grants nothing on groups.

Otherwise the entry is **omitted entirely**: no title, no placeholder, no "1 hidden list"
count, no position gap. Counts, sidebars and API pages are computed after filtering, in SQL.
Group editors see a notice on entries hidden from some viewers, for example "Unlisted lists
aren't shown to visitors of a public group. Make it public to show it." This is the critical
access rule from prompt 5.5: a public group can't expose a private list's data **or its
existence**.

## Synchronization

> **Postponed** ([ADR-015](adr/ADR-015-postpone-synchronization.md), 2026-10-29): these rules apply once synchronization is resumed.

- Preview and apply require editor (or above) on the child **and** the ability to view the
  parent **now**. Both are re-checked under the child lock at apply time.
- Losing access to the parent (it became private, or a membership was removed) sets status
  `parent_inaccessible`. The child keeps all its content. The preview answers 404 and reveals
  no parent titles, counts or changes.
- Provenance banners ("Synced copy of *Team tools*") show the parent's title only when the
  viewer can view the parent. Otherwise they say "Copied from a list you can't access".
- Branch creation needs only *view* access plus `allow_branch`. That is safe because the child
  receives only what the creator could already see, and access is re-checked on every sync.

## Short URLs and other entry points

| Entry point | Rule |
|---|---|
| `/r/{code}` | Resolve link → list. **404** if the link is tombstoned, the list is not viewable by the requester (session cookie, same origin) or `private` for anonymous requests. **410** if the list is expired, the redirect inactive or the host blocked (V1 semantics). Otherwise 302 to the current URL |
| `/l/{code}`, `/g/{code}` | The SPA loads the API. The API applies the same rules |
| `/api/v1/…` (transition) | Reads: `unlisted` and `public` lists only (private → 404). Writes: legacy token on legacy lists only. Claimed lists answer 403 to tokens |
| Directory and search | `visibility = 'public'` only, filtered in SQL. Tag facets count public resources only |
| Media files `/media/…` | Random 128-bit filenames, served without an access check. Acceptable for icons and images; see [13](13-SECURITY.md#media) |

## Status codes

| Situation | Response |
|---|---|
| The actor can't view the resource (including private lists for anonymous or unauthorized users, and nonexistent codes) | **404**, the same body as nonexistent |
| The actor can view but may not perform the action, and is signed in | **403** |
| An action needs an account and the actor is anonymous | **401**, keeping V1's 401 vs 403 split. `WWW-Authenticate: Session` on session-only endpoints, `Bearer` where legacy owner tokens are also accepted |
| A legacy token on a claimed or other list | 403 (V1 semantics: the token doesn't own this list) |

## Leak analysis

| Possible leak | Mitigation |
|---|---|
| Existence of a private list (via `/l`, `/r`, API, group pages, branch banners) | uniform 404. Omission in groups. Neutral banners |
| Titles or counts through groups | per-viewer SQL filtering. No placeholders. Counts after filtering |
| Removed links through history | history only for editors, owners and legacy token holders |
| Content through sync preview | requires current view access to the parent |
| Private or unlisted lists in the directory | `public` only. The directory query is built from `visible` + `public` filters |
| Account enumeration when adding a member by email | owners with a verified email only, rate-limited (`member_add`), with one generic message for unknown and unverified addresses. Accepted residual risk. Email invitations for unregistered addresses are a later enhancement |
| Access meant for someone else's address | only **verified** addresses can be added: an account that signed up with another person's address but never verified it can't receive their access |
| Members' email addresses | other people see `display_name` and an `email_hint` (`b…@example.com`), never the full address |
| Owner identity | owner display name shown on `public` lists only. Email addresses are never exposed except to their owner |
| Guessing codes or ids | 96-bit codes (V1). UUIDv4 ids are never authorization on their own: every lookup goes through the parent list's policy check |
| Metadata or images of private lists | media filenames are unguessable. Fetched text is stored on the link row behind normal checks |

## Concurrent permission changes

- Writes re-evaluate authorization after taking the aggregate row lock (V1's
  `_lock_active_list` pattern, extended to membership and visibility). A request that started
  before a revocation can't commit after it.
- Membership changes lock the list row too, so they serialize with writes on that list.
- Reads use committed state at statement time. A read that races a revocation may return the
  pre-revocation state once. That is acceptable and matches how revocation works on the web.

## Operator actions

Since task 9.0 the operator moderates with management commands
([13](13-SECURITY.md#moderation)). They run in a shell on the server, and shell access is
their authorization, so they don't go through the policy. Like every write, they lock the rows
they change, and they log the ids and the reason given.

A suspended account (`User.suspended_at`) can't sign in and its sessions end at once: both
authentication backends refuse it (`apps/accounts/backends.py`, at sign-in and whenever a
session is loaded), and so does allauth's sign-in (`apps/accounts/adapter.py`), which answers
as for a wrong password. `is_active` stays reserved for erased accounts ([ADR-016](adr/ADR-016-account-deletion-grace-period.md)).

## Implementation notes

- `policy.can(actor, action, resource) -> bool` is pure. Its inputs are an actor descriptor
  `{user_id | None, legacy_list_id | None}` and resource facts (owner id, role of the actor,
  visibility, flags, expiry), loaded by selectors in one query.
- `policy.py` stays pure, so the SQL side lives in `sharing/selectors.py`: `get_list_for(principal, code)` (one list, 404 when not viewable) and `lists_of(user)` (owned or member lists; unlisted lists of others never enumerate). They, and later `visible_groups`, are the **only** way list
  and group querysets are filtered, in API lists, groups, directory and counts.
- DRF: `get_object()` is overridden in every ViewSet to call the selector plus
  `check_object_permissions`. Object permissions aren't applied to list endpoints or creation
  automatically [R7], so list endpoints always start from the visible queryset and create
  actions check the parent resource explicitly.
- Tests: one parametrized matrix test per table above, covering every (role × visibility ×
  action) combination, plus leak tests that diff anonymous and member responses.
