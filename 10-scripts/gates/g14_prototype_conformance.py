"""G14 — prototype conformance (US-SHL-020 TC-9; the answer to DEF-021).

Added 2026-08-10 by Eng-Lead, from hard-won law 6:

    "Diff the running app against 05-prototype/. No gate looks at rendered
     output. Nine defects were found this way and by nothing else."

DEF-021 was found exactly that way — the PO walked the prototype screen by
screen and found four page headers, each misplaced differently. G1-G13 all
passed on every one of them, because each asks about law, traceability, wiring
or output shape, and none compares the app to the design it was drawn from.

This gate repeats the part of that walk a machine can. It cannot see pixels, so
it does not claim to (law 1 — a check that implies more than it tested is worse
than no check). It asserts the two things that actually drifted:

  1. COPY  — every per-tab guidance sentence and tab label the app ships is one
             the prototype writes, read out of UtilityBilling.html at gate time.
             Change one side only and this goes red. It found DEF-022 on the
             commit that added it: the Plans guidance had been a paraphrase, and
             had dropped "with a name customers understand" in all five
             catalogs since the screen was built.
  2. SHAPE — no converted screen draws its own page head any more. Every
             bespoke `-head` / `-tabs` block is gone and PageHeader renders it.

Proven RED before trusted green (law 7): on the commit that introduced it, the
shape checks named PremisesListPage, PremisesDetailPage and AssetDetailPage as
still drawing their own heads, and the copy check named rating.explainer.plans.

RATIFIED 2026-08-11 by the PO (option A, "keep all four blocking"): G1-G16 are
the confirmed merge-blocking set. G13-G16 were Eng-Lead additions made from
defects that reached the running product; they are now confirmed law, so a
loosening here - an allowlist entry, a skipped check, a widened pattern - is a
change to a ratified decision and belongs in the daily PO batch.
G13 and G14 were added by Eng-Lead from the defect log's own numbers.

Python 3.12 stdlib only. Safe to run from any cwd.
"""

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
#: ⚠ **RE-POINTED AT r10 ON 2026-08-21 (`DEF-524`).** This constant read
#: `UtilityBilling.html` — **r9** — for five days after the PO ruled r10 THE
#: reference (2026-08-16: *"for this session we will be refering to r10 - as
#: default"*). CLAUDE.md, B14 and B15 all carry that ruling; this one hardcoded
#: path did not, so the single automated answer to *"does the app look like the
#: design"* was comparing against a superseded file and reporting PASS.
#:
#: **It reported PASS through `DEF-441`, `DEF-442`, `DEF-443`, `DEF-445`,
#: `DEF-446` and `DEF-520`** — every UI divergence the PO found by opening the
#: app. A permanently-GREEN gate is worse than the permanently-RED one
#: `DEF-490` was written about, because a red gate is eventually noticed and a
#: green one is trusted.
PROTOTYPE = REPO / "05-prototype" / "r10-2026-08-16" / "SMARTBillHub.dc.html"

