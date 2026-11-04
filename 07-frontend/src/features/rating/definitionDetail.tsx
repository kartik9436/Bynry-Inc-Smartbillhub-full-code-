// ── Trace ──────────────────────────────────────────────
// Change:   CR-013 P2 — the shared DEFINITION DETAIL, rows 8 · 11 · 14 of the
//           16-surface inventory (`09-screen-inventory.md` §18)
//           Screens: CHG-01 (charge) · CHG-01.discount · CHG-01.tax
// Rules:    BR-RAT-084 (ONE component behind THREE routes with THREE screen ids —
//           *"Reduction in FILES, never in the enumeration … the three are not
//           identical and the shell must not force them to be"*; tab counts
//           5 · 5 · 6, and the four KPI tiles differ per kind) ·
//           BR-RAT-087 / DEF-364 (money and percent render from the SERVER's
//           `*_display` string — never the stored value, never scaled here) ·
//           BR-RAT-035 (service `Any` is a real answer, not a blank) ·
//           BR-RAT-005 (a fee is never in the tax base) · BR-SHL-034 (one date
//           formatter) · B12 §"No hard-coded values" (the three kinds are DATA)
// ───────────────────────────────────────────────────────
//
// THE THREE KINDS, AS DATA. This file holds no markup and no routing: it is the
// per-kind configuration BR-RAT-084 requires, plus one presenter per kind that
// turns a served row into the eight-part shell's slots. `DefinitionDetailPage`
// renders whatever it is handed, so adding a fourth kind is a table entry and a
// presenter — never a fourth branch of copy-pasted JSX.
//
// ⚠ THE TAB SETS DIFFER AND THAT IS THE RULING, NOT AN OVERSIGHT. §2 part 7
// records 5 · 5 · 6 off the running canvas, and BR-RAT-084 states the shell
// "must not force them to be" identical. Anything that normalises the three to
// one tab list has built the wrong screen.
//
// ⚠ AND SO DOES TILE 4. §2's table gives the charge `BASIS · Per size` and the
// discount `TYPE · % of subtotal` — TEXT, not a number — against the tax's
// `RATE 2.00%`. The tile type below therefore takes a `ReactNode` value and
// never a number, so a kind that wants a word can have one.
import type { ReactNode } from "react";

import { CUSTOMER_CLASSES } from "@/api/endpoints";
import type { ChargeRow, DiscountDetail, GlAccountRef, TaxRow } from "@/api/endpoints";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import type { KpiTile } from "@/components/KPIStrip";
import type { StatusTone } from "@/components/StatusPill";

import { chargeAmountDisplay } from "./ChargeCodesTab";
import { taxRateDisplay } from "./TaxesFeesTab";
import {
  PLANS_RATES_ROUTE,
  activeStatusTone,
  discountStatusTone,
  enumLabel,
} from "./ratingShared";
import type { Translator } from "./ratingShared";

// ── The three kinds ────────────────────────────────────────────────────────

/** r10's `cdKind`, verbatim (`charge|disc|tax` at 10561) — spelled out here so
 *  the three routes, the three ids and the three tab sets key off one list. */
export const DEFINITION_KINDS = ["charge", "discount", "tax"] as const;
export type DefinitionKind = (typeof DEFINITION_KINDS)[number];

/**
 * §2 part 7, read off the running canvas: **8 · 5 · 5 · 5 · 6** across the five
 * details, of which these three are the last three.
 *
 * ⚠ THE SECOND TAB IS A DIFFERENT TAB ON EACH KIND, which is why it carries a
 * different id rather than one `detail` id relabelled: `Amounts` asks what a
 * charge costs, `Value & rules` asks what a discount takes off, and
 * `Rate & basis` asks what a tax is computed over. Three questions, three tabs.
 */
export const DEFINITION_TABS: Readonly<Record<DefinitionKind, readonly string[]>> = {
  charge: ["overview", "amounts", "applicability", "plans", "versions"],
  // ⚠ **FIVE BECAME THREE — CR-087 C2**, PO 2026-09-08: *"there is no point user
  // clicking on 10 thing to review"*. Overview, `Value & rules` and
  // `Applicability` were three tabs answering ONE question — what is this, what
  // is it worth, who qualifies — so a clerk on the phone opened all three to
  // answer one caller. They are three BLOCKS of one Overview now, in the order
  // a call goes: what it IS · what it is WORTH · who QUALIFIES. Same mechanism
  // the tax merge uses one line below, on purpose — two lanes reached for it in
  // the same hour and one of them had to give its name up.
  //
  // ⚠ AND THE LAST TAB IS `audit`, THE NAME EVERY OTHER MODULE USES — assets,
  // premises, units, accounts, bills, cycles, routes and work templates all
  // call this tab `audit`, and Plans & Rates alone called it `Versions`.
  // **What it RENDERS has not changed and must not**: still the object's own
  // version table, never a filtered `audit_log` query (§10, and the
  // source-as-text guard in `DefinitionDetail.test.tsx`). The charge and the
  // tax still say `versions`; {@link isHistoryTab} is the one place that knows
  // both, and it goes when they follow.
  discount: ["overview", "plans", "audit"],
  // ⚠ THE TAX READ SIX UNTIL 2026-09-08 — `overview · basis · applicability ·
  // plans · remittance · versions`. PO ruling of that date, verbatim: *"overview
  // and Remittance & filings - you can merge it in Overview only"*. FOUR tabs
  // answered ONE question about one object, so a clerk on the phone to a
  // customer clicked three times to read a rate, what it was charged on and who
  // it reached. They are five BLOCKS of one Overview now, in the order a
  // question about a tax arrives: what it is · on the bill · what is taxed ·
  // who it reaches · remittance & filings. No data moved; a tab merge is a
  // rendering decision (CR-087 §8).
  // ⚠ **AND THE TAX FOLLOWS THE DISCOUNT ONTO `audit` RATHER THAN KEEPING A
  // SECOND SPELLING OF THE SAME TAB (CR-087 B2).** `VERSIONS_TAB`'s own note
  // calls the two ids *"a migration in progress rather than a choice"* and says
  // `VERSIONS_TAB` goes when the other kinds follow. The tax is the second to
  // follow; the CHARGE is the last one left, and until it moves `isHistoryTab`
  // stays the one place that knows. What the tab RENDERS has not changed and
  // must not: it is still the object's own version table, never a filtered
  // `audit_log` query — renaming the tab renamed the tab.
  tax: ["overview", "plans", "audit"],
};

/** Every tab a shell can be asked for, once — the catalog keys hang off these. */
export const DEFINITION_TAB_IDS = [
  "overview",
  "amounts",
  // ⚠ `value` LEFT THIS LIST WITH THE DISCOUNT'S TAB (CR-087 C2). It was the
  // only kind that declared it, and its fields now live in the merged
  // Overview's *what it is worth* section. The catalogue keeps
  // `rating.definition.panel.value` because `panels.value` is still the flat
  // alias of that list — what has gone is a TAB a shell can be asked for, which
  // is what this array is.
  "basis",
  "applicability",
  "plans",
  "remittance",
  "versions",
  "audit",
] as const;

/** The tab every kind ends on, and the only one carrying the DATED banner.
 *
 *  ⚠ **TWO SPELLINGS, ONE TAB, AND THAT IS A MIGRATION IN PROGRESS RATHER THAN
 *  A CHOICE.** CR-087 renames it `audit` — the name every other module uses —
 *  and the discount is the kind that moved first. Until the charge and the tax
 *  follow, both ids exist and {@link isHistoryTab} is the one place that knows
 *  it. When they follow, `VERSIONS_TAB` goes and nothing else changes. */
export const VERSIONS_TAB = "versions";
/** What the discount's history tab is called from CR-087 C2 onward. */
export const AUDIT_TAB = "audit";

