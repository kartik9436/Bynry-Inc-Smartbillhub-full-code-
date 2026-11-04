# CR-142-BRC07 — Reports becomes a framework: definitions are data, not code

**Raised:** 2026-09-26, by the Product Owner, who handed the coordinator a generated build
brief and asked for a change request from it.
**Branch:** `BRC07`, `claude/kind-goldberg-k0acqg`. Number from `allocate.py cr`, checked free
against the remote with `allocate.py cr --verify 142` at allocation and again at push.
**Source document:** *Reports Build Brief*, generated 2026-09-26, stamped against product
version **2.340.0**. 86 tasks · 6 phases · 5 tabs · 13 screens · 9 datasets · 46 reports.
**Classification:** ⚠ **MIXED, and the split is the point — see §1.** Eight screens are BUILD;
five live screens are MAINTENANCE.
**Version at capture:** `2.353.0`.

---

## 0 · What arrived, in the requester's words

> *"can you write a new CR? using this document"*, having first asked *"new build or
> Maintaince?"* and then *"first re-check all file and line references against current
> version"*.

**The brief's own one-sentence thesis, quoted:** *datasets are code, definitions are data.*
Today a report is Python. After this, a report is a row in a table, so a utility adds one,
renames a column or hides a report **without a release**.

---

## 1 · Classification — MIXED, and a lane that gets this wrong loses four things

`22-product-maintenance-process.md`'s test is about the USER, not the code: *can a user do this
task in the product today?* Applied screen by screen against the routes actually mounted in
`07-frontend/src/App.tsx` (verified, not assumed):

| Screen | Route today | Route |
|---|---|---|
| 1·1 Report library | `ReportLibraryPage`, `App.tsx:1704` — **S44** | **MAINTENANCE** |
| 2·1 Report viewer | `ReportViewerPage`, `App.tsx:1709` — **S46** | **MAINTENANCE** |
| Account ledger | `AccountLedgerReportPage`, `App.tsx:1685` — **S59** | **MAINTENANCE** — retired |
| By-premises | `ByPremisesReportPage`, `App.tsx:1686` — **S60** | **MAINTENANCE** — retired |
| Customer statement | `CustomerStatementPage`, `App.tsx:1696` | **MAINTENANCE** — retired |
| 1·2, 2·2, 2·3, 2·4, 3·1, 4·1, 4·2, 5·1, 5·2, E·2 | not routed | **BUILD** |

⚠ **`2·1` IS THE TRAP AND THE PROCESS NAMES IT BY NAME.** It is a live screen being redrawn end
to end — it gains paging, sorting, search, grouping, drill-through and slicers, and goes from
rendering a handful of reports to rendering all 46. *"It feels like building (new wireframes,
many waves, hundreds of lines) and a lane that follows Build loses reproduce, blast radius,
regression and the reporter. It has already gone wrong once, on the property Overview."*
**Every existing report opens through `2·1`**, so a lane that skips *reproduce* there breaks
every report at once and finds out from a clerk.

**The three retirements are the sharper half of the same rule.** Blast radius runs **both**
ways: what uses this, AND what used what is being removed. The brief already requires the old
addresses to keep opening (`P2.8`, `P2.16`); that requirement is load-bearing and is not a nicety.

---

## 2 · What is being reversed

**Three signed or shipped statements move. Each is quoted rather than summarised.**

**(a) The catalogue is code.** `apps/reports/catalog.py` holds the reports and three category
constants; `apps/reports/migrations/` contains **only `__init__.py`** — the module has never had
a table (verified at `2dd46ff34`). After this, `report_definitions`, `report_categories` and
`report_tenant_settings` exist and the catalogue count reads **46, not 23**.

**(b) Three live screens stop being screens and become rows.** Account ledger, by-premises and
customer statement are deleted as page components and re-expressed as definitions. **Their
addresses must still open** — a clerk with a bookmark is not a clerk to be broken.

**(c) Sorting and paging leave Python.** This is not new ground: `CLAUDE.md` already records
`NFR-3` as **breached in at least four places**, and the measured cost at the top of the ICP —
`40,046 debtors 61.539s` against a **60-second worker timeout** — means the read was not slow,
**it was killed before it answered**. `P2.12` names the three read models that must accept
paging first: `payments/reporting.py`, `billing/reporting.py`, `ledger/reporting.py`.

**Nothing ❄️ FROZEN moves.** No B4/B5 figure, no money rule, no rounding. The row cap is
**deleted rather than raised** (`P2.4`), which is `NFR-5` applied, not overridden.

---

## 3 · Impact across the surfaces

| surface | impact |
|---|---|
| screens | **13** — 10 new, 2 updated, 1 untouched; **3 retired**. The shell dashboard (`E·1`) is explicitly **not** replaced — PO ruling, *"dont replace existing one"*. |
| routes | **7 new**, and four segments — `custom`, `dashboard`, `scheduled`, `history` — must rank **above** `{key}`. See §4. |
| schema | **4 new tables**: `report_definitions`, `report_categories`, `report_tenant_settings`, `report_schedules`. No existing table altered. |
| API | `/reports`, `/reports/{key}`, `/definitions`, `/datasets`, `/exports`, `/schedules`, `/runs`. |
| RLS | every new table is tenant-scoped; `P0.10` and `P5.6` require the probe **on PostgreSQL**, because the default suite is SQLite and the guarantee cannot exist there (law 14). |
| cross-module | **seams only, read-only, resolved by name at call time.** `apps/reports/` imports no other module's models. Seven modules are named: payments, billing, ledger, customers, tenancy, notifications, identity, portal. |
| copy | new strings in all eleven catalogues, through `10-scripts/i18n_fanin.py`. |
| open questions | one — see §6. |
| demo fixture | 46 platform rows seeded (`P0.6`). |
| Settings | `P0.9` is **"None — and that is a finding"**, deliberately; `E·2` arrives only in phase 5. |

---

## 4 · What is already built that this makes wrong

**One broken card, already shipped.** `ReportLibraryPage.tsx:76` points at an address that does
not resolve; `P1.4` fixes it and `P1.6` adds the check that catches the next one at merge rather
than by a clerk.

**One latent fault nobody has hit yet, and it is the best catch in the brief.** A report's key
sits in the same URL position as a tab name. **A utility naming a report `History` shadows the
History tab and the tab stops opening** — invisible until a real customer does it, and then the
product looks broken. `P0.11` ranks the four reserved segments and `P5.2` refuses them **by
name** when a definition is saved. Both are required; neither alone is enough.

**Nothing else is invalidated.** The work is additive until phase 2's retirements, which are
staged and reversible.

---

## 5 · Size, and the re-check the PO asked for first

**The PO's instruction was to re-check every file and line reference against the current
version before anything else.** Done, mechanically, at `2dd46ff34`:

| | |
|---|---|
| Distinct references extracted from the brief | **77** |
| File exists, cited line within it | **49** |
| File exists, no line cited | **25** |
| Files gone | **0** |
| Lines past end of file | **0** |

**Two apparent misses and one apparent overrun were all faults in the checking script, not in
the brief** — two paths outside the search roots, and one bare `services.py` resolved to the
wrong module (`tenancy/services.py` has 6,518 lines and 6202 is the export runner, as cited).
**Despite thirteen versions of drift (2.340.0 → 2.353.0) the references have held.** That is the
finding, and it removes the coordinator's stated objection to building from this document.

**Size:** 86 tasks, 6 phases, 4 tables, 7 routes, 10 new screens, a scheduler and a query
engine. **This is a module, not a wave.** Phases 0–2 are the spine; 3–5 are separable and each
delivers on its own.

---

## 6 · Still open — put to the PO, not decided here

**`OQ-REP-A` — a computed column.** *Total = 61–90 plus 90+* on the ageing report. Marked OPEN
in the brief and correctly stubbed rather than guessed.

**One word inside a FINAL decision.** *Who may create a BI connection* reads **Administrators**,
with the brief's own note that whether a clerk may as well *"is the one word still to confirm"*.

**And one the coordinator adds.** The brief is stamped **2.340.0** and the product is at
**2.353.0**. The references survived, but a document that describes its own baseline by a
version number thirteen releases old will drift again. Re-run the reference check at the start
of each phase rather than once, here, at capture.

---

## 7 · AMENDMENT, 2026-09-26 — the source document is now IN THE REPO, and it is a LATER draft

**What changed.** §0 above was written from a generated artifact. The PO then uploaded the
brief as a PDF: **`05-prototype/09 Reports Build Brief.pdf`**, 11,228,038 bytes, sha256
`e5934af1…`, 92 pages, 1224×792pt. ⚠ **It was uploaded to the DEFAULT branch
(`claude/confirm-understanding-3ktufc`, `feefef925`) and not to `BRC07`**, so a lane on this
branch would have found nothing — `git ls-tree` on one ref is how a blueprint gets reported
missing (`DEF-GOV-6236`'s shape). It is copied onto this branch byte-identically in the
commit carrying this amendment.

**THE DRAWING FILE IS NOW THIS, AND B14 RULE 42 APPLIES.** A lane builds from the PAGE AS AN
IMAGE — `python3 10-scripts/pdf/pdf_render.py "05-prototype/09 Reports Build Brief.pdf"
<outdir> 3 <pages>` — and uses the text layer only as an index. **The text layer of this
document is measurably lossy**: extracted, it drops `P0.9`, `P0.12`–`P0.14`, `P0.17` and
`P1.7` entirely. A lane that counts tasks from extracted text undercounts Phase 0 by five.

### 7.1 · What the PDF carries that the artifact did not

**It has a section headed *"What the PO changed after reading the first version of this
document, and it is most of the shape"*.** Those are PO rulings and they bind:

| | the ruling, in the document's words |
|---|---|
| **Tabs** | *"It is now **four, flat** — Catalogue · Dashboard · Scheduled · History. **Activity is deleted**, the word and the address."* ⚠ **§0's header above says FIVE TABS and is hereby corrected to four tabs plus two sub-tabs.** |
| **Custom reports** | Not a filter on the catalogue. *"It is a **sub-tab** — Standard · Custom — so an empty sub-tab reading **0** is how a clerk learns the feature exists."* |
| **The dashboard** | Verbatim: *"no i dont want to update existing dashboard … you can create a tab - dont replace existing one"*. **The shell dashboard is fenced off and untouched by every task in this plan.** |
| **The finance statement** | Three bespoke pages exist and a fourth was never built. They collapse into **two definitions with a Subject parameter**, drawn four times each. |
| **The builder** | *"user cannot add columns"* — columns may now be **reordered and renamed**; an unticked column is an empty box, not greyed out. You still cannot invent a column the dataset does not produce. |

**And one ruling dated TODAY, which is in no register:** *"The builder is a panel, not a
wizard"* — put to the PO on **2026-09-26** and answered **"panel"**. It breaks a 42-file
`WizardFrame` convention and was raised as such. Consequence stated in the document: **no flow
in Reports uses the shared wizard frame at all.** A decision-log row is written in the same
commit as this amendment (law 9).

### 7.2 · Three corrections the document makes to ITSELF, and one of them matters

The PDF opens by correcting its own earlier draft in the place each error was made:

1. **95 requirement rows and 42 capabilities**, not the 84 and 41 the earlier draft counted in
   four places.
2. **The download control is an icon**, 36×36, no label — `DownloadButton.tsx:49-51`. The
   earlier draft drew the RULE instead of the CODE, *"which launders a violation into something
   that looks shipped"*.
3. ⚠ **The one that would have caused real damage.** The earlier draft read A1's screen
   inventory — four dashboard period windows defaulting to the last completed cycle, citing
   `BR-REP-035` and `CR-015` — and wrote it up as a confirmed ruling the code had missed, **as
   the first task in the plan**. It is the other way round: `CR-029` `D8①` withdrew that window
   on 23 August, the PO's words were *"dont build it"*, and **A1 is a month stale.** Building
   the first reading would have re-added a feature the PO declined, on a real citation, past
   every check. **VERIFIED INDEPENDENTLY FOR THIS AMENDMENT:** `01-open-questions.md:389` has
   `OQ-268` as **CLOSED — WITHDRAWN by the PO**, quoting `D8①`, and `02-decision-log.md:756`
   records `D8①` verbatim. **The document is right and A1 is stale.** It is now task `P0.15`.

### 7.3 · A drift inside the document, found by counting — report it, do not silently follow it

Each phase carries a **TASK MIX** row and a task table beneath it. **They disagree in five of
the six phases**, because tasks were appended after the mix rows were written:

| phase | TASK MIX says | rows in the table |
|---|---|---|
| **0** | 12 | **18 rows — 16 tasks**, `P0.1`–`P0.18` |
| **1** | 8 | **8** ✓ agrees |
| 2 | 12 | **27 rows, `P2.1`–`P2.27`** — corrected 2026-09-27, lane REP-P2-REST |
| 3 | 6 | **6 rows, `P3.1`–`P3.6`** ✓ agrees — corrected 2026-09-27, lane REP-P3 |
| 4 | 10 | **15 rows, `P4.1`–`P4.15`** — counted from p014–p016 as IMAGES, 2026-09-27, lane REP-P4-REST |
| 5 | 10 | up to `P5.12` |

⚠ **THIS TABLE SAID PHASE 1 WAS *"the only phase that agrees"* AND PHASE 3 REACHED ONLY
`P3.5`, AND BOTH WERE WRONG — corrected 2026-09-27 by lane REP-P3, from the rendered
page.** Phase 3's table on **p14** carries **SIX rows**, `P3.1` (Backend · the runs
endpoint) · `P3.2` (Front end · screens `5·1`/`5·2`) · `P3.3` (Front end · the toast's
destination) · `P3.4` (Front end · re-run) · `P3.5` (Test · retention) · `P3.6` (E2E ·
`J-REP-02`) — which is `1 Backend · 3 Front end · 1 Test · 1 E2E`, **exactly the six its own
TASK MIX row on p13 declares.** So TWO phases agree with themselves, not one.

