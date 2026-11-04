// ── Trace ──────────────────────────────────────────────
// Story:    US-PAY-013 (S34 Outstandings: every account that owes money, AR
//           high→low, the ageing KPI strip that foots to the rows, the bucket
//           and bad-address filters, and the bulk toolbar) · US-PAY-012 (the
//           S35 Write-off request modal this list opens, and the approval that
//           posts it) · US-PAY-014 (the collection ladder, driven over an S34
//           selection — the ONLY caller the engine has)
//           Screens: S34 (AppShell sidebar → Payments → Outstandings) · S35
// Rules:    BR-PAY-029 (AR high→low; bulk reminder/notice/plan/write-off) ·
//           BR-PAY-032 (days late = as_of − the OLDEST UNPAID bill's due date;
//           null when no unpaid bill carries one) · BR-PAY-021 (money POSTED by
//           the due date is not outstanding, even before it clears) ·
//           BR-PAY-015 (the autopay column is enrolment state — there is NO
//           retry and no charge action anywhere) · BR-PAY-018 (bad address is a
//           column AND a filter) · BR-PAY-017 (the collection tier and its next
//           step) · BR-PAY-020 (a write-off is INITIATED here and APPROVED in
//           finance; nothing money-bearing happens at initiation) ·
//           BR-CUS-015 (`accounts.balance` is a CACHE — this list never reads
//           it) · BR-REP-011 (DSO belongs to reports; served null with its
//           reason) · BR-TEN-043 (`as_of` is asked for, never taken from a
//           clock) · BR-SHL-010 (an undeclared capability is not rendered) ·
//           BR-SHL-012 (the A18 states) · BR-SHL-020 (plain-language failure) ·
//           BR-SHL-023 (one money formatting path) · BR-SHL-025 (a control this
//           deployment cannot honour renders DISABLED WITH its reason)
// ───────────────────────────────────────────────────────
// S34 — who owes money, worst first.
//
// `apps/payments/outstandings.py` landed on 2026-08-15 with the whole read
// model in it — balances computed from bills and allocations rather than from
// the cached column, BR-PAY-032's days-late anchor, the five ageing bands, the
// notice summary, the collection tier, the plan status, autopay and bad address
// — and `PaymentsPage.tsx` rendered the *awaiting* panel over the top of it.
// Its own story file says so in as many words: **"THE S34 TAB IS STILL THE
// PLACEHOLDER PANEL … no human can see any of it"**. This is the caller.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THIS SCREEN REFUSES TO DO
// ══════════════════════════════════════════════════════════════════════════
//   · **It never renders a DSO number.** `totals.dso_days` is always null and
//     the tile shows the reason: BR-REP-011 ratifies the formula and REPORTS
//     own the read, so a figure computed here could disagree with S36's.
//   · **It never renders a 0% share.** A bucket in an empty ledger has no
//     share — a share of nothing is undefined, and "0%" is a claim.
//   · **It never shows a "Retry autopay" action.** BR-PAY-015 makes v1
//     capture-only; the prototype's row option is superseded and no charging
//     path exists anywhere for a button to call.
//   · **It never treats `days_late: null` as 0.** A bill nobody can place in
//     time cannot be aged, the account still owes the money, and `problems[]`
//     names the case.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getOutstandings, requestWriteOff, runCollections } from "@/api/endpoints";
import type {
  CollectionsRunResult,
  OutstandingRow,
  OutstandingsResponse,
  WriteOffRequested,
} from "@/api/endpoints";
import { AgeingCards } from "@/components/AgeingCards";
import type { AgeingBand, AgeingTone } from "@/components/AgeingCards";
import { Button } from "@/components/Button";
import { DatePickerField, FormModal, SelectField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { KPIStrip } from "@/components/KPIStrip";
import { MoneyCell } from "@/components/MoneyCell";
import type { KpiTile } from "@/components/KPIStrip";
import { DataTable } from "@/components/DataTable";
import { FilterBar } from "@/components/FilterBar";
import { clientPage } from "@/components/clientTable";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableRequestState } from "@/components/tableTypes";
import { LoadingSkeleton } from "@/components/StateFrame";
// Still used by the two RESULT panels below — the write-off receipt and the
// ladder run — which are unchanged by `P4.7`'s redraw of the list above them.
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkAnchor } from "@/components/Surfaces";
import { useToast } from "@/components/Toast";
import { Panel } from "@/components/Panel";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { revenueArViewPath } from "@/features/ledger/financeViewStrip";
import { useNavigate } from "react-router-dom";

import { useTenantPath } from "@/routing/tenantPath";
import { SEND_NOTICE_ROUTE } from "./SendNoticeWizard";

import { DebtorBulkBar } from "./DebtorBulkBar";
import {
  DEBTORS_DEFAULT_SORT,
  DEBTOR_TABLE_SPEC,
  debtorTiles,
  debtorsTableConfig,
} from "./debtorsTable";
import {
  Money,
  ProblemList,
  WRITE_OFF_REASON_CODES,
  bucketLabel,
  collectionTierLabel,
  ladderSkipLabel,
  sumDecimalStrings,
  writeOffReasonLabel,
} from "./paymentsShared";

import "./payments.css";

// ── Pure pieces (provable without a browser or a network) ──────────────────

export const outstandingsQueryKey = (asOf: string, bucket: string, badAddress: boolean) =>
  ["payments", "outstandings", asOf, bucket, badAddress] as const;

