// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-048 (EP-CWP-09) — payments and receipts, and a bounce is two
//           rows. Screen: CWP-041 (blueprint `P27`)
// Rules:    BR-CWP-061 (a bounce is TWO rows, the reversal directly above,
//           worded *returned by the bank*) · BR-CWP-050 (an adjustment shows
//           its date and a plain reason) · BR-CWP-051 (a write-off shows its
//           amount and date and NEVER its reason code) · BR-CWP-056 (a control
//           that may not be used is DISABLED WITH ITS REASON) · B14 rule 20
//           (ONE table type) · rule 21 · rule 31 (no database id on screen) ·
//           rule 32 (one sentence per section) · rule 33 (a refusal is five or
//           six words) · rule 35 · rule 36 (compose the kit) · CLAUDE.md hard
//           rule 2 (2 dp displayed) · hard rule 4
// Open:     OQ-1340 — whether the audit row holding a CORRECTED cheque number
//           survives pruning. Until it is answered this screen is NOT described
//           as a record of the old value. (`CLAUDE.md` hard rule 4 and
//           `US-CWP-048` §8 both cited it as `OQ-1330` until 2026-09-14, when
//           `DEF-GOV-5229` corrected both; `OQ-1330` is a real and different
//           question about a meter reading's unit.)
// Tests:    src/portal/payments/Payments.dom.test.tsx
// Impacts:  src/portal/api/portalClient.ts `getMoneyList`
// ───────────────────────────────────────────────────────
import { useEffect, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { PageHeader } from "@/components/PageHeader";

import {
  Card,
  CardGrid3,
  ErrandCard,
  ErrandLink,
  HeldButton,
  SegmentedChoice,
  StatusChip,
  TextInput,
  usePortalPath,
} from "../components/primitives";
import { usePortalDate } from "../components/regional";
import { PortalListTable } from "../components/listTable";
import { usePortalListWindow } from "../components/listWindow";
import { ListPager } from "@/components/ListPager";
import type { PageSize } from "@/components/tableTypes";
import { DownloadIcon, EyeIcon } from "@/components/icons";
import { formatMoney } from "../signin/Enrol";
import { ButtonAnchor } from "@/components/Button";
import { useParams } from "react-router-dom";
import { PortalScreen, PortalState } from "../components/states";
import {
  documentFileHref,
  getMoneyList,
  type PortalMoney,
  type PortalMoneyRow,
} from "../api/portalClient";

/**
 * The seven money errands this screen hands off to — **the errand-card grid the
 * home page already uses** (`DEF-CWP-3975`, delta 41.9).
 *
 * ⚠ **EACH ONE GAINS A DESCRIPTION, WHICH IS THE WHOLE DIFFERENCE.** A row of
 * seven boxes reading *Your payment plan · A plan we have offered you · Credits
 * on the account* asks a customer to tell three near-identical phrases apart
 * from four words each. The card's grey line says what the errand IS, once, in
 * one sentence — B14 rule 32's budget, and rule 31 keeps every id off it.
 *
 * ⚠ **THE TITLES ARE THE DESTINATION SCREENS' OWN, DELIBERATELY.** Naming a
 * door after the screen it opens means a customer reads the same words on the
 * card and on the page they land on, and it minted no new title in eleven
 * languages.
 */
const ERRANDS: readonly { key: string; title: string; description: string; to: string }[] = [
  { key: "pay-now", title: "portal.card.pay_bill.title", description: "portal.money.errand.payNow", to: "/pay-now" },
  { key: "methods", title: "portal.methods.title", description: "portal.money.errand.methods", to: "/payment-methods" },
  { key: "autopay", title: "portal.autopay.title", description: "portal.money.errand.autopay", to: "/autopay" },
  { key: "plan", title: "portal.yourPlan.title", description: "portal.money.errand.plan", to: "/plan" },
  { key: "plan-offer", title: "portal.planOffer.title", description: "portal.money.errand.planOffer", to: "/plan-offer" },
  { key: "money-back", title: "portal.moneyBack.creditsHeading", description: "portal.money.errand.moneyBack", to: "/money-back" },
  // ⚠ **BUDGET BILLING'S ONLY DOOR WAS *HELP PAYING*** until 2026-09-08
  // (`DEF-CWP-4653`, `CR-085`). It is a mainstream product for anybody with a
  // summer-and-winter bill, and routing it exclusively through a screen about
  // not being able to pay made it both hard to find and, for some people, off-
  // putting. It belongs with the other six money errands. The Help paying link
  // STAYS — it is genuinely useful there; this is a door added, not moved.
  { key: "level-pay", title: "portal.levelPay.title", description: "portal.money.errand.levelPay", to: "/level-pay" },
  { key: "fees", title: "portal.fees.title", description: "portal.money.errand.fees", to: "/fees" },
];

/** `state` → the chip's tone.
 *
 * ⚠ **`bounced` IS THE ONLY DANGER TONE ON THIS SCREEN AND IT IS EARNED.** r10
 * rule 6 reserves danger for a destructive commit — money the bank took back is
 * the one row here a customer must not skim past. `reversed` is NEUTRAL: the
 * payment was real, and it is history rather than a warning.
 *
 * ⚠ **A CANCEL IS NEUTRAL TOO, AND IS NOT A BOUNCE** (`DEF-CWP-10341`). Both
 * rows of a cancel read *Canceled*; no bank took anything back.
 */
const TONE: Record<PortalMoneyRow["state"], "success" | "warning" | "danger" | "neutral" | "info"> = {
  received: "success",
  processing: "warning",
  failed: "danger",
  cancelled: "neutral",
  unknown: "neutral",
  bounced: "danger",
  reversed: "neutral",
  credited: "info",
  written_off: "neutral",
  write_off_reversed: "neutral",
};

/** The state a chip draws — **an unrecognised one reads `unknown`**, never its
 *  raw key and never a borrowed word (`DEF-CWP-10341`). */
export function moneyState(state: string): PortalMoneyRow["state"] {
  return Object.hasOwn(TONE, state) ? (state as PortalMoneyRow["state"]) : "unknown";
}

/** History rather than money the customer has been given credit for. */
function isMuted(row: PortalMoneyRow): boolean {
  const shown = moneyState(row.state);
  return shown === "reversed" || shown === "cancelled";
}

/**
 * `CWP-041` — everything that moved money, and a bounce as **two rows**.
 *
 * ⚠ **THE TWO ROWS ARE THE WHOLE SCREEN** (`BR-CWP-061`). Nothing in this
 * product edits a payment (hard rule 4), so a reversal is a NEW negative row
 * against the original and the customer sees both: `−$129.02` reading *returned
 * by the bank* directly above the `$129.02` it undoes. **The word REVERSED on
 * the second row is the server's reading of "something points at me"** — the
 * database row still says cleared — and a screen that showed one row with a
 * changed status would be describing a database this product does not have.
 *
 * ⚠ **THE SIGN IS RENDERED AS IT ARRIVES.** No absolute value is taken
 * anywhere: `formatMoney("-129.0200")` is `-$129.02`, and that minus is the
 * point of the row.
 *
 * ⚠ **A WRITE-OFF'S REASON IS NOT ON THIS SCREEN BECAUSE IT IS NOT IN THE
 * BODY** (`BR-CWP-051`). A goodwill credit's reason IS, because `BR-CWP-050`
 * asks for it. Two different rules about two different rows.
 *
 * ⚠ **RECEIPT AND CSV ARE ONE HELD CONTROL EACH, BELOW THE TABLE, RATHER THAN
 * A PAIR ON EVERY ROW.** The story draws receipts as row actions; `HeldButton`
 * renders its reason as visible text, and thirty-one rows each repeating six
 * words is exactly the description budget B14 rule 32 was ratified to stop
 * (*"too much content — desctiption is too much for clark to read"*). One
 * control, one reason, and the row actions return with the rails that make
 * them live.
 */
export function PaymentsView(props: { accountId?: string | null } = {}) {
  const { t } = useTranslation();
  // `DEF-CWP-3994` — the tenant's own date format, published at the frame.
  const asDate = usePortalDate();
  // The tenant comes from the address bar and from nowhere else (`BR-TEN-003`),
  // the same source every other portal screen that leaves the SPA reads.
  const tenant = useParams().tenant ?? "";
  const path = usePortalPath();
  /**
   * ⚠ **ONE PAGE, AND THE SEARCH AND THE SORT TRAVEL WITH IT**
   * (`DEF-CWP-5747`, `NFR-3`). This screen asked for every payment the login
   * had ever made and searched, sorted and sliced them in the browser. Moving
   * only the page would have been worse than leaving it: a customer typing a
   * cheque number that is on page 7 would be told we never took that payment,
   * which on this screen of all screens is the sentence that cannot be wrong.
   *
   * ⚠ **THE SEARCH BOX IS STILL THE SCREEN'S AND NOT THE TABLE'S**
   * (`DEF-CWP-4879`): the table is inside `max-md:hidden`, so a box drawn by
   * the table does not exist on a phone at all. It now feeds the SERVER
   * through this window instead of filtering an array — one needle, one
   * filter, both halves, exactly as before.
   */
  const list = usePortalListWindow();
  const [answer, setAnswer] = useState<PortalMoney | null>(null);
  const rows = answer?.money ?? null;
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const [thisYear, setThisYear] = useState(false);
  // ⚠ **THE SEARCH BOX IS THE SCREEN'S NOW AND NOT THE TABLE'S — `DEF-CWP-4879`.**
  // It lived inside `PortalListTable`, which this screen renders inside a
  // `max-md:hidden` wrapper, so at 390 the search box and the `All | This year`
  // filter **did not exist at all**: measured on 2026-09-11, zero visible
  // inputs and zero segment buttons in `main` against one of each at 1280. The
  // phone half is the half a customer actually uses to answer *did my payment
  // go through*, and it was the half that could not look anything up.
  // ⚠ **ONE NEEDLE, ONE FILTER, BOTH HALVES.** Giving the phone its own search
  // box would be two states over one list — the drift `DEF-CWP-3994`'s family
  // is made of. The predicate below is the one the table used, moved rather
  // than copied.
  const needle = list.typed;
  const accountId = props.accountId ?? null;
  // ⚠ **DECLARED ABOVE THE HEAD, WHICH READS IT.** `secondaryActions` holds the
  // CSV control and is absent where there is nothing to export; a read that has
  // not answered yet is the same case (`BR-CWP-093` — nothing empty ever
  // appears). `populated` is the SERVER's *has this customer any payments in
  // this year*, because `count` is what the search matched and would hide the
  // control from somebody who mistyped a reference.
  const populated = answer?.populated === true;

  const { request } = list;
  useEffect(() => {
    let live = true;
    // ⚠ **THE FILTER IS THE SERVER'S** — a client-side filter over a list the
    // server paged would search what arrived and report that as the answer.
    // The account travels the same way and for the same reason
    // (`BR-CWP-010`), and it is in the dependency array so that changing the
    // switcher RELOADS this tab rather than leaving it on the old account.
    setBusy(true);
    getMoneyList({
      year: thisYear ? new Date().getFullYear() : undefined,
      accountId,
      ...request,
    })
      .then((next) => {
        if (live) {
          setAnswer(next);
          setBusy(false);
        }
      })
      .catch(() => {
        if (live) {
          setFailed(true);
          setBusy(false);
        }
      });
    return () => {
      live = false;
    };
  }, [thisYear, accountId, request]);

  // ⚠ **THE HEAD IS BUILT ONCE, ABOVE THE BRANCHES, AND RENDERS ON EVERY ONE
  // OF THEM — `DEF-CWP-4926` (`CR-085` step 2).** It was declared INSIDE the
  // success branch, below `if (failed) return …`, so a failed or a slow read
  // threw away the page title, the `data-screen` mark every rendered check in
  // this repo selects on, and the drawing's whole top row of controls — the
  // one row that could have got the customer anywhere else. Ten signed-in
  // screens shared that single misplaced `return`; `arrears/Overdue.tsx` is
  // the model that already did it this way. R-10 (PO 2026-09-11: *"when a
  // screen tells a customer something bad, the thing they can do about it must
  // be on that same screen"*) cannot be met by a branch that renders no
  // controls at all.
  const head = (
    <PageHeader
      kicker={t("portal.money.kicker")}
      title={t("portal.money.title")}
      // ⚠ **THE ACTION ROW IS THE HALF OF `DEF-CWP-4000` THAT COSTS.** The
      // head landed here first and the drawing's action did not follow it:
      // `08-screen-layouts.md` heads `CWP-041` *· action ↓ CSV*, and this
      // screen drew it in a `mt-3` row UNDER the table, which is D1's
      // *"where a control survived it drifted to the FOOT of the page"*.
      // Moved, not re-drawn — the same `HeldButton`, the same reason.
      // ⚠ It stays absent on the empty state with the rest of the held row:
      // `BR-CWP-093`, nothing empty ever appears, and an export of no
      // payments is exactly that. **A read that has not answered yet, or has
      // failed, is the same case** — there is nothing to export either way,
      // which is why the test is `rows` rather than `rows.length` alone.
      secondaryActions={
        rows === null || !populated ? null : (
          <HeldButton
            label={t("portal.money.exportCsv")}
            reason={t("portal.money.exportHeld")}
          />
        )
      }
    />
  );

  if (failed) {
    return (
      <PortalScreen screen="CWP-041" head={head}>
        <PortalState kind="failed" testId="money" sentence={t("portal.money.couldNotRead")} />
      </PortalScreen>
    );
  }
  if (rows === null || answer === null) {
    return (
      <PortalScreen screen="CWP-041" head={head}>
        <PortalState kind="loading" testId="money" sentence={t("portal.money.reading")} />
      </PortalScreen>
    );
  }

  // ⚠ **ONE PREDICATE, BOTH HALVES, AND IT IS THE SERVER'S NOW**
  // (`DEF-CWP-5747`). It was a `rows.filter` here so the phone cards and the
  // table would give one answer; it is `apps/portal/selectors.
  // MONEY_SEARCH_FIELDS` for the same reason one layer down, and both halves
  // render the page the server matched. What a search looks at did not change:
  // the date, the tender, the reference the customer can read and the receipt
  // number (`applied_to` is the invoice numbers a payment settled and the
  // server matches those on the row it built them from).
  const shown = rows;
  /**
   * A row's place in the LIST THE SERVER JUST ANSWERED — the page's offset plus
   * its place on the page.
   *
   * ⚠ **IT USED TO BE `rows.indexOf(row)` OVER THE WHOLE UNFILTERED ARRAY,
   * AND THAT IS NO LONGER A THING THE BROWSER HAS (`DEF-CWP-5747`).** The comment
   * it replaces said *"the index is the row's place in the whole list, not in
   * the filtered one — an attribute that renumbers under a filter is a test
   * that silently changes what it asserts"*. The reasoning still holds and the
   * reference point moved: with the search on the server there IS no unfiltered
   * array here, so the honest answer is the position within the result set that
   * was asked for. It is stable across a page turn, which is what the hook is
   * for, and it renumbers when a search changes the result set — which is now
   * a fact about the product rather than a fact about this file.
   */
  const placeOf = (row: PortalMoneyRow) =>
    (answer.page - 1) * answer.per + shown.indexOf(row);

  return (
    <div data-screen="CWP-041">
      {/* ⚠ **A PAGE HEAD, NOT A SECTION LABEL** (delta 41.1 · X4). The title
          WAS the kicker: small, uppercase, grey `YOUR PAYMENTS`, so the screen
          had a section label and no heading. `components/PageHeader` is the
          shared one and thirteen portal files already compose it — this lane
          builds no second page head. */}
      {head}
      <Card testId="money">
        {/* ⚠ **THE TOOLBAR IS ABOVE THE WIDTH SPLIT, WHICH IS THE WHOLE FIX
            (`DEF-CWP-4879`).** `PortalListTable` draws its own toolbar and this
            screen renders that table inside `max-md:hidden`, so on a phone the
            search box and the year filter were not hidden — they were never in
            the DOM. The markup below is the kit's own toolbar row, in the kit's
            own classes (`mb-3 flex flex-wrap items-center gap-3`, the search in
            a `w-full max-w-xs` with an `sr-only` label), MOVED out of the table
            rather than re-styled: a second toolbar design is what B14 rule 36
            exists to stop, and a placeholder alone is not a label — it
            disappears the moment somebody types, which is exactly when a
            screen-reader user needs to know what the field is. */}
        {populated ? (
          <div className="mb-3 flex flex-wrap items-center gap-3" data-money-toolbar="">
            <div className="w-full max-w-xs">
              <label className="sr-only" htmlFor="money-search">
                {t("portal.money.search")}
              </label>
              <TextInput
                id="money-search"
                type="search"
                value={needle}
                placeholder={t("portal.money.search")}
                onChange={list.type}
              />
            </div>
            {/* ⚠ **THE YEAR FILTER IS THE SERVER'S AND STAYS THE SCREEN'S.**
                It is a `year` parameter on `GET /portal/payments`, so the rows
                that arrive are already the answer — a `chips` option would
                narrow the narrowed set. */}
            <SegmentedChoice
              testId="CWP-041-year"
              label={t("portal.money.filterLabel")}
              current={thisYear ? "year" : "all"}
              options={[
                { key: "all", label: t("portal.money.filterAll") },
                { key: "year", label: t("portal.money.filterThisYear") },
              ]}
              onChoose={(key) => {
                setThisYear(key === "year");
                // A new year is a new result set, so the page goes with it —
                // asking for page 7 of a list that now has two is blank.
                list.setPage(1);
              }}
            />
          </div>
        ) : null}
        {!populated ? (
          // B14 rule 17 — a sentence naming what will fill it, never a table of
          // dashes.
          <p className="mt-2 text-body text-neutral-600" data-money-empty="">
            {t("portal.money.none")}
          </p>
        ) : answer.count === 0 ? (
          // ⚠ **A SEARCH THAT MATCHED NOTHING IS NOT AN EMPTY LIST, AND THE
          // TWO MUST NOT SHARE A SENTENCE** — R-22 as the PO ruled it
          // (*"differntiate it using text message"*), and the exact fault the
          // ruling cites on two other screens. *You have not made a payment
          // yet* to somebody who has made nine and mistyped a reference is a
          // small lie, and it is the one that makes a person ring. The table
          // owns this sentence for its own search; lifting the search lifted
          // the sentence with it.
          <p className="mt-3 text-body text-neutral-600" data-money-nomatch="">
            {t("portal.table.noMatch")}
          </p>
        ) : (
          <>
            {/* ⚠ **THE PHONE GETS A CARD PER PAYMENT AND THE DESK GETS THE
                TABLE, AND THAT IS NOT A STYLE PREFERENCE — IT IS THE ONE THING
                THIS SCREEN COULD NOT DO ON A PHONE** (`CR-085`). Measured at
                390: the table's own content is 637px wide inside a 316px
                column, so `AMOUNT`, `STATUS` and the row action all sit off the
                right-hand edge behind a sideways scroll a customer has no
                reason to look for. *Did my payment go through* is the whole
                question this screen answers, and on a phone neither half of the
                answer was on screen. `overflow-x-auto` (which `MiniTable`
                correctly has) stops the PAGE moving without making a figure
                readable — `CWP-027` reached the same conclusion the same week.

                ⚠ **ONE SOURCE FOR BOTH.** Both halves render `shown`, so
                nothing can drift; what the phone drops is the two columns the
                drawing itself leaves out of its phone frame. ⚠ **The toolbar
                used to be on that list and it was a defect, not a decision**
                (`DEF-CWP-4879`) — it is above this split now and serves both. */}
            <div className="mt-3 flex flex-col gap-3 md:hidden" data-money-cards="">
              {/* ⚠ **THE INDEX IS THE ROW'S PLACE IN THE WHOLE LIST, NOT IN
                  THE FILTERED ONE.** `data-card-amount='0'` has to mean the
                  same payment whether or not somebody has typed in the search
                  box — an attribute that renumbers under a filter is a test
                  that silently changes what it asserts. It is also what the
                  desk table beside it already does. */}
              {shown.map((row) => (
                <PaymentCard
                  key={`${placeOf(row)}-${row.date ?? ""}-${row.reference ?? ""}`}
                  row={row}
                  index={placeOf(row)}
                />
              ))}
              {/* ⚠ **THE PHONE GETS A FOOTER TOO, AND WITHOUT IT THIS COMMIT
                  WOULD HAVE BUILT A WALL** (`DEF-CWP-5747`). The card stack had
                  no pager because it had every row and a customer scrolled; it
                  holds ONE PAGE now, so a phone with no footer would leave
                  payment 51 unreachable — the payload defect fixed by
                  manufacturing a worse one, on the screen whose whole question
                  is *did my payment go through*. Same shared `ListPager`, same
                  four `table.pager.*` keys as the table's own (B14 rule 16). */}
              <ListPager
                total={answer.count}
                page={answer.page}
                per={answer.per as PageSize}
                onPage={list.setPage}
                onPer={list.setPer}
              />
            </div>
            {/* ⚠ **THE HOOK IS WHAT MAKES `DEF-CWP-4879` TESTABLE AT ALL.**
                jsdom applies no media query, so no unit test can see that this
                half is hidden on a phone — what it CAN see is that the toolbar
                is not INSIDE it, which is the structural fact the defect was.
                The width itself is proved in a browser at 390. */}
            <div className="mt-3 max-md:hidden" data-money-table="">
              <PortalListTable<PortalMoneyRow>
                screen="CWP-041"
                caption={t("portal.money.caption")}
                rows={shown}
                /* ⚠ **THE PAGE, THE SORT AND THE FOOTER ARE THE SERVER'S**
                   (`DEF-CWP-5747`). No `search` rides here: this screen's box
                   is ABOVE the width split because the table lives inside
                   `max-md:hidden` and a box drawn by the table does not exist
                   on a phone (`DEF-CWP-4879`). The year pair stays its own
                   control for the reason beside it — it is a `year` parameter
                   applied BEFORE `BR-CWP-061`'s bounce pairing, not a chip. */
                server={list.window({
                  total: answer.count,
                  page: answer.page,
                  per: answer.per as PageSize,
                  populated,
                  busy,
                })}
                rowKey={(row) =>
                  `${placeOf(row)}-${row.date ?? ""}-${row.reference ?? ""}`
                }
                // A reversed payment is history: still readable, no longer
                // money the customer has been given credit for.
                rowMuted={isMuted}
                empty={
                  <p className="mt-2 text-body text-neutral-600" data-money-empty="">
                    {t("portal.money.none")}
                  </p>
                }
                // ⚠ **THE YEAR FILTER IS THE SERVER'S AND STAYS THE SCREEN'S.**
                // It is a `year` parameter on `GET /portal/payments`, so the
                // rows that arrive are already the answer — passing it as a
                // `chips` option would narrow the narrowed set. It moves from a
                // hand-rolled pair of `Button`s into the shared control, which
                // is B14 rule 36: *"compose the kit … rather than hand-rolling
                // it in the screen"*.
                icons={[
                  {
                    // ⚠ **`CR-085` `CPB-20` — THE RECEIPT, WHERE A PERSON LOOKS
                    // FOR IT.** `CWP-041`'s drawing gives receipts as ROW icons
                    // and the build shipped ONE held button under the table
                    // reading *"Receipts arrive later this year"* — over a
                    // document `notifications` freezes at dispatch and the
                    // store has been keeping all along. A customer wanting the
                    // receipt for one payment could not have said which one.
                    // ⚠ **ADDRESSED BY THE `PMT-` NUMBER AND NOT BY
                    // `reference`**, which prefers the cheque number the
                    // customer wrote — see `payments_seam`'s note. Two facts,
                    // two fields.
                    key: "receipt",
                    icon: <DownloadIcon />,
                    label: () => t("portal.money.receiptRow"),
                    // A reversal, a credit and a write-off mint no payment
                    // number and post no receipt, so the icon is ABSENT there
                    // rather than permanently refused — a control that can
                    // never be used on a row is not a control.
                    absent: (row) => row.receipt_reference === null,
                    href: (row) =>
                      row.receipt_reference === null || !row.receipt_available
                        ? null
                        : documentFileHref(tenant, row.receipt_reference),
                    // ⚠ **THE THIRD STATE, AND A BROWSER IS WHAT FOUND IT.**
                    // A payment CAN have a number and no kept receipt — every
                    // held dispatch on this deployment is one — and the first
                    // draft drew a live download over exactly that, which the
                    // server then refused. The same sentence `CWP-031` uses,
                    // because it is the same fact about the same document.
                    reason: (row) =>
                      row.receipt_available ? null : t("portal.documents.cannotOpen"),
                  },
                  {
                    key: "view",
                    icon: <EyeIcon />,
                    label: () => t("portal.money.viewRow"),
                    // ⚠ **THE DRAWING'S 👁 IS *view the payment* AND THERE IS NO
                    // PAYMENT SCREEN**, so this opens the BILL the money
                    // settled — which is the question a customer actually has
                    // about a row on this list. The visible value in the
                    // address is the bill NUMBER printed on their paper, never
                    // a row id (B14 rule 31).
                    to: (row) => path(`/bills/${encodeURIComponent(row.applied_to[0] ?? "")}`),
                    // A reversal settled nothing and a payment split across two
                    // bills has no single destination. The control stays
                    // visible and says why (`BR-SHL-025`).
                    // ⚠ **THE SENTENCE USED TO BE `portal.money.noReceipt` —
                    // *"No receipt for this row."* — AND IT WAS FALSE
                    // (`DEF-CWP-4705`). That key is RETIRED from all eleven
                    // catalogues**, because re-pointing this call site was what
                    // made it dead, and a key nothing calls is one more line on
                    // `G18`'s "renders to nobody" list. Naming it here is not a
                    // call site: `G18` reads call sites and this is a comment,
                    // which is why the row could be retired at all. This control opens the BILL a payment
                    // settled; a receipt is a different document, and on a
                    // split payment it is very often downloadable from the icon
                    // immediately to the left of this one. The comment three
                    // lines up stated the true reason in prose the whole time
                    // and the key beside it said something else, which is why
                    // reading the diff could not catch it: both halves look
                    // right on their own. Nothing in this repository asks
                    // whether a refusal is TRUE — `G32` asks only that it
                    // RESOLVES, and this one always did.
                    reason: (row) =>
                      row.applied_to.length === 1 ? null : t("portal.money.noSingleBill"),
                  },
                ]}
                columns={[
                  {
                    key: "date",
                    label: t("portal.money.colDate"),
                    sortable: true,
                    sortValue: (row) => row.date,
                    cell: (row) => <Reversal row={row}>{asDate(row.date) || "—"}</Reversal>,
                  },
                  {
                    key: "how",
                    label: t("portal.money.colHow"),
                    cell: (row) => (
                      <Reversal row={row}>
                        <HowCell row={row} />
                      </Reversal>
                    ),
                  },
                  {
                    key: "reference",
                    label: t("portal.money.colReference"),
                    // ⚠ A human reference or a stated absence — never an id,
                    // and never eight characters of one (B14 rule 31). The
                    // SHAPE is the server's (`#10188` on a cheque, the
                    // instrument on a card) so the browser holds no second
                    // definition of *what is my reference* — `DEF-CWP-3974`.
                    cell: (row) => <Reversal row={row}>{row.reference ?? "—"}</Reversal>,
                  },
                  {
                    key: "applied",
                    label: t("portal.money.colAppliedTo"),
                    cell: (row) => <AppliedCell row={row} />,
                  },
                  {
                    key: "amount",
                    label: t("portal.money.colAmount"),
                    align: "right",
                    sortable: true,
                    sortValue: (row) => Number(row.amount),
                    cell: (row) => (
                      <Reversal row={row}>
                        <span className="tabular-nums" data-amount={placeOf(row)}>
                          {/* The sign is the server's. No `Math.abs` anywhere. */}
                          {formatMoney(row.amount, row.currency)}
                        </span>
                      </Reversal>
                    ),
                  },
                  {
                    key: "status",
                    label: t("portal.money.colStatus"),
                    cell: (row) => (
                      <StatusChip
                        tone={TONE[moneyState(row.state)]}
                        testKey={`state-${placeOf(row)}`}
                      >
                        {t(`portal.money.state.${moneyState(row.state)}`)}
                      </StatusChip>
                    ),
                  },
                ]}
              />
            </div>
            {/* ⚠ **THE PER-PAGE RECEIPT BUTTON IS GONE, AND ITS ABSENCE IS THE
                FIX** (`CR-085` `CPB-20`). It stood here reading *"Receipts
                arrive later this year"* — one control, under a table of many
                payments, that could not have said WHICH receipt even if it had
                worked. `CWP-041`'s drawing gives receipts as ROW icons (👁 🖨)
                and that is where the live one is now, on the row and on the
                phone card. The CSV export left this row for the page head with
                `DEF-CWP-4000` and is still held there, honestly: nothing in
                this product writes a customer CSV. */}
          </>
        )}
        {/* ⚠ **SEVEN SCREENS HUNG OFF NOTHING UNTIL THIS ROW EXISTED**
            (`DEF-CWP-3954`). Every one of them is money, and *Payments* is the
            tab a customer presses when money is the question — which is why
            `08-screen-layouts.md` heads all seven with the same kicker,
            **PAYMENTS**. Two of them were a closed loop: `CWP-039` linked to
            `CWP-040` and `CWP-040` linked back, and those were the only two
            references to either address in the whole front end.

            ⚠ **BUT SEVEN BARE BUTTONS ARE NOT A DESIGN** (`DEF-CWP-3975`,
            delta 41.9). A wrapped row of undifferentiated boxes passes every
            check we own — each is wired, each has a label, G13 is satisfied
            because each prop is passed — and nothing asks whether it is a
            navigation design. It is the errand-card grid the home page already
            uses: a title, one grey line saying what the errand IS, and
            `Start →`. Same seven destinations, same addresses, same doors.

            ⚠ **`/ask-for-a-plan` AND `/level-pay` ARE DELIBERATELY NOT HERE.**
            They are reached from `CWP-057` and `CWP-056`, where a customer who
            cannot pay is already standing and where the layout draws them —
            adding them again would be a second door onto one screen from a
            place nobody arrives at with that question. */}
        <CardGrid3>
          {ERRANDS.map((errand) => (
            <ErrandCard
              key={errand.key}
              cardKey={errand.key}
              title={t(errand.title)}
              description={t(errand.description)}
              action={<ErrandLink label={t("portal.money.errandStart")} to={errand.to} />}
            />
          ))}
        </CardGrid3>
      </Card>
    </div>
  );
}

/**
 * **ONE PAYMENT, PHONE-SHAPED** (`CR-085`, wireframe frame *Phone · 390*).
 *
 * The drawing's phone frame is a stack rather than a table: the figure first,
 * then the date and how it was paid, then the status, then which bill it went
 * against. Every one of those four is the same value the desk table's cell
 * renders — `formatMoney` on the server's own signed string, `usePortalDate`'s
 * published format, the same chip and the same `AppliedCell` — so the two
 * halves of this screen cannot say different things.
 *
 * ⚠ **`data-card-amount` AND NOT `data-amount`.** The desk row already carries
 * `data-amount`, and both halves are in the DOM at once (only CSS hides one),
 * so re-using the attribute would make `[data-amount='0']` answer with
 * whichever came first in the markup — a test that silently changed what it
 * was asserting.
 *
 * ⚠ **THE MUTED CLASS IS WRITTEN OUT IN BOTH BRANCHES, NEVER INTERPOLATED.**
 * Tailwind's scanner cannot see a class it did not read literally, and a class
 * the compiler never emitted renders as NOTHING while every assertion about the
 * class list passes (B14 rule 21's per-file clause, `DEF-974`).
 */
function PaymentCard(props: { row: PortalMoneyRow; index: number }) {
  const { t } = useTranslation();
  const asDate = usePortalDate();
  const tenant = useParams().tenant ?? "";
  const { row, index } = props;
  return (
    <div
      className={
        isMuted(row)
          ? "border border-neutral-200 p-3 text-neutral-600"
          : "border border-neutral-200 p-3"
      }
      data-money-card={index}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Reversal row={row}>
          {/* The sign is the server's. No `Math.abs` here either. */}
          <span className="text-h3 font-bold tabular-nums" data-card-amount={index}>
            {formatMoney(row.amount, row.currency)}
          </span>
        </Reversal>
        <StatusChip tone={TONE[moneyState(row.state)]} testKey={`card-state-${index}`}>
          {t(`portal.money.state.${moneyState(row.state)}`)}
        </StatusChip>
      </div>
      <p className="text-body text-neutral-600">
        <Reversal row={row}>
          <span data-card-when={index}>{asDate(row.date) || "\u2014"}</span>
        </Reversal>
        {/* The drawing's own separator. A middle dot is punctuation rather than
            a word, so it mints no key in eleven catalogues — the same reading
            `used_for`'s ` · ` join already takes one screen over. */}
        {" \u00b7 "}
        <Reversal row={row}>
          <HowCell row={row} />
        </Reversal>
      </p>
      {/* *Went against* is the half a landlord and a disputed account need, and
          it is a whole line here rather than a column that fell off the edge. */}
      <div className="text-body text-neutral-700">
        <AppliedCell row={row} />
      </div>
      {row.reference !== null ? (
        <p className="text-base text-neutral-600" data-card-reference={index}>
          {row.reference}
        </p>
      ) : null}
      {/* ⚠ **THE PHONE GETS THE RECEIPT TOO** (`CR-085` `CPB-20`). The card and
          the table render the same rows and the phone half is the one wave F
          had to add because the desk table fell off the edge at 390px; a
          control added to the table alone would be the same defect wearing the
          opposite face. It is a full-width link rather than a 32px glyph
          because a row icon on a card has no row to sit in. */}
      {row.receipt_reference !== null && row.receipt_available ? (
        <p className="mt-2">
          <ButtonAnchor
            variant="ghost"
            href={documentFileHref(tenant, row.receipt_reference)}
            data-card-receipt={index}
          >
            {t("portal.money.receiptRow")}
          </ButtonAnchor>
        </p>
      ) : null}
    </div>
  );
}

/**
 * **The reversal row, in red** (`BR-CWP-061`, delta 41.3, `CWP-041.png`).
 *
 * ⚠ **A BOUNCE IS TWO ROWS AND THE WORDING HAS TO CARRY IT.** Nothing in this
 * product edits a payment (hard rule 4), so a returned cheque is a NEW negative
 * row against the original and the customer sees both: `−$129.02` reading
 * *Returned by the bank* directly above the `$129.02` it undoes. The drawing
 * paints that whole row red — date, how, reference and the words — and greys
 * the row beneath it. Only the chip was red here; the rest of the row read
 * exactly like a payment that went through.
 *
 * ⚠ **PER CELL, AND NOT PER ROW, BECAUSE THE ROW IS NOT THIS LANE'S TO PAINT.**
 * `PortalListTable` takes `rowMuted` and no tone, and the shared table is
 * another lane's file this week — a second author on one file is hard-won law
 * 11's `DEF-165`. Wrapping the four cells this screen owns gets the drawing
 * without reaching into the kit. If a `rowTone` lands later this collapses to
 * one prop, and the test below will still be asserting the right thing: that
 * the reversal's cells are marked, not how.
 *
 * ⚠ **`text-danger-700` AND NOT AN INTERPOLATED CLASS.** Tailwind's scanner
 * cannot see `text-${tone}-700`, and a class the compiler never emitted renders
 * as NOTHING while every `toContain` assertion passes (B14 rule 21's per-file
 * clause, `DEF-974`). `portal/` is a directory entry on `route-b-migrated.txt`,
 * so `routeBUtilities.test.ts` asks the compiler about this one by name.
 */
function Reversal(props: { row: PortalMoneyRow; children: ReactNode }) {
  if (!props.row.returned_by_the_bank) return <>{props.children}</>;
  return (
    <span className="text-danger-700" data-reversal="">
      {props.children}
    </span>
  );
}

/** How the money moved. A credit and a write-off carry no instrument, so they
 *  name what they ARE rather than leaving an empty cell that reads as missing. */
function HowCell(props: { row: PortalMoneyRow }) {
  const { t } = useTranslation();
  const { row } = props;
  if (row.how) return <span>{row.how}</span>;
  if (row.kind === "credit") return <span>{t("portal.money.how.credit")}</span>;
  if (row.kind === "write_off") return <span>{t("portal.money.how.writeOff")}</span>;
  return <span>—</span>;
}

/** What the money met — or, on a reversal, **returned by the bank**.
 *
 * ⚠ **THE WORDING IS THE STORY'S AND IT CARRIES THE WHOLE EXPLANATION**
 * (`US-CWP-048` §1): *"the wording has to carry it — returned by the bank,
 * sitting directly above the payment it undoes."*
 */
function AppliedCell(props: { row: PortalMoneyRow }) {
  const { t } = useTranslation();
  const { row } = props;
  if (row.returned_by_the_bank) {
    return (
      <span className="font-semibold text-danger-700" data-returned="">
        {t("portal.money.returnedByTheBank")}
      </span>
    );
  }
  return (
    <span className="flex flex-col">
      {row.applied_to.length > 0 ? (
        <span data-applied="">{row.applied_to.join(", ")}</span>
      ) : (
        <span>—</span>
      )}
      {/* `BR-CWP-050` — a goodwill credit's reason, in plain words. ⚠ A
          write-off never reaches this branch: its reason is not in the body. */}
      {row.reason ? (
        <span className="text-base text-neutral-600" data-reason="">
          {row.reason}
        </span>
      ) : null}
    </span>
  );
}
