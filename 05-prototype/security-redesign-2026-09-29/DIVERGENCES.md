# Where the built screen differs from the approved drawing — `CR-155-BRC09`

**Built 2026-09-29 by lane SEC-REDESIGN, version `2.396.0`.** The photographs are in
`built-2026-09-29/`, taken through this container's Chromium at deviceScaleFactor 2 by
`10-scripts/cr155_security_redesign_walkthrough.mjs`, against a real stack
(`11-smoke-stack.sh`: PostgreSQL 16 → `migrate` → `seed_demo` → Django → `vite build
--mode compose` → `server.mjs`). Put them beside `approved-proposed-1440.png`,
`approved-proposed-1280.png` and `approved-proposed-420.png`.

**B14 rule 44 is why this file exists**: the drawing says what is on the screen and how
it is arranged, our UI standard says how it is built, and where they disagree the
standard and the component kit win — **and the divergence is stamped here rather than
left for the next reader to rediscover.**

---

## 1 · CLOSED THE SAME DAY — ALL SEVEN VALUES ARE DROPDOWNS

⚠ **THIS SECTION READ *"four of seven values are still typed numbers"* FOR
THREE HOURS AND IT IS NO LONGER TRUE.** It is kept rather than deleted because
the sequence is the point.

The PO ruled every value a dropdown — *"(a) Short dropdown, list chosen from
real use - Dropdown"*. When the screen landed, three of the seven were:
`services.SETTING_LIMITS` published a `choices` list for `pw_min_length`,
`pw_expiry_days` and `session_timeout_minutes`, and served the other four as
`min`/`max` ranges, which the screen therefore drew as typed numbers with the
server's own range stated beside them.

**The screen was NOT given four hand-typed lists to match the drawing sooner.**
That is `DEF-IDN-7501` exactly — a TypeScript literal beside a Python tuple
that no gate in this repo can compare — and it survived weeks of a green suite
the last time. `PolicyValueField` reads the SHAPE the server sent instead.

**The SERVER lane then published the four lists (`c122891af`), and the screen
followed with no front-end edit at all.** Measured in a browser immediately
after: **7 dropdowns of 7**, and the four *"Between 4 and 12 hours."* help
lines gone with the ranges they described — because a dropdown IS its range,
which is the drawing's own reason for deleting them.

**That is the whole argument for reading a shape rather than typing a list,
and it was settled by the clock rather than by anybody's opinion.**

## 2 · CLOSED THE SAME DAY — THE AUDIT CARD SHOWS REAL ROWS

⚠ **THIS SECTION READ *"the card renders its failure state"* AND IT NO LONGER
DOES.** `GET /settings/security-policy/audit` did not exist when the screen
landed; the wire type and the fetch were declared in
`07-frontend/src/api/endpoints.ts` so the card had a contract to be built and
tested against, and the card rendered its FAILURE state — **never zero rows**,
because *"nothing has changed"* and *"we could not find out"* are different
sentences and only one of them was true.

The SERVER lane built the read to that contract, at that path, with those field
names. Walked end to end afterwards: the card opened on its **honest empty
state** (this demo utility had never changed a security setting), the
walkthrough changed *Sign out when idle* and saved, and the reload showed

> `09/29/2026 00:25 | Dana Whitfield | Sign out when idle | 1 hour → 15 minutes`

— a person by name, the setting in the same words the control above it uses,
and both values through `securityValueLabel`, the one formatter that also
labels that dropdown's options. All four states are real: five rows, fewer,
none, and failed.

## 3 · THE `WHEN` COLUMN IS `DateCell`, NOT THE DRAWN `28 Sep, 23:14`

BR-SHL-034: an instant renders in the tenant's zone through one shared component, and no
screen formats a date itself. The drawn string is the shape, not the format — B14 rule 37
makes a drawn figure an illustration — and rule 44 hands the construction to the kit.

## 4 · `8 hours → 1 hour`, WHERE THE DRAWING SHOWS `480 minutes → 60 minutes`

The audit card renders a value through `securityValueLabel`, **the same function that
labels that field's dropdown options** — which is precisely what the approved README asks
for (*"values are rendered the way the control renders them"*). `durationLabel` has said
`1 hour` for 60 minutes since it was written, in all eleven catalogues, and the
dropdown above says the same. Two formatters would satisfy the drawing's literal string
today and drift the first time either side moved; one formatter cannot. The drawn numbers
are illustrations (rule 37).

