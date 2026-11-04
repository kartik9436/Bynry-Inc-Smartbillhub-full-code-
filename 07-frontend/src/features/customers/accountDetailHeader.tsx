// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W3 (B18 §5.2.1) tasks 3.1 and 3.3 — the ACC-01 header
//           furniture: the service chips that carry a METER NUMBER, the
//           `Since Feb 2024` tail on the identity line, and the three metric
//           columns (`BALANCE` · `PLAN` · `LAST ACTIVITY`).
//           Screens: S21 (the account detail).
// Story:    US-CUS-008 (S21 header, status pills and action rails).
// Rules:    BR-CUS-015 (one chip per ACTIVE service agreement) ·
//           BR-CUS-029 (the account plan snapshot has NO table — `plan` is
//           still null and still carries the rule id. ⚠ THE SECOND HALF OF
//           THIS LINE READ "the unit's plan is never substituted for it"
//           UNTIL 2026-09-01 and was the defect, not the rule: DEF-2419, PO
//           *"It should be foreign key - it should take it from Unit and
//           display it there"*. The unit's plan is now SHOWN, under its own
//           `unit_plan` key — showing is not storing, and nothing is
//           substituted for the snapshot) · BR-CUS-033 (the balance due
//           date is the oldest OPEN invoice's) · BR-CUS-059 (autopay is
//           capture-only, so the pill states ENROLMENT) · BR-SHL-023 (one
//           money path) · BR-SHL-034 (one date formatter) ·
//           B14 rule 21 (Tailwind utilities — this file adds NO class to any
//           stylesheet and is registered in `styles/route-b-migrated.txt`, so
//           the real compiler owns every utility here).
// ───────────────────────────────────────────────────────
// WHY THIS IS ITS OWN FILE AND NOT MORE OF `AccountDetailPage.tsx`.
// The same reason `accountsListCells.tsx` gives, one screen along:
// `AccountDetailPage.tsx` is a pre-Route-B screen styled from `customers.css`,
// so G31 holds it to "every class this file names is declared by a stylesheet".
// B14 rule 21 says new UI is Tailwind and adds no stylesheet class. Those two
// cannot both be honoured inside one unmigrated file, so the new markup lives
// here, where `route-b-migrated.txt` hands it to `routeBUtilities.test.ts` and
// the actual Tailwind compiler.
//
// ⚠ **WHAT r10 DRAWS, MEASURED — NOT INFERRED FROM B18's TEXT.** B18 §5.2 marks
// its rows `[shot: ACC-01 detail ×10]` and those screenshots are NOT in this
// repo (DEF-631 / B18 D5). r10 IS: `SMARTBillHub.dc.html` draws the whole
// account detail, and its markup is the reference used here —
//
//     <span class="kicker">Account A-10432</span>
//       <span class="pill ok">Active</span><span class="pill warn">Autopay on</span>
//     <div …28px>Miller, Sarah</div>
//     <div …13px 65%>1408 Elm Street · Unit A · Austin, TX 78704 · Since Feb 2024</div>
//     <span class="svc-dot svc-E">ELECTRIC · M-4021</span>
//     <span class="svc-dot svc-W">WATER · M-4022</span>
//     Balance $247.30 / Due Aug 25 · Plan Residential Standard / $30.50/mo base
//     · Last activity ACH payment / Aug 6 · 07:15
//
// — so every geometry below (`.svc-dot`'s 3px/8px padding, its 8px square, the
// 26px accent balance, the 12px sub-lines) is r10's own declaration ported, not
// a new design. Where the served data cannot fill a cell the cell says so; it
// never borrows a neighbouring fact.
import { DateCell, formatDate } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { Kicker } from "@/components/TextBits";
import { MoneyCell } from "@/components/MoneyCell";
import { ACCOUNT_KIND_MASTER } from "@/api/endpoints";
import type { AccountDetail } from "@/api/endpoints";
import { serviceBadge } from "@/features/rating/ratingShared";
import type { Translator } from "@/features/tenancy/settingsShared";

import { StatusPill } from "@/components/StatusPill";

import { AwaitsCell, Dash } from "./customersShared";
// The band's NAME and the rule for reading it come from the Accounts list, so
// the two screens cannot call one band two things. The list's `AgeingCell` is
// deliberately NOT imported — see the Ageing tile's own note.
import { ageingSegmentOf } from "./accountsListCells";
import type { AccountAgeingCells } from "./accountsListCells";

/** r10's `.svc-dot`, declaration for declaration:
 *
 *      display:inline-flex; align-items:center; gap:5px
 *      padding:3px 8px; background:var(--color-surface)
 *      font-size:11px; letter-spacing:0.04em
 *      font-family:var(--font-heading); font-weight:600
 *
 * `gap-[5px]` and `py-[3px]` are r10's own odd values rather than the 4px
 * scale's nearest step: this chip is a ported drawing, and rounding it to
 * `gap-1.5`/`py-0.5` would move the one element the PO asked to be matched.
 */
