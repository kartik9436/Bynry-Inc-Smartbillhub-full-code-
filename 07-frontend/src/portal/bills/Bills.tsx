// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-032 (EP-CWP-07) — bills. Screen: CWP-027 (blueprint `P11`)
// Rules:    BR-CWP-043 (owing and amount are TWO columns; part-paid is a THIRD
//           state) · BR-CWP-042 (the corrected pair are both present, the
//           original greyed and naming its replacement) · BR-CWP-041 (nothing
//           above the issued bill) · B14 rule 20 (ONE table type) · rule 21 ·
//           rule 31 (no database id on screen) · rule 32 · rule 33 (a refusal
//           is five or six words) · rule 35 · rule 36 (compose the kit) ·
//           CLAUDE.md hard rule 2 (2 dp displayed)
// Tests:    src/portal/bills/Bills.dom.test.tsx
// Design:   CR-085 (c) — redrawn against the signed-off wireframe for s30:
//           the month as the row's heading, the lead sentence, `Pay` only
//           where something is owed, and a phone card list in place of a
//           nine-column table nobody can read at 390.
// Design:   CR-085 step 2 — the blueprint's FOUR columns (PO 2026-09-11: the
//           8 September PDF is the design, the 3 September wireframe images
//           are superseded), R-22's three sentences through `PortalState`,
//           R-10's way out on the failed read, and the printed-bill door on
//           the phone card (DEF-CWP-4864).
// Defects:  DEF-CWP-4864 — at 390 the table is `display:none`, so the row's
//           `↓ PDF` icon went with it and the printed bill had NO door on a
//           phone. The card list carries both doors now.
// Impacts:  src/portal/api/portalClient.ts `getBills`
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { PageHeader } from "@/components/PageHeader";

import {
  Card,
  ErrandLink,
  rowActionName,
  StatusChip,
  WhereNext,
  monthYearText,
  usePortalPath,
} from "../components/primitives";
import { usePortalDate } from "../components/regional";
import { PortalListTable } from "../components/listTable";
import type { PageSize } from "@/components/tableTypes";
import { PortalScreen, PortalState } from "../components/states";
import { formatMoney } from "../signin/Enrol";
import { getBills, type PortalBill, type PortalBills } from "../api/portalClient";
import { monthWords, splitNeedle, usePortalListWindow } from "../components/listWindow";
import { EyeIcon, PrinterIcon } from "@/components/icons";

/** `state` → the chip's tone. ⚠ **`part_paid` HAS ITS OWN TONE** because it is
 *  its own state: painting it like *due* would ask for the whole amount again
 *  and painting it like *paid* would ask nobody for the rest. */
const TONE: Record<string, "success" | "warning" | "danger" | "neutral" | "info"> = {
  paid: "success",
  due: "warning",
  part_paid: "info",
  overdue: "danger",
  corrected: "neutral",
};

/**
 * `CWP-027` — every bill: which one, what it covers, what it charged, and
 * where it stands.
 *
 * ⚠ **FOUR COLUMNS, RULED BY THE PO ON 2026-09-11.** Three drawings cover this
 * screen — the 8 September blueprint (four columns), the module pack's
 * 3 September PNG (eight) and the build (nine). The ruling is that the
 * blueprint is the design and the September images are superseded, so the
 * table is `BILL · COVERS · AMOUNT · STATUS` and the row's two icons.
 *
 * ⚠ **NEITHER FIGURE ON THIS SCREEN IS COMPUTED HERE.** `total` and `owing`
 * are the server's, resolved from the ledger; a screen that subtracted would
 * be a second implementation of the one number a customer argues about.
 * `BR-CWP-043` asks for owing in a column of its OWN and the ruling above
 * leaves no room for one — the collision, and what is kept of the rule, is
 * written out beside the column list below rather than summarised here.
 *
 * ⚠ **A CORRECTED BILL STAYS IN THE LIST, GREYED, NAMING ITS REPLACEMENT**
 * (`BR-CWP-042`). Dropping it would leave somebody holding a bank statement
 * they cannot reconcile against anything.
 *
 * ⚠ **THE BILL NUMBER IS A LINK, AND WITHOUT IT `CWP-028` DOES NOT EXIST**
 * (`DEF-CWP-3954`). It was bold text: a customer could see every bill they had
 * ever been sent and could not open one of them. Five screens hang off that one
 * anchor — the bill itself, the document as it was printed, *why is this bill
 * different*, *dispute a bill* and *ask about this bill* — and all five were
 * shipped, routed and tested at their own addresses with nothing pointing at
 * any of them. **The visible value is the NUMBER**, which is what is printed on
 * the paper the customer is holding, never a row id (B14 rule 31).
 *
 * ⚠ **THE PAY CONTROL WAS HELD AND THE SCREEN IT WAS WAITING FOR HAD LANDED.**
 * It was a `HeldButton` reading *Online payment arrives later this year*, and
 * the reason was written when there was nowhere to send anybody. `CWP-038`
 * *Pay now* is live — it reads what is owed, lets a customer choose an amount
 * and a method, and shows which bills the money settles — so the door opens it.
 * **The rails are still absent and the refusal has not gone anywhere**: it is
 * served per account on `CWP-038` itself, in the words the server chooses
 * (*"We cannot take card payments yet."*), which is where a refusal about
 * a payment provider belongs and where it stops being true on its own. A hold
 * whose screen has landed is `DEF-CWP-3925` — hard-won law 2's mirror — and
 * `Bills.dom.test.tsx` now asserts the door by address so it cannot close
 * again quietly.
 */
