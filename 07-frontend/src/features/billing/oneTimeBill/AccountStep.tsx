// ── Trace ──────────────────────────────────────────────
// Drawing: 05-prototype/one-time-bill-2026-09-30/*-1-account.png, *-02-*-dropdown-open.png,
//          *-33/34/35-state-problems-*.png (inventory.md §2, §6)
// Design:  11-one-time-bill-redesign.md §2 (step 1 fields by kind)
// Plan:    12-one-time-bill-build-plan.md F4, F5, F13
// Rules:   B14 rules 10 (asterisk on the label), 31, 33, 38/44 (a form is built
//          our way), 39 (LABEL → INPUT → HELPER)
// ───────────────────────────────────────────────────────
/**
 * STEP 1 — Account, then Period (Charge on a fee), then Dates.
 *
 * Every field shows its own problem under it and the whole set stands in one
 * list above the Account panel (`ProblemsBanner`) — all problems at once, each
 * on its field, which is gap 7 of the design's review (*"one problem at a
 * time, not on the field"*).
 *
 * ⚠ **NOTHING HERE TYPES A LIST.** Reasons and charge codes are the tenant's
 * own rows from Settings, handed in as options; a kind's fields are decided by
 * the model's `takesWindow` / `takesPeriodList` / `chargeCodeRule`.
 */
import type { AccountRow } from "@/api/endpoints";
import type {
  OneTimeBillAccount,
  OneTimeBillPreview,
} from "@/api/billingOpsEndpoints";
import { AccountCombobox } from "@/components/AccountCombobox";
import type { AccountComboboxOption } from "@/components/AccountCombobox";
import { Button } from "@/components/Button";
import { FactBlock } from "@/components/FactBlock";
import type { Fact } from "@/components/FactBlock";
import { DatePickerField, SelectField, TextField } from "@/components/FormModal";
import type { Translator } from "@/components/FormModal";
import { Panel } from "@/components/Panel";
import type { RemoteSearchStatus } from "@/components/RemoteSearchSelectField";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";

import {
  chargeCodeRule,
  derivedDueDate,
  problemFor,
  summaryLine,
  takesPeriodList,
  takesReason,
  takesWindow,
} from "./oneTimeBillModel";
import type { OneTimeBillForm, PeriodEntry, Problem } from "./oneTimeBillModel";
import { day, money } from "./oneTimeBillShared";
import type { OtbFormat } from "./oneTimeBillShared";

/** An option the step's selects draw — the tenant's own code and words. */
export interface CodeOption {
  value: string;
  label: string;
  /** DEF-RAT-8753 — a charge code priced *entered when used* (`per_case`). */
  entered?: boolean;
  /** DEF-RAT-9807 — that code's optional default, as the amount box starts it
   *  (`BR-RAT-1054` AMENDED 2026-10-06); `""` when it has none. */
  startAmount?: string;
}

/** The status pill's tone, read off the account's BEHAVIOUR class rather than
 *  its renameable name (a tenant may call *Active* anything it likes). */
export function accountStatusTone(behaviorClass: string | null | undefined): StatusTone {
  if (behaviorClass === "billable" || behaviorClass === "billable_base_only") return "success";
  if (behaviorClass === "terminal") return "muted";
  return "neutral";
}

/** One account as the dropdown draws it: name, status, number · address. */
export function accountOption(row: AccountRow, t: Translator): AccountComboboxOption {
  // DEF-BIL-8302 — customers' `premise` cell is already "1408 Elm St · Unit A"
  // (address · unit label); the label is added only when no premise is served.
  const address = [row.premise ?? row.unit_label].filter(
    (part): part is string => part !== null && part !== undefined && part !== "",
  );
  const detail = [row.account_no ?? t("billing.oneTimeBill.account.noNumber"), ...address].join(" · ");
  return {
    value: row.id,
    name: row.name ?? t("billing.oneTimeBill.account.noName"),
    detail,
    status: { label: row.status_name, tone: accountStatusTone(row.status_behavior_class) },
  };
}

