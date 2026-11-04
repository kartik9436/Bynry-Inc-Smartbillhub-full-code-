// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-REP-7070 — Product Owner, on deployed v2.380.3, looking at
//          `/{tenant}/reports/statement?edit=1`: *"report editor is not user
//          friendly — as a user I don't know what I'm doing and how fields are
//          shown — no edit no adds"*.
// Screens: 2·2 (A1 S47), the edit panel beside the live table
// Rules:   B14 rule 43 (a piece of UI is a COMPONENT — this is why the chooser
//          is not 60 lines inside a 660-line panel) · rule 44 (our kit and our
//          tokens win over the drawing, every time) · rule 33 (a LABEL ≤ 3
//          words · a FACT ≤ 6 words · RATIONALE is ZERO words on screen) ·
//          rule 31 (no database id is ever the VISIBLE value of a field) ·
//          rule 36 (the shared component kit is how you comply) · rule 21
//          (Tailwind utilities; this file is listed in route-b-migrated.txt) ·
//          BR-REP-043 (a statement is served for five subjects) ·
//          BR-REP-038 (a statement is one account's running record) ·
//          hard-won law 2's MIRROR (never a control the query cannot honour)
// Tests:   07-frontend/src/features/reports/reportRequiredInput.dom.test.tsx
// Impacts: ReportEditPanel.tsx (draws this FIRST, above section ①) ·
//          ReportViewerPage.tsx (owns the value; it lives in the URL) ·
//          apps/reports/statement.py (publishes `controls.requires`)
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  THE SCREEN OPENED ON A DEAD END, AND EVERY PART OF IT WAS CORRECT       ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// Walked at 1440 on 2026-09-27, before this file existed. The statement editor
// opened on four tiles reading *Not counted yet*, a table reading *No rows
// match — Widen the dates or filters.*, and — **four scroll-lengths below the
// fold** — the only sentence on the page that explains any of it: *"A statement
// opens on one account."*
//
// Nothing was broken. `apps/reports/statement.py` returns zero rows and states
// its reason, exactly as it should; `ReportGapList` renders that reason under
// the report, exactly as it should. **The fault is that the one thing a clerk
// must do FIRST was the last thing on the page**, and the instruction the
// screen did offer — *widen the dates* — is advice that cannot work, because no
// window contains rows until an account is named.
//
// ⚠ **THE CONTROL IS GENERAL AND THE STATEMENT IS ONE CASE OF IT.** This file
// contains no mention of a statement and no list of which report needs what.
// The SERVER declares `controls.requires`, each entry naming a run parameter
// and the KIND of record it finds; this draws one chooser per entry. A report
// that declares none — forty-five of the forty-six today — gets nothing at all,
// which is the half that is easy to get wrong: a chooser on a report that needs
// no record is a step invented by the screen.
//
// ⚠ **`BR-REP-043` IS WHY `finds` IS A KIND AND NOT A BOOLEAN.** Ruled today:
// a statement is served for five subjects — regular account, master account,
// premises, unit and customer. A master account is an ordinary `accounts` row
// (`BR-CUS-068`), so it is found by the account finder; the other three are
// their own kinds. Hard-coding *"ask for an account"* here would have had to be
// unpicked by the lane building those subjects.
//
// ⚠ **A KIND WITH NO FINDER DRAWS NOTHING, AND THAT IS NOT A GAP BEING
// HIDDEN.** `apps/reports/statement.py` REFUSES `customer`, `premises` and
// `unit` BY NAME today — each has no running-record read model — so the report
// never reaches this control at those subjects: it is refused before any id
// could help. Drawing a premises box over a report that will refuse the
// premises subject whatever is typed into it is hard-won law 2's mirror, a live
// control in front of a dead query. `finderFor` returns `null` and the server's
// own refusal is what the clerk reads. **The day the ledger publishes a
// premises running record, this is one entry in `FINDERS` and nothing else.**
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import type { ApiClient } from "@/api/client";
import { getAccounts } from "@/api/endpoints";
import { RemoteSearchSelectField } from "@/components/RemoteSearchSelectField";
import type { ReportRequiredParam } from "@/api/reportsEndpoints";
import type { Translator } from "@/features/tenancy/settingsShared";
import { accountPickerLabel, useAccountSearch } from "@/features/payments/paymentsShared";

