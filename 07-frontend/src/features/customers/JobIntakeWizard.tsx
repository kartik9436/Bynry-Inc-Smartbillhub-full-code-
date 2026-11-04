// ── Trace ──────────────────────────────────────────────
// Change:   CR-094-BRC01 step 2 wave G — **the complaint form and the service
//           form, each a FULL PAGE at its own address.** PO ruling 2026-09-12,
//           verbatim: *"A complaint form should be of a staple form and on new
//           page it should open up. Same for the services"*, confirmed
//           ***"Yes that is correct"***.
// Design:   `05-prototype/02 Accounts Menu Blueprint.pdf` pages 41–44
//           (`/brazosbend/complaints/new?step=1..4` — *Who is complaining ·
//           What happened · How fast we answer · Review & log*) and pages
//           47–52 (`/brazosbend/services/new?step=…`), read as IMAGES.
// Rules:    BR-WRK-006 (an anchor is required; an account is one) ·
//           BR-WRK-018 (the promise is stamped at the raise) · BR-WRK-058
//           (the kinds are a two-level catalogue the utility owns) ·
//           BR-SHL-018 (forward movement only after a step validates) ·
//           BR-SHL-019 (ONE transactional commit, single-flight) ·
//           BR-SHL-020 (the frame is handed plain language) · B14 rules 3 (a
//           multi-stage flow uses the stepper, not a page head), 31, 32, 33,
//           38 (a FORM is built our way), 39 (spacing)
// Tests:    src/features/customers/JobIntake.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **A PAGE, NOT A DIALOG, AND THE RULING IS ALREADY MADE.** B14 rule 30
// (*"a form that does not leave the user's current context opens in a
// DIALOG"*) was DECLINED on 2026-08-30 and the number is deliberately unused;
// the PO ruled this instance a page and confirmed it. Both forms also meet the
// estimate precedent's SCREEN column on their own: four steps, an address a
// person can send, and state that must survive a refresh. **Nothing here may
// be moved into a modal without a new ruling.**
//
// ⚠ **ONE COMPONENT, TWO FORMS** — `jobIntakeShared.JobIntakeSpec` is the only
// difference. PO standing instruction of the same day: *"Do all changes bsed on
// actual code - also dont create duplcate code"*. The two forms ask the same
// four questions (who, what kind, how fast, review) of the same table, so a
// second file would be a second review step and a second write to keep in step.
//
// ⚠ **THE WRITE IS `POST /work-orders` AND NOTHING ELSE.** That route is *"the
// ONE raise every door uses"* (`07-endpoints.md` §1 row 14) — the dispatcher's
// wizard, the Assets door, the move-out door and the rules engine all arrive
// there — so this form inherits `BR-WRK-006`'s anchor refusal and
// `BR-WRK-018`'s promise without restating either. A write of its own would be
// two rules to keep in step instead of none.
//
// ⚠ **NOTHING IS WRITTEN UNTIL THE LAST STEP** (the `BR-MET-112` shape). Close
// the tab on step 3 and there is no row, no `WO-` number burned and nothing for
// a dispatcher to wonder about. The frame keeps the entered state so Back
// loses nothing.
//
// ⚠ **WHAT THE DRAWING ASKS FOR THAT THIS DOES NOT COLLECT, EACH WITH ITS
// REASON — because `work_orders` has no column for it and a field with nowhere
// to store its value is dead UI (hard-won law 2):**
//
//   * **`Who told us` — a name and a phone** (page 41). The complainant may
//     not be the account holder, and the table has no reporter column. NOT
//     collected; REPORTED.
//   * **The complaint's own words, and an attachment** (page 41/42). There is
//     no description column on a work order — `technician_notes` is the field
//     crew fills in afterwards, which is a different fact. The drawing says so
//     itself: *"A job closes with a sentence somebody typed and nothing else
//     — no cause, no outcome category, no complaints register."* NOT
//     collected; REPORTED.
//   * **A cause or an outcome category** (page 42's own dashed block: *"There
//     is no vocabulary to offer"*). Not built, and the drawing agrees.
//   * **`Service fees`, the service form's drawn fourth step.** Page 219 calls
//     it *"a proposal"* on a model that *"already exists rather than a new
//     one"* — the SERVICE REQUEST's. `work_orders` carries no quoted,
//     collected or outstanding column. NOT built; REPORTED, and argued in
//     `jobIntakeShared.SERVICE_INTAKE`.
//
// What IS collected is every field the table can hold: the ACCOUNT it stands
// on, the KIND, the PRIORITY override and the AREA.
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { SelectField } from "@/components/FormModal";
import { PageHeader } from "@/components/PageHeader";
import { useToast } from "@/components/Toast";
import { WizardFrame, clampStepToReached, initialWizardNav } from "@/components/WizardFrame";
import type { WizardCommitOutcome, WizardNavState } from "@/components/WizardFrame";
import { getAccountDetail } from "@/api/endpoints";
import type { LookupEntry } from "@/api/endpoints";
import { listWorkAreas, raiseWorkOrderFromDispatcher } from "@/features/work/workEndpoints";
import { workOrderDetailPath } from "@/features/work/OrderDetailPage";
import { queryKeys } from "@/api/queryClient";
import { useTenantPath } from "@/routing/tenantPath";

