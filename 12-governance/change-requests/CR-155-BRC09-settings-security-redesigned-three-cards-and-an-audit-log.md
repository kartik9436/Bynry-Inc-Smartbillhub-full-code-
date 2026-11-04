# CR-155-BRC09 — Settings → Security redesigned: three cards, Save in view, and the audit log on the screen

**Raised:** 2026-09-29, by the Product Owner, reviewing the live Settings → Security tab
and being put three questions in plain English with worked figures. They answered all
three and approved a drawing of the result.
**Branch:** `claude/brave-dijkstra-xgfsgz` (`BRC09`). Number from
`10-scripts/allocate.py cr` against the remote; reserved in
`12-governance/14-id-reservations.md` before the lane started.
**Version:** `2.396.0` (`allocate.py version --bump change`, re-verified at push time — `2.394.0`
AND `2.395.0` were both taken by siblings while this lane worked, which is exactly what
the allocator exists to catch; both of this lane's earlier arithmetic was right and both
answers were stale).
**Classification:** ⚠ **MAINTENANCE, borrowing exactly one thing from Build — the
drawing step.** The Product Owner's own test (`12-governance/22-product-maintenance-process.md`):
*can a user do this task in the product today?* A System Admin can open Settings →
Security and change every one of these settings today, so the answer is **yes**. The
maintenance process names the redesign case deliberately — *"a live screen redrawn end
to end is MAINTENANCE"* — and warns that a lane following Build loses reproduce, blast
radius, regression and the reporter. It is nevertheless filed as a **CR and not a
defect**, because nothing was broken: the PO asked for a different arrangement and
approved it. `13-change-process.md` §1.
**Screen-shaped:** yes. **Screen:** `S8` → Security, at `/{tenant}/settings/security`.
**Drawings:** `05-prototype/security-redesign-2026-09-29/` — **six PNGs, and they are the
specification** (B14 rules 42 and 44). The README beside them is an index, never the
screen.
**Divergences from the drawing:** `05-prototype/security-redesign-2026-09-29/DIVERGENCES.md`,
seven of them, two CLOSED the same day and five stamped with their reason (B14 rule 44).

---

## 0 · What arrived, in the requester's words

Three questions, each put with a worked figure, each answered:

> **Q1 — every value becomes a dropdown.** *"(a) Short dropdown, list chosen from real
> use - Dropdown"*

> **Q2 — the audit log stays here.** *"keep it here only in this screen"*, then
> *"i only need bigger real estate for audit logs - can you give a card layout for it"*

> **Q3 — the tick boxes stay tick boxes.** *"(a) Keep them as checkboxes"*

⚠ **Q1 CARRIES A PRECONDITION AND IT IS NOT A DETAIL.** *"list chosen from real use"*
means the list must be drawn from what utilities actually hold, **so that nobody moves**
— converting a range to a list withdraws every value left off it, and on 2026-09-28
exactly that moved utilities from 480 minutes to 60 and signed their staff out seven
hours earlier. The count is `value-census-2026-09-29.md` beside the drawings, and its
figures are **DEMO**: this container holds no production data, so it proposes the lists
and proves the counter can find an awkward value. **The lists that ship come from the
same command run against production.**

## 1 · What was wrong with the screen, measured

Five cards in a three-then-two grid: Password policy · Access · Stay signed in, then
Lockout · Audit log — four, three, two, then two and one controls. That left

* an **empty column** in the top row,
* a whole **card whose entire content was one button** (*View audit log →*),
* and **Save below the fold**.

## 2 · What was built

**Three cards of four, four and three controls, in one row**, then the Save row, then a
**full-width Audit log card**.

| Card | Holds | Why |
|---|---|---|
| **Passwords** | Minimum length · the two rules · Expire passwords · the platform facts | unchanged in substance; the two platform facts MOVED here from *Access*, because they are about passwords |
| **Sessions** | Sign out when idle · Hard limit · Offer "Stay signed in" · Stay signed in for | *Stay signed in* answers **how long a session lasts**, which is the same question as the timeout and the hard limit; a card of its own made it look like a different one |
| **Signing in** | Wrong passwords · Lockout length · Allowed addresses | the lockout pair and the address list both answer **who gets in**; today they sat in different ROWS |

Copy changes, each drawn and each deliberate:

* the `SECURITY` kicker is **gone** — it sat 40px under a tab already reading *Security*;
* the page subtitle is the **utility's name**, not *"Configure the platform. Every change
  is audit-logged."* — the first half restates the `<h1>` above it (B14 rule 32) and the
  second half is rationale (rule 33, zero words on screen);