#: ⚠ **r9 IS GONE FROM THE REPO — THE PO DELETED IT ON 2026-08-21**, in the
#: same exchange as *"r10 is the new UI prototype; we have to ensure UI
#: matches"*. So the explainer check can no longer pin to it, and the nine
#: sentences it protected are now measured against r10 like everything else.
#:
#: **2026-08-22 (`DEF-527` lane): the original "all nine fail, r10 removed the
#: explainer" finding was HALF an extractor artifact.** r10 did not remove the
#: per-tab explainer paragraph — it RESTYLED it, from r9's `max-width:70ch` to
#: `max-width:66%`, and `_prototype_guidance` only read the r9 spelling, so the
#: gate reported r10 as drawing no explainers at all. With the extractor
#: reading r10's own markup (see `_prototype_guidance`), r10 draws SEVEN of the
#: nine: three were already shipped verbatim (plans, premises, units), and four
#: were adopted from r10's paragraphs into all eleven catalogues on 2026-08-22
#: (rates, chargeCodes, taxesFees, sub_meters). The TWO that remain are real:
#: r10's assets **Meters** and **Behind the meter** tabs draw a KPI stat grid
#: and no prose at all, so `assets.explainer.meters` and
#: `assets.explainer.behind_the_meter` have no r10 sentence to adopt — whether
#: the app drops those two explainers (a structure change, not a copy change)
#: is the PO's call, not a lane's. Still a RATCHET, not a bar: the number may
#: fall and may never rise.
#:
#: ⚠ **2 → 3 ON 2026-09-12, AND IT IS A SUPERSESSION RATHER THAN A WIDENING
#: (`DEF-MET-4961`, `CR-092-BRC01` step 2 lane 1).** The third is
#: `assets.explainer.sub_meters`. It shipped r10's own sentence — *"Sub-meters
#: hang off a master meter and bill their own unit. Click one for its detail;
#: add, edit, reassign, or retire from the row."* — adopted by `DEF-527` on
#: **2026-08-22**. **B14 rule 32 was ratified on 2026-08-31 and rule 33 before
#: it**, and both are LATER law than that adoption: rule 32 allows **one
#: sentence per section** (PO, *"too much content - desctiption is too much for
#: clark to read"*, said four times in twenty minutes) and rule 33 caps an
#: instruction at **six words per sentence**. r10's sentence is 24 words in
#: two, and its second sentence names the four row actions that are visible
#: three inches below it. It now reads *"Sub-meters bill their own unit."* —
#: five words, one sentence — in all eleven catalogues.
#:
#: **`CLAUDE.md` settles which authority wins and it is not this gate's:**
#: r10's `UI-RULES.md` *"is its SOURCE, not its authority — B14 wins and every
#: divergence is stamped there."* This is that stamp on the gate side; the
#: matching stamp is in `04-docs/02-decisions/14-ui-conventions.md`.
#:
#: ⚠ **RAISING THIS NUMBER IS NORMALLY THE MOST DAMAGING MOVE AVAILABLE** — it
#: turns a true finding into a permanently invisible one — so the bar for
#: doing it is a named key, a named rule that outranks r10, and the wording in
#: the same commit. A FOURTH stale explainer still goes red, which is the whole
#: point of leaving it a ratchet.
EXPLAINERS_NOT_IN_R10 = 3