export function BillsView(props: { accountId?: string | null } = {}) {
  const { t, i18n } = useTranslation();
  // `DEF-CWP-3994` — the tenant's own date format, published at the frame.
  const asDate = usePortalDate();
  const path = usePortalPath();
  /**
   * ⚠ **ONE PAGE, AND THE SEARCH, THE CHIPS AND THE SORT TRAVEL WITH IT**
   * (`DEF-CWP-5747`, `NFR-3`). This screen asked for every bill the login had
   * ever had and let the browser do all four. Moving only the page would have
   * been worse than leaving it: a customer typing a bill number that is on
   * page 7 would be told they have no such bill.
   *
   * ⚠ **THE MONTH NAME IS RESOLVED HERE BECAUSE ONLY THIS SIDE KNOWS THE
   * LANGUAGE.** `BILL` renders *August 2026* over the number, and a customer
   * hunting for *my August bill* types `aug`. The server stores `2026-08-31`
   * and may not write *August* in any of the eleven languages (B14 rule 35),
   * so the screen turns the word it drew back into the code the server knows:
   * `aug` → `f.month=08`, `2026` → `f.year=2026`. Anything it cannot name —
   * `BL-2608` — travels as `q`.
   */
  const list = usePortalListWindow({
    resolve: (needle) =>
      splitNeedle(needle, [{ name: "month", words: monthWords(i18n.language) }], "year"),
  });
  const [answer, setAnswer] = useState<PortalBills | null>(null);
  const rows = answer?.bills ?? null;
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  // ⚠ **R-10's WAY OUT HAS TO ACTUALLY DO SOMETHING** (PO 2026-09-11: *"the
  // thing they can do about it must be on that same screen, next to the
  // message"*). The drawing's FAILED state is *"We could not load your bills."
  // Retry, plus the phone number* — so `Try again` is a real control and not a
  // label: bumping this counter re-runs the effect below, which is the same
  // read that failed. A `Try again` wired to nothing is `EmptyList`'s own
  // `onCta: () => undefined` defect (`DEF-MET-4764`) — pressable, and inert.
  const [attempt, setAttempt] = useState(0);
  const accountId = props.accountId ?? null;

  const { request } = list;
  useEffect(() => {
    let live = true;
    // Both flags reset, or a retry after a failure would draw the failed card
    // over a successful read.
    setFailed(false);
    // ⚠ **THE ROWS STAY ON SCREEN WHILE THE NEXT PAGE IS IN FLIGHT.** Clearing
    // them here would blank the card to a loading state on every page turn and
    // every settled keystroke, which loses the reader's place and reads as the
    // screen breaking. Only the FIRST load has nothing to show.
    setBusy(true);
    // ⚠ **THE ACCOUNT IS IN THE REQUEST AND IS ALSO THE EFFECT'S DEPENDENCY**
    // (`BR-CWP-010`, `US-CWP-023` TC-2). Both halves are needed: sending it
    // scopes the answer, and listing it below is what makes the list RELOAD
    // when the customer changes the switcher. A dependency array that omitted
    // it would leave the header naming one account over another account's
    // bills — which is the exact confusion this story exists to remove.
    getBills({ accountId, ...request })
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
  }, [accountId, request, attempt]);

  // ⚠ **ALL THREE ARE THE SERVER'S FACTS NOW, AND EACH WAS COUNTED OFF THE
  // ARRAY THIS SCREEN USED TO HOLD (`DEF-CWP-5747`).** Over a PAGE, `anyOwing`
  // would hide the *Pay* control from a customer whose only unpaid bill is on
  // page 2; `oldest` would say *since Aug 2026* on page 1 of eleven years; and
  // `populated` would answer *you have no bills* to a search that matched
  // none. `count` cannot stand in for the third: it is the MATCHING set.
  const anyOwing = answer?.any_owing === true;
  const oldest = answer?.oldest_on ?? null;
  const populated = answer?.populated === true;

  // ⚠ **THE HEAD IS BUILT ONCE AND RENDERS ON EVERY BRANCH, INCLUDING WHILE
  // THE LIST IS STILL LOADING** (`DEF-CWP-4000`, audit D1 / delta X4-X5). A
  // head that lived only in the happy-path return would leave the page with no
  // `<h1>` for as long as the request takes — nothing for a screen reader to
  // land on, and a visible jump when the title arrives.
  //
  // ⚠ **AND `Pay` IS UP HERE NOW RATHER THAN UNDER THE TABLE.** The drawing
  // puts this screen's actions in the head; the build had drifted it to the
  // foot of the page, which is what the audit measured as *"where a control
  // survived at all it has drifted to the bottom"*. It is `ErrandLink`, an
  // OUTLINE button — not the brand primary `13-wireframe-delta.md` 34.2
  // describes, because the PNG draws an outline and the PNG wins.
  //
  // ⚠ **IT CARRIES NO AMOUNT, AND THAT IS A GAP STATED RATHER THAN INVENTED.**
  // The drawing writes *Pay $142.18*. `GET /portal/bills` serves each bill's
  // own `owing` and NO total, so an amount here would either be a sum computed
  // in the browser — money arithmetic on the client, which hard rule 2 keeps
  // out of the display layer — or a number for one bill labelled as if it were
  // all of them. Owed: a served `total_owing` on the bills envelope.
  const head = (
    <PageHeader
      kicker={t("portal.kicker.bills")}
      title={t("portal.bills.title")}
      // ⚠ **THE DRAWING'S OWN SENTENCE — *"Every bill since you started, Jun
      // 2026 · 3 bills"*.** It answers *is this all of them* before a customer
      // has to count the rows, which is the question a bill list that starts
      // mid-history provokes. It is drawn only when there ARE bills: over an
      // empty list it would say *since you started, · 0 bills*, and the empty
      // sentence below already says what will fill it (B14 rule 17).
      rollup={
        oldest === null ? undefined : (
          <span data-bills-since={oldest}>
            {t("portal.bills.since", {
              month: monthYearText(oldest, i18n.language),
              // ⚠ **THE SERVER'S `count`, NOT `rows.length`** — the drawing's
              // sentence is *"Every bill since you started, Jun 2026 · 3
              // bills"*, and a page would make it *· 50 bills* on page 1 of
              // eleven years (`DEF-NOT-5746`'s footer, one line up the page).
              count: answer?.count ?? 0,
            })}
          </span>
        )
      }
      secondaryActions={
        // ⚠ **ONLY WHEN SOMETHING IS ACTUALLY OWED, AND THAT IS THE DRAWING'S
        // RULE RATHER THAN A TIDY-UP** — *"Pay on the unpaid bill only. Paid
        // rows carry no filled button — nothing to do means nothing to
        // press."* This read `rows.length > 0`, so a customer whose every bill
        // was settled still met a Pay control on the screen that exists to
        // tell them they owe nothing. `Bills.dom.test.tsx` already pins the
        // empty-list case; this is the same rule one step further in.
        //
        // ⚠ **`Number(...) > 0` IS A COMPARISON AND NOT ARITHMETIC** (hard rule
        // 2 keeps money off floats in a browser): it is the same test the
        // *Unpaid* filter chip below already makes, deliberately the same, so
        // the button and the filter cannot disagree about what unpaid means.
        anyOwing ? (
          <span data-bills-pay="">
            <ErrandLink label={t("portal.bills.pay")} to="/pay-now" />
          </span>
        ) : undefined
      }
    />
  );

  // ⚠ **THREE STATES, THREE SENTENCES, ONE CARD — R-22 AS THE PO RULED IT**
  // (2026-09-11, verbatim: *"differntiate it using text message"*). They were
  // three hand-rolled `Card`s each holding one grey `<p>`, which is the shape
  // the blueprint objects to: *loading*, *empty* and *failed* rendered the same
  // picture and the reader had to read the sentence to tell which had happened.
  // `PortalState` keeps the one picture and puts the KIND in the DOM
  // (`data-portal-state`), which is the only way anything but a person can ever
  // check that the empty address and the failed address differ.
  if (failed) {
    return (
      <PortalScreen screen="CWP-027" head={head}>
        <PortalState
          kind="failed"
          testId="bills"
          sentence={t("portal.bills.couldNotRead")}
          // ⚠ **R-10, AND THE DRAWING ASKS FOR BOTH OF THESE BY NAME** —
          // *"Retry, plus the phone number."* We do not hold a phone number on
          // this payload, so the second way out is the screen that DOES carry
          // the office and emergency numbers (`CWP-052`, *Still stuck? Call us
          // or come in*). A door to the numbers is the honest version of
          // printing a number this screen cannot derive.
          waysOut={[
            { label: t("portal.state.tryAgain"), onClick: () => setAttempt((n) => n + 1), tone: "primary", testKey: "retry" },
            { label: t("portal.state.getHelp"), to: path("/help"), testKey: "help" },
          ]}
        />
      </PortalScreen>
    );
  }
  if (answer === null || rows === null) {
    return (
      <PortalScreen screen="CWP-027" head={head}>
        <PortalState kind="loading" testId="bills" sentence={t("portal.bills.reading")} />
      </PortalScreen>
    );
  }

  // Narrowed ONCE into a const so the closures below keep the narrowing:
  // TypeScript drops a narrowing of a mutable binding inside a callback.
  const served = answer;

  return (
    <PortalScreen screen="CWP-027" head={head}>
      <Card testId="bills">
        {!populated ? (
          // B14 rule 17 — a sentence that says what will fill it, never a table
          // of dashes. ⚠ **AND IT IS THE `empty` KIND, NOT A BARE `<p>`**: the
          // three states have to be distinguishable to something other than a
          // reader, and `data-portal-state="empty"` beside the failed card's
          // `"failed"` is what makes R-22 checkable at all.
          <PortalState kind="empty" sentence={t("portal.bills.none")}>
            <span data-bills-empty="" />
          </PortalState>
        ) : (
          <>
            {/* ⚠ **THE PHONE GETS A LIST OF CARDS AND THE DESK GETS THE TABLE,
                AND THAT IS NOT A STYLE PREFERENCE — IT IS THE ONE THING THIS
                SCREEN COULD NOT DO ON A PHONE.** Measured at 390: the table's
                own content is 805px wide inside a 316px column, so `Amount`,
                `Owing` and `Status` all sit off the right-hand edge behind a
                sideways scroll a customer has no reason to look for. A bill
                list that cannot say what a bill COST is the whole screen
                failing on the device most customers open it on, and
                `overflow-x-auto` (which `MiniTable` already has, correctly)
                stops the PAGE moving without making the figures readable.
                The drawing answers it the same way: its phone frame is a
                stack of cards — month, period, amount, status — and its
                desktop frame is the table.

                ⚠ **ONE SOURCE FOR BOTH.** Both halves render `rows`, so
                nothing can drift; what the phone drops is the toolbar and the
                three columns the drawing itself leaves out of its phone
                frame. */}
            <div className="mt-3 flex flex-col gap-3 md:hidden" data-bills-cards="">
              {rows.map((bill) => (
                <BillCard key={bill.number ?? String(bill.issued_on)} bill={bill} />
              ))}
            </div>
            <div className="mt-3 max-md:hidden">
              <PortalListTable<PortalBill>
                screen="CWP-027"
                caption={t("portal.bills.caption")}
                rows={rows}
                rowKey={(bill) => bill.number ?? String(bill.issued_on)}
                // ⚠ The GREY is `BR-CWP-042`'s — a corrected bill is history,
                // still readable, no longer owed.
                rowMuted={(bill) => bill.state === "corrected"}
                empty={
                  <p className="mt-2 text-body text-neutral-600" data-bills-empty="">
                    {t("portal.bills.none")}
                  </p>
                }
                /* ⚠ **THE SEARCH AND THE TWO CHIPS ARE THE SERVER'S NOW
                   (`DEF-CWP-5747`) AND MATCH WHAT THEY ALWAYS MATCHED.** The
                   browser predicate was the bill NUMBER and the four dates,
                   plus the MONTH the column prints in the reader's own
                   language; `apps/portal/selectors.BILL_SEARCH_FIELDS` is the
                   first half on the server and `resolve` above is the second,
                   because only this side knows what language *August* is in.
                   *Unpaid* is still OWING and not the state word, so a
                   part-paid bill counts (`BR-CWP-043`) — the predicate moved,
                   it did not change. There is no `match` to pass here: the
                   predicate is the server's, and one this component were free
                   to ignore is the dead prop hard-won law 2 is about. */
                server={list.window({
                  total: served.count,
                  page: served.page,
                  per: served.per as PageSize,
                  populated,
                  busy,
                  search: { placeholder: t("portal.bills.search") },
                  chips: {
                    name: "state",
                    label: t("portal.bills.filterLabel"),
                    options: [
                      { key: "unpaid", label: t("portal.bills.filterUnpaid") },
                      { key: "this_year", label: t("portal.bills.filterThisYear") },
                    ],
                  },
                })}
                icons={[
                  {
                    key: "view",
                    icon: <EyeIcon />,
                    label: (bill) => t("portal.bills.viewRow", { number: bill.number ?? "" }),
                    to: (bill) => path(`/bills/${encodeURIComponent(bill.number ?? "")}`),
                    // A bill with no number has nowhere to go — `/bills/` opens
                    // nothing — so the control stays visible and says why
                    // (`BR-SHL-025`), rather than vanishing from the row.
                    reason: (bill) => (bill.number === null ? t("portal.bills.noNumber") : null),
                  },
                  {
                    key: "print",
                    icon: <PrinterIcon />,
                    label: (bill) => t("portal.bills.printRow", { number: bill.number ?? "" }),
                    to: (bill) =>
                      path(`/bills/${encodeURIComponent(bill.number ?? "")}/document`),
                    reason: (bill) => (bill.number === null ? t("portal.bills.noNumber") : null),
                  },
                ]}
                columns={[
                // ⚠ **FOUR COLUMNS — `BILL · COVERS · AMOUNT · STATUS` — AND
                // THAT IS A PO RULING OF 2026-09-11, NOT A TIDY-UP.** Three
                // drawings cover this screen and they disagreed about the
                // column set: the 8 September blueprint draws FOUR, the module
                // pack's 3 September PNG draws EIGHT, and the build had NINE.
                // The PO ruled the blueprint is the design and the September
                // wireframe images are superseded, so every one of this
                // screen's drawing-versus-drawing disagreements now decides the
                // same way. `ISSUED`, `DUE`, `USAGE` and `OWING` leave the
                // table; the four facts the drawing keeps are which bill, what
                // it covers, what it charged and where it stands.
                //
                // ⚠ **`BR-CWP-043` IS SIGNED LAW AND IT COLLIDES WITH THIS,
                // AND THE COLLISION IS RECORDED RATHER THAN RESOLVED HERE.**
                // That rule reads *"Owing is a separate column from amount. A
                // $142.18 bill with $40.00 paid against it is neither a paid
                // bill nor an unpaid one"* — and its own citation is
                // **blueprint `P13`**, the SAME document whose section 05 draws
                // four columns on page 56. The winning drawing contradicts
                // itself, which is not something a lane may settle: a ruling
                // that collides with a signed rule needs the supersession
                // stated (CLAUDE.md law 13). **What is built keeps the rule's
                // SUBSTANCE inside the drawn four** — the amount cell carries
                // what is still owed whenever that differs from what was
                // charged, and `part_paid` keeps its own chip and its own tone
                // — so no customer loses a figure. What is NOT kept is the
                // rule's letter, the separate column. Reported in
                // `conformance/CR-085-lane5-04-step2-after.md`.
                {
                  key: "bill",
                  label: t("portal.bills.colBill"),
                  sortable: true,
                  sortValue: (bill) => bill.number,
                  cell: (bill) => <BillCell bill={bill} />,
                },
                // ⚠ **`COVERS`, NOT `PERIOD`** — the blueprint's own word. The
                // column is the same two dates it always was; what changed is
                // the heading, and the heading is what a customer reads when
                // they are hunting for *my August bill*.
                {
                  key: "covers",
                  label: t("portal.bills.colCovers"),
                  sortable: true,
                  // The START sorts the column: two bills in one month sort
                  // by when the period opened, which is the order they were
                  // billed in. Sorting the rendered range would sort text.
                  sortValue: (bill) => bill.period_start,
                  cell: (bill) =>
                    bill.period_start && bill.period_end
                      ? t("portal.bills.period", {
                          from: asDate(bill.period_start),
                          to: asDate(bill.period_end),
                        })
                      : "—",
                },
                {
                  key: "amount",
                  label: t("portal.bills.colAmount"),
                  align: "right",
                  sortable: true,
                  // A NUMBER, so 9.00 sorts below 10.00. Sorting the rendered
                  // string would put "$9.00" after "$10.00" and look broken
                  // on exactly the screen a customer checks arithmetic on.
                  sortValue: (bill) => Number(bill.total),
                  cell: (bill) => <AmountCell bill={bill} />,
                },
                {
                  key: "status",
                  label: t("portal.bills.colStatus"),
                  cell: (bill) => (
                    <StatusChip
                      tone={TONE[bill.state] ?? "neutral"}
                      testKey={`state-${bill.number}`}
                    >
                      {stateWord(t, bill)}
                    </StatusChip>
                  ),
                },
                ]}
              />
            </div>
          </>
        )}
        {/* ⚠ **THESE THREE SCREENS HAD NO DOOR ANYWHERE IN THE PRODUCT**
            (`DEF-CWP-3954`). Bills is where they belong: `08-screen-layouts.md`
            files *Documents and letters* in the same section as the bills it
            lists, and the arrears ladder is what a bill turns into when it is
            not paid. They are rendered whether or not there are bills — a
            customer with nothing owing still opens *Where things stand*, and
            `CWP-057` answers *"Nothing is overdue on this account."* */}
        <WhereNext
          mark="bills"
          doors={[
            { key: "documents", label: t("portal.documents.title"), to: "/documents" },
            { key: "overdue", label: t("portal.overdue.whereThingsStand"), to: "/overdue" },
            { key: "help-paying", label: t("portal.overdue.helpPaying"), to: "/help-paying" },
          ]}
        />
      </Card>
    </PortalScreen>
  );
}

