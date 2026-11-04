// ── Trace ──────────────────────────────────────────────
// Change:   the Reads→Work door — PO ruling 2026-09-14, verbatim *"please build
//           this"*, reversing that morning's `Q2` deferral.
//           Drawing: blueprint **p028** — the upload wizard's stage-3 REGISTERS
//           EXPECTED table, whose DECISION cell carries `Estimate all` and
//           `Send someone out` side by side. **p047**'s control table names the
//           second one: *"Send someone out · On the shortfall · Raises a visit
//           for the ticked meters · The **work** module — and this is the one
//           action that crosses a module boundary, so it is drawn and flagged,
//           not assumed."* **p045 / p051** draw the same pair on the cycle's and
//           the route's *Still to read* bulk bar.
// Rules:    B14 rule 11 (a consequence preview before a commit that changes
//           service state) · rule 31 (a work order shows its `WO-…` number,
//           never a uuid) · rule 32 (one sentence per section) · rule 33 (label
//           ≤3 words · fact ≤6 · instruction ≤6 per sentence · RATIONALE is
//           ZERO words on screen) · rule 36 (compose the kit — the tick list is
//           `FieldWorkTemplateList`, the kit's own, not a sixth copy) · rule 38
//           (the drawing decides what the form CONTAINS; our UI rules decide how
//           it is BUILT, so this is the kit's `FormModal`) · rule 21 (Tailwind
//           utilities, and this file is on `route-b-migrated.txt`) ·
//           BR-WRK-016 · BR-WRK-024 · BR-WRK-055 · BR-MET-023 / 027 / 062
// Tests:    SendSomeoneOutModal.test.tsx
// Impacts:  readsImportRail.tsx (the control that opens it) ·
//           UploadReadsWizard.tsx (the group's meters, and the disposition)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY A DIALOG, AND WHY THE DIALOG IS NOT DRAWN
// ══════════════════════════════════════════════════════════════════════════
// The drawing shows the CONTROL, on the shortfall row, and stops there — which
// is right, because what the control opens is form construction and B14 rule 38
// gives that to our UI rules rather than to the frame. B14 rule 30 was DECLINED
// on 2026-08-30 and the PO answered the instance instead — *"for estimate reads
// - keep it modal"* — so the estimate precedent is what settles this one: a
// handful of fields, one outcome, returns to the list it was launched from,
// nothing worth a URL. `EstimateReadModal` is its sibling on the same shortfall
// and this is built to match it.
//
// ══════════════════════════════════════════════════════════════════════════
// THE TWO THINGS THIS SCREEN MUST NEVER DO
// ══════════════════════════════════════════════════════════════════════════
// **1 · IT MUST NEVER RAISE A VISIT BY ITSELF.** `from_flows`' first rule, in
// its own words: *"a flow that raised jobs on its own would put a crew in a van
// because somebody pressed Close account."* Opening this dialog writes nothing;
// only the commit writes, and only the templates a person ticked. A clerk who
// ticks nothing gets nothing raised and that is an ANSWER, not a failure.
//
// **2 · IT MUST NEVER LET A FAILED RAISE COST THE READING WORK** (`BR-WRK-055`).
// The clerk's decision — *these rows are not posting, somebody is going out* —
// is metering's own record and is written FIRST, through the wizard's existing
// disposition path. The raise runs after it and reports what it could not do.
// A partial answer is rendered as a partial answer: `raised` AND `not_raised`,
// both on screen, because a screen showing only the successes would tell a
// clerk five visits were booked when four were.
import { useMutation, useQueries } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { FormModal } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { FieldWorkTemplateList } from "@/components/RaiseFieldWork";
import type { FieldWorkOffer, FieldWorkTemplate } from "@/components/RaiseFieldWork";
import { Note } from "@/components/TextBits";
import { InlineLinkTo } from "@/components/Surfaces";
import { workOrderDetailPath } from "@/features/work/OrderDetailPage";
import { useTenantPath } from "@/routing/tenantPath";

