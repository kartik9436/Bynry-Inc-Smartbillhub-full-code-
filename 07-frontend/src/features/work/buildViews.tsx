// ── Trace ──────────────────────────────────────────────
// ⚠ `DEF-GOV-10106`: `BuildTab`, `BuildTabPanel` AND `BuildActions` ARE
//           DELETED, with the eight record panels only `BuildTab` drew. The PO
//           took the Build panel off the property and the account on
//           2026-10-02 (`CR-162-BRC10`, `728fe0248`): the New Connection's own
//           page tracks progress and takes every action. `useBuild` stays
//           (the property header's `PendingBuildLink` reads it), and so does
//           everything below about work orders.
// Story:    US-WRK-002 (EP-WRK-01) — the acts on a build, RE-HOSTED: the same
//           doors wave B mounted, pressed from the premises and from the
//           account instead of from a screen of their own.
//           US-WRK-004 — the work orders at a place, and on an account.
//           Screens: Work-002 (`wireframes/Work-002.png`) on TWO hosts now
//           (`08-screen-layouts.md`, stamped by wave O).
// Rules:    CR-070 §W.10/§W.11 (one destination — PO 2026-09-04) ·
//           BR-SHL-025 (the server refuses regardless; the control says why
//           first) · BR-WRK-006 (four anchors) · BR-MET-110 (a person accepts
//           what the field sent) · BR-MET-114 (outstanding work is written by
//           a human and blocks nothing) · BR-MET-1161 (an address lives on
//           `premises`; everything else WALKS to it) · CLAUDE.md hard rule 2
//           (money stored to 4, displayed at 2 — the SERVER rounds once) ·
//           B14 rule 6 (the danger tier is the destructive commit alone) ·
//           rule 15 (row actions are glyphs) · rule 20 (one table type) ·
//           rule 21 (Tailwind utilities; this file is on route-b-migrated.txt
//           from its first commit) · rule 31 (no database id is ever a visible
//           value) · rule 32 (one sentence per section; no rule id or internal
//           code in clerk copy) · rule 33 (a refusal is five or six words) ·
//           rule 36 (the pack gives LAYOUT, r10 gives STYLE, the shared kit is
//           how you comply)
// Change:   CR-126-BRC07 lane NCD-7 — THE JOIN. `GET /connections/{id}/record`
//           is read here and its answers reach the eight drawn panels; before
//           this they were props nothing passed (CLAUDE.md hard-won law 2).
//           No markup changed and no route was added — the Build tab IS the
//           build record (`OQ-MET-12520`, option C, confirmed).
// Tests:    src/features/work/buildViews.test.tsx ·
//           src/features/work/buildViewsWorkOrders.dom.test.tsx (the drawn
//           OPEN chip, PRESSED — a static render can only show the arrival
//           state, so `does All bring the finished job back` lives there) ·
//           src/features/work/buildRecord/buildRecordPanels.test.tsx (the JOIN:
//           which rows stopped being stated absences, and which must not)
// Impacts:  src/features/metering/PremisesDetailPage.tsx (the Build and Work
//           orders tabs) · src/features/customers/AccountDetailPage.tsx (the
//           twelfth tab) · src/features/work/workEndpoints.ts
// ───────────────────────────────────────────────────────
//
// ⚠ **WHY THIS FILE EXISTS, IN THE PRODUCT OWNER'S OWN WORDS (2026-09-04).**
//
//   *"you are duplicating this — there is nothing called as connections;
//    Connection = Account only — you cannot have two different screen — this is
//    an integration problem"*
//
// and, scoping it the same day:
//
//   *"One screen too many. The objection is the duplicate destination — a
//    person should reach the build's progress, its units, its work orders and
//    its charges from the account, not from a parallel screen. Whatever the
//    tables are called underneath, there is one place to look."*
//
// So the panels a person needs live HERE, once, and the two hosts compose them.
// `features/customers/ConnectionDetailPage.tsx` — the parallel screen — is
// deleted in the same commit. **This is a move, not a rewrite:** the action row,
// its refusal reasons and the work-order drawer below are that screen's, kept
// word for word wherever the words were already right, because they were built
// and tested against fourteen mounted doors and re-deriving them would have
// thrown that away to make a diff look tidier.
//
// ⚠ **THE TABLE IS NOT ONE THING TOO.** `connections` survives as plumbing —
// §W.10 is explicit (*"whatever the tables are called underneath"*), and §W.10
// marks the retire-the-table proposal SUPERSEDED. Nothing here migrates
// anything.
import { useState } from "react";
import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { Button, ButtonLink } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { Disclosure } from "@/components/Disclosure";
import { FilterBar } from "@/components/FilterBar";
import { EyeIcon } from "@/components/icons";
import { Panel } from "@/components/Panel";
import { RowAction, RowActions } from "@/components/RowActions";
import { WorkingButton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { InlineLinkTo, PlainTable, RefusalStrip } from "@/components/Surfaces";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableColumnConfig, TableConfig, TableRequestState } from "@/components/tableTypes";
import { Kicker, Note } from "@/components/TextBits";
// CR-126-BRC07 lane NCD-7 — the two step-1 vocabularies the record reads back.
// ⚠ **THE STORED VALUE IS A CODE** (`builder_developer`, `new_premise`) and a
// code on a clerk's screen is the defect these lists exist to prevent. They are
// IMPORTED rather than re-typed so a fifth owner kind appears here on its own,
// which is CLAUDE.md hard-won law 2's other half: a hand-typed list is why an
// eleventh service never reached the sign-up screen.
import type { WorkOrderAcceptResult } from "@/features/customers/newConnectEndpoints";
import { acceptWorkOrder } from "@/features/customers/newConnectEndpoints";
// ⚠ `MoneyOrReason` left this import with CR-126-BRC07: the seven-fact strip
// that used it is replaced by the drawn tiles, which print the server's own
// `display` string. `AbsentValue` is still used by the work-order tables below.
import { AbsentValue } from "@/features/customers/newConnectShared";
// ⚠ **THE ENABLED FILTER IS IMPORTED, NEVER RE-WRITTEN** — one predicate for
// *does this utility sell it*, shared with the premises wizard, the assets
// wizard and New Connect's step 4 (`DEF-MET-6118`).
import { Dash } from "@/features/customers/customersShared";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";
import { workOrderDetailPath } from "./OrderDetailPage";

// ⚠ CR-126-BRC07 — the drawn build record, as SECTIONS on this tab. There is
// NO `/connections/{no}` screen: `OQ-MET-12520` closed on option C and the PO
// CONFIRMED it (decision log 2026-09-20, `8cb9a379c`) — *"MAKE THE BUILD TAB
// COMPLETE."* Only the drawing's ADDRESS and TAB STRIP are superseded;
// blueprint p100–p107 remain the CONTENT contract.
import { newOrderOnPremisesPath } from "./NewOrderWizard";
import { accountRaisePath } from "./raise/AccountRaisePage";
import { CONNECTION_MODE_FALLBACK } from "./workforceLabels";
import {
  buildHomePath,
  getAccountBuild,
  getPremisesBuild,
  listAccountWorkOrders,
  listPremisesWorkOrders,
} from "./workEndpoints";
import type { BuildFacts,  ScopedWorkOrderRow } from "./workEndpoints";

// ══════════════════════════════════════════════════════════════════════════
// VOCABULARY — the words a build is described in
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **EVERY ONE OF THESE IS A CATALOGUE KEY WITH AN ENGLISH FALLBACK, AND THE
// FALLBACK IS NOT THE CODE.** `defaultValue: order.mode` would ship `our_crew`
// to a clerk's screen — visible, ugly and wrong — which is what the first draft
// of the screen this came from did. The eleven catalogues own these words; the
// fallback is what a person reads until a catalogue is missing one.

// ⚠ **THE WORDS LIVE IN `workforceLabels.ts` NOW AND THIS IS THE RE-EXPORT
// (`DEF-MET-6453`).** The warning above was right and this file could not act
// on it: `BuildOwnerScopePanel` needs the same three words and importing them
// from HERE would close a cycle, because this file MOUNTS that panel —
// `DEF-WRK-3955`'s shape, where the constant is simply `undefined` while the
// other module's body runs and `tsc` has nothing to say. A leaf module that
// imports nothing is the fix the repo already built for this.
export const MODE_LABELS = CONNECTION_MODE_FALLBACK;

export const SCOPE_LABELS: Record<string, string> = {
  per_premise: "Premise",
  per_unit: "Unit",
  per_asset: "Asset",
};

export const OUTCOME_LABELS: Record<string, string> = {
  passed: "Passed",
  failed: "Failed",
  partially_done: "Partially done",
  cancelled: "Cancelled",
  waiting_on_someone_else: "Waiting on someone else",
  not_done_payment_received: "Not done — payment received",
};

