// ── Trace ──────────────────────────────────────────────
// Change:  **PO drawings of 2026-09-25** — putting service back on stops being
//          one dialog and becomes a SCREEN of two steps, at an address of its
//          own. `DEF-CUS-6743`.
// Story:   `US-CUS-032` (`S148`) — *Put service back on*.
// Drawing: `Reconnect1.png` · `Reconnect2.png` · `MasterReconnect1.png` ·
//          `MasterReconnect2.png`, all four read AS IMAGES (B14 rule 42),
//          never from extracted text and never from a description.
//          ⚠ **The Accounts blueprint draws NOTHING here** — 283 pages, the
//          word *reconnect* on five of them, every one a fee, a job type or
//          prose. p143 was rendered and read: three case actions, `Hold the
//          case`, `Open the account`, `Mark as cut`, and no reconnect screen.
// Rules:   `BR-CUS-1097` (the balance is SHOWN and never blocks) ·
//          `BR-CUS-1098` (a master's units come back TOGETHER; residue
//          transferred up is its own line; one work order per service point) ·
//          `BR-CUS-104` (the fee landed at the cut — untouched) ·
//          `BR-WRK-055` (the flow does not wait for the visit) · B14 rule 44
//          (our UI standard beats the drawing on HOW it is built, INCLUDING
//          THE FRAME) · rule 43 (a piece of UI is a COMPONENT) · rule 37 (a
//          drawn figure is an illustration) · rule 33 (label ≤ 3 words · fact
//          ≤ 6 · RATIONALE is ZERO WORDS) · rule 31 (no database id on screen)
//          · rule 21 (Tailwind utilities; this file is on
//          `src/styles/route-b-migrated.txt`, added in this commit) ·
//          hard rule 2 (money displays at 2 and is never parsed here) ·
//          hard rule 8 (the address is the premises', walked by the server).
// Tests:   `ReconnectPage.dom.test.tsx` · `10-scripts/po20260925_reconnect_walk.mjs`
// ───────────────────────────────────────────────────────
/**
 * `S148` — **Put service back on**, in two steps: *Choose*, then *Confirm*.
 *
 * ════════════════════════════════════════════════════════════════════════
 * WHY IT IS A SCREEN AND NOT THE DIALOG IT REPLACES
 * ════════════════════════════════════════════════════════════════════════
 * The dialog it replaces is the §5 test in the UI skill answered wrongly on
 * five of its six lines: this holds TWO TABLES of its own, has more than one
 * step and more than one outcome, a clerk raises work orders from it and comes
 * back to it, and losing it on refresh costs a clerk a building's worth of
 * decisions. **It needs an address a person can send**, which is 4.8, and the
 * address is the case record's plus one segment so the back link writes itself.
 *
 * ════════════════════════════════════════════════════════════════════════
 * ⚠ THE FRAME IS THE KIT'S AND NOT THE DRAWING'S — B14 RULE 44
 * ════════════════════════════════════════════════════════════════════════
 * The drawings show the two steps as a full-width two-cell bar, one black and
 * one grey. **`WizardFrame`'s numbered rail is what is built**, because rule 44
 * gives our UI standard the win on spacing, sizes, the type scale, the tokens
 * and the component kit — *INCLUDING THE FRAME* — every time, on every screen.
 * Rule 37 says the same thing from the other side: a figure drawn in a
 * wireframe is an illustration. **What the drawing decides is the CONTENT** —
 * that there are two steps, that they are called *Choose* and *Confirm*, and
 * what is on each — and every one of those is built exactly as drawn.
 *
 * ════════════════════════════════════════════════════════════════════════
 * ⚠ THE BALANCE IS A FACT HERE, NOT A GATE — AND THE PRODUCT STILL REFUSES
 * ════════════════════════════════════════════════════════════════════════
 * `BR-CUS-1097` (PO 2026-09-25, *"Show what's still owed and let the clerk
 * proceed"*) supersedes `BR-CUS-104`'s clear-before-reconnecting gate. So step
 * 2 draws the money as a TABLE and one warning sentence — a figure and four
 * words — and **nothing on this screen refuses over it**.
 *
 * ✅ **THE PARAGRAPH BELOW IS HISTORY (DEF-CUS-10657, 2026-10-29).**
 * `not_settled` went on 2026-09-25 and the commit's hold on it is released:
 * PO C1, *"Restore = Reconnect request"* — on a `cut` case Confirm SENDS the
 * reconnect request (`POST …/reconnect/request`), on a `reconnecting` case it
 * COMPLETES it (`POST …/reconnect/complete`). See the decision log of
 * 2026-10-29 for the reading and its worked example.
 *
 * ⛔ **`disconnects.reconnect_blockers` STILL APPENDS `not_settled`, AND THAT
 * FILE BELONGS TO ANOTHER LANE** (`DEF-CUS-6742`). So the commit renders
 * DISABLED WITH ITS REASON AS VISIBLE TEXT (`BR-SHL-025`) whenever the server
 * says it would refuse — reported, never hidden, because a screen that offers a
 * button the server will refuse is worse than one that says so, and hiding it
 * is how a signed rule stays unbuilt while every screen looks finished. **The
 * refusal is ASKED of the server (`commit_refused_by`) and never restated
 * here**, so the day that clause goes this screen starts working with nothing
 * on this side edited (hard-won law 1).
 *
 * ════════════════════════════════════════════════════════════════════════
 * ⚠ RATIONALE IS ZERO WORDS ON SCREEN (B14 rule 33)
 * ════════════════════════════════════════════════════════════════════════
 * The warning reads *"$879.50 still owed. You may continue."* — it states the
 * figure and gets out of the way. It does NOT explain the rule, the retention,
 * why nothing blocks, or what the product used to do. Rationale is REMOVED and
 * never shortened; all of it is in this docstring and in the register, which is
 * what both are FOR.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { Button } from "@/components/Button";
import { DateCell } from "@/components/DateCell";
import { EditableTable } from "@/components/EditableTable";
import { DatePickerField, SelectField, TextField } from "@/components/FormModal";
import { MoneyCell, formatMoney } from "@/components/MoneyCell";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { LoadingSkeleton } from "@/components/StateFrame";
import { WizardFrame, clampStepToReached } from "@/components/WizardFrame";
import type { WizardNavState } from "@/components/WizardFrame";
import { WarningBox } from "@/components/WarningBox";
// ⚠ **ONE LABEL PER SERVICE CODE PRODUCT-WIDE, AND IT IS NOT MINE TO WRITE
// AGAIN.** `serviceLabel` keys on `rating.service.*`, which holds all ELEVEN
// platform codes; a hand-typed map here would be the twelfth place the list is
// spelled out and would show a clerk `storm_water` for four of them. That is
// `DEF-763` exactly, and the first draft of this screen made it — the walk
// showed the word `electric` in lower case on the running product while every
// assertion passed, because a `defaultValue` fallback hides it.
import { serviceLabel } from "@/features/assets/assetsShared";
import { useRegional } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

import { disconnectRecordKey, disconnectRecordPath } from "../record/disconnectRecordEndpoints";
import {
  RECONNECT_SCREEN,
  completeReconnect,
  raiseReconnectWorkOrder,
  readReconnect,
  reconnectKey,
  requestReconnect,
} from "./reconnectEndpoints";
import type { ReconnectDetail, ReconnectMoney, ReconnectServiceRow } from "./reconnectEndpoints";

/**
 * One row of the service table AS THE CLERK HAS EDITED IT.
 *
 * ⚠ **THE SERVER'S ROW IS THE SEED AND THE CLERK'S IS THE TRUTH**, which is
 * why they are two types. A clerk removes a row, adds one, changes how a
 * service goes back and types an instruction; none of that is a fact about the
 * case until the commit, and a screen that mutated the read would lose it all
 * on the next refetch.
 */
