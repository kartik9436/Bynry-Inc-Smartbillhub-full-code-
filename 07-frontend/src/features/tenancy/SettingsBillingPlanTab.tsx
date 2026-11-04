// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-022 (EP-TEN-05) — S107 Settings → Billing plan · Plan tab.
//           Authored 2026-08-27 for DEF-1092, BEFORE this file was written
//           (hard-won law 8: every screen needs a story).
//           Screens: S107 (A1) · SET-15 (r10's own badge, line 7927)
// Defect:   DEF-1092 — "THE ENTIRE COMMERCIAL MODEL — SUBSCRIPTION,
//           IMPLEMENTATION ORDER AND ADD-ONS — HAS NO SCREEN ANYWHERE, AND THE
//           ONE PLACE IT WOULD LIVE IS AN UNBUILT FEATURE THAT SAYS SO ON THE
//           SCREEN." This file is that place, built. Also DEF-1220 (r10 prices
//           per connection, the product prices in bands) and DEF-1222 (A1
//           prices packages in weeks, the column is months).
// Rules:    BR-TEN-002 (the account band is a COMMERCIAL tier, never enforced
//           technically — so the screen must not imply a limit) · BR-TEN-014
//           (the subscription is created `trial`, +14 days, no card) ·
//           BR-TEN-240 (the zero-month self-serve order written at signup) ·
//           BR-SHL-020 (the six A18 states, composed and never rebuilt) ·
//           BR-SHL-023 (one money formatting path; every amount with its
//           currency) · BR-SHL-025 (a control this role may not use renders
//           disabled WITH its reason — here there are no controls at all, and
//           the screen says why) · BR-SHL-034 (dates only through DateCell) ·
//           BR-SHL-044 (ONE page header — this is a TAB BODY and mints no
//           second <h1>) · B14 rules 2, 5, 18, 20, 21
// Tests:    src/features/tenancy/SettingsBillingPlanTab.test.tsx
// Impacts:  SettingsPage.tsx drops this tab's `arrivesWith` and mounts it;
//           src/styles/route-b-migrated.txt gains this file (B14 rule 21).
// ───────────────────────────────────────────────────────
// S107 — what this utility pays BYNRY for SMARTBillHub.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THE BOUNDARY THIS SCREEN EXISTS ON, BEFORE ANYTHING ELSE
// ══════════════════════════════════════════════════════════════════════════
// A1's own sentence on the S107–S109 rows: *"these invoices are what the
// tenant pays Bynry. They are a different entity from customer bills and must
// never appear in Billing, Payments, Finance, or Reports."* Everything drawn
// here comes from four PLATFORM tables — `subscription_plans`, `subscriptions`,
// `implementation_orders`, `tenant_addons` — and nothing here is reachable
// from, or reaches into, a customer's bill. The lede says so on the screen,
// because a utility's operator looking at a dollar figure is entitled to know
// whose dollar it is.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ WHAT r10 SET-15 DRAWS THAT THIS SCREEN DELIBERATELY DOES NOT — FOUR THINGS
// ══════════════════════════════════════════════════════════════════════════
// CLAUDE.md's standing instruction is that where A1 contradicts r10, r10 wins.
// **This is the case that instruction does not cover**: r10 was drawn on
// 2026-08-16 and the commercial model was ruled by the PO on 2026-08-26, ten
// days later, and seeded before both. So each divergence is STAMPED here and
// filed, which is what the rule asks for when it is the prototype that is
// stale.
//
//   1. **`$0.85 / connection` × 1,247 = `$1,059.95`** (r10 7945–7949). There is
//      no per-connection rate column in `subscription_plans` and there never
//      has been; the model the PO gave verbatim on 2026-08-26 is *"we ahve
//      $1000,$5000,$8000 plan"*, banded by account count and seeded in
//      `tenancy/0005`. Porting the panel would have put an invented price in
//      front of a paying customer. **DEF-1220.** The plan card renders the
//      CATALOGUE price and no arithmetic happens on this screen at all.
//   2. **The entitlement count** — *"1,247 active connections"*. The band is
//      real; the word is not defined in `16-glossary.md`, in `03-contracts/`
//      or anywhere else, and accounts, units, service points and meters are
//      four different figures on the same tenant. The boundary it decides is
//      $5,000 against $8,000 a month. The server serves `connections: null`
//      beside `connections_unavailable: "OQ-660"` and this screen states the
//      absence. **`OQ-660`, open — a lane may not answer it by rendering it.**
//   3. **Three Bynry invoices with a download icon each** (r10 7936–7942).
//      S108. No invoice table, no column, no route exists on the platform side.
//   4. **"card on file ending 4242"** (r10 7952). S109, and OQ-015 ruled that
//      v1 takes no card at all — so there is nothing to store and nothing
//      stores it.
//
// (3) and (4) are drawn as ONE stated absence rather than two empty panels: an
// empty invoice table reads as *you have no invoices*, which is a different and
// false sentence.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ NO CONTROL ON THIS SCREEN WRITES ANYTHING, AND THAT IS A DECISION
// ══════════════════════════════════════════════════════════════════════════
// r10 offers *Compare plans* and *Contact sales*; A1's S107 row adds *Change
// plan*, *Manage payment method* and *Cancel subscription*. **Not one of the
// five has an endpoint, a rule or a ruling.** `GET /subscription` is the only
// route on this resource and it is GET-only on purpose: a plan change would
// move money between a utility and Bynry, and the implementation order's
// editability is the still-open half of `OQ-610`. A button that posts nowhere
// is the DEF-007..010 class (hard-won law 2), and a disabled button with no
// rule behind it is worse — it implies the capability exists and is merely
// gated. So the screen carries a sentence naming who to talk to instead.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THE LAYOUT: FOUR CARDS, ONE GRID, TWO COLUMNS, ROWS THAT STRETCH
// ══════════════════════════════════════════════════════════════════════════
// The PO photographed this screen at v2.123.0 and asked for two things —
// *"correct layout of this page"* and *"also content on the screen"*. They are
// ONE defect, and the order matters: the ragged card heights were a CONTENT
// problem wearing a grid's clothes.
//
// What the photograph showed: Scale carried a price, a band and then THREE
// stacked paragraphs (the band rationale, the OQ-660 absence, the trial
// sentence) while Setting you up carried four labelled facts. Two cards of the
// same kind, drawn in two different shapes, sitting in a `items-start` grid
// that let each keep its own height. Add-ons held one sentence; Invoices held
// two. Nothing lined up, so four related cards read as four unrelated blocks.
//
// THE FIX, IN THE ORDER IT WAS MADE:
//
//   1. **The content, first.** B14 rules 32 and 33 turn Scale's three
//      paragraphs into one three-word qualifier, one THIRD `Fact` row (Trial
//      ends · <DateCell>) and one CLOSED `<details>`. Scale and Setting you up
//      are now the same shape — three label/value rows each — so their heights
//      agree because their STRUCTURE agrees, not because CSS forced them to.
//   2. **One grid, not two.** The four cards were two `<div>` grids stacked
//      with `mt-4`. Two grids are two independent row contexts with the gutter
//      between them maintained by hand: `mt-4` and `gap-4` are the same 1rem
//      today and a change to one is silently not a change to the other. One
//      grid has one set of column tracks and one gutter, by construction.
//   3. **The column count is PINNED at two** (`grid-cols-1 md:grid-cols-2`).
//      The old `repeat(auto-fit,minmax(320px,1fr))` was only ever two columns
//      BY ACCIDENT — each grid held exactly two children, so `auto-fit` could
//      not open a third track. Merge them under `auto-fit` and a wide viewport
//      puts all four in ONE row, which then stretches every card to Scale's
//      height. Pinning states the intent the old markup only stumbled into.
//   4. **Rows stretch** — `items-start` is GONE. Grid rows are independent, so
//      row 1 equalises to max(Scale, Setting you up) and row 2 to max(Add-ons,
//      Invoices); the four cards share two bottom edges instead of four.
//
// WHY NOT THE ALTERNATIVES, since equal heights are not the only answer:
//   · **A different GROUPING** (Scale full width, three beneath) was rejected
//     because the existing pairing is semantic and worth keeping: row 1 is
//     what this utility HAS and pays for, row 2 is what this screen cannot
//     show yet. Regrouping to flatten heights would trade meaning for tidiness.
//   · **A different COLUMN ORDER** — putting the two short cards side by side
//     — flattens the rows perfectly and destroys the same pairing, and it puts
//     two absences above the plan the operator opened the page to read.
//   · **Equal heights ALONE**, with the copy untouched, would have left Scale
//     tall and stretched Setting you up to match it: a taller ragged screen,
//     and the PO's second sentence unanswered.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THE COPY: B14 RULES 32 AND 33, AND WHERE THE DELETED WORDS WENT
// ══════════════════════════════════════════════════════════════════════════
// Rule 32 (PO 2026-08-31, said four times: *"too much content - desctiption is
// too much for clark to read"*) — one sentence per section; a stated absence
// is a `<details>` CLOSED by default. Rule 33 — a LABEL ≤3 words, a FACT ≤6,
// an INSTRUCTION ≤6 per sentence and at most two, and **RATIONALE is ZERO
// words on screen**: it moves to the code comment beside the string.
//
// This screen carried 32 words of lede, an 18-word band note, an 18-word
// absence, a 19-word self-serve sentence and an 18-word payment-method note.
// Every cut below is a cut to RATIONALE; not one instruction or fact was lost,
// and each reason now sits beside the string it used to be printed next to.
//
// ⚠ **WHICH ABSENCES CLOSED, AND WHICH DID NOT.** Rule 32 says a stated
// absence is a closed `<details>`; it does not say a card may be silent. So
// the test applied here is whether the absence sits BESIDE the work or IS the
// work: `plan.connectionsUnavailable` sits beside three facts in Scale and
// `paymentMethod.absent` sits beside `invoices.absent`, so both closed;
// `invoices.absent`, `addons.catalogueEmpty`, `plan.absent` and `impl.absent`
// are the whole of their card in that branch and stay VISIBLE, because
// collapsing them leaves a heading and a twisty saying nothing. Not one
// absence was deleted (G38 / DEF-445): an absence that stops being stated
// stops expiring, and this screen's four absences are still all true.
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getSubscriptionOverview } from "@/api/endpoints";
import type {
  ImplementationOrderRef,
  SubscriptionOverview,
  SubscriptionPlanRef,
  TenantAddonRow,
} from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { formatMoney } from "@/components/MoneyCell";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import { PlainTable } from "@/components/Surfaces";
import { useRegional } from "@/features/metering/meteringShared";
import { Kicker, Note } from "@/components/TextBits";

