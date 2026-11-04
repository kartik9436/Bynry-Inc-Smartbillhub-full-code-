// ── Trace ──────────────────────────────────────────────
// Screen:   S31 · BIL-02 — the bill run, step 2 Check
// Drawing:  05-prototype/bulk-bill-run-2026-09-30/11…23-check-*.png ·
//           inventory.md §3.3 (the list), §3.4 (the tag pane), §3.5 (Ready to
//           bill), §3.6 (Fix account)
// Story:    US-BIL-037 (TC-1, TC-6 … TC-14)
// Plan:     15-bulk-bill-run-build-plan.md F8 · F9 · F10 · F11 · F12 · B14 ·
//           B18
// Rules:    changes rows 20, 36, 41, 46 · B14 rules 3 (one table type), 21, 31,
//           33, 43, 44 · NFR-3 (every list pages on the server)
// Defects:  DEF-BIL-8216 (the served grouped read) · DEF-BIL-8217 (leave out) ·
//           DEF-BIL-8218 (inline fixes) · DEF-BIL-8219 (re-check by account)
// ───────────────────────────────────────────────────────
/**
 * THE CHECK STEP'S PIECES — the problem list, one tag's pane, the Ready list
 * and the Fix-account panel, each on the SERVER's grouped read
 * (`GET …/check/findings`, DEF-BIL-8216). Each is a component (rule 43);
 * `CheckStep.tsx` wires them.
 *
 * **Nothing here holds the whole run.** The list is the summary's categories →
 * tags with ACCOUNT counts; a tag's accounts are ONE server page (`?tag=`);
 * the Ready list is ONE server page (`?list=ready`); Fix account is ONE
 * account (`?account=`). The client taxonomy that used to group two raw reads
 * in the browser is gone — a tag is the engine's code, named by its served
 * `label_key`.
 *
 * **What each fix does.** A decision is answered HERE (`POST …/check/decisions`,
 * for all accounts of the tag, for a selection, or per row). A blocked row
 * whose fact the clerk can supply HERE carries `fix_here` and gets the inline
 * control — a plan, a connection size, inside/outside city limits — written by
 * the OWNING module and followed by a re-check of that account
 * (`POST …/check/fix`, DEF-BIL-8218). Every other blocked row links to its
 * screen and is re-checked by name.
 */
import { useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";

import type { ApiClient } from "@/api/client";
import {
  checkAccountKey,
  checkReadyKey,
  checkTagKey,
  getCheckAccount,
  getCheckReady,
  getCheckTag,
} from "@/api/bulkRunEndpoints";
import type {
  CheckAccountFinding,
  CheckCategoryGroup,
  CheckSeverity,
  CheckSummary,
  CheckTag,
  CheckTagRow,
  FixHere,
} from "@/api/bulkRunEndpoints";
import { getLookupEntries, getPlans } from "@/api/endpoints";
import { Button } from "@/components/Button";
import type { Translator } from "@/components/FormModal";
import { ListPager } from "@/components/ListPager";
import { formatMoney } from "@/components/MoneyCell";
import { SegmentedControl } from "@/components/SegmentedControl";
import { StatusPill } from "@/components/StatusPill";
import { PlainTable } from "@/components/Surfaces";
import type { PageSize } from "@/components/tableTypes";

import {
  Kicker,
  RUN_TABLE,
  ServiceLabel,
  SeverityMark,
  SeverityPill,
  SidePanel,
  TableScroll,
  TagChip,
  count,
  placeLine,
} from "./bulkRunShared";
import { fixScreenOf as taxonomyFixScreen, tagIdOf } from "./bulkRunTaxonomy";
import { useDebouncedTerm } from "@/features/work/raise/raiseModel";
import type { FixScreen } from "./bulkRunTaxonomy";

export type TileFilter = "all" | "blocks" | "decision" | "warning" | "ready";

export const READY_TAG = "ready";

export interface CheckLinks {
  /** Where a problem is fixed, for this account (new tab). */
  fix: (screen: FixScreen, accountId: string | null) => string;
  unit: (unitId: string) => string;
}

const INPUT = "input";

/** The served taxonomy's fix screen → the screen this page links to. `null`
 *  when the fix is on the Check itself or with support (no link). */
const SCREEN_BY_FIX: Readonly<Record<string, FixScreen>> = {
  reads: "meterReads",
  accounts: "accounts",
  plans: "plans",
  assets: "assets",
  premises: "premises",
  payments: "payments",
  settings: "settings",
};

export function fixScreenOf(tag: { fix_action?: { screen?: string } } | null | undefined): FixScreen | null {
  const screen = tag?.fix_action?.screen;
  return screen === undefined ? null : (SCREEN_BY_FIX[screen] ?? null);
}

function screenName(screen: FixScreen, t: Translator): string {
  return t(`billing.bulkRun.screen.${screen}`);
}

/** A tag's clerk name — DEF-BIL-8675: the drawn name (`billing.bulkRun.tag.<id>.name`,
 *  1–3 words, B14 rule 33) for every engine code the bulk run's taxonomy maps;
 *  the served `label_key` only for a code it does not. The older exceptions
 *  screen keeps the engine's sentences — these are the bulk run's own keys. */
export function tagLabel(tag: { code: string; label_key?: string }, t: Translator): string {
  const id = tagIdOf(tag.code);
  if (id !== null) return t(`billing.bulkRun.tag.${id}.name`);
  return t(tag.label_key ?? `billing.run.reason.${tag.code}`, { defaultValue: tag.code });
}

/** DEF-BIL-8676 / 8686 — what the tag means, in one drawn sentence, or null. */
export function tagMeaning(code: string, t: Translator): string | null {
  const id = tagIdOf(code);
  return id === null ? null : t(`billing.bulkRun.tag.${id}.meaning`);
}

function severityOf(severity: CheckSeverity): "blocks" | "decision" | "warning" {
  return severity ?? "warning";
}

/** The tags the list shows under the tile filter, the search and the passed tick. */
export function visibleTags(
  category: CheckCategoryGroup,
  filter: TileFilter,
  query: string,
  showPassed: boolean,
  t: Translator,
): CheckTag[] {
  const q = query.trim().toLowerCase();
  return category.tags.filter((tag) => {
    if (tag.severity === null) return false; // nothing to bill is not a problem (BR-BIL-1025)
    if (tag.count === 0 && !showPassed) return false;
    if (filter === "blocks" || filter === "decision" || filter === "warning") {
      if (tag.severity !== filter) return false;
    }
    if (q !== "" && !tagLabel(tag, t).toLowerCase().includes(q)) return false;
    return true;
  });
}

/** The first tag the list shows under a filter and search — the pane opens it
 *  when the open tag is hidden (inventory §0, image 18's fault not copied). */
export function firstShownTag(summary: CheckSummary, filter: TileFilter, query: string, showPassed: boolean, t: Translator): string | null {
  for (const category of summary.categories) {
    const tags = visibleTags(category, filter, query, showPassed, t);
    if (tags.length > 0) return tags[0].code;
  }
  return null;
}

/** Every tag of the summary by its code — what an *Also has* chip names. */
export function tagsByCode(summary: CheckSummary): Map<string, CheckTag> {
  const map = new Map<string, CheckTag>();
  for (const category of summary.categories) for (const tag of category.tags) map.set(tag.code, tag);
  return map;
}

// ── The left list (F8) ──────────────────────────────────────────────────────

export function ProblemTagList(props: {
  summary: CheckSummary;
  filter: TileFilter;
  selected: string;
  onSelect: (code: string) => void;
  query: string;
  onQuery: (query: string) => void;
  showPassed: boolean;
  onShowPassed: (show: boolean) => void;
  t: Translator;
}) {
  const { summary, t } = props;
  const [closed, setClosed] = useState<ReadonlySet<string>>(new Set());
  const passed = summary.categories.reduce(
    (sum, category) => sum + category.tags.filter((tag) => tag.severity !== null && tag.count === 0).length,
    0,
  );
  const shown = summary.categories
    .map((category) => ({ category, tags: visibleTags(category, props.filter, props.query, props.showPassed, t) }))
    .filter(({ tags }) => tags.length > 0);
  const readyShown = props.filter === "all" || props.filter === "ready";
  const rowBase = "flex w-full cursor-pointer items-center gap-2 border-0 border-t border-divider px-3 py-2 text-left text-base";
  return (
    <nav className="flex flex-col border border-divider bg-bg" aria-label={t("billing.bulkRun.check.listLabel")} data-problem-list="">
      <div className="flex flex-col gap-2 p-3">
        <label className="sr-only" htmlFor="problem-search">
          {t("billing.bulkRun.check.findProblem")}
        </label>
        <input
          id="problem-search"
          className={INPUT}
          type="search"
          placeholder={t("billing.bulkRun.check.findProblem")}
          value={props.query}
          onChange={(event) => props.onQuery(event.target.value)}
        />
        <label className="flex items-center gap-2 text-base">
          <input type="checkbox" checked={props.showPassed} onChange={(event) => props.onShowPassed(event.target.checked)} />
          {t("billing.bulkRun.check.showPassed", { count: passed })}
        </label>
      </div>
      {readyShown && (
        <button
          type="button"
          className={`${rowBase} ${props.selected === READY_TAG ? "bg-text text-bg" : "bg-bg"}`}
          aria-current={props.selected === READY_TAG ? "true" : undefined}
          onClick={() => props.onSelect(READY_TAG)}
          data-tag={READY_TAG}
        >
          <SeverityMark severity="ok" />
          <span className="flex-1 font-heading font-semibold">{t("billing.bulkRun.check.readyToBill")}</span>
          <span>{count(summary.tiles.ready)}</span>
        </button>
      )}
      {shown.length === 0 && !readyShown && (
        <p className="m-0 border-t border-divider px-3 py-2 text-base text-neutral-700" role="status">
          {t("billing.bulkRun.check.noMatch")}
        </p>
      )}
      {shown.map(({ category, tags }) => {
        const open = !closed.has(category.category);
        return (
          <div key={category.category} data-category={category.category}>
            <button
              type="button"
              className={`${rowBase} bg-surface`}
              aria-expanded={open}
              onClick={() =>
                setClosed((was) => {
                  const next = new Set(was);
                  if (next.has(category.category)) next.delete(category.category);
                  else next.add(category.category);
                  return next;
                })
              }
            >
              <span className="flex-1 font-heading text-md font-semibold">{t(category.label_key)}</span>
              <span className="font-heading font-semibold">{count(category.count)}</span>
              <span aria-hidden="true" className="text-xs">
                {open ? "▲" : "▼"}
              </span>
            </button>
            {open &&
              tags.map((tag) => (
                <button
                  key={tag.code}
                  type="button"
                  className={`${rowBase} ${props.selected === tag.code ? "bg-text text-bg" : "bg-bg"}`}
                  aria-current={props.selected === tag.code ? "true" : undefined}
                  onClick={() => props.onSelect(tag.code)}
                  data-tag={tag.code}
                >
                  <SeverityMark severity={severityOf(tag.severity)} />
                  <span className="flex-1">{tagLabel(tag, t)}</span>
                  <span>{tag.count === 0 ? "✓" : count(tag.count)}</span>
                </button>
              ))}
          </div>
        );
      })}
    </nav>
  );
}

// ── A row's answer, and a row's inline fix ──────────────────────────────────

/**
 * Two answers carry the PO's own words on this screen (fixed-charge cases 1
 * and 2, decision log 2026-09-30): *Standing charges only → Leave out* is
 * **Waive** — the base is not billed this month, a reason is REQUIRED and the
 * waiver is listed on Sign off — and *Bill without it* bills the service's
 * BASE now while the usage waits for the next bill.
 */
const CASE_CHOICE_KEYS: Readonly<Record<string, string>> = {
  "base_only_billing:exclude": "billing.bulkRun.choice.waive",
  "base_only_billing:waive": "billing.bulkRun.choice.waive",
  "missing_read:bill_without_service": "billing.bulkRun.choice.billBaseOnly",
  // DEF-BIL-8674 — `apply_next_bill` is shared with `true_up`, where the
  // catalogue's `Put it on this bill` is right (the trued-up quantity bills on
  // THIS bill). For a payment that arrived after the cut-off the same code
  // sends the payment to the NEXT bill, and beside `Apply to this bill` the
  // shared words read as the same answer. Drawn `Next bill` (D1 16).
  "paid_after_cutoff:apply_next_bill": "billing.bulkRun.choice.nextBill",
};

export function choiceLabel(choice: string, t: Translator, caseCode?: string | null): string {
  const own = caseCode === undefined || caseCode === null ? undefined : CASE_CHOICE_KEYS[`${caseCode}:${choice}`];
  if (own !== undefined) return t(own);
  if (choice === "bill_without_service") return t("billing.bulkRun.choice.billBaseOnly");
  // DEF-BIL-8676 — the drawn answers (D1 11): *Estimate*, *Hold*.
  if (choice === "estimate" || choice === "hold") return t(`billing.bulkRun.choice.${choice}`);
  return t(`billing.run.choice.${choice}`, { defaultValue: t("billing.bulkRun.check.answerGeneric") });
}

/** A waiver is a decision a clerk must give a reason for (PO 2026-09-30;
 *  the server's `decisions.REASON_REQUIRED`). The Check's own case answers
 *  `waive`; `exclude` is the older exceptions path's word for the same act. */
export function needsReason(caseCode: string | null | undefined, choice: string): boolean {
  return caseCode === "base_only_billing" && (choice === "waive" || choice === "exclude");
}

/** What an answer already given will do to this bill — stated, never hidden. */
function consequenceKey(caseCode: string, chosen: string | null): string | null {
  if (chosen === null) return null;
  if (needsReason(caseCode, chosen)) return "billing.bulkRun.check.waived";
  if (chosen === "bill_without_service") return "billing.bulkRun.check.usageLater";
  return null;
}

/** The reason box a waiver asks for, with its own Save. */
function ReasonBox(props: { id: string; t: Translator; working: boolean; label: string; onSave: (reason: string) => void; onCancel: () => void }) {
  const [reason, setReason] = useState("");
  return (
    <span className="flex flex-wrap items-center gap-2" data-reason-box="">
      <label className="sr-only" htmlFor={props.id}>
        {props.t("billing.bulkRun.check.reason")}
      </label>
      <input
        id={props.id}
        className={`${INPUT} w-56`}
        placeholder={props.t("billing.bulkRun.check.reason")}
        value={reason}
        onChange={(event) => setReason(event.target.value)}
      />
      <Button size="sm" variant="primary" disabled={props.working || reason.trim() === ""} onClick={() => props.onSave(reason.trim())}>
        {props.label}
      </Button>
      <Button size="sm" disabled={props.working} onClick={props.onCancel}>
        {props.t("billing.bulkRun.cancel")}
      </Button>
    </span>
  );
}

/** An Estimate's quantity and unit — what the clerk typed, never a default. */
export interface EstimateValues {
  amount: string;
  unit: string;
}

/** What an Estimate needs from its row: the account's own average month to
 *  start from (DEF-2859, metering's figure — null when there is no history)
 *  and the estimate already recorded. */
export interface EstimateFacts {
  basis: { quantity: string; unit: string } | null;
  quantity: string | null;
  unit: string | null;
}

/**
 * DEF-BIL-8551 / DEF-BIL-8415 — THE ESTIMATE BOX. Choosing *Estimate the
 * reading* opens a quantity and its unit, started from the account's own
 * average month where metering has one; nothing is recorded until *Record
 * this estimate* (the 2026-08-31 judgment: a prefilled box submits nothing,
 * the choice is the clerk's act). CLAUDE.md rule 3: both, or it is not sent.
 */
function EstimateBox(props: {
  id: string;
  t: Translator;
  working: boolean;
  facts: EstimateFacts;
  onSave: (values: EstimateValues) => void;
  onCancel: () => void;
}) {
  const { t, facts } = props;
  const [amount, setAmount] = useState(facts.quantity ?? facts.basis?.quantity ?? "");
  const [unit, setUnit] = useState(facts.unit ?? facts.basis?.unit ?? "");
  const number = Number(amount);
  const lawful = amount.trim() !== "" && Number.isFinite(number) && number >= 0 && unit.trim() !== "";
  return (
    <span className="flex flex-wrap items-center gap-2" data-estimate-box="">
      <label className="sr-only" htmlFor={props.id}>
        {t("billing.bulkRun.check.estimate.quantity")}
      </label>
      <input
        id={props.id}
        inputMode="decimal"
        className={`${INPUT} w-28`}
        value={amount}
        onChange={(event) => setAmount(event.target.value)}
      />
      <label className="sr-only" htmlFor={`${props.id}-unit`}>
        {t("billing.bulkRun.check.estimate.unit")}
      </label>
      <input
        id={`${props.id}-unit`}
        className={`${INPUT} w-20`}
        value={unit}
        readOnly={facts.basis !== null}
        onChange={(event) => setUnit(event.target.value)}
      />
      <Button size="sm" variant="primary" disabled={props.working || !lawful} onClick={() => props.onSave({ amount: amount.trim(), unit: unit.trim() })}>
        {t("billing.bulkRun.check.estimate.record")}
      </Button>
      <Button size="sm" disabled={props.working} onClick={props.onCancel}>
        {t("billing.bulkRun.cancel")}
      </Button>
      {facts.basis !== null && (
        <span className="text-neutral-700" data-estimate-usual="">
          {t("billing.bulkRun.check.estimate.usual", { quantity: facts.basis.quantity, unit: facts.basis.unit })}
        </span>
      )}
    </span>
  );
}

/** A row's own decision: a select with the tag's answers; a waiver asks why,
 *  an estimate asks how much. */
export function DecisionControl(props: {
  id: string;
  code: string;
  choices: readonly string[];
  answer: string | null;
  accountNo: string;
  t: Translator;
  working: boolean;
  /** Present on a No-reading row: an Estimate opens the estimate box. */
  estimate?: EstimateFacts;
  onChoose: (choice: string, reason?: string, estimate?: EstimateValues) => void;
}) {
  const { t } = props;
  const [pending, setPending] = useState<string | null>(null);
  if (props.choices.length === 0) return null;
  const consequence = pending === null ? consequenceKey(props.code, props.answer) : null;
  const asksHowMuch = (choice: string) => choice === "estimate" && props.estimate !== undefined;
  const recorded =
    pending === null && props.answer === "estimate" && props.estimate?.quantity != null && props.estimate.unit != null
      ? t("billing.bulkRun.check.estimate.recorded", { quantity: props.estimate.quantity, unit: props.estimate.unit })
      : null;
  return (
    <div className="flex flex-col gap-1" data-decision={props.answer === null ? "open" : "answered"}>
      <label className="sr-only" htmlFor={props.id}>
        {t("billing.bulkRun.check.decideFor", { account: props.accountNo })}
      </label>
      <select
        id={props.id}
        className={`${INPUT} min-w-52`}
        value={pending ?? props.answer ?? ""}
        disabled={props.working}
        onChange={(event) => {
          const choice = event.target.value;
          if (choice === "") return;
          if (needsReason(props.code, choice) || asksHowMuch(choice)) {
            setPending(choice);
            return;
          }
          setPending(null);
          props.onChoose(choice);
        }}
      >
        <option value="">{t("billing.bulkRun.check.choose")}</option>
        {props.choices.map((choice) => (
          <option key={choice} value={choice}>
            {choiceLabel(choice, t, props.code)}
          </option>
        ))}
      </select>
      {pending !== null && asksHowMuch(pending) && props.estimate !== undefined && (
        <EstimateBox
          id={`${props.id}-estimate`}
          t={t}
          working={props.working}
          facts={props.estimate}
          onSave={(values) => {
            props.onChoose(pending, undefined, values);
            setPending(null);
          }}
          onCancel={() => setPending(null)}
        />
      )}
      {recorded !== null && (
        <span className="text-base text-neutral-700" data-estimate-recorded="">
          {recorded}
        </span>
      )}
      {pending !== null && !asksHowMuch(pending) && (
        <ReasonBox
          id={`${props.id}-reason`}
          t={t}
          working={props.working}
          label={t("billing.bulkRun.save")}
          onSave={(reason) => {
            props.onChoose(pending, reason);
            setPending(null);
          }}
          onCancel={() => setPending(null)}
        />
      )}
      {consequence !== null && (
        <span className="text-base text-warning-700" data-consequence-line="">
          {t(consequence)}
        </span>
      )}
    </div>
  );
}

/** What a fix writes — the owning module's value, never billing's. */
export interface FixValues {
  plan_id?: string;
  size_class?: string;
  service_code?: string | null;
  inside_city_limits?: boolean;
}

/**
 * THE INLINE FIX (DEF-BIL-8218, image 13's *Choose pl… ▾ Save*): one control
 * and Save. The owning module writes it; the account is then re-checked and
 * the pane reads the saved answer — never an optimistic *fixed*.
 */
export function FixHereControl(props: {
  id: string;
  fix: Exclude<FixHere, null>;
  serviceCode: string | null;
  client: ApiClient;
  working: boolean;
  t: Translator;
  onFix: (values: FixValues) => void;
}) {
  const { t, fix } = props;
  const [value, setValue] = useState("");
  const plansQuery = useQuery({
    queryKey: ["bulk-run", "fix", "plans"],
    queryFn: () => getPlans({ filters: { status: "published" }, per: 100, sort: "name" }, props.client),
    enabled: fix === "set_plan",
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const sizesQuery = useQuery({
    queryKey: ["lookups", "service_size_classes"],
    queryFn: () => getLookupEntries("service_size_classes", { per: 200 }, props.client),
    enabled: fix === "set_size",
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const options: { value: string; label: string }[] =
    fix === "set_plan"
      ? (plansQuery.data?.results ?? []).map((plan) => ({ value: plan.id, label: plan.name }))
      : fix === "set_size"
        ? (sizesQuery.data?.results ?? [])
            .filter((row) => row.active && (row.service == null || props.serviceCode === null || row.service.code === props.serviceCode))
            .map((row) => ({ value: row.code, label: row.name }))
        : [
            { value: "inside", label: t("billing.bulkRun.check.fix.inside") },
            { value: "outside", label: t("billing.bulkRun.check.fix.outside") },
          ];
  const labelKey =
    fix === "set_plan" ? "billing.bulkRun.check.fix.plan" : fix === "set_size" ? "billing.bulkRun.check.fix.size" : "billing.bulkRun.check.fix.cityLimits";
  const save = () => {
    if (value === "") return;
    if (fix === "set_plan") props.onFix({ plan_id: value });
    else if (fix === "set_size") props.onFix({ size_class: value, service_code: props.serviceCode });
    else props.onFix({ inside_city_limits: value === "inside" });
  };
  return (
    <span className="flex flex-wrap items-center gap-2" data-fix-here={fix}>
      <label className="sr-only" htmlFor={props.id}>
        {t(labelKey)}
      </label>
      <select id={props.id} className={`${INPUT} min-w-40`} value={value} disabled={props.working} onChange={(event) => setValue(event.target.value)}>
        <option value="">{t(labelKey)}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <Button size="sm" variant="primary" disabled={props.working || value === ""} onClick={save} data-fix-save="">
        {t("billing.bulkRun.save")}
      </Button>
    </span>
  );
}

// ── The tag pane (F9, F10) ──────────────────────────────────────────────────

function AccountCell(props: { row: { account_no: string; customer_name: string | null }; onOpen: () => void }) {
  return (
    <>
      <button
        type="button"
        className="cursor-pointer border-0 bg-transparent p-0 font-heading font-semibold text-accent-700 underline"
        onClick={props.onOpen}
        data-open-account=""
      >
        {props.row.account_no}
      </button>
      {props.row.customer_name !== null && <span className="block text-neutral-700">{props.row.customer_name}</span>}
    </>
  );
}

/** A finding's own sentence (the engine's message key and params), or nothing. */
function foundLine(finding: { message_key: string | null; params: Record<string, unknown> }, t: Translator): string {
  if (finding.message_key === null) return "";
  return t(finding.message_key, { ...moneyParams(finding.params), defaultValue: "" });
}

/** DEF-BIL-10200 — a late-fee row's two figures, shown as money in the row's
 *  own currency (the server serves decimal strings, hard rule 2). */
function moneyParams(params: Record<string, unknown>): Record<string, unknown> {
  const currency = typeof params.currency === "string" ? params.currency : null;
  if (currency === null) return params;
  const out: Record<string, unknown> = { ...params };
  for (const key of ["amount", "overdue"]) {
    if (typeof params[key] === "string") out[key] = formatMoney(params[key] as string, currency);
  }
  return out;
}

/** BR-BIL-003 — answers a tag may never take for all its accounts at once
 *  (the server's `decisions.BULK_FORBIDDEN`): a late-fee waiver is per account. */
const PER_ACCOUNT_ONLY: ReadonlySet<string> = new Set(["late_fee:waive"]);

/** DEF-BIL-10200 — tags whose unanswered rows already bill (the server's
 *  `decisions.DEFAULT_ANSWERS`): a late fee applies unless it is waived. */
const ANSWERED_BY_DEFAULT: ReadonlySet<string> = new Set(["late_fee"]);

export interface CheckPaneActions {
  /** Answer ONE tag: every account (`all`) or the named ones. */
  onDecide: (
    tag: CheckTag,
    choice: string,
    accountIds: readonly string[] | "all",
    reason?: string,
    serviceCode?: string | null,
    estimate?: EstimateValues,
  ) => void;
  /** Re-check NAMED accounts only (DEF-BIL-8219), optionally one category. */
  onRecheck: (accountIds: readonly string[], categories?: readonly string[]) => void;
  /** Write one fact through its owning module, then re-check that account. */
  onFix: (accountId: string, fix: Exclude<FixHere, null>, values: FixValues) => void;
  /** Leave READY accounts out of this run, or put them back (DEF-BIL-8217). */
  onLeaveOut: (accountIds: readonly string[], back: boolean) => void;
}

/** DEF-BIL-8676 — *48 accounts · No reading this period. Fixed in Meter Reads.* (D1 11). */
function paneLine(total: number, meaning: string | null, screen: string | null, t: Translator): string {
  if (meaning === null) {
    return screen === null
      ? t("billing.bulkRun.check.paneCount", { count: total })
      : t("billing.bulkRun.check.paneCountIn", { count: total, screen });
  }
  return screen === null
    ? t("billing.bulkRun.check.paneMeaning", { count: total, meaning })
    : t("billing.bulkRun.check.paneMeaningIn", { count: total, meaning, screen });
}

export function ProblemTagPane(props: {
  runId: string;
  tag: CheckTag;
  tags: ReadonlyMap<string, CheckTag>;
  client: ApiClient;
  working: boolean;
  refusal: string | null;
  actions: CheckPaneActions;
  onOpenAccount: (accountId: string) => void;
  onOpenTag: (code: string) => void;
  links: CheckLinks;
  t: Translator;
}) {
  const { tag, t } = props;
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [per, setPer] = useState<PageSize>(50);
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
  // DEF-BIL-8677 — a row fixed inline stays on the page, green, reading
  // *Fixed · re-checked* (D1 13, 23) once the re-check has taken it OUT of the
  // tag. Only a row the server no longer lists is drawn fixed, so a fix that
  // did not take leaves the row as it was — never an optimistic "fixed".
  const [fixedRows, setFixedRows] = useState<ReadonlyMap<string, CheckTagRow>>(new Map());
  const [answer, setAnswer] = useState<string | null>(null);
  const [waiving, setWaiving] = useState<readonly string[] | "all" | null>(null);
  // DEF-BIL-10709 (tester L3-07) — the search reaches the server 300 ms after
  // the last keystroke, and only the pane's FIRST read sweeps for staleness;
  // every later page and keystroke reads what is saved (the beat sweeps open
  // runs every 60 s).
  const term = useDebouncedTerm(query.trim());
  const swept = useRef(false);
  const pageQuery = useQuery({
    queryKey: checkTagKey(props.runId, tag.code, page, per, term),
    queryFn: () => {
      const sweep = !swept.current;
      swept.current = true;
      return getCheckTag(props.runId, tag.code, page, per, term, props.client, sweep);
    },
    retry: false,
    placeholderData: (previous) => previous,
  });
  const rows: CheckTagRow[] = pageQuery.data?.results ?? [];
  // DEF-BIL-10709 — never the cached tag count over rows that have not
  // arrived: "1–20 of 20" over an empty table is the defect.
  const total = pageQuery.data?.count ?? null;
  const lateFees = pageQuery.data?.late_fees ?? null;
  const bulkChoices = tag.choices.filter((choice) => !PER_ACCOUNT_ONLY.has(`${tag.code}:${choice}`));
  const byDefault = ANSWERED_BY_DEFAULT.has(tag.code);
  const screen = fixScreenOf(tag);
  // DEF-BIL-8676 — the head line names where the problem is fixed even for a
  // tag decided here (*No reading … Fixed in Meter Reads.*, D1 11); the row's
  // own link still follows the served screen only.
  const taxonomyId = tagIdOf(tag.code);
  const headScreen = screen ?? (taxonomyId === null ? null : taxonomyFixScreen(taxonomyId));
  const severity = severityOf(tag.severity);
  // DEF-BIL-8418 / BR-BIL-1040 — *Answer for all N* opens on the run's stored
  // answer; where nothing is stored yet it opens on the tag's default (its S66
  // setting, else its first choice) and says so with an Apply button, because
  // a pre-selection nobody stored is not an answer (changes row 45).
  const opening = answer === null && tag.answer_for_all === null ? tag.default_choice : null;
  const chosenAnswer = answer ?? tag.answer_for_all ?? tag.default_choice ?? null;
  const keyOf = (row: CheckTagRow) => `${row.account_id}-${row.service_code ?? ""}`;
  const allOnPage = rows.length > 0 && rows.every((row) => selected.has(keyOf(row)));
  const selectedIds = [...new Set(rows.filter((row) => selected.has(keyOf(row))).map((row) => row.account_id))];
  // DEF-BIL-8472 — a row answers only from ITS OWN served list (an overlap has
  // no *Bill as it stands*), so *Apply to selected* sends only the rows that
  // may take the answer and says how many may not.
  const rowChoices = (row: CheckTagRow): readonly string[] => row.choices ?? tag.choices;
  const lawfulIds =
    chosenAnswer === null
      ? []
      : [
          ...new Set(
            rows
              .filter((row) => selected.has(keyOf(row)) && rowChoices(row).includes(chosenAnswer))
              .map((row) => row.account_id),
          ),
        ];
  const cannotTake = selectedIds.length - lawfulIds.length;
  const lastHead =
    severity === "decision" ? t("billing.bulkRun.col.decision") : severity === "blocks" ? t("billing.bulkRun.col.fix") : t("billing.bulkRun.col.more");
  // A tag's category is the SCREEN's grouping, not one of the engine's check
  // categories, so a pane's re-check re-checks its accounts in full.
  const recheckAll = () => props.actions.onRecheck(rows.map((row) => row.account_id));

  return (
    <section className="flex flex-col gap-3" aria-label={tagLabel(tag, t)} data-tag-pane={tag.code}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <Kicker as="div">{t(`billing.check.category.${tag.category}`)}</Kicker>
          <h3 className="m-0 mt-1 flex items-center gap-2 font-heading text-h5 font-semibold">
            {/* DEF-BIL-10202 — a tag the run answers by itself (a late fee bills
                unless waived) needs no decision and is answered here, so it
                carries no pill and no fix-screen sentence: its one line is the
                count and the total below. */}
            {tagLabel(tag, t)} {!byDefault && <SeverityPill severity={severity} t={t} />}
          </h3>
          {!byDefault && (
            <p className="m-0 mt-1 text-base text-neutral-700" data-pane-line="">
              {/* DEF-BIL-9005 — ACCOUNTS, as the tile and Answer for all count them;
                  the page count is service rows (two unread meters = two rows). */}
              {paneLine(tag.count, tagMeaning(tag.code, t), headScreen === null ? null : screenName(headScreen, t), t)}
            </p>
          )}
          {lateFees !== null && lateFees.currency !== null && (
            <p className="m-0 mt-1 font-heading text-base font-semibold" data-late-fee-total="">
              {t("billing.bulkRun.check.lateFeeTotal", { count: lateFees.accounts, total: formatMoney(lateFees.total, lateFees.currency) })}
            </p>
          )}
        </div>
        <div className="w-56 shrink-0">
          <label className="sr-only" htmlFor="account-search">
            {t("billing.bulkRun.check.findAccount")}
          </label>
          <input
            id="account-search"
            className={INPUT}
            type="search"
            placeholder={t("billing.bulkRun.check.findAccount")}
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(1);
            }}
          />
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 border border-divider bg-surface px-3 py-2 text-base" data-tag-actions={severity}>
        {severity === "decision" && byDefault && (
          <span data-waive-per-account="">{t("billing.bulkRun.check.waivePerAccount")}</span>
        )}
        {severity === "decision" && !byDefault && bulkChoices.length > 0 && (
          <>
            <span>{t("billing.bulkRun.check.answerAll", { count: tag.count })}</span>
            <SegmentedControl
              purpose="choice"
              name="answer-all"
              label={t("billing.bulkRun.check.answerAll", { count: tag.count })}
              segments={bulkChoices.map((choice) => ({ id: choice, label: choiceLabel(choice, t, tag.code), disabled: props.working }))}
              active={chosenAnswer ?? ""}
              onSelect={(choice) => {
                setAnswer(choice);
                if (needsReason(tag.code, choice)) {
                  setWaiving("all");
                  return;
                }
                props.actions.onDecide(tag, choice, "all");
              }}
            />
            {opening !== null && (
              <Button
                size="sm"
                variant="primary"
                disabled={props.working}
                onClick={() => {
                  setAnswer(opening);
                  if (needsReason(tag.code, opening)) {
                    setWaiving("all");
                    return;
                  }
                  props.actions.onDecide(tag, opening, "all");
                }}
                data-apply-all={opening}
              >
                {t("billing.bulkRun.check.applyAll", { count: tag.count })}
              </Button>
            )}
            {waiving !== null && chosenAnswer !== null && (
              <ReasonBox
                id="answer-all-reason"
                t={t}
                working={props.working}
                label={t("billing.bulkRun.check.waiveFor", { count: waiving === "all" ? tag.count : waiving.length })}
                onSave={(reason) => {
                  props.actions.onDecide(tag, chosenAnswer, waiving, reason);
                  setWaiving(null);
                }}
                onCancel={() => setWaiving(null)}
              />
            )}
            {selectedIds.length > 0 && chosenAnswer !== null && (
              <Button
                size="sm"
                disabled={props.working || lawfulIds.length === 0}
                onClick={() => {
                  if (needsReason(tag.code, chosenAnswer)) setWaiving(lawfulIds);
                  else props.actions.onDecide(tag, chosenAnswer, lawfulIds);
                }}
                data-apply-selected=""
              >
                {t("billing.bulkRun.check.applySelected", { count: lawfulIds.length })}
              </Button>
            )}
            {selectedIds.length > 0 && chosenAnswer !== null && cannotTake > 0 && (
              <span className="text-warning-700" data-cannot-take={cannotTake}>
                {t("billing.bulkRun.check.cannotTake", { count: cannotTake })}
              </span>
            )}
            {opening !== null && (
              <span className="text-neutral-700" data-preselected="">
                {t("billing.bulkRun.check.preselected")}
              </span>
            )}
            {/* DEF-BIL-9006 — an Estimate for all is not an answer until each
                account has its figure, so Price does not count them; say so. */}
            {tag.code === "missing_read" && chosenAnswer === "estimate" && (
              <span className="text-warning-700" data-estimate-needs-figure="">
                {t("billing.bulkRun.check.estimateNeedsFigure")}
              </span>
            )}
          </>
        )}
        {severity === "decision" && tag.choices.length === 0 && (
          <>
            <span>{t("billing.bulkRun.check.noAnswers")}</span>
            <Button size="sm" disabled={props.working || rows.length === 0} onClick={recheckAll} data-recheck="">
              {t("billing.bulkRun.check.recheck", { count: rows.length })}
            </Button>
          </>
        )}
        {severity === "blocks" && (
          <>
            {screen !== null && (
              <a
                href={props.links.fix(screen, null)}
                target="_blank"
                rel="noreferrer"
                className="font-heading font-semibold text-accent-700 underline"
                data-link="open-screen"
              >
                {t("billing.bulkRun.check.openScreen", { screen: screenName(screen, t) })}
              </a>
            )}
            <Button size="sm" disabled={props.working || rows.length === 0} onClick={recheckAll} data-recheck="">
              {t("billing.bulkRun.check.recheck", { count: rows.length })}
            </Button>
            <span className="text-neutral-700">{t("billing.bulkRun.check.staysOut")}</span>
          </>
        )}
        {severity === "warning" && <span>{t("billing.bulkRun.check.billsAnyway")}</span>}
      </div>
      {props.refusal !== null && (
        <p className="m-0 bg-danger-100 px-3 py-2 text-base text-danger-700" role="alert">
          {props.refusal}
        </p>
      )}

      {/* DEF-BIL-8419 — no page yet is not an empty tag. DEF-BIL-10709 — and
          it is not silence either: say it is loading, or that it failed. */}
      {pageQuery.data === undefined && pageQuery.isError ? (
        <p className="m-0 flex items-center gap-3 bg-danger-100 px-3 py-2 text-base text-danger-700" role="alert" data-pane-failed="">
          {t("billing.bulkRun.check.paneFailed")}
          <Button size="sm" onClick={() => void pageQuery.refetch()} data-pane-retry="">
            {t("billing.bulkRun.check.paneRetry")}
          </Button>
        </p>
      ) : pageQuery.data === undefined ? (
        <p className="m-0 text-base text-neutral-700" role="status" data-pane-loading="">
          {t("billing.bulkRun.check.paneLoading")}
        </p>
      ) : rows.length === 0 && fixedRows.size === 0 ? (
        <p className="m-0 text-base text-neutral-700" role="status">
          {t("billing.bulkRun.check.nobodyHere")}
        </p>
      ) : (
        <TableScroll>
          <PlainTable className={RUN_TABLE} data-run-table="tag">
            <thead>
              <tr>
                {/* DEF-BIL-10202 — no bulk answer on a tag the run answers by itself, so no selection. */}
                {!byDefault && (
                  <th scope="col" className="w-8">
                    <input
                      type="checkbox"
                      aria-label={t("billing.bulkRun.check.selectPage")}
                      checked={allOnPage}
                      onChange={() =>
                        setSelected((was) => {
                          const next = new Set(was);
                          for (const row of rows) {
                            if (allOnPage) next.delete(keyOf(row));
                            else next.add(keyOf(row));
                          }
                          return next;
                        })
                      }
                    />
                  </th>
                )}
                <th scope="col">{t("billing.bulkRun.col.account")}</th>
                <th scope="col">{t("billing.bulkRun.col.unit")}</th>
                <th scope="col">{t("billing.bulkRun.col.service")}</th>
                <th scope="col">{t("billing.bulkRun.col.alsoHas")}</th>
                <th scope="col">{lastHead}</th>
              </tr>
            </thead>
            <tbody>
              {[...fixedRows.entries()]
                .filter(([key]) => !rows.some((row) => keyOf(row) === key))
                .map(([key, row]) => (
                  <tr key={`fixed-${key}`} className="bg-success-100" data-row-account={row.account_no} data-row-fixed="">
                    {!byDefault && <td />}
                    <td>
                      <AccountCell row={row} onOpen={() => props.onOpenAccount(row.account_id)} />
                    </td>
                    <td>
                      {placeLine(row) ?? "—"}
                    </td>
                    <td>{row.service_code === null ? "—" : <ServiceLabel code={row.service_code} t={t} suffix={meterSuffix(row)} />}</td>
                    <td>—</td>
                    <td className="font-heading font-semibold text-success-700">{t("billing.bulkRun.check.fixedRechecked")}</td>
                  </tr>
                ))}
              {rows.map((row) => {
                const key = keyOf(row);
                const found = foundLine(row, t);
                return (
                  <tr key={key} data-row-account={row.account_no}>
                    {!byDefault && (
                      <td>
                        <input
                          type="checkbox"
                          aria-label={t("billing.bulkRun.check.selectRow", { account: row.account_no })}
                          checked={selected.has(key)}
                          onChange={() =>
                            setSelected((was) => {
                              const next = new Set(was);
                              if (next.has(key)) next.delete(key);
                              else next.add(key);
                              return next;
                            })
                          }
                        />
                      </td>
                    )}
                    <td>
                      <AccountCell row={row} onOpen={() => props.onOpenAccount(row.account_id)} />
                    </td>
                    <td>
                      {row.unit_id === null ? (
                        "—"
                      ) : (
                        <a href={props.links.unit(row.unit_id)} target="_blank" rel="noreferrer" className="text-accent-700 underline">
                          {placeLine(row) ?? t("billing.bulkRun.check.openUnit")}
                        </a>
                      )}
                    </td>
                    <td>{row.service_code === null ? "—" : <ServiceLabel code={row.service_code} t={t} suffix={meterSuffix(row)} />}</td>
                    <td>
                      {row.also_has.length === 0 ? (
                        "—"
                      ) : (
                        <span className="flex flex-wrap gap-1">
                          {row.also_has.map((code) => {
                            const other = props.tags.get(code);
                            return (
                              <TagChip
                                key={code}
                                code={code}
                                severity={severityOf(other?.severity ?? null)}
                                label={tagLabel(other ?? { code }, t)}
                                onOpen={props.onOpenTag}
                              />
                            );
                          })}
                        </span>
                      )}
                    </td>
                    <td>
                      <span className="flex flex-col gap-1">
                        {found !== "" && <span className="text-base" data-found="">{found}</span>}
                        {severity === "decision" && (
                          <DecisionControl
                            id={`decide-${row.account_id}-${row.service_code ?? "all"}`}
                            code={tag.code}
                            choices={rowChoices(row)}
                            answer={row.answer_source === "account" || row.answer_source === "default" ? row.answer : null}
                            accountNo={row.account_no}
                            t={t}
                            working={props.working}
                            estimate={
                              tag.code === "missing_read"
                                ? { basis: row.basis ?? null, quantity: row.answer_quantity ?? null, unit: row.answer_unit ?? null }
                                : undefined
                            }
                            onChoose={(choice, reason, estimate) =>
                              props.actions.onDecide(tag, choice, [row.account_id], reason, row.service_code, estimate)
                            }
                          />
                        )}
                        {row.answer_source === "tag" && row.answer !== null && (
                          <span className="text-neutral-700" data-answer-for-all="">
                            {t("billing.bulkRun.check.answeredForAll", { answer: choiceLabel(row.answer, t, tag.code) })}
                          </span>
                        )}
                        {row.fix_here !== null && (
                          <FixHereControl
                            id={`fix-${row.account_id}-${row.service_code ?? "all"}`}
                            fix={row.fix_here}
                            serviceCode={row.service_code}
                            client={props.client}
                            working={props.working}
                            t={t}
                            onFix={(values) => {
                              setFixedRows((was) => new Map(was).set(key, row));
                              props.actions.onFix(row.account_id, row.fix_here as Exclude<FixHere, null>, values);
                            }}
                          />
                        )}
                        {screen !== null && (
                          <a
                            href={props.links.fix(screen, row.account_id)}
                            target="_blank"
                            rel="noreferrer"
                            className="text-accent-700 underline"
                            data-link="fix-row"
                          >
                            {severity === "warning"
                              ? t("billing.bulkRun.check.seeIn", { screen: screenName(screen, t) })
                              : t("billing.bulkRun.check.fixIn", { screen: screenName(screen, t) })}
                          </a>
                        )}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </PlainTable>
        </TableScroll>
      )}
      {total !== null && total > 0 && (
        <ListPager total={total} page={page} per={per} onPage={setPage} onPer={(next) => { setPer(next); setPage(1); }} />
      )}
    </section>
  );
}

// ── Ready to bill (F12) with Leave out / Put back (B18, DEF-BIL-8217) ─────

type KindFilter = "all" | "regular" | "master";

export function ReadyToBillPane(props: {
  runId: string;
  client: ApiClient;
  working: boolean;
  actions: CheckPaneActions;
  links: CheckLinks;
  t: Translator;
}) {
  const { t } = props;
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<KindFilter>("all");
  const [page, setPage] = useState(1);
  const [per, setPer] = useState<PageSize>(50);
  const readyQuery = useQuery({
    queryKey: checkReadyKey(props.runId, page, per, query.trim(), kind),
    queryFn: () => getCheckReady(props.runId, { page, per, q: query.trim(), kind: kind === "all" ? "" : kind }, props.client),
    retry: false,
    placeholderData: (previous) => previous,
  });
  const data = readyQuery.data ?? null;
  const rows = data?.results ?? [];
  const total = data?.count ?? 0;
  // DEF-BIL-8687 — the drawn segment counts (*Regular 1,306 · Master 12*, D1 20):
  // each is the served count of that kind's first page, never a client tally.
  const regularQuery = useQuery({
    queryKey: checkReadyKey(props.runId, 1, 50, "", "regular"),
    queryFn: () => getCheckReady(props.runId, { page: 1, per: 50, q: "", kind: "regular" }, props.client),
    retry: false,
  });
  const masterQuery = useQuery({
    queryKey: checkReadyKey(props.runId, 1, 50, "", "master"),
    queryFn: () => getCheckReady(props.runId, { page: 1, per: 50, q: "", kind: "master" }, props.client),
    retry: false,
  });
  const regularCount = regularQuery.data?.count ?? null;
  const masterCount = masterQuery.data?.count ?? null;
  return (
    <section className="flex flex-col gap-3" aria-label={t("billing.bulkRun.check.readyToBill")} data-tag-pane={READY_TAG}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <Kicker as="div">{t("billing.bulkRun.check.readyKicker")}</Kicker>
          <h3 className="m-0 mt-1 flex items-center gap-2 font-heading text-h5 font-semibold">
            {t("billing.bulkRun.check.readyToBill")} <SeverityPill severity="ok" t={t} />
            {data !== null && data.left_out > 0 && (
              <StatusPill tone="neutral">{t("billing.bulkRun.check.leftOutCount", { count: data.left_out })}</StatusPill>
            )}
          </h3>
          <p className="m-0 mt-1 text-base text-neutral-700" data-ready-line="">
            {t("billing.bulkRun.check.readyLine", { count: total })}
          </p>
        </div>
        <div className="w-56 shrink-0">
          <label className="sr-only" htmlFor="ready-search">
            {t("billing.bulkRun.check.findAccount")}
          </label>
          <input
            id="ready-search"
            className={INPUT}
            type="search"
            placeholder={t("billing.bulkRun.check.findAccount")}
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(1);
            }}
          />
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-3 border border-divider bg-surface px-3 py-2 text-base" data-ready-filter="">
        <SegmentedControl
          name="ready-kind"
          label={t("billing.bulkRun.check.kindLabel")}
          segments={[
            { id: "all", label: t("billing.bulkRun.check.kind.all") },
            {
              id: "regular",
              label: regularCount === null ? t("billing.bulkRun.check.kind.regular") : t("billing.bulkRun.check.kind.regularN", { count: regularCount }),
            },
            {
              id: "master",
              label: masterCount === null ? t("billing.bulkRun.check.kind.master") : t("billing.bulkRun.check.kind.masterN", { count: masterCount }),
            },
          ]}
          active={kind}
          onSelect={(id) => {
            setKind(id as KindFilter);
            setPage(1);
          }}
        />
        <span className="text-neutral-700">{t("billing.bulkRun.check.leaveOneOut")}</span>
      </div>
      {rows.length === 0 ? (
        <p className="m-0 text-base text-neutral-700" role="status">
          {t("billing.bulkRun.check.nobodyHere")}
        </p>
      ) : (
        <TableScroll>
          <PlainTable className={RUN_TABLE} data-run-table="ready">
            <thead>
              <tr>
                <th scope="col">{t("billing.bulkRun.col.account")}</th>
                <th scope="col">{t("billing.bulkRun.col.unit")}</th>
                <th scope="col">{t("billing.bulkRun.col.services")}</th>
                <th scope="col">{t("billing.bulkRun.col.plan")}</th>
                <th scope="col">{t("billing.bulkRun.col.readings")}</th>
                <th scope="col">{t("billing.bulkRun.col.action")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                // DEF-BIL-8687 — a left-out row is dimmed (D1 21); no Status column.
                <tr key={row.account_id} className={row.left_out ? "text-neutral-600" : undefined} data-ready-row={row.left_out ? "left-out" : "ready"}>
                  <td>
                    <a
                      href={props.links.fix("accounts", row.account_id)}
                      target="_blank"
                      rel="noreferrer"
                      className="font-heading font-semibold text-accent-700 underline"
                    >
                      {row.account_no}
                    </a>
                    {row.customer_name !== null && <span className="block text-neutral-700">{row.customer_name}</span>}
                  </td>
                  <td>
                    {placeLine(row) ?? "—"}
                  </td>
                  {/* DEF-BIL-8414 — image 21: services, plan, readings. */}
                  <td data-ready-services="">
                    {(row.services ?? []).length === 0 ? (
                      "—"
                    ) : (
                      <span className="flex flex-wrap gap-1">
                        {(row.services ?? []).map((code) => (
                          <StatusPill key={code} tone="neutral">
                            <ServiceLabel code={code} t={t} />
                          </StatusPill>
                        ))}
                      </span>
                    )}
                  </td>
                  <td>{row.plan_name ?? "—"}</td>
                  <td>
                    {row.all_read === false ? (
                      <StatusPill tone="warning">{t("billing.bulkRun.check.someEstimated")}</StatusPill>
                    ) : (
                      t("billing.bulkRun.check.allRead")
                    )}
                  </td>
                  <td>
                    <Button
                      size="sm"
                      disabled={props.working}
                      onClick={() => props.actions.onLeaveOut([row.account_id], row.left_out)}
                      data-leave-out={row.left_out ? "put-back" : "leave-out"}
                    >
                      {row.left_out ? t("billing.bulkRun.check.putBack") : t("billing.bulkRun.check.leaveOut")}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
        </TableScroll>
      )}
      {total > 0 && (
        <ListPager total={total} page={page} per={per} onPage={setPage} onPer={(next) => { setPer(next); setPage(1); }} />
      )}
    </section>
  );
}

// ── Fix account (F11) ───────────────────────────────────────────────────────

function FixCard(props: {
  finding: CheckAccountFinding;
  accountId: string;
  accountNo: string;
  tags: ReadonlyMap<string, CheckTag>;
  index: number;
  client: ApiClient;
  working: boolean;
  actions: CheckPaneActions;
  links: CheckLinks;
  t: Translator;
}) {
  const { finding, t } = props;
  const tag = props.tags.get(finding.code) ?? null;
  const screen = fixScreenOf(finding.tag);
  const severity = severityOf(finding.severity);
  const found = foundLine(finding, t);
  const meaning = tagMeaning(finding.code, t);
  return (
    <article className="border border-divider bg-bg p-4" data-fix-card={finding.code}>
      <div className="flex items-center justify-between gap-3">
        <h3 className="m-0 flex items-center gap-2 font-heading text-md font-semibold">
          <SeverityMark severity={severity} />
          {tagLabel(finding.tag, t)}
        </h3>
        <SeverityPill severity={severity} t={t} />
      </div>
      {/* DEF-BIL-8686 — each card says what the problem means (D1 22). */}
      {(found !== "" || meaning !== null) && (
        <p className="m-0 mt-1 text-base text-neutral-700" data-fix-meaning="">
          {found !== "" ? found : meaning}
        </p>
      )}
      <div className="mt-2 flex flex-col gap-1">
        {severity === "decision" && tag !== null && (
          <DecisionControl
            id={`panel-decide-${props.index}`}
            code={finding.code}
            choices={finding.choices}
            answer={finding.answer}
            accountNo={props.accountNo}
            t={t}
            working={props.working}
            estimate={finding.code === "missing_read" ? { basis: null, quantity: null, unit: null } : undefined}
            onChoose={(choice, reason, estimate) =>
              props.actions.onDecide(tag, choice, [props.accountId], reason, finding.service_code, estimate)
            }
          />
        )}
        {finding.fix_here !== null && (
          <FixHereControl
            id={`panel-fix-${props.index}`}
            fix={finding.fix_here}
            serviceCode={finding.service_code}
            client={props.client}
            working={props.working}
            t={t}
            onFix={(values) => props.actions.onFix(props.accountId, finding.fix_here as Exclude<FixHere, null>, values)}
          />
        )}
        {screen !== null && (
          <a
            href={props.links.fix(screen, props.accountId)}
            target="_blank"
            rel="noreferrer"
            className="font-heading font-semibold text-accent-700 underline"
          >
            {severity === "warning"
              ? t("billing.bulkRun.check.seeIn", { screen: screenName(screen, t) })
              : t("billing.bulkRun.check.fixIn", { screen: screenName(screen, t) })}
          </a>
        )}
      </div>
    </article>
  );
}

export function FixAccountPanel(props: {
  runId: string;
  accountId: string;
  tags: ReadonlyMap<string, CheckTag>;
  client: ApiClient;
  working: boolean;
  actions: CheckPaneActions;
  onClose: () => void;
  links: CheckLinks;
  t: Translator;
}) {
  const { t } = props;
  const accountQuery = useQuery({
    queryKey: checkAccountKey(props.runId, props.accountId),
    queryFn: () => getCheckAccount(props.runId, props.accountId, props.client),
    retry: false,
  });
  const account = accountQuery.data ?? null;
  const findings = account?.findings ?? [];
  return (
    <SidePanel
      name="fix-account"
      kicker={t("billing.bulkRun.check.fixAccount")}
      title={account?.account_no ?? "—"}
      // DEF-BIL-8686 — *Sara Cohen · 1589 Pine Ct · Unit A* (D1 22).
      note={
        account === null
          ? undefined
          : [account.customer_name, account.address, account.unit_label].filter((part): part is string => !!part).join(" · ") ||
            undefined
      }
      closeLabel={t("billing.bulkRun.close")}
      onClose={props.onClose}
      footer={
        <>
          <span className="mr-auto text-base text-neutral-700">{t("billing.bulkRun.check.recheckNote")}</span>
          <Button variant="primary" disabled={props.working} onClick={() => props.actions.onRecheck([props.accountId])} data-recheck-account="">
            {t("billing.bulkRun.check.recheckAccount")}
          </Button>
        </>
      }
    >
      <Kicker as="div">{t("billing.bulkRun.check.problemsOnAccount", { count: findings.length })}</Kicker>
      <div className="mt-3 flex flex-col gap-3">
        {findings.map((finding, index) => (
          <FixCard
            key={`${finding.code}-${finding.service_code ?? ""}-${index}`}
            finding={finding}
            accountId={props.accountId}
            accountNo={account?.account_no ?? ""}
            tags={props.tags}
            index={index}
            client={props.client}
            working={props.working}
            actions={props.actions}
            links={props.links}
            t={t}
          />
        ))}
      </div>
    </SidePanel>
  );
}


/** DEF-BIL-8701 — the meter NUMBERS beside the service, *Water · W-10442*
 *  (D1 11–14); nothing when the row's service has no meter on file. */
function meterSuffix(row: CheckTagRow): string | undefined {
  const meters = row.meters ?? [];
  return meters.length === 0 ? undefined : meters.join(", ");
}
