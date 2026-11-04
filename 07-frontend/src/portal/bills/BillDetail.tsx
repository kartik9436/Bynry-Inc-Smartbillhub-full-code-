// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-033 (EP-CWP-07) — one bill, line by line, grouped by
//           service, every unit named. Screen: CWP-028 (blueprint `P14`)
// Rules:    BR-CWP-044 (grouped by service; every usage line carries its unit) ·
//           BR-CWP-071 (the readings behind the bill show HOW they were taken) ·
//           BR-CWP-041 (nothing above the issued bill) · BR-CWP-093 (nothing
//           empty ever appears) · CLAUDE.md hard rule 2 (DISPLAY 2) · hard rule
//           3 (a quantity always carries its unit) · B14 rule 20 (ONE table
//           type) · rule 21 (Tailwind utilities; `portal/` is on
//           route-b-migrated.txt) · rule 31 (no database id on screen) · rule
//           32 (one sentence per section) · rule 35 · rule 36 (compose the kit)
// Tests:    src/portal/bills/BillDetail.dom.test.tsx
// Design:   CR-085 (c) — redrawn against the signed-off wireframe for s31:
//           the month as the title, the issue date in the subtitle, and the
//           `AmountDueCard` the drawing names — what is owed, when, and the
//           button, above the lines on a phone and in the rail on a desk.
// Impacts:  src/portal/api/portalClient.ts `getBillDetail`
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { DayShareNote } from "@/components/DayShareNote";
import { PageHeader } from "@/components/PageHeader";
import { Link, useParams } from "react-router-dom";

import { Panel } from "@/components/Panel";
import { AttachedAnswerCard } from "../components/content";
import {
  Card,
  ErrandLink,
  KVList,
  MiniTable,
  SectionTitle,
  StatusChip,
  TotalRow,
  TwoCol,
  formatQuantity,
  monthYearText,
  usePortalPath,
} from "../components/primitives";
import { formatMoney, formatRate } from "../signin/Enrol";
import { usePortalDate } from "../components/regional";
import { getBillDetail, type PortalBillDetail, type PortalBillGroup } from "../api/portalClient";
import { PortalScreen, PortalState } from "../components/states";

/**
 * `CWP-028` — **what you were charged**, so a customer can add it up themselves
 * and reach the same total.
 *
 * ⚠ **THE ADDITION IS THE SCREEN.** Every figure below is the server's own,
 * rounded once by it, and **nothing here sums anything**. `subtotal_display`,
 * `tax_display` and `total_display` come down already resolved; a browser that
 * added the lines to check them would be a second implementation of signed
 * money law, free to disagree with the ledger — which is the prohibition the
 * staff bill detail states in its own words (PO 2026-08-30).
 *
 * ⚠ **EVERY QUANTITY CELL CARRIES ITS UNIT, AND THE SCREEN CANNOT DROP IT.**
 * `formatQuantity` returns `null` when the unit is absent and the cell draws an
 * em-dash, and the server refuses to serve the pair at all — two guards on hard
 * rule 3, because `4,820` in a column headed *Quantity* is read as whatever
 * unit the reader assumes.
 *
 * ⚠ **UP TO ELEVEN GROUPS CAN APPEAR** (`BR-RAT-024`), which is why the
 * grouping is a map over what the server sent rather than four fixed headings.
 * Fire is among them and it **counts**: one 6" line and two 2" lines arrive as
 * TWO rows and are drawn as two, because that is what the bill charged.
 */