import { SettingsDenied, apiErrorText, isPermissionDenied } from "./settingsShared";

/**
 * The subscription's own status → a B13 tone.
 *
 * `trial` is INFO and not SUCCESS on purpose: a trial is a state that ENDS, and
 * a green pill beside "your trial ends in four days" tells the operator the
 * opposite of what the sentence beside it says. An unrecognised status falls to
 * `neutral` and renders its own raw value — a status we cannot name is still a
 * fact about this tenant, and hiding it would be worse than showing it plainly.
 */
const SUBSCRIPTION_TONE: Record<string, StatusTone> = {
  trial: "info",
  active: "success",
  past_due: "warning",
  suspended: "danger",
  cancelled: "muted",
};

/** The four `implementation_orders.status` values `tenancy/0021` declares. */
const ORDER_TONE: Record<string, StatusTone> = {
  draft: "neutral",
  agreed: "info",
  in_progress: "warning",
  delivered: "success",
};

/**
 * IS-8 / BR-SHL-034 — every date renders in the TENANT's zone and format, and
 * only ever through `DateCell`. The pair travels as one object so a card
 * cannot accidentally take the zone from one place and the format from another.
 */
export interface Regional {
  timeZone: string;
  dateFormat: RegionalDateFormat;
}

/** One label · one value, the shape both cards read down. */
function Fact(props: { label: string; children: React.ReactNode; note?: string }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-table-header uppercase tracking-table-header font-extrabold text-accent">
        {props.label}
      </span>
      <span className="text-body">{props.children}</span>
      {props.note !== undefined && <Note>{props.note}</Note>}
    </div>
  );
}