/** Whether a field shows its problem yet: only after the clerk has pressed
 *  Continue once, so an empty form does not open in red. */
function shown(problems: readonly Problem[], field: string, t: Translator): string | undefined {
  const problem = problemFor(problems, field);
  return problem === undefined
    ? undefined
    : t(problem.messageKey, { ...problem.params, defaultValue: t("billing.oneTimeBill.problem.generic") });
}

// ── The list at the top ─────────────────────────────────────────────────────

/** Move focus to the field a problem stands on — its input carries the
 *  problem's field name as its `id`. */
export function focusField(field: string): void {
  const target = document.getElementById(field);
  if (target instanceof HTMLElement) target.focus();
}

/** `Fix 2 things to continue.` and every problem, above the Account panel. */
export function ProblemsBanner(props: { problems: readonly Problem[]; t: Translator }) {
  if (props.problems.length === 0) return null;
  return (
    <div
      className="mb-4 bg-danger-100 px-4 py-3 text-base text-danger-700"
      role="alert"
      data-otb-problems={props.problems.length}
    >
      <p className="m-0 font-heading font-semibold">
        {props.t("billing.oneTimeBill.problem.summary", { count: props.problems.length })}
      </p>
      <ul className="m-0 mt-1 list-disc pl-5">
        {props.problems.map((problem) => {
          const line = summaryLine(problem);
          return (
            <li key={problem.field}>
              {/* Each item takes the clerk to its field (PO report, 2.411.4). */}
              <button
                type="button"
                className="cursor-pointer border-0 bg-transparent p-0 text-left text-danger-700 underline"
                data-problem-field={problem.field}
                onClick={() => focusField(problem.field)}
              >
                {props.t(line.key, {
                  ...line.params,
                  defaultValue: props.t("billing.oneTimeBill.problem.generic"),
                })}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// ── Account ─────────────────────────────────────────────────────────────────

export function AccountPanel(props: {
  t: Translator;
  fmt: OtbFormat;
  term: string;
  onTermChange: (term: string) => void;
  search: RemoteSearchStatus;
  matches: readonly AccountRow[];
  chosen: AccountRow | null;
  onChoose: (row: AccountRow | null) => void;
  preview: OneTimeBillPreview | null;
  /** DEF-BIL-8281 — the account's own facts, read the moment it is chosen;
   *  the preview's `account` fills anything this has not answered. */
  account?: OneTimeBillAccount | null;
  problems: readonly Problem[];
}) {
  const { t, fmt, chosen } = props;
  const options = props.matches.map((row) => accountOption(row, t));
  const fromPreview = props.preview?.account ?? null;
  const fromAccount = props.account ?? null;
  const account =
    fromAccount === null && fromPreview === null
      ? null
      : {
          address: fromAccount?.address ?? fromPreview?.address ?? null,
          plan: fromAccount?.plan ?? fromPreview?.plan ?? null,
          cycle_due_days: fromAccount?.cycle_due_days ?? fromPreview?.cycle_due_days ?? null,
          // DEF-BIL-8329 — `undefined` is NOT READ YET, `null` is NO CYCLE.
          cycle_name:
            fromAccount !== null && fromAccount.cycle_name !== undefined
              ? fromAccount.cycle_name
              : fromPreview?.cycle_name,
          last_bill_on: fromAccount?.last_bill_on ?? fromPreview?.last_bill_on ?? null,
        };
  const facts: Fact[] =
    chosen === null
      ? []
      : [
          { id: "customer", label: t("billing.oneTimeBill.account.customer"), value: chosen.name ?? "—" },
          { id: "account", label: t("billing.oneTimeBill.account.number"), value: chosen.account_no ?? "—" },
          {
            id: "address",
            label: t("billing.oneTimeBill.account.address"),
            value: account?.address ?? chosen.premise ?? chosen.unit_label ?? "—",
          },
          { id: "plan", label: t("billing.oneTimeBill.account.plan"), value: account?.plan ?? "—" },
          {
            id: "status",
            label: t("billing.oneTimeBill.account.status"),
            value: (
              <StatusPill tone={accountStatusTone(chosen.status_behavior_class)}>
                {chosen.status_name}
              </StatusPill>
            ),
          },
          {
            id: "balance",
            label: t("billing.oneTimeBill.account.balance"),
            value: money(chosen.balance, { ...fmt, currency: chosen.balance_currency ?? fmt.currency }),
          },
          {
            id: "cycle",
            label: t("billing.oneTimeBill.account.cycle"),
            // DEF-BIL-8329 — the CYCLE, never its days to pay (which printed
            // "10 days to pay" under this label; they belong to Days to pay).
            // No cycle is a fact and says so; not read yet is a dash.
            value:
              account?.cycle_name === undefined
                ? "—"
                : account.cycle_name === null || account.cycle_name === ""
                  ? t("billing.oneTimeBill.account.cycleNone")
                  : account.cycle_name,
          },
          {
            id: "last-bill",
            label: t("billing.oneTimeBill.account.lastBill"),
            value: day(account?.last_bill_on ?? chosen.last_bill_at, fmt),
          },
        ];
  return (
    <Panel as="section" title={t("billing.oneTimeBill.account.title")} aria-label={t("billing.oneTimeBill.account.title")} data-otb-panel="account">
      <AccountCombobox
        id="account_id"
        label={t("billing.oneTimeBill.account.find")}
        required
        term={props.term}
        onTermChange={props.onTermChange}
        status={props.search}
        options={options}
        value={chosen?.id ?? ""}
        selectedName={chosen === null ? "" : (chosen.name ?? chosen.account_no ?? "")}
        onChange={(option) =>
          props.onChoose(option === null ? null : (props.matches.find((row) => row.id === option.value) ?? null))
        }
        words={{
          tooShort: t("billing.oneTimeBill.account.tooShort"),
          searching: t("billing.oneTimeBill.account.searching"),
          failed: t("billing.oneTimeBill.account.failed"),
          noMatch: t("billing.oneTimeBill.account.noMatch"),
        }}
        placeholder={t("billing.oneTimeBill.account.placeholder")}
        help={t("billing.oneTimeBill.account.help")}
        error={shown(props.problems, "account_id", t)}
      />
      {facts.length > 0 && (
        <div className="mt-4">
          {/* DEF-BIL-8318 — four across, in the drawing's order. */}
          <FactBlock name="otb-account" facts={facts} columns={4} />
        </div>
      )}
    </Panel>
  );
}

// ── Period (or Charge on a fee) ─────────────────────────────────────────────

const FIELD_GRID = "grid grid-cols-3 gap-4";

/** The missed-periods list: one From · To · Remove row each, then Add period. */
export function PeriodsList(props: {
  periods: readonly PeriodEntry[];
  onChange: (periods: PeriodEntry[]) => void;
  t: Translator;
  fmt: OtbFormat;
  problems: readonly Problem[];
}) {
  const { t } = props;
  function update(index: number, patch: Partial<PeriodEntry>): void {
    props.onChange(props.periods.map((p, i) => (i === index ? { ...p, ...patch } : p)));
  }
  return (
    <fieldset className="m-0 border-0 p-0" data-otb-periods={props.periods.length}>
      <legend className="mb-1 font-heading text-base font-semibold">
        {t("billing.oneTimeBill.period.missed")}
        <span className="text-accent" aria-hidden="true">
          {" *"}
        </span>
      </legend>
      {props.periods.map((period, index) => (
        <div
          key={index}
          className="grid grid-cols-[1fr_1fr_auto] items-end gap-2"
          data-otb-period-row={index}
        >
          <DatePickerField
            id={`sub_periods[${index}].period_start`}
            label={t("billing.oneTimeBill.period.from")}
            value={period.start}
            onChange={(value) => update(index, { start: value })}
            dateFormat={props.fmt.dateFormat}
            error={shown(props.problems, `sub_periods[${index}].period_start`, t)}
          />
          <DatePickerField
            id={`sub_periods[${index}].period_end`}
            label={t("billing.oneTimeBill.period.to")}
            value={period.end}
            onChange={(value) => update(index, { end: value })}
            dateFormat={props.fmt.dateFormat}
            error={shown(props.problems, `sub_periods[${index}].period_end`, t)}
          />
          <div className="field">
            <Button
              size="sm"
              disabled={props.periods.length === 1}
              aria-label={t("billing.oneTimeBill.period.removeNamed", { n: index + 1 })}
              onClick={() => props.onChange(props.periods.filter((_, i) => i !== index))}
            >
              {t("billing.oneTimeBill.period.remove")}
            </Button>
          </div>
        </div>
      ))}
      <div className="mt-2 flex flex-col items-start gap-1">
        <Button size="sm" onClick={() => props.onChange([...props.periods, { start: "", end: "" }])}>
          {t("billing.oneTimeBill.period.add")}
        </Button>
        <p className="field-help m-0" data-otb-period-count="">
          {t("billing.oneTimeBill.period.count", { count: props.periods.length })}
        </p>
      </div>
    </fieldset>
  );
}

export function PeriodPanel(props: {
  form: OneTimeBillForm;
  update: (patch: Partial<OneTimeBillForm>) => void;
  t: Translator;
  fmt: OtbFormat;
  reasons: readonly CodeOption[];
  charges: readonly CodeOption[];
  movedInOn: string | null;
  problems: readonly Problem[];
}) {
  const { form, t, fmt } = props;
  const chargeRule = chargeCodeRule(form.kind);

  if (form.kind === "fee") {
    return (
      <Panel as="section" title={t("billing.oneTimeBill.charge.title")} aria-label={t("billing.oneTimeBill.charge.title")} data-otb-panel="charge-code">
        <div className="grid grid-cols-3 gap-4">
          <div className="col-span-2">
            <SelectField
              id="charge_code"
              label={t("billing.oneTimeBill.charge.code")}
              required
              value={form.chargeCode}
              onChange={(value) =>
                props.update({
                  chargeCode: value,
                  chargeEntered: props.charges.find((option) => option.value === value)?.entered === true,
                  // DEF-RAT-9807 — the box starts at the code's default; the
                  // clerk may change it, and what they end with is billed.
                  enteredAmount: props.charges.find((option) => option.value === value)?.startAmount ?? "",
                })
              }
              options={props.charges.map(({ value, label }) => ({ value, label }))}
              placeholder={t("billing.oneTimeBill.charge.choose")}
              help={t("billing.oneTimeBill.charge.helpFee")}
              error={shown(props.problems, "charge_code", t)}
            />
          </div>
          {form.chargeEntered === true && (
            // DEF-RAT-8753 — images 41 · 64 · 70: the amount is entered when
            // the fee is used. Only for a code priced that way.
            <TextField
              id="entered_amount"
              label={t("billing.oneTimeBill.charge.enteredAmount")}
              required
              numeric
              value={form.enteredAmount ?? ""}
              onChange={(value) => props.update({ enteredAmount: value })}
              error={shown(props.problems, "entered_amount", t)}
            />
          )}
        </div>
      </Panel>
    );
  }

  return (
    <Panel as="section" title={t("billing.oneTimeBill.period.title")} aria-label={t("billing.oneTimeBill.period.title")} data-otb-panel="period">
      {takesWindow(form.kind) && (
        <div className={FIELD_GRID}>
          {form.kind === "first" ? (
            // PO change 2026-09-30 (*"Move -date should have date picker
            // cleark will overwrite it"*): pre-filled from the account's
            // recorded move-in date, editable for THIS bill only, and a
            // changed date says so beside the account's own.
            <DatePickerField
              id="period_start"
              label={t("billing.oneTimeBill.period.moveIn")}
              required
              value={form.periodStart}
              onChange={(value) => props.update({ periodStart: value })}
              dateFormat={fmt.dateFormat}
              help={
                props.movedInOn !== null && form.periodStart !== "" && form.periodStart !== props.movedInOn
                  ? t("billing.oneTimeBill.period.moveInDiffers", { date: day(props.movedInOn, fmt) })
                  : t("billing.oneTimeBill.period.moveInHelp")
              }
              error={shown(props.problems, "period_start", t)}
            />
          ) : (
            <DatePickerField
              id="period_start"
              label={t("billing.oneTimeBill.period.from")}
              required
              value={form.periodStart}
              onChange={(value) => props.update({ periodStart: value })}
              dateFormat={fmt.dateFormat}
              error={shown(props.problems, "period_start", t)}
            />
          )}
          <DatePickerField
            id="period_end"
            label={
              form.kind === "final"
                ? t("billing.oneTimeBill.period.moveOut")
                : t("billing.oneTimeBill.period.to")
            }
            required
            value={form.periodEnd}
            onChange={(value) => props.update({ periodEnd: value })}
            dateFormat={fmt.dateFormat}
            error={shown(props.problems, "period_end", t)}
          />
        </div>
      )}
      {takesPeriodList(form.kind) && (
        <PeriodsList
          periods={form.periods}
          onChange={(periods) => props.update({ periods })}
          t={t}
          fmt={fmt}
          problems={props.problems}
        />
      )}
      {takesReason(form.kind) && (
        <div className={`${FIELD_GRID} mt-4`}>
          <SelectField
            id="reason_code"
            label={t("billing.oneTimeBill.period.reason")}
            required
            value={form.reasonCode}
            onChange={(value) => props.update({ reasonCode: value })}
            options={[...props.reasons]}
            placeholder={t("billing.oneTimeBill.period.chooseReason")}
            error={shown(props.problems, "reason_code", t)}
          />
          {chargeRule === "optional" && (
            <SelectField
              id="charge_code"
              label={t("billing.oneTimeBill.charge.code")}
              value={form.chargeCode}
              onChange={(value) => props.update({ chargeCode: value })}
              options={[...props.charges]}
              placeholder={t("billing.oneTimeBill.charge.choose")}
              help={t("billing.oneTimeBill.charge.helpPenalty")}
              error={shown(props.problems, "charge_code", t)}
            />
          )}
        </div>
      )}
    </Panel>
  );
}

// ── Dates ───────────────────────────────────────────────────────────────────

export function DatesPanel(props: {
  form: OneTimeBillForm;
  update: (patch: Partial<OneTimeBillForm>) => void;
  t: Translator;
  fmt: OtbFormat;
  problems: readonly Problem[];
}) {
  const { form, t, fmt } = props;
  const due = derivedDueDate(form);
  return (
    <Panel as="section" title={t("billing.oneTimeBill.dates.title")} aria-label={t("billing.oneTimeBill.dates.title")} data-otb-panel="dates">
      <div className={FIELD_GRID}>
        <DatePickerField
          id="bill_date"
          label={t("billing.oneTimeBill.dates.billDate")}
          required
          value={form.billDate}
          onChange={(value) => props.update({ billDate: value })}
          dateFormat={fmt.dateFormat}
          error={shown(props.problems, "bill_date", t)}
        />
        <TextField
          id="due_days"
          label={t("billing.oneTimeBill.dates.dueDays")}
          required
          numeric
          value={form.dueDays}
          onChange={(value) => props.update({ dueDays: value })}
          help={t("billing.oneTimeBill.dates.dueDaysHelp")}
          error={shown(props.problems, "due_days", t)}
        />
        <TextField
          id="due_date"
          label={t("billing.oneTimeBill.dates.dueDate")}
          readOnly
          value={due === null ? "—" : day(due, fmt)}
          onChange={() => undefined}
        />
      </div>
    </Panel>
  );
}