* `(optional)` left the address label — we mark what is REQUIRED;
* **every** *"Between 4 and 12 hours."* help line goes where the control is a dropdown,
  because a dropdown IS its range. The one kept is *"Applies to the next sign-in."* on
  Hard limit — a fact a clerk cannot read off the control;
* the standing self-lockout warning is **removed, not shortened**: fifteen words
  explaining why the product may refuse is rationale. The refusal itself still renders,
  with the IP the server saw, at the moment it happens;
* **units live inside the option** — `12 hours`, `5 tries`, `15 minutes`, `30 days`,
  `8 characters` — which is what lets every label stay a name of three words or fewer.

**Thirty catalogue keys moved through `10-scripts/i18n_fanin.py` in all eleven
languages**: 22 new, 8 rewritten, 10 retired. Every catalogue holds 21,088 keys, parity
checked by the tool before a byte was written.

## 3 · Why an over-cap drawn sentence was built as drawn

Four sentences on the approved drawing run past B14 rule 33's six-word cap for a fact —
*"Applies to every password set from now on."*, *"How long a signed-in clerk stays signed
in."*, *"New rules apply to the next password change."* and *"The last five changes on
this tab."*

**They were built as drawn**, and rule 33 itself is why. Its own text says: *"an over-cap
string is not automatically wrong and not automatically lawful — check whether it has
been ruled before touching it"*, and it records two 2026-09-24 rulings pointing in
opposite directions, the move-out's four path names left as drawn and the transfer's five
titles shortened. **The Product Owner was shown these images, with these strings on them,
and approved them on 2026-09-29.** Shortening them afterwards is the copy audit reading
only the cap that the rule explicitly warns against.

⚠ **`DEF-IDN-7810` NAMES FIVE OLDER SENTENCES ON THIS SCREEN AND THIS BUILD MOVED FOUR OF
THEM — NOT AS A FIX, AS A CONSEQUENCE, AND THE ROW IS LEFT OPEN.** Its five are
`passwordHint`, `accessHint`, `auditHint`, `appliesNext` and the allowlist note. After
this change:

| String | What happened | Still over the cap? |
|---|---|---|
| `passwordHint` | untouched, and drawn identically | yes — and ruled 2026-09-29 |
| `accessHint` | **retired** — the Access card is gone | n/a |
| the allowlist note (`selfLockoutNote`) | **retired** — rationale, rule 33 | n/a |
| `allowlistHelp` | shortened to *"Comma-separated IPv4 blocks. Empty allows all."* | no — 4 and 3 words |
| `appliesNext` | rewritten to the drawn sentence | yes — and ruled 2026-09-29 |
| `auditHint` | rewritten to the drawn sentence | yes — and ruled 2026-09-29 |

**Nobody should read this as the defect being fixed.** It is not: two of its strings are
still over the cap, and what changed is that they are now ruled rather than unruled.
⚠ **The row's BODY is now stale in one respect** — it names `accessHint` and the
allowlist note, which no longer exist on this screen — and no tool in `10-scripts/` can
amend a register body (`close_defect.py` moves the STATUS only). **That is recorded here
and in the decision log, which is where a lane looks when a body and a status
disagree**, per the prime directive's fan-out clause.

## 4 · What was NOT done when the screen landed, and what closed within hours

**(a) Four of seven values were typed numbers, and are not any more.** When the screen
landed, `absolute_session_hours`, `keep_signed_in_days`, `lockout_max_failed` and
`lockout_minutes` arrived as `min`/`max` on the wire while the PO had ruled every value
a dropdown. **The front end did not type the four lists in to satisfy that sooner** — a
TypeScript literal beside a Python tuple that no gate in this repo can compare is
`DEF-IDN-7501`, which survived weeks of a green suite. The control reads the SHAPE the
server sent instead.

⚠ **THE SERVER LANE THEN PUBLISHED THE FOUR LISTS (`c122891af`) AND THE SCREEN FOLLOWED
WITH NO FRONT-END EDIT AT ALL.** Measured in a browser immediately after: **7 dropdowns
of 7**, and the four *"Between 4 and 12 hours."* help lines gone with the ranges they
described. That is the entire argument for reading a shape rather than typing a list,
settled by the clock rather than by anybody's opinion.

