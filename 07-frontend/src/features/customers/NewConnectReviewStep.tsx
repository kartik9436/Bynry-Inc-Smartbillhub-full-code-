// ── Trace ──────────────────────────────────────────────
// Change:   `CR-150-BRC09` tasks 12, 13 and 14 — **STEP 5 · REVIEW, REDRAWN,
//           AND IT ABSORBS THE WHOLE COMMUNICATION STEP.** Built from
//           `05-prototype/new-connect-redesign-2026-09-28/step5-review.png`,
//           READ AS AN IMAGE (B14 rule 42), with spacing, sizes, the type
//           scale and the component kit from B14 (rule 44). The step was 8 (of
//           a nine that became eight) and is now **5 of 5**, titled *What will
//           be created*.
//
//           **FOUR THINGS THE DRAWING ASKS FOR:**
//             1 · an **At a glance** strip of nine counts, over the services;
//             2 · **four collapsible groups, each with an `Edit ›`** — which
//                 is `DEF-CUS-7613`, PO verbatim: *"the information
//                 architecture is not grouped in logical section and text is
//                 so much please reduce it"*;
//             3 · the **charge lines repeated** inside the charges group;
//             4 · the **Messages** table with `+ Add template` — the fold,
//                 whose field-by-field audit is §0 of
//                 `NewConnectCommunicationStep.tsx` and is a deliverable;
//             5 · **What pressing Create makes**, a row per record.
//
//           ⚠⚠ **THE CREATE TABLE NAMES ONLY WHAT `commit_connection`
//           ACTUALLY WRITES, AND FOUR OF THE DRAWN ROWS ARE THEREFORE NOT
//           WHAT THE DRAWING SAYS.** PO, verbatim: *"we create acounts,
//           custoemr iD if required, we create work orders, we create entries
//           in books - you will ahve to include all these changes"* — and a
//           row promising something the commit does not do is worse than no
//           table. Every row below was checked line by line against
//           `apps/metering/connections.py::commit_connection`; §2 records
//           what moved and why.
// Rules:    BR-MET-112 (this is the step that writes, and nothing before it
//           does) · BR-MET-105 (the empty-unit base charge accrues to the
//           owner — the second occupancy option) · BR-MET-114 (*"human will
//           mark everything to start with"* — outstanding work is stored and
//           human-authored) · BR-MET-116 / BR-MET-1010 (the owner's account) ·
//           BR-MET-1187 (the books entry and the payment, at creation) ·
//           CLAUDE.md hard rule 2 (money is the server's; never multiplied,
//           summed or rounded in a browser) · B14 rules 20, 21, 31, 32, 33,
//           37, 42, 43, 44
// Questions: ⛔ `OQ-376` (no `connection` source kind) — the queue holds ZERO
//           rows after a real commit and the table says so · `OQ-379`
//           (sub-meter links have no door from metering)
// Tests:    NewConnectReviewRedesign.dom.test.tsx ·
//           NewConnectSteps78.dom.test.tsx · NewConnectWizard.test.tsx
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// 1 · THE STEP NUMBER BEHIND EVERY `Edit ›` IS LOOKED UP, NEVER TYPED
// ══════════════════════════════════════════════════════════════════════════
// `GroupHead` used to take `step={1}`, `step={2}`, `step={3}` as literals.
// They happened to be right, and **"happens to be correct today" is exactly
// the state that rots the next time the steps move** — which is what this
// change request IS: eight steps became five, and a fourth group (Charges and
// payment) joined them at 4.
//
// So the number is resolved from `NEW_CONNECT_STEPS` by the step's **id**. One
// list decides the rail, the step line, the `?step=` parameter and these four
// links, so none of them can disagree, and a step inserted tomorrow moves all
// of them at once.
//
// ══════════════════════════════════════════════════════════════════════════
// 2 · WHAT `commit_connection` REALLY WRITES — THE DRAWING vs THE CODE
// ══════════════════════════════════════════════════════════════════════════
// Read off `apps/metering/connections.py::commit_connection`, in its own
// order. **Five of the drawn rows do not say what the commit does**, and each
// is corrected here rather than printed as drawn (B14 rule 37 — a drawn figure
// is an ILLUSTRATION, and `DEF-MET-5428` is what a promised count costs).
//
//   · **Premises — the drawing says `1 · On create`. THE COMMIT CREATES
//     NONE.** `made["premises"] = None`, with its own stated absence,
//     `premises_created_at_step_1_not_at_commit` (`DEF-2961`): the address
//     already exists by the time a commit runs, because `create_connection`
//     made it at step 1–2 and reports `premises_created` on its OWN response.
//     A manifest is a statement about what was WRITTEN, so the row says the
//     address is already there.
//   · **Meters and assets — drawn `On the work order`, and that is RIGHT for
//     the FITTING and wrong for the ROW.** The asset row is created at the
//     commit, through the assets seam, with **`installed=False`** — PO ruling
//     2026-09-21, *"you can generate meter, sub meter or asset # and assigned
//     it - but theya re not yet installed or actiavted"*. So: created on
//     create, FITTED on the work order, and the row says both.
//   · **Messages queued — the drawing says `3`. THE COMMIT QUEUES ZERO.**
//     `OQ-376` is open, the platform has no `connection` source kind, and all
//     three are refused BY NAME. A screen promising three would be the
//     Messages table's own STATE column contradicted one panel below it.
//   · **The two SHADED rows — `Entry in the books` and `Payment recorded` —
//     ARE NO LONGER SHADED, AND THE RED NOTE UNDER THE TABLE IS DELETED.**
//     The drawing's note reads *"The two shaded rows do not happen today. The
//     quote is kept as a figure on the build and no invoice is written, so the
//     charges never reach the books and nothing can be paid against them."*
//     **That was true and is now false.** `_post_connection_quote` raises and
//     ISSUES the invoice inside the commit's own transaction, writes
//     `quote_invoice_id` on the connection, and `_record_the_payment_taken`
//     records the payment against that bill in the same act (`BR-MET-1187`,
//     `CR-126-BRC07`). **A stated absence that outlives its cause is a lie the
//     product tells about itself** (hard-won law 1), so the note is DELETED
//     rather than reworded. ⚠ The drawing is the specification and this
//     contradicts it deliberately, on evidence, which is the one thing rule 37
//     exists to license.
//   · **Audit entry — the drawing says `1`. IT IS AT LEAST TWO** and there is
//     no count on the manifest to read, so **no number is printed.**
//     `commit_connection` calls `_stamp` (`connection.submitted`) and
//     `_audit` (`connection.committed`), and every module it orchestrates
//     writes its own besides. A `1` would be a figure this screen invented.
//
// **AND WHAT THE DRAWING GETS EXACTLY RIGHT**, each verified in the code:
// the customer record and its customer ID are created *only when the search
// found none* (`create_master_account` matches a customer first and creates
// one where no match exists — PO 2026-09-01, *"we have to create it if not
// matching customer ID not available"*); the owner's account is a MASTER
// account (`BR-MET-116`); units, plan assignments and work orders are all
// written at the commit; **sub-meter links are not written at all** and are
// reported as an absence rather than as `0`; and service starts on
// completion, never here.
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useSearchParams } from "react-router-dom";

import type { ApiClient } from "@/api/client";
import { getLookupEntries } from "@/api/endpoints";
import { MoneyCell } from "@/components/MoneyCell";
import { Panel } from "@/components/Panel";
import { InlineLink, PlainTable } from "@/components/Surfaces";
import { CellStatic, TableArray } from "@/components/TableArray";
import { Note } from "@/components/TextBits";
import { ServiceTags } from "@/features/rating/ratingShared";