/** Is this the tab that draws the object's OWN version table?
 *
 *  ⚠ IT IS STILL NOT `audit_log`, WHATEVER IT IS CALLED. A version row is a
 *  priced state a bill can resolve to, with a CHANGE sentence a person wrote;
 *  an audit row is an actor plus an action plus a timestamp and the engine
 *  never reads one. Renaming the tab renamed the tab. */
export function isHistoryTab(tab: string): boolean {
  return tab === VERSIONS_TAB || tab === AUDIT_TAB;
}
/** The tab whose body is a list of plans — no endpoint serves it yet (below). */
export const PLANS_TAB = "plans";

/**
 * Where each kind lives, so a deep link resolves (BR-RAT-084's second half).
 *
 * `listRoute` IS THE KIND'S OWN LANDING TAB, and all three now have one. The
 * discount was the exception until CR-013 part 3 built row 10 — for months the
 * six discount tables existed and no tab listed them, so this back link pointed
 * at the Plans & Rates default rather than at a route that would 404. Left
 * written down because the asymmetry is what the absence looked like from here.
 */
export interface DefinitionRouteConfig {
  readonly kind: DefinitionKind;
  /** The segment under `/plans-rates`, matching the landing tab's own path. */
  readonly segment: string;
  /** Back-link target and its label key. */
  readonly listRoute: string;
  readonly backLabelKey: string;
  /** The eyebrow's first part — `CHARGE CODE` · `DISCOUNT` · `TAX` (§2 part 2). */
  readonly kindLabelKey: string;
}

export const DEFINITION_ROUTES: Readonly<Record<DefinitionKind, DefinitionRouteConfig>> = {
  charge: {
    kind: "charge",
    segment: "charge-codes",
    listRoute: `${PLANS_RATES_ROUTE}/charge-codes`,
    backLabelKey: "rating.kicker",
    kindLabelKey: "rating.definition.kind.charge",
  },
  discount: {
    kind: "discount",
    segment: "discounts",
    // ⚠ THIS USED TO BE THE BARE `PLANS_RATES_ROUTE`, because §18 row 10 was
    // *"the tab that is simply absent today"* and a back link to
    // `/plans-rates/discounts` would have 404'd. The tab exists now
    // (`DiscountsTab.tsx`), so the three kinds are finally symmetrical and the
    // back link lands where the row was clicked.
    listRoute: `${PLANS_RATES_ROUTE}/discounts`,
    backLabelKey: "rating.kicker",
    kindLabelKey: "rating.definition.kind.discount",
  },
  tax: {
    kind: "tax",
    segment: "taxes-fees",
    listRoute: `${PLANS_RATES_ROUTE}/taxes-fees`,
    backLabelKey: "rating.kicker",
    kindLabelKey: "rating.definition.kind.tax",
  },
};

// ── TAX-02's two doors (CR-013 P4) ─────────────────────────────────────────
//
// ⚠ THEY LIVE HERE, WITH THE REST OF THE MODULE'S ROUTE TABLE, AND NOT IN
// `TaxWizard.tsx` — WHICH IS A CYCLE, NOT A PREFERENCE. This file already reads
// `taxRateDisplay` from `TaxesFeesTab`, and the tab now links to the wizard, so
// a constant DEFINED in the wizard and DERIVED from `DEFINITION_ROUTES` is
// evaluated at module scope while this module is still initialising:
// `Cannot read properties of undefined (reading 'tax')`, three suites red.
// Declared beside the segment they extend, the string is still spelled once and
// nothing is evaluated before it exists.

/** `+ New tax or fee` — the tab's primary action and the empty state's CTA. */
export const TAX_WIZARD_NEW_ROUTE = `${DEFINITION_ROUTES.tax.listRoute}/new`;

/** The route PATTERN `App.tsx` registers for the edit door. */
export const TAX_WIZARD_EDIT_PATTERN = `${DEFINITION_ROUTES.tax.listRoute}/:taxId/edit`;

/** The edit door for one tax — the row's pencil action goes here. */
export function taxWizardEditPath(taxId: string): string {
  return `${DEFINITION_ROUTES.tax.listRoute}/${encodeURIComponent(taxId)}/edit`;
}

/** The route a landing row links to. One function, so the three paths are
 *  spelled once and `App.tsx` cannot drift from the links that reach it. */
export function definitionPath(kind: DefinitionKind, id: string): string {
  return `${PLANS_RATES_ROUTE}/${DEFINITION_ROUTES[kind].segment}/${encodeURIComponent(id)}`;
}

/**
 * The FULL-PAGE wizard route for a kind — `…/new` to create, `…/{id}/edit` to
 * change (§18 rows 9 · 12 · 15, which *"share a wizard chassis"*).
 *
 * It lives beside `definitionPath` for the same reason that function does: the
 * segment is spelled ONCE, so `App.tsx`, the landing tab's `+ New` button, its
 * pencil row action and the detail header's `Edit` cannot drift apart. Only the
 * charge kind has a wizard built today (CHG-02); the other two resolve to a
 * path nothing routes yet, which is why callers pass a kind rather than reading
 * this for every kind.
 */
export function definitionWizardPath(kind: DefinitionKind, id: string | null): string {
  const base = `${PLANS_RATES_ROUTE}/${DEFINITION_ROUTES[kind].segment}`;
  return id === null ? `${base}/new` : `${base}/${encodeURIComponent(id)}/edit`;
}

// ── The four KPI tiles, per kind (§2 part 6) ───────────────────────────────

/**
 * THREE OR FOUR, and the type says so. §2 reads *"Exactly four KPI tiles,
 * hairline-divided. Tile 1 is always the reach ('who uses this'); tile 4 is the
 * object's defining characteristic and is text, not a number, on three of the
 * five."* A tuple rather than an array is still the cheapest possible
 * enforcement — a kind that grows a FIFTH tile does not compile.
 *
 * ⚠ **THE `EXACTLY FOUR` HALF IS SUPERSEDED FOR THE TAX KIND BY A PO RULING OF
 * 2026-09-10 — verbatim, *"show only one status"*.** The blueprint draws the tax
 * status TWICE, as the pill under the title and again as a KPI tile, and
 * contradicts itself; the ruling picks the pill, which is where every other
 * detail screen in Plans & Rates carries a lifecycle word. So the tax strip is
 * THREE. Nothing is invented to fill the gap: adding a tile the drawing does
 * not draw would be this file trading one divergence for a worse one, and
 * `KPIStrip` lays out on `repeat(auto-fit, minmax(180px, 1fr))`, so three tiles
 * fill the row rather than leaving a hole. Recorded in the tax conformance file.
 */
export type DefinitionKpis =
  | readonly [KpiTile, KpiTile, KpiTile]
  | readonly [KpiTile, KpiTile, KpiTile, KpiTile];

/** The labels §2's table gives each kind, in its order — three or four. */
export const DEFINITION_KPI_LABEL_KEYS: Readonly<
  Record<
    DefinitionKind,
    readonly [string, string, string] | readonly [string, string, string, string]
  >