export function BillDetailView(props: { number?: string }) {
  const { t, i18n } = useTranslation();
  const params = useParams();
  const path = usePortalPath();
  // The tenant's own date format, published at the frame (`DEF-CWP-3994`) —
  // the same hook the readings panel below has always used.
  const asDate = usePortalDate();
  const number = props.number ?? params.number ?? "";
  const [bill, setBill] = useState<PortalBillDetail | null>(null);
  const [failed, setFailed] = useState(false);
  // ⚠ **R-10's `Try again` HAS TO BE A CONTROL AND NOT A LABEL.** Bumping this
  // re-runs the effect below — the same read that failed. A way out wired to
  // nothing is `DEF-MET-4764`: pressable, and inert.
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    setBill(null);
    setFailed(false);
    getBillDetail(number)
      .then((answer) => {
        if (live) setBill(answer);
      })
      .catch(() => {
        if (live) setFailed(true);
      });
    return () => {
      live = false;
    };
  }, [number, attempt]);

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
  // ⚠ **AND ITS TWO BILL-DEPENDENT PARTS FALL BACK RATHER THAN THROW.** The
  // title is the bill's own month, then its number, then the screen's plain
  // name — the third rung already existed for *a bill with no number yet* and
  // is now also what a failed read draws. `Why is this bill different?` needs
  // a number to point at, so on a branch with no bill it is ABSENT rather than
  // a link to `/bills//comparison`.
  const head = (
    <PageHeader
      kicker={t("portal.kicker.bills")}
      title={
        (bill === null ? "" : monthYearText(bill.issued_on, i18n.language, "long")) ||
        bill?.number ||
        t("portal.bills.title")
      }
      backTo={{ to: path("/bills"), label: t("portal.billDetail.backToBills") }}
      secondaryActions={
        bill === null ? null : (
          <span className="flex items-center gap-3">
            {/* ⚠ **`CR-182-BRC10` (PO A2, 2026-10-14) — *"option 1 - just say -
                high usage"*.** Two words beside the link that explains them,
                only on a bill that priced a reading BR-MET-020/120 flagged high
                (the server's `high_usage`, read off the bill's own frozen read
                ids). Nothing longer: why is the comparison's job. */}
            {bill.high_usage ? (
              <StatusChip tone="warning" testKey="bill-high-usage">
                {t("portal.billDetail.highUsage")}
              </StatusChip>
            ) : null}
            <Link
              to={path(`/bills/${encodeURIComponent(bill.number ?? "")}/comparison`)}
              className="text-body text-neutral-700 no-underline hover:underline"
              data-link="comparison"
            >
              {t("portal.billDetail.whyDifferent")}
            </Link>
          </span>
        )
      }
    />
  );

  if (failed) {
    return (
      <PortalScreen screen="CWP-028" head={head}>
        <PortalState
          kind="failed"
          testId="bill-detail"
          sentence={t("portal.billDetail.couldNotRead")}
          // ⚠ **R-10 — *"the thing they can do about it must be on that same
          // screen, next to the message"* (PO 2026-09-11).** The head above
          // carries a back link, and the head is not *next to the message*:
          // this card is where the bad news is, so the ways out are in it.
          // `Try again` re-runs the read that failed; the list is the door a
          // customer who cannot open THIS bill actually wants, because the
          // number in the address may simply be wrong.
          waysOut={[
            {
              label: t("portal.state.tryAgain"),
              onClick: () => setAttempt((n) => n + 1),
              tone: "primary",
              testKey: "retry",
            },
            {
              // `Your bills`, not the back link's bare `Bills` — a button in a
              // row of buttons has to say where it goes on its own.
              label: t("portal.bills.title"),
              to: path("/bills"),
              testKey: "bills",
            },
          ]}
        />
      </PortalScreen>
    );
  }
  if (!bill) {
    return (
      <PortalScreen screen="CWP-028" head={head}>
        <PortalState kind="loading" testId="bill-detail" sentence={t("portal.billDetail.reading")} />
      </PortalScreen>
    );
  }

  return (
    <div data-screen="CWP-028">
      {/* ⚠ **B14 rule 31 — THE TITLE IS THE BILL NUMBER**, which is what is
          printed on the paper the customer is holding, and what
          `08-screen-layouts.md` puts here. The drawing also puts the
          *1–31 August · issued 30 August · due 14 September* line under the
          title as a grey subtitle; it already opens the charges card as
          `[data-bill-number]`, and printing it twice is B14 rule 32's
          description budget — so the head carries the title and the sentence
          stays where it is. REPORTED as a placement question rather than
          settled here.
          ⚠ **`Why is this bill different?` MOVES INTO THE ACTION ROW** — it
          was a bare link floating opposite the back link, which is where a
          page's actions belong and is what delta X5 complains about. Its
          `data-link="comparison"` handle travels with it, because two suites
          select on it.
          ⚠ **`↓ PDF`, `Query this bill` AND `Pay` ARE NOT DRAWN HERE.** The
          drawing gives this head all three. The printed bill has its own
          screen (`CWP-029`) reached from the body, disputing has its own
          (`CWP-055`), and `Pay` has no per-bill amount served — inventing
          three head buttons that duplicate or guess is not what D1 asked for.
          REPORTED. */}
      {/* ⚠ **THE MONTH IS THE TITLE AND THE NUMBER IS THE SUBTITLE, WHICH IS
          A SWAP RATHER THAN A REPLACEMENT.** The drawing heads this page
          *August 2026* and puts *Bill BL-2608-000042 · covers Jul 1 – Jul 31
          · issued Aug 5* under it — because a person arrives here having
          clicked *my August bill*, and `BL-2608-000052` in 40px type answers
          a question nobody asked. **The number has not gone anywhere** (B14
          rule 31): it is the first thing in the charges card's own subtitle,
          it is the address, and it is what a customer reads out on the
          telephone. A bill with no number yet keeps the plain heading. The
          head itself is built above the branches — see `DEF-CWP-4926`. */}
      {head}
      {/* ⚠ **ON A PHONE THIS CARD COMES FIRST, AND ON A DESK IT IS IN THE
          RAIL — THE SAME CARD, DRAWN WHERE THE DRAWING PUTS IT.** `TwoCol`
          stacks the rail UNDER the main column at narrow widths, so a card
          that lived only in the rail sat below four charge tables: at 390 the
          customer had to scroll the whole bill to reach *what do I owe*, which
          is the first question they opened it with. The drawing's phone frame
          puts *Amount due · $191.00 · Due Aug 22 · Pay* directly under the
          title, above the lines, and its desktop frame puts it in the rail. */}
      <div className="md:hidden">
        <AmountDueCard bill={bill} where="phone" />
      </div>
      <TwoCol
        main={
          <>
            <Card testId="bill-charges">
              <SectionTitle>{t("portal.billDetail.charged")}</SectionTitle>
              {/* ⚠ **THE THREE DATES GO THROUGH `asDate`, AND THEY DID NOT
                  UNTIL 2026-09-06** (`DEF-CWP-4150`, delta `X1`). This sentence
                  interpolated `period_start`, `period_end` and `due_on` raw, so
                  the one line under the bill's own number read
                  *"BL-2608-000096 · 2026-07-01 to 2026-07-31 · due
                  2026-08-22"* — three ISO strings, on a customer's screen, on
                  the screen a person opens to check a charge.
                  **The tell is that it was inconsistent WITHIN THIS FILE:**
                  `usePortalDate` is imported at the top and the readings panel
                  below has always used it, so the same bill drew `07/31/2026`
                  in its readings and `2026-07-31` in its subtitle. Nothing
                  could see it — both are strings, both are truthy, and no test
                  asserts a date's SHAPE. */}
              <p className="text-body text-neutral-700" data-bill-number={bill.number ?? ""}>
                {/* ⚠ **`issued`, NOT `due` — THE DUE DATE MOVED UP INTO THE
                    AMOUNT CARD AND IS NOT PRINTED TWICE** (B14 rule 32's
                    description budget). The drawing's own subtitle is *covers
                    Jul 1 – Jul 31, 2026 · issued Aug 5*, and the issue date was
                    the one date on the payload this screen never drew — which
                    is the fact that answers *when did this arrive* and settles
                    which month's bill a customer is holding. */}
                {t("portal.billDetail.subtitle", {
                  number: bill.number,
                  from: asDate(bill.period_start),
                  to: asDate(bill.period_end),
                  issued: asDate(bill.issued_on),
                })}
              </p>
              {bill.groups.length === 0 ? (
                // B14 rule 17 — a sentence, never a table of dashes.
                <p className="text-body text-neutral-600" data-charges-empty="">
                  {t("portal.billDetail.noLines")}
                </p>
              ) : (
                // ⚠ **A SERVICE THAT CHARGED NOTHING IS NOT DRAWN**
                // (`DEF-CWP-3967` fault 5). `FIRE 0 connection $0.00` and
                // `TRASH 0 cart $0.00` each occupied a full block of a bill,
                // and `08-screen-layouts.md` draws only what was charged.
                // `BR-CWP-093` — nothing empty ever appears — is the same
                // rule one level up.
                //
                // ⚠ **NOTHING IS HIDDEN THAT COST MONEY, INCLUDING A CREDIT.**
                // The test is on the AMOUNTS, so a group is dropped only when
                // its subtotal is zero AND every line in it is zero; a −$5.00
                // discount line, a $0.00 line beside a charged one, and a
                // group whose lines cancel to a zero subtotal all still draw.
                // And it changes what is RENDERED and never a stored row —
                // hard rule 4 makes an issued bill append-only, and the
                // figures still foot to the server's own total because a
                // block of zeros contributes nothing to add.
                bill.groups
                  .filter(charged)
                  .map((group) => <ServiceGroup key={group.service} group={group} currency={bill.currency} />)
              )}
              <div className="mt-2 flex flex-col gap-2">
                <KVList
                  rows={[
                    {
                      key: "subtotal",
                      label: t("portal.billDetail.beforeTax"),
                      value: (
                        <span data-figure="subtotal">
                          {formatMoney(bill.subtotal_display, bill.currency)}
                        </span>
                      ),
                    },
                    {
                      key: "tax",
                      label: t("portal.billDetail.tax"),
                      value: (
                        <span data-figure="tax">{formatMoney(bill.tax_display, bill.currency)}</span>
                      ),
                    },
                  ]}
                />
                <TotalRow
                  testKey="bill-total"
                  label={t("portal.billDetail.totalFor")}
                  value={formatMoney(bill.total_display, bill.currency)}
                />
              </div>
            </Card>
            <div className="mt-4">
              <Card testId="bill-document">
                <SectionTitle>{t("portal.billDetail.asPrinted")}</SectionTitle>
                {/* B14 rule 32 — ONE sentence, and the route to the document
                    rather than a second copy of the bill on this page. */}
                <p className="text-body text-neutral-700">{t("portal.billDetail.asPrintedWhy")}</p>
                <Link
                  to={path(`/bills/${encodeURIComponent(bill.number ?? "")}/document`)}
                  className="text-body text-neutral-900 no-underline hover:underline"
                  data-link="document"
                >
                  {t("portal.billDetail.openDocument")}
                </Link>
              </Card>
            </div>
            {/* ⚠ **`CWP-061` — THE ANSWER, WHERE THE QUESTION GETS ASKED
                (`DEF-CWP-3985`).** A clerk could tick *also show on the bill*
                against a help answer and **no customer could ever see it**:
                the column, the read and this card were all built and nothing
                joined them up. It sits UNDER the charges, because it explains
                something a person has just read and been puzzled by.

                ⚠ **`null` DRAWS NOTHING AT ALL** — not a frame, not a
                placeholder (`BR-CWP-093`), the same posture `TipBar` takes. */}
            {bill.attached_answer ? (
              <AttachedAnswerCard
                question={bill.attached_answer.question}
                body={bill.attached_answer.body}
                readMoreLabel={t("portal.billDetail.readMoreAnswer")}
                href={path(`/help/${encodeURIComponent(bill.attached_answer.slug)}`)}
                whyLabel={t("portal.billDetail.whyThisAnswer")}
              />
            ) : null}
          </>
        }
        rail={
          <>
            <div className="max-md:hidden">
              <AmountDueCard bill={bill} where="desk" />
            </div>
            <Panel as="aside" title={t("portal.billDetail.yourAccount")}>
              <KVList rows={accountRows(t, bill)} />
              <TotalRow
                testKey="bill-owing"
                label={t("portal.billDetail.owing")}
                value={formatMoney(bill.account.owing, bill.currency)}
              />
            </Panel>
            <ReadingsPanel bill={bill} />
            <SomethingNotRight number={bill.number ?? ""} />
          </>
        }
      />
    </div>
  );
}