⚠ **AND PHASE 2's ROW SAID `up to P2.26` AND WAS ALSO ONE SHORT — corrected 2026-09-27 by
lane REP-P2-REST, from the rendered page.** Phase 2's table runs **`P2.1` to `P2.27`** across
**p010–p013**, and Phase 3's heading follows immediately after `P2.27` on p013. So the
document's own TASK MIX box for Phase 2 (`0 DB · 4 Backend · 4 Front end · 0 Settings · 2
Test · 1 E2E · 1 Other-module` = **12**) describes the FIRST TWELVE ROWS ONLY and nothing
says so — `P2.13`–`P2.27` were appended beneath it. **This is the THIRD row of this table to
be found wrong by counting, and all three were wrong in the same direction: short.** A
briefing built from this table told a lane Phase 2 held *14 of 27 built*; the row count was
right by accident and the built count was nine stale.

⚠ **AND THE SHAPE OF THE MISS IS THIS DOCUMENT'S OWN SUBJECT.** §7.3 exists to say *count it
yourself, do not trust the cover* — and its own table was a count somebody had done once and
nobody re-did. A row here is as quotable as a row anywhere else, and this one sent a lane
looking for a missing sixth task that was never missing. **It was found by rendering p13–p14
as IMAGES (B14 rule 42) and counting the rows**, which is the method the rule exists for; the
text layer of this PDF is measurably lossy.

**Phase 0 is the worked case:** the mix counts `P0.1`–`P0.14`; `P0.15` (Docs), `P0.16`
(Backend), `P0.17` (Test) and `P0.18` (Other · customers) were appended afterwards and no
mix row moved. `P0.9` and `P0.12` are **stated absences** — *"None, and that is a finding"* and
*"No new journey"* — deliberately written as rows so the gap is visible, which is why 18 rows
are 16 tasks.

⚠ **PHASE 4 RECOUNTED 2026-09-27 BY LANE REP-P4-REST, AND ITS MIX ROW IS FIVE
TASKS SHORT.** p014's TASK MIX reads `1 DB · 2 Backend · 2 Front end · 1 Settings ·
2 Test · 1 E2E · 1 Other-module` — **ten**, and it describes `P4.1`–`P4.10`
exactly. The table runs to **`P4.15`**. Counted by hand off the rendered pages:

| id | kind | what |
|---|---|---|
| `P4.1` | DB | `report_schedules` |
| `P4.2` | Backend | the scheduler |
| `P4.3` | Backend | recipients — internal staff only |
| `P4.4` | Front end | screen `2·3`, one `FormModal`, three fields |
| `P4.5` | Front end | screens `4·1`, `4·2` |
| `P4.6` | Settings | retention and default format |
| `P4.7` | Test | cadence arithmetic |
| `P4.8` | Test | failure is visible |
| `P4.9` | E2E | `J-REP-03` |
| `P4.10` | Other · notifications | deliver the file |
| `P4.11` | Front end | **the Dashboard tab** |
| `P4.12` | Backend | period and comparison |
| `P4.13` | Front end | panel → report carries the period |
| `P4.14` | Backend | BI tier 2 — scheduled delivery |
| `P4.15` | Other · portal | a landlord sees their own account only |

**So Phase 4 is `1 DB · 4 Backend · 4 Front end · 1 Settings · 2 Test · 1 E2E ·
2 Other-module`** — fifteen. `P4.11`–`P4.15` are the DASHBOARD half and the two
cross-module tasks, appended after the mix row was written; the mix row is a
faithful count of the phase as it stood before them.

⚠ **AND `P4.11` AND `P4.13` CITE THE WRONG SCREEN NUMBER — the brief disagrees
with its own drawings.** Both name the dashboard as **`4·1`** (`P4.13`'s
reference is `4·1 → 2·1`). `4·1` is **Scheduled**, drawn on p040; the dashboard
is **`3·1`**, drawn on **p036** and listed as `3·1 Dashboard` on p078. A lane
that followed the task line would have built the dashboard's panels onto the
schedules screen. Build to **p036**, and read `4·1` in those two rows as `3·1`.

**Counted from the tables, Phase 0 is: 3 DB · 5 Backend · 1 Front end · 3 Test · 1 Docs ·
3 Other-module.** Phase 1 is `0 DB · 2 Backend · 2 Front end · 2 Test · 1 E2E · 1
Other-module`, which is what its own mix row says.

**⚠ THE TOTAL `86 TASKS` IN §0 IS THEREFORE UNVERIFIED** and is not to be quoted. The mix
rows sum to 58; the row ids reach 84. Each phase is recounted from its own table at the start
of that phase, not from the cover.

### 7.4 · The document is stale on B14's own count, and it matters here

§01 of the brief states B14 is *"numbered 1–21 and **31–43**"*. **B14 holds rule 44**,
ratified **2026-09-24**: our UI standard — spacing, sizes, the type scale, the tokens, the
component kit — **wins every time, on every screen, including the frame**, and it is rule 38
with its scope removed. **A document made of drawings that does not know about rule 44 is
exactly the document where that matters**, and the brief's own §01 already reaches the right
answer by another road (*"if the product has a component, draw that component"*). **No
drawing in this brief overrides the token scale**, whatever it draws.

### 7.5 · What does NOT change

The classification in §1 stands — MIXED, five live screens maintenance, the rest build, and
`2·1` is still the named trap. The 77-reference re-check in §5 stands; it was run against this
same content. The three retirements stand.

---

## 8 · PHASE 0 EXECUTION — the routes/seams/tests/docs half (lane REP-P0B, 2026-09-26, `2.354.0`)

**Built:** `P0.8` · `P0.10` · `P0.11` · `P0.13` · `P0.14` · `P0.15` · `P0.17` · `P0.18`.
**Not built, on purpose, and NOT deleted:** `P0.9` (Settings — *"None, and that is a
finding"*) and `P0.12` (E2E — *"No new journey"*). `P0.1`–`P0.7` and `P0.16` are lane
REP-P0A's.

**Version:** `2.353.0` → **`2.354.0`** (step 7 of the change process), written in
`07-frontend/package.json`, `07-frontend/package-lock.json` and `06-backend/pyproject.toml`.

**Rollback, stated before shipping (step 8).** Revert the commit and run
`manage.py migrate customers 0071`. `customers/0073` drops its own policy in
`reverse_sql`; `customers/0072` drops an EMPTY table — there is no backfill and there can be
none, so nothing is lost by reversing and nothing is recovered by re-applying. The four
`/reports` routes and the two seam indirections are pure code and revert with the commit; the
five document amendments would revert to text that is **known wrong** and would have to be
re-applied by hand, which is the one part of this change that should not be rolled back.

**Defects filed:** `DEF-REP-6808` · `DEF-REP-6809` · `DEF-REP-6805` — found and fixed here.
`DEF-SHL-6810` · `DEF-REP-6804` · `DEF-MET-6806` · `DEF-LED-6807` — found, named, **NOT fixed**
(none is this lane's). The last three are **checks that were already red and unread**: the
screen-id map is 21 routes behind App.tsx, `usEnglishCatalogue.test.ts` went red on the tip
commit itself (`Untick`), and `financeCopyRule33.test.ts` has been red since 2026-09-25 over a
seven-word sentence. All three were dated with `git log -S` before being called pre-existing.

**One correction to this document, in its own §02.** `P0.8`'s hazard sentence names the wrong
mechanism — see `DEF-REP-6805` and the decision log of 2026-09-26. React Router v6 ranks a
static segment above a dynamic one **regardless of declaration order**, so what protects the
four reserved words is the route EXISTING, not where it is written. The outcome the brief
states is right; a lane building to its mechanism would have written a test incapable of
failing.

---

## 9 · PHASE 2 EXECUTION — the READ PATH (lane REP-P2A, 2026-09-26, `2.357.0`)

**Built:** `P2.12` (the gating dependency) · `P2.1` · `P2.2` · `P2.3` · `P2.4`.
**Not built and not this lane's:** every other phase-2 task, including the `2·1`
screen work, which waits on phase 0's dimension model and phase 1's screen.

### 9.1 · What `P2.12` actually found — one of the three was already done

`P2.12`'s reference column names `payments/reporting.py:235,291`,
`billing/reporting.py:199` and `ledger/reporting.py:2003`. **Both payments line
numbers fall inside `ar_aging`, which has paged, sorted and filtered in SQL
since `P2.21` landed in `fefb1be9e`** — so the payments third of this task was
finished before phase 2 began, and the read model in that same file that *does*
still materialise its whole window, `payments_by_method`, is named nowhere.
Filed as **`DEF-REP-6816`** and NOT fixed here: it is a different dataset and a
different task, and quietly widening this one is how a lane's scope stops being
reviewable. The brief's own §7.6 says `P2.12` *"asserts paging on all nine"*,
which is the right shape and is not what its reference column says.

The line drift is **`DEF-REP-6817`** — `tenancy/services.py:6202` is really
6259, on top of the two above and the `queries.py:668` → 781 a sibling already
found. **Find code by symbol; a function name survives every edit above it.**

### 9.2 · What changed, and the one judgment inside it

| | |
|---|---|
| `billing.reporting.billing_register` | `search`, `page`, `per`, `sort`, `direction`. Window, bill type, service (`Exists`, never a `DISTINCT` join) and `q` are all `WHERE`; the order is an `ORDER BY` with `id` as a total second term; the page is `LIMIT`/`OFFSET`. **KPIs are a SQL aggregate over the whole FILTERED set** |
| `ledger.reporting.account_ledger` | `page`, `per` — and **no `sort`**, deliberately. `ACCOUNT_LEDGER_SORTS` is `()` |
| `payments.reporting.ar_aging` | unchanged; already done by `P2.21` |
| `billing.customers_seam` | two published reads resolved by name: the account search `q` uses, and the BATCHED contact-name read |
| `reports.queries.billing_register` | passes `page`/`per`/`sort`/`dir`/`q` through and publishes the `page` block |
| `reports.exports.BILLING_REGISTER` | **`whole=True`** — see 9.4 |
| `tenancy.exports` | `EXPORT_ROW_CAP` and `selection_count` **deleted** |
| `tenancy.services.accept_list_export` | the pre-count and the `BIZ-CAP` refusal **deleted**; the audit row no longer carries `row_count` |
| `07-frontend` | `exportCapRefusal` deleted from `ListExportButton.tsx`; `exports.capped` and `exports.row_cap_exceeded` retired from all eleven catalogues |

**THE JUDGMENT: the default order is `invoice_no` ASC, which is what
`_issued_queryset()` has always returned.** `P2.12` is a read-signature change
to another module's published model, so a caller that passes no `sort` must get
byte-identical rows in byte-identical order. A default that quietly became
*newest first* would be a behaviour change hiding inside a performance fix —
and it would have reversed every register in the product on the day paging
landed, with every test still green because no test asserts an order it did not
ask for. `REGISTER_DEFAULT_SORT`/`REGISTER_DEFAULT_DIRECTION` are read through
the seam so the screen and the read model cannot disagree.

**THE OTHER JUDGMENT: the `estimated` tile asks the BACKEND whether it can be a
`COUNT`.** `estimated` is not a column — it is *did any meter block in this
bill's frozen payload carry `estimated: true`* — and the containment lookup that
answers it in SQL exists on PostgreSQL's `jsonb` and is refused by Django on
SQLite, which is the backend `config/settings/test.py` hardcodes.
`connection.features.supports_json_field_contains` decides, and the fallback
streams one column with `.iterator()`. Returning `None` on SQLite instead would
make the two backends disagree about a number, which is worse than being slow on
a fixture (law 14's shape, answered rather than discovered).

### 9.3 · What `P2.4` reverses, quoted

`BR-SHL-016` refuses an export above a cap. `NFR-5` forbids a hard cap
anywhere. **The cap is deleted, not raised** — raising it is what
`DEF-MET-5756` did on 2026-09-18 (50,000 → 100,000) and 100,000 is still short:
**Killeen at 57,066 accounts × 14 cycles is ~685,000 bill rows a year.** The
deletion costs nothing the writer was not already doing — `write_csv` pulls from
`row_stream`, which pulls from `selection_iter`, which is
`.iterator(chunk_size=500)`. **`apps/audit/services.py` keeps its own 50,000
under `BR-AUD-014`**: another module's rule, another module's to move, and the
divergence is stated out loud in both files rather than silently inherited.

### 9.4 · The trap `P2.12` created, caught in the same commit

`reports/exports.py` builds each resource's rows through `_rows_for(key,
params)`, whose `whole` flag defaults to **False**. `AR_AGING` passes
`whole=True` because it pages; `BILLING_REGISTER` did not, because it did not.
**The moment the register started paging, its export would have written the
screen's fifty rows into a file that looks perfectly valid** — no error, no
gate, no test. It is now `whole=True`, and
`test_p2_4__the_report_export_takes_the_WHOLE_filtered_set_not_a_page` fails for
the next paged report that forgets.

### 9.5 · Measured, on real PostgreSQL 16 — `10-scripts/cr142_p2_read_path_cost.py`

19,281 accounts · **39,981 register rows** · 40,621 invoice lines. Median of 3
after a discarded warm-up, every figure the read model's own work and no HTTP.

| | seconds | statements | rows served |
|---|---|---|---|
| register **page 1** of 50 | **0.211** | 7 | 50 |
| register **page 799** (the last) of 50 | **0.206** | 7 | 50 |
| `list(_issued_queryset())` — the line `P2.12` deleted | **3.416** | 1 | 39,981 |
| each of the 8 sort/direction pairs | 0.185 – 0.256 | 7 | 50 |
| page 1 with `q` | 0.138 | 7 | 10 |
| account ledger page 2 of 200 | 0.029 | 7 | 200 |

**The plan, printed rather than described:** `Limit (cost=3152.82..3152.94
rows=50) … Sort Key: invoices.invoice_no, invoices.id … top-N heapsort`.
**Execution Time: 133 ms.**

**The statement count is the second finding and it is not cosmetic.** A page
cost **56 statements** on the first run — fifty of them the Name column,
resolved one account at a time. `customers.primary_contact_names_for` has been
published since `DEF-2723` and `P2.21` put the ageing on it; the register was
the last caller still asking one name at a time. **56 → 7**, and the unpaged
version was making one per bill: **~40,000 round trips for one column.**

**The account ledger's carry-forward, proved rather than asserted:** row 201's
running balance is `13.000000` read unpaged and `13.000000` read as the first
row of page two, and the window's charges are `2597.000000` either way.

⚠ **TWO FLAWS IN THIS SCRIPT WERE FOUND BY ITS OWN OUTPUT AND ARE RECORDED IN
IT (law 7).** Its first draft EXPLAINed the last statement containing `LIMIT`,
which is customers' contact read — a beautiful three-buffer plan over the wrong
table, under a heading that said PAGE. And leg C's carry-forward check sat
behind an `if` and printed nothing when the fixture was too small, so a run in
which the one assertion that can fail correctly never executed looked exactly
like a run in which it passed. Both now refuse instead.

⚠ **AND THE DATABASE REFUSED THE FIXTURE, WHICH IS THE BEST PROOF THERE IS.**
The ledger seeder's first draft wrote `journal_entries` with raw SQL and
`ledger_sole_writer_guard()` raised **CLAUDE.md rule 5** by name. It posts
balanced pairs through `posting.post()` now — and `post()` then refused the
dates, because 2026-07 is a CLOSED fiscal period (`BR-LED-006`), so the fixture
asks `close.resolve_entry_date` rather than picking a date that happens to work.

### 9.6 · Reds seen and NOT caused by this lane — dated, per law 7 habit (1)

* `tests/test_import_scale_80k.py::test_every_target_fits_eighty_thousand_rows_under_the_byte_cap`
  — `TARGET_PAYMENTS` joined `import_runs.TARGETS` in **`b06eba2bb`, 2026-09-23**
  without a measured row width. `git log -S "assets_devices" -- apps/metering/import_runs.py`.
  This lane touched neither file.
* `tests/test_def_081_mixed_currency_book.py` (12 cases) — the posting service
  refuses an entry in a currency that is not the tenant's books', landed
  **`5022fab70`, 2026-09-24**. `git log -S "this utility keeps its books in" -- apps/ledger/posting.py`.
  The fixture posts CAD on a USD tenant, so every case in the file raises at seeding.

Neither is fixed here — neither is this lane's — and both are named so the next
reader does not have to re-date them.

### 9.7 · Rollback, stated before shipping (step 8)

Revert the commit. **There is no migration and no data to lose** — every change
is a read path, a signature with a safe default, or a deletion of a constant.
The one irreversible half is the eleven catalogues: reverting restores two keys
whose sentence describes a refusal the server will not send, so the honest
rollback is the commit minus the `i18n_fanin.retire` call. `NFR-5` means
`EXPORT_ROW_CAP` must not come back at all, and three tests now fail by name if
it does.

### 9.8 · Defects filed

`DEF-REP-6816` — `payments_by_method` is the last unbounded read in payments,
and `P2.12`'s own reference column is why nobody counted it. **Not fixed here.**
`DEF-REP-6817` — the brief's phase-2 line references have drifted in three
places. **Not fixed here** (it is a PDF; the correction belongs with the next
amendment).

---

## 8 · AMENDMENT, 2026-09-26 (second) — PHASE 6 IS ADDED, AND THE DEFINITION OF DONE IS RESTATED

### 8.1 · The gap this closes, stated plainly

**The six-phase plan builds the reporting MACHINE and no task in it builds the QUERIES.**
`P0.4` builds the dataset **registry** — nine datasets each *declaring* its columns, types,
units and money basis. **A declaration is not a query.** Phases 1–5 build the catalogue, the
viewer, history, schedules and the builder.

**Measured at `bab9843a2`:** `apps/reports/queries.py::VIEWERS` holds **four** entries —
`ar_aging`, `billing_register`, `revenue_by_service_rate`, `payments_by_method`. The
catalogue renders **45 cards of which 8 can be produced**; **37 say *"This report cannot be
produced yet."*** The document designs that state carefully and even disables Schedule on
those rows — *"you cannot schedule a refusal"* — **but nothing in the plan turns them on.**

⚠ **So if every one of Phases 0–5 completed perfectly, the result would be a complete
reporting framework serving eight reports.** That is not a defect in the document; it is a
scope boundary nobody had stated. The PO approved closing it on 2026-09-26.

### 8.2 · The shape of the work — 9 queries, not 46 reports

**46 definitions sit on 9 datasets**, so a dataset lights a whole block at once. Counted from
`reports/0003`'s own `DEFINITIONS` tuple:

| dataset | reports | servable today |
|---|---|---|
| `payments` | 10 | 2 |
| `journal_lines` | 10 | 1 |
| `invoices` | 8 | 1 |
| `meter_reads` | 6 | 0 |
| `accounts` | 5 | 0 |
| `audit_log` | 3 | 0 |
| `work_orders` | ~~2~~ **1** | 0 |
| `assets` | 1 | 0 |
| `rate_schedules` | ~~1~~ **0** | 0 |

⚠ **CORRECTED 2026-09-27, measured by lane DS-SMALL against the drawings.** Two of
the four reports these three datasets were counted as unlocking are drawn at a
GRAIN the dataset does not have, so the dataset cannot serve them and the count
was optimistic. **R34 Disconnect & Reconnect** is drawn one line per ACCOUNT
carrying the whole cut-and-restore sequence; `work_orders` is a list of field
jobs, so an account cut and restored in one month appears twice and its balance
is counted twice in the total. **R37 Rate Change History** is drawn one line per
PRICE that moved; `rate_schedules` states one whole VERSION per row, so a
schedule whose four tiers all move on one date is four drawn lines and one data
row, with one price column and nowhere to say which tier it holds. Both refusals
are carried by name in the code (`GAP_R34_IS_A_DIFFERENT_GRAIN`,
`GAP_R37_IS_A_DIFFERENT_GRAIN`) and filed as `DEF-REP-6879`. **So `work_orders`
unlocks 1, not 2, and `rate_schedules` unlocks 0, not 1** — the measurement in
§9 stated it was blind to grain and this is the first place that blindness cost
a number.

### 8.3 · Phase 6 · The datasets — TWELVE tasks

| id | kind | what | unlocks |
|---|---|---|---|
| **P6.1** | BE | `journal_lines` dataset query — ⚠ **reads** journal lines; **hard rule 5** means it writes none | **10** |
| **P6.2** | BE | `invoices` dataset query — generalises today's `billing_register`, which is already paged and measured | **8** |
| **P6.3** | BE | `payments` dataset query — two of its ten exist; lift them into the dataset rather than leave two shapes | **8 more** |
| **P6.4** | BE | `meter_reads` dataset query — ⚠ **hard rule 3**: every quantity carries its unit, in its own column | **6** |
| **P6.5** | BE | `accounts` dataset query | **5** |
| **P6.6** | BE | `audit_log` dataset query — ⚠ retention is evaluated against the row's own timestamp | **3** |
| **P6.7** | BE | `work_orders` dataset query | ~~2~~ **1** — R34 is a different grain, see §8.2 |
| **P6.8** | BE | `assets` dataset query | **1** |
| **P6.9** | BE | `rate_schedules` dataset query — ⚠ rates 4 decimals, percentages 6 | ~~1~~ **0** — R37 is a different grain, see §8.2 |
| **P6.10** | E2E | ⚠ **THE FORTY-SIX-REPORT RENDER WALK.** Open **every** definition in a browser against a seeded tenant and assert it renders **rows**, not a refusal and not an empty table. **PO requirement, 2026-09-26.** One case per report, failing **by report name** |
| **P6.11** | Test | ⚠ **A definition may not ship without a servable query.** A standing check that fails naming any definition whose key `runner.queries_for()` cannot resolve. **Without this, *"cannot be produced yet"* silently becomes permanent** — the shape that left 37 cards dark and no check counting them |
| **P6.12** | Docs | **The column-set ratification**, put to the PO with figures. `reports/0003` deliberately seeds **no `columns`** on any row, because the drawn sets are *"a screen's four-of-seven choice rather than a ratified list"* and `BR-REP-021` already puts five reports on the generic viewer **because their column sets are unratified**. Today a report shows **every column its dataset declares**. REP-REGISTER is measuring drawn-vs-declared per report |

⚠ **`P6.10` AND `P6.11` ARE THE TASKS THAT MAKE *"DONE"* MEAN SOMETHING**, and they are law 7's
whole lesson applied in advance: a catalogue of 46 cards is **not** 46 working reports, and
nothing in the repo currently counts the difference. `P6.11` is the number beside the blind
spot.

### 8.4 · DEFINITION OF DONE — restated by the PO, 2026-09-26

> *"when we say report rebuild is completed - we have framework and we ahve all 46 reports -
> you ahve to do end to end testng also of all 46 reports and see whether it is rendering on
> screen"*

**Three conditions, all required. Any one alone is not done:**

1. **The framework** — Phases 0–5 complete.
2. **All 46 reports** — every definition resolves to a servable query (Phase 6, and `P6.11`
   is the check that says so).
3. **Every one of the 46 proved rendering ON SCREEN, end to end** — `P6.10`, in a browser,
   against a seeded tenant, asserting rows.

⚠ **Condition 3 is not implied by 1 and 2 and that is why it is written down.** A definition
can resolve, a query can return rows, and the screen can still show nothing — this repo's
most-filed defect class is a check that passes over a screen nobody looked at, and no gate
here reads rendered output.

### 8.5 · The corrected task count for the whole change request

| phase | tasks | source |
|---|---|---|
| 0 · Foundations | **16** (18 rows, 2 stated absences) | counted from the table |
| 1 · Catalogue | **8** | counted; the only phase whose own mix row agrees |
| 2 · Report | **27** | counted from the table; its mix row says 12 |
| 3 · History | **6** | counted from the table |
| 4 · Schedules | **≥15** | lane REP-P4 is counting from the images |
| 5 · Build your own | **≥12** | lane REP-P5 is counting from the images |
| **6 · The datasets** | **12** | **NEW, this amendment** |
| | **≈96** | |

**§0's header figure of `86 tasks` is superseded and is not to be quoted** — it was never
verified, the per-phase mix rows disagree with their own tables in five of six phases, and it
predates Phase 6 entirely.

---

## 9 · AMENDMENT, 2026-09-27 — PHASE 6 RESIZED, MEASURED RATHER THAN ESTIMATED

### 9.1 · The estimate in §8 was wrong and this states how

§8.2 said *"46 definitions sit on 9 datasets, so a dataset lights a whole block at once"*
and sized Phase 6 at **twelve tasks**. **That was derived from the seed's `dataset` column
alone and never checked against what each report's DRAWING names as its source.** Two lanes
then built two of the nine and the premise broke in both:

* **`journal_lines`** — 10 reports seeded, **4 now produce a report.** Of the six that do
  not, three need a source the dataset does not own and two need a concept the product does
  not have (a filing template, the other system's totals).
* **`invoices`** — 8 reports seeded, **1 now produces a report.** The lane's own words:
  *"the premise is wrong — eight reports are seeded onto the `invoices` dataset and only one
  of them is a report about bills."* Six of the other seven name a source `invoices` does not
  own, and **all seven state a grain that is not one bill.**

⚠ **The failure mode this prevents is the one worth naming:** serving those seven from
`invoices` anyway would have rendered **a bill register under the title *Bill Print File*** —
real rows, a footing total, an answer to a question nobody asked, **invisible to every gate
and to the clerk.** Both lanes refused BY NAME instead, which is why this resize exists
rather than a silent shortfall.

### 9.2 · Measured across all 46 — seed's dataset against the drawing's own source line

| | count |
|---|---|
| Single-source **and** the seed agrees | **27** |
| **Multi-source** — the drawing names two or three | **15** |
| Single-source but **seeded against the wrong dataset** | **2** |
| No drawn source line resolvable by script | 2 |

**The 15 multi-source reports**, named so nobody re-derives them: `R4` bills+reads · `R23`
accounts+audit · `R26` accounts+premises+assets · `R27` accounts+rating · `R32` jobs+reads ·
`R34` work orders+accounts · `R36` identity+audit · `R37` rating+audit · `R38`
invoices+journal lines · `R39` journal lines+accounts+reads · `R40` journal lines+payments ·
`R41` accounts+journal lines · `R43` journal lines+accounts · `R44` invoices+payments ·
`R46` meter reads+rating.

⚠ **`R8 Bill Delivery` IS SEEDED ON `audit_log` AND DRAWN FROM `notifications` — A TENTH
DATASET THAT THE REGISTRY DOES NOT HOLD.** This is the same finding already filed from the
other direction: the brief says *nine datasets* four times and its own §05 table lists **ten
owners**. Ten is right.

### 9.3 · What this measurement CANNOT see, stated rather than implied

**It compares SOURCE and is blind to GRAIN.** `R6 Bill Adjustments`, `R7 Bill Print File`
and `R13 Write-Offs` all name *"bills & lines"* — so they count in the **27 that agree** —
and DS-INVOICES established by reading their drawings that each states a grain that is not
one bill (one adjustment, one print batch, one write-off). §7.2 says a dataset states **one
grain**, so a grain mismatch needs its own read exactly as a source mismatch does.

**So 27 is an upper bound on what the nine datasets cover, not a finding.** `P6.26` below
exists to turn it into one, and until it reports, no number in this section may be quoted as
the total.

### 9.4 · Phase 6, resized — 27 tasks remaining (29 counting the two done)

| id | kind | what | count |
|---|---|---|---|
| **P6.1–P6.9** | BE | The nine dataset queries. ✅ `journal_lines` (`2.358.0`) · ✅ `invoices` (`2.359.0`) | **7 left** |
| **P6.10** | BE | ⚠ **The TENTH dataset — `notifications`**, which `R8` is drawn from and the registry does not hold | 1 |
| **P6.11–P6.25** | BE | **One joining read per multi-source report**, listed in §9.2. Each states its own grain and declares its measures' additivity; none may be served by bending a dataset to a grain it does not state | 15 |
| **P6.26** | Docs | ⚠ **The GRAIN audit across all 46** — read every drawing and record its stated grain against its dataset's. This is the number §9.3 says we do not yet have, and it may move `P6.11–P6.25`'s count | 1 |
| **P6.27** | E2E | **The forty-six-report render walk** (was `P6.10`). Every definition opened in a browser, asserting **rows**, failing by report name | 1 |
| **P6.28** | Test | **No definition ships without a servable query** (was `P6.11`). Fails naming any key `runner.queries_for()` cannot resolve | 1 |
| **P6.29** | Docs | **The column-set ratification** (was `P6.12`), put to the PO with figures | 1 |

**Phase 6: 12 → 29 tasks.** The whole change request moves from **≈96 to ≈113**.

### 9.5 · What did NOT change

The three conditions of done in §8.4 stand exactly as the PO stated them on 2026-09-26 —
the framework, all 46 reports resolving, and **every one of the 46 proved rendering on
screen end to end**. §9.3's open grain question makes the third condition *more* load-bearing,
not less: a report can resolve to a query and still answer a different question from its
title, and only `P6.27` looks at what a clerk would see.

## 10 · PHASE 2 EXECUTION — DRILL DOWN IN PLACE (lane REP-P2-REST, 2026-09-27, `2.372.0`)

**Built:** `P2.24`. **Phase 2 now stands at 23 of 27.**

### 10.1 · What Phase 2 actually holds, counted against the code

Verified task by task against the files, not against this document. Built:
`P2.1`–`P2.7`, `P2.9`–`P2.14`, `P2.17`–`P2.23`, `P2.25`–`P2.27`, and now
`P2.24`. **Not built: `P2.8`, `P2.15`, `P2.16`** — all three blocked on the
retirement wall §9 records, none of them by a coding gap.

### 10.2 · The re-measurement of the retirement wall, as asked

`journal_lines` was registered in `DATASET_QUERIES` this morning
(`DEF-REP-6876`), which was the stated cause of `account_ledger`'s
`DatasetNotExecutable`. **Re-measured on real PostgreSQL 16 against the seeded
tenant: `account_ledger` still returns `DatasetCannotServe`, and `statement`
still does too.** So the registration moved the refusal from one kind to the
other and did not lift it. `P2.8`, `P2.15` and `P2.16` remain blocked, and the
thing that unblocks them is a ruling about which dataset a customer statement
belongs on — not a lane.

### 10.3 · The measurement `P2.24` was built on, and why it was taken first

`10-scripts/rep_p2_24_grouping_depth.py`, real PostgreSQL 16, seeded
`brazosbend`, 2026-09-27. Of the **46** live definitions:

| grouping depth that ANSWERED | definitions |
|---|---|
| 3 | **1** — `trend_pack` (`journal_lines`) |
| 1 | **2** — `ar_aging` (consumer class) · `journal_export` (service) |
| 0 | **43** — of which 18 `DatasetNotExecutable`, 17 `DatasetCannotServe` |

⚠ **THE DEEPEST GROUP ROW OPENS NOTHING ON 45 OF THE 46**, because the SQL path
answers `collapsed: true` — group rows and no facts. A disclosure drawn on
*every* group row would therefore have been a dead control on nearly every
grouped report in the product. It is derived from the payload instead (*is the
next row deeper?*), so a group with nothing beneath it draws a spacer and not a
disabled triangle.

### 10.4 · Proved

**RED FIRST, THROUGH VITEST — the harness that runs it, never `node <file>`.**
`reportDrillDownInPlace.dom.test.tsx` was written before `ReportGroupRow`
exported any of `groupDisclosureKey`, `openableGroups` or `visibleRows`: **12
failed, 12 total**. After the build: **12 passed**.

**WALKED, AND THE REQUESTS COUNTED.** `10-scripts/rep_p2_24_shots.mjs` at 1440
and 1280 on `trend_pack` grouped three deep, `v2.372.0` visible on screen:
body rows `1 → 2 → 3 → 1` across open, open and close, and **0** report reads.

**NEIGHBOURS.** `src/features/reports` + `DataTable.dom.test.tsx`: **22 files,
237 tests, all green.** `tsc --noEmit`: clean, through the LOCAL `tsc`
(`npx tsc` in a worktree with no install fetches a newer compiler and reports
nothing — law 7's *structurally incapable of failing*). `G31` PASS through its
`run()` entry point.

### 10.5 · One regression this lane caused, and did not hide

`reportGroupRow.dom.test.tsx` asserted a FACT row was on screen under a group
row. With a resting state of *closed* it is one click away, so that case went
red. **It was amended rather than deleted, and its subject is unchanged** — the
same fact row, the same markup, the same reason — with the click the drawing
says is required and a note saying why. Asserting it before the click would
have turned a `P2.18` case into a test of `P2.24`'s default by accident.

### 10.6 · Defects filed

| id | what |
|---|---|
| `DEF-REP-6890` | the drill-through is on the group's LABEL; p028 note ③ puts it on the SUBTOTAL amount |
| `DEF-REP-6891` | a grouped report's pager counts FACTS while the table draws GROUP ROWS — *"1–36 of 36"* over three rows |

Neither is fixed here. `DEF-REP-6891` is the older and the worse: it is
`DEF-REP-6875`'s shape — two figures on one screen that do not foot — one layer
up, in the pager rather than in the subtotals.

### 10.7 · Rollback, stated before shipping

Revert the commit. `visibleRows` and `openableGroups` are pure additions and
`GroupLabelCell`'s three new props are required, so a revert takes the call site
with them and the screen returns to drawing every level at once. No migration,
no data, no catalogue key — the control reuses `table.expand.row` /
`table.expand.rowCollapse`, already shipped in all eleven catalogues.

## 11 · PHASE 2 — THE RULING LANDS AND THE STATEMENT SERVES ROWS (lane REP-P2-LAST, 2026-09-27, `2.374.0`)

**Built:** the R24 `statement` half of `P2.8`. **Phase 2 stands at 24 of 27.**

### 11.1 · What the three remaining tasks actually say, read as IMAGES (B14 rule 42)

Rendered from `05-prototype/09 Reports Build Brief.pdf` at scale 4,
pages 10–13. ⚠ **The text layer does NOT carry these rows** — `pdf_text.py`
returns `P2.7` on p011 and then nothing until `P2.13`, so a lane reading the
extracted text would find `P2.8`, `P2.15` and `P2.16` missing and conclude they
do not exist. That is rule 42 earning its place, measured.

| task | kind (as filed) | what it says, in its own words | outcome column |
|---|---|---|---|
| **`P2.8`** | Front end | *"Retire three screens. Account ledger, by-premises and customer statement become definitions rendered by 2·1. ⚠ **Keep the addresses** — they are bookmarked and linked from Finance. Redirect to `/reports/{key}`"* | *"Three page components deleted; three definitions added; the old addresses still open"* |
| **`P2.15`** | Front end | *"The unit grain. The one subject nobody built. The head reads **premises address + unit label** and the unit declares no address (hard rule 8); an **Occupant** column appears on this subject only, because a unit outlives its tenants"* | *"A three-month unit statement spanning a move-out names both occupants"* |
| **`P2.16`** | Front end | *"Retire the third page. `CustomerStatementPage.tsx` joins the account ledger and by-premises in becoming a definition. ⚠ **Its careful parts are kept** — the `held_with` guard that stops a stranger's arrears appearing on this person's statement, and the server-reasoned `AbsentFigure`"* | *"Three page components deleted, two definitions gained, the old addresses still open"* |

**`P2.8` and `P2.16` disagree with each other and both disagree with the table
— `DEF-REP-6859`, re-verified at the tip and RIGHT.** Three definitions added
against two definitions gained, over a catalogue that holds `statement` and
`account_ledger` and **no `by_premises` and no `customer_statement` key**.
Nothing was minted to match the prose.

### 11.2 · What landed

`BR-REP-038` (PO ruling 2026-09-27) unblocked the statement, and it is built:
`reports/0007_br_rep_038_statement_on_ledger.py` moves R24 to `journal_lines`,
and `apps/reports/statement.py` serves it out of the ledger's own running-record
read model. The PO's worked case is asserted — the `$84.20` bill, the `$84.20`
payment on the 14th, a closing balance struck as `opening + charges − payments`.
Full reasoning and every judgment call: `12-governance/02-decision-log.md`,
2026-09-27.

### 11.3 · What did NOT land, and the reason in each case

| | why |
|---|---|
| `P2.8`'s other two thirds | Both the Account ledger and By-premises addresses collapse into **`R25 account_ledger`**, which is refused by an entry in `queries.JOURNAL_LINES_DEFINITIONS_NOT_SERVED`. That table is inside `apps/reports/queries.py`, **fenced for this lane** while a sibling fixes the refusal path, and `queries.definition_refusal` reads it to decide whether a CARD is available — so registering a viewer anywhere else would leave the catalogue saying *unavailable* over a report that serves rows, which is the disagreement that table exists to prevent |
| `P2.15` | The `unit` subject needs a **running-record read model in `apps/ledger`**, which no seam publishes. `apps/reports` imports no other module's models (§3), so this is a ledger task filed as Front end — the same misfiling `DEF-REP-6859` records for `P2.8` and `P2.16` |
| `P2.16` | ⚠ **The page it deletes is not the report that replaced it.** `CustomerStatementPage.tsx` is *"one person, their accounts, each balance, and a total across them"* — the CUSTOMER grain, with the `held_with` guard and the `AbsentFigure` the task names. R24 at the `account` grain is a different report, and the `customer` subject **refuses**. Deleting the page now would remove a working screen and leave a refusal at its address, which is `P2.8`'s *"keep the addresses"* broken by its own sibling |

### 11.4 · Two defects filed and one fixed

| id | what | state |
|---|---|---|
| `DEF-REP-6908` | `runner.bind` DROPPED `subject`, `subject_id` and `account`, so `P2.14`'s four-grain vocabulary reached **no query at all** | **FIXED** — both names join `_RUN_CONTROLS` |
| `DEF-REP-6909` | `R44 My Bills & Payments` **cannot show a payment today**: seeded on `invoices`, refuses by name. The ruling names the statement and **not R44** | **OPEN** — one question for the PO, no dataset chosen by a lane |

### 11.5 · Reds this lane did not cause, DATED

Every one was reproduced on the **untouched pinned tip** in a throwaway
worktree, so the number beside each is the tip's and not this lane's.

| check | on the tip | in this lane | dated |
|---|---|---|---|
| `G31` | PASS | PASS | — |
| `G134` | FAIL, 3 class tokens | FAIL, **the same 3** | `border-border` in `ReportEditPanel.tsx` → `b3699fb1f` (`2.365.0`) · `default` and `primary` in `RunDialog.tsx` → `007510e95` (`2.363.0`), both by `git log -S` |
| `G15` | FAIL, 689 untranslated | FAIL, **689** | pre-existing; the 14 keys added here are translated and move the number by zero |
| `G17` | FAIL, 14 running-number shares | FAIL, **the same 14** | `DEF-PAY-6554`/`DEF-SHL-6554` → `3edf74eaa` and `c548f4921` |
| `G33` | FAIL, 10 over six words | FAIL, **the same 10** | the named one is `integrations.field.site_id`; none of this lane's strings is over six words |
| `G07` | FAIL, 30 migrations | FAIL, **the same** | pre-existing; `reports/0007` carries its `HUMAN-REVIEW-PENDING` marker and its ledger row |

⚠ **ONE OF THOSE WAS A DUPLICATE ID OF THIS LANE'S OWN AND IS FIXED.** `G17`
also reported `DEF-REP-6905 defined 2×` in the first run: **two sibling lanes
took `DEF-REP-6904` and `DEF-REP-6905` while this one worked**, and the
allocator was right both times it was asked — it reads the pushed world plus
this checkout, and a sibling's row is in neither until it pushes (law 11). Both
were re-derived from the pinned tip at push time and moved to `DEF-REP-6908`
and `DEF-REP-6909` through `renumber_defect.py`, with every citation moved in
the same commit. `G17` reports no duplicate of this lane's after the move.

### 11.6 · SEVEN REDS IN THE SIBLING FILE, READ RATHER THAN SKIPPED — `DEF-REP-6910`

Running `test_br_rep_038_statement.py` beside `test_cr142_p2_retirement_contract.py`
on real PostgreSQL 16: **7 failed, 16 passed.** All eleven of this lane's cases
passed; **every one of the seven is in the sibling file and every one is a
HOLD-EXPIRY CLOCK THAT FIRED AND WAS NEVER MOVED.**

| failing case | why it is red | dated |
|---|---|---|
| `…the_ledger_target_cannot_be_executed…[account_ledger-DatasetNotExecutable]` | `account_ledger` now raises `DatasetCannotServe`, because `journal_lines` was registered in `DATASET_QUERIES` | `72d259e89` (`2.368.0`, `DEF-REP-6876`) |
| `test_p2_24__group_by_is_accepted_and_echoed_and_changes_not_one_row`, **all six** parametrisations | it asserts a grouped run returns rows byte-identical to an ungrouped one and carries no `groups` key; `P2.17` and `P2.24` made grouping cut a real `GROUP BY` in SQL, so both assertions are now false **by design** | assertions written `e9f5666b3` (`2.363.1`); the behaviour changed in `72d259e89` and `b0a900c4e` |

⚠ **THE FILE'S OWN LIFECYCLE NOTE PREDICTED THE FIRST ONE, WORD FOR WORD** —
*"(2) a `DATASET_QUERIES["journal_lines"]` entry turned the account-ledger clock
red"*. It was written as a breaker to prove the clock worked, the entry landed
for real four commits later, and **nobody moved the clock**. That is exactly
hard-won law 7's first shape: *proved red, then never read* — a guard is a claim
only while somebody reads its output.

**NOT FIXED HERE, DELIBERATELY.** Rewriting another lane's assertion is a
judgment about what it should now SAY — the account-ledger clock needs to
expect `DatasetCannotServe` and name who does the work next, and the six
grouping cases need to assert that grouping CHANGES the rows rather than that
it does not. `DEF-REP-6910` holds them so they are counted rather than absorbed
into a suite where an eighth red could hide.

---

## 12 · PHASE 5 · THE TAIL, AND A RECOUNT OF PHASE 0 (lane REP-P5-REST, 2026-09-27, `2.375.0`)

**Counted from the rendered pages as IMAGES (B14 rule 42), p006–p009 and
p016–p017, at scale 4 — not from the text layer, which drops whole rows.**

| Phase | Rows in the table | Its own TASK MIX row sums to | Real mix, counted |
|---|---|---|---|
| **0** | **18** (`P0.1`–`P0.18`) | **12** | 3 DB · 5 Backend · 1 Front end · 1 Settings · 3 Test · 1 E2E · 1 Docs · 3 Other-module |
| **5** | **12** (`P5.1`–`P5.12`) | **10** | 2 Backend · **5** Front end · 1 Settings · 2 Test · 1 E2E · 1 Other·identity |

⚠ **BOTH MIX ROWS ARE SHORT, AND FOR THE SAME REASON §7.3 ALREADY RECORDS FOR
PHASE 0: rows were appended after the summary was written and the summary did
not move.** Phase 5's mix says `3 Front end` and there are **five** — `P5.3`,
`P5.4`, `P5.10`, `P5.11`, `P5.12`. **Count the table; never the mix row.**

### 12.1 · Phase 0 is COMPLETE, and it is 16 tasks in 18 rows

`P0.9` (*"None — and that is a finding"*) and `P0.12` (*"No new journey"*) are
**stated absences written as rows so the gap is visible**, which §7.3 already
says. Every other row is built: `P0.1`–`P0.7` and `P0.16` in `f11824714`,
`P0.8` · `P0.10` · `P0.11` · `P0.13`–`P0.15` · `P0.17` · `P0.18` in
`64f7c64bd`. ⚠ **There is no outstanding Phase 0 task.**

⚠ **ONE HONEST FOOTNOTE ON `P0.12`.** Its outcome reads *"The existing spec
passes against the table-backed catalogue with no edit"*, and
`07-frontend/e2e/US-REP-report-centre.spec.ts` **was** edited — in `bab9843a2`,
Phase **1**, from three groups to six. That is Phase 1 changing what the
catalogue IS and moving its own assertions with it, which is correct; `P0.12`'s
promise was about Phase 0's change and held through it. Recorded so the next
reader does not re-derive it.

### 12.2 · Phase 5 · `P5.9` BUILT — the rule that was signed and not enforced

`BR-REP-023` (PO AR-1, 2026-08-08) restricts the access-review report to System
Admin and Executive. **Measured on 2026-09-27, a Billing Clerk was drawn all 45
cards and `GET /reports/access_review` served him.** Three files cited the rule
and a test asserted the CITATION was present. Built: `min_role` on
`report_definitions` (migration `0008`, 🔒, `FORCE` lifted round the backfill,
proved forward → back → forward on PostgreSQL 16) and `apps/reports/role_gate.py`,
asked by the catalogue and by the viewer. `tests/test_rep_p5_9_role_gate.py` —
**12 failed with the gate disabled, 17 passed with it on.** Walked as three
real people at 1440. Full reasoning and the two green-passing faults are in the
decision log of the same date.

⚠ **IT CHANGED SIX PHASE-1 CASES AND THAT IS WORTH READING.** `catalogue_payload`
now takes a `role` and **fails closed** on it, so a caller stating no role is
shown no report carrying a floor — and every count in
`tests/test_rep_p1_catalogue.py` went from 45 to 44. **The fixture was fixed,
not the gate:** `api.report_library` reads `request.tenant_role` and can never
call the read with nothing, so a test that does is testing a path the product
does not have. The no-role answer is asserted deliberately, in the file that
owns the rule. ⚠ **It was nearly reported as *"a red I did not cause"*** — the
first run's grep caught unrelated `kombu` lines and read as an environment
fault; running the same file with this lane's code REVERTED gave **24 passed**,
which is law 7 habit 1 doing exactly its job.

### 12.3 · Phase 5 · `P5.8` BUILT — `J-REP-04`

`08-qa/01-e2e/journeys/J-REP-04-build-a-report-save-it-share-it.md`. Nine
steps. **Steps 8 and 9 name the harness that proves them instead of implying
the browser walk covered them** — `P5.9` is pytest and tenant isolation is
PostgreSQL-only, because SQLite has no row-level security and a probe there
passes while proving nothing (law 14).

⚠ **AND THE PREVIOUS WALK'S `CANNOT` WAS WRONG.**
`rep_p5_builder_walkthrough.mjs` announces *"no COLLEAGUE= address was given,
so this deployment has one signed-in user"* for the private/shared pair. The
seeded `brazosbend` tenant holds **seven memberships** —
`sam.reyes@sample.test` (billing_clerk), `avery.cole@sample.test` (executive),
four field technicians and Dana. **The addresses were there the whole time**;
what stopped them is that both sample logins carry a temporary password with
`must_change_password` set, which is a FIXTURE gap and not a product one.

### 12.4 · Phase 5 · `P5.5` and `P5.12` NOT BUILT, and the size in the decision log was wrong in BOTH directions

The 2026-09-27 decision row says `P5.5` *"needs a `/lookups` handler for
`report_categories` and a new `reports` group in `referenceDataConfig.ts`; the
grid pattern exists and the work is real but untouched."* **Read against p047
as an image, that is too small in one way and too large in another.**

**TOO SMALL:** p047 legend ④ is explicit — *"one string appended to
`REFERENCE_GROUP_ORDER` (ten entries today) and **four rows** added to
`referenceDataConfig.ts` (35 cards today, 39 after)"*, and the four are
**Report groups · File retention · Default format · Delivery**, not one. **NO
NEW ROUTE, NO NEW TAB, NO NEW SCREEN FILE** — it is a section of `S8` at
`/{tenant}/settings/reference-data/reference-data`. Measured today:
`REFERENCE_GROUP_ORDER` holds **10** entries and `REFERENCE_CARDS` holds **36**,
so the drawing's *"35 today"* is one behind and the shape is right.

**TOO LARGE, in the sense that matters:** it is **NOT** one lookup handler.
Two of the four cards are single values on a small form (the `Billing defaults`
pattern, used three times already), and one of them — **File retention** —
does not live in this module at all: `ARTIFACT_RETENTION_DAYS = 3` is in
`06-backend/apps/tenancy/exports.py:137`, and its comment already says
*"(tenant-config half unbuilt)"*. A Reports settings card writing it is a
cross-module write, which B2 §2 forbids.

**AND `Delivery` HAS NOTHING TO READ.** p047 draws it as *"Where a scheduled
report goes · 2"*. `apps/reports/schedules.py` contains the string `delivery`
**zero times**.

**⚠ AND THE TWO CARDS THAT WOULD HAVE MADE THIS SMALLER NEVER ARRIVED.**
p048's TASK row says *"`P4.6` lands retention and the default format one phase
earlier, because Tab 3's expiry helper needs them and schedules cannot be built
without a format — so two of the four cards arrive in Phase 4 and the section
is completed in Phase 5."* **`P4.6` was not built** — `c7609569a` landed
`P4.1`–`P4.5`, `P4.7`, `P4.8` — so Phase 5 would have had to deliver all four,
two of them across a module boundary.

**`P5.12` IS BLOCKED ON `P5.5` AND MUST STAY BLOCKED.** It puts a link on
`5·1 History`'s retention line to a Settings section, *for an admin only*.
p048's own DOORS row is the argument for it — *"a retention setting nobody can
find from the screen it governs is a setting nobody uses"* — and building the
link before the section is hard-won law 2's mirror exactly: a live control
pointing at nothing. The retention line itself is already on screen
(`ReportRunsPage.tsx:337`, `P3.5`) and stays a bare six-word fact.

### 12.5 · Where Phase 5 stands

| | |
|---|---|
| Rows in the table | **12** |
| Built | **10** — `P5.1`–`P5.4`, `P5.6`–`P5.11` |
| Not built | **2** — `P5.5` (four Settings cards; one is another module's constant, one has nothing to read) and `P5.12` (its door, blocked on `P5.5`) |

**Version:** `2.374.0` → **`2.375.0`**. ⚠ **This lane held `2.374.0` and a
migration numbered `reports/0007`, and BOTH were taken by a sibling while it
was being tested.** Re-derived at push time and renumbered to `2.375.0` and
`reports/0008` — which is CLAUDE.md law 11 applied to two id families the
`allocate.py` verify does not cover on its own.

**Rollback, stated before shipping:** revert the commit and run
`manage.py migrate reports 0007`. The column goes and with it the one
restriction; `role_gate.may_run` then answers True for every row, which is the
behaviour of every build before today. Nothing else reads the column.

## 13 · AMENDMENT, 2026-09-27 — PHASE 6's FIRST THREE JOINING READS, AND §9.2's COUNT IS WRONG (lane REP-P6-JOIN, `P6.11`)

### 13.1 · §9.2 says FIFTEEN multi-source reports. It is SEVENTEEN.

§9.2 lists `R4 · R23 · R26 · R27 · R32 · R34 · R36 · R37 · R38 · R39 · R40 ·
R41 · R43 · R44 · R46`. Read against the drawings **as images** (B14 rule 42),
two more state two sources each in their own eyebrow lines:

| | drawn source line | where |
|---|---|---|
| **`R24` Statement** | *accounts + invoices + payments* | p069–p071, drawn four times |
| **`R25` Ledger** | *accounts + journal lines* | p071–p073, drawn four times |

They are drawn **separately, after the six groups** — the document says so on
p060 — which is how a pass over the six groups missed them. **Neither is this
lane's**; the count is corrected so nobody re-derives it. `P6.11`'s task count
moves from 15 to 17, of which `R24`/`R25` already have a ruling of their own
(*the customer statement is built on the ledger*, decision log 2026-09-27).

### 13.2 · THE GRAIN, MEASURED, FOR ALL FIFTEEN — §9.3's missing number, for this subset

§9.3 says the §9.2 measurement *"compares SOURCE and is blind to GRAIN"*, and
that `P6.26` exists to fix it. This is that read for the fifteen, done from the
images rather than the text layer:

| | **one row is** | verdict |
|---|---|---|
| `R4` Bill Run Readiness | one **account in a cycle that failed a check** | **RULED `BR-REP-041`** — the latest PREPARED RUN for the cycle; where none exists, state the absence |
| `R23` Account Activity | one **lifecycle event** | ✅ **BUILT** |
| `R26` Data Quality | one **CHECK that failed**, with a count and one example | buildable — needs a rule registry, which no module holds |
| `R27` Plans & Discounts | one **enrolment** | **RULED `BR-REP-040`** — one report, k-way merge of three streams, and the slower last page is a NAMED exception |
| `R32` Read Import Log | one **read-import batch** | ✅ **BUILT** |
| `R34` Disconnect & Reconnect | one **ACCOUNT**, latest case | **RULED `BR-REP-039`** — see 13.3 |
| `R36` Access Review | one **user of this tenant** | ✅ **BUILT** |
| `R37` Rate Change History | one **component change** | buildable, own wave — four component tables, four key shapes |
| `R38` Adjustment Register | one **adjustment** | **refused** — `adjustments` has no reference number and no `raised_by` |
| `R39` Regulatory Filing | one **line of a prescribed filing** | **refused permanently** — no filing-template model exists |
| `R40` External Reconciliation | one **measure against ANOTHER system's figure** | **refused permanently** — nothing fetches the other side |
| `R41` Migration Assurance | one **cutover check, legacy vs loaded** | **refused permanently** — `AccountImportBatch` holds counts and no money column |
| `R43` Trend Pack | one **fiscal period** | buildable — wave 2 |
| `R44` My Bills & Payments | one **transaction on one account** | buildable — wave 2. ⚠ `DEF-REP-6909` records that it **cannot show a payment today**, which is the same fault `BR-REP-038` settled for the statement |
| `R46` Bill Projection | one **projected charge component** | **RULED `BR-REP-042`** — ± 15% of the USAGE part only |

### 13.3 · `R34` HAS A BETTER SPINE THAN `work_orders`, AND THE REFUSAL SHOULD NOT BE READ AS FINAL

`apps/work/work_orders_dataset.GAP_R34_IS_A_DIFFERENT_GRAIN` refuses R34 because
*"an account cut and restored inside the window has TWO orders, so it would
appear twice and the balance column would double-count the debt."* **That is
correct about `work_orders` and it is not the end of the question.**

`apps/customers/disconnects.py` holds **`disconnect_cases`**, and one case is
one whole cut-and-restore sequence: `account`, `state`, `tier`,
`amount_owed_at_open`, `opened_on`, `cut_on`, `reconnected_on` — every drawn
column except `Paid`. **An account cut and restored twice has two CASES, not two
field jobs sharing one account row**, so the double-count the refusal names does
not arise at that grain.

⚠ **THAT QUESTION IS NOW ANSWERED — `BR-REP-039`, PO ruling 2026-09-27, option
(a).** ONE ROW PER ACCOUNT, showing its **latest** case; earlier cases are
available underneath and never as sibling rows. The worked case the PO was
shown: *Alia is cut off on 3 June for `$210` and restored on the 11th; cut off
again on 9 September for `$185`. One row per case would total `$395` — money
she never owed at once.* The `work_orders` refusal **stands as a statement
about that dataset and is superseded as a statement about this report.**

⚠ **THIS PARAGRAPH SAID *"No value is chosen here"* UNTIL THE RULING LANDED,
AND IT IS AMENDED RATHER THAN LEFT.** A closed question whose body goes on
describing the open world is the rot `CLAUDE.md`'s prime-directive section
names by name — three lanes were misled by one in an evening — and the body is
what a lane actually reads.

### 13.4 · BUILT — three read models, three seams, three viewers, one runner fix

| | |
|---|---|
| `apps/identity/access_review.py` | R36 · one row per **membership** · memberships × users × roles, `A4_MATRIX` for the approval cell |
| `apps/metering/read_import_log.py` | R32 · one row per **batch** · `read_import_batches` + a `GROUP BY` over `read_import_rows` |
| `apps/customers/account_activity.py` | R23 · one row per **event** · a SQL `UNION` of `move_records` and `transfers` |
| `apps/reports/report_seams.py` | three seams × (page · stream · constant), resolved by name at call time |
| `apps/reports/queries.py` | three per-key viewers, three per-key streams, `KEY_STREAMS` |
| `apps/reports/runner.py` | `stream_for` gains a per-KEY lookup **before** the dataset one — ONE `or`, joining the tip's own `statement.MODULE_STREAMS` rather than a second mechanism |
| `apps/reports/datasets.py` | `audit_log` gains `as_of`/`role`; `meter_reads` gains `source`/`result`/`status`; `accounts` gains `event`/`account` |
| `07-frontend` · `ReportCell` | a BOOLEAN renders as a word and an ISO TIMESTAMP as a tenant-formatted date; six more columns join the live-vocabulary branch. Decided by TYPE, so all 46 reports gain it |
| `07-frontend` · `ReportKpiBand` | a PERCENT tile displays **two** decimals (hard rule 2). It printed `100.000000` |
| `apps/reports/exports.py` | the three registered as EXPORT RESOURCES, `whole=True` on each — see 13.6a for the live control that would otherwise have 404'd |
| eleven catalogues | 64 keys each — columns, tiles, gaps, `Yes`/`No`, two basis labels and nineteen vocabulary values. Additions only; parity held |

⚠ **EVERY ONE OF THE FOUR SCREEN FAULTS ABOVE WAS FOUND BY PHOTOGRAPHING THE
PAGE AND BY NOTHING ELSE** — `cells.basis.as_at` under the page head, `true`
in a column, an ISO instant in another, and a six-decimal percentage on a tile.
`tsc`, 42 backend cases and the whole gate suite were green over all four, which
is hard-won law 6 with four fresh instances. **And the walkthrough itself said
PASS over three of them on its first run**, because it read `<th>` text and
cells matching a uuid and nothing else; it now scans the WHOLE page for a raw
key, a raw instant and a raw boolean. A check whose output cannot distinguish
pass from fail is worse than none, because it is trusted.

**No migration.** All three definitions are already seeded by `reports/0003` and
each is served by a per-key viewer on the dataset it sits on — the same
arrangement the four `journal_lines` viewers already use. `reports/migrations/`
is another lane's this week and was not touched.

**The three dataset refusals STAY.** `queries_for` and `definition_refusal()`
both ask `VIEWERS` first, so the card and the viewer agree; a refusal deleted
the day its read model lands is a refusal nobody can read when the wiring rots.

### 13.5 · THE DEFECTS FILED — `DEF-REP-6921` and `DEF-REP-6922`

**Three of the brief's own source lines name sources the report does not read.**
`R32` says *jobs + meter reads* and reads neither — `jobs` is tenancy's
export-job table, and a REJECTED row never reaches `meter_reads` at all, so the
drawn `REJECTED` tile could not be computed from either. `R36` says *identity +
audit* and is answerable from **identity alone**. `R26` says *accounts +
premises + assets* and its fourth drawn row needs **meter reads**, a fourth
source.

**Why §9.2 could not have found these:** it compared the drawn line against the
SEEDED dataset column, which can only detect a disagreement between two
documents — never a document that is wrong about the code. **`P6.26` should
record the drawn SOURCE beside the drawn GRAIN and compare both against the read
model that serves the report.**

### 13.6 · THE FOUR RULINGS LANDED WHILE THIS WAVE WAS IN FLIGHT (`f3c570032`)

`BR-REP-039`–`042` answer every question 13.2 left open, all option (a). They
are recorded HERE as well as in the business rules because this amendment's own
table said *needs a ruling* four times, and a table that goes on saying so is
the exact rot `CLAUDE.md`'s prime-directive section names. **The rows above are
amended, not annotated.**

| | the ruling, in one line |
|---|---|
| `BR-REP-039` `R34` | ONE ROW PER ACCOUNT, latest case; earlier cases underneath, never siblings. Spine is `customers.disconnect_cases` |
| `BR-REP-040` `R27` | ONE report, k-way merge of three streams. **The slower last page is a NAMED, RULED exception to this phase's rule and to nothing else** — `NFR-3` and `NFR-5` untouched. Publish the measured cost in the rule |
| `BR-REP-041` `R4` | The latest PREPARED RUN for the cycle. Where none exists, **state the absence** — nothing substituted |
| `BR-REP-042` `R46` | **± 15% of the USAGE part only.** `$84.00` of `$24.00` base + `$60.00` usage carries ± `$9.00`, not ± `$12.60`. A test asserts that figure. The sewer row's *Winter average* basis is a SECOND tenant rule and is **not** ruled — stub and ask |

**NONE OF THE FOUR IS BUILT BY THIS LANE**, and neither is `R43` or `R44`. Six
reports remain in `P6.11`; this wave delivered three of the seventeen.

### 13.6a · THE DOWNLOAD BUTTON — A LIVE CONTROL THAT WOULD HAVE 404'd

⚠ **THE MOMENT THESE THREE REPORTS STOPPED REFUSING, THREE DOWNLOAD BUTTONS
WENT LIVE OVER NOTHING.** `ReportViewerPage` enables the export icon whenever a
report renders, and `apps/reports/exports.py` registered FOUR export resources;
a report outside that four posts a `resource` the server answers **404** to.
That is hard-won law 2's mirror — a live screen behind a dead control — and
this wave would have CREATED it on three screens rather than inheriting it.

**All three are registered**, with `whole=True` on each (`P2.12`'s own trap:
the flag defaults to False and an export without it writes the screen's fifty
rows into a file that looks entirely valid). None declares `money=True`,
because none serves a money column. `can_approve_money` is exported as a
`BOOLEAN` and not as the screen's `Yes`/`No` — the kernel's own comment on that
kind is *"machine-parseable, never Yes/No copy"* — and `last_active_at` keeps
its honest name in the file as well as on the screen.

⚠ **AND THE CHECK THAT FOUND IT WAS WRONG TWICE BEFORE IT WAS RIGHT, WHICH IS
THE PART WORTH RECORDING.** The first probe was an unauthenticated `curl` and
answered 404 for every resource **including a registered one** — a check that
cannot tell a missing resource from a missing session. The second posted to
`${BASE}/api/${TENANT}/exports`, and `/api/exports` is one of the routes
`src/api/client.ts` lists BY NAME as un-tenanted: so it 404'd on the URL and
reported three findings that were its own bug. **Law 7's second habit is *ask
what would make this check pass wrongly*; both of these were the same question
asked in the other direction, and neither was asked until the answers stopped
making sense.** The guard was then proved RED properly — the three removed from
`RESOURCES`, the server restarted, `404 · 404 · 404` — and green again on
restore: **`202 · 202 · 202`.**

### 13.6b · A LANE COLLISION THIS WAVE WALKED INTO, AND WHAT CAUGHT IT

⚠ **`DEF-REP-6904` WAS ALLOCATED BY THIS LANE AND TAKEN BY A SIBLING BEFORE IT
PUSHED.** `file_defect.py` computed the next free id correctly against
everything it could see; a sibling working in its own worktree had rows in none
of those places until it pushed. That is CLAUDE.md law 11's id clause exactly,
and it is the SECOND half — the re-derivation AT PUSH TIME — that caught it,
not the allocation.

⚠ **AND THE REPAIR HAD ITS OWN TRAP.** A `sed` repointing every `DEF-REP-6904`
at the re-derived `DEF-REP-6921` also rewrote a sentence in §11.5 — *another
lane's* paragraph, which happens to name `DEF-REP-6904` legitimately. The file
was restored from the pinned tip byte-for-byte and this block re-appended, and
the prefix was then PROVED identical rather than eyeballed. **A blind
find-and-replace over a shared document is a whole-file write wearing an
edit's clothes**, which is the same shape as the `csv`-writer lesson in law 11
and is worth recording in its own right.

⚠ **THE TIP ALSO MOVED UNDER THIS WAVE IN A WAY THAT MADE THE WORK BETTER.**
`runner.stream_for` gained `statement.MODULE_STREAMS` while this lane was
building `queries.KEY_STREAMS` for the same purpose. Re-deriving from the new
tip turned an eleven-line patch into a ONE-LINE `or`, and avoided shipping two
mechanisms for one question — which is the PO's own standing instruction,
*"dont create duplcate code"*. Blind re-application would have shipped both.

### 13.6c · REDS THIS LANE DID NOT CAUSE — DATED, per law 7 habit (1)

Two front-end catalogue suites fail on the TIP, before this lane touched
anything. **Each is dated with `git log -S`**, because `DEF-CWP-4187` records
that *"pre-existing, not mine"* is a claim about history and two lanes once
made it in good faith about a red one of them had caused.

| the failure | the string | landed |
|---|---|---|
| `financeCopyRule33.test.ts` — B14 rule 33's six-word cap | `finance.cost.emptyHelper` = *"Clear a filter, or capture an invoice."* — **seven words** | `26376795e`, 2026-09-25 |
| `usEnglishCatalogue.test.ts` — American spelling | `metering.units.services.help` = *"Untick what a unit will not take."* | `630f472c3`, 2026-09-26 |
| `usEnglishCatalogue.test.ts` — American spelling | `reports.tabs.catalogue` = *"Catalogue"* | `007510e95`, 2026-09-27 |

**None is fixed here and that is deliberate:** two are other modules'
clerk-facing copy and the third is a shipped tab name whose spelling may have
been shown to the PO, so changing any of them is a copy change across eleven
catalogues and not a lane's to take in passing. Filed as `DEF-REP-6922` so they
are countable rather than re-discovered. **The backend suite and the gate suite
were green.**

### 13.6d · `P5.9` LANDED MID-WAVE AND MADE ONE OF THIS LANE'S OWN STATEMENTS FALSE

⚠ **`access_review.py` SHIPPED A CONSTANT SAYING `BR-REP-023` WAS ENFORCED BY
NOTHING. IT WAS TRUE WHEN IT WAS WRITTEN AND FALSE BY THE TIME IT WAS PUSHED.**
`apps/reports/role_gate.py` and `reports/0008_p5_9_min_role.py` landed in
`c79edc4c8` while this wave was in its third re-derivation, and the restriction
is now resolved server-side at the catalogue and at the run.

**It is AMENDED, not deleted and not left.** Deleted, the next reader cannot
learn that this read model deliberately carries no authorisation check of its
own; left, it is a stale claim on a SECURITY rule — and `role_gate.py`'s own
docstring opens by recording the mirror image of that: *"`BR-REP-023` has been
signed since 2026-08-08 and nothing enforced it"*, while three files cited it.
This wave would have shipped the same shape running the other way.

⚠ **IT WAS CAUGHT BY RE-DERIVING FROM THE TIP AND BY NOTHING ELSE.** Every
test was green over it — the constant's own assertion checked that the code
string was present, which stayed true. A claim about another module's state is
not something a test in this module can check, which is why the re-derivation
at push time is the check, and why `git diff --name-only <base> <tip>` is read
rather than skimmed.

### 13.7 · Rollback, stated before shipping

Revert the commit. **There is no migration and no data to lose** — every change
is a new read-path file, a seam, a viewer, three filter tuples and one lookup in
`stream_for`. Reverting returns R36, R32 and R23 to the NAMED dataset refusals
they carry today, which is a worse answer and not a broken one: the refusals
were never deleted. The one thing a revert must not do is remove
`queries.KEY_STREAMS` while leaving a per-key viewer behind — that combination
is the dead-generator state 11.4 exists to prevent, and it is the only ordering
that matters.

---

## 14 · `P4.6` BUILT AND `P5.12` BUILT · `P5.5` IS HALF (lane REP-P5-SETTINGS, 2026-09-27, `2.379.0`)

**Counted from the rendered pages as IMAGES (B14 rule 42), p016, p017, p047,
p048 and p049, at scale 4.**

### 14.1 · §12's count is right, and one measurement in §12.4 is not

**Phase 5 is 12 rows (`P5.1`–`P5.12`)** and its own TASK MIX row sums to 10 —
both exactly as §12 records, re-counted from p016–p017 rather than taken from
it. The mix undercounts Front end by two, again as §12 says.

⚠ **§12.4's *"`REFERENCE_CARDS` holds 36"* IS WRONG BY ONE; IT HOLDS 35, WHICH
IS THE DRAWING'S OWN FIGURE.** p047 legend ④ reads *"35 cards today, 39
after"*, and §12.4 concluded *"the drawing's '35 today' is one behind"*. It is
not behind. The over-count comes from grepping `code: "` — `account_subtypes`
carries a SECOND `code:` inside its `parentList` block, naming the list its
Parent picker offers. Counted as objects in the array: **35**.
`REFERENCE_GROUP_ORDER` holds **10**, as §12.4 says. The drawing was right on
both numbers and the correction matters only because the next lane will
otherwise "fix" a figure in a PDF that is already correct.

