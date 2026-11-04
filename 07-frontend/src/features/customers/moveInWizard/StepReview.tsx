// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-004 (S19 Move-In wizard, step 4 · Review) · CR-171-BRC10
//           P2.32 · P2.33 (lane MVI-WIZ-REV), **built from images 45 and 46**
// Rules:    B14 rules 21, 31, 33, 36, 41, 43, 44 · BR-TEN-035 (the account
//           number is given at Complete) · BR-CUS-092 (an identifier shows its
//           last four only) · hard rules 2 (money displays 2) and 3 (a reading
//           carries its unit) · BR-NOT-013 (nothing is promised as sent)
// Tests:    moveInWizard/StepReview.dom.test.tsx · MoveInMessages.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// 1 · WHAT IS DRAWN — images 45 and 46, top to bottom
// ══════════════════════════════════════════════════════════════════════════
//   Unit      ✎ Edit — Unit · Address · Previous · Services · Move-in date ·
//                      Opening read · Field visit
//   Customer  ✎ Edit — Customer ID · Legal name (Full name) · Trading as ·
//                      Customer type · Business type · EIN (SSN) · State of
//                      formation · Contact · Owners (Co-owners) · Email · Phone ·
//                      Bills go to · PO on bills · Documents · Mailing address
//   Billing   ✎ Edit — Plan · Preferences · Discounts · Tax · Fees · Payment ·
//                      Account number
//   Messaging          the table (`MoveInMessages`, P2.33)
// Each section is the kit's `Panel`, its facts the kit's `FactBlock` in its
// `rows` shape (label left on a tinted sixth, value right — added to the kit
// for this drawing, B14 rule 36). ✎ Edit opens that section's step.
//
// ══════════════════════════════════════════════════════════════════════════
// 2 · IT READS WHAT THE OTHER THREE STEPS HOLD THROUGH THE CONTRACT, NEVER
//     THROUGH THEIR INTERNALS
// ══════════════════════════════════════════════════════════════════════════
// Steps 1–3 are three other lanes' files (CR §8.1). What each will COMMIT is
// `ctx.own.<step>.payload`, whose keys are fixed by the API contract (§9.IDN-2
// `contact`, `co_owners`, `company`, `po_number`, `bills_go_to`, `documents`;
// §9.MONEY `fees`, `payment`, `discount_claims`, `tax_exemption`) — so this
// step summarises the payload, which is the one thing that cannot disagree
// with what Complete is sent. The wizard's own state (`ctx.customer`,
// `ctx.preferences`, `ctx.readsDraft`, `ctx.fieldVisit` …) fills the rest.
// A row whose fact no step holds is drawn with *Not set* or *None* — a stated
// value, never a blank.
//
// ══════════════════════════════════════════════════════════════════════════
// 3 · DIFFERENCES FROM THE DRAWING, RECORDED (CR-171, lane MVI-WIZ-REV record)
// ══════════════════════════════════════════════════════════════════════════
//   * *Customer type*, *Owners*, *Bills go to* and the company rows are drawn
//     for a COMPANY (image 45 is Kestrel Bakery LLC). A person draws *Full
//     name*, *Co-owners* and *SSN* in their places, and no Trading as /
//     Business type / Registered in / Contact / Bills go to / PO rows.
//   * *Mailing address* reads *Same as service address* or the address
//     itself — the drawn *As entered* says neither which nor what.
//   * The Plan's *a month* figure is the plan's base charge, rating's derived
//     Σ (`base_charges`), forwarded and never recomputed.
//   * *Registered in* reads **State of formation**: `register` is a word a
//     clerk only reads in its METER sense in `customers.*` (DEF-CUS-6422's
//     guard, `retiredWords.test.ts`), and a company's state of formation is
//     not a list it was put on.
//   * The Messaging defaults' TO / CHANNEL / WHEN are facts, not dropdowns —
//     `MoveInMessages.tsx` §1 says why.

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { DateCell } from "@/components/DateCell";
import { FactBlock } from "@/components/FactBlock";
import type { Fact } from "@/components/FactBlock";
import { formatMoney } from "@/components/MoneyCell";
import { sumAmounts } from "@/components/moneyMath";
import { Panel } from "@/components/Panel";
import { InlineLink } from "@/components/Surfaces";
import { useTenantCurrency } from "@/components/TenantRegional";
import { FIELD_VISIT_HOLDERS_KEY, FIELD_VISIT_OPTIONS_KEY, holderValue } from "@/features/work/FieldVisitOrders";
import { getRaiseOptions, listCrews } from "@/features/work/workEndpoints";

