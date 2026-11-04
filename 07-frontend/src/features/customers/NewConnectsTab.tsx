// ── Trace ──────────────────────────────────────────────
// Change:   **CR-150-BRC09 (2026-09-28) — THE LIST, REVAMPED.** PO, verbatim:
//           *"ensure you use images to build screens and not text/content"*.
//           Built from `05-prototype/new-connect-detail-2026-09-28/
//           00-list.png` AS AN IMAGE (B14 rule 42) and to that folder's
//           README. Seven changes: the row door decides for both doors on a
//           row, the tiles SET the filter, the money columns are REFUSED
//           rather than invented (§4), the state cell folds `waiting_on` in,
//           the chooser gets `Waiting on` and `From request`, the row grows a
//           `⋮` menu and the rows grow tick boxes. **Task 17 — saved views —
//           is CANCELLED by the PO**: *"all these option will anyway will be
//           in filter - so we dont need them outside"*. There are no view
//           chips and a case asserts there are none.
// Change:   CR-030 W6 task 6.12 — **S86 `NCT-01`, the NEW CONNECT worklist,
//           FRONTEND half.** The backend landed 2026-08-25 carrying
//           `E=deferred(no-frontend-half — the Accounts "New connects" tab still
//           renders its placeholder and NOTHING CALLS THIS ENDPOINT YET)`, and
//           the PO reported the hole from a live build: *"nothing on new connect
//           + on all of these screens"*. This is that half.
// Rules:    BR-SHL-010 (an undeclared capability is not rendered) · BR-SHL-011
//           (the URL grammar — and this list owns NO query string, DEF-664) ·
//           BR-SHL-012 (the shared empty/loading states) · BR-SHL-025 (a
//           control that cannot be used renders DISABLED WITH ITS REASON) ·
//           B14 rule 5 (two button sizes) · rule 12 (the toolbar) · rule 16
//           (the pager) · rule 17 (an empty state) · rule 19 (the search
//           prompt names what it matches) · rule 20 (ONE table type) · rule 21
//           (Tailwind utilities; this file adds NO class to a stylesheet)
// Questions: ⛔ **OQ-371 — OPEN and BLOCKING the segment strip.** Four of the
//           five drawn segments are DISABLED WITH THE SERVER'S OWN REASON.
// Design:   04-docs/02-decisions/18-cr030-onboarding-design.md §5.4.1 (the five
//           tiles) · §5.4.2 (the columns, the search, the sort footnote) ·
//           §5.4.9 `NCT-01` (the drawing) · §5.4.8 (the eight seeded rows)
// Tests:    07-frontend/src/features/customers/NewConnectsTab.test.tsx
// Impacts:  AccountsListPage.tsx (the mount + `ACCOUNTS_BUILT_TABS`) ·
//           06-backend `GET /connections` (live)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// 1 · EMBEDDED, AND IT OWNS ITS OWN CORNER OF THE QUERY STRING — `DEF-664`
//     AND `DEF-CUS-6099`, WHICH ARE THE TWO HALVES OF ONE PROBLEM
// ══════════════════════════════════════════════════════════════════════════
// ⛔ **THIS BLOCK USED TO SAY THIS TAB OWNS NO QUERY STRING AT ALL, AND THE
// PRICE IT STATED CAME DUE.** It read: *"the honest way to say that is to never
// import `useSearchParams` at all … ⛔ THE PRICE, STATED: a page or search
// choice inside this tab does not survive a reload and cannot be pasted to a
// colleague. REPORTED."* It was reported and then measured in a browser on
// 2026-09-21: clicking `Draft` narrowed eleven rows to one, the address stayed
// `/accounts?tab=new-connects`, a reload gave eleven rows back, and an address
// carrying the filter opened unfiltered. **The sibling Accounts tab on the very
// same page does both correctly.**
//
// ⚠ **`DEF-664`'s READ HALF IS STILL REAL AND IS WHAT THE PREFIX IS FOR.** An
// embedded list that parsed the outer page's BARE `?page=3&q=smith` would open
// this tab on page 3 of a search somebody typed into the accounts list — and
// the page's own `selectTab` carries `sort`, `dir` and `q` across when a clerk
// changes tab, so this is not hypothetical. So this tab reads and writes
// `nc.q`, `nc.sort`, `nc.dir`, `nc.page`, `nc.per` and `nc.f.state`: **its own
// room in one query string, colliding with nothing the page owns.**
//
// ⚠ **IT IS THE SAME MECHANISM THE ACCOUNTS TAB USES, NOT A SECOND ONE** —
// `parseTableParams` / `serializeTableParams` (`BR-SHL-011`) and
// `setSearchParams`, with the namespace that those two grew for exactly this.
// A hand-rolled reader here would be two answers to *what is a table's URL*.
//
// ⚠ **EVERY PARAM THIS TAB DOES NOT OWN IS PRESERVED ON EVERY WRITE**,
// `?tab=` above all: dropping it would bounce the clerk back to the Accounts
// tab mid-task, which is the reason `AccountsListPage.writeParams` exists.
//
// ══════════════════════════════════════════════════════════════════════════
// 2 · THE SEGMENT STRIP IS DRAWN AND FOUR OF ITS FIVE TABS ARE OFF (OQ-371)
// ══════════════════════════════════════════════════════════════════════════
// `NCT-01` draws `All · In progress · Waiting · Partly energised · Done` as an
// EXCLUSIVE strip, and `CON-26-0126` is `partly_activated` AND waiting on
// `inspection` at the same time — so it satisfies two segments and **nothing
// says which one holds it.** OQ-371 puts three options to the PO and is OPEN.
//
// The server serves `segment=all` and raises `NotImplementedError("OQ-371")`
// for every other value. So the strip renders all five, `All` selected, and the
// other four DISABLED CARRYING THE SERVER'S OWN SENTENCE (BR-SHL-025). Three
// things follow from that and each is deliberate:
//
//   · **The screen never calls the route to discover the refusal.** The reason
//     rides on every response in `unavailable`, so a disabled tab has its
//     explanation before anyone clicks anything.
//   · **The four names come from the PAYLOAD, not from a list typed here.**
//     `unavailable[].segments` is the server's own tuple; a hardcoded copy
//     would be the second vocabulary that disagrees the day OQ-371 closes.
//   · **They are not hidden.** BR-SHL-025's whole point: a control that
//     vanishes sends somebody hunting for it. A visible, disabled tab with a
//     sentence is the product telling the truth about what it cannot do yet.
//
// ⚠ **THE PRODUCT WORD IS `activated` / `partly_activated`, AND B18 STILL
// DRAWS *"Partly energised"*.** CR-032, PO 2026-08-25, verbatim: *"instead of
// energise can we use activated"*. Shipped in `2.46.0`; `connections.py`'s
// tokens are `ACTIVATED` / `PARTLY_ACTIVATED` and the old names are GONE, not
// aliased. B18 is stamped rather than rewritten, because rewriting a quotation
// to match a later ruling destroys the evidence that the ruling changed
// anything. **The UI ships the new word.**
//
// ══════════════════════════════════════════════════════════════════════════
// 3 · WHAT `NCT-01` DRAWS THAT THIS DOES NOT, EACH WITH ITS REASON
// ══════════════════════════════════════════════════════════════════════════
//   * **`Export`.** `POST /exports` registers no `connections` resource, so
//     BR-SHL-010 keeps it unrendered rather than drawing a button onto
//     nothing. Not drawn disabled either: BR-SHL-025 is for a control this
//     ROLE cannot use, not one the PRODUCT does not have. ⚠ **TRACKED AS
//     DEF-1005 SINCE 2026-08-27** — this was one of only two of the eight
//     export-less lists that said so at all, and a stated absence with no id
//     behind it outlives its reason and nothing notices (DEF-445).
//   * ✅ **THE `+ New connect` PRIMARY EXISTS — DEF-730, 2026-08-26.** This
//     bullet used to say there was *"no connection wizard route in this app to
//     point one at"*, which was true for a few hours and false from the night
//     `/connections/new` landed. The primary is `AccountsListPage`'s, in the
//     page header's ONE slot, which relabels to the ACTIVE tab's create action
//     — so exactly-one-primary (B14 rule 4 / BR-SHL-044) is honoured rather
//     than fought. The empty state's CTA below goes to the same route.
//   * ✅ **AND SO DOES THE ROW ACTION.** This bullet said `NCT-02` had no route
//     and *"an 👁 view icon would be a link onto nothing"*. S88 is mounted at
//     `/connections/:connectionId`; the ACTIONS column carries the eye link,
//     because a row that can be read and never OPENED is the other half of the
//     PO's report.
//   * **The superscript tab count** (`New Connect ⁷`). `PageHeaderTab` has no
//     count slot and `components/PageHeader.tsx` is another lane's file.
//   * **A sort control.** `list_connections` accepts no `sort`: B18 §5.4.2
//     fixes the order — *"Sorted by target date, soonest first"* — so no column
//     is declared sortable, because a sort control would offer an ordering the
//     request cannot ask for. The footnote under the pager says so in words.
//
// ══════════════════════════════════════════════════════════════════════════
// 4 · WHAT `00-list.png` DRAWS, WHAT IS NOW WIRED, AND THE ONE THING STILL OFF
// ══════════════════════════════════════════════════════════════════════════
// ✅ **FIVE OF THE SIX ITEMS THIS SECTION LISTED AS UNSERVED ARE WIRED FROM
// 2026-09-29 (`DEF-CUS-7804`).** This block used to be a table of what the
// endpoint *would need*; `01580d8fc` served all of it on 2026-09-28 and
// **nothing on screen read a single one of those five facts** — the row type
// did not even declare them. That is hard-won law 2 in its purest form: built,
// tested, shipped, and rendering nothing. The table is rewritten rather than
// deleted, because what a screen deliberately does NOT draw is the part that
// rots (law 1), and one item is still genuinely off.
//
//   | drawn            | where it is now                               |
//   |------------------|-----------------------------------------------|
//   | `CUSTOMER`       | ✅ `row.customer` — the name over the account |
//   |                  | NUMBER, and the WHOLE BLOCK is null when no   |
//   |                  | owner account exists: *no account yet*        |
//   | `AGING`          | ✅ `row.age_days` + `row.age_is_accented`,    |
//   |                  | drawn by `AgeCell`, the cell one tab over     |
//   | tile `Waiting …` | ✅ `kpis.waiting_on_anyone`, as a FACT        |
//   | tile `Owed …`    | ✅ as a STATED ABSENCE — there is no figure   |
//   | chooser: Charged,| ✅ `quote_total.display`, `mode`, `scope`,    |
//   | Mode, Scope,     | `raised_by`, `last_stamped_event`             |
//   | Raised by,       |                                               |
//   | Last event       |                                               |
//   | `DUE`            | ⛔ **STILL OFF — `DEF-CUS-7619`.** No row      |
//   |                  | carries a `due` key at all                    |
//
// ⛔ **THE `DUE` COLUMN AND ANY NUMERIC OWED TILE STAY OFF UNTIL
// `DEF-CUS-7619` CLOSES**, and the reason is billing's rather than this
// screen's: `invoice_detail` takes ONE id and there is no batched position, so
// a 25-row page would be 25 calls. `BR-SHL-010` keeps an undeclared capability
// unrendered, so the column is not declared — a dash on every row forever is
// the live-screen-behind-a-dead-control shape, and a `{None, None}` on 25 rows
// is 25 copies of one sentence.
//
// ⚠ **NONE OF THE MONEY MAY BE COMPUTED HERE, AND THAT IS HARD RULE 2 RATHER
// THAN CAUTION.** Money is stored to 4 decimals and DISPLAYED at 2, rounded
// ONCE, server-side; `quote_total.display` is that 2-dp string and this screen
// PRINTS it — it never re-rounds `stored`, never multiplies, and never adds
// rows up to make the tile's total. `DEF-127` records what a fabricated
// `$0.00` costs: *"it looks exactly like a settled account"*. So the owed tile
// states an absence and an unpriced build states one too.
//
// ⚠ **AND `AGING` IS NOT DERIVED HERE EITHER.** `AgeCell`'s own note one tab
// along: the threshold lives SERVER-SIDE and the cell renders the flag,
// because *"two thresholds is how the list and a later KPI drift apart"*. A
// `days > 30 ? red : plain` written here would be this list's threshold
// disagreeing with `kpis.oldest`'s — and `DEF-CUS-7620` is what that already
// cost once, when the tile and this column counted days off two clocks.
//
// ⚠ **THE STRIP NOW HOLDS SEVEN TILES AND THE DRAWING DRAWS FIVE —
// `DEF-CUS-7805`, FILED RATHER THAN DECIDED HERE.** `00-list.png` draws
// `Open · Waiting on someone · Partly activated · Units awaiting · Owed on
// open builds`; this screen also carries `Waiting on inspection` and `Oldest`,
// both live, both served, and neither on the new drawing. **Taking a working
// tile off the page is not this lane's call** — the backend's own note says
// the two waiting figures answer different questions and that removing a
// served figure to swap a caption is law 2 running backwards. Filed so the
// supersession is counted rather than left to the next reader.
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { DataTable } from "@/components/DataTable";
import { FilterBar, offerableFilters } from "@/components/FilterBar";
import { DateCell } from "@/components/DateCell";
import type { KpiTile } from "@/components/KPIStrip";
import { RowAction, RowActionLink, RowActions } from "@/components/RowActions";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { EyeIcon } from "@/components/icons";
import { parseTableParams, serializeTableParams } from "@/components/tableTypes";
import type {
  TableConfig,
  TableFilterConfig,
  TableRequestState,
} from "@/components/tableTypes";
import { ServiceTags } from "@/features/rating/ratingShared";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import type { RegionalDateFormat } from "@/components/DateCell";
import { useTenantPath } from "@/routing/tenantPath";
// ── `CR-150-BRC09` · THREE READERS THIS SCREEN DOES NOT GET TO INVENT ──────
// `AgeCell` is the AGING column one tab over — the SAME rule (`BR-CUS-106`),
// the same server flag, and B14 rule 43: a piece of UI is a component, not
// code copied into a second page. `connectModeWord` and `connectScopeWord`
// are the wizard's own readers of the two codes this list now shows; a second
// reading of either is what `DEF-CUS-6100` was, and it printed `our_crew` to a
// clerk on the last screen before the commit.
import { AgeCell } from "./ServiceRequestsListPage";
import { connectModeWord, connectScopeWord } from "./newConnectDraft";