interface ChosenRow extends ReconnectServiceRow {
  key: string;
  how: string;
  /** Set by the row's own `+ Raise work order` (4.5) — reference and crew. */
  raised: { reference: string; assignee: string | null; done?: boolean; accepted?: boolean } | null;
  raising: boolean;
  /** `DEF-CUS-9674` — the catalogue key of the last raise that came back with
   *  no job: the server's refusal, or its not-raised warning. Shown on the row. */
  refusal?: string | null;
}

/**
 * What a row is CALLED — *Water*, or *Water — common supply*.
 *
 * ⚠ **THE SERVICE HALF IS `serviceLabel` AND NOTHING ELSE.** One label per
 * service code product-wide, keyed on `rating.service.*`, which holds all
 * eleven platform codes. The scope half is this screen's own word for WHERE
 * the service is restored, which the drawing gives it.
 */
function rowLabel(row: { service: string | null; scope: string | null }, t: TFunction): string {
  const service = row.service ? serviceLabel(row.service, t) : "";
  if (!row.scope) {
    return service;
  }
  const scope = t(`customers.reconnect.scope.${row.scope}`);
  return service ? `${service} — ${scope}` : scope;
}

function seedRows(detail: ReconnectDetail): ChosenRow[] {
  return detail.services.rows.map((row, index) => ({
    ...row,
    key: `${row.service ?? "x"}-${row.scope ?? "x"}-${index}`,
    how: row.how_default,
    raised: row.work_order,
    raising: false,
  }));
}