/**
 * The honest absence, with the id that closes it on the ELEMENT and not in the
 * sentence.
 *
 * `data-tracks` is `ArrivesWith`'s mechanism (DEF-445) and the reasoning is
 * identical: the PO ruled on 2026-08-19 that our internal ids do not belong on
 * a customer's screen, and a clerk at a 1–2 staff utility can do nothing with
 * `OQ-660`. The id is for us; the sentence is for them. G38 counts the notes
 * that cite nothing at all, so a new absence must carry one.
 */
function StatedAbsence(props: { children: React.ReactNode; tracks: string }) {
  return (
    <p
      role="note"
      data-tracks={props.tracks}
      className="m-0 text-base max-w-measure text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]"
    >
      {props.children}
    </p>
  );
}

/**
 * B14 rule 32's stated absence: a `<details>` CLOSED by default.
 *
 * Modelled on `billing/billRunShared.tsx`'s `RunGap`, which is the only other
 * place in the product that already holds this rule by construction. Three
 * things it keeps from `StatedAbsence` above and one it adds:
 *
 *   · `data-tracks` still carries the DEF or OQ that will close the absence
 *     (DEF-445), on the ELEMENT and never in the sentence (DEF-332 / B14 rule
 *     31) — a clerk at a two-person utility can do nothing with `OQ-660`.
 *   · `role="note"` still sits on the prose, so a screen reader announces the
 *     body as the aside it is.
 *   · `max-w-measure` and not `max-w-prose` — B14 rule 18's cap is 80% of the
 *     content width and `max-w-prose` is the WRONG one (G43 clause (b) holds
 *     the live count of the wrong cap at 50 and it may only fall).
 *   · the SUMMARY is a LABEL and obeys rule 33's three-word cap, because it is
 *     the only part of an absence that is read when nobody opens it.
 *
 * ⚠ No `open` prop, deliberately. Rule 32 says CLOSED by default and an
 * optional `open` is how a default becomes a suggestion — and an unpassed
 * optional prop is the G13 / hard-won-law-2 shape besides.
 */