> = {
  charge: [
    "rating.definition.kpi.charge.plans",
    "rating.definition.kpi.charge.bills",
    "rating.definition.kpi.charge.revenue",
    "rating.definition.kpi.charge.basis",
  ],
  discount: [
    "rating.definition.kpi.discount.plans",
    "rating.definition.kpi.discount.enrolled",
    // ⚠ **CR-087 C2 — `…discount.cost` STOOD HERE AND WAS AN EM-DASH ON EVERY
    // DISCOUNT THAT HAS EVER EXISTED.** Nothing computes a month's subsidy for
    // one programme, so the tile was a permanently blank quarter of the strip —
    // furniture, not a stated absence. The take-up denominator is a real figure
    // and earns the slot; the cost is named in words on the Overview instead,
    // so it is not deleted in silence.
    "rating.definition.kpi.discount.offered",
    "rating.definition.kpi.discount.type",
  ],
  tax: [
    "rating.definition.kpi.tax.plans",
    // ⚠ **`…tax.base` AND `…tax.collected` STOOD IN THESE TWO SLOTS AND WERE AN
    // EM-DASH ON EVERY TAX THAT HAS EVER EXISTED.** Nothing totals the base one
    // tax is charged on and nothing totals what one tax collected — both are
    // `PRB-06`, both need reads over invoice tax lines that do not exist — so
    // HALF THIS STRIP was furniture rather than a stated absence. That is the
    // defect `CR-087 C2` already fixed for the discount kind, whose own comment
    // twenty lines up says it in as many words; it never reached the tax, which
    // had two such quarters where the discount had one.
    //
    // The two facts that replace them are the two the blueprint draws
    // (`CR-087-p030-tax-overview.md` §4) and both have a server read today:
    // PREMISES IN SCOPE is `GET /taxes/matched-premises`, which the wizard has
    // used since DEF-380 and this page never called, and STATUS is on the row.
    // The absences are NOT deleted in silence — they are stated in words under
    // the strip, which is the drawing's own `NOT WORKED OUT YET` bar and its
    // rules line: *"A figure that does not exist is stated with its reason and
    // never drawn at the weight of one that does."*
    "rating.definition.kpi.tax.premises",
    // ⚠ **`…tax.status` STOOD HERE AND WAS THE SECOND RENDERING OF ONE FACT.**
    // `row.status` already draws as the pill under the title. PO 2026-09-10,
    // verbatim: *"show only one status"*.
    "rating.definition.kpi.tax.rate",
  ],
};

/**
 * What a tile or a field renders when nothing serves its value: an em-dash,
 * never a zero and never a plausible-looking number. Every such site names the
 * read it is missing, in a TODO in the presenter below.
 *
 * ⚠ IT IS *NOT* DERIVED FROM `ratingShared.CELL_NONE`, WHICH IS THE SAME GLYPH.
 * That constant is the A4 permission vocabulary — the `—` the SERVER sends for
 * a role with no access to a module — and this is "the server serves no figure
 * for this tile". Two different facts that happen to render the same character;
 * tying them together would make a permission-vocabulary change silently move
 * an unrelated KPI. B12's no-hard-coded-values rule asks whether another part
 * of the system knows THIS value, and nothing does.
 */
export const NO_FIGURE = "—";

function tiles(
  kind: DefinitionKind,
  t: Translator,
  /** ⚠ **THE KEY LIST DECIDES HOW MANY TILES A KIND HAS, NOT THIS ARRAY.** A
   *  kind's count is stated ONCE, in `DEFINITION_KPI_LABEL_KEYS`, and a value
   *  past the end of that kind's keys is ignored rather than drawn under a
   *  missing label — which is what lets `emptyKpis` pass four for every kind. */
  values: readonly ReactNode[],
  /** CR-087 C2 — the caption under a figure, saying WHAT IT COUNTS. A count with
   *  no denominator and no unit is trivia; `31` under *Enrolled accounts* and
   *  `86` under *Offered to* only become take-up once each says what it is
   *  counting. Omitted per tile, and a tile with none draws as it always did. */
  details: readonly (ReactNode | undefined)[] = [],
): DefinitionKpis {
  const keys = DEFINITION_KPI_LABEL_KEYS[kind];
  const tile = (index: number, key: string): KpiTile => ({
    id: `${kind}-${index + 1}`,
    label: t(key),
    value: values[index],
    detail: details[index],
  });
  // Narrowed by LENGTH so each branch returns a real tuple — no cast, which is
  // the whole point of the type being a tuple rather than an array.
  return keys.length === 3
    ? [tile(0, keys[0]), tile(1, keys[1]), tile(2, keys[2])]
    : [tile(0, keys[0]), tile(1, keys[1]), tile(2, keys[2]), tile(3, keys[3])];
}

// ── What the shell renders ─────────────────────────────────────────────────

/** One labelled fact inside a panel. The label is a catalog KEY, never a
 *  sentence — B8's i18n rule and B12's no-hard-coded-values rule, together. */
export interface DefinitionField {
  readonly labelKey: string;
  readonly value: ReactNode;
}

/**
 * The eight-part shell's slots, filled by a presenter and rendered by the page.
 *
 * `panels` is keyed by TAB ID: a tab present here renders its fields, a tab
 * absent from it renders the shell's own body for that tab (`plans` and
 * `versions`, neither of which any endpoint serves). That is what keeps the
 * page one loop instead of three.
 */
/**
 * One titled group of facts inside a tab — CR-087 B2.
 *
 * ⚠ **IT EXISTS BECAUSE A MERGED TAB IS NOT A LONGER LIST.** Folding four tax
 * tabs into one Overview without headings would produce twenty-odd labelled
 * rows in a single grid, which is harder to read than the four tabs it
 * replaced. Each block keeps the heading its tab had, so *"Remittance &
 * filings"* is still found by looking for the word — which is the practical
 * answer to the outside bookkeeper whose own tab this merge took away.
 *
 * `noteKey` is at most ONE sentence (B14 rule 32: a screen has a description
 * budget), and it is optional because most blocks do not need one.
 */
export interface DefinitionBlock {
  readonly id: string;
  readonly titleKey: string;
  readonly noteKey?: string;
  readonly fields: readonly DefinitionField[];
}

export interface DefinitionPresentation {
  /** §2 part 3 — the `<h1>`. */
  readonly title: string;
  /** §2 part 2 — the uppercase `·`-separated eyebrow, already assembled. */
  readonly eyebrow: string;
  /** §2 part 4 — the muted sub-line, as already-rendered fragments. A date in
   *  it goes through `DateCell` like every other date on the screen
   *  (BR-SHL-034), so the fragments are nodes rather than strings. */
  readonly subline: readonly ReactNode[];
  /** §2 part 5 — the status pill's own value and tone. */
  readonly statusValue: string | null;
  readonly statusStem: string;
  readonly statusTone: StatusTone;
  readonly kpis: DefinitionKpis;
  readonly panels: Readonly<Record<string, readonly DefinitionField[]>>;
  /**
   * Keyed by TAB ID like `panels`, and it WINS where both are present. A kind
   * that has nothing to group keeps `panels` and renders one panel, exactly as
   * all three did before CR-087 — this is additive, and the charge and discount
   * kinds are untouched by it.
   */
  readonly blocks?: Readonly<Record<string, readonly DefinitionBlock[]>>;
}

// ── Charge code (§18 row 8) ────────────────────────────────────────────────

/** The GL account named rather than printed as a uuid (DEF-206's lesson). */
function glText(
  t: Translator,
  accountId: string | null,
  accounts: readonly GlAccountRef[],
): string {
  if (accountId === null) {
    return t("rating.gl.unset");
  }
  const account = accounts.find((row) => row.id === accountId);
  return account === undefined ? t("rating.gl.unresolved") : `${account.code} — ${account.name}`;
}

/**
 * The enrolment answer as a FACT, with the chooser's trailing clause taken off
 * — `CR-087-p076` §6.
 *
 * ⚠ **THE CLAUSE IS SPLIT OFF RATHER THAN RE-WRITTEN INTO A SECOND KEY SET.**
 * Three more catalogue strings saying the same three things in eleven
 * languages is how a product ends up with two vocabularies for one field, and
 * the day one of them is amended they disagree. The dropdown's own strings are
 * `Answer — what picking it does`, one em-dash, written that way on purpose in
 * all eleven; the fact is the half before it.
 */
function enrolmentFact(t: Translator, choice: string): string {
  const composed = t(`rating.discountWizard.enrolmentChoice.${choice}`);
  const [answer] = composed.split(" — ");
  return answer.trim();
}

function serviceText(t: Translator, service: string | null): string {
  // BR-RAT-035: NULL service = Any, and "Any" is a real answer, not a blank.
  return service === null
    ? t("rating.charges.anyService")
    : t(`rating.service.${service}`, { defaultValue: service });
}

function yesNo(t: Translator, value: boolean): string {
  return t(value ? "rating.yes" : "rating.no");
}