export const ORDER_STATE_LABELS: Record<string, string> = {
  planned: "Planned",
  in_progress: "In progress",
  blocked: "Blocked",
  completed: "Completed",
  cancelled: "Cancelled",
};

/** Which anchor a job stands on, in a clerk's words. `stands_on` travels as one
 *  token and is NEVER printed — B14 rule 32 forbids an internal code in copy. */
export const STANDS_ON_LABELS: Record<string, string> = {
  account: "On this account",
  asset: "On a meter here",
  unit: "On a unit here",
  build: "On the build here",
  premises: "At this address",
};

/**
 * The tone a build's state is drawn in.
 *
 * B18 draws NO tone for a connection state, so this is the SCREEN's reading and
 * it decides nothing: a tone is not a segment and no row is filtered by one.
 */
export function buildStateTone(state: string): StatusTone {
  if (state === "activated") {
    return "success";
  }
  if (state === "partly_activated" || state === "on_hold") {
    return "warning";
  }
  if (state === "cancelled") {
    return "danger";
  }
  return "neutral";
}

// ══════════════════════════════════════════════════════════════════════════
// THE ACTION ROW — eight acts, on whichever host the person is standing on
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **EIGHT, AND THE PLAN SAID SEVEN.** `04-docs/05-modules/16-work/
// 10-execution-plan.md` describes wave O as carrying *"the seven acts"* in four
// places; `CR-070 §W.6` says **eight**, `ConnectionAct` had eight members and
// `cr070-b-fourteen-doors-and-the-queue.mjs` asserts `acts.length === 8`. The
// code and the change request agree and the plan was wrong; filed as
// `DEF-WRK-3748` and corrected there rather than silently built to whichever
// number was convenient.
//
// ⚠ **EVERY BUTTON IS EITHER ENABLED OR DISABLED WITH ITS REASON, NEVER HIDDEN
// (`BR-SHL-025`), AND THE REASON IS FIVE OR SIX WORDS (B14 rule 33).** Hiding a
// control teaches a clerk the product cannot do a thing; disabling it with a
// sentence teaches them WHEN it can.
//
// ⚠ **AND THE SCREEN'S ANSWER IS NEVER THE GUARANTEE.** Every refusal here is
// ALSO enforced server-side, on the same rule, by the service the door calls.
// `actBlockedReason` restates them so a clerk reads the reason before the
// click; if it is ever wrong, the server still refuses.

/** The eight acts of `Work-002`'s row, in the order they are drawn. */
export type BuildAct =
  | "hold"
  | "release"
  | "cancel"
  | "waitingOn"
  | "addService"
  // CR-162-BRC10 item 7 — *Add unit* on a committed build.
  | "addUnit"
  | "markOutstanding"
  | "closeOutstanding"
  | "raiseOrder";

/**
 * Why an act cannot be performed on this build right now, or `null` when it can.
 *
 * Exported so a test can ask the QUESTION without a DOM, which is why a rule can
 * be asserted here rather than inferred from a `disabled` attribute.
 *
 * The rules, and each is the SERVER's own restated:
 *   * a **cancelled** build takes no further records at all
 *     (`_refuse_if_cancelled`) — every act but *Close* on an existing to-do;
 *   * **Hold** is refused on a build already held (`_stamp`'s `expect_unset`);
 *   * **Release** is refused on a build that is not held (nothing to lift);
 *   * **Close** needs a to-do to close.
 */
export function actBlockedReason(
  act: BuildAct,
  build: BuildFacts,
  t: Translator,
): string | null {
  const cancelled = build.state === "cancelled";
  const held = build.state === "on_hold";
  if (cancelled) {
    // ⚠ Cancel is refused on a cancelled build too — the stamp is set once and
    // the service says so. A second Cancel is not a no-op, it is a refusal.
    return t("customers.connection.act.whyCancelled");
  }
  if (act === "hold" && held) {
    return t("customers.connection.act.whyHeld");
  }
  if (act === "release" && !held) {
    return t("customers.connection.act.whyNotHeld");
  }
  if (act === "closeOutstanding" && build.outstanding.length === 0) {
    return t("customers.connection.act.whyNothingOpen");
  }
  return null;
}

// ══════════════════════════════════════════════════════════════════════════
// THE BUILD TAB — the five facts, what is outstanding, and the eight acts
// ══════════════════════════════════════════════════════════════════════════

/** `GET /premises/{id}/build` and `GET /accounts/{id}/build`, keyed per host so
 *  an act on one does not silently re-read the other. */
export const buildQueryKey = (host: "premises" | "account", id: string) =>
  ["work", "build", host, id] as const;

// ══════════════════════════════════════════════════════════════════════════
// CR-126-BRC07 lane NCD-7 — THE RECORD READ, JOINED TO THE DRAWN SECTIONS
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THIS IS CLAUDE.md HARD-WON LAW 2 BEING CLOSED RATHER THAN QUOTED.** The
// backend landed `GET /connections/{id}/record` and the eight panels below
// landed against `buildRecordSource.ts`, and until this join existed **nothing
// passed them a value**: every section rendered its stated absence, `tsc` and
// every test passed, and the feature did not exist. The previous lane left the
// seam clean and DECLARED, which is the right way to leave one — it is still
// not a feature until somebody closes it.
//
// ⛔ **IT ADDS NO SCREEN AND NO ROUTE.** `/connections/:connectionId` stays a
// redirect, there is no `SCREEN_ROUTES` row and no `NCT-02` badge:
// `OQ-MET-12520` closed on the PO's option C and was confirmed a second time
// when the collision was put to them. The property's Build tab IS the record.
//
// ⚠ **WHERE BOTH READS ANSWER, THE BUILD READ WINS AND THE RECORD FILLS THE
// REST.** `state`, `waiting_on`, `target_activation` and `mode` are on both
// payloads and are the same derivation over the same row — but the build read
// is what GATES the eight acts, so a screen whose pill and whose buttons
// disagreed would be two sources for one fact. The record answers what the
// build read cannot: the counted pairs, the activation stamp, step 1's three
// answers, the whole premise block on a host that has none, the provenance and
// the service tags.

/** `GET /connections/{id}/record`, keyed by the BUILD — the subject of the
 *  read, and a property can carry more than one. */
export const buildRecordQueryKey = (connectionId: string) =>
  ["work", "build-record", connectionId] as const;

/** The one read behind both hosts' Build tabs. Exported so a host can ask
 *  whether to OFFER the tab before it renders one (law 2). */
export function useBuild(host: "premises" | "account", hostId: string, client?: ApiClient) {
  const transport = client ?? api;
  return useQuery({
    queryKey: buildQueryKey(host, hostId),
    queryFn: () =>
      host === "premises"
        ? getPremisesBuild(hostId, transport)
        : getAccountBuild(hostId, transport),
    enabled: hostId !== "",
  });
}

// ══════════════════════════════════════════════════════════════════════════
// THE WORK ORDERS TAB — every job at a place, or on an account
// ══════════════════════════════════════════════════════════════════════════

export const scopedOrdersQueryKey = (host: "premises" | "account", id: string) =>
  ["work", "orders", host, id] as const;

/**
 * The orders table both hosts draw — `CR-089`'s **P8** for the property
 * (blueprint pages 32–34) and `Work-002`'s Work orders region for the account.
 *
 * **The question it answers, as drawn:** *is anybody due to visit, and what
 * for?* Seven columns — `Work · What · Where · Crew · Booked · Status` and the
 * row actions — one filter chip, and no prose.
 *
 * ⚠ **IT DREW NINE COLUMNS AND NOT ONE OF THEM WAS *WHERE* (`DEF-4740`).** The
 * order number and the job were collapsed into one cell, `Service`, `Mode`,
 * `Outcome` and `Stands on` were drawn where the blueprint draws nothing, and
 * `unit_label` — served on every scoped row since wave O — was visible only
 * inside the drawer. Nothing is deleted: the four undrawn columns are declared
 * and OFF by default, which is what the column chooser the shared table brings
 * is for.
 *
 * ⚠ **`stands_on` IS DRAWN AND THE ANCHOR ID IS NOT.** `US-WRK-004`: each row
 * says which anchor it is standing on, because a person on an ACCOUNT sees the
 * move-out's final read (on the account), the meter exchange beside it (on the
 * asset) and the build's install jobs (on the build) in one list, and a list
 * that did not say would be claiming they are all the same kind of thing. So
 * that column is default-ON for the account host and default-OFF for the
 * property, where the blueprint draws seven columns and this is not one of
 * them. B14 rule 31: the column prints a sentence, never the id it came from.
 *
 * ⚠ **THIS DOC USED TO END *"THERE IS NO TECHNICIAN COLUMN AND THAT IS NOT AN
 * OMISSION"* AND THAT STOPPED BEING TRUE AT WAVE `C6`.** `assignee_technician_id`
 * landed with wave G and `technician` has been on the scoped row since; the
 * `Crew` column draws it, and *Nobody yet* is what an unassigned job says. The
 * note outlived the gap by a week, which is hard-won law 1 in a docstring.
 */
