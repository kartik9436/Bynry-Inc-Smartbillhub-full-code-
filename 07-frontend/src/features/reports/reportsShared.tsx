// ── Trace ──────────────────────────────────────────────
// Story:    US-LED-009 (S59 Account ledger report — params, the FULL source
//           vocabulary and the running balance) · US-LED-010 (S60 By-premises
//           summary)
//           Screens: S59 · S60
// Rules:    BR-LED-010 (account + date range → dated charges/payments +
//           running balance → PDF/CSV) · BR-LED-011 (by-premises billed /
//           collected / owed) · BR-REP-001 (basis label in every header) ·
//           BR-REP-006 (vocabularies enumerate the LIVE set, never hardcoded) ·
//           BR-REP-008 (Type = the FULL source vocabulary, so the report foots
//           to the AR tie-out — nothing invisible) · BR-REP-018 (downloads per
//           IS-11) · BR-SHL-011 (the URL grammar) · BR-SHL-020 (plain-language
//           failure) · BR-SHL-025 (a control this deployment cannot honour
//           renders disabled WITH its reason) · BR-SHL-044 (one page header)
// ───────────────────────────────────────────────────────
// The pieces the two ledger-owned report viewers are built from.
//
// **S59 AND S60 ARE NOT LIST SCREENS AND DO NOT PRETEND TO BE.** 13a's
// component map names `DataTable` for both; EP-LED-03's own capability matrix
// overrules it in a parenthesis that is easy to miss and is the whole design:
// *"(S36 is a dashboard tab — KPI/panel layout, no IS-2 list. S59/S60 are
// parameterized report viewers — parameter bar + result table per A14,
// downloads per IS-11.)"*
//
// That distinction has teeth. `DataTable` renders IS-2's sort headers, IS-3's
// search box and IS-9's pager, and every one of those is a promise the server
// makes: a sortable header sends `sort=`/`dir=` and a pager sends `page=`/`per=`.
// `apps/ledger/reporting.account_ledger` accepts none of them — it returns the
// window's rows in book order with a RUNNING BALANCE, which is a column that
// stops meaning anything the moment a user sorts by amount. So these two screens
// render a plain table, and the capability a user is not offered is one the
// server was never asked for (BR-SHL-010).
import { useMutation } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import type { ExportResource, LedgerUnavailable } from "@/api/endpoints";
import { requestListExport } from "@/api/endpoints";
import { DownloadButton } from "@/components/DownloadButton";
import { Panel } from "@/components/Panel";
import { useToast } from "@/components/Toast";
import type { Translator } from "@/features/tenancy/settingsShared";

import "@/features/ledger/finance.css";

// ── Routes ────────────────────────────────────────────────────────────────
// TENANT-RELATIVE.
//
// ⚠ **THESE USED TO BE BUILT FROM THE API's `{key}` CONSTANTS, and the comment
// here said that was so "the URL a user bookmarks and the endpoint the screen
// calls can never drift apart". The opposite happened (DEF-131).** One constant
// served two purposes, the hyphenated spelling was chosen for the URL — where
// it is right — and it silently became the API key, where it was wrong: the
// server has always registered `account_ledger` and `by_premises`, so every
// request 422'd and NEITHER SCREEN COULD RENDER FOR ANYONE for a day.
//
// They are now two vocabularies, deliberately, each owned by the layer that
// cares about it: the URL segment is a DISPLAY choice and lives here; the API
// key is a CONTRACT with the server and lives in `api/endpoints.ts`. A test
// pins the API keys against the server's own registry, which is the thing that
// can actually drift — a URL cannot drift from anything.
export const REPORTS_ROUTE = "/reports";
export const ACCOUNT_LEDGER_SEGMENT = "account-ledger";
export const BY_PREMISES_SEGMENT = "by-premises";
export const ACCOUNT_LEDGER_ROUTE = `${REPORTS_ROUTE}/${ACCOUNT_LEDGER_SEGMENT}`;
export const BY_PREMISES_ROUTE = `${REPORTS_ROUTE}/${BY_PREMISES_SEGMENT}`;