#: ── THE COLUMN-HEADING RATCHET (`DEF-524`) ────────────────────────────────
#: r10 draws 409 distinct `<th>` texts. The app ships 571 column-heading
#: strings, and **169 of them are headings r10 draws nowhere.** Many are
#: legitimate — audit, bank reconciliation and budget billing are screens r10
#: does not draw at all — so this is a RATCHET, not a bar: the count may fall
#: and may never rise. A new heading that r10 does not use is either a column
#: r10 does not have (the `DEF-441` shape: nine columns drawn as three, or three
#: drawn as nine) or a rewording of one it does, and both are the drift the PO
#: asked about. **This is the check G14 never had** — it compared 18 sentences
#: and could not see a table at all.
#:
#: ⚠ **RAISED 169 → 179 ON 2026-08-23 BY CR-029 RC-W3, AND THE REASON IS THAT
#: r10 IS NO LONGER THIS SURFACE'S AUTHORITY.** The PO rebuilt the Routes &
#: Cycles prototype on 2026-08-23 and B17 §4 records that it *"supersedes r10
#: for every Routes & Cycles surface exactly as r10 superseded r9"*. The
#: upgraded drawing is not a file in this tree — it arrived as screenshots — so
#: this gate compares the new screens against a prototype that predates them and
#: reports every ruled column as drift. It is measuring correctly; its reference
#: is one generation stale for these ten strings and for nothing else.
#:
#: The ten, each named by B17 §4's own target rows, so a reviewer can check them
#: against the ruling rather than against this number:
#:   settings.routes.col.routeNo · .services · .area        (SET-05: *"Route # ·
#:     Name · Type · Service(s) · Area · Members · Meters · Cycle · Status"*;
#:     Service(s) and Area are D10's service SET and the area filter)
#:   settings.cycles.col.cycleNo · .startDay · .daysToComplete
#:     (SET-05.cycles: *"Cycle # · Name · **Frequency · Start day · Days to
#:     complete** · Routes (chips) · Accounts · Status"*)
#:   metering.cycles.col.startDay · .daysToComplete · metering.routes.col.services
#:     (S26/S27 adopting the same vocabulary — B17 §4's last row)
#:   settings.routes.detail.col.onRoute  (SET-06D's Assets tab)
#:
#: ⚠ **NOTHING ELSE MOVED, AND THAT IS THE CHECK ON THIS PARAGRAPH.** The same
#: CR DELETED five headings the rebuild orphaned — `settings.cycles.col.code`,
#: `.window`, `.billDay`, `.dueDay` and `settings.routes.col.service` — and the
#: count did not fall by five, because r10 DOES draw those five. So the rise is
#: exactly the ten new ruled names and no rewording rode in with them.
#:
#: This number falls back the day the upgraded prototype lands in
#: `05-prototype/` — the same fix G29's `screens_without_r10 22` is waiting on.
#
# 2026-08-24 · 179 -> 180 (CR-030 W2). ONE heading bought, and it is named:
# `customers.accounts.col.ageing` = "Ageing". B18 §5.1.2 splits the Accounts
# list's single STATUS column into STATUS and AGEING — today one cell shows
# `Pending` beside `30d past`, which is two different facts in one column — and
# the AGEING half is BR-CUS-016's derived-never-stored display. r10 does not
# draw the heading because the column was ruled in AFTER r10 was drawn.
#
# ⚠ THAT IS DEF-524's HAZARD, NOT AN EXCUSE, and it is why the rise is ONE and
# not SEVEN. Measured in a detached worktree at d513c4be, the commit before
# CR-030 began: the count was ALREADY 185 against a ceiling of 179, so SIX
# headings were over and unledgered before this CR touched anything. Raising
# straight to 186 would have absorbed those six silently — which is exactly what
# the paragraph above forbids, and what turns a ratchet back into a number
# nobody reads.
#
# So the gate STAYS RED, reporting precisely the six nobody has explained, and
# those six are filed as DEF-631. Whoever explains them raises this to 186.
#
# ══════════════════════════════════════════════════════════════════════════
# 2026-08-24 · 180 -> 196 (DEF-631 CLOSED). SIXTEEN headings, EVERY ONE NAMED.
# ══════════════════════════════════════════════════════════════════════════
#
# ⚠ **DEF-631 NAMED THE WRONG SIX, AND THE REASON IS A FLAW IN THIS GATE'S OWN
# FAILURE MESSAGE — fix that before reading anything else here.** The row says
# the six are *"`assets.col.assetNo`, `assets.col.manufacturer`,
# `assets.col.select`, `assets.col.serial`, which look like CR-028's assets
# registry columns"*. They are not. Those four are simply the alphabetically
# FIRST entries of `sorted(unknown)`, which is what the message prints as
# *"first few"* — it reports the front of the whole 196-name list, never the
# NEW ones, so every reader of a rise is handed four headings that are almost
# certainly innocent and have been in the count for weeks. A ratchet that
# cannot say WHAT rose sends its next reader to the wrong CR; DEF-631's own
# diagnosis was written from this message and is wrong because of it.
#
# **The six were found by replaying this gate's own arithmetic over the history
# of `en.json`** — the count depends on nothing else — and they landed in ONE
# commit, `6934183bb` *"CR-029 RC-W3c i18n"*, the SECOND half of the same
# Routes & Cycles rebuild whose first ten are ledgered above:
#     settings.cycles.detail.col.lacks          "What is missing"
#     settings.cycles.detail.col.occurrence     "Occurrence"
#     settings.cycles.detail.col.window         "Window"
#     settings.cycles.detail.col.windowStatus   "Window status"
#     settings.routes.detail.col.readOn         "Read on"
#     settings.routes.detail.col.readWindow     "Window"
# They are SET-06D/SET-05's detail sub-tabs, bought by exactly the ruling the
# ten above cite: B17 §4, *"supersedes r10 for every Routes & Cycles surface
# exactly as r10 superseded r9"*. Same CR, same ruling, same day — the ledger
# comment was updated for the first commit and not for the second, which is the
# whole of DEF-631. Not drift.
#
# THE OTHER TEN, since d513c4be, each with what bought it:
#   `customers.accounts.col.ageing` "Ageing" — CR-030 W2, already ledgered
#     above as the 179 -> 180 rise. Counted once, here for completeness.
#
#   ⛔ `customers.accounts.col.customerNo` "Customer #" — **THIS ONE IS DEBT,
#     NOT A PURCHASE, AND IT IS THE ONLY RISE HERE THAT SHOULD COME BACK OUT.**
#     It was added by `8c3a06006`, the SAME commit that carried the PO's ruling
#     removing the column — *"we dont need this column … you can sho it as part
#     of details screen"*. No component references it (G18 reports it DEAD),
#     so it is a catalogue orphan of a deletion, inflating this ratchet by one.
#     **DELETE IT FROM THE ELEVEN CATALOGUES AND LOWER THIS NUMBER TO 195 IN
#     THE SAME DIFF** — the FALL branch below refuses to let those two separate.
#     Not done here: this lane may not edit `i18n/locales/*.json`.
#
#   The NINE service-request headings, from `69ba1eb86` and `1e2ba13bd`:
#     customers.serviceRequest.col.applicant             "Applicant"
#     customers.serviceRequest.col.received              "Received"
#     customers.serviceRequest.col.request               "Request"
#     customers.serviceRequest.col.state                 "State"
#     customers.serviceRequest.col.waitingOn             "Waiting on"
#     customers.serviceRequest.documents.col.uploaded    "Uploaded"
#     customers.serviceRequest.documents.col.verified    "Verified"
#     customers.serviceRequest.documents.col.whatItProves "What it proves"
#     customers.serviceRequest.fees.col.fee              "Fee"
#   These are REQ-01/REQ-02/REQ-03 (B19, CR-031). **r10 draws no service-request
#   screen at all** — it is the *"audit, bank reconciliation and budget billing"*
#   class this comment names at the top: a screen r10 does not have cannot have
#   its headings compared against r10, and reproducing r10 here would mean not
#   building the screen. Legitimate, and legitimately invisible to this check.
#
# ⚠ **AND THE STANDING WARNING IS NOW LOUDER, NOT QUIETER.** Fifteen of these
# sixteen are correct work that this gate cannot distinguish from drift, because
# it measures against `05-prototype/r10-2026-08-16` and the spec has moved twice
# since (B17 §4's Routes & Cycles rebuild, B19's service requests) — DEF-524's
# hazard, exactly as written. The real fix stays B18 §10 decision D5: export the
# CURRENT prototype into `05-prototype/` so this gate measures what was actually
# ruled. Until then every rise costs a paragraph like this one, which is the
# price of the ratchet still meaning something.
# 2026-08-24 · 196 -> 195, in the SAME diff that deletes the heading, which is
# what the FALL branch demands. `customers.accounts.col.customerNo` ("Customer
# #") was added by `8c3a06006` — the very commit that carried the PO ruling
# REMOVING that column (*"we dont need this column - customers.accounts.col.
# customerNo - why youa re showing it like this"*). No component ever referenced
# it and G18 reported it DEAD. A heading that exists only in the catalogues is
# not a conformance gap with r10; it is debt, and it is now gone from all eleven.
# 2026-08-31 · 195 -> 199, CR-056 W5 task 25 — THE CUSTOMERS LIST. FOUR
# headings, and they are the service-request case above word for word:
#     customers.customer.col.number      "Customer #"
#     customers.customer.col.identity    "ID on file"
#     customers.customer.col.accountNo   "Account #"
#     customers.customer.col.matchedOn   "Matched on"
#   **r10 draws no customers screen at all**, and that is not an accident of the
#   drawing — it is the same fact `CR-056` §4 was filed about, from the other
#   side: *"you reach a person only through the accounts linked to them"*. A
#   screen r10 does not have cannot have its headings compared against r10, and
#   reproducing r10 here would mean not building the screen. Legitimate, and
#   legitimately invisible to this check. The other six headings on that screen
#   ("Name", "Type", "Kind", "Status", "Accounts", "Actions") DO match headings
#   r10 already draws, which is why only four move this number.
#
# ⚠ **"Customer #" IS NOT THE COLUMN THE PO DELETED, AND THE COLLISION IS WORTH
#   NAMING BECAUSE THE STRING IS IDENTICAL.** The entry above records
#   `customers.accounts.col.customerNo` ("Customer #") being removed on a PO
#   ruling — *"we dont need this column ... why youa re showing it like this"* —
#   from the ACCOUNTS list, where it was a second number beside the account's
#   own. This is the CUSTOMERS list, where the customer number is the identity
#   column and the only number the row has. Different screen, different
#   question; a future sweep matching on the VALUE alone would read one as the
#   other, so it is written down here rather than left to be re-derived.
#
# ⚠ **THIS LANE BANKS ITS OWN FOUR AND ONLY ITS OWN FOUR, SO THE GATE STAYS
#   RED — READ THAT BEFORE READING 199 AS "SETTLED".** Measured with this file's
#   own arithmetic on the tree this lands on: 252 headings are unknown to r10, so
#   53 remain above this number and none of them is this lane's. A ratchet raised
#   on somebody else's behalf is a number nobody justified, which is the
#   discipline `screen_id_baseline.txt` records about itself four separate times.
# ── 2026-09-02 · CR-060 C4/T9 — TWO HEADINGS ADDED, BASELINE NOT MOVED ─────
# `finance.gl.col.opening` "Opening" and `finance.gl.col.closing` "Closing", on
# the S56 trial balance. **r10 draws neither**, and it cannot: r10's trial
# balance has debit and credit columns and no position columns at all — which is
# the gap `CR-060` C4 exists to close, in the requester's own words (*"without
# the opening column they cannot tie this month to last month's signed statement
# without exporting"*). A design the product has deliberately moved past cannot
# be compared against, and reproducing r10 here would mean not building C4.
#
# **THE BASELINE IS NOT RAISED, AND THAT IS THE DISCIPLINE RATHER THAN AN
# OVERSIGHT.** This gate is RED already — measured on the tree this lands on,
# 256 headings are unknown to r10 against a baseline of 199 — so 57 sit above
# this number and NONE of them is this lane's. Raising it to swallow those 57
# would bank a number nobody justified, which is the mistake the entry above
# this one records about itself. These two are named HERE instead, so the sweep
# that eventually reconciles the 57 can attribute them without replaying
# `git log -- en.json` (DEF-631's whole complaint: a ratchet whose alarm cannot
# say WHAT rose is a number nobody can act on).
# ── 2026-10-01 · CR-156-BRC10 wave B — SIX HEADINGS ADDED, BASELINE NOT MOVED ──
# The charge-code screens are built from the 83 images of the PO-reviewed
# mock-up (05-prototype/charge-codes-2026-10-01), which the PO named as the
# reference for these screens INSTEAD of r10 (decision log 2026-10-01, *"not
# Plans & Rates blueprint PDF"*; the mock-up supersedes r10's charge editor).
# Six of its column words appear in no r10 table: `rating.chargeCode.col.pricedBy`
# "Priced by" (list, image 01), `col.percent` "Percent" and `col.minimum`
# "Minimum" (penalty prices, images 31/61), and `col.item` "Item", `col.now`
# "Now", `col.new` "New" (Edit's *What changes*, image 75). Named here, not
# banked, for the reason the entry above gives.
# ── 2026-10-03 · CR-165-BRC10 task 5 — FIVE HEADINGS ADDED, BASELINE NOT MOVED ──
# The taxes & fees list is built from images 01–03 of
# 05-prototype/taxes-fees-2026-10-03, which the PO named the reference for
# these screens. Its new column words: `rating.taxes.list.col.version`
# "Version", `.from` "From", `.to` "To", `.gl` "GL account", `.premises`
# "Premises". Named here, not banked, for the reason the entry above gives.
# ── 2026-10-03 · CR-167-BRC10 task 6 — ONE HEADING ADDED, BASELINE NOT MOVED ──
# The plans list is built from images 01–03 of 05-prototype/plans-2026-10-03.
# Its new column words: `rating.plans.list.col.schedules` "Schedules" (the only
# one r10 does not draw; Version, Services, From and To are r10 words). Named
# here, not banked. ⚠ The count already stood at 703 at tip 8eed65807, far
# above this baseline — that red is not this lane's and is reported.
COLUMN_HEADINGS_NOT_IN_R10 = 199
CATALOG =REPO / "07-frontend" / "src" / "i18n" / "locales" / "en.json"
SCREENS = REPO / "07-frontend" / "src" / "features"