/**
 * Which kinds this screen can FIND a record of today.
 *
 * ⚠ **THIS IS A CAPABILITY LIST, NOT A VOCABULARY** — which is the distinction
 * `CLAUDE.md`'s *never hand-type a list* turns on. The SUBJECTS are the
 * server's and are never written here; this says only which of them the front
 * end has a search box for. A kind the server offers and this omits is caught
 * by `reportRequiredInput.dom.test.tsx`, which asserts that every kind without
 * a finder is one the server refuses by name.
 */
const FINDERS: Readonly<Record<string, "account" | "owner">> = {
  account: "account",
  // `CR-185-BRC10` D4 — the Owner summary is about an OWNER, and an owner is
  // found by one of their MASTER accounts: the same account search, narrowed
  // to `f.kind=master` (the server's own filter, `BR-CUS-068`). The server
  // widens the account it is handed to every master account that customer
  // holds, so picking any one of an owner's properties opens the same report.
  owner: "owner",
};

export function finderFor(finds: string): "account" | "owner" | null {
  return FINDERS[finds] ?? null;
}

/** The minimum a search sends — the account finder's own IS-3 floor. */
const OWNER_SEARCH_MIN_CHARS = 2;

/**
 * The chooser for an OWNER — a search over master accounts only.
 *
 * ⚠ **A SEPARATE COMPONENT RATHER THAN A MODE OF `AccountRequirement`** for the
 * reason that one gives: a hook cannot be called conditionally, and two kinds
 * of record are two independent searches. It reads the SAME endpoint
 * (`GET /accounts`) with the server's own `kind` filter, so there is no second
 * answer to *which accounts are mine*.
 */
function OwnerRequirement(props: {
  requirement: ReportRequiredParam;
  value: string;
  onChange: (value: string) => void;
  client: ApiClient;
  t: Translator;
}) {
  const { t } = props;
  const [term, setTerm] = useState("");
  const trimmed = term.trim();
  const enabled = trimmed.length >= OWNER_SEARCH_MIN_CHARS;
  const query = useQuery({
    queryKey: ["reports", "owner-subject", trimmed],
    queryFn: () => getAccounts({ q: trimmed, per: 50, filters: { kind: "master" } }, props.client),
    enabled,
    retry: false,
  });
  const matches = enabled ? (query.data?.results ?? []) : [];
  return (
    <RemoteSearchSelectField
      id={`report-requires-${props.requirement.param}`}
      label={t("reports.requires.label.owner")}
      placeholder={t("reports.requires.find.owner")}
      term={term}
      onTermChange={setTerm}
      status={{
        idle: !enabled,
        searching: enabled && query.isPending,
        searched: enabled && query.isSuccess,
        failed: enabled && query.isError,
      }}
      // B14 rule 31 — the id posts and travels in the URL; the account number
      // and the owner's name are what a clerk reads.
      options={matches.map((account) => ({
        value: account.id,
        label: accountPickerLabel(account, t),
      }))}
      value={props.value}
      onChange={props.onChange}
      words={{
        tooShort: t("payments.form.accountTooShort"),
        searching: t("payments.form.accountSearching"),
        failed: t("payments.form.accountSearchFailed"),
        noMatch: t("payments.form.accountNoMatch"),
      }}
      help={t("reports.requires.fact.owner")}
      required
    />
  );
}

/**
 * The chooser for ONE required input — the account a statement is about.
 *
 * ⚠ **IT IS A SEPARATE COMPONENT PER REQUIREMENT BECAUSE A HOOK CANNOT BE
 * CALLED IN A LOOP CONDITIONALLY.** Each requirement owns its own search term
 * and its own query, which is also the honest shape: two required inputs on one
 * report are two independent searches, not one search with a mode.
 */
