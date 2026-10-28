# Design system

The visual language of the listlinkedin frontend. Everything is built on Vuetify 4 and
driven by tokens in [`frontend/src/design/`](../frontend/src/design/). To see the system
rendered by the live theme, run the dev stack and open **http://localhost:5173/design**.
That route exists only in development builds.

## Principles

1. **Calm and purple.** The brand is violet. Surfaces, neutrals and accents are all tinted
   purple, so even greys belong to the palette. Colour marks meaning and the main action,
   never decoration.
2. **One obvious next step.** Each view has at most one filled (primary) button. Everything
   else is tonal, outlined or text.
3. **Honest about privacy.** The product has no accounts. Copy explains what is public (the
   share link), what is secret (the edit link) and what happens after 30 days, in plain
   words, at the moment it matters.
4. **Accessible by default.** WCAG 2.2 AA is enforced by a script, not just reviewed. See
   [Contrast](#contrast).

## Tokens ([`tokens.ts`](../frontend/src/design/tokens.ts))

| Token | Use |
|---|---|
| `violet` 50–950 | Brand. 700 is the light-theme primary, 300 the dark-theme primary. |
| `orchid` 50–950 | Pink-purple accent (`secondary`): highlights, the logo gradient, count chips. |
| `mauve` 0–950 | Violet-tinted neutrals: backgrounds, surfaces, borders, text. |
| `status` | Muted red, amber and green for error, warning and success. Info is violet-blue. These keep their usual meaning on purpose; never use them for decoration. |
| `avatarTints` | Purple-family backgrounds for domain avatars (white initials). |
| `space` | 4px base unit, matching Vuetify's spacing helpers (`pa-4` = 16px). |
| `radius` | sm 4 · md 8 · lg 12 (buttons, fields) · xl 16 (cards) · xxl 24 · pill. |
| `elevation` | MD3 levels: flat 0 (default), raised 1, overlay 3, modal 5. Prefer borders to shadows. |
| `motion` | 120 / 200 / 320 ms with MD3 easing. All motion is turned off under `prefers-reduced-motion`. |

The browser favicon stays **blue** on purpose; the in-app logo
([`AppLogo.vue`](../frontend/src/components/AppLogo.vue)) is the violet-to-orchid mark.

## Colour roles ([`themes.ts`](../frontend/src/design/themes.ts))

Components use **roles**, never raw palette values: `color="primary"`,
`bg-surface-container`, `rgba(var(--v-theme-primary), 0.2)`.

| Role | Light | Dark | Use |
|---|---|---|---|
| `background` | mauve 50 | mauve 950 | Page |
| `surface` | white | mauve 925 | Cards, dialogs, app bar |
| `surface-container` | violet 50 | `#211833` | Highlighted panels (the add-link card) |
| `primary` / `on-primary` | violet 700 / white | violet 300 / violet 950 | Main actions, links, active nav |
| `primary-container` | violet 100 | violet 800 | Icon tiles, selection, badges |
| `secondary` | orchid 700 | orchid 300 | Accent chips, gradient end |
| `outline` | mauve 500 | mauve 500 | Field borders (3:1 against surfaces) |
| `focus` | violet 600 | violet 300 | Keyboard focus ring |
| `error`/`warning`/`success`/`info` (+ `-container`) | strong hues | soft hues | Feedback only |

Note that Vuetify theme variables are comma-separated RGB triplets. Use
`rgba(var(--v-theme-primary), 0.25)`, not `rgb(var(...) / 0.25)`, which is invalid.

## Typography

**Inter Variable**, self-hosted through `@fontsource-variable/inter`, so there are no
third-party requests and the CSP stays `'self'`. Use Vuetify 4's MD3 type roles:

| Class | Use |
|---|---|
| `text-display-small` | Home hero only |
| `text-headline-large` | Page title (`<h1>`) |
| `text-headline-small` | Section titles, empty and error states |
| `text-title-large` / `-medium` | Card and dialog titles / list item titles |
| `text-body-large` / `-medium` / `-small` | Lead paragraphs / body / supporting text |
| `text-label-large` / `-small` | Eyebrows and buttons / chips and metadata |

Display and headline styles get tighter tracking (−0.02em) and weight 700 in
[`global.css`](../frontend/src/design/global.css). Buttons are never uppercase.

## Components

Global defaults live in [`defaults.ts`](../frontend/src/design/defaults.ts). Override them in
a view only with a reason.

- **Buttons:** `flat` primary for the one main action; `tonal` for secondary actions;
  `text` for tertiary actions and Cancel. Destructive actions use `color="error"` and always
  go through `ConfirmDialog`.
- **Fields:** outlined, comfortable density, rounded-lg. Errors appear under the field that
  caused them, using the server's message when there is one.
- **Cards:** flat with a 1px border, rounded-xl.
- **Chips:** tonal pills. The expiry chip turns warning under 3 days and error once expired.
- **Feedback:**
  - Toasts (`useNotify`) confirm completed actions.
  - Alerts explain state on the page.
  - Dialogs are for decisions and secrets: the edit link.

Shared building blocks in [`frontend/src/components/`](../frontend/src/components/):
`StatePanel` (every empty and error state), `CopyField`, `ExpiryChip`, `DomainAvatar`,
`LinkCard`, `LinkForm`, `LinkLimitMeter`, `ConfirmDialog`, `ShareDialog`,
`EditLinkReveal`, `ClaimTokenDialog`.

## Layout and navigation

- Content is centred at 880px (`.ll-content`), and paragraphs are capped at 680px
  (`.ll-reading`).
- The menu is defined once in [`navigation.ts`](../frontend/src/navigation.ts) and rendered
  in three places:
  - the app bar (desktop),
  - a modal drawer (mobile; Escape closes it and focus returns to the menu button),
  - the footer.
- **It's a single-page app.** Navigation never reloads the document.
- **After every route change**, focus moves to the page's `<h1>` and the new title is
  announced to screen readers. The skip link jumps to `<main>`.
- **Dialogs that users expect Back to close are in the URL**, for example the share
  dialog's `?dialog=share`.

## Voice and tone

- Short, plain sentences. Say "link", "list", "edit link"; never "token", "capability" or
  "resource" in the UI.
- Say what happened and what to do next: "This list has expired. Lists are available for 30
  days." plus a **Create a new list** button.
- Be direct about consequences before they happen: "The current one will stop working
  immediately."

## Contrast

`npm run check:contrast` ([`scripts/check-contrast.ts`](../frontend/scripts/check-contrast.ts))
computes the WCAG 2.2 ratio of every text/background pairing in both themes. It covers
secondary text at its real opacity, the coloured text roles on each surface, field
outlines, the focus ring and avatar initials. It fails CI below 4.5:1 for text and 3:1 for
UI parts. Change a token, run it, and adjust until it passes. The `/design` page shows the
same numbers as badges.