### 14.2 · The cross-module write, which is what this task was deferred on

§12.4's blocker, verbatim: *"`ARTIFACT_RETENTION_DAYS = 3` is in
`06-backend/apps/tenancy/exports.py:137` … A Reports settings card writing it
is a cross-module write, which B2 §2 forbids."*

**That is true of the CARD and false of the SETTING, and the difference is the
whole answer.** The constant was never reports'. It governs the **platform
export kernel** — every list export in this product runs through
`apps/tenancy/exports.py`, audit's and the platform's as well as reports' — so
the tenant-settable half belongs exactly where the constant does. Built as:

* **`settings_families.REPORTS`**, tenancy's sixth settings family, with
  `file_retention_days` (min 1, **no maximum** — `NFR-5`) and
  `default_download_format`. Tenancy declares it, validates it, writes it and
  audits it (`settings.reports.updated`).
* **`tenancy/0053`** — one `jsonb` column, defaulted by dotted path exactly as
  `0004` does for the other five, so a row seeded before anybody opens the card
  already reads `3` and `csv`.
* **`GET|PUT /settings/reports`**, the same `_rule_page` shape as the other four.
* **`apps/reports` READS it through the seam it has had since `P3.1`** and
  writes nothing. `report_seams.py` declares both reads.

**No module writes another module's row and no module writes another module's
constant.** The heading is presentation — `referenceDataConfig.ts` says so in
its own words (*"owner is not the group"*), and `reason_codes` is the worked
case: billing's, filed under Plans & Rates.

