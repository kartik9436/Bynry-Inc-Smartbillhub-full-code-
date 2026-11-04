// ── Trace ──────────────────────────────────────────────
// Story:    US-LED-018 (S73 Capture — date · service · supplier FREE TEXT ·
//           amount · OPTIONAL volume · GL account · period) · US-LED-019 (S73
//           the register: list · search · filter · edit · VOID with reason,
//           never delete — and OQ-203's after-close correction) · US-LED-020
//           (S74 bought vs billed, and the ABSENT-with-reason case that
//           protects it) · US-LED-021 (the export section, whose drift this
//           screen's correction creates)
//           Screens: S73 · S74 (AppShell sidebar → Finance → Cost of service)
// Rules:    BR-LED-028 (capture, hold, reconcile, export — and process NOTHING:
//           no approvals, no payment runs, no vendor master, no ageing chase) ·
//           BR-LED-029 (what a captured invoice holds) · BR-LED-030 (the volume
//           is OPTIONAL) · BR-LED-031 (the unaccounted-for figure is
//           ALL-OR-NOTHING per service per period) · BR-LED-032 (it is a VOLUME
//           ratio, never a money one) · BR-LED-033 (bought and billed must
//           carry the SAME unit) · BR-LED-034 (editable while OPEN; after close
//           with a REASON) · BR-LED-035 (void, never delete) · BR-LED-037 (the
//           eight cost codes are PROPOSED and UNSIGNED) · BR-REP-001 (every
//           figure labels its basis) · BR-SHL-011 (list grammar) · BR-SHL-020
//           (plain-language failure) · BR-SHL-023 (one money formatting path) ·
//           BR-SHL-025 (a control this deployment cannot honour renders
//           DISABLED with its reason) · BR-SHL-044 (one page header)
// ───────────────────────────────────────────────────────
// S73 · S74 — what the utility BOUGHT, and how much of it it failed to bill.
//
// ══════════════════════════════════════════════════════════════════════════
// THE ONE FIGURE THIS PRODUCT CAN PRODUCE AND AN ACCOUNTING PACKAGE CANNOT
// ══════════════════════════════════════════════════════════════════════════
// Bought 1,000,000 gallons, billed 910,000 → **9.00% unaccounted for**: leak,
// meter under-registration or theft, in one number. QuickBooks holds the
// supplier invoice and Xero holds the supplier invoice, and neither holds the
// billed volumes — only this product does. That is the whole argument for the
// screen, and it is why the capture form asks for a volume at all.
//
// ══════════════════════════════════════════════════════════════════════════
// A ZERO IS NEVER AN ANSWER ON THIS SCREEN
// ══════════════════════════════════════════════════════════════════════════
// Every reconciliation row carries a percentage or the REASON it cannot, with
// its count. The suppressed case is the whole point of BR-LED-031: with one of
// five water purchases captured cost-only, the partial denominator reads
// **−13.75%** — a utility that appears to have delivered more water than it
// bought — and that number never reaches a screen, a CSV or a PDF. So the cell
// prints *"no volume captured for 1 of 5 water purchases this period"*, and
// `unaccounted_for_pct ?? 0` would undo all of it in one character.
//
// ══════════════════════════════════════════════════════════════════════════
// THE BOOKS DO NOT MOVE, AND THIS SCREEN SAYS SO OUT LOUD
// ══════════════════════════════════════════════════════════════════════════
// OQ-200, PO 2026-08-16: *"(b) for R2, (a) once supplier payments exist"*. A
// capture posts NOTHING — it is a filing and reconciliation record. The closure
// text is explicit that *"any screen implying otherwise is a defect"*, so the
// banner is not decoration: without it a clerk who captures $51,902.50 and
// finds an unmoved trial balance has every reason to think the product is
// broken. The sentence is SERVED (`register.posting`), never written here, so
// it cannot drift from the ledger's the day the ruling's trigger fires.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT IS DELIBERATELY ABSENT, SAID WHERE SOMEBODY WOULD LOOK FOR IT
// ══════════════════════════════════════════════════════════════════════════
//   · **No Approve, no Mark paid, no Schedule payment, no supplier page, no
//     ageing bucket** — BR-LED-028 makes every one of them a RULE, not a
//     missing feature, and the panel says so by name. A silent absence reads as
//     an unbuilt feature; a named refusal reads as law.
//   · **No bulk-action bar.** A bulk action over captured payables IS a payment
//     run or an approval queue. The server serves `bulk_actions: []` with its
//     reason and this screen prints the reason.
//   · **No Delete.** Void is the only disposition and there is no delete route
//     at any layer (BR-LED-035, hard rule 4).
//   · **No unit PICKER on the capture form.** A picker would be a vocabulary,
//     and the per-service purchase-unit vocabulary is OQ-201, OPEN. The field is
//     free text that must match the billed unit exactly; when it does not, the
//     reconciliation says so by name (MMBtu vs ccf) rather than converting.
//   · **The S74 Download renders DISABLED with its reason** (BR-SHL-025):
//     whether this view is a Finance sub-view or a report beside S59/S60 decides
//     which download pipeline it registers with, and that is OQ-204, OPEN.
//
// ══════════════════════════════════════════════════════════════════════════
// LAW 6 — DIFFED AGAINST `05-prototype/UtilityBilling.html`, BOTH DIRECTIONS
// ══════════════════════════════════════════════════════════════════════════
// **The prototype contains NOTHING for this capability** — zero occurrences of
// *supplier*, *vendor* or *purchased power*; it predates the OQ-188 ruling. So
// no element here is prototype-extracted and none is presented as such (hard-won
// law 1). The layout follows the S73/S74 capability matrix in EP-LED-06 and the
// list grammar the other Finance tabs already use.
import { useMemo, useState } from "react";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  attachSupplierInvoiceDocument,
  captureSupplierInvoice,
  correctSupplierInvoice,
  getCostReconciliation,
  getCostRegister,
  getChartOfAccounts,
  recordCostSettlement,
  voidSupplierInvoice,
} from "@/api/endpoints";
import type {
  CostReconciliationRow,
  CostRegisterResponse,
  CostRegisterRow,
} from "@/api/endpoints";
import { AbsentFigure } from "@/components/AbsentFigure";
import { Button } from "@/components/Button";
import { RowAction, RowActions } from "@/components/RowActions";
import { DollarIcon, PencilIcon, RetireIcon } from "@/components/icons";
import { FormModal, SelectField, TextField } from "@/components/FormModal";
/* ⚠ **THE KIT'S DROP FIELD, NOT A SECOND UPLOADER (`DEF-LED-6708`, B14 rule
   43).** `FileDropField` is what `REQ-03.4` and `NEW-01` already take a file
   with, through `DocumentCaptureForm`. The blueprint p065 draws ONE optional
   file on this modal — *"Attach the invoice · drag or choose the supplier's
   PDF · Optional, so capture still works without one"* — so this takes the
   FIELD and not `DocumentCaptureForm`'s whole section, which brings a type
   picker and a submit button of its own and would give the modal two
   primaries (B14 rule 4). `DOCUMENT_ACCEPT` is the shared allowlist hint; the
   server is the guard (`BR-SHL-031`). */