/**
 * **WHAT IS DUE, AND WHEN** — the drawing's `AmountDueCard`, and the one thing
 * this screen did not say.
 *
 * ⚠ **THE PAGE ANSWERED *what am I paying for* AND NOT *what do I pay*.** The
 * rail carried a four-row account panel — brought forward, this bill, paid
 * since, owing — which is a reconciliation, and the bottom line of it was a
 * plain grey row. A customer opening one bill wants the figure and the date in
 * that order and nothing between them, and the drawing gives them a card of
 * their own at the top of the rail with the button under them.
 *
 * ⚠ **BOTH FIGURES ARE THE SERVER'S AND NEITHER IS DERIVED HERE.** `owing` is
 * `BR-CWP-043`'s own column, computed from the ledger; `due_on` is the date the
 * bill carries. Nothing subtracts, nothing sums, and the account panel below
 * still shows the same `owing` because it is the same served figure rather than
 * a second calculation of it (hard rule 2, and law 5's one-source rule).
 *
 * ⚠ **A SETTLED BILL LOSES THE BUTTON ENTIRELY AND SAYS SO** — the drawing's
 * *Paid* state, *"the button disappears entirely"*. A disabled *Pay* over a
 * bill with nothing owing is a control that cannot do anything.
 *
 * ⚠ **NO COUNTDOWN, AND THAT IS A GAP STATED RATHER THAN INVENTED.** The
 * drawing writes *Due Aug 22, 2026 · in 9 days*. `GET /portal/bills` serves
 * `due_in_days` on every row of the LIST — computed against the same `today`
 * that produced `state`, so the two can never contradict each other — and
 * `GET /portal/bills/{number}` serves no such field. Counting the days in the
 * browser is the thing `Bills.tsx` already refuses by name: it would print
 * *Due in 1 day* under a bill the server had already called overdue, for every
 * customer a time zone east of the utility. REPORTED, not guessed.
 */