## 5 · THE APP FRAME IS THE PRODUCT'S, NOT THE DRAWING'S

The drawing's sidebar is a simplified render: no tenant block, no nav icons, no
*Runbooks*, no *Billing plan* tab. The real frame has all four, and B14 rule 44 says the
UI standard wins **including the frame**. Nothing in the drawing's frame was built to.

## 6 · THE PASSWORDS NOTE IS `<Note>`, NOT A SHADED INSET PANEL

The drawing shows the three platform sentences inside a tinted box. The kit's `Note`
(`components/TextBits.tsx`) is the product's one way of saying this — small, muted, no
container — and it is used by 89 sites. Rule 44: the kit decides how a thing is built.
The GROUPING the drawing specifies — those sentences in **Passwords**, in one block,
under the expiry control — is followed exactly.

## 7 · THE AUDIT CARD IS BUILT FROM TOKENS, NOT FROM `<Panel>`

The drawing puts `View all →` on the card's title row, right-aligned, and the kit's
`Panel` renders a bare `<h3>` with no header-action slot. B14 rule 36 says add the
missing piece to the kit — and doing that needs a flex header row written in Tailwind
inside `settingsShared.tsx`, which is **not** on `07-frontend/src/styles/route-b-migrated.txt`:
listing it hands fifteen other Settings screens' bespoke classes to the stricter
`routeBUtilities.test.ts` in the same commit, for one header row. So `SecurityAuditCard.tsx`
is built from the same four tokens `.panel` uses (`--color-surface`, `--color-accent`,
`--space-6`, `--space-4`) and **that file** is on the ledger instead. B14 rule 43 is
satisfied either way: it is a component, not code inlined in a page.

---

## FOUND BY THE PHOTOGRAPH AND FIXED, NOT STAMPED — THE 1280 ROW

⚠ **THE FIRST BUILD PUT TWO CARDS IN THE ROW AT 1280 AND THE DRAWING PUTS
THREE.** The drawing's own 1280 frame is captioned *"three cards still fit"*, so
this is the arrangement the PO checked at that width — and the arrangement is
the drawing's to decide, even under rule 44.

**The arithmetic, because it is sixteen pixels and nobody would guess it:**
1280 − 240 (the sidebar) − 48 (`.view`'s padding at this breakpoint) leaves
**992px** of content. `.settings-grid` is `repeat(auto-fit, minmax(320px, 1fr))`
with a 24px gap, so three columns need **1008px**. The grid dropped to two and
*Signing in* fell under *Passwords*. The drawing's frame was a simplified render
with a narrower rail, which is why it fit there.

**Fixed in the kit, not in the page, and nothing else moved.** `.settings-grid`
now reads `minmax(var(--panel-min, 320px), 1fr)` and `PanelGrid` takes an opt-in
`min`; the Security tab passes `288px`, which makes the sum 912. **The fifteen
other Settings surfaces that compose this grid do not pass it and render
byte-for-byte what they rendered before.** It is a custom property rather than a
second class because B14 rule 21 forbids adding a class to a stylesheet, and
writing the whole `grid-template-columns` as a Tailwind utility inside
`settingsShared.tsx` would put an undeclared class in a file that is not on the
migration ledger — which G31 refuses, and listing that file hands fifteen
screens' bespoke classes to the stricter compiler check for the sake of one
number.

**No test could have found this and no gate did.** `tsc`, eslint, 95 test cases,
G31 and G134 were all green over a screen whose third card was in the wrong
place, because jsdom has no layout and no check in this repo reads rendered
output. It was found by looking at the 1280 photograph beside the 1280 drawing —
CLAUDE.md law 6, twice in one lane.

---

## NOT A DIVERGENCE — FOUND THE SAME WAY, AND FILED RATHER THAN FIXED

⚠ **At 420 the sidebar does not drop, and the drawing says it should.** It is the app
FRAME and not this screen: `AppShell.css` has no media query below 1024px that touches
`.sidebar` — only `.view`'s padding shrinks — so a 240px rail pushes **all 114 screens**
off a phone viewport, not just this one. Filed as **`DEF-SHL-7827`**, not fixed here.
The cards themselves stack correctly at 420, which is the part this lane owns.

**It was found by exactly the thing CLAUDE.md law 6 says finds things and nothing else
does**: photographing the running app and laying the shot next to the drawing. Every
gate, `tsc`, eslint and 95 test cases were green over it.