// ── The S46 viewer's URL segment ↔ API key pair (US-REP-002) ──────────────
//
// DEF-131's lesson, applied from the start rather than after a day of 422s: the
// URL segment is a DISPLAY choice (hyphens, because that is what a URL reads
// like) and the API key is a CONTRACT with the server (underscores, because
// that is what `apps/reports/catalog.py` registers). They are two vocabularies
// and the translation between them lives HERE, in one pair of functions, so a
// screen never spells either one by hand.
//
// A segment with no mapping is passed through UNCHANGED rather than defaulted:
// an unknown key reaches the server, which refuses it with VAL-005 and
// enumerates what it does serve. Guessing a nearby key here would turn a typo
// into a different report.
// ⚠ **THE MAP STOOD HERE UNTIL 2026-09-27 AND IS DELETED** (`CR-142-BRC07`
// `P0.7`, lane REP-P2-TAIL — the fifth of the six hand-typed maps). It held
// four rows, one per BUILT report, and the catalogue serves **46 definitions**:
// the other 42 fell through its `?? segment` fallback and worked by accident,
// which is the only reason nobody had noticed the map was 42 rows short.
//
// **THE TRANSLATION IS MECHANICAL, SO IT IS A FUNCTION.** Every one of the
// four rows was exactly `key.replace("_", "-")`, verified row by row:
// `ar-aging`↔`ar_aging`, `billing-register`↔`billing_register`,
// `revenue-by-service-rate`↔`revenue_by_service_rate`,
// `payments-by-method`↔`payments_by_method`. A per-report table whose every
// row is one rule is the map this task exists to delete.
//
// ⚠ **A KEY IS `[a-z0-9_]` AND NEVER CARRIES A HYPHEN, WHICH IS WHAT MAKES
// THE ROUND TRIP SAFE.** `apps/reports/models.py` validates the key column and
// `migrations/0003_seed_catalogue.py` seeds 46 snake_case keys; a key holding a
// hyphen would make `segment → key` ambiguous, so `reportKeyGrammar.test.ts`
// asserts the seeded vocabulary rather than trusting this sentence — hard-won
// law 1.
//
// A segment that does not round-trip is still passed through UNCHANGED, which
// is the behaviour the map had and the reason is unchanged: an unknown key
// reaches the server, which refuses it with VAL-005 and enumerates what it does
// serve. Guessing a nearby key here would turn a typo into a different report.

/** URL segment → the API key the server registered. */
export function keyForSegment(segment: string): string {
  return segment.replace(/-/g, "_");
}

/** API key → the tenant-relative route a library card links to. */
export function viewerRouteFor(key: string): string {
  return `${REPORTS_ROUTE}/${key.replace(/_/g, "-")}`;
}

// ── PO ruling 2026-09-28 · THE BUILDER HAS ITS OWN ADDRESS ────────────────
//
// ⚠ **A CHILD SEGMENT, AND THAT IS WHAT MAKES IT SAFE.** `/reports/:reportKey`
// is a catch-all over a name a TENANT chooses, which is why `custom`,
// `dashboard`, `scheduled` and `history` each had to be RESERVED before they
// could be routed — four ordinary English words a utility might name a report.
// `edit` is not a fifth of those. A report key is `[a-z0-9_]` and never holds a
// slash, so `/reports/edit` is still a report a utility may call *Edit* and
// `/reports/edit/edit` is that report's builder. **The signed reserved list
// stays at four**, which is the constraint `?edit=1` was reached for in the
// first place (`P5.3`'s own note in `ReportViewerPage`).
//
// ⚠ **AND THE SEGMENT IS WHY `DEF-REP-7073` CANNOT COME BACK.** That defect
// was `searchFrom` rebuilding the whole query string from the report's own
// parameters, so `edit` — which is not one of them — was deleted by every
// control on the screen, and the editor closed on a keystroke. A PATH is not
// rebuilt by `searchFrom` and cannot be dropped by it. The fix is structural
// rather than a flag one more function has to remember.
export const REPORT_EDITOR_SEGMENT = "edit";

