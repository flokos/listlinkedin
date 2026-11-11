# Manual QA checklist

The end-to-end suite ([e2e/](../e2e/)) covers the flows in five browser configurations and
runs axe on every page and dialog, in light and dark, on desktop and a phone. It can't judge
what real assistive technology and real devices do. Run this list before a release, or after
changes to the UI shell, dialogs or forms. Use the production stack
(`docker compose -f compose.prod.yaml up --build -d`) with two accounts, one of them added to
the other's list as an editor. Rewritten for V2 in task 9.3; note the date, browser and result
of each run in the release PR.

## Screen readers

Run each with **VoiceOver** (macOS Safari and iOS Safari) and **NVDA** (Windows Firefox).

**Accounts**

- [ ] Sign up: field errors are read next to their fields; after signing up, the "check your
      inbox" message is announced.
- [ ] Open the verification link: "Your email is verified" is announced as the page heading.
- [ ] Sign in with a wrong password: the error is announced, and focus stays in the form.
- [ ] Account page: each section heading is reachable with heading navigation; Delete account
      reads its type-to-confirm field and keeps the button's disabled state clear.

**Lists**

- [ ] My lists: the heading, then each list with its role, visibility and link count.
- [ ] Create a list: focus lands on the new list's heading.
- [ ] Add a link: errors are read next to the field; "Link added" is announced; while its
      details are fetched the tile says "Fetching details…".
- [ ] A tile's ⋮ menu reads as a menu (Open, Copy short link, Details, Move up, Move down, Move
      to top, Move to bottom, Move to position…, Move to another list…, Edit, Delete).
- [ ] Reorder with "Move up": the new position is announced, and focus stays on the moved link.
- [ ] Grid and list view: the toggle reads its state; the links read in order in both.
- [ ] Edit a link: the page's own title is offered as a button that says what it fills in.
- [ ] Share: "Who can see this list" reads as a radio group; "Allow copies" as a switch; the
      QR code has a description; adding a person reads the role choice and any error.
- [ ] Settings: each section heading; saving announces the result; a refused description save
      reads why.
- [ ] History: the versions read as a list with who and when; choosing one announces its
      changes; Restore asks for confirmation.
- [ ] Make a copy: the dialog explains what a copy is; afterwards "Copied from …" is read
      under the title.
- [ ] Report…: the reasons read as a radio group; a missing reason is announced.

**Groups and Explore**

- [ ] A group: the sidebar reads as navigation with its lists; choosing one moves focus to the
      list's heading; lists not everyone sees say so.
- [ ] Reorder lists: the drag handles are hidden; Move up, Move down and Remove are reachable
      and announce the result.
- [ ] Explore: the tabs, the search field and Sort by are labelled; each tag reads as a toggle
      with its state; the result count is announced after a search.

**Everywhere**

- [ ] Navigating with the menu announces each new page title, and focus is on its heading.
- [ ] The expiry chip reads the exact date as well as "Expires in N days".
- [ ] Toasts are announced once and don't take focus.

## Real devices