/**
 * **THIS TAB'S OWN ROOM IN THE PAGE'S QUERY STRING — `DEF-CUS-6099`.**
 *
 * `nc.q`, `nc.sort`, `nc.dir`, `nc.page`, `nc.per`, `nc.f.state`. The dot is
 * what makes it read as a namespace beside the page's own bare `sort` and
 * `f.status`, and it is the same separator `f.<name>` already uses.
 *
 * ⚠ **IT IS A CONSTANT SO THE READ AND THE WRITE CANNOT DRIFT.** Two literals
 * would be two spellings of one namespace, and a filter that writes `nc.` and
 * reads `nct.` is a filter that is silently lost on reload — which is the
 * defect this closes, reintroduced by a typo.
 */
export const NEW_CONNECTS_PARAM_PREFIX = "nc.";

// DEF-730 — the two routes §3 said this file had none of. Both are mounted in
// `App.tsx`: S87 at `/connections/new` (2026-08-25) and S88 at
// `/connections/:connectionId`.
// CR-070 wave O — ONE function says where a build lives, and it is Work's.

// `DEF-CUS-5994` — the three controls the five worklists share, now that a
// parked draft is a ROW rather than a panel above the table.
import {
  ParkedBadge,
  ParkedDiscardDialog,
  ParkedDraftActions,
  ParkedWhyCell,
} from "./parkedDrafts";
import type { ParkedDiscardTarget } from "./parkedDrafts";
import {
  CONNECTIONS_ROUTE,
  NEW_CONNECT_ROUTE,
  draftBuildPath,
  isDraftBuild,
} from "./newConnectShared";
// `CR-150-BRC09` — the four pieces of UI this list is built from, as
// COMPONENTS rather than as 300 lines inside this file (B14 rule 43).
import {
  BUILD_STATE_FILTER,
  BuildActDialog,
  BuildBulkBar,
  BuildRowMenu,
  NewConnectTiles,
} from "./newConnectListViews";
import type { BuildActTarget, BuildTile } from "./newConnectListViews";
import { CONNECTION_SEGMENT_ALL, listConnections, rowsOf, totalOf } from "./worklistEndpoints";
import type {
  ConnectionList,
  ConnectionRow,
  WorklistFilterState,
} from "./worklistEndpoints";

/** The screen id `TableConfig` keys its column preference on. A1 allocates S86
 *  and **no story owns it** — hard-won law 8, filed by three backend files and
 *  REPORTED again here rather than invented. */
export const NEW_CONNECTS_TABLE_SCREEN = "S86";

/** How many service badges fit before the overflow chip. `NCT-01` draws
 *  `E W S T +1` on `CON-26-0117`, which is four badges and then the chip — so
 *  four is READ OFF THE DRAWING, not chosen. `connection_reads._row` leaves
 *  this decision here on purpose: *"the screen … is the only thing that knows
 *  how many badges fit"*. */
export const SERVICE_BADGE_LIMIT = 4;

// ══════════════════════════════════════════════════════════════════════════
// ⛔ THE SEGMENT STRIP IS GONE — CR-045 wave G, `DEF-1702`
// ══════════════════════════════════════════════════════════════════════════
//
// **WHAT STOOD HERE.** `WorklistSegmentOption` and `WorklistSegments`: B18's
// exclusive-tab strip, shared by this screen, S90 and the two move tabs. Four
// screens mounted it and **all four passed it `onSelect={() => undefined}`**,
// because on every one of them exactly one option was `supported` and it was
// the one already active. There was no state for a handler to write.
//
// **WHY IT WENT, AND IT IS NOT BECAUSE OF THE `mb-3`.** It occupied
// `filterBarSlot` — the slot B14 rule 12 reserves for the FILTER, immediately
// after the search box — so four screens read as filtered in a screenshot and
// narrowed nothing. `DEF-1702` was sized twice by walking the screens and
// missed all four both times, and the mechanised sweep says why in one line:
// *"a control that occupies the filter slot, reads as a filter in a screenshot
// and narrows nothing"* is scored `inert`, which is a DIFFERENT FINDING from
// `bare` with a different fix.
//
// **THE RULE THAT DECIDES IT was already written on these same screens**, in
// each one's `downloadSlot` comment: *"Not drawn DISABLED either — BR-SHL-025
// is for a control this ROLE cannot use, not one the PRODUCT does not have."*
// Ranking B18's segments is a capability the PRODUCT does not have — `OQ-371`
// here, `OQ-374` on S90 — so BR-SHL-010 leaves it undrawn, by the files' own
// reasoning. Every one of the four argued both ways until this commit.
//
// **NOTHING ABOUT OQ-371 IS DECIDED.** `unavailable[]` still travels on every
// response with the four unserved segment codes in it, `?segment=` still
// raises `NotImplementedError("OQ-371")` for everything but `all`, and the
// open question still names the strip as its remedy. When it closes, the strip
// comes back — as a control that works. **`SegmentedFilter` is the precedent
// for the deletion itself**: `DEF-1700` removed it the same day, for the same
// reason, and G40 is what keeps a component nothing mounts from lingering.

/**
 * The English fallbacks for the two vocabularies this screen names.
 *
 * ⚠ **THEY ARE `defaultValue`s, NOT COPY.** Every string reaches the screen
 * through `t(key, {defaultValue})`, so the catalogues own the words the moment
 * the locale lane adds the keys — this lane may not edit
 * `src/i18n/locales/*.json`, and shipping a raw `customers.newConnects.state.
 * partly_activated` onto the tab the PO just reported as empty would be a
 * second defect on top of the one being fixed. The keys and these sentences are
 * REPORTED for that lane.
 *
 * ⚠ **AND `partly_activated` READS "Partly activated" — CR-032.** B18 draws
 * *"Partly energised"* and is stamped rather than rewritten; the product ships
 * the ruled word.
 *
 * ⛔ **THIS DOCSTRING USED TO END *"a code this map does not know falls back to
 * the code itself, which is ugly and visible — never blank"*, AND THAT
 * SENTENCE WAS THE DEFECT (`DEF-CUS-6098`).** A code on screen is not
 * ugly-and-visible; **it is invisible**, because it looks deliberate and is
 * never blank. `in_progress_draft` and `parked` sat in the Show filter beside
 * eight translated words for as long as the two codes have existed, and every
 * check passed: `G18` finds a DEAD catalogue entry and `G27` an untranslated
 * literal, and neither can see a key that is never asked for.
 *
 * ⚠ **THE MAP IS ASSERTED COMPLETE AGAINST THE SERVER'S VOCABULARY** by
 * `newConnectStateLabels.test.ts`, which reads `CONNECTION_STATES` out of
 * `apps/metering/connections.py` and the two minted draft codes plus `open` out
 * of `connection_reads.py`. That is `disconnectStateLabels.test.ts`'s shape,
 * minted the same week for the identical defect one tab over, and
 * `signupServices.test.ts`'s before it: **a hand-maintained map keyed on a
 * server vocabulary fails SILENTLY, and only a test that crosses the boundary
 * can see it.**
 */
// ⚠ **HELD, NOT DEAD — `OQ-371` IS OPEN AND BLOCKS THE SEGMENT STRIP.**
// Nothing renders these today, so the linter is right that they are unused.
// They are kept rather than deleted because the map carries a SIGNED word:
// `partly_activated` reads *"Partly activated"* per `CR-032`, where B18 draws
// *"Partly energised"* and was stamped rather than rewritten. Delete this
// suppression and wire the map the day `OQ-371` is answered (`DEF-CUS-3935`).
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const SEGMENT_LABELS: Record<string, string> = {
  all: "All",
  in_progress: "In progress",
  waiting: "Waiting",
  partly_activated: "Partly activated",
  done: "Done",
};

const STATE_LABELS: Record<string, string> = {
  // `open` is the ONE value here that is not a stored state: it is the KPI tile
  // `OPEN BUILDS · not fully activated`, offered as a chip so a clerk can ask
  // for the set the tile above the toolbar already counts. The server names it;
  // this map only says how it reads.
  open: "Open",
  draft: "Draft",
  requested: "Requested",
  in_progress: "In progress",
  partly_activated: "Partly activated",
  on_hold: "On hold",
  activated: "Activated",
  cancelled: "Cancelled",
  // ── `DEF-CUS-6098` · THE TWO THE LIST MINTS, WHICH ARE NOT BUILD STATES ──
  // A parked draft is a `wizard_parks` row and no build at all, which is why
  // `connection_reads` marks both `drawn: false` and why neither could reuse a
  // stored state. **They are deliberately the same two words the Disconnects,
  // Move-ins and Transfers tabs already use** — two spellings for one concept
  // is two things to get wrong (B14 rule 34's reasoning, one register along).
  in_progress_draft: "Draft",
  parked: "Parked",
  // ⚠ **`pending` IS `SERVICE_STATES`'s AND NOT A BUILD STATE (`DEF-MET-7805`).**
  // The build record's Units tab reads a state PER SERVICE and renders it
  // through this same helper rather than opening a second vocabulary, and
  // `apps/metering/connections.SERVICE_STATES` carries one value the build
  // vocabulary does not: `pending`. Without this row that tab would print the
  // token, which is the whole of the defect it was added for.
  pending: "Pending",
};

/**
 * One state code → the word a clerk reads, or an honest absence. **Never the
 * code** (`DEF-CUS-6098`).
 *
 * ⚠ **A MISSING LABEL FAILS LOUDLY IN THREE PLACES, AND THE SCREEN IS THE
 * QUIETEST OF THEM** — `disconnectStateLabel`'s posture, deliberately the same
 * one rather than a second invention. (1) `newConnectStateLabels.test.ts` goes
 * RED when the server's vocabulary grows past this map, (2) landing here writes
 * a `console.error` naming the code, and (3) the option states an absence
 * rather than the code.
 *
 * ⚠ **THE SERVER'S OWN `label` IS READ WHEN IT SENDS ONE**, which it does for
 * `in_progress_draft` and `parked` and which nothing has ever looked at. It
 * sits BELOW the catalogue and below this map, because it is English from a
 * payload and the catalogues carry eleven languages — but above the absence,
 * because a real word beats *not named yet*.
 */
/**
 * ══════════════════════════════════════════════════════════════════════════
 * **WHERE A ROW ON THIS TAB GOES — ONE ANSWER FOR BOTH DOORS**
 * ══════════════════════════════════════════════════════════════════════════
 *
 * `DEF-CUS-6132`, under `BR-SHL-048 (d)` (PO 2026-09-21: *"this is big problem
 * - we cannot create two build - you can update the existing build"*). The
 * ruling is about FINISHING one build rather than minting a second, and it is
 * not satisfied by code that finishes it correctly down a path no clerk can
 * walk.
 *
 * Three kinds of row and three answers:
 *
 *   * **A DRAFT BUILD** — `submitted_at IS NULL`, raised by approving an
 *     application and not yet finished. Its door is **its own wizard**. This
 *     is the row that was broken: `buildHomePath` sent it to the property page
 *     where *Edit details* reads *"No edit path exists yet."*, and a draft
 *     whose address had not resolved has no home at all, so the row carried no
 *     link whatsoever.
 *   * **A COMMITTED BUILD** — **its own page, `/{tenant}/connections/{id}`,
 *     from 2026-09-28 (`CR-151-BRC09` §6a).** It read `buildHomePath` until
 *     that day, because the build had no page of its own and the address was a
 *     doorway that sent the reader to the premises or the account. The hold
 *     that said so carried its own expiry test (law 2's mirror), the test went
 *     red the moment `App.tsx` mounted `BuildDetailPage` there, and this is the
 *     one line it named. `buildHomePath` is still the ONE function saying where
 *     a build LIVES — the approval queue and the dispatcher go on reading it;
 *     what changed is that a clerk opening a build from this list now gets the
 *     build rather than its host.
 *   * **A PARKED WIZARD** — `id` is null and there is no build to open. Its
 *     door is the `Resume` control in the state cell, which `resumePath`
 *     builds; this returns `null` and the number renders as text.
 *
 * ⚠ **A `null` MEANS *NO DOOR*, NEVER *THIS DOOR IS BROKEN***. Both callers
 * render the refusal rather than a link onto nothing — law 2's mirror, which
 * is the fault this whole change exists to remove rather than to move.
 */