const SERVICE_CHIP =
  "inline-flex items-center gap-[5px] bg-surface px-2 py-[3px] " +
  "font-heading text-xs font-semibold uppercase tracking-label";

/** The muted 65% text r10 uses for the identity line and every metric sub-line. */
const MUTED = "text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]";

/**
 * The `▪ ELECTRIC · M-4021` chips (B18 §5.2.1 row 6 — *"service chips carrying
 * the meter number are not drawn"*).
 *
 * ⚠ **THE PAIRING IS THE ASSET'S, NOT THIS SCREEN'S.** `GET /accounts/{id}`
 * serves `services` (codes) and `meters` (`{id, asset_no, qualifier}`) as two
 * INDEPENDENT lists — nothing in that payload says which meter measures which
 * service, because `account_detail_dict` drops the `type` key
 * `assets_on_unit` puts on every meter and never carried a service at all. So
 * the meter number on a chip comes from the ASSETS module's own row for that
 * meter (`GET /assets/{id}.service`), read once by the page and passed in here.
 * A service whose meter has not answered — or has not got one — renders as the
 * bare service chip, exactly what this screen drew before: the chip degrades to
 * less information, never to a guessed pairing.
 */
export interface AccountMeterChip {
  /** The asset's user-facing number (`M-4021`), never its uuid. */
  assetNo: string | null;
  /** The service code the ASSET carries, via its service point. */
  service: string | null;
}

/**
 * THE HEADER'S CHIP ROW — the five the blueprint draws beside the account name.
 *
 * `ACCOUNT A-11812 · CUSTOMER — NOT LINKED` / `Bramble Bakery` /
 * **`Active` · `Billable` · `Commercial · Small commercial` · `Regular account`**
 *
 * ⚠ **THE PRODUCT DREW ONE OF THEM AND THE PRODUCT OWNER FOUND IT BY LOOKING
 * (2026-09-13)** — *"in header we have billable, account type etc - none of
 * them are shown"*. **Every one was already on the wire**: `status_behavior_class`,
 * `account_type`, `account_subtype_name` and `kind` are all served by
 * `account_row` and have been for weeks, so this is hard-won law 2's *built is
 * not wired*, at the top of the most-opened screen in the product. Nothing
 * could have caught it: the fields type-check, the row serves them, and no
 * check in this repository reads rendered output (law 6).
 *
 * ⚠ **EVERY CHIP IS RESOLVED THROUGH A CATALOGUE AND NONE PRINTS ITS CODE**
 * (B14 rule 31 — *"no Databse ID on screen - that is a rule"*, PO 2026-08-31).
 * `billable`, `small_commercial` and `regular` are raw enums on the wire, and
 * the blueprint's own finding for this screen is that it already breaks that
 * rule once. **So a chip whose name does not resolve does not render at all.**
 * That is stricter than `accountCategoryName`, which falls back to the CODE on
 * purpose — inventing a category label is how `government` starts reading as
 * "Municipal". A chip has a third option a table cell does not: absence. One
 * fewer chip costs a clerk nothing; `small_commercial` beside `Commercial`
 * costs them the rule.
 *
 * ⚠ **THE SUB-TYPE RIDES ON THE CATEGORY CHIP AND NEVER ALONE.** The drawing
 * draws them as ONE chip, `Commercial · Small commercial`, because the sub-type
 * is a refinement and means nothing without what it refines. A tenant-defined
 * sub-type (`BR-CUS-067`) arrives with its NAME beside its code on the wire, so
 * this reads the name and never a front-end catalogue — `DEF-684`'s mistake.
 *
 * ⚠ **NO `Autopay off` CHIP, AND THE DRAWING DOES DRAW ONE.** `B18 §5.2.3`
 * rules it out in as many words — *"no `Autopay on` pill (absence is not a grey
 * pill)"* — and `CR-094-lane2-account-detail-step1.md` §2.2 already recorded
 * that collision and resolved it the same way: *"a build lane must not add it
 * back on this drawing's authority"*. Re-deciding it here would be a lane
 * overturning a ratified rule on a wireframe, which B14 rule 38 forbids for
 * construction and law 13 forbids by re-asking. **REPORTED to the Product
 * Owner with both sides quoted; the `Autopay on` chip below is unchanged.**
 */
