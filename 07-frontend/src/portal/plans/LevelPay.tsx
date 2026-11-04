// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-054 (EP-CWP-10) — *"Level pay: pay the same amount every
//           month"*. Screen: CWP-044 (blueprint `P30`)
// Rules:    BR-CWP-054 (the level, the variance and the settle-up month are
//           SHOWN) · BR-BIL-017 / BR-BIL-021 (eligibility, rounding, re-level
//           cadence and settle-up month are TENANT SETTINGS, read not assumed)
//           · BR-CWP-001 (enrolment is not one of the six portal writes) ·
//           BR-CWP-056 (held WITH its reason) · B14 rule 21 · rule 31 ·
//           rule 32 · rule 33 · rule 35 · rule 36 (compose the kit) ·
//           CLAUDE.md hard rule 2 (money displays at 2 dp)
// Open:     OQ-CWP-1568 (may a customer join level pay themselves? — the
//           SAME question as CWP-063's three controls, which is why one id
//           answers both)
// Defect:   DEF-CWP-4139 — this read OQ-CWP-1565 until 2026-09-06, an id that
//           was never issued.
// Tests:    src/portal/plans/LevelPay.dom.test.tsx
// Impacts:  src/portal/api/portalClient.ts `getLevelPay`
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { PageHeader } from "@/components/PageHeader";

import {
  Card,
  ConsequenceBox,
  HeldButton,
  KVList,
  SectionTitle,
  TotalRow,
  MoneyBars,
  TwoCol,
  WhereNext,
  usePortalPath,
} from "../components/primitives";
import { PortalScreen, PortalState, type PortalWayOut } from "../components/states";
import { formatMoney } from "../signin/Enrol";
import { getLevelPay, type PortalLevelPay } from "../api/portalClient";

/**
 * The month's name, keyed 1–12.
 *
 * ⚠ **THIS READS THE VOCABULARY THE PRODUCT ALREADY HAS RATHER THAN A SECOND
 * COPY OF IT.** `settings.regional.month.*` has existed in all eleven
 * catalogues since the regional settings screen; this lane wrote twelve more
 * keys saying the same twelve words before G15 caught it. Two homes for one
 * fact are free to disagree the day somebody corrects one — the PO's ruling of
 * 2026-09-04 about reads, in copy instead of in code.
 *
 * ⚠ **AND NOT `Intl.DateTimeFormat` EITHER**, which is how `SettingsPortalTips`
 * does it: that formats in the BROWSER's idea of the language, and this screen
 * must say the month in the language the customer chose for the portal.
 *
 * `null` for an unset month is a real answer and never a default —
 * `settings_families` ratifies no month (*"rule names the parameter, ratifies
 * no month"*), so a screen that fell back to June would be right for one
 * utility and silently wrong for every other (TC-6).
 */
function monthKey(month: number | null): string | null {
  if (month === null || month < 1 || month > 12) return null;
  return `settings.regional.month.${month}`;
}

/**
 * `[year, month]` → *March 2026*, in the language the customer chose.
 *
 * ⚠ **THE ORDER IS THE CATALOGUE'S AND NOT THIS FILE'S** (`CR-085` `CPB-18`,
 * B14 rule 35). `portal.levelPay.monthAndYear` is one tiny key precisely so
 * that Japanese can write `2026年3月` and Korean `2026년 3월` while English
 * writes `March 2026` — a template built here with a space in it would force
 * every language into English word order.
 *
 * ⚠ **AND THE MONTH WORD IS `settings.regional.month.*`, THE PRODUCT'S OWN**,
 * for the reason `monthKey` above already gives: two homes for one fact are
 * free to disagree the day somebody corrects one.
 */
function monthAndYear(
  pair: [number, number] | null,
  t: (key: string, options?: Record<string, unknown>) => string,
): string | null {
  if (pair === null) return null;
  const [year, month] = pair;
  const key = monthKey(month);
  if (key === null) return null;
  return t("portal.levelPay.monthAndYear", { month: t(key), year: String(year) });
}

/**
 * The month an account short of history becomes eligible — its FIRST bill plus
 * the tenant's own window, less one.
 *
 * ⚠ **BOTH INPUTS ARE FACTS AND NEITHER IS A CLOCK.** The first billed month
 * is the account's own, the window is `eligibility_months` from the tenant's
 * settings (`BR-BIL-017`/`BR-BIL-021`), and nothing here reads a date. So the
 * sentence is reproducible from the same two numbers a clerk can see, which is
 * the test `CPB-07` is kept out of scope for failing.
 *
 * ⚠ **IT PROMISES A DATE, NOT A FIGURE.** *We can work this out once your
 * March 2027 bill is here* says when the question can be ANSWERED. It does not
 * say what the answer will be, because nobody knows yet.
 */