/** API key → the tenant-relative address of 2·2, the builder, for that report.
 *
 *  ⚠ **ONE SOURCE.** `App.tsx`'s route, the `Edit` door on 2·1, the redirect
 *  that keeps old `?edit=1` bookmarks working and the tests that assert a
 *  built address all read THIS — never a literal repeated four times, which is
 *  how `fire` failed silently in two hand-typed lists (the skill's §12). */
export function editorRouteFor(key: string): string {
  return `${viewerRouteFor(key)}/${REPORT_EDITOR_SEGMENT}`;
}

/** The ROUTE PATTERN `App.tsx` registers for 2·2, tenant-relative.
 *
 *  ⚠ **A TEST ASSERTS A BUILT ADDRESS AGAINST THIS, NEVER AGAINST A LITERAL
 *  REPEATED IN THE TEST.** A hold-expiry test once asserted a screen was
 *  registered at an address while the router mounted it somewhere else, and
 *  both opened onto *"not built yet"* with every check green (hard-won law 7,
 *  *looking at the wrong thing*). One string, read by the router and by the
 *  assertion, is what removes that. */
export const REPORT_EDITOR_ROUTE_PATTERN = `${REPORTS_ROUTE}/:reportKey/${REPORT_EDITOR_SEGMENT}`;

// ── `DEF-REP-7640` · WHERE `+ Build your own` GOES ────────────────────────
//
// ⚠ **THE BUTTON WENT TO `/reports/custom` AND THAT IS THE CATALOGUE IT IS
// STANDING ON.** `P5.10` mounted the catalogue's Custom sub-tab at that
// address on 2026-09-27, and the Phase 5 hold on this control expired the same
// day pointing at it — so from `/reports/custom` the press was a no-op and
// from `/reports` it switched sub-tab to an empty list. The Product Owner
// pressed it on deployed `v2.388.0` and nothing happened. A live control in
// front of a screen that does not exist is hard-won law 2's mirror.
//
// **PO ruling 2026-09-28, verbatim: *"Opens the editor on a blank definition,
// then Save as"*.** `ReportEditorPage` already exists and is already the
// builder; what it could not do was START without a report key, because it
// resolves one from `useParams().reportKey` through `keyForSegment`.
//
// ⚠ **`custom/new` RATHER THAN A FIFTH RESERVED WORD, AND THE REASON IS THE
// SIGNED LIST.** `/reports/new/edit` was the obvious address and it would have
// needed `new` added to `RESERVED_REPORT_SEGMENTS` **and** to
// `apps/reports/definitions.RESERVED_KEYS`, because `:reportKey` is a
// catch-all over a name a TENANT chooses and *New* is an ordinary English word
// a utility could name a report. `custom` is ALREADY on both lists and the
// server already refuses it BY NAME, so no report can ever hold that key and
// nothing under `/reports/custom/` can collide with one. **The signed reserved
// list stays at four**, which is the same argument `REPORT_EDITOR_SEGMENT`
// records one constant above.
//
// ⚠ **AND IT READS AS WHAT IT IS**: a new report under the tab where custom
// reports live. `/reports/custom/new` is three segments and `/reports/:key` is
// two, so neither can swallow the other whatever the declaration order.
export const REPORT_BUILDER_NEW_ROUTE = `${REPORTS_ROUTE}/custom/new`;

// ── `DEF-REP-6898` · WHAT A CLERK READS WHEN A REPORT CANNOT BE PRODUCED ───
//
// ⚠ **THE CARD AND THE VIEWER SAID DIFFERENT THINGS ABOUT THE SAME REPORT.**
// The catalogue card said *"This report cannot be produced yet."* — calm, true,
// six words — and the viewer, two clicks later, drew the finance error panel:
// *"The finance figures could not be loaded / Something went wrong on our side.
// Nothing was saved."* on a METER READS report. Twenty-seven of the forty-six.
//
// The card resolved its sentence in `ReportLibraryPage` and the viewer had no
// sentence at all, so there was no one place to correct. There is now: both
// surfaces call this, one of them with the catalogue row's `reason_code` and
// the other with the same code off the refusal envelope's `params`. Two
// derivations of one fact is how they came to disagree (B14 rule 43 — a piece
// of UI is built as something importable, and this is the sentence behind two
// of them).
//
// ⚠ **THE FALLBACK IS THE POINT AND IT IS NOT DEFENSIVE.** An unknown reason
// code renders the six-word sentence rather than the server's engineering
// prose: B14 rule 33 puts RATIONALE at ZERO WORDS ON SCREEN, so a paragraph
// about grain and datasets is REMOVED rather than shortened.