export function AccountHeaderChips(props: {
  detail: AccountDetail;
  /** The platform category catalogue (`useAccountCategories().all`). */
  categories: readonly { code: string; name: string }[];
  t: Translator;
}) {
  const { detail, t } = props;
  // ⚠ **THE NAME OR NOTHING.** `find` rather than `accountCategoryName`,
  // because that helper's documented fallback is the CODE and a code is what
  // rule 31 forbids. While the catalogue is still loading there is simply no
  // category chip, which is a chip arriving late rather than a wrong one.
  const category = props.categories.find((row) => row.code === detail.account_type)?.name ?? null;
  const subtype = detail.account_subtype_name ?? null;
  // `customers.account.behaviourClass.*` covers all four of BR-CUS-055's
  // classes. `defaultValue: ""` is what makes a tenant-added class render as
  // NOTHING rather than as its slug.
  const behaviour =
    detail.status_behavior_class === null || detail.status_behavior_class === undefined
      ? ""
      : t(`customers.account.behaviourClass.${detail.status_behavior_class}`, {
          defaultValue: "",
        });
  const kind =
    detail.kind === ACCOUNT_KIND_MASTER || detail.kind === "regular"
      ? t(`customers.account.pill.kind.${detail.kind}`)
      : "";
  return (
    <>
      {behaviour !== "" && <StatusPill tone="neutral">{behaviour}</StatusPill>}
      {category !== null && (
        <StatusPill tone="neutral">
          {subtype === null ? category : `${category} · ${subtype}`}
        </StatusPill>
      )}
      {kind !== "" && <StatusPill tone="neutral">{kind}</StatusPill>}
    </>
  );
}

export function AccountServiceChips(props: {
  services: readonly string[];
  meters: readonly AccountMeterChip[];
  t: Translator;
}) {
  if (props.services.length === 0) {
    return <Dash>{props.t("customers.accounts.services.none")}</Dash>;
  }
  return (
    <span className="flex flex-wrap items-center gap-1.5">
      {props.services.map((code) => {
        const badge = serviceBadge(code);
        const name = props.t(`rating.service.${code}`, { defaultValue: code });
        // The FIRST meter this service is measured by. Two meters on one
        // service is a real shape (a master and its sub), and r10 draws one
        // chip per service — so the chip names one and the Meters tab lists
        // them all, rather than this cell inventing a second chip.
        const meter = props.meters.find(
          (candidate) => candidate.service === code && candidate.assetNo !== null,
        );
        return (
          <span
            key={code}
            className={SERVICE_CHIP}
            aria-label={
              meter === undefined
                ? name
                : props.t("customers.account.serviceChip.withMeter", {
                    service: name,
                    meter: meter.assetNo,
                  })
            }
          >
            {/* r10's `::before` square, as a real element: the colour is a
                token read at runtime and a pseudo-element cannot take one
                without a class per service (which is the interpolated-class
                trap `routeBUtilities.test.ts` documents). */}
            <span
              aria-hidden="true"
              className="inline-block h-2 w-2 shrink-0"
              style={{ background: `var(${badge.token})` }}
            />
            <span aria-hidden="true">{name}</span>
            {meter !== undefined && (
              <>
                {/* A separator glyph, deliberately not a catalogue key: `·` is
                    punctuation and a key holding it is byte-identical in all
                    eleven catalogues, which G15 reads (correctly) as eleven
                    values left in English. The whole chip's MEANING is in the
                    accessible name above, which IS translated. */}
                <span aria-hidden="true">·</span>
                <span aria-hidden="true" className="tabular-nums">
                  {meter.assetNo}
                </span>
              </>
            )}
          </span>
        );
      })}
    </span>
  );
}

/**
 * r10's one identity line: `1408 Elm Street · Unit A · Austin, TX 78704 ·
 * Since Feb 2024`.
 *
 * The chain is DATA joined by `·`, and the one WORD in it (`Since`) stays a
 * labelled pair — B8 forbids a translated sentence assembled either side of a
 * component, and `Since` + a `<DateCell>` is a label and its value, not a
 * sentence. The date renders MONTH-YEAR through the shared formatter's own
 * `monthYear` mode (BR-SHL-034), which is what r10 prints; there is no second
 * date path here.
 */