function eligibleFrom(
  firstBilled: [number, number] | null,
  requiredMonths: number | null,
): [number, number] | null {
  if (firstBilled === null || requiredMonths === null || requiredMonths < 1) return null;
  const [year, month] = firstBilled;
  const zeroBased = (year * 12 + (month - 1)) + (requiredMonths - 1);
  return [Math.floor(zeroBased / 12), (zeroBased % 12) + 1];
}

/**
 * `CWP-044` — *"we average your year and settle up once"*.
 *
 * ⚠ **THIS SCREEN IS A VIEW OVER MACHINERY THAT ALREADY RUNS.** Eligibility
 * months, the rounding of the level, the re-level cadence and the settle-up
 * month are all configured settings today, and `apps.billing.budget` has
 * computed the level since `US-BIL-018` — ❄️ GT-24's own function. Level pay
 * is genuinely finished behind the counter and hidden from the person it
 * helps; nothing here recomputes anything (`US-CWP-054` §7: *"existing,
 * configured arithmetic; read, not recomputed"*).
 *
 * ⚠ **THE ROUNDING IS THE TENANT'S AND NOT A RULE IN THE PORTAL** (TC-2).
 * `$1,501.09 ÷ 12 = $125.0908…` and the level is `$125.00` because the
 * tenant's `level_rounding` says whole dollars. Both figures are shown,
 * because *"$125.09 rounded to $125.00"* is the sentence that explains the
 * level and a screen given only the level cannot say it.
 *
 * ⚠ **THE SETTLE-UP MONTH IS NAMED FROM THE SETTING, NEVER HARDCODED TO JUNE**
 * (TC-6). A screen that wrote June would be right for one utility and silently
 * wrong for every other, which is the failure mode no test in this repo can
 * see. Where no month is set the box says so.
 *
 * ⚠ **AN ALREADY-ENROLLED ACCOUNT IS NOT OFFERED ENROLMENT AGAIN** (TC-4): it
 * is routed to where its level actually stands, which is `CWP-066`.
 *
 * ⚠ **AND *JOIN LEVEL PAY* IS HELD.** Enrolling writes `account_budget_status`
 * and `BR-CWP-001` allows the portal six kinds of row, none of them this one.
 * `08-screen-layouts.md` already draws the control **held**; the ruling that
 * would open it is `OQ-CWP-1568`.
 */