function AmountDueCard(props: { bill: PortalBillDetail; where: "phone" | "desk" }) {
  const { t } = useTranslation();
  const asDate = usePortalDate();
  const { bill } = props;
  // A COMPARISON, never arithmetic — the same test `CWP-027`'s *Unpaid* filter
  // makes, so the two screens cannot disagree about what is still owed.
  const owed = Number(bill.owing) > 0;
  return (
    // ⚠ **THE MARK SAYS WHICH COPY THIS IS.** Both are always in the DOM and
    // CSS shows one; a test that could not tell them apart would answer with
    // whichever happened to be first and would go on passing if the other
    // disappeared.
    <div data-amount-due={props.where}>
    <Panel as="aside" title={t("portal.billDetail.amountDue")}>
      <p className="text-h3 font-bold tabular-nums text-neutral-900" data-figure="amount_due">
        {formatMoney(bill.owing, bill.currency)}
      </p>
      {owed ? (
        <>
          {bill.due_on ? (
            <p className="text-body text-neutral-700" data-due-on={bill.due_on}>
              {t("portal.billDetail.dueOn", { date: asDate(bill.due_on) })}
            </p>
          ) : null}
          <div className="mt-3" data-bill-pay="">
            <ErrandLink label={t("portal.bills.pay")} to="/pay-now" />
          </div>
        </>
      ) : (
        // B14 rule 32 — ONE sentence, and it is the whole state.
        <p className="text-body text-neutral-700" data-bill-settled="">
          {t("portal.billDetail.paidInFull")}
        </p>
      )}
    </Panel>
    </div>
  );
}