/**
 * `Taxed` / `Not taxed` — DEF-RAT-4662.
 *
 * ⚠ **`Usage charges: Yes` ANSWERS A QUESTION THE LABEL DOES NOT ASK.** The
 * label is a NOUN, so the reader has to already know that the unwritten
 * question is *"is this in the tax base"* — and a column of Yeses tells them
 * nothing about what was being asked. The wizard gets this right, because
 * there the heading above the two ticks is *"What is taxed"*; the read screen
 * had no such heading and kept the abstract answer.
 *
 * `yesNo` above is deliberately left alone: on the charge kind the labels ARE
 * questions (*"Waivable"*, *"Auto-apply"*) and Yes is the right word there.
 */
function taxedOrNot(t: Translator, value: boolean): string {
  return t(value ? "rating.taxes.baseTaxed" : "rating.taxes.baseNotTaxed");
}

/** The tenant's Regional settings, carried in so a presenter never formats a
 *  date itself — BR-SHL-034 is one formatter with no exception for a sub-line. */
export interface DefinitionRegional {
  readonly timeZone: string;
  readonly dateFormat: RegionalDateFormat;
}

function dateNode(value: string | null, regional: DefinitionRegional): ReactNode {
  return value === null ? (
    NO_FIGURE
  ) : (
    <DateCell value={value} timeZone={regional.timeZone} dateFormat={regional.dateFormat} />
  );
}

/**
 * The customer types a charge code prices SEPARATELY, in the order the platform
 * lists them (`BR-CUS-094`'s ruling order, never alphabetical).
 *
 * ⚠ **THIS IS NOT `applies_to_customer_classes`.** That field says who the code
 * REACHES; this says which of them it charges a different amount. A code can
 * reach everybody and price one type differently, and it can name three types
 * and price them all the same.
 */
function chargeCustomerClasses(row: ChargeRow): string[] {
  const priced = new Set(
    row.size_amounts
      .map((size) => size.customer_class)
      .filter((code): code is string => code !== null),
  );
  return CUSTOMER_CLASSES.filter((code) => priced.has(code));
}

export function presentCharge(
  row: ChargeRow,
  t: Translator,
  accounts: readonly GlAccountRef[],
): DefinitionPresentation {
  // BR-RAT-087 / DEF-364: the shared display helper, reused rather than
  // reimplemented — it reads `amount_display` / `percent_display`, so this
  // screen cannot re-introduce the raw fraction the landing tab stopped showing.
  const amount = chargeAmountDisplay(row);
  const amountText = t(amount.key, amount.params);
  const basis = enumLabel(t, "rating.charges.amountRule", row.amount_rule);

  return {
    title: row.name,
    // §2 part 2: `CHARGE CODE · BASE-W · RECURRING · V2`. The version is the
    // fourth part on the drawing and is DELIBERATELY ABSENT here: charge codes
    // carry no version table (§10 · DEF-357), and printing `V1` would assert a
    // history the product does not keep.
    eyebrow: [
      t("rating.definition.kind.charge"),
      row.code,
      enumLabel(t, "rating.charges.type", row.charge_type),
    ].join(" · "),
    subline: [
      `${t("rating.charges.col.gl")}: ${glText(t, row.gl_account_id, accounts)}`,
      // BR-RAT-005's policy note, which is the sub-line's third part on r10.
      t("rating.definition.charge.policy"),
    ],
    statusValue: row.status,
    statusStem: "rating.status",
    statusTone: activeStatusTone(row.status),
    kpis: tiles("charge", t, [
      // Tile 1 — the reach. Served (`used_by_plans`).
      row.used_by_plans,
      // TODO(CR-013 row 8): "bills last month" has no read. `used_by_invoice_lines`
      // is a LIFETIME count of referencing lines, which is a different question,
      // and labelling it as last month's would be a wrong number rather than a
      // missing one. Needs a period-scoped count on `GET /charges/{id}`.
      NO_FIGURE,
      // TODO(CR-013 row 8): monthly revenue for one charge code is not served by
      // any route in `apps/rating/api.py`. It belongs with the Finance
      // reconcile-by-code read (CR-013 part 2 "Downstream").
      NO_FIGURE,
      // Tile 4 — TEXT, per §2. `Per size` arrives with `charge_code_amounts`
      // (DEF-356, not built), so today the basis is the amount RULE.
      basis,
    ]),
    panels: {
      // §2 part 8: charge / discount / tax Overviews are ONE panel deep.
      overview: [
        { labelKey: "rating.charges.col.description", value: row.name },
        {
          labelKey: "rating.charges.col.type",
          value: enumLabel(t, "rating.charges.type", row.charge_type),
        },
        { labelKey: "rating.filter.service", value: serviceText(t, row.service) },
        { labelKey: "rating.charges.col.amount", value: amountText },
      ],
      amounts: [
        { labelKey: "rating.charges.amountRuleLabel", value: basis },
        { labelKey: "rating.charges.col.amount", value: amountText },
        { labelKey: "rating.charges.minLabel", value: row.min_amount_display ?? NO_FIGURE },
        { labelKey: "rating.charges.maxLabel", value: row.max_amount_display ?? NO_FIGURE },
        {
          // BR-RAT-690 (DEF-2190). This line read *"Per-size amounts are not
          // stored yet, so this code has one amount for every size"* until a
          // utility could store them — a stated absence that had become a
          // false statement about the tenant's own data the moment CHG-02 grew
          // the table. It now reports what the code actually carries: the
          // sizes it prices, and how many of those it does NOT SERVE (a row
          // with no amount refuses the bill rather than charging $0.00 —
          // DEF-277).
          labelKey: "rating.definition.charge.perSize",
          value:
            row.size_amounts.length === 0
              ? t("rating.definition.charge.perSizeNone")
              : t("rating.definition.charge.perSizeCount", {
                  // ⚠ **DISTINCT SIZES, NOT ROWS (CR-087 A1).** A code can now
                  // hold two rows for ONE size — $45.00 for every customer type
                  // and $85.00 for Commercial — and counting rows reports that
                  // as *"2 connection sizes listed"*, which is a false statement
                  // about the tenant's own data of exactly the kind this line
                  // was rewritten once already to stop making.
                  count: new Set(row.size_amounts.map((size) => size.size_class)).size,
                  served: new Set(
                    row.size_amounts
                      .filter((size) => size.amount_display !== null)
                      .map((size) => size.size_class),
                  ).size,
                }),
        },
        // ⚠ **AND THE SECOND DIMENSION HAS TO SAY IT IS THERE.** Without this
        // line a code priced differently for Commercial looks identical on its
        // own page to one that is not, and the difference is money. The figures
        // themselves are the grid's, one click away under Edit — drawing all of
        // them on this page is `PRB-04` and is not built.
        ...(chargeCustomerClasses(row).length === 0
          ? []
          : [
              {
                labelKey: "rating.definition.charge.perClass",
                value: chargeCustomerClasses(row)
                  .map((code) => t(`rating.customerClass.${code}`))
                  .join(", "),
              },
            ]),
      ],
      applicability: [
        { labelKey: "rating.charges.appliesTo", value: serviceText(t, row.service) },
        /**
         * **WHO IT REACHES — `DEF-RAT-5821`, and the tab named for the question
         * did not answer it.**
         *
         * `applies_to_customer_classes` is one of the two rules that decide
         * whether a code touches a given customer at all, and it was drawn on
         * NO surface a clerk could reach: not a list column, not a filter, and
         * not here. `BASE-E` is `["residential"]` and its Applicability tab
         * printed `Applies to Electric` and four Yes/No flags and never the
         * word `Residential`.
         *
         * ⚠ **THE VALUE WAS ALREADY SERVED** — `charge_row` returns it and the
         * wizard's steps 2 and 3 both render it — so this was a read that
         * stopped one layer short, not a missing endpoint. That is what made it
         * invisible: the tab rendered, every field it listed was correct, the
         * catalogue keys all resolved, and nothing in this repository compares
         * the fields a detail tab shows against the columns the row carries.
         *
         * ⚠ **IT IS THE RATE SCHEDULE'S OWN ROW, KEYS AND ALL, NOT A SECOND
         * SHAPE.** `RateScheduleDetail` already draws `Customer class` →
         * `Every customer class`, so the same fact is stated in the same words
         * for both priced objects. `[]` and a missing value both mean EVERY
         * class (`BR-RAT-108`) and are said so — an empty cell would read as a
         * restriction nobody can see.
         *
         * ⚠ **THIS IS NOT `chargeCustomerClasses` TWENTY LINES UP.** That reads
         * the size grid and answers *which classes are PRICED SEPARATELY*; this
         * answers *which classes the code REACHES AT ALL*. A code can reach
         * everybody and price one class differently, and confusing the two is
         * how a code that reaches everybody quietly stops reaching anybody.
         */
        {
          labelKey: "rating.plan.customerClassLabel",
          value:
            (row.applies_to_customer_classes ?? []).length === 0
              ? t("rating.rateDetail.field.customerClassAll")
              : (row.applies_to_customer_classes ?? [])
                  .map((code) => t(`rating.customerClass.${code}`, { defaultValue: code }))
                  .join(", "),
        },
        { labelKey: "rating.charges.taxableLabel", value: yesNo(t, row.taxable_default) },
        { labelKey: "rating.charges.autoApplyLabel", value: yesNo(t, row.auto_apply) },
        { labelKey: "rating.charges.waivableLabel", value: yesNo(t, row.waivable) },
        { labelKey: "rating.charges.separateLineLabel", value: yesNo(t, row.separate_line) },
      ],
    },
  };
}