import { ACCOUNT_SEARCH_IDLE, AccountFinder, useAccountSearch } from "./accountFinder";
import { accountHeadline } from "./customersShared";
import { ACCOUNTS_ROUTE } from "./customersShared";
import { ACCOUNTS_TAB_PARAM } from "./AccountsListPage";
import { useJobKinds } from "./jobIntakeShared";
import type { JobIntakeSpec } from "./jobIntakeShared";

export interface JobIntakeWizardProps {
  spec: JobIntakeSpec;
  client?: ApiClient; // test seam — screens never build their own transport
}

/** The four steps every configuration has. Named so the rail, the URL and the
 *  review all count the same set. */
const STEP_COUNT = 4;

export function JobIntakeWizard(props: JobIntakeWizardProps) {
  const { spec } = props;
  const client = props.client ?? api;
  const { t } = useTranslation();
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const toast = useToast();

  // ⚠ **THE STEP IS URL STATE**, which is what `WizardFrame` asks consumers
  // for and half of why this is a page: `?step=3` is an address, and
  // `clampStepToReached` is what makes a PASTED one safe — on a fresh load
  // `reached` is 1, so a deep link cannot skip a validation
  // (`BR-SHL-018`).
  const [params, setParams] = useSearchParams();
  const [nav, setNav] = useState<WizardNavState>(() =>
    clampStepToReached(Number(params.get("step") ?? 1), initialWizardNav(), STEP_COUNT),
  );

  function moveTo(next: WizardNavState) {
    setNav(next);
    const search = new URLSearchParams(params);
    search.set("step", String(next.step));
    setParams(search, { replace: true });
  }

  // Step 1 — who. The account this job stands on (`BR-WRK-006`'s third anchor).
  const [accountTerm, setAccountTerm] = useState("");
  const [accountId, setAccountId] = useState("");
  // Step 2 — what kind, and which service it is about.
  const [kindId, setKindId] = useState("");
  // Step 3 — how fast, and who picks it up.
  const [priorityId, setPriorityId] = useState("");
  const [areaId, setAreaId] = useState("");

  const accountSearch = useAccountSearch(accountTerm, client);
  const accountQuery = useQuery({
    queryKey: ["customers", "jobIntake", "account", accountId],
    queryFn: () => getAccountDetail(accountId, client),
    enabled: accountId !== "",
  });
  const account = accountQuery.data ?? null;

  const { kinds, failed: kindsFailed } = useJobKinds(spec, client);
  const areas = useQuery({
    queryKey: queryKeys.workAreas(),
    queryFn: () => listWorkAreas(client),
  });

  const chosenKind = useMemo(
    () => kinds.find((row) => row.id === kindId) ?? null,
    [kinds, kindId],
  );

  // ⚠ **THE PRIORITY IS NOT TYPED AND IS NOT DEFAULTED ON THIS FORM.** Page
  // 40's own line: *"Priority came from the kind of complaint, not from the
  // clerk."* `metering.connections._resolve_priority` reads the TYPE's own
  // `default_priority` when the payload names none, and four sub-types beat
  // their heading on purpose (`models.URGENT_BEATS_ITS_PARENT` — a gas leak
  // call-out, an odour report, no water, an outage). So the priority field on
  // step 3 is a DELIBERATE OVERRIDE with an empty default: leaving it empty is
  // what lets the utility's own answer stand.

  async function commit(): Promise<WizardCommitOutcome> {
    try {
      const raised = await raiseWorkOrderFromDispatcher(
        {
          // `BR-WRK-006` — the anchor. The wizard refuses an empty one on step
          // 1 and the database's `ck_work_orders_has_anchor` is the backstop.
          account_id: accountId || null,
          // ⚠ **THE KIND'S ID, NOT ITS WORDS.** `_resolve_order_type` takes
          // `type_id` exactly, or matches typed words against a code or a name
          // *"case-insensitively and in full"* and stays a bare string
          // otherwise — and a job with no resolved type gets NO priority and
          // therefore NO promise (`BR-WRK-018`). Sending the id is what makes
          // the respond-by figure exist.
          type: chosenKind?.name ?? "",
          type_id: kindId || null,
          priority_id: priorityId || null,
          area_id: areaId || null,
        },
        client,
      );
      toast(t(spec.toastKey, { ref: raised.order_no ?? "" }));
      // The record's own page — the blueprint's detail view, which already
      // exists (`CR-070` wave O's one destination).
      navigate(tenantPath(workOrderDetailPath("", raised.id).slice(1)));
      return { ok: true };
    } catch {
      // `BR-SHL-020` — the frame is handed PLAIN LANGUAGE, never an envelope.
      return { ok: false, reason: t(spec.commitFailedKey) };
    }
  }

  const fieldPrefix = spec.kind === "complaint" ? "cmp" : "svc";

  return (
    <div className="flex flex-col gap-6" data-job-intake={spec.kind}>
      {/* ⚠ **THE SHARED `PageHeader`, NOT A HAND-ROLLED KICKER AND `<h1>` —
          B14 rules 2 and 40.** Rule 2: *"One page header. EVERY screen,
          including task pages and workflows"*; rule 40 ratified the page-head
          title at 32px on 2026-09-12 with **no wizard exception, deliberately**
          (*"a second size for them would re-create the defect this rule
          closes"*), and fifteen wizards already mount this component. A
          bespoke `<h1 className="text-[2rem]">` here would be an arbitrary
          value AND a sixteenth place for the title size to drift.

          The blueprint draws exactly this head: the kicker `COMPLAINT`, the
          step's own title, and `← Complaints` back to the queue. */}
      <PageHeader
        kicker={t(spec.kickerKey)}
        title={t(spec.titleKey)}
        backTo={{
          to: `${tenantPath(ACCOUNTS_ROUTE)}?${ACCOUNTS_TAB_PARAM}=${spec.tab}`,
          label: t(spec.tabLabelKey),
        }}
      />
      <WizardFrame
        nav={nav}
        onNavChange={moveTo}
        steps={[
          {
            id: "who",
            label: t(spec.steps[0]),
            content: (
              // B14 rule 39 — 20px between FIELDS, and the field anatomy is
              // LABEL → INPUT → HELPER, which is what `TextField` draws.
              <div className="flex flex-col gap-5">
                <AccountFinder
                  idPrefix={fieldPrefix}
                  label={t("customers.accounts.col.account")}
                  required
                  term={accountTerm}
                  onTermChange={setAccountTerm}
                  search={accountSearch ?? ACCOUNT_SEARCH_IDLE}
                  value={accountId}
                  onChange={setAccountId}
                  t={(key, vars) => t(key, vars)}
                />
                {account !== null && (
                  // The account as it stands, so a clerk can see they picked
                  // the right one. B14 rule 31 — the HEADLINE, never the uuid.
                  <p className="text-sm text-neutral-700" data-chosen-account="">
                    {accountHeadline(account, (key, vars) => t(key, vars))}
                  </p>
                )}
              </div>
            ),
            validate: () =>
              accountId.trim().length > 0
                ? true
                : t("customers.jobIntake.refusal.accountRequired"),
          },
          {
            id: "what",
            label: t(spec.steps[1]),
            content: (
              <div className="flex flex-col gap-5">
                <SelectField
                  id={`${fieldPrefix}-kind`}
                  label={t("customers.jobIntake.field.kind")}
                  value={kindId}
                  onChange={setKindId}
                  required
                  help={t("customers.jobIntake.help.kind")}
                  placeholder=""
                  options={kinds.map((row) => ({
                    // B14 rule 31 — the VALUE is the id the call needs; the
                    // LABEL is what a person reads, and never the uuid.
                    value: row.id,
                    label: row.name,
                  }))}
                />
                {kindsFailed && (
                  <p className="text-sm text-neutral-700">
                    {t("customers.jobIntake.kindsUnavailable")}
                  </p>
                )}
              </div>
            ),
            validate: () =>
              kindId.trim().length > 0 ? true : t("customers.jobIntake.refusal.kindRequired"),
          },
          {
            id: "fast",
            label: t(spec.steps[2]),
            content: (
              <div className="flex flex-col gap-5">
                {/* ⚠ **AN OVERRIDE WITH AN EMPTY DEFAULT.** Leaving this blank
                    is what lets the kind's own priority stand, which is where
                    the four Urgent sub-types come from. */}
                <SelectField
                  id={`${fieldPrefix}-priority`}
                  label={t("work.orders.col.priority")}
                  value={priorityId}
                  onChange={setPriorityId}
                  help={t("customers.jobIntake.help.priority")}
                  placeholder=""
                  options={priorityChoices(kinds, chosenKind)}
                />
                <SelectField
                  id={`${fieldPrefix}-area`}
                  label={t("work.orders.filter.area")}
                  value={areaId}
                  onChange={setAreaId}
                  placeholder=""
                  options={(areas.data ?? []).map((area) => ({
                    value: area.id,
                    label: area.name,
                  }))}
                />
                {/* A FACT about when the promise is set, capped at rule 33's
                    six words. The figure itself is the SERVER's and is not
                    computed here. */}
                <p className="text-sm text-neutral-700" data-respond-by-note="">
                  {t("customers.jobIntake.respondBy.stamped")}
                </p>
              </div>
            ),
          },
          {
            id: "review",
            label: t(spec.steps[3]),
            content: (
              // Page 44: *"Every field from three steps"*. A fact list, so it
              // is the same four rows the commit sends and cannot drift from
              // them.
              <section className="flex flex-col gap-4" data-job-intake-review="">
                <h2 className="text-base font-semibold">
                  {t("customers.jobIntake.review.heading")}
                </h2>
                <dl className="flex flex-col gap-4">
                  <ReviewRow
                    label={t("customers.accounts.col.account")}
                    value={account === null ? null : accountHeadline(account, (key, vars) => t(key, vars))}
                  />
                  <ReviewRow
                    label={t("customers.jobIntake.field.kind")}
                    value={chosenKind?.name ?? null}
                  />
                  <ReviewRow
                    label={t("work.orders.col.priority")}
                    value={priorityLabel(kinds, chosenKind, priorityId)}
                  />
                  <ReviewRow
                    label={t("work.orders.filter.area")}
                    value={(areas.data ?? []).find((area) => area.id === areaId)?.name ?? null}
                  />
                </dl>
              </section>
            ),
          },
        ]}
        commitLabel={t(spec.commitKey)}
        commitFailedTitle={t(spec.commitFailedKey)}
        onCommit={commit}
        onCommitted={() => undefined}
      />
    </div>
  );
}

