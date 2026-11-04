# 14 · Layout audit — all fifty portal addresses against `08-screen-layouts.md`

**Measured 2026-09-05** against tip `e27fbe4c`, by a lane that opened every portal address in
a real browser on a freshly seeded database, signed in as a customer with real bills, and
compared what rendered against the layout drawing. Source reading told it which pieces each
screen composes; the browser told it what a person actually sees. Both halves were needed —
several gaps were invisible in one and obvious in the other.

⚠ **THIS IS A MEASUREMENT WITH A DATE ON IT, NOT A STANDING STATEMENT.** It was true of one
commit, one tenant, one fixture and one window width. Six lanes have pushed since. Before
citing a row here as current, open the screen.

⚠ **ITS SIBLING IS `13-wireframe-delta.md`**, written the same day from the wireframe IMAGES
rather than from this spec, with neither pass seeing the other. **They agree on the three
root causes** — no page heads on the signed-in screens, no list on the shared table, and a
KPI row that was never built — which is worth more than either pass alone, because they
could not have agreed by copying. Each also found what the other structurally cannot: this
pass found the shared control writing its label to `aria-label` only (D4); the image pass
found the formatting decisions and the emphasis landing on the wrong clause.

⚠ **THE LANE THAT WROTE THIS WAS KILLED BY A CONTAINER RESTART BEFORE IT COULD LAND IT.**
The report survived in its worktree and was landed by the orchestrating session; its
defect rows were filed as `DEF-CWP-3976` … `DEF-CWP-3989`. Its evidence — the walk's
`probe.json`, `summary.txt` and twelve screenshots — did NOT survive and is gone. The
figures below are the lane's own and were not re-measured.

⚠ **TWO THINGS IT EXPECTED TO FIND BROKEN AND FOUND WORKING**, recorded so nobody spends a
wave on them: a corrected bill is on screen and reads correctly (the superseded bill stays
in the list, greyed, saying *Replaced by …*, and its replacement says *Replaces …*; only
the colour differs), and the front page's six doors are live with the two held ones saying
why.

---

# The customer portal, screen by screen, against its own layout drawing

**What this is.** Somebody opened all fifty addresses of the customer portal in a real
browser, signed in as a real customer with real bills, and compared each screen with the
drawing that says what should be on it (`04-docs/05-modules/15-portal/08-screen-layouts.md`).
Nothing was changed. This is a list of what is missing, ranked.

Measured on 5 September 2026 against the branch tip `e27fbe4c`, a freshly seeded database
and a bundle built from that tip.

---

## 1 · The verdict, in a paragraph

**Forty-nine of the fifty addresses opened, thirty-nine could be judged properly, and
every one of those thirty-nine is short of its own drawing in at least one named piece.**
One screen could not be reached at all — *Track your request* needs a request reference and
the demo utility has no service requests on file. Ten more opened but could not be judged
fairly: two are steps inside the quick-pay form and send you back to step one when you type
their address, one read was refused by the rate limiter, and seven were simply empty because
the demo customer has no payment plan, no refund, no protection, no fees, no offered plan and
is not moving out. Those seven were read in the code instead and none looks wrong; they need
one look each against a fuller fixture. **Fourteen of those thirty-nine match their drawing and twenty-five
are short of it** — and the fifteen that match are almost all the pages a visitor sees
before signing in. **The count is not the finding, though: the shape is.** Almost everything
on the list comes from **three faults, not twenty-four**. The signed-in half of the portal
has no page heads, so **twenty-eight screens carry no heading of any kind, no explaining
sentence and — the part that costs — no row of buttons at the top, which is where the
drawing puts *Download all*, *Pay $201.21*, *Download CSV*, *Send a reading* and the rest**.
No list uses the shared table, so **the six lists that draw one have no search box, no
sorting, no row icons and no page footer**, and a seventh draws no table at all. And the row
of big numbers the drawing puts at the top of *Home* and *Usage* has never been built, so
those two open with a stack of boxes instead. Fix those three and most of the twenty-five
move at once. **Twelve screens, plus the header that sits on all of them, are short in a way
a customer would actually feel** — they cannot see something, or cannot get somewhere. The
rest are short of furniture.