/**
 * The chip's word — and for a bill that is not settled yet, **the count**.
 *
 * ⚠ **`Due` IS NOT WHAT `CWP-027` DRAWS** (`DEF-CWP-3980`). The drawing counts
 * down — *DUE IN 12 DAYS* — and the difference is the whole value of the
 * column: *Due* is true of a bill payable tomorrow and of one payable in five
 * weeks, so it tells a customer scanning a list nothing about which one to deal
 * with. The same applies in the other direction, where *Overdue by 3 days* and
 * *Overdue by 90 days* are very different conversations.
 *
 * ⚠ **THE COUNT IS THE SERVER'S AND IS NEVER SUBTRACTED HERE.** `due_in_days`
 * is computed against the same `today` that produced `state`, so the two cannot
 * contradict each other. A browser doing its own date arithmetic would print
 * *Due in 1 day* inside a chip the server had already coloured `overdue`, for
 * every customer a time zone east of the utility.
 *
 * ⚠ **TODAY IS `Due today`, NOT `Due in 0 days`.** Zero is a real answer here
 * and the arithmetic phrasing is the one place a countdown reads as a machine.
 *
 * Any other state — `paid`, `part_paid`, `corrected` — keeps its plain word: a
 * paid bill has no countdown left to run.
 */
function stateWord(
  t: (key: string, options?: Record<string, unknown>) => string,
  bill: PortalBill,
): string {
  const days = bill.due_in_days;
  if (days !== null && days !== undefined) {
    if (bill.state === "due") {
      return days === 0
        ? t("portal.bills.state.dueToday")
        : t("portal.bills.state.dueInDays", { count: days });
    }
    if (bill.state === "overdue") {
      return t("portal.bills.state.overdueByDays", { count: Math.abs(days) });
    }
  }
  return t(`portal.bills.state.${bill.state}`);
}