function AbsenceDetails(props: {
  summary: string;
  children: React.ReactNode;
  tracks: string;
}) {
  return (
    <details data-tracks={props.tracks} className="m-0">
      <summary className="cursor-pointer text-base text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
        {props.summary}
      </summary>
      <p
        role="note"
        className="m-0 mt-1 text-base max-w-measure text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]"
      >
        {props.children}
      </p>
    </details>
  );
}

function Card(props: { children: React.ReactNode }) {
  return (
    <section className="border border-divider bg-surface p-4 flex flex-col gap-4">
      {props.children}
    </section>
  );
}

function CardHead(props: { title: string; pill?: React.ReactNode }) {
  return (
    <div className="flex justify-between items-baseline gap-3">
      {/* ⚠ `text-h5` / `text-h4` AND NOT `text-lg` / `text-xl`. Those two are
          TAILWIND'S OWN names and `tailwind.css` sets `--text-*: initial`, so
          they compile to NOTHING — the class lands in the DOM, tsc and eslint
          pass, and the text renders at the inherited size (DEF-974, and the
          `routeBUtilities` suite caught exactly this pair here). This project's
          scale is `--text-h1…h5` plus the small tier. */}
      <h3 className="m-0 font-heading text-h5">{props.title}</h3>
      {props.pill}
    </div>
  );
}

// ── The plan card ──────────────────────────────────────────────────────────