/** The tone a work order's STATE is drawn in.
 *
 * The blueprint draws this column as a PILL (`SCHEDULED`, `WAITING`) where the
 * product drew a bare word. `B18` assigns no tone to an order state, so this is
 * the SCREEN's reading and it decides nothing — no row is filtered by a tone and
 * no rule reads one. `blocked` takes the warning tier because it is the one
 * state a dispatcher is there to clear; `cancelled` is the only ending nobody
 * wanted, and takes danger.
 */
export function orderStateTone(state: string): StatusTone {
  if (state === "completed") {
    return "success";
  }
  if (state === "blocked") {
    return "warning";
  }
  if (state === "cancelled") {
    return "danger";
  }
  return "neutral";
}

/** The drawn default filter is the chip `OPEN`, and *open* is a GROUPING rather
 *  than one of `work_orders`' five states: planned, in progress and blocked are
 *  all jobs somebody still has to do. `done` is the complement, which is what
 *  the drawn footer counts beside it (*"Showing 2 open · 7 done in the last
 *  year"*). Declared once here so the chip, the option list and the count
 *  cannot come to disagree. */
export const OPEN_ORDER_STATES = ["planned", "in_progress", "blocked"] as const;

export function isOpenOrder(order: ScopedWorkOrderRow): boolean {
  return (OPEN_ORDER_STATES as readonly string[]).includes(order.state);
}

/**
 * `ACC-T08` draws FOUR chips — `All` `Open` `Scheduled` `Closed` — where this
 * tab offered two. The two extra are read off the row rather than invented:
 *
 *   · **Scheduled** is an open job that has an APPOINTMENT WINDOW. It is a
 *     narrowing of `Open`, not a sibling of it, and that is the truth about
 *     these jobs rather than a tidier taxonomy: a job is scheduled *because*
 *     somebody booked it, and it is still open until it is done.
 *   · **Closed** is `done`'s grouping, which this tab already had under the
 *     word *Done*. The blueprint's own STATUS column reads `Closed`, so the
 *     chip and the cell say the same word.
 *
 * ⚠ **DECLARED ONCE, HERE, SO THE CHIP AND THE PREDICATE CANNOT DISAGREE** —
 * the reason `OPEN_ORDER_STATES` above exists at all.
 */
export const ACCOUNT_ORDER_GROUPS = ["open", "scheduled", "closed"] as const;

export function orderMatchesGroup(order: ScopedWorkOrderRow, group: string): boolean {
  if (group === "") {
    return true;
  }
  if (group === "scheduled") {
    return isOpenOrder(order) && order.window_start !== null;
  }
  if (group === "closed" || group === "done") {
    return !isOpenOrder(order);
  }
  return isOpenOrder(order);
}

/**
 * `ACC-T08`, verbatim: *"This list is not in date order and the footer has to
 * say so. It is sorted by priority rank, then by due time, and that sort is
 * fixed — there is no column to click."*
 *
 * ⚠ **IT IS THE DISPATCHER'S OWN ORDER, WHICH IS THE POINT.**
 * `apps/work/dispatch.dispatch_page` orders by `priority__rank` then `due_at`,
 * both NULLS LAST, and its docstring gives the reason in one sentence: *"an
 * order with NO priority sorts last rather than first, because a job nobody
 * set a priority on is not more urgent than one somebody marked Urgent."* The
 * same sentence is true on an account, so the same order is used rather than a
 * second one written here.
 */
export function comparePriorityThenDue(a: ScopedWorkOrderRow, b: ScopedWorkOrderRow): number {
  const rank = (row: ScopedWorkOrderRow) =>
    row.priority === null || row.priority === undefined ? Number.MAX_SAFE_INTEGER : row.priority.rank;
  const byRank = rank(a) - rank(b);
  if (byRank !== 0) {
    return byRank;
  }
  if (a.due_at === null && b.due_at === null) {
    // The server's own tiebreak, preserved rather than re-derived.
    return (a.order_no ?? "").localeCompare(b.order_no ?? "");
  }
  if (a.due_at === null) {
    return 1;
  }
  if (b.due_at === null) {
    return -1;
  }
  return a.due_at.localeCompare(b.due_at);
}

/** IS-3, client-side: `GET /premises/{id}/work-orders` takes `page` and `per`
 *  and no `q` at all, so there is no server to ask. It matches exactly what the
 *  row DISPLAYS — the order number, the job, where it is and who is going. */
export function workOrderMatches(order: ScopedWorkOrderRow, q: string): boolean {
  const needle = q.trim().toLowerCase();
  if (needle === "") {
    return true;
  }
  return [order.order_no, order.type, order.unit_label, order.technician?.name ?? null]
    .filter((part): part is string => typeof part === "string" && part !== "")
    .some((part) => part.toLowerCase().includes(needle));
}

/**
 * IS-2, client-side, over the two sortable columns this tab declares.
 *
 * ⚠ **THE DEFAULT IS THE SOONEST VISIT, NOT THE NEWEST ROW, AND THAT IS THE
 * QUESTION THE TAB ASKS** — *is anybody due to visit, and what for?* A job with
 * no appointment sorts LAST rather than first: *Not booked yet* is an absence,
 * and floating it to the top of a list ordered by date would read as *this one
 * is next*. Within the unbooked half the server's own order is kept — newest
 * raise first, which is what `US-WRK-004` asks for.
 */
export function compareWorkOrders(
  a: ScopedWorkOrderRow,
  b: ScopedWorkOrderRow,
  sort: string,
  dir: "asc" | "desc",
): number {
  const way = dir === "desc" ? -1 : 1;
  if (sort === "work") {
    return (a.order_no ?? "").localeCompare(b.order_no ?? "") * way;
  }
  const left = a.window_start ?? a.due_at;
  const right = b.window_start ?? b.due_at;
  if (left === null && right === null) {
    // Newest raise first — the server's own order, preserved rather than
    // re-derived, so clearing a sort returns a person to what they had.
    return (b.raised_at ?? "").localeCompare(a.raised_at ?? "");
  }
  if (left === null) {
    return 1;
  }
  if (right === null) {
    return -1;
  }
  return left.localeCompare(right) * way;
}

/**
 * `03-work.png`'s drawn column order for the BUILD host — ORDER · WHAT ·
 * SERVICE · UNIT · CREW · TECHNICIAN · TARGET · STATE, with the kit's row
 * action last. Every other declared column keeps its place behind them and
 * stays reachable through `Columns ▾`; nothing is deleted (`DEF-CUS-7618`).
 */
const BUILD_COLUMN_ORDER = [
  "work",
  "what",
  "service",
  "where",
  "crew",
  "technician",
  "booked",
  "status",
] as const;

function buildColumnRank(key: string): number {
  if (key === "actions") {
    return 999;
  }
  const at = BUILD_COLUMN_ORDER.indexOf(key as (typeof BUILD_COLUMN_ORDER)[number]);
  return at === -1 ? 500 : at;
}

/**
 * ⚠ **THE THIRD HOST IS `build`, ADDED BY `DEF-CUS-7618` (2026-09-28), AND IT
 * READS THE PREMISES LIST RATHER THAN A LIST OF ITS OWN.**
 *
 * The build detail page had a hand-rolled `PlainTable` of its own — its own
 * `<thead>`, its own tiles, its own empty state — where this component is the
 * shared `DataTable` the premises and the account already compose. That is
 * `CR-151-BRC09` §2 rule (2) (*no panel is copied*) and B14 rule 43, and the
 * fix is a host rather than a second table.
 *
 * ⚠ **WHY `hostId` IS THE PREMISES ID ON THE BUILD HOST, WHICH LOOKS WRONG
 * UNTIL YOU LOOK FOR THE ROUTE.** There is **no `GET /connections/{id}/work-
 * orders`** — `apps/work/api.py` mounts `premises/<id>/work-orders` and
 * `accounts/<id>/work-orders` and nothing else — and `_scoped_row` publishes
 * no build id, so a premises read cannot be narrowed to one build by anything
 * ON the row. What the build DOES hold is the ids: `GET /connections/{id}`
 * serves `work_orders[]`. So the build host reads the SHARED premises list and
 * `onlyOrderIds` intersects it. One read, one row shape, one table.
 *
 * ⚠ **AND IT SHARES THE PREMISES CACHE ON PURPOSE** — the query key below is
 * the premises key, so a clerk who has already opened the property tab pays
 * for no second request, and the two screens cannot show one order two ways.
 */