/** The one sentence, keyed on the machine reason code the server sends. */
export function unavailableSentence(reasonCode: string | null, t: Translator): string {
  if (reasonCode === null) {
    return t("reports.library.unavailableGeneric");
  }
  return t(`reports.library.reason.${reasonCode}`, {
    defaultValue: t("reports.library.unavailableGeneric"),
  });
}

/**
 * True when the SERVER said this report cannot be produced — never when it
 * said something broke.
 *
 * ⚠ **IT ASKS ABOUT THE `message_key` AND NOT ABOUT THE STATUS.** A 422 is
 * also what an inverted date range and an unknown bill type answer, and those
 * are the clerk's to fix; this one is not. `reports.library.unavailableGeneric`
 * is the key `apps/reports/api._cannot_be_produced` sends and it is the card's
 * own key, which is what makes the two surfaces agree by construction.
 */
export function isNotProducible(error: unknown): boolean {
  return isApiError(error) && error.messageKey === "reports.library.unavailableGeneric";
}

/** The `reason_code` off that refusal, for `unavailableSentence`. */
export function refusalReasonCode(error: unknown): string | null {
  if (!isApiError(error)) {
    return null;
  }
  const code = error.params?.reason_code;
  return typeof code === "string" ? code : null;
}

// ── BR-REP-008's vocabulary, as catalogue keys ────────────────────────────

/**
 * The server sends BR-REP-008's WORD (`bill`, `write-off`, `manual JE`); the
 * screen renders the tenant's language. Two of the ten words carry characters a
 * dotted catalogue key cannot: a space and a hyphen. Slugged here, in one
 * place, rather than in the cell — the alternative is a screen that renders
 * eight types translated and two in English.
 *
 * An UNKNOWN word is NOT slugged into a familiar one. `type_mapped=false` is the
 * read model saying it met a source it has no word for, and BR-REP-008's whole
 * point is that the report foots to the tie-out with *nothing invisible* — so
 * the raw value shows through, marked.
 */
export function sourceTypeKey(vocabularyWord: string): string {
  return `reports.ledger.type.${vocabularyWord.replace(/[^A-Za-z0-9]+/g, "_").toLowerCase()}`;
}

export function sourceTypeLabel(word: string, mapped: boolean, t: Translator): string {
  if (!mapped) {
    return t("reports.ledger.type.unmapped", { source: word });
  }
  return t(sourceTypeKey(word), { defaultValue: word });
}

// ── The IS-11 download row (BR-REP-018) ───────────────────────────────────