⚠ **THE PER-TENANT NUMBER OPENED A HAZARD THE CONSTANT DID NOT HAVE.**
`JOB_ARTIFACTS_DIR` holds every tenant's files in ONE directory, and
`purge_expired` swept it whole. The moment retention became per-tenant, a sweep
at one utility's one-day setting would have deleted another utility's
two-day-old file. `purge_expired` takes a `prefix` now — the same slug
`artifact_filename` already puts at the front of every name — and
`test_a_short_window_sweeps_only_its_own_tenants_files` asserts the sibling's
file SURVIVES, which is the half that would otherwise have passed silently.

### 14.3 · Two of the four cards, and the other two are ABSENT rather than empty

p048's TASK row splits the section on purpose: *"`P4.6` lands retention and the
default format one phase earlier … so two of the four cards arrive in Phase 4
and the section is completed in Phase 5."* That split is what shipped.

| Card | State |
|---|---|
| **File retention** | BUILT — `kind: "rules"`, opens `PUT /settings/reports` |
| **Default format** | BUILT — one ratified value, drawn as a fixed control |
| **Report groups** | NOT BUILT — needs a `report_categories` lookup handler AND a declaration in tenancy's `LOOKUP_LISTS`; `report_categories` is also a two-level tree (6 groups · 19 sub-groups), so it needs `hierarchical`'s four title keys as well |
| **Delivery** | NOT BUILT — see 14.5 |