import { proposeMeterFieldWork, raiseMeterFieldWork } from "./readsFieldWorkEndpoints";
import type { RaiseFieldWorkResult } from "./readsFieldWorkEndpoints";

/** r10 UI-RULES 18 as amended (PO 80%) — the description measure, as the named
 *  utility over the `--desc-measure` token. ⚠ NOT `max-w-prose`, which is a real
 *  Tailwind utility and the WRONG cap — that exact confusion is `DEF-900`. */
const MEASURE = "max-w-measure";

/** `EstimateReadModal`'s outcome panel, to the pixel — the two dialogs sit on
 *  the same shortfall and a clerk moves between them. */
const OUTCOME = "mt-6 border-l-[3px] bg-surface p-4";
const OUTCOME_MADE = "border-l-success-500";
const OUTCOME_REFUSED = "border-l-warning-500";
const OUTCOME_TITLE = "m-0 mb-3 font-heading text-h4";
const SENTENCE = "m-0 mb-2 max-w-measure text-sm leading-prose";

/** One meter this dialog can send somebody to. */
export interface FieldVisitMeter {
  /** ⚠ The asset uuid. It is the ANCHOR the raise is keyed on and it is NEVER
   *  drawn (B14 rule 31) — `meterNo` is what a person sees. */
  assetId: string;
  /** `MTR-0463` — the meter's issued number, and the only identity on screen. */
  meterNo: string;
}

/**
 * The dialog is submittable with nothing ticked, and that is deliberate — see
 * rule 1 in this file's header. So the schema constrains what a person CAN
 * choose rather than forcing a choice: template ids are strings, and the
 * server stays the authority on whether each one is published (`BR-WRK-016`).
 */
export const sendSomeoneOutSchema = z.object({
  template_ids: z.array(z.string().trim().min(1)),
});

/**
 * **THE OFFER, ACROSS EVERY TICKED METER, WITH NOTHING INVENTED.**
 *
 * ⚠ **THE METERS IN ONE GROUP DO NOT ALWAYS RUN ONE SERVICE**, so the offer is
 * asked per meter and the answers are UNIONED by template. Asking only the
 * first meter would quietly offer an electric job over a water meter, which is
 * the sort of wrong that reaches a crew rather than a screen.
 *
 * ⚠ **A REFUSAL ON ONE METER IS NOT A REFUSAL OF THE PANEL** — judgment 8 bites
 * per meter (a spare on no service point has no address), and the other meters'
 * templates are still offered. The refusal travels back out separately so the
 * dialog can name the meters it will not be able to reach.
 */
export function mergeOffers(
  offers: readonly (FieldWorkOffer | undefined)[],
): { proposed: FieldWorkTemplate[]; refusedCount: number } {
  const byId = new Map<string, FieldWorkTemplate>();
  let refusedCount = 0;
  for (const offer of offers) {
    if (offer === undefined) continue;
    if (offer.refusal !== null) {
      refusedCount += 1;
      continue;
    }
    for (const template of offer.proposed) {
      if (!byId.has(template.template_id)) byId.set(template.template_id, template);
    }
  }
  return { proposed: [...byId.values()], refusedCount };
}

export interface SendSomeoneOutModalProps {
  /** The SHORT meters of the group the clerk pressed on. */
  meters: readonly FieldVisitMeter[];
  client?: ApiClient;
  onClose: () => void;
  /**
   * **THE CLERK'S OWN DECISION, WRITTEN BEFORE THE RAISE AND INDEPENDENTLY OF
   * IT.** `BR-WRK-055`: a field module must never be able to cost a clerk their
   * reading work, so the disposition — *these rows are not posting, somebody is
   * going out* — is metering's own record and goes first. If it throws, nothing
   * is raised and the dialog says so; if the RAISE throws, the decision stands.
   */
  onRecordDecision: () => Promise<void>;
}

/**
 * The RESULT, rendered as the two halves it actually has.
 *
 * ⚠ **A PARTIAL ANSWER IS RENDERED AS A PARTIAL ANSWER.** `raised` and
 * `not_raised` are both on screen whenever both are non-empty. Rendering only
 * the successes is `DEF-708`'s shape — an act reported that never happened —
 * and here it would send a clerk home believing a crew was going somewhere.
 */