import { getCustomer } from "../customerEndpoints";
import { getServiceRequestDocuments } from "../serviceRequestEndpoints";
import {
  accountCategoryName,
  accountSubtypeName,
  useAccountCategories,
  useAccountSubtypes,
} from "../customersShared";
import { getUnitMoveInFacts, getUnitMoveInMeters } from "../moveDetail/moveDetailEndpoints";
import type { UnitMeterRow } from "../moveDetail/moveDetailEndpoints";
import {
  MoveInMessages,
  defaultMessagesPayload,
  extraMessagesPayload,
  hydrateDefaultChoices,
  hydrateExtraMessages,
} from "../MoveInMessages";
import type { DefaultChoices, ExtraMessageRow } from "../MoveInMessages";
import { CUSTOMER_KIND_COMPANY } from "../NewAccountWizard";
import { getUnitPricing, unitPricingQueryKey } from "../UnitPricingPanel";
import type { MoveInWizardContext, StepOwn } from "./moveInWizardContext";
import { reopenAsked } from "./StepCustomer";

/**
 * This step's own state, held by the wizard across the rail (see `StepOwn`):
 * the Messaging table's ADDED rows (P2.33). The defaults are the server's and
 * are never held here.
 */
export interface StepReviewOwn {
  extra_messages: ExtraMessageRow[];
  /** CR-190-BRC10 — the clerk's per-move-in answers for the editable defaults. */
  default_messages: DefaultChoices;
}

export function useStepReviewOwn(): StepOwn<StepReviewOwn> {
  const [value, set] = useState<StepReviewOwn>({ extra_messages: [], default_messages: {} });
  const extra = extraMessagesPayload(value.extra_messages);
  const defaults = defaultMessagesPayload(value.default_messages);
  const changedDefaults = Object.keys(value.default_messages).length > 0;
  return {
    value,
    set,
    // §9.FLOW P1.20 — OMITTED when nothing is added: a payload without it is
    // the old move-in, byte for byte. CR-190: the same for the defaults.
    payload: {
      ...(extra.length > 0 ? { extra_messages: extra } : {}),
      ...(defaults.length > 0 ? { default_messages: defaults } : {}),
    },
    park: {
      ...(value.extra_messages.length > 0 ? { extra_messages: value.extra_messages } : {}),
      ...(changedDefaults ? { default_messages: value.default_messages } : {}),
    },
    hydrate: (parked) => {
      const raw = typeof parked === "object" && parked !== null ? (parked as Record<string, unknown>) : {};
      set({
        extra_messages: hydrateExtraMessages(raw.extra_messages),
        default_messages: hydrateDefaultChoices(raw.default_messages),
      });
    },
  };
}

// ── Reading the contract's keys out of the other steps' payloads ───────────

type Bag = Record<string, unknown>;

function bag(value: unknown): Bag {
  return typeof value === "object" && value !== null && !Array.isArray(value) ? (value as Bag) : {};
}
function list(value: unknown): Bag[] {
  return Array.isArray(value) ? value.map(bag) : [];
}
function text(value: unknown): string {
  return typeof value === "string" ? value.trim() : typeof value === "number" ? String(value) : "";
}

/** `•••-••-1234` / `••-•••4567` — the last four only (BR-CUS-092). `""` when
 *  nothing was typed. */
export function maskedLastFour(value: string, shape: "ssn" | "ein"): string {
  const digits = value.replace(/\D/g, "");
  if (digits.length < 4) return "";
  return `${shape === "ssn" ? "•••-••-" : "••-•••"}${digits.slice(-4)}`;
}