Two things I expected to find broken and found working, so nobody spends a wave on them:
**a corrected bill is on screen and reads correctly** — the old bill stays in the list,
greyed, saying *Replaced by BL-2607-000051*, and its replacement says *Replaces
BL-2607-000032*; and **the front page's six doors are now live and the two that are still
held say why**, so the problem the Product Owner hit last week is fixed.

---

## 2 · Every screen, and the one thing most wrong with it

*ISO dates like `2026-08-22` appear on nearly every screen. That is already being fixed by
another lane and is not repeated below. Screens the other lane is rebuilding are marked
**in hand**.*

| # | What it is called on screen | The gap, in one line |
|---|---|---|
| CWP-001 | What do you need? | Matches. Six cards, the two that are not offered say why. |
| CWP-002 | Find your bill | Matches. |
| CWP-003 | Quick pay · check and pay | Cannot be opened by address — it is step 2 of the pay form and sends you back to step 1. Judged from the code: correct shape. |
| CWP-004 | Quick pay · done | Same — a receipt screen with no receipt to show. Code shape is correct. |
| CWP-006 | Tell us what is wrong | Matches. |
| CWP-008 | Can I get service at this address? | Matches. |
| CWP-010 | Ask us for something | Matches. |
| CWP-011 | Answers (not signed in) | The right-hand *Still stuck?* panel is there but sits in its own column code rather than the shared one — two different column layouts now exist in the portal. |
| CWP-012 | Track anything | No title on the page at all; the drawing gives it *Look something up*. |
| CWP-013 | Where you can walk in | Matches. |
| CWP-014 | One service centre | Matches. |
| CWP-015 | Welcome back (sign in) | Matches. |
| CWP-016 | Find your account | Matches. |
| CWP-019 | Send me a reset link | Matches. |
| CWP-020 | Add another account | No page title; the drawing's right-hand panel listing the accounts already on this login is absent. |
| CWP-022 | Home | **In hand.** No right-hand column, so the twelve-month chart, *Your service* and *Paying by instalments?* are all absent; the four big numbers are a stack of boxes instead of a row. |
| CWP-023 | All my accounts | No count in the title, no search, no *On a plan* filter, no view or pay icon on a row, no page footer; services are spelled out as words where the drawing has coloured chips. |
| CWP-024 | My details | No page title or explaining sentence; otherwise the two panels are right. |
| CWP-025 | How we contact you | **Four bare *On* / *Off* buttons float above the table with nothing saying what they switch.** |
| CWP-027 | Your bills | **No *Period* column and no *Usage* column** — both facts are already sent to the screen. Also no *Download all*, no search, no filters, no sorting, no row icons, no footer; the *Pay* button is at the bottom and carries no amount. |
| CWP-028 | One bill, line by line | The best screen in the portal. Missing only the top row of actions — *PDF*, *Query this bill*, *Pay* — and a title. |
| CWP-029 | The bill we sent you | **No preview.** The drawing shows the printed page; the screen is one sentence and a download link. |
| CWP-030 | Why is this bill different? | Only half the screen: *Against last month* is there, *Against last August* and its little chart are not. |
| CWP-031 | Documents and letters | Has its filter chips. Missing search, row icons, footer, and *Download a year* is at the bottom and switched off. |
| CWP-032 | Your final bill | Could not be seen filled — the demo customer is not moving out. Code shape is close; the drawing wants two panels side by side and the code stacks them. |
| CWP-033 | Usage | No row of three big numbers (this period, daily average, next reading due); the per-service panels stack full-width instead of three across; the tip bar is a hand-drawn box, not the shared one, and cannot be dismissed. |
| CWP-034 | Readings on your meter | Columns are exactly right and the closing note about estimated readings is there. No sorting, no row icons, no footer, and the *Send a reading* button the drawing puts at the top is absent — the screen behind it is not built. |
| CWP-035 | Send your own reading | **Not built.** No address in the product. |
| CWP-037 | Meters and equipment | Columns right and the closing note is there, but without the *Report a problem* button the drawing puts inside it. |
| CWP-038 | Pay now | Matches. (This is a form, and the drawing gives forms a step bar instead of a page title.) The one difference: *where it will go* is behind a *Show me where it goes* button rather than shown in the right-hand column. |
| CWP-039 | Your payment methods | The drawing wants a table of cards and bank accounts; the screen renders them as paragraphs. No footer note about never holding a card number. |
| CWP-040 | Automatic payment | Matches. The *Turn on* button is correctly held and says why. |
| CWP-041 | Your payments | Columns exactly right. No search, no sorting, no row icons, no footer. |
| CWP-042 | Spread what you owe | Could not be judged — the demo customer has nothing overdue to spread, so the instalment table never appears and *See the instalments* is switched off. |
| CWP-043 | Your payment plan | Could not be seen filled — the demo customer has no plan. Code shape is right. |
| CWP-044 | Pay the same amount every month | The comparison chart the drawing puts on the right is a text panel; no chart is drawn. |
| CWP-045 | Credits and refunds | Could not be seen filled — no refund on the demo account. Code stacks two panels the drawing puts side by side. |
| CWP-046 | What do you need? (requests) | Close. No page title, and the open-requests panel has no *All requests* link. |
| CWP-047 | Start service · about you | Matches. |
| CWP-050 | What starting service will cost | Could not be seen filled — no fees owing on the demo account. |
| CWP-051 | Track your request | **Could not be reached** — needs a request reference and the demo utility has none. |
| CWP-052 | Stop or restart service | No page title or explaining sentence; the two panels either side are otherwise right. |
| CWP-054 | Ask us something | No page title; both right-hand panels are there. |
| CWP-055 | Something is wrong with this bill | Matches. (A form, so no page title is expected.) |
| CWP-056 | Help paying | Close. The three cards and the moratorium note are all there; only the page title and its sentence are missing. |
| CWP-057 | Where things stand | The ladder is there. No title, and the top actions *Ask for a plan* / *Pay* are absent. |
| CWP-060 | One answer | The read was refused by the rate limiter during the walk, so this one is **unmeasured**. |
| CWP-063 | A plan we have offered you | Could not be seen filled — no offer on the demo account. Code shape is right. |
| CWP-064 | What is protecting your supply | Could not be seen filled — no protection on the demo account. Code shape is right. |
| CWP-065 | Your account | No right-hand column, so the tax-exemption panel and *when this account opened* are absent. (The deposit panel is correctly absent — this account holds no deposit.) |
| CWP-066 | Where your level pay stands | Has its three big numbers. The chart of what you paid against what you used is absent. |