export function RaiseOutcome(props: {
  result: RaiseFieldWorkResult;
  meters: readonly FieldVisitMeter[];
  t: (key: string, params?: Record<string, unknown>) => string;
}) {
  const { result, t } = props;
  const tenantPath = useTenantPath();
  const numberOf = (meterId: string) =>
    props.meters.find((meter) => meter.assetId === meterId)?.meterNo ?? null;
  const anyRaised = result.raised.length > 0;
  return (
    <div
      className={`${OUTCOME} ${anyRaised ? OUTCOME_MADE : OUTCOME_REFUSED}`}
      role="note"
      data-reads="field-visit-outcome"
    >
      <h3 className={OUTCOME_TITLE}>
        {anyRaised
          ? t("metering.fieldVisit.raisedTitle")
          : t("metering.fieldVisit.noneRaisedTitle")}
      </h3>
      {anyRaised && (
        <ul className="m-0 mb-2 list-none p-0">
          {result.raised.map((order) => (
            <li key={order.id} className="text-sm" data-field-visit-order={order.order_no}>
              {/* B14 rule 31 — the `WO-…` number a clerk quotes, and the METER
                  number beside it. Neither uuid is drawn. */}
              {/* Record links (PO 2026-10-19): the number opens the order, BY
                  NUMBER — the order page resolves one, and the uuid stays off
                  the page entirely (rule 31, the test below). */}
              <InlineLinkTo
                className="font-semibold"
                to={tenantPath(workOrderDetailPath("", encodeURIComponent(order.order_no)).slice(1))}
              >
                {order.order_no}
              </InlineLinkTo>
              {order.source_ref === null ? null : <span> · {order.source_ref}</span>}
              <span> · {order.name}</span>
            </li>
          ))}
        </ul>
      )}
      {result.not_raised.length > 0 && (
        <>
          <p className={`${SENTENCE} font-semibold text-warning-700`}>
            {t("metering.fieldVisit.notRaised", { count: result.not_raised.length })}
          </p>
          <ul className="m-0 list-none p-0">
            {result.not_raised.map((row) => (
              <li
                key={row.meter_id}
                className="text-sm"
                // ⚠ **THE HOOK CARRIES THE METER NUMBER, NOT THE ID, AND THE
                // TEST IS WHAT FOUND THAT.** B14 rule 31 permits an internal
                // value to ride on `title` as evidence, and a `data-` hook is
                // not a visible value either — but a uuid anywhere in this
                // markup makes the one assertion worth writing unwritable, and
                // the rule's own note says a check over the DOM string goes RED
                // on a correct fix. Keyed on the NUMBER, the uuid is nowhere in
                // the rendered output at all and the check is a plain
                // `not.toContain`. The id survives as the React key, which
                // never reaches the DOM.
                data-field-visit-unraised={numberOf(row.meter_id) ?? ""}
              >
                {/* The meter NUMBER, resolved from what this dialog already
                    holds. The server sends the id because that is what matches
                    the two lists; it is never what a person reads. */}
                {numberOf(row.meter_id) ?? t("metering.fieldVisit.unknownMeter")}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

/**
 * **SEND SOMEONE OUT — the shortfall's other answer.**
 *
 * `Estimate all` fills the gap from history; this one admits that somebody has
 * to go and look. `BR-MET-062` makes it the ONLY answer for a missing demand
 * peak, and `BR-MET-027` makes it the answer once the consecutive-estimate cap
 * is reached — which is why the two controls sit side by side on the drawn row
 * rather than one being a fallback for the other.
 */
export function SendSomeoneOutModal(props: SendSomeoneOutModalProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const [selected, setSelected] = useState<string[]>([]);

  // The offer, per meter. `useQueries` rather than one call because the endpoint
  // answers for ONE flow id — see `mergeOffers` for why every meter is asked.
  const offers = useQueries({
    queries: props.meters.map((meter) => ({
      queryKey: ["meter-field-work-offer", meter.assetId],
      queryFn: () => proposeMeterFieldWork(meter.assetId, client),
    })),
  });
  const loading = offers.some((query) => query.isPending);
  const { proposed, refusedCount } = mergeOffers(offers.map((query) => query.data));

  const raise = useMutation({
    mutationFn: async () => {
      // ⚠ **ORDER IS THE RULE, NOT A PREFERENCE (`BR-WRK-055`).** The clerk's
      // own decision is recorded first and does not depend on Work being
      // reachable; the raise runs after it and reports what it could not do.
      await props.onRecordDecision();
      return raiseMeterFieldWork(
        { meters: props.meters.map((meter) => meter.assetId), templateIds: selected },
        client,
      );
    },
  });

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    try {
      await raise.mutateAsync();
      // ⚠ `ok: true` REPORTS ONLY THAT THE REQUEST WAS ANSWERED. Which meters
      // got their visit is `RaiseOutcome`'s to render, and the dialog stays open
      // either way — the same posture `EstimateReadModal` takes over its own
      // refusal, and for the same reason: a partial answer is an answer a clerk
      // has to read.
      return { ok: true };
    } catch (error) {
      // A18 §4 — a TRANSPORT failure is a different thing from a partial raise,
      // and the two are rendered differently: one is retried, the other acted on.
      return { ok: false, error: error as never };
    }
  }

  return (
    <FormModal
      title={t("metering.fieldVisit.title")}
      kicker={t("metering.fieldVisit.kicker")}
      schema={sendSomeoneOutSchema}
      values={{ template_ids: selected }}
      submitLabel={t("metering.fieldVisit.submit")}
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      {/* B14 rule 32 — ONE sentence for this section, and rule 33 caps an
          instruction at six words per sentence. */}
      <Note className={MEASURE}>{t("metering.fieldVisit.lede")}</Note>

      {/* A FACT, ≤6 words (rule 33): how many meters this will act on. It is not
          a rationale and it is not an instruction. */}
      <p className="mb-3 text-sm" data-field-visit-meters={props.meters.length}>
        {t("metering.fieldVisit.meterCount", { count: props.meters.length })}
      </p>

      <FieldWorkTemplateList
        offer={{
          flow: { kind: "meter_read", id: "", ref: null },
          proposed,
          count: proposed.length,
          // The panel's own refusal is for a flow with NO anchor at all. Here
          // the meters are asked one by one, so a refusal is per meter and is
          // reported beneath rather than instead of the list.
          refusal: null,
        }}
        selected={selected}
        onChange={setSelected}
        t={(key, fallback, params) => t(key, { defaultValue: fallback, ...(params ?? {}) })}
        loading={loading}
      />

      {refusedCount > 0 && (
        // A FACT, ≤6 words. WHY those meters cannot be reached is rationale and
        // is ZERO words on screen (rule 33) — it is in `_resolve_meter_read`.
        <p className="mt-2 text-sm text-warning-700" data-field-visit-refused={refusedCount}>
          {t("metering.fieldVisit.noAddress", { count: refusedCount })}
        </p>
      )}

      {/* B14 rule 11 — the consequence, before the commit. Rule 33 caps it at
          six words per sentence and at most two sentences. */}
      <ConsequenceBox
        tone="check"
        tag={t("metering.fieldVisit.consequence.tag")}
        title={t("metering.fieldVisit.consequence.title")}
        body={t("metering.fieldVisit.consequence.body")}
        data-consequence="reads-field-visit"
      />

      {raise.data !== undefined && (
        <RaiseOutcome
          result={raise.data}
          meters={props.meters}
          t={(key, params) => t(key, params)}
        />
      )}
    </FormModal>
  );
}

export default SendSomeoneOutModal;

// ── Lifecycle ─────────────────────────────────────────────
// packet: the Reads→Work door (decision log 2026-09-14) · blueprint p028/p045/p047/p051
// generated: 2026-09-14 by the Meter Reads field-visit lane
// checklist: A=n/a B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// gates: tsc · vitest SendSomeoneOutModal.test.tsx · G31 (this file is on
//   styles/route-b-migrated.txt, added in the commit that created it)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