/** Step 4 as the rail draws it. The commit is the frame's (`BR-SHL-019`). */
export function StepReview(props: { ctx: MoveInWizardContext }) {
  const { ctx } = props;
  const { t } = ctx;
  const tenantCurrency = useTenantCurrency();
  const currency = ctx.currency ?? tenantCurrency;
  const categories = useAccountCategories(ctx.client);
  const subtypes = useAccountSubtypes(ctx.client);
  const unitId = ctx.outgoingUnitId !== "" ? ctx.outgoingUnitId : ctx.unitId;

  // What steps 1–3 will commit, keyed by the contract (§9.IDN-2, §9.MONEY).
  const committed: Bag = Object.assign(
    {},
    ctx.own.unit.payload,
    ctx.own.customer.payload,
    ctx.own.billing.payload,
  );
  const linkedId = text(bag(committed.customer).customer_id);

  // The request's own papers — the read step 2's documents table makes,
  // under the same key.
  const requestDocs = useQuery({
    queryKey: ["service-request-documents", ctx.serviceRequestId],
    queryFn: () => getServiceRequestDocuments(ctx.serviceRequestId, ctx.client),
    enabled: ctx.serviceRequestId !== "",
    retry: false,
  });
  const facts = useQuery({
    queryKey: ["move-in-review-unit-facts", unitId],
    queryFn: () => getUnitMoveInFacts(unitId, ctx.client),
    enabled: unitId !== "",
    retry: false,
  });
  const meters = useQuery({
    queryKey: ["move-in-review-unit-meters", unitId],
    queryFn: () => getUnitMoveInMeters(unitId, ctx.client),
    enabled: unitId !== "",
    retry: false,
  });
  const pricing = useQuery({
    queryKey: unitPricingQueryKey(unitId),
    queryFn: () => getUnitPricing(unitId, ctx.client),
    enabled: unitId !== "",
    retry: false,
  });
  const linked = useQuery({
    queryKey: ["customer", linkedId],
    queryFn: () => getCustomer(linkedId, ctx.client),
    enabled: linkedId !== "",
    retry: false,
  });
  const raiseOptions = useQuery({
    queryKey: FIELD_VISIT_OPTIONS_KEY,
    queryFn: () => getRaiseOptions(ctx.client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const holders = useQuery({
    queryKey: FIELD_VISIT_HOLDERS_KEY,
    queryFn: () => listCrews({ per: 200 }, ctx.client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const none = t("customers.moveIn.review.none");
  const notSet = t("customers.moveIn.review.notSet");
  const joined = (parts: readonly string[]) => parts.filter((part) => part !== "").join(" · ");
  const orNone = (value: string) => (value === "" ? none : value);
  const amount = (value: string) => (currency === null ? value : formatMoney(value, currency));

  // ── Unit ─────────────────────────────────────────────────────────────────
  const address = facts.data?.unit.address ?? null;
  const addressLine =
    address === null
      ? ""
      : [address.line1 ?? "", address.city ?? "", [address.state, address.postal_code].filter(Boolean).join(" ")]
          .filter((part) => part !== "")
          .join(", ");
  const history = bag(bag(facts.data).history);
  const previous = bag(history.previous);
  const previousText =
    text(previous.account_no) !== ""
      ? joined([text(previous.name), text(previous.account_no)])
      : ctx.firstOccupant || history.first_occupant === true
        ? t("customers.moveIn.review.firstOccupant")
        : "";
  const meterUnits = new Map<string, string>();
  const walk = (rows: readonly UnitMeterRow[]) => {
    for (const row of rows) {
      if (row.unit) meterUnits.set(row.asset_no, row.unit);
      walk(row.children ?? []);
    }
  };
  for (const service of meters.data?.services ?? []) walk(service.meters);
  walk(meters.data?.unplaced ?? []);
  const reads = Object.values(ctx.readsDraft)
    .filter((row) => row.estimate || row.value.trim() !== "")
    .map((row) => {
      if (row.estimate) return joined([row.meterNo, t("customers.moveIn.review.estimated")]);
      // Hard rule 3: a reading is shown WITH its unit, or not as a figure.
      const unit = meterUnits.get(row.meterNo);
      return unit === undefined ? row.meterNo : joined([row.meterNo, `${row.value.trim()} ${unit}`]);
    });
  const typeName = (id: string) => (raiseOptions.data?.types ?? []).find((one) => one.id === id)?.name ?? "";
  const holderName = (key: string) =>
    key === "" ? "" : ((holders.data?.results ?? []).find((row) => holderValue(row) === key)?.name ?? "");
  const visit = ctx.fieldVisit.none
    ? t("customers.moveIn.review.noVisit")
    : ctx.fieldVisit.rows.map((row) => joined([typeName(row.type_id), holderName(row.holder), row.due_on])).join("; ");

  const unitFacts: Fact[] = [
    { id: "unit", label: t("customers.moveIn.review.unit"), value: orNone(ctx.unitLabel) },
    { id: "address", label: t("customers.moveIn.review.address"), value: orNone(addressLine) },
    { id: "previous", label: t("customers.moveIn.review.previous"), value: orNone(previousText) },
    {
      id: "services",
      label: t("customers.moveIn.review.services"),
      value: orNone(joined(ctx.ticked.map((code) => t(`rating.service.${code}`, { defaultValue: code })))),
    },
    {
      id: "moveInDate",
      label: t("customers.moveIn.review.moveInDate"),
      value:
        ctx.openedAt === "" ? (
          notSet
        ) : (
          <DateCell value={ctx.openedAt} timeZone={ctx.timeZone} dateFormat={ctx.dateFormat} />
        ),
    },
    { id: "openingRead", label: t("customers.moveIn.review.openingRead"), value: orNone(reads.join("; ")) },
    { id: "fieldVisit", label: t("customers.moveIn.review.fieldVisit"), value: orNone(visit) },
  ];

  // ── Customer ─────────────────────────────────────────────────────────────
  const customer = ctx.customer;
  const company = customer.customer_kind === CUSTOMER_KIND_COMPANY;
  const companyBlock = bag(committed.company);
  const contact = bag(committed.contact);
  const owners = list(committed.co_owners).map((owner) =>
    joined([
      text(owner.full_name),
      company && text(owner.ownership_pct) !== ""
        ? t("customers.moveIn.review.percent", { value: text(owner.ownership_pct) })
        : // ⊕ `DEF-CUS-10259` — the relationship's WORD (it printed `spouse`).
          text(owner.relationship) === ""
          ? ""
          : t(`customers.moveIn.customer.relationship.${text(owner.relationship)}`, {
              defaultValue: text(owner.relationship),
            }),
      owner.signs_for_company === true ? t("customers.moveIn.review.signs") : "",
    ]),
  );
  const kindWord = company
    ? t("customers.moveIn.review.kindCompany")
    : customer.customer_kind === ""
      ? ""
      : t("customers.moveIn.review.kindPerson");
  const customerId =
    linkedId === ""
      ? t("customers.moveIn.review.customerNew")
      : joined([linked.data?.customer_no ?? "", t("customers.moveIn.review.customerLinked")]);
  // ⊕ `DEF-CUS-10260` — the request's papers that hold a file are carried
  // onto the account at Complete (`carry_request_documents`) and the table
  // on step 2 lists them; Review counts them too (it said *None*). A card the
  // clerk staged over a request's paper is counted once.
  const ownCards = new Set(
    list(committed.documents)
      .map((doc) => text(doc.card_id))
      .filter((id) => id !== ""),
  );
  const fromRequest = (requestDocs.data?.documents ?? []).filter(
    (doc) => doc.file_present && !ownCards.has(doc.id),
  ).length;
  const documents = list(committed.documents).length + fromRequest;
  const mailing = customer.mailing_same
    ? t("customers.moveIn.review.mailingSame")
    : [
        customer.mailing_line1,
        customer.mailing_line2,
        customer.mailing_city,
        [customer.mailing_state, customer.mailing_postal_code].filter(Boolean).join(" "),
      ]
        .filter((part) => part !== "")
        .join(", ");
  const billsGoTo = text(committed.bills_go_to);
  const identifier = company ? maskedLastFour(customer.tax_id, "ein") : maskedLastFour(customer.ssn, "ssn");
  const companyOnly = (rows: Fact[]): Fact[] => (company ? rows : []);

  // CR-181-BRC10 F3 — the reopened account and the clerk's balance choice.
  const reopen = reopenAsked(ctx.own.customer.value);
  const reopenBalance = ctx.own.customer.value.reopen_balance;
  const reopenFacts: Fact[] =
    reopen === null
      ? []
      : [
          {
            id: "reopen",
            label: t("customers.moveIn.reopen.title"),
            value: joined([
              t("customers.moveIn.reopen.reopened", { account: reopen.account_no }),
              reopenBalance === "carry"
                ? reopen.outstanding === null
                  ? t("customers.moveIn.reopen.carryOption")
                  : t("customers.moveIn.reopen.carried", {
                      amount: formatMoney(reopen.outstanding, reopen.currency ?? currency ?? "USD"),
                    })
                : reopenBalance === "pay_first"
                  ? t("customers.moveIn.reopen.payFirstOption")
                  : "",
            ]),
          },
        ];
  const customerFacts: Fact[] = [
    { id: "customerId", label: t("customers.moveIn.review.customerId"), value: customerId },
    ...reopenFacts,
    {
      id: "name",
      label: company ? t("customers.moveIn.review.legalName") : t("customers.moveIn.review.fullName"),
      value: orNone(joined([customer.full_name.trim(), kindWord])),
    },
    ...companyOnly([
      { id: "tradingAs", label: t("customers.moveIn.review.tradingAs"), value: orNone(text(companyBlock.trading_as)) },
    ]),
    {
      id: "customerType",
      label: t("customers.moveIn.review.customerType"),
      value: orNone(
        joined([
          customer.account_type === "" ? "" : accountCategoryName(customer.account_type, categories.all),
          customer.account_subtype === "" ? "" : accountSubtypeName(customer.account_subtype, subtypes.rows),
        ]),
      ),
    },
    ...companyOnly([
      {
        id: "businessType",
        label: t("customers.moveIn.review.businessType"),
        value: orNone(text(companyBlock.business_type)),
      },
    ]),
    {
      id: "identifier",
      label: company ? t("customers.moveIn.review.ein") : t("customers.moveIn.review.ssn"),
      value: orNone(identifier),
    },
    ...companyOnly([
      {
        id: "registeredIn",
        label: t("customers.moveIn.review.registeredIn"),
        value: orNone(text(companyBlock.registered_in)),
      },
      {
        id: "contact",
        label: t("customers.moveIn.review.contact"),
        value: orNone(joined([text(contact.full_name), text(contact.job_title)])),
      },
    ]),
    {
      id: "owners",
      label: company ? t("customers.moveIn.review.owners") : t("customers.moveIn.review.coOwners"),
      value: orNone(owners.join("; ")),
    },
    { id: "email", label: t("customers.moveIn.review.email"), value: orNone(customer.email.trim()) },
    { id: "phone", label: t("customers.moveIn.review.phone"), value: orNone(customer.phone.trim()) },
    ...companyOnly([
      {
        id: "billsGoTo",
        label: t("customers.moveIn.review.billsGoTo"),
        value:
          billsGoTo === "contact_person"
            ? t("customers.moveIn.review.billsContact")
            : t("customers.moveIn.review.billsHolder"),
      },
      { id: "po", label: t("customers.moveIn.review.po"), value: orNone(text(committed.po_number)) },
    ]),
    {
      id: "documents",
      label: t("customers.moveIn.review.documents"),
      value: documents === 0 ? none : t("customers.moveIn.review.documentCount", { count: documents }),
    },
    { id: "mailing", label: t("customers.moveIn.review.mailing"), value: orNone(mailing) },
  ];

  // ── Billing ──────────────────────────────────────────────────────────────
  const plan = pricing.data?.plan ?? null;
  const planText =
    plan === null
      ? ""
      : joined([
          plan.name ?? "",
          plan.version === null ? "" : `v${plan.version}`,
          plan.base_charges === null || plan.base_charges === ""
            ? ""
            : t("customers.moveIn.review.perMonth", { amount: amount(plan.base_charges) }),
        ]);
  const prefs = ctx.preferences;
  const preferenceWords = [
    prefs.paperless ? t("customers.moveIn.review.paperless") : "",
    prefs.sms_reminders ? t("customers.moveIn.review.textReminders") : "",
    prefs.autopay ? t("customers.moveIn.review.autopay") : "",
  ];
  const offered = pricing.data?.discounts?.offered ?? [];
  const claimIds = list(committed.discount_claims).map((claim) => text(claim.discount_id));
  const discountNames =
    claimIds.length > 0
      ? claimIds.map((id) => offered.find((one) => one.discount_id === id)?.name ?? "")
      : ctx.discount.codes.map((code) => offered.find((one) => one.code === code)?.name ?? code);
  const exemption = bag(committed.tax_exemption);
  const tax =
    committed.tax_exempt === true || text(exemption.category_id) !== "" || prefs.tax_exempt
      ? t("customers.moveIn.review.exempt")
      : t("customers.moveIn.review.notExempt");
  const feeRows = list(committed.fees).filter((row) => text(row.amount) !== "");
  // `sumAmounts` is fixed-point and exact — never a float (hard rule 2).
  const feeTotal = feeRows.length === 0 ? null : sumAmounts(feeRows.map((row) => text(row.amount)));
  const feesText =
    feeTotal === null
      ? ""
      : joined([
          ...feeRows.map((row) => `${text(row.code)} ${amount(text(row.amount))}`),
          t("customers.moveIn.review.total", { amount: amount(feeTotal) }),
        ]);
  // ⚖️ PO ruling (7), 2026-10-05 — a deposit the clerk waived on step 3 is not
  // a fee (no line is written) and reads as waived, with its reason.
  const deposit = bag(committed.deposit);
  const depositWaived =
    text(deposit.decision) === "waived"
      ? t("customers.moveIn.review.depositWaived", { reason: text(deposit.waive_reason) })
      : "";
  const payment = bag(committed.payment);
  const paymentText =
    text(payment.mode) === "pay_now"
      ? joined([t("customers.moveIn.review.payNow"), text(payment.amount) === "" ? "" : amount(text(payment.amount))])
      : text(payment.mode) === "add_to_bill"
        ? joined([
            t("customers.moveIn.review.addToBill"),
            feeTotal === null ? "" : t("customers.moveIn.review.onFirstBill", { amount: amount(feeTotal) }),
          ])
        : "";

  const billingFacts: Fact[] = [
    {
      id: "plan",
      label: t("customers.moveIn.review.plan"),
      // `DEF-CUS-9762` — a read still in flight is not the fact that there is
      // no plan: it says it is loading until the answer lands.
      value:
        pricing.isPending && unitId !== "" ? (
          <span aria-busy="true" data-review-loading="plan">
            {t("states.loading")}
          </span>
        ) : (
          orNone(planText)
        ),
    },
    {
      id: "preferences",
      label: t("customers.moveIn.review.preferences"),
      value: joined(preferenceWords) || notSet,
    },
    { id: "discounts", label: t("customers.moveIn.review.discounts"), value: orNone(joined(discountNames)) },
    { id: "tax", label: t("customers.moveIn.review.tax"), value: tax },
    { id: "fees", label: t("customers.moveIn.review.fees"), value: orNone(feesText) },
    ...(depositWaived === ""
      ? []
      : [{ id: "deposit", label: t("customers.moveIn.review.deposit"), value: depositWaived }]),
    { id: "payment", label: t("customers.moveIn.review.payment"), value: paymentText || notSet },
    {
      id: "accountNumber",
      label: t("customers.moveIn.review.accountNumber"),
      // BR-TEN-035: allocated from the tenant series AT COMPLETE — unless the
      // returning customer's own account is reopened (BR-CUS-1119): same number.
      value:
        reopen === null
          ? t("customers.moveIn.review.numberAtComplete")
          : t("customers.moveIn.reopen.reopened", { account: reopen.account_no }),
    },
  ];

  const section = (id: string, title: string, step: number, rows: readonly Fact[]) => (
    <Panel
      as="section"
      title={title}
      data-review-section={id}
      trailing={
        <InlineLink onClick={() => ctx.goToStep(step)} data-review-edit={id}>
          {t("customers.moveIn.review.edit")}
        </InlineLink>
      }
    >
      <FactBlock name={`move-in-review-${id}`} facts={rows} variant="rows" />
    </Panel>
  );

  const depositTaken = ctx.deposit.decision === "required" && ctx.deposit.take_now;
  return (
    <div className="flex flex-col gap-5" data-move-in-review="">
      {section("unit", t("customers.moveIn.review.sectionUnit"), 1, unitFacts)}
      {section("customer", t("customers.moveIn.review.sectionCustomer"), 2, customerFacts)}
      {section("billing", t("customers.moveIn.review.sectionBilling"), 3, billingFacts)}
      <MoveInMessages
        category={customer.account_type}
        depositTaken={depositTaken}
        // DEF-CUS-10324 (CR-186-BRC10): a deposit taken today is POSTED and
        // held at once, so its letter is queued with its receipt — there is no
        // clearing date to wait on.
        depositCleared={depositTaken}
        to={customer.full_name}
        extra={ctx.own.review.value.extra_messages}
        onExtraChange={(next) => ctx.own.review.set({ ...ctx.own.review.value, extra_messages: next })}
        defaults={ctx.own.review.value.default_messages}
        onDefaultsChange={(next) => ctx.own.review.set({ ...ctx.own.review.value, default_messages: next })}
        coOwners={list(committed.co_owners)
          .map((owner) => text(owner.full_name))
          .filter((name) => name !== "")}
        unitOwner={facts.data?.owner?.name ?? null}
        visitPlanned={!ctx.fieldVisit.none && ctx.fieldVisit.rows.length > 0}
        t={t}
        client={ctx.client}
      />
    </div>
  );
}