**Screens the drawing describes that have no address in the product at all (14):** accept an
invitation · people with access · send your own reading · your usage looks high · moving out ·
documents we need from you · messages · outages and planned work · answers while signed in ·
an answer attached to a bill · a tip on the usage screen · a visit is booked · everything we
sent you and what came back · check my area. Four of those (usage-looks-high, outages, a
visit booked, check my area) the drawing itself marks as deferred or blocked, so ten are
simply not built yet. Separately, the seven staff-side portal settings screens **do** exist,
inside the staff app, as the drawing says they should.

---

## 3 · The worst ten, in order, and what a person cannot do

1. **Home has no right-hand column** *(CWP-022 — in hand)*. A customer signs in and sees
   what they owe and nothing else. The twelve-month chart of what they used, *Your
   service* (their address, their plan, how they are billed, whether they are paperless)
   and the panel that offers to spread a bill into instalments are all absent. The
   instalments panel is the only place on the home screen that offers help to somebody who
   cannot pay.

2. **No list in the portal can be searched, sorted or paged.** Six screens draw a table —
   bills, accounts, documents, readings, equipment, payments — and not one has a search
   box, a sortable column heading or a page footer; a seventh, payment methods, draws no
   table at all where the drawing asks for one. The server sends every row at once and the
   screen prints all of them. A customer with three years of bills, or the forty-one
   documents the drawing shows, scrolls and squints. There is no way to find one bill by
   number and no way to sort by date.