/**
 * Did this service block charge anything at all? — `DEF-CWP-3967` fault 5.
 *
 * ⚠ **ZERO IS THE TEST, NOT "HAS LINES".** A group with lines every one of
 * which is `0.00` is a heading, a table and a subtotal saying nothing, and the
 * live bill carried two of them. A group whose lines sum to zero because a
 * charge and a credit cancel is a different thing entirely and still draws —
 * which is why every line is examined rather than only the subtotal.
 *
 * ⚠ **STRING COMPARISON, NOT `Number`.** Hard rule 2 keeps money off floats in
 * a browser too. A 4dp figure is zero when its digits are; `-0.0000` is
 * treated as zero for the same reason `0.0000` is.
 */
function charged(group: PortalBillGroup): boolean {
  const isZero = (value: string | null) =>
    value === null || /^-?0*\.?0*$/.test(value.trim());
  if (!isZero(group.subtotal_display)) return true;
  return group.lines.some((line) => !isZero(line.amount_display));
}

/** The rail's three lines above the owing total.
 *
 *  ⚠ **AN UNSTAMPED FIGURE IS OMITTED, NEVER DRAWN AS `$0.00`.** `BR-BIL-035`
 *  writes nulls rather than zeros on purpose — *"0.00 would tell a customer in
 *  arrears that they are square"* — and `BR-CWP-093` says nothing empty ever
 *  appears, so the row simply is not there. */