export function WorkOrdersTab(props: {
  host: "premises" | "account" | "build";
  /** The premises id on the `build` host — see this component's docstring. */
  hostId: string;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  openOrderId: string | null;
  onOpenOrder: (id: string | null) => void;
  client?: ApiClient;
  /**
   * `build` host only — the ids of the orders THIS build raised, from the
   * build's own read. Undefined on the other two hosts, where the route
   * already answers the exact question the tab asks.
   */
  onlyOrderIds?: readonly string[];
}) {
  const { t } = props;
  const client = props.client ?? api;
  const tenantPath = useTenantPath();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  // ── DEF-4739 · THE SHARED TABLE, NOT THE IN-PANEL ONE ────────────────────
  // Search, the filter chip, the column chooser and the pagination footer are
  // all `DataTable`'s, in the same places as every other list in the product.
  // The request state is CLIENT-side because this route takes `page`/`per` and
  // nothing else — see `workOrderMatches` — and a property or an account holds
  // a handful of jobs. `per: 200` is asked for so that handful is genuinely all
  // of them rather than the server's default page.
  // ⚠ **THE BUILD HOST READS THE PREMISES ROUTE**, so its cache key, its
  // fetcher and its arrival sort are the premises ones. Only the COLUMN SET,
  // the narrowing and the two notes below differ — see the docstring.
  const readHost: "premises" | "account" = props.host === "account" ? "account" : "premises";
  const [state, setState] = useState<TableRequestState>({
    q: "",
    sort: props.host === "account" ? "priority" : "booked",
    dir: "asc",
    page: 1,
    per: DEFAULT_PAGE_SIZE,
    // ⚠ **THE PROPERTY OPENS ON `OPEN` AND THE ACCOUNT OPENS ON `ALL`, AND
    // BOTH ARE READ OFF A DRAWING.** `P8` applies the `OPEN` chip on arrival.
    // `ACC-T08` does not: its four rows are one Scheduled and three Closed and
    // its footer counts *1–4 of 4*, so the account's arrival state is every
    // job at this address, finished ones included — which is also the question
    // the tab exists to answer on an account.
    // ⚠ **AND THE BUILD OPENS ON EVERY JOB IT RAISED**, finished ones
    // included: `03-work.png` draws four rows, three of them `Done`, under a
    // strip that counts Orders · Done · Open. An `OPEN` chip on arrival would
    // hide three of the four and make the strip disagree with the table.
    filters: props.host === "premises" ? { state: "open" } : {},
  });
  const listQuery = useQuery({
    queryKey: scopedOrdersQueryKey(readHost, props.hostId),
    queryFn: () =>
      readHost === "premises"
        ? listPremisesWorkOrders(props.hostId, { per: 200 }, client)
        : listAccountWorkOrders(props.hostId, { per: 200 }, client),
    enabled: props.hostId !== "",
  });

  const accept = useMutation({
    mutationFn: (orderId: string) => acceptWorkOrder(orderId, client),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: scopedOrdersQueryKey(readHost, props.hostId),
      });
      void queryClient.invalidateQueries({ queryKey: buildQueryKey(readHost, props.hostId) });
    },
  });

  const served: readonly ScopedWorkOrderRow[] = listQuery.data?.results ?? [];
  // ⚠ **THE NARROWING IS THE BUILD HOST'S WHOLE READ**, and it is an
  // intersection rather than a predicate on the row: nothing on a scoped row
  // says which build raised it (`_scoped_row` publishes no connection id), so
  // the build's own `work_orders[]` names the ids and this keeps those.
  const onlyIds = props.onlyOrderIds;
  const rows: readonly ScopedWorkOrderRow[] =
    onlyIds === undefined ? served : served.filter((row) => onlyIds.includes(row.id));
  const openOrder =
    props.openOrderId === null
      ? null
      : (rows.find((row) => row.id === props.openOrderId) ?? null);

  // ⚠ **EVERY DRAWN DIFFERENCE ON THIS TAB IS KEYED OFF THE HOST, AND NOT ONE
  // OF THEM MOVES THE PROPERTY TAB.** Two blueprints draw this one component:
  // `CR-089`'s `P8` for the property (seven columns, one chip, no prose) and
  // the accounts blueprint's `ACC-T08` for the account (`ORDER # · TYPE ·
  // PRIORITY · TECHNICIAN · DUE · STATUS · RAISED BY`, four chips, a fixed
  // sort and a footer that says so). `standsOn` already worked this way; the
  // rest follows it rather than forking the component.
  const onAccount = props.host === "account";
  // ⚠ **THREE HOSTS NOW, AND EVERY BUILD-ONLY DIFFERENCE IS KEYED OFF THIS
  // FLAG SO THE OTHER TWO RENDER EXACTLY AS THEY DID** (`DEF-CUS-7618`). The
  // build's column set is `03-work.png`'s: ORDER · WHAT · SERVICE · UNIT ·
  // CREW · TECHNICIAN · TARGET · STATE, plus the kit's row action.
  const onBuild = props.host === "build";
  const technicianColumn: TableColumnConfig<ScopedWorkOrderRow> = {
    // ⚠ **CREW AND TECHNICIAN ARE TWO COLUMNS ON THE BUILD AND ONE EVERYWHERE
    // ELSE, AND THE SPLIT IS READ OFF THE HOLDER RATHER THAN INVENTED.**
    // `dispatch._holder` answers with `kind: "person"` for a technician and
    // with the CREW's own kind otherwise, so each cell shows the holder it is
    // about and states an absence for the other. The one case the wire cannot
    // express is a crew holding an order that ALSO names a technician — it
    // serves one holder — and `03-work.png` draws no such row.
    key: "technician",
    label: t("customers.build.work.col.technician", { defaultValue: "Technician" }),
    cell: (row) => (
      <span data-order-technician={row.order_no ?? row.id}>
        {row.technician !== null && row.technician.kind === "person" ? (
          row.technician.name
        ) : (
          <AbsentValue
            reason={t("customers.build.work.technicianNotServed", {
              defaultValue: "Technician is on the order.",
            })}
          />
        )}
      </span>
    ),
  };
  // ⚠ **THE BUILD DRAWS ITS COLUMNS IN ITS OWN ORDER AND THE OTHER TWO KEEP
  // THEIRS UNTOUCHED.** `03-work.png` puts SERVICE third, where the shared set
  // has it declared ninth and hidden; moving it in the array itself would
  // reorder the `Columns ▾` chooser on the property and the account for the
  // sake of one screen. So the array stays as it was and the BUILD host sorts
  // a copy of it.
  const arrange = (all: TableColumnConfig<ScopedWorkOrderRow>[]) =>
    onBuild ? [...all].sort((a, b) => buildColumnRank(a.key) - buildColumnRank(b.key)) : all;
  const config: TableConfig<ScopedWorkOrderRow> = {
    // Its own suffix per host: a dispatcher's column set on a property and on
    // an account are different questions, and `standsOn` below is why.
    screenId: onBuild
      ? "NCT-02.work-orders"
      : props.host === "premises"
        ? "PRM-02.work-orders"
        : "S21.work-orders",
    getRowId: (row) => row.id,
    searchFields: ["work", "what", "where", "crew"],
    // B14 rule 19 — the prompt names WHAT the box matches, and on the account
    // the blueprint writes the sentence itself: *"Search by order number, type
    // or technician"*.
    searchPlaceholder: onAccount
      ? "work.orders.atPlace.searchAccount"
      : "work.orders.atPlace.searchPlaceholder",
    // ⚠ **THE SORT IS FIXED ON THE ACCOUNT AND THERE IS NO COLUMN TO CLICK**
    // (`ACC-T08`). `defaultSort` still names a key because `TableRequestState`
    // requires one; no column on the account host declares `sortable`, so
    // nothing can change it, and `comparePriorityThenDue` is what actually
    // orders the rows.
    defaultSort: onAccount ? { sort: "priority", dir: "asc" } : { sort: "booked", dir: "asc" },
    filters: [
      {
        name: "state",
        label: t("work.orders.atPlace.col.status"),
        // `ACC-T08` draws four chips — `All` is the no-filter state the bar
        // already gives, and these are the other three. The property keeps the
        // two its own blueprint draws.
        options: onAccount
          ? [
              { value: "open", label: t("work.orders.atPlace.filter.open") },
              { value: "scheduled", label: t("work.orders.atPlace.filter.scheduled") },
              { value: "closed", label: t("work.orders.atPlace.filter.closed") },
            ]
          : [
              { value: "open", label: t("work.orders.atPlace.filter.open") },
              { value: "done", label: t("work.orders.atPlace.filter.done") },
            ],
      },
    ],
    columns: arrange([
      {
        // ⚠ **`Work` AND `What` ARE TWO COLUMNS AND WERE ONE CELL** (`DEF-4740`).
        // The number and the job were drawn `WO-4822 · Meter change` in a single
        // cell, so neither could be scanned down and neither could be sorted.
        key: "work",
        // `ACC-T08` names this column `ORDER #`; `P8` names it `Work`;
        // `03-work.png` names it `ORDER`. One column, three drawings, and each
        // gets its own word.
        label: onAccount
          ? t("work.orders.col.orderNo")
          : onBuild
            ? t("customers.connection.order.order")
            : t("work.orders.atPlace.col.work"),
        identity: true,
        // The account's sort is FIXED (`ACC-T08`), so no header on it is a
        // control a person can press.
        sortable: !onAccount,
        cell: (row) => (
          <span data-order-row={row.order_no ?? row.id}>
            {/* B14 rule 31 — `order_no` is what a clerk says on the phone. The
                id is never the visible value, so an unnumbered order draws a
                dash rather than a uuid. */}
            {/* Record links (PO 2026-10-19): the number opens the order's own
                page. The row click and the eye still open the drawer —
                `DataTable` ignores a click that lands on a link. */}
            {row.order_no === null ? (
              <Dash />
            ) : (
              <InlineLinkTo className="tabular-nums" to={tenantPath(workOrderDetailPath("", row.id).slice(1))}>
                {row.order_no}
              </InlineLinkTo>
            )}
            {row.is_gate && (
              <span
                className="ml-1"
                role="img"
                data-gate=""
                aria-label={t("customers.connection.order.gate")}
                title={t("customers.connection.order.gate")}
              >
                🚩
              </span>
            )}
          </span>
        ),
      },
      {
        key: "what",
        label: onAccount ? t("work.orders.col.type") : t("work.orders.atPlace.col.what"),
        cell: (row) => <span className="proportional-nums">{row.type}</span>,
      },
      {
        // ⚠ **DRAWN, SERVED, AND SHOWN ONLY INSIDE THE DRAWER UNTIL NOW**
        // (`DEF-4740`). `unit_label` has been on the scoped row since wave O.
        // *"Where, within the building, so a resident can be told whether it is
        // their flat."* A job standing on the address itself has no unit, and
        // that is an absence rather than a blank (the blueprint's RULES row).
        key: "where",
        // `03-work.png` names it `UNIT`, which is what it holds on a build:
        // every job is at the one address and the question is which unit.
        label: onBuild
          ? t("customers.connection.order.unit")
          : t("work.orders.atPlace.col.where"),
        // `ACC-T08` draws seven columns and WHERE is not one of them — every
        // job on this tab is at the account's own address. Nothing is deleted:
        // the column stays declared and the `Columns ▾` chooser is where a
        // clerk who wants it goes (`service`/`mode`/`outcome` already work
        // this way).
        defaultVisible: !onAccount,
        // ⚠ **ON A BUILD, NO UNIT IS A FACT AND NOT A GAP (`DEF-CUS-9178`).**
        // An order a build raised without naming a unit stands on the WHOLE
        // build, and the dash read as *unknown* to the PO. The property and
        // the account keep their dash: there an order with no unit may stand
        // on the address, an asset or the account, and `standsOn` says which.
        cell: (row) =>
          row.unit_label !== null ? (
            <span data-order-where={row.id}>{row.unit_label}</span>
          ) : onBuild ? (
            <span data-order-where={row.id} data-whole-build="">
              {t("customers.build.work.wholeBuild", { defaultValue: "Whole build" })}
            </span>
          ) : (
            <Dash />
          ),
      },
      {
        // ── `ACC-T08`'s PRIORITY ──────────────────────────────────────────
        // ⚠ **SERVED SINCE 2026-09-13 AND NOT BEFORE.** `work_orders.priority_id`
        // is stamped at the raise (`BR-WRK-018`) and reached only the
        // dispatcher's own list; `apps/work/selectors._scoped_row` serves it
        // here now, through `dispatch._priority_of`, so the pill takes the
        // TENANT's own colour and this screen invents none (B14 rule 31 — the
        // NAME is the visible value, never the id).
        //
        // ⚠ **A UTILITY THAT HAS SEEDED NO PRIORITIES HAS NOTHING TO SHOW, AND
        // THE CELL SAYS SO.** `BR-WRK-018` gives a typeless order no priority
        // and therefore no `due_at`; a blank cell would read as *ordinary*,
        // which is a claim about how urgent somebody's job is.
        key: "priority",
        label: t("work.orders.col.priority"),
        defaultVisible: onAccount,
        cell: (row) =>
          row.priority === null || row.priority === undefined ? (
            <Dash />
          ) : (
            <span data-priority={row.priority.code}>
              <StatusPill tone={row.priority.colour}>{row.priority.name}</StatusPill>
            </span>
          ),
      },
      {
        key: "crew",
        label: onAccount ? t("work.orders.col.technician") : t("work.orders.atPlace.col.crew"),
        // ⚠ **THE BUILD SPLITS THE HOLDER AND THE OTHER TWO HOSTS DO NOT.**
        // `03-work.png` draws CREW and TECHNICIAN side by side and the PO
        // removed the one-cell version; `dispatch._holder` answers with ONE
        // holder, `kind: "person"` for a technician and the crew's own kind
        // otherwise, so this cell shows a crew and states an absence for a
        // person. The property and the account render exactly the branch they
        // rendered before.
        cell: (row) =>
          onBuild ? (
            <span data-order-crew={row.order_no ?? row.id}>
              {row.technician === null ? (
                <AbsentValue reason={t("work.orders.atPlace.nobody")} />
              ) : row.technician.kind === "person" ? (
                <AbsentValue
                  reason={t("customers.build.work.noCrew", { defaultValue: "No crew named" })}
                />
              ) : (
                row.technician.name
              )}
            </span>
          ) : (
            <span data-order-who={row.order_no ?? row.id}>
              {row.technician === null ? (
                <span className="text-sm">{t("work.orders.atPlace.nobody")}</span>
              ) : (
                row.technician.name
              )}
            </span>
          ),
      },
      {
        key: "booked",
        // `ACC-T08` names this column `DUE`; `P8` names it `Booked`;
        // `03-work.png` names it `TARGET`. The CELL is the same either way —
        // `OrderWhenCell` answers *when*, which on a finished job is the day
        // it was done and on an unbooked one is the SLA deadline, labelled so
        // nobody reads it as a promise to a customer.
        label: onAccount
          ? t("work.orders.col.due")
          : onBuild
            ? t("customers.build.work.col.target", { defaultValue: "Target" })
            : t("work.orders.atPlace.col.booked"),
        sortable: !onAccount,
        cell: (row) => (
          <span data-order-when={row.order_no ?? row.id}>
            <OrderWhenCell
              order={row}
              t={t}
              timeZone={props.timeZone}
              dateFormat={props.dateFormat}
            />
          </span>
        ),
      },
      {
        key: "status",
        // `03-work.png` names it `STATE`, which is the word the build's own
        // vocabulary already uses everywhere else on that page.
        label: onBuild
          ? t("customers.connection.order.state")
          : t("work.orders.atPlace.col.status"),
        cell: (row) => (
          <StatusPill tone={orderStateTone(row.state)}>
            {t(`customers.connection.orderState.${row.state}`, {
              defaultValue: ORDER_STATE_LABELS[row.state] ?? row.state,
            })}
          </StatusPill>
        ),
      },
      {
        // ── `ACC-T08`'s RAISED BY ─────────────────────────────────────────
        // ⚠ **THE COLUMN EXISTED, WAS WRITTEN, AND REACHED ONLY THE
        // DISPATCHER.** `work_orders.source` is `BR-WRK-024`'s fourteen-value
        // vocabulary and its own model docstring says *"`Work-007` draws it as
        // RAISED BY"*; `_scoped_row` serves it from 2026-09-13. The screen
        // translates each value — never the raw token (`DEF-322`'s shape, a
        // dotted key on a clerk's screen) — and a job raised before any door
        // stamped one draws a dash rather than a guess.
        key: "raisedBy",
        label: t("work.orders.col.raisedBy"),
        defaultVisible: onAccount,
        cell: (row) =>
          row.source === null || row.source === undefined ? (
            <Dash />
          ) : (
            <span data-raised-by={row.source}>{t(`work.orders.source.${row.source}`)}</span>
          ),
      },
      {
        // ── AVAILABLE, NOT DEFAULT — AND NOTHING IS DELETED ────────────────
        // The blueprint draws SEVEN columns on the property tab and `Service`,
        // `Mode` and `Outcome` are drawn nowhere, so they come off the default
        // set. They stay declared, because the column chooser the shared table
        // brings IS where a capability like this belongs, and deleting them
        // would be a cut `CR-089` never asked for.
        key: "service",
        label: t("customers.connection.order.service"),
        // ⚠ **DRAWN THIRD ON THE BUILD AND NOWHERE ON THE OTHER TWO.**
        // `03-work.png` puts SERVICE between WHAT and UNIT — a build raises
        // one job per service and the tab is how a clerk sees which service
        // is still waiting — while `P8` and `ACC-T08` draw neither.
        defaultVisible: onBuild,
        cell: (row) =>
          row.service === null ? (
            <Dash />
          ) : (
            <span data-service={row.service}>
              {t(`work.orders.service.${row.service}`, { defaultValue: row.service })}
            </span>
          ),
      },
      {
        // ⚠ **DEFAULT ON THE ACCOUNT AND OFF ON THE PROPERTY, AND THAT IS
        // `US-WRK-004` RATHER THAN A PREFERENCE.** A person on an ACCOUNT sees
        // the move-out's final read (on the account), the meter exchange beside
        // it (on the asset) and the build's install jobs (on the build) in one
        // list, and a list that did not say which is which would be claiming
        // they are all the same kind of thing. On a PROPERTY the blueprint draws
        // seven columns and this is not one of them.
        key: "standsOn",
        label: t("work.orders.atPlace.col.standsOn"),
        // ⚠ **THIS WAS DEFAULT-ON FOR THE ACCOUNT AND `ACC-T08` DRAWS SEVEN
        // COLUMNS WITHOUT IT.** `US-WRK-004`'s reason for the column stands —
        // a person on an account sees jobs standing on the account, the asset
        // and the build in one list — so it is declared and reachable through
        // `Columns ▾`, exactly as `service`, `mode` and `outcome` are. The
        // drawing decides the DEFAULT set; nothing is deleted.
        defaultVisible: false,
        cell: (row) => (
          <span data-stands-on={row.stands_on}>
            {t(`work.orders.standsOn.${row.stands_on}`, {
              defaultValue: STANDS_ON_LABELS[row.stands_on] ?? row.stands_on,
            })}
          </span>
        ),
      },
      {
        key: "mode",
        label: t("customers.connection.order.mode"),
        defaultVisible: false,
        cell: (row) => (
          <span>
            {t(`customers.newConnect.mode.${row.mode}`, {
              defaultValue: MODE_LABELS[row.mode] ?? row.mode,
            })}
          </span>
        ),
      },
      {
        key: "outcome",
        label: t("customers.connection.order.outcome"),
        defaultVisible: false,
        cell: (row) =>
          row.outcome === null ? (
            <Dash />
          ) : (
            <span>
              {t(`customers.connection.outcome.${row.outcome}`, {
                defaultValue: OUTCOME_LABELS[row.outcome] ?? row.outcome,
              })}
            </span>
          ),
      },
      {
        key: "actions",
        label: t("customers.connection.order.actions"),
        cell: (row) => (
          // B14 rule 15 — row actions are glyphs with tooltips.
          <RowActions>
            <RowAction
              label={t("customers.connection.order.open")}
              icon={<EyeIcon />}
              onClick={() => props.onOpenOrder(row.id)}
            />
          </RowActions>
        ),
      },
      // ⚠ **DECLARED ONLY ON THE BUILD HOST.** A column with
      // `defaultVisible: false` is still an entry in the `Columns ▾` chooser,
      // so declaring it everywhere would change the property and the account
      // screens for the sake of one — and `DEF-CUS-7618`'s fix is not allowed
      // to move either of them.
      ...(onBuild ? [technicianColumn] : []),
    ]),
  };

  const wanted = state.filters.state ?? "";
  const matched = rows
    .filter((row) => orderMatchesGroup(row, wanted))
    .filter((row) => workOrderMatches(row, state.q));
  // ⚠ **THE ACCOUNT'S ORDER IS FIXED AND THE PROPERTY'S IS THE CLERK'S**
  // (`ACC-T08` vs `P8`). Priority rank then due time is the dispatcher's own
  // order, reused rather than re-derived — see `comparePriorityThenDue`.
  const sorted = onAccount
    ? [...matched].sort(comparePriorityThenDue)
    : [...matched].sort((a, b) => compareWorkOrders(a, b, state.sort, state.dir));
  const from = (state.page - 1) * state.per;
  const page = sorted.slice(from, from + state.per);

  // ⚠ **AN ADDRESS WITH NO JOBS AT ALL MUST READ AS GOOD NEWS, AND A DEFAULTED
  // FILTER WOULD HAVE STOPPED IT.** `DataTable` draws the screen's own empty
  // state only when nothing is searched and nothing is filtered — otherwise it
  // draws *no results, clear filters*, which is the right sentence for a filter
  // that hid something and the wrong one for a building nobody has ever raised
  // work on. The drawn `OPEN` chip is a default, so it would have turned the
  // blueprint's *"an empty list here is good news and should read like it"*
  // into a dead end on every quiet property. So when there is genuinely
  // nothing to filter, nothing is filtered: the chip row goes back to `All`
  // and the empty state is the tab's own.
  // `DEF-WRK-4752` (CR-168 ruling 35) — the door carries its subject: an
  // account opens the raise filled from the account (image 19); a premises or
  // a build opens it on that building, its units already listed (image 14).
  const raiseDoor =
    props.host === "account" ? accountRaisePath(props.hostId) : newOrderOnPremisesPath(props.hostId);
  const nothingHere = !listQuery.isPending && rows.length === 0;
  const tableState = nothingHere ? { ...state, q: "", filters: {} } : state;

  const table = (
    <Panel
      as="section"
      data-work-orders-tab={props.host}
      {...(onAccount
        ? { tone: "group" as const, "data-overview-group": "work-orders",
            title: t("work.orders.atPlace.title") }
        : {})}
    >
      {/* ⚠ **NO `<h3>` AND NO EXPLANATORY SENTENCE ABOVE THE TABLE.** The tab
          strip already says *Work orders*, and the blueprint's COGNITIVE LOAD
          row for this screen is *"Seven columns, one filter chip, no prose."*
          The sentence that stood here — *every job here, finished ones
          included* — is not deleted; it is in the closed disclosure at the
          foot, which is what B14 rule 32 asks for, and it matters more now that
          the drawn `OPEN` chip is applied on arrival. */}
      {/* ⚠ **NOT ON THE BUILD, AND THAT IS THE DUPLICATE-DOOR RULE RATHER
          THAN A CUT.** `NCT-02`'s page header already carries `Raise order`
          as the tab's primary action (`BR-SHL-044 (a)`), and the same act
          twice on one screen is what the Product Owner removed from that
          header on 2026-09-28 when they took `Open premises` and `Open
          account` off it. The EMPTY state below still offers it, because
          there is nothing above an empty table to duplicate. */}
      {!onBuild && (
      <div className="flex flex-wrap items-center justify-end gap-2 mb-3">
        {/* The drawn PRIMARY ACTION. Button grammar: ⚡ raises work (the
            blueprint's own RULES row) — *"with the property already the
            subject"*, which it now is (`DEF-WRK-4752`, fixed CR-168 round 3). */}
        <ButtonLink to={tenantPath(raiseDoor.slice(1))} variant="primary" data-raise-door={props.host}>
          {t("work.orders.atPlace.raise")}
        </ButtonLink>
      </div>
      )}

      <DataTable<ScopedWorkOrderRow>
        config={config}
        state={tableState}
        onStateChange={setState}
        rows={page}
        totalRows={listQuery.data === undefined ? null : matched.length}
        loading={listQuery.isPending}
        empty={{
          // The blueprint's STATES row: *"Says so, and offers to raise work —
          // an empty list here is good news and should read like it."* It said
          // *No jobs have been raised here.* and offered nothing.
          title: t("work.orders.atPlace.emptyTitle"),
          helper: t("work.orders.atPlace.emptyHelper"),
          ctaLabel: t("work.orders.atPlace.raise"),
          onCta: () => navigate(tenantPath(raiseDoor.slice(1))),
        }}
        filterBarSlot={
          <FilterBar filters={config.filters ?? []} state={tableState} onStateChange={setState} />
        }
      />

      {/* B14 rule 32 — a stated absence is CLOSED by default.
          ⚠ **NOT ON THE ACCOUNT, AND THE REASON IS THAT THE SENTENCE WOULD BE
          FALSE THERE** (hard-won law 1). It reads *"Every job here, finished
          ones included, newest first"* — and `ACC-T08` orders the account's
          list by priority rank then due time, which is the opposite claim. The
          account states its order in the footer line above instead, where the
          drawing puts it.
          ⚠ **NOR ON THE BUILD, FOR THE SAME REASON ONE LAYER ALONG.** It
          reads *"Every job here, finished ones included, newest first"* and
          the build host shows the jobs of ONE build at this address, sorted
          by target — two false clauses out of three (hard-won law 1). */}
      {!onAccount && !onBuild && (
        <Disclosure title={t("work.orders.atPlace.notes")}>
          <Note>{t("work.orders.atPlace.sentence")}</Note>
        </Disclosure>
      )}

      {/* `ACC-T08`'s footer reads *"1–4 of 4 · sorted by priority, then due
          time · Rows per page …"*. The pagination footer is the kit's and is
          not forked for one screen (B14 rule 38 — the UI rules own how a thing
          is BUILT), so the sentence sits directly under it. Five words: a FACT
          caps at six (rule 33). */}
      {onAccount && (
        <p
          className="m-0 mt-2 text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]"
          data-order-sort=""
        >
          {t("work.orders.atPlace.sortedBy")}
        </p>
      )}

      {openOrder !== null && (
        <WorkOrderPanel
          order={openOrder}
          t={t}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
          working={accept.isPending}
          onAccept={() => accept.mutate(openOrder.id)}
          onClose={() => props.onOpenOrder(null)}
          failure={accept.isError ? apiErrorText(accept.error, t) : null}
          // ⚠ WIRED HERE, AND THE WIRING IS THE POINT (hard-won law 2, `G13`).
          // The mutation already held this answer and nothing read it; an
          // optional prop no caller passes is a section that renders nothing
          // while every test passes. It is scoped to the OPEN order so that
          // closing the drawer and opening a second job does not show the
          // first job's letter under the second job's number.
          outcome={
            accept.data !== undefined && accept.data.id === openOrder.id ? accept.data : null
          }
        />
      )}
    </Panel>
  );

  /* ⚠ **THE CENSUS HOOKS ARE ON THE ACCOUNT HOST ONLY.**
     `data-account-overview` and `data-overview-group` are what
     `10-scripts/render-checks/acc02-tab-conformance.mjs` selects on, and they
     belong to `ACC-02`. The property page has its own blueprint and its own
     check; wrapping it here would put a second screen's hook on it. */
  return onAccount ? (
    <div data-account-overview="">
      <div className="flex min-w-0 flex-col">{table}</div>
    </div>
  ) : (
    table
  );
}