/**
 * ONE BILL ON A PHONE — the drawing's phone frame, card for card.
 *
 * ⚠ **THE MONTH IS THE HEADING AND THE PERIOD IS UNDER IT**, which is the
 * drawing's own reasoning written out: *"customers say 'my August bill' and
 * mean the one that arrived in August. Both are shown so neither reading is
 * wrong."* The month comes off `issued_on` — the month the bill ARRIVED — and
 * the period says which days it charges for.
 *
 * ⚠ **THE NUMBER IS STILL DRAWN AND IS STILL THE LINK'S DESTINATION** (B14
 * rule 31): it is what is printed on the paper and what a customer reads out
 * on the telephone, so it stays visible under the month rather than being
 * replaced by it.
 *
 * ⚠ **`Pay` ONLY WHERE SOMETHING IS OWED** — *"Paid rows carry no filled
 * button — nothing to do means nothing to press."*
 *
 * ⚠ **NEITHER FIGURE IS COMPUTED HERE.** `total` and `owing` are the server's,
 * `BR-CWP-043`'s two columns, and this card shows the same two the table does.
 */
function BillCard(props: { bill: PortalBill }) {
  const { t, i18n } = useTranslation();
  const asDate = usePortalDate();
  const path = usePortalPath();
  const { bill } = props;
  const number = bill.number ?? "";
  const month = monthYearText(bill.issued_on, i18n.language);
  return (
    <div className="border border-neutral-200 p-3" data-bill-card={number}>
      {number === "" ? (
        <span className="text-h3 font-bold text-neutral-900">{month}</span>
      ) : (
        <Link
          to={path(`/bills/${encodeURIComponent(number)}`)}
          className="text-h3 font-bold text-neutral-900 no-underline hover:underline"
          data-bill-card-link={number}
        >
          {month}
        </Link>
      )}
      <p className="text-base text-neutral-600">{number}</p>
      {bill.period_start && bill.period_end ? (
        <p className="text-body text-neutral-700">
          {t("portal.bills.period", {
            from: asDate(bill.period_start),
            to: asDate(bill.period_end),
          })}
        </p>
      ) : null}
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
        <span className="text-h3 font-bold tabular-nums" data-card-amount={number}>
          {formatMoney(bill.total, bill.currency)}
        </span>
        <StatusChip tone={TONE[bill.state] ?? "neutral"} testKey={`card-state-${number}`}>
          {stateWord(t, bill)}
        </StatusChip>
      </div>
      {/* ⚠ **WHAT IS STILL OWED, WHERE IT DIFFERS FROM WHAT WAS CHARGED** —
          the same half of `BR-CWP-043` the desktop `AmountCell` keeps, drawn
          the same way and from the same two server strings, so the phone and
          the desk cannot disagree about a part-paid bill. */}
      {formatMoney(bill.owing, bill.currency) !== formatMoney(bill.total, bill.currency) &&
      Number(bill.owing) > 0 ? (
        <p className="text-base font-bold tabular-nums" data-card-owing={number}>
          {t("portal.bills.stillOwing", { amount: formatMoney(bill.owing, bill.currency) })}
        </p>
      ) : null}
      {/* ⚠ **THE TWO ROW DOORS, WHICH THE PHONE DID NOT HAVE AT ALL —
          `DEF-CWP-4864`.** At 390 the table is `display:none`, and the row's
          `View` and `↓ PDF` icons are INSIDE the table, so the printed bill —
          the screen that exists precisely so a customer can send the real
          document to a landlord or an accountant — had **no door anywhere on a
          phone**. The month heading has always linked to the bill; what was
          missing was the printed one, and the drawing's own desktop row draws
          both (` View · ↓ PDF`). They are WORDS here rather than the table's
          icons, because the blueprint's standard A says every icon in the
          portal carries its word and *a phone has no hover* — which is the one
          width where an `aria-label` reaches nobody at all. */}
      {number === "" ? null : (
        <p className="mt-2 flex flex-wrap gap-4" data-card-doors={number}>
          <Link
            to={path(`/bills/${encodeURIComponent(number)}`)}
            className="text-body text-neutral-700 no-underline hover:underline"
            data-card-view={number}
            // DEF-CWP-10566: one card per bill, so each link is named for its bill.
            aria-label={rowActionName(t("portal.bills.seeWholeBill"), number, t)}
          >
            {/* ⚠ **ONE SENTENCE FOR ONE DESTINATION, AND LANE 8 USES THE SAME
                ONE.** `CPB-08` joins a usage month to the bill line that
                produced it, so the Usage screen carries a door to this same
                address; two phrasings of *open the bill* is the thing a
                customer rings about. `portal.bills.seeWholeBill` is the shared
                words and this is its first call site. */}
            {t("portal.bills.seeWholeBill")}
          </Link>
          <Link
            to={path(`/bills/${encodeURIComponent(number)}/document`)}
            className="text-body text-neutral-700 no-underline hover:underline"
            data-card-print={number}
            aria-label={rowActionName(t("portal.billDetail.openDocument"), number, t)}
          >
            {t("portal.billDetail.openDocument")}
          </Link>
        </p>
      )}
      {Number(bill.owing) > 0 ? (
        <div className="mt-3" data-card-pay={number}>
          <ErrandLink label={t("portal.bills.pay")} to="/pay-now" />
        </div>
      ) : null}
    </div>
  );
}