export function PlanCard(props: {
  plan: SubscriptionPlanRef | null;
  status: string | null;
  trialEndsAt: string | null;
  connectionsUnavailable: string | null;
  regional: Regional;
}) {
  const { t } = useTranslation();
  if (props.plan === null) {
    return (
      <Card>
        <CardHead title={t("settings.billingPlan.plan.heading")} />
        <StatedAbsence tracks="DEF-1092">{t("settings.billingPlan.plan.absent")}</StatedAbsence>
      </Card>
    );
  }
  const plan = props.plan;
  const status = props.status;
  return (
    <Card>
      <CardHead
        title={plan.name}
        pill={
          status === null ? undefined : (
            <StatusPill tone={SUBSCRIPTION_TONE[status] ?? "neutral"}>
              {t(`settings.billingPlan.status.${status}`, { defaultValue: status })}
            </StatusPill>
          )
        }
      />
      {/* BR-SHL-023 — ONE money path. `formatMoney` renders the served 4dp
          string at 2 decimals with its own CHAR(3); this screen never does
          arithmetic on money (CLAUDE.md hard rule 2), which is also why there
          is no "your monthly total" line adding the plan to its add-ons. */}
      <Fact label={t("settings.billingPlan.plan.price")}>
        <span className="tabular-nums font-extrabold text-h4">
          {formatMoney(plan.price_month, plan.currency)}
        </span>
        <span className="ml-2">{t("settings.billingPlan.plan.perMonth")}</span>
      </Fact>
      <Fact
        label={t("settings.billingPlan.plan.band")}
        // ⚠ THE NOTE IS THREE WORDS AND ITS REASON IS HERE, NOT ON SCREEN
        // (B14 rule 33). It read *"This range is what the plan was priced for.
        // Nothing stops working if you go past it."* — eighteen words over two
        // sentences, and every one of them RATIONALE, which rule 33 puts at
        // ZERO words on screen.
        // What the rationale said, kept here because it is still the reason
        // this note exists at all: BR-TEN-002 makes the account band a
        // COMMERCIAL tier that is never enforced technically — no code
        // anywhere refuses a 3,001st account on a 3,000 plan — so the one
        // thing the screen must not do is imply a limit. "Not a limit."
        // carries the whole of that, and the label above it already says
        // "Sized for" rather than "Up to".
        note={t("settings.billingPlan.plan.bandNote")}
      >
        <span className="tabular-nums">
          {t("settings.billingPlan.plan.bandValue", {
            min: plan.min_accounts.toLocaleString(),
            max: plan.max_accounts.toLocaleString(),
          })}
        </span>
      </Fact>
      {/* BR-TEN-014 — the trial ends on a date the SERVER computed.
          ⚠ A LABELLED `Fact` ROW NOW, NOT A SENTENCE (B14 rules 32 + 33). It
          was `"Your free trial ends "` + <DateCell> + `". No card is needed
          until then."`, a sentence spliced round a component — and its second
          half repeated `paymentMethod.absent` two cards down, which is rule
          32's "a row never repeats what its own control offers" pointed at a
          screen instead of a control. The date is a FACT and now reads down
          the same column as Price and Sized for; the card half lives once, in
          Invoices and payment, where a reader goes looking for it.
          This is also the layout fix: it makes Scale THREE Fact rows, the same
          shape as Setting you up, so the two cards agree in height because
          they agree in structure. See the header block. */}
      {props.trialEndsAt !== null && status === "trial" && (
        <Fact label={t("settings.billingPlan.plan.trialEnds")}>
          <DateCell
            value={props.trialEndsAt}
            timeZone={props.regional.timeZone}
            dateFormat={props.regional.dateFormat}
          />
        </Fact>
      )}
      {/* OQ-660 — r10 counts "connections" against this band. Four things in
          this product could be that number and they are four different figures
          on one tenant. Stated, never drawn — and CLOSED by default (B14 rule
          32), because it is an absence sitting BESIDE the work rather than
          being the card's only content. The sentence lost the eleven-word
          first half (*"Your live account total is not counted against this
          range here"*): the summary "Your account total" says which figure is
          meant, and a disclosure that is shut already says it is not counted. */}
      {props.connectionsUnavailable !== null && (
        <AbsenceDetails
          summary={t("settings.billingPlan.plan.connectionsSummary")}
          tracks={props.connectionsUnavailable}
        >
          {t("settings.billingPlan.plan.connectionsUnavailable")}
        </AbsenceDetails>
      )}
    </Card>
  );
}