/**
 * One row of the review.
 *
 * A value nobody entered renders a DASH, which here means *"you left this
 * blank"* — and the two optional fields are genuinely optional, so that is the
 * true statement rather than an absence needing a sentence.
 */
function ReviewRow(props: { label: string; value: string | null }) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="text-xs font-semibold uppercase tracking-wide text-neutral-700">
        {props.label}
      </dt>
      <dd className="text-sm">{props.value ?? "—"}</dd>
    </div>
  );
}

/**
 * The PRIORITY options, which are the utility's own `work_priorities` rows as
 * they reach us on the kinds themselves.
 *
 * ⚠ **NOT A SECOND LOOKUP CALL AND NOT A TYPED LIST.** Each
 * `work_order_types` row carries its `default_priority` as the card's own
 * detail field, so the distinct set of those names IS this utility's priority
 * vocabulary — read from the catalogue rather than restated here (the service
 * list's own lesson: a hand-typed list does not grow when the data does, and
 * it fails silently).
 */
export function priorityChoices(
  kinds: readonly LookupEntry[],
  chosen: LookupEntry | null,
): { value: string; label: string }[] {
  const names = new Set<string>();
  for (const row of [...kinds, ...(chosen === null ? [] : [chosen])]) {
    const name = row.default_priority;
    if (typeof name === "string" && name.trim() !== "") {
      names.add(name);
    }
  }
  return [...names].sort().map((name) => ({ value: name, label: name }));
}