/**
 * `CR-089` wave C `C6` (`PUJ-16`) — **when is somebody coming.**
 *
 * ⚠ **THREE ANSWERS, AND THE SECOND ONE IS THE REASON THIS IS A COMPONENT AND
 * NOT A `DateCell`.**
 *
 *   · **an appointment window** — what a customer was actually PROMISED. Drawn
 *     as the date, with the window's hours beside it when both ends are known.
 *   · **an SLA deadline and no appointment** — `BR-WRK-018` stamps `due_at` at
 *     the raise from the priority's hours. It is an INTERNAL promise about how
 *     fast this utility answers, not a time anybody told the customer, so it
 *     is labelled *by* rather than printed bare. A clerk reading *Thursday*
 *     will say *Thursday* down the phone, and *due by Thursday* is the honest
 *     version of a job nobody has scheduled yet.
 *   · **neither** — *Not scheduled*, which is a real state and the one a
 *     dispatcher is there to clear. Never an empty cell.
 *
 * ⚠ **A FINISHED JOB SAYS WHEN IT WAS DONE.** *When is somebody coming* has a
 * past tense, and on a completed order the answer is a date that already
 * happened; showing a stale window or an expired deadline there would read as
 * a promise still outstanding.
 *
 * `BR-SHL-034`: every displayed date goes through the ONE shared formatter, in
 * the tenant's zone. There is no second date path here.
 */