# The per-tab guidance each of the four screens the PO walked renders.
EXPLAINER_KEYS = [
    # ⚠ `rating.explainer.plans` LEFT THIS LIST ON 2026-10-03 (CR-167-BRC10
    # round 2 task 6, `DEF-RAT-9333`): images 01–03 of the plans drawing draw no
    # paragraph above the list, so the key is retired from every catalogue and
    # `plansList.dom.test.tsx` asserts it is in none — asking for it here would
    # make this gate red over the fix (the rates/chargeCodes/taxesFees shape).
    # It MATCHED r10, so the stale count below does not move.
    # ⚠ `rating.explainer.rates` LEFT THIS LIST ON 2026-10-02 (gate census,
    # `DEF-GOV-9129`). It was retired from every catalogue on purpose by
    # 49594f53b (`DEF-RAT-8840`, CR-157-BRC10 wave C, 2026-10-01: *"the Rates
    # tab loses an explainer no drawing has"*) — the Plans & Rates blueprint's
    # `01-list-all.png` draws the Rate schedules tab with no paragraph, and the
    # blueprint owns layout (B14 rules 36/41, `DEF-GOV-5248`). The test
    # `RateSchedulesTable.test.tsx` asserts the key is in NO catalogue, so this
    # list asking for it made G14 red over the fix — the chargeCodes and
    # premises entries below are the same shape, twice before.
    # ⚠ `rating.explainer.chargeCodes` LEFT THIS LIST ON 2026-10-01 (CR-156-BRC10
    # wave B). The PO's charge-code list ruling of that day drops *"the
    # explanatory paragraph above the table"* (B14 rules 32/33), so the screen
    # renders none and the key is retired — the same shape as the premises
    # explainers below, and asking for it would make this gate red over the fix.
    # ⚠ `rating.explainer.taxesFees` LEFT THIS LIST ON 2026-10-03 (CR-165-BRC10
    # task 5, P21, `DEF-RAT-9274`): images 01–03 of the taxes & fees drawing
    # draw no paragraph above the list, so the key is retired from every
    # catalogue and asking for it would make this gate red over the fix.
    # ⚠ `metering.premises.explainer.premises` and `.units` LEFT THIS LIST ON
    # 2026-09-30 (gate triage T6). They were deleted from every catalogue on
    # purpose by ca3050616 (DEF-MET-5835, 2026-09-19: "the premises list loses
    # its 27-word explainer", B14 rules 32/33), and this list still asked for
    # them, so G14 was red from that commit over a removal that was the fix.
    # `.imports` is the one explainer the premises screens still render.
    "assets.explainer.meters",
    "assets.explainer.sub_meters",
    "assets.explainer.behind_the_meter",
]