⚠ **NEITHER MISSING CARD IS DECLARED WITH `arrivesWithKey`.** That key exists
for an honest promise and two cards already carry it; adding two more would
have put four *"arrives with"* cards in one grid with no dated owner for any of
them, which is hard-won law 2's mirror with better manners.
`retentionDoor.dom.test.tsx` asserts both codes resolve to NOTHING, so the day
either is added the case names itself.

⚠ **NEITHER BUILT CARD DRAWS A VALUE LINE, AND THE DRAWING DRAWS ONE.** p047
shows *"3 days"* under File retention and *"CSV"* under Default format. B14
rule 37 makes a drawn figure an ILLUSTRATION, and none of the three rule cards
this product already ships draws one. Drawing it would mean the grid reading
five settings families to head five cards — and a tenant on seven days would
read *"3 days"* on the card and *"7"* inside it. **Recorded as a deliberate
divergence rather than a miss.**

### 14.4 · `P5.12`, and the sentence that had gone false

The line under `5·1 History`'s table read **`"Files are kept for 3 days."` in
all eleven catalogues**, over a `3` the server had just made settable. A FALSE
fact in six words is worse than a long true one, so:

* `GET /reports/history` carries **`retention_days`**, computed by the same
  helper that decides whether a run's file has expired — so the sentence and
  the expiry cannot disagree. It is named explicitly in the view because
  `_envelope` keeps nothing it is not given.
* The line is a COMPONENT (B14 rule 43) — `RetentionNote.tsx`, 90 lines — and
  the catalogue string takes `{{days}}`, still six words in all eleven.
* **The link is admin-only and points at `?list=file_retention`**, the grid's
  own deep link, so the fact and the control are ONE click apart rather than
  one click plus a hunt through forty cards. A clerk sees the fact and no link,
  which is the task table's own OUTCOME column, and **nothing explains why** —
  rule 33 puts rationale at zero words.

### 14.5 · `Delivery` — §12.4's *"nothing to read"* is now WRONG, and it is still not a card

§12.4 measured *"`apps/reports/schedules.py` contains the string `delivery`
**zero times**"*. **That was true when it was written and is not true now.**
`aff5f079d` landed `apps/reports/delivery.py` (`P4.10`) and `schedules.py`
names it eleven times; `report_schedules.recipients` is read, resolved against
this tenant's staff and turned into a queued message.