export function LevelPayView(props: { accountId: string }) {
  const { t } = useTranslation();
  const path = usePortalPath();
  const [position, setPosition] = useState<PortalLevelPay | null | undefined>(undefined);
  const [failed, setFailed] = useState(false);
  //: R-10's *Try again* needs something to try — see `Overdue.tsx`.
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    setFailed(false);
    getLevelPay(props.accountId)
      .then((answer) => {
        if (live) setPosition(answer.level_pay);
      })
      .catch(() => {
        if (live) setFailed(true);
      });
    return () => {
      live = false;
    };
  }, [props.accountId, attempt]);

  // ⚠ **THE HEAD IS BUILT ONCE AND RENDERS ON EVERY BRANCH, LOADING INCLUDED**
  // (`DEF-CWP-4000`; audit D1, delta X4/X5). It composes the shared
  // `components/PageHeader.tsx` — the ONE page head B14 rule 2 names, which
  // fifteen portal files already used and twenty-eight signed-in screens did
  // not. A head that lived only in the happy-path return would leave the page
  // with no `<h1>` for as long as the request takes.
  const head = (
    <PageHeader
      kicker={t("portal.kicker.payments")}
      title={t("portal.levelPay.title")}
    />
  );

  // ⚠ **THIS SCREEN HELD THE WORST R-10 BREACH ON THE WHOLE PATCH AND IT WAS
  // THE `null` BRANCH** (PO 2026-09-11, verbatim: *"when a screen tells a
  // customer something bad, the thing they can do about it must be on that
  // same screen, next to the message. Not a page away. Not in a menu. Right
  // there."*). *"We could not find an account to work this out for."* was the
  // entire page: **no button, no telephone number, no link back**, on a screen
  // somebody opens because their bills swing and they want them not to. Every
  // other empty branch on this patch already carried a door; this one was
  // audited as the single exception and is now the same shape as the rest.
  const waysOutOfNothing: PortalWayOut[] = [
    {
      label: t("portal.payNow.tryAgain"),
      onClick: () => setAttempt((n) => n + 1),
      tone: "primary",
      testKey: "try-again",
    },
    { label: t("portal.levelStanding.title"), to: path("/level-pay/standing"), testKey: "standing" },
    { label: t("portal.overdue.helpPaying"), to: path("/help-paying"), testKey: "help-paying" },
  ];

  if (failed) {
    return (
      <PortalScreen screen="CWP-044" head={head}>
        <PortalState
          kind="failed"
          testId="level-pay"
          sentence={t("portal.levelPay.couldNotRead")}
          waysOut={waysOutOfNothing}
        />
      </PortalScreen>
    );
  }
  if (position === undefined) {
    return (
      <PortalScreen screen="CWP-044" head={head}>
        <PortalState kind="loading" testId="level-pay" sentence={t("portal.levelPay.reading")} />
      </PortalScreen>
    );
  }
  if (position === null) {
    return (
      <PortalScreen screen="CWP-044" head={head}>
        <PortalState
          kind="empty"
          testId="level-pay"
          sentence={t("portal.levelPay.noAccount")}
          waysOut={waysOutOfNothing}
        />
      </PortalScreen>
    );
  }

  // TC-4 — an enrolled account is ROUTED, not offered enrolment a second time.
  if (position.enrolled) {
    const enrolledMonth = monthKey(position.enrolled_settle_up_month);
    return (
      <PortalScreen screen="CWP-044" head={head}>
        <Card testId="level-pay">
          {/* ⚠ **NO SECOND HEADING** (`CR-085`, B14 rule 32). The head above
              already carries `portal.levelPay.title`; printing it again here
              spent the section's whole description budget saying the screen's
              own name twice. */}
          <p className="mt-2 text-body text-neutral-700" data-level-pay-enrolled="">
            {t("portal.levelPay.alreadyOn", {
              amount: formatMoney(position.enrolled_level ?? "0", position.currency ?? "USD"),
            })}
          </p>
          <p className="mt-2 text-base text-neutral-600" data-level-pay-enrolled-month="">
            {enrolledMonth === null
              ? t("portal.levelPay.settleMonthUnset")
              : t("portal.levelPay.settlesIn", { month: t(enrolledMonth) })}
          </p>
          {/* ⚠ **THIS BRANCH NEEDS THE DOOR MOST, AND IT WAS THE ONE MOST
              LIKELY TO BE MISSED** (`DEF-CWP-3954`). A customer already ON
              level pay is not offered enrolment a second time — so this card
              is all they see here, and *where your level pay stands* is the
              only question they had. It is on the offer branch below as well. */}
          <WhereNext
            mark="level-pay"
            doors={[
              {
                key: "standing",
                label: t("portal.levelStanding.title"),
                to: "/level-pay/standing",
              },
            ]}
          />
        </Card>
      </PortalScreen>
    );
  }

  const currency = position.currency ?? "USD";
  const month = monthKey(position.settle_up_month);
  //: `CR-085` `CPB-18`. ⚠ **THE EARLIEST GAP AND NOT THE NEWEST.** The lists
  //: arrive newest first; the oldest hole is the one that has been outstanding
  //: longest and is the one worth ringing about.
  const gaps = position.missing_month_gaps;
  const gapMonth = gaps.length > 0 ? monthAndYear(gaps[gaps.length - 1], t) : null;
  //: ⚠ **`null` WHERE THE ACCOUNT HAS NEVER BEEN BILLED.** No history is not a
  //: hole in one, and this screen already has a sentence for that case.
  const possibleFrom =
    position.missing_months_before_first_bill.length > 0
      ? monthAndYear(eligibleFrom(position.first_billed_month, position.required_months), t)
      : null;
  return (
    <div data-screen="CWP-044">
      {/* ⚠ **THE SCREEN ID IS A LITERAL HERE AND MUST STAY ONE — `CR-085` lane 8.**
          `PortalScreen` renders an identical DOM from its `screen` prop, but THREE
          source scanners find a portal screen by the exact string
          `data-screen="CWP-…"` and not one of them reads a prop: this census,
          `g100_every_screen_has_a_door.py` and `g103_holds_cannot_rot.py`. Wrapping
          this branch too made the whole file invisible to all three — hard-won law
          7’s *reporting zero over a scope it silently excluded*.
          `bills/BillDetail.tsx` keeps the literal on its populated branch for
          exactly this reason. */}
      {head}
      <TwoCol
        main={
          <Card testId="level-pay">
            {/* B14 rule 32 — one sentence for the section, and the head above
                already names the screen (`CR-085`). */}
            <p className="mt-2 text-body text-neutral-700" data-level-pay-lead="">
              {t("portal.levelPay.lead")}
            </p>
            {/* ⚠ **THE HONEST PART, AND IT GOES ABOVE THE BUTTON**
                (wireframe screen 47): *"'This spreads your bills — it does not
                lower them' is on the screen, above the button. Budget billing
                generates complaints when the settle-up arrives unexplained."*
                The lead beside it explains what the product does; this is the
                one line that says what it does NOT do, and it was nowhere on
                the screen. It is outside the branch below, so it is read by
                the customer who cannot be quoted a figure yet as well as by
                the one who can. */}
            <p className="mt-2 text-body font-semibold text-neutral-800" data-level-pay-honest="">
              {t("portal.levelPay.spreadsNotLowers")}
            </p>
            {position.level === null ? (
              // ⚠ NOT `$0.00`. A zero monthly amount is a real, chooseable
              // figure and would read as *this customer pays nothing*. The
              // reason travels from the server and is said in words (TC-3).
              <>
                {/* ⚠ **`CR-085` `CPB-18` — *WHICH* MONTH, NOT JUST HOW MANY.**
                    *You have 11 months of bills and we average 12* is true and
                    a customer can do nothing with it: it does not say whether a
                    bill went astray or whether they simply have not been here a
                    year, and those want opposite actions. The server publishes
                    the two lists separately for exactly that reason.

                    ⚠ **A GAP IS THE FIRST THING SAID, BECAUSE IT IS THE ONLY
                    ONE ANYBODY CAN ACT ON.** A missing bill inside a run of
                    bills is something to ring about; months before the account
                    existed are not. */}
                {gapMonth !== null ? (
                  <p className="mt-3 text-body text-neutral-600" data-level-pay-gap="">
                    {t("portal.levelPay.missingMonth", {
                      count: position.missing_month_gaps.length,
                      first: gapMonth,
                    })}
                  </p>
                ) : (
                  <p className="mt-3 text-body text-neutral-600" data-level-pay-unavailable="">
                    {position.months_of_history < (position.required_months ?? 12)
                      ? t("portal.levelPay.notEnoughHistory", {
                          have: position.months_of_history,
                          need: position.required_months ?? 12,
                        })
                      : t("portal.levelPay.cannotCompute")}
                  </p>
                )}
                {/* ⚠ **THE MONTH IT BECOMES POSSIBLE — A DATE, NOT A FIGURE.**
                    A stated absence in its own small line, the shape this screen
                    already uses for `settleMonthUnset`, so the section keeps one
                    sentence (B14 rule 32). Drawn only where the account is
                    simply young: an account with a real GAP is told about the
                    gap, and quoting a future month beside it would suggest the
                    missing bill will arrive on its own. */}
                {gapMonth === null && possibleFrom !== null ? (
                  <p className="mt-2 text-base text-neutral-600" data-level-pay-possible-from="">
                    {t("portal.levelPay.possibleFrom", { month: possibleFrom })}
                  </p>
                ) : null}
              </>
            ) : (
              <>
                <div className="mt-3">
                  <KVList
                    rows={[
                      {
                        key: "twelve",
                        label: t("portal.levelPay.lastMonths", {
                          count: position.months_counted,
                        }),
                        value: formatMoney(position.trailing_total ?? "0", currency),
                      },
                      {
                        key: "average",
                        label: t("portal.levelPay.monthlyAverage"),
                        value: formatMoney(position.monthly_average ?? "0", currency),
                      },
                      {
                        key: "rounded",
                        label: t("portal.levelPay.roundedTo"),
                        value: formatMoney(position.level, currency),
                      },
                    ]}
                  />
                </div>
                <div className="mt-2">
                  <TotalRow
                    testKey="level"
                    label={t("portal.levelPay.youWouldPay")}
                    value={formatMoney(position.level, currency)}
                  />
                </div>
                <div className="mt-4">
                  <ConsequenceBox
                    heading={t("portal.levelPay.consequenceHeading")}
                    bullets={[
                      <span key="every" data-consequence-code="every_bill">
                        {t("portal.levelPay.consequence.everyBill", {
                          amount: formatMoney(position.level, currency),
                        })}
                      </span>,
                      <span key="check" data-consequence-code="checked">
                        {position.relevel_cadence_months === null
                          ? t("portal.levelPay.consequence.checkedUnset")
                          : t("portal.levelPay.consequence.checked", {
                              count: position.relevel_cadence_months,
                            })}
                      </span>,
                      <span key="settle" data-consequence-code="settles">
                        {month === null
                          ? t("portal.levelPay.settleMonthUnset")
                          : t("portal.levelPay.consequence.settles", { month: t(month) })}
                      </span>,
                    ]}
                  />
                </div>
                {/* ⚠ **STILL HELD, AND THE RULING THAT WOULD RELEASE IT IS
                    NOW CLOSED — WHICH IS THE OPPOSITE OF WHAT IT LOOKS LIKE.**
                    `OQ-CWP-1568` was answered on 2026-09-11: a signed-in
                    customer MAY join budget billing. **Permission is not a
                    write path.** `apps/portal` serves this screen as a READ;
                    `BR-CWP-001` allows the portal rows of exactly six kinds and
                    budget enrolment is none of them, `write_points.py` says in
                    its own words that adding one *"is a ruling and not an
                    edit"*, and `G81` fails the build until a row is recorded.
                    There is no endpoint to point this button at, so it stays
                    held and `holds.ts` now carries the CLOSED ruling and the
                    three things still to decide rather than *"the question is
                    open"*, which stopped being true.

                    ⚠ **AND THE SERVER'S `join_held` IS NOT READ, DELIBERATELY**
                    (`DEF-CWP-4913`, amended). `selectors.level_pay` writes
                    `"join_held": True` as a literal and `"join_held_reason":
                    "OQ-CWP-1568"` beside it. Reading a constant would add a
                    branch that cannot execute — hard-won law 7's *incapable of
                    failing* shape — and the reason is an internal id that B14
                    rule 31 keeps off the glass in every language. The refusal
                    a customer reads is the catalogue's own six words. */}
                <div className="mt-3" data-level-pay-join="">
                  <HeldButton
                    label={t("portal.levelPay.join")}
                    reason={t("portal.levelPay.joinHeld")}
                  />
                </div>
              </>
            )}
            {/* ⚠ **`CWP-066` HAD NO DOOR** (`DEF-CWP-3954`). `screenIds.ts`
                says why the two are separate screens — *"`CWP-044` is the
                JOINING screen and this is the STANDING one — two questions
                about one subject, and a customer is sent to each from a
                different place"* — and this is that place: somebody reading
                what level pay WOULD cost is one question away from where
                theirs actually stands. It is outside the branch above, so a
                customer with too little history to be quoted a figure can
                still get there; `CWP-066` answers *"You are not on level pay,
                so there is nothing to show here yet."* */}
            <WhereNext
              mark="level-pay"
              doors={[
                {
                  key: "standing",
                  label: t("portal.levelStanding.title"),
                  to: "/level-pay/standing",
                },
              ]}
            />
          </Card>
        }
        rail={
          <Card testId="level-pay-chart">
            {/* ⚠ **THE TITLE SAID *This month, either way* OVER TWELVE MONTHS
                OF BILLS** (`DEF-CWP-4915`). The chart is this account's last
                twelve bills with the level drawn across them — a YEAR, and the
                one picture that makes the argument — and it was captioned as
                though it compared a single month two ways. It was wrong in all
                eleven catalogues, and no check in this repository can read
                whether a caption describes the thing under it. */}
            <SectionTitle>{t("portal.levelPay.chartTitle")}</SectionTitle>
            {position.billed.length === 0 ? (
              <p className="mt-2 text-body text-neutral-600" data-level-pay-chart-empty="">
                {t("portal.levelPay.noBills")}
              </p>
            ) : (
              // ⚠ **THE KIT'S CHART, NOT THIS SCREEN'S OWN (`DEF-CWP-3981`,
              // B14 rule 36).** `BilledBars` was declared in this file, which
              // is how `Panel`, `Chip` and `TwoCol` each ended up existing
              // twice (`DEF-CWP-3655`, `DEF-CWP-3984`). `CWP-066` wants the
              // same picture with a second series, and copying this one is
              // exactly the drift rule 36 exists to stop — so it moved to the
              // kit before the second caller arrived rather than after.
              <MoneyBars
                testId="level-pay"
                bars={position.billed.map((amount, index) => ({
                  key: String(index),
                  label: null,
                  value: Number(amount),
                  display: formatMoney(amount, currency),
                }))}
                seriesLabel={t("portal.levelPay.chartTitle")}
                referenceValue={position.level === null ? null : Number(position.level)}
                referenceLabel={
                  position.level === null
                    ? null
                    : t("portal.levelPay.chartLegend", {
                        amount: formatMoney(position.level, currency),
                      })
                }
                emptyLabel={t("portal.levelPay.noBills")}
              />
            )}
          </Card>
        }
      />
    </div>
  );
}

