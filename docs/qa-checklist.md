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