export function AccountIdentityChain(props: {
  detail: AccountDetail;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { detail, t } = props;
  const parts: string[] = [];
  if (detail.premise !== null && detail.premise !== "") {
    parts.push(detail.premise);
  } else if (detail.unit_label !== null && detail.unit_label !== "") {
    parts.push(detail.unit_label);
  }
  // r10's `Austin, TX 78704` — the locality of the PREMISES, when the server
  // holds one. `premise` is metering's "<address> · <unit>" string and carries
  // no city, so this adds what it does not have and repeats nothing.
  const locality = premiseLocality(detail.premise_locality ?? null);
  if (locality !== null) {
    parts.push(locality);
  }
  return (
    <span className={`flex flex-wrap items-center gap-x-2 gap-y-1 text-base ${MUTED}`}>
      {parts.length === 0 ? (
        <Dash />
      ) : (
        parts.map((part, index) => (
          <span key={`${part}-${index}`} className="flex items-center gap-x-2">
            {index > 0 && <span aria-hidden="true">·</span>}
            <span>{part}</span>
          </span>
        ))
      )}
      <span className="flex items-center gap-x-2">
        {parts.length > 0 && <span aria-hidden="true">·</span>}
        <span>{t("customers.accounts.col.since")}</span>
        {detail.opened_at !== null ? (
          <DateCell
            value={detail.opened_at}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
            monthYear
          />
        ) : (
          <Dash />
        )}
      </span>
    </span>
  );
}

/**
 * `Austin, TX 78704` off the PREMISES, or null.
 *
 * ⚠ **THIS READ MOVED ON 2026-09-04 (`BR-MET-1161`, `DEF-CUS-3653`).** It used
 * to find a `customers.addresses` row of `kind='service'` — a second, editable
 * copy of where the meter is. Under the PO's ruling of that day an address is
 * stored on `premises` and everything else walks to it, that kind is retired,
 * and this function would have returned `null` on every account forever while
 * `tsc` and every test stayed green. Hard-won law 2: a line that renders
 * nothing is not a line that is absent, it is a line nobody can see is broken.
 *
 * An account whose premises has no city recorded still has an address — the
 * premise line above already carries the street — so this returns null rather
 * than a placeholder, and the chain simply has one part fewer.
 */
export function premiseLocality(
  locality: { city: string | null; state: string | null; postal_code: string | null } | null,
): string | null {
  if (locality === null) {
    return null;
  }
  const cityState = [locality.city, locality.state]
    .filter((part) => part !== null && part !== "")
    .join(", ");
  const line = [cityState, locality.postal_code ?? ""].filter((part) => part !== "").join(" ");
  return line === "" ? null : line;
}

/**
 * r10's three metric columns, in r10's order and with r10's sub-lines.
 *
 * ⚠ **THREE, AND THE AGEING FACT IS NOT A FOURTH.** This block replaced a
 * five-row fact list (Balance · Due date · Plan · Ageing · Last activity).
 * r10's header card draws exactly three columns and no ageing state, and
 * B18 §5.1.2 puts ageing on the S17 LIST row where the clerk scans for it.
 * Adding a fourth column here would be inventing a layout — REPORTED as a
 * deliberate divergence from what this screen used to show.
 *
 * Each column is `kicker / figure / sub-line`, and each sub-line is a fact
 * about the figure above it — never about a different one.
 */
export function AccountMetricColumns(props: {
  /** ⚠ `& Partial<AccountAgeingCells>` — the server has spread `ageing_cells`
   *  into every account row since 2026-08-24 and the TYPE never declared them,
   *  so the data arrived and no screen could see it. Same widening as
   *  `OverviewTab`, from the same single owner. */
  detail: AccountDetail & Partial<AccountAgeingCells>;
  t: Translator;
  /**
   * DEF-2419 — REQUIRED, not optional. The PLAN column prints the date the
   * unit came onto its plan, and a tenant's own date format is the only
   * lawful way to render it (BR-SHL-034, one date formatter). An optional
   * prop nothing passed would render nothing and pass every test, which is
   * hard-won law 2 exactly.
   */
  timeZone: string;
  dateFormat: RegionalDateFormat;
  /* ⚠ `lastActivity` IS DELETED, AND IT WAS DEAD BEFORE IT WAS DROPPED.
     The PO's row of 2026-09-13 does not include a Last activity tile. Before
     removing it, every `.ts`/`.tsx` file in `src/` was searched for a caller:
     **NOTHING IN THE PRODUCT EVER PASSED IT.** The prop was optional, so the
     tile rendered its `Awaits` branch on every account that has ever loaded
     this screen and could not have rendered anything else — hard-won law 2's
     dead UI exactly, sitting in the header of the most-opened screen we have.
     So the ruling removes a tile that was never able to answer, and the two it
     adds (Ageing, Last bill) are both served today. */
}) {
  const { detail, t } = props;
  const ageingSegment = ageingSegmentOf(detail);
  // The SERVER's own reason when it sent one, the catalogue's when it did not —
  // the same precedence `AgeingCell` uses, so the two screens explain an absent
  // band identically.
  //
  // ⚠ AMENDED 2026-10-17 (`DEF-CUS-10181`): a null band is an ANSWER now —
  // the band reads the oldest unpaid bill as well as migrated buckets, so
  // null means nothing owed ages. Only a served reason (the bill half could
  // not be asked) still renders "Not worked out"; otherwise the tile is a dash.
  const servedWhy = detail.ageing_unavailable?.[0]?.detail;
  const ageingWhy = servedWhy !== undefined && servedWhy !== "" ? servedWhy : null;
  // WHERE the band came from, as the server says — never assumed to be the
  // migrated opening balance, which a bill-aged band is not.
  const ageingSourceLabel =
    detail.ageing_source === "bills"
      ? t("customers.account.ageingSource.bills")
      : t("customers.account.ageingSource.openingBuckets");
  // `?? null` and not a bare read: the field is REQUIRED in the contract, but a
  // frontend deployed against a server that has not shipped it yet would read
  // `undefined` and take the `.name` branch, and the whole account screen would
  // go blank over one cell. It degrades to the stated absence instead — law 3,
  // the unsafe option is the one you have to type.
  const unitPlan = detail.unit_plan ?? null;
  // `?? null` for the same reason: `deposit_waiver` is optional in the type so
  // a bundle ahead of its server degrades to the ordinary deposit figure.
  const waiver = detail.deposit_waiver ?? null;
  return (
    <div
      // ⚠ **FIVE TILES (PO 2026-09-13), SO THE STEP IS 1 → 3 → 5 AND NOT
      // 1 → 2 → 4.** `DEF-3485` chose 1 → 2 → 4 for four tiles on the reasoning
      // that three-of-four strands the deposit alone on a second row; the same
      // reasoning gives a different answer for five. **No row may end in ONE
      // orphan** — the rule the portal's `kpiColumns` already states — and of
      // the options for five, 2 leaves an orphan (2·2·1) and 4 leaves one
      // (4·1). 3 gives 3·2 and 5 gives one row, so both are clean.
      // The staff app is laptop and desktop only (PO 2026-09-10), so 1280 and
      // 1440 are what this is built for; the narrower steps are courtesy.
      className="mb-4 grid grid-cols-1 gap-6 border-t-2 border-t-accent bg-surface px-6 py-5 md:grid-cols-3 xl:grid-cols-5"
      data-account-metrics=""
    >
      <div>
        <Kicker as="div">{t("customers.accounts.col.balance")}</Kicker>
        <div
          className="mt-0.5 font-heading text-metric font-extrabold tabular-nums text-accent"
          // DEF-127: the LEDGER's figure with the CHAR(3) the ledger derived
          // for it, never `accounts.balance` (a cache nothing writes). WHERE
          // the figure came from rides on the element rather than in a line
          // beneath it, because r10 spends that line on the due date — the
          // sentence is unchanged, and it is still one hover from the reader.
          title={t("customers.account.balanceCached")}
        >
          {/* A null means the books could not be asked — a dash, never $0.00.

              ✅ **AND A REAL ZERO THAT IS NOT AN ANSWER GETS ITS OWN CELL —
              DEF-628 / BR-CUS-510.** The S17 row and this header read ONE
              derivation (DEF-127's whole point), so they must spell it one way
              too: a `Pending activation` account served `0.000000` with an
              empty `balance_unavailable`, and a `$0.00` at 26px accent on the
              header of an account that cannot be billed yet is the same false
              claim the row was making, larger. `balance_not_yet_billable` is
              the server's four-clause conjunction and is never re-derived here
              — `Disconnected` is `non_billable` too and holds a debt
              (BR-CUS-107). The sub-line below stays the DUE DATE's: it is
              about the figure above it, and CR-043 finding 11 is what happens
              when a sub-line names no subject. */}
          {detail.balance === null ? (
            <Dash />
          ) : detail.balance_not_yet_billable ? (
            <span className="font-body text-base font-normal text-body">
              {t("customers.accounts.balance.awaiting", { defaultValue: "Awaiting" })}
            </span>
          ) : (
            <MoneyCell
              amount={detail.balance}
              currency={detail.balance_currency ?? detail.currency}
            />
          )}
        </div>
        <div className={`text-sm ${MUTED}`}>
          {/* r10 prints `Due Aug 25`. BR-CUS-033 makes that the oldest OPEN
              invoice's due date — an AR position billing publishes for no
              account today, so this states the absence rather than reaching
              into `GET /invoices` and deciding for itself which bill is open.

              ⚠ **THE LABEL USED TO READ "Not known yet" AND THE PO READ IT AS
              BEING ABOUT THE BALANCE ABOVE IT (CR-043 finding 11).** The
              screenshot is unambiguous: **$64.57** with *"Not known yet"*
              underneath. This component's own docstring already required the
              sub-line to be *"about the figure above it — never about a
              different one"*, and a sub-line that names no subject is read as
              being about whatever it sits under. It now names the due date.
              The reason sentence also said *"Billing is not built yet"*, and
              billing IS built — the same page lists this account's bills, each
              with its own due date. Hard-won law 1: the sentence was true when
              written and nothing re-read it. What is actually missing is which
              of those bills is still OPEN. */}
          <AwaitsCell
            label={t("customers.account.awaits.dueDate")}
            why={t("customers.account.awaits.dueDateWhy")}
          />
        </div>
      </div>

      {/* ── AGEING · THE SECOND TILE (PO ruling 2026-09-13) ───────────────
          PO verbatim, naming the row in full: *"Balance, Ageing, Last bill,
          Plan from unit, Deposit - this is correct"*, confirming the Accounts
          blueprint's own drawing of `ACC-02` under B14 rule 41.

          ⚠ **THIS SUPERSEDES THE COUNT IN `DEF-3485` (PO, 2026-09-03), NOT ITS
          REASONING.** That ruling read *"Can we show deposite data as 4th item
          on this line - Balance / Plan from unit / Last activity"* and set this
          row to FOUR. The blueprint draws FIVE and drops **Last activity** for
          **Ageing** and **Last bill**. Put to the PO as a contradiction between
          a drawing and a signed ruling — which is the one question B14 rule 41
          allows — and ruled for the drawing. `DEF-3485`'s deposit tile stays
          exactly where it put it, last.

          **WHY AGEING EARNS A TILE, and it is the whole reason this row moved.**
          The accounts LIST draws an Ageing column. The DETAIL drew nothing: on
          `A-11812` the server answers `d61_90`, 61 days, source
          `opening_buckets`, and the words *past due* appeared NOWHERE on that
          account's page. A clerk drilling in from the list lost the single fact
          that says how overdue the account is.

          ⚠ **THE BAND'S WORDS ARE THE LIST'S AND THE PRESENTATION IS NOT.**
          `ageingSegmentOf` and `customers.accounts.ageing.<segment>` are
          mounted from `accountsListCells`, so the two screens can never name a
          band differently. `AgeingCell` itself is NOT reused: it renders a
          `StatusPill`, which is right in a table row and wrong as a tile value
          — the drawing puts the band at the tile's own metric size beside
          `$2,410.00`. Sharing the vocabulary is the part that must not drift;
          sharing the pill would have imported a table's presentation onto a
          header. */}
      <div>
        <Kicker as="div">{t("customers.accounts.col.ageing")}</Kicker>
        {ageingSegment === null ? (
          <>
            <div className="mt-1.5 text-base">
              {ageingWhy === null ? (
                <Dash />
              ) : (
                <AwaitsCell label={t("customers.accounts.ageing.unknown")} why={ageingWhy} />
              )}
            </div>
            <div className={`text-sm ${MUTED}`} />
          </>
        ) : (
          <>
            <div className="mt-0.5 font-heading text-metric font-extrabold text-accent">
              {t(`customers.accounts.ageing.${ageingSegment}`)}
            </div>
            <div className={`text-sm ${MUTED}`}>
              {props.detail.ageing_days_past_due === null ||
              props.detail.ageing_days_past_due === undefined
                ? ageingSourceLabel
                : `${t("customers.accounts.ageing.daysPastDue", {
                    days: props.detail.ageing_days_past_due,
                  })} · ${ageingSourceLabel}`}
            </div>
          </>
        )}
      </div>

      {/* ── LAST BILL · THE THIRD TILE (PO ruling 2026-09-13) ─────────────
          `last_bill_at` has been on `AccountRow` since the row existed and was
          drawn on no screen — one of the eleven served fields the Accounts
          blueprint counted as reaching nobody.

          ⚠ **NULL IS A FACT HERE, NOT A FAILURE, AND THE TWO MUST NOT LOOK
          ALIKE.** An account that has never been billed is an ordinary and
          permanent state — a new connection, or an opening balance carried in
          at migration — so this says *Never billed* rather than awaiting
          anything. `AwaitsCell` would promise a figure is coming; this one is
          not. That is `AgeingCell`'s own distinction, two files over, applied
          the other way round. */}
      <div>
        <Kicker as="div">{t("customers.account.field.lastBill")}</Kicker>
        {props.detail.last_bill_at === null ? (
          <>
            <div className="mt-1.5 text-base">{t("customers.account.neverBilled")}</div>
            <div className={`text-sm ${MUTED}`}>{t("customers.account.neverBilledWhy")}</div>
          </>
        ) : (
          <>
            <div className="mt-0.5 font-heading text-metric font-extrabold tabular-nums">
              <DateCell
                value={props.detail.last_bill_at}
                timeZone={props.timeZone}
                dateFormat={props.dateFormat}
              />
            </div>
            <div className={`text-sm ${MUTED}`} />
          </>
        )}
      </div>

      <div>
        {/* ⚠ **THE KICKER NAMES THE UNIT, AND IT IS A KEY OF ITS OWN.**
            `customers.account.field.plan` — plain *"Plan"* — is SHARED with the
            New-account and Move-in wizards and is not touched here (rewording a
            shared plan key once before made both wizards say the wrong thing,
            and their three tests caught it — one sentence per meaning). A box
            captioned only *"Plan"* is read as the plan every past bill used;
            what priced an OLD bill is that bill's Charges tab and not this
            box, so the caption says where this figure comes from. */}
        <Kicker as="div">{t("customers.account.planFromUnit")}</Kicker>
        <div className="mt-1.5 font-heading text-body font-extrabold">
          {/* ── DEF-2419 · THE PLAN THIS ACCOUNT IS BILLED ON ────────────────
              PO ruling 2026-09-01: *"It should be foreign key - it should take
              it from Unit and display it there - that is important"*, said
              after seeing the UNIT screen print this same unit's plan
              correctly while this box refused to. It confirms their ruling of
              2026-08-11 — *"from unit you will derive the plan"* — which
              `services._account_and_unit_plan` and the whole change-plan
              wizard have followed since, leaving this header as the one
              surface that never did.

              **WHAT THIS BOX USED TO SAY, AND WHY IT WAS WRONG.** It stated an
              absence — *"Plan not shown here"* — over a 68-word explanation
              that the billed plan is kept as an account snapshot whose table
              does not exist, and that the unit's plan is not put in its place
              *"because the two match only until the first override"*.

              **There is no override and there cannot be one.** `accounts`
              carries no plan column of any kind and `account_plan_assignments`
              was never built, so no per-account plan can be stored anywhere:
              the divergence that sentence guarded against has nowhere to live.
              The decision conflated STORING a snapshot on the account
              (correctly not done — there is no DDL) with SHOWING which plan
              the account is billed on, which stores nothing and is a read
              along keys the schema already has.

              **The premise was wrong; the caution was not, and the split keeps
              it.** `detail.plan` is UNCHANGED — still null, still beside
              `plan_snapshot_unavailable` — and means the snapshot taken when
              the account was set up, which priced its old bills. `unit_plan` is
              a different question with a different answer: the plan the unit
              stands on today. Nothing can read one as the other.

              **The 68 words are gone from the screen and are these words
              instead.** B14 rule 33 puts RATIONALE at ZERO words on screen and
              rule 32 caps the section at one sentence; the paragraph explained
              why a control was absent, which is precisely the class rule 33
              names. Both keys left all eleven catalogues with it. */}
          {unitPlan === null ? (
            /* Three different absences arrive here as the same null and all
               three are REAL: the account names no unit (a master covering
               premises, BR-CUS-1010), the unit stands on no plan
               (`units.rate_plan_id` is nullable — an ordinary state, not a gap
               in the utility's data), or the plan is no longer published
               (BR-RAT-030, so it prices nothing either). `Dash` and not
               `NotRecorded`: the server no longer refuses this field, it
               answers, and the answer is nothing. And NOT the shared
               `planUnavailable` key, for the reason the kicker comment above
               gives. */
            <Dash>{t("customers.account.planNone")}</Dash>
          ) : (
            <>
              {unitPlan.name}
              {/* BR-CUS-013's SNAPSHOT integer, served verbatim by rating and
                  never recomputed — the same `v1` the unit screen prints. */}
              {unitPlan.version === null ? null : (
                <span className={`font-normal ${MUTED}`}>
                  {" "}
                  {t("customers.account.planVersion", { version: unitPlan.version })}
                </span>
              )}
              {/* `units.plan_effective_from` — the unit screen's *"ON PLAN
                  SINCE"*. Interpolated rather than concatenated because the
                  word order moves between languages; `formatDate` is
                  BR-SHL-034's one formatter and the tenant's own format. */}
              {unitPlan.since === null ? null : (
                <span className={`font-body text-sm font-normal ${MUTED}`}>
                  {" · "}
                  {t("customers.account.planSince", {
                    date: formatDate(unitPlan.since, props.timeZone, props.dateFormat),
                  })}
                </span>
              )}
            </>
          )}
        </div>
        {/* ⚠ **THE SENTENCE IS UNCHANGED AND IT IS NOW CLOSED BY DEFAULT —
            B14 rule 32, `DEF-3484`.** The Product Owner, on this tile:
            *"too much content here - Sample — Commercial v1 · since 06/01/2026
            / Base charge not shown here — see any bill's Charges tab"*. Two
            facts were competing for one tile: the plan the account is billed
            on, and a nineteen-word explanation of a figure that is NOT here.
            Rule 32 gives a section ONE sentence and puts a stated absence in
            something closed by default, so the absence keeps its subject
            (`Base charge`) and its whole reason travels on the element instead
            of on the screen — one hover away for the clerk who wonders, and out
            of the way of the clerk who does not.

            `AwaitsCell` and not a `<details>` element: this screen already has
            one shape for "a fact this cell cannot show, with its reason", it is
            used four times within thirty lines of here, and a second shape for
            the same meaning is the drift B14 exists to stop. Nothing is lost —
            `customers.account.planBaseUnavailable` is the same string it was,
            in all eleven catalogues. */}
        <div className={`text-sm ${MUTED}`}>
          <AwaitsCell
            label={t("customers.account.awaits.baseCharge")}
            why={t("customers.account.planBaseUnavailable")}
          />
        </div>
      </div>

      {/* ── THE FOURTH COLUMN (PO 2026-09-03, `DEF-3485`) ──────────────────
          Verbatim: *"Can we show deposite data as 4th item on this line -
          Balance / Plan from unit / Last activity - you can adjust the
          deposite details and show all information that can i=fit on that
          line"*.

          ⚠ **THE DOCSTRING ABOVE SAID "THREE, AND THE AGEING FACT IS NOT A
          FOURTH", AND THAT STILL HOLDS — IT IS NOT BEING BENT HERE.** That
          paragraph refuses to INVENT a fourth column, on the reasoning that
          r10 draws three and B18 puts ageing on the S17 row. This fourth
          column is not an invention: the Product Owner asked for it, in this
          slot, in those words, and gave the latitude to choose which deposit
          facts earn the space. So the rule that paragraph states is unchanged
          and its COUNT is superseded by a ruling.

          **WHAT EARNS THE SPACE, out of the four rows the "Deposit & credit"
          card carries.** THE AMOUNT HELD, because it is the only one a clerk
          acts on — a customer asking "how much of my money do you have" is the
          question this tile answers in one glance. Its RECEIVED DATE as the
          sub-line, because this component's own rule is that a sub-line is a
          fact about the figure above it. The other two stay on the card below
          and NOTHING is lost: the credit tier is honestly "Not computed" and
          would be a tile saying nothing, and accrued interest is a figure this
          screen is not served (`DEF-3486`) — a tile cannot show what no
          endpoint sends. */}
      <div>
        <Kicker as="div">{t("customers.account.field.depositOnFile")}</Kicker>
        <div className="mt-0.5 font-heading text-metric font-extrabold tabular-nums text-accent">
          {/* The BALANCE column three tiles left refuses to print a zero that
              is not an answer (DEF-628), and this figure has the same shape:
              the column defaults to 0 and an account that has never lodged a
              deposit reads exactly like an account holding none of the
              customer's money. The difference is that here the two are the
              SAME STATEMENT — a utility holding no deposit holds $0.00 — so
              the figure is honest, and the sub-line carries where it comes
              from rather than a second figure being invented for the gap. */}
          {waiver !== null ? (
            // ── A WAIVED DEPOSIT (`DEF-CUS-6370`) ───────────────────────────
            // The register reads $0.00 on a waived account, exactly as it does
            // on an account whose plan asked nothing — so the figure here is
            // the WAIVE, kept on the account, and never the zero. The sub-line
            // below says who and when (a name, never an id — rule 31).
            <span data-deposit-waived="">
              {t("customers.account.depositWaived")} ·{" "}
              <MoneyCell amount={waiver.amount} currency={waiver.currency} />
            </span>
          ) : detail.deposit_on_file === null ? (
            <Dash />
          ) : (
            <MoneyCell amount={detail.deposit_on_file} currency={detail.currency} />
          )}
        </div>
        <div className={`text-sm ${MUTED}`}>
          {waiver !== null ? (
            <span data-deposit-waived-by="">
              {[waiver.waived_by_name, waiver.reason].filter((part) => part).join(" · ")}
              {waiver.waived_at === null ? null : (
                <>
                  {waiver.waived_by_name || waiver.reason ? " · " : null}
                  <DateCell
                    value={waiver.waived_at}
                    timeZone={props.timeZone}
                    dateFormat={props.dateFormat}
                  />
                </>
              )}
            </span>
          ) : detail.deposit_received_on === null ? (
            <AwaitsCell
              label={t("customers.account.field.depositReceived")}
              why={t("customers.account.depositNoWriter")}
            />
          ) : (
            <span className="tabular-nums">
              <DateCell
                value={detail.deposit_received_on}
                timeZone={props.timeZone}
                dateFormat={props.dateFormat}
              />
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-CUS-008@6825515 (sha1[:7] of the three sources this lane was authored from, concatenated in order: 04-docs/05-modules/03-customers/06-epics/EP-CUS-03-account-detail.md · 04-docs/05-modules/03-customers/02-business-rules.md · 04-docs/02-decisions/18-cr030-onboarding-design.md §5.2 — the CR-030 W3 packet)
// co-packet: CR-030/B18@2026-08-23 §5.2.1 (S21 · ACC-01) · BR-CUS-015/029/033/059 · W3 tasks 3.1 + 3.3
// generated: 2026-08-24 by the CR-030 W3 frontend lane
// checklist: A✔ B✔ C✔ D=deferred(no API call — display components; the page owns every fetch) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest (AccountDetailPage.test.tsx TC-ACD-1/4 + the chip cases) · g31 (registered in styles/route-b-migrated.txt, so routeBUtilities.test.ts and the real Tailwind compiler own every utility here) · g38 (no <ArrivesWith> in this file — its absences are AwaitsCell/NotRecorded, which carry their reason on the element) · g14 (adds no `.col.` heading)
// exceptions: E3 the metric block renders BELOW the shared PageHeader rather than INSIDE the header card as r10 draws it: `components/PageHeader.tsx` owns the card and belongs to another lane, and a second card drawn here would be two headers (B14 rule 2). REPORTED · E3 THREE metric columns, not four: the AGEING fact this screen used to show is dropped, because r10's header draws three and B18 §5.1.2 puts ageing on the S17 row. REPORTED as a divergence from the shipped screen · E3 the PLAN column's sub-line (`$30.50/mo base` in r10) is a stated absence rather than a figure: the base charge belongs to the plan snapshot BR-CUS-029 has no table for, and reading the UNIT's plan for it is exactly the substitution that rule forbids · E3 the service chip pairs a meter number from the ASSETS row (`GET /assets/{id}.service`), because `GET /accounts/{id}` serves services and meters as two unrelated lists; an unpaired service renders the bare chip rather than a guessed pairing · E3 `gap-[5px]` / `py-[3px]` are r10's own `.svc-dot` values rather than the 4px scale's nearest step — this chip is a ported drawing
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