// ── The implementation card ────────────────────────────────────────────────

export function ImplementationCard(props: {
  order: ImplementationOrderRef | null;
  regional: Regional;
}) {
  const { t } = useTranslation();
  if (props.order === null) {
    return (
      <Card>
        <CardHead title={t("settings.billingPlan.impl.heading")} />
        <StatedAbsence tracks="DEF-1092">{t("settings.billingPlan.impl.absent")}</StatedAbsence>
      </Card>
    );
  }
  const order = props.order;
  return (
    <Card>
      <CardHead
        title={t("settings.billingPlan.impl.heading")}
        pill={
          <StatusPill tone={ORDER_TONE[order.status] ?? "neutral"}>
            {t(`settings.billingPlan.implStatus.${order.status}`, { defaultValue: order.status })}
          </StatusPill>
        }
      />
      {/* The whole of DEF-1092's headline: IMPL-26-0001 reaches a human. The
          reference is monospaced because it is quoted into a support
          conversation, exactly as a bill number is. */}
      <Fact label={t("settings.billingPlan.impl.reference")}>
        <span className="font-mono tabular-nums">
          {order.order_no ?? t("settings.billingPlan.impl.noReference")}
        </span>
      </Fact>
      <Fact label={t("settings.billingPlan.impl.duration")}>
        {/* DEF-1222 — MONTHS. A1 still tabulates four packages in WEEKS and the
            PO ruled *"it is duration of implmentation project"*, in months, on
            2026-08-27. This renders the COLUMN. */}
        {order.is_self_serve
          ? t("settings.billingPlan.impl.selfServe")
          : t("settings.billingPlan.impl.durationValue", { months: order.duration_months })}
      </Fact>
      <Fact
        label={t("settings.billingPlan.impl.fee")}
        note={
          order.instalments === 2
            ? t("settings.billingPlan.impl.instalmentsTwo")
            : t("settings.billingPlan.impl.instalmentsOne")
        }
      >
        <span className="tabular-nums">{formatMoney(order.price, order.currency)}</span>
      </Fact>
      {order.delivered_on !== null && (
        <Fact label={t("settings.billingPlan.impl.delivered")}>
          <DateCell
            value={order.delivered_on}
            timeZone={props.regional.timeZone}
            dateFormat={props.regional.dateFormat}
          />
        </Fact>
      )}
    </Card>
  );
}

// ── The add-ons card ───────────────────────────────────────────────────────

