# 10: Frontend architecture

The V1 SPA (Vue 3.5, Vuetify 4, vue-router 5, Vite 8, TypeScript 6) is **extended, not
rebuilt** [Decision]. It already has the hard parts V2 needs: a design system with enforced
contrast, route focus management, route announcements, dialogs reflected in the URL, typed API
errors, offline and stale-chunk handling, and a five-browser e2e suite
([01](01-V1-AUDIT.md#frontend)). Nothing in the V2 requirements justifies a new framework or a
competing UI library.

## Principles

1. Vuetify stays the only component library. New UI is composed from Vuetify components and
   the existing design tokens and roles ([docs/design-system.md](../design-system.md)).
2. Server rules are not re-implemented in the client. Permissions come from the API
   (`permissions` array), as do display values (`display`), merge plans and sync status.
3. Every view keeps V1's accessibility contract: one `<h1>`, focus moved to it on navigation,
   announcements through `RouteAnnouncer`, and Back closing dialogs.
4. Add a dependency only where native code would be clearly worse. V2 adds two
   (see [Dependencies](#dependencies)).

## Structure (target)

Since task 1.2, `api/` exists as `client.ts` (request, `ApiError` with `code` and allauth
error parsing, CSRF), `lists.ts` (the V1 calls), `auth.ts` (allauth and `/api/v2/session|me`)
and `index.ts`. Also in place: `useSession`, `useSignOut`, `PasswordField`, `AuthPanel`,
`utils/forms.ts`. The other modules below arrive with their roadmap tasks. Generated types
(`schema.d.ts`) come with the first v2 list endpoints (task 1.3).

```text
src/
  api/
    client.ts        request(), ApiError/NetworkError (from V1 api.ts), CSRF + session handling, ETag/If-Match helpers
    schema.d.ts      generated from /api/schema/?version=v2 by openapi-typescript (committed, CI-checked)
    lists.ts auth.ts groups.ts revisions.ts sync.ts members.ts directory.ts
  composables/
    useSession.ts         current user, sign-in state, route guard helper            (new)
    useListPage.ts        extended: permissions, ETag, tiles, reorder, history entry  (V1)
    useOwnedLists.ts      V1 device tokens → "On this device" legacy section + claim  (V1, narrowed)
    useGroupWorkspace.ts  group + visible lists + current list, persisted in the URL  (new)
    useSyncPreview.ts     load plan, hold decisions, apply with idempotency key       (new)
    useHistory.ts useDirectory.ts useViewPreference.ts useReorder.ts                  (new)
    useNotify useClipboard useShare useRouteFocus useOnline useNow useThemePreference (V1, unchanged)
  components/ … (see below)
  views/ … (see 11-UI-UX-MIGRATION.md)
  design/ (V1 tokens, themes, contrast: unchanged; new tokens only for tiles and diff colours)
```

V1's `api.ts` becomes `api/client.ts` plus resource modules. `ApiError` gains `code` (the
API's machine code) so views can branch on `stale_preview`, `revision_mismatch` and so on.

## State management

V1 uses module-level `reactive` singletons inside composables, with no store library. V2 keeps
that pattern [Decision] and adds a few singletons (`useSession`, the per-list cache in
`useListPage`, the group workspace). Pinia (4.1.0 current [R23]) was considered. It would add
devtools and a formal store API, but the app has few cross-view entities and the composable
pattern is already tested. Adopt Pinia only if more than three composables start sharing
mutable caches of the same entities. If that happens, add an ADR.

Caching and staleness (risk 28):

- `useListPage` keeps V1's per-list cache for instant back navigation. It always revalidates,
  and it tracks the list `ETag`. A 412 on a write triggers reload-and-retry UX, never a silent
  overwrite.
- After a merge or restore, the list cache is replaced from the response's new head. Group
  sidebars refetch the visible lists on focus and every 60 s while visible.
- Cross-tab: V1's `storage` event sync stays for device tokens. Session changes (sign out in
  another tab) are detected on the next API 401/403, which sends the user to sign-in.

## API integration

- **Session and CSRF.** `credentials: 'same-origin'` (V1 used `'omit'` because there were no
  cookies). `GET /api/v2/session/` sets the `csrftoken` cookie and returns the user. The router
  loads it before pages marked `requiresAuth` or `guestOnly`, and in the background otherwise.
  Unsafe requests without a bearer token send `X-CSRFToken`. If the cookie isn't there yet,
  the client calls the session endpoint first. Same-origin `fetch()` keeps sending a real
  `Origin` header under the app's `no-referrer` policy, which Django checks over HTTPS.
  Verified in all five e2e browser projects.
- **allauth responses.** `ApiError` maps allauth's `{errors: [{message, code, param}]}` to
  field errors. allauth answers **401 when a step succeeded but left you signed out** (sign-out,
  password reset, verifying while signed out), and `api/auth.ts` treats those as success.
- **Legacy tokens.** For lists in the device's legacy store, the client adds
  `Authorization: Bearer` on writes to that list only (V1 behaviour). After a successful claim
  the token is deleted from storage.
- **Generated types.** `openapi-typescript` turns the v2 schema into `schema.d.ts`. A CI step
  regenerates it and fails on diff, so client and server can't drift silently.
- **Idempotency.** The client generates `Idempotency-Key`s (`crypto.randomUUID()`) per user
  action for create, fork, branch and sync, and reuses the key when it retries that action.

## Routing and guards

New routes are in [11](11-UI-UX-MIGRATION.md#screen-inventory). Route `meta.requiresAuth`
redirects to `/signin?next=<path>`. `next` must be a same-origin path starting with `/`
(open-redirect guard, [13](13-SECURITY.md)). `/l/:code/:slug?` replaces `/l/:code`, and the
reserved segments (`manage`, `history`, `sync`, `settings`) get their own routes.

## Components

| V1 component | V2 |
|---|---|
| `LinkCard` | Kept as the **list view** row. Shows the full description and the icon (`display`), since 2.4 |
| `DomainAvatar` | Kept as the icon **fallback**, scaled for tiles |
| `LinkForm` | Extended: description (2.4); metadata preview ("Fetched title: … Use it?", 7.3). The icon upload is in `LinkEditDialog` (`ImageUploadField`), since an icon belongs to a saved link. No `autofocus`: the dialog focuses the URL after opening, only if focus isn't already in the form |
| `StatePanel`, `ConfirmDialog`, `CopyField`, `ExpiryChip`, `LinkLimitMeter`, `RouteAnnouncer`, `RouteProgress`, `ThemeMenu`, `AppFooter` | Unchanged or copy-only changes |
| `ShareDialog` | Extended with a visibility selector and a members section |
| `AppHeader`, `AppNavDrawer` | New nav items and an account menu. The drawer pattern is reused for the group sidebar on mobile |
| `EditLinkReveal`, `ClaimTokenDialog`, `BackupCard` | Legacy only. They gain "Add to my account". Removed at the legacy sunset |
| `ListView.vue` (619 lines) | Split into `ListHeader`, `ListToolbar`, `AddLinkCard`, `LinkCollection` (grid/list) and dialog components (`LinkEditDialog`, `LinkDetailsDialog`), since 2.4. `LinkMenu` (the ⋮ menu) and `LinkIcon` (icon or avatar) are shared by tiles and rows |

New components: `LinkTile`, `LinkGrid`, `ViewToggle`, `MoveMenuItems`, `LiveRegion`,
`VisibilitySelect`, `MembersPanel`, `ListSettingsDialog`, `ImageUploadField`, `MetadataStatus`,
`GroupSidebar`, `GroupWorkspaceLayout`, `ListPickerDialog`, `HistoryTimeline`, `RevisionDiff`,
`ProvenanceBanner`, `CopyListDialog` (fork only in V2), `AuthForm` variants, `TagInput`, `TagChips`.
Postponed with synchronization ([ADR-015](adr/ADR-015-postpone-synchronization.md)): `SyncStatusChip`,
`ChangeCard`, `FieldCompare`, `DecisionGroup`, `ExclusionsPanel`, `api/sync.ts`, `useSyncPreview`.

## Drag and drop

Requirements (prompt 8.7): reorder tiles in a grid and lists in a sidebar, with touch,
keyboard and screen-reader support, a small bundle and active maintenance.

| Option | Facts (registry, 2026-10-28) [R23] | Assessment |
|---|---|---|
| **vue-draggable-plus** (SortableJS wrapper) | 0.6.1 (2026-01-11). SortableJS 1.15.7 (2026-02-11) | **Chosen.** Mature touch support and grid sorting, a thin Vue 3 API (component, composable or directive). Like the others, it doesn't make reordering keyboard- or screen-reader-accessible |
| @formkit/drag-and-drop | 0.6.1 (2026-06-15) | Small and framework-agnostic, but its grid and touch behaviour is less proven |
| @atlaskit/pragmatic-drag-and-drop | 4.0.0 (2026-09-24) | Tiny core and the best accessibility guidance, but low-level: drop indicators, grid logic and auto-scroll would be ours to build |
| Native HTML5 DnD | — | Poor and inconsistent touch support. Rebuilding SortableJS's fallbacks isn't worth it |

Whichever library is used, **dragging is only a pointer shortcut**. WCAG 2.2 SC 2.5.7
requires a single-pointer alternative that doesn't involve dragging, and keyboard support alone
doesn't satisfy it [R21]. Every tile and sidebar entry has a ⋮ menu with **Move up**,
**Move down**, **Move to top**, **Move to bottom** and **Move to position…**. A polite live
region announces "Docker moved to position 3 of 12", following Atlassian's
announce-and-continue pattern [R22]. Each move calls `POST …/reorder/ {link, to_index}`, the
same endpoint drag-and-drop uses. Task 2.5 starts with a one-day spike that confirms
vue-draggable-plus on iOS Safari and Android Chrome in the e2e phone projects. If it fails
there, switch to Pragmatic drag and drop. The API doesn't change either way.

## Dependencies

| Package | Type | Why |
|---|---|---|
| `vue-draggable-plus` (+ `sortablejs`) | runtime | Pointer and touch reordering (above) |
| `openapi-typescript` | dev | Client types generated from the API schema |

Nothing else. Diff display, the tiles, the sidebar and the forms use Vuetify and plain code.

## Error and state handling

`describeStatus` gains V2 cases: 409 `stale_preview` ("The source list changed while you were
reviewing"), 412 `revision_mismatch` ("This list changed. Reloaded the latest version."),
422 `link_limit`, and 401 ("Sign in to continue"). Every state in
[11 UI states](11-UI-UX-MIGRATION.md#ui-states) maps to `StatePanel`, an alert or a toast, as
in V1.

## Testing

Vitest and @vue/test-utils (V1 tooling) cover composables (session, sync decisions, reorder)
and components (`LinkTile`, `DecisionGroup`, `FieldCompare`, `VisibilitySelect`). Playwright
(V1 tooling) covers the journeys in [15](15-TEST-STRATEGY.md#end-to-end-scenarios). No new
test framework is added.
