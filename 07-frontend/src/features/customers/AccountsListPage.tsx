// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-001 (S17 accounts table + header roll-up) ·
//           US-CUS-002 (S17 search, the AC-8 filters and the wizard entry points)
//           Screens: S17 (entered from the AppShell sidebar → Accounts)
// Rules:    BR-CUS-015 (the S17 list contract: the prototype's seven columns,
//           one service tag per ACTIVE service agreement, Balance = the cached
//           `accounts.balance` with the ledger still the source of truth) ·
//           BR-CUS-016 (stored status comes from the account-status lookup;
//           Current / 30d past / 60+ past are DERIVED from open-invoice
//           due-date math and are NEVER stored) · BR-CUS-017 (an account
//           belongs to exactly one unit) · BR-CUS-029 (the account plan
//           snapshot has no DDL — so there is no Plan column and no Plan
//           filter) · BR-CUS-053 (the capability row: search account # /
//           customer name / service address / meter #; filters status ·
//           category · autopay · balance > 0; default sort customer name
//           A→Z) · BR-CUS-054 (a name search resolves the CUSTOMER entity) ·
//           BR-CUS-055 (the five seeded, tenant-extensible statuses) ·
//           BR-CUS-059 (autopay is CAPTURE-ONLY in v1 — nothing collects) ·
//           BR-SHL-010/011/012 (the ONE table framework, its URL grammar, the
//           A18 states) · BR-SHL-023 (one money/number formatting path) ·
//           BR-SHL-025 (a forbidden control renders disabled WITH its reason) ·
//           BR-SHL-034 (every displayed date goes through the shared cell) ·
//           BR-SHL-044 (one page header — this screen DECLARES one, never
//           draws its own)
// ───────────────────────────────────────────────────────
// S17 — the accounts list. The `customers` backend landed with no screen on
// it; this is that screen, and it renders WHAT THE ENDPOINT ACTUALLY SERVES.
//
// What this screen refuses to do — each of these is a cell the prototype draws
// and the API cannot answer, and each is rendered as ABSENT WITH ITS REASON
// rather than as a zero, a dash, or a blank:
//
//   · **No aging pill.** The prototype's Status column mixes a stored status
//     ("Pending") with a DERIVED one ("Current", "30d past", "60+ past").
//     BR-CUS-016 derives the second kind from open invoices; billing owns
//     `invoices` and it does not exist (W3), so `aging` is served null and this
//     column shows the STORED status only. Nothing here turns a null into
//     "Current" — that would be a claim about a customer's money.
//
//   · **No Last bill date.** Same missing table. The cell says it is waiting,
//     because "—" in a date column reads as "this customer was never billed".
//
//   · **No past-due-60+ figure** in the roll-up, for the same reason. The
//     server sends null rather than 0, and "18 past-due 60+" and "0 past-due
//     60+" are different claims.
//
//   · **No Plan column and no Plan filter.** BR-CUS-053's capability row lists
//     both; they need the BR-CUS-029 account plan snapshot, which has no DDL in
//     any signed document. The UNIT's plan is not substituted — the two are
//     equal only until the first override (BR-CUS-010).
//
//   · **No status segments and no CSV export.** Only "All" and "Closed" of the
//     four prototype segments are answerable without invoices, and a
//     half-implemented segment set is worse than none; `/exports` has no
//     `accounts` resource registered, and BR-SHL-010 says an undeclared
//     capability does not render.
//
// The one figure that IS served and still needs a caveat is Outstanding: it
// sums the cached `accounts.balance`, and nothing writes that column yet, so it
// is honestly 0 today. The roll-up says so rather than implying an AR position.
//
// AMENDED 2026-08-11 (S18/S21 lane). Two of the absences above are now built,
// so the screen stops naming them as gaps:
//
//   · The account number is a LINK to S21 (`/accounts/{id}`), because that
//     screen exists and reads `GET /accounts/{id}`.
//   · "+ New account" navigates to the S18 guided page instead of rendering
//     disabled with "that page is a later story". (Superseded 2026-10-11 by
//     `DEF-CUS-10049`: it is disabled for every role again, with its reason.)
//     The ROLE was then the only thing that could block it — Move-in and Move-out still have neither route nor
//     endpoint and keep theirs.
//
// AMENDED 2026-08-24 (CR-030 W1 · T1.10 + T1.11). The screen grows a TAB STRIP
// and its first second tab:
//
//   · **S81 · Imports** — the run history for the `accounts` target of the ONE
//     ETL runner (BR-MET-096), mounted from `AccountImportsTab`. It exists at
//     `/accounts?tab=imports` because that is the literal `returnTo` the
//     accounts workflow kind carries, so a finished import lands here by URL
//     and by nothing else.
//   · **The `↑` import LEAVES the header's secondary row** (B18 §5.9.2 row 7)
//     and becomes the Imports tab's ONE primary. The page therefore still has
//     exactly one primary on either tab (B14 rule 4 / BR-SHL-044) — which is
//     the shape B18 §5.9.4 rules over r10's own screenshot, because `[shot]`
//     draws `↑ New import` TWICE and that would be two primaries.
//   · **Two tabs, not `[shot]`'s eight.** Requests · New Connect · Move-ins ·
//     Move-outs · Transfers · Disconnects are W4–W7's; a tab label with no
//     body behind it is hard-won law 2 wearing a tab.
//
// AMENDED 2026-08-24 (CR-030 W2 · tasks 2.1, 2.2, 2.3, 2.6, 2.7, 2.8, 2.9).
// B18 §5.1 is the specification for everything below; each change and each gap
// is named where it is made. The four headline ones:
//
//   · **EIGHT TABS, and the line above is now half wrong.** Six of them have no
//     body, and the W1 lane's reading — "a tab label with no body behind it is
//     hard-won law 2 wearing a tab" — was right about the DANGER and wrong about
//     the remedy. Hard-won law 2 is about UI that renders NOTHING and passes
//     every test; an EMPTY TABLE under `Move-ins` is worse than that, because it
//     asserts "you have no move-ins", which is false — the feature does not
//     exist. So the six render a STATED ABSENCE naming the wave that brings
//     them, which is the shape `SettingsPage.tsx:432` has shipped for unbuilt
//     settings tabs since 2026-08-09 and `AssetDetailPage`'s Reads tab for an
//     unserved endpoint. Nothing here draws an empty table.
//
//   · **THE `.sub` ROLL-UP LINE IS REPLACED BY A KPI STRIP** (B18 §5.1.1), which
//     is why `AccountsRollupLine` is gone rather than kept beside it: its first
//     three figures ARE three of the five tiles, and one screen stating "8
//     accounts" twice is the drift the PO keeps finding. The strip is the shared
//     `KPIStrip`, the same component the Assets registry and the Reads list use.
//
//   · **`STATUS` AND `AGEING` ARE TWO COLUMNS NOW** (B18 §5.1.2). The ageing
//     half arrived server-side on 2026-08-24 as `ageing_segment` — BR-CUS-048's
//     four bands, derived from the account's OWN opening position. It is NOT the
//     `aging` field beside it, which is billing's still-unwired three-state
//     vocabulary; see `accountsListCells.tsx` for the whole of that.
//
//   · **THE SEARCH PLACEHOLDER STILL DOES NOT SAY `customer #`**, and B18 §5.1.2
//     is the reason it now says everything else. Its rule is *"Do not ship the
//     placeholder before the column"*; `customers.customer_no` DID land (W0,
//     migrations 0013 + 0014) — and `selectors.account_list` still matches only
//     `account_no`, `contacts.full_name` and metering/assets ids, so typing a
//     customer number finds nothing. A placeholder is a promise about the SEARCH,
//     not about the schema, so the sentence names the four things that really
//     match and no fifth. REPORTED.
//
// ⚠ AMENDED 2026-08-24 (CR-030 W2 close-out · T2.5 + T2.9). **THE PARAGRAPH
// DIRECTLY ABOVE IS NOW FALSE AND IS KEPT ONLY SO THIS SENTENCE HAS SOMETHING
// TO CORRECT** — hard-won law 1: the comment changes with the fact, in the same
// commit as the fact. Two rulings landed, and the exception notes at the foot of
// this file are amended to match rather than left standing (DEF-445's shape is a
// true absence still being claimed after another lane shipped the thing it was
// waiting for):
//
//   · **`selectors.account_list` NOW MATCHES `customer_no`** — BR-CUS-053,
//     AMENDED 2026-08-24 by PO ruling, asked as *"we were suppose to add
//     customer # comlume what happened to that"*. The rule names three pieces
//     in a fixed order and B18's own sentence sets it — *"Do not ship the
//     placeholder before the column"*: **(a)** the selector learns the column
//     (`_account_ids_by_customer_no`, ORed into the same group as `account_no`,
//     proved by `tests/test_cr030_w2_customer_no_search.py`), **(b)** the list
//     renders `CUSTOMER #` over the served `customer_no` field, and only then
//     **(c)** the prompt names it. All three are in this commit, in that order.
//     The withheld placeholder was RIGHT while it was withheld, and the reason
//     it is no longer withheld is that the promise is now kept.
//
//   · **THE `4 accounts` CUSTOMER SUB-LINK IS CUT** — PO ruling 2026-08-24,
//     verbatim: *"okay dont link it"*. W2 task 2.5 is struck through in B18. It
//     is **not built and will not be built**, and neither are the two server
//     halves it needed. `TC-ACC-3` is closed as **WON'T BUILD** in
//     `AccountsPage.test.tsx` rather than left as an `it.todo`, because a todo
//     left standing reads as work owed. Nothing here is waiting on it.
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {useNavigate, useSearchParams} from "react-router-dom";