- [ ] iPhone (Safari): reorder tiles by touch drag (can't be automated, risk 22), and with the
      ⋮ Move items.
- [ ] iPhone: open a shared link; use the native share sheet from "Share"; copy a short link
      and paste it into Messages.
- [ ] Scan the QR code with another phone's camera. It opens the list.
- [ ] Android (Chrome): the same checks.
- [ ] A group on a phone: the drawer opens, switching lists closes it, Escape or Back closes
      it.
- [ ] Notched phones: nothing hides under the notch or the home indicator, in portrait and
      landscape.

## Display settings

- [ ] 200% browser zoom on desktop: no overlapping or cut-off content, and no horizontal
      scrolling at 1280px (tiles, the group sidebar, Explore, Settings).
- [ ] Windows High Contrast / forced colours: buttons, fields, focus rings, chips, tag toggles
      and the tile shimmer stay visible.
- [ ] OS "reduce motion" on: no route, list or shimmer animations.
- [ ] Dark mode follows the OS, and the theme menu overrides it. Sites' icons stay visible on
      their light plate.

## Browser extension

Since task 11.2. The automated tests load the extension into Chromium, open its popup as a
page, and fire menu clicks and shortcuts on the background script's own events. Nothing
automated opens the popup from the toolbar, opens a right-click menu, presses a shortcut or
loads the extension into Firefox.
Run this list in **Chrome** and in **Firefox** with a build for the stack under test
([extension/README.md](../extension/README.md)), before a release that changes `extension/`
or the Connect page.

- [ ] Install: the welcome page opens by itself. Installed from a file, Firefox's prompt
      names the site and says the extension sends browsing activity and website content (a
      temporary add-on shows no prompt).
- [ ] Connect from the welcome page while signed out on the site: sign in, land on "Connect
      this browser?", approve, and the welcome page says the browser is connected. The email
      about the new connection arrives.
- [ ] Open a page, click the toolbar button: the popup shows that page's title and address.
- [ ] Save it to a new list, then save another page: the list used last is chosen already.
- [ ] Save the same page again: "This URL is already in the list."
- [ ] Open the popup on a new tab, on the browser's settings page and on the site itself: each
      says why the page can't be saved.
- [ ] Popup with the keyboard only: Tab reaches every control, arrows move through the lists,
      Enter saves, and focus is always visible. Light and dark both read well.
- [ ] Options: the account's email, then Disconnect. The site's account page no longer lists
      the browser.
- [ ] Disconnect on the site's account page instead: the popup says the browser was
      disconnected and offers to connect again.
- [ ] Restart the browser: still connected (in Firefox, only for an add-on installed for
      good, not a temporary one).

Menus, shortcuts and sharing (since task 11.3):

- [ ] The toolbar button: in Firefox it is on the toolbar right after installing; in Chrome it
      is in the Extensions menu until pinned.
- [ ] Right-click a page: **Save to listlinkedin** lists the lists saved to last, the latest
      first, then **Choose a list…**. Pick a list: nothing opens, the button shows `✓` for a
      few seconds, and the page is in the list under the tab's title.
- [ ] Right-click a link and pick a list: the link's address is saved, not the page's. On the
      site the link gets the linked page's own title after a moment.
- [ ] Pick the same list for the same page again: the button shows `!`. Open the popup: it
      says the page was already in the list, and the `!` is gone.
- [ ] **Choose a list…** on a link: a small window opens about that link (its address is
      shown, the title is empty). Save from it.
- [ ] Not connected: the menu has one entry, **Save to listlinkedin…**, which opens that
      window with "Connect this browser". After connecting, the menu lists the lists without
      a restart.
- [ ] Right-click the toolbar button: **Copy link to "…"** names the list saved to last and
      puts its address on the clipboard; **Open my lists** opens the site's lists page.
- [ ] **Save open tabs…** and **Save from history…**, under "Save to listlinkedin" on a page
      and on the toolbar button, each open the page for saving several, on that source.
- [ ] Shortcuts (`Alt+Shift+L`, `Alt+Shift+D`, `Alt+Shift+C` unless changed): the popup
      opens; the page is saved to the list saved to last (`✓`); that list's address is on the
      clipboard (`✓`). After copying a private list's link, the popup says once that only
      people added to it can open it.
- [ ] Options lists the three shortcuts with the keys the browser shows in its own settings,
      and **Change shortcuts** opens those settings. Change one there and use it.
- [ ] Popup, **My lists**: open a list, open one of its links, **Copy link**, and paste: the
      list's address. An account the list isn't shared with still can't open it.
- [ ] As the owner: change "Who can open it" to **Anyone with the link** and choose
      **Change**. A private window can open the pasted address now. Change it back.
- [ ] Choosing **Public** with an unverified email address: the popup says to verify it, and
      nothing changes.
- [ ] A list the account can only view: no "Who can open it" choice, only the sentence.
- [ ] **Add to a group**, then on the site the group shows the list. Add it again: "already
      in the group".
- [ ] Popup, **Save several: open tabs**: a page opens and reads nothing yet. **Allow reading
      your open tabs**: the browser asks, and after "Allow" the tabs are listed, without
      private windows, the browser's own pages or listlinkedin itself (since task 11.5).
- [ ] Refuse the browser's question instead: the page says it can't show the tabs.
- [ ] Tick a few, choose **A new list…**, save: the sentence says how many were saved, the
      list has them in the order shown, and its history shows one change.
- [ ] A new list, in the popup and in the picker, has **Who can open it**: "Only people you
      add" the first time. Choose **Anyone with the link**: the list opens in a private
      window, and the next new list offers that answer first.
- [ ] **History**: its own question; the latest visits come first; search narrows them. Save
      some that are in the list already: "… were already there".
- [ ] Tick more than a list has room for: the note says how many will fit, and the result
      says how many didn't.
- [ ] Options, "Open tabs and history": **Stop reading …** for each; the picker then asks
      again.
- [ ] After saving a page: **Copy short link** and paste it in a private window: it opens the
      page only if that visitor may open the list.
