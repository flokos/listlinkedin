# The browser extension

The listlinkedin extension saves pages into your lists and shares your lists without opening
the site: from the button on the browser's toolbar, the right-click menu and keyboard
shortcuts. It works in Chrome, Edge and other Chromium browsers, and in Firefox 140 or later.

It is not in the Chrome Web Store or on addons.mozilla.org. You install it from a file, as
this page describes. Developers building it themselves: see
[extension/README.md](../extension/README.md).

## Get it

Each [GitHub Release](https://github.com/flokos/listlinkedin/releases) since `v2.3.0` carries
the extension, built for `https://listlinkedin.versioncontrol.xyz`:

| File | For |
|---|---|
| `listlinkedin-<version>-chrome.zip` | Chrome, Edge, Brave and other Chromium browsers |
| `listlinkedin-<version>-firefox-signed.xpi` | Firefox: signed by Mozilla, stays installed |
| `listlinkedin-<version>-firefox.zip` | Firefox, unsigned: only as a temporary add-on |

`<version>` is the extension's own version (`1.0.0` first), not the site's. An extension
talks to one site, fixed when it is built. For another site (a development stack, your own
installation), build it yourself with `LL_BASE_URL` set
([extension/README.md](../extension/README.md#build-and-load-it)).

## Install it

### Chrome, Edge and other Chromium browsers

1. Unzip `listlinkedin-<version>-chrome.zip` into a folder you will keep. The browser loads
   the extension from that folder every time it starts.
2. Open `chrome://extensions` (`edge://extensions` in Edge) and turn on **Developer mode**.
3. Choose **Load unpacked** and pick the folder.
4. Open the Extensions menu (the puzzle piece) and pin **listlinkedin**, so its button and
   the mark it shows after a save are on the toolbar.

The browser may remind you at start that an extension in developer mode is on. That is
expected for an extension that didn't come from the store.

### Firefox

**Signed (`…-firefox-signed.xpi`):** open the file with Firefox (drag it into a window, or
`about:addons` → the gear → **Install Add-on From File…**) and choose **Add**. Firefox names
the site the add-on may reach and says that it sends browsing activity and website content:
the address and the title of each page you save.

**Unsigned (`…-firefox.zip`, or your own build):** release Firefox only loads it until it
closes. Unzip it, open `about:debugging#/runtime/this-firefox`, choose **Load Temporary
Add-on…** and pick `manifest.json` in the folder. Firefox Developer Edition, Nightly and ESR
can install it for good after `xpinstall.signatures.required` is set to `false` in
`about:config`.

## Connect it to your account

The welcome page opens after the install; later, the toolbar button offers the same.

1. Choose **Connect this browser**. The site opens on its Connect page; sign in if it asks.
2. Check the browser's name and choose **Connect**. No password is typed into the extension.
3. The extension is connected until you disconnect it, change your password, or leave it
   unused for 90 days; at the latest for a year. Your account page lists the connected
   browsers and can disconnect each one. Every new connection is also emailed to you.

## Use it

- **The toolbar button** opens the popup. _Save this page_: pick a list or make a new one
  (choosing who can open it), and save. _My lists_: look into a list, copy its link or a
  link's short link, change who can open it, put its links in another order or remove them;
  make groups and change them.
- **Right-click** a page or a link: **Save to listlinkedin**, then one of the lists you saved
  to last, **Choose a list…**, **Save open tabs…** or **Save from history…**. Right-click
  the toolbar button for **Copy link to …**, the same two "Save …" entries and **Open my
  lists**.
- **Keyboard:** `Alt+Shift+L` opens the popup, `Alt+Shift+D` saves the page to the list you
  saved to last, `Alt+Shift+C` copies that list's link. Change them in the browser
  (`chrome://extensions/shortcuts`; Firefox: `about:addons` → the gear → **Manage Extension
  Shortcuts**). A browser leaves out a shortcut that something else already uses.
- After a right-click or a shortcut, the button shows `✓` when it worked and `!` when it
  didn't; the popup then says why, once.

Copying a link never changes who can open a list. Only your choice under "Who can open it"
does.

## What it may do, and what it sends

| Permission | Asked | Why |
|---|---|---|
| The listlinkedin site it was built for | At install | Its only connection. It reaches no other site |
| The tab in front (`activeTab`) | At install; used only when you act | The address and title of the page you save |
| Right-click menus, storage, copying to the clipboard | At install | The menus; staying connected; copying a link from a menu or a shortcut |
| Open tabs (`tabs`) | When you first use "Save open tabs" | Listing your tabs for you to tick |
| History (`history`) | When you first use "Save from history" | Listing visited pages for you to tick |

- It **sends** to the site: the address and title of each page you save, and what you do to
  your lists and groups there. Tabs and history are read inside the browser; only the pages
  you tick are sent. It has no analytics and loads no code from anywhere.
- It **keeps** in the browser: the connection (a token for the site, your email address,
  the browser's name), your lists' names and which ones you used last, and your last answer
  to "Who can open it" for a new list. **Disconnect** on its options page, or on your
  account page, removes them.
- The options page takes the tabs and history permissions back (**Stop reading …**).

## Update or remove it

- **Update:** download the new release's file. Chrome: replace the folder's contents with
  the new zip's and press the reload arrow on `chrome://extensions`. Firefox: install the
  new `.xpi` over the old one. You stay connected. There are no automatic updates.
- **Remove:** disconnect first (options page), so the site forgets this browser at once.
  Then remove the extension on `chrome://extensions` or `about:addons`.

## When something is wrong

| What you see | What to do |
|---|---|
| Firefox: "This add-on could not be installed because it has not been verified" | That file is unsigned. Use the `-signed.xpi`, or load it as a temporary add-on |
| The popup says the extension can't reach listlinkedin | Chrome: `chrome://extensions` → Details → **Site access** must allow the site. Firefox: `about:addons` → listlinkedin → **Permissions**. Or choose **Allow access** where the extension offers it |
| The Connect page says "Open this page from the extension" | It was opened by hand or reloaded. Start again from the extension's **Connect this browser** |
| "This browser isn't connected" after it worked before | The connection ended (password change, 90 days unused, disconnected on the site). Connect again |
| No **Save to listlinkedin** in the right-click menu | Reload the extension; menus are made when it starts. On the browser's own pages there is none |
| A shortcut does nothing | Another extension or the browser has it. Set another one in the browser's shortcut settings |
| A page can't be saved | Only `http` and `https` pages are links; the browser's own pages and listlinkedin itself are not |

## For maintainers: releasing it

`extension/package.json` holds the extension's version. **Raise it in any release that
changes `extension/`**: Mozilla signs each version once, and browsers treat a file with the
same version as the same extension.

Publishing a GitHub Release runs
[`extension-release.yml`](../.github/workflows/extension-release.yml), which builds the
extension from the release's tag for production's address and attaches the two zips. It can
be run again for a tag from the Actions page. It never touches the deployment
([ADR-018](v2/adr/ADR-018-pull-based-deployment.md)).

**Mozilla signing** ([ADR-021](v2/adr/ADR-021-extension-distribution.md)) happens in the same
workflow when two repository secrets exist; without them the step is skipped and says so.

1. Sign in on [addons.mozilla.org](https://addons.mozilla.org/developers/addon/api/key/) with
   the Mozilla account that should own the add-on, and generate API credentials.
2. Store them as repository secrets: the "JWT issuer" as `AMO_JWT_ISSUER`, the "JWT secret"
   as `AMO_JWT_SECRET` (`gh secret set AMO_JWT_ISSUER`, or Settings → Secrets and variables
   → Actions). They are never written to a file or a log.

The workflow then sends the Firefox build and its source to Mozilla as an **unlisted**
add-on: it is checked automatically and signed, usually within minutes, and is not put on
addons.mozilla.org. The signed file is attached to the release as
`listlinkedin-<version>-firefox-signed.xpi`. The add-on's ID
(`extension@listlinkedin.versioncontrol.xyz`) belongs to the first Mozilla account that
signs it.

Every pull request's `checks` job also keeps both zips for 14 days as the `extension`
artifact (unsigned, for production's address), to try a change by hand.