/** The bucket filter's options — A2 §S34's four bands plus `current`, in the
 *  server's own order (`outstandings.AGEING_BUCKETS`). */
export const BUCKET_FILTER_VALUES = ["current", "1-30", "31-60", "61-90", "90+"] as const;

/**
 * How OLD each band is, which is what its colour names — never how much money
 * is in it (`P0.11`, and `AgeingCards` says why in full).
 *
 * The five come from the SERVER (`outstandings.AGEING_BUCKETS`) and a band it
 * does not know falls to `neutral` rather than guessing a tier: a grey card is
 * a card a clerk reads as ordinary, and the failure of a wrong tone is that
 * ninety-day debt looks ordinary.
 */
export function ageingTone(bucket: string): AgeingTone {
  if (bucket === "61-90" || bucket === "90+") {
    return "danger";
  }
  if (bucket === "1-30" || bucket === "31-60") {
    return "warning";
  }
  return "neutral";
}

/**
 * The five debtor bands, for the kit's `AgeingCards` (`P0.11`).
 *
 * ⚠ **ONE BUILDER, TWO READERS — `ageingTiles` BELOW COMPOSES THIS.** A second
 * pass over `view.ageing` computing the same share sentence a different way is
 * how two figures for one fact start to drift (decision log, 2026-09-05), and
 * `OutstandingsTab.test.tsx` asserts the tie-out through `ageingTiles`, which
 * would then be testing the copy nobody renders.
 */
export function ageingBands(
  view: OutstandingsResponse,
  currency: string | null,
  t: Translator,
): AgeingBand[] {
  return view.ageing.map((tile) => {
    const detail =
      tile.share === null
        ? t("payments.outstandings.tileNoShare", { accounts: tile.accounts })
        : t("payments.outstandings.tileDetail", { accounts: tile.accounts, share: tile.share });
    return {
      id: tile.bucket,
      label: bucketLabel(tile.bucket, t),
      value:
        currency === null ? (
          // The server serves these amounts with no CHAR(3) code. An
          // unlabelled figure on a collections screen is one a clerk acts on.
          <span className="cus-awaits">{t("payments.money.currencyUnavailable")}</span>
        ) : (
          // ⚠ **NO `basis` MARKER ON A CARD, AND THIS WAS FOUND IN A BROWSER
          // AND BY NOTHING ELSE (CLAUDE.md hard-won law 6).** `ageingTiles`
          // passes `basis="posting"` and is right to: a KPI tile is wide and
          // the marker is BR-REP-001's. A CARD is a fifth of that width and
          // `.cell-money` is `white-space: nowrap`, so `$7,938.35 POSTING DATE`
          // ran off the edge and was CLIPPED on two of the five cards. Every
          // check passed over it — `tsc`, six card cases, 386 payments cases,
          // the route-B compiler check — because not one of them reads rendered
          // output.
          //
          // The FACT is not lost, it is said ONCE instead of five times, which
          // is B14 rule 32's description budget: the *Owing as of* field above
          // these cards carries *"The business day this ageing uses."* And the
          // blueprint's own card is the money and the share, with no marker.
          <MoneyCell amount={tile.amount} currency={currency} />
        ),
      detail,
      tone: ageingTone(tile.bucket),
    };
  });
}

/**
 * The ageing strip (A2 §S34's five tiles), as `KPIStrip` reads it.
 *
 * The tiles are a FOLD OVER THE ROWS on the server, not a second query, which
 * is what makes US-PAY-013 TC-1's *"KPI strip bucket totals tie to the rows
 * exactly"* true rather than hoped for. Nothing is re-added here.
 *
 * The fifth tile is the prototype's **DSO**, and it renders its REASON rather
 * than a number: `totals.dso_days` is always null (BR-REP-011 is reports') and
 * a plausible 18.4 computed here is exactly the fabricated figure the defect
 * log keeps a family for.
 *
 * ⚠ **THE FIVE BANDS ARE NO LONGER DRAWN THROUGH THIS ON SCREEN (`P0.11`).**
 * The blueprint draws them as CARDS that filter — *"five cards, each a filter …
 * lighter than the tiles above"* — so the screen renders `AgeingCards` from
 * `ageingBands` above, and this composition is kept because the TIE-OUT is
 * asserted through it (`OutstandingsTab.test.tsx` TC-1) and because the DSO
 * tile, which is a READ and not a filter, still needs a strip to sit in.
 */
export function ageingTiles(
  view: OutstandingsResponse,
  currency: string | null,
  t: Translator,
): KpiTile[] {
  const tiles: KpiTile[] = view.ageing.map((tile) => {
    const detail =
      tile.share === null
        ? t("payments.outstandings.tileNoShare", { accounts: tile.accounts })
        : t("payments.outstandings.tileDetail", { accounts: tile.accounts, share: tile.share });
    if (currency === null) {
      // The server serves these amounts with no CHAR(3) code (see
      // `paymentsDisplayCurrency`). An unlabelled figure on a collections
      // screen is a figure a clerk would act on.
      return {
        id: tile.bucket,
        label: bucketLabel(tile.bucket, t),
        value: <span className="cus-awaits">{t("payments.money.currencyUnavailable")}</span>,
        detail,
      };
    }
    return {
      id: tile.bucket,
      label: bucketLabel(tile.bucket, t),
      // BR-PAY-021: outstanding is judged on the POSTING date — money posted by
      // the due date has already left this list.
      money: { amount: tile.amount, currency, basis: "posting" },
      detail,
    };
  });
  tiles.push({
    id: "dso",
    label: t("payments.outstandings.kpi.dso"),
    value: <span className="cus-awaits">{t("payments.outstandings.dsoUnavailable")}</span>,
  });
  return tiles;
}