function accountRows(t: (key: string) => string, bill: PortalBillDetail) {
  const rows: { key: string; label: string; value: React.ReactNode }[] = [];
  if (bill.account.brought_forward !== null) {
    rows.push({
      key: "brought_forward",
      label: t("portal.billDetail.broughtForward"),
      value: (
        <span data-figure="brought_forward">
          {formatMoney(bill.account.brought_forward, bill.currency)}
        </span>
      ),
    });
  }
  rows.push({
    key: "this_bill",
    label: t("portal.billDetail.thisBill"),
    value: <span data-figure="this_bill">{formatMoney(bill.account.this_bill, bill.currency)}</span>,
  });
  if (bill.account.paid_since !== null) {
    rows.push({
      key: "paid_since",
      label: t("portal.billDetail.paidSince"),
      value: (
        <span data-figure="paid_since">{formatMoney(bill.account.paid_since, bill.currency)}</span>
      ),
    });
  }
  return rows;
}

/**
 * **THE RATE, AS A NUMBER SOMEBODY CAN READ** — `DEF-CWP-3967`.
 *
 * `$5.2000 / kgal` where the column read `5.2000`, and `6.25%` where it read
 * `0.0625`. A customer could not tell whether `4.2400` was four dollars or
 * four cents, or per what — and `0.0200` for a two-per-cent tax is not even
 * the right order of magnitude to guess at.
 *
 * ⚠ **THE SCREEN DOES NOT DECIDE WHICH SHAPE IT IS.** `rate_basis` comes down
 * from the server, which owns the ×100 as well: `wording.percent_text` takes
 * percentage POINTS and a fraction handed to it prints `0.02%` for a two
 * per-cent rate. Both are well-formed strings, which is exactly why that
 * conversion is not done here.
 *
 * ⚠ **AND THE UNIT IS THE LINE'S OWN.** `formatQuantity` already refuses to
 * render a quantity without one (hard rule 3); a RATE per an unnamed unit is
 * the same fault, so a `per_unit` rate with no unit falls back to the bare
 * money figure rather than composing `$5.2000 / `.
 */
function rateText(
  t: (key: string, options?: Record<string, unknown>) => string,
  line: { rate: string | null; rate_basis: string | null; rate_percent: string | null; unit: string | null },
  currency: string | null,
): string {
  if (line.rate_basis === "percent" && line.rate_percent !== null) {
    return t("portal.billDetail.ratePercent", { percent: line.rate_percent });
  }
  if (line.rate_basis === "per_unit" && line.rate !== null) {
    const money = formatRate(line.rate, currency);
    return line.unit
      ? t("portal.billDetail.ratePerUnit", { rate: money, unit: line.unit })
      : money;
  }
  return line.rate ?? "—";
}