/**
 * **WHAT IT CHARGED — and, where they differ, WHAT IS STILL OWED.**
 *
 * ⚠ **THIS IS WHAT SURVIVES OF `BR-CWP-043` INSIDE THE DRAWN FOUR COLUMNS.**
 * The rule reads *"Owing is a separate column from amount. A $142.18 bill with
 * $40.00 paid against it is neither a paid bill nor an unpaid one"*, and its
 * own citation is blueprint `P13` — the same PDF whose section 05 draws four
 * columns with no `OWING` among them. A lane may not settle a signed rule
 * against a ruling; what it can do is refuse to lose the FIGURE. So the second
 * line is drawn **only when what is owed differs from what was charged**, which
 * is exactly the part-paid case the rule is written about, and it is never
 * drawn on a bill that is wholly paid or wholly due — on those two the amount
 * and the chip already say everything, and a repeated figure is noise.
 *
 * ⚠ **NOTHING IS SUBTRACTED HERE.** Both strings are the server's own. The
 * comparison is `!==` on the rendered pair, not arithmetic on money (hard rule
 * 2 keeps money off floats in a browser).
 */
function AmountCell(props: { bill: PortalBill }) {
  const { t } = useTranslation();
  const { bill } = props;
  const number = bill.number ?? "";
  const charged = formatMoney(bill.total, bill.currency);
  const owing = formatMoney(bill.owing, bill.currency);
  return (
    <span className="flex flex-col items-end">
      <span className="tabular-nums" data-amount={number}>
        {charged}
      </span>
      {owing !== charged && Number(bill.owing) > 0 ? (
        <span className="text-base font-bold tabular-nums" data-owing={number}>
          {t("portal.bills.stillOwing", { amount: owing })}
        </span>
      ) : null}
    </span>
  );
}