/** The write-off request body's client-side shape (the SERVER re-refuses all
 *  of it with its own rule ids — this only saves a round trip). */
export function writeOffSchema(t: Translator) {
  return z.object({
    reason: z.string().min(1, t("payments.writeOff.reasonRequired")),
    // US-PAY-012 §5 marks the note *Required* and so does `writeoffs._note`: it
    // is the only place a human explains a decision that permanently reduces
    // receivables, and a bad-debt report whose rows say nothing cannot be
    // reviewed by anybody.
    note: z.string().min(1, t("payments.writeOff.noteRequired")),
    requested_on: z.string().min(1, t("payments.writeOff.dateRequired")),
  });
}

// ⚠ **`CreditApplied` AND `isZeroDecimal` MOVED TO `debtorsTable.tsx` ON
// 2026-09-23 (`P4.7`), AND ARE RE-EXPORTED HERE SO NO IMPORTER MOVES.** They
// are CELL-level pieces and the cells are declared in that file now; leaving
// them here would have made `debtorsTable` import this module and this module
// import `debtorsTable`, which ES modules tolerate and which is a live hazard
// the next refactor steps in. `concessionOnScreen.test.tsx` and
// `OutstandingsTab.test.tsx` both go on importing them from here.
export { CreditApplied, isZeroDecimal } from "./debtorsTable";

/**
 * *"Write off balances"* — the prototype's own modal title.
 *
 * **One request PER ACCOUNT, in a loop, and that is the rule rather than an
 * implementation choice.** `writeoffs.py` records it: *"BULK IS THE CALLER'S
 * LOOP (US-PAY-012 TC-3): one request per account, one approval decision over
 * the reviewed set, per-account results. A single row spanning four accounts
 * could not post four balanced entries or close four plans."*
 *
 * Each account is written off at ITS OWN balance — the figure this list already
 * computed from bills and allocations. The server checks it again against the
 * same computation and refuses anything larger, because writing off more than a
 * customer owes puts revenue into bad debt that nobody was ever charged.
 */
export function WriteOffModal(props: {
  client: ApiClient;
  rows: readonly OutstandingRow[];
  currency: string | null;
  today: string;
  dateFormat: RegionalProps["dateFormat"];
  onClose: () => void;
  onRequested: (results: WriteOffRequested[]) => void;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const [reason, setReason] = useState<string>(WRITE_OFF_REASON_CODES[0]);
  const [note, setNote] = useState("");
  const [requestedOn, setRequestedOn] = useState("");
  const total = sumDecimalStrings(props.rows.map((row) => row.balance));
  // DEF-SHL-3964 — the date picker below spelled its own seed fallback. The
  // caller still supplies `dateFormat` and still wins; the tenant's published
  // setting is what stands behind it now, instead of "MM/DD/YYYY".
  const { dateFormat } = useRegional(props);

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    try {
      const results: WriteOffRequested[] = [];
      for (const row of props.rows) {
        results.push(
          await requestWriteOff(
            {
              account_id: row.account_id,
              amount: row.balance,
              reason: reason as (typeof WRITE_OFF_REASON_CODES)[number],
              note,
              requested_on: requestedOn === "" ? props.today : requestedOn,
            },
            props.client,
          ),
        );
      }
      props.onRequested(results);
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t("payments.writeOff.title")}
      kicker={t("payments.writeOff.kicker", { count: props.rows.length })}
      schema={writeOffSchema(translate)}
      values={{ reason, note, requested_on: requestedOn === "" ? props.today : requestedOn }}
      submitLabel={t("payments.writeOff.submit")}
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      {/* The prototype's "This cannot be undone easily" card, as the rule
          actually stands: a write-off row is append-only (BR-PAY-002) and an
          erroneous one is corrected by a new row, never an edit. */}
      <p className="pay-form-note">{t("payments.writeOff.warning")}</p>
      <ul className="pay-writeoff-rows">
        {props.rows.map((row) => (
          <li key={row.account_id}>
            <span className="pay-id">{row.account_no ?? t("payments.row.noAccountNo")}</span>
            <Money amount={row.balance} currency={props.currency} />
          </li>
        ))}
      </ul>
      <p className="pay-form-note">
        {t("payments.writeOff.total")}{" "}
        {total === null ? (
          <span className="cus-awaits">{t("payments.money.sumUnavailable")}</span>
        ) : (
          <Money amount={total} currency={props.currency} />
        )}
      </p>
      <SelectField
        id="reason"
        label={t("payments.writeOff.reason")}
        value={reason}
        onChange={setReason}
        options={WRITE_OFF_REASON_CODES.map((code) => ({
          value: code,
          label: writeOffReasonLabel(code, translate),
        }))}
        required
        // BR-SHL-025: the two prototype options this product will not accept
        // are named here rather than offered and refused on submit.
        help={t("payments.writeOff.reasonHelp")}
      />
      <TextField
        id="note"
        label={t("payments.writeOff.note")}
        value={note}
        onChange={setNote}
        multiline
        required
        help={t("payments.writeOff.noteHelp")}
      />
      <DatePickerField
        id="requested_on"
        label={t("payments.writeOff.requestedOn")}
        value={requestedOn}
        onChange={setRequestedOn}
        prefill={props.today}
        dateFormat={dateFormat}
        required
        help={t("payments.writeOff.requestedOnHelp")}
      />
      {/* The prototype's GL-account picker (6100 Bad Debt / 6110 Allowance) is
          NOT offered: the posting picks finance's designated bad-debt account
          through the ledger seam (BR-PAY-020), and a picker here would let a
          clerk post bad debt where finance did not designate it. */}
      <p className="pay-form-note">{t("payments.writeOff.glNote")}</p>
    </FormModal>
  );
}

