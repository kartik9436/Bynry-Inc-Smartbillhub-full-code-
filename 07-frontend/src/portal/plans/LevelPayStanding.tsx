// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-055 (EP-CWP-10) — *"where your level pay stands."*
//           Screen: CWP-066 (blueprint `P52`)
// Rules:    BR-CWP-054 (the level, the variance and the settle-up, plus each
//           re-levelling and what happened) · BR-CWP-052 (the utility's own
//           assessment of a customer is held back) · B14 rule 21 · rule 31 ·
//           rule 32 · rule 33 · rule 35 · rule 36 (compose the kit) ·
//           CLAUDE.md hard rule 2 (money displays at 2 dp)
// Tests:    src/portal/plans/LevelPayStanding.dom.test.tsx
// Impacts:  src/portal/api/portalClient.ts `getLevelPayStanding`
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { PageHeader } from "@/components/PageHeader";

import {
  Card,
  ConsequenceBox,
  KpiRow,
  KpiTile,
  MiniTable,
  MoneyBars,
  SectionTitle,
  TwoCol,
  shortMonthText,
  usePortalPath,
} from "../components/primitives";
import { PortalScreen, PortalState, type PortalWayOut } from "../components/states";
import { usePortalDate } from "../components/regional";
import { formatMoney } from "../signin/Enrol";
import { getLevelPayStanding, type PortalLevelStandingView } from "../api/portalClient";

/** The month's name, keyed 1–12.
 *
 * ⚠ **THE SAME `settings.regional.month.*` KEYS `CWP-044` READS, AND FOR THE
 * REASON THAT SCREEN WROTE DOWN:** two homes for one fact are free to disagree
 * the day somebody corrects one. `null` for an unset month is a real answer and
 * never June — a screen that defaulted would be right for one utility and
 * silently wrong for every other.
 */
function monthKey(month: number | null): string | null {
  if (month === null || month < 1 || month > 12) return null;
  return `settings.regional.month.${month}`;
}

/**
 * `CWP-066` — what level pay is really costing, and when it settles.
 *
 * ⚠ **`CWP-044` IS THE JOINING SCREEN AND THIS IS THE STANDING ONE**
 * (`US-CWP-055` §1: *"an enrolled customer has no screen at all today"*). It
 * carries none of the offer's figures — no trailing total, no monthly average,
 * no *you would pay* — because those answer a different question and a second
 * copy of them here is a second arithmetic over one fact.
 *
 * ⚠ **AHEAD AND BEHIND ARE WORDS, NEVER A BARE SIGNED NUMBER** (TC-7). The
 * server sends a positive size and a DIRECTION; the catalogue writes *you are
 * `$47.30` ahead*. `Math.abs` appears nowhere, because there is no sign here to
 * strip — the direction was decided where the balance is stored.
 *
 * ⚠ **AN OVERRIDE IS SHOWN AND ITS REASON IS NOT** (TC-4). The reason is the
 * utility's own note about a customer and is not on the wire at all, which is
 * `BR-CWP-052`'s posture: the surest guard is that the server never selects it.
 *
 * ⚠ **A CUSTOMER NOT ON LEVEL PAY IS ROUTED, NOT SHOWN AN EMPTY SCREEN**
 * (TC-5) — and the SERVER says where, so the wave that moves `CWP-044` moves
 * one map and not two.
 */