/**
 * ⚠ **THIS CONTROL WAS DISABLED WITH A REASON UNTIL 2026-09-24. IT WORKS NOW
 * (`P4.5`), AND THE REASON SENTENCE IS DELETED RATHER THAN REWORDED.**
 *
 * The history is worth keeping because it is a shape this repo repeats. The
 * sentence began as *"Downloads are not built yet: nothing on this deployment
 * writes a report file."* **Its second clause was already false** —
 * `apps/tenancy/exports.py` had been writing report files since August — so
 * `P2.10` narrowed it on the MORNING of 2026-09-24 to say that THESE reports
 * have no download, which was true and which stopped sending a finance officer
 * to an administrator for a switch that does not exist.
 *
 * **`P4.1` then registered them**, so by the afternoon the narrowed sentence
 * was false too. `apps/ledger/finance_exports.py` registers `account_ledger`,
 * `by_premises` and `customer_statement` at startup beside four others, and
 * `POST /exports` answers 202 for each. A refusal outliving the thing it
 * refused is hard-won law 2's mirror, and the gap between the two edits was
 * about six hours.
 *
 * **The sentence is DELETED, not shortened.** B14 rule 33 puts RATIONALE at
 * **zero words on screen** — *"why the product works this way, why a control is
 * absent"* — and cutting a *why* sentence to six words keeps the breach and
 * makes it terser. A working download needs nothing beside it; the control is
 * the whole statement.
 *
 * ⚠ **`P2.10`'s *"One change, three screens"* still holds, which is why this
 * stays a COMPONENT rather than becoming three copies** (B14 rule 43).
 * `ByPremisesReportPage`, `CustomerStatementPage` and `AccountLedgerReportPage`
 * each pass their own resource and their own filters into this one control.
 *
 * The `pdf` prop is NOT passed. IS-11 says CSV always and PDF where layout
 * matters; this deployment has no PDF renderer of any kind, and offering a
 * format nothing can produce is worse than offering one.
 *
 * **`disabled` is still reachable and is still true when it fires** — while the
 * report has not loaded there is nothing to export, and the control says so by
 * being unpressable rather than by carrying a sentence.
 */