**(b) The Audit log card had no read, and now has one.** `GET
/settings/security-policy/audit` did not exist when the screen landed; its wire type and
fetch were declared in `07-frontend/src/api/endpoints.ts` **so the card had a contract to
be built and tested against**, and the card rendered its FAILURE state — never zero rows,
because *"nothing has changed"* and *"we could not find out"* are different sentences.
The SERVER lane built the read to that contract, at that path, with those field names,
and returns `{rows, complete, scan_capped}` with raw stored values and no words, so
`securityValueLabel` remains the one formatter for the dropdowns and the card alike.

Walked end to end afterwards: the card opened on its honest **empty state** (this demo
utility had never changed a security setting), the walkthrough changed *Sign out when
idle* and saved, and the reload showed

> `09/29/2026 00:25 | Dana Whitfield | Sign out when idle | 1 hour → 15 minutes`

then put the value back. A person by name, the setting in the control's own words, both
values rendered the way the control renders them.

**(c) `DEF-SHL-7827` — the sidebar does not collapse at 420, and is NOT fixed here.** The
drawing shows it dropping at phone width. `AppShell.css` has no media query below 1024px
that touches `.sidebar`, so a 240px rail pushes **all 114 screens** off a phone viewport.
It is the FRAME, this lane owns no shell file, and it is filed rather than fixed. Found
only by photographing the running app and putting the shot beside the drawing.

**(d) The 1280 row was two cards wide and is now three.** Found the same way, in the same
minute, and FIXED — the arithmetic and the kit change are in `DIVERGENCES.md`. It is
sixteen pixels, and `tsc`, eslint, 95 test cases, `G31` and `G134` were all green over a
screen whose third card was in the wrong place, because jsdom has no layout.

## 5 · Proof

* **Clicked, twice, against a real stack** — PostgreSQL 16 → `migrate` → `seed_demo` →
  Django → `vite build --mode compose` → `server.mjs` → Chromium at
  `/opt/pw-browsers/chromium-1194`, driven by
  `10-scripts/cr155_security_redesign_walkthrough.mjs`. Signed in as the seeded System
  Admin, opened the tab, and checked the four headings in order, Save before the audit
  card, the tag of every value control, the three tick boxes, the audit card's state,
  and that no catalogue key, UUID or column name is on the page. **Then changed a
  setting, saved, reloaded, read the row the card recorded, and put the value back.**
  PASSED both runs; the first reported 3 dropdowns of 7 and a failed audit read, the
  second 7 of 7 and a real row.
* **Photographed** at 1440, 1280 and 420 into
  `05-prototype/security-redesign-2026-09-29/built-2026-09-29/`, beside the drawings.
  **Two faults came out of laying them side by side and nothing else found either**:
  the 1280 row (fixed) and `DEF-SHL-7827` (filed).
* **95 test cases** across nine identity files — 84 in the existing suite and **11 new**
  in `securityRedesign.dom.test.tsx`, mounted under the real `/:tenant/settings/security`
  route pattern.
* **Twelve sabotages**, each applied to the real source, run through `vitest`, and the
  source restored byte-for-byte. Two of the first ten came back GREEN and **neither was
  the test's fault**: the anchors only added a comment and swapped a help key, so the
  screen never moved. A sabotage that does not sabotage proves nothing; both were
  rewritten to move the markup and both then named their case.
* **`tsc --noEmit`** through the LOCAL install, exit 0 — and proved able to fail first on
  a planted `const x: number = "not a number"`, which it named at
  `securityPolicyFields.tsx(344,7)`. An empty log is only a pass because the same
  invocation was seen to produce output minutes earlier.
* **eslint** clean on every file touched.
* **`run_gates`: 83 PASS, 50 FAIL, 4 SKIP.** `G31` (declared classes) and `G134` (Route B
  utilities compile) both PASS over the new component; `G15` flags none of this lane's
  30 catalogue keys as untranslated; `G33` names no `settings.security.*` string. **Not
  one of the 50 failures names a file, key, symbol or register row this lane touched**,
  and the runner itself printed *"NOTHING TO COMPARE — no record existed before this
  run"*, so no dated baseline for all 50 exists. That is stated rather than glossed: a
  red called pre-existing without being dated is the dismissal `DEF-CWP-4187` is about.
* **Twelve vitest reds elsewhere** (tenancy, components, i18n) were dated conclusively:
  the same twelve reproduce at `11c729d69` in a detached worktree with none of this
  lane's work in it.

## 6 · Rollback

One revert of the front-end commits and the catalogues go back with them; nothing in this
change writes to a table, adds a migration or touches a backend file. The server's
`SETTING_LIMITS` is untouched, so a rolled-back screen still reads the same eight
published limits — it just reads two of them into hand-typed dropdowns again, which is
`DEF-IDN-7501` re-opened and would have to be re-filed.
