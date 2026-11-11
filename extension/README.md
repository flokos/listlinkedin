# Browser extension

The listlinkedin extension for Chrome and Firefox: save the page you are on into one of your
lists and share your lists, without opening the site. It works from the toolbar popup, from
the right-click menu and from keyboard shortcuts. It is a second client of the same API as the
web app in `../frontend`. Vue 3 and TypeScript, built with Vite; no Vuetify.

A build talks to **one** listlinkedin site, fixed when it is built (`LL_BASE_URL`). The
manifest grants the extension that site and no other.

## Build and load it

Everything runs in Docker, from the repository root.

```bash
# Docker only adds to the output folder, so files of an earlier build would stay in it.
rm -rf extension/dist

# For the development stack (docker compose up -d), into extension/dist/:
docker build --target export --build-arg LL_BASE_URL=http://localhost:5173 \
    --output extension/dist extension

# For production (the default LL_BASE_URL):
docker build --target export --output extension/dist extension

# Rebuild on every change while developing:
docker compose --profile extension up extension
```

That writes `extension/dist/chrome` and `extension/dist/firefox`.

- **Chrome, Edge and other Chromium browsers:** open `chrome://extensions`, turn on
  **Developer mode**, choose **Load unpacked** and pick `extension/dist/chrome`. After a
  rebuild, press the extension's reload button there. Pin the button to the toolbar from the
  Extensions (puzzle piece) menu: Chrome hides it there at first.
- **Firefox:** open `about:debugging#/runtime/this-firefox`, choose **Load Temporary Add-on…**
  and pick `extension/dist/firefox/manifest.json`. Firefox removes a temporary add-on when it
  closes. The Add-ons page ("Install Add-on From File…") refuses these builds: release
  Firefox installs for good only what Mozilla has signed. Developer Edition, Nightly and ESR
  can turn that check off (`xpinstall.signatures.required`).

## What it does

- **The popup** (the toolbar button): "Connect this browser" until an account is connected.
  Then two views. _Save this page_: the tab's title, a list to pick (the ones saved to last
  first), a new list (with who can open it: private unless chosen otherwise, and the answer
  given last is offered again). _My lists_: the account's lists and groups; a list's links; copying a
  list's, a group's or a link's address; who can open a list; adding a list to a group.
- **Groups in the popup** (_My lists_): **New group** (with who can open it: private unless
  chosen otherwise), and **Edit group** for a group the account may change: its name, who
  can open it, adding lists, their order (drag, or the arrows), taking a list out, deleting
  the group. A group never changes its lists or who can open them.
- **The right-click menu**, on a page or a link: **Save to listlinkedin** with the six lists
  saved to last, and **Choose a list…**, which opens the popup in a small window about that
  page or link, then **Save open tabs…** and **Save from history…**. On the toolbar button:
  **Copy link to "…"** (the list saved to last), the same two, and **Open my lists**.
- **Saving several pages at once** (`picker.html`, from the popup's "Save several" links or
  the right-click menu's two entries):
  tick pages among the open tabs or in the history, choose a list or a new one, and they are
  saved as one change. The page asks for the permission to read the tabs or the history the
  first time; the options page takes it back.
- **Keyboard shortcuts**, each one changeable in the browser's own settings (the options page
  lists them and opens those settings):

  | Suggested key | What                                         |
  | ------------- | -------------------------------------------- |
  | `Alt+Shift+L` | Open the popup for this page                 |
  | `Alt+Shift+D` | Save this page to the list you saved to last |
  | `Alt+Shift+C` | Copy the link of the list you saved to last  |

A menu entry and the last two shortcuts open nothing. A mark on the toolbar button says how
it went: `✓` for a moment, or `!` until the popup is opened, which then says what went wrong
(`src/lib/feedback.ts`). The shortcuts act on the list saved to last and never pick another.

Copying a link never changes who can open the list. That changes only when the user picks
another answer under "Who can open it" and chooses **Change** (invariant 2 in
[CLAUDE.md](../CLAUDE.md)). What an account may do with a list comes from the server
(`permissions`), which decides again on every request.

## What is in it