/** One service's block — heading, its lines, and its own subtotal. */
function ServiceGroup(props: { group: PortalBillGroup; currency: string | null }) {
  const { t } = useTranslation();
  const { group } = props;
  // ⚠ **THE SERVICE NAMES ARE `rating.service.*`, THE KEYS THE PRODUCT ALREADY
  // HAS IN ALL ELEVEN CATALOGUES** — the same lookup the staff bill detail
  // makes. A second set of portal-only words for *Water* and *Sewer* would be
  // two names for one thing, which is how they start disagreeing (law 5). The
  // ONE heading the portal owns is `taxes_and_fees`, which names no service.
  const heading =
    group.service === "taxes_and_fees"
      ? t("portal.billDetail.taxesAndFees")
      : t(`rating.service.${group.service}`, {
          defaultValue: group.service_name ?? group.service,
        });
  return (
    <div className="mt-3" data-group={group.service}>
      <SectionTitle>{heading}</SectionTitle>
      <MiniTable
        caption={t("portal.billDetail.linesCaption", { service: heading })}
        columns={[
          { key: "line", label: t("portal.billDetail.colLine") },
          { key: "quantity", label: t("portal.billDetail.colQuantity"), align: "right" },
          { key: "rate", label: t("portal.billDetail.colRate"), align: "right" },
          { key: "amount", label: t("portal.billDetail.colAmount"), align: "right" },
        ]}
        rows={group.lines.map((line, index) => ({
          key: `${group.service}-${index}`,
          cells: {
            line: line.description ?? "—",
            // ⚠ hard rule 3 — `formatQuantity` returns null without a unit, so
            // a bare number cannot reach this cell.
            quantity: (
              <span className="tabular-nums" data-quantity={`${group.service}-${index}`}>
                {formatQuantity(line.quantity, line.unit) ?? "—"}
              </span>
            ),
            // ⚠ A RATE IS NOT MONEY (`OQ-620(a)`): four decimals, and never
            // through `formatMoney`, which would print `$0.01` for `0.0089`.
            // ⚠ **AND IT IS NOT A BARE NUMBER EITHER** (`DEF-CWP-3967`). This
            // cell printed `4.2400` beside a water line and `0.0200` beside a
            // local tax, with nothing on the page saying whether either was
            // dollars, cents, or per what. The server says WHICH KIND of
            // number it is and the screen puts the currency and the unit, or
            // the per-cent sign, on it.
            rate: (
              <span className="tabular-nums" data-rate={`${group.service}-${index}`}>
                {rateText(t, line, props.currency)}
                {/* DEF-BIL-8744 — `19/30 days` under a rate whose amount was
                    cut down by days, so the line foots. */}
                <DayShareNote share={line.day_share} t={t} />
              </span>
            ),
            amount: (
              <span className="tabular-nums" data-amount={`${group.service}-${index}`}>
                {formatMoney(line.amount_display, props.currency)}
              </span>
            ),
          },
        }))}
      />
      {group.subtotal_display === null ? null : (
        <p className="mt-1 text-right text-base text-neutral-600" data-subtotal={group.service}>
          {t("portal.billDetail.groupSubtotal", {
            amount: formatMoney(group.subtotal_display, props.currency),
          })}
        </p>
      )}
    </div>
  );
}

/** `BR-CWP-071` — the readings behind the bill, **and how each was taken**.
 *
 *  ⚠ **THE PANEL IS ABSENT WHEN THERE ARE NO READINGS** (`BR-CWP-093`), which
 *  is every trash-only account and every bill issued before the read identity
 *  was stamped. An empty *Readings* heading invites the question of what
 *  belongs under it. */