// ── The result panel: requested write-offs, and where they go next ─────────

/**
 * What a write-off request DID — which is nothing, and saying so is the whole
 * control (US-PAY-012 TC-1: *"pending-approval record; NO balance/ledger effect
 * yet"*).
 *
 * ⚠ **THE APPROVE CONTROL USED TO BE HERE AND IS GONE (DEF-100).** It sat
 * beside the request that had just minted the id, because `/write-offs` was
 * POST-only and this panel was the only place in the product that could hold a
 * write-off id at all — so the person who asked could approve in the same
 * breath and BR-PAY-020's *"initiated in Payments, approved in FINANCE"* was
 * true on paper and nowhere else. `GET /write-offs` now serves the queue, so
 * the control lives on S36 where the rule puts it, and this panel says where it
 * went rather than silently losing a button.
 *
 * **This is a SCREEN separation, not a new authorisation.** BR-PAY-037 is
 * CONFIRMED and unchanged: the same user holding the approver role MAY still
 * initiate and approve in v1, with both acts recorded distinctly; enforced
 * separation-of-duties is v2. The server refuses a non-admin approval and
 * always did (`@require_role(SYSTEM_ADMIN)`) — that is the authorisation, and
 * moving a button neither adds to it nor stands in for it (BR-SHL-025).
 */
export function WriteOffResultPanel(props: {
  requested: readonly WriteOffRequested[];
  currency: string | null;
  /** Where the second person does their half — the S36 Finance queue. */
  financeQueueHref: string;
  onDismiss: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="pay-result" role="status">
      <div className="pay-result-head">
        <h3>{t("payments.writeOff.requestedTitle", { count: props.requested.length })}</h3>
        <Button variant="ghost"  onClick={props.onDismiss}>
          {t("payments.result.dismiss")}
        </Button>
      </div>
      <p className="pay-result-ledger">{t("payments.writeOff.nothingMoved")}</p>
      <ul className="pay-writeoff-rows">
        {props.requested.map((row) => (
          <li key={row.id}>
            <Money amount={row.amount} currency={props.currency} />
            <StatusPill tone="warning">{t("payments.writeOff.status.requested")}</StatusPill>
          </li>
        ))}
      </ul>
      {/* WHERE THE SECOND PERSON DOES THEIR HALF. A link, not a button that
          approves: this screen is the requester's and BR-PAY-020 puts the
          decision on the Finance queue. */}
      <p className="pay-result-ledger">{t("payments.writeOff.approveInFinance")}</p>
      <InlineLinkAnchor href={props.financeQueueHref}>
        {t("payments.writeOff.openFinanceQueue")}
      </InlineLinkAnchor>
      <ProblemList
        problems={props.requested.flatMap((row) => row.problems)}
        title={t("payments.problems.title")}
      />
    </div>
  );
}

// ── The collections run result (US-PAY-014) ────────────────────────────────

/**
 * What the ladder did over the selection — and what it deliberately did not.
 *
 * Every SKIP is rendered, because J4 step 2 requires each one to be recorded
 * and a silent exclusion is the one thing a collections trail may not contain:
 * a customer who was never chased has to have an answer to *"why not?"*.
 */
export function CollectionsRunPanel(props: {
  run: CollectionsRunResult;
  rowsByAccount: Record<string, OutstandingRow>;
  onDismiss: () => void;
}) {
  const { t } = useTranslation();
  const name = (accountId: string): string =>
    props.rowsByAccount[accountId]?.account_no ?? accountId;
  return (
    <div className="pay-result" role="status">
      <div className="pay-result-head">
        <h3>{t("payments.collections.ranTitle", { count: props.run.stepped.length })}</h3>
        <Button variant="ghost"  onClick={props.onDismiss}>
          {t("payments.result.dismiss")}
        </Button>
      </div>
      {props.run.stepped.length > 0 && (
        <ul className="pay-writeoff-rows">
          {props.run.stepped.map((step) => (
            <li key={step.account_id}>
              <span className="pay-id">{name(step.account_id)}</span>
              <StatusPill tone="warning">{collectionTierLabel(step.rung, (k, p) => t(k, p))}</StatusPill>
            </li>
          ))}
        </ul>
      )}
      {props.run.skipped.length > 0 && (
        <ul className="pay-writeoff-rows">
          {props.run.skipped.map((skip) => (
            <li key={skip.account_id}>
              <span className="pay-id">{name(skip.account_id)}</span>
              <span className="met-muted">{ladderSkipLabel(skip.reason, (k, p) => t(k, p))}</span>
            </li>
          ))}
        </ul>
      )}
      <ProblemList problems={props.run.problems} title={t("payments.problems.title")} />
    </div>
  );
}

// ── The tab ────────────────────────────────────────────────────────────────

