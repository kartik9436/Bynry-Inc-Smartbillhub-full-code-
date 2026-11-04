// ── Trace ──────────────────────────────────────────────
// Change:   CR-161-BRC10 wave W6 — the utility's own fields on the STAFF New
//           Request (input) and on the request's Applicant tab (read-only).
// Rulings:  PO 2026-10-02, Part 2 row 15 (*"Staff New Request · Request detail
//           · Review / approval"*), *"account / customer / premises fields may
//           also be placed on Staff New Request"*, and gap 2 (*"Request detail
//           always shows the request's copy of every intake field (account,
//           customer, premises) read-only, so the reviewer sees what was typed
//           before approving"*). W6's judgments: decision log 2026-10-02
//           *"Custom fields on the staff service request (CR-161-BRC10 W6)"*.
// Rules:    B14 rule 43 (one component per piece of UI — the 4,800-line
//           capture page and the detail page only mount these) · rule 21
//           (Tailwind; on route-b-migrated.txt) · BR-SHL-036/037 (the kit's
//           controls, `custom_data.<key>` errors) · BR-TEN-048
// Tests:    src/features/customers/requestCustomFieldsW6.dom.test.tsx ·
//           06-backend/tests/test_cr161_w1_custom_field_settings.py (pairs
//           every `<CustomFields… entity=… screen=…>` below with the slot list)
// ───────────────────────────────────────────────────────
//
// ⚠ **WRITE EACH CALL WITH LITERAL `entity` AND `screen` STRINGS.** The W1
// pairing test reads them out of this file; a computed entity would be a slot
// no test could see — which is why the three record types are spelled out
// three times below rather than mapped over a list.
//
// WHERE EACH RECORD TYPE IS TYPED: the customer's and the account's fields on
// step 1 (*Applicant*, where the person and their category are asked), the
// premises' on step 2 (*Property*, where the address is). Step 4 (*Review*)
// lists every answer automatically, as Add Premises' review does.
import { useQueries } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getCustomFieldRegistry } from "@/api/endpoints";
import type { CustomFieldRegistryEntry } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import {
  CustomFieldsAnswers,
  CustomFieldsInput,
  CustomFieldsView,
  customDataChanges,
  missingRequiredLabels,
} from "@/components/CustomFields";
import type { CustomFieldValues } from "@/components/CustomFields";
import { FieldErrorsScope } from "@/components/FormModal";
import { Panel } from "@/components/Panel";

import { REQUEST_CUSTOM_ENTITIES } from "./serviceRequestEndpoints";
import type { RequestCustomData, RequestCustomEntity } from "./serviceRequestEndpoints";

const NS = "customers.serviceRequest.customFields";

/**
 * Gap 2 — *"Request detail always shows the request's copy of every intake
 * field"* — and a request has TWO intake screens: the clerk's New request
 * (W6) and the customer portal's new-service form (W7, `DEF-CUS-9214`). A
 * field asked only on the portal is read back here as surely as one typed by
 * a clerk.
 */
const REQUEST_INTAKE_SCREENS = ["REQUEST_NEW", "PORTAL_NEW_SERVICE"] as const;

/** The form's copy: always all three, so a control never reads `undefined`. */
export type RequestCustomForm = Record<RequestCustomEntity, CustomFieldValues>;

export function emptyRequestCustom(): RequestCustomForm {
  return { customers: {}, accounts: {}, premises: {} };
}

export function hydrateRequestCustom(stored: RequestCustomData | undefined): RequestCustomForm {
  return {
    customers: { ...(stored?.customers ?? {}) },
    accounts: { ...(stored?.accounts ?? {}) },
    premises: { ...(stored?.premises ?? {}) },
  };
}

function answered(value: unknown): boolean {
  if (value === undefined || value === null || value === "") return false;
  if (Array.isArray(value)) return value.length > 0;
  return !(typeof value === "string" && value.trim() === "");
}

/**
 * What a CREATE sends: the answered keys only, and no `custom_data` key at all
 * when nothing was typed — so a utility with no fields posts exactly what it
 * posted before W6.
 */
export function requestCustomPayload(form: RequestCustomForm): RequestCustomData | undefined {
  const out: RequestCustomData = {};
  for (const entity of REQUEST_CUSTOM_ENTITIES) {
    const values = Object.fromEntries(
      Object.entries(form[entity]).filter(([, value]) => answered(value)),
    );
    if (Object.keys(values).length > 0) out[entity] = values;
  }
  return Object.keys(out).length === 0 ? undefined : out;
}

/**
 * What a PATCH sends: per record type, only the keys whose answer changed
 * since the last save, a cleared one as `null` (the kit's `customDataChanges`).
 * A stored answer to a field switched off since is never re-sent, so the
 * server's unknown-key refusal cannot be tripped by a reopened request.
 */
export function changedRequestCustom(
  saved: RequestCustomForm,
  next: RequestCustomForm,
): RequestCustomData | undefined {
  const out: RequestCustomData = {};
  for (const entity of REQUEST_CUSTOM_ENTITIES) {
    const changes = customDataChanges(saved[entity], next[entity]);
    if (Object.keys(changes).length > 0) out[entity] = changes;
  }
  return Object.keys(out).length === 0 ? undefined : out;
}

/** The labels of the required fields left blank on one step, so `Continue`
 *  can name them; the server's submit check stays the rule underneath. */
export function missingOnStep(
  registries: Partial<Record<RequestCustomEntity, CustomFieldRegistryEntry[]>>,
  form: RequestCustomForm,
  entities: readonly RequestCustomEntity[],
): string[] {
  return entities.flatMap((entity) => missingRequiredLabels(registries[entity] ?? [], form[entity]));
}