**So Delivery has plenty to read and still has nothing to be.** p075's data
table gives the reason in the design's own words: *"Delivery — Where a schedule
sends its file. **A list**, because a utility has more than one recipient."* A
LIST card needs a list, and recipients are stored **per schedule**
(`report_schedules.recipients`), never per tenant. A tenant-level list of
destinations is a table this product does not have, and Phase 5's mix says
**0 DB**. The honest options are a `link` card to `4·1 Scheduled` or a new
table, and **both are a ruling rather than a build**: one changes what the
drawing says the card IS, the other adds storage the phase excludes. Left for
`P5.5` with this paragraph as its packet.

### 14.6 · Where Phase 5 stands now

| | |
|---|---|
| Rows in the table | **12** |
| Built | **11** — `P5.1`–`P5.4`, `P5.6`–`P5.12` |
| Half built | **1** — `P5.5`: two of four cards, the section and its group heading exist |
| Phase 4 | `P4.6` BUILT, which §12.4 recorded as never built |

### 14.7 · Rollback, stated before shipping

`migrate tenancy 0052` and revert the commit. The column goes and with it every
tenant override; `artifact_retention_days()` then answers the constant for
everybody, which is the behaviour of every build before this one. **Nothing is
deleted by the migration going backwards** — no file, no run, no schedule — and
no other table references the column. The one ordering that matters: revert the
FRONT end no later than the back, because `RetentionNote` renders nothing at all
when `retention_days` is absent (it is `null`-guarded on purpose), so a
front-end left ahead of a reverted server drops the sentence silently rather
than drawing a wrong number.

---

## 14 · PHASE 4 · THE DASHBOARD TAB — `P4.11` · `P4.12` · `P4.13` (lane REP-P4-DASH, 2026-09-27, `2.380.0`)

### 14.1 · The task count, counted again against this document's own table

§7.3's recount stands: **Phase 4 is FIFTEEN tasks**, `P4.1`–`P4.15`, and p014's
TASK MIX row describes only the first ten. Counted from the table rather than
from a report: `P4.1`–`P4.5`, `P4.7`, `P4.8` landed in `c7609569a`; `P4.9` and
`P4.10` are recorded above; **`P4.11`, `P4.12` and `P4.13` land here**. That
leaves **`P4.6`** (Settings — landed on the tip at `97ac0ddd0` by the Settings
lane while this wave was in flight), **`P4.14`** (BI tier 2) and **`P4.15`**
(the landlord portal view). **Phase 4 stands at 13 of 15.**

### 14.2 · §7.3's screen-number correction is confirmed against the drawings

`P4.11` and `P4.13` both name the dashboard **`4·1`**, and `4·1` is **Scheduled**
(p040). The dashboard is **`3·1`**, drawn on **p036** under the heading
*"3·1 · DASHBOARD · TASK P4.11 · RULED — A NEW TAB, NOT A REPLACEMENT"*. This
wave was built to **p036–p038, read as IMAGES** per B14 rule 42. A lane
following the task line would have built five panels onto the schedules table.

### 14.3 · What the drawing rules, and what it rules OUT

p038 answers the question this wave was sent to ask — *what chart, and what does
the kit already have?* — in its own TODAY row, verbatim:

> *"Does not exist. ⚠ And neither does **any chart anywhere in this product** —
> there is no charting library in `07-frontend/package.json`. The bars above are
> drawn in CSS, which is deliberate: five panels do not justify a dependency,
> and a CSS bar prints, scales and theme-switches for free."*

Checked against `package.json` before a line was written: **no `recharts`, no
`d3`, no `victory`, no `nivo`, no `apexcharts`.** **No dependency was added.**
The kit already held what two of the three bar panels needed:
`components/ContributionBars.tsx`, whose documented denominator is *"the LARGEST
ROW rather than … the total"* — which is word for word what p037 ⑦ asks of the
service mix. The twelve-bar revenue panel is ~40 lines of CSS in its own
component.

⚠ **`components/AgeingCards.tsx` WAS NOT REUSED, AND THAT IS A DECISION.** Its
own header says *"THE TONE IS THE BAND'S, NOT THE FIGURE'S"* — it colours `90+`
in the danger tier by position. p037 ⑥ rules the opposite for this panel and
argues it: *"One colour for every bar, on purpose. A first draft coloured them
by size, so the `Current` band — the healthy one — came out warning-coloured
because it was the biggest. Colour that encodes magnitude reads as a judgment."*

### 14.4 · The panels ask the catalogue's own resolver, and all four reports pass

The briefing that sent this lane said *"21 of 46 reports serve rows; the rest
refuse by name"*, and warned that a panel pointing at a refused report is a dead
control. **Measured, and the briefing is RIGHT:** asking
`runner.queries_for(key, dataset)` and `queries.definition_refusal(key, dataset)`
— the pair `catalogue_read.catalogue_payload` asks for every card — over all
forty-six seeded definitions gives **21 servable, 25 refusing**.

⚠ **AND THE FIRST MEASUREMENT OF THAT WAS WRONG IN THIS LANE'S OWN HANDS, WHICH
IS WORTH RECORDING.** Passed the report CODE (`R17`) instead of the definition
KEY (`revenue_by_service_rate`), both functions answered *servable* for all
forty-six — `_DEFINITION_REFUSALS` keys on the definition key, and a code it has
never heard of refuses nothing. **A check that answers confidently about the
wrong subject is law 7's fourth shape**, and the only thing that caught it was
that 46/46 disagreed with a sibling's number.

All four reports the five panels open are among the 21, verified on this
deployment's PostgreSQL: **R17 Revenue Analysis** (`journal_lines`), **R9 AR
Ageing** (`payments`), **R21 Close Pack** (`journal_lines`), **R30 Usage &
Ranking** (`meter_reads`). Every panel nevertheless asks
`queries.definition_refusal` before it is built, and a refused panel carries
**no `report_params` at all** — the destination is absent from the payload
rather than present-and-ignored, so the screen cannot draw a door by forgetting
to check a flag.

### 14.5 · WHAT A PANEL DOES WHEN ITS REPORT CANNOT BE PRODUCED — three cases, not one

This was asked as one question and the code answers it as **three**, because
they need three different sentences and a single one would be wrong twice:

| the case | what it means | what the panel does |
|---|---|---|
| the catalogue **refuses the definition** (`definition_refusal`) | this deployment cannot produce this report at all | `opens: false`, **no `report_params`**, so **no link is drawn**; the panel states the absence and keeps its heading |
| the report **ran and broke**, or refused at run time (`DatasetCannotServe`) | the report is real and this window did not answer | the panel's own `reason_code`; its five siblings are unaffected, because each is fetched and caught separately |
| the report **ran, is not refused, and published no figure** | nothing happened in this period | `no_figure_published_for_this_period` — a null WITH a reason (BR-REP-024), never a `0` |

The third is a real state on this deployment today: `payments_by_method` over a
period with no payments answers `{"count": 0, "amount": null}`. Without a reason
that tile would be a gap indistinguishable from a broken seam.

**And a KPI tile whose figure no report publishes at all is a FOURTH case, and
it is drawn rather than dropped:** `days to collect` reads *Not counted yet*
with `days_to_collect_is_not_published`. p037 ④ rules it — *"A tile whose owner
publishes no count reads Not counted yet with its reason"* — and dropping it
would leave the drawn band of four silently three.

### 14.6 · THE ONE DEFECT THIS WAVE CAUGHT IN ITSELF — `DEF-REP-6933`

⚠ **A FIRST DRAFT HANDED `ar_aging` A DATE RANGE, AND EVERY AGEING FIGURE ON
THIS SCREEN WOULD HAVE BEEN AN EM-DASH.** `datasets.PAYMENTS` declares the five
bands **semi-additive**, `slicers.footer_across` adds `time` to what a footer
spans whenever a report is given a range, and `additivity.footer` then replaces
every band total with `{"refused": true, "display": "—",
"reason_code": "balance_does_not_sum_across_time"}`.

**Measured on this deployment's PostgreSQL, both ways:**

| request | `totals.total` |
|---|---|
| `ar_aging?from=2026-09-01&to=2026-09-30` | **refused** — every band, with its reason |
| `ar_aging?as_of=2026-09-30` | **`8372.060000`**, over 26 accounts |

**Nothing in this repo would have caught it**, and that is the point: a refusal
IS a valid payload. The endpoint answers 200, `tsc` passes, and a case asserting
*"the panel has five bands"* passes over five dashes. It also reaches `P4.13`:
the panel's door has to spell `f.as_of` too, or a panel showing `$48,221.14`
opens a report showing five dashes — *"the numbers change under you and nothing
says why"*, which p038 calls worse than having no link at all.

**Two assertions now hold it**, one per side: the backend case asserts a band's
value is a **decimal string** and that `report_params` spell `f.as_of` and never
`f.from`; the dom case asserts a **formatted figure** and the **absence of an
em-dash**.

### 14.7 · THE HOLD EXPIRED, AND ALL THREE CASES WERE READ BEFORE ANY WAS EDITED

`/reports/dashboard` was the LAST of `P0.8`'s four reserved segments still
rendering `ReportsTabRoute`'s placeholder, and **three** tests pinned it there.
All three were **run and seen RED, naming the segment**, before one character of
any of them was changed:

```
× phaseHolds.dom.test.tsx > Dashboard is still a reserved segment
  → Dashboard → /brazosbend/reports/dashboard no longer opens the reserved
    placeholder, so Phase 4 has landed. DRAW THE FOUR-TAB STRIP on screen 1·1
    … and delete this case.: expected [Function ReportsDashboardPage] to be
    [Function ReportsTabRoute]
× reportsReservedSegments.test.tsx > /reports/dashboard opens its own tab
  → /brazosbend/reports/dashboard is answered by ReportsDashboardPage. CR-142
    P0.11: this reserved segment no longer has a route of its own …
```

The `Dashboard` tab is drawn in `ReportsTabs.LIVE_REPORT_TABS` and all three
expired cases are retired **in the same commit**. `P0.11`'s actual guarantee is
untouched: the *is NOT the report viewer* case still runs over **all four**
segments, and that is the one that says a tenant naming a report *Dashboard*
cannot take the word.

### 14.8 · What is NOT built, and why in each case

1. **`Biggest movers` draws no rows.** p037 ⑧ wants *top 3 by change, one
   service at a time*. `usage_and_ranking` is producible and serves the READS;
   **no definition in the catalogue publishes a per-account usage comparison
   between two periods.** Deriving one here is the arithmetic p038 forbids by
   name. The panel states the absence in six words and **keeps its door**,
   because the report itself opens and is real — two different sentences.
2. **`days to collect` has no figure**, for the same cause: no definition
   publishes a collection-days measure.
3. **`budget`, the third comparison p036 draws, is not offered.** Nothing in
   this product publishes a budget for any of the four KPIs.
   `report_seams.monthly_revenue_target()` is a single typed REVENUE target the
   SHELL dashboard renders (BR-REP-034); building *budget* on it would give a
   real comparison on one tile and an invented one on three — a screen wrong in
   a way a reader cannot see. Named on the payload rather than silently dropped.
4. **The download control p036 draws beside the two pickers is not built.** This
   screen composes FIVE reports over one window and there is no one file to
   produce; each panel's own report has a working Download. REPORTED.

### 14.9 · Divergences from the drawing, each reported rather than quietly taken

* The two period controls are the kit's `select` where p036 draws pill buttons
  with a chevron — **B14 rule 44**: the drawing says what is on screen and how
  it is arranged, our UI standard says how it is BUILT, and it wins every time.
* The comparison tokens say `period` where p036's copy says `month`. A tenant on
  a **quarterly** `close_cadence` has a three-month accounting period and a
  token spelled `same_month_last_year` would be a name that lies on every one of
  them. The words ON SCREEN still read *September 2026* for a monthly tenant,
  because the label is composed from the window the server served.
* The revenue axis draws **three** labels under twelve bars — which is p036's
  own arrangement, not a reduction.

### 14.10 · Two lane collisions this wave walked into, and what caught them

⚠ **THE VERSION WAS TAKEN TWICE WHILE THIS WAVE WAS IN FLIGHT.** `2.378.0` was
allocated, a sibling pushed `2.378.0` minutes later; `2.379.0` was allocated,
and the Settings lane pushed `2.379.0`. Both were caught by
`allocate.py version --verify` at push time — *"2.378.0: TAKEN —
origin/… carries it. Re-bump before you commit."* — which is exactly the
unconditional push-time re-derivation CLAUDE.md law 11 prescribes, and it is the
third family (defect id · gate number · version) to collide on this branch.

⚠ **AND THE RE-DERIVATION HAD TO RUN THREE TIMES, NOT ONCE.** The tip moved
twice more while this wave was being proved, and both times it carried
`apps/reports/api.py` and all eleven locale catalogues. Each time, `api.py` was
re-fetched from the new tip and the two-line splice re-applied, and the
catalogues were re-fetched and the fan-in re-run — never patched from the copy
in hand. A `10-scripts/`-style helper was written for it so the third run was
one command rather than a fresh chance to revert a sibling.

### 14.11 · Rollback, stated before shipping

Revert the commit. **There is no migration and no data to lose** — every file
added is a read path, a screen or a test, and the only edits to existing files
are a two-line route splice in `apps/reports/api.py`, one route and one import
in `App.tsx`, one entry in `LIVE_REPORT_TABS`, the G31 ledger, the version and
the catalogues.

**The one ordering that matters:** a revert must not leave the `Dashboard` tab
drawn in `ReportsTabs` while `/reports/dashboard` returns to the placeholder.
That combination is hard-won law 2's mirror exactly — a live nav word over a
screen that says *"Arrives in a later release."* — and it is the state the three
hold cases existed to prevent. Reverting the whole commit restores all three
together, which is why they are retired in the same commit rather than earlier.
---

## 15 · `P4.6`/`P5.12` PROVED IN A BROWSER, AND TWO DEFECTS FOUND DOING IT (lane REP-P5-SETTINGS, 2026-09-27, `2.379.0`)

⚠ **THIS CONTINUES §14 ABOVE — THE FIRST §14, `P4.6` BUILT AND `P5.12` BUILT.
THERE ARE TWO SECTIONS NUMBERED 14 IN THIS FILE AND NEITHER IS WRONG:** this
lane landed its `## 14` at `97ac0ddd0` and lane REP-P4-DASH appended a second
`## 14` at `596f179a4` half an hour later, each correctly taking "the next
number" from the file it had. That is `CR-090-BRC01`'s duplicate-NUMBER shape
one file down, and git cannot see it — two appends to one file merge cleanly.
**Neither heading is renumbered**, for the reason `OQ-291` is not zero-padded:
a renumber moves every cross-reference at once. This section is 15 and says
which 14 it belongs to.

### 15.1 · Walked in a browser at 1440 and 1280 — `0 FAIL · 1 CANNOT`

`10-scripts/rep_p4_6_retention_walkthrough.mjs`, against the deployed join
(vite build → `server.mjs` → Django on real PostgreSQL 16), screenshots in
`scratchpad/po-shots/p5-settings/`. **Every retention proof is a PAIR**, because
a screenshot of a form with `3` in it proves a form renders and nothing else:

> BEFORE · `5·1` retention line reads: **"Files are kept for 3 days. Change this"**
> AFTER  · `5·1` retention line reads: **"Files are kept for 9 days. Change this"**

— with the value changed on the Settings form in between, re-read from a cold
load to prove it persisted, and put back afterwards. Both widths. The door's
`href` is asserted as a string and printed:
`/brazosbend/settings/reference-data/reference-data?list=file_retention`.

`tenancy/0053` was proved forward → back → forward on PostgreSQL 16 on a
separate database, and the grid's eleven group headings were read off the
rendered page: `Platform-wide … Work, Finance, Reports`.

**The one `CANNOT`, counted rather than passed quietly.** The clerk half was not
walked: the seeded `sam.reyes@sample.test` is `status=invited` with no usable
password — a FIXTURE gap, not a product one, and the same one §12.3 records for
`P5.8`'s private/shared pair. The assertion is made in
`retentionDoor.dom.test.tsx` instead, mounted under the real route pattern with
a `billing_clerk` permissions payload.

⚠ **TWO OF THIS SCRIPT'S OWN CHECKS WERE WRONG BEFORE THEY WERE RIGHT, AND BOTH
ARE LAW 7's *LOOKING AT THE WRONG THING*.** The first draft asked for
`input[type="number"]` and reported `CANNOT change the value` over a form that
works — every rule-page value is a TEXT input, because a decimal is never parsed
into a binary float (hard rule 2). It also tested `/CSV/` against
`body.innerText`, which does not contain what is inside an input, and reported
`FAIL` beside a screenshot showing the control reading `CSV`. A third was a
fixed 1500 ms sleep that reported both cards MISSING at 1280 over a page that
draws them; it waits for the heading now. **All three were found by comparing
the check against the picture it was taken with**, which is the only thing that
could have found any of them.

### 15.2 · Two defects filed, neither this lane's, both dated with `git log -S`

⚠ **THEY WERE FILED AS `DEF-REP-6933`/`DEF-TEN-6934` AND ARE `DEF-REP-6934`/
`DEF-TEN-6935`, BECAUSE A SIBLING TOOK 6933 WHILE THIS LANE WAS WALKING THE
BROWSER.** `file_defect.py` was right both times — lane REP-P4-DASH's row was
in no world this checkout could see until it pushed. **It was caught by
re-deriving the ids at push time from the pinned tip**, which is CLAUDE.md law
11's unconditional step and not a branch of any conflict handling: the register
merged cleanly, so nothing would have gone red and the register would simply
have published two `DEF-REP-6933`s.