export function rowDoor(row: Pick<ConnectionRow, "id" | "state" | "home">): string | null {
  if (isDraftBuild(row.state) && (row.id ?? "") !== "") {
    return draftBuildPath(row.id);
  }
  if ((row.id ?? "") !== "") {
    return `${CONNECTIONS_ROUTE}/${row.id}`;
  }
  // A PARKED WIZARD has no build to open, so it has no door here — the state
  // cell's `Resume` is its way in. `buildHomePath` is not reached from this
  // function any more and is deliberately not called as a fallback: a row with
  // no id has no build, and sending the reader to a HOST instead would be the
  // doorway this flip removed, wearing a different name.
  return null;
}

export function connectionStateLabel(
  code: string,
  t: (key: string, params?: Record<string, unknown>) => string,
  servedLabel?: string | null,
): string {
  const known = STATE_LABELS[code] ?? (servedLabel === null ? undefined : servedLabel);
  if (known === undefined) {
    console.error(
      `NewConnectsTab: the server offers the state "${code}" and STATE_LABELS has no word ` +
        "for it, so the option states an absence rather than the code (DEF-CUS-6098). Add " +
        "the label and the eleven catalogue keys; newConnectStateLabels.test.ts is already " +
        "red.",
    );
    return t("customers.newConnects.state.unnamed", { defaultValue: "Not named yet" });
  }
  return t(`customers.newConnects.state.${code}`, { defaultValue: known });
}

/**
 * The one dimension `NCT-01` declares — the build's STATE (CR-045 wave G,
 * `DEF-1702`).
 *
 * ⚠ **THIS REPLACED `connectionSegments`/`connectionSegmentAbsence`, AND A
 * SEGMENT IS NOT A FILTER.** `OQ-371` asks which EXCLUSIVE tab holds a build
 * that is `partly_activated` AND waiting — `CON-26-0126` is genuinely both, the
 * tabs are exclusive, and one of the two facts has to lose. That is an
 * assignment problem and only the PO can settle it. **`f.state=partly_activated`
 * returns the builds in that state and claims nothing about which tab owns
 * them**, so it needs no precedence and hides nothing.
 *
 * The registry states the same distinction from the other side: *"The segments
 * are not the state tokens — not one drawn row carries `Waiting` or `Done` in
 * its STATE column, and `waiting_on` is a separate column beside STATE."*
 * `Waiting` is derived from `waiting_on`; `state` is a stored column this table
 * already draws. **They are different questions over different data**, which is
 * why one is open and the other shipped.
 *
 * ⚠ **THE VOCABULARY IS `states` ON THE PAYLOAD (BR-SHL-010).**
 * `connection_reads.OPEN_STATES` is `CONNECTION_STATES` minus `activated` and
 * `cancelled` — the two the worklist's own window already excludes — so this
 * panel can never offer an option that always answers "none". Nothing is typed
 * here; a state added to the workflow reaches the panel with no edit, and
 * `STATE_LABELS` stays a `defaultValue` map rather than a second vocabulary.
 */
export function connectionFilterGroups(
  states: WorklistFilterState[] | undefined,
  t: (key: string, params?: Record<string, unknown>) => string,
): TableFilterConfig[] {
  return [
    {
      // ⚠ **ONE LITERAL FOR THE DIMENSION, SHARED WITH THE TILES
      // (`CR-150-BRC09`).** A tile writing `nc.f.state` while the bar read
      // `nc.f.status` would be a filter that applies and is never shown — the
      // two halves of one control disagreeing, silently, with `tsc` and every
      // test green. The constant is what makes that impossible.
      name: BUILD_STATE_FILTER,
      // ── THE CHIP'S WORD IS `Show`, NOT `State` (the blueprint, p094) ──────
      // The bar renders an applied filter as `{label}: {value} ×`, so this
      // label is what a clerk actually reads on the toolbar. `Show: Open ×` is
      // the sentence the Requests tab one tab over already prints, and the two
      // tabs of one register now ask their one question in one voice. `State`
      // stays the COLUMN's word, which is a different job: the column reports
      // a row's state, the chip says what the list is showing.
      label: t("customers.newConnects.filter.show", { defaultValue: "Show" }),
      // ⚠ **`connectionStateLabel`, NEVER `STATE_LABELS[code] ?? code`
      // (`DEF-CUS-6098`).** The inline fallback is what put `in_progress_draft`
      // and `parked` in front of a clerk: the option list is built from
      // whatever the SERVER sends, so adding a state server-side silently added
      // an untranslated chip to the screen — hard-won law 2's shape for the
      // eleventh service, one module along.
      options: (states ?? []).map((state) => ({
        value: state.code,
        label: connectionStateLabel(state.code, t, state.label ?? null),
      })),
    },
  ];
}

// ══════════════════════════════════════════════════════════════════════════
// THE CELLS
// ══════════════════════════════════════════════════════════════════════════

/**
 * `NCT-01`'s STATE column.
 *
 * ⚠ **B18 DRAWS NO TONE FOR THIS COLUMN**, so the mapping below is the
 * SCREEN's and is stated as such rather than presented as design: a finished
 * build reads success, a build that is part-way or parked reads warning, and
 * everything else is neutral. It decides nothing about OQ-371 — a tone is not a
 * segment, and no row is filtered by it.
 */
export function connectionStateTone(state: string): StatusTone {
  if (state === "activated") {
    return "success";
  }
  if (state === "partly_activated" || state === "on_hold") {
    return "warning";
  }
  return "neutral";
}

/**
 * `ORDERS` — B18 §5.4.2, verbatim: *"drawn as `5 of 9` over an accent progress
 * underline `[shot]` — not a percentage, not a bar alone. The fraction is
 * readable; a bar is not."*
 *
 * So the FRACTION is the value and the underline is decoration beneath it. The
 * server sends both halves and no ratio (`connection_reads._row`), and the
 * percentage computed here never becomes text — it is a width, and it is
 * `aria-hidden` because the fraction above it already says the same thing to a
 * screen reader.
 *
 * ⚠ A build with NO orders draws no underline rather than a full one: zero of
 * zero is not complete.
 */
export function OrdersCell(props: {
  row: ConnectionRow;
  t: (key: string, params?: Record<string, unknown>) => string;
}) {
  const { done, total } = props.row.orders;
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  return (
    <span className="inline-flex flex-col gap-1">
      <span className="tabular-nums" data-orders={`${done}/${total}`}>
        {props.t("customers.newConnects.list.orders", {
          defaultValue: "{{done}} of {{total}}",
          done,
          total,
        })}
      </span>
      <span aria-hidden="true" className="block h-0.5 w-16 bg-neutral-300">
        <span className="block h-0.5 bg-accent" style={{ width: `${pct}%` }} />
      </span>
    </span>
  );
}

/**
 * `SERVICES` — the two-character badge set with a `+N` overflow chip.
 *
 * `ServiceTags` is the ONE badge control (ten services, ten distinct tokens);
 * this only decides how many of them fit, which is the decision
 * `connection_reads._row` deliberately left to the screen.
 */
export function ServicesCell(props: {
  services: readonly string[];
  t: (key: string, params?: Record<string, unknown>) => string;
}) {
  const shown = props.services.slice(0, SERVICE_BADGE_LIMIT);
  const overflow = props.services.length - shown.length;
  return (
    <span className="inline-flex items-center gap-1">
      <ServiceTags services={shown} />
      {overflow > 0 && (
        <span
          className="text-xs text-neutral-700"
          data-services-overflow={overflow}
          title={props.services.join(" · ")}
        >
          {props.t("customers.newConnects.list.servicesMore", {
            defaultValue: "+{{count}}",
            count: overflow,
          })}
        </span>
      )}
    </span>
  );
}

/**
 * `CUSTOMER` — the owner account's customer NAME over its account NUMBER.
 *
 * ⚠ **THE WHOLE BLOCK IS NULL WHEN THERE IS NO OWNER ACCOUNT, AND THAT IS ONE
 * FACT RATHER THAN TWO EMPTY CELLS.** The server serves `customer: null` — not
 * an object of nulls — precisely so this cell cannot read `account_no` off a
 * block meaning *nobody has been assigned* and draw it as *a customer with no
 * number*. The drawing writes **no account yet** under the name on exactly
 * that row, and the words are the screen's: three words, a FACT, B14 rule 33.
 * An EMPTY cell here would be `DEF-127`'s shape one column along — a blank and
 * an absent fact read the same way once drawn.
 *
 * ⚠ **`account_no` IS NOT A DATABASE ID AND B14 RULE 31 DOES NOT FORBID IT.**
 * Rule 31 is *"no Databse ID on screen"* — the primary key. This is
 * `accounts.account_no`, the number a clerk reads down the phone
 * (`AC-2026-00011`), the same class as `connection_no` in the BUILD column and
 * `premise_no` in PREMISE, and `worklistEndpoints` serves no `id` on this
 * block at all, so there is nothing here to render by mistake.
 */
export function CustomerCell(props: {
  row: ConnectionRow;
  t: (key: string, params?: Record<string, unknown>) => string;
}) {
  const noAccount = (
    <span className="text-sm text-neutral-700" data-customer-absent="">
      {props.t("customers.newConnects.list.noAccountYet", {
        defaultValue: "no account yet",
      })}
    </span>
  );
  const customer = props.row.customer ?? null;
  if (customer === null) {
    return noAccount;
  }
  const name = customer.name ?? "";
  const accountNo = customer.account_no ?? "";
  return (
    <span className="flex flex-col" data-customer-account={accountNo}>
      {name === "" ? noAccount : <span>{name}</span>}
      {accountNo !== "" && (
        <span className="text-sm tabular-nums text-neutral-700">{accountNo}</span>
      )}
      {name !== "" && accountNo === "" && noAccount}
    </span>
  );
}

/**
 * `Charged` behind the column chooser — the build's quote, as the SERVER
 * rounded it.
 *
 * ⚠ **`display` IS PRINTED AND NOTHING IS RE-ROUNDED OR MULTIPLIED** (hard
 * rule 2: money is stored to 4 decimals, displayed at 2, and rounded ONCE,
 * server-side). `stored` is deliberately not read here.
 *
 * ⚠ **`{stored: null, display: null}` IS A BUILD NOBODY PRICED AND IT STATES
 * AN ABSENCE, NEVER `$0.00`.** `DEF-127`: a fabricated zero *"looks exactly
 * like a settled account"* — here it would read as a build that costs the
 * customer nothing, which is the most expensive wrong thing this column can
 * say. A parked draft is always in this case: the wizard parks before a quote
 * exists.
 *
 * ⛔ **NO CURRENCY SYMBOL, BECAUSE THE ENDPOINT SERVES NO CURRENCY —
 * `DEF-CUS-7806`.** `connection_reads._pair` emits `{stored, display}` and no
 * `CHAR(3)`, so `MoneyCell` cannot be used and a `$` typed here would be this
 * screen asserting a currency for a tenant that may not be in it (hard rule
 * 2). The figure is drawn right-aligned in tabular figures and the symbol
 * arrives with the field.
 */
export function ChargedCell(props: {
  row: ConnectionRow;
  t: (key: string, params?: Record<string, unknown>) => string;
}) {
  const display = props.row.quote_total?.display ?? null;
  if (display === null) {
    return (
      <span className="text-sm text-neutral-700" data-charged-absent="">
        {props.t("customers.newConnects.list.notPriced", { defaultValue: "Not priced" })}
      </span>
    );
  }
  return (
    <span className="tabular-nums" data-charged={display}>
      {display}
    </span>
  );
}

/** The six tokens `connection_reads.STAMPED_EVENTS` can emit, plus the one a
 *  parked draft emits (`parked`). ⚠ **THE SERVER SENDS A TOKEN AND NEVER A
 *  SENTENCE**, deliberately — an English sentence composed on the server
 *  cannot be translated — so the words live here and in the catalogues. */
const LAST_EVENT_WORDS: Record<string, string> = {
  created: "Created",
  submitted: "Submitted",
  held: "Held",
  activated: "Activated",
  cancelled: "Cancelled",
  parked: "Parked",
};