export interface OutstandingsTabProps extends RegionalProps {
  client?: ApiClient; // test seam — screens never build their own transport
  /** BR-TEN-043: the business day this list is asked about. REQUIRED, held by
   *  the page, and shown on screen — the API reads no clock and neither does
   *  this screen (OQ-153 / DEF-082: the tenant timezone cannot be chosen yet,
   *  so nothing may pretend to know the utility's business day). */
  asOf: string;
  onAsOfChange: (next: string) => void;
  /** The tenant's CHAR(3), read off the payments list — see
   *  `paymentsDisplayCurrency`. Null renders a stated absence, never a guess. */
  currency: string | null;
  /** BR-SHL-025: null = this role may act; a sentence = the control is disabled
   *  WITH that sentence. The server refuses regardless. */
  writeBlockedReason: string | null;
}

export function OutstandingsTab(props: OutstandingsTabProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const queryClient = useQueryClient();
  const fireToast = useToast();
  const { timeZone, dateFormat } = useRegional(props);

  const [bucket, setBucket] = useState("");
  const [selected, setSelected] = useState<readonly string[]>([]);
  const [writingOff, setWritingOff] = useState(false);
  const [requested, setRequested] = useState<WriteOffRequested[] | null>(null);
  const [run, setRun] = useState<CollectionsRunResult | null>(null);
  // BR-SHL-011's vocabulary, held here rather than in the URL: this is a TAB
  // inside `PaymentsPage`, whose address already carries the tab id, and a
  // second writer on the same query string is a race rather than a feature.
  // `P4.1` is where it moves onto the request.
  const [tableState, setTableState] = useState<TableRequestState>(() => ({
    q: "",
    sort: DEBTORS_DEFAULT_SORT.sort,
    dir: DEBTORS_DEFAULT_SORT.dir,
    page: 1,
    per: DEFAULT_PAGE_SIZE,
    filters: {},
  }));

  const listQuery = useQuery({
    queryKey: outstandingsQueryKey(props.asOf, bucket, tableState.filters.bad_address === "only"),
    queryFn: () =>
      getOutstandings(
        { asOf: props.asOf, bucket, badAddressOnly: tableState.filters.bad_address === "only" },
        client,
      ),
    // A missing route is not a flaky network, and neither is a refused role.
    retry: false,
  });

  // DEF-100: there is NO approve mutation on this screen any more. It lived
  // here only because nothing could list a pending write-off, so the requester
  // held the only id. `GET /write-offs` now serves the Finance queue and the
  // decision belongs to whoever is looking at it (BR-PAY-020).

  const collections = useMutation({
    mutationFn: (accountIds: readonly string[]) =>
      runCollections({ account_ids: [...accountIds], as_of: props.asOf }, client),
    onSuccess: (result) => {
      setRun(result);
      fireToast(t("payments.collections.ranToast", { count: result.stepped.length }));
      void queryClient.invalidateQueries({ queryKey: ["payments"] });
    },
  });

  const view = listQuery.data;
  // ⚠ **`DEF-PAY-6269` — THE READ THAT COMPUTED THE FIGURES NAMES THEIR UNIT.**
  // This screen read `props.currency`, which `PaymentsPage` derives from
  // `GET /payments` — so a tenant with issued bills and NO PAYMENTS YET had a
  // null there and every amount on the list, the four tiles and the five
  // ageing cards rendered the absence sentence. `GET /outstandings` has
  // carried the tenant's CHAR(3) since `DEF-099`; the fix landed on the server
  // and the screen was never re-pointed at it.
  //
  // The prop stays as the FALLBACK rather than being removed: a deployment
  // whose payments read answers and whose outstandings read does not is a real
  // state, and two sources that agree are better than one that can be absent.
  // `null` from both still refuses — hard rule 2 is a PAIR and a bare figure on
  // a collections screen is one a clerk acts on.
  const currency = view?.currency ?? props.currency;
  const rows: readonly OutstandingRow[] = view?.rows ?? [];
  const rowsByAccount: Record<string, OutstandingRow> = {};
  for (const row of rows) {
    rowsByAccount[row.account_id] = row;
  }
  const selectedRows = rows.filter((row) => selected.includes(row.account_id));

  /** Open 7·3d over the current selection — ONE function, two controls.
   *
   *  ⚠ **ROUTER STATE, NOT THE URL.** A selection is N account ids and B14
   *  rule 31 keeps a database id out of the address bar — the same reasoning
   *  that makes a counter resolve by its CODE. The STEP is URL state (`?step=`)
   *  and the SELECTION is not, so a hard refresh lands on an honest empty step 1
   *  with the way back to Debtors rather than on a silent empty send.
   *
   *  ⚠ `asOf` and the tenant's CURRENCY travel with it because the wizard has
   *  neither and must not guess: `BR-TEN-043` makes the business date an
   *  argument and never a clock, and `OutstandingRow` carries no currency at
   *  all (`BR-TEN-042` gives a tenant one).
   *
   *  ⚠ **IT IS THIS SCREEN'S RESOLVED `currency`, NOT `props.currency`, AND
   *  THE DIFFERENCE IS `DEF-PAY-6269`.** The prop is derived from
   *  `GET /payments` and is null on a tenant with issued bills and no payments
   *  yet; the resolved one prefers the CHAR(3) that `GET /outstandings` — the
   *  read that computed these very balances — carries. Handing the wizard the
   *  prop would have reproduced that defect one screen downstream, on a letter
   *  that states an amount owed, and every suite would have passed. `null`
   *  still travels as `null` and the wizard still refuses: it is a PAIR either
   *  way. */
  function openSendNotice(): void {
    navigate(tenantPath(SEND_NOTICE_ROUTE), {
      state: { accounts: selectedRows, asOf: props.asOf, currency },
    });
  }
  const selectedTotal = sumDecimalStrings(selectedRows.map((row) => row.balance));
  const failed = listQuery.isError && view === undefined;

  function toggle(accountId: string): void {
    setSelected((current) =>
      current.includes(accountId)
        ? current.filter((id) => id !== accountId)
        : [...current, accountId],
    );
  }

  const config = debtorsTableConfig(translate, { timeZone, dateFormat }, currency, tenantPath, {
    selected,
    onToggle: toggle,
  });
  // ⚠ **THE SEAM, NAMED IN ONE PLACE.** `GET /outstandings` takes no `q`,
  // `sort`, `page` or `per` — that is `P4.1`, and it is the `NFR-3` breach
  // `CLAUDE.md` names by name. Until it lands, the toolbar's five controls are
  // honoured HERE, over the rows the server sent whole. **This line is what
  // `P4.1` deletes**, and nothing above or below it changes when it does.
  const paged = clientPage(rows, tableState, DEBTOR_TABLE_SPEC);

  return (
    <div className="pay-outstandings">
      {/* BR-TEN-043 / the README's first rule: `as_of` is REQUIRED and is not
          defaulted silently in the client. The field is on screen with today
          proposed into it, exactly as the Record form proposes its posting
          date — a clerk reconciling yesterday asks for yesterday and gets
          yesterday's ageing rather than a figure that moved at midnight.

          ⚠ **IT IS NOT IN THE TABLE'S TOOLBAR AND MUST NOT GO THERE.** B14
          rule 12 names five things a toolbar holds and `DEF-1700` deleted the
          second row a screen grew for its dimension controls. `as_of` is not a
          dimension of the LIST, it is the question the whole page asks — the
          tiles, the cards and the rows all move with it — so it sits above
          them all, where the drawing puts it. */}
      <div className="pay-toolbar">
        {/* The help line was cut on 2026-09-03: *"too much ocntent Owing as
            of* The business day to age the debt on..."*. B14 rule 32 gives a
            field ONE sentence; the rule it was explaining is BR-TEN-043 and it
            lives in the comment above, which is what a comment is for. */}
        <DatePickerField
          id="as_of"
          label={t("payments.outstandings.asOf")}
          value={props.asOf}
          onChange={props.onAsOfChange}
          dateFormat={dateFormat}
          required
          help={t("payments.outstandings.asOfHelp")}
        />
      </div>

      {failed ? (
        <Panel role="alert">
          <h3>{t("payments.outstandings.failedTitle")}</h3>
          <p className="met-panel-hint">{apiErrorText(listQuery.error, translate)}</p>
          <Button variant="secondary" onClick={() => void listQuery.refetch()}>
            {t("states.failed.retry")}
          </Button>
        </Panel>
      ) : view === undefined ? (
        <LoadingSkeleton variant="kpi" />
      ) : (
        <>
          {/* ⚠ **① FOUR TILES, NOT NINE — the drawing's own first annotation,
              and it is a RULE finding rather than a taste one.** The page
              carried two KPI blocks: accounts owing, total owed, a *Sort*
              label, the five ageing bands and a DSO tile.

              **The five bands are one row of CARDS now and each is a filter**
              (`P0.11`), so the information became a control instead of taking
              four times the height to say the same thing.

              **And two tiles left the KPI area ON RULES, NOT TASTE.** *Sort ·
              Largest balance first* was a static label standing in for a
              control — it belongs in the table as a ⇅ header (rule 13), and
              now it is one. *Days sales outstanding · Reported on the Finance
              page* is a STATED ABSENCE, and rule 32 makes a stated absence a
              closed disclosure, never a tile. The DSO figure is still refused
              for BR-REP-011's reason and `problems[]` still carries it. */}
          <KPIStrip kpis={debtorTiles(view, currency, translate)} />

          {/* ④ **FIVE CARDS, EACH A FILTER** — *"the ageing bands, lighter than
              the tiles above, and they narrow the list"*. They drive the
              SERVER's `f.bucket`, which is the one filter `GET /outstandings`
              already accepts, so this narrowing is real rather than a page
              slice. */}
          <AgeingCards
            label={t("payments.outstandings.bucketFilter")}
            bands={ageingBands(view, currency, translate)}
            selectedId={bucket === "" ? null : bucket}
            onSelect={(id) => {
              setBucket(id ?? "");
              setSelected([]);
              setTableState((current) => ({ ...current, page: 1 }));
            }}
          />

          {/* ⑤ **THE TOOLBAR SWAPS IN PLACE** — *"the same row, its contents
              replaced; no second bar, no layout jump"*. `SelectionToolbar` is
              that row and `DataTable` owns its own; the screen draws ONE of
              them at a time, which is what makes the swap a swap. */}
          {selected.length > 0 ? (
            <DebtorBulkBar
              label={t("payments.outstandings.bulkLabel")}
              count={t("payments.outstandings.selected", { count: selected.length })}
              totalText={
                selectedTotal === null ? (
                  <span className="cus-awaits">{t("payments.money.sumUnavailable")}</span>
                ) : (
                  <Money amount={selectedTotal} currency={currency} />
                )
              }
              // ⚠ **NO ELIGIBLE COUNT AND NO ELIGIBILITY SENTENCE, AND THAT
              //    IS THE HONEST ANSWER RATHER THAN A MISSING FEATURE
              //    (`DEF-PAY-6264`).** The drawing reads *"2 can be sent · 1 is
              //    on a medical hold"* and draws *Send notice 2*. The medical
              //    hold is this read's OWN declared absence — `problems[]` says
              //    *"the medical-hold column is unavailable"* — and no served
              //    field carries BR-PAY-017's other stop conditions per row.
              //
              //    A count over the one stop condition that IS served would
              //    read as a count over all of them, which is precisely the
              //    failure the blueprint files as a gap: a confirm that asks
              //    *"Send 5 notices?"* when it is about to send two and
              //    silently skip three. `countedLabel` draws the bare verb on a
              //    null and the `eligibility` slot draws nothing when absent,
              //    so both were built for exactly this.
              sendableCount={null}
              steppableCount={null}
              // ⚠ **`DEF-PAY-6252`'s HOLD EXPIRES HERE — `CR-138-BRC07` `P4.14`
              // + `P4.27` BUILT 7·3d, AND THE SENTENCE GOES IN THE SAME COMMIT
              // AS THE SCREEN.** The comment above this line named the missing
              // wizard by name and by page: *"What is still missing is **7·3d
              // Send a notice**, the three-step wizard the drawing puts behind
              // this button (p087) — that is `P4.14`. So the control stays
              // disabled…"* **It is `SendNoticeWizard` now, routed at
              // `SEND_NOTICE_ROUTE`**, so that sentence is deleted rather than
              // left standing above a live control. Leaving a refusal that has
              // become untrue is the shape that cost the customer portal six of
              // its eight front doors.
              sendNoticeReason={props.writeBlockedReason}
              onSendNotice={openSendNotice}
              moveOnReason={props.writeBlockedReason}
              moveOnWorking={collections.isPending}
              onMoveOn={() => collections.mutate(selected)}
              writeOffReason={props.writeBlockedReason}
              onWriteOff={() => setWritingOff(true)}
              // ⚠ **THE SAME DOOR, AND BOTH ARE RELEASED FOR ONE REASON:** this
              // slot carried the SAME sentence, and a refusal that has become
              // untrue is a defect wherever it sits. A reminder IS a tone —
              // *friendly* — and the tone is step 2's choice, so both controls
              // open the wizard and the clerk chooses there. The bar keeps both
              // controls: which six it holds and where they sit is `P4.11`'s
              // decision and it is not reopened here.
              reminderReason={props.writeBlockedReason}
              onReminder={openSendNotice}
              // ⚠ **`DEF-PAY-6253` — S24 HAS BEEN LIVE SINCE 2026-08-16.** The
              // sentence said the wizard *"is not built yet"* and it is built,
              // routed and reachable. What this BAR cannot do is offer a plan
              // over a SELECTION: S24 takes one account. The door for one
              // account is on 7·2, where the drawing puts it.
              planReason={t("payments.outstandings.action.planNeedsOneAccount")}
              onPlan={() => undefined}
              // ⚠ `P4.17` owns this string WORD FOR WORD. Re-checked
              // 2026-09-23, still true, and its pairing invariant asserts it.
              siteVisitReason={t("payments.outstandings.action.fieldVisitUnavailable")}
              onSiteVisit={() => undefined}
              labels={{
                sendNotice: t("payments.outstandings.action.notice"),
                moveOn: t("payments.outstandings.action.runLadder"),
                writeOff: t("payments.outstandings.action.writeOff"),
                reminder: t("payments.outstandings.action.reminder"),
                plan: t("payments.outstandings.action.plan"),
                siteVisit: t("payments.outstandings.action.fieldVisit"),
                more: t("table.rowActions.more"),
                clear: t("payments.outstandings.action.clear"),
              }}
              onClear={() => setSelected([])}
            />
          ) : null}

          {run !== null && (
            <CollectionsRunPanel
              run={run}
              rowsByAccount={rowsByAccount}
              onDismiss={() => setRun(null)}
            />
          )}
          {requested !== null && (
            <WriteOffResultPanel
              requested={requested}
              currency={currency}
              // ⚠ **`DEF-PAY-6329` — THIS OPENED THE GENERAL LEDGER.** It read
              // `tenantPath(FINANCE_ROUTE)`, and `CR-060` T10 moved the bare
              // `/finance` from Revenue & AR to the TRIAL BALANCE. A clerk
              // pressed *"Open the Finance queue"*, landed on S56, found no
              // queue, and reported the write-off screen as MISSING — which is
              // the PO's report, word for word. Nothing 404'd and nothing went
              // red, because the wrong address is a real working screen.
              //
              // **`financeTabPath` rather than a second literal**: that
              // function is the one place deciding where a Finance tab lives
              // (`financeTabFrom`'s docstring says so), so if the queue's tab
              // moves again this door moves with it instead of rotting.
              // `WriteOffQueuePanel` is inside `RevenueArPage`, and
              // `writeOffQueueDoor.dom.test.tsx` asserts this destination by
              // address, by screen id and by the component mounted there.
              //
              // ⚠ **AND IT NOW NAMES THE VIEW (`P2.23`, 2026-09-24).** `P2.18`
              // split Revenue & AR into five views with **Services** as the
              // landing one, so this door — *"Open the Finance queue"* — would
              // have opened the revenue-by-service table. **That is
              // `DEF-PAY-6329` happening a second time to the same button:**
              // the reader presses it, gets a real working screen with no queue
              // on it, and reports the write-off screen as missing. The address
              // went one level deeper; `revenueArViewPath` still composes
              // `financeTabPath`, so there is still no literal here.
              financeQueueHref={tenantPath(revenueArViewPath("writeoffs"))}
              onDismiss={() => setRequested(null)}
            />
          )}
          {collections.isError && (
            <Panel role="alert">
              <h3>{t("payments.collections.failedTitle")}</h3>
              <p className="met-panel-hint">{apiErrorText(collections.error, translate)}</p>
            </Panel>
          )}

          {/* ⚠ **THE FIVE BREACHES CLOSE HERE, AND THEY CLOSE BECAUSE THIS IS
              THE KIT'S TABLE RATHER THAN A HAND-ROLLED ONE.** Rule 12's
              toolbar, rule 13's ⇅ headers, rule 14's ▦ chooser, rule 15's two
              row actions plus an overflow and rule 16's pagination footer are
              all `DataTable`'s, on every list that uses it. The screen
              declares its columns and its filters; it draws none of the
              chrome. */}
          <DataTable
            config={config}
            state={tableState}
            onStateChange={(next) => {
              setTableState(next);
              // A row that has scrolled off the page a clerk is looking at is a
              // row they cannot see they have selected — and the bulk bar's
              // total would then name money off screen.
              setSelected([]);
            }}
            rows={paged.page}
            totalRows={paged.total}
            loading={listQuery.isFetching && view === undefined}
            // ⚠ DECLARING `config.filters` IS NOT RENDERING THEM, AND A
            // BROWSER IS WHAT SAID SO. `DataTable` takes the chips as a
            // COMPOSED slot (IS-4) rather than building them from the config,
            // so the three filters this screen declares were reachable by
            // nobody: `+ Filter ▾` simply was not on the toolbar, and every
            // suite passed because a declared filter is a config field that
            // reads back perfectly. The `ReadsListPage` wiring, exactly.
            filterBarSlot={
              <FilterBar
                filters={config.filters ?? []}
                state={tableState}
                onStateChange={(next) => {
                  setTableState(next);
                  setSelected([]);
                }}
              />
            }
            empty={{
              title: t("payments.outstandings.emptyTitle"),
              helper: t("payments.outstandings.emptyHelper"),
            }}
          />

          {/* The README's fourth rule. Each entry names something the product
              genuinely cannot answer — the DSO tile, the medical-hold column,
              an unpaid bill with no due date — and a screen that drops them is
              the comment that claims a guarantee (hard-won law 1). */}
          <ProblemList problems={view.problems} title={t("payments.problems.title")} />

          {writingOff && (
            <WriteOffModal
              client={client}
              rows={selectedRows}
              currency={currency}
              today={props.asOf}
              dateFormat={dateFormat}
              onClose={() => setWritingOff(false)}
              onRequested={(results) => {
                setWritingOff(false);
                setRequested(results);
                fireToast(t("payments.writeOff.requestedToast", { count: results.length }));
                void queryClient.invalidateQueries({ queryKey: ["payments"] });
              }}
            />
          )}
        </>
      )}
    </div>
  );
}