/**
 * WHAT THE PREMISES TILE SAYS UNDER ITS NUMBER — CR-087.
 *
 * A count with no denominator and no unit is trivia (`tiles()`' own words). The
 * caption is what turns `1,284` into a fact: *every premises*, or *of 1,284*
 * when something narrowed it, or the reason there is no number at all.
 *
 * ⚠ **`everywhere` DESCRIBES THE BOUNDARY AND `narrowed` DESCRIBES THE REST.**
 * A tax that covers the whole utility and reaches Commercial customers only is
 * both `everywhere` and `narrowed`, and its count is NOT the total — so the
 * *every premises* caption is only right when neither is in play. `DEF-RAT-4672`
 * is that distinction got wrong one screen over, where the sentence blamed a
 * boundary that was correct.
 */
export function reachDetail(t: Translator, reach: TaxPremisesReach): ReactNode {
  if (reach.state === "pending") {
    return undefined;
  }
  if (reach.state === "unavailable") {
    return t("rating.definition.tax.reach.unavailable");
  }
  if (reach.state === "unresolvable") {
    return t("rating.definition.tax.reach.unchecked");
  }
  return reach.everywhere && !reach.narrowed
    ? t("rating.definition.tax.reach.everyPremises")
    : t("rating.definition.tax.reach.ofTotal", { total: reach.total });
}

// ── Tax or fee (§18 row 14) ────────────────────────────────────────────────

/**
 * HOW MANY PREMISES THIS TAX REACHES, as the tile can render it — CR-087.
 *
 * ⚠ **A COUNT AND ITS REASON TRAVEL TOGETHER.** Three of the five scope
 * mechanisms have no fact in this product to resolve against, so the true count
 * is `0`, and a bare zero on a tile reads as *"your boundary matches nobody,
 * fix your boundary"* rather than *"we cannot check this kind of boundary"*.
 * That is `MatchedPremisesNote`'s own argument, and this type carries the same
 * distinction into the strip instead of restating it.
 */
export type TaxPremisesReach =
  | { state: "pending" }
  | { state: "unavailable" }
  | { state: "unresolvable"; total: number }
  | { state: "counted"; count: number; total: number; everywhere: boolean; narrowed: boolean };