| Path                                    | What                                                                                          |
| --------------------------------------- | --------------------------------------------------------------------------------------------- |
| `popup.html`, `src/popup/`              | The toolbar popup, and "Choose a list…" as a window (`popup.html?url=…&title=…`)              |
| `welcome.html`, `src/pages/welcome/`    | Opened once after install                                                                     |
| `options.html`, `src/pages/options/`    | The connected account, disconnecting, the shortcuts, and what the picker may read             |
| `picker.html`, `src/pages/picker/`      | Saving several pages at once, from the open tabs or the history                               |
| `src/background/`                       | The background script: a service worker in Chrome, an event page in Firefox                   |
| `src/background/menus.ts`, `actions.ts` | The right-click menus, and what they and the shortcuts do                                     |
| `offscreen.html`, `src/offscreen/`      | Chrome only: the hidden document that copies for the service worker (`src/lib/clipboard.ts`)  |
| `src/content/`                          | The content script. It runs on the listlinkedin site only                                     |
| `src/lib/`                              | Everything the pages and scripts share: the API client, storage, connecting, lists, clipboard |
| `src/ui/`                               | Shared components and the stylesheet (the web app's colours, from its tokens)                 |
| `scripts/`                              | The build, and the manifest for each browser                                                  |
| `public/icons/`                         | Toolbar icons, rendered from `assets/icon.svg`                                                |

The two browsers get the same pages and scripts. `manifest.json` differs
(`scripts/manifest.ts`): how the background script is declared, the `offscreen` permission
and its page (Chrome), and the add-on ID, minimum version, data declaration and the button's
place on the toolbar (Firefox, which would otherwise keep it in its Extensions menu).

## Signing in: a connected browser

The extension never sees a password ([ADR-020](../docs/v2/adr/ADR-020-connected-browsers.md)):

1. "Connect this browser" makes a random secret (a PKCE verifier), keeps it for the browser
   session, and opens the site's `/connect-browser` page with the secret's hash.
2. That page asks the content script whether this extension started the request, and shows
   nothing to approve otherwise.
3. The user approves on the site. The page hands the content script a one-time code.
4. The background script exchanges the code and the verifier for a session token and keeps
   it in `storage.local`. Every API request sends it as `X-Session-Token`, with
   `credentials: 'omit'`: the site's cookies are never sent.

The page and the content script talk through `src/lib/bridge.ts`, whose other half is
`../frontend/src/utils/extensionBridge.ts`. Change them together.

## Permissions

| Permission                              | Why                                                                                                     |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| the listlinkedin site (host permission) | Calling its API, and the content script on its Connect page                                             |
| `activeTab`                             | The address and title of the tab in front, only when you ask there: the popup, a menu entry, a shortcut |
| `storage`                               | The connection and a copy of your lists' names, in this browser                                         |
| `contextMenus`                          | The right-click menus                                                                                   |
| `clipboardWrite`                        | Copying a list's link from a shortcut or a menu, where no click in a page allows it                     |
| `offscreen` (Chrome only)               | The hidden document that copies, because Chrome's service worker has no clipboard                       |
| `tabs`, `history` (optional)            | The picker: asked for when it is first used, never at install, and given back on the options page       |

Without those two it does not read other tabs or the history. It never reads page content or
the clipboard, and runs no code on the pages you save. What the picker reads stays in the
browser: only the pages you tick are sent.

## Checks

```bash
docker build --target dev -t listlinkedin-extension:dev extension
docker run --rm listlinkedin-extension:dev sh -c \
    "npm run lint && npm run format:check && npm run type-check && npm run test"
docker run --rm -v "$PWD/extension/dist:/app/dist:ro" listlinkedin-extension:dev npm run lint:firefox
bash e2e/run.sh --project=extension
```

- **Unit tests** (Vitest) run against a fake browser API (`src/test/fakeBrowser.ts`) and a
  mocked site (`src/test/site.ts`).
- **`lint:firefox`** is Mozilla's add-on linter on the Firefox build. One warning is expected:
  `UNSAFE_VAR_ASSIGNMENT`, for Vue's own runtime. The extension's code never sets HTML from
  data (`vue/no-v-html` is an error).
- **End-to-end tests** load the Chrome build into Chromium and run against the production
  stack (`../e2e/tests/extension/`). They open the popup as a page about an address
  (`popup.html?url=…&title=…`), and fire menu clicks and shortcuts on the service worker's
  own events, since Playwright can't open a browser's menus or press its shortcuts.
- **By hand**, because no test can drive them: the popup opened from the toolbar on a real
  tab, the menus as the browser draws them, the keys as it binds them, and everything in
  Firefox ([docs/qa-checklist.md](../docs/qa-checklist.md#browser-extension)).

Dependencies are declared in `package.json` and locked in `package-lock.json`. Change them in
a container:

```bash
docker run --rm -v "$PWD/extension":/app -w /app node:26-alpine npm install --package-lock-only <package>
```