* **`DEF-REP-6934`** — `G134` has been RED since the commits that added the
  tokens: `border-border` in `ReportEditPanel.tsx` (`b3699fb1f`, `2.365.0`,
  the `P5.1`–`P5.11` lane) and `buttonClasses("primary", "default")` in
  `RunDialog.tsx` (`007510e95`, `2.363.0`, `P3.1`–`P3.6`) emitting its
  ARGUMENTS as class tokens. Three class names that compile to no CSS rule at
  all, over which `tsc`, `eslint` and `toHaveClass()` all pass.
* **`DEF-TEN-6935`** — **every** Settings rule page prints a rule id at a clerk:
  the help line under each field reads *"Set by BR-REP-018"*. B14 rule 32
  clause 4 bans it and was ratified three weeks after the string shipped. The id
  is INTERPOLATED (`"Set by {{br}}"`), so every gate that greps catalogues for
  `BR-`/`US-`/`OQ-` passes over it — the blind spot `DEF-2882`'s own prevention
  note already named. **It is on this lane's two new forms too**, and is NOT
  fixed here: the string is shared by six forms and rewording it is a
  product-wide copy change with its own blast radius.

* **`DEF-REP-6936`** — a THIRD red, found by running the check the ledger entry
  below hands `RetentionNote.tsx` to. `routeBUtilities.test.ts` has been red
  since `a771036f2` (`2.362.0`) and `b0a900c4e` (`2.372.0`) on two CSS custom
  properties no theme declares — `--fin-muted` on the `2·1` viewer and
  `--fin-ink` on the group row. **An arbitrary value naming an undeclared
  property COMPILES**: Tailwind emits the utility, the browser parses
  `var(--fin-muted)` with no fallback, finds nothing and DROPS the declaration,
  so the text simply renders in the inherited colour and every other check
  passes. The names look like the finance theme's, which is what makes them
  read as correct at a glance. **This lane's four utilities all compile** —
  none of the five names `RetentionNote.tsx`.

⚠ **`src/styles/route-b-migrated.txt` GAINED `RetentionNote.tsx`, AND THE REASON
IS WORTH THE LINE.** `G31` went red on four Tailwind utilities in the new
component. CLAUDE.md's own correction of that warning is the fix: **the ledger
gates the CHECKS, not the CSS** — a utility in an unlisted file renders fine and
fails a gate, and the repair is to list the file, never to reach for a
stylesheet class, which is what rule 21 forbids.

### 14.12 · WHAT THE BROWSER FOUND THAT NOTHING ELSE COULD — THREE DEFECTS IN ONE PASS

⚠ **THE SUITE WAS GREEN, `tsc` WAS CLEAN, BOTH RULE-21 GATES WERE SATISFIED, AND
THE SCREEN HAD THREE FAULTS ON IT.** CLAUDE.md hard-won law 6 in one paragraph —
*"No gate looks at rendered output. Nine defects were found this way and by
nothing else."* Walked at 1440 and 1280 against a real PostgreSQL:

| what the photograph showed | why every check passed over it | `DEF` |
|---|---|---|
| the Close Pack head read **`DifferenceResult`** and its row read **`$0.00Foots`** — two columns touching | a `<td>` with no padding is a perfectly good `<td>` and its text is exactly right. The dom case asserts the word *Foots* INSIDE the row and would pass however tightly it sat | `DEF-REP-6938` |
| **Service mix was a blank box** — a heading, a link and two inches of nothing | September 2026 has no revenue here, so the server correctly served an empty list and `ContributionBars` correctly rendered an empty `<ol>`. Every layer was right. The fixture carried three services, so no case ever mounted the empty shape | `DEF-REP-6939` |
| at **1280** every ageing figure wrapped onto its own line under its bar | ⚠ **`styles/tailwind.css` REDEFINES THE WHOLE SCALE AND THIS PROJECT'S `xl` IS 1100px**, not Tailwind's 1280 — so `xl:grid-cols-2` put TWO columns at 1280, and half of 1280 is not the ~490px `ContributionBars` needs (a 200px label, a 180px track, a 110px figure). The brief says build at 1440 and WORK at 1280; `2xl` here is 1440 exactly, so `2xl:grid-cols-2` gives the drawing's two columns at the build width and one honest column below it. Fixed in place. **A lane reading Tailwind's published breakpoints instead of this repo's would get it wrong every time** | fixed in place |

⚠ **AND A FOURTH, WHICH IS ANOTHER MODULE'S AND IS FILED RATHER THAN FIXED —
`DEF-PAY-6940`.** `ar_aging` answers the **same five band totals for every
as-at date**. Measured at `2026-09-30`, `2025-09-30` and `2024-01-31`:
`31-60 = 7678.460000`, `61-90 = 693.600000`, `total = 8372.060000`, 26 accounts
— byte-identical, all three. It takes `as_of` and uses it to BAND the bills; the
SET it ages is whatever is outstanding now.

**The visible consequence is on this screen:** the `Outstanding` tile reads
*0.00% against the comparison* and will for ever, on every tenant. It is
REPORTED rather than papered over — suppressing the comparison here would hide
another module's defect behind this screen's copy, and that tile would then be
silently different from its three neighbours for a reason no reader could find.
Nothing caught it because every existing case passes a SINGLE date: a report
parameter that nothing varies is a parameter nothing tests.

## 15 · `P5.5` COMPLETE — the Delivery card is a LINK, and Phase 5 closes (lane REP-SUBJECTS, 2026-09-27, `2.381.0`)

**`BR-REP-044` (PO ruling 2026-09-27, option (a) of two, answered *"a"*) built.**
§14.5 left this card with its packet written and the ruling outstanding; the
ruling arrived and the card is the LINK, not the list the drawing draws.

### 15.1 · What landed

`07-frontend/src/features/tenancy/referenceDataConfig.ts` gains one card —
`code: "delivery"`, `kind: "link"`, `target: "/reports/scheduled"`,
`owner: "reports"`. Two keys in all eleven catalogues
(`settings.reference.card.delivery` · `settings.reference.sample.delivery`),
fanned through `10-scripts/i18n_fanin.py`; every catalogue now holds **20,944**
keys, parity intact.

**It needed NO new rendering code, and that was checked rather than assumed.**
`kind: "link"` is a shape this grid already ships: `SettingsReferenceData.tsx`
navigates on click (line 538) and `badgeFor` gives a link card the
`opensElsewhere` badge rather than a count (line 592). `templates` and
`work_parts` already stand on it (`BR-TEN-033`). So this is hard-won law 2
checked in the direction that matters — the card is not a component nothing
passes a prop to; it joins a path the product already walks.

⚠ **`owner: "reports"`, unlike its two neighbours in this group.**
`file_retention` and `default_format` are `tenancy`'s because the numbers they
govern live in the platform export kernel (§14.3). A report SCHEDULE is reports'
own, so the frame header names the right module.

### 15.2 · The guard that was designed to fire, fired

§14.3 recorded that `retentionDoor.dom.test.tsx` held both missing codes to
NULL *"so the day either is added the case names itself"*. It did, by name:

```
× does NOT declare Report groups or Delivery — P5.5's half is not built
  → expected { code: 'delivery', …(6) } to be null
```

That is a hold with a test behind it working exactly as hard-won law 2's mirror
asks — and it is worth recording that it cost nothing to honour, because the
case said what to do. `delivery` leaves that assertion and gains one of its own;
**`report_groups` stays**, so the remaining half still names itself.

The new case asserts the destination **BY ADDRESS** — `matchRoutes(APP_ROUTES,
"/reports/scheduled")` — and not merely that some target is set, which is the
assertion that fires if `4·1 Scheduled` is ever moved or renamed. It also
asserts `arrivesWithKey` is `undefined`: the ruling's whole point is that this
card is not a promise.

### 15.3 · `DEF-REP-7050` — a pin that was red all day, and nobody read it

⚠ **NOT THIS LANE'S, AND DATED WITH `git log -S` RATHER THAN ASSUMED.**
`SettingsReferenceData.test.tsx`'s `BR-SHL-035` case pins the rule-card list. It
expected **6** codes and `ruleCards()` returned **8** from the moment `97ac0ddd0`
(`P4.6`, `2.379.0`, 2026-09-27) added `file_retention` and `default_format` as
`kind: "rules"` cards without moving the pin.

**It could not have been this lane's**, and the arithmetic is the proof rather
than a claim: this lane added a `kind: "link"` card, and `ruleCards()` filters
`kind === "rules"`. 8 − 6 is exactly `P4.6`'s two.

The pin did its job — it exists so a rule card cannot arrive unnoticed — and the
failure is that **nobody read its output**, which is hard-won law 7's first
shape: *a guard is a claim only while somebody reads it*. FIXED here (the two
codes join the list, with the date and the cause in the comment).

The `+3` remainder in the same file becomes `+4` for the new link card, which is
this lane's own and is marked as such.

### 15.4 · Proof

| | |
|---|---|
| `retentionDoor.dom.test.tsx` · `SettingsReferenceData.test.tsx` · `i18n/locales.test.ts` | **81 passed, 8 todo, 0 failed** |
| Guards proved RED first | **4** — both `delivery` cases, the `+3` count, and `DEF-REP-7050`'s pin — then green |
| `tsc --noEmit` | exit **0**, with the LOCAL TypeScript **5.5.4** from `node_modules` (law 7: `npx tsc` in a worktree with no local install fetches a newer one and can report no errors at all) |
| Catalogue parity | 11 files, **20,944** keys each |

### 15.5 · Where Phase 5 stands now

| | |
|---|---|
| Rows in the table | **12** |
| Built | **12** — `P5.1`–`P5.12` |
| `P5.5`'s four cards | File retention · Default format · **Delivery** built; **`Report groups` NOT built** and still needs a `report_categories` lookup handler, a `LOOKUP_LISTS` declaration and `hierarchical`'s four title keys (§12.4) |