/** Rule 2 — the string the server sent, at 2dp, through the kit's own cell. */
function Money(props: { money: ReconnectMoney | null; negative?: boolean }) {
  const { t } = useTranslation();
  if (!props.money?.stored) {
    return <span className="text-neutral-600">{t("customers.reconnect.absent")}</span>;
  }
  return (
    <span>
      {props.negative ? "− " : null}
      <MoneyCell amount={props.money.stored} currency={props.money.currency ?? "USD"} />
    </span>
  );
}

export function ReconnectPage(props: { client?: ApiClient }) {
  const { t } = useTranslation();
  const params = useParams();
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const regional = useRegional({});
  const reference = params.ref ?? "";
  const client = props.client ?? api;
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: reconnectKey(reference),
    queryFn: () => readReconnect(reference, client),
    enabled: reference !== "",
  });

  // ⚠ **THE STEP IS URL STATE, WHICH IS `WizardFrame`'s OWN CONTRACT** (A9,
  // `BR-SHL-018`): *"the step number is URL state (`?step=`) — pass
  // `nav`/`onNavChange` and serialize in the consumer, restoring through
  // `clampStepToReached`"*. On a screen whose whole point is having an address
  // a person can send, a step that lives only in memory would make half of it
  // unsendable. `clampStepToReached` is what stops a pasted `?step=2` skipping
  // step 1 — the fence is the frame's, not this screen's to re-implement.
  const [search, setSearch] = useSearchParams();
  const [nav, setNav] = useState<WizardNavState>(() => {
    const asked = Number(search.get("step") ?? "1");
    return clampStepToReached(asked, { step: 1, reached: asked > 1 ? asked : 1 }, 2);
  });
  const [rows, setRows] = useState<ChosenRow[] | null>(null);
  const [restoreOn, setRestoreOn] = useState<string | null>(null);
  const [addService, setAddService] = useState("");

  if (query.isLoading) {
    return <LoadingSkeleton variant="card" />;
  }
  const detail = query.data;
  if (!detail) {
    return (
      <div data-screen={RECONNECT_SCREEN}>
        <PageHeader
          title={t("customers.reconnect.notFound.title")}
          backTo={{
            to: tenantPath(disconnectRecordPath(reference)),
            label: t("customers.reconnect.back", { case: reference.toUpperCase() }),
          }}
        />
      </div>
    );
  }

  const chosen = rows ?? seedRows(detail);
  const on = restoreOn ?? detail.restore_on;
  const isMaster = detail.account.account_kind === "master";
  const refusal = detail.commit_refused_by;
  // DEF-CUS-10657 — PO C1 2026-10-29, *"Restore = Reconnect request"*. On a
  // `cut` case the commit SENDS the request; on a `reconnecting` case it
  // COMPLETES it. The step is the server's (`reconnection_readiness`), never
  // worked out here.
  const completing = detail.step === "restore_service";

  function edit(next: ChosenRow[]): void {
    setRows(next);
  }

  async function raise(row: ChosenRow): Promise<void> {
    // ⚠ **`BR-WRK-055` — IT NEVER FAILS THE SCREEN.** The server returns the
    // sentence rather than raising, so a retired template comes back as a
    // warning on a row and the clerk carries on.
    edit(chosen.map((one) => (one.key === row.key ? { ...one, raising: true, refusal: null } : one)));
    let result: Awaited<ReturnType<typeof raiseReconnectWorkOrder>>;
    try {
      result = await raiseReconnectWorkOrder(
        reference,
        // `DEF-CUS-9630` — the row names its SERVICE and the server picks the
        // utility's own reconnect template for it. This sent the service code
        // as a template id, which raised nothing, every time.
        { service: row.service ?? "" },
        client,
      );
    } catch (error) {
      // ⚠ `DEF-CUS-9674` — the client THROWS on a 4xx, and this await had no
      // catch: `raising` stayed true (the button dead) and the refusal never
      // reached the clerk. The row now says it and can be pressed again.
      edit(
        chosen.map((one) =>
          one.key === row.key
            ? {
                ...one,
                raising: false,
                refusal: isApiError(error) ? error.messageKey : "work.fromFlows.notRaised",
              }
            : one,
        ),
      );
      return;
    }
    const order = result.work_orders[0];
    const warning = result.warnings[0] as { message_key?: string } | undefined;
    edit(
      chosen.map((one) =>
        one.key === row.key
          ? {
              ...one,
              raising: false,
              // A 200 with no job is `BR-WRK-055`'s not-raised warning — said.
              refusal: (order?.order_no ?? order?.work_order_no)
                ? null
                : (warning?.message_key ?? "work.fromFlows.notRaised"),
              // The raise answers `order_no` (Work's own word); the older
              // `work_order_no` spelling is read too.
              raised: (order?.order_no ?? order?.work_order_no)
                ? {
                    reference: (order?.order_no ?? order?.work_order_no) as string,
                    assignee: order?.assignee ?? null,
                  }
                : null,
            }
          : one,
      ),
    );
  }

  // ══════════════════════════════════════════════════════════════════════
  // STEP 1 · CHOOSE — the account, and which services go back on
  // ══════════════════════════════════════════════════════════════════════
  const step1 = (
    <div className="flex flex-col gap-6">
      {/* `BR-CUS-1098` — ONE LINE is the whole master warning. The drawing puts
          it above everything, and the PO confirmed that single line in so many
          words for the disconnect wizard's step 1. */}
      {isMaster ? (
        // ⚠ **NOT `WarningBox`, AND THAT IS THE KIT DECIDING RATHER THAN
        // TASTE.** That component's own type says it has no `info` tone on
        // purpose: *"a box that is sometimes merely interesting is a box people
        // stop reading, and the next one they skip is the one that mattered.
        // If it does not need an action, it is not this component."* This line
        // is a FACT about the account (`BR-CUS-1098`) and asks the clerk for
        // nothing, so it is a note. The drawing's green band is an
        // ILLUSTRATION (B14 rule 37); the kit decides how it is built (rule 44).
        <p
          role="note"
          data-testid="reconnect-master"
          className="border-l-4 border-success-500 bg-success-100 px-4 py-3 text-body font-semibold text-success-700"
        >
          {t("customers.reconnect.master.together", { count: detail.master.units ?? 0 })}
        </p>
      ) : null}

      <Panel title={t("customers.reconnect.account.title")}>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <TextField
            id="reconnect-account"
            label={t("customers.reconnect.account.label")}
            value={`${detail.account.account_no ?? ""} — ${detail.account.customer_name ?? ""}`}
            onChange={() => undefined}
            readOnly
          />
          <DatePickerField
            id="reconnect-on"
            label={t("customers.reconnect.restoreOn")}
            value={on}
            onChange={setRestoreOn}
            required
            dateFormat={regional.dateFormat}
          />
        </div>
        {/* 4.3 — all the customer details, AND the account type. The kind
            (`Master` · `Regular`) was on no reconnect surface before this
            screen; a clerk restoring a building needs to know it is a building
            before they press anything. */}
        <dl
          className="mt-4 grid grid-cols-2 gap-4 border border-divider bg-surface px-4 py-3 lg:grid-cols-6"
          data-testid="reconnect-account-facts"
        >
          <Fact label={t("customers.reconnect.fact.customer")}>{detail.account.customer_name}</Fact>
          <Fact label={t("customers.reconnect.fact.address")}>{detail.account.address}</Fact>
          <Fact label={t("customers.reconnect.fact.accountType")}>
            {t(`customers.reconnect.kind.${detail.account.account_kind}`)}
            {detail.account.account_class ? ` · ${detail.account.account_class}` : null}
          </Fact>
          {isMaster ? (
            <Fact label={t("customers.reconnect.fact.occupants")}>
              {t("customers.reconnect.units", { count: detail.master.units ?? 0 })}
            </Fact>
          ) : null}
          {/* ⚠ **`DateCell`, NEVER THE RAW STRING.** `IS-8` / `BR-SHL-023` keep
              ONE formatting path: a date renders in the TENANT's format. The
              first draft printed `2026-09-20` where the drawing shows
              `14 Aug 26`, and only looking at the screen found it. */}
          <Fact label={t("customers.reconnect.fact.cutOn")}>
            {detail.account.cut_on ? (
              <DateCell value={detail.account.cut_on} {...regional} />
            ) : (
              <span className="text-neutral-600">{t("customers.reconnect.absent")}</span>
            )}
          </Fact>
          <Fact label={t("customers.reconnect.fact.balance")}>
            <Money money={detail.account.balance} />
          </Fact>
          {/* B14 rule 31 — the CASE NUMBER, which is what a clerk reads back to
              a customer. Never an id. */}
          {isMaster ? null : (
            <Fact label={t("customers.reconnect.fact.case")}>{detail.case_no}</Fact>
          )}
        </dl>
      </Panel>

      {/* 4.4 — the table array. `EditableTable` IS the kit's one, with an inline
          add row and a per-row remove; rule 43 is satisfied by REUSING it
          rather than by writing a second one. `reorderable={false}` because
          these rows have no order that means anything, and `numbered={false}`
          because a `#` beside six columns of facts is a seventh that means
          nothing. */}
      <Panel
        title={t("customers.reconnect.services.title")}
        trailing={
          <span className="text-sm text-neutral-600">
            {t(isMaster ? "customers.reconnect.services.asideMaster" : "customers.reconnect.services.aside")}
          </span>
        }
      >
        <EditableTable<ChosenRow>
          caption=""
          data-collection="reconnect-services"
          rows={chosen}
          rowKey={(row) => row.key}
          reorderable={false}
          numbered={false}
          emptyText={t("customers.reconnect.services.empty")}
          labels={{ remove: t("customers.reconnect.services.remove") }}
          onChange={edit}
          columns={[
            {
              key: "service",
              label: t("customers.reconnect.col.service"),
              cell: (row) => (
<span className="font-semibold">{rowLabel(row, t)}</span>
              ),
            },
            {
              key: "point",
              label: t("customers.reconnect.col.servicePoint"),
              cell: (row) => <span className="block max-w-[14rem]">{row.service_point ?? "—"}</span>,
            },
            {
              key: "meter",
              label: t("customers.reconnect.col.meter"),
              // ⚠ **NEVER INVENTED.** The server answers `null` with its reason;
              // an em dash is what a clerk sees and a made-up meter number is
              // what a crew would be sent out on.
              cell: (row) => row.meter ?? "—",
            },
            {
              key: "how",
              label: t("customers.reconnect.col.how"),
              cell: (row) => (
                <div className="min-w-[10rem]">
                <SelectField
                  id={`reconnect-how-${row.key}`}
                  label={t("customers.reconnect.col.how")}
                  labelHidden
                  value={row.how}
                  onChange={(value) =>
                    edit(chosen.map((one) => (one.key === row.key ? { ...one, how: value } : one)))
                  }
                  options={row.how_options.map((code) => ({
                    value: code,
                    label: t(`customers.reconnect.how.${code}`),
                  }))}
                />
                </div>
              ),
            },
            {
              key: "instruction",
              label: t("customers.reconnect.col.instruction"),
              cell: (row) => (
                <TextField
                  id={`reconnect-instruction-${row.key}`}
                  label={t("customers.reconnect.col.instruction")}
                  labelHidden
                  value={row.instruction ?? ""}
                  onChange={(value) =>
                    edit(
                      chosen.map((one) =>
                        one.key === row.key ? { ...one, instruction: value } : one,
                      ),
                    )
                  }
                />
              ),
            },
            ...(isMaster
              ? [
                  {
                    key: "reaches",
                    label: t("customers.reconnect.col.reaches"),
                    cell: (row: ChosenRow) =>
                      row.reaches ? (
                        <span className="font-semibold text-success-700">
                          {t(`customers.reconnect.reaches.${row.reaches}`, {
                            count: detail.master.units ?? 0,
                          })}
                        </span>
                      ) : (
                        "—"
                      ),
                  },
                ]
              : []),
            {
              key: "work_order",
              label: t("customers.reconnect.col.workOrder"),
              // 4.5 — **THE CLERK RAISES IT FROM THE ROW.** Before this, a work
              // order was IMPLIED: a word in a cell and a job raised at commit.
              // A word is not a job. A raised one shows its reference and who it
              // is with; one not yet raised shows the act.
              cell: (row) =>
                row.raised ? (
                  <span className="flex flex-col" data-testid={`reconnect-wo-${row.key}`}>
                    <span className="font-semibold">{row.raised.reference}</span>
                    <span className="text-sm text-neutral-600">
                      {row.raised.assignee ?? t("customers.reconnect.workOrder.unassigned")}
                      {row.raised.accepted
                        ? ` · ${t("work.order.approval.accepted")}`
                        : row.raised.done
                          ? ` · ${t("customers.reconnect.workOrder.done")}`
                          : ""}
                    </span>
                  </span>
                ) : row.how === "no_visit" || row.how === "remote" ? (
                  <span className="text-neutral-600">—</span>
                ) : (
                  <span className="flex flex-col items-start gap-1">
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={row.raising}
                      data-testid={`reconnect-raise-${row.key}`}
                      onClick={() => {
                        void raise(row);
                      }}
                    >
                      <span className="whitespace-nowrap">
                        {t("customers.reconnect.workOrder.raise")}
                      </span>
                    </Button>
                    {row.refusal ? (
                      <span role="alert" className="text-sm text-danger-700">
                        {t(row.refusal)}
                      </span>
                    ) : null}
                  </span>
                ),
            },
          ]}
          addRow={
            <div className="flex items-center gap-3">
              <SelectField
                id="reconnect-add-service"
                label={t("customers.reconnect.services.add")}
                labelHidden
                value={addService}
                onChange={setAddService}
                options={[
                  { value: "", label: t("customers.reconnect.services.addPick") },
                  ...detail.services.addable.map((one) => ({
                    value: one.service,
                    label: serviceLabel(one.service, t),
                  })),
                ]}
              />
              <Button
                size="sm"
                variant="secondary"
                disabled={addService === ""}
                data-testid="reconnect-add"
                onClick={() => {
                  const source = detail.services.addable.find((one) => one.service === addService);
                  if (!source) {
                    return;
                  }
                  edit([
                    ...chosen,
                    {
                      service: source.service,
                      service_point: source.service_point,
                      point_known: true,
                      meter: null,
                      meter_absence: null,
                      scope: null,
                      how_options: ["work_order", "remote", "no_visit"],
                      how_default: "work_order",
                      instruction: null,
                      work_order: null,
                      reaches: null,
                      key: `${source.service}-added-${chosen.length}`,
                      how: "work_order",
                      raised: null,
                      raising: false,
                    },
                  ]);
                  setAddService("");
                }}
              >
                {t("customers.reconnect.services.add")}
              </Button>
              <span className="text-sm text-neutral-600" data-testid="reconnect-raised-count">
                {t("customers.reconnect.services.raisedCount", {
                  raised: chosen.filter((one) => one.raised).length,
                  toRaise: chosen.filter((one) => !one.raised && one.how === "work_order").length,
                })}
              </span>
            </div>
          }
        />
      </Panel>
    </div>
  );

  // ══════════════════════════════════════════════════════════════════════
  // STEP 2 · CONFIRM — this restoration, what is still owed, what happens
  // ══════════════════════════════════════════════════════════════════════
  const step2 = (
    <div className="flex flex-col gap-6">
      <Panel title={t("customers.reconnect.confirm.title")}>
        <dl
          className="grid grid-cols-1 gap-4 border border-divider bg-surface px-4 py-3 lg:grid-cols-3"
          data-testid="reconnect-confirm-facts"
        >
          <Fact label={t("customers.reconnect.fact.account")}>
            {detail.account.account_no} · {detail.account.customer_name}
          </Fact>
          <Fact label={t("customers.reconnect.fact.address")}>{detail.account.address}</Fact>
          <Fact label={t("customers.reconnect.fact.accountType")}>
            {t(`customers.reconnect.kind.${detail.account.account_kind}`)}
            {detail.account.account_class ? ` · ${detail.account.account_class}` : null}
          </Fact>
          <Fact label={t("customers.reconnect.fact.services")}>
            {chosen.map((row) => rowLabel(row, t)).join(", ")}
          </Fact>
          <Fact label={t("customers.reconnect.restoreOn")}>
            <DateCell value={on} {...regional} />
          </Fact>
          <Fact label={t("customers.reconnect.fact.cutOn")}>
            {detail.account.cut_on ? (
              <DateCell value={detail.account.cut_on} {...regional} />
            ) : (
              <span className="text-neutral-600">{t("customers.reconnect.absent")}</span>
            )}
          </Fact>
        </dl>
        {isMaster ? (
          <div className="mt-4">
            <p
              role="note"
              data-testid="reconnect-master-reach"
              className="border-l-4 border-success-500 bg-success-100 px-4 py-3 text-body font-semibold text-success-700"
            >
              {t("customers.reconnect.master.reach", { count: detail.master.units ?? 0 })}
            </p>
          </div>
        ) : null}
      </Panel>

      {/* 4.7 — four lines in a box become a TABLE. For a master, residue
          transferred up is its OWN LINE (`BR-CUS-1098`).
          ⚠ **THE TOTAL IS THE LEDGER'S AND IS NOT SUMMED HERE** — `DEF-CUS-6050`:
          the figure a clerk states and the figure that admits the customer back
          must be one read. */}
      <Panel
        title={t("customers.reconnect.owed.title")}
        trailing={
          detail.owed.plan_label ? (
            <span className="text-sm text-neutral-600">{detail.owed.plan_label}</span>
          ) : null
        }
      >
        <table className="w-full text-body" data-testid="reconnect-owed">
          <thead>
            <tr className="border-b border-divider text-table-header uppercase tracking-table-header text-neutral-600">
              <th className="py-2 text-left font-semibold">{t("customers.reconnect.owed.line")}</th>
              <th className="py-2 text-left font-semibold">{t("customers.reconnect.owed.from")}</th>
              {/* ⚠ **THE GUTTER IS NOT DECORATION.** A right-aligned money
                  column with nothing between it and the next one printed
                  `$64.802026-09-20` on the running product — one string to a
                  reader, two facts in the markup, and every assertion in the
                  walk passed over it. Only looking at the screen finds this
                  (hard-won law 6). Spacing comes from the scale (B14 rule 44). */}
              <th className="py-2 pr-6 text-right font-semibold">
                {t("customers.reconnect.owed.amount")}
              </th>
              <th className="py-2 text-left font-semibold">{t("customers.reconnect.owed.when")}</th>
            </tr>
          </thead>
          <tbody>
            {detail.owed.lines.map((line) => (
              <tr key={line.code} className="border-b border-divider">
                <td className="py-3 font-semibold" data-owed-line={line.code}>
                  {t(`customers.reconnect.owed.code.${line.code}`)}
                </td>
                <td className="py-3 text-neutral-700">
                  {t(`customers.reconnect.owed.from.${line.from_code}`)}
                </td>
                <td className="py-3 pr-6 text-right">
                  <Money money={line.amount} negative={line.negative} />
                </td>
                <td className="py-3 text-neutral-700">
                  {/* `at_the_cut` is a CODE the catalogue owns; anything else
                      is a date and takes the tenant's format. */}
                  {line.when === null ? (
                    "—"
                  ) : line.when === "at_the_cut" ? (
                    t("customers.reconnect.owed.when.at_the_cut")
                  ) : (
                    <DateCell value={line.when} {...regional} />
                  )}
                </td>
              </tr>
            ))}
            <tr>
              <td className="py-3 font-semibold" data-owed-line="still_owed">
                {t("customers.reconnect.owed.stillOwed")}
              </td>
              <td />
              <td
                className="py-3 pr-6 text-right text-h4 font-semibold"
                data-testid="reconnect-still-owed"
              >
                <Money money={detail.owed.still_owed} />
              </td>
              <td />
            </tr>
          </tbody>
        </table>

        {/* 4.2 — `BR-CUS-1097` ON SCREEN, AND THIS IS ALL OF IT. A figure and
            four words. No rule, no rationale, no retention note (rule 33). */}
        {detail.warning ? (
          <div className="mt-4">
            <WarningBox
              tone="soon"
              data-warning="reconnect-still-owed"
              sentence={
                <strong data-testid="reconnect-warning">
                  {/* ⚠ **THE FIGURE CARRIES ITS CURRENCY, AND THE WALK IS WHAT
                      CAUGHT THAT IT DID NOT.** `amount.display` is the bare
                      2dp string, so the sentence read *"139.80 still owed"* on
                      the running product while every assertion passed — the
                      drawing says **$879.50**, and a money figure with no
                      symbol on the one sentence a clerk reads before restoring
                      supply is exactly the kind of thing only a person looking
                      at the screen finds (hard-won law 6). `formatMoney` is the
                      kit's single formatting path (`BR-SHL-023`); nothing here
                      builds a symbol of its own. */}
                  {t("customers.reconnect.warning.stillOwed", {
                    amount: formatMoney(
                      detail.warning.amount.display ?? "0.00",
                      detail.warning.amount.currency ?? "USD",
                    ),
                  })}
                </strong>
              }
            />
          </div>
        ) : null}
      </Panel>

      {/* ⚠ **THE DEPOSIT IS A LINE A CLERK SEES AND NOT A FIELD.** Nothing in
          this product collects one on this path, and a field that writes
          nowhere is dead UI (hard-won law 2). The coordinator drew it as a
          visible line rather than something that happens silently, and that is
          strictly more honest than the dialog it replaces. */}
      {/* ⚠ **A `$0.00` DEPOSIT PANEL IS NOISE AND `"0.0000"` IS TRUTHY.** The
          first draft drew *The deposit · Held before the cut · Still held ·
          $0.00* on an account that never had one — a whole panel saying
          nothing, on a screen with a description budget (B14 rule 32). A zero
          here is a real measured figure and NOT an absence (`DEF-127`), so it
          is not rendered as one; it is simply not a panel. */}
      {Number(detail.deposit.held_before_the_cut?.stored ?? "0") > 0 ||
      detail.deposit.new_deposit_required ? (
        <Panel title={t("customers.reconnect.deposit.title")}>
          <table className="w-full text-body" data-testid="reconnect-deposit">
            <tbody>
              <tr className="border-b border-divider">
                <td className="py-3 font-semibold">{t("customers.reconnect.deposit.held")}</td>
                <td className="py-3 text-neutral-700">
                  {t(`customers.reconnect.deposit.disposition.${detail.deposit.disposition ?? "held"}`)}
                </td>
                <td className="py-3 pr-6 text-right">
                  <Money money={detail.deposit.held_before_the_cut} />
                </td>
              </tr>
              {detail.deposit.new_deposit_required ? (
                <tr>
                  <td className="py-3 font-semibold">{t("customers.reconnect.deposit.new")}</td>
                  <td className="py-3 text-neutral-700">
                    {t("customers.reconnect.deposit.dueBefore")}
                  </td>
                  <td className="py-3 pr-6 text-right">
                    <Money money={detail.deposit.held_before_the_cut} />
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </Panel>
      ) : null}

      <Panel title={t("customers.reconnect.happens.title")}>
        <table className="w-full text-body" data-testid="reconnect-happens">
          <tbody>
            {detail.consequences.map((one) => (
              <tr key={one.code} className="border-b border-divider">
                <td className="w-16 py-3">
                  <span className="bg-success-100 px-2 py-1 text-sm font-semibold text-success-700">
                    {t("customers.reconnect.happens.yes")}
                  </span>
                </td>
                <td className="py-3 font-semibold" data-happens={one.code}>
                  {t(`customers.reconnect.happens.${one.code}`)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  );

  return (
    <div data-screen={RECONNECT_SCREEN}>
      <PageHeader
        // The drawing's `← Case DSC-26-0002`. A real `<Link>` to a real
        // address, so ⌘-click opens the case in a second tab.
        backTo={{
          to: tenantPath(disconnectRecordPath(reference)),
          label: t("customers.reconnect.back", { case: (detail.case_no ?? reference).toUpperCase() }),
          testId: "reconnect-back",
        }}
        kicker={t("customers.reconnect.kicker")}
        title={t("customers.reconnect.title")}
      />
      <WizardFrame
        nav={nav}
        onNavChange={(next) => {
          setNav(next);
          const params = new URLSearchParams(search);
          params.set("step", String(next.step));
          setSearch(params, { replace: true });
        }}
        steps={[
          { id: "choose", label: t("customers.reconnect.step.choose"), content: step1 },
          { id: "confirm", label: t("customers.reconnect.step.confirm"), content: step2 },
        ]}
        commitLabel={t(
          completing ? "customers.reconnect.commitComplete" : "customers.reconnect.commitRequest",
        )}
        // ⚠ **NOT THE DANGER TIER.** B14 rule 6 reserves it for a DESTRUCTIVE
        // commit. Putting somebody's water back on is the opposite act, and
        // dressing it in red would teach a clerk the colour means *important*
        // rather than *irreversible*.
        // ⚠ **THE COMMIT IS REFUSED BEFORE IT IS PRESSED ONLY WHEN THE ENGINE
        // SAYS SO** (`commit_refused_by` — an unreadable balance, a case in the
        // wrong state). Money still owed is a WARNING and never greys it
        // (`BR-CUS-1097`); the reason, when there is one, is the note under the
        // action row (`BR-SHL-025`).
        commitDisabled={refusal !== null}
        commitFailedTitle={t(
          completing ? "customers.reconnect.failed" : "customers.reconnect.failedRequest",
        )}
        onCommit={async () => {
          // ✅ **THE HOLD IS RELEASED — DEF-CUS-10657.** Until 2026-10-29 this
          // returned `ok: false` with *"This step is not built yet"* on both
          // steps, held on `not_settled`, which the engine dropped on
          // 2026-09-25. `ReconnectCommit.dom.test.tsx` asserts each step's
          // POST by ADDRESS, so a return to refusing goes red by name.
          try {
            if (completing) {
              await completeReconnect(reference, { on_date: on }, client);
            } else {
              // The rows still to raise: on *Work order* with no job yet. A row
              // the clerk raised from the row is not sent twice; *Remote* and
              // *No visit* raise nothing.
              const services = chosen
                .filter((one) => one.how === "work_order" && !one.raised && one.service)
                .map((one) => one.service as string);
              await requestReconnect(reference, { on_date: on, services }, client);
            }
          } catch (error) {
            const code = isApiError(error) ? String(error.params.code ?? "") : "";
            return {
              ok: false,
              reason: t(code ? `customers.disconnectRecord.refused.${code}` : "customers.reconnect.refused.generic", {
                defaultValue: t("customers.reconnect.refused.generic"),
              }),
            };
          }
          await Promise.all([
            queryClient.invalidateQueries({ queryKey: reconnectKey(reference) }),
            queryClient.invalidateQueries({ queryKey: disconnectRecordKey(reference) }),
          ]);
          return { ok: true };
        }}
        onCommitted={() => navigate(tenantPath(disconnectRecordPath(reference)))}
      />
      {/* `BR-SHL-025` — the reason is VISIBLE TEXT and never a hover title, and
          it sits UNDER the action row rather than in it, because a row of
          controls holds only things a person can press. */}
      {refusal ? (
        <p
          role="note"
          data-testid="reconnect-refused"
          className="mt-3 border border-divider bg-neutral-100 px-4 py-3 text-body font-semibold text-neutral-900"
        >
          {t(`customers.disconnectRecord.refused.${refusal.code}`, {
            defaultValue: t("customers.reconnect.refused.generic"),
          })}
        </p>
      ) : null}
    </div>
  );
}

function Fact(props: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="text-sm text-neutral-600">{props.label}</dt>
      <dd className="m-0 font-semibold text-neutral-900">{props.children ?? "—"}</dd>
    </div>
  );
}