/** The input registry a step's `validate` reads — the SAME cached query the
 *  controls below read, keyed identically. */
export function requestRegistryQuery(entity: RequestCustomEntity, client: ApiClient) {
  return {
    queryKey: queryKeys.customFieldRegistry(entity, "REQUEST_NEW", "input"),
    queryFn: () => getCustomFieldRegistry({ entity, screen: "REQUEST_NEW", mode: "input" }, client),
    retry: 1,
  };
}

/**
 * The step's own panel, drawn ONLY when the utility placed a field here — so a
 * utility with no fields sees the wizard exactly as it was (no empty box).
 * Reads the same cached registry the controls read.
 */
function Scope(props: {
  entities: readonly RequestCustomEntity[];
  errors: Record<string, string>;
  client?: ApiClient;
  children: ReactNode;
}) {
  const client = props.client ?? api;
  const results = useQueries({
    queries: props.entities.map((entity) => requestRegistryQuery(entity, client)),
  });
  if (!results.some((result) => (result.data ?? []).length > 0)) return null;
  return (
    <Panel as="section" data-request-custom-input={props.entities.join(" ")}>
      <FieldErrorsScope errors={props.errors}>{props.children}</FieldErrorsScope>
    </Panel>
  );
}

/**
 * Step 1 — the ACCOUNT's own fields.
 *
 * ⊕ Lane CF-1 (2026-10-18): the CUSTOMER's fields moved into the shared
 * customer form's *About the customer* panel (`customerForm/
 * CustomerCustomFieldsPanel`, slot `REQUEST_NEW`) — the same panel Move-in and
 * New connect draw (drawing set `customer-forms-2026-10-18`, image 03). The
 * account's stay here, below it.
 */
export function RequestApplicantCustomFields(props: {
  form: RequestCustomForm;
  onChange: (entity: RequestCustomEntity, values: CustomFieldValues) => void;
  errors: Record<string, string>;
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  return (
    <Scope entities={["accounts"]} errors={props.errors} client={props.client}>
      <CustomFieldsInput entity="accounts" screen="REQUEST_NEW"
        values={props.form.accounts}
        onChange={(values) => props.onChange("accounts", values)}
        heading={t(`${NS}.heading.accounts`)}
        client={props.client}
      />
    </Scope>
  );
}

/** Step 2 — the property's own fields. */
export function RequestPropertyCustomFields(props: {
  form: RequestCustomForm;
  onChange: (entity: RequestCustomEntity, values: CustomFieldValues) => void;
  errors: Record<string, string>;
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  return (
    <Scope entities={["premises"]} errors={props.errors} client={props.client}>
      <CustomFieldsInput entity="premises" screen="REQUEST_NEW"
        values={props.form.premises}
        onChange={(values) => props.onChange("premises", values)}
        heading={t(`${NS}.heading.premises`)}
        client={props.client}
      />
    </Scope>
  );
}

/** Step 4 — every answer typed, listed automatically. */
export function RequestCustomFieldsRecap(props: { form: RequestCustomForm; client?: ApiClient }) {
  const { t } = useTranslation();
  return (
    <div data-request-custom-recap="">
      <CustomFieldsAnswers
        entity="customers"
        screen="REQUEST_NEW"
        values={props.form.customers}
        heading={t(`${NS}.heading.customers`)}
        client={props.client}
      />
      <CustomFieldsAnswers
        entity="accounts"
        screen="REQUEST_NEW"
        values={props.form.accounts}
        heading={t(`${NS}.heading.accounts`)}
        client={props.client}
      />
      <CustomFieldsAnswers
        entity="premises"
        screen="REQUEST_NEW"
        values={props.form.premises}
        heading={t(`${NS}.heading.premises`)}
        client={props.client}
      />
    </div>
  );
}

/**
 * The request's Applicant tab — the REQUEST'S OWN COPY, read-only. Gap 2: every
 * field typed on Staff New Request is shown here whatever its Request detail
 * choice (`alsoInputOf`), and a field placed View on Request detail is shown
 * too. Nothing at all for a utility with no fields.
 */
export function RequestCustomFieldsDetail(props: {
  data: RequestCustomData | undefined;
  formatDate: (iso: string) => string;
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  const form = hydrateRequestCustom(props.data);
  return (
    <div data-request-custom-detail="">
      <CustomFieldsView entity="customers" screen="REQUEST_DETAIL"
        alsoInputOf={REQUEST_INTAKE_SCREENS}
        values={form.customers}
        formatDate={props.formatDate}
        heading={t(`${NS}.heading.customers`)}
        client={props.client}
      />
      <CustomFieldsView entity="accounts" screen="REQUEST_DETAIL"
        alsoInputOf={REQUEST_INTAKE_SCREENS}
        values={form.accounts}
        formatDate={props.formatDate}
        heading={t(`${NS}.heading.accounts`)}
        client={props.client}
      />
      <CustomFieldsView entity="premises" screen="REQUEST_DETAIL"
        alsoInputOf={REQUEST_INTAKE_SCREENS}
        values={form.premises}
        formatDate={props.formatDate}
        heading={t(`${NS}.heading.premises`)}
        client={props.client}
      />
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-161-BRC10 §R6 Part 2 row 15 + gap 2 · decision log 2026-10-02 (W6) · B14 rules 21, 43
// generated: 2026-10-02 by lane CF-W6
// checklist: A✔ B✔ C✔ D✔ E✔(ServiceRequestCapturePage + ServiceRequestDetailPage mount these) F✔ G✔ H=n/a
// gates: tsc · vitest requestCustomFieldsW6.dom.test.tsx · W1 pairing test
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