/**
 * What the review shows for PRIORITY when the clerk chose nothing.
 *
 * ⚠ **IT IS THE KIND'S OWN ANSWER, AND SAYING SO IS THE POINT.** Page 42's
 * warning: a gas leak hanging under a heading about consumer complaints *"would
 * quietly arrive with eight hours instead of four, chosen by nobody, with
 * nothing on any screen showing that a choice had been skipped."* So the review
 * prints the kind's default rather than a dash, and a clerk sees the figure they
 * are about to commit to.
 */
export function priorityLabel(
  kinds: readonly LookupEntry[],
  chosen: LookupEntry | null,
  chosenPriority: string,
): string | null {
  if (chosenPriority.trim() !== "") {
    return chosenPriority;
  }
  const row = chosen ?? null;
  const fallback = row === null ? null : kinds.find((k) => k.id === row.id) ?? row;
  const name = fallback?.default_priority;
  return typeof name === "string" && name.trim() !== "" ? name : null;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-094-BRC01 step 2 wave G · blueprint pages 41–44 and 47–52 · PO
//         rulings of 2026-09-12 quoted in the header · `POST /work-orders`
//         (`apps/work/services.raise_work_order` → metering's
//         `create_work_order`) · BR-WRK-006 · BR-WRK-018 · BR-WRK-058
// generated: 2026-09-12 by CR-094-BRC01 wave G
// checklist: A=n/a(no backend half in this file) B✔ C✔ D✔ E✔ F✔ G✔
//         H=deferred(PO 2026-08-09)
// exceptions: E3 **four fields the drawing asks for are NOT collected** — the
//         reporter's name and phone, the complaint's own words, an attachment,
//         and a cause/outcome category — because `work_orders` has no column
//         for any of them and a field with nowhere to store its value is dead
//         UI. Each is REPORTED; the drawing itself states the last one as a
//         gap · E3 **the service form's drawn `Service fees` step is not
//         built** — page 219 calls it *"a proposal"* and a work order carries
//         no price. REPORTED · E3 the PRIORITY override's options are derived
//         from the kinds' own `default_priority` values rather than from a
//         second lookup call, because that is the vocabulary the catalogue
//         already publishes to this screen