export function presentTax(
  row: TaxRow,
  t: Translator,
  accounts: readonly GlAccountRef[],
  regional: DefinitionRegional,
  /** Absent means the page has not asked yet — the tile draws `—`, never a
   *  plausible-looking number. */
  reach: TaxPremisesReach = { state: "pending" },
): DefinitionPresentation {
  // BR-RAT-087 / DEF-291 / DEF-364 again: `rate_display` carries "6.25%".
  const rate = taxRateDisplay(row);
  const rateText = t(rate.key, rate.params);
  const appliesTo =
    row.applies_to_services.length === 0
      ? t("rating.taxes.allServices")
      : row.applies_to_services
          .map((code) => t(`rating.service.${code}`, { defaultValue: code }))
          .join(", ");
  // DEF-273's inclusion list, read back: NONE ticked means EVERY class, and
  // saying "every customer class" is the only rendering of that fact a reader
  // can act on — an empty cell would read as a restriction nobody can see.
  const appliesToClasses =
    row.applies_to_customer_classes.length === 0
      ? t("rating.taxWiz.classes.all")
      : row.applies_to_customer_classes
          .map((code) => t(`rating.taxWiz.classes.${code}`, { defaultValue: code }))
          .join(", ");
  // ⚠ A BOUNDARY WE CANNOT EVALUATE IS NOT A BOUNDARY THAT MATCHES EVERYONE.
  // Three of the five mechanisms have no fact to resolve against, and the count
  // beside this line says so; here the scope is simply named as it was stored.
  const scopeText =
    row.premises_scope_kind === null || row.premises_scope_kind === ""
      ? t("rating.taxWiz.scope.everywhere")
      : `${t(`rating.taxWiz.scope.kind.${row.premises_scope_kind}`, {
          defaultValue: row.premises_scope_kind,
        })}${row.premises_scope_value ? ` · ${row.premises_scope_value}` : ""}`;

  return {
    title: row.name,
    // §2 part 2: `TAX · LOCAL · BEXAR COUNTY · V1`.
    eyebrow: [
      t("rating.definition.kind.tax"),
      enumLabel(t, "rating.taxes.level", row.jurisdiction?.level ?? null),
      row.jurisdiction?.name ?? t("rating.gl.unset"),
    ].join(" · "),
    subline: [
      <>
        {t("rating.effectiveFrom")}: {dateNode(row.effective_from, regional)}
      </>,
      `${t("rating.taxes.col.gl")}: ${glText(t, row.liability_gl_account_id, accounts)}`,
      // ⚠ **THE SENTENCE THE WHOLE ACTION RULING DEPENDS ON, AND IT WAS NOT
      // BUILT.** The blueprint gives all five detail screens ONE action set —
      // `Duplicate · Edit · Retire` — and page 33 says why the fourth name for
      // Edit went: *"What editing does still differs — and that belongs in a
      // sentence, not in a fourth name for the same button … the line under the
      // title says so before anyone presses it."* Without that line, `Edit` on
      // a live tax is an unlabelled trap: it opens a wizard that files a
      // CORRECTION — a new dated row with a written reason — where on a
      // scheduled tax the same button edits the row in place.
      //
      // ⚠ **IT REPLACES `rating.definition.tax.policy` RATHER THAN JOINING
      // IT**, which is B14 rule 32's description budget (one sentence per
      // section) and the drawing's own three-segment sub-line. Nothing is lost
      // that the page does not already say: the policy sentence's *"attaches by
      // jurisdiction and service rather than by plan"* half is the `Who it
      // reaches` block's own note, word for word, and its *"a liability, never
      // revenue"* half is what the `LIABILITY GL ACCOUNT` segment directly to
      // the left of this one names. The key is kept in the catalogue rather
      // than retired, because retiring a value without grepping its consumers
      // is `DEF-CUS-3653`.
      t("rating.definition.tax.editPolicy"),
    ],
    statusValue: row.status,
    statusStem: "rating.status",
    statusTone: activeStatusTone(row.status),
    kpis: tiles(
      "tax",
      t,
      [
        // Tile 1 — THE REACH, which §2 makes tile 1 on every one of the five
        // details. The blueprint draws the RATE first; that is tile ORDER in a
        // shared four-tile strip, which is form construction, so B14 rule 38
        // gives it to the kit and the divergence is recorded in the conformance
        // file. All four DRAWN FACTS are on the strip, which is the half the
        // drawing decides.
        row.used_by_plans,
        // Tile 2 — PREMISES IN SCOPE, from the engine's own predicate.
        reach.state === "counted" ? reach.count : reach.state === "unresolvable" ? 0 : NO_FIGURE,
        // Tile 3 — the rate, from the SERVER's display string.
        //
        // ⚠ **STATUS STOOD BETWEEN THESE TWO AND IS GONE (PO, *"show only one
        // status"*).** It rendered `row.status`, the same value the pill under
        // the title already draws.
        //
        // ⚠ **THE DRAWING SPLITS THIS ONE AND WE DELIBERATELY DO NOT.** The
        // frame puts `6.25%` in the value and `of the taxable amount` in the
        // caption; the product renders the whole sentence, from ONE catalogue
        // key per computation form (`rating.taxes.rate.percent|flat|perUnit`).
        // Splitting it means a second copy of half a money sentence in three
        // more keys × eleven catalogues, and two copies of a money string is
        // how a screen and a bill start disagreeing (DEF-364's own shape).
        // RECORDED as a divergence in the conformance file rather than built.
        rateText,
      ],
      [undefined, reachDetail(t, reach), undefined],
    ),
    panels: {
      // ⚠ THE FLAT LIST IS KEPT AS THE FALLBACK AND IS NOT WHAT DRAWS. `blocks`
      // below wins for the Overview; this stays so a reader of `panels` alone —
      // a test, a future fourth kind, the shell's own `fields === undefined`
      // branch — still gets a coherent answer rather than an empty tab.
      overview: [
        { labelKey: "rating.taxes.nameLabel", value: row.name },
        { labelKey: "rating.taxes.jurisdictionLabel", value: row.jurisdiction?.name ?? NO_FIGURE },
        { labelKey: "rating.taxes.kindLabel", value: enumLabel(t, "rating.taxes.kind", row.kind) },
        { labelKey: "rating.taxes.rateLabel", value: rateText },
      ],
    },
    // ── ONE TAB, FIVE BLOCKS (CR-087 B2, PO ruling 2026-09-08) ─────────────
    //
    // The order is the order a question about a tax arrives in: a clerk with a
    // customer on the phone asks WHAT IS THIS, then WHAT DOES IT SAY ON MY
    // BILL; an auditor asks WHAT IS IT CHARGED ON and WHO DOES IT REACH; and a
    // bookkeeper filing a return asks the last one. Four tabs used to answer
    // those five questions about one object.
    blocks: {
      overview: [
        {
          id: "identity",
          titleKey: "rating.definition.tax.block.identity",
          fields: [
            { labelKey: "rating.taxes.nameLabel", value: row.name },
            {
              labelKey: "rating.taxes.jurisdictionLabel",
              value: row.jurisdiction?.name ?? NO_FIGURE,
            },
            {
              labelKey: "rating.taxes.jurisdiction.level",
              value: enumLabel(t, "rating.taxes.level", row.jurisdiction?.level ?? null),
            },
            {
              labelKey: "rating.taxes.kindLabel",
              value: enumLabel(t, "rating.taxes.kind", row.kind),
            },
          ],
        },
        // ⚠ **`onBill` AND `remittance` WERE READ-ONLY BLOCKS HERE AND ARE
        // GONE — CR-087, `p030` §10.6.** They are not deleted as CONTENT: every
        // field they showed is drawn on the same screen, under the same
        // heading, in the same order, by `TaxRemittancePanel` — which is the
        // wizard's own field set, so the values are READ in the boxes that also
        // ENTER them. What has gone is the second copy.
        //
        // **The drawing has ONE block that both reads and writes** (page 23:
        // *"the tax's own page already has a `Remittance & filings` block where
        // they live, are read, and are now entered"*), and the product had two
        // of it plus a fourth heading — `Filing details` — that the drawing does
        // not have at all. So the filing form number, the account number with
        // the authority, the due-date rule, the collection allowance and the
        // bookkeeper's address each appeared TWICE on one screen, which is B14
        // rule 32's *"a row never repeats what its own control offers"*.
        //
        // ⚠ **THE FLAT `panels.overview` FALLBACK BELOW IS UNTOUCHED** and
        // still names the authority and the rate, so a reader of `panels` alone
        // — a test, a future fourth kind, the shell's `fields === undefined`
        // branch — still gets a coherent answer.
        {
          id: "taxed",
          titleKey: "rating.definition.tax.block.taxed",
          noteKey: "rating.definition.tax.block.taxedNote",
          fields: [
            { labelKey: "rating.taxes.rateLabel", value: rateText },
            // DEF-RAT-4662 — `Taxed`, not `Yes`. BR-RAT-036 / BR-RAT-005: only
            // usage and base can ever be in the base.
            {
              labelKey: "rating.taxes.baseUsage",
              value: taxedOrNot(t, row.base_includes_usage),
            },
            {
              labelKey: "rating.taxes.baseBase",
              value: taxedOrNot(t, row.base_includes_base),
            },
            // ⚠ DEF-RAT-4661 — THE FIELD THAT CHANGES THE ARITHMETIC AND WAS ON
            // NO READ SCREEN AT ALL. `taxes.discount_treatment` picks WHICH
            // subtotal this authority levies on: a $1.00 credit on a Bexar
            // County bill leaves the county line at $3.78 under one answer and
            // $3.80 under the other. It was collected on the wizard and shown
            // nowhere afterwards, so a clerk answering a customer or an auditor
            // checking a line could read every other term and not that one.
            // ⚠ THE SAME KEY THE WIZARD USES, deliberately: two wordings for one
            // statutory choice is how a screen and a form start disagreeing.
            {
              labelKey: "rating.taxWiz.discountTreatment.label",
              value:
                row.discount_treatment === null || row.discount_treatment === undefined
                  ? NO_FIGURE
                  : t(`rating.taxWiz.discountTreatment.${row.discount_treatment}`, {
                      defaultValue: row.discount_treatment,
                    }),
            },
            // BR-RAT-042 — MARGINAL: only the units ABOVE the threshold.
            { labelKey: "rating.taxes.appliesAboveLabel", value: row.applies_above_units ?? NO_FIGURE },
            {
              labelKey: "rating.taxWiz.rounding.label",
              // ⚠ RECORDED AND NOT HONOURED (DEF-385 / OQ-309). B4's rounding is
              // ❄️ FROZEN, so a blank here is not "nothing chosen" — it is the
              // rule bills actually use, and the screen says so rather than
              // printing a dash that reads as a gap.
              value:
                row.rounding_rule === null || row.rounding_rule === ""
                  ? t("rating.taxWiz.rounding.b4")
                  : t(`rating.taxWiz.rounding.${row.rounding_rule}`, {
                      defaultValue: row.rounding_rule,
                    }),
            },
          ],
        },
        {
          id: "reach",
          titleKey: "rating.definition.tax.block.reach",
          noteKey: "rating.definition.tax.block.reachNote",
          fields: [
            { labelKey: "rating.taxes.appliesToLabel", value: appliesTo },
            { labelKey: "rating.taxWiz.classes.label", value: appliesToClasses },
            { labelKey: "rating.taxWiz.scope.kindLabel", value: scopeText },
            { labelKey: "rating.effectiveFrom", value: dateNode(row.effective_from, regional) },
            { labelKey: "rating.effectiveTo", value: dateNode(row.effective_to, regional) },
          ],
        },
      ],
    },
  };
}

// ── Discount (§18 row 11) ──────────────────────────────────────────────────
//
// ⚠ THIS BLOCK USED TO SAY *"THERE IS NO PRESENTER HERE, AND THAT IS THE HONEST
// STATE OF THE PRODUCT"* — six tables and no route. `GET /discounts/{id}` is
// served now (CR-013 part 3, `apps/rating/api.discount_item`), so the sentence
// was true when it was written and is false today, and a comment claiming the
// state of the world is exactly the thing hard-won law 1 says goes stale. What
// replaced it is below.

