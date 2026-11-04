// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-040 (EP-CWP-08) — *Usage, and the services that are not
//           measured say so*. Screen: CWP-033 (blueprint `P19`)
// Rules:    BR-CWP-073 (an unmeasured service says what it is billed on —
//           **no empty chart**) · BR-CWP-095 (one tip, on and in season, or no
//           slot at all) · BR-CWP-093 (nothing empty ever appears) ·
//           BR-MET-106 (an unread month is ABSENT, never 0; estimates count
//           and are MARKED) · CLAUDE.md hard rule 3 (a consumption always
//           carries its unit — including on a chart axis and in a CSV column) ·
//           B14 rule 21 (Tailwind utilities; `portal/` is on
//           route-b-migrated.txt) · rule 31 (no database id on screen) ·
//           rule 32 (one sentence per section) · rule 35 (the catalogue writes
//           the words) · rule 36 (compose the kit — `UsageBars` was ADDED to it)
// CR-085:   s50 (group H) — **ONE SERVICE AT A TIME.** Product Owner, verbatim:
//           *"on this screen usage you will ahve to give drop down for utility
//           services"*. The screen stacked a chart per measured service and
//           then repeated every service in a row of cards; on the demo account
//           that is 800 kWh and 8 kgal on one page. `ServicePicker` chooses,
//           and every figure under it belongs to the chosen service.
//           `08-screen-layouts.md` CWP-033 amended the same day.
// Tests:    src/portal/usage/Usage.dom.test.tsx
// Impacts:  src/portal/api/portalClient.ts `getAccountUsage` ·
//           src/portal/components/primitives.tsx `UsageBars` · `SegmentedChoice`
// ───────────────────────────────────────────────────────
import { useEffect, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

import {
  Card,
  KVList,
  KpiRow,
  KpiTile,
  SectionTitle,
  SegmentedChoice,
  ServicePicker,
  UsageBars,
  WhereNext,
  formatQuantity,
  monthYearText,
  usePortalPath,
  type UsageBar,
} from "../components/primitives";
import { AttachedAnswerCard, TipBar } from "../components/content";
import { PortalScreen, PortalState } from "../components/states";
import { DownloadButton } from "@/components/DownloadButton";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
// ⚠ **THE PRODUCT'S ONE QUANTITY FORMATTER, REACHED DIRECTLY**
// (`BR-SHL-023`, `DEF-CWP-4168`). The server composes its figures through
// `metering/quantity_display.py`, which rounds and trims and does NOT group —
// so a KPI tile printed `8402` beside a year card printing `8,402 kWh`, the
// same kind of number written two ways on one screen. This is the same
// function `primitives.formatQuantity` and `formatDialFigure` already wrap;
// it is imported here rather than re-wrapped because the tile wants the
// NUMBER on its own (the unit is `KpiTile`'s separate prop, so the two type
// sizes cannot drift).
import { formatQuantity as groupQuantity } from "@/components/UnitCell";
import {
  getAccountUsage,
  type PortalUsage,
  type PortalUsageCostLine,
  type PortalUsageMetric,
  type PortalUsageService,
} from "../api/portalClient";

/** The CSV `US-CWP-040` TC-9 asks for.
 *
 * ⚠ **THE UNIT IS A COLUMN ON EVERY ROW, NOT A WORD IN A HEADER** — TC-9 says
 * so in as many words, and the reason is that a header travels badly: a
 * spreadsheet sorted, filtered or pasted into another one keeps its rows and
 * loses its heading, and a column of bare numbers then means whatever the
 * reader assumes.
 *
 * ⚠ **BUILT FROM WHAT IS ALREADY ON THE PAGE, AND THAT IS NOT A SHORTCUT.**
 * `BR-SHL-016`'s server-side export exists for lists the browser has not got —
 * fifty thousand rows under RLS with a money-export audit row. This is twelve
 * numbers the screen is already drawing; a round trip for them would be a
 * second answer to a question already answered (and `POST /exports` registers
 * no portal resource, so `BR-SHL-010` would forbid the control anyway).
 *
 * ⚠ **AN ABSENT MONTH IS ABSENT FROM THE FILE TOO** (`BR-MET-106`) — a `0`
 * row would say the customer used nothing that month.
 */
export function usageCsv(services: PortalUsageService[]): string {
  const rows = [["service", "month", "quantity", "unit", "estimated"]];
  for (const service of services) {
    // ⚠ **KEYED ON `measured`, NOT ON *does it happen to have a series*.**
    // Found by mutating the fixture to give a `share` service a series (law 7):
    // the SCREEN was right — it renders the *billed on* panel off `measured` —
    // and this function was not, so a sewer row would have reached the file
    // while the page said sewer is not measured. Two answers to one question
    // is the whole thing the reuse map warns about, one function apart.
    if (!service.measured) continue;
    for (const point of service.series?.points ?? []) {
      if (point.absent || point.quantity === null || !point.unit) continue;
      rows.push([
        service.code,
        point.month,
        point.quantity_display ?? point.quantity,
        point.unit,
        point.estimated ? "yes" : "no",
      ]);
    }
  }
  return rows.map((row) => row.map(csvCell).join(",")).join("\n");
}

function csvCell(value: string): string {
  return /[",\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

/** Hand the file to the browser. Kept apart from `usageCsv` so the CONTENT —
 *  which is what TC-9 is about — is a pure function a test can read without
 *  any download machinery at all. */
function downloadUsageCsv(services: PortalUsageService[]): void {
  const blob = new Blob([usageCsv(services)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "usage.csv";
  link.click();
  URL.revokeObjectURL(url);
}

/**
 * `CWP-033` — a year of usage, and **the services that are not measured saying
 * so**.
 *
 * ⚠ **THE ABSENCE IS THE FEATURE, NOT THE CHART** (`BR-CWP-073`). Of the eleven
 * services this product bills, only some produce a reading: sewer is priced as
 * a share of water and trash on the cart at the kerb. A portal that drew an
 * empty chart for either *"will be asked where the missing graph is"* — so an
 * unmeasured service gets a panel that says what it IS billed on, and **no
 * `<svg>`, no canvas and no zero series anywhere near it.**
 *
 * ⚠ **AND *NOT MEASURED* IS NOT THE SAME CLAIM AS *NOT READ YET*.** A water
 * service nobody has read has no bars and is still metered; the panel says so
 * in its own sentence rather than borrowing the unmeasured one.
 *
 * ⚠ **NOTHING ON THIS SCREEN ADDS TWO SERVICES TOGETHER** (hard rule 3).
 * Gallons and therms share a month and nothing else, so there is one chart per
 * service and no total — which is the published read's own shape, not a
 * decision taken here.
 */
export function UsageView(props: { accountId: string; today?: Date }) {
  const { t } = useTranslation();
  const path = usePortalPath();
  const [months, setMonths] = useState(12);
  /**
   * ⚠ **WHAT `Try again` ACTUALLY DOES — R-10's way out, wired to a real
   * read rather than to nothing.** `states.tsx` states the trap in its own
   * words: a required `waysOut` would have been satisfied ten times over by a
   * `Try again` bound to no handler, which is `EmptyList`'s `onCta: () =>
   * undefined` defect (`DEF-MET-4764`) — a control that looks pressable, is
   * pressable, and does nothing. Bumping this counter is in the effect's
   * dependency list, so the button re-runs the read it failed on.
   */
  const [attempt, setAttempt] = useState(0);
  /**
   * ⚠ **WHICH SERVICE THE SCREEN IS ABOUT — THE PRODUCT OWNER'S OWN REQUEST**
   * (*"on this screen usage you will ahve to give drop down for utility
   * services"*) and the drawing's first rule: *"One service at a time — a
   * customer cannot read four units on one axis."*
   *
   * ⚠ **`null` MEANS *THE ONE THE SERVER LISTED FIRST*, NOT *NONE***. Holding
   * a CODE here and resolving it against the payload on every render is what
   * survives the window changing from 12 to 24 months, an account switch, and
   * a service the customer no longer has: a `useState` seeded from the first
   * payload would keep pointing at a code that is no longer in the list, and
   * the screen would draw nothing with the picker showing a live tab.
   */
  const [chosen, setChosen] = useState<string | null>(null);
  const [data, setData] = useState<PortalUsage | null>(null);
  const [failed, setFailed] = useState(false);
  /**
   * ⚠ **THE DISMISS LASTS THE VISIT AND NOT LONGER, DELIBERATELY.** `×` is on
   * the drawing (`CWP-062`) and `BR-CWP-095` says nothing about remembering
   * one. Remembering would need a per-customer row keyed to a tip, which is a
   * schema no signed rule asks for; forgetting on the next visit is the
   * honest minimum for a tip that is seasonal anyway. Decision log
   * 2026-09-05 — recorded rather than put to the PO (hard-won law 13).
   */
  const [tipShown, setTipShown] = useState(true);

  useEffect(() => {
    let live = true;
    setData(null);
    setFailed(false);
    getAccountUsage(props.accountId, months)
      .then((answer) => {
        if (live) setData(answer);
      })
      .catch(() => {
        if (live) setFailed(true);
      });
    return () => {
      live = false;
    };
  }, [props.accountId, months, attempt]);

  /**
   * ⚠ **THE HEAD IS BUILT ONCE, ABOVE THE BRANCHES, AND RENDERS ON EVERY
   * ONE OF THEM — `DEF-CWP-4846` / `DEF-CWP-4926`, and this screen was the
   * LAST of the ten.** It had no page head of any kind: `pageHeadCensus.test`
   * carried `usage/Usage.tsx` as its one remaining `AWAITING_ANOTHER_LANE`
   * entry, and `document.querySelectorAll("h1,h2,h3,h4")` returned exactly one
   * node at both widths — the chart panel's `<h3>`. What stood where the title
   * belongs was a `SectionTitle` inside the first card, eleven pixels tall,
   * and on a failed read even that went away with the data.
   *
   * ⚠ **THE CONTROLS ARE IN THE HEAD BECAUSE THE DRAWING PUTS THEM THERE**
   * — `08-screen-layouts.md` CWP-033, verbatim: *"`PageHead` kicker **USAGE** ·
   * title *What you have used* · controls: segmented `Button(outline)` pair
   * *12 months* (selected) | *24 months* + *↓ CSV*"*. They used to sit inside
   * the first card beside a second copy of the title, which is `14-layout-audit`
   * D1's other half: where a drawn head control survived at all it drifted into
   * the body.
   *
   * ⚠ **AND THEY RIDE ONLY WHERE THERE IS SOMETHING TO ACT ON**, which is
   * `BR-CWP-093` rather than a shortcut: the window options are the payload's
   * own `windows` and the CSV is built from the rows on the page, so on a read
   * that failed both controls would be furniture over nothing — a `↓ CSV` that
   * downloads an empty file is worse than no button. The kicker, the title and
   * the `data-screen` mark are on every branch, which is what the defect is
   * about.
   */
  const head = (
    <PageHeader
      kicker={t("portal.kicker.usage")}
      title={t("portal.usage.title")}
      secondaryActions={
        data === null ? undefined : (
          <>
            <SegmentedChoice
              testId="window"
              label={t("portal.usage.windowLabel")}
              current={String(months)}
              options={data.windows.map((option) => ({
                key: String(option),
                label: t("portal.usage.window", { months: option }),
              }))}
              onChoose={(key) => setMonths(Number(key))}
            />
            <DownloadButton onDownload={() => downloadUsageCsv(data.services)} />
          </>
        )
      }
    />
  );

  if (failed) {
    return (
      <PortalScreen screen="CWP-033" head={head} className="flex flex-col gap-4">
        <PortalState
          kind="failed"
          testId="usage"
          sentence={t("portal.usage.couldNotRead")}
          /* R-10, verbatim: *"the thing they can do about it must be on that
             same screen, next to the message"*. The read is held in this
             screen's own effect, so the way out is an action here and not an
             address. */
          waysOut={[
            {
              label: t("portal.state.tryAgain"),
              tone: "primary",
              testKey: "retry",
              onClick: () => setAttempt((n) => n + 1),
            },
          ]}
        />
      </PortalScreen>
    );
  }
  if (!data) {
    return (
      <PortalScreen screen="CWP-033" head={head} className="flex flex-col gap-4">
        <PortalState kind="loading" testId="usage" sentence={t("portal.usage.reading")} />
      </PortalScreen>
    );
  }

  const unmeasured = data.services.filter((service) => !service.measured);
  // The drawing opens on a service that HAS a chart where the account has one,
  // because the screen's own question — *am I using more than I used to* — has
  // no answer on a service nobody reads.
  const opening = data.services.find((service) => service.measured) ?? data.services[0] ?? null;
  const current = data.services.find((service) => service.code === chosen) ?? opening;

  return (
    // ⚠ **A LITERAL `<div data-screen="CWP-033">` ON THE SUCCESS BRANCH, AND
    // IT IS NOT AN OVERSIGHT THAT `PortalScreen` IS NOT USED HERE.** Three
    // SOURCE scanners find a portal screen by grepping this exact string —
    // `pageHeadCensus.test.ts`, `g100_every_screen_has_a_door.py`'s
    // `SCREEN_MARK`, and `g103_holds_cannot_rot.py`'s `DECLARES_SCREEN` — and
    // none of them knows about a `screen=` PROP. Replacing this tag with
    // `<PortalScreen screen="CWP-033">` renders an identical DOM and makes all
    // three quietly stop seeing this file: G100 would lose the only door in the
    // product to `CWP-034` and `CWP-037` and report ZERO over a scope it had
    // silently excluded, which is hard-won law 7's own named shape. Caught
    // because the census went GREEN when its negative assertion should have
    // gone red. `bills/BillDetail.tsx` is the shape and does the same thing.
    <div data-screen="CWP-033" className="flex flex-col gap-4">
      {head}
      {/* `CWP-062` — the tip where it lands. `BR-CWP-095`: one tip, on and in
          season; `null` closes the slot up and nobody can tell it was there.

          ⚠ **THIS WAS A PRIVATE COPY AND IT IS THE KIT'S NOW**
          (`DEF-CWP-3985`, B14 rule 36). The screen drew its own `div` with a
          brand left rule — no `TIP` kicker, no dismiss — three directories
          from `content.tsx`, which exports the component the drawing names and
          which NO portal screen imported. Two tip bars in one product, and
          neither was the drawn one.

          ⚠ **AND THE PRIVATE COPY RENDERED NOTHING** (`DEF-CWP-3998`): it read
          `data.tip.body ?? data.tip.title` and the server sends `text`. A
          clerk who switched a tip on published an empty box. */}
      {tipShown ? (
        <TipBar
          tip={data.tip}
          kicker={t("portal.tip.kicker")}
          dismissLabel={t("portal.tip.dismiss")}
          onDismiss={() => setTipShown(false)}
        />
      ) : null}

      <Card testId="usage">
        {/* ⚠ **THE `SectionTitle` THAT USED TO OPEN THIS CARD IS GONE, AND
            SO IS THE CONTROL ROW BESIDE IT** (`DEF-CWP-4846`, `CR-085` step 2).
            It said *What you have used* — the page title, drawn at eleven
            pixels inside a card, on a screen whose `<h1>` did not exist. Two
            titles saying the same thing is the hand-rolled head B14 rule 2 and
            `pageHeadCensus.test.ts`'s last case both exist to stop; the head
            above owns the words now and the drawing's two controls with them. */}
        {data.services.length === 0 ? (
          <p className="mt-2 text-body text-neutral-600" data-usage-empty="">
            {t("portal.usage.noServices")}
          </p>
        ) : null}

        {/* ⚠ **ONE SERVICE AT A TIME, AND THE PICKER IS THE WHOLE POINT OF THE
            SCREEN'S REDRAW** (`CR-085` s50; Product Owner, *"on this screen
            usage you will ahve to give drop down for utility services"*). Ana's
            account is the case that proves it: **800 kWh and 8 kgal**, drawn one
            under the other, with a `MONTHLY AVERAGE` tile that named neither.
            The list is the ACCOUNT'S OWN services — measured and unmeasured
            alike, exactly as the drawing's three tabs show — and it draws
            nothing at all where there is only one (a chooser with one option is
            furniture). */}
        {/* ⚠ **NO `services.length > 1` GUARD HERE, DELIBERATELY.** The rule
            *a chooser with one option is furniture* belongs to the component
            and is written there once; repeating it at the call site would be
            two implementations of one decision, which is how `TwoCol` and
            `Panel` drifted (`DEF-CWP-3655`) — and a test mutating either half
            alone would stay green. `ServicePicker` returns `null` on a
            one-service account. */}
        <div className="mt-3">
          <ServicePicker
            testId="service"
            label={t("portal.usage.serviceLabel")}
            services={data.services.map((service) => ({
              code: service.code,
              name: service.name,
            }))}
            current={current?.code ?? ""}
            onChoose={setChosen}
          />
        </div>

        {/* ⚠ **THE ONLY WAY INTO `CWP-034` AND `CWP-037`, AND THAT IS WHY THEY
            ARE HERE** (hard-won law 2, G13): a screen with a route and no link
            is a screen nobody reaches, which is dead UI wearing a URL. Both
            layouts draw `back ← USAGE`, so this is the page they come from. */}
        {/* ⚠ **THIS ROW WAS HAND-DRAWN HERE AND IT IS THE KIT'S NOW**
            (B14 rule 36, `DEF-CWP-3954`). It was the first door row in the
            portal and it had its own margin, its own gap and its own mark;
            six more screens then needed the same block, which is six more
            chances to draw it differently. `WhereNext` is that one decision.
            `data-usage-links` is kept as well so nothing that already reads
            this screen has to change. */}
        <div data-usage-links="">
          <WhereNext
            mark="usage"
            doors={[
              { key: "readings", label: t("portal.usage.seeReadings"), to: "/readings" },
              { key: "equipment", label: t("portal.usage.seeEquipment"), to: "/equipment" },
            ]}
          />
        </div>
      </Card>

      {/* ⚠ **EVERY FIGURE BELOW BELONGS TO THE SERVICE IN THE PICKER, AND
          THAT IS THE DRAWING'S NAMED FAILURE TO AVOID** — verbatim: *"Showing
          'Average water month 15 kgal' while Electric is selected is the defect
          that reached a live screen this week; the fix is that no summary is
          rendered outside the block that owns its data."* This screen HAD that
          fault: `MONTHLY AVERAGE 800 kWh` sat above a water chart with nothing
          saying which service it counted. Everything under here now takes one
          service as its only argument. */}
      {current === null ? null : current.measured ? (
        <>
          <UsageFigures service={current} nextReading={data.next_reading} />
          <ServiceChart
            service={current}
            months={months}
            shareNames={shareNamesOf(current, unmeasured)}
          />
          {/* ⚠ **`CPB-08` — *why does it cost this*, on the screen that shows
              what was used.** The blueprint's gap was five words: *"Nothing
              joins a usage month to the bill line it produced."* Every figure
              in this panel is the BILL'S OWN — nothing here multiplies, which
              is the specification's own requirement (*"not a re-calculation"*)
              and what keeps this off B4's ❄️ FROZEN ground. */}
          <MonthCost service={current} />
          <YearComparison service={current} />
        </>
      ) : (
        /* ⚠ **33.6 — AN UNMEASURED SERVICE IS A PANEL SAYING WHAT IT IS BILLED
           ON, AND NO CHART** (`BR-CWP-073`). It is a tab in the picker like any
           other — the drawing's desktop row draws `Sewer` beside `Electric` and
           `Water` — and choosing it draws no `<svg>`, no canvas and no zero
           series. */
        <UnmeasuredService service={current} />
      )}

      {/* ⚠ **`DEF-CWP-3945` — THE ANSWER A CLERK PINNED TO THIS SCREEN, AND
          IT HAS BEEN PUBLISHING INTO NOTHING SINCE THE FEATURE SHIPPED.**
          `published_content.ALSO_SHOW_SCREENS` is `("bill", "usage",
          "overdue")`; `bills/BillDetail.tsx` and `arrears/Overdue.tsx` each
          draw theirs and this screen had no field, no read and no card — so a
          clerk who ticked *also show this on the Usage screen* got a
          confirmation and no customer ever saw the answer.

          ⚠ **AT THE FOOT AND NOT AT THE TOP.** The drawing's own rule for
          this screen is *"Weight follows importance — the chart outranks the
          summary tiles above it"*; an answer card above the chart would
          outrank both. `CWP-028` puts its card under the charges panel for the
          same reason.

          ⚠ **ABSENT, NEVER EMPTY** (`BR-CWP-093`) — `null` is the ordinary
          answer and closes the slot up entirely. */}
      {data.attached_answer ? (
        <AttachedAnswerCard
          question={data.attached_answer.question}
          body={data.attached_answer.body}
          readMoreLabel={t("portal.attachedAnswer.readMore")}
          href={path(`/help/${encodeURIComponent(data.attached_answer.slug)}`)}
          whyLabel={t("portal.attachedAnswer.why")}
        />
      ) : null}
    </div>
  );
}

/**
 * The services billed as a SHARE of this one — `BR-RAT-015`'s sewer-on-water,
 * and the source of the chart head's brand note.
 *
 * ⚠ **READ FROM `billed_on`, NEVER HARDCODED AS *sewer follows water***. The
 * shape the server publishes already answers it, and a utility that prices
 * something else as a share of water would otherwise get a note naming the
 * wrong service — the `DEF-CWP-3765` lesson (*read the column; a shape that
 * implies it is a rule in disguise, and rules move*).
 */
export function shareNamesOf(
  service: PortalUsageService,
  unmeasured: PortalUsageService[],
): string[] {
  return unmeasured
    .filter((one) => one.billed_on?.kind === "share" && one.billed_on.of === service.code)
    .map((one) => one.name);
}

/**
 * `33.1` — the drawing's row of figures, **all four about the ONE service in
 * the picker**: *This month* · *Lowest · Feb* · *Average* · *Highest · Jul
 * 2025*.
 *
 * ⚠ **EVERY TILE NAMES ITS SERVICE OR SITS UNDER A PICKER THAT DOES.** The
 * drawing's first tile reads `ELECTRIC · THIS PERIOD`, not `THIS PERIOD`, and
 * this file used to draw a bare `MONTHLY AVERAGE` above two charts in two
 * different units — the drawing's own *failure to avoid*, on screen.
 *
 * ⚠ **THE LOWEST AND THE HIGHEST MONTH CARRY THE MONTH THEY HAPPENED IN, AND
 * THE SERVER HAS ALWAYS SERVED IT** (`metrics.low.month`, `metrics.peak.month`
 * — `2026-06` on the wire). They used to be a footnote under the axis reading
 * *Lowest 800 kWh* with no month at all, which answers half the question a
 * customer came with. The month is written by `Intl` through the kit's
 * `monthYearText` and never by a catalogue list of twelve names (B14 rule 35).
 *
 * ⚠ **THE AVERAGE TILE IS A MONTHLY AVERAGE AND THE DRAWING SAYS *DAILY
 * AVERAGE*.** That divergence is deliberate and filed (`DEF-CWP-4001`): the
 * published read carries `avg_per_month` and no daily figure, months are not
 * the same length, and `BR-MET-106` makes absent months absent rather than
 * zero — so dividing by thirty here would put a number on screen that the
 * clerk's own Account view cannot produce. The label says what the figure IS.
 *
 * ⚠ **A TILE WITH NOTHING BEHIND IT IS ABSENT, NOT DASHED** (`BR-CWP-093`).
 * Most days have no reading window open, and an empty row draws nothing at
 * all.
 */
/**
 * A server-composed figure, **grouped the way every other number on these two
 * screens is grouped** — `DEF-CWP-4168`.
 *
 * ⚠ **IT CHANGES NO VALUE AND THAT IS THE POINT.** The server already
 * rounded and trimmed this string (`metering/quantity_display.quantity_text`:
 * at most two decimals, half-up, trailing zeros gone) and `UnitCell`'s
 * `formatQuantity` applies the SAME rule before it groups, so the digits that
 * come out are the digits that went in. What was wrong was that one screen
 * printed `8,402 kWh` in its year card — client-grouped — beside `8402` in a
 * KPI tile, which is the same kind of number written two ways one inch apart.
 *
 * `null` in, `null` out: `KpiTile` is only built where the figure exists.
 */
function grouped(display: string | null): string | null {
  return display === null ? null : groupQuantity(display);
}

function UsageFigures(props: {
  service: PortalUsageService;
  nextReading: PortalUsage["next_reading"];
}) {
  const { t, i18n } = useTranslation();
  const service = props.service;
  const series = service.series;
  const unit = series?.unit ?? "";
  const drawn = (series?.points ?? []).filter(
    (point) => !point.absent && point.quantity !== null,
  );
  const latest = drawn.length > 0 ? drawn[drawn.length - 1] : null;
  const average = series?.metrics.avg_per_month ?? null;
  const low = series?.metrics.low ?? null;
  const peak = series?.metrics.peak ?? null;

  const tiles: ReactNode[] = [];
  if (latest) {
    tiles.push(
      <KpiTile
        key="period"
        lead
        testKey={`period-${service.code}`}
        label={`${service.name} · ${t("portal.usage.thisPeriod")}`}
        value={grouped(latest.quantity_display)}
        unit={unit}
        /* ⚠ **`CPB-07` LIVES HERE — *"under the big number"*, which is the
           blueprint's own words for this slot.** It used to carry the
           YEAR-on-year percentage, which is a total against a total and now
           has one home of its own in `YearComparison` below; a figure with two
           homes is how two answers to one question get built (`DEF-CWP-3655`).
           `null` closes the line up entirely (`BR-CWP-093`) — a dash under a
           big number reads as a figure we lost. */
        sub={periodChangeText(series?.metrics.vs_last_month, service.code, t, i18n.language)}
      />,
    );
  }
  if (low && low.absent_reason === null && low.display !== null) {
    tiles.push(
      <KpiTile
        key="low"
        testKey={`lowest-${service.code}`}
        label={
          low.month
            ? t("portal.usage.lowestIn", { month: monthYearText(low.month, i18n.language) })
            : t("portal.usage.lowestLabel")
        }
        value={grouped(low.display)}
        unit={low.unit ?? unit}
      />,
    );
  }
  if (average && average.absent_reason === null && average.display !== null) {
    tiles.push(
      <KpiTile
        key="average"
        testKey={`average-${service.code}`}
        label={t("portal.usage.average")}
        value={grouped(average.display)}
        unit={average.unit ?? unit}
        sub={t("portal.usage.averageNote")}
      />,
    );
  }
  if (peak && peak.absent_reason === null && peak.display !== null) {
    tiles.push(
      <KpiTile
        key="high"
        testKey={`highest-${service.code}`}
        label={
          peak.month
            ? t("portal.usage.highestIn", { month: monthYearText(peak.month, i18n.language) })
            : t("portal.usage.highestLabel")
        }
        value={grouped(peak.display)}
        unit={peak.unit ?? unit}
      />,
    );
  }
  if (props.nextReading) {
    /* ⚠ **`DEF-CWP-4169` — THE THIRD TILE THE WIREFRAME DRAWS, AND IT IS THE
       FIFTH NOW.** That row read *"the third tile, NEXT READING DUE, is not
       built"*; it is built, it renders, and its arrival is what made five
       tiles the ordinary case and `DEF-CWP-4847` a live defect rather than a
       theoretical one. Two rows, one cause, and they close together. */
    tiles.push(
      <KpiTile
        key="next"
        testKey="next-reading"
        label={t("portal.usage.nextReadingLabel")}
        /* ⚠ **`DEF-CWP-4685` — THIS PRINTED `2026-09-14–2026-09-14` UNTIL
           TODAY.** The tile could never render at all (`DEF-MET-4684`), so
           nobody had ever seen its copy; the moment it went live it put two ISO
           dates in the KPI number font, wrapping over three lines, and repeated
           the same date on the demo's own one-day cycle. Written by `Intl` in
           the reader's own language now, and collapsed to one date when the
           window is a single day — a dash between two identical dates is not a
           range, it is a rendering bug wearing one. */
        value={readWindowText(
          props.nextReading.from,
          props.nextReading.to,
          i18n.language,
          t,
        )}
        sub={t("portal.usage.nextReadingNote")}
      />,
    );
  }
  if (tiles.length === 0) return null;
  return (
    <div data-next-reading={props.nextReading ? "" : undefined}>
      <KpiRow columns={kpiColumns(tiles.length)}>{tiles}</KpiRow>
    </div>
  );
}

/**
 * How many columns this many tiles want — **`DEF-CWP-4847`**.
 *
 * ⚠ **THE OLD EXPRESSION WAS `tiles.length > 3 ? 4 : 3`, WHICH IS RIGHT
 * FOR THREE AND FOUR AND WRONG FOR FIVE.** Measured at 1280 on 2026-09-11,
 * `grid-template-columns` came back `253px 253px 253px 253px` with five tiles
 * rendered, so `NEXT READING DUE` sat alone on a second row with three
 * quarters of it empty — and at 253px its own value wrapped over two lines
 * (`Sep 30 –` / `Oct 2`) in the metric font. **Five is the ORDINARY case now**,
 * not an edge: the fifth tile only started rendering when `DEF-MET-4684` gave
 * the read window a source that could answer.
 *
 * ⚠ **THE RULE IS *NO ROW ENDS IN ONE ORPHAN*, NOT *FIVE IS SPECIAL*.**
 * `KpiRow` offers three columns and four, and anything past the count wraps
 * rather than being dropped (a tile is a fact). A last row holding exactly one
 * tile reads as a rendering fault; a last row holding two reads as a list that
 * ran out. So four is the default and three is chosen wherever four would
 * leave a remainder of one.
 *
 * ⚠ **AND IT IS A FUNCTION RATHER THAN AN EXPRESSION AT THE CALL SITE SO
 * THAT IT CAN BE TESTED WITHOUT A BROWSER.** jsdom applies no CSS, so a grid
 * that wraps and a grid that does not are the same DOM: the screen's own
 * 1,141-line suite asserts every tile's label and value and could never have
 * seen this. The count-to-columns decision is arithmetic and arithmetic is
 * assertable; the rendered `grid-template-columns` is the walkthrough's job.
 */
export function kpiColumns(count: number): 3 | 4 {
  if (count <= 3) return 3;
  return count % 4 === 1 ? 3 : 4;
}


/**
 * `Sep 14` or `Sep 14 – Sep 18`, in the reader's own language (`DEF-CWP-4685`).
 *
 * ⚠ **`Intl`, NEVER A CATALOGUE LIST OF TWELVE MONTH NAMES** (B14 rule 35) —
 * the same rule the Lowest and Highest tiles already follow through
 * `monthYearText`. The SEPARATOR is a catalogue key, because a range is
 * punctuated differently in different languages.
 */
function readWindowText(from: string, to: string, language: string, t: TFunction): string {
  const day = (iso: string) =>
    new Intl.DateTimeFormat(language, {
      month: "short",
      day: "numeric",
      timeZone: "UTC",
    }).format(new Date(`${iso}T00:00:00Z`));
  return from === to ? day(from) : t("portal.usage.readWindow", { from: day(from), to: day(to) });
}

/**
 * The drawing's `ComparisonRows` — **against last year, and nothing this
 * screen worked out for itself.**
 *
 * ⚠ **WHAT IS DRAWN IS WHAT IS SERVED, AND THE GAP IS REPORTED RATHER THAN
 * FILLED IN.** The drawing asks for two rows — *Against July 2026 −42 kWh* and
 * *Against August 2025 +86 kWh*. The published read carries a year-on-year
 * PERCENT over twelve-month totals (`metrics.yoy`) and the two yearly totals
 * it is computed from; it carries **no month-against-month difference and no
 * same-month-last-year figure at all**. Subtracting two points on this screen
 * would put a number in front of a customer that no clerk screen and no bill
 * can reproduce, and CLAUDE.md's rule on browser arithmetic is not a style
 * preference — so those two rows are absent, and the absence is on the record
 * as a gap in the read.
 *
 * ⚠ **NO PRIOR YEAR IS A SENTENCE AND NEVER A BLANK ROW** — the drawing's own
 * state. Ana's own account is in it (`absent_reason: "no_prior_reads"`), so
 * this is the branch that actually ships today.
 *
 * ⚠ **THE TWO TOTALS ARE SERVED, NOT SUMMED HERE** — `yoy.this_year_total` and
 * `yoy.prior_year_total` have been on `monthly_usage_reads` since `CR-030` W3.
 * Adding the twelve points up on screen would be a second arithmetic for a
 * figure the read already answers, and it would be WRONG: `BR-MET-106` makes
 * an unread month absent rather than zero, so a screen-side total silently
 * understates a year with a gap in it.
 */
function YearComparison(props: { service: PortalUsageService }) {
  const { t } = useTranslation();
  const series = props.service.series;
  // A window whose months disagree about their unit has no comparable figure
  // at all (hard rule 3) — the chart says so in its own sentence and this
  // block has nothing truthful to add.
  if (series === null || series.unit_absence) return null;
  const yoy = series.metrics.yoy;
  const unit = series.unit;
  const thisYear = formatQuantity(yoy.this_year_total ?? null, unit);
  const lastYear = formatQuantity(yoy.prior_year_total ?? null, unit);
  const rows = [
    ...(thisYear ? [{ key: "this-year", label: t("portal.usage.thisYear"), value: thisYear }] : []),
    ...(lastYear ? [{ key: "last-year", label: t("portal.usage.lastYear"), value: lastYear }] : []),
  ];
  /* ⚠ **`CPB-06` IS THE HEADLINE OF THIS CARD AND THE TOTALS ARE THE
     FOOTNOTE.** The blueprint asks for *"800 kWh · 86 kWh more than August
     2025"* **rather than** the sentence saying there is nothing to compare
     with — and that sentence was this card's whole content on any account
     without two full years. An August against an August is the comparison a
     person actually arrives with; the two twelve-month totals answer a
     different and broader question and stay underneath it. */
  const sameMonth = series.metrics.same_month_last_year;
  // `SameMonthLine` draws something for every reason EXCEPT `no_current_reads`
  // (which has no month to name). The two are read from ONE expression so the
  // card and the line cannot disagree about whether anything was said.
  const sameMonthSpoke =
    sameMonth !== undefined &&
    (sameMonth.absent_reason === null ||
      sameMonth.absent_reason === "no_same_month_last_year") &&
    Boolean(sameMonth.month ?? sameMonth.against_month);
  /* ⚠ **THE YEAR-ON-YEAR PERCENTAGE MOVED HERE FROM UNDER THE BIG NUMBER, AND
     IT DID NOT LEAVE THE SCREEN.** `CPB-07` claims the sub-line under the
     latest figure — *"5% less than July"*, the blueprint's own placement — and
     a tile carrying two comparison sentences is B14 rule 32's *one sentence
     per section* broken by addition. This card is titled *Against last year*,
     which is exactly what `yoy` measures (twelve months against the twelve
     before them), so the figure is home rather than displaced. `Usage.dom.test.tsx`
     TC-1 asserts it is still on the page. */
  const yoyNote =
    yoy && yoy.absent_reason === null && yoy.display !== null
      ? t("portal.usage.vsLastYear", { percent: yoy.display })
      : null;
  return (
    <Card testId={`usage-year-${props.service.code}`}>
      <SectionTitle>{t("portal.usage.againstLastYear")}</SectionTitle>
      <SameMonthLine change={sameMonth} code={props.service.code} />
      {yoyNote ? (
        <p className="m-0 mt-2 text-base text-neutral-600" data-yoy-note={props.service.code}>
          {yoyNote}
        </p>
      ) : null}
      {rows.length === 2 ? (
        <KVList rows={rows} />
      ) : sameMonthSpoke ? null : (
        /* ⚠ **ONLY WHEN THE SAME-MONTH LINE SAID NOTHING AT ALL** (B14 rule
           32, one sentence per section). Found in a BROWSER and by nothing
           else: the first version of this guard asked whether the comparison
           had ANSWERED, so an account whose August 2025 is missing printed
           *"No Aug 2025 to compare with."* and then, underneath it, *"We do
           not have a year to compare with yet."* — two refusals for one
           absence, the second vaguer than the first. Every DOM test passed,
           because each asserted its own line and neither asked what sat
           beside it. */
        <p className="m-0 mt-2 text-body text-neutral-600" data-no-prior-year={props.service.code}>
          {t("portal.usage.noPriorYear")}
        </p>
      )}
    </Card>
  );
}


/**
 * `CPB-07` — *"5% less than July"*, in the reader's own language.
 *
 * ⚠ **THE MONTH IS THE ONE THE SERVER ACTUALLY COMPARED WITH, NOT *last
 * month*.** `BR-MET-106` makes an unread month ABSENT rather than `0`, so
 * `month_on_month` walks back to the nearest month that HAS a figure and
 * reports which — and a screen printing a bare *"20% less than last month"*
 * over that answer would make a false claim about a month nobody walked.
 *
 * ⚠ **`direction` PICKS THE KEY AND THE CATALOGUE WRITES THE SENTENCE**
 * (B14 rule 35). `same` is its own key rather than a `0.00%` with a word in
 * front, because *"0.00% more than July"* is not a sentence anybody says.
 *
 * ⚠ **NOTHING TO SAY DRAWS NOTHING AT ALL** (`BR-CWP-093`) — no dash, no
 * empty line, no reserved height.
 */
function periodChangeText(
  change: PortalUsageMetric | undefined,
  code: string,
  t: TFunction,
  language: string,
): ReactNode {
  /* ⚠ **A FUNCTION AND NOT A COMPONENT, BECAUSE THE CALLER NEEDS THE `null`
     ITSELF** (`BR-CWP-093`, and `Usage.dom.test.tsx` TC-6 caught this the
     first time it was written the other way). `KpiTile` draws its sub-line
     wrapper when `sub` is truthy — and a `<PeriodChangeText/>` ELEMENT that
     renders nothing is perfectly truthy, so the tile grew an EMPTY `<p>` on
     every account with no earlier month. A component cannot tell its parent
     "there is nothing here"; a function returning `null` can. */
  if (!change || change.absent_reason !== null || !change.against_month) return null;
  const month = monthYearText(change.against_month, language);
  if (change.direction === "same") {
    return <span data-vs-last-month={code}>{t("portal.usage.sameAsMonth", { month })}</span>;
  }
  // A percentage with no figure behind it is not a comparison; the difference
  // line in `SameMonthLine` is the one that survives an unanswerable division.
  if (change.display === null || change.direction == null) return null;
  return (
    <span data-vs-last-month={code}>
      {t(
        change.direction === "more"
          ? "portal.usage.percentMoreThan"
          : "portal.usage.percentLessThan",
        // The sign is carried by the WORD, so the number is printed bare —
        // *"-5.00% less"* would say the opposite twice.
        { percent: change.display.replace("-", ""), month },
      )}
    </span>
  );
}

/**
 * `CPB-06` — *"86 kWh more than August 2025"*, and the absence that NAMES the
 * month it wanted.
 *
 * ⚠ **THE UNIT IS THE WHOLE JOB** (CLAUDE.md hard rule 3, and wave H's own
 * finding: a *"Monthly average 800"* that never said 800 of what, between an
 * electricity chart in kWh and a water chart in thousands of gallons). The
 * difference and its unit are read as a PAIR and neither is drawn without the
 * other — so the failure mode is a missing line rather than a naked number.
 *
 * ⚠ **THE ABSENCE NAMES THE MONTH.** *"No August 2025 to compare with"* tells a
 * customer exactly what we are missing; the blanket *"We do not have a year to
 * compare with yet"* it replaces told them nothing they could act on. B14 rule
 * 33 caps a refusal at five or six words and this is five.
 */
function SameMonthLine(props: { change: PortalUsageMetric | undefined; code: string }): ReactNode {
  const { t, i18n } = useTranslation();
  const change = props.change;
  if (!change) return null;
  if (change.absent_reason !== null) {
    // `no_current_reads` has no month to name and the card's own empty state
    // covers it; only a MISSING same-month can name what it wanted.
    const wanted = change.month;
    if (change.absent_reason !== "no_same_month_last_year" || !wanted) return null;
    const wantedLastYear = `${Number(wanted.slice(0, 4)) - 1}-${wanted.slice(5, 7)}`;
    return (
      <p className="m-0 mt-2 text-body text-neutral-600" data-no-same-month={props.code}>
        {t("portal.usage.noSameMonth", {
          month: monthYearText(wantedLastYear, i18n.language),
        })}
      </p>
    );
  }
  if (!change.against_month) return null;
  const month = monthYearText(change.against_month, i18n.language);
  if (change.direction === "same") {
    return (
      <p className="m-0 mt-2 text-body text-neutral-900" data-same-month={props.code}>
        {t("portal.usage.sameAsMonth", { month })}
      </p>
    );
  }
  // ⚠ **BOTH HALVES OR NEITHER** — hard rule 3. A difference without its unit
  // is a number under a heading that names one of eleven services.
  if (change.difference_display == null || !change.unit || !change.direction) return null;
  return (
    <p className="m-0 mt-2 text-body text-neutral-900" data-same-month={props.code}>
      {t(
        change.direction === "more"
          ? "portal.usage.quantityMoreThan"
          : "portal.usage.quantityLessThan",
        {
          // The word carries the sign, so the number is printed bare.
          quantity: change.difference_display.replace("-", ""),
          unit: change.unit,
          month,
        },
      )}
    </p>
  );
}

/**
 * `33.2` + `33.3` — the drawing's `ChartPanel`: a `Panel` wrapped round
 * `UsageBars`, **not one piece but two** (`14-layout-audit.md` §4).
 *
 * ⚠ **THE CHART USED TO SIT LOOSE INSIDE A CARD WITH THREE FIGURES ABOVE IT.**
 * The figures are the `KpiRow` now and the chart has its own panel with a
 * head, which is what gives the brand note somewhere to be.
 *
 * ⚠ **THE BRAND NOTE IS DATA, NOT A SENTENCE ABOUT SEWERS.** The drawing reads
 * *Sewer is billed on this figure*; it is composed from whichever of the
 * account's own services declares `billed_on.kind === "share"` of THIS one, so
 * a utility that prices something else that way gets its own word (B14 rule 35
 * writes the frame, the tenant writes the name). No share, no note.
 */
function ServiceChart(props: {
  service: PortalUsageService;
  months: number;
  shareNames: string[];
}) {
  const { t } = useTranslation();
  const { service } = props;
  const series = service.series;
  const title = t("portal.usage.chartTitle", {
    service: service.name,
    unit: series?.unit ?? "",
  });

  if (series === null || series.points.length === 0) {
    // ⚠ **A DIFFERENT SENTENCE FROM THE UNMEASURED ONE.** This service IS
    // metered; nobody has read it yet, and saying *not measured* here would be
    // a false claim about the customer's own meter.
    return (
      <Panel as="section" title={service.name} data-testid={`usage-${service.code}`}>
        <p className="text-body text-neutral-600" data-not-read={service.code}>
          {t("portal.usage.noReadingsYet")}
        </p>
      </Panel>
    );
  }

  const unit = series.unit ?? "";
  const drawn = series.points.filter((point) => !point.absent && point.quantity !== null);
  const bars: UsageBar[] = series.points.map((point) => ({
    month: point.month,
    quantity: point.quantity,
    quantityDisplay: point.quantity_display,
    absent: point.absent,
    estimated: point.estimated,
  }));
  const estimatedMonths = drawn.filter((point) => point.estimated).length;

  return (
    <Panel
      as="section"
      title={title}
      data-testid={`usage-${service.code}`}
      trailing={
        props.shareNames.length > 0 ? (
          <span className="text-base font-semibold text-accent-text" data-share-note={service.code}>
            {t("portal.usage.shareNote", { service: props.shareNames.join(" · ") })}
          </span>
        ) : undefined
      }
    >
      {series.unit_absence ? (
        // Hard rule 3 one level up: months that disagree about their unit have
        // no summable figure, and the screen says so rather than adding them.
        <p className="text-body text-neutral-600" data-mixed-units={service.code}>
          {t("portal.usage.mixedUnits")}
        </p>
      ) : (
        <UsageBars
          testId={service.code}
          bars={bars}
          unit={unit}
          axisLabel={t("portal.usage.axis", { unit })}
          caption={t("portal.usage.chartCaption", {
            service: service.name,
            months: props.months,
            unit,
          })}
          emptyLabel={t("portal.usage.noReadingsYet")}
          legendMeasured={t("portal.usage.legendMeasured")}
          legendHighest={t("portal.usage.legendHighest")}
          /* ⚠ **THE DRAWING'S OWN STATE, AND THE MARK WAS ALREADY THERE** —
             *"Estimated months: marked on the chart with a legend, so the
             customer knows which bars are measured."* The dashed outline has
             been drawn on an estimated bar since the chart was written and
             nothing named it, so a reader could see a difference and not know
             what it meant. The kit draws this entry only when a bar in the
             window is actually estimated. */
          legendEstimated={t("portal.usage.legendEstimated")}
          barTitle={(bar) =>
            bar.absent
              ? t("portal.usage.barAbsent", { month: bar.month })
              : t(bar.estimated ? "portal.usage.barEstimated" : "portal.usage.bar", {
                  month: bar.month,
                  value: bar.quantityDisplay ?? "",
                  unit,
                })
          }
        />
      )}

      {/* `BR-MET-106` — an estimate COUNTS and is MARKED. A customer looking at
          a month is entitled to know part of it was estimated. */}
      {estimatedMonths > 0 ? (
        <p className="text-body text-neutral-600" data-estimated-months={service.code}>
          {t("portal.usage.estimatedMonths", { count: estimatedMonths })}
        </p>
      ) : null}
    </Panel>
  );
}

/* ⚠ **`MeasuredCard` USED TO BE HERE AND ITS WHOLE ROW OF CARDS WITH IT
 * (`CR-085` s50).** The screen ended with a `CardGrid3` holding one card per
 * service — *ELECTRIC · 3 months read*, *WATER · 3 months read*, the sewer
 * panel and the trash panel — under two stacked charts that had just said the
 * same thing. With one service on screen at a time that row is the drawing's
 * named failure with a grid round it: a WATER total sitting on a page whose
 * picker says ELECTRIC. The two served year totals it carried moved into
 * `YearComparison`, which is the drawing's `ComparisonRows` and belongs to the
 * chosen service; `UnmeasuredService` below is what a `share` or `capacity`
 * service draws when the picker lands on it. */


/**
 * `CPB-08` — *"800 kWh at $0.1150 = $92.00"*, for the latest stated month.
 *
 * ⚠ **THE THREE NUMBERS ARE THE BILL'S OWN AND THE `=` IS NOT AN OPERATOR.**
 * `800 × 0.1150` is `92.00` on a flat line and stops being so the moment a
 * tier, a minimum or a proration is involved — and the customer's paper says
 * the stored figure either way. A screen that multiplied would eventually
 * contradict the bill it exists to explain, which is the one thing this panel
 * must not do. The server refuses a quantity with no unit (hard rule 3), so
 * there is no state in which this prints a bare number.
 *
 * ⚠ **NO RATE IS A DIFFERENT SENTENCE, NOT A MISSING ONE.** A flat or minimum
 * charge has an amount and no per-unit price, and *"800 kWh cost $92.00"* is
 * still the answer to *why does it cost this*.
 *
 * ⚠ **NOT BILLED YET IS THE COMMON ANSWER AND IT IS SAID OUT LOUD**
 * (`BR-CWP-093`, B14 rule 32/33). The latest stated month usually has no bill —
 * Ana's August is read and unbilled — and silence there reads as a figure the
 * screen failed to fetch. It must never print `$0.00`, which is a claim that
 * the month was free.
 */
function MonthCost(props: { service: PortalUsageService }) {
  const { t, i18n } = useTranslation();
  const series = props.service.series;
  if (series === null || series.unit_absence) return null;
  const stated = series.points.filter((point) => !point.absent && point.quantity !== null);
  if (stated.length === 0) return null;
  const cost = series.cost ?? null;
  const month = monthYearText(
    cost?.month ?? stated[stated.length - 1].month,
    i18n.language,
  );
  return (
    <Card testId={`usage-cost-${props.service.code}`}>
      <SectionTitle>{t("portal.usage.whatItCost", { month })}</SectionTitle>
      {cost === null || cost.lines.length === 0 ? (
        <p className="m-0 mt-2 text-body text-neutral-600" data-usage-not-billed={props.service.code}>
          {t("portal.usage.notBilledYet")}
        </p>
      ) : (
        <>
          {/* ⚠ **WHEN THE PANEL IS ABOUT AN EARLIER MONTH, IT SAYS SO FIRST.**
              The number at the top of this screen is the newest month READ, and
              that month is almost never billed yet — so answering about July
              under a heading a customer read as August would be the quiet kind
              of wrong. One sentence, above the figures (B14 rule 32). */}
          {cost.is_latest_month === false ? (
            <p
              className="m-0 mt-2 text-base text-neutral-600"
              data-usage-cost-earlier={props.service.code}
            >
              {t("portal.usage.latestNotBilled")}
            </p>
          ) : null}
          {/* ⚠ **ONE ROW PER LINE THE BILL WROTE, AND MOST TARIFFS ARE
              TIERED.** Ana's July electric is two rows — `500 kWh at $0.1100 =
              $55.00` and `300 kWh at $0.1350 = $40.50`. A panel drawing only
              the first would say `$55.00` about a month that cost `$95.50` and
              call it an explanation. */}
          <ul className="m-0 mt-2 flex list-none flex-col gap-1 p-0">
            {cost.lines.map((line, index) => (
              <li
                key={`${line.description ?? "line"}-${index}`}
                className="text-body text-neutral-900"
                data-usage-cost={index === 0 ? props.service.code : undefined}
                data-usage-cost-line={`${props.service.code}-${index}`}
              >
                {costLineText(line, t)}
              </li>
            ))}
          </ul>
          {/* ⚠ **THE TOTAL IS THE SERVER'S SUM OF THE LINES' OWN STORED
              AMOUNTS** — never added up here, so the panel foots against the
              printed column by construction rather than by luck. It is drawn
              only when there is more than one line: repeating a single line's
              own figure underneath it says the same thing twice (B14 rule 32). */}
          {cost.lines.length > 1 ? (
            <p
              className="m-0 mt-2 text-h3 font-bold text-neutral-900"
              data-usage-cost-total={props.service.code}
            >
              {t("portal.usage.costTotal", { amount: cost.total_display })}
            </p>
          ) : null}
          {/* The bill's NUMBER — the reference on the customer's own paper, so
              they can go and check it. Never an invoice id (B14 rule 31). */}
          <p className="m-0 mt-1 text-base text-neutral-600" data-usage-cost-bill={props.service.code}>
            {t("portal.usage.costFromBill", { bill: cost.bill_number })}
          </p>
        </>
      )}
    </Card>
  );
}


/**
 * One line of `CPB-08`'s panel — *"500 kWh at $0.1100 = $55.00"*.
 *
 * ⚠ **THE `=` IS NOT AN OPERATOR AND THE SCREEN DOES NOT COMPUTE IT.** All
 * three numbers are the bill's own stored figures; `500 × 0.1100` happens to be
 * `55.00` here and stops being so the moment a minimum or a proration is
 * involved, and the paper says the stored figure either way.
 *
 * ⚠ **A LINE WITH NO QUANTITY FALLS BACK TO ITS OWN DESCRIPTION**, which the
 * bill wrote — *"sewer usage — 40.00% of water usage charges"* is a real one on
 * this product — rather than to a bare amount under a service heading.
 *
 * ⚠ **A PERCENTAGE RATE IS NOT A DOLLAR RATE** (`DEF-CWP-3967`): `rate_basis`
 * decides which sentence, so `0.4000` never reaches a customer wearing a `$`.
 */
function costLineText(line: PortalUsageCostLine, t: TFunction): string {
  const amount = line.amount_display;
  if (line.quantity === null || line.unit === null) {
    return line.description
      ? t("portal.usage.costNamed", { what: line.description, amount })
      : t("portal.usage.costTotal", { amount });
  }
  if (line.rate === null || line.rate_basis !== "per_unit") {
    return t("portal.usage.costFlat", { quantity: line.quantity, unit: line.unit, amount });
  }
  return t("portal.usage.costAtRate", {
    quantity: line.quantity,
    unit: line.unit,
    rate: line.rate,
    amount,
  });
}

/**
 * A service that produces no reading — `BR-CWP-073`'s whole point.
 *
 * ⚠ **NO CHART, NO CANVAS, NO ZERO SERIES.** The walkthrough asserts the
 * absence of any `<svg>` inside this panel, because *"a portal that pretends
 * otherwise will be asked where the missing graph is"*.
 */
function UnmeasuredService(props: { service: PortalUsageService }) {
  const { t } = useTranslation();
  const { service } = props;
  const on = service.billed_on;

  let what: string;
  if (on?.kind === "share") {
    what = on.of
      ? t("portal.usage.billedOnShareOf", { service: t(`portal.usage.service.${on.of}`, { defaultValue: on.of }) })
      : t("portal.usage.billedOnShare");
  } else if (on?.kind === "equipment" && on.size && on.count > 1) {
    what = t("portal.usage.billedOnManyCarts", { count: on.count, size: on.size });
  } else if (on?.kind === "equipment" && on.size) {
    what = t("portal.usage.billedOnCart", { size: on.size });
  } else if (on?.kind === "equipment" && on.equipment) {
    what = t("portal.usage.billedOnEquipment", { equipment: on.equipment });
  } else {
    what = t("portal.usage.billedOnNothingRecorded");
  }

  return (
    <Card testId={`usage-${service.code}`}>
      <SectionTitle>{service.name}</SectionTitle>
      <dl className="mt-2 flex flex-col gap-1" data-unmeasured={service.code}>
        <div className="flex flex-wrap gap-2">
          <dt className="text-body font-semibold text-neutral-700">
            {t("portal.usage.billedOn")}
          </dt>
          <dd className="m-0 text-body text-neutral-900" data-billed-on={service.code}>
            {what}
          </dd>
        </div>
        <p className="m-0 text-base text-neutral-600" data-not-measured={service.code}>
          {on?.kind === "share"
            ? t("portal.usage.notSeparatelyMetered")
            : t("portal.usage.notMeasured")}
        </p>
      </dl>
    </Card>
  );
}