TAB_LABEL_KEYS = [
    "rating.tab.plans",
    "rating.tab.rates",
    "rating.tab.chargeCodes",
    "rating.tab.taxesFees",
    "assets.tab.meters",
    "assets.tab.sub_meters",
    "assets.tab.behind_the_meter",
    # S8 Settings -> Company's SECOND-level strip. `_prototype_tab_labels`
    # already collects every `.settings-tabs` strip in the prototype, nested
    # ones included, so these two are guarded by the same extractor with no
    # special case — and a future paraphrase of either now fails the gate.
    "settings.company.subTab.profile",
    "settings.company.subTab.regional",
]

# Screen -> the bespoke markup it used to ship. A converted screen renders
# PageHeader and contains none of its own.
#
# Screen IDs are A1's, checked against 04-docs/01-spec/01-screen-inventory.md —
# S15 is the Units TAB and S16 is the Add Premises & Unit form; the asset
# screens are S49 (Assets list) and S50 (Asset detail). An earlier revision of
# this file called the asset screens S15/S16, which renumbered two screens that
# already meant something else. CLAUDE.md: use A1 as the vocabulary, never
# renumber.
CONVERTED = [
    ("S9 Plans & Rates", "rating/PlansRatesPage.tsx", ["rating-head", "rating-tabs", "rating-sub"]),
    # ⚠ CR-023 P0 MOVED THE PREMISES/UNITS HEAD UP ONE LEVEL, 2026-08-21.
    # r10 draws Premises · Units · Imports as ONE page, so the head, its roll-up
    # and the three-tab strip belong to `PremisesTabsPage` and the two list
    # screens are TAB BODIES that correctly draw no head at all. This gate went
    # RED on exactly that — `S14 Premises does not render PageHeader
    # (metering/PremisesListPage.tsx)` — which is the check working: it noticed
    # a head disappearing from a converted screen. The rule it enforces is
    # unchanged and is now asserted one file up; the two bodies keep their
    # BESPOKE-block check, because a tab body growing its own `met-head` would
    # be the regression this list exists to catch.
    ("S14/S15 Premises page", "metering/PremisesTabsPage.tsx", ["met-head", "met-tabs"]),
    ("S14 Premises tab body", "metering/PremisesListPage.tsx", ["met-head", "met-tabs"], False),
    ("S14 Premise detail", "metering/PremisesDetailPage.tsx", ["met-head", "met-tabs"]),
    ("S15 Units tab body", "metering/UnitsListPage.tsx", ["met-head", "met-tabs"], False),
    ("S15 Unit detail", "metering/UnitDetailPage.tsx", ["met-head", "met-tabs"]),
    ("S49 Assets list", "assets/AssetRegistryPage.tsx", ["ast-head", "ast-tabs"]),
    ("S50 Asset detail", "assets/AssetDetailPage.tsx", ["ast-head", "ast-tabs"]),
]