import { CLASS_OF, MESSAGES, MessagesFold, WhoWeAreTelling } from "./NewConnectCommunicationStep";
import { paymentTermOptions } from "./NewConnectChargesStep";
import { getConnectTemplates } from "./newConnectEndpoints";
import { equipmentCounts, plannedAssets } from "./NewConnectUnitsStep";
import type { SizeRow } from "./NewConnectUnitsStep";
import { commitUnitServicesOf } from "./newConnectDraft";
import {
  buildChargeQuantities,
  buildOpensOwnerAccount,
  buildOpensOwnerRegular,
  ownerAccountKind,
  ownerLivesThere,
  connectModeWord,
  connectScopeWord,
  draftUnitServices,
  draftUnits,
  ownerMasterRefusedForSingleUnit,
} from "./newConnectDraft";
import type { BuildChargeLine, NewConnectDraft } from "./newConnectDraft";
//: `DEF-CUS-7911` — the review repeats step 4's lines, so it repeats step
//: 4's MONEY CELLS. Same preview, same renderer, no second opinion.
import { QuoteMoney, quoteFigureOf, useQuotePreview } from "./NewConnectChargesStep";
// ⚠ `NEW_CONNECT_STEPS` IS NO LONGER IMPORTED: this file used to read the
// list itself to work out a step number, and now asks
// `newConnectStepNumber(id)` for it instead — one answer to *which step is
// this*, owned by the file that owns the list. The prose above still names
// the list because the list is still where the answer comes from.
import { newConnectStepNumber } from "./newConnectShared";
import type { ManifestPreview, OccupancyChoice, Translator } from "./newConnectShared";
import { EmptyValue } from "./newConnectStepKit";

// ══════════════════════════════════════════════════════════════════════════
// WHICH STEP A GROUP EDITS — looked up by ID, never typed
// ══════════════════════════════════════════════════════════════════════════

/**
 * **THE POSITION OF A STEP, FROM ITS ID.**
 *
 * ⚠ **NO LITERAL STEP NUMBER APPEARS ON THIS SCREEN.** `NEW_CONNECT_STEPS` is
 * the one list the rail, the step line, `stepFromParam` and these four links
 * all read, so a step inserted or merged tomorrow moves every one of them at
 * once. Three of the four groups happened to be right as literals; that is
 * precisely the state this change request found and is fixing.
 *
 * ⚠ **AN UNKNOWN ID RESOLVES TO NOTHING AND THE LINK IS NOT DRAWN.** A `0`
 * would be a `?step=0` the wizard clamps back to 1, which is a link that
 * silently goes somewhere else — law 7's *looking at the wrong thing*. It
 * returns `null` and `ReviewGroup` renders no `Edit ›` for it, so a group
 * whose step has gone says so by having no control rather than by having a
 * broken one.
 */
/**
 * **THE POSITION OF A STEP, FROM ITS ID — the Model lane's helper, re-exported
 * under this file's own name so the four `Edit ›` links have one caller.**
 *
 * ⚠ **NO LITERAL STEP NUMBER APPEARS ON THIS SCREEN.** `NEW_CONNECT_STEPS` is
 * the one list the rail, the step line, `stepFromParam` and these four links
 * all read, so a step inserted or merged tomorrow moves every one of them at
 * once. Three of the four groups happened to be right as literals before this
 * change, and *"happens to be correct today"* is exactly the state that rots
 * the next time the steps move — which is what this change request IS.
 *
 * ⚠ **AN UNKNOWN ID RESOLVES TO `null` AND THE LINK IS NOT DRAWN.** A `0`
 * would be a `?step=0` the wizard clamps back to 1, which is a link that
 * silently goes somewhere else — law 7's *looking at the wrong thing*.
 *
 * ⚠ **A ONE-COMMIT ALIAS FOR `owner` → `customer` STOOD HERE AND IS DELETED.**
 * The Model lane's five-step list has landed and the first step's id IS
 * `customer`, so the bridge is dead code; keeping it would be a second answer
 * to *where is step one* that nothing exercises. The first run of
 * `NewConnectRedesignSteps45.dom.test.tsx` is what found the gap it covered —
 * the Customer group rendered no `Edit ›` at all — and that case still guards
 * it.
 */
export const stepNumberOf = newConnectStepNumber;

// ══════════════════════════════════════════════════════════════════════════
// THE READ-BACK'S SMALL PARTS
// ══════════════════════════════════════════════════════════════════════════

/** One read-back row: what it is on the left, what was answered on the right.
 *
 *  ⚠ **`[&&]:text-right` RATHER THAN `text-right`, AND IT IS NOT A TYPO.**
 *  `PlainTable` sets alignment through a descendant variant — `.[&_td]:text-left
 *  td` at specificity (0,1,1) — so a plain `.text-right` at (0,1,0) loses and
 *  the class sits in the DOM doing nothing. Doubling the selector is the idiom
 *  this kit already uses (`AssetInventoryTab`, `RoutesCyclesPage`). It is
 *  exactly the shape of a check that cannot fail: `tsc`, eslint and a
 *  `toContain("text-right")` all pass over the broken version. */
function FieldRow(props: { label: string; children: ReactNode }) {
  return (
    <tr>
      <td>{props.label}</td>
      <td className="[&&]:text-right" data-field-value="">
        {props.children}
      </td>
    </tr>
  );
}

/**
 * **ONE OF THE FOUR COLLAPSIBLE GROUPS — `step5-review.png`.**
 *
 * ⚠ **IT IS A NATIVE `<details>`, WHICH IS WHY IT IS KEYBOARD-REACHABLE FOR
 * FREE.** A `<div>` with an `onClick` is a clickable div — the UI method's
 * first never-do — and a hand-rolled disclosure has to re-implement Enter,
 * Space, the expanded state and the announcement. The drawing's own caption
 * says what opening does: *"Opened: each group expands to every field from
 * its step, read-only."*
 *
 * ⚠ **CLOSED BY DEFAULT**, which is B14 rule 32's own posture for a stated
 * absence and is what the drawing shows: four one-line summaries, and the
 * detail on demand. The PO's complaint was *"text is so much please reduce
 * it"*.
 *
 * ⚠ **THE `Edit ›` IS A `<button>`, NOT A LINK, AND IT DOES NOT NAVIGATE.**
 * The wizard reads its step from the URL and holds the whole draft in
 * component state (`BR-MET-112` — nothing is written until the last button),
 * so a client-side search-param change keeps the component mounted and every
 * answer alive. A real `<a href>` would reload and lose the lot. It is also
 * OUTSIDE the `<summary>`: a button inside a summary is a control inside a
 * control, and a press on it would toggle the group as well as jump.
 *
 * ⚠ **THE SUMMARY IS A FACT, ≤ 6 WORDS PER CLAUSE** (B14 rule 33), and it is
 * the drawing's own dot-separated shape.
 */
function ReviewGroup(props: {
  mark: string;
  label: string;
  stepId: string;
  summary: ReactNode;
  t: Translator;
  children: ReactNode;
}) {
  const [searchParams, setSearchParams] = useSearchParams();
  const step = stepNumberOf(props.stepId);
  return (
    <div className="mb-2 border border-divider bg-surface" data-review-group={props.mark}>
      <div className="flex items-start gap-3 p-3">
        <details className="flex-1">
          <summary className="cursor-pointer">
            <span className="font-medium">{props.label}</span>{" "}
            <span className="text-neutral-700" data-group-summary={props.mark}>
              {props.summary}
            </span>
          </summary>
          <div className="mt-2">{props.children}</div>
        </details>
        {step !== null && (
          <InlineLink
            data-group-edit={props.mark}
            data-edits-step={String(step)}
            onClick={() => {
              const query = new URLSearchParams(searchParams);
              query.set("step", String(step));
              setSearchParams(query, { replace: true });
            }}
          >
            {props.t("customers.newConnect.step8.edit", { defaultValue: "Edit" })}
          </InlineLink>
        )}
      </div>
    </div>
  );
}