export function AddonsCard(props: {
  addons: TenantAddonRow[];
  catalogueSize: number;
  regional: Regional;
}) {
  const { t } = useTranslation();
  return (
    <Card>
      <CardHead title={t("settings.billingPlan.addons.heading")} />
      {props.addons.length === 0 ? (
        // B14 rule 17 — an empty state says what is missing. TWO different
        // sentences, because `you have taken none` and `there is nothing to
        // take` are different facts and the catalogue is seeded EMPTY by
        // ruling: the PO named no add-on and gave only a placeholder price.
        <StatedAbsence tracks={props.catalogueSize === 0 ? "DEF-1092" : "OQ-610"}>
          {props.catalogueSize === 0
            ? t("settings.billingPlan.addons.catalogueEmpty")
            : t("settings.billingPlan.addons.none")}
        </StatedAbsence>
      ) : (
        <PlainTable>
          <thead>
            <tr>
              <th scope="col" className="text-left">
                {t("settings.billingPlan.addons.col.addon")}
              </th>
              <th scope="col" className="text-right">
                {t("settings.billingPlan.addons.col.price")}
              </th>
              <th scope="col" className="text-left">
                {t("settings.billingPlan.addons.col.since")}
              </th>
            </tr>
          </thead>
          <tbody>
            {props.addons.map((row) => (
              <tr key={row.code}>
                <td>
                  {row.name}
                  {row.price_source === "negotiated" && (
                    <Note as="span" className="ml-2">
                      {t("settings.billingPlan.addons.negotiated")}
                    </Note>
                  )}
                </td>
                {/* ⚠ AN UNPRICED ADD-ON RENDERS ITS REASON, NEVER ITS $1.00.
                    That dollar is the PO's placeholder (2026-08-27: *"we will
                    add price latet currently you default it to $1"*) and a
                    placeholder that looks like a considered price is worse than
                    no add-on at all — the model's own words. */}
                <td className="text-right tabular-nums">
                  {row.priced ? (
                    formatMoney(row.price_month, row.currency)
                  ) : (
                    <span className="text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
                      {t("settings.billingPlan.addons.unpriced")}
                    </span>
                  )}
                </td>
                <td>
                  {row.started_on === null ? (
                    <span aria-hidden="true">—</span>
                  ) : (
                    <DateCell
                      value={row.started_on}
                      timeZone={props.regional.timeZone}
                      dateFormat={props.regional.dateFormat}
                    />
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </PlainTable>
      )}
    </Card>
  );
}

// ── The tab ────────────────────────────────────────────────────────────────

export interface BillingPlanTabProps {
  /** ⚠ ACCEPTED AND USED, never decorative (hard-won law 2 / G13). A "View"
   *  cell on A4's `settings_lookups` row means every write control renders
   *  disabled with its reason — and this screen HAS no write control at all,
   *  so `readOnly` cannot change what is drawn. It selects the sentence at the
   *  foot instead: an Executive is told the read is all their role gets, an
   *  Admin is told the change is a conversation with Bynry. Both are true and
   *  they are different sentences. */
  readOnly: boolean;
  client?: ApiClient; // test seam — screens never build their own transport
}

export function BillingPlanTab(props: BillingPlanTabProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const query = useQuery({
    queryKey: queryKeys.subscription,
    queryFn: () => getSubscriptionOverview(client),
    staleTime: REFERENCE_STALE_MS,
  });
  // IS-8 / BR-SHL-034 — the trial end and the hand-over date are the tenant's
  // dates and render in the tenant's zone and format.
  //
  // ⚠ DEF-SHL-3964 — THE COMMENT THAT USED TO BE HERE IS WHY THIS LANE EXISTS.
  // It read: *"the seed pair is the fallback every screen in this product uses
  // while the value is not yet known, never a guess at the browser's locale."*
  // Every word of that was true and the conclusion was wrong: the value was
  // NEVER known on any other screen, so "while" was "always" and the seed pair
  // was not a fallback, it was the answer. This screen ran its own copy of the
  // shell's query under the same key — never a second request, only a second
  // fallback. The shell publishes it now and renders no screen until it has it.
  const regional: Regional = useRegional({});

  if (query.isPending) {
    return <LoadingSkeleton variant="card" />; // A18 §3
  }
  if (query.data === undefined) {
    if (isPermissionDenied(query.error)) {
      return <SettingsDenied helper={t("settings.denied.tab")} />; // A18 §6
    }
    return (
      <FailedWithRetry
        title={t("settings.billingPlan.failedTitle")}
        reason={apiErrorText(query.error, t)}
        onRetry={() => void query.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => void query.refetch()}
      />
    );
  }

  const data: SubscriptionOverview = query.data;
  return (
    <div className="settings-tab">
      <Kicker>{t("settings.billingPlan.kicker")}</Kicker>
      {/* B14 rule 18 — a description caps at 80% of the content width, which is
          what `max-w-measure` (`--desc-measure`) is, and NEVER `max-w-prose`.
          ⚠ SIX WORDS, DOWN FROM THIRTY-TWO (B14 rules 32 and 33). It read
          *"What this utility pays Bynry for SMARTBillHub. It is separate from
          the bills you send your own customers, and it never appears in
          Billing, Payments, Finance or Reports."* — two sentences, the second
          of them twenty-five words and pure RATIONALE.
          The rationale, kept here because it is A1's own boundary and the
          reason this screen exists at all: *"these invoices are what the
          tenant pays Bynry. They are a different entity from customer bills
          and must never appear in Billing, Payments, Finance, or Reports."*
          Naming those four modules on screen tells a clerk where the figure is
          NOT, which is four places they were not looking; "not your customers"
          tells them whose dollar it is, which is the one thing they came to
          know. */}
      <p className="mt-1 mb-4 text-base max-w-measure">{t("settings.billingPlan.lede")}</p>

      {/* ⚠ ONE GRID · TWO PINNED COLUMNS · NO `items-start`. The four cards
          were two grids stacked with `mt-4`, each on
          `grid-cols-[repeat(auto-fit,minmax(320px,1fr))]`, which was two
          columns only BY ACCIDENT — each grid held two children, so `auto-fit`
          had nothing to open a third track with. Merging them under `auto-fit`
          would put all four in one row above ~1,330px and then stretch every
          card to Scale's height, so the column count is now STATED rather than
          stumbled into. Dropping `items-start` lets each ROW equalise (rows
          are independent in grid, so row 1 takes max(Scale, Setting you up)
          and row 2 max(Add-ons, Invoices) — the cards share two bottom edges
          instead of four). The reading order is deliberate and is why the
          columns were not re-ordered to flatten the rows: row 1 is what this
          utility HAS, row 2 is what this screen cannot show yet. Full note in
          the header block. */}
      <div className="grid gap-4 grid-cols-1 md:grid-cols-2">
        <PlanCard
          plan={data.plan}
          status={data.subscription?.status ?? null}
          trialEndsAt={data.subscription?.trial_ends_at ?? null}
          connectionsUnavailable={data.connections_unavailable}
          regional={regional}
        />
        <ImplementationCard order={data.implementation_order} regional={regional} />
        <AddonsCard
          addons={data.addons}
          catalogueSize={data.addon_catalogue_size}
          regional={regional}
        />
        {/* S108 + S109 as ONE card. An empty invoice table would read as *you
            have no invoices*, which is false: Bynry invoices this utility and
            this product cannot show it.
            ⚠ TWO ABSENCES, AND ONLY THE SECOND CLOSES (B14 rule 32). The
            invoice sentence is the whole answer to the question that brings
            anyone to this card, so collapsing it would leave a heading and a
            twisty — the "never silent" half of the same rule. The payment
            method sits BESIDE it, so it closes. */}
        <Card>
          <CardHead title={t("settings.billingPlan.invoices.heading")} />
          <StatedAbsence tracks={data.invoices_unavailable ?? "S108"}>
            {t("settings.billingPlan.invoices.absent")}
          </StatedAbsence>
          {data.payment_method_unavailable !== null && (
            <AbsenceDetails
              summary={t("settings.billingPlan.paymentMethod.summary")}
              tracks={data.payment_method_unavailable}
            >
              {t("settings.billingPlan.paymentMethod.absent")}
            </AbsenceDetails>
          )}
        </Card>
      </div>

      {/* BR-SHL-025's spirit with no control to disable: the reason is given
          where the missing button would be, so an operator is not left hunting
          for one. */}
      <Note className="mt-4 max-w-measure">
        {props.readOnly
          ? t("settings.billingPlan.readOnlyRole")
          : t("settings.billingPlan.changeIsAConversation")}
      </Note>
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-022@EP-TEN-05 (authored 2026-08-27 for DEF-1092)
// screens: S107
// generated: 2026-08-27 by the CR-039 wave F screen lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a(no write path exists on this resource)
// exceptions: E3 r10 SET-15's per-connection rate, its entitlement count, its
//   invoice table and its card-on-file are NOT ported — DEF-1220, OQ-660, S108
//   and S109 respectively; each is stamped in the header block above · E3 A1's
//   S107 row lists Change plan / Manage payment method / Cancel subscription
//   and none has an endpoint, a rule or a ruling, so none is drawn (a disabled
//   button with no rule behind it implies a capability that does not exist)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