/** The bill's number, and under it the sentence that ties a corrected pair
 *  together in whichever direction the reader arrived from. */
function BillCell(props: { bill: PortalBill }) {
  const { t, i18n } = useTranslation();
  const path = usePortalPath();
  const { bill } = props;
  const number = bill.number ?? "";
  return (
    <span className="flex flex-col">
      {/* ⚠ **THE MONTH, ABOVE THE NUMBER, AND BOTH ARE DRAWN** — the drawing's
          own instruction: *"The month is the heading and the period is
          underneath, because customers say 'my August bill' and mean the one
          that arrived in August. Both are shown so neither reading is
          wrong."* The column held the number alone, so a customer hunting for
          *my August bill* had to translate `BL-2608-000052` into a month in
          their head, or read the period column and translate the other way.
          It is `issued_on` — the month the bill ARRIVED — while the period
          column beside it says which days were charged; the two are a month
          apart on almost every bill, which is exactly why neither alone is
          enough. */}
      <span className="font-semibold" data-bill-month={number}>
        {monthYearText(bill.issued_on, i18n.language)}
      </span>
      {/* ⚠ The NUMBER is the link text and the path segment both (B14 rule 31,
          PO 2026-08-30: *"no Databse ID on screen - that is a rule"*), which is
          the same reading `screenIds.ts` records for `/bills/:number`. A bill
          with no number is still drawn — as the bold text it always was —
          because a link to `/bills/` opens nothing. */}
      {number === "" ? (
        <span className="text-base text-neutral-600">{bill.number}</span>
      ) : (
        <Link
          to={path(`/bills/${encodeURIComponent(number)}`)}
          className="text-base text-neutral-600 no-underline hover:underline"
          data-bill-link={number}
        >
          {number}
        </Link>
      )}
      {bill.replaced_by ? (
        <span className="text-base text-neutral-600" data-replaced-by={bill.replaced_by}>
          {t("portal.bills.replacedBy", { number: bill.replaced_by })}
        </span>
      ) : null}
      {bill.replaces ? (
        <span className="text-base text-neutral-600" data-replaces={bill.replaces}>
          {t("portal.bills.replaces", { number: bill.replaces })}
        </span>
      ) : null}
    </span>
  );
}