export function LevelPayStandingView(props: { accountId: string }) {
  const { t, i18n } = useTranslation();
  //: `DEF-CWP-4138` — the tenant's own date format, through the ONE formatter
  //: (`DEF-CWP-3994`'s wire). An unset Regional setting publishes nothing and
  //: this hands back the server's string unchanged, so it cannot invent a
  //: format for a tenant that has not chosen one.
  const showDate = usePortalDate();
  // ⚠ `undefined` IS *STILL READING*; *not on level pay* is
  // `view.standing === null`, which the server states and routes on. Two
  // different absences, two different screens.
  const [view, setView] = useState<PortalLevelStandingView | undefined>(undefined);
  const [failed, setFailed] = useState(false);
  //: R-10's *Try again* needs something to try — see `Overdue.tsx`.
  const [attempt, setAttempt] = useState(0);
  const path = usePortalPath();

  useEffect(() => {
    let live = true;
    setFailed(false);
    getLevelPayStanding(props.accountId)
      .then((answer) => {
        if (live) setView(answer);
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
      title={t("portal.levelStanding.title")}
    />
  );

  // ⚠ **R-10** (PO 2026-09-11). A customer on budget billing who cannot read
  // where they stand is being told, on a money screen, that something is wrong
  // and nothing more. *Try again* re-issues the read; the second door is the
  // joining screen, which is where this one's own empty branch already points.
  const failedWaysOut: PortalWayOut[] = [
    {
      label: t("portal.payNow.tryAgain"),
      onClick: () => setAttempt((n) => n + 1),
      tone: "primary",
      testKey: "try-again",
    },
    { label: t("portal.levelPay.title"), to: path("/level-pay"), testKey: "level-pay" },
  ];

  if (failed) {
    return (
      <PortalScreen screen="CWP-066" head={head}>
        <PortalState
          kind="failed"
          testId="level-standing"
          sentence={t("portal.levelStanding.couldNotRead")}
          waysOut={failedWaysOut}
        />
      </PortalScreen>
    );
  }
  if (view === undefined) {
    return (
      <PortalScreen screen="CWP-066" head={head}>
        <PortalState
          kind="loading"
          testId="level-standing"
          sentence={t("portal.levelStanding.reading")}
        />
      </PortalScreen>
    );
  }

  const standing = view.standing;
  if (standing === null) {
    // ⚠ **THE DOOR IS THE SERVER'S OWN `join_at`, NOT A STRING THIS FILE
    // TYPES** — so a tenant that does not offer budget billing gets the
    // sentence and no door, rather than a button into a screen that refuses.
    return (
      <PortalScreen screen="CWP-066" head={head}>
        <PortalState
          kind="empty"
          testId="level-standing"
          sentence={t("portal.levelStanding.notOnIt")}
          waysOut={
            view.join_at
              ? [
                  {
                    label: t("portal.levelStanding.readAbout"),
                    // ⚠ **`path(...)`, AND THE TEST CAUGHT IT MISSING.**
                    // `ErrandLink` resolves a portal address itself;
                    // `PortalWayOut.to` does NOT — its own docstring says
                    // *"an ALREADY-RESOLVED portal address — run it through
                    // `usePortalPath` in the screen"*, because a bare
                    // `/level-pay` comes out `//portal/level-pay`, a
                    // protocol-relative URL to another host that reads as a
                    // perfectly good string to every assertion we own
                    // (`BR-CWP-007`). This lane wrote the bare form while
                    // moving the door into the card and TC-5 went red on the
                    // whole address, which is why it asserts the whole one.
                    to: path(view.join_at),
                    testKey: "join",
                  },
                ]
              : undefined
          }
        />
      </PortalScreen>
    );
  }

  const currency = standing.currency;
  const month = monthKey(standing.settle_up_month);
  const settlesIn =
    month === null
      ? t("portal.levelStanding.settleMonthUnset")
      : t(month);

  return (
    <div data-screen="CWP-066" className="flex flex-col gap-4">
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
      {/* ⚠ **THE PORTAL'S `KpiRow`, NOT THE STAFF `KPIStrip` — `DEF-CWP-4914`.**
          The staff strip's money tile REQUIRES a `BR-REP-001` date basis and
          PRINTS it in the tile header, so **`AS AT POSTING DATE` was rendered
          on two of the three tiles, in the largest type on the screen**, to a
          customer looking at what they pay each month. It is a reporting label
          — it tells an accountant which of two dates a figure is cut on — and
          a customer reads it as an error or as a date that is somehow theirs.
          ⚠ **`primitives.tsx` PREDICTED THIS IN ITS OWN DOCSTRING** and built
          `KpiRow`/`KpiTile` for exactly this reason: *"`as at posting date` is
          a reporting label a customer has no use for and would read as an
          error"*. The component existed, the reason was written down, and this
          screen imported the other one anyway — which is B14 rule 36 needing a
          person rather than a gate, because nothing here reads a rendered
          tile header.
          ⚠ **`columns={3}` IS A REAL VALUE** and `08-screen-layouts.md` names
          three tiles on this screen; it stacks to one column at `max-md`. */}
      <KpiRow columns={3}>
        <KpiTile
          testKey="level"
          lead
          label={t("portal.levelStanding.youPay")}
          value={formatMoney(standing.level, currency)}
        />
        <KpiTile
          testKey="variance"
          label={
            standing.variance_direction === "behind"
              ? t("portal.levelStanding.behindBy")
              : standing.variance_direction === "ahead"
                ? t("portal.levelStanding.aheadBy")
                : t("portal.levelStanding.exactlyLevel")
          }
          value={formatMoney(standing.variance, currency)}
        />
        <KpiTile
          testKey="settles"
          label={t("portal.levelStanding.settlesUpIn")}
          value={settlesIn}
        />
      </KpiRow>

      {/* ⚠ **THE PICTURE THIS SCREEN IS ABOUT (`CWP-066`, `DEF-CWP-3981`).**
          `months[]` — what you PAID against what it actually COST, month by
          month — has been served since `US-CWP-055` and the screen drew a
          COUNT of it: *"12 months counted"*. The whole point of a level-pay
          standing screen is the gap between the two lines, and a count cannot
          show a gap.

          ⚠ **BOTH SERIES ARE MONEY AND NEITHER IS A QUANTITY**, which is why
          this is `MoneyBars` and not `UsageBars`. `billing_seam.level_pay_
          months` composes both through `_money()`: `paid` is the LEVEL in
          force that month and `used` is the ACTUAL the bill came to. Hard
          rule 3 is not engaged — there is no unit here, only a currency —
          and `DEF-CWP-3981` was right that pushing money through the
          consumption chart would have labelled a currency as a unit. */}
      {view.months.length > 0 ? (
        <Card testId="level-standing-chart">
          <SectionTitle>{t("portal.levelStanding.chartTitle")}</SectionTitle>
          <MoneyBars
            testId="level-standing"
            bars={view.months.map((row, index) => ({
              key: row.month ?? String(index),
              label: row.month ? shortMonthText(row.month, i18n.language) : null,
              value: row.paid === null ? null : Number(row.paid),
              display:
                row.paid === null ? null : formatMoney(row.paid, row.currency ?? currency),
              compareValue: row.used === null ? null : Number(row.used),
              compareDisplay:
                row.used === null ? null : formatMoney(row.used, row.currency ?? currency),
            }))}
            seriesLabel={t("portal.levelStanding.chartPaid")}
            compareLabel={t("portal.levelStanding.chartUsed")}
            emptyLabel={t("portal.levelStanding.noMonthsYet")}
          />
        </Card>
      ) : null}

      <TwoCol
        main={
          <Card testId="level-changes">
            <SectionTitle>{t("portal.levelStanding.whenItChanged")}</SectionTitle>
            {standing.override !== null ? (
              // TC-4 — the override's VALUE, and never the internal reason.
              <p className="text-body text-neutral-700" data-standing-override="">
                {t("portal.levelStanding.overrideSet", {
                  amount: formatMoney(standing.override, currency),
                  computed: formatMoney(standing.computed_level ?? standing.level, currency),
                })}
              </p>
            ) : null}
            {standing.changes.length === 0 ? (
              // B14 rule 17 — a sentence naming what will fill it (TC-3's
              // absence, which is a real state on a first year).
              <p className="text-body text-neutral-600" data-changes-empty="">
                {t("portal.levelStanding.noChangesYet")}
              </p>
            ) : (
              <div className="mt-1">
                <MiniTable
                  caption={t("portal.levelStanding.changesCaption")}
                  columns={[
                    { key: "when", label: t("portal.levelStanding.colWhen") },
                    { key: "what", label: t("portal.levelStanding.colWhat") },
                    { key: "level", label: t("portal.levelStanding.colNewLevel"), align: "right" },
                    { key: "after", label: t("portal.levelStanding.colBalanceAfter"), align: "right" },
                  ]}
                  rows={standing.changes.map((change, index) => ({
                    key: `${change.on ?? index}-${change.event}`,
                    cells: {
                      when: showDate(change.on) || "—",
                      what: t(`portal.levelStanding.event.${change.event}`, {
                        defaultValue: t("portal.levelStanding.event.other"),
                      }),
                      level:
                        change.level === null
                          ? "—"
                          : formatMoney(change.level, change.currency ?? currency),
                      // The sign is the server's — a movement that took money
                      // off the balance arrives negative and stays negative.
                      after: formatMoney(change.balance_after, change.currency ?? currency),
                    },
                  }))}
                />
              </div>
            )}
          </Card>
        }
        rail={
          <Card testId="level-settle-up">
            <SectionTitle>{t("portal.levelStanding.whatHappensThen")}</SectionTitle>
            <ConsequenceBox
              heading={
                month === null
                  ? t("portal.levelStanding.settleMonthUnset")
                  : t("portal.levelStanding.inMonth", { month: settlesIn })
              }
              bullets={[
                <span key="direction" data-consequence-code={standing.variance_direction}>
                  {standing.variance_direction === "behind"
                    ? t("portal.levelStanding.then.behind", {
                        amount: formatMoney(standing.variance, currency),
                      })
                    : standing.variance_direction === "ahead"
                      ? t("portal.levelStanding.then.ahead", {
                          amount: formatMoney(standing.variance, currency),
                        })
                      : t("portal.levelStanding.then.level")}
                </span>,
                <span key="relevel" data-consequence-code="relevelled">
                  {t("portal.levelStanding.then.relevelled")}
                </span>,
              ]}
            />
            {view.months.length > 0 ? (
              <p className="text-base text-neutral-600" data-standing-months="">
                {t("portal.levelStanding.monthsCounted", { count: view.months.length })}
              </p>
            ) : null}
          </Card>
        }
      />
    </div>
  );
}