import { FileDropField } from "@/components/FileDropField";
import { DOCUMENT_ACCEPT } from "@/components/documents";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { MoneyCell } from "@/components/MoneyCell";
import { LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { useToast } from "@/components/Toast";
import { PlainTable } from "@/components/Surfaces";
import { Panel } from "@/components/Panel";
/* ⚠ **THE SHARED TABLE, NOT A SECOND ONE (`DEF-LED-6710`, B14 rules 43 + 44).**
   This screen hand-rolled a `PlainTable` with a bare labelled `<input>` and one
   `<select>` beside it, so the PO read a Finance tab that carried none of the
   controls its five neighbours carry. The Finance blueprint p062 already said
   so in terms — *"one filter wired, five unreachable · no chooser · no pager"*,
   *"Breaks UI-RULES 13·14·15·16·17 · NFR-3"* — and named the remedy as tasks
   `P1.8` and *"P1 kit for the filters and empty state"*.
   `DataTable` brings the search, the `+ Filter`, the `▦` chooser, the sortable
   headers, the empty state and the pager, and every one of them is then ONE
   thing across the product rather than six. */
import { DataTable } from "@/components/DataTable";
import { FilterBar } from "@/components/FilterBar";
import { parseTableParams, serializeTableParams } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
/* ⚠ **ONE LABEL PER SERVICE CODE PRODUCT-WIDE, AND IT IS THIS ONE
   (`DEF-LED-6670`).** Both tables on this screen rendered `row.service` raw, so
   a clerk read `electric` and `water` in lower case while the capture dialog
   beside them offered *Cost of service · Electric*. `serviceLabel` resolves
   `rating.service.<code>` — the single source `DEF-763` already settled for the
   whole product, and the eleven values the Finance blueprint p063 draws
   (*Water*, *Electric*). Typing a twelfth map here is what that defect was.

   ⚠ **THIS COVERS THE ELEVEN SERVICES AND NOT THE SIXTEEN COST CATEGORIES,
   AND THAT HALF IS `DEF-LED-6677`, FILED RATHER THAN GUESSED.** A category row
   appears only when it has purchases in the window, so the demo tenant shows
   none today — but `admin_payroll_benefits` would still render raw. Its NAME
   already exists (`chart.COST_CATEGORY_SPECS[].account_name`, served to the
   capture picker by `cost_category_catalog`), so the fix is to fan those into
   the catalogues, never to coin sixteen new ones here. */
import { serviceLabel } from "@/features/assets/assetsShared";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import type { Translator } from "@/features/tenancy/settingsShared";

import { FinanceBody, FinanceHeader, useFinancePeriod } from "./financeChrome";

import "./finance.css";

export const COST_OF_SERVICE_ROUTE = "/finance/cost-of-service";

export const costRegisterKey = (params: Record<string, string>) =>
  ["ledger", "cost-of-service", params] as const;
export const costReconciliationKey = (from: string, to: string) =>
  ["ledger", "cost-of-service", "reconciliation", from, to] as const;

/**
 * The reason sentence for one served problem code.
 *
 * Keyed on the SERVER's stable code and rendered from THIS app's catalogue —
 * never from server prose, which would be English-only on a product with eleven
 * catalogues (TD-16/B8). A code with no copy falls back to a sentence that NAMES
 * the code, so a new suppression reason surfaces as itself rather than as a
 * blank cell — which is the one thing a reader fills in for themselves.
 */
function problemSentence(code: string, t: Translator): string {
  const copy = t(`finance.cost.problem.${code}`, { defaultValue: "" });
  return copy !== "" ? copy : t("finance.cost.problem.unknown", { code });
}

/** The FIRST problem on a row, as a sentence, or null. Rows carry at most one
 *  suppression reason that matters to a reader; listing all of them turns a
 *  cell into a paragraph. */
function firstProblem(problems: string[], t: Translator): string | null {
  return problems.length === 0 ? null : problemSentence(problems[0], t);
}

// ══════════════════════════════════════════════════════════════════════════
// S74 — bought vs billed
// ══════════════════════════════════════════════════════════════════════════
function ReconciliationPanel(props: {
  from: string;
  to: string;
  client: ApiClient;
  t: Translator;
}) {
  const { t } = useTranslation();
  const query = useQuery({
    queryKey: costReconciliationKey(props.from, props.to),
    queryFn: () => getCostReconciliation({ from: props.from, to: props.to }, props.client),
    retry: false,
  });

  if (query.data === undefined) {
    return <LoadingSkeleton variant="table" />;
  }
  const data = query.data;
  return (
    <Panel>
      <div className="fin-panel-head">
        <h3>{t("finance.cost.tab.reconciliation")}</h3>
      </div>
      {/* BR-REP-001 — the basis is MANDATORY and rides with the figures, never
          in a caption somebody may not scroll to.

          ⚠ **THIS WAS `data.basis_label` UNTIL 2026-09-25: NINETY WORDS OF
          ENGINEERING RATIONALE (`DEF-LED-6669`).** The server composed an
          English paragraph naming `OQ-202`, quoting a PO ruling verbatim and
          working a 2.55-point swing out in prose, and this line printed it.
          B14 rule 33 puts rationale at ZERO words on screen and rule 32 keeps a
          rule id out of clerk-facing copy — so it is DELETED, not shortened.

          The basis is still labelled, which is what BR-REP-001 asks: the CODE
          is served and the words are the blueprint's own (p063 draws the basis
          as a two-value control, *Service period · Issued*). Three words, and
          translated in all eleven catalogues instead of one.

          The "this is not the ruled basis" warning is NOT lost with it — it
          never lived here. `data.problems` already carries it as a code and
          `firstProblem` renders the catalogue's sentence for it, per row. */}
      <p className="fin-absent-reason" role="note">
        {t(`finance.cost.basis.${data.basis}`)}
      </p>
      <PlainTable>
        <thead>
          <tr>
            <th scope="col">{t("finance.map.col.service")}</th>
            <th scope="col">{t("finance.cost.col.boughtVolume")}</th>
            <th scope="col">{t("finance.cost.col.boughtCost")}</th>
            <th scope="col">{t("finance.cost.col.billedVolume")}</th>
            <th scope="col">{t("finance.cost.col.unaccounted")}</th>
          </tr>
        </thead>
        <tbody>
          {data.rows.map((row: CostReconciliationRow) => {
            const reason = firstProblem(row.problems, props.t);
            return (
              <tr key={row.service}>
                <th scope="row">{serviceLabel(row.service, t)}</th>
                <td>
                  {/* ⚠ **THE SAME ONE CELL AS THE REGISTER (`DEF-LED-6711`).**
                      This column printed `10.000000 10` too — the PO reported
                      it on BOTH views, which is the tell that it was never one
                      row of one table but how the value rendered wherever it
                      appeared. CLAUDE.md rule 3 — a quantity NEVER renders
                      without its unit, and an absent volume says so rather
                      than showing 0. */}
                  <VolumeCell
                    volume={row.bought_volume}
                    unit={row.bought_unit}
                    t={t}
                    reason={t("finance.cost.noVolumeReason")}
                  />
                </td>
                <td>
                  {row.bought_cost === null ? (
                    "—"
                  ) : (
                    <MoneyCell
                      amount={row.bought_cost}
                      currency={row.currency ?? data.currency ?? ""}
                              />
                  )}
                </td>
                <td>
                  {/* The BILLED side, through the same cell. A dash stood here
                      for an absent billed volume and is kept as the absence's
                      shape, because BR-LED-031 already suppresses the
                      percentage beside it with a REASON — two stated absences
                      on one row would say the same thing twice. */}
                  {row.billed_volume === null ? (
                    "—"
                  ) : (
                    <VolumeCell volume={row.billed_volume} unit={row.billed_unit} t={t} />
                  )}
                </td>
                <td>
                  {/* ⚠ THE LINE THIS WHOLE SCREEN TURNS ON. A null is not a
                      zero: `?? 0` here prints "0.00%" over a month nobody could
                      compute, which reads as a utility losing nothing. */}
                  {row.unaccounted_for_pct === null ? (
                    <AbsentFigure
                      label={t("finance.absent")}
                      reason={reason ?? t("finance.cost.problem.unknown", { code: "" })}
                    />
                  ) : (
                    <strong>{t("finance.cost.pct", { value: row.unaccounted_for_pct })}</strong>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </PlainTable>
      {/* ⚠ **`Formula: (bought_volume - billed_volume) / bought_volume` STOOD
          HERE UNTIL 2026-09-25 AND IS DELETED (`DEF-LED-6669`).** It is this
          module's own field names rendered to a finance officer, which rule 32
          forbids outright. BR-REP-009 wants the numerator, the denominator and
          the basis shown — and each is a COLUMN on the table above (Bought,
          Billed) plus the basis line at its head, so the arithmetic is on the
          screen rather than spelled out in code. */}
      {/* BR-SHL-025 — DISABLED WITH ITS REASON, never hidden. A missing control
          reads as a feature nobody thought of; this one is a decision nobody has
          taken yet, and the person who needs the CSV has to know the difference. */}
      <Button variant="secondary" disabled>
        {t("download.open")}
      </Button>
      {/* ⚠ **FIFTY-FIVE WORDS OF UNDECIDED ENGINEERING UNTIL 2026-09-25
          (`DEF-LED-6669`).** The served sentence weighed up *"the platform
          export registry, or the IS-11 report pipeline under a report key"* at
          a finance officer who can act on neither. The blueprint (p063) says
          the button is right to be disabled and the SENTENCE is wrong. So the
          state is untouched and the words are the product's own six for this
          exact absence. */}
      <p className="fin-absent-reason" role="note">
        {t(data.download.reason_key)}
      </p>
    </Panel>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// S73 — the capture modal
// ══════════════════════════════════════════════════════════════════════════
const captureSchema = z.object({
  invoice_date: z.string().min(1),
  service: z.string().min(1),
  supplier_name: z.string().min(1),
  amount: z.string().min(1),
  ledger_account_id: z.string().min(1),
});

// ⚠ **CR-060 C15 · task T5 — THE WIDENED PICKER, AND IT ADDS NO CLASS AT ALL.**
// `features/ledger/` is NOT on `src/styles/route-b-migrated.txt`, so a Tailwind
// utility written in this file renders as NOTHING while `tsc`, eslint and every
// `toContain` assertion pass on it (B14 rule 21 / DEF-974). This adds none: the
// operating-statement grouping rides the option LABEL and the payroll caution
// rides `SelectField`'s own `help` — both already-declared surfaces.
//
// EXPORTED as a pure function rather than inlined in the modal, so the rule it
// carries is testable without mounting a form. That rule is the capital
// refusal, and a refusal nothing asserts is a refusal nobody notices leaving.
export function captureCategoryOptions(
  register: CostRegisterResponse,
  t: Translator,
): { value: string; label: string; disabled?: boolean }[] {
  const catalog = register.category_catalog;
  // The flat list stays the contract and is the fallback: a server or a mock
  // that predates the catalog still renders a working picker.
  const capturable =
    catalog !== undefined && catalog.length > 0
      ? catalog.map((row) => ({
          value: row.code,
          // The bucket rides the label because a native <select> here has no
          // <optgroup>, and inventing disabled separator rows would put
          // unselectable entries into a list of choices.
          label: `${row.group_label} · ${row.label}`,
        }))
      : register.categories.map((code) => ({ value: code, label: code }));
  // ⚠ **THE CAPITAL NAMES ARE PRESENT AND UNSELECTABLE, WHICH IS THE POINT.**
  // `FieldOption.disabled` exists for exactly this and says so in its own
  // comment: present-and-unselectable beats absent (the clerk would never learn
  // the category exists) and beats selectable (they would only learn on
  // submit). The label carries where the money goes instead — a $40,000 truck
  // recorded as a cost overstates the year by $40,000 and leaves the asset off
  // the balance sheet entirely. The server refuses these BY NAME as well, so a
  // caller reaching the API directly meets the same rule.
  const refused = (register.refused_categories ?? []).map((row) => ({
    value: row.code,
    // ⚠ **THE `defaultValue` IS GONE BECAUSE THE KEY IS REAL NOW (`P2.6`).**
    // It read `t("finance.cost.recordOnAsset", { defaultValue: "record it on
    // the asset instead" })`, above a note saying the eleven catalogues were
    // another lane's file and that the key was "reported to that lane". It was
    // never written, so for as long as that stood **ten of the eleven
    // catalogues showed a clerk English** — and the fallback rendering
    // perfectly is exactly why nobody noticed. A `defaultValue` is a promise
    // to come back; this is coming back.
    label: `${row.label} — ${t("finance.cost.recordOnAsset")}`,
    disabled: true,
  }));
  return [...capturable, ...refused];
}

/** CR-060 §6's one caution, SERVED so it cannot drift from the ledger's: a
 *  payroll figure is a record of what left the bank and is not payroll
 *  accounting. Returned only for the category that carries one, so the field
 *  shows a sentence only where it means something (B14 rule 32). */
export function cautionFor(register: CostRegisterResponse, code: string): string | null {
  return (register.category_catalog ?? []).find((row) => row.code === code)?.caution ?? null;
}


export function CaptureModal(props: {
  register: CostRegisterResponse;
  currency: string;
  client: ApiClient;
  t: Translator;
  onClose: () => void;
  onCaptured: () => void;
}) {
  const { t } = useTranslation();
  const toast = useToast();
  const [invoiceDate, setInvoiceDate] = useState("");
  const [service, setService] = useState("");
  const [supplier, setSupplier] = useState("");
  const [amount, setAmount] = useState("");
  const [volume, setVolume] = useState("");
  const [unit, setUnit] = useState("");
  /* ⚠ **THE FILE IS HELD HERE AND SENT AFTER THE CAPTURE, AND THAT ORDER IS
     FORCED.** A `File` is not JSON and cannot ride the capture body, and the
     document hangs off the PURCHASE — `stored_documents.source_id` — which
     does not exist until the capture returns an id. The same two-step
     `TransferWizard` already uses. */
  const [invoiceFile, setInvoiceFile] = useState<File | null>(null);
  const [account, setAccount] = useState("");
  const [reference, setReference] = useState("");

  const accounts = useQuery({
    queryKey: ["ledger", "accounts", "cost"],
    queryFn: () => getChartOfAccounts({ status: "active" }, props.client),
    retry: false,
  });

  const options = useMemo(
    () =>
      (accounts.data?.rows ?? [])
        .filter((row) => row.type === "expense")
        .map((row) => ({
          value: row.account_id,
          // US-LED-017 TC-5 — an UNSIGNED code is offered MARKED, never hidden
          // and never presented as finance-signed. Hiding the eight would leave
          // a capture form with nowhere to point.
          label: props.register.pending_finance_re_sign_cost.includes(row.code)
            ? t("finance.cost.accountUnsigned", { code: row.code, name: row.name })
            : `${row.code} · ${row.name}`,
        })),
    [accounts.data, props.register.pending_finance_re_sign_cost, t],
  );

  const categoryOptions = useMemo(
    () => captureCategoryOptions(props.register, t),
    [props.register, t],
  );
  const selectedCaution = useMemo(
    () => cautionFor(props.register, service),
    [props.register, service],
  );

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      const captured = await captureSupplierInvoice(
        {
          invoice_date: invoiceDate,
          service,
          supplier_name: supplier,
          // Money leaves as the STRING the clerk typed. Never `Number(amount)`:
          // a float has already lost digits before it reaches the wire.
          amount,
          currency: props.currency,
          volume: volume.trim() === "" ? null : volume,
          volume_unit: unit.trim() === "" ? null : unit,
          ledger_account_id: account,
          reference: reference.trim() === "" ? undefined : reference,
        },
        props.client,
      );
      /* ⚠ **A FAILED ATTACH DOES NOT UNDO THE CAPTURE, AND THE CLERK IS TOLD
         WHICH HALF HAPPENED.** The purchase is captured and immutable
         (hard rule 4) — there is no rollback and inventing one would mean
         deleting a financial row. So a refused file is reported as itself,
         over a purchase that IS on the register, and the clerk attaches it
         again from the row rather than re-keying the invoice. Swallowing this
         is the failure that matters: a clerk who dropped a PDF and saw a
         success toast believes it was kept. */
      if (invoiceFile !== null) {
        try {
          await attachSupplierInvoiceDocument(captured.id, invoiceFile, props.client);
        } catch (attachError) {
          return {
            ok: false,
            error: isApiError(attachError)
              ? formErrorEnvelope(attachError)
              : { code: "", message_key: "finance.cost.documentFailed" },
          };
        }
      }
      toast(
        t("finance.cost.capturedToast", {
          reference: captured.reference ?? captured.supplier_name,
        }),
      );
      props.onCaptured();
      return { ok: true };
    } catch (error) {
      return {
        ok: false,
        error: isApiError(error)
          ? formErrorEnvelope(error)
          : { code: "", message_key: "finance.cost.captureFailed" },
      };
    }
  }

  return (
    <FormModal
      title={t("finance.cost.capture")}
      schema={captureSchema}
      values={{ invoice_date: invoiceDate, service, supplier_name: supplier, amount, ledger_account_id: account }}
      onSubmit={submit}
      onClose={props.onClose}
      submitLabel={t("finance.cost.capture")}
    >
      <TextField id="invoice_date" label={t("finance.cost.col.date")} value={invoiceDate} onChange={setInvoiceDate} required />
      <SelectField
        id="service"
        label={t("assets.form.service")}
        value={service}
        onChange={setService}
        required
        // BR-REP-006 — the LIVE vocabulary, served, never hardcoded here.
        options={categoryOptions}
        // `DEF-SHL-10751` — starts "", so without this the box drew its first
        // category while holding none and "required" fired on a shown value.
        placeholder={t("finance.taxes.form.basisPlaceholder")}
        // CR-060 §6's one caution, and it is SERVED so it cannot drift from the
        // ledger's: a payroll figure is a record of what left the bank and is
        // not payroll accounting. Shown only when that category is chosen, so
        // the field carries one sentence and only where it means something
        // (B14 rule 32's description budget).
        help={selectedCaution ?? undefined}
      />
      <TextField
        id="supplier_name"
        label={t("finance.cost.field.supplier")}
        value={supplier}
        onChange={setSupplier}
        required
        // BR-LED-028: FREE TEXT. No vendor master, no dedupe prompt, no merge —
        // two spellings of "City of Rosenberg" are both stored as typed.
        help={t("finance.cost.field.supplierHelp")}
      />
      <TextField id="amount" label={t("finance.cost.field.amount", { currency: props.currency })} value={amount} onChange={setAmount} required numeric />
      <TextField
        id="volume"
        label={t("finance.cost.col.volume")}
        value={volume}
        onChange={setVolume}
        numeric
        // BR-LED-030 — OPTIONAL, and the help says what leaving it blank costs,
        // because the price is paid on the OTHER screen (BR-LED-031).
        help={t("finance.cost.field.volumeHelp")}
      />
      <TextField
        id="volume_unit"
        label={t("finance.cost.field.unit")}
        value={unit}
        onChange={setUnit}
        // Free text, not a picker: a picker would be the vocabulary OQ-201 asks
        // for, and inventing one is how gas gets silently converted.
        help={t("finance.cost.field.unitHelp")}
      />
      <SelectField
        id="ledger_account_id"
        label={t("finance.export.col.account")}
        value={account}
        onChange={setAccount}
        required
        options={options}
        // `DEF-SHL-10751` — the same empty start as `service` above.
        placeholder={t("finance.je.field.accountPlaceholder")}
      />
      <TextField id="reference" label={t("finance.cost.field.reference")} value={reference} onChange={setReference} />
      {/* p065 item 2 — OPTIONAL, so a capture still works without one. B14
          rule 33: the hint is what to DO (five words) and the help is a FACT
          (six words); how long the file is kept is RATIONALE and is ZERO
          WORDS ON SCREEN, even though it is now ruled at seven years
          (`BR-LED-799`) — a screen that explains a retention policy breaks
          rule 33 while trying to be helpful. */}
      <FileDropField
        id="invoice_document"
        label={t("finance.cost.field.document")}
        hint={t("finance.cost.field.documentHint")}
        browseLabel={t("finance.cost.field.documentBrowse")}
        help={t("finance.cost.field.documentHelp")}
        accept={DOCUMENT_ACCEPT}
        fileName={invoiceFile?.name ?? null}
        onChange={setInvoiceFile}
      />
    </FormModal>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// S73 — void with a reason (never delete)
// ══════════════════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════════════════════
// S73 — RECORD THE PAYMENT (CR-060 C1 · task T6(e))
// ══════════════════════════════════════════════════════════════════════════
// **This is the control the whole change request turns on, and until now it did
// not exist.** T6 landed the column, the posting and the route on 2026-09-02
// and said so in writing — *"(e) THE SCREEN — NOT LANDED"* — so the books moved
// only for somebody holding an HTTP client. Hard-won law 2, on the row carrying
// this CR's own argument.
//
// PO ruling 2026-09-02, verbatim: *"why cant to add the check that whether this
// is paid or unpaid and allow clark to udpaet it - that way we can reconcicle -
// again system of record we dont have to match we can take input from Clark and
// close it"*. **The clerk's input IS the authority.** Nothing is matched against
// a bank feed; a clerk with the statement open types the date they see.
//
// ⚠ **IT IS A SEPARATE SAVE FROM THE CORRECTION, BECAUSE IT IS A SEPARATE ACT.**
// The server refuses a body carrying `paid_on` beside anything else: recording a
// payment posts money and writes its own audit row, correcting a captured fact
// writes a different one, and one request doing both would leave half a state
// behind if the second half were refused.
const settlementSchema = z.object({ paid_on: z.string().min(1) });

function SettlementModal(props: {
  row: CostRegisterRow;
  now: () => string;
  client: ApiClient;
  t: Translator;
  onClose: () => void;
  onRecorded: () => void;
}) {
  const { t } = useTranslation();
  const [paidOn, setPaidOn] = useState(props.row.paid_on ?? "");

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      // BR-TEN-043 — the CALLER stamps the moment, so a double-submitted save
      // records one instant. `paid_on` is the day the BANK moved the money and
      // is the BOOK DATE of the entry it posts; the two are different facts and
      // the server is given both.
      await recordCostSettlement(
        props.row.id,
        { paid_on: paidOn, settled_at: props.now() },
        props.client,
      );
      props.onRecorded();
      return { ok: true };
    } catch (error) {
      return {
        ok: false,
        error: isApiError(error)
          ? formErrorEnvelope(error)
          : { code: "", message_key: "finance.cost.settleFailed" },
      };
    }
  }

  return (
    <FormModal
      title={t("finance.cost.recordPayment")}
      kicker={props.row.reference ?? props.row.supplier_name}
      schema={settlementSchema}
      values={{ paid_on: paidOn }}
      onSubmit={submit}
      onClose={props.onClose}
      submitLabel={t("finance.cost.recordPayment")}
    >
      <TextField
        id="paid_on"
        label={t("finance.cost.field.paidOn")}
        value={paidOn}
        onChange={setPaidOn}
        required
        help={t("finance.cost.field.paidOnHelp")}
      />
      {/* B14 rule 32 — the consequence is real and it is long, so it goes
          behind a disclosure CLOSED by default rather than as a paragraph
          above a date field. The SENTENCE IS THE SERVER'S (`settlement.ruling`)
          and is not composed here, so it cannot drift from what the ledger
          actually does. */}
      <AbsentFigure
        label={t("finance.cost.state.inTheBooks")}
        reason={props.row.settlement.ruling}
      />
    </FormModal>
  );
}

const voidSchema = z.object({ reason: z.string().min(1) });

function VoidModal(props: {
  row: CostRegisterRow;
  now: () => string;
  client: ApiClient;
  t: Translator;
  onClose: () => void;
  onVoided: (afterClose: string | null) => void;
}) {
  const { t } = useTranslation();
  const [reason, setReason] = useState("");

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      const voided = await voidSupplierInvoice(
        props.row.id,
        { reason, voided_at: props.now() },
        props.client,
      );
      // OQ-203's condition, delivered at the moment of the act: if this period
      // has already gone to an accounting system, the clerk is told WHICH batch
      // no longer matches before they walk away from the screen.
      const batches = voided.after_close?.exported_batches ?? [];
      props.onVoided(
        batches.length === 0
          ? null
          : batches.map((batch) => batch.batch_no ?? batch.target).join(", "),
      );
      return { ok: true };
    } catch (error) {
      return {
        ok: false,
        error: isApiError(error)
          ? formErrorEnvelope(error)
          : { code: "", message_key: "finance.cost.voidFailed" },
      };
    }
  }

  return (
    <FormModal
      title={t("finance.cost.void")}
      kicker={props.row.reference ?? props.row.supplier_name}
      schema={voidSchema}
      values={{ reason }}
      onSubmit={submit}
      onClose={props.onClose}
      submitLabel={t("finance.cost.void")}
    >
      {/* The row STAYS VISIBLE after this, with its reason — a register that
          hides its corrections cannot be reconciled against a supplier
          statement. The help text says so, because a clerk expecting a delete
          needs to know the row is not going anywhere. */}
      <TextField
        id="reason"
        label={t("assets.retire.reason")}
        value={reason}
        onChange={setReason}
        required
        multiline
        help={t("finance.cost.field.voidReasonHelp")}
      />
    </FormModal>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// S73 — the after-close correction (OQ-203, ruled)
// ══════════════════════════════════════════════════════════════════════════
const correctSchema = z.object({ amount: z.string().min(1), correction_reason: z.string().min(1) });

function CorrectionModal(props: {
  row: CostRegisterRow;
  client: ApiClient;
  t: Translator;
  onClose: () => void;
  onCorrected: (afterClose: string | null) => void;
}) {
  const { t } = useTranslation();
  const [amount, setAmount] = useState(props.row.amount);
  const [reason, setReason] = useState("");

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      const corrected = await correctSupplierInvoice(
        props.row.id,
        { amount, correction_reason: reason },
        props.client,
      );
      const batches = corrected.after_close?.exported_batches ?? [];
      props.onCorrected(
        batches.length === 0
          ? null
          : batches.map((batch) => batch.batch_no ?? batch.target).join(", "),
      );
      return { ok: true };
    } catch (error) {
      return {
        ok: false,
        error: isApiError(error)
          ? formErrorEnvelope(error)
          : { code: "", message_key: "finance.cost.correctFailed" },
      };
    }
  }

  return (
    <FormModal
      title={t("finance.cost.correct")}
      kicker={props.row.reference ?? props.row.supplier_name}
      schema={correctSchema}
      values={{ amount, correction_reason: reason }}
      onSubmit={submit}
      onClose={props.onClose}
      submitLabel={t("finance.cost.correct")}
    >
      <TextField id="amount" label={t("finance.cost.field.amount", { currency: props.row.currency })} value={amount} onChange={setAmount} required numeric />
      {/* REQUIRED once the period has closed, and the help says why: this audit
          row is the only artifact that can later explain the difference to
          whoever reconciles a month-end that was already signed off. */}
      <TextField
        id="correction_reason"
        label={t("finance.cost.field.correctionReason")}
        value={reason}
        onChange={setReason}
        required
        multiline
        help={t("finance.cost.field.correctionReasonHelp")}
      />
    </FormModal>
  );
}

/**
 * One register row's settlement state, in B14 rule 34's ratified pair.
 *
 * **Recorded** — held here, not in the books. **In the books** — the cost
 * account is charged and the same amount has left cash.
 *
 * ⚠ **THE STATE IS THE SERVER'S `in_the_books`, NEVER `paid_on !== null`.**
 * The two agree today because `record_settlement` writes the column and posts
 * the entry in one transaction; a screen that leans on that equality goes wrong
 * the first time they come apart and nothing anywhere goes red. `paid_on` is
 * printed as the DATE beside the state, which is the one thing it does mean.
 *
 * ⚠ **`settlement.journal_entry_id` IS NEVER RENDERED** — B14 rule 31. It rides
 * the payload for the tie-out and the drill-back; a clerk reads a state and a
 * date.
 */
export function SettlementCell(props: { row: CostRegisterRow; t: Translator }) {
  if (props.row.settlement.in_the_books) {
    return (
      <>
        <StatusPill tone="success">{props.t("finance.cost.state.inTheBooks")}</StatusPill>{" "}
        {props.row.settlement.paid_on ?? props.row.paid_on}
      </>
    );
  }
  // A stated absence, CLOSED by default (B14 rule 32, `AbsentFigure`'s ratified
  // shape). An unpaid purchase is the ORDINARY case — nine of LE-11's nine on
  // the day it is captured — so the reason must not shout at a clerk on every
  // row of the register.
  return (
    <AbsentFigure
      label={props.t("finance.cost.state.recorded")}
      reason={props.t("finance.cost.state.recordedHelp")}
    />
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE VOLUME AND ITS UNIT — ONE CELL, EVERYWHERE — `DEF-LED-6711`
// ══════════════════════════════════════════════════════════════════════════
/**
 * A captured volume with the unit it was measured in, or the stated absence.
 *
 * ⚠ **THIS RENDERED `10.000000 10` ON A LIVE SCREEN.** Both tables on this page
 * interpolated the wire value straight into a template literal —
 * `` `${row.volume} ${row.volume_unit ?? ""}` `` — so the screen printed
 * whatever SCALE the serialiser emitted (six decimals, because that is how the
 * column is stored) beside whatever the unit field happened to hold. The two
 * tokens then read as one number.
 *
 * ⚠ **THE TRAILING ZEROS ARE THE ONLY THING TRIMMED, AND THE FIGURE IS NEVER
 * ROUNDED.** A consumption is not money and B4's display rule does not reach
 * it: `10.000000` becomes `10` and `1.234567` stays `1.234567`, because a
 * volume a clerk keyed is the volume a clerk keyed and a reconciliation
 * compares it against a billed figure. Dropping a digit here would move a
 * bought-versus-billed percentage.
 *
 * ⚠ **AND THE UNIT IS PRINTED, NEVER INVENTED.** CLAUDE.md hard rule 3 —
 * consumption always travels with an explicit unit. `volume_unit` is FREE TEXT
 * by ruling (a picker would be the `OQ-201` vocabulary), so this cell cannot
 * correct a unit it does not like; a unit that is wholly numeric is
 * `DEF-LED-6712` and belongs at the capture boundary, not here. What this cell
 * refuses to do is guess: a volume with NO unit says so rather than standing
 * alone as a bare number.
 */
export function VolumeCell(props: {
  volume: string | null;
  unit: string | null;
  t: Translator;
  /** The row-level absence sentence — the register's and the reconciliation's
   *  differ, because one is about a purchase and one about a service. */
  reason?: string;
}) {
  if (props.volume === null) {
    return (
      <AbsentFigure
        label={props.t("finance.cost.noVolume")}
        reason={props.reason ?? props.t("finance.cost.noVolumeRow")}
      />
    );
  }
  const unit = (props.unit ?? "").trim();
  if (unit === "") {
    // A quantity with no unit is not a consumption (hard rule 3). It is shown
    // as an absence rather than as a bare number, so nobody reads it as being
    // in whatever unit the row above was in.
    return (
      <AbsentFigure
        label={props.t("finance.cost.noVolume")}
        reason={props.reason ?? props.t("finance.cost.noVolumeRow")}
      />
    );
  }
  return (
    <>
      {trimTrailingZeros(props.volume)} {unit}
    </>
  );
}

/** `"10.000000"` → `"10"`; `"1.234567"` → `"1.234567"`; `"10"` → `"10"`. */
export function trimTrailingZeros(value: string): string {
  if (!value.includes(".")) {
    return value;
  }
  const trimmed = value.replace(/0+$/, "").replace(/\.$/, "");
  return trimmed === "" || trimmed === "-" ? "0" : trimmed;
}

// ══════════════════════════════════════════════════════════════════════════
// THE REGISTER'S TABLE CONFIG — `DEF-LED-6710`
// ══════════════════════════════════════════════════════════════════════════
/**
 * S73's captured-purchase register, declared for the shared `DataTable`.
 *
 * ⚠ **EVERY CONTROL HERE IS SERVED, AND THAT IS THE POINT.** A screen that
 * declares a sort or a filter the server does not honour is a live screen
 * behind a broken control — hard-won law 2's mirror, and the reason
 * `DEF-PAY-4221` did not close when `/outstandings` learned to page. So:
 *   · the five SORTS are exactly `cost_capture.SORTABLE` — date, supplier,
 *     service, amount, volume — and nothing else carries a caret;
 *   · the three FILTERS are exactly the `f.` params `cost_api` reads —
 *     `service`, `status`, `volume_captured`;
 *   · the SEARCH is the server's, over supplier, reference and memo, and the
 *     server refuses a single character (`MIN_SEARCH_CHARS`).
 * A column the server cannot order by is declared WITHOUT `sortable`, which
 * draws no caret at all rather than a caret that does nothing.
 */
function costRegisterConfig(
  t: Translator,
  options: { services: { value: string; label: string }[] },
  actions?: {
    onSettle: (row: CostRegisterRow) => void;
    onCorrect: (row: CostRegisterRow) => void;
    onVoid: (row: CostRegisterRow) => void;
  },
): TableConfig<CostRegisterRow> {
  return {
    // S73 — the register's screen id, which is how a stored column set and a
    // saved list preference find their way back to THIS table.
    screenId: "S73",
    getRowId: (row) => String(row.id),
    // Served: supplier_name, reference, memo (the S73 capability row).
    searchFields: ["supplier_name", "reference", "memo"],
    searchPlaceholder: "finance.cost.searchLabel",
    defaultSort: { sort: "date", dir: "desc" },
    filters: [
      {
        name: "service",
        label: t("finance.map.col.service"),
        // BR-REP-006 — the tenant's OWN live vocabulary, served on the
        // register beside the rows. This file holds no literal service array;
        // an eleventh service typed out here is exactly `DEF-763`'s shape.
        options: options.services,
      },
      {
        name: "status",
        label: t("assets.col.status"),
        // Two values and no third: there is no approved, scheduled or paid
        // status BY RULE (BR-LED-028), and the server refuses any other.
        options: [
          { value: "captured", label: t("finance.cost.status.captured") },
          { value: "voided", label: t("finance.cost.status.voided") },
        ],
      },
      {
        name: "volume_captured",
        label: t("finance.cost.volumeFilter"),
        // THE FILTER THAT EARNS ITS PLACE (US-LED-019 TC-3): it returns exactly
        // the set that decides whether an unaccounted-for percentage can be
        // produced at all (BR-LED-031).
        options: [
          { value: "yes", label: t("finance.cost.volumeFilter.yes") },
          { value: "no", label: t("finance.cost.volumeFilter.no") },
        ],
      },
    ],
    columns: [
      {
        key: "date",
        label: t("finance.cost.col.date"),
        identity: true,
        sortable: true,
        cell: (row) => row.invoice_date,
      },
      {
        key: "supplier",
        label: t("finance.cost.col.supplier"),
        sortable: true,
        cell: (row) => row.supplier_name,
      },
      {
        key: "service",
        label: t("finance.map.col.service"),
        sortable: true,
        // ONE LABEL PER SERVICE CODE PRODUCT-WIDE (`DEF-LED-6670`).
        cell: (row) => serviceLabel(row.service, t),
      },
      {
        key: "amount",
        label: t("billing.bill.col.amount"),
        numeric: true,
        sortable: true,
        cell: (row) => <MoneyCell amount={row.amount} currency={row.currency} />,
      },
      {
        key: "volume",
        label: t("finance.cost.col.volume"),
        numeric: true,
        sortable: true,
        cell: (row) => <VolumeCell volume={row.volume} unit={row.volume_unit} t={t} />,
      },
      {
        key: "account",
        label: t("finance.export.col.account"),
        cell: (row) => (
          <>
            {row.gl_account_code} · {row.gl_account_name}
            {row.gl_account_unsigned && (
              <span className="fin-absent-reason" role="note">
                {t("finance.cost.unsignedAccount")}
              </span>
            )}
          </>
        ),
      },
      {
        key: "status",
        label: t("assets.col.status"),
        cell: (row) => (
          <>
            <StatusPill tone={row.status === "voided" ? "warning" : "success"}>
              {t(`finance.cost.status.${row.status}`)}
            </StatusPill>
            {row.void_reason !== null && (
              <span className="fin-absent-reason" role="note">
                {row.void_reason}
              </span>
            )}
          </>
        ),
      },
      {
        // CR-060 C1 · T6(e). Beside Status and not inside it: Status is whether
        // the PURCHASE stands, this is whether the MONEY is in the books.
        key: "paid_on",
        label: t("finance.cost.field.paidOn"),
        cell: (row) => <SettlementCell row={row} t={t} />,
      },
      {
        key: "actions",
        label: t("finance.coa.col.actions"),
        // B14 rule 15 — icons for row actions, and this column can never be
        // hidden: a register with no way to void is a different screen.
        locked: true,
        cell: (row) =>
          actions === undefined || row.status !== "captured" ? null : (
            <RowActions>
              {/* NOT offered once the settlement is in the books: hard rule 4
                  leaves no path to change a posted entry, so the server
                  refuses by name and a control that can only be refused is
                  worse than none. */}
              {!row.settlement.in_the_books && (
                <RowAction
                  label={t("finance.cost.recordPayment")}
                  icon={<DollarIcon />}
                  onClick={() => actions.onSettle(row)}
                />
              )}
              <RowAction
                label={t("finance.cost.correct")}
                icon={<PencilIcon />}
                onClick={() => actions.onCorrect(row)}
              />
              <RowAction
                label={t("finance.cost.void")}
                icon={<RetireIcon />}
                danger
                onClick={() => actions.onVoid(row)}
              />
            </RowActions>
          ),
      },
    ],
  };
}

/**
 * The register's request, from the table state the URL holds.
 *
 * The wire. `sort`/`dir` and `per` are the product's own list grammar
 * (`BR-SHL-011`); `cost_api` reads both and folds them into the register's
 * signed sort key, so no second grammar exists on this screen.
 *
 * ⚠ `DEF-LED-9029` — EXPORTED SO A TEST CAN ASK FOR THE SAME KEY THE PAGE
 * DOES. The register test seeded `costRegisterKey({})` while the page (since
 * the shared-table rebuild, 26376795e) asks with its sort and page, so the
 * seeded rows never reached the screen and three cases measured an empty one.
 */
export function costRegisterParams(tableState: TableRequestState): Record<string, string> {
  const registerParams: Record<string, string> = {
    sort: tableState.sort,
    dir: tableState.dir,
    page: String(tableState.page),
    per: String(tableState.per),
  };
  // IS-3 — the server refuses a one-character term, so it is not sent. A
  // request that can only be refused is not a request.
  if (tableState.q.trim().length >= 2) registerParams.q = tableState.q;
  for (const [name, value] of Object.entries(tableState.filters)) {
    if (value !== "") registerParams[`f.${name}`] = value;
  }
  return registerParams;
}

/** The register's request for a URL with no table params — the first load. */
export function costRegisterDefaultParams(t: Translator): Record<string, string> {
  return costRegisterParams(
    parseTableParams(new URLSearchParams(), costRegisterConfig(t, { services: [] })),
  );
}

// ══════════════════════════════════════════════════════════════════════════
// The page
// ══════════════════════════════════════════════════════════════════════════
export function CostOfServicePage(props: RegionalProps & { client?: ApiClient; now?: () => string }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const toast = useToast();
  const queryClient = useQueryClient();
  const regional = useRegional(props);
  const { period, loading } = useFinancePeriod(client);
  const [search, setSearch] = useSearchParams();
  const [capturing, setCapturing] = useState(false);
  const [voiding, setVoiding] = useState<CostRegisterRow | null>(null);
  const [correcting, setCorrecting] = useState<CostRegisterRow | null>(null);
  const [settling, setSettling] = useState<CostRegisterRow | null>(null);

  // IS-4 — the whole request state lives in the URL, so a clerk can send
  // somebody the exact view they are looking at: the search, the three
  // filters, the sort, the page and the page size.
  const view = search.get("view") ?? "register";

  // ⚠ **PARSED WITH THE REGISTER'S OWN CONFIG (`DEF-LED-6710`).**
  // `parseTableParams` validates `sort` against the columns it is handed, so a
  // config built without the real column set would silently fall back to the
  // default sort on every load. The options are empty HERE on purpose — this
  // copy decides nothing but which params are legal, and the served vocabulary
  // arrives with the rows.
  const paramsConfig = useMemo(() => costRegisterConfig(t, { services: [] }), [t]);
  const tableState = parseTableParams(search, paramsConfig);

  function setTableState(next: TableRequestState) {
    const params = serializeTableParams(next, paramsConfig);
    // The view strip is not the table's and must survive every table act.
    if (view !== "register") params.set("view", view);
    setSearch(params, { replace: true });
  }

  const registerParams = costRegisterParams(tableState);

  const register = useQuery({
    queryKey: costRegisterKey(registerParams),
    queryFn: () => getCostRegister(registerParams, client),
    retry: false,
  });

  function setParam(key: string, value: string) {
    const next = new URLSearchParams(search);
    if (value === "") next.delete(key);
    else next.set(key, value);
    setSearch(next, { replace: true });
  }

  // ⚠ **THE FILTER'S OPTIONS ARE THE SERVER'S, NEVER A LITERAL ARRAY.** The
  // register serves this tenant's live capture vocabulary beside the rows —
  // `category_catalog` with its labels, `categories` as the older contract —
  // and BR-REP-006 makes that the only lawful source. An eleventh service
  // typed out in this file is `DEF-763`'s shape and `DEF-LED-6677` is the
  // sixteen COST CATEGORIES' half of the same job, filed rather than guessed.
  const serviceOptions = useMemo(() => {
    const catalog = register.data?.category_catalog;
    if (catalog !== undefined && catalog.length > 0) {
      return catalog.map((entry) => ({
        value: entry.code,
        label: entry.label ?? serviceLabel(entry.code, t),
      }));
    }
    return (register.data?.categories ?? []).map((code) => ({
      value: code,
      label: serviceLabel(code, t),
    }));
  }, [register.data?.category_catalog, register.data?.categories, t]);

  const registerTable = useMemo(
    () =>
      costRegisterConfig(t, { services: serviceOptions }, {
        onSettle: setSettling,
        onCorrect: setCorrecting,
        onVoid: setVoiding,
      }),
    [t, serviceOptions],
  );

  function refresh(afterClose: string | null, toastKey: string) {
    void queryClient.invalidateQueries({ queryKey: ["ledger"] });
    toast(
      afterClose === null
        ? t(toastKey)
        : // ⚠ The OQ-203 warning, at the moment of the act. The batch is NAMED,
          // because the clerk has to go and fix it at the accounting system's end
          // and "something is now out of date" is not an instruction.
          t("finance.cost.correctedButExported", { batches: afterClose }),
    );
    setVoiding(null);
    setCorrecting(null);
    setSettling(null);
  }

  return (
    <>
      <FinanceHeader
        activeTab="cost-of-service"
        explainer={t("finance.cost.explainer")}
        period={period}
        t={t}
        timeZone={regional.timeZone}
        dateFormat={regional.dateFormat}
      />
      <FinanceBody period={period} loading={loading} t={t}>
        {/* ⚠ **DEF-2365 — THIS SENTENCE HAD GONE FALSE, AND IT WAS FALSE ON A
            MONEY SCREEN.** It printed the `OQ-200` ruling that capture posts
            nothing in R2 — *"records it and moves no books … and in no trial
            balance"* — which was true when it was written and was **superseded
            by CR-060 T6 the same day**: a supplier cost now posts
            `DR cost / CR cash` on the day a clerk records it was settled. The
            copy is now B14 rule 34's pair, **Recorded** / **In the books**, and
            it names BOTH states because both are reachable.

            The reason it is still printed at all is unchanged: without it a
            clerk who captures $51,902.50 and finds an unmoved trial balance has
            every reason to think the product is broken. */}
        {register.data !== undefined && (
          <p className="fin-absent-reason" role="note">
            {t("finance.cost.postsNothing")}
          </p>
        )}

        <div className="fin-panel-head">
          <Button
            variant={view === "register" ? "primary" : "secondary"}
            onClick={() => setParam("view", "register")}
          >
            {t("finance.cost.tab.register")}
          </Button>
          <Button
            variant={view === "reconciliation" ? "primary" : "secondary"}
            onClick={() => setParam("view", "reconciliation")}
          >
            {t("finance.cost.tab.reconciliation")}
          </Button>
        </div>

        {view === "reconciliation" && period !== null ? (
          <ReconciliationPanel
            from={period.start}
            to={period.end}
            client={client}
            t={t}
           
          />
        ) : register.data === undefined ? (
          <LoadingSkeleton variant="table" />
        ) : (
          <Panel>
            <div className="mb-4 flex items-center justify-between gap-4">
              {/* B14 rule 44 — the kit's panel heading and `--space-4` from
                  the scale. The page head's 32px title (rule 40) is the
                  PAGE's and is not repeated here. */}
              <h3 className="m-0 font-heading text-h5 leading-heading">
                {t("finance.cost.tab.register")}
              </h3>
              <div className="flex items-center gap-3">
                {/* ⚠ **THE FOOTER MOVED OUT OF THE TABLE AND THAT IS THE
                    HONEST PLACE FOR IT (`DEF-LED-6710`).** It was a `<tfoot>`
                    under the rows. Now that the rows are ONE PAGE, a total
                    sitting under them reads as the page's total — and it is
                    not: the server computes it over the whole FILTERED set, as
                    a SQL aggregate, which is exactly why cutting a page did not
                    have to move it. Beside the heading it describes the set the
                    pager is counting.
                    B14 rule 33 — a FACT, three words, no sentence. */}
                {register.data.total_amount !== null && (
                  <span className="text-sm text-neutral-700">
                    {t("finance.cost.footer")}{" "}
                    <MoneyCell
                      amount={register.data.total_amount}
                      currency={register.data.currency ?? ""}
                    />
                  </span>
                )}
                <Button variant="primary" onClick={() => setCapturing(true)}>
                  {t("finance.cost.capture")}
                </Button>
              </div>
            </div>

            {/* ⚠ **THE SHARED TABLE — `DEF-LED-6710`, B14 rules 43 and 44.**
                What stood here was a `PlainTable` with a bare `<input>` and one
                `<select>` above it. The kit brings the search, the `All / +
                Filter` control, the `▦` column chooser, sortable headers, the
                empty state and the pager, and every one of them then behaves
                the way it behaves on the other five Finance tables. */}
            <DataTable<CostRegisterRow>
              config={registerTable}
              state={tableState}
              onStateChange={setTableState}
              rows={register.data.rows}
              // ⚠ **THE SERVER'S COUNT OVER THE WHOLE FILTERED SET — never
              //    `rows.length`, which is the page and would make the pager
              //    describe itself.**
              totalRows={register.data.page?.total ?? register.data.count}
              loading={register.isFetching}
              error={
                register.error === null || register.error === undefined
                  ? null
                  : { onRetry: () => void register.refetch() }
              }
              filterBarSlot={
                <FilterBar
                  filters={registerTable.filters ?? []}
                  state={tableState}
                  onStateChange={setTableState}
                />
              }
              empty={{
                title: t("finance.cost.emptyTitle"),
                helper: t("finance.cost.emptyHelper"),
                ctaLabel: t("finance.cost.capture"),
                // B14 rule 4 — the panel head already carries this action, so
                // the empty state's copy of it is the secondary tier and the
                // screen keeps one primary.
                ctaVariant: "secondary",
                onCta: () => setCapturing(true),
              }}
            />

            {/* ⚠ **BR-LED-028 WAS STATED HERE AS 38 WORDS WITH ITS RULE ID
                IN FRONT, AND IS DELETED (`DEF-LED-6642`).** It read
                *"BR-LED-028: no approval workflow and no payment run exists in
                this product…"* — which is RATIONALE, why a control is absent,
                and B14 rule 33 puts that at zero words on screen while rule 32
                keeps a rule id out of clerk-facing copy. Rationale is REMOVED,
                never shortened. The rule lives in `cost_capture.py`'s
                `FORBIDDEN_ACTIONS` and in BR-LED-028 itself. */}
          </Panel>
        )}
      </FinanceBody>

      {capturing && register.data !== undefined && (
        <CaptureModal
          register={register.data}
          currency={register.data.currency ?? "USD"}
          client={client}
          t={t}
          onClose={() => setCapturing(false)}
          onCaptured={() => {
            setCapturing(false);
            void queryClient.invalidateQueries({ queryKey: ["ledger"] });
          }}
        />
      )}
      {voiding !== null && (
        <VoidModal
          row={voiding}
          now={props.now ?? (() => new Date().toISOString())}
          client={client}
          t={t}
          onClose={() => setVoiding(null)}
          onVoided={(afterClose) => refresh(afterClose, "finance.cost.voidedToast")}
        />
      )}
      {settling !== null && (
        <SettlementModal
          row={settling}
          now={props.now ?? (() => new Date().toISOString())}
          client={client}
          t={t}
          onClose={() => setSettling(null)}
          onRecorded={() => refresh(null, "finance.cost.settledToast")}
        />
      )}
      {correcting !== null && (
        <CorrectionModal
          row={correcting}
          client={client}
          t={t}
          onClose={() => setCorrecting(null)}
          onCorrected={(afterClose) => refresh(afterClose, "finance.cost.correctedToast")}
        />
      )}
    </>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-LED-018@d744841 (US-LED-019/020/021 draw in this file too — sources: 04-docs/05-modules/09-ledger/06-epics/EP-LED-06-cost-of-service-capture.md · 09-ledger/02-business-rules.md BR-LED-028..039 · 09-ledger/08-worked-examples.md LE-11..LE-14 · 08-qa/01-e2e/journeys/J25-cost-of-service-month.md · 12-governance/01-open-questions.md OQ-200/202/203 CLOSED, OQ-201/204 OPEN, OQ-227 minted)
// generated: 2026-08-16 by the surface-debt tails lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — the screen test failed to resolve this module before the file existed, and the backend routes answered `Resolver404` before `config/urls.py` named `apps.ledger.cost_api`. PROVED IN A BOOTED BROWSER, quoted in the lane report.
// exceptions: (1) the S74 Download renders DISABLED with its reason (BR-SHL-025) — OQ-204 decides which download pipeline this view registers with · (2) the capture form offers NO unit picker: a picker would be the per-service purchase-unit vocabulary OQ-201 asks for · (3) `05-prototype/UtilityBilling.html` contains NOTHING for this capability (zero occurrences of supplier/vendor/purchased power — it predates the OQ-188 ruling), so no element here is prototype-extracted and none is presented as such · (4) the register is UNPAGINATED, matching the server's own reported limit rather than inventing a second contract
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