function ReadingsPanel(props: { bill: PortalBillDetail }) {
  const { t } = useTranslation();
  // `DEF-CWP-3967` fault 3 — this panel was the ONE place in the portal
  // rendering a raw instant.
  const asDate = usePortalDate();
  const readings = props.bill.readings;
  if (readings.length === 0) return null;
  const anyEstimated = readings.some((row) => row.estimated);
  return (
    <Panel as="aside" title={t("portal.billDetail.readings")}>
      <MiniTable
        caption={t("portal.billDetail.readingsCaption")}
        columns={[
          { key: "meter", label: t("portal.billDetail.colMeter") },
          { key: "taken", label: t("portal.billDetail.colTaken") },
          { key: "reading", label: t("portal.billDetail.colReading"), align: "right" },
        ]}
        rows={readings.map((row, index) => ({
          key: `${row.meter ?? "meter"}-${index}`,
          cells: {
            // ⚠ **THE METER NAMES ITS SERVICE** (`DEF-CWP-3967` fault 4). The
            // column read `W-5026` and `E-5026` — two serial numbers one
            // letter apart — where a customer needs to know which row is
            // their water. The NUMBER stays, because it is the label on the
            // box in the yard and the thing they can go and check; the
            // service is the word that makes the row findable. The service is
            // the read's OWN linkage, so it names the meter that was actually
            // read rather than a service guessed from the number.
            meter: (
              <span data-meter={row.meter ?? ""}>
                {row.service
                  ? t("portal.billDetail.meterOf", {
                      service: t(`rating.service.${row.service}`, { defaultValue: row.service }),
                      meter: row.meter ?? "",
                    })
                  : row.meter ?? "—"}
              </span>
            ),
            // ⚠ **THROUGH THE TENANT'S OWN DATE FORMAT** — the value never
            // touched a formatter at all, so `2026-07-31T00:00:00+00:00`
            // reached the screen verbatim. `withTime` is FALSE: a meter
            // reading is a day's fact, and the time on it is midnight UTC on
            // every row this deployment has written.
            taken: (
              <span data-read-at={index}>{asDate(row.read_at) || "—"}</span>
            ),
            reading: (
              <span className="tabular-nums" data-reading={index}>
                {row.current_value ?? "—"}
              </span>
            ),
          },
        }))}
      />
      {/* ⚠ ONE SENTENCE, and it says HOW — which is the whole of BR-CWP-071.
          A reading with nothing on file about its method says so rather than
          claiming a reader took it. */}
      <p className="text-base text-neutral-600" data-readings-method="">
        {anyEstimated
          ? t("portal.billDetail.someEstimated")
          : t("portal.billDetail.noneEstimated")}
      </p>
    </Panel>
  );
}


/**
 * `US-CWP-065` / `US-CWP-066`'s two doors — **added by the wave-R lane, and the
 * reason it is HERE is hard-won law 2.**
 *
 * `CWP-055` (query this bill) and `CWP-054` (ask about it) are two built,
 * routed, tested screens; without a link from the bill a customer is looking at
 * they are dead UI — *"a component with an optional prop that nothing passes is
 * dead UI: it renders nothing, every test passes, and the feature does not
 * exist"*. The bill is where a person is standing when either question occurs
 * to them, so this is where the doors go.
 *
 * ⚠ **TWO DOORS AND NOT ONE, BECAUSE THEY ARE DIFFERENT CLAIMS.** *This bill is
 * wrong* raises a query a clerk judges and the bill does not change
 * (CLAUDE.md hard rule 4); *I do not understand this bill* raises a question a
 * clerk answers. Collapsing them would put every "what is this line?" on the
 * dispute queue.
 *
 * ⚠ **THE BILL TRAVELS BY ITS NUMBER IN BOTH** (B14 rule 31) — into the path
 * for the query, into `?bill=` for the question, which is where it can be
 * absent (`US-CWP-066` TC-5).
 */
function SomethingNotRight(props: { number: string }) {
  const { t } = useTranslation();
  const path = usePortalPath();
  if (props.number === "") return null;
  const bill = encodeURIComponent(props.number);
  return (
    <Panel as="aside" title={t("portal.billDetail.notRightTitle")}>
      {/* B14 rule 32 — one sentence for the section. */}
      <p>{t("portal.billDetail.notRightSentence")}</p>
      <Link
        to={path(`/bills/${bill}/dispute`)}
        className="mt-3 inline-block font-semibold text-accent-text no-underline hover:underline"
        data-link="dispute"
      >
        {t("portal.billDetail.queryThisBill")}
      </Link>
      <Link
        to={path(`/ask-a-question?bill=${bill}`)}
        className="mt-2 block font-semibold text-accent-text no-underline hover:underline"
        data-link="ask"
      >
        {t("portal.billDetail.askAboutThisBill")}
      </Link>
    </Panel>
  );
}