_TAG = re.compile(r"<[^>]+>")
_ENTITIES = [("&amp;", "&"), ("&nbsp;", " "), ("&#39;", "'"), ("&quot;", '"'), ("&mdash;", "—")]


def _plain(html: str) -> str:
    """Tags out, entities decoded, whitespace collapsed — the sentence as read."""
    text = _TAG.sub("", html)
    for entity, char in _ENTITIES:
        text = text.replace(entity, char)
    return " ".join(text.split())


def _prototype_guidance(html: str) -> set[str]:
    """Every sentence the prototype uses as page guidance.

    Collected from the places it puts one — the guidance paragraph under a tab
    strip (Plans & Rates, Premises, Assets sub-meters) and the `.sub` line
    inside a page head — as a SET rather than by line number, so re-ordering
    the prototype does not fail this and rewording it does.

    ⚠ THE PARAGRAPH STYLE IS A REVISION MARKER (`DEF-527`): r9 wrote its
    guidance paragraphs `max-width:70ch`; r10 restyled the same slot to
    `max-width:66%` (e.g. SMARTBillHub.dc.html lines 649, 688, 741, 3246).
    When this file was re-pointed at r10 (`DEF-524`) the extractor still read
    only the r9 spelling, so it collected ZERO guidance paragraphs from r10 and
    the gate mis-reported r10 as having removed the explainers entirely. Both
    spellings are read so the extractor matches the file the PROTOTYPE constant
    actually points at — this is the DEF-524 re-point finished, not a loosening:
    every sentence collected is one r10 itself draws.
    """
    found = set()
    for match in re.finditer(r'<p style="[^"]*max-width:(?:70ch|66%)"[^>]*>(.*?)</p>', html, re.S):
        found.add(_plain(match.group(1)))
    for match in re.finditer(r'<div class="sub">(.*?)</div>', html, re.S):
        found.add(_plain(match.group(1)))
    return found