/** `6 · electric, water, sewer` — the drawn shape, or the absence. */
function UnitCount(props: { count: number; services: readonly string[]; t: Translator }) {
  if (props.count === 0) {
    return <EmptyValue tracks="step-3" />;
  }
  return (
    <span className="tabular-nums">
      {props.count}
      {props.services.length === 0
        ? ""
        : ` · ${props.services
            .map((code) => props.t(`rating.service.${code}`, { defaultValue: code }))
            .join(", ")}`}
    </span>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// WHAT PRESSING CREATE MAKES — and every row is checked against the commit
// ══════════════════════════════════════════════════════════════════════════

/**
 * `step5-review.png`'s last table, **as the commit really behaves.**
 *
 * Each row carries `what · howMany · named · where · when`. `howMany` is a key
 * into the counts this screen already holds, or `null` where the commit
 * publishes no count — and **`null` draws the em dash, never a zero**, because
 * on this table a zero reads as *we made none* where the truth is often *this
 * cannot be counted here* (`commit_connection`'s own posture for `premises`
 * and `sub_meter_links`).
 *
 * ⚠ **`named` IS NEVER DRAWN FROM THE DRAWING.** `C-00011`, `AC-2026-00011`,
 * `cheque 4471` and `invoice no.` are ILLUSTRATIONS (B14 rule 37) and none of
 * them exists before the press — the customer number, the account number, the
 * invoice number and the receipt number are all ALLOCATED BY THE COMMIT and
 * come back on its manifest. The Done screen prints the real ones. Printing a
 * shape here would be `DEF-2961`'s defect: a screen reporting something
 * nothing produced.
 */
const WHAT_CREATE_MAKES = [
  // ⊕ **`CR-164-BRC10` item 47 — EVERY ROW SAYS ITS LIFECYCLE** (PO, with
  // "go": *"Step 5 · What Create makes - show lifecycle status of all items in
  // this list"*). `statusEn` is the state Create leaves the row in and, where it
  // moves, what moves it — read off the lifecycle `CR-162-BRC10` built
  // (`connection_activation.py`): premises, master account, customer, units and
  // service points are Pending until approval activates them; a device is in
  // Inventory until its work order installs it; the request runs Requested →
  // Partly activated → Activated. Words, never the stored code (B14 rule 31).
  {
    key: "customer",
    countKey: "customers",
    whatEn: "Customer record and ID",
    whereEn: "Accounts › Customers",
    whenEn: "On create",
    statusEn: "Pending → Active on approval",
  },
  {
    // ⊕ `DEF-CUS-9196` (item 28) — *Master account*, the PO's word, never
    // *the owner's account*. Counted by `buildOpensOwnerAccount` (master, or
    // ⊕ `DEF-CUS-9228` the single-family owner's own, worded *Owner's account*), which is
    // NC-A's premises-type rule (Q1), so a single-family home shows 0.
    key: "ownerAccount",
    countKey: "masterAccounts",
    whatEn: "Master account",
    whereEn: "Accounts",
    whenEn: "On create",
    statusEn: "Pending → Active on approval",
  },
  {
    // ⊕ `DEF-CUS-9197` (item 27) — Create MAKES the address when it is new
    // (`_premises_made_for_the_wizard`, inside the commit — `DEF-2961`'s
    // count), and it is Pending until approval (`CR-162-BRC10`). An address
    // picked from the register counts 0.
    key: "premises",
    countKey: "premises",
    whatEn: "Premises",
    whereEn: "Premises",
    whenEn: "On create",
    statusEn: "Pending → Active on approval",
  },
  {
    key: "units",
    countKey: "units",
    whatEn: "Units",
    whereEn: "Premises",
    whenEn: "On create",
    statusEn: "Pending → Active",
  },
  {
    key: "servicePoints",
    countKey: "servicePoints",
    whatEn: "Service points",
    whereEn: "Premises",
    whenEn: "On create",
    statusEn: "Pending → Active",
  },
  {
    // ⊕ items 29, 30 — meters and behind-the-meter devices are two rows.
    key: "meters",
    countKey: "meters",
    whatEn: "Meters",
    whereEn: "Assets",
    whenEn: "On create",
    statusEn: "Inventory → Installed",
  },
  {
    key: "behindTheMeter",
    countKey: "behindTheMeter",
    whatEn: "Behind-the-meter devices",
    whereEn: "Assets",
    whenEn: "On create",
    statusEn: "Inventory → Installed",
  },
  {
    key: "equipment",
    countKey: "equipment",
    whatEn: "Other equipment",
    whereEn: "Assets",
    whenEn: "On create",
    statusEn: "Inventory → Installed",
  },
  {
    key: "subMeterLinks",
    countKey: null,
    whatEn: "Sub-meter links",
    whereEn: "Assets",
    whenEn: "Not from here",
    statusEn: "",
  },
  {
    key: "planAssignments",
    countKey: "planAssignments",
    whatEn: "Plan assignments",
    whereEn: "Plans & Rates",
    whenEn: "On create",
    statusEn: "Billed from activation",
  },
  {
    key: "workOrders",
    countKey: "workOrders",
    whatEn: "Work orders",
    whereEn: "Work › Orders",
    whenEn: "On create",
    statusEn: "Planned",
  },
  {
    // ✔ `_post_connection_quote` raises and ISSUES the invoice inside the
    // commit's transaction.
    key: "booksEntry",
    countKey: "oneTimeCharges",
    whatEn: "Entry in the books",
    whereEn: "Billing & Finance",
    whenEn: "On create",
    statusEn: "Issued",
  },
  {
    // ✔ `_record_the_payment_taken`, against the bill just raised, in the same
    // act (`BR-MET-1187`).
    key: "payment",
    countKey: "paidNow",
    whatEn: "Payment recorded",
    whereEn: "Payments",
    whenEn: "On create",
    statusEn: "Recorded",
  },
  {
    // ⊕ `DEF-CUS-9198` / item 31 — the messages that have a template and are
    // still on the list, sent when the request is approved
    // (`connection_messages.fire_on_approval`, `BR-MET-115`, PO Q8).
    key: "messages",
    countKey: "messages",
    whatEn: "Messages",
    whereEn: "Notifications",
    whenEn: "On approval",
    statusEn: "Queued → Sent on approval",
  },
  {
    key: "audit",
    countKey: null,
    whatEn: "Audit entries",
    whereEn: "Settings › Audit",
    whenEn: "On create",
    statusEn: "",
  },
  {
    key: "request",
    countKey: "request",
    whatEn: "The request",
    whereEn: "Accounts › New connections",
    whenEn: "On create",
    statusEn: "Requested → Partly activated → Activated",
  },
] as const;

// ══════════════════════════════════════════════════════════════════════════
// STEP 5 · REVIEW
// ══════════════════════════════════════════════════════════════════════════

// ⚠ **`sub` IS NO LONGER RENDERED AND IS KEPT AS THE DEFINITION IT IS (PO
// 2026-09-28, reported bug 1).** The four glosses used to print under the
// radio; the redesign drawing lists them under *Removed from this step* and
// B14 rule 33 gives that kind of sentence zero words on screen. They stay here
// because this table IS where the four choices are defined, and rule 33 puts
// rationale in the code. **Do not re-mount them on a screen** — that is the
// deletion being undone, not a gap being filled.
//
// ⚠ **AND THE RADIO ITSELF IS GONE FROM THIS STEP — `DEF-CUS-7613`.**
// Occupancy is asked ON THE UNIT ROWS at step 3 now (`draft.unitOccupancy`),
// and this step SHOWS it without asking it. `OCCUPANCY_COPY` is still the
// vocabulary both screens read, which is why it is still exported from here.
export const OCCUPANCY_COPY = [
  {
    code: "vacant_service_off",
    en: "Vacant · service off, billing nobody",
    sub: "The default. Nothing is billed on a unit until somebody moves in.",
  },
  {
    code: "vacant_base_only",
    en: "Vacant · base charges only",
    sub: "The monthly base charge accrues on each empty unit, to the owner's account.",
  },
] as const;

/** The word for an occupancy choice — the vocabulary above, never the code
 *  (B14 rule 31, and `DEF-CUS-6100` is the row where `our_crew` reached a
 *  clerk on this very screen). */
function occupancyWord(t: Translator, code: OccupancyChoice): string {
  const row = OCCUPANCY_COPY.find((one) => one.code === code);
  return String(
    t(`customers.newConnect.occupancy.${code}`, { defaultValue: row?.en ?? String(code) }),
  );
}

export function ReviewStep(props: {
  draft: NewConnectDraft;
  manifest: ManifestPreview;
  /**
   * **THE QUOTE'S 4-DECIMAL `stored` FIGURE AND ITS `CHAR(3)`.**
   *
   * ⚠ **BOTH ARE REQUIRED PROPS, NOT OPTIONAL ONES** (hard-won law 2): an
   * optional currency nothing passes is a cell that silently prints a bare
   * number, which is the defect the PO reported on 2026-09-28 (`1035.00`
   * where every other money cell shows `$1,035.00`). `null` is a real answer
   * — the preview has not answered, or the tenant's currency could not be
   * read — and is never guessed at here (hard rule 2: money travels with its
   * currency).
   */
  quoteTotal: string | null;
  quoteCurrency: string | null;
  /**
   * ⊕ **`DEF-CUS-9197` — HOW MANY WORK ORDERS THE COMMIT WILL RAISE**: one per
   * surviving proposal, `commitPlanOf`'s own `work_orders`. REQUIRED, so a host
   * cannot mount this step without the figure (hard-won law 2); step 3's tile
   * reads the same list.
   */
  workOrderCount: number;
  onPatch: (next: Partial<NewConnectDraft>) => void;
  t: Translator;
  client?: ApiClient;
}) {
  const services = draftUnitServices(props.draft);
  const mappedServices = Array.from(new Set(Object.values(services).flat())).sort();
  const units = draftUnits(props.draft);
  const dwellings = units.filter((unit) => !unit.isCommonArea);
  const commonAreas = units.filter((unit) => unit.isCommonArea);
  /**
   * **THE SERVICE POINTS THIS BUILD WILL HAVE** — one per unit × service.
   *
   * ⚠ **IT IS THE SAME DERIVATION THE COMMIT WRITES FROM.** `commit_connection`
   * step 2b writes one `connection_services` row per unit × service, in the
   * same pass that raises the service points, and `draftUnitServices` is the
   * ONE derivation step 3's grid, step 4's counts and this strip all read. A
   * second count here is how a screen comes to promise a figure the server
   * does not raise (`DEF-MET-5428`).
   */
  const servicePoints = Object.values(services).reduce((n, list) => n + list.length, 0);
  const quantities = buildChargeQuantities(props.draft);
  /**
   * **THE PRICED LINES, FROM THE SERVER — `DEF-CUS-7911`.**
   *
   * ⚠ **THE SAME CACHED `quote-preview` STEP 4 READS**, by the same query key,
   * so the review cannot disagree with the step it summarises. `Each` and
   * `Amount` are the server's own `display` strings; **nothing on this screen
   * multiplies a quantity by a price** (hard rule 2, `DEF-088`, `DEF-127`).
   *
   * ⚠ **AN UNPRICED LINE DRAWS A BLANK, NEVER `$0.00`** — `quoteFigureOf`
   * returns `null` for a figure the server did not send, and a zero on a money
   * line reads as *free* where the truth is *not priced*.
   */
  const reviewQuote = useQuotePreview(props.draft, props.client).data;
  const reviewPriced = new Map(
    (reviewQuote?.lines ?? []).map((line) => [
      `${line.charge_code}|${line.basis ?? ""}`,
      line,
    ]),
  );
  const dwellingServices = Array.from(
    new Set(dwellings.flatMap((unit) => services[unit.label] ?? [])),
  ).sort();
  const commonAreaServices = Array.from(
    new Set(commonAreas.flatMap((unit) => services[unit.label] ?? [])),
  ).sort();

  /** What each row of *What pressing Create makes* counts, by its `countKey`.
   *  ⚠ **NOT ONE OF THEM IS COMPUTED FROM MONEY.** `oneTimeCharges` and
   *  `paidNow` are figures, so they are rendered by `MoneyCell` from the
   *  server's own string and the clerk's own string; every other entry is a
   *  COUNT of rows. */
  const assetTypes = useQuery({
    // The SAME key step 3 reads, so this is a cache hit, never a second list.
    queryKey: ["lookups", "asset_types", "new-connect"],
    queryFn: () => getLookupEntries("asset_types", { per: 200 }, props.client),
  });
  const equipment = equipmentCounts(
    props.draft,
    units,
    (assetTypes.data?.results ?? []) as { code: string; name: string; category?: string }[],
  );
  /**
   * ⊕ **`DEF-CUS-9840` — EVERY ASSET CREATE WILL MAKE, ONE LINE EACH**, read
   * off the commit's own `unit_services` payload (PO ruling (a), 2026-10-06:
   * *"we have to create those many assets and tag them to unit"*). Names come
   * from the same two catalogues step 3 reads, by the same keys (cache hits).
   */
  const sizeLookup = useQuery({
    queryKey: ["lookups", "service_size_classes", "new-connect"],
    queryFn: () => getLookupEntries("service_size_classes", { per: 200 }, props.client),
  });
  const typeNames = new Map(
    ((assetTypes.data?.results ?? []) as { code: string; name: string }[]).map((row) => [row.code, row.name]),
  );
  const sizeNames = new Map(
    ((sizeLookup.data?.results ?? []) as SizeRow[]).map((row) => [row.code, row.name]),
  );
  const assetsPlanned = plannedAssets(commitUnitServicesOf(props.draft, units, services));
  /** ⊕ `CR-164-BRC10` — a NEW address is made by Create; a picked one is not. */
  const premisesMade =
    props.draft.premise.premisesId === "" && props.draft.premise.address.trim() !== "" ? 1 : 0;
  // ⊕ item 31 — the messages that WILL go on approval: on the list, and with
  // a published template (the Messages table's own *Sent on approval* rows).
  // The SAME query key `MessagesFold` reads, so this is a cache hit.
  const templateRows = useQuery({
    queryKey: ["connect-message-templates", ""],
    queryFn: () => getConnectTemplates("", props.client),
  });
  const messagesSent =
    templateRows.data === undefined
      ? null
      : MESSAGES.filter(
          (message) =>
            !props.draft.messagesOff.includes(message.code) &&
            (templateRows.data?.rows ?? []).some(
              (row) => row.code === CLASS_OF[message.code] && row.pickable,
            ),
        ).length;
  const ownersOwnAccount = buildOpensOwnerRegular(props.draft);
  const counts: Record<string, number | null> = {
    customers: props.manifest.customers,
    // ⊕ `DEF-CUS-9228` — the master account, or on a single-family home the
    // owner's own account (PO 2026-10-02, item 1); the row says which.
    masterAccounts: buildOpensOwnerAccount(props.draft) ? 1 : 0,
    premises: premisesMade,
    units: props.manifest.units,
    servicePoints,
    meters: assetTypes.data === undefined ? null : equipment.meters + equipment.subMeters,
    behindTheMeter: assetTypes.data === undefined ? null : equipment.behindTheMeter,
    equipment: assetTypes.data === undefined ? null : equipment.other,
    planAssignments: props.manifest.planAssignments,
    workOrders: props.workOrderCount,
    messages: messagesSent,
    request: 1,
  };
  const moneyKeys = new Set(["oneTimeCharges", "paidNow"]);

  return (
    <>
      {/* ══════════════════════════════════════════════════════════════════
          AT A GLANCE — nine cells, then the services
          ══════════════════════════════════════════════════════════════════
          ⚠ **EVERY CELL IS A COUNT OF ROWS OR A SERVER MONEY FIGURE.** Nothing
          here is added up, multiplied or rounded (hard rule 2), and nothing is
          taken off the drawing: `1 new`, `3`, `12`, `$1,035.00` are all
          ILLUSTRATIONS (B14 rule 37). */}
      <Panel as="section">
        <h4 className="font-heading text-md m-0 mb-1">
          {props.t("customers.newConnect.review.atAGlance", { defaultValue: "At a glance" })}
        </h4>
        <div
          className="grid grid-cols-5 border border-divider bg-surface max-lg:grid-cols-2"
          data-at-a-glance=""
        >
          <GlanceCell
            what={props.t("customers.newConnect.manifest.customers", {
              defaultValue: "Customer",
            })}
            mark="customers"
          >
            <span className="tabular-nums">{props.manifest.customers}</span>
          </GlanceCell>
          {/* ⚠ **NOT CREATED AT THE COMMIT** (`DEF-2961`) — the address exists
              before the draft does. The count is what the build HAS. */}
          <GlanceCell
            what={props.t("customers.newConnect.manifest.premises", { defaultValue: "Premises" })}
            mark="premises"
          >
            <span className="tabular-nums">{premisesMade}</span>
          </GlanceCell>
          <GlanceCell
            what={props.t("customers.newConnect.manifest.units", { defaultValue: "Units" })}
            mark="units"
          >
            <span className="tabular-nums">{props.manifest.units}</span>
          </GlanceCell>
          <GlanceCell
            what={props.t("customers.newConnect.review.servicePoints", {
              defaultValue: "Service points",
            })}
            mark="service-points"
          >
            <span className="tabular-nums">{servicePoints}</span>
          </GlanceCell>
          {/* ⊕ items 21, 29 — meters and behind-the-meter devices apart, each
              from the tenant's own asset-type category. */}
          <GlanceCell
            what={props.t("customers.newConnect.manifest.meters", { defaultValue: "Meters" })}
            mark="meters"
          >
            <GlanceCount value={counts.meters} />
          </GlanceCell>
          <GlanceCell
            what={props.t("customers.newConnect.review.behindTheMeter", {
              defaultValue: "Behind the meter",
            })}
            mark="behind-the-meter"
          >
            <GlanceCount value={counts.behindTheMeter} />
          </GlanceCell>
          {/* ⚠ **NOT A ZERO.** `commit_connection` returns
              `sub_meter_links: None` with its own stated reason — a sub-meter
              link is an assets relationship this module has no door to
              (`OQ-379`) — and a zero would read as *we made none* where the
              truth is *we cannot make them from here*. */}
          <GlanceCell
            what={props.t("customers.newConnect.manifest.subMeterLinks", {
              defaultValue: "Sub-meter links",
            })}
            mark="sub-meter-links"
          >
            <EmptyValue tracks="OQ-379" />
          </GlanceCell>
          {/* ⛔ **A ZERO HERE IS A REFUSAL, NOT A COUNT — PO ruling
              2026-09-21, *"ask for plan"*.** This printed `0` as a plain fact
              and the clerk pressed anyway; the server then refused the whole
              build because `_apply_unit_plan` will not take an empty
              `tariff_id`. ⚠ It counts DWELLINGS ONLY: a common area is sent no
              plan and needs none. */}
          <GlanceCell
            what={props.t("customers.newConnect.manifest.planAssignments", {
              defaultValue: "Plan assignments",
            })}
            mark="plan-assignments"
          >
            {props.manifest.planAssignments === 0 ? (
              <>
                {/* ⚠ **`step-3`, NOT `step-2` — THERE IS NO PLANS STEP ANY
                    MORE.** Under the old eight a plan had a step of its own;
                    the five-step list folds units, services and plans into
                    ONE step 3, so the handle that says *where this value gets
                    filled* had to move with it. Invisible to the reader
                    (`aria-hidden`), which is exactly why it rots unnoticed. */}
                <EmptyValue tracks="step-3" />
                <Note as="span" className="ml-2">
                  {props.t("customers.newConnect.step3.planRequired", {
                    defaultValue: "Choose a plan for the units.",
                  })}
                </Note>
              </>
            ) : (
              <span className="tabular-nums">{props.manifest.planAssignments}</span>
            )}
          </GlanceCell>
          {/* ⛔ **NO COUNT, AND `DEF-MET-5428` IS WHY.** The commit DOES raise
              the work orders and reports `manifest.work_orders` — but only
              AFTER the press. The only figure this screen could print before
              it is the proposal it showed itself at step 3, which is exactly
              the number that agreed with itself for eleven days while the
              server raised none. The Done screen reads the manifest and
              prints the real one. */}
          <GlanceCell
            what={props.t("customers.newConnect.review.workOrders", {
              defaultValue: "Work orders",
            })}
            mark="work-orders"
          >
            {/* ⊕ `DEF-CUS-9197` — the count the commit raises, the figure step
                3's tile shows. It was a dash after `DEF-MET-5428`, when the
                commit raised none; it raises one per surviving proposal now. */}
            <span className="tabular-nums">{props.workOrderCount}</span>
          </GlanceCell>
          {/* ⚠ **`$1,035.00`, NEVER `1035.00` AND NEVER `$0.00`.**
              `MoneyCell` is the ONE formatting path (`BR-SHL-023`), given the
              server's 4-decimal `stored` figure with the tenant's `CHAR(3)`.
              Nothing is multiplied, summed or rounded here (hard rule 2,
              `DEF-088`). The dash is NOT replaced by a zero: a zero on a money
              line reads as *free* and the truth is *not priced*. */}
          <GlanceCell
            what={props.t("customers.newConnect.manifest.charges", {
              defaultValue: "One-time charges",
            })}
            mark="one-time-charges"
          >
            {props.quoteTotal !== null && props.quoteCurrency !== null ? (
              <MoneyCell amount={props.quoteTotal} currency={props.quoteCurrency} />
            ) : (
              <EmptyValue tracks="step-4" />
            )}
          </GlanceCell>
        </div>
        {/* `BR-CUS-1114` (PO 2026-10-02) — a single-unit build opens no
            owner's master account; the applicant gets a regular one. */}
        {ownerMasterRefusedForSingleUnit(props.draft) && (
          <Note className="mt-2 max-w-measure" data-owner-master-single-unit="">
            {props.t("customers.account.master_needs_two_units", {
              defaultValue: "Single unit. Open a regular account.",
            })}
          </Note>
        )}
        <Note className="mt-2 max-w-measure">
          {props.t("customers.newConnect.step9.services", {
            defaultValue: "Services mapped on this build:",
          })}{" "}
          {mappedServices.length === 0 ? (
            props.t("customers.newConnect.step9.noServices", { defaultValue: "none yet" })
          ) : (
            <ServiceTags services={mappedServices} />
          )}
        </Note>
      </Panel>

      {/* ══════════════════════════════════════════════════════════════════
          FOUR COLLAPSIBLE GROUPS, EACH WITH AN `Edit ›` — `DEF-CUS-7613`
          ══════════════════════════════════════════════════════════════════
          ⚠ **AN EMPTY VALUE IS AN EM DASH AND NOTHING ELSE (PO 2026-09-28).**
          Six cells of this read-back used to draw the dash and then a sentence
          saying why — *"Not answered yet."* four times over — so a build a
          clerk had barely started read as a page of apologies. `EmptyValue`
          keeps each cell's `tracks` id invisibly (`DEF-332`). */}
      <Panel as="section">
        <ReviewGroup
          mark="customer"
          stepId="customer"
          t={props.t}
          label={props.t("customers.newConnect.review.groupCustomer", {
            defaultValue: "Customer",
          })}
          summary={
            props.draft.owner.name.trim() === "" ? (
              <EmptyValue tracks="step-1" />
            ) : (
              `· ${props.draft.owner.name.trim()} · ${connectScopeWord(props.draft.scope, props.t)}`
            )
          }
        >
          <PlainTable data-group-fields="customer">
            <tbody>
              <FieldRow
                label={props.t("customers.newConnect.step8.owner", {
                  defaultValue: "Owner or developer",
                })}
              >
                {props.draft.owner.name.trim() === "" ? (
                  <EmptyValue tracks="step-1" />
                ) : (
                  props.draft.owner.name
                )}
              </FieldRow>
              <FieldRow
                label={props.t("customers.newConnect.step7.email", { defaultValue: "Email" })}
              >
                {props.draft.owner.email.trim() === "" ? (
                  <EmptyValue tracks="step-1" />
                ) : (
                  props.draft.owner.email
                )}
              </FieldRow>
              <FieldRow
                label={props.t("customers.newConnect.step7.phone", { defaultValue: "Phone" })}
              >
                {props.draft.owner.phone.trim() === "" ? (
                  <EmptyValue tracks="step-1" />
                ) : (
                  props.draft.owner.phone
                )}
              </FieldRow>
              {/* ── `DEF-CUS-6100` · THE WORD, NEVER THE STORED VALUE ────────
                  ⚠ **THIS ROW PRINTED `our_crew` ON THE LAST SCREEN BEFORE THE
                  COMMIT, ON EVERY ONE OF SEVEN BUILDS WALKED.** B14 rule 31
                  (no database value is ever visible) and rule 32 (no internal
                  code in clerk-facing copy). `connectModeWord` and
                  `connectScopeWord` are the only two ways either fact is read,
                  and each FAILS LOUDLY rather than falling back to the code. */}
              <FieldRow
                label={props.t("customers.newConnect.step8.scope", { defaultValue: "Scope" })}
              >
                {connectScopeWord(props.draft.scope, props.t)}
              </FieldRow>
              <FieldRow
                label={props.t("customers.newConnect.step8.mode", {
                  defaultValue: "How the work is done",
                })}
              >
                {connectModeWord(props.draft.mode, props.t)}
              </FieldRow>
              {/* ⚠ **DRAWN AS `SR-26-0001 · approved 05/04/2026` AND THERE IS
                  NO FIELD BEHIND IT.** A build raised from an approved request
                  carries one; this wizard never asks, and `NewConnectDraft`
                  has no member for it. Rendering the drawn value would be
                  `DEF-2961`'s shape — a screen reporting something nothing
                  produced. */}
              <FieldRow
                label={props.t("customers.newConnect.step8.fromRequest", {
                  defaultValue: "From request",
                })}
              >
                {props.draft.requestNo === null ? (
                  <EmptyValue tracks="from_request" />
                ) : (
                  props.draft.requestNo
                )}
              </FieldRow>
            </tbody>
          </PlainTable>
        </ReviewGroup>

        <ReviewGroup
          mark="premise"
          stepId="premise"
          t={props.t}
          label={props.t("customers.newConnect.review.groupPremise", {
            defaultValue: "Premise",
          })}
          summary={
            props.draft.premise.address.trim() === "" ? (
              <EmptyValue tracks="step-2" />
            ) : (
              `· ${props.draft.premise.address.trim()}`
            )
          }
        >
          <PlainTable data-group-fields="premise">
            <tbody>
              <FieldRow
                label={props.t("customers.newConnect.step8.address", {
                  defaultValue: "Service address",
                })}
              >
                {props.draft.premise.address.trim() === "" ? (
                  <EmptyValue tracks="step-2" />
                ) : (
                  props.draft.premise.address
                )}
              </FieldRow>
              <FieldRow
                label={props.t("customers.newConnect.step8.parcel", { defaultValue: "Import reference" })}
              >
                {props.draft.premise.parcelRef.trim() === "" ? (
                  <EmptyValue tracks="step-2" />
                ) : (
                  props.draft.premise.parcelRef
                )}
              </FieldRow>
              <FieldRow
                label={props.t("customers.newConnect.step8.route", {
                  defaultValue: "Read route",
                })}
              >
                {props.draft.premise.readRoute.trim() === "" ? (
                  <EmptyValue tracks="step-2" />
                ) : (
                  props.draft.premise.readRoute
                )}
              </FieldRow>
            </tbody>
          </PlainTable>
        </ReviewGroup>

        <ReviewGroup
          mark="units"
          stepId="units"
          t={props.t}
          label={props.t("customers.newConnect.review.groupUnits", {
            defaultValue: "Units and work",
          })}
          summary={
            units.length === 0 ? (
              <EmptyValue tracks="step-3" />
            ) : (
              `· ${units.length} · ${servicePoints}`
            )
          }
        >
          <PlainTable data-group-fields="units">
            <tbody>
              <FieldRow
                label={props.t("customers.newConnect.step8.prefix", { defaultValue: "Prefix" })}
              >
                {props.draft.pattern.prefix.trim() === "" ? (
                  <EmptyValue tracks="step-3" />
                ) : (
                  props.draft.pattern.prefix
                )}
              </FieldRow>
              {/* ⚠ **READ OFF `draftUnitServices`, NEVER OFF
                  `apartmentServices`.** Those bulk sets STOPPED deciding what
                  a unit takes when step 3 became a grid — PO: *"units inherit
                  all utility services from premises"* — and a read-back
                  rendering them would show the answer BEFORE the clerk's
                  per-unit deviations, which is the one thing a read-back
                  exists to catch. */}
              <FieldRow
                label={props.t("customers.newConnect.step8.dwellings", {
                  defaultValue: "Dwellings",
                })}
              >
                <UnitCount count={dwellings.length} services={dwellingServices} t={props.t} />
              </FieldRow>
              <FieldRow
                label={props.t("customers.newConnect.step8.commonArea", {
                  defaultValue: "Common area",
                })}
              >
                <UnitCount count={commonAreas.length} services={commonAreaServices} t={props.t} />
              </FieldRow>
              {/* ⚠ **SHOWN, NOT ASKED — `DEF-CUS-7613`.** Occupancy moved onto
                  the unit rows at step 3; this is the build's DEFAULT for a
                  unit the clerk did not move, in words and never as the
                  stored code (B14 rule 31). */}
              <FieldRow
                label={props.t("customers.newConnect.step9.occupancyLabel", {
                  defaultValue: "Occupancy",
                })}
              >
                {occupancyWord(props.t, props.draft.occupancy)}
              </FieldRow>
              {/* ⊕ `DEF-CUS-9840` — one line per asset: *PV panel · Solar panel
                  10 kW · Unit 1*. Absent when Create makes none. */}
              {assetsPlanned.length > 0 && assetTypes.data !== undefined && sizeLookup.data !== undefined && (
                <FieldRow
                  label={props.t("customers.newConnect.review.assets", { defaultValue: "Assets" })}
                >
                  <span data-planned-assets={assetsPlanned.length}>
                    {assetsPlanned.map((asset, index) => (
                      <span key={index} className="block" data-planned-asset="">
                        {[typeNames.get(asset.type), sizeNames.get(asset.size), asset.unit].filter(Boolean).join(" · ")}
                      </span>
                    ))}
                  </span>
                </FieldRow>
              )}
            </tbody>
          </PlainTable>
        </ReviewGroup>

        {/* ══════════════════════════════════════════════════════════════
            CHARGES AND PAYMENT — the fourth group, and it REPEATS THE LINES
            ══════════════════════════════════════════════════════════════
            ⚠ **THE LINES ARE READ-ONLY HERE AND EDITABLE ON STEP 4**, which
            is what the drawing shows and what `Edit ›` is for. `TableArray`'s
            `readOnly` is that exact shape, so this is the same component as
            the charges step rather than a second table (B14 rules 20 and 43).

            ⚠ **EVERY MONEY FIGURE IS THE SERVER'S.** `Each` and `Amount` come
            from `POST /connections/quote-preview` through the props this
            component is handed; nothing on this screen multiplies a quantity
            by a price (hard rule 2, `DEF-088`, `DEF-127`). */}
        <ReviewGroup
          mark="charges"
          stepId="charges"
          t={props.t}
          label={props.t("customers.newConnect.review.groupCharges", {
            defaultValue: "Charges and payment",
          })}
          summary={
            <ChargesSummary
              draft={props.draft}
              t={props.t}
              total={props.quoteTotal}
              currency={props.quoteCurrency}
            />
          }
        >
          <TableArray<BuildChargeLine>
            readOnly
            collection="review-charges"
            title={props.t("customers.newConnect.step6.lines", {
              defaultValue: "What is charged",
            })}
            rows={props.draft.quoteLines}
            rowKey={(line, index) => `${line.chargeCode}-${line.basis}-${index}`}
            emptyText={props.t("customers.newConnect.step6.noLines")}
            columns={[
              {
                key: "charge",
                label: props.t("customers.newConnect.step6.charge", { defaultValue: "Charge" }),
                cell: (line) => <CellStatic name="charge">{line.chargeCode}</CellStatic>,
              },
              {
                key: "basis",
                label: props.t("customers.newConnect.step6.basis", { defaultValue: "Basis" }),
                cell: (line) => <CellStatic name="basis">{line.basis}</CellStatic>,
              },
              {
                key: "qty",
                label: props.t("customers.newConnect.step6.qty", { defaultValue: "Qty" }),
                numeric: true,
                cell: (line) => (
                  <CellStatic name="qty">
                    <span className="tabular-nums">{quantities[line.basis]}</span>
                  </CellStatic>
                ),
              },
              // ⚠ **`EACH` AND `AMOUNT` — `DEF-CUS-7911`, FOUND IN A
              // PHOTOGRAPH.** `step5-review.png` draws five columns and this
              // table had three, so the review summarised the charges without
              // ever saying what one costs. **The docstring above this group
              // already promised these two came from `quote-preview`** — a
              // comment claiming a guarantee is not the guarantee (law 1),
              // and the photograph is what noticed, not any test.
              {
                key: "each",
                label: props.t("customers.newConnect.step6.unitPrice", {
                  defaultValue: "Each",
                }),
                numeric: true,
                cell: (line) => (
                  <QuoteMoney
                    what="unit-price"
                    amount={quoteFigureOf(
                      reviewPriced.get(`${line.chargeCode}|${line.basis}`)?.unit_price,
                    )}
                    currency={reviewQuote?.currency ?? null}
                  />
                ),
              },
              {
                key: "amount",
                label: props.t("customers.newConnect.step6.amount", {
                  defaultValue: "Amount",
                }),
                numeric: true,
                cell: (line) => (
                  <QuoteMoney
                    what="amount"
                    amount={quoteFigureOf(
                      reviewPriced.get(`${line.chargeCode}|${line.basis}`)?.amount,
                    )}
                    currency={reviewQuote?.currency ?? null}
                  />
                ),
              },
            ]}
          />
          <PlainTable data-group-fields="charges">
            <tbody>
              <FieldRow
                label={props.t("customers.newConnect.step6.dueDays", {
                  defaultValue: "Payment terms",
                })}
              >
                {props.draft.quoteDueDays.trim() === "" ? (
                  <EmptyValue tracks="step-4" />
                ) : (
                  <span className="tabular-nums">
                    {paymentTermOptions(props.draft.quoteDueDays, props.t).find(
                      (option) => option.value === props.draft.quoteDueDays.trim(),
                    )?.label ?? props.draft.quoteDueDays}
                  </span>
                )}
              </FieldRow>
              <FieldRow
                label={props.t("customers.newConnect.charges.autopay", {
                  defaultValue: "Autopay",
                })}
              >
                {props.draft.billing.autopay
                  ? props.t("customers.account.yes")
                  : props.t("customers.account.no")}
              </FieldRow>
              <FieldRow
                label={props.t("customers.newConnect.charges.taxExempt", {
                  defaultValue: "Tax exempt",
                })}
              >
                {props.draft.billing.taxExempt
                  ? props.t("customers.account.yes")
                  : props.t("customers.account.no")}
              </FieldRow>
            </tbody>
          </PlainTable>
        </ReviewGroup>
      </Panel>

      {/* ══════════════════════════════════════════════════════════════════
          MESSAGES — the whole Communication step, folded in (task 13)
          ══════════════════════════════════════════════════════════════════
          ⚠ **THE FIELD-BY-FIELD AUDIT IS §0 OF
          `NewConnectCommunicationStep.tsx`** and it is a deliverable: with the
          `communication` step id gone there is no other screen left that holds
          any of this, so a field missed there is a field the product no longer
          has. PO: *"we dont want any information to be reduced or lost"*. */}
      <Panel as="section">
        <h4 className="font-heading text-md m-0 mb-1">
          {props.t("customers.newConnect.step7.who", { defaultValue: "Who we are telling" })}
        </h4>
        <WhoWeAreTelling draft={props.draft} t={props.t} />
      </Panel>
      <MessagesFold
        draft={props.draft}
        onPatch={props.onPatch}
        t={props.t}
        client={props.client}
      />

      {/* ══════════════════════════════════════════════════════════════════
          WHAT PRESSING CREATE MAKES — and it is TRUE, not aspirational
          ══════════════════════════════════════════════════════════════════
          ⚠ **EVERY ROW WAS CHECKED AGAINST `commit_connection` LINE BY LINE;
          §2 records the five that do not say what the drawing says.** A row
          promising something the commit does not do is worse than no table,
          and `DEF-MET-5428` is what one costs: the review step promised nine
          work orders and the server raised none, for eleven days, with both
          sides green because both were tested on the payload.

          ⚠ **THE DRAWING'S RED NOTE IS DELETED RATHER THAN REWORDED.** It
          said the two shaded rows *"do not happen today"*. They happen: the
          invoice is raised and ISSUED inside the commit's transaction and the
          payment is recorded against it in the same act. A stated absence that
          outlives its cause is a lie the product tells about itself (hard-won
          law 1). */}
      <Panel as="section">
        <h4 className="font-heading text-md m-0 mb-1">
          {props.t("customers.newConnect.review.whatCreateMakes", {
            defaultValue: "What pressing Create makes",
          })}
        </h4>
        <PlainTable data-create-makes="">
          <thead>
            <tr>
              <th scope="col">
                {props.t("customers.newConnect.step8.colWhat", { defaultValue: "What" })}
              </th>
              <th scope="col">
                {props.t("customers.newConnect.review.howMany", { defaultValue: "How many" })}
              </th>
              <th scope="col">
                {props.t("customers.newConnect.step8.colWhere", {
                  defaultValue: "Where it shows",
                })}
              </th>
              <th scope="col">
                {props.t("customers.newConnect.step8.colWhen", { defaultValue: "When" })}
              </th>
              <th scope="col">
                {props.t("customers.newConnect.review.colStatus", { defaultValue: "Status" })}
              </th>
            </tr>
          </thead>
          <tbody>
            {WHAT_CREATE_MAKES.map((row) => (
              <tr key={row.key} data-creates={row.key}>
                <td>
                  {/* ⊕ `CR-164-BRC10` wave 4 — which it will be, by owner type. */}
                  {row.key === "ownerAccount" && ownersOwnAccount
                    ? // `DEF-CUS-10047` follow-up (walk, 2026-10-11) — the line names
                      // the SAME kind step 4's *Who is billed* names (Regular or
                      // Master), then whether the owner lives there.
                      `${props.t(`customers.account.pill.kind.${ownerAccountKind(props.draft)}`)} · ${
                        ownerLivesThere(props.draft.owner.kind)
                          ? props.t("customers.newConnect.creates.livesThere")
                          : props.t("customers.newConnect.creates.billingOnly")
                      }`
                    : props.t(`customers.newConnect.creates.${row.key}.what`, {
                        defaultValue: row.whatEn,
                      })}
                </td>
                <td className="tabular-nums" data-creates-count={row.key}>
                  <CreateCount
                    countKey={row.countKey}
                    counts={counts}
                    isMoney={row.countKey !== null && moneyKeys.has(row.countKey)}
                    quoteTotal={props.quoteTotal}
                    paidNow={props.draft.paymentAmount.trim()}
                    currency={props.quoteCurrency}
                  />
                </td>
                <td>
                  {props.t(`customers.newConnect.creates.${row.key}.where`, {
                    defaultValue: row.whereEn,
                  })}
                </td>
                <td>
                  {props.t(`customers.newConnect.creates.${row.key}.when`, {
                    defaultValue: row.whenEn,
                  })}
                </td>
                <td data-creates-status={row.key}>
                  {row.statusEn === "" ? (
                    <EmptyValue tracks={row.key} />
                  ) : (
                    props.t(`customers.newConnect.creates.${row.key}.status`, {
                      defaultValue: row.statusEn,
                    })
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </PlainTable>
      </Panel>

      <Panel as="section">
        <h4 className="font-heading text-md m-0 mb-1">
          {props.t("customers.newConnect.step9.outstanding", { defaultValue: "Outstanding work" })}
        </h4>
        {/* BR-MET-114 (PO 2026-08-25): *"human will mark everything to start
            with"*. The list is STORED and human-authored, so a wizard that has
            written nothing has none — and it never blocks creating the
            connection. Items are added on the connection's own screen. */}
        <Note className="max-w-measure">
          {props.t("customers.newConnect.review.outstandingHelp", {
            defaultValue: "Noted by hand once the build exists.",
          })}
        </Note>
      </Panel>
    </>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE SMALL PARTS OF THE TWO NEW TABLES
// ══════════════════════════════════════════════════════════════════════════

/** A count, or the dash while the asset-type list is still loading. */
function GlanceCount(props: { value: number | null | undefined }) {
  return props.value === null || props.value === undefined ? (
    <EmptyValue tracks="asset_types" />
  ) : (
    <span className="tabular-nums">{props.value}</span>
  );
}

function GlanceCell(props: { what: string; mark: string; children: ReactNode }) {
  return (
    <div
      className="border-r border-b border-divider p-3 last:border-r-0"
      data-glance-cell={props.mark}
    >
      <div className="text-sm text-neutral-700">{props.what}</div>
      <div className="font-medium" data-glance-value={props.mark}>
        {props.children}
      </div>
    </div>
  );
}

/**
 * One `How many` cell.
 *
 * ⚠ **A COUNT, A SERVER MONEY FIGURE, OR THE EM DASH — AND NEVER A ZERO FOR
 * UNKNOWN.** `commit_connection` takes exactly this posture for `premises`
 * and `sub_meter_links`: a zero reads as *we made none* where the truth is
 * *this cannot be counted here*.
 *
 * ⚠ **THE TWO MONEY ROWS GO THROUGH `MoneyCell` AND NOTHING ELSE.** The
 * invoice's figure is the engine's own string for these lines and the
 * payment's is the clerk's own string, unparsed; neither is added, subtracted
 * or rounded in this browser (hard rule 2, `DEF-088`, `DEF-127`).
 */
function CreateCount(props: {
  countKey: string | null;
  counts: Record<string, number | null>;
  isMoney: boolean;
  quoteTotal: string | null;
  paidNow: string;
  currency: string | null;
}) {
  if (props.countKey === null) {
    return <EmptyValue tracks={props.countKey ?? undefined} />;
  }
  if (props.isMoney) {
    const amount = props.countKey === "paidNow" ? props.paidNow : (props.quoteTotal ?? "");
    if (amount === "" || props.currency === null) {
      return <EmptyValue tracks="step-4" />;
    }
    return <MoneyCell amount={amount} currency={props.currency} basis="priced" />;
  }
  const value = props.counts[props.countKey];
  return value === null || value === undefined ? (
    <EmptyValue tracks={props.countKey} />
  ) : (
    <span className="tabular-nums">{value}</span>
  );
}

/**
 * The charges group's one-line summary — the drawing's own dot-separated
 * shape: `$1,035.00 · owner's account · $500.00 check · 30-day terms`.
 *
 * ⚠ **BOTH FIGURES ARE PRINTED, NEITHER IS COMBINED.** There is no
 * subtraction, no sum and no rounding on this line; `MoneyCell` is the one
 * display boundary (`BR-SHL-023`) and it rounds once, exactly as the server's
 * finalization does.
 */
function ChargesSummary(props: {
  draft: NewConnectDraft;
  t: Translator;
  total: string | null;
  currency: string | null;
}) {
  const paid = props.draft.paymentAmount.trim();
  return (
    <span data-charges-summary="">
      {"· "}
      {props.total === null || props.currency === null ? (
        props.t("customers.newConnect.step6.notPriced", { defaultValue: "Not priced" })
      ) : (
        <MoneyCell amount={props.total} currency={props.currency} basis="priced" />
      )}
      {/* ⊕ **`CR-164-BRC10` item 26 (PO ruling Q8, *"the charges line
          once"*).** The payment printed a second *Priced, not posted* marker
          beside the first, so one charge read as two priced lines. The paid
          figure is the clerk's own, and says so in one word. */}
      {paid !== "" && props.currency !== null && (
        <>
          {" · "}
          <MoneyCell amount={paid} currency={props.currency} />{" "}
          {props.t("customers.newConnect.review.paidNow", { defaultValue: "paid" })}
        </>
      )}
    </span>
  );
}