export function presentDiscount(
  row: DiscountDetail,
  t: Translator,
  regional: DefinitionRegional,
): DefinitionPresentation {
  // BR-RAT-087: the SERVER's display string, unmodified. `15` arrives as
  // "15.00%" and `25` as "25.00" — a discount stores PERCENTAGE POINTS where a
  // charge stores a fraction, and scaling either one here would be client-side
  // money arithmetic on a value the server owns.
  const value = row.value_display ?? NO_FIGURE;
  const type = enumLabel(t, "rating.discounts.type", row.type);
  const scope = enumLabel(t, "rating.discounts.scope", row.applies_to);

  // ⚠ **BUILT ONCE, USED TWICE — CR-087 C2.** These are the BLOCKS of the
  // merged Overview AND the flat `panels` entries a reader of `panels` alone
  // still finds. Spelling them twice would be two places to add a cap to and
  // one place to forget it.
  // ⚠ **`CR-091-BRC01` — THE DETAIL VIEW SHOWED NO SERVICE AT ALL.** That is
  // the second of the PO's three asks (2026-09-10): *"we will ahve to dsplay in
  // detail view and also allow to enit it duing edit process"*. Before today a
  // discount narrowed to one service read exactly like one that applied to
  // everything, on the page a clerk opens to answer a customer.
  //
  // ⚠ **IT IS ALWAYS DRAWN, INCLUDING WHEN THE ANSWER IS *ALL SERVICES*.** The
  // drawn RULES line for this screen is *"a figure that does not exist is
  // stated with its reason and never drawn at the weight of one that does"*,
  // and the mirror of it holds here: a row that appears only on two of the
  // seven scopes is an absence nobody can see, so *All services* is stated
  // rather than left blank. It is true of every scope that does not narrow by
  // service — a `usage_only` discount reduces usage on all of them.
  const services: string =
    row.applies_to === "specific_services"
      ? (row.applies_to_services ?? []).length === 0
        // A stored row that names none should not exist — the write path
        // refuses it — so this reads as the absence it is rather than
        // silently as "everywhere", which is the reading the PO ruled out.
        ? NO_FIGURE
        : (row.applies_to_services ?? [])
            .map((code) => t(`rating.service.${code}`, { defaultValue: code }))
            .join(" · ")
      : row.applies_to === "one_service" && row.applies_to_service
        ? t(`rating.service.${row.applies_to_service}`, {
            defaultValue: row.applies_to_service,
          })
        : t("rating.discounts.servicesAll");
  const worth: readonly DefinitionField[] = [
      { labelKey: "rating.discounts.col.value", value },
      { labelKey: "rating.discounts.scopeLabel", value: scope },
      { labelKey: "rating.discounts.servicesLabel", value: services },
      // ⚠ EVERY CAP IS AN EM-DASH WHEN IT WAS NOT TYPED, NEVER A ZERO
      // (BR-RAT-075). Null means UNCAPPED, and a `0.00` here would describe a
      // programme that pays nothing — the opposite fact.
      { labelKey: "rating.discounts.capPerBill", value: row.cap_per_bill_display ?? NO_FIGURE },
      { labelKey: "rating.discounts.capPerYear", value: row.cap_per_year_display ?? NO_FIGURE },
      { labelKey: "rating.discounts.capLifetime", value: row.cap_lifetime_display ?? NO_FIGURE },
      // ⚠ AND THE FLOOR IS THE ONE EXCEPTION: BR-RAT-074 makes a floor of
      // zero MEAN that the bill may reach zero, so `0.00` here is a decision
      // someone took and is rendered as the figure it is.
      {
        labelKey: "rating.discounts.floorLabel",
        value: row.bill_floor_amount_display ?? NO_FIGURE,
      },
      // BR-RAT-073 — order is DATA, because "percentage-of-usage after a
      // usage allowance gives a different number than the reverse".
      {
        labelKey: "rating.discounts.precedenceLabel",
        value: row.stacking_precedence ?? NO_FIGURE,
      },
      { labelKey: "rating.discounts.budgetLabel", value: row.budget_cap_display ?? NO_FIGURE },
      {
        labelKey: "rating.discounts.budgetRemainingLabel",
        value: row.budget_remaining_display ?? NO_FIGURE,
      },
      {
        labelKey: "rating.discounts.grantedLabel",
        value: row.granted_to_date_display ?? NO_FIGURE,
      },
  ];
  const qualifies: readonly DefinitionField[] = [
      { labelKey: "rating.discounts.col.eligibility", value: row.eligibility ?? NO_FIGURE },
      // ⚠ **ONE ROW, BECAUSE IT IS ONE CONTROL — CR-087 C1 + C2.** The screen
      // that sets this stopped being two controls: *automatic* + *proof
      // required* could express a fourth combination that means nothing, so
      // DIS-02 step 3 asks it as one dropdown of the three answers that do.
      // Reading it back as two rows — *Enrolment · Apply and approve* above
      // *Proof required · Yes* — would make a clerk re-assemble on the page the
      // thing the form spared them, and it is the row that used to invite the
      // impossible pair. Same three sentences, from the same three keys.
      {
        labelKey: "rating.discounts.enrolmentModeLabel",
        // ⚠ **A READ SCREEN SHOWS THE FACT, NOT THE CHOOSER'S EXPLANATION —
        // `CR-087-p076` §6.** These three strings are written for a DROPDOWN,
        // where each option earns a clause telling a clerk what picking it
        // does: *"Apply and approve, with proof — a document is needed as
        // well"*. Read back as a VALUE on a fact grid, the clause is a hint
        // with nothing to hint at, and the frame draws the bare answer.
        //
        // ⚠ IT IS STILL ONE ROW AND NOT TWO (CR-087 C1). Splitting it back
        // into *Enrolment* above *Proof required* would make a clerk
        // re-assemble on the page the thing step 3 spared them, and it is the
        // pair that used to invite the impossible combination.
        value:
          row.enrolment_mode === undefined && row.proof_required === undefined
            ? NO_FIGURE
            : enrolmentFact(
                t,
                row.proof_required === true
                  ? "apply_and_approve_with_proof"
                  : row.enrolment_mode === "automatic"
                    ? "automatic"
                    : "apply_and_approve",
              ),
      },
      {
        labelKey: "rating.discounts.col.verification",
        value: enumLabel(t, "rating.discounts.verification", row.verification),
      },
      // ⚠ THE ACCEPTED PROOF KINDS ARE A POLICY LIST, NOT DOCUMENTS. BR-RAT-079
      // restricts income and medical PROOF and excludes it from general
      // document lists; neither discount read serves a document, an enrolment
      // or an account id at all, so there is nothing here to leak. What this
      // row states is which kinds the programme accepts, which is what a
      // clerk about to refuse an enrolment needs to read.
      {
        labelKey: "rating.discounts.proofKindsLabel",
        value:
          row.accepted_proof_kinds === undefined || row.accepted_proof_kinds.length === 0
            ? NO_FIGURE
            : row.accepted_proof_kinds
                // ⚠ ` · `, NOT `, ` — `CR-087-p076` §7. The frame draws
                // `Government ID · Birth certificate`, and a comma reads as
                // part of a document's own name where the mid-dot cannot.
                .map((kind) => t(`rating.discounts.proof.${kind}`, { defaultValue: kind }))
                .join(" · "),
      },
      {
        labelKey: "rating.discounts.recertLabel",
        value:
          row.recertification_months === undefined || row.recertification_months === null
            ? t("rating.discounts.recertNever")
            : t("rating.discounts.recertMonths", { count: row.recertification_months }),
      },
      { labelKey: "rating.effectiveTo", value: dateNode(row.effective_to ?? null, regional) },
  ];

  return {
    title: row.name,
    // §2 part 2: `DISCOUNT · SENIOR · PERCENTAGE · V2`. Unlike the charge, a
    // discount DOES carry a version table (`discount_versions`), so the version
    // number is real and is drawn — it is omitted only when the discount has no
    // version at all, which is a discount nobody has priced yet.
    eyebrow: [
      t("rating.definition.kind.discount"),
      row.code,
      type,
      ...(row.version_no === null ? [] : [`V${row.version_no}`]),
    ].join(" · "),
    subline: [
      <>
        {t("rating.effectiveFrom")}: {dateNode(row.effective_from, regional)}
      </>,
      // ⚠ **THE FUNDING SOURCE IS NOT HERE ANY MORE — `CR-087-p076` §5, and a
      // COMMENT TWENTY LINES BELOW HAS CLAIMED SO SINCE THE MERGE.** It read
      // *"the FUNDING SOURCE moved off the sub-line into `what it is`"*; it
      // moved INTO `what it is` and did not move OFF, so the same fact printed
      // twice on one screen and the file said otherwise. Hard-won law 1: a
      // comment claiming a change is not the change. The drawn sub-line is TWO
      // parts — the effective date and the overlay sentence — and page 77 says
      // so in as many words.
      // ⚠ CR-013 part 3's DEFINING sentence, and the one a reader of this screen
      // most needs: *"a discount is an overlay: it references the plan's normal
      // rates and reduces what the customer pays without altering the schedule
      // or charge code. The bill shows the full tariff amount and the reduction
      // as its own line, so subsidy granted is reportable."*
      t("rating.definition.discount.policy"),
    ],
    statusValue: row.status,
    statusStem: "rating.discounts.status",
    statusTone: discountStatusTone(row.status),
    kpis: tiles("discount", t, [
      // Tile 1 — the reach. ⚠ PLANS THAT OFFER IT, which is NOT the number of
      // accounts getting it (BR-RAT-069).
      row.plans,
      // Tile 2 — the GRANT. The only one of the two that reduces a bill.
      row.enrolled,
      // Tile 3 — **THE DENOMINATOR TAKE-UP NEEDS, CR-087 C2.** `31` enrolled
      // says nothing on its own; `31` against `86` offered is take-up, and low
      // take-up on an assistance programme is a finding a finance lead acts on.
      //
      // ⚠ IT SAYS **UNITS**, BECAUSE UNITS IS WHAT IT COUNTS. A plan is
      // assigned to a UNIT, so `offered_units` is a fact about plans; the
      // neighbouring `enrolled` says ACCOUNTS and counts accounts (enrolment
      // carries an FK to `customers.Account`). They are deliberately NOT drawn
      // as one fraction — a vacant unit has no account and cannot enrol.
      // `DEF-RAT-4664` is the same distinction got wrong on four other labels.
      //
      // ⚠ AND IT IS NOT `eligible`, WHICH IS WHAT `PRB-20` ASKS FOR.
      // Eligibility on a discount is a sentence a person typed and nothing
      // evaluates one. Offered is computable, eligible is not, and drawing the
      // first under the second's name would be a wrong number rather than a
      // missing one — the distinction the tile this replaced was built on.
      row.offered_units ?? NO_FIGURE,
      // Tile 4 — TEXT, per §2 (`TYPE · % of subtotal`): the type and what it
      // applies to, which together are the discount's defining characteristic.
      row.applies_to === null ? type : `${type} · ${scope}`,
    ],
    // ⚠ **EACH COUNT SAYS WHAT IT COUNTS — CR-087 C2.** Two different
    // populations, so the captions carry the words rather than the strip
    // implying a fraction between them.
    [
      undefined,
      t("rating.definition.discount.enrolledAccounts"),
      row.offered_units === undefined
        ? undefined
        : t("rating.definition.discount.offeredUnits", { count: row.offered_units }),
      undefined,
    ]),
    // ── ONE TAB, THREE BLOCKS (CR-087 C2, PO ruling 2026-09-08) ───────────
    //
    // ⚠ **TEN FIELDS OF TWO DIFFERENT KINDS WERE RUNNING AS ONE FLAT LIST.**
    // Merging three tabs into one grid would have put *Cap per year* beside
    // *Programme owner*. A clerk reads a discount as three questions, in the
    // order a call to the counter arrives: what it IS, what it is WORTH, who
    // QUALIFIES. Same `blocks` mechanism the tax merge uses above.
    //
    // ⚠ TWO FIELDS SWAPPED SIDES AND THAT IS THE POINT OF SPLITTING THEM: the
    // VALUE moved out of *what it is* into *what it is worth*, and the FUNDING
    // SOURCE moved off the sub-line into *what it is*.
    blocks: {
      overview: [
        {
          id: "identity",
          titleKey: "rating.definition.panel.identity",
          fields: [
            { labelKey: "rating.discounts.col.name", value: row.name },
            { labelKey: "rating.discounts.col.type", value: type },
            { labelKey: "rating.discounts.col.owner", value: row.programme_owner ?? NO_FIGURE },
            { labelKey: "rating.discounts.col.funding", value: row.funding_source ?? NO_FIGURE },
          ],
        },
        { id: "worth", titleKey: "rating.definition.panel.worth", fields: worth },
        {
          id: "qualifies",
          titleKey: "rating.definition.panel.qualifies",
          noteKey: "rating.definition.discount.notWorkedOut",
          fields: qualifies,
        },
      ],
    },
    panels: {
      // §2 part 8: the discount Overview is ONE panel deep, like the charge's.
      // ⚠ THE FLAT LIST IS THE FALLBACK AND IS NOT WHAT DRAWS — `blocks` above
      // wins. It stays so a reader of `panels` alone still gets a coherent
      // answer, exactly as the tax kind keeps its own.
      overview: [
        { labelKey: "rating.discounts.col.name", value: row.name },
        { labelKey: "rating.discounts.col.type", value: type },
        { labelKey: "rating.discounts.col.value", value },
        { labelKey: "rating.discounts.col.owner", value: row.programme_owner ?? NO_FIGURE },
      ],
      // The second tab is `Value & rules` — what this discount takes off, and
      // the four limits that stop it taking off too much.
      value: worth,
      // Eligibility and verification — CR-013 part 3's own detail tab, mapped
      // onto the shared shell's `applicability`.
      applicability: qualifies,
    },
  };
}