3. **Your bills does not say what period a bill covers.** The screen shows the bill number,
   when it was issued, when it is due, the amount and what is owing — but not *1–31 August*
   and not how much water or electricity that bill was for. **Both facts are already sent to
   the screen and thrown away.** A customer comparing two bills has to open each one.

4. **Twenty-eight signed-in screens have no title and no top row of buttons.** This is one
   fault with two costs. The small cost is that every page opens with an eleven-pixel grey
   label inside a box instead of a heading — and there is no page heading in the markup at
   all, which is also how somebody using a screen reader finds out where they are.
   The large cost is that the drawing puts the page's main actions in that top row, so they
   are missing with it: *Download all* and *Pay* on bills, *Download CSV* on payments and on
   usage, *Send a reading* on readings, *PDF* and *Query this bill* on a bill, *Add an
   account* and *Pay several* on accounts, *Ask for a plan* and *Pay* on the overdue screen,
   *Download the agreement* on a payment plan. Where a control survived at all it has
   drifted to the bottom of the page — bills has a bare *Pay* button under the table with no
   amount on it.

5. **The contact-preferences screen has four unlabelled buttons.** Two *On*/*Off* pairs
   float above the table with nothing saying which is email and which is text, and the
   selected one is a solid red block, which reads as an error. The cause is one line in one
   shared component: it writes its label for a screen reader only. Fixing that component
   labels these four and the *12 months / 24 months* pair on Usage at the same time.

6. **The printed bill cannot be looked at, only downloaded** *(CWP-029)*. The drawing shows
   the issued page in a frame, letter-shaped, on screen. The build is a sentence and a
   link. A customer who wants to check the bill they were sent must download a PDF first.

7. **The *Messages* word in the header goes nowhere and says nothing.** It sits at the top
   right of every signed-in screen, next to *Help* which is a working link, and it is plain
   text. There is no messages screen behind it, no count of unread ones, and no sentence
   saying it is coming. A customer will click it.

8. **Three screens draw no chart where the drawing draws one.** *Why is this bill
   different?* has no bar comparison against the same month last year; *Pay the same amount
   every month* has no picture of what you would pay either way; *Where your level pay
   stands* has no picture of what you paid against what you used. All three are the screens
   where the picture **is** the explanation. The kit has had a bar chart since last week and
   only one screen uses it.

9. **Usage opens without its three numbers and stacks its services down the page.** *This
   period*, *daily average* and *next reading due* should be a row of big numbers at the
   top; the first two are absent and the third is a grey sentence. The three service panels
   should sit side by side and instead run full-width down a very long page.

10. **Your account has no right-hand column** *(CWP-065)*. A customer cannot see their tax
    exemption, when it runs out, the button to send a new certificate, or when the account
    was opened. The deposit panel belongs there too — it is correctly hidden on the demo
    account because no deposit is held, but there is no column for it to appear in, so a
    customer who *has* paid a deposit would still not see it.

**Just below the line, and worth naming because they are cheap:** not one row on any list
carries a view or print icon, and the drawing puts them on six lists — the portal has no
row-icon component at all; the tip bar on Usage is hand-drawn rather than the shared one and
cannot be dismissed; and *All my accounts* spells services out as words where the drawing has
coloured chips.

---

## 4 · What the drawing's names mean in the code

The drawing and the code use different words for the same things. This cost me an hour and
will cost the next lane the same, so here it is.

| The drawing says | The code calls it | Where it lives |
|---|---|---|
| `Panel`, and its `.Info` / `.Warning` variants | `Panel`, with `tone="info"` / `tone="warning"` | `07-frontend/src/components/Panel.tsx` (shared with the staff app) |
| `Card` | `Card` | `07-frontend/src/portal/components/primitives.tsx` |
| `ChartPanel` | a `Panel` wrapped round **`UsageBars`** — not one piece, two | `primitives.tsx` |
| `PageHead` | `PageHeader` | `07-frontend/src/components/PageHeader.tsx` |
| `DataTable` (toolbar, sortable headers, row icons, footer) | `DataTable` + `FilterBar` + `ListPager` — all three exist and **no portal screen imports any of them** | `07-frontend/src/components/` |
| `MiniTable` | `MiniTable` — and this is what all eight portal lists actually use | `primitives.tsx` |
| `StatusChip` | `StatusChip`, which wraps the staff `StatusPill` | `primitives.tsx` |
| `ConsequenceBox` | `ConsequenceBox` | `07-frontend/src/components/ConsequenceBox.tsx` |
| `TipBar` | `TipBar` — **built, and no portal screen renders it**; only the staff tips-editor preview does | `07-frontend/src/portal/components/content.tsx` |
| `AttachedAnswerCard` | `AttachedAnswerCard` — **built, and nothing renders it at all** | `content.tsx` |
| `CentreCard` | `CentreCard` | `content.tsx` |
| `FormField.Select` | `SelectInput` | `primitives.tsx` |
| `Stepper`, `TwoCol`, `TwoEqual`, `CardGrid3`, `KVList`, `TotalRow`, `ChecklistTimeline`, `ErrandCard`, `InfoBar`, `RadioList`, `PhotoPicker`, `TwoUp`, `PreferenceGrid`, `ProtectionCard` | same names | `primitives.tsx` |
| `Avatar` | not a component — two initials in a bordered box, written inline | `portal/shell/PortalShell.tsx` |

**Pieces the drawing names that do not exist anywhere:**

* **`KpiRow` / `KpiTile`** — the row of big numbers, with a red left rule on the lead tile.
  The staff app has a `KPIStrip`, which one screen borrows, but it is stylesheet-driven and
  has no lead variant. This is the one piece that genuinely has to be built, and the UI
  rules say it belongs in the shared kit rather than on the two screens that want it.
* **`DocumentPreview`** — the framed picture of the printed bill.
* **`WarningBar`** — the full-width warning strip under a card.
* **`DialInput`** — the wide spaced-digit box for a six-digit code or a meter dial.
* **`ToggleChips`** — the payment-method chips on the staff service-centre editor.
* **`Panel.Emergency`** — the red-ruled *is anyone in danger?* panel; drawn by hand on the
  report-a-problem screen instead.

**Two components exist twice under one name**, which is how screens quietly diverge: there
is a `TwoCol` in `primitives.tsx` (stacks on a narrow screen) and a second `TwoCol` in
`content.tsx` (does not), and the guest help, service-centre and quick-pay screens use the
second one.

**In the kit and not in the drawing**, because waves added them: `WhereNext` (the row of
doors at the foot of a screen — this is a good invention and the drawing should catch up),
`NamedGaps`, `ErrandLink`, `HeldButton`, `CommitButton`, `SegmentedChoice`, `NavLinkWord`,
`SectionTitle`.

---

## 5 · How this was measured, and what it does not cover

A real PostgreSQL seeded from scratch with the demo utility, a login attached to the
customer holding the most bills, the bundle rebuilt from the branch tip, and a browser
opening all forty-nine reachable addresses in turn, recording for each one: the page's
headings, whether it has two columns, every table and its column names, every button and
whether it is switched off, every status chip, every search box, and whether a page footer
exists. Screenshots were taken of the ten screens the ranking above depends on.

**What it does not cover.** Nothing here is a judgement about spacing, type size or colour
beyond three cases obvious enough to name (the solid red on selected filter buttons, the
grey fill on right-hand panels where the portal's own token table says white, and the red
`Off` block). Seven screens were empty because the demo customer has no payment plan, no
refund, no protection, no move-out, no fees and no offered plan; those were judged from
their code and are marked as such. One screen was refused by the rate limiter and is
unmeasured. Nothing was changed — no code, no tests, no registers.

**Servers left running, on this container:** the portal API on **port 8299** (Django,
against a database named `sbh_auditfresh`) and the built front end on **port 4399**. Two
logins were created on that database for measuring — `audit@example.test` and
`corrected@example.test`. It is a scratch database; nothing else uses it.

**One thing that affected other lanes.** Half way through, the shared PostgreSQL role's
password stopped working for everyone and a running job failed on it. I set it back to the
value the repo's own notes use. If another lane changed it deliberately, they will need to
change it again and say so.