def _prototype_tab_labels(html: str) -> set[str]:
    """Every label the prototype puts in a `.settings-tabs` strip."""
    found = set()
    for strip in re.finditer(r'<div class="settings-tabs"[^>]*>(.*?)</div>', html, re.S):
        for button in re.finditer(r"<button[^>]*>(.*?)</button>", strip.group(1), re.S):
            found.add(_plain(button.group(1)))
    return found


def run():
    missing_inputs = [p for p in (PROTOTYPE, CATALOG) if not p.exists()]
    if missing_inputs:
        names = ", ".join(str(p.relative_to(REPO)) for p in missing_inputs)
        return "SKIP", f"nothing to compare against — {names} not present"

    html = PROTOTYPE.read_text(encoding="utf-8")
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    guidance = _prototype_guidance(html)
    labels = _prototype_tab_labels(html)

    failures = []
    notes = []

    # ⚠ **SEVEN OF THE NINE EXPLAINERS NOW SHIP r10's OWN SENTENCES
    # (`DEF-527`, adopted 2026-08-22).** The original finding — "all nine fail,
    # r10 removed the explainer" — was measured through an extractor that only
    # read r9's `max-width:70ch` paragraph style; r10 restyled the same slot to
    # `max-width:66%` and kept the prose (see `_prototype_guidance`). Four
    # sentences were adopted verbatim from r10 into all eleven catalogues
    # (rates, chargeCodes, taxesFees, sub_meters); three already matched
    # (plans, premises, units). The remaining TWO are the real residue: r10's
    # assets Meters and Behind-the-meter tabs draw a KPI stat grid and no
    # prose, so `assets.explainer.meters` / `assets.explainer.behind_the_meter`
    # have no r10 sentence to adopt — dropping those two explainers from the
    # app is a structure change and stays the PO's call.
    for key in EXPLAINER_KEYS:
        if catalog.get(key) is None:
            failures.append(f"{key} is missing from the English catalog")
    stale = [key for key in EXPLAINER_KEYS if catalog.get(key) not in guidance]
    if len(stale) > EXPLAINERS_NOT_IN_R10:
        failures.append(
            f"explainer(s) r10 does not draw ROSE to {len(stale)} from {EXPLAINERS_NOT_IN_R10}: "
            f"{', '.join(stale[:3])}"
        )
    elif len(stale) < EXPLAINERS_NOT_IN_R10:
        failures.append(
            f"explainer(s) r10 does not draw FELL to {len(stale)} from {EXPLAINERS_NOT_IN_R10} — "
            f"lower the baseline in the SAME commit"
        )
    elif stale:
        notes.append(
            f"{len(stale)} of {len(EXPLAINER_KEYS)} explainer(s) have no r10 sentence to match "
            f"— r10's assets Meters and Behind-the-meter tabs draw a KPI stat grid and no prose "
            f"({', '.join(stale)}). Dropping those explainers is a structure change for the PO; "
            f"the other seven ship r10's own sentences (DEF-527, adopted 2026-08-22)"
        )

    for key in TAB_LABEL_KEYS:
        shipped = catalog.get(key)
        if shipped is None:
            failures.append(f"{key} is missing from the English catalog")
        elif shipped not in labels:
            failures.append(f"{key} = {shipped!r} is not a tab label in the prototype")

    checked = 0
    for entry in CONVERTED:
        # A fourth element means "this file is a TAB BODY: it must NOT draw a
        # head, and it must not draw a bespoke one either" (CR-023 P0).
        screen, relative, bespoke = entry[0], entry[1], entry[2]
        wants_header = entry[3] if len(entry) > 3 else True
        path = SCREENS / relative
        if not path.exists():
            failures.append(f"{screen}: {relative} not found")
            continue
        checked += 1
        source = path.read_text(encoding="utf-8")
        if wants_header and "<PageHeader" not in source:
            failures.append(f"{screen} does not render PageHeader ({relative})")
        # ⚠ AND THE MIRROR, WHICH IS THE NEW HALF (CR-023 P0). A tab body that
        # grows its OWN `<PageHeader` puts two heads on one page — B14 rule 2
        # broken in the direction this list never had to look at before, because
        # until 2026-08-21 every converted screen was a whole page.
        if not wants_header and "<PageHeader" in source:
            failures.append(
                f"{screen} draws its own PageHeader ({relative}) — it is a TAB BODY and "
                f"the page it belongs to already draws one (B14 rule 2)"
            )
        for class_name in bespoke:
            # `className="rating-head"` — the screen drawing its own header. A
            # CSS file may still define the class; only the screen using it is
            # the defect.
            if re.search(rf'className=["\'`][^"\'`]*\b{class_name}', source):
                failures.append(f"{screen} still renders .{class_name} ({relative})")

    # ── the check this gate never had: does the app's TABLE look like r10's ──
    r10_headings = {
        re.sub(r"<[^>]+>", "", cell).strip()
        for cell in re.findall(r"<th[^>]*>(.*?)</th>", html, re.S)
    }
    r10_headings = {h for h in r10_headings if h and "{{" not in h and len(h) < 60}
    shipped_headings = {
        key: value
        for key, value in catalog.items()
        if re.search(r"\.col\.|\.column\.|\.header\.", key) and isinstance(value, str)
    }
    unknown = sorted(k for k, v in shipped_headings.items() if v not in r10_headings)
    if len(unknown) > COLUMN_HEADINGS_NOT_IN_R10:
        newly = len(unknown) - COLUMN_HEADINGS_NOT_IN_R10
        # ⚠ **THIS MESSAGE USED TO PRINT `unknown[:4]` AND CALL IT "first few",
        # WHICH IS THE FRONT OF THE WHOLE ALPHABETICAL LIST AND NOT THE RISE
        # (DEF-631).** A lane reading it was handed four headings that had been
        # in the count for weeks and filed the defect against the wrong CR. A
        # ratchet whose alarm cannot say WHAT rose is a number nobody can act
        # on, so it now says so out loud and points at the one procedure that
        # DOES answer it — this file's arithmetic depends on nothing but
        # `en.json` and the prototype, so replaying it over `git log -- en.json`
        # names the exact commit and the exact headings, in seconds.
        failures.append(
            f"column headings r10 does not draw ROSE by {newly}: {len(unknown)} now, "
            f"{COLUMN_HEADINGS_NOT_IN_R10} baselined. A heading r10 never uses is a column r10 "
            f"does not have or a rewording of one it does. ⚠ THE NAMES BELOW ARE THE "
            f"ALPHABETICAL FRONT OF ALL {len(unknown)}, NOT THE {newly} THAT ROSE — to find "
            f"those, replay this file's `unknown` set across `git log --reverse -- "
            f"07-frontend/src/i18n/locales/en.json` and diff consecutive revisions "
            f"(DEF-631). First few: {', '.join(unknown[:4])}"
        )
    elif len(unknown) < COLUMN_HEADINGS_NOT_IN_R10:
        failures.append(
            f"column headings r10 does not draw FELL to {len(unknown)} from "
            f"{COLUMN_HEADINGS_NOT_IN_R10} — lower the baseline in the SAME commit, or the "
            f"ratchet keeps claiming debt that is already paid off"
        )
    else:
        notes.append(
            f"{len(shipped_headings)} column heading(s) shipped, {len(unknown)} of them not drawn "
            f"anywhere in r10 (at the baseline of {COLUMN_HEADINGS_NOT_IN_R10}); "
            f"r10 draws {len(r10_headings)} distinct headings"
        )

    if failures:
        head = failures[0] if len(failures) == 1 else f"{len(failures)} conformance failure(s): {failures[0]}"
        return "FAIL", head + ("" if len(failures) == 1 else f" (+{len(failures) - 1} more)")

    detail = (
        f"{len(TAB_LABEL_KEYS)} tab label(s) match r10; {len(EXPLAINER_KEYS)} explainer(s) measured against r10; {checked} converted screen(s) draw no page head of their own"
    )
    for note in notes:
        detail += f"\n  note: {note}"
    return "PASS", detail


if __name__ == "__main__":
    status, detail = run()
    print(f"{status}: {detail}")
    raise SystemExit(0 if status != "FAIL" else 1)