/**
 * `Last event` behind the column chooser — the build's own newest STAMP.
 *
 * ⚠ **IT IS NOT THE AUDIT TRAIL, AND THE SERVER NAMED IT `last_stamped_event`
 * SO NO LANE READS IT AS ONE.** The History tab reads `entity_trail`, which
 * addresses one entity; a list column calling it per row would be a query per
 * row to draw an optional cell.
 *
 * ⚠ **AN UNKNOWN TOKEN FAILS LOUDLY AND NEVER PRINTS ITSELF** —
 * `connectionStateLabel`'s posture in the same file and `DEF-CUS-6098`'s
 * lesson: a code on screen is not ugly-and-visible, it is INVISIBLE, because
 * it looks deliberate and is never blank.
 */
export function LastEventCell(props: {
  row: ConnectionRow;
  t: (key: string, params?: Record<string, unknown>) => string;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const event = props.row.last_stamped_event ?? null;
  if (event === null) {
    return <Dash />;
  }
  const known = LAST_EVENT_WORDS[event.what];
  if (known === undefined) {
    console.error(
      `NewConnectsTab: the server stamped the event "${event.what}" and LAST_EVENT_WORDS ` +
        "has no word for it, so the cell states an absence rather than the code " +
        "(DEF-CUS-6098). Add the word and the eleven catalogue keys.",
    );
  }
  return (
    <span className="flex flex-col" data-last-event={event.what}>
      <span>
        {known === undefined
          ? props.t("customers.newConnects.state.unnamed", { defaultValue: "Not named yet" })
          : props.t(`customers.newConnects.event.${event.what}`, { defaultValue: known })}
      </span>
      <span className="text-sm text-neutral-700">
        <DateCell value={event.at} timeZone={props.timeZone} dateFormat={props.dateFormat} />
      </span>
    </span>
  );
}

/**
 * The in-table link, once.
 *
 * ⚠ **IT IS `AssetDetailPage`'s `LINK` STRING, CHARACTER FOR CHARACTER**, and
 * that file's own note says why it had to become a constant there: *"Five call
 * sites wrote this identical string out by hand and a sixth was about to …
 * which is how a screen ends up with two kinds of link that nobody chose."*
 * The product has two link looks today — this one and a bare `text-accent
 * underline` at five sites — and B14 rule 36's lesson is that a visual decision
 * only one file can read is a visual decision the next file makes again.
 * **This is the SEVENTH site and it belongs in the kit, not in a third file.**
 * Copying it here rather than importing another feature's private constant is
 * the lesser of two wrongs for one wave; moving it into `components/` is its
 * own change with its own sweep, and is REPORTED rather than done in passing.
 *
 * `focus-visible:underline` is not decoration — the underline is the only
 * non-colour cue the link carries, so a keyboard user needs it (skill §3 step
 * 6: default · hover · focus-visible · active, all of them).
 */
const LINK =
  "cursor-pointer text-accent-700 no-underline hover:underline focus-visible:underline";

/** A value the server sent as null or empty. `NCT-01` draws `—` in WAITING ON
 *  for a build nobody is waiting on, and that IS "none" — not "we do not know"
 *  — so the dash is correct here and only here. */
function Dash() {
  return <span aria-hidden="true">—</span>;
}

export function newConnectsTableConfig(
  t: (key: string, params?: Record<string, unknown>) => string,
  cells: {
    // `CR-150-BRC09` — the tick box the drawing puts in front of every row.
    select: (row: ConnectionRow) => JSX.Element;
    // The row's OWN way in — see the BUILD column below.
    connection: (row: ConnectionRow) => JSX.Element;
    premise: (row: ConnectionRow) => JSX.Element;
    // `DEF-CUS-7804` — the drawn CUSTOMER column.
    customer: (row: ConnectionRow) => JSX.Element;
    // `DEF-CUS-7804` — the chooser's `Charged`.
    charged: (row: ConnectionRow) => JSX.Element;
    services: (row: ConnectionRow) => JSX.Element;
    orders: (row: ConnectionRow) => JSX.Element;
    target: (row: ConnectionRow) => JSX.Element;
    state: (row: ConnectionRow) => JSX.Element;
    // `DEF-CUS-7804` — the drawn `Last event`, which needs the tenant's own
    // clock and date format and so cannot be built out of `t` alone.
    lastEvent: (row: ConnectionRow) => JSX.Element;
    // DEF-730 — the row's own way in. See the ACTIONS column below.
    actions: (row: ConnectionRow) => JSX.Element;
  },
): TableConfig<ConnectionRow> {
  return {
    screenId: NEW_CONNECTS_TABLE_SCREEN,
    getRowId: (row) => row.id,
    searchFields: ["connection_no", "premise", "address", "applicant", "request_no"],
    // ✅ **B14 RULE 19'S PROMPT IS WIRED (CR-041 task 2).** It was OWED and
    // deliberately unset here, for a correct reason: `searchPlaceholder` is an
    // i18n KEY rendered through `t(key)` with NO `defaultValue`, so a key the
    // catalogues do not hold ships the raw identifier to the screen — and that
    // lane could not edit the eleven catalogues.
    //
    // ⚠ **THE LOCALE LANE THEN ADDED THE KEY IN ALL ELEVEN LANGUAGES AND NOBODY
    // CAME BACK TO SET IT.** Same for `DisconnectsTab` and `TransfersTab`.
    // Three fully translated sentences, reachable by nothing, while the boxes
    // said "Search this list" — hard-won law 2, built is not wired, in the one
    // shape no gate here catches: G13 reads component PROPS, and this is a
    // catalogue key with no reader. G18's "catalogue key with no call site"
    // count did name them, at 181 keys deep.
    //
    // The sentence is B18 §5.4.2's own, which `connection_reads._search` quotes
    // verbatim above its five `Q(...)` legs, so prompt and predicate agree.
    searchPlaceholder: "customers.newConnects.list.searchPlaceholder",
    //
    // ⚠ **THE PATH ABOVE USED TO BE WRITTEN `src/i18n/locales/*.json` AND THAT
    // BLINDED A GATE (found 2026-08-26, DEF-730's lane).** `G27` strips block
    // comments with `/\*.*?\*/` BEFORE line comments, so the `/*` inside
    // `locales/*.json` opened a comment that ran to the next `*/` — 5.5 KB
    // further down — and every `t("...")` in between was invisible to the check
    // that exists to find a key no catalogue answers. It was hiding exactly one
    // key, this file's new `customers.newConnects.col.actions`, so rewording
    // the path is what makes the gate able to report it. REPORTED: the same
    // spelling appears in `DisconnectsTab`, `MoveInsTab`, `TransfersTab` and
    // once more in this file's own header, and the durable fix is G27 stripping
    // line comments first.
    // ⚠ NO SORT. `list_connections` accepts no `sort`/`dir` and fixes the order
    // itself; this value only seeds `defaultRequestState` and reaches no
    // request. No column below is `sortable`, so `DataTable` draws no control.
    // ── `BR-CUS-1046` (PO 2026-09-10, EXTENDED 2026-09-12) ──────────────────
    // *"It should always sort it by the creation order. The new newly created
    // entries should always show on the top."* The name is the SERVER's sort
    // name; `created` orders `created_at DESC, id DESC`.
    //
    // ⚠ **`created` IS NOT A COLUMN ON THIS TABLE, AND THAT IS DELIBERATE.**
    // Neither the blueprint nor B18 draws a Created column here, and the skill's
    // §2.5 is explicit that an absence is a decision: *say so, do not add it*.
    // So no header carries the glyph while the list is on its default, and the
    // sentence under the pager is what states the ordering — which is the
    // mechanism this screen already used for exactly that job.
    // ⚠ **THIS TAB OPENED ON `target_activation` ASCENDING** — B18 §5.4.2's
    // *"the next thing due is at the top"*. That column is sortable now, and the
    // server keeps its nulls-last rule in BOTH directions: a build with no target
    // date is the one blocked on a human, never the top of page one.
    defaultSort: { sort: "created", dir: "desc" },
    // ── CR-045 wave G · `DEF-1702` — STATE, and state only ────────────────
    // ⚠ **THE DIMENSION IS DECLARED HERE; THE OPTIONS ARE NOT.**
    // `parseTableParams`/`serializeTableParams` read only `filter.name`, which
    // is what round-trips `?f.state=on_hold` (BR-SHL-011), and the name is a
    // static capability of this screen. The VALUES are the server's and arrive
    // on the response, so this call passes none; the panel is handed
    // `connectionFilterGroups(listQuery.data?.states, …)` at render.
    filters: connectionFilterGroups(undefined, t),
    columns: [
      // ── `CR-150-BRC09` · THE TICK BOX, WHICH IS A NEW COLUMN KEY ─────────
      // ⚠ **A CLERK WITH A SAVED COLUMN SET ON S86 WILL NOT SEE IT UNTIL THEY
      // PRESS RESET, AND THAT IS STATED RATHER THAN WORKED AROUND.**
      // `columnsFromPreference` keeps only the keys a preference already
      // holds, and `DataTable` force-shows the IDENTITY column alone — so a
      // column minted after a preference was stored is absent from it. The
      // alternatives were worse: folding the box into the Build cell would put
      // a control inside an identity value, and making it the identity column
      // would take that status off the number rule 31 says is the visible one.
      // `locked` at least means it cannot be hidden again once seen.
      {
        key: "select",
        locked: true,
        label: t("customers.newConnects.col.select", { defaultValue: "Pick" }),
        cell: cells.select,
      },
      {
        key: "connection_no",
        // `BR-CUS-1046` — SORTABLE, and the key IS the server's sort name.
        sortable: true,
        // ⚠ **THE WORD IS `Build` AND THE KEY IS STILL `connection_no`.** The
        // 2026-09-28 drawing heads this column `BUILD`, which is what the PO
        // calls the thing; `connection_no` stays the column KEY because
        // `DataTable` stores a clerk's show/hide/reorder preference against it
        // (`BR-SHL-013`, `DEF-647`) and it is also the SERVER's sort name, so
        // renaming the key would discard every saved column set on this screen
        // AND silently stop the header sorting. `connection_reads.SORTS` made
        // the same trade in the same words.
        label: t("customers.newConnects.col.build", { defaultValue: "Build" }),
        identity: true,
        // ⚠ **THE NUMBER IS THE DOOR NOW, AND IT WAS PLAIN TEXT UNTIL TODAY.**
        // PO, on this list: *"can you imporve the interaction design"*. The only
        // way into a build was an icon at the far right of a nine-column row,
        // and a clerk's hand goes to the number they came here to find — so the
        // number they are already looking at is what opens it. The eye stays:
        // it is B14 rule 15's row action and it is where a clerk who works by
        // the action column looks. Two doors, one destination, one function
        // deciding where that is (`buildHomePath`).
        //
        // Rule 31 — the visible value is `connection_no`, the human number the
        // blueprint draws (`CX-26-0007`). The primary key is never on screen.
        cell: cells.connection,
      },
      {
        key: "premise",
        label: t("customers.newConnects.col.premise", { defaultValue: "Premise" }),
        // ⚠ **A FOURTH CASE SINCE `DEF-CUS-6109`: THERE MAY BE NO PREMISES AT
        // ALL.** A build raised by approving an application whose address had
        // not resolved carries none until its wizard commits (`BR-MET-112`),
        // and the three-way fallback below would have thrown on the FIRST
        // clause — `tsc` caught it only because the row type moved with the
        // server, which is the whole reason it did.
        //
        // ⚠ **AN EM DASH RATHER THAN A SENTENCE, AND THAT IS THE HOUSE
        // CONVENTION** — `waiting_on` renders its own absence the same way. A
        // sentence here would be a fourteenth locale key for a cell that is
        // empty for a few minutes, and `B14` rule 32 caps what a table says.
        //
        // ⚠ **TWO LINES SINCE `CR-150-BRC09`** — the drawing stacks the
        // property's NAME over its address (`New Highland Park` / `1200 Main
        // St, Ottumwa`), which is how a clerk recognises the site before they
        // read the street. The one-line fallbacks are unchanged and are still
        // what a premises with no name, or no premises at all, renders.
        cell: cells.premise,
      },
      // ── `DEF-CUS-7804` · `CUSTOMER`, THE DRAWN COLUMN NOTHING READ ───────
      // `00-list.png` puts it between PREMISE and UNITS and `_row` has served
      // it since `01580d8fc`. It was declared nowhere on this side, so the
      // whole fact rendered as nothing while `tsc`, every case and every gate
      // passed — hard-won law 2.
      //
      // ⚠ **A CLERK WITH A SAVED COLUMN SET ON S86 WILL NOT SEE IT UNTIL THEY
      // PRESS RESET**, the same caveat the tick box above carries and for the
      // same mechanism: `columnsFromPreference` keeps only the keys a stored
      // preference already holds, so a column minted after it was stored is
      // absent from it. It is NOT `locked` — locking is for a control that
      // must never be hidden, and a clerk may legitimately hide this one.
      {
        key: "customer",
        label: t("customers.newConnects.col.customer", { defaultValue: "Customer" }),
        cell: cells.customer,
      },
      {
        key: "units",
        label: t("customers.newConnects.col.units", { defaultValue: "Units" }),
        numeric: true,
        cell: (row) => <span className="tabular-nums">{row.units}</span>,
      },
      {
        key: "services",
        label: t("customers.newConnects.col.services", { defaultValue: "Services" }),
        cell: cells.services,
      },
      {
        key: "orders",
        label: t("customers.newConnects.col.orders", { defaultValue: "Orders" }),
        cell: cells.orders,
      },
      {
        key: "target_activation",
        // `BR-CUS-1046` — SORTABLE, and the key IS the server's sort name.
        sortable: true,
        label: t("customers.newConnects.col.target", { defaultValue: "Target" }),
        cell: cells.target,
      },
      {
        key: "state",
        // `BR-CUS-1046` — SORTABLE, and the key IS the server's sort name.
        sortable: true,
        label: t("customers.newConnects.col.state", { defaultValue: "State" }),
        cell: cells.state,
      },
      // ── `DEF-CUS-7804` · `AGING`, THE OTHER DRAWN COLUMN NOTHING READ ────
      // The drawing puts it last, after STATE, and draws `41 days` in the
      // accent on the build that has been waiting on the fire marshal.
      //
      // ⚠ **`AgeCell` IS THE CELL ONE TAB OVER AND IS IMPORTED, NOT COPIED**
      // (B14 rule 43). The threshold is `BR-CUS-106`'s, it lives on the
      // SERVER, and this screen renders the flag — writing `days >= 7` here
      // would be the second copy, which is the one that drifts. The same
      // component also draws *nobody could be asked* apart from *not old*,
      // which is a distinction the New connects list can actually reach
      // because it asks customers through a seam.
      //
      // ⚠ **NOT SORTABLE.** `connection_reads.SORTS` holds `created`,
      // `target_activation`, `connection_no` and `state` and no age term, so
      // declaring this sortable would render a control the request cannot
      // carry — both halves or neither (hard-won law 2, and `BR-CUS-1046`'s
      // own note on this table).
      {
        key: "aging",
        label: t("customers.newConnects.col.aging", { defaultValue: "Aging" }),
        cell: (row) => <AgeCell row={row} t={t} />,
      },
      // ⚠ **`WAITING ON` MOVED BEHIND THE CHOOSER — `CR-150-BRC09`.** The
      // 2026-09-28 drawing draws no Waiting-on column: it folds the fact into
      // the STATE cell as `Waiting · fire marshal`, which is one cell saying
      // what is true of the build instead of two saying halves of it. The
      // column stays DECLARED, because the fact is still worth a column to a
      // clerk chasing third parties, and the chooser is where the drawing puts
      // the rest.
      {
        key: "waiting_on",
        defaultVisible: false,
        label: t("customers.newConnects.col.waitingOn", { defaultValue: "Waiting on" }),
        cell: (row) =>
          row.waiting_on === null || row.waiting_on === "" ? (
            <Dash />
          ) : (
            <span>{row.waiting_on}</span>
          ),
      },
      // ⚠ **`FROM REQUEST` IS ON BY DEFAULT FROM TODAY, AND IT IS THE COLUMN
      // THE BLUEPRINT CALLS THE SPINE.** It was `defaultVisible: false` under
      // the label `Request #`, on the reasoning that *"drawing them by default
      // would add two columns to a drawn screen"* — correct against `NCT-01`,
      // which does not draw it, and overtaken by the Accounts blueprint, which
      // does. p093 states what the column is FOR in the sentence that is this
      // list's whole brief: *"Onto the New connects tab, either raised directly
      // or created by approving a request — and the list says which."* A list
      // that cannot say which does not answer the question it exists for, and
      // p094's own caption names the column as the thing that answers it.
      //
      // The dash is the fact rather than an absence: a build with no request
      // was raised at the counter, which is one of the two things this column
      // reports.
      //
      // ⚠⚠ **AND IT IS OFF BY DEFAULT AGAIN FROM 2026-09-28 (`CR-150-BRC09`),
      // WHICH REVERSES THE PARAGRAPH ABOVE RATHER THAN CONTRADICTING IT.** The
      // Accounts blueprint p093/p094 is a drawing of this list from BEFORE the
      // PO redrew it; `00-list.png` is the drawing of record for this screen
      // now, it draws ten columns and this is not one of them, and its README
      // names the column explicitly among the six the chooser holds:
      // *"Columns chooses the rest: charged, mode, scope, raised by, request
      // number, last event."* Later drawing of the same screen wins (B14 rule
      // 41), and the supersession is stamped rather than the old reasoning
      // deleted (hard-won law 1).
      {
        key: "request_no",
        defaultVisible: false,
        label: t("customers.newConnects.col.fromRequest", { defaultValue: "From request" }),
        cell: (row) =>
          row.request_no === null ? (
            <Dash />
          ) : (
            <span className="tabular-nums">{row.request_no}</span>
          ),
      },
      // ══════════════════════════════════════════════════════════════════
      // `DEF-CUS-7804` — THE FIVE THE CHOOSER HOLDS, WIRED
      // ══════════════════════════════════════════════════════════════════
      // The drawing's README names six columns behind `Columns ▾`:
      // *"charged, mode, scope, raised by, request number, last event"*. The
      // request number is above; these are the other five. `_row` has served
      // every one since `01580d8fc` and **not one of them was declared here**,
      // so the chooser offered a clerk five columns fewer than the endpoint
      // could fill and nothing anywhere went red (hard-won law 2).
      //
      // ⚠ **EACH ABSENCE SAYS WHICH KIND OF NOTHING IT IS, AND THAT IS THE
      // WHOLE CARE IN THIS BLOCK.** An em dash means *none of this* — the
      // reading `Dash()`'s own note reserves for `waiting_on`. These three
      // fields are different: `scope` is null because **nobody was asked**
      // (the column was deliberately not back-filled), `mode` is null because
      // **no order has been raised yet**, and `raised_by` is null because the
      // person **can no longer be named**. A dash on any of them would be
      // `DEF-127`'s substitution — an absent fact and a blank read the same
      // way once drawn.
      {
        key: "quote_total",
        defaultVisible: false,
        numeric: true,
        label: t("customers.newConnects.col.charged", { defaultValue: "Charged" }),
        cell: cells.charged,
      },
      {
        key: "mode",
        defaultVisible: false,
        label: t("customers.newConnects.col.mode", { defaultValue: "Mode" }),
        // `connectModeWord` is the wizard's own reader — one reading of this
        // code in the product (`DEF-CUS-6100`), including the derived `mixed`.
        cell: (row) =>
          (row.mode ?? "") === "" ? (
            <span className="text-sm text-neutral-700" data-mode-absent="">
              {t("customers.newConnects.list.noOrdersYet", { defaultValue: "No orders yet" })}
            </span>
          ) : (
            <span data-mode={row.mode}>{connectModeWord(String(row.mode), t)}</span>
          ),
      },
      {
        key: "scope",
        defaultVisible: false,
        label: t("customers.newConnects.col.scope", { defaultValue: "Scope" }),
        cell: (row) =>
          (row.scope ?? "") === "" ? (
            <span className="text-sm text-neutral-700" data-scope-absent="">
              {t("customers.newConnects.list.notAsked", { defaultValue: "Not asked" })}
            </span>
          ) : (
            <span data-scope={row.scope}>{connectScopeWord(String(row.scope), t)}</span>
          ),
      },
      {
        key: "raised_by",
        defaultVisible: false,
        label: t("customers.newConnects.col.raisedBy", { defaultValue: "Raised by" }),
        cell: (row) =>
          (row.raised_by ?? "") === "" ? (
            <span className="text-sm text-neutral-700" data-raised-by-absent="">
              {t("customers.newConnects.list.notNamed", { defaultValue: "Not named" })}
            </span>
          ) : (
            <span>{row.raised_by}</span>
          ),
      },
      {
        key: "last_stamped_event",
        defaultVisible: false,
        label: t("customers.newConnects.col.lastEvent", { defaultValue: "Last event" }),
        cell: cells.lastEvent,
      },
      // ⚠ **THE ACTIONS COLUMN §3 SAID THIS TAB WOULD NOT HAVE, ADDED BY
      // DEF-730.** That refusal was right when written — *"`NCT-02` (the
      // connection detail) has no route in this application, so an 👁 view icon
      // would be a link onto nothing"* — and S88 landed at
      // `/connections/:connectionId` the same day. Without it a row could be
      // read and never OPENED, which is the other half of the PO's report.
      //
      // ⚠ **AND IT CARRIES THE `⋮` MENU FROM 2026-09-28 (`CR-150-BRC09`).**
      // The drawing puts one control at the end of a row and it is the menu;
      // the eye stays beside it because task 15 keeps the row's second door
      // and because B14 rule 15's grammar is *max two visible plus an
      // overflow* — an eye and a `⋮` is exactly that shape.
      {
        key: "actions",
        locked: true,
        label: t("customers.newConnects.col.actions", { defaultValue: "Actions" }),
        cell: cells.actions,
      },
      // ⚠ THE COLUMN `NCT-01` DOES NOT DRAW, AND WHY IT IS HERE AT ALL.
      // `connection_reads._row` serves `applicant` for one stated reason: *"a
      // clerk who searches an applicant's name and gets back four rows that
      // mention neither cannot tell why they matched."* Drawing it by default
      // would add a column the blueprint does not draw; dropping it would leave
      // a search leg whose results look arbitrary. So it is DECLARED and OFF,
      // and the column chooser every list already has turns it on.
      {
        key: "applicant",
        label: t("customers.newConnects.col.applicant", { defaultValue: "Applicant" }),
        defaultVisible: false,
        cell: (row) =>
          row.applicant === null || row.applicant === "" ? <Dash /> : <span>{row.applicant}</span>,
      },
    ],
  };
}

export function connectionsQueryKey(state: TableRequestState): readonly unknown[] {
  // `state.filters` is IN THE KEY, or react-query answers the filtered request
  // from the unfiltered page already in cache and the list never moves.
  return [
    "connections",
    CONNECTION_SEGMENT_ALL,
    state.q,
    state.page,
    state.per,
    state.filters,
    // ⚠ **`state.sort` AND `state.dir` ARE IN THE KEY FOR THE REASON
    // `state.filters` IS (`BR-CUS-1046`).** Without them react-query answers a
    // re-sorted request from the previously-sorted page already in cache: the
    // header's arrow flips, the rows do not move, and no request is ever made.
    // That is `state.filters`' own defect one column along.
    state.sort,
    state.dir,
  ];
}

/**
 * The strip — B18 §5.4.1's five, plus the two `00-list.png` adds.
 *
 * ⚠ **THIS DOCSTRING READ *"The five tiles of B18 §5.4.1"* UNTIL 2026-09-29
 * AND THE COUNT IS NOW SEVEN (`DEF-CUS-7804`).** `Waiting on someone` and
 * `Owed on builds` are the drawing's, and neither of the two the drawing
 * dropped — `Waiting on inspection` and `Oldest` — has been taken off, because
 * both are live and served and removing a working figure is law 2 backwards.
 * **The drawing draws FIVE and this draws SEVEN, which is `DEF-CUS-7805`**,
 * filed rather than settled by this lane.
 *
 * ⚠ **`OLDEST` IS NOT `?? 0`.** A tenant with no open build has NO oldest one,
 * and *"0 days"* is a different claim from *"there is none"* — the same
 * judgment `ServiceRequestsListPage` makes one tab over, and the same one
 * DEF-127 was filed for on a money figure.
 *
 * ⚠ **`UNITS AWAITING ACTIVATION`'s CAPTION IS THE DESIGN'S AND ITS FIGURE IS
 * THE SERVER'S, AND THEY DO NOT QUITE AGREE.** `connection_reads` §2 measured
 * it: 42 is the UNITS column summed over the OPEN builds, which includes units
 * of a partly-activated build that are already live, so the *awaiting* reading
 * is not computable from anything signed. The tile prints the served figure and
 * the drawn caption, exactly as the backend REPORTED it; nothing here
 * reconciles the two, because reconciling them would mean inventing the split.
 */
export function newConnectsKpis(
  payload: ConnectionList | undefined,
  t: (key: string, params?: Record<string, unknown>) => string,
): KpiTile[] {
  const kpis = payload?.kpis;
  const oldest = kpis?.oldest ?? null;
  // ⛔ `DEF-CUS-7619` — the 2-dp string the server rounded, or `null`. Exactly
  // one of this and `owed_on_open_builds_unavailable` is ever set, and today
  // it is always the reason. Read ONCE here so the tile below cannot branch on
  // one field and print another.
  const owed = kpis?.owed_on_open_builds?.display ?? null;
  return [
    {
      id: "open",
      label: t("customers.newConnects.kpi.open", { defaultValue: "Open" }),
      value: kpis?.open ?? 0,
      detail: t("customers.newConnects.kpi.openDetail", {
        defaultValue: "service being established",
      }),
    },
    {
      // ── `DEF-CUS-7804` · THE DRAWING'S SECOND TILE, WIRED ───────────────
      // `00-list.png` captions it *Waiting on someone*: every open build with
      // ANY value in `waiting_on`, counted in SQL with the column trimmed.
      // The server has served it since `01580d8fc` and nothing read it.
      //
      // ⛔ **IT IS A FACT AND NOT A CONTROL** (`filter: null` in
      // `newConnectsTiles` below, so `NewConnectTiles` draws the static `<div>`).
      // `f.state` has no *waiting* value — *waiting* is derived from a
      // separate COLUMN, which is `OQ-371`'s own point — so wiring this to
      // `f.state=on_hold` would be a plausible-looking lie: hold and waiting
      // are two independent axes and `CON-26-0126` is both at once.
      id: "waiting-anyone",
      label: t("customers.newConnects.kpi.waitingAnyone", {
        defaultValue: "Waiting on someone",
      }),
      value: kpis?.waiting_on_anyone ?? 0,
      detail: t("customers.newConnects.kpi.waitingAnyoneDetail", {
        defaultValue: "anyone, not only the inspector",
      }),
    },
    {
      // ⚠ **THE OLDER TILE HAS NOT LEFT, AND THAT IS DELIBERATE.** B18 §5.4.1
      // draws *WAITING ON INSPECTION*, which is the one literal; the tile
      // above is every third party. They are different questions — a build
      // waiting on *"site inspection"* is invisible to this one and counted
      // by that one — and taking a live, served figure off the page to swap a
      // caption is hard-won law 2 running backwards. **That the strip now
      // holds seven tiles where the drawing draws five is `DEF-CUS-7805`**,
      // filed rather than settled here.
      id: "waiting-inspection",
      label: t("customers.newConnects.kpi.waitingInspection", {
        defaultValue: "Waiting on inspection",
      }),
      value: kpis?.waiting_on_inspection ?? 0,
      detail: t("customers.newConnects.kpi.waitingInspectionDetail", {
        defaultValue: "nothing can pass until they attend",
      }),
    },
    {
      id: "partly-activated",
      // CR-032 — `Partly activated`, never `Partly energised`. B18 draws the
      // old word and is stamped; the product ships the ruled one.
      label: t("customers.newConnects.kpi.partlyActivated", {
        defaultValue: "Partly activated",
      }),
      value: kpis?.partly_activated ?? 0,
      detail: t("customers.newConnects.kpi.partlyActivatedDetail", {
        defaultValue: "some services billing, some not",
      }),
    },
    {
      id: "units-awaiting",
      label: t("customers.newConnects.kpi.unitsAwaiting", {
        defaultValue: "Units awaiting activation",
      }),
      value: kpis?.units_awaiting_activation ?? 0,
      detail: t("customers.newConnects.kpi.unitsAwaitingDetail", {
        defaultValue: "across the {{count}} open builds",
        count: kpis?.open ?? 0,
      }),
    },
    {
      id: "oldest",
      label: t("customers.newConnects.kpi.oldest", { defaultValue: "Oldest" }),
      value:
        oldest === null
          ? t("customers.newConnects.kpi.oldestNone", { defaultValue: "None open" })
          : t("customers.newConnects.list.ageDays", {
              defaultValue: "{{days}} days",
              days: oldest.days,
            }),
      detail:
        oldest === null
          ? undefined
          : oldest.waiting_on === null || oldest.waiting_on === ""
            ? oldest.connection_no
            : `${oldest.connection_no} · ${oldest.waiting_on}`,
    },
    {
      // ══════════════════════════════════════════════════════════════════
      // ⛔ `Owed on builds` — A STATED ABSENCE, AND NEVER A FIGURE THIS
      //    SCREEN WORKED OUT (`DEF-CUS-7619`, OPEN · `DEF-CUS-7804`)
      // ══════════════════════════════════════════════════════════════════
      // The drawing puts `$4,210 · Owed on open builds` here and the server
      // serves `owed_on_open_builds: null` beside a named reason, because
      // billing publishes no batched invoice position and B1 puts that read
      // in billing's own module. Until it lands there is no figure at all.
      //
      // ⚠ **`$0.00` IS THE ONE THING THIS TILE MAY NOT SAY** — it reads as
      // *every build is paid for* (`DEF-127`), on the tile a supervisor uses
      // to decide whether to chase anybody. **AND THE ROWS ARE NOT ADDED UP
      // HERE:** no row carries a `due` key, and summing 25 rows of a 40,000-
      // build tenant would describe a PAGE, not the debt — besides being a
      // second rounding path on a receivable (hard rule 2).
      //
      // ⚠ **THE SERVER'S OWN `detail` IS NOT PRINTED.** It is two sentences
      // of engineering, and B14 rule 33 caps a FACT at six words and puts
      // RATIONALE at ZERO on screen. The absence is keyed off the
      // `code` — `billing_publishes_no_batched_invoice_position` — and the
      // words a clerk reads are three: *No total yet*. The code and its
      // tracking row ride as `data-` attributes, never as copy (`DEF-332`).
      //
      // ⚠ **THE LABEL IS THREE WORDS WHERE THE DRAWING WRITES FOUR.** B14
      // rule 33 caps a LABEL at three, rule 44 gives the UI standard the win
      // over the drawing on how a screen is BUILT, and rule 37 makes a drawn
      // string an illustration. Stamped as a divergence rather than taken
      // silently.
      //
      // ⚠ **THE BRANCH IS LIVE RATHER THAN DEAD.** When `DEF-CUS-7619`
      // closes and a `display` arrives, this tile prints the SERVER's 2-dp
      // string and nothing here changes — which is why the figure path is
      // written and asserted now rather than left for the day it is needed.
      id: "owed",
      label: t("customers.newConnects.kpi.owed", { defaultValue: "Owed on builds" }),
      value:
        owed === null ? (
          <span
            role="note"
            className="text-base text-neutral-700"
            data-owed-absent=""
            data-owed-code={kpis?.owed_on_open_builds_unavailable?.code}
            data-tracks={kpis?.owed_on_open_builds_unavailable?.tracks}
          >
            {t("customers.newConnects.kpi.owedNone", { defaultValue: "No total yet" })}
          </span>
        ) : (
          // The SERVER's 2-dp string, printed. No symbol: `_pair` serves no
          // `CHAR(3)` currency (`DEF-CUS-7806`) and one typed here would be
          // this screen asserting a currency for a tenant that may not be in
          // it (hard rule 2).
          <span className="tabular-nums" data-owed-display={owed}>
            {owed}
          </span>
        ),
      detail: undefined,
    },
  ];
}

/**
 * ══════════════════════════════════════════════════════════════════════════
 * **THE FIVE TILES, AND WHICH OF THEM SET THE FILTER — `CR-150-BRC09`**
 * ══════════════════════════════════════════════════════════════════════════
 *
 * The drawing's README: *"The tiles filter. Clicking one narrows the table,
 * which is what four counts sitting above a table should do."*
 *
 * ⚠ **THE TILE SETS `state.filters`; IT DOES NOT FILTER AROUND IT.** Pressing
 * one writes through the same `onStateChange` the `+ Filter ▾` bar writes
 * through, so the bar shows `Show: Open ×` the moment a tile is pressed and
 * the two controls cannot disagree about what the table is showing. The two
 * halves of that are `pressTile` (what a press writes) and `tileIsApplied`
 * (what the tile reads back), both in `newConnectListViews.tsx`, and both
 * exported so a test can make the round trip without a DOM.
 *
 * ⚠ **TWO OF THE SEVEN CARRY A FILTER AND FIVE DO NOT (BR-SHL-010).** This
 * line read *"two of the five … and three do not"* until 2026-09-29; the two
 * that carry one are unchanged and the drawing's two new tiles are both
 * facts. The reasoning is written out where the component lives, in
 * `newConnectListViews.tsx` §1; in one line each: both *waiting* tiles are
 * derived from a different COLUMN and are `OQ-371`'s open question, *units
 * awaiting* counts units where every control here selects builds, *oldest*
 * names one build rather than a set, and *owed* has no served figure at all
 * (§4 above, `DEF-CUS-7619`).
 */
export function newConnectsTiles(
  payload: ConnectionList | undefined,
  t: (key: string, params?: Record<string, unknown>) => string,
): BuildTile[] {
  // The server's own filter value for the KPI tile's set. `connection_reads`
  // mints it as `SCOPE_OPEN` and serves it in `states`; it is read off the
  // shared constant rather than typed twice.
  const filters: Record<string, string | null> = {
    open: "open",
    // ⛔ `DEF-CUS-7804` — the drawn *Waiting on someone* tile is a FACT.
    // `GET /connections` declares ONE filter dimension, `state`, and *waiting*
    // is not one of its values: it is derived from the `waiting_on` COLUMN,
    // which is exactly what `OQ-371` is open about. `NewConnectTiles` draws a
    // `null` filter as the static tile the kit already draws, so nothing looks
    // pressable and then refuses (law 2's mirror).
    "waiting-anyone": null,
    "waiting-inspection": null,
    "partly-activated": "partly_activated",
    "units-awaiting": null,
    oldest: null,
    // ⛔ `DEF-CUS-7619` — there is no figure behind it, so there is certainly
    // nothing to filter by.
    owed: null,
  };
  return newConnectsKpis(payload, t).map((tile) => ({
    tile,
    filter: filters[tile.id] ?? null,
  }));
}

export interface NewConnectsTabProps extends RegionalProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

export function NewConnectsTab(props: NewConnectsTabProps) {
  // ⚠ **THE DISCARD DIALOG'S STATE LIVES HERE AND NOT IN THE ROW
  // (`DEF-CUS-6011`).** `DataTable` rebuilds `columnDefs` on every render, so
  // `flexRender` hands React a new component type each time and the whole cell
  // subtree is unmounted and remounted — **a `useState` inside a cell is
  // destroyed by the very re-render that setting it caused.** The first draft
  // kept `confirming` in `ParkedDraftActions`, and the dialog never opened, in
  // the browser or under vitest. `DEF-CUS-5994`.
  const [discarding, setDiscarding] = useState<ParkedDiscardTarget | null>(null);
  // `CR-150-BRC09` — the ticked rows and the act a clerk has asked for. Both
  // live HERE for `discarding`'s reason (`DEF-CUS-6011`): a `useState` inside
  // a `DataTable` cell is destroyed by the render its own click causes.
  const [picked, setPicked] = useState<readonly string[]>([]);
  const [acting, setActing] = useState<BuildActTarget | null>(null);
  const { t } = useTranslation();
  const translate = (key: string, params?: Record<string, unknown>): string => t(key, params);
  const client = props.client ?? api;
  const { timeZone, dateFormat } = useRegional(props);
  const navigate = useNavigate();
  const tenantPath = useTenantPath();

  const config = useMemo(
    () =>
      newConnectsTableConfig(translate, {
        // ── `CR-150-BRC09` · THE TICK BOX ────────────────────────────────
        // A real `<input type="checkbox">` with a real accessible name — the
        // `AssetRegistryPage` shape, because `DataTable` has no selection
        // capability of its own and a second answer to *what is a table's
        // selection* is the last thing this kit needs.
        //
        // ⚠ **IT IS NAMED BY THE BUILD NUMBER AND NEVER BY THE ROW ID.** Rule
        // 31: no database id is a visible value, and an accessible name is a
        // value a person reads.
        select: (row) => (
          <input
            type="checkbox"
            aria-label={translate("customers.newConnects.action.pick", {
              defaultValue: "Pick {{build}}",
              build: row.connection_no,
            })}
            checked={picked.includes(row.id)}
            onChange={(event) =>
              setPicked(
                event.target.checked
                  ? [...picked, row.id]
                  : picked.filter((id) => id !== row.id),
              )
            }
          />
        ),
        // The row's first door. A build with no home — impossible today,
        // `premises_id` is NOT NULL — renders the number as text rather than a
        // link onto nothing, which is the same refusal the eye already makes
        // and for the same reason (law 2: a link that silently goes nowhere
        // passes every test in this repo).
        // ⚠ **A DRAFT'S DOOR IS ITS OWN WIZARD, AND IT WAS THE PROPERTY PAGE
        // UNTIL TODAY (`DEF-CUS-6132`, `BR-SHL-048 (d)`).** PO ruling
        // 2026-09-21: *"you can update the existing build"* — which requires a
        // clerk to be able to REACH it. `buildHomePath` answers where a
        // FINISHED build lives and was right for every row that existed before
        // `DEF-CUS-6109` made approving an application raise a DRAFT one. On
        // the acceptance walk that draft's number led to the property page with
        // *Edit details* greyed out, and where the address had not resolved the
        // row carried no link at all; the lane that found it could only carry
        // on by typing the address in by hand. **ONE function decides, for both
        // doors on this row** (`rowDoor`), so the number and the eye cannot
        // disagree.
        //
        // ⚠ **AND THE `Draft` BADGE SITS UNDER THE NUMBER FROM 2026-09-28.**
        // The drawing draws it there, on the row whose state reads
        // `Parked · step 3`, so a clerk scanning the first column can see
        // which rows are unfinished without reading across to STATE.
        connection: (row) => {
          const door = rowDoor(row);
          const draft = isDraftBuild(row.state) || (row.park_id ?? "") !== "";
          return (
            <span className="flex flex-col items-start gap-1">
              {door === null ? (
                <span className="tabular-nums">{row.connection_no}</span>
              ) : (
                <Link className={`${LINK} tabular-nums`} to={tenantPath(door)}>
                  {row.connection_no}
                </Link>
              )}
              {draft && <ParkedBadge parked={false} t={translate} />}
            </span>
          );
        },
        // The drawing stacks the property's NAME over its address. The
        // three-way fallback below it is unchanged (`DEF-CUS-6109`): no
        // premises at all is one em dash, and a premises with no name or no
        // address renders the half it has.
        premise: (row) => {
          if (row.premises === null) {
            return <Dash />;
          }
          const name = row.premises.name ?? "";
          const address = row.premises.address ?? "";
          if (name === "" && address === "") {
            return <span className="tabular-nums">{row.premises.premise_no}</span>;
          }
          return (
            <span className="flex flex-col">
              <span>{name === "" ? address : name}</span>
              {name !== "" && address !== "" && (
                <span className="text-sm text-neutral-700">{address}</span>
              )}
            </span>
          );
        },
        // `DEF-CUS-7804` — the drawn CUSTOMER column and the chooser's two
        // composite cells. They are COMPONENTS above rather than blocks
        // inline here (B14 rule 43), and `lastEvent` is handed down because
        // it needs the tenant's own clock, which only this component holds.
        customer: (row) => <CustomerCell row={row} t={translate} />,
        charged: (row) => <ChargedCell row={row} t={translate} />,
        lastEvent: (row) => (
          <LastEventCell
            row={row}
            t={translate}
            timeZone={timeZone}
            dateFormat={dateFormat}
          />
        ),
        services: (row) => <ServicesCell services={row.services} t={translate} />,
        orders: (row) => <OrdersCell row={row} t={translate} />,
        target: (row) =>
          row.target_activation === null ? (
            // ⚠ A BUILD WITH NO TARGET SORTS LAST AND RENDERS A DASH. The
            // server states the same thing about the ordering: *"a missing date
            // is not the most urgent thing on the list"*.
            <Dash />
          ) : (
            <DateCell value={row.target_activation} timeZone={timeZone} dateFormat={dateFormat} />
          ),
        state: (row) =>
          // ⚠ **REQUIREMENT 1 OF `CR-035` AMENDMENT 1, MET ON THE ROW INSTEAD
          // OF ABOVE THE TABLE (`DEF-CUS-5994`).** *"A clerk cannot mistake a
          // draft for a job that happened"* was the pinned panel's dashed
          // border and its own block; the panel is gone and the requirement is
          // not. **The two controls ride in this cell rather than in a new
          // ACTIONS column**, because this table's columns are the drawing's
          // and a column nobody drew is not invented here — B14 rule 38 gives
          // the UI rules the FORM and leaves what a screen CONTAINS to the
          // blueprint. The state cell is where a row already declares what
          // kind of thing it is, which is exactly what a draft needs to say.
          (row.park_id ?? "") !== "" ? (
            <span className="flex flex-col items-start gap-1" data-connect-draft={row.park_id}>
              <ParkedBadge parked={(row.waiting_on ?? "") !== ""} t={translate} />
              <ParkedWhyCell row={row} timeZone={timeZone} dateFormat={dateFormat} />
              <ParkedDraftActions
                flow="new_connect"
                onDiscard={setDiscarding}
                parkId={String(row.park_id)}
                subjectLabel={row.address_typed ?? ""}
              />
            </span>
          ) : (
            /* The COLUMN reads through the same helper the filter does
               (`DEF-CUS-6098`). It was the second inline `?? row.state` in this
               file, and a state that reaches the list without reaching the
               filter would have printed its code here alone.

               ⚠ **AND A BUILD SOMEBODY IS WAITING ON SAYS SO HERE FROM
               2026-09-28 (`CR-150-BRC09`).** The drawing folds the two facts
               into one cell — `Waiting · fire marshal` — which is why the
               Waiting-on COLUMN moved behind the chooser. The tone is warning
               because a build nobody can move is the one to look at, and it is
               the same tone `on_hold` already carried.

               ⚠ **IT SAYS `Waiting` AND NOT THE STORED STATE, AND THAT DECIDES
               NOTHING ABOUT `OQ-371`.** The open question is which EXCLUSIVE
               tab holds a build that is `partly_activated` AND waiting; this
               cell shows BOTH facts on one row and ranks neither, which is
               precisely the thing a segment cannot do. */
            (row.waiting_on ?? "") !== "" ? (
              <StatusPill tone="warning">
                {translate("customers.newConnects.state.waitingOn", {
                  defaultValue: "Waiting · {{who}}",
                  who: row.waiting_on,
                })}
              </StatusPill>
            ) : (
              <StatusPill tone={connectionStateTone(row.state)}>
                {connectionStateLabel(row.state, translate)}
              </StatusPill>
            )
          ),
        // DEF-730 — B14 rule 15 / G37: an ICON with an accessible NAME, and a
        // LINK rather than a button, so middle-click and "open in new tab"
        // still work on a build a clerk wants beside the list.
        // ⚠ CR-070 WAVE O — THE EYE GOES TO THE BUILD'S HOME. The screen it
        // used to open is deleted (PO: *"you cannot have two differnt screen -
        // this is an integration problem"*), and the build's progress, units,
        // work orders and charges are on the premises and on the account now.
        // The row's own text is unchanged.
        //
        // A build with no home — impossible today, `premises_id` is NOT NULL —
        // gets the action DISABLED WITH ITS REASON rather than a link onto
        // nothing: a link that silently goes nowhere passes every test in this
        // repo (law 6), which is precisely what wave O exists to stop.
        actions: (row) => {
          // The SAME `rowDoor` the number cell reads — B14 rule 15's row action
          // and the identity cell are two doors onto one destination, and a
          // draft sends both to its wizard (`DEF-CUS-6132`).
          const door = rowDoor(row);
          return (
            <RowActions>
              {door === null ? (
                <RowAction
                  label={translate("customers.newConnects.action.open", {
                    defaultValue: "Open this connection",
                  })}
                  icon={<EyeIcon />}
                  reason={translate("customers.newConnects.action.openBlocked", {
                    defaultValue: "This build has no home yet.",
                  })}
                  onClick={() => undefined}
                />
              ) : (
                <RowActionLink
                  label={translate("customers.newConnects.action.open", {
                    defaultValue: "Open this connection",
                  })}
                  icon={<EyeIcon />}
                  to={tenantPath(door)}
                />
              )}
              {/* `CR-150-BRC09` — Hold · Waiting on · Cancel build, each
                  refused or allowed by Work's own `actBlockedReason` rather
                  than by a rule restated here. A parked wizard is not a build
                  and has no act to perform on it, so it carries no menu. */}
              {(row.park_id ?? "") === "" && (
                <BuildRowMenu row={row} t={translate} onAct={setActing} />
              )}
            </RowActions>
          );
        },
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t, timeZone, dateFormat, picked],
  );

  // §1 — the table state lives in the ADDRESS, under this tab's own namespace,
  // so a filtered list survives a reload and can be sent to somebody
  // (`DEF-CUS-6099`). The prefix is what keeps `DEF-664` closed.
  const [searchParams, setSearchParams] = useSearchParams();
  const state = parseTableParams(searchParams, config, NEW_CONNECTS_PARAM_PREFIX);
  function setState(next: TableRequestState): void {
    // ⚠ **EVERY PARAM THIS TAB DOES NOT OWN SURVIVES**, `?tab=` above all —
    // the page reads that one to decide which tab is on screen, and dropping
    // it would throw the clerk back to Accounts on their first filter press.
    // Built by REMOVING this tab's own keys and setting them again, rather
    // than by starting from an empty `URLSearchParams`: a filter cleared has
    // to leave the address, and only a removal does that.
    const params = new URLSearchParams(searchParams);
    for (const key of [...params.keys()]) {
      if (key.startsWith(NEW_CONNECTS_PARAM_PREFIX)) {
        params.delete(key);
      }
    }
    for (const [key, value] of serializeTableParams(next, config, NEW_CONNECTS_PARAM_PREFIX)) {
      params.set(key, value);
    }
    // `replace`, like the page's own writer: a filter press is not a place a
    // clerk means to go Back to, and eight of them would bury the screen they
    // arrived from.
    setSearchParams(params, { replace: true });
  }

  const listQuery = useQuery({
    // ══════════════════════════════════════════════════════════════════
    // ⚠ **THE FILTER BAR DISAPPEARED ON EVERY PRESS UNTIL 2026-09-28, AND
    //    THE TILE IS WHAT MADE IT VISIBLE (`CR-150-BRC09`)**
    // ══════════════════════════════════════════════════════════════════
    // Every dimension of `state` is IN the query key — page, sort, filter —
    // which is right and is what stops a filtered request being answered from
    // the unfiltered cache. The cost is that changing any of them is a NEW
    // cache entry, so `listQuery.data` goes `undefined` for the length of the
    // round trip. **This screen builds its FILTER OPTIONS out of that
    // payload** (`listQuery.data?.states`, BR-SHL-010 — the screen never
    // invents an option), and `offerableFilters` drops a group with no
    // options, and `FilterBar` returns `null` when nothing is declared. So:
    // press a filter, and the toolbar's whole chip row — including the chip
    // you just made — **vanishes until the response lands**, then reappears.
    //
    // ⚠ **IT WAS FOUND BY A DOM TEST AND BY NOTHING ELSE**, which is the part
    // worth recording. Every static case renders one settled payload and
    // could not see an in-flight state at all; `tsc`, eslint and every gate
    // pass over it. It was already true of the `+ Filter ▾` panel and of the
    // pager, and the tiles only made it easy to hit.
    //
    // `placeholderData` keeps the PREVIOUS answer on screen while the next
    // one is fetched — the table, the tiles and the filter vocabulary all
    // hold still, and `isPending` stays false so nothing flashes a skeleton.
    // It is the same line `AssetDetailPage` and `RoutesCyclesPage` already
    // carry for paged lists, for the same reason.
    placeholderData: (previous) => previous,
    queryKey: connectionsQueryKey(state),
    queryFn: () =>
      listConnections(
        {
          q: state.q,
          page: state.page,
          per: state.per,
          filters: state.filters,
          // `BR-CUS-1046` — the clerk's chosen column reaches the `ORDER BY`.
          sort: state.sort,
          dir: state.dir,
        },
        client,
      ),
  });

  const rows = rowsOf<ConnectionRow>(listQuery.data);

  return (
    <div data-embedded="" data-screen={NEW_CONNECTS_TABLE_SCREEN}>
      {/* `DEF-CUS-5994` — the parked draft's DISCARD confirmation, mounted ONCE
          and ABOVE the table. It is here rather than in the row because a
          `DataTable` cell is unmounted and remounted on every render
          (`DEF-CUS-6011`), so state set by a click inside one does not survive
          the render that click causes. It draws nothing until a clerk asks. */}
      <ParkedDiscardDialog
        flow="new_connect"
        target={discarding}
        onClose={() => setDiscarding(null)}
        client={client}
      />
      {/* ── THE TAB'S ONE SENTENCE ────────────────────────────────────────
          PO, on this list: *"you also dont have filter and toolkit -
          elements search, filter, colum selecot, description etc"*. This is
          the description, and it is ONE sentence because B14 rule 32 gives a
          section one (*"too much content - desctiption is too much for clark
          to read"*, said four times in twenty minutes).

          WHAT IT SAYS, AND WHY THAT AND NOT THE BLUEPRINT'S OWN PARAGRAPHS.
          p093 states this list's whole brief in one line — *"either raised
          directly or created by approving a request — and the list says
          which"* — and that is a FACT about what the register holds, so it
          caps at six words (rule 33) and it is six. p094 also prints two grey
          paragraphs under its pager, and those are RATIONALE: *"a list that
          answered only activated: yes or no would call that whole building
          unfinished or finished, and both would be wrong"* argues for a design
          rather than telling a clerk anything. Rule 33 puts rationale at ZERO
          words on screen and says it belongs in the code and the register —
          so it is here, and the way the drawing's argument reaches the product
          is the PARTLY ACTIVATED state and the FROM REQUEST column, not prose.
          That divergence from the drawing is rule 41's named case and is
          REPORTED rather than taken silently.

          Capped at rule 18's measure — the `--desc-measure` token behind
          `max-w-measure`, never `max-w-prose` (DEF-900). */}
      <p className="mb-3 max-w-measure text-sm text-neutral-700">
        {t("customers.newConnects.list.description", {
          defaultValue: "Raised here, or from a request.",
        })}
      </p>

      {/* `CR-150-BRC09` — the five tiles, and two of them SET the filter the
          bar below then shows as applied. They are pressed through the SAME
          `setState` the `FilterBar` writes through, which is the whole of the
          requirement: a tile that filtered around it would leave the bar
          saying *no filters* over a narrowed table. */}
      <NewConnectTiles
        tiles={newConnectsTiles(listQuery.data, translate)}
        state={state}
        onStateChange={setState}
        t={translate}
        // `BR-SHL-012` — the SHARED skeleton, the one `KPIStrip` drew here
        // before the tiles became controls. Without it the first paint shows
        // five `0`s, which is a figure where there is no answer yet.
        loading={listQuery.isPending}
      />

      {/* The bulk bar draws only when something is ticked — `SelectionToolbar`'s
          own rule: *"no second bar, no layout jump"*. The three acts are the
          row menu's three, from one list. */}
      {picked.length > 0 && (
        <BuildBulkBar
          rows={rows.filter((row) => picked.includes(row.id))}
          t={translate}
          onAct={setActing}
          onClear={() => setPicked([])}
        />
      )}

      {/* One dialog for both doors, mounted ABOVE the table for the reason the
          discard dialog is (`DEF-CUS-6011`). It draws nothing until a clerk
          picks an act. */}
      <BuildActDialog
        target={acting}
        client={client}
        onClose={() => setActing(null)}
        onDone={() => {
          setActing(null);
          setPicked([]);
        }}
      />

      <DataTable<ConnectionRow>
        config={config}
        // ── CR-045 wave G · `DEF-1702` — THE `+ Filter ▾` PANEL, WHERE THE
        //    INERT SEGMENT STRIP USED TO BE ────────────────────────────────
        //
        // The strip and the reasoning for removing it are recorded where the
        // component stood, above. In one line: five tabs, four permanently
        // `supported: false`, the fifth permanently active, `onSelect={() =>
        // undefined}` — a control that occupied the filter slot and narrowed
        // nothing, which is how this screen was scored as *having* a filter
        // twice while having none.
        //
        // The groups are built from the RESPONSE, so the options are the
        // server's `OPEN_STATES` and never a copy of them (BR-SHL-010);
        // `offerableFilters` drops the group before the first response rather
        // than drawing a legend over nothing (`DEF-782`).
        filterBarSlot={
          <FilterBar
            filters={offerableFilters(connectionFilterGroups(listQuery.data?.states, translate))}
            state={state}
            onStateChange={setState}
          />
        }
        state={state}
        onStateChange={setState}
        rows={rows}
        totalRows={totalOf(listQuery.data)}
        loading={listQuery.isPending}
        error={
          listQuery.isError
            ? {
                reason: t("customers.newConnects.list.loadFailed", {
                  defaultValue: "The new connects could not be loaded.",
                }),
                onRetry: () => void listQuery.refetch(),
              }
            : null
        }
        empty={{
          title: t("customers.newConnects.list.emptyTitle", {
            defaultValue: "No new connects yet",
          }),
          helper: t("customers.newConnects.list.emptyHelper", {
            defaultValue:
              "A new connect is raised when a property needs service brought to it for the first time.",
          }),
          ctaLabel: t("customers.newConnects.action.new", { defaultValue: "+ New connect" }),
          // ⚠ **WAS DISABLED, AND IS LIVE FROM 2026-08-26 (DEF-730).** This CTA
          // carried `ctaReason: "The new-connect wizard is not built yet, so
          // this cannot start here."` — BR-SHL-025 / law 2, correctly, while
          // `NCT-01`'s wizard had no route. `NewConnectWizard` shipped at
          // `/connections/new` the NIGHT the tab was written, and the sentence
          // became a lie the moment the route landed: the product refused an
          // act it could perform and told the user a falsehood about itself.
          // A disabled control with a stale reason is worse than a missing one
          // — a missing button reads as unfinished, a disabled one reads as
          // decided. Anything a clerk still cannot do is refused ON the wizard,
          // carrying its own reason, which is where it belongs.
          //
          // ⛔ The catalogue key `customers.newConnects.action.newBlocked` is
          // now unused and its English is FALSE in all eleven locales. This
          // lane may not edit `src/i18n/locales/`; the deletion is REPORTED.
          onCta: () => navigate(tenantPath(NEW_CONNECT_ROUTE)),
        }}
      />

      {/* B18 §5.4.2's own footnote, and it is a true statement about the SORT:
          the server orders by target date ascending and accepts no other
          ordering, which is why no column above is sortable. */}
      <p className="mt-2 text-sm text-neutral-700">
        {t("customers.newConnects.list.sortFootnote")}
      </p>
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-030 W6 task 6.12 (S86 `NCT-01`, frontend half) · B18 §5.4.1 ·
//         §5.4.2 · §5.4.8 · §5.4.9 · `apps/metering/connection_reads.py` ·
//         `GET /connections` · OQ-371 (OPEN) · CR-032 · DEF-664 (the embedded
//         rule) · hard-won law 8 (no story owns S86)
// generated: 2026-08-25 by lane F-TABS (the frontend half of three worklists)
//            · AMENDED 2026-08-26 by lane TABCTA (DEF-730: the `+ New connect`
//            CTA goes LIVE to `/connections/new` and the row grows its eye link
//            to `/connections/:id`; the two E3 exceptions that withheld them are
//            SUPERSEDED below, and the `not built yet` sentence is gone)
// checklist: A=n/a(no backend half in this lane) B✔ C✔ D✔ E✔ F✔ G✔
//         H=deferred(PO 2026-08-09)
// exceptions: E2 **the exception that stood here is SUPERSEDED BY CR-045 WAVE G
//         (2026-08-27, `DEF-1702`) and is kept rather than deleted (hard-won law
//         1).** It read: *"E3 four of five segments are DISABLED WITH THEIR
//         REASON — OQ-371 is OPEN, the server serves `all` only, and the screen
//         never calls the route to discover the refusal"*. True, and the control
//         could not be operated — the fifth was the one already active. **The
//         strip is DELETED, and `WorklistSegments` with it** (this file owned the
//         component; G40's baseline of 1 holds). **OQ-371 IS STILL OPEN and the
//         last clause still holds: the screen never asks for a segment**, and a
//         case asserts it · E3 **the toolbar now carries a REAL `+ Filter ▾`** —
//         `f.state` over `OPEN_STATES`, applied by the server before paging. It
//         is not the segments in another shape: `Waiting` is derived from
//         `waiting_on`, a different column, which is OQ-371's own point · E3 no `+ New connect`
//         primary and no `Export`: no wizard route exists and `POST /exports`
//         registers no `connections` resource (BR-SHL-010); the empty-state CTA
//         is drawn disabled with that reason · E3 no row action — `NCT-02` has
//         no route, so a view icon would link onto nothing (law 2) · E3 no
//         sortable column: the server accepts no `sort` · E3 `applicant` and
//         `request_no` are DECLARED and OFF by default — they are search legs
//         B18 does not draw as columns · E3 the page/search choice does not
//         survive a reload (DEF-664's embedded trade) and there is no
//         standalone screen to go to · E3 the STATE tone mapping is the
//         SCREEN's; B18 draws no tone for that column · E3 no story owns S86
//         (law 8) — OWED
//         · **[TABCTA 2026-08-26 · DEF-730]** E2 **the two E3 rows above that
//         begin "no `+ New connect` primary" and "no row action" ARE
//         SUPERSEDED, and both were right when written.** `NewConnectWizard`
//         landed at `/connections/new` and `ConnectionDetailPage` at
//         `/connections/:connectionId` the same night this tab was built, so
//         both refusals became false within hours and the CTA went on telling
//         the user a falsehood about the product for a day. The CTA now
//         navigates and the ACTIONS column carries the eye link; `Export` is
//         still unrendered, which is BR-SHL-010 and unchanged · E3 **the
//         `+ New connect` PRIMARY is not this file's** — it is
//         `AccountsListPage`'s ONE header slot, relabelled per active tab, so
//         the page keeps exactly one primary (B14 rule 4 / BR-SHL-044) · E3
//         **`customers.newConnects.col.actions` IS NOT IN ANY CATALOGUE.** It
//         renders "Actions" through an explicit `defaultValue` and is handed to
//         the locale lane in `scratchpad/newkeys-TABCTA.json`; G27 counts it,
//         and it counts it only because the `locales/*.json` spelling that used
//         to blind the gate in this file was reworded in the same commit · E3
//         **`customers.newConnects.action.newBlocked` IS NOW DEAD AND ITS
//         ENGLISH IS FALSE IN ELEVEN CATALOGUES.** This lane may not edit
//         `src/i18n/locales/`; the DELETION is handed over in the same file.
//         · **[LIST 2026-09-28 · CR-150-BRC09]** E3 **THREE DRAWN COLUMNS AND
//         TWO DRAWN TILES ARE NOT BUILT, AND THE REASON IS THE SERVER RATHER
//         THAN THE LANE.** `CUSTOMER`, `DUE` and `AGING` are drawn on
//         `00-list.png` and `GET /connections` serves none of the three —
//         `connection_reads._row` has no customer block, no money and no
//         `age_days` on a build row. Each is LEFT OUT rather than drawn over a
//         dash on every row forever (BR-SHL-010), and §4 above names the
//         field each one needs so the backend half is one entry apiece.
//         ⚠ **NONE OF THE MONEY IS COMPUTED HERE** — hard rule 2 rounds once,
//         server-side, and `DEF-127` records what a fabricated `$0.00` costs.
//         The AGING THRESHOLD is server-side too, for `AgeCell`'s stated
//         reason: two thresholds is how a list and a KPI drift apart ·
//         E3 **THE FOUR CHOOSER COLUMNS THE README NAMES — Charged, Mode,
//         Scope, Raised by, Last event — ARE NOT DECLARED**, for the same
//         reason: no served field. `Waiting on`, `From request` and
//         `Applicant` are what is behind the chooser today · E3 **THREE OF
//         THE FIVE TILES ARE FACTS AND NOT FILTERS.** `GET /connections`
//         declares exactly one dimension (`state`); *waiting* is derived from
//         a different COLUMN and is `OQ-371`'s open question, *units
//         awaiting* counts units where every control here selects builds, and
//         *owed* has no figure. A tile that cannot filter is drawn as a fact,
//         never as a control that does nothing (law 2's mirror) · E3 **THE
//         FIFTH TILE IS STILL `Oldest` AND THE DRAWING SAYS `Owed on open
//         builds`** — the swap needs `kpis.owed_on_open_builds`, and the
//         second tile needs a count of builds with ANY `waiting_on` rather
//         than only `waiting_on_inspection`. REPORTED · E3 ⏳ **`rowDoor` IS
//         UNCHANGED AND THE DRAWING ASKS FOR A NEW DESTINATION.** A finished
//         build's number and eye should open `/{tenant}/connections/{id}`;
//         that address still mounts `BuildRedirect` on this branch, so
//         pointing at it today would be a live control onto a doorway. The
//         HOLD CARRIES ITS OWN EXPIRY TEST (law 2): the case named
//         *task 15 HOLD* asserts the route still redirects and goes RED the
//         day the detail page is mounted there, naming the one line to change
//         · E3 **`From request` IS OFF BY DEFAULT AGAIN**, reversing the
//         p093/p094 decision on the later drawing's authority (B14 rule 41);
//         the two cases that asserted the old default are rewritten to assert
//         the new one and say so · E3 **`select` IS A NEW COLUMN KEY, SO A
//         CLERK WITH A SAVED COLUMN SET ON S86 MUST PRESS RESET ONCE TO SEE
//         THE TICK BOXES.** `columnsFromPreference` keeps only stored keys and
//         `DataTable` force-shows the IDENTITY column alone. Stated rather
//         than worked around; both alternatives were worse · E3 **FOURTEEN
//         CATALOGUE KEYS ARE NEW AND EACH RENDERS ITS ENGLISH `defaultValue`
//         UNTIL THE TEXT LANE FANS IT IN** — counted against `en.json` rather
//         than from memory, which is how this line first said *ten*:
//         `customers.newConnects.col.build` · `.col.select` · `.action.pick` ·
//         `.state.waitingOn` · `.act.holdTitle` · `.act.holdReason` ·
//         `.act.waitingTitle` · `.act.waitingWho` · `.act.cancelTitle` ·
//         `.act.cancelReason` · `.bulk.label` · `.bulk.selected` ·
//         `.bulk.eligible` · `.bulk.clear`. This lane may not edit
//         `src/i18n/locales/` · E3 **THE DRAWING'S STATE WORD IS
//         `Active` AND THE PRODUCT SHIPS `Activated`** — `CR-032` is a PO
//         ruling (*"instead of energise can we use activated"*) and a drawing
//         does not supersede one; B14 rule 41 says a drawing that contradicts
//         a signed rule is the thing that reaches the PO. REPORTED, not
//         changed · E4 **NO PIXEL IS ASSERTED ANYWHERE.** The drawn spacing,
//         the accent ring and the two-line cells are hard-won law 6's
//         territory — a person, in a browser, beside the drawing — and this
//         screen has NOT been walked in one by this lane
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