/**
 * The kinds an endpoint AND a presenter both answer for, listed rather than
 * derived from `DEFINITION_KINDS`.
 *
 * ⚠ THE DIFFERENCE BETWEEN THIS LIST AND `DEFINITION_KINDS` IS THE POINT. A
 * kind is declared up there — with its tabs, its route and its four KPI labels
 * — the moment the inventory names it, and its READ arrives later: the discount
 * spent from CR-013 P2 until CR-013 part 3 in exactly that state, six tables and
 * no route, with all five of its tabs saying what they waited for. Deriving this
 * list from that one would make a newly declared fourth kind claim a read it
 * does not have, and the shell would render an empty object as though it were
 * the truth. Adding a kind here is therefore a separate, deliberate line.
 */
export const SERVED_DEFINITION_KINDS: readonly DefinitionKind[] = ["charge", "discount", "tax"];

/**
 * Which kinds a presenter can answer for today — ONE fact, shared by the page
 * and by the tests, so "this kind has no read" cannot drift into two answers.
 *
 * ⚠ ALL THREE ARE SERVED NOW. This read `kind !== "discount"` from the day the
 * shell was built until `GET /discounts/{id}` existed.
 */
export function definitionIsServed(kind: DefinitionKind): boolean {
  return SERVED_DEFINITION_KINDS.includes(kind);
}

/** The four tiles a kind shows before (or without) any data — labels present,
 *  figures absent. The strip keeps its four-tile shape on every kind, which is
 *  what §2 asks for; nothing here invents a number. */
export function emptyKpis(kind: DefinitionKind, t: Translator): DefinitionKpis {
  return tiles(kind, t, [NO_FIGURE, NO_FIGURE, NO_FIGURE, NO_FIGURE]);
}