⚠ **`P5.5` IS COMPLETE AS A TASK AND ITS FOURTH CARD IS NOT BUILT.** Those are
two different statements and collapsing them is how a phase reports done over a
gap. The task's blocker was a RULING (§14.5) and the ruling is built; `Report
groups` was never blocked on a ruling, it is blocked on a lookup handler, and it
is recorded here rather than folded into a tick.

### 15.6 · Rollback, stated before shipping

Revert the one card object in `referenceDataConfig.ts`, restore the two
assertions in `retentionDoor.dom.test.tsx`, put the remainder back to `+3`, and
retire the two catalogue keys through `i18n_fanin.py`. **`DEF-REP-7050`'s fix is
independent and should NOT be reverted with it** — it was red before this lane
arrived and would go red again.

## 16 · PHASE 4 CLOSES — `P4.14` (BI tier 2) AND `P4.15` (the landlord's own account only) (lane REP-P4-LAST, 2026-09-27, `2.383.0`)

⚠ **THERE ARE TWO SECTIONS NUMBERED 14 AND TWO NUMBERED 15 IN THIS FILE AND
NONE OF THEM IS WRONG** — §15 above already records why for the pair of 14s,
and a second 15 arrived the same way half an hour later. **Neither is
renumbered**, for the reason `OQ-291` is not zero-padded: a renumber moves
every cross-reference at once. This is 16 and it follows the LAST 15.

### 16.1 · The task count, recounted off the rendered pages — **15, and 13 were built**

Counted independently of §7.3 and of §14 (REP-P4-DASH), from p014–p016 rendered
as IMAGES at scale 4 (B14 rule 42), 2026-09-27: **Phase 4 is `P4.1`–`P4.15`.**
§7.3's recount stands and this lane confirms rather than corrects it.

⚠ **p014's own TASK MIX row still reads `1 DB · 2 Backend · 2 Front end · 1
Settings · 2 Test · 1 E2E · 1 Other-module` — TEN**, and it describes
`P4.1`–`P4.10` exactly. `P4.11`–`P4.15` are appended below it. That is the
brief disagreeing with itself, already recorded at §7.3; it is re-measured here
because a count nobody re-derives is a count that rots.

| built before this lane | `P4.1`–`P4.5`, `P4.7`, `P4.8` (`c7609569a`) · `P4.9`, `P4.10` (`aff5f079d`) · `P4.6` (`97ac0ddd0`) · `P4.11`–`P4.13` (`596f179a4`) |
|---|---|
| **built here** | **`P4.14`** (the signed-link half) · **`P4.15`** |
| **NOT built here, and named** | `P4.14`'s **SFTP** transport — `OQ-REP-12767`, OPEN |

### 16.2 · `P4.14` — what a signed link permits, and for how long

The ruling is p090's decisions register, **FINAL**: *"A scheduled file may leave
the product — **Yes** — admin-set destinations, encrypted in transit, every
delivery logged."* Its three conditions map to code one for one:

| condition | how it is structural rather than remembered |
|---|---|
| set up **by an administrator** | `report_destinations` is its OWN table with its own role gate. A schedule POINTS at a row (`report_schedules.destination_id`) and cannot describe a destination, so the act p015 forbids — *"a clerk schedules the debtor list … to a personal address"* — has no field to happen in |
| **encrypted in transit** | the one transport built is HTTPS |
| **every delivery logged** | a `report_deliveries` row AND an `audit_log` entry. Two records, two questions: the audit row answers *who caused data to leave*, the delivery row answers *did it go and may this link still be redeemed*. The audit row is pruned on the utility's retention schedule; the operational one is not a second copy of it |

**WHAT A LINK PERMITS — the whole list, and it is short.** ONE job's artifact ·
ONE tenant · **FOUR HOURS** · READ, and there is no verb in the payload because
there is only one. It carries no session, no role and no user.

⚠ **THE FOUR HOURS ARE NOT THIS LANE'S NUMBER AND THAT IS THE POINT.** A link
lifetime is a security parameter and a lane may not choose one — it did not have
to. The PO ruled this exact question on **2026-08-30**, verbatim: *"dont expire
it in minutes - exprise it in 3 or 4 hours"*, and
`apps/tenancy/document_storage.url_ttl_seconds()` is that ruling in code, a CAP
rather than a clamp, refusing by name if an operator lengthens it.
`signed_links.ttl_seconds()` **CALLS** it rather than declaring a constant
beside it, and the test asserts the two AGREE rather than asserting `14400` —
because a literal here would be a second copy of a ruled figure, free to go on
passing after a re-sign moved the real one.

⚠ **THE BRIEFING THIS LANE WAS GIVEN SAID THERE WAS *"no SFTP or signed-URL
delivery anywhere in the product"*. THAT IS WRONG IN TWO PLACES AND BOTH
MATTER.** `apps/tenancy/document_storage.py` has carried a PO-ruled signed-URL
contract since 2026-08-30 — four hours, tenant-prefixed keys, `_require_key`
refusing a composed one — and `apps/integrations/manifests/accounting_file.py`
already carries a complete SFTP path with its client absent and NAMED. Had the
briefing been believed, this lane would have invented a link lifetime the PO had
already ruled on, which is law 13's manufactured inconsistency exactly.

**Six forgeries are asserted refused** (`tests/test_cr142_p4_14_signed_delivery.py`),
each taking a known-good token and breaking one thing: a flipped signature · a
swapped job · a swapped tenant · an extended `exp` · a token read past its `exp`
· a foreign prefix. The happy path is ONE case and the refusals are six, because
a verifier that returns the payload unconditionally passes *"a minted token
verifies"* exactly as well as a correct one does (law 7).

### 16.3 · `P4.14`'s SFTP half is NOT built — `OQ-REP-12767`, OPEN

⚠ **TWO SEPARATE THINGS ARE MISSING AND ONLY ONE OF THEM IS CODE.**
**(a) A decision nobody has made.** An SSH client must do something the first
time it meets a host key. *Accept whatever the server presents* is the default
of every convenient library and it is a man-in-the-middle **with no symptom**:
the transfer succeeds, the delivery is logged as sent, and p015's own *"412
names, addresses and balances"* are read by whoever answered. Pinning a
fingerprint is a fact **only the customer holds**. **A lane may not pick one.**
**(b) No client** — `paramiko`, `pysftp` and `asyncssh` are all absent from this
deployment, **checked on 2026-09-27, not assumed.**

Grepped before asking (law 13): `02-decision-log.md` and `01-open-questions.md`
hold **zero** occurrences of `host key`, `known_hosts` or `fingerprint`. New
question, not a re-ask.

⚠ **REFUSED AT *CREATE*, NOT ONLY AT SEND, WHICH IS LAW 2's MIRROR.** A
destination of kind `sftp` that could be created and then failed every night
would be a live control over a dead transport: an administrator sees it in the
picker, a clerk chooses it, and the failure lands weeks later as an operational
mystery. `destinations.create` refuses the kind outright, so the picker has
nothing to offer. When the question is answered the refusal moves and the form
gains a field — **one commit, both halves**, which is the hold-with-a-test
discipline law 2's mirror asks for.

### 16.4 · `P4.15` — a landlord sees their own account only

The ruling, p070–p071 and p016, **LAW**: *"This report crosses customers — and
that is now ruled. Staff see it as drawn. In the customer portal a landlord sees
**their own master account only**: the $69.60, never Unit 3's $100.00."*

⚠ **THE SCOPING IS NOT A FILTER OVER THE STAFF REPORT, AND THAT IS THE WHOLE
TASK.** The tempting build is *run `R24c`, then drop the rows that are not
yours*: five rows fetched, four discarded, and every figure the landlord must
never see already assembled in memory one serialiser from the wire.
`apps/portal/premises_statement.py` never asks *what is at this premises*. It
asks *which of MY accounts are here*, starting from `principal.account_ids`.
**There is no widened query for a screen state to reach.**

⚠ **THE SUBJECT IS AN ACCOUNT, NOT A PREMISES, AND THAT CLOSED A HOLE AS WELL
AS A RULE.** `portalRoutes.tsx` reads B14 rule 31 as reaching URLs — *"a
database id in a URL is a database id on screen"* — and a premises has no human
reference a customer could quote the way `BL-2608-0141` is printed on their
bill. So the endpoint is `GET /portal/accounts/{id}/premises-statement`, the
screen is `/{tenant}/portal/property` with **nothing in the path**, and the
shell's switcher says which account. The side effect is the better half: **there
is no id a stranger could supply at all**, because the one the read starts from
came out of their own session.

⚠ **`UNITS BILLED` IS NOT SERVED.** p070's third KPI counts the BUILDING's
billed units — `4` — and it is the one figure on that drawing that is a fact
about other customers rather than money belonging to them. Stated here and in
the module's own docstring; the SCREEN says nothing at all, because B14 rule 33
puts rationale at zero words and a page explaining what it is not showing breaks
that rule while trying to obey this one.

⚠ **`COMMON AREAS` IS THEIRS OR IT IS ABSENT — never `$0.00`** (`BR-CWP-093`).
A zero would be a claim about what this building's common areas cost, read by
somebody it is not about.

⚠ **THE DRAWING'S `CUSTOMER` COLUMN IS REPLACED BY `holding`, AND THAT IS A
JUDGMENT WITH A REASON.** p070 draws CUSTOMER because a staff reader looks
across five customers. Every row here belongs to the signed-in person by
construction, so the column would repeat their own name down the page — except
on a DELEGATED account, where it would name the holder who invited them.
`source` (`holder` | `delegate`) is the fact that actually varies.

**`CWP-078` is taken from CR-068 §9's own *"Next free ground"* and §9 is amended
in the same commit** — G82 refuses an id the register does not allocate, and an
id allocated in code but not in §9 is an id nobody can look up in a bug report.
Its `blueprint` column names **`R24c`**, the REPORT it serves, because the
customer-portal blueprint draws no property statement at all; naming a portal
page it does not have would be a cross-reference to nothing.

### 16.5 · What this lane could NOT do, counted rather than passed over

* **The SFTP transport** — `OQ-REP-12767`, above. Deliberate.
* **The browser walk and the RLS proof** were **not completed**. The machine
  carried a load average of **45** with twenty sibling `pytest` processes on it;
  the seeded template database `proof-db.sh build --force` needed was still
  migrating, and a single `tsc --noEmit` did not finish in 590 s. **The proofs
  that DID run are named in 16.6 and the two that did not are named here rather
  than implied** — hard-won law 7's fifth shape: an absence with no number
  beside it is indistinguishable from a pass.
* **The version files** (`package.json`, `package-lock.json`, `pyproject.toml`)
  are NOT written by this commit: all three moved under this lane's base while
  it worked, and writing them from a stale read is law 11's revert-by-
  subtraction. `2.383.0` is allocated and recorded here.

### 16.6 · What was proved, and how

* **`PremisesStatement.dom.test.tsx` — 4 cases, green, and the leak guard was
  PROVED RED FIRST.** Unit 3's row was added to the landlord's fixture, as a
  leaking server would send it, and the case failed on exactly the sentence it
  exists for: `AssertionError: expected '1408 Elm StreetAccounts1Charged$69.60…'
  not to contain '$100.00'`. Restored byte-for-byte afterwards.
* ⚠ **THE ABSENCE IS ASSERTED OVER THE WHOLE RENDERED PAGE, NOT OVER A CELL.**
  `queryByText` on a column somebody remembered to name passes over a total, a
  tile or a `title` carrying the same figure — which is exactly how a scoped
  screen leaks. The backend cases do the same thing to the serialised payload.
* **Both new routes RESOLVE** — checked through `django.urls.resolve`, not
  assumed: `/api/reports/delivery/{token}` → the view, and
  `/api/brazosbend/portal/accounts/{id}/premises-statement` → the view.
* **`makemigrations --check` is clean** after `reports/0009`, whose RLS policy
  is in the SAME migration as its tables — `0006`'s posture, for `0006`'s
  reason: these two tables decide where a utility's data may leave the product.
* **The 11 catalogues were re-derived from the pinned tip and re-applied**
  through `10-scripts/i18n_fanin.py` after the tip moved under this lane;
  verified as additions only (`0` deletions against the tip).

### 16.7 · A red this lane did not cause, DATED

* **`G107`** has been RED on four portal files (`md:hidden` in a desktop-first
  theme) since **2026-09-08** — `a2aa63cfb`, `e83971d55`, as `MyAccounts.tsx`'s
  own comment already records. This lane did not cause it and **did not join
  it**: `PremisesStatement.tsx` writes `max-md:flex` / `max-md:hidden`.

## 17 · `P2.15` — THE UNIT SUBJECT SERVES ROWS (lane REP-SUBJECTS, 2026-09-27)

**`BR-REP-043` (PO ruling 2026-09-27), verbatim: *"we can do based on regualr
account, master account, premises, units, customer id"*, and asked again about
this one specifically, *"yes; i can generate statement for Unit"*.**

§11.3 recorded why this did not land: *"the `unit` subject needs a running-record
read model in `apps/ledger`, which no seam publishes."* It publishes one now.

### 17.1 · What the build actually was, and why it is a LEDGER task

`P2.15` is filed as a **Front end** task and is a ledger task — `DEF-REP-6859`'s
misfiling, confirmed a third time. Nothing on the screen needed inventing; what
was missing was `apps.ledger.reporting.unit_ledger`.

**IT IS A SEPARATE READ MODEL AND NOT `account_ledger` WITH A FILTER, AND THAT
IS THE WHOLE DESIGN DECISION.** `account_ledger` opens on ONE account and every
figure it strikes — the opening balance above all — is that account's. A unit's
window can span a move-out, so its rows belong to two or more accounts and its
opening balance is the sum over all of them. Handing `account_ledger` a unit
filter would have produced **an opening balance for one account and rows for
several**: a document that does not add up, which is the one thing a statement
may never be.

| piece | where |
|---|---|
| the read model | `apps/ledger/reporting.py` · `unit_ledger` + `UnitLedgerRow` |
| the Occupant's NAME | `apps/ledger/dimension_seam.py` · `customer_labels` |
| the seam | `apps/reports/report_seams.py` · `unit_ledger` |
| the wiring, columns and head | `apps/reports/statement.py` |

### 17.2 · The Occupant column, and the one way it could have been wrong

⚠ **IT READS `journal_lines.customer_id` — THE HOLDER AT POSTING — AND NEVER A
JOIN THROUGH TODAY'S HOLDER.** A reader walking `journal_lines → accounts →
customer_accounts` gets *who holds this account NOW*, so on the day an account
changes hands every historical line silently re-attributes itself to the new
occupant: **figures still footing, still balanced, about the wrong person.** A
unit outlives its tenants, so that is not a corner case here — it is the
ordinary case, and it would print the new tenant's name over the old tenant's
arrears. `dimension_seam.customer_id_for_account` already makes this argument
for the posting-time stamp; this column is the first reader to depend on it.

The test asserts it from the side that actually separates the two
implementations: not merely that both names appear, but that **Marisol's two
rows are hers and Dwayne's one row is his**. An implementation reading today's
holder puts one name on all three and still contains both names in the head.

⚠ **AND THE COLUMN IS ON THIS SUBJECT AND NO OTHER**, asserted from both sides
so a branch that stops branching fails — a column of one repeated value on an
account statement is furniture, not information.

### 17.3 · Hard rule 8, and the key that is asserted ABSENT

The head reads the **premises' address** (`163 Willow Bend Dr`) plus the unit's
**label** (`Unit 1`), walked through `dimension_seam`. There is no
`unit_address` and the test asserts that key is **absent by name** — a key that
does not exist cannot be read by accident by a later screen.

### 17.4 · Proved on REAL PostgreSQL 16 (law 14), with figures

The suite runs on SQLite, where RLS does not exist and a `LIMIT` that was
applied looks identical to one that was not. Measured on the seeded
`Brazos Bend Utilities`, 661 journal lines, all carrying `unit_id`:

| | |
|---|---|
| head | `premises_address` **`163 Willow Bend Dr`** · `unit_label` **`Unit 1`** — the premises' address, never the unit's |
| money | charges **`470.590000`** · payments **`470.590000`** · closing **`0.000000`**, and the last row's running balance **equals** the closing balance |
| columns served | 9 — `entry_date, type, reference, description, occupant, account, charge, payment, running_balance` |
| Reference | **`BL-2607-000029`** — the document number, never a uuid (B14 rule 31) |
| Account | **`AC-2026-00032`** — the account number, never a uuid |
| first page / last page / export | **0.340s · 0.744s · 0.212s** |
| carry-forward, paged vs unpaged | **IDENTICAL**, walked page by page at `per=2` |
| closing balance across every page | **IDENTICAL** — the window's, never the page's |
| through `runner.run` and `runner.stream_for` | viewer 6 rows · export 6 rows, `subject`/`subject_id` **not dropped** (`dropped: ()`) |

⚠ **THE COST FIGURES ARE OVER A SMALL UNIT AND ARE SAID SO RATHER THAN
GENERALISED.** The busiest unit on this database carries **6** AR lines, so
these timings prove the paging WORKS and prove nothing about its cost at scale.
A blind spot with no number beside it is indistinguishable from an empty one
(law 7's fifth shape).

**ISOLATION** — `10-scripts/rep_p2_15_unit_statement_rls_proof.py`, and it
exists because `P2.15` added a read whose WHERE clause names **`unit_id` alone**,
a predicate no report had ever filtered on, **with a value that arrives in the
URL**. Probed as a role that is neither SUPERUSER nor BYPASSRLS (asserted, not
assumed), over **7 tables**, with the neighbour's balanced pair PLANTED and
**proved visible from the neighbour's own context first**, my own count asserted
NON-ZERO (**661**) so a zero beside a zero cannot read as isolation, and the
neighbour asserted invisible **four ways** — unfiltered, by `tenant_id`, by memo,
and **by `unit_id`**, which is the one this script exists for. Nothing planted
survived, checked from a **separate connection**.

⚠ **THE DATABASE REFUSED THIS PROOF THREE TIMES BEFORE IT PASSED, AND THAT IS
THE FINDING WORTH KEEPING.** `trg_journal_lines_sole_writer` refused the plant
(hard rule 5, enforced in PostgreSQL and not only in code), the same guard
refused it on `journal_entries`, and `trg_journal_line_append_only` refused a
line joining an already-POSTED entry (hard rule 4). Every one of them was the
guard working on its reader. The script sets `app.ledger_posting` explicitly,
inside a transaction it rolls back, and says so in its own docstring.

### 17.5 · `DEF-REP-7051` — the Occupant column is EMPTY on every existing row

⚠ **NOT A BUG IN THIS BUILD, AND IT IS THE FIRST THING A READER SHOULD KNOW.**
Measured: of **661** journal lines on the seeded tenant, **661 carry `unit_id`
and ZERO carry `customer_id`.** Customer stamping landed on 2026-09-24
(`P0.1`), hard rule 4 forbids a backfill, and `dimension_seam`'s own comment
already says NULL *"is already a lawful, permanent state"* on that column.

So on every line this product has written to date the Occupant cell is **empty**,
and `GAP_OCCUPANT_NOT_STAMPED` fires and says why. **It is said rather than
guessed**: filling it from today's holder is precisely the defect 16.2 is about,
and the gap is CONDITIONAL so it is announced only on a page that actually holds
such a row (`DEF-CWP-3925`'s shape — a refusal that outlives what it refused
over).

**The column populates for lines posted from now on.** That is a real limitation
of the SHIPPED data rather than of the code, and it is filed so nobody reads an
empty column as a broken one.

### 17.6 · The money columns are now typed BY THE SERVER

`charge`, `payment` and `running_balance` are this viewer's own derived columns
— **no dataset declares them** — so `runner`'s defaulting loop omits them, and
its own comment says an omitted column means *render it as text*.

⚠ **THEY RENDER CORRECTLY TODAY ONLY BECAUSE `ReportViewerPage.tsx` KEEPS A
HAND-TYPED MAP** with `statement: ["charge","payment","running_balance"]` in it,
which the screen consults SECOND. That was checked rather than assumed — the
first reading of this was that a clerk already sees `84.200000`, and **that was
wrong**; the fallback covers it. But a report typed only there is one rename away
from `DEF-REP-6902`'s exact fault, and the map is keyed by report KEY rather than
by subject, so a money column added to the unit subject later would be typed by
nobody. The viewer now publishes `column_meta` for all three, and the test
asserts `occupant` and `account` are **not** money.

### 17.7 · What did NOT land, and the reason in each case

| | why |
|---|---|
| **`P2.8` · `P2.16` — no page retired** | **Deliberate, and it is the ORDER RULE.** *Serve the subject → prove it → then retire the page.* The `customer` and `premises` subjects still REFUSE, so their definitions cannot render and a redirect would land on a refusal — the dead-control failure this repo files most. All three old addresses still open. |
| the `customer` subject | needs a running record across every account one customer holds, and a jointly-held account belongs in full to each holder (`BR-CUS-054`), so the arithmetic is not a sum. `CustomerStatementPage.tsx`'s `held_with` guard and its server-reasoned absent-figure are the careful parts to carry over. **Not started.** |
| the `premises` subject | `by_premises_summary` publishes three totals, not an ordered sequence with a carry-forward. A running record at that grain is a read model nobody has built. **Not started.** |
| the browser proof | recorded in the lane's report with what was and was not reachable. |

### 17.8 · Rollback, stated before shipping

Delete `unit_ledger`, `UnitLedgerRow`, `GAP_OCCUPANT_NOT_STAMPED` and
`UNIT_LEDGER_SORTS` from `apps/ledger/reporting.py`; delete `customer_labels`
and `CUSTOMER_QUERYSET_READ` from `dimension_seam.py`; delete the seam wrapper;
restore the `unit` entry in `statement.SUBJECTS_NOT_SERVED` and remove
`UNIT_STATEMENT_COLUMNS`, `SUBJECT_UNIT` and the head block. **No migration was
added and no column was written**, so a rollback is code only — the read is a
read (hard rule 5). ⚠ **Keep `column_meta`**: it fixes a latent typing gap on
the account statement too and is independent of this subject.

### 16.8 · AN INVERSION A READER WOULD OTHERWISE TRIP OVER: the PORTAL now has a premises statement and STAFF still do not

⚠ **`R24c`'s row in `02-business-rules.md` says *"Staff see it as drawn"*. THEY
DO NOT, AND THAT IS NOT THIS LANE'S GAP — but nothing said the two halves had
landed in the opposite order, so this section says it.**

`apps/reports/statement.py` refuses the **`premises`** subject BY NAME —
`SUBJECTS_NOT_SERVED`, read by `queries.DatasetCannotServe` — because the
ledger publishes no running-record read model at that grain.

⚠ **CORRECTED WITHIN THE HOUR, AND THE MISTAKE IS THE LESSON.** This paragraph
first read *"along with `customer` and `unit`"*. **`unit` LEFT that table at
`d7515c106`, 18:02 on 2026-09-27** — `P2.15`, built by lane REP-SUBJECTS while
this one was working — so the sentence was stale about two hours after it was
true, and it was written AFTER that commit was already on the branch. It is the
exact rot this section exists to name, committed by the lane naming it. **The
table holds `customer` and `premises` today**; read `SUBJECTS_NOT_SERVED`,
never this paragraph.

⚠ **AND THE STAFF PREMISES STATEMENT IS NOW RULED AS WELL AS DRAWN.**
`BR-REP-043`, **CONFIRMED by PO ruling 2026-09-27** — *"we can do based on
regualr account, master account, premises, units, customer id"* — makes five
subjects law, and its own title reads *"A statement is served for five
subjects"*. **That is the RULE's intent and not a statement of what is built**:
two of the five refuse in code today. A reader who takes the heading at face
value will believe the premises statement exists. It does not.

§12 already records `P2.8`/`P2.16` as blocked on a ledger task and
`DEF-REP-6859` records the misfiling. Nothing here reopens either.

**So the state of `R24c` after this lane is:**

| half | who sees it | state |
|---|---|---|
| the STAFF report, all five accounts at 1408 Elm Street, as drawn on p070 | staff | **NOT BUILT** — the `premises` subject refuses by name (`P2.8`, blocked on `apps/ledger`) |
| the PORTAL statement, scoped to what the signed-in person holds | a landlord, a tenant | **BUILT** (`CWP-078`, this lane) |

**WHY THE SCOPED HALF COULD LAND FIRST, WHICH IS THE NON-OBVIOUS PART.** The
staff report needs a read model at the **premises grain** — one query that
crosses customers and foots. The portal one does not: every row it draws is ONE
ACCOUNT, and `apps.ledger.reporting.account_ledger` has published that since
`US-LED-009`. `premises_statement` walks an account to its property, intersects
with the session's own account set, and asks the ledger for each row
separately. **It never asks the question the staff report is blocked on**, which
is the same fact that makes it safe: there is no cross-customer query here to
scope down, because there is no cross-customer query at all.

⚠ **THE PRACTICAL CONSEQUENCE, SO NOBODY READS IT AS A DEFECT:** a clerk cannot
today open the report a landlord can. That looks wrong and is not — it is
`P2.8`'s absence, visible from a new angle. **It becomes a real inconsistency
the day `P2.8` lands**, and whoever builds it should read
`apps/portal/premises_statement.py` first: the portal's scoping must keep
working when a premises-grain read model exists to be reached for, and the
tempting refactor — *serve the staff query and filter* — is the one thing
`P4.15`'s ruling forbids.