export function ReportDownloads(props: {
  resource: ExportResource;
  filters?: Record<string, string>;
  columns?: readonly string[];
  disabled?: boolean;
  /**
   * ⚠ **THE PAGE'S CLIENT, AND IT IS NOT OPTIONAL PLUMBING.** `requestListExport`
   * defaults to the module-level `api`, so a component that does not pass one
   * reaches the real network from inside a test and from inside any screen
   * mounted against a seam. The first draft of this component omitted it; the
   * hold-expiry test caught it by recording zero POSTs against a client that
   * records every one — which is the whole reason that test asserts the CALL
   * and not just that the button is pressable.
   */
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  const toast = useToast();
  const request = useMutation({
    mutationFn: () =>
      requestListExport(
        {
          resource: props.resource,
          filters: props.filters ?? {},
          columns: props.columns,
        },
        props.client ?? api,
      ),
    // US-SHL-012: a toast fires on a COMMITTED action and never on a failure.
    // The server answers 202 and a job writes the file, so the honest statement
    // is that the download was ASKED FOR — not that it has arrived.
    onSuccess: () => toast(t("reports.export.queued")),
  });

  return (
    <DownloadButton
      disabled={props.disabled === true || request.isPending}
      onDownload={() => request.mutate()}
    />
  );
}

// ── The parameter bar (A14's own, ported as layout) ───────────────────────

export function ReportParamBar(props: { children: ReactNode; actions: ReactNode }) {
  return (
    <div className="fin-params">
      {props.children}
      <div className="fin-params-actions">{props.actions}</div>
    </div>
  );
}

/**
 * Every gap the response named, listed under the report it belongs to.
 *
 * ⚠ **A BULLET WITH NO WORDS IN IT IS NOT DRAWN, AND NEITHER IS A PANEL WHOSE
 * BULLETS ARE ALL WORDLESS (`DEF-LED-6729`).** The Product Owner, on deployed
 * v2.351.84, reported a *"What this does not cover"* section rendering two
 * EMPTY bullets. **B14 rule 32**: a stated absence is CLOSED by default and it
 * is a STATEMENT — an empty bullet list is neither a statement nor an absence,
 * it is a heading promising something it has nothing to say about, which is
 * strictly worse than saying nothing.
 *
 * ⚠ **AND SAYING WHAT THIS GUARD DOES *NOT* PROVE MATTERS MORE THAN THE GUARD.**
 * Every caller today renders through `gapSentence`, which falls back to
 * `finance.gap.unknown` and therefore CANNOT return an empty string — so this
 * is a shape the branch tip could not produce, and lane REV could not reproduce
 * it on 2026-09-25 (the bad-debt caveats on that screen rendered two bullets
 * WITH words: *"By reason and month only."* and *"Small automatic write-offs
 * are not counted."*, read out of the live DOM). `render` is a PROP, so the
 * guarantee lives in every caller rather than here, which is exactly the shape
 * hard-won law 1 is about. The guard makes it structural instead.
 * `BadDebtCaveats` already resolves its lines before drawing, for this reason
 * and in these words; this is the same decision, taken once, in the kit.
 */
export function ReportGapList(props: {
  gaps: readonly LedgerUnavailable[];
  render: (gap: LedgerUnavailable) => string;
  title: string;
}) {
  // Resolved BEFORE the panel is drawn, never inside the map: a heading must
  // not render over a list that turns out to be empty one line later.
  const lines = props.gaps
    .map((gap) => ({ code: gap.code, words: props.render(gap).trim() }))
    .filter((line) => line.words !== "");
  if (lines.length === 0) {
    return null;
  }
  return (
    <Panel>
      <div className="fin-panel-head">
        <h3>{props.title}</h3>
      </div>
      <ul className="fin-gap-list">
        {lines.map((line) => (
          <li key={line.code} className="fin-absent-reason">
            {line.words}
          </li>
        ))}
      </ul>
    </Panel>
  );
}

// ── `DEF-REP-6902` / `DEF-REP-6903` · HOW MANY DIGITS A PERSON READS ────────
//
// ⚠ **THEY LIVE HERE AND NOT IN `ReportViewerPage` BECAUSE THE KPI BAND NEEDS
// THEM TOO, AND THE VIEWER IMPORTS THE BAND.** Putting them in the page and
// importing back would be a cycle; a second copy in the band would be two
// answers to *how many decimals is money* on one screen, which is the shape of
// the defect these exist to close.
//
// ⚠ **NOT ONE OF THEM ROUNDS ANYTHING UPSTREAM.** CLAUDE.md: *round only at
// finalization/display*. The wire keeps every stored digit, the query returns
// stored decimals, and this is the last inch before a pair of eyes.

/**
 * A QUANTITY AS A METER READS IT, NOT AS THE COLUMN STORES IT
 * (`DEF-REP-6903`).
 *
 * ⚠ **`46754.000000 kWh` REACHED A CLERK**, and `41.200000 kW` for a demand of
 * 41.2. Hard rule 3 was honoured — the unit IS beside the number — and the
 * PRECISION was nobody's: the repo's one display rule, hard rule 2, is written
 * about money and percentages and says nothing about a quantity.
 *
 * ⚠ **IT TRIMS AND IT NEVER ROUNDS, AND THE DIFFERENCE IS THE WHOLE OF IT.**
 * A quantity column declares NO scale — `datasets.Column.scale` is 4 for money,
 * 6 for a percentage and `None` for every quantity — so there is no declared
 * number of places to render to, and picking one here would invent a precision
 * the dataset never claimed. Dropping trailing zeros loses no information at
 * all: `46754.000000` and `46754` are the same reading, and `41.200000` reads
 * `41.2` rather than `41.20`. A quantity that genuinely carries digits keeps
 * every one of them.
 *
 * Anything that is not a plain decimal string is returned UNCHANGED — a value
 * we cannot parse is shown as it arrived, never dropped.
 */
export function trimQuantity(value: string): string {
  if (!/^-?\d+\.\d+$/.test(value)) return value;
  return value.replace(/(\.\d*?)0+$/, "$1").replace(/\.$/, "");
}

/**
 * A MONEY FIGURE AT TWO PLACES WITH NO CURRENCY CODE (`DEF-REP-6902`).
 *
 * The fallback for the one case `MoneyCell` cannot serve: a report whose
 * window holds more than one currency, or an empty book, publishes
 * `currency: null` and no figure may wear a code it did not come from
 * (`DEF-081` / `DEF-099`). The DIGITS are still hard rule 2's — two.
 *
 * ⚠ **IT ROUNDS FOR DISPLAY AND WRITES NOTHING BACK**, which is the same inch
 * `MoneyCell` occupies and the same one CLAUDE.md permits: *round only at
 * finalization/display*. Unparseable input is returned as it arrived.
 */
export function moneyDisplay(amount: string): string {
  const parsed = Number(amount);
  return Number.isFinite(parsed) ? parsed.toFixed(2) : amount;
}

/**
 * A PERCENTAGE AT TWO PLACES, WITH ITS SIGN (`DEF-REP-6902`).
 *
 * CLAUDE.md hard rule 2: a percentage is STORED to six places and **DISPLAYS
 * two**. `service_order_activity`'s ON TIME tile printed `100.000000`.
 *
 * ⚠ **TRIMMED HERE AND NEVER ROUNDED UPSTREAM.** The wire keeps all six,
 * because a report that rounded before it was displayed could not be
 * reconciled against the figure it came from — the same posture
 * `ReportKpiTile` already takes for the tile half of this defect.
 */
export function percentDisplay(value: string | number): string {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? `${parsed.toFixed(2)}%` : `${String(value)}%`;
}


// ── `DEF-REP-7070` · A FIELD IS NAMED IN WORDS, IN ONE PLACE ────────────────
//
// ⚠ **THE VIEWER WAS GIVEN WORDS AND THE EDITOR WAS NOT** (`DEF-REP-6901`
// fixed the table's headings on 2026-09-27; screen 2·2 was not in that
// commit). The Product Owner opened `/{tenant}/reports/statement?edit=1` and
// read `posted_on`, `account_code`, `account_na…`, `narrative`, `source_type`
// — stored column names, in English, in all eleven languages, on a screen
// whose whole job is to let a clerk choose between them.
//
// ⚠ **IT IS THE VIEWER'S OWN PATH, EXTRACTED — NOT A SECOND ONE.**
// `reportTableConfig` read `t("reports.col.<name>", { defaultValue: name })`
// inline, so the editor could only have had words by writing that expression a
// second time. Two copies of *how a column is named* is how a heading and its
// own checkbox come to disagree, which is the class of defect this whole wave
// is about. Both call THIS.
//
// ⚠ **A FILTER AND A DIMENSION ARE NAMED HERE TOO, AND THEY ARE NOT COLUMNS.**
// `from`, `to`, `service`, `level` are the parameter bar's vocabulary and have
// been authored under `reports.param.*` since `P2.7`; `reports.col.*` has no
// entry for them. So the lookup is ordered — the column catalogue, then the
// parameter catalogue — and the raw name survives only where neither
// catalogue has authored the word yet. **A raw name is therefore a MISSING
// CATALOGUE ENTRY and never a design**, which is why it is left visible rather
// than blanked: a blank is a silence a clerk cannot report.

/**
 * The words for one served name — a column, a measure, a filter or a grouping
 * dimension — in the reader's own language.
 *
 * Precedence: the utility's own rename (the caller applies that; it wins over
 * everything) → `reports.col.<name>` → `reports.param.<name>` → the raw name.
 */
export function reportWord(name: string, t: Translator): string {
  const column = t(`reports.col.${name}`, { defaultValue: "" });
  if (column !== "") {
    return column;
  }
  const param = t(`reports.param.${name}`, { defaultValue: "" });
  if (param !== "") {
    return param;
  }
  return name;
}


// ── Lifecycle ─────────────────────────────────────────────
// packet: US-LED-009@a1f04c9 (story+rules snapshot — EP-LED-03 US-LED-009 + US-LED-010; 09-ledger/02-business-rules.md BR-LED-010/011; 12-reports/02-business-rules.md BR-REP-001/006/008/018; 11b §1's `GET /reports/{key}` row; 05-prototype/UtilityBilling.html lines 4220-4290)
// generated: 2026-08-11 by story-coder (W5 finance SCREENS lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest✔ · vite build✔ · run_gates✔ — see the lane report
// exceptions: (1) NEITHER report renders `DataTable`, although 13a's component map names it for both: EP-LED-03's capability matrix says S59/S60 are *parameterized report viewers — parameter bar + result table*, and DataTable's sort headers and pager are promises `apps/ledger/reporting.py` never made. Sorting an account ledger by amount destroys the running-balance column outright · (2) the IS-11 downloads render DISABLED with their reason: `POST /reports/{key}/export` is contracted and served by nothing · (3) the two `{key}` slugs come from `api/endpoints.ts` and are this lane's PROPOSAL — no document in the repo enumerates the vocabulary
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
