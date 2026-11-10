# Browser extension

The listlinkedin extension for Chrome and Firefox: save the page you are on into one of your
lists, without opening the site. It is a second client of the same API as the web app in
`../frontend`. Vue 3 and TypeScript, built with Vite; no Vuetify.

A build talks to **one** listlinkedin site, fixed when it is built (`LL_BASE_URL`). The
manifest grants the extension that site and no other.

## Build and load it

Everything runs in Docker, from the repository root.

```bash
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
  rebuild, press the extension's reload button there.
- **Firefox:** open `about:debugging#/runtime/this-firefox`, choose **Load Temporary Add-on…**
  and pick `extension/dist/firefox/manifest.json`. Firefox removes a temporary add-on when it
  closes. Release Firefox installs for good only what Mozilla has signed; Developer Edition,
  Nightly and ESR can turn that check off (`xpinstall.signatures.required`).

## What is in it

| Path                                 | What                                                                               |
| ------------------------------------ | ---------------------------------------------------------------------------------- |
| `popup.html`, `src/popup/`           | The toolbar popup: "Connect this browser", or save this page to a list             |
| `welcome.html`, `src/pages/welcome/` | Opened once after install                                                          |
| `options.html`, `src/pages/options/` | The connected account, and disconnecting                                           |
| `src/background/`                    | The background script: a service worker in Chrome, an event page in Firefox        |
| `src/content/`                       | The content script. It runs on the listlinkedin site only                          |
| `src/lib/`                           | Everything the pages and scripts share: the API client, storage, connecting, lists |
| `src/ui/`                            | Shared components and the stylesheet (the web app's colours, from its tokens)      |
| `scripts/`                           | The build, and the manifest for each browser                                       |
| `public/icons/`                      | Toolbar icons, rendered from `assets/icon.svg`                                     |

The two browsers get the same pages and scripts. Only `manifest.json` differs
(`scripts/manifest.ts`): how the background script is declared, and Firefox's add-on ID,
minimum version and data declaration.

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

| Permission                              | Why                                                                           |
| --------------------------------------- | ----------------------------------------------------------------------------- |
| the listlinkedin site (host permission) | Calling its API, and the content script on its Connect page                   |
| `activeTab`                             | The address and title of the tab in front, only when you open the popup on it |
| `storage`                               | The connection and a copy of your lists' names, in this browser               |

It does not read other tabs, history or page content, and runs no code on the pages you save.

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
  (`popup.html?url=…&title=…`).
- **By hand**, because no test can drive them: the popup opened from the toolbar on a real
  tab, and everything in Firefox.

Dependencies are declared in `package.json` and locked in `package-lock.json`. Change them in
a container:

```bash
docker run --rm -v "$PWD/extension":/app -w /app node:26-alpine npm install --package-lock-only <package>
```