export default OutstandingsTab;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-PAY-013@3c9f5a1 (story+rules snapshot — EP-PAY-04 US-PAY-013 lead story; co-packets US-PAY-012 (EP-PAY-03) and US-PAY-014 (EP-PAY-04), same rules file; 04-docs/05-modules/08-payments/02-business-rules.md BR-PAY-029/032/021/015/018/017/020; 07-frontend/src/features/payments/README.md §2026-08-15)
// generated: 2026-08-15 by story-coder (payments FRONTEND visible-half lane — the S34 tab the read-model shipped without)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: see the lane report — tsc✔ · eslint --max-warnings 0✔ · vitest✔ (RED-PROVED FIRST) · run_gates✔ (G13 unwired-props included — every prop this file declares has a caller in PaymentsPage.tsx)
// exceptions: (1) NO `GET /outstandings` CSV EXPORT — `POST /exports` registers no `outstandings` resource and BR-SHL-010 keeps an undeclared capability unrendered · (2) FOUR of the prototype's six bulk actions render DISABLED WITH THEIR REASON: reminder and disconnect notice are US-PAY-015's and no endpoint serves either, the payment plan is US-PAY-017's wizard, and the field visit has NO ratified rule at all (EP-PAY-04 scope line) · (3) NO PER-ROW ACTION MENU — the prototype's select offers Send disconnect / Payment plan / Record payment / Write off per row and the same four endpoints are missing or another story's; the selection toolbar carries every action that exists and the account number links to the account · (4) THE SELECTED TOTAL IS SUMMED IN THE BROWSER, exactly, on the NUMERIC(18,6) grid with BigInt — no endpoint totals a selection, US-PAY-013 TC-4 asks for the figure, and a float would be the money defect CLAUDE.md rule 2 exists to prevent · (5) THE SERVER SENDS NO CURRENCY CODE on this body; the tenant's CHAR(3) is read off `GET /payments` (BR-TEN-042's one-currency lock) and a stated absence renders when it cannot be — REPORTED as the one backend shape change this screen wants · (6) THE WRITE-OFF APPROVAL LIVES HERE, not on S36, because `/write-offs` is POST-only and no route lists pending ones — REPORTED · (7) the prototype's GL-account picker, "send to collections agency" and "flag for a future deposit" are NOT offered: the first would let a clerk post bad debt outside finance's designation (BR-PAY-020) and the other two have no ratified rule (field-map P-4/P-5) and a CHECK constraint that refuses them
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