export function OrderWhenCell(props: {
  order: ScopedWorkOrderRow;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { order, t } = props;
  const when = (value: string, withTime = false) => (
    <DateCell
      value={value}
      timeZone={props.timeZone}
      dateFormat={props.dateFormat}
      withTime={withTime}
    />
  );
  if (order.completed_at !== null) {
    return (
      <span data-when="completed">
        {t("work.orders.atPlace.completedOn")} {when(order.completed_at)}
      </span>
    );
  }
  if (order.window_start !== null) {
    return (
      <span data-when="window">
        {when(order.window_start, true)}
        {order.window_end !== null && (
          <>
            {" – "}
            {when(order.window_end, true)}
          </>
        )}
      </span>
    );
  }
  if (order.due_at !== null) {
    return (
      <span data-when="due">
        {t("work.orders.atPlace.dueBy")} {when(order.due_at)}
      </span>
    );
  }
  return (
    <span className="text-sm" data-when="none">
      {t("work.orders.atPlace.notScheduled")}
    </span>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE WORK-ORDER DRAWER — the button BR-MET-115 has been missing
// ══════════════════════════════════════════════════════════════════════════

/**
 * Why *Mark complete* cannot be pressed on this order, or null when it can.
 *
 * `BR-MET-110`: a person accepts what the FIELD sent, so there has to be
 * something to accept and it has to be unaccepted.
 */
export function acceptBlockedReason(order: ScopedWorkOrderRow, t: Translator): string | null {
  if (order.accepted_at !== null) {
    return t("customers.connection.order.whyAccepted");
  }
  if (order.state !== "completed") {
    return t("customers.connection.order.whyNotComplete");
  }
  return null;
}

/**
 * **WHAT THE LETTER ACTUALLY DID — the four answers `dispatch_communication`
 * can give, each in a clerk's own sentence.**
 *
 * ⚠ **THIS EXISTS BECAUSE THE TYPE ALREADY DEMANDED IT AND NO SCREEN OBEYED.**
 * `WorkOrderAcceptResult`'s own docstring has said, in capitals, *"`queued` CAN
 * BE `false` WITH A REASON, AND THE SCREEN MUST SAY SO"* since 2026-09-04 — and
 * until CR-070 wave L's leftovers the drawer threw the whole `communication`
 * answer away. The consequence box two sections below promises *"tells the
 * customer their service is live"*; on this platform today that letter is
 * REFUSED at the queue, so a supervisor pressed a button, read a promise, and
 * was never told the promise had not been kept. That is hard-won law 1 —
 * *"a comment claiming a guarantee is not the guarantee"* — with the comment in
 * a type and the guarantee in nobody's code.
 *
 * ⛔ **THE SERVER'S `unavailable` STRING IS NEVER PRINTED.** It names the
 * `SOURCE_TYPES` constant and lists its whole vocabulary; B14 rule 32 forbids
 * an internal code in clerk-facing copy. The SHAPE of the answer picks the
 * sentence, and the sentence is ours. The question it tracks travels in a DOM
 * attribute (`data-tracks`), which is not a visible value and therefore not a
 * rule 31 breach — a walkthrough can witness it and a clerk never sees it.
 *
 * ⚠ **`no_connection` IS NOT THE SAME ANSWER AS A REFUSAL AND MUST NOT SHARE A
 * SENTENCE** (`DEF-WRK-3635`). A leak investigation never had a new connection,
 * so no *your service is live* letter was ever due; the queue refusing one is a
 * platform gap. Telling a supervisor "cannot be sent yet" about a job that
 * never had a letter to send would teach them the product is broken.
 */
export function letterOutcome(
  communication: WorkOrderAcceptResult["communication"] | undefined,
  t: Translator,
): { sent: boolean; sentence: string; tracks?: string } | null {
  if (communication === undefined) {
    return null;
  }
  if (communication.queued) {
    return {
      sent: true,
      sentence: t("customers.connection.order.letterSent"),
    };
  }
  if (communication.already_sent === true) {
    return {
      sent: false,
      sentence: t("customers.connection.order.letterAlready"),
    };
  }
  if (communication.no_connection === true) {
    return {
      sent: false,
      sentence: t("customers.connection.order.letterNoBuild"),
    };
  }
  return {
    sent: false,
    sentence: t("customers.connection.order.letterHeld"),
    tracks: communication.tracks,
  };
}

/** `Work-003` — the drawer a supervisor accepts a job in, opened by the eye on
 *  either host's Work orders tab and by the approval queue's own eye. ONE
 *  acceptance, ONE place, whichever screen reached it. */
export function WorkOrderPanel(props: {
  order: ScopedWorkOrderRow;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  working: boolean;
  failure: string | null;
  /**
   * What the acceptance ANSWERED, or null before one has been made in this
   * session. Passed by `ScopedWorkOrdersTab` from the mutation's own data —
   * never optional-and-unpassed, which is hard-won law 2 and `G13`.
   */
  outcome: WorkOrderAcceptResult | null;
  onAccept: () => void;
  onClose: () => void;
}) {
  const { order, t } = props;
  const letter = letterOutcome(props.outcome?.communication, t);
  const blocked = acceptBlockedReason(order, t);
  const fieldEntries = Object.entries(order.field_data ?? {});
  return (
    <Panel as="section" accent data-work-order-panel={order.id}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <Kicker as="div">
            {t("customers.connection.order.kicker")}
          </Kicker>
          <h3>
            {order.order_no ?? ""} · {order.type}
          </h3>
        </div>
        <Button variant="secondary" size="sm" onClick={props.onClose}>
          {t("customers.connection.order.close")}
        </Button>
      </div>

      <PlainTable>
        <tbody>
          <tr>
            <td>{t("customers.connection.order.mode")}</td>
            <td>
              {t(`customers.newConnect.mode.${order.mode}`, {
                defaultValue: MODE_LABELS[order.mode] ?? order.mode,
              })}
            </td>
          </tr>
          <tr>
            <td>{t("customers.connection.order.scope")}</td>
            <td>
              {t(`customers.connection.scope.${order.scope}`, {
                defaultValue: SCOPE_LABELS[order.scope] ?? order.scope,
              })}
            </td>
          </tr>
          <tr>
            <td>{t("customers.connection.order.unit")}</td>
            <td>{order.unit_label ?? <Dash />}</td>
          </tr>
          <tr>
            <td>{t("customers.connection.order.completed")}</td>
            <td>
              {order.completed_at === null ? (
                <Dash />
              ) : (
                <DateCell
                  value={order.completed_at}
                  timeZone={props.timeZone}
                  dateFormat={props.dateFormat}
                />
              )}
            </td>
          </tr>
          <tr>
            <td>
              {t("customers.connection.order.externalRef")}
            </td>
            <td>{order.external_ref ?? <Dash />}</td>
          </tr>
          <tr>
            <td>{t("customers.connection.order.accepted")}</td>
            <td>
              {order.accepted_at === null ? (
                // ⚠ THIS NULL IS THE REVIEW QUEUE. It is the only thing in the
                // product that says the field sent data and no person has
                // accepted it — so it is a sentence, not a dash.
                <AbsentValue
                  reason={t("customers.connection.order.notAcceptedYet")}
                />
              ) : (
                <>
                  <DateCell
                    value={order.accepted_at}
                    timeZone={props.timeZone}
                    dateFormat={props.dateFormat}
                  />
                  {order.accepted_by !== null && (
                    <span className="ml-2">{order.accepted_by}</span>
                  )}
                </>
              )}
            </td>
          </tr>
        </tbody>
      </PlainTable>

      <h4 className="font-heading text-md m-0 mb-1 mt-4">
        {t("customers.connection.order.fieldData")}
      </h4>
      {fieldEntries.length === 0 ? (
        <Note className="max-w-measure">
          {t("customers.connection.order.noFieldData")}
        </Note>
      ) : (
        <PlainTable data-field-data="">
          <tbody>
            {fieldEntries.map(([key, value]) => (
              <tr key={key}>
                <td>{key}</td>
                <td>{String(value)}</td>
              </tr>
            ))}
          </tbody>
        </PlainTable>
      )}

      {/* ── THE PRESS ────────────────────────────────────────────────────
          BR-MET-110 + BR-MET-115: one human act, one auditable moment, three
          consequences — the data is accepted, the service goes live, and the
          customer is told. The consequence preview above the button is B14
          rule 11: this writes service state and sends a letter. */}
      <h4 className="font-heading text-md m-0 mb-1 mt-4">
        {t("customers.connection.order.markCompleteTitle")}
      </h4>
      <Note className="max-w-measure">
        {t("customers.connection.order.markCompleteWhat")}
      </Note>
      {props.failure !== null && <RefusalStrip>{props.failure}</RefusalStrip>}

      {/* ── WHAT THE PRESS ACTUALLY DID ──────────────────────────────────
          B14 rule 32 — ONE section, two facts, and no sentence explaining
          the mechanism. It renders only after an acceptance has answered in
          this session, because before that there is nothing to report and a
          permanently-present "not sent" would read as a standing failure.

          ⚠ THE SERVICE ROW IS THE FIRST PROMISE AND THE LETTER ROW IS THE
          THIRD (`BR-MET-110`: one human act, three consequences). The middle
          one — the field data is accepted — is the `Accepted` row in the table
          above, which now carries a date where it said *Nobody has accepted
          this yet*. All three are on the screen or none of them is honest. */}
      {letter !== null && (
        <section className="mt-4" data-accept-outcome="">
          <h4 className="font-heading text-md m-0 mb-1">
            {t("customers.connection.order.didTitle")}
          </h4>
          <PlainTable>
            <tbody>
              <tr>
                <td>{t("customers.connection.order.didService")}</td>
                <td>
                  {/* `null` on a job with no build — the server re-derives
                      nothing there and this prints the reason, never the word
                      "null" and never a guessed state (`DEF-WRK-3635`). */}
                  {props.outcome?.connection_state == null ? (
                    <AbsentValue
                      reason={t("customers.connection.order.didNoBuild")}
                    />
                  ) : (
                    <StatusPill tone={buildStateTone(props.outcome.connection_state)}>
                      {t(`customers.newConnects.state.${props.outcome.connection_state}`, {
                        defaultValue: props.outcome.connection_state,
                      })}
                    </StatusPill>
                  )}
                </td>
              </tr>
              <tr>
                <td>
                  {t("customers.connection.order.didLetter")}
                </td>
                <td data-letter-sent={letter.sent ? "yes" : "no"}>
                  {letter.sent ? (
                    <span>{letter.sentence}</span>
                  ) : (
                    // The dash CARRIES the sentence — a bare dash reads as
                    // "none" and this is "not sent, and here is why".
                    <AbsentValue reason={letter.sentence} tracks={letter.tracks} />
                  )}
                </td>
              </tr>
            </tbody>
          </PlainTable>
        </section>
      )}

      <div className="mt-3 flex flex-col items-start gap-1">
        {blocked === null ? (
          <WorkingButton working={props.working} onClick={props.onAccept}>
            {t("customers.connection.order.markComplete")}
          </WorkingButton>
        ) : (
          <>
            <Button disabled title={blocked}>
              {t("customers.connection.order.markComplete")}
            </Button>
            <Note as="span" className="max-w-measure">
              {blocked}
            </Note>
          </>
        )}
      </div>
    </Panel>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE CONNECTION CELL — the number a clerk quotes, linking to the build's home
// ══════════════════════════════════════════════════════════════════════════

/**
 * `Work-009`'s and the dispatcher's CONNECTION cell, written once.
 *
 * ⚠ **THE TEXT DID NOT CHANGE AND THE LINK DID** (wave O task `O5`).
 * `CON-26-0117` is a number a clerk quotes down a phone, not a database id, so
 * B14 rule 31 is satisfied and the column keeps its words. Where it GOES is the
 * build's home — the account that owns it, the premises otherwise — because
 * `/connections/<uuid>` stopped being a place a person navigates to.
 *
 * A build with no home draws the number as plain text. A link that silently
 * goes nowhere passes every test in this repo (law 6), so it is not offered.
 */
export function ConnectionCell(props: {
  connection: { connection_no: string | null; home: { kind: "premises" | "account"; id: string } | null } | null;
}): ReactNode {
  const tenantPath = useTenantPath();
  if (props.connection === null) {
    return <Dash />;
  }
  const text = props.connection.connection_no ?? "";
  if (props.connection.home === null) {
    return <span className="tabular-nums">{text}</span>;
  }
  return (
    <Link className="tabular-nums" to={tenantPath(buildHomePath(props.connection.home))}>
      {text}
    </Link>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-WRK-002 · US-WRK-004 (EP-WRK-01) · CR-070 §W.10 · §W.11 · 04-docs/05-modules/16-work/10-execution-plan.md wave O
// generated: 2026-09-04 by the CR-070 wave O build lane
// checklist: A✔ B✔ C✔ D✔ E✔(PremisesDetailPage and AccountDetailPage both render these) F✔ G✔ H=n/a(no 🔒 path; the money it prints is the server's own 2-dp string)
// gates: G13 (nothing here is an unwired prop) · G15 (every key in all eleven catalogues) · G31 (Tailwind only; this file is on route-b-migrated.txt in the commit that creates it) · G33 (every refusal five or six words) · G78 (the reads are Work's; the writes are metering's own doors) · vitest src/features/work/buildViews.test.tsx
// exceptions: E3 the TECHNICIAN column of `wireframes/Work-002.png` is NOT drawn — `work_orders` has no assignee column until wave G's `metering/000N`, and a column that can never carry a value is dead UI (law 2, G13). REPORTED, not faked · E3 the *Split into individual orders* button and the templates link the retired screen carried are NOT re-hosted: both were stated absences pointing at wave D/E work, and re-hosting a disabled control onto two screens doubles the thing law 2 is about · E3 the per-service progress blocks and the timeline of the retired screen's Overview are not re-hosted either — the premises' Audit log tab and the account's Audit tab are the trail (execution plan judgment 2), and a third copy is the duplicate destination one level down · E2 `addService` still posts a fixed `water` because the picker is `Work-028`'s form (wave G) — unchanged from wave B, carried across rather than quietly improved
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