import { api } from "@/api/client";
import { ListExportButton } from "@/features/exports/ListExportButton";
import type { ApiClient } from "@/api/client";
import { ACCOUNT_KINDS, ACCOUNT_KIND_MASTER, getAccounts } from "@/api/endpoints";
import type { AccountsRollup } from "@/api/endpoints";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import { FilterBar } from "@/components/FilterBar";
import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";
import { MoneyCell } from "@/components/MoneyCell";
import { useCrumbLeaf } from "@/components/crumbLeaf";
import { PageHeader } from "@/components/PageHeader";
import { PermissionDenied } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { parseTableParams, serializeTableParams } from "@/components/tableTypes";
import { InlineLinkTo } from "@/components/Surfaces";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import {
  CELL_FULL,
  GuardedButton,
  isDenied,
  premisesDetailPath,
  unitDetailPath,
  useRegional,
  useAccessCell,
} from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
// ⚠ `ArrivesWith` IS NO LONGER IMPORTED, AND ITS ABSENCE IS THE MILESTONE.
// Six of the eight tabs rendered it as recently as this morning. With W5's two
// move worklists mounted below, **every tab on this screen renders its contents
// rather than a note about itself** — hard-won law 2, closed on the screen that
// taught it. Re-adding the import means a tab has gone back to describing
// itself, which is a thing to notice rather than to do quietly.
import { apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";
// ⚠ `Button` and `SERVICE_REQUESTS_ROUTE` WERE IMPORTED HERE AND USED BY
// NOTHING, and `eslint --max-warnings 0` was RED on this branch before this
// lane touched the file (verified against HEAD through `--stdin`). They were
// the interim Requests panel's — a `Button` linking to `/requests` — and
// DEF-664's embed removed the panel and left its two imports behind. Deleted
// rather than silenced: a dead import is what a reader mistakes for a
// dependency. REPORTED as pre-existing, not this lane's.

import { AccountImportsTab } from "./AccountImportsTab";
// CR-030 W6 task 6.12 / W7 tasks 7.4 and 7.11 — the three worklists whose
// backends shipped 2026-08-25 with no frontend half. The PO reported all three
// from a live build: *"nothing on new connect + on all of these screens"*.
import { DisconnectsTab } from "./DisconnectsTab";
// CR-094-BRC01 wave G — the two queues and the two forms they open.
import { JobQueueTab } from "./JobQueueTab";
import { COMPLAINT_INTAKE, SERVICE_INTAKE } from "./jobIntakeShared";
import { MoveInsTab } from "./MoveInsTab";
import { MoveOutsTab } from "./MoveOutsTab";
import { MOVE_IN_WIZARD_ROUTE, MOVE_OUT_WIZARD_ROUTE } from "./moveShared";
import { NewConnectsTab } from "./NewConnectsTab";
import { ServiceRequestsListPage } from "./ServiceRequestsListPage";
import { TransfersTab } from "./TransfersTab";
// DEF-729 / DEF-730 — the four wizard routes this page's ONE primary slot
// points at. Each is imported from the feature that OWNS it and each is
// mounted in `App.tsx`; see `tabPrimary` for the two acts that have no
// standalone route and therefore stay disabled.
import { NEW_CONNECT_ROUTE } from "./newConnectShared";
import { SERVICE_REQUEST_NEW_ROUTE } from "./serviceRequestShared";
import { DISCONNECT_WIZARD_ROUTE, TRANSFER_WIZARD_ROUTE } from "./transferDisconnectShared";
import {
  AGEING_SEGMENTS,
  AccountServiceChips,
  AccountAgeCell,
  AgeingCell,
  CustomerNoCell,
} from "./accountsListCells";
import type { AccountRowWithAgeing } from "./accountsListCells";
import type { AccountCategoryOption } from "./customersShared";
import {
  ACCOUNTS_PERMISSION,
  ACCOUNT_IMPORT_ROUTE,
  ACCOUNT_NEW_ROUTE,
  ACCOUNT_SEED_STATUSES,
  ACTIVE_STATUS_CODE,
  AwaitsCell,
  DASHBOARD_ROUTE,
  DRAFT_STATUS_CODE,
  Dash,
  accountDetailPath,
  accountStatusLabel,
  accountStatusTone,
  useAccountCategories,
} from "./customersShared";
// ⚠ `rollupCurrency` IS NO LONGER IMPORTED, AND ITS ABSENCE IS THE CHANGE.
// It resolved the CHAR(3) for the `OUTSTANDING` tile, and the PO's four tiles
// of 2026-09-28 carry no money at all — so this screen states no tenant-wide
// figure in any currency. The helper stays in `customersShared` (it is
// exported and asserted there); what went is this screen's use of it.

import "./customers.css";

// ── Pure pieces (provable without a browser or a network) ──────────────────

export const accountsQueryKey = (query: string) => ["accounts", query] as const;

/**
 * CR-030 W2 T2.1 — B18 §4's EIGHT tabs, in the strip order a user reads them.
 *
 * ⚠ **THE STRIP IS URL STATE (BR-SHL-011), AND IT HAS TO BE**: the account
 * import workflow's `returnTo` is the literal string `/accounts?tab=imports`
 * (`components/workflow/kinds.ts`), so a run that finishes lands here by URL
 * and by nothing else. An unknown `?tab=` falls back rather than erroring —
 * the same posture `tabFromParam` takes on the Assets registry.
 *
 * ⚠ **ALL EIGHT HAVE A BODY AS OF 2026-08-25 (CR-030 W5), AND THE PARAGRAPH
 * THAT STOOD HERE IS SUPERSEDED RATHER THAN DELETED.** It read: *"TWO OF THE
 * EIGHT HAVE A BODY. THE OTHER SIX STATE THEIR ABSENCE … So each of the six
 * renders `ArrivesWith`, naming what arrives and citing the open question that
 * keeps its wave open (G38)."* That was true and was the right call at the
 * time — a tab opening onto the shared empty state would have said *"No
 * move-ins yet"*, a statement about this utility's DATA, when the product
 * could not hold a move-in at all.
 *
 * The six were mounted over two days: `Requests` (DEF-664), then `New
 * connects`, `Transfers` and `Disconnects` in W6/W7, and `Move-ins` and
 * `Move-outs` last. **Each list still names what it cannot show** — the
 * absences moved from a panel covering the whole tab onto the cells, segments
 * and tiles they are actually about, which is BR-SHL-025's placement rule and
 * is why the notes got more specific rather than disappearing.
 *
 * ⚠ **AND THE COUNTS: THE STRIP CARRIES NONE, ON ANY TAB, SINCE 2026-09-20
 * (`DEF-CUS-5939`).** This paragraph read *"seven of the eight carry one in
 * `[shot]`, and exactly one of those is a figure this product can answer"*,
 * and `Accounts` rendered `Accounts 82` from `listQuery.data.count`. Two
 * things were wrong with it. The **redesign** draws the strip four times —
 * p117, p131, p41, p48 — and NOT ONE tab carries a count in any of them. And
 * the figure itself was the count of rows matching the CURRENT FILTERS rather
 * than a tenant total, so typing in the search box moved the number beside the
 * tab's own word. The reasoning the paragraph gave for the other tabs stands
 * and is now the rule for all ten: a number beside a tab word is read as a
 * fact about that tab, and this product can answer it for none of them. The
 * pager under the table states `1–N of M` for what is actually on screen.
 */
export const ACCOUNTS_TAB_PARAM = "tab";
export const ACCOUNTS_TAB_IDS = [
  "accounts",
  "requests",
  "new-connects",
  "move-ins",
  "move-outs",
  "transfers",
  "disconnects",
  // ⛔ **`waiting-on` WAS THE NINTH ENTRY HERE FOR ONE DAY AND IS SUPERSEDED —
  // CR-035 · AMENDMENT 1, PO 2026-08-26.** Verbatim: *"We dont need seperate tab
  // for this - this will be directly on each request Request, Connect, Move IN
  // move Out, Trasnfr, Disconnect - seperate queue not reequired"*, then
  // **"yyes"**. A parked job now appears on the tab for ITS OWN KIND OF WORK,
  // and on `requests` in the `waiting_on` COLUMN that list has carried since it
  // was built. The strip is back to the EIGHT tabs B18 §4 draws.
  //
  // ⚠ **AND SINCE 2026-09-20 IT IS A ROW OF THAT TAB'S OWN LIST, NOT A PANEL
  // ABOVE IT (`DEF-CUS-5994`).** PO, verbatim: *"remove it - it is anyway in
  // the list so we dont need it sepretely - if it is not in list add it"*. This
  // paragraph named `ParkedDraftsPanel` and five mounts of it stood below;
  // every one of the five lists unions `wizard_parks` for its own flow now, so
  // the draft is a row with a real step, a Resume and a Discard, ordered and
  // paged by the DATABASE alongside the records. The amendment's own two
  // requirements are unchanged and are met on the row instead of above it: a
  // draft is unmistakably a draft, and the count does not lie.
  //
  // ⚠ The behaviour did not disappear with the tab, so neither did its record:
  // `US-CUS-031` / `EP-CUS-11` / A1's `S17.2` are RE-POINTED (dated 2026-08-26),
  // not deleted — the list is keeping its home rather than its own screen.
  //
  // ── CR-094-BRC01 WAVE G (2026-09-12) · THE NINTH AND TENTH TABS ─────────
  //
  // PO ruling, verbatim: *"in the main tab list, add complaints and services.
  // These two tabs. build their ad form and detail view. and tables."*
  //
  // ⚠ **THE POSITION IS THE DRAWING'S AND IT IS NOT ALPHABETICAL OR
  // APPENDED.** `05-prototype/02 Accounts Menu Blueprint.pdf` page 39 draws
  // the strip as `Accounts · Requests · New connects · Move-ins · Move-outs ·
  // Transfers · Disconnects · **Complaints · Services** · Imports` — so the
  // two arrive AFTER the six flow queues and BEFORE `Imports`, which stays
  // last. The header beside them reads *"10 tabs"* in the drawing's own words.
  //
  // ⚠ **THE MAIN TAB LIST IS THIS REGISTER'S, NOT THE ACCOUNT DETAIL'S.** Both
  // screens draw a strip and the ruling names neither, so it was read off the
  // drawing: page 39's address is `/:tenant/accounts?tab=complaints` and page
  // 47's is `/:tenant/accounts?tab=services`. The account detail's twelve tabs
  // are untouched by this wave.
  //
  // ⚠ **A COMPLAINT IS A WORK ORDER AND SO IS A SERVICE — NO NEW TABLE.**
  // `work.models.SEED_TYPE_SPINE` already seeds `Consumer Complaint` and
  // `Consumer Services`, a job already stands on an account (`BR-WRK-006`) and
  // `BR-WRK-018` already stamps its response time. `jobIntakeShared.tsx` §1
  // carries the whole judgment, its evidence and what it supersedes.
  "complaints",
  "services",
  "imports",
] as const;
export type AccountsTab = (typeof ACCOUNTS_TAB_IDS)[number];

/**
 * The two tabs that have a body. Every other tab states its absence.
 *
 * Exported so `AccountsPage.test.tsx` can walk `ACCOUNTS_TAB_IDS` and assert
 * that each tab is EITHER in this list OR renders a note carrying a
 * `data-tracks` id. ⚠ **EVERY TAB IS NOW IN THIS LIST**, so the second arm of
 * that assertion currently has nothing to check — it is kept, not deleted,
 * because it is what a ninth tab would meet if it were added without a body.
 */
/** The tabs that render a real surface rather than a stated absence.
 *
 * ⚠ **`requests` JOINED THIS LIST ON 2026-08-25 (DEF-664), REPORTED FROM
 * PRODUCTION.** The PO created `SR-26-0001`, opened this tab, and saw a panel
 * saying the list *"is still to come"* — while their request was sitting on
 * `/requests`, one click away. Their words: *"When I click on service request
 * nothing is shoing, but I ahve created one request - it shows up on another
 * scren"*. The panel was TRUE and it was still the wrong thing to show them. */
/** ⚠ **`new-connects`, `transfers` AND `disconnects` JOINED THIS LIST ON
 *  2026-08-25, REPORTED FROM PRODUCTION IN THE SAME BREATH AS DEF-664.** The
 *  PO, on a live build: *"nothing on new connect + on all of these screens"*.
 *  Each of the three had a finished read model, a mounted endpoint and a panel
 *  saying the surface *"arrives with"* a wave — three honest notes that added
 *  up to a screen a user experiences as broken (hard-won law 2). The three tabs
 *  below now mount the real lists.
 *
 *  ⚠ **`move-ins` AND `move-outs` JOINED THIS LIST ON 2026-08-25 (CR-030 W5),
 *  AND THE PARAGRAPH THAT STOOD HERE IS SUPERSEDED.** It read: *"W5's lists
 *  have no read model and no endpoint (measured 2026-08-25 — there is no
 *  `GET /move-ins` or `GET /move-outs` anywhere in `06-backend`), so those two
 *  keep their `ArrivesWith` panel."* That measurement was true when it was
 *  written and is now false: `apps/customers/move_reads.py` is the read model
 *  and both routes are REPORTED for mounting. **These were the last two of the
 *  eight**, and with them the Accounts screen has no tab that renders a note
 *  about itself instead of its contents (hard-won law 2).
 *
 *  ⚠ **NEITHER LIST SHOWS WHAT B18 DRAWS, AND BOTH SAY SO ON THE TAB.** There
 *  is no `move_ins` table and no `move_outs` table: a move-in is the life of a
 *  BR-CUS-018 draft account, and a move-out is a `closed_at` that
 *  `services.move_out` already wrote. So four of B18 §5.6.7's six drawn
 *  move-outs are in a state this schema cannot hold, and the segments that
 *  would show them render DISABLED carrying the columns they would need. The
 *  old `ArrivesWith` panel was honest about the same gap; the difference is
 *  that a user can now see the rows that DO exist. */
export const ACCOUNTS_BUILT_TABS: readonly AccountsTab[] = [
  "accounts",
  "requests",
  "new-connects",
  "move-ins",
  "move-outs",
  "transfers",
  "disconnects",
  // CR-094-BRC01 wave G — each mounts a real `JobQueueTab` over
  // `GET /work-orders` with its type pinned, in the SAME commit as the tab. A
  // tab label with no body behind it is hard-won law 2 wearing a tab.
  "complaints",
  "services",
  "imports",
];

/** The tab's label key. One key per tab, never a concatenation (B8). */
export const ACCOUNTS_TAB_LABEL_KEYS: Readonly<Record<AccountsTab, string>> = {
  accounts: "customers.accounts.tab.accounts",
  requests: "customers.accounts.tab.requests",
  "new-connects": "customers.accounts.tab.newConnects",
  "move-ins": "customers.accounts.tab.moveIns",
  "move-outs": "customers.accounts.tab.moveOuts",
  transfers: "customers.accounts.tab.transfers",
  disconnects: "customers.accounts.tab.disconnects",
  // CR-094-BRC01 wave G. Both land in all eleven catalogues in the commit that
  // adds the tab, so `ACCOUNTS_TAB_LABEL_EN` below stays empty — which is the
  // posture its own header asks for and what `G15`/`G27` check.
  complaints: "customers.accounts.tab.complaints",
  services: "customers.accounts.tab.services",
  imports: "customers.accounts.tab.imports",
};

/**
 * The English for a label key that HAS NO CATALOGUE ROW YET.
 *
 * ⚠ **IT IS EMPTY, AND IT IS KEPT EMPTY RATHER THAN DELETED.** Its one entry
 * was `waiting-on`, added on 2026-08-26 because that key had no catalogue row
 * on the day the ninth tab shipped; the tab was folded away the same day
 * (CR-035 · AMENDMENT 1) and every remaining tab label IS translated in all
 * eleven catalogues. The map stays because it is the shape a tenth tab would
 * need on the day it is added before its key lands, and because deleting it
 * would put the next lane's untranslated label straight onto the strip as a raw
 * dotted key — which is the defect G27 exists for.
 */
export const ACCOUNTS_TAB_LABEL_EN: Partial<Record<AccountsTab, string>> = {};

export function accountsTabFromParam(raw: string | null): AccountsTab {
  return (ACCOUNTS_TAB_IDS as readonly string[]).includes(raw ?? "")
    ? (raw as AccountsTab)
    : "accounts";
}

/**
 * The US-CUS-001 capability row, as the shared table framework reads it
 * (BR-SHL-010: a capability that is not declared here is not rendered).
 *
 * Column keys are the SERVER's sort names where a column is sortable, so the
 * request stays the contract's (`account_no`, `name`, `balance`, `status` are
 * `selectors.ACCOUNT_SORTS`; the renderer bridges key and field).
 *
 * `last_bill` is in the server's sort set and is DELIBERATELY not sortable
 * here: every value is null until billing lands, so a sort control would offer
 * an ordering that does not exist.
 */
export function accountsTableConfig(
  t: Translator,
  cells: {
    accountNo: (row: AccountRowWithAgeing) => JSX.Element;
    customerNo: (row: AccountRowWithAgeing) => JSX.Element;
    name: (row: AccountRowWithAgeing) => JSX.Element;
    premise: (row: AccountRowWithAgeing) => JSX.Element;
    services: (row: AccountRowWithAgeing) => JSX.Element;
    balance: (row: AccountRowWithAgeing) => JSX.Element;
    lastBill: (row: AccountRowWithAgeing) => JSX.Element;
    status: (row: AccountRowWithAgeing) => JSX.Element;
    ageing: (row: AccountRowWithAgeing) => JSX.Element;
    accountAge: (row: AccountRowWithAgeing) => JSX.Element;
    autopay: (row: AccountRowWithAgeing) => JSX.Element;
    since: (row: AccountRowWithAgeing) => JSX.Element;
  },
  /** DEF-684 — the platform category catalogue, fetched. See `accountsFilters`. */
  categories: readonly AccountCategoryOption[] = [],
): TableConfig<AccountRowWithAgeing> {
  return {
    screenId: "S17",
    // B14 rule 19 / DEF-510 — THIS list's own prompt, naming what the SERVER
    // really matches. As of 2026-08-24 that is FIVE things and `customer #` is
    // one of them (CR-030 W2 T2.9 (c)); see the file header for the order the
    // rule required and why the prompt went last.
    searchPlaceholder: "customers.accounts.searchPlaceholder",
    columns: [
      // The prototype's seven default columns, in its order (line 2796).
      {
        key: "account_no",
        label: t("customers.accounts.col.account"),
        sortable: true,
        identity: true, // BR-SHL-013: the identity column can never be hidden
        cell: cells.accountNo,
      },
      // CR-030 W2 T2.9(b) — `CUSTOMER #`, the column the PO asked after by name
      // on 2026-08-24: *"we were suppose to add customer # comlume what
      // happened to that"*. BR-CUS-053 (AMENDED the same day) is the contract:
      // *"the list renders `CUSTOMER #` as a column, available through the
      // shared column selector."*
      //
      // ⚠ **SECOND, BESIDE `ACCOUNT`, AND `[shot]` DRAWS NO SUCH COLUMN AT
      // ALL.** B18 §5.1.2's transcribed table has eight columns and this is not
      // one of them — the design only ever asked for the number as a SEARCH
      // term. The ruling made it a column, and nothing in the ruling says
      // where. It sits here because the two numbers are the pair a clerk holds
      // one of and does not know which: putting them adjacent is what makes
      // "either number finds the row" legible on the screen as well as true in
      // the selector. REPORTED as a placement this lane chose.
      //
      // ⚠ **VISIBLE BY DEFAULT, WHICH IS ALSO A JUDGMENT.** *"available through
      // the shared column selector"* could be read as `defaultVisible: false`,
      // like `autopay` and `opened_at` below. It is not read that way, because
      // the PO's sentence is a complaint that they could not SEE the number —
      // shipping it hidden behind a menu would answer the letter of the rule
      // and not the question. Every reader can still turn it off.
      //
      // ⚠ **NOT SORTABLE.** `selectors.ACCOUNT_SORTS` is `account_no · name ·
      // balance · last_bill · status`, and `customer_no` is not in it — the
      // same refusal `ageing` and `last_bill` carry below. A sort control here
      // would offer an ordering the request cannot ask for.
      // ⚠ THE `CUSTOMER #` COLUMN IS REMOVED FROM THIS LIST — PO ruling
      // 2026-08-24, made while walking the DEPLOYED build: *"on account tab -
      // we dont need this column … you can sho it as part of details screen"*.
      //
      // THIS REVERSES THE READING ABOVE, AND THE REVERSAL IS THE USEFUL PART.
      // Earlier the same day the PO asked *"we were suppose to add customer #
      // comlume what happened to that"*, which was read here as "put it on the
      // list where I can see it". Seeing it on the list answered the question
      // and changed the answer: the number belongs on the ACCOUNT DETAIL, not
      // in a column that pushes NAME and PREMISE sideways on every row of the
      // busiest screen in the product. Nothing was wrong with the first
      // reading; the screen is simply better evidence than the sentence, which
      // is hard-won law 6 arriving from the PO's side.
      //
      // WHAT SURVIVES, DELIBERATELY: `selectors.account_list` still MATCHES
      // `customer_no`, and the placeholder still names it. The ruling is about
      // a COLUMN, not about search — one box finding a person by either number
      // is the capability the PO asked for, and removing it would answer a
      // question they did not ask. `account_row` keeps serving the field, so
      // the detail screen reads it with no further server work.
      { key: "name", label: t("customers.accounts.col.name"), sortable: true, cell: cells.name },
      { key: "premise", label: t("customers.accounts.col.premise"), cell: cells.premise },
      { key: "services", label: t("customers.accounts.col.services"), cell: cells.services },
      {
        key: "balance",
        label: t("customers.accounts.col.balance"),
        sortable: true,
        numeric: true,
        cell: cells.balance,
      },
      { key: "last_bill", label: t("customers.accounts.col.lastBill"), cell: cells.lastBill },
      {
        key: "status",
        label: t("customers.accounts.col.status"),
        sortable: true,
        cell: cells.status,
      },
      // CR-030 W2 T2.3 — B18 §5.1.2 splits the prototype's one Status column in
      // two, and this is the half it adds. Today `[shot]` draws `Pending`
      // (stored) beside `30d past` (derived) in the SAME cell, and those are two
      // different questions about an account: what the utility set it to, and
      // where its money sits.
      //
      // ⚠ SORTABLE SINCE 2026-10-17 (DEF-CUS-10181). This read "NOT SORTABLE
      // … `ageing` is not in [ACCOUNT_SORTS]" — true until the PO ruled that
      // *"filter and sort work for bill-only accounts"*; the server now orders
      // by the anchor in SQL (`desc` = oldest unpaid money first).
      {
        key: "ageing",
        label: t("customers.accounts.col.ageing"),
        sortable: true,
        cell: cells.ageing,
      },
      // DEF-CUS-10180 — PO 2026-10-17: *"Column Account age with the Opened
      // (or closed date) beneath; sortable oldest ↔ newest by Opened"*. The
      // cell is the SHARED `AgeCell` via `AccountAgeCell`. Default-visible:
      // the ruling asks for a column, not a menu entry.
      {
        key: "account_age",
        label: t("customers.accounts.col.accountAge"),
        sortable: true,
        cell: cells.accountAge,
      },
      // Two of the epic's three "available" columns. The third (+Plan) is
      // absent because BR-CUS-029's snapshot table does not exist — an
      // always-empty column would be a worse answer than none.
      {
        key: "autopay",
        label: t("customers.accounts.col.autopay"),
        defaultVisible: false,
        cell: cells.autopay,
      },
      {
        key: "opened_at",
        label: t("customers.accounts.col.since"),
        defaultVisible: false,
        cell: cells.since,
      },
    ],
    getRowId: (row) => row.id,
    // IS-3 / BR-CUS-053: server-side search over account #, **customer #**,
    // customer name, service address and meter #. Declared, not implemented
    // here — the server reaches the last two through metering's and assets'
    // own selectors (B1).
    //
    // ⚠ **FIVE SINCE 2026-08-24, AND THE FIFTH IS WHAT LETS THE PLACEHOLDER
    // CHANGE.** `selectors.account_list` now ORs
    // `_account_ids_by_customer_no(term)` into the same group as `account_no`
    // (BR-CUS-053 (a)), so this list is what the server really matches — which
    // is the only condition under which B18 §5.1.2 permits the prompt below to
    // name `customer #`.
    searchFields: ["account_no", "customer_no", "name", "address", "meter_no"],
    filters: accountsFilters(t, categories),
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
    // ⚠ **THIS SUPERSEDES `BR-CUS-053`'s `default sort name A→Z` CLAUSE**, and
    // only that clause — the five search terms, the filters and the columns above
    // are untouched. `NAME` is still sortable, so A→Z is one click away.
    defaultSort: { sort: "created", dir: "desc" },
  };
}

/**
 * BR-CUS-053's AC-8 filter set, minus `plan`. `plan` is NOT declared because
 * the endpoint does not accept it (no BR-CUS-029 snapshot): BE-05 ignores an
 * undeclared filter, so offering the control would narrow nothing while
 * looking as though it had.
 */
export function accountsFilters(
  t: Translator,
  /**
   * ⛔ **FETCHED — DEF-684, 2026-08-26.** These options were
   * `ACCOUNT_CATEGORIES`, the four codes BR-CUS-094 (PO 2026-08-24)
   * superseded. **A FILTER takes `all`, not `selectable`**: the ruling keeps a
   * legacy code *"still a valid FK, still filterable, still priceable"*, and
   * every account already carrying `government` has to stay findable or the
   * additive migration hid live customers behind a chip. An empty list while
   * the catalogue loads offers nothing, which is honest; four wrong codes were
   * not.
   */
  categories: readonly AccountCategoryOption[] = [],
) {
  return [
    {
      name: "status",
      label: t("customers.accounts.filter.status"),
      options: ACCOUNT_SEED_STATUSES.map((code) => ({
        value: code,
        label: t(`customers.accounts.status.${code}`),
      })),
    },
    {
      name: "category",
      label: t("customers.accounts.filter.category"),
      options: categories.map((category) => ({
        value: category.code,
        label: category.name,
      })),
    },
    {
      name: "autopay",
      label: t("customers.accounts.filter.autopay"),
      options: [
        { value: "true", label: t("customers.accounts.autopay.on") },
        { value: "false", label: t("customers.accounts.autopay.off") },
      ],
    },
    {
      // BR-CUS-068 (PO 2026-08-22) — `f.kind` partitions the list into the
      // ordinary accounts and the owner's MASTER accounts over common areas.
      //
      // ⚠ **THE OPTIONS ARE `ACCOUNT_KINDS`, NOT A PAIR WRITTEN OUT HERE.**
      // `selectors.account_list` applies the filter only for exactly `regular`
      // and `master` and IGNORES anything else — so a third option typed into
      // this list would render a chip that quietly returned the whole tenant,
      // which is BR-CUS-053's `plan` mistake with a different name.
      name: "kind",
      label: t("customers.accounts.filter.kind"),
      options: ACCOUNT_KINDS.map((code) => ({
        value: code,
        label: t(`customers.accounts.kind.${code}`),
      })),
    },
    {
      // CR-030 W2 — B18 §5.1.2's SEGMENTS (`All · Current · 30d past · 60+
      // past`), as this product's ONE filter capability.
      //
      // ⚠ `[shot]` DRAWS A SEGMENTED RADIO CONTROL and this renders a filter
      // chip, which is a stamped divergence rather than an oversight: B14 rule
      // 12 fixes the toolbar's grammar exactly — `[Search…] [All | chips ×]
      // [+ Filter ▾] … [▦ Columns]` — and the shared table framework has no
      // segment capability at all (BR-SHL-010: a capability not declared in
      // `TableConfig` is not rendered). Adding one is a change to every list in
      // the product, not to this screen. The BEHAVIOUR B18 asks for is intact:
      // the choice rides in the URL as `f.ageing=` and a reload restores it
      // (TC-ACC-5), and `All` is the chip row's own first control.
      //
      // ⚠ FOUR OPTIONS, NOT `[shot]`'s THREE. The server's segment vocabulary
      // is BR-CUS-048's four bands; there is no value meaning "60+ past", so
      // offering one would send a segment `normalize_ageing_segment` does not
      // recognise — and BR-SHL-011 makes it fall back to NO filter, i.e. a chip
      // that quietly returned the whole tenant. That is BR-CUS-053's `plan`
      // mistake with a different name. REPORTED.
      name: "ageing",
      label: t("customers.accounts.filter.ageing"),
      options: AGEING_SEGMENTS.map((code) => ({
        value: code,
        label: t(`customers.accounts.ageing.${code}`),
      })),
    },
    {
      // The server reads `balance_gt` as a flag, not a threshold: any of
      // 0 / 1 / true means "balance > 0" (selectors.account_list). One option,
      // so the control cannot imply a number it will not honour.
      name: "balance_gt",
      label: t("customers.accounts.filter.balance"),
      options: [{ value: "1", label: t("customers.accounts.filter.balanceOverZero") }],
    },
  ];
}

/** The request state → the wrapper's params. One translation, one place. */
export function accountsParamsFrom(state: TableRequestState) {
  return {
    q: state.q,
    sort: state.sort,
    dir: state.dir,
    page: state.page,
    per: state.per,
    filters: state.filters,
  };
}

// ── The KPI strip (PO ruling 2026-09-28 — FOUR tiles, one per status) ──────

/**
 * THE FOUR STATUS TILES, IN THE PRODUCT OWNER'S OWN ORDER AND WORDS.
 *
 * PO ruling 2026-09-28, given as a table: **Active · Pending · Disconnecting ·
 * Suspended**, one word each, each with a short line under it, and each one
 * SETS the list's filter when it is pressed.
 *
 * ⚠ **`Disconnecting`, NOT `Disconnects` — RULED, AND THE REASON IS ON THIS
 * SCREEN.** `Disconnects` is already a TAB here and it means the disconnect
 * REQUESTS, not the accounts. Two controls one word apart, counting different
 * things, on one screen.
 *
 * ⚠ **THE TILE KEYS OFF THE STATUS `code`; THE LABEL IS THIS CATALOGUE'S.**
 * `BR-CUS-055` makes the status list TENANT-EXTENSIBLE, so a utility may rename
 * *Vacation hold/Suspended* to *Snowbird hold* — the count follows the code and
 * does not move, and the tile still reads the PO's one ruled word. Using the
 * tenant's own name here would break the one-word ruling and B14 rule 33's
 * three-word cap the first time a utility wrote a sentence into a lookup row.
 *
 * ⚠ **A CODE THE TENANT DOES NOT HAVE DRAWS A DASH AND DOES NOT PRESS.** The
 * server sends one row per status the tenant HAS (`rollup.by_status`), so an
 * absent code means *this utility has no such status*, which is a different
 * sentence from *nobody is on it* — and `0` would state the second about the
 * first. Nor may it press: a filter on a status no account can hold is a
 * control that returns an empty list for ever, which is hard-won law 2's
 * mirror (a live screen behind a dead control).
 */
export const ACCOUNT_STATUS_TILES = [
  {
    id: "active",
    code: ACTIVE_STATUS_CODE,
    label: "customers.accounts.kpi.statusActive",
    detail: "customers.accounts.kpi.statusActiveDetail",
  },
  {
    id: "pending",
    code: DRAFT_STATUS_CODE,
    label: "customers.accounts.kpi.statusPending",
    detail: "customers.accounts.kpi.statusPendingDetail",
  },
  {
    // `marked_disconnect` — BILLABLE, because the account is still consuming
    // until the cut (BR-CUS-055 / OQ-064's closure). That is what the line
    // under the tile says in four words.
    id: "disconnecting",
    code: "marked_disconnect",
    label: "customers.accounts.kpi.statusDisconnecting",
    detail: "customers.accounts.kpi.statusDisconnectingDetail",
  },
  {
    // `vacation_hold` — `billable_base_only`. The line says so.
    id: "suspended",
    code: "vacation_hold",
    label: "customers.accounts.kpi.statusSuspended",
    detail: "customers.accounts.kpi.statusSuspendedDetail",
  },
] as const;

/** The filter this screen's tiles write. The FilterBar declares the same name,
 *  which is the whole point: pressing a tile and picking the chip are one
 *  control writing one piece of state, not two that can disagree. */
export const ACCOUNT_STATUS_FILTER = "status";

/**
 * The four tiles, built from the ONE grouped count the roll-up carries.
 *
 * ⚠ **WHAT THIS REPLACED, SAID PLAINLY, BECAUSE TWO OF THE FIVE NEVER WORKED
 * (`DEF-CUS-7700`).** The strip was `Accounts · Outstanding · Past-due 60+ ·
 * Closed this year · Pending activation`, and `PAST DUE 60+` and `CLOSED THIS
 * YEAR` rendered the literal *"Not counted yet"* from the day they shipped —
 * honestly, each with a reason, and for weeks. `AccountsPage.test.tsx` asserted
 * that literal, so the two gaps read as intended behaviour to every check in
 * this repo.
 *
 * ⚠ **`OUTSTANDING` WAS REAL AND IS GONE ANYWAY, AND NOTHING ELSE ON THIS
 * SCREEN STATES IT.** The ruling is four tiles and Outstanding is not one of
 * them. The BALANCE column still shows what ONE account owes, the head's
 * sub-line carries `10 tabs · <Tab>`, and no surface here now adds the tenant's
 * receivable up — that figure lives on Finance's Revenue & AR screen, which is
 * where `rollup.outstanding` was always tied out against (DEF-127). The SERVER
 * still serves it; what went is the renderer. Reported in the lane report
 * rather than kept as a quiet fifth tile.
 *
 * ⚠ **THE HEADLINE NUMBER FALLS, ON PURPOSE.** `ACCOUNTS` counted live AND
 * closed; `Active` counts only the accounts billing normally. On the demo
 * utility that is 79 → about 71, and it will look like a bug on the day it
 * ships, which is why the tile says `Active` and not `Accounts` and why its
 * line says `billing normally`.
 */
export function accountsKpis(args: {
  byStatus: AccountsRollup["by_status"] | undefined;
  /** The status filter the list is narrowed to right now, or undefined. */
  applied: string | undefined;
  onToggle: (code: string) => void;
  t: Translator;
}): KpiTile[] {
  const counts = new Map((args.byStatus ?? []).map((row) => [row.code, row.accounts]));
  return ACCOUNT_STATUS_TILES.map((tile) => {
    const count = counts.get(tile.code);
    return {
      id: tile.id,
      label: args.t(tile.label),
      // A dash, never a 0: the server did not answer for this status, either
      // because the read failed or because this tenant does not have it. Same
      // disposition the `ACCOUNTS` tile carried, for the same reason.
      value: count ?? <Dash />,
      detail: args.t(tile.detail),
      press:
        count === undefined
          ? undefined
          : {
              onPress: () => args.onToggle(tile.code),
              pressed: args.applied === tile.code,
            },
    };
  });
}

/**
 * Press once to narrow the list to a status; press the same tile again to clear
 * it. Returns the NEXT request state — pure, so the DOM test can read it
 * without a browser and the screen has one place that writes this.
 *
 * ⚠ **IT WRITES `state.filters`, WHICH IS WHAT THE FILTER BAR READS.** That is
 * the ruling's own sentence — *"through the same state the FilterBar reads, so
 * the filter bar shows it as applied afterwards"* — and it is why the tile does
 * not keep a selection of its own. A tile holding its own copy is two controls
 * disagreeing, which is the defect just removed from the New Connects list.
 *
 * ⚠ **THE KEY IS DELETED RATHER THAN SET EMPTY**, exactly as `FilterBar`'s own
 * `setFilter(state, name, "")` does, so *no filter* is one representation and
 * not two — `f.status=` in the URL is a filter nobody can see.
 *
 * ⚠ **AND THE PAGE GOES BACK TO 1.** A narrower result set has fewer pages, and
 * page 4 of a list that now holds one page is the blank table `BR-SHL-011`'s
 * clamp exists to prevent.
 */
export function accountsStateAfterTilePress(
  state: TableRequestState,
  code: string,
): TableRequestState {
  const filters = { ...state.filters };
  if (filters[ACCOUNT_STATUS_FILTER] === code) {
    delete filters[ACCOUNT_STATUS_FILTER];
  } else {
    filters[ACCOUNT_STATUS_FILTER] = code;
  }
  return { ...state, filters, page: 1 };
}

// ── The screen ─────────────────────────────────────────────────────────────

export interface AccountsListPageProps extends RegionalProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

export function AccountsListPage(props: AccountsListPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const [searchParams, setSearchParams] = useSearchParams();
  const { timeZone, dateFormat } = useRegional(props);

  const cell = useAccessCell(ACCOUNTS_PERMISSION, client);
  // BR-SHL-025: "Full" writes; anything else renders the control disabled WITH
  // the reason. The server refuses regardless — this only saves a round trip.
  const writeBlockedReason =
    cell === CELL_FULL || cell === null ? null : t("customers.accounts.rbac.readOnly");
  // S18 landed (US-CUS-003), so "+ New account" WAS a real navigation and the
  // ROLE the only thing that could block it — until the ruling below. S19/S20 landed too, but both
  // act on ONE account and this header has none selected — so Move-in/Move-out
  // keep a reason that now names the right fact (hard-won law 1: the string
  // changes with what is true).
  //
  // ⛔ **`DEF-CUS-10049` — `+ New account` IS DISABLED FOR EVERY ROLE (PO ruling
  // 2026-10-11, verbatim: *"this si correct 0 fix it"*).** A new account is
  // created through New connect or Move-in, both of which make the account as
  // part of the act that needs it; the bare S18 wizard made one with no
  // service behind it. The control stays on screen, greyed, WITH its reason
  // (BR-SHL-025) rather than vanishing, so a clerk who looks for it is told
  // where to go. The role's own reason still wins when it applies, because it
  // is the truer of the two for that user. The empty state's CTA is the same
  // control and carries the same reason.
  const newAccountReason = writeBlockedReason ?? t("customers.accounts.action.newDisabled");
  // ⚠ **`customers.accounts.action.moveBlocked` IS GONE FROM THIS SCREEN — PO
  // ruling 2026-08-26.** It said *"Move-in and move-out each act on one account,
  // and none is selected here. Open the account from the list and use its own
  // Move-out…"*, and the PO quoted that justification back and overruled it:
  // *"-Enable Move in /move out"*. Both acts now have a standalone entry point
  // (`/move-ins/new`, `/move-outs/new`) whose FIRST STEP chooses the subject, so
  // the sentence is not merely unwanted — it is false. The ROLE is the only
  // thing left that can block either (BR-SHL-025), exactly like `+ New account`.
  // The orphaned key is REPORTED for the locale lane to retire from all eleven
  // catalogues; nothing here edits one.
  const moveReason = writeBlockedReason;
  // S68 (US-CUS-019). The prototype's accounts header has no import control —
  // EP-CUS-07 was approved after the prototype was drawn (BR-CUS-046) and the
  // screen id came from the OQ-063 closure. It is a POST-PROTOTYPE ADDITION,
  // recorded as one, and it is the reason a new tenant can load 2,000 existing
  // accounts at all instead of typing them one wizard at a time.
  //
  // ⚠ CR-030 W1 T1.11 — IT IS NO LONGER A SECONDARY BESIDE "+ New account".
  // B18 §5.9.2 row 7: *"`↑ Import CSV` **leaves the Accounts header** for its
  // own tab"*. It is now the ONE primary of the S81 Imports tab, which is the
  // only place it can be without the page carrying two primaries at once
  // (B14 rule 4 / BR-SHL-044) — and §5.9.4 rules that shape explicitly, over
  // r10's own screenshot, which draws the button twice.
  const importReason = writeBlockedReason;
  const activeTab = accountsTabFromParam(searchParams.get(ACCOUNTS_TAB_PARAM));
  // DEF-684 — the platform consumer categories the CATEGORY chip offers. The
  // FILTER takes `all` (selectable + legacy): BR-CUS-094 keeps a legacy code
  // filterable, and an account already carrying `government` must stay
  // findable.
  const categories = useAccountCategories(client);
  const isAccountsTab = activeTab === "accounts";
  const isImportsTab = activeTab === "imports";
  function openNewAccount(): void {
    navigate(tenantPath(ACCOUNT_NEW_ROUTE));
  }
  function openImportAccounts(): void {
    navigate(tenantPath(ACCOUNT_IMPORT_ROUTE));
  }
  // S19 / S20 standalone (PO 2026-08-26). Verified mounted in `App.tsx` — the
  // mirror of DEF-730 is a CTA enabled onto a route that does not exist, so the
  // two constants are imported from the file that declares them rather than
  // spelled here.
  function openMoveIn(): void {
    navigate(tenantPath(MOVE_IN_WIZARD_ROUTE));
  }
  function openMoveOut(): void {
    navigate(tenantPath(MOVE_OUT_WIZARD_ROUTE));
  }

  // ══════════════════════════════════════════════════════════════════════════
  // THE ONE PRIMARY, PER TAB — DEF-729 + DEF-730, 2026-08-26
  // ══════════════════════════════════════════════════════════════════════════
  // ⚠ **THE PO WALKED THE DEPLOYED BUILD AND COULD NOT RAISE A REQUEST, A NEW
  // CONNECT, A MOVE-IN OR A MOVE-OUT FROM THIS PAGE.** All six wizards were
  // built and routed at the time — `ServiceRequestCapturePage`,
  // `NewConnectWizard`, `MoveInWizard`, `MoveOutWizard`, `TransferWizard`,
  // `DisconnectWizard` — so the product could perform every one of those acts
  // and offered a way in to none of them from the tab a clerk uses. Two
  // separate causes met here:
  //
  //   1. `ServiceRequestsListPage` suppresses its own page header inside this
  //      tab, CORRECTLY (two H1s and two primaries break B14 rule 4 /
  //      BR-SHL-044), and its comment claimed the route was not lost because
  //      *"the empty state's CTA below still offers it"*. **That is true only
  //      while the list is EMPTY.** The PO's tab held one row.
  //   2. Five tabs disabled their empty-state CTA with a `ctaReason`, one of
  //      which — `NewConnectsTab`'s *"The new-connect wizard is not built
  //      yet"* — became FALSE the night `/connections/new` landed. Hard-won
  //      law 1, pointed at a disabled control: a missing button reads as
  //      unfinished, a disabled one reads as DECIDED.
  //
  // ⚠ **THE SLOT RELABELS; IT DOES NOT MULTIPLY.** `PageHeader` renders
  // `active.primaryAction` and nothing else, so exactly ONE primary is on the
  // page whatever the tab — this HONOURS rule 4 rather than fighting it, and
  // it is what r10 draws (`+ New request` / `+ New connect` / `+ Move-in` /
  // `+ Move-out`, each in the Accounts header).
  //
  // ⚠ **AND THE SUPERSEDED NOTE, KEPT.** T2.8 (CR-030 W2) declared NO primary
  // on the six tabs without a body, reasoning that *"a primary action over a
  // body that says 'not built yet' is a button onto nothing"*. That was right
  // then and is wrong now: every tab renders its real list, and every act has
  // a route. The rule underneath is unchanged — never point a button at
  // something that does not exist — which is why the two entries below that
  // have no route to point at stay DISABLED WITH THEIR REASON (BR-SHL-025)
  // instead of being wired to a guess.
  // ══════════════════════════════════════════════════════════════════════════
  // THE TAB'S WORD, IN ONE PLACE — the strip, the head line AND the breadcrumb
  // ══════════════════════════════════════════════════════════════════════════
  // ⚠ **THREE SURFACES NOW NAME THE ACTIVE TAB AND THEY MUST NOT BE ABLE TO
  // DISAGREE.** `AccountsListPage`'s head reads `10 tabs · Move-outs`, the
  // breadcrumb reads `Accounts › Move-outs` and the strip has `Move-outs`
  // underlined — all three from `activeTab`, all three through this function.
  // A second spelling anywhere is the defect where the head says one tab and
  // the body renders another, which no test asserting `t(key)` on both sides
  // could ever catch (it would only prove the code agrees with itself).
  function tabLabel(id: AccountsTab): string {
    return t(ACCOUNTS_TAB_LABEL_KEYS[id], { defaultValue: ACCOUNTS_TAB_LABEL_EN[id] });
  }

  function tabPrimary(id: AccountsTab): {
    label: string;
    reason: string | null;
    onClick: () => void;
  } {
    switch (id) {
      case "requests":
        // S85 · `/requests/new`, the six-step capture page (verified mounted
        // in `App.tsx`). The standalone `/requests` screen draws this same
        // button in its OWN header; the embedded copy has none, so this is it.
        return {
          label: t("customers.serviceRequest.action.new"),
          reason: writeBlockedReason,
          onClick: () => navigate(tenantPath(SERVICE_REQUEST_NEW_ROUTE)),
        };
      case "new-connects":
        // S87 · `/connections/new`, nine steps, shipped 2026-08-25. This is
        // DEF-730's own line: the tab said the wizard was not built while the
        // route was live.
        return {
          label: t("customers.newConnects.action.new"),
          reason: writeBlockedReason,
          onClick: () => navigate(tenantPath(NEW_CONNECT_ROUTE)),
        };
      case "transfers":
        // S89 · `/transfers/new`. Its own tab CTA went live 2026-08-25.
        return {
          label: t("customers.transfers.action.new"),
          reason: writeBlockedReason,
          onClick: () => navigate(tenantPath(TRANSFER_WIZARD_ROUTE)),
        };
      case "disconnects":
        // S90 · `/disconnects/new`.
        return {
          label: t("customers.disconnects.action.new"),
          reason: writeBlockedReason,
          onClick: () => navigate(tenantPath(DISCONNECT_WIZARD_ROUTE)),
        };
      case "move-ins":
      case "move-outs":
        // ✅ **LIVE AS OF 2026-08-26, AND THE SUPERSEDED REASONING IS KEPT
        // BELOW BECAUSE IT IS WHY THIS TOOK A PO RULING TO FIX.**
        //
        // It read: *"Both wizards ARE built, and both are mounted ONLY at
        // `/accounts/:accountId/move-in|move-out`, because the ENDPOINTS are
        // account-scoped … There is no standalone route to send this header to
        // and no account selected in it, so a live button here would have to
        // GUESS which account you meant."* Every clause of that was TRUE when
        // it was written, and it is still true of the ENDPOINTS. What it got
        // wrong is the conclusion: the answer to "no account is selected" is a
        // first step that ASKS, not a disabled button — which is exactly what
        // `/transfers/new` and `/disconnects/new` already did, one tab over,
        // with the identical constraint.
        //
        // The PO read that sentence on the deployed build and overruled it:
        // *"Move-in and move-out stay disabled, on purpose: both wizards are
        // built, but a move-in creates the next occupant of a particular
        // account's unit and no account is chosen in that header. The live
        // control is on the account's own page and the button says so. -Enable
        // Move in /move out"*.
        //
        // Both wizards now mount standalone too, and each one's FIRST STEP is
        // the picker it always was — `MOVE_OUT_STEPS[0]` is "Find account" and
        // `MOVE_IN_STEPS[0]` is "Unit". Nothing guesses: move-out searches for
        // the account (the shared `AccountFinder`), move-in asks for the unit
        // and derives the outgoing account from it.
        //
        // ⚠ **THE LABEL IS THE HEADER'S OWN `Move-in` / `Move-out`, NOT THE
        // TAB'S `+ New move-in`.** Both exist: the tabs call
        // `customers.moveIns.action.new` for their empty-state CTA, with an
        // English `defaultValue` and NO catalogue row in any of the eleven
        // locales. Asking for them here would put a second literal key on this
        // screen that only English can answer — and G27 counts exactly that.
        // `customers.accounts.action.moveIn` is translated everywhere and is
        // the same vocabulary the two secondaries beside it already use, so a
        // clerk reads one word for one act. The divergence with the tab's own
        // CTA copy is REPORTED, and it closes the day those two keys land.
        return {
          label:
            // ⚠ **`CR-171-BRC10` P2.01 — THE MOVE-INS TAB SAYS `+ New move-in`**
            // (image 01). The note above borrowed the header's own `Move-in`
            // because the tab's key had no catalogue row; it has had one in
            // all eleven since, so the drawn words are used.
            id === "move-ins"
              ? t("customers.moveIns.action.new")
              : t("customers.accounts.action.moveOut"),
          reason: moveReason,
          onClick: id === "move-ins" ? openMoveIn : openMoveOut,
        };
      // ── CR-094-BRC01 wave G ────────────────────────────────────────────
      // Page 39 draws `+ Log a complaint` in the register's own header, and
      // page 47 the service equivalent. Each points at a route registered in
      // THIS COMMIT — landing a screen and landing the door that reaches it
      // are one act, and treating them as two is what shipped the customer
      // portal with two working doors out of eight (`DEF-CWP-3925`).
      case "complaints":
      case "services": {
        const spec = id === "complaints" ? COMPLAINT_INTAKE : SERVICE_INTAKE;
        return {
          label: t(spec.newActionKey),
          reason: writeBlockedReason,
          onClick: () => navigate(tenantPath(spec.route)),
        };
      }
      case "imports":
        return {
          label: t("customers.accounts.action.import"),
          reason: importReason,
          onClick: openImportAccounts,
        };
      case "accounts":
      default:
        // The S18 guided page (BR-CUS-018, six steps), which exists and posts
        // to `POST /accounts` — DISABLED here by `DEF-CUS-10049` (see
        // `newAccountReason`); the route itself is untouched.
        return {
          label: t("customers.accounts.action.new"),
          reason: newAccountReason,
          onClick: openNewAccount,
        };
    }
  }

  const config = accountsTableConfig(translate, {
    // The prototype's row opens S21, and S21 now exists (US-CUS-008) — so the
    // identity cell is a LINK to it. It was deliberately plain text until that
    // screen landed: a link onto a placeholder is the "built is not wired"
    // defect wearing a different hat.
    //
    // BR-CUS-068 — a MASTER account is an ordinary row with `kind='master'`, so
    // it arrives in this list mixed among the tenants' accounts and looks
    // exactly like one. The pill is the SERVER's own column rendered, in the
    // identity cell, because "who is this bill for" is the difference: a master
    // bills the owner for shared space and has no tenant behind it. Same shape
    // as the `Common` pill on every unit surface (BR-MET-101).
    accountNo: (row) => (
      <>
        <InlineLinkTo className="cus-id" to={tenantPath(accountDetailPath(row.id))}>
          {row.account_no ?? t("customers.account.noNumber")}
        </InlineLinkTo>
        {row.kind === ACCOUNT_KIND_MASTER && (
          <>
            {" "}
            <StatusPill tone="neutral">{t("customers.accounts.kind.master")}</StatusPill>
          </>
        )}
      </>
    ),
    // CR-030 W2 T2.9(b) — OUR number for the customer behind this account.
    // The cell lives in `accountsListCells.tsx` because B14 rule 21 makes new
    // UI Tailwind-only and this file is a pre-Route-B screen that G31 holds to
    // `customers.css`; same reason `AgeingCell` and `AccountServiceChips` do.
    customerNo: (row) => <CustomerNoCell row={row} t={translate} />,
    // BR-CUS-054's `customers` entity is unbuilt, so the server sends the
    // primary CONTACT's name; null means no contact has been recorded yet.
    //
    // ⚠ **NO `4 accounts` SUB-LINK, AND IT IS NOT COMING — CUT BY PO RULING
    // 2026-08-24, verbatim: *"okay dont link it"*.** B18 §5.1.2 put one here
    // (BR-CUS-054's shape). W2 task 2.5 is struck through with that ruling and
    // the two server halves it would have needed — a customer block on the row
    // and a `customer_id` in `ACCOUNT_FILTERS` — are not built either. The
    // customer is still reachable from this row: their NUMBER is the column two
    // cells to the left, and typing it into the search box returns every
    // account they hold, which is the capability the link was for.
    name: (row) =>
      row.name !== null ? <span>{row.name}</span> : <Dash>{t("customers.accounts.noName")}</Dash>,
    // Record links (PO 2026-10-19): the cell opens the UNIT it names, or — on a
    // master account that names no unit — the PREMISES. Plain text only when
    // the row carries neither id.
    premise: (row) => {
      if (row.premise === null) return <Dash />;
      const to =
        row.unit_id !== null && row.unit_id !== ""
          ? unitDetailPath(row.unit_id)
          : row.premises_id !== undefined && row.premises_id !== null && row.premises_id !== ""
            ? premisesDetailPath(row.premises_id)
            : null;
      return to === null ? <span>{row.premise}</span> : <InlineLinkTo to={tenantPath(to)}>{row.premise}</InlineLinkTo>;
    },
    // CR-030 W2 T2.6 — five squares then a `+N` square, never six wrapping.
    // See `accountsListCells.tsx` for why this is not metering's `ServiceTags`
    // (that one wraps, has no cap, and belongs to another lane today) and why
    // the letters still come from the ONE badge map.
    //
    // `kind` travels because an EMPTY cell means something different on a
    // master account (`DEF-CUS-6295`): the building has no services recorded,
    // not the account. `BR-CUS-1093` makes the row's list a read of the
    // premises, so the row that shows nothing is the row that names the
    // address.
    // `DEF-CUS-6917` — `services_unresolved` travels with the codes because a
    // short chip row and a complete one were the same picture: two chips means
    // *this account took two services* only when the server also says it lost
    // none. Passing it is the whole fix at this surface (hard-won law 2 — an
    // optional prop nothing passes is dead UI).
    services: (row) => (
      <AccountServiceChips
        services={row.services}
        kind={row.kind}
        unresolved={row.services_unresolved}
        t={translate}
      />
    ),
    // CLAUDE.md #2: the decimal STRING and its CHAR(3) code travel together
    // from the database to the pixel; nothing here parses or rounds one.
    balance: (row) =>
      // DEF-127 — the LEDGER's figure, with the CHAR(3) the ledger derived for
      // it. Null means the books could not be asked, and the awaiting cell
      // below says so rather than rendering a $0.00 nobody computed.
      //
      // ✅ **AND ITS NEIGHBOUR, DEF-628 / BR-CUS-510.** A `Pending activation`
      // row served `balance='0.000000'` with an EMPTY `balance_unavailable` —
      // the ledger was asked and answered nothing — so this cell rendered
      // `$0.00` on an account that cannot be billed yet. B18 §5.1.5 requires
      // *awaiting*. `balance_not_yet_billable` is the server's conjunction of
      // four clauses; this screen does not re-derive it, because the obvious
      // client-side guess (`status_behavior_class === "non_billable"`) would
      // ALSO hide the $612.75 owed by cut account `A-11488` (BR-CUS-107).
      // The order matters: unavailable first (a gap in the books), then
      // not-yet-billable (a real zero that is not an answer), then the figure.
      row.balance === null ? (
        <Dash />
      ) : row.balance_not_yet_billable ? (
        <AwaitsCell
          label={t("customers.accounts.balance.awaiting", { defaultValue: "Awaiting" })}
          why={t("customers.accounts.balance.awaitingWhy", {
            defaultValue:
              "This account cannot be billed yet, so nothing can be owed on it. It is not a settled balance.",
          })}
        />
      ) : (
        <MoneyCell amount={row.balance} currency={row.balance_currency ?? row.currency} />
      ),
    // Always absent today — see the file header. NOT a dash: a dash in a date
    // column reads as "never billed", which is a different claim.
    lastBill: (row) =>
      row.last_bill_at !== null ? (
        <DateCell value={row.last_bill_at} timeZone={timeZone} dateFormat={dateFormat} />
      ) : (
        <AwaitsCell
          label={t("customers.accounts.lastBill.awaiting")}
          why={t("customers.accounts.lastBill.awaitingWhy")}
        />
      ),
    // BR-CUS-016: the STORED status, and ONLY the stored status. The derived
    // ageing state that `[shot]` mixes into this cell now has a column of its
    // own (T2.3) — `Active` and `30d past` are answers to different questions
    // and a reader cannot see both when one cell holds one of them.
    status: (row) => (
      <StatusPill tone={accountStatusTone(row)}>
        {accountStatusLabel(row, translate)}
      </StatusPill>
    ),
    // BR-CUS-016 / BR-CUS-048 — derived, never stored; null renders `—` with
    // the server's own reason on hover, and never `Current`.
    ageing: (row) => <AgeingCell row={row} t={translate} />,
    // DEF-CUS-10180 — the shared AgeCell, through `AccountAgeCell`.
    accountAge: (row) => (
      <AccountAgeCell row={row} t={translate} timeZone={timeZone} dateFormat={dateFormat} />
    ),
    // BR-CUS-059: capture-only in v1 — the flag is stored and shown, and
    // nothing collects on it. Said once, in the awaiting panel below.
    autopay: (row) => (
      <span>
        {row.autopay ? t("customers.accounts.autopay.on") : t("customers.accounts.autopay.off")}
      </span>
    ),
    since: (row) =>
      row.opened_at !== null ? (
        <DateCell value={row.opened_at} timeZone={timeZone} dateFormat={dateFormat} />
      ) : (
        <Dash />
      ),
  }, categories.all);

  const state = parseTableParams(searchParams, config);
  // BR-SHL-011: the table's own params are serialized by the shared framework,
  // and the tab rides beside them. Written through ONE function so a sort or a
  // page change can never drop `?tab=` and silently bounce the user back to
  // the Accounts tab mid-task — AssetRegistryPage's `writeParams`, same reason.
  function writeParams(next: TableRequestState, nextTab: AccountsTab): void {
    const params = serializeTableParams(next, config);
    params.set(ACCOUNTS_TAB_PARAM, nextTab);
    setSearchParams(params, { replace: true });
  }
  function setState(next: TableRequestState): void {
    writeParams(next, activeTab);
  }
  function selectTab(next: AccountsTab): void {
    // A different tab is a different result set — the old page number is about
    // rows that are no longer on screen.
    writeParams({ ...state, page: 1 }, next);
  }

  const listKey = accountsQueryKey(serializeTableParams(state, config).toString());
  const listQuery = useQuery({
    queryKey: listKey,
    queryFn: () => getAccounts(accountsParamsFrom(state), client),
    // Only the Accounts tab reads the accounts list. The Imports tab draws its
    // own (`GET /imports`), and the six unbuilt tabs draw a sentence.
    enabled: isAccountsTab,
  });

  // ⚠ **THE SECOND `GET /accounts` IS GONE — PO ruling 2026-09-28.** CR-030 W2
  // T2.2 counted the `PENDING ACTIVATION` tile with a whole extra list read
  // (`f.status=pending_activation`, envelope `count`, rows discarded), and its
  // own exception line REPORTED the fix: *"a `rollup.pending_activation`
  // beside the two figures the roll-up already carries would pay for itself"*.
  // Four tiles built that way would have been four list reads. They are ONE
  // grouped count inside the roll-up this screen already fetches
  // (`selectors.account_status_counts`), so the strip now costs no request at
  // all.

  // ── THE BREADCRUMB LEAF · p117 / p131 draw `Accounts / <Tab>` ────────────
  //
  // ⚠ **IT IS PUBLISHED, NOT DRAWN HERE.** The crumb lives in the topbar, two
  // components up, and `breadcrumbFor` resolves it from the PATHNAME alone —
  // correctly, because US-SHL-002 TC-3 says query params never move the
  // breadcrumb and this tab rides in `?tab=`. `components/crumbLeaf.ts` is the
  // shell capability `DEF-374` has carried OPEN since 2026-08-21 and whose own
  // fix_suggestion asks for exactly this shape; `breadcrumbFor`'s comment had
  // promised the leaf was *"the consuming detail screen's to supply"* and
  // nothing was ever built for it (hard-won law 1).
  //
  // ⚠ **THE ACCOUNTS TAB PUBLISHES NOTHING, AND THAT IS THE RIGHT ANSWER.**
  // The module crumb already reads `Accounts`; a leaf here would render
  // `Accounts › Accounts`. A tab that is the module's own default has no
  // sub-context, and an empty crumb is a different claim from no crumb.
  //
  // ⚠ **A HOOK, SO IT SITS ABOVE THE TWO EARLY RETURNS BELOW.** Moving it down
  // beside the header it belongs to would put a hook after a conditional
  // return and React would refuse the render on the denied path.
  useCrumbLeaf(isAccountsTab ? null : tabLabel(activeTab));

  // ── `CR-125-BRC07` — THE HEAD'S OPEN-CASE FRAGMENT ────────────────────────
  // The head is this component's and the figure is a tab's, so the tab hands it
  // up (`DisconnectsTab.onOpenCaseCount`) and nothing is derived twice.
  // `undefined` is the honest starting value and the only one: it means *no tab
  // has told us*, which is a different fact from *zero are open* and prints a
  // different line. Reset the moment the tab changes, so a count published by
  // Disconnects can never be read under the word `Move-outs`.
  //
  // ⚠ **HOOKS, SO THEY SIT ABOVE THE TWO EARLY RETURNS BELOW** — exactly what
  // `useCrumbLeaf` says one line up, and the first draft of this pair ignored
  // it and put them after `const rows = …`. `eslint`'s `rules-of-hooks` caught
  // it; the browser walk did not, because the denied path is the one that
  // breaks and a System Admin never takes it.
  const [openCaseCount, setOpenCaseCount] = useState<number | undefined>(undefined);
  useEffect(() => {
    setOpenCaseCount(undefined);
  }, [activeTab]);

  if (isDenied(cell)) {
    // BR-SHL-003 / A18 §6: a surface this role cannot reach is not drawn.
    return (
      <PermissionDenied
        helper={t("customers.accounts.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }
  if (listQuery.data === undefined && listQuery.isError && isPermissionDenied(listQuery.error)) {
    return (
      <PermissionDenied
        helper={t("customers.accounts.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }

  const rows = listQuery.data?.results ?? [];

  return (
    <div className="cus-page">
      {/* US-SHL-020 / BR-SHL-044: this screen DECLARES a header, it does not
          draw one. The prototype's accounts head is an H1 plus its page actions
          — no kicker.
          ⚠ IT HAS A TAB STRIP AS OF CR-030 W1 (2026-08-24), and EIGHT TABS as
          of W2. B18 §4 gives the page the eight; two have a body and six state
          what they are waiting for (see ACCOUNTS_ABSENT_TABS).
          ⚠ AND NO `rollup` PROP: B18 §5.1.1's KPI strip replaced the `.sub`
          line, and it renders below the header, the same place the Assets
          registry and the Reads list put theirs. */}
      <PageHeader
        // ── THE HEAD, BUILT FROM THE DRAWING · `DEF-CUS-5939` ──────────────
        //
        // The Accounts blueprint draws THIS head four times — p117 Move-outs,
        // p131 Transfers, p41 Complaints, p48 Services — and all four agree:
        // an `ACCOUNTS` kicker, the title **The register**, a `10 tabs ·
        // <Tab> · N open` sub-line, a breadcrumb reaching `Accounts / <Tab>`,
        // a tab strip with NO count, and a quiet text action top right. Read
        // AS IMAGES (B14 rule 42) at scale 6; the text layer carries none of
        // the four sub-lines, which is rule 42's own point.
        //
        // ⚠ **ONE HEAD SERVES TEN TABS, WHICH IS WHY THIS TOOK ITS OWN LANE.**
        // The Move-outs lane wrote the five missing strings into its own
        // exceptions line on 2026-09-19 and deferred, in its words, because
        // *"retitling it from a Move-outs lane would rename the page under
        // nine siblings"*; the Transfers lane deferred the same way. Both
        // were right, and neither filed a row, so nothing counted it.
        //
        // ⚠ **THE KICKER IS ITS OWN KEY AND NOT THE TITLE'S.** They were the
        // same word until this commit and they are now different facts: the
        // kicker names the MODULE you are in (and matches the breadcrumb's
        // ancestor), the title names the SCREEN.
        kicker={t("customers.accounts.head.kicker")}
        // ⚠ **`CR-171-BRC10` P2.01 — THE MOVE-INS TAB IS TITLED `Move-ins`
        // AND CARRIES NO SUB-LINE** (image 01: kicker `ACCOUNTS`, title
        // `Move-ins`, the tabs, nothing between). Every other tab keeps the
        // register's head until its own redesign arrives.
        title={
          activeTab === "move-ins"
            ? t("customers.moveIns.head.title")
            : t("customers.accounts.head.title")
        }
        // ⚠ **`customers.accounts.title` IS UNTOUCHED AND STILL READS
        // `Accounts`** — five other screens use it as their `← back` LABEL
        // (`AccountDetailPage`, `NewAccountWizard`, `NewConnectWizard`,
        // `MoveInWizard`, `MoveOutWizard`), and p117's second figure draws
        // that control as `← The register`. Changing one key's value would
        // have renamed a control on five screens, four of them under a live
        // lane, on this lane's authority. REPORTED as `DEF-CUS-5952` instead.
        //
        // ── THE SUB-LINE ──────────────────────────────────────────────────
        // ⚠ **TWO FRAGMENTS, NOT THE DRAWING'S THREE, AND THE THIRD IS
        // OMITTED RATHER THAN ZEROED.** The drawings read `10 tabs ·
        // Move-outs · 1 still open`, `… · 3 open` and `… · 4 open, 1 past
        // due` — the figures are illustrations (B14 rule 37) and the SHAPE
        // all four agree on is `<N> open`. **No tab can honestly supply that
        // number to this head today.** Every tab body owns its own query and
        // its OPEN tile rides INSIDE that query's envelope, keyed by table
        // state the tab holds in its own `useState` (`MoveOutsTab`'s
        // `moveOutsQueryKey(state)` is the shape). A second read from here
        // would be a second definition of *open* on the same screen — which
        // is the hazard the PO ruled on for the Move-outs tile on
        // 2026-09-19, choosing **A, leave it**, because a figure that
        // contradicts its own caption is worse than a missing one. And a `0`
        // is a claim, not an absence. `DEF-CUS-5953` carries the fragment and
        // names what it needs: each tab publishing its SERVED `kpis.open` to
        // the head, the way this screen publishes its breadcrumb leaf.
        //
        // ONE key with two interpolations, never two translated fragments
        // either side of a number (B8).
        // ⚠ **THE THIRD FRAGMENT IS BACK — `CR-125-BRC07`, 2026-09-20, AND IT
        // CLOSES `DEF-CUS-5953` FOR ONE TAB OF TEN.** The comment above records
        // why it was omitted: no tab could honestly supply the number, and a
        // `0` is a claim rather than an absence. The Disconnects tab can now —
        // `GET /disconnects` serves `open_case_count`, computed once by the
        // same pass that counts the tiles — so it hands the figure up and this
        // head prints it. The other nine publish nothing and still render the
        // two-fragment line, unchanged, which is why `DEF-CUS-5953` stays open.
        //
        // ⚠ **TWO KEYS, NOT A CONCATENATION (B8).** One whole sentence per
        // form, each with all its interpolations; never a translated fragment
        // glued either side of a number. The plural is i18next's, so a
        // catalogue whose language counts differently is not forced into
        // English's two forms.
        rollup={
          activeTab === "move-ins"
            ? undefined
            : openCaseCount === undefined
            ? t("customers.accounts.head.tabLine", {
                tabs: ACCOUNTS_TAB_IDS.length,
                tab: tabLabel(activeTab),
              })
            : t("customers.accounts.head.tabLineOpen", {
                count: openCaseCount,
                tabs: ACCOUNTS_TAB_IDS.length,
                tab: tabLabel(activeTab),
              })
        }
        secondaryActions={
          !isAccountsTab ? undefined : (
            <>
              {/* The prototype's Move-out / Move-in actions. ⚠ LIVE AS OF
                  2026-08-26 (PO ruling). They were disabled from 2026-08-11 on
                  the argument that both ENDPOINTS are account-scoped and this
                  header has no row selected — true of the endpoints, wrong
                  about the screen: the answer to "no account is selected" is a
                  first step that asks. `/move-outs/new` and `/move-ins/new`
                  mount the same two wizards with an empty first step, exactly
                  as `/transfers/new` and `/disconnects/new` already did under
                  the identical constraint. See `tabPrimary` for the ruling
                  verbatim and for the superseded reasoning. */}
              <GuardedButton
                label={t("customers.accounts.action.moveOut")}
                reason={moveReason}
                onClick={openMoveOut}
              />
              <GuardedButton
                label={t("customers.accounts.action.moveIn")}
                reason={moveReason}
                onClick={openMoveIn}
              />
            </>
          )
        }
        // CR-030 W2 T2.8 / BR-SHL-044 (a): the primary slot is per-TAB and the
        // SAME slot relabels as the user moves across — "+ New account" on
        // Accounts, "↑ New import" on Imports. Exactly one primary renders on
        // either, and the six unbuilt tabs declare NONE: a primary action over
        // a body that says "not built yet" is a button onto nothing, which is
        // the "built is not wired" defect with a label on it.
        //
        // ⚠ **`Export` IS NOT RENDERED AS THE SECONDARY B18 §5.1 ASKS FOR, AND
        // THAT IS BR-SHL-010 RATHER THAN AN OMISSION.** `POST /exports`
        // resolves a registry that metering, assets, rating and reports
        // populate; `apps/customers/` has no `exports.py` and registers no
        // `accounts` resource, so there is nothing for the button to call. The
        // rule says a capability that is not declared does not render, and this
        // screen has applied it to Export since it was written. It is REPORTED
        // as owed rather than drawn disabled: BR-SHL-025's disabled-with-reason
        // is for a control this ROLE cannot use (Move-in/Move-out above), not
        // for one the PRODUCT does not have.
        tabs={ACCOUNTS_TAB_IDS.map((id) => ({
          id,
          // ⚠ **NO COUNT ON THE STRIP — `DEF-CUS-5939`.** It read `Accounts
          // 82` for one tab out of ten, from `listQuery.data.count`, which is
          // the count of rows matching the CURRENT filters rather than a
          // tenant total: type a search and the tab's own number moved. None
          // of the four drawn frames carries a count on any tab, and one
          // number beside one word out of ten reads as a fact about that tab
          // rather than about the filter a clerk just typed. The figure is not
          // lost — the pager below the table states `1–N of M` for whatever is
          // on screen, which is the honest place for it.
          label: tabLabel(id),
          explainer:
            // B18 §5.9.4's lede, verbatim, on the tab it belongs to.
            id === "imports" ? t("customers.imports.lede") : undefined,
          // DEF-729 / DEF-730 — EVERY tab's create action, in the ONE slot.
          // Read `tabPrimary` for why this is a relabelling slot rather than
          // six buttons, and for the two entries that are deliberately
          // disabled.
          primaryAction: (
            // ⚠ **`primary`, AND THE `ghost` REASONING BELOW IS SUPERSEDED BY
            // THE PO LOOKING AT THE RUNNING SCREEN — 2026-09-22 (`DEF-CUS`
            // item 1).** They reported `+ New request` on this tab as *red
            // TEXT, not a button*, and it is the page's only header action. A
            // ruling made against the deployed product outranks a lane's
            // reading of a drawing, so the tier moves and the supersession is
            // STATED here rather than assumed (hard-won law 13).
            //
            // ⛔ **THE SUPERSEDED NOTE, KEPT, BECAUSE IT IS WHY THIS WAS EVER
            // `ghost`:** *"THE FOUR DRAWN FRAMES ALL DRAW A QUIET TEXT
            // CONTROL. `+ New move-out` (p117), `+ New transfer` (p131), `+
            // Log a complaint` (p41) and `+ Request a service` (p48) are each
            // plain words top right: no fill, no border, no underline. The
            // filled accent button was the loudest thing on a screen whose
            // Transfers tab holds two rows and whose Move-ins tab can hold
            // none at all."* Every clause of that is still TRUE OF THE
            // DRAWINGS. What it got wrong is the conclusion: a quiet text
            // control is the one thing on this page a clerk cannot find, and
            // the PO could not find it. Recorded as a divergence from those
            // four frames rather than a correction of them.
            //
            // ⚠ **IT IS STILL THE ONE HEADER ACTION AND STILL PER-TAB.**
            // `PageHeader` renders `active.primaryAction` and nothing else, so
            // exactly ONE primary is on the page whatever the tab —
            // BR-SHL-044's *status → secondaries → ONE primary* is HONOURED by
            // this change rather than strained by it, where `ghost` satisfied
            // the cap and left the slot invisible. B14 rule 4's `+ Noun`
            // grammar is untouched: this is a TIER change and nothing else.
            //
            // ⚠ **THE SLOT IS SHARED BY ALL TEN TABS, SO THIS MOVES ALL TEN,
            // AND THAT IS THE INTENT.** One relabelling slot is what stops ten
            // tabs acquiring ten button styles; a tier that varied per tab
            // would be exactly that. The entries with no route still render
            // DISABLED WITH THEIR REASON (BR-SHL-025) — `GuardedButton`
            // decides that, not the tier.
            <GuardedButton
              label={tabPrimary(id).label}
              reason={tabPrimary(id).reason}
              variant="primary"
              onClick={tabPrimary(id).onClick}
            />
          ),
        }))}
        activeTabId={activeTab}
        tabsLabel={t("customers.accounts.tabsLabel")}
        onTabSelect={(next) => selectTab(accountsTabFromParam(next.id))}
      />

      {/* S81 — the run-history tab replaces the accounts body; the shared page
          head above is untouched (one head, eight tabs — B18 §4's skeleton). */}
      {isImportsTab && (
        <AccountImportsTab
          writeBlockedReason={importReason}
          onImport={openImportAccounts}
          client={client}
        />
      )}

      {/* CR-030 W2 T2.1 — the six tabs B18 §4 gives the page and W4–W7 build.
          ⚠ THIS IS NOT AN EMPTY TABLE, ON PURPOSE. The shared empty state says
          "nothing here yet", which is a statement about THIS UTILITY'S DATA —
          and it would be false on every one of these six, because the product
          cannot hold a request, a connection, a move-in, a transfer or a
          disconnect at all. The copy names the WORK, never the wave id: a clerk
          at a two-person utility can do nothing with "W6" (DEF-332).

          ⚠ SIX ELEMENTS, WRITTEN OUT, AND `tracks` A LITERAL IN EVERY ONE.
          A `tracks={map[tab].tracks}` reads identically to a human and is
          INVISIBLE to G38, whose whole job is to find a stated absence that
          cites nothing — it matches a quoted id and nothing else, deliberately,
          because an id assembled at runtime is not greppable when the row it
          names finally closes. The first draft of this block was the map, the
          gate counted all six as untracked, and this is that gate biting.

          The id on each is the open question B18 §12.1 maps to that tab's own
          wave — never a wave number, which can never "close" and so could
          outlive its reason forever (DEF-445). */}
      {activeTab === "requests" && (
        // ✅ **CR-035 · AMENDMENT 1 (PO 2026-08-26) — THIS TAB NEEDED NOTHING,
        // AND THAT IS THE EVIDENCE THE RULING WAS RIGHT.** The PO's sentence
        // groups Requests with the five wizard flows, but a parked service
        // request is a DIFFERENT THING: it is the same numbered row, annotated,
        // because `park()`/`unpark()` write `waiting_on`, `park_note`,
        // `remind_on`, `parked_at` and `parked_by` as COLUMNS on
        // `customers.ServiceRequest`. `ServiceRequestsListPage` has rendered a
        // `waiting_on` column, default-visible, since it was built (B19 §12.2 —
        // park *"moves no state"*). So nothing extra is drawn here: there is no
        // FK-less draft to fold in, and a second surface for a fact already on
        // the row is exactly what the separate tab was.
        //
        // ⚠ **THIS PARAGRAPH IS NOW THE GENERAL RULE RATHER THAN THE EXCEPTION
        // (`DEF-CUS-5994`, 2026-09-20).** It read *"So no `ParkedDraftsPanel`
        // here"* while five of those panels stood below it, and the PO has
        // since ruled them all away: *"remove it - it is anyway in the list so
        // we dont need it sepretely - if it is not in list add it"*. What was
        // true of the Requests tab from the start — the draft is the same row,
        // annotated — is now true of all five flows, each list having widened
        // its own window to `wizard_parks`.
        //
        // ✅ DEF-664 CLOSED 2026-08-25 — the list itself, not a note about it.
        //
        // The two earlier shapes are worth remembering because each was true
        // when written and each was still wrong to show a user. First this tab
        // said *"the request itself is still being designed"* — false the day W4
        // shipped (DEF-664's original). Then it said the list *"is still to
        // come"* with a button to `/requests` — true, and the PO still hit it in
        // production with their own request sitting on the other side of that
        // button. **A panel describing a surface is not the surface.**
        //
        // ⚠ THE STATED BLOCKER WAS REAL AND IT IS SIDESTEPPED, NOT SOLVED.
        // DEF-664 recorded that embedding was not a one-line job because this
        // page and `ServiceRequestsListPage` BOTH serialise table state into the
        // SAME query string, so each one's `?page=`/`?sort=` overwrites the
        // other's on the next `setParams(..., {replace: true})`. That is still
        // exactly true — and it does not apply here, because `urlState={false}`
        // means the embedded copy neither WRITES nor READS the query string. It
        // keeps page, per, sort and search in component state.
        //
        // The read half matters as much as the write half: without it the tab
        // would open on the ACCOUNTS list's `?page=3&q=smith` and show a page of
        // requests nobody asked for.
        //
        // So no URL grammar is decided here. BR-SHL-011 is untouched and
        // `/requests` keeps its shareable links byte-for-byte.
        <ServiceRequestsListPage {...props} urlState={false} />
      )}
      {activeTab === "new-connects" && (
        // ✅ THE LIST, NOT A NOTE ABOUT THE LIST — CR-030 W6 task 6.12, S86
        // `NCT-01`. `connection_reads.py` landed with its own trailer saying
        // *"the Accounts 'New connects' tab still renders its placeholder and
        // NOTHING CALLS THIS ENDPOINT YET"*; this is the call.
        //
        // ⚠ FOUR OF THE FIVE SEGMENTS ARE OFF AND THE TAB SAYS WHY. OQ-371 is
        // OPEN — a build can be `partly_activated` AND waiting at the same
        // time, and which exclusive segment holds it is unruled — so the server
        // serves `all` and the strip disables the rest with the reason.
        //
        // ⚠ AND IT SAYS `activated`, NOT `energised` (CR-032, PO 2026-08-25).
        <NewConnectsTab {...props} />
      )}
      {activeTab === "move-ins" && (
        // ✅ THE LIST — CR-030 W5. There is no `move_ins` table: a move-in is
        // the LIFE OF A BR-CUS-018 DRAFT ACCOUNT, from the day it is booked in
        // to the day `activate_account` opens it. Which is this tab's own
        // former placeholder sentence, derived from the data instead of
        // promised.
        //
        // ⚠ THE DEPOSIT CELL NEVER SAYS `waived`. B18 draws five DEPOSIT
        // sentences and no column records which applies (BR-CUS-023 — the
        // deposit is a lookup), so a zero renders the reason. A deposit nobody
        // recorded and a deposit deliberately waived are different facts.
        <MoveInsTab {...props} />
      )}
      {activeTab === "move-outs" && (
        // ✅ THE LIST — CR-030 W5, the last of the eight tabs.
        //
        // ⚠ **OQ-346 IS CLOSED (→ BR-CUS-082, PO 2026-08-24)**, so the panel
        // that stood here was tracking a question that no longer existed.
        //
        // ⚠ NO SETTLEMENT VERDICT IS RENDERED ON ANY ROW — not `SHORT`, not
        // `settles exactly`. `MoveOutSettlement.landing`'s own rule is that any
        // gap means no landing, and both gaps are open on every row: billing
        // publishes no per-account final bill and BR-CUS-057's interest accrual
        // is unbuilt. A guessed landing feeds §5.6.4's four-way decision.
        <MoveOutsTab {...props} />
      )}
      {activeTab === "transfers" && (
        // ✅ THE LIST — CR-030 W7 task 7.4, S89. One job, not a move-out
        // followed by a move-in, and the tab draws §5.7.3's counting contract
        // as the callout it is drawn as.
        //
        // ⚠ NO MONEY MOVES AND THE CELL SAYS SO. A `MONEY` line whose figure
        // cannot be read renders the reason, never `$0.00` and never the
        // principal — reading BR-CUS-057's unwired interest as zero serves
        // $150.00 where $153.50 is held (❄️ WE-7 / GT-23).
        <TransfersTab {...props} />
      )}
      {activeTab === "disconnects" && (
        // ✅ THE LIST — CR-030 W7 task 7.11, S90. The ladder, its protections,
        // the cut and the reconnect.
        //
        // ⚠ FIVE OF THE SIX SEGMENTS ARE OFF (OQ-374) and `LAST NOTICE` renders
        // NO DELIVERY CLAIM: there is no email, SMS or print adapter in this
        // release, so `emailed` / `posted` / `certified sent` / `certified
        // signed` appear nowhere on the tab (TC-DSC-6).
        <DisconnectsTab {...props} onOpenCaseCount={setOpenCaseCount} />
      )}

      {/* ── CR-094-BRC01 wave G · THE TWO NEW QUEUES ──────────────────────
          ONE component, two configurations — the only difference between them
          is which `work_order_types` HEADING each stands on and which words it
          uses. PO standing instruction of 2026-09-12: *"Do all changes bsed on
          actual code - also dont create duplcate code"*.

          ⚠ **NO PARKED DRAFTS ON EITHER, AND THE REASON OUTLIVED THE
          PANEL.** `CR-035` · AMENDMENT 1 puts a parked draft on the tab for
          its own KIND of work, and the park store's flows are the five wizards
          that have one. Neither of these forms parks: both write once at the
          last step and nothing before it (`BR-MET-112`'s shape), so there is
          no draft to show. **This said `ParkedDraftsPanel` until 2026-09-20**,
          when the PO removed that panel from all five flows
          (`DEF-CUS-5994`) — the conclusion did not change, only the thing it
          names. A queue here would be empty for ever, which is dead UI with a
          reason attached rather than a reason not to build it. */}
      {activeTab === "complaints" && (
        <JobQueueTab
          {...props}
          spec={COMPLAINT_INTAKE}
          onNew={() => navigate(tenantPath(COMPLAINT_INTAKE.route))}
          newReason={writeBlockedReason}
        />
      )}
      {activeTab === "services" && (
        <JobQueueTab
          {...props}
          spec={SERVICE_INTAKE}
          onNew={() => navigate(tenantPath(SERVICE_INTAKE.route))}
          newReason={writeBlockedReason}
        />
      )}

      {isAccountsTab && (
        <>

      {/* PO ruling 2026-09-28 — FOUR tiles, one per account status, and each
          one SETS the list's filter when pressed. `accountsKpis` holds the
          four and its docstring holds the reasons; `accountsStateAfterTilePress`
          is the toggle, written once so the tile and the filter chip can never
          hold two answers. */}
      <KPIStrip
        label={t("customers.accounts.kpi.statusGroup")}
        kpis={accountsKpis({
          byStatus: listQuery.data?.rollup?.by_status,
          applied: state.filters[ACCOUNT_STATUS_FILTER],
          onToggle: (code) => setState(accountsStateAfterTilePress(state, code)),
          t: translate,
        })}
        loading={listQuery.isPending}
      />

      <DataTable<AccountRowWithAgeing>
        config={config}
        state={state}
        onStateChange={setState}
        rows={rows}
        totalRows={listQuery.data?.count ?? null}
        loading={listQuery.isPending}
        error={
          listQuery.isError && listQuery.data === undefined
            ? {
                reason: apiErrorText(listQuery.error, translate),
                onRetry: () => void listQuery.refetch(),
              }
            : null
        }
        filterBarSlot={
          <FilterBar filters={config.filters ?? []} state={state} onStateChange={setState} />
        }
        // ⚠ THE DOWNLOAD EXISTS SINCE 2026-10-17 (DEF-CUS-10180). This read
        // "No `downloadSlot`: `/exports` registers no `accounts` resource" —
        // true until the PO put Account age *"in the download"*;
        // `apps/customers/exports.py` registers it now, with Opened, Account
        // age and Aging. The shared control posts THIS list's state.
        downloadSlot={<ListExportButton resource="accounts" state={state} client={client} />}
        empty={{
          title: t("customers.accounts.emptyTitle"),
          helper: t("customers.accounts.emptyHelper"),
          ctaLabel: t("customers.accounts.action.new"),
          // The empty state's CTA is the same wizard as the header's, so it
          // carries the same reason and the same gating.
          ctaReason: newAccountReason,
          onCta: openNewAccount,
        }}
      />

      {/* ⚠ THE TWO "WAITING ON …" PANELS ARE DELETED — PO ruling 2026-08-24,
          made while walking the DEPLOYED v2.42.0: *"on account tab - im seeing
          these two boxes - are they required?"*, then **"Delete both boxes
          entirely"**.

          They were not wrong, and that is worth recording rather than
          pretending they were. Hard-won law 2 asks a screen to say why a thing
          is blank instead of silently omitting it, and both sentences were TRUE
          when re-read against the code that morning. What the ruling settles is
          FORM, not honesty: two grey paragraphs about our own build state, at
          the bottom of the list a clerk uses all day, is developer-facing text
          on an operator's screen.

          Sorted by whether a user is actually confused, which is what was put
          to the PO: the ageing dash and the uncounted 60+ tile ARE visible and
          were offered a home beside the column and the tile; the missing plan
          column and the missing CSV route are invisible absences — nobody
          misses a control they have never seen — and were proposed for
          deletion outright.

          ⚠ ONE SENTENCE IN THE SECOND PANEL WAS NOT LIKE THE OTHERS, AND
          DELETING IT LOSES SOMETHING REAL: *"autopay is recorded here but
          nothing collects on it in this version"*. Verified in
          `apps/payments/models.py:623` — *"what autopay IS in v1: a promise
          recorded, never a charge"*. A staff member can switch autopay on for a
          customer and reasonably believe money will now be taken; it will not
          be, and after this deletion the product says so NOWHERE. That was
          stated in the option the PO chose, so the box goes as ruled — and the
          trap is filed as DEF-644 rather than quietly leaving with the box.

          G38 is unaffected: it checks that a stated absence cites the row that
          will kill it, never that the screen must carry one. */}
        </>
      )}
    </div>
  );
}

export default AccountsListPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-CUS-001@a2e1d59 (story+rules snapshot — EP-CUS-01 lead story; co-packets US-CUS-002 same epic · customers 02-business-rules@f125a9c)
// generated: 2026-08-10 by story-coder (W2 customers FRONTEND lane — S17, the screen the `customers` backend slice landed without) · AMENDED 2026-08-11 by story-coder (W2 customers FRONTEND lane 2 — S18/S21 landed, so the account number is a link to the detail and "+ New account" opens the guided page) · AMENDED 2026-08-24 by the CR-030 W1 lane (T1.10: the page DECLARES a tab strip — Accounts · Imports (S81) — mounting AccountImportsTab on `?tab=imports`, the literal `returnTo` the accounts workflow kind carries; the accounts list query is disabled on the Imports tab and the roll-up, Move-in and Move-out are Accounts-tab-only. T1.11: the `↑` import button LEAVES the header's secondary row (B18 §5.9.2 row 7) and becomes the Imports tab's ONE primary — same key `customers.accounts.action.import`, relabelled to "↑ New import" in all eleven catalogues) · AMENDED 2026-08-24 by the CR-030 W2 FRONTEND lane (T2.1 the strip grows to B18 §4's EIGHT tabs, six of them stating their absence with a tracked id rather than drawing an empty table · T2.2 the `.sub` roll-up line becomes the shared five-tile KPIStrip, with PAST DUE 60+ and CLOSED THIS YEAR as honest absences and PENDING ACTIVATION counted through a second `f.status=` read · T2.3 `AGEING` splits off `STATUS` as its own column over the served `ageing_segment` · T2.5 NOT BUILT — no served customer block on a row · T2.6 the service cell caps at five squares plus a `+N` · T2.7 the shared column selector already ships on every list, so declaring the column was the work · T2.8 the per-tab primary relabels and the unbuilt tabs declare none · T2.9 the search prompt names the four things the server really matches and not `customer #`) · AMENDED 2026-08-24 by the CR-030 W2 CLOSE-OUT lane (L2) — the two W2 tasks the frontend lane could not finish, both now settled by PO ruling of the same day. T2.5 the `4 accounts` customer sub-link is CUT (*"okay dont link it"*) and `TC-ACC-3` closes as WON'T BUILD rather than staying an `it.todo` that reads as work owed. T2.9 all three pieces land in ONE commit and in B18's own order — (a) `selectors.account_list` ORs `_account_ids_by_customer_no` into the same group as `account_no`, (b) this file declares a `CUSTOMER #` column over the newly-served `customer_no` field, rendered by `accountsListCells.CustomerNoCell`, (c) only then does the prompt name it. BR-CUS-053 was AMENDED for this on 2026-08-24 and BR-CUS-015 is amended with it)
// amended: 2026-08-26 by lane MOVEENTRY — **PO ruling**, verbatim: *"Move-in and
//         move-out stay disabled, on purpose: both wizards are built, but a
//         move-in creates the next occupant of a particular account's unit and
//         no account is chosen in that header. The live control is on the
//         account's own page and the button says so. -Enable Move in /move
//         out"*. The last two disabled controls on this page go LIVE — the
//         `move-ins`/`move-outs` tab primary and the two Accounts-tab
//         secondaries — pointing at `/move-ins/new` and `/move-outs/new`, both
//         verified mounted in `App.tsx`. Exactly-one-primary is unchanged
//         (B14 rule 4 / BR-SHL-044): the slot still relabels, it does not
//         multiply. ⚠ `customers.accounts.action.moveBlocked` is no longer asked
//         for by anything; it is REPORTED for retirement from all eleven
//         catalogues in `scratchpad/newkeys-MOVEENTRY.json`.
// amended: 2026-09-28 by lane CUS-TILES — **PO ruling of that date**, given as
//         a table: the KPI strip becomes **FOUR** tiles, one word each —
//         **Active** *(billing normally)* · **Pending** *(no bill can be
//         raised)* · **Disconnecting** *(still consuming)* · **Suspended**
//         *(base charges only)* — and *"each tile SETS the list's filter when
//         pressed, through the same state the FilterBar reads"*. `BR-CUS-1105`.
//         Dropped: `Accounts 79`, `Outstanding`, `Past-due 60+`, `Closed this
//         year`. ⚠ **`Outstanding` WORKED AND IS GONE ANYWAY** — this screen
//         now states no tenant-wide receivable at all; the BALANCE column
//         answers for one account and Finance's Revenue & AR answers for the
//         utility. ⚠ **`Past-due 60+` and `Closed this year` NEVER COUNTED
//         ANYTHING** and are `DEF-CUS-7700`; the suite asserted their
//         placeholder, which is that row's escape reason. The second
//         `GET /accounts` that counted the pending tile is DELETED — all four
//         counts ride in the roll-up this screen already fetches.
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest 622 passed / 148 todo across 47 files✔ (604 passed / 142 todo across 46 files was the pre-lane baseline — the suite grew by 18 passing + 6 todo and nothing was dropped) · vite build✔ · run_gates 14 PASS · 0 FAIL · 1 SKIP✔ (G13 unwired-props, G14 prototype-conformance and G15 i18n-parity included) · [S18/S21 lane 2026-08-11] tsc✔ · eslint --max-warnings 0✔ · vitest 670 passed / 160 todo across 49 files✔ (622 passed / 148 todo across 47 files was the pre-lane baseline) · vite build✔ · run_gates 14 PASS · 0 FAIL · 1 SKIP✔ · [CR-030 W2 2026-08-24] tsc✔ · eslint --max-warnings 0✔ · vitest AccountsPage.test.tsx 35 passed / 11 todo✔ · routeBUtilities.test.ts 9/9✔ · g31 0 undeclared at the baseline of 0✔ · g38 74 untracked at the baseline of 74 (22 tracked, up from 16 — the six new tab notes)✔ · g13/g29/g37/g40 PASS✔
// exceptions: [CR-030 W1 2026-08-24] E2 the file header's "no tab strip" note is AMENDED rather than left standing — hard-won law 1: a comment describing the screen is not the screen · E3 the strip carries TWO of `[shot: ACC-01]`'s eight tabs; the other six (Requests · New Connect · Move-ins · Move-outs · Transfers · Disconnects) are W4–W7's and a tab label with no body behind it is hard-won law 2 · E2 `↑ New import` renders as the Imports tab's PRIMARY, not twice as `[shot]` draws it — B18 §5.9.4 rules that explicitly ("build one, in the page header") because two primaries break B14 rule 4 / BR-SHL-044 · E3 the page-header roll-up and the Move-in/Move-out secondaries are ACCOUNTS-TAB ONLY: the roll-up counts accounts and the list read is disabled on the Imports tab, so it would render a line of dashes · E3 the S17 header pin in AccountsPage.test.tsx (`expect(html).not.toContain("page-header-tabs")`) is now FALSE BY RULING and is REPORTED, not edited — that file is outside this lane's write scope · E3 the prototype's Status column carries a DERIVED aging pill (Current / 30d past / 60+ past); `aging` is served null until billing's `invoices` lands (W3), so this column shows the STORED status only and the gap is named in the awaiting panel — no null is ever turned into "Current" · E3 "Last bill" renders "Awaits billing" with its reason instead of "—": a dash in a date column reads as "never billed", a different claim · E3 the roll-up's `past_due_60_plus` is null and renders as awaiting, never 0 · E3 the prototype's "+Plan" column and the BR-CUS-053 `plan` FILTER are both absent — BR-CUS-029's `account_plan_assignments` has no DDL in any signed document, and the unit's plan is NOT substituted (BR-CUS-010: the two diverge at the first override) · E3 the four prototype status SEGMENTS (All/Current/Past due/Closed) are not rendered: only All and Closed are answerable without invoices and a half-implemented segment set is worse than none (the backend packet reported the same) · E3 no CSV export control: `POST /exports` registers no `accounts` resource, so BR-SHL-010 keeps the capability unrendered · E2 [2026-08-11] the account # became a LINK to S21 and "+ New account" a navigation to S18 — both were disabled/plain until those screens existed. "Move-in" and "Move-out" still render DISABLED WITH THEIR REASON: the move-in/move-out routes are deliberately unstubbed server-side (BR-CUS-030 — closing is US-CUS-005's flow) · E2 [2026-08-11 lane 3] S19/S20 exist now, and Move-in/Move-out STILL render disabled here — both endpoints act on ONE account and this header has no row selected, so the reason was rewritten to name that (it no longer claims the pages are unbuilt). The live controls are on the account's own page · E4 `last_bill` is in the server's sort set and is declared NOT sortable here, because every value is null and a sort control would offer an ordering that does not exist · E4 the service tags reuse metering's `ServiceTags` and its `metering.service.*` keys: the service catalog is platform-level (BR-TEN-025) and a second tag implementation with duplicated names would be the drift US-SHL-020 exists to remove · E4 the roll-up renders as label·value pairs rather than the prototype's "8 accounts · $11,704.30 outstanding" sentence — the money value is a MoneyCell and translated fragments either side of a component are the concatenated sentence B8 forbids · E4 the tenant TZ + date format arrive as props with the same seed fallbacks every other list uses, until US-SHL-013's formatting service lands · **[CR-030 W2 2026-08-24]** E2 the W1 exception two rows up — *"the strip carries TWO of `[shot: ACC-01]`'s eight tabs"* — IS SUPERSEDED: the strip carries all eight, and the six without a body render `ArrivesWith` rather than an empty table, because the shared empty state asserts *"you have none of these"* about a feature that does not exist. `SettingsPage.tsx:432` is the house precedent · E3 **r10 DOES NOT DRAW ANY OF THIS.** `SMARTBillHub.dc.html` line 3889 gives the accounts module exactly TWO tabs, a `.sub` roll-up line and no KPI strip, no AGEING column, no customer sub-link and no chip overflow. Everything in W2 comes from B18 §5.1's `[shot: ACC-01 ×2]` — PO screenshots of 2026-08-23 that are NOT in the repo. This lane built to B18's TEXT and could not diff against the drawing; REPORTED, and it is the reason each divergence below is stamped rather than merely noted · E3 **T2.5 IS NOT BUILT AND NOTHING FAKES IT.** B18 §5.1.2 puts a `4 accounts` sub-link on the NAME cell (BR-CUS-054). `selectors.account_row` serves NO customer block — no customer id, no `customer_no`, no linked-account count — and `ACCOUNT_FILTERS` declares no `customer_id`, so following the link could not filter either. Both halves are server-side. TC-ACC-3 is an `it.todo` naming exactly that · E3 **T2.9's `customer #` IS NOT SHIPPED, AND THE COLUMN IS NOT THE TEST.** B18 says *"Do not ship the placeholder before the column"*; `customers.customer_no` landed in W0 (migrations 0013 + 0014) — and `selectors.account_list` matches `account_no`, `contacts.full_name` and metering/assets ids and NOT `customer_no`, so the placeholder would promise a search the server does not perform (hard-won law 1). The prompt names the four that really match; TC-ACC-7 goes green the day the search learns the column · E3 **`Export` IS STILL NOT RENDERED** although B18 §5.1 asks for it as the secondary: `apps/customers/` registers no `accounts` export resource, and BR-SHL-010 says an undeclared capability does not render. Not drawn disabled either — BR-SHL-025 is for a control this ROLE cannot use, not one the PRODUCT does not have · E3 **FOUR AGEING LABELS WHERE `[shot]` DRAWS THREE.** B18 §5.1.2 writes `Current · 30d past · 60+ past · —`; the server serves BR-CUS-048's four bands and has no value meaning "60+ past", so a collapsed label could not be filtered on. REPORTED as needing a ruling when billing wires its half · E3 **THE SEGMENTS RENDER AS A FILTER CHIP, NOT `[shot]`'s RADIO `seg` CONTROL.** B14 rule 12 fixes the toolbar's grammar and the shared `TableConfig` has no segment capability; adding one changes every list in the product. The BEHAVIOUR B18 asks for is intact — the choice rides in the URL as `f.ageing=` and a reload restores it · E3 **SIX OF `[shot]`'s SEVEN TAB COUNTS ARE ABSENT.** Only `Accounts` has a served figure; a `42` beside `Requests` would be a fabricated number on the first screen a tenant opens. The count rides INSIDE the label because `PageHeaderTab` has no count slot and `components/PageHeader.tsx` is outside this lane's scope — so it is not superscripted as `[shot]` draws it. REPORTED · E3 **THE PAGER FOOTNOTE IS THE SHARED ONE** (`1–2 of 2`), not `[shot]`'s *"Showing 1–8 of 1,247"*; the wording belongs to `ListPager` and to every list in the product · E3 the four `ageing_*` keys and the `ageing` FILTER NAME are both missing from `src/api/endpoints.ts` (`AccountRow`, `ACCOUNT_FILTERS`) — the backend half landed this morning and that file belongs to another lane today. Typed locally in `accountsListCells.tsx` as an intersection that needs no cast; the AccountsPage suite carries a named allowance for the filter mirror that disappears with the wrapper's own commit · E4 `PENDING ACTIVATION` costs a SECOND `GET /accounts` (`f.status=pending_activation`, envelope `count`) whose rows are discarded. A stated absence over a figure the product can answer is DEF-445's shape, so it is counted — and a `rollup.pending_activation` beside the two figures the roll-up already carries would pay for itself. REPORTED · **[CR-030 W2 CLOSE-OUT 2026-08-24 · lane L2]** E2 **the E3 note above beginning "T2.5 IS NOT BUILT AND NOTHING FAKES IT" IS SUPERSEDED — not by work, by a RULING.** PO 2026-08-24, verbatim: *"okay dont link it"*. The sub-link is CUT: not built, and not owed. The two server halves it named are still absent and that is now correct rather than a gap — `ACCOUNT_FILTERS` declares no `customer_id` because nothing will follow the link. `TC-ACC-3` is closed as WON'T BUILD, citing the ruling and its date, and is no longer an `it.todo` · E2 **the E3 note above beginning "T2.9's `customer #` IS NOT SHIPPED" IS SUPERSEDED, and the withholding it records was RIGHT.** That lane refused to draw a prompt promising a search the server did not perform (hard-won law 1), and B18 §5.1.2's *"Do not ship the placeholder before the column"* is why. All three pieces now exist in one commit, in that order, so the promise is kept before it is made: the search leg is proved by `06-backend/tests/test_cr030_w2_customer_no_search.py` (12 cases, RED-first), the column renders the served field, and the prompt names five things · E3 **`CUSTOMER #` SITS SECOND, BESIDE `ACCOUNT`, AND IS VISIBLE BY DEFAULT — BOTH ARE THIS LANE'S JUDGMENTS AND NEITHER IS IN A RULING.** B18 §5.1.2's transcribed `[shot]` table has EIGHT columns and `CUSTOMER #` is not one of them; the design only ever wanted the number as a search term, and the PO's ruling made it a column without saying where or whether it defaults on. Placement: the two numbers are the pair a clerk holds one of without knowing which, so adjacency is what makes "either number finds the row" legible. Default-visible: BR-CUS-053(b) says *"available through the shared column selector"*, which could be read as `defaultVisible: false` like `autopay` and `opened_at` — it is not read that way, because the PO's sentence is a complaint that they could not SEE the number and shipping it hidden behind a menu answers the letter and not the question. REPORTED for a ruling; either is one line to change · E4 **NOT SORTABLE.** `selectors.ACCOUNT_SORTS` is `account_no · name · balance · last_bill · status` and `customer_no` is not in it, so a sort control would offer an ordering the request cannot ask for — the same refusal `ageing` and `last_bill` already carry · E3 **THE PROMPT'S NEW ENGLISH IS NOT IN THIS COMMIT.** `customers.accounts.searchPlaceholder` keeps its key and needs its VALUE changed to *"Account #, customer #, name, address, or meter #…"* in all eleven catalogues — the same shape T1.11 used to relabel `customers.accounts.action.import`. This lane may not edit `src/i18n/locales/`, so the key and its English are handed over in the lane report and `TC-ACC-7`'s copy assertion in `AccountsPage.test.tsx` is RED until that fan-in lands. Stated rather than worked around: a test edited to assert the OLD copy would have hidden the last third of the task · E3 **`customer_no` IS DECLARED OPTIONAL ON `AccountRow`** (`src/api/endpoints.ts`, which WAS clean in the shared tree and so was editable). The server serves it on every row, always, so `string | null` is the truth and `?` is weaker than it — required went red in three fixtures (`AccountDetailPage.test.tsx`, `MoveInWizard.test.tsx`, `MoveOutWizard.test.tsx`) that belong to other lanes this session, one of them dirty at the time. One added line in each closes it; owed · **[TABCTA 2026-08-26 · DEF-729 + DEF-730]** E2 **the CR-030 W2 T2.8 exception above — *"the six unbuilt tabs declare NONE: a primary action over a body that says 'not built yet' is a button onto nothing"* — IS SUPERSEDED.** It was right while six tabs rendered a note about themselves; every tab now renders its real list and every act has a route, and what the withholding cost is the two defects: the PO walked the deployed v2.49.0 and could not raise a request, a new connect, a move-in or a move-out from this page, although all six wizards were built and routed. The ONE primary slot now carries the ACTIVE tab's create action and relabels across the eight — exactly-one-primary (B14 rule 4 / BR-SHL-044) is HONOURED rather than fought, which is what r10 draws · E3 **`move-ins` and `move-outs` STAY DISABLED WITH THEIR REASON, and the reason was MEASURED rather than assumed.** `MoveInWizard` and `MoveOutWizard` ARE built, and both are mounted only at `/accounts/:accountId/move-in|move-out` because the ENDPOINTS are account-scoped; this header has no account selected, so a live button would have to guess which one you meant (BR-SHL-025, and hard rule 2 — never wire a button to something that does not exist) · E3 **THE TWO MOVE PRIMARIES BORROW `customers.accounts.action.moveIn` / `.moveOut` RATHER THAN THE TABS' OWN `customers.moveIns.action.new`.** The tab keys exist only as English `defaultValue`s and no catalogue answers them, so asking for them here would put a second untranslated literal on this screen and raise G27; the borrowed pair is translated in all eleven locales and is the same vocabulary the two secondaries beside it use. The divergence with the tabs' own `+ New move-in` empty-state CTA copy is REPORTED · E3 **`Export` IS STILL NOT RENDERED** — unchanged, BR-SHL-010 · E3 the segment strips on `new-connects` and `disconnects` render their SELECTED chip as `data-variant="primary"` at `data-size="sm"`; that is `WorklistSegments`' on-state and not a page action, and it is why the new suite counts primaries inside `page-header-actions` rather than over the whole head — REPORTED, not changed · **[CR-045 wave G 2026-08-27 · `DEF-1702`]** E2 **the exception immediately above IS SUPERSEDED and the narrowing it explains STAYS.** `WorklistSegments` was an INERT control — five mounts, every one handed `onSelect={() => undefined}`, sitting in the slot B14 rule 12 reserves for the filter — and it is deleted, so no `data-segment` renders anywhere and neither tab draws a second `data-variant="primary"` before the table. The suite still counts inside `page-header-actions`, because the reason was never this particular strip: any selected-state control rendering the primary variant before the table would fail a test about the page's one primary ACTION. Amended rather than removed (hard-won law 1) so the next lane does not read the narrowing as unexplained and widen it back · **[CUS-TILES 2026-09-28]** E2 **THE `E3` NOTE ABOVE BEGINNING "the roll-up's `past_due_60_plus` is null and renders as awaiting, never 0" IS SUPERSEDED, AND SO IS THE `E4` NOTE BEGINNING "`PENDING ACTIVATION` costs a SECOND `GET /accounts`".** The first tile no longer exists and the second read is deleted; both are amended rather than removed, because a reader meeting an unexplained deletion widens it back (hard-won law 1). The `E4` note ends *"a `rollup.pending_activation` … would pay for itself. REPORTED"* — this is that report being acted on, four tiles at once, as `rollup.by_status`. · E3 **`Outstanding` IS DROPPED ALTHOUGH IT WORKED, AND THE SCREEN NOW STATES NO TENANT-WIDE MONEY.** The ruling is four tiles and money is not one of them. Checked before deleting: the page head's sub-line carries `10 tabs · <Tab>` and no figure, and the only other money on the screen is the per-row BALANCE cell. REPORTED in the lane report and written into `BR-CUS-1105`; the server still serves `rollup.outstanding` and Finance's Revenue & AR is where the utility-wide figure lives. · E4 **THE TILE LABELS ARE THIS CATALOGUE'S, NOT THE TENANT'S STATUS NAMES.** `BR-CUS-055` lets a utility rename a seeded status; the COUNT keys off the code so a rename cannot move a tile, and the LABEL stays the PO's ruled word because a tenant's own name would break the one-word ruling and B14 rule 33's cap the first time somebody wrote a sentence into a lookup row. `rollup.by_status[].name` is served for a caller that wants it. · E4 **A STATUS THE TENANT DOES NOT HAVE DRAWS A DASH AND IS NOT A CONTROL**, and the strip stays four wide. `0` would say *nobody is suspended* about a utility with no such status, and a filter on it would return an empty list for ever (law 2's mirror). · E4 **`ACCOUNT_STATUS_TILES` NAMES TWO CODES AS LITERALS** — `marked_disconnect` and `vacation_hold`, beside the two `customersShared` already exports as constants. Adding two more constants to that shared file was not worth the blast radius from this lane; `test_def_cus_7700_account_status_tiles.py::test_tc1b` asserts all four are members of `services.SEED_ACCOUNT_STATUSES`, so a rename in the seed goes red rather than silently counting nothing. · E2 **THE SHARED `KPIStrip` GAINED THE PRESS, RATHER THAN THIS SCREEN GROWING A SECOND STRIP (B14 rule 43)** — and that is the home `features/customers/newConnectListViews.BuildTiles` asked for by name hours earlier on this branch. Its fold-in is `DEF-CUS-7701`, and the pressed ring here is deliberately that component's own so the fold-in moves no pixel.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