function AccountRequirement(props: {
  requirement: ReportRequiredParam;
  value: string;
  onChange: (value: string) => void;
  client: ApiClient;
  t: Translator;
}) {
  const { t } = props;
  const [term, setTerm] = useState("");
  // The search the account finder, the four payment doors and the meter owner
  // screen all use. IS-3: server-side, debounced, nothing sent under two
  // characters. A second copy of it here would be a second answer to *which
  // accounts are mine*.
  const search = useAccountSearch(term, props.client, "report-subject");
  return (
    <RemoteSearchSelectField
      id={`report-requires-${props.requirement.param}`}
      // A LABEL: one word, no sentence (rule 33).
      label={t("reports.requires.label.account")}
      placeholder={t("reports.requires.find.account")}
      term={term}
      onTermChange={setTerm}
      status={search}
      // B14 rule 31 — the id is the VALUE, which posts and travels in the URL;
      // the number and the name are the only things a clerk reads.
      options={search.matches.map((account) => ({
        value: account.id,
        label: accountPickerLabel(account, t),
      }))}
      value={props.value}
      onChange={props.onChange}
      words={{
        tooShort: t("payments.form.accountTooShort"),
        searching: t("payments.form.accountSearching"),
        // BR-SHL-020 — THE PLATFORM failed, the only one support can act on.
        failed: t("payments.form.accountSearchFailed"),
        // ⛔ NOT a refusal: the search ran and matched nothing. A fact about
        // the term, which is the half the clerk can fix.
        noMatch: t("payments.form.accountNoMatch"),
      }}
      // ⚠ **A FACT, ≤ 6 WORDS, AND IT IS THE SERVER'S OWN SENTENCE MOVED UP
      // THE PAGE** — *"A statement opens on one account."* It was already on
      // this screen, below the fold, where it explained an empty table after
      // the fact. It is not RATIONALE: it says what the report IS, not why the
      // product works this way, so rule 33 admits it at six words.
      help={t("reports.requires.fact.account")}
      required
    />
  );
}

/**
 * Every input the report declares it is about, asked for FIRST.
 *
 * Draws NOTHING when the report declares none — no heading, no empty box, no
 * *"this report needs nothing"*. B14 rule 32: a stated absence is closed by
 * default, and an absence nobody is wondering about is not stated at all.
 */
export function ReportRequiredInputs(props: {
  requires: readonly ReportRequiredParam[] | undefined;
  /** The value of each required parameter, keyed by `param`. */
  values: Readonly<Record<string, string>>;
  onChange: (param: string, value: string) => void;
  client: ApiClient;
  t: Translator;
}) {
  const drawable = (props.requires ?? []).filter(
    (one) => finderFor(one.finds) !== null,
  );
  if (drawable.length === 0) {
    return null;
  }
  return (
    <div className="flex flex-col gap-2" data-report-requires>
      {drawable.map((one) =>
        finderFor(one.finds) === "owner" ? (
          <OwnerRequirement
            key={one.param}
            requirement={one}
            value={props.values[one.param] ?? ""}
            onChange={(value) => props.onChange(one.param, value)}
            client={props.client}
            t={props.t}
          />
        ) : (
        <AccountRequirement
          key={one.param}
          requirement={one}
          value={props.values[one.param] ?? ""}
          onChange={(value) => props.onChange(one.param, value)}
          client={props.client}
          t={props.t}
        />
        ),
      )}
    </div>
  );
}

export default ReportRequiredInputs;

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-REP-7070 (PO report, deployed v2.380.3, 2026-09-27) · BR-REP-043 · BR-REP-038 · CR-142-BRC07 Phase 5 `P5.3`
// screens: 2·2 (A1 S47)
// generated: 2026-09-27 by lane REP-EDITOR-A
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — reportRequiredInput.dom.test.tsx was shown red on every case before this file existed. G31: this file is listed in styles/route-b-migrated.txt in the same commit.
// exceptions: (1) `useAccountSearch` and `accountPickerLabel` are imported from features/payments/paymentsShared — a cross-feature import, and the alternative is a SECOND answer to *which accounts are mine*. `features/customers` and `features/ledger` already import from it; moving the hook into the kit beside `RemoteSearchSelectField` is wave-2 work and is filed · (2) `FINDERS` is a hand-written map, which CLAUDE.md warns against — it is a CAPABILITY list rather than a vocabulary, the vocabulary stays the server's, and the test asserts every kind without a finder is one the server refuses by name
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
