# Settings → Security, redesigned — APPROVED by the PO, 2026-09-29

**These PNGs are the specification. Build from the IMAGES (B14 rule 42), not from this
text.** The text below is an index so a reader knows which file to open and what was
ruled; it is not the screen. *"When you use images to create screens your accuracy is
higher; hence dont create screens using only Text"* (PO, 2026-09-13).

| File | What it is |
|---|---|
| `approved-proposed-1440.png` | **The screen.** Full app frame at 1440. |
| `approved-cards-1440.png` | The three cards, close up. |
| `approved-auditcard-1440.png` | The Audit log card, close up. |
| `approved-proposed-1280.png` | The same screen at 1280 — three cards still fit. |
| `approved-proposed-420.png` | Phone width — cards stack, sidebar drops. |
| `today-1440.png` | What ships today, for comparison. Do NOT build this one. |

⚠ **THE TYPEFACE IN THESE IMAGES IS WRONG AND THE LAYOUT IS RIGHT.** The renderer could
not reach `fonts.googleapis.com` through this container's proxy (`document.fonts.size`
came back **0**), so every image shows the `system-ui` fallback rather than **Archivo**.
Build with the product's own font token; do not match the letterforms you see.
Everything else — spacing, colour, control types, grouping, order — is drawn to
`07-frontend/src/styles/tokens.css` and is the specification.

⚠ **B14 rule 44 still wins over these drawings.** They were drawn ON our tokens, so no
disagreement is expected — but where one appears, the UI standard and the component kit
decide, and the divergence is stamped here.

---

## What the PO ruled, 2026-09-29

Three questions were put to them in plain English with worked figures. All three answered:

**Q1 — every value becomes a dropdown.** Verbatim: *"(a) Short dropdown, list chosen from
real use - Dropdown"*. ⚠ **The list is chosen from what utilities actually hold, so that
NOBODY MOVES.** That is the whole point of the answer and it is a precondition, not a
detail: converting a range to a list withdraws every value left off it, and on
2026-09-28 exactly that moved utilities from 480 minutes to 60 and signed their staff out
seven hours earlier. **Count first. Draw the lists from the count. Then build.** The count is
`value-census-2026-09-29.md` beside this file, measured by
`10-scripts/cr145_security_dropdown_value_census.py` (READ-ONLY). ⚠ **Its figures are
DEMO** — this container holds no production data — so it proposes the lists and proves
the counter finds an awkward value; **the lists that ship are drawn from the same command
run against production**, and that command is in it.

**Q2 — the audit log stays on this screen.** Verbatim: *"keep it here only in this
screen"*, then *"i only need bigger real estate for audit logs - can you give a card
layout for it"*. So it is a **full-width card below Save**, showing the last five changes
**made on this tab** — not the platform-wide log, which would be noise here. `View all →`
goes to the whole log.

**Q3 — the tick boxes stay tick boxes.** Verbatim: *"(a) Keep them as checkboxes"*. A
yes/no is a tick box everywhere in this product; making three of them dropdowns would
break this screen's agreement with every other screen.

---

## The grouping, and why each field moved

Today: Password policy · Access · Stay signed in, then Lockout · Audit log. Four, three,
two, then two and one — a ragged grid with an empty column and Save below the fold.

Approved: **three cards of four, four and three controls**, one row, Save in view.

| Card | Holds | Why |
|---|---|---|
| **Passwords** | Minimum length · the two rules · Expire passwords | unchanged in substance |
| **Sessions** | Sign out when idle · Hard limit · Offer "Stay signed in" · Stay signed in for | *Stay signed in* answers **how long a session lasts**, so it belongs with the timeout and the hard limit rather than in a card of its own |
| **Signing in** | Wrong passwords · Lockout length · Allowed addresses | lockout and the address list both answer **who gets in**; today they sit in different rows |

Also drawn, each one deliberate:

- **The `SECURITY` kicker is gone** — it sat 40px under a tab already reading *Security*.
- **The page description is the utility's name**, not *"Configure the platform. Every
  change is audit-logged."* The second sentence is rationale (rule 33: zero words on
  screen) and the audit card says it anyway.
- **The platform facts moved into Passwords** — *the last 5 passwords are blocked, a
  temporary password lasts 7 days* sat in the **Access** card and are about passwords.
- **`(optional)` left the address label.** We mark what is required.
- **Every "Between 4 and 12 hours." help line is gone** — a dropdown IS its range. The one
  help line kept is *"Applies to the next sign-in."* on Hard limit, because that is a
  fact a clerk cannot infer from the control.
- **Units are inside the option**: `12 hours`, `5 tries`, `15 minutes`, `30 days`,
  `8 characters` — so the value reads as a sentence and the label stays ≤3 words.

## The Audit log card

Full width, under Save. Columns **WHEN · WHO · SETTING · CHANGE**, five rows, old value
struck through and new value bold, `View all →` at the top right.

⚠ **Rule 31 applies: no database id is ever the visible value of a field.** People are
named, settings are named in the same words the controls above use, and values are
rendered the way the control renders them (`480 minutes → 60 minutes`, not a raw integer).

⚠ **The second drawn row is real and is the reason this card is worth the space:**
`Product upgrade · Sign out when idle · 480 minutes → 60 minutes`. `identity/0007` and
`0008` write exactly that row for every utility they move, attributed to the migration
rather than to a person. A clerk at a moved utility asking *"why am I being signed out
earlier?"* finds the answer on this screen.

## Source

`10-scripts/` has no renderer for this; the drawing is an HTML artifact rendered with the
container's Chromium at deviceScaleFactor 2. The artifact is the PO-approved one shown in
the working session of 2026-09-29.
