# Manual QA checklist

The end-to-end suite ([e2e/](../e2e/)) covers the flows in five browser configurations and
runs automated accessibility checks. It can't judge what real assistive technology and real
devices do. Run this list before a release, or after changes to the UI shell, dialogs or
forms. Use the production stack (`docker compose -f compose.prod.yaml up --build -d`).

## Screen readers

Run each with **VoiceOver** (macOS Safari and iOS Safari) and **NVDA** (Windows Firefox).

- [ ] Home: the heading and the create form are announced. An empty submit reads the error.
- [ ] Create a list. The "Save your edit link" dialog is announced with its title, the
      checkbox and button states are clear, and focus stays inside the dialog.
- [ ] After closing it, the list page title is announced and focus is on the heading.
- [ ] Add a link. Errors are read next to the field, and the "Link added" toast is announced.
- [ ] The link card menu reads as a menu with "Edit" and "Delete" items.
- [ ] Navigating with the menu announces each new page title.
- [ ] The expiry chip reads the exact date as well as "Expires in N days".
- [ ] Share dialog: the QR code has a meaningful description.

## Real devices

- [ ] iPhone (Safari): open a shared link, and use the native share sheet from "Share".
- [ ] iPhone: copy a short link and paste it into Messages.
- [ ] Scan the QR code with another phone's camera. It opens the list.
- [ ] Android (Chrome): the same three checks.
- [ ] Notched phones: nothing hides under the notch or the home indicator, in portrait and
      landscape.

## Display settings

- [ ] 200% browser zoom on desktop: no overlapping or cut-off content, and no horizontal
      scrolling at 1280px.
- [ ] Windows High Contrast / forced colours: buttons, fields, focus rings and chips stay
      visible.
- [ ] OS "reduce motion" on: no route or list animations.
- [ ] Dark mode follows the OS, and the theme menu overrides it.
