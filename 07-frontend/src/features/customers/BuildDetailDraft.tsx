// ── Trace ──────────────────────────────────────────────
// Change:   CR-150-BRC09 · the New Connect BUILD DETAIL page — task 13, the
//           DRAFT variant.
// Drawing:  `05-prototype/new-connect-detail-2026-09-28/10-draft.png`, opened
//           with the Read tool and LOOKED AT before a line of this file
//           (B14 rule 42).
// Rules:    BR-SHL-046 (**ONE declared step list** — the rail, the waiting
//           list and this panel all read `NEW_CONNECT_STEPS`, so `Step N of M`
//           cannot drift) · BR-SHL-048 (d) / `DEF-CUS-6132` (a draft is
//           finished by the wizard it belongs to, at `?build=`) · B14 rule 33
//           (a LABEL ≤ 3 words · a FACT ≤ 6) · rule 37 (the drawn `Step 3 of
//           5` is an ILLUSTRATION — the count comes from the declared list,
//           which holds FIVE since `CR-150-BRC09`, 2026-09-28; this line said
//           `eight` and was amended with the list rather than left to rot) ·
//           rule 43 (a COMPONENT).
// Tests:    src/features/customers/BuildDetailPage.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **THE SAME HEADER AND THE SAME TAB BAR, SO THE PAGE NEVER REARRANGES
// ITSELF UNDER A CLERK.** The drawing's own note, and it is why the four tabs
// with nothing behind them are SHOWN and not selectable rather than hidden —
// `buildDetailTabs` draws them without a destination.
//
// ⚠ **NO `Open premises` AND NO `Open account`, BECAUSE NEITHER EXISTS.** On a
// committed build the PO removed both because the Overview table links them;
// on a draft nothing has been created at all, so a control would point at
// nothing. Same absence, two different reasons, and both are the drawing's.
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useState } from "react";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError, UNEXPECTED_ERROR_KEY } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { FormModal, SelectField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";
import { Panel } from "@/components/Panel";
import { WIZARD_PARK_REASON_COPY } from "@/components/WizardFrame";

import { stepOf, waitingOnLabel } from "./parkedDrafts";
import { patchWizardPark } from "./wizardParkEndpoints";
import type { WizardParkRow } from "./wizardParkEndpoints";
import { listWizardParks } from "./wizardParkEndpoints";
import { NEW_CONNECT_STEPS, draftBuildPath } from "./newConnectShared";
import type { Translator } from "./newConnectShared";
import type { ConnectionDetail } from "./newConnectEndpoints";

export const draftParksQueryKey = ["wizard-parks", "new_connect"] as const;

/**
 * The park row this build is parked under, or `null`.
 *
 * ⚠ **MATCHED ON `subject_ref.connection_id`, WHICH IS A COPIED VALUE AND NOT
 * A FOREIGN KEY** — `BR-SHL-048 (d)`'s own words. A draft started from scratch
 * names no build and correctly matches nothing; that build is a draft nobody
 * parked, which is an ordinary state and not a broken one.
 */
export function parkOfBuild(
  rows: readonly WizardParkRow[],
  connectionId: string,
): WizardParkRow | null {
  return rows.find((row) => row.subject_ref.connection_id === connectionId) ?? null;
}

/**
 * ⚠ **`enabled` IS NOT A TIDINESS FLAG.** Only a DRAFT can be parked, so a
 * committed build asking `GET /wizard-parks` is a request whose answer the
 * screen throws away — on every build page, for ever. It is a parameter
 * rather than an early return because a hook cannot be conditional, and the
 * caller only learns whether this build is a draft once its own read lands.
 */
export function useDraftPark(connectionId: string, client?: ApiClient, enabled = true) {
  return useQuery({
    queryKey: draftParksQueryKey,
    queryFn: () => listWizardParks({ flow: "new_connect" }, client ?? api),
    retry: false,
    enabled,
    select: (list) => parkOfBuild(list.results, connectionId),
  });
}

/** Where `Carry on` goes. A parked draft resumes through its park so the
 *  typing comes back; an unparked one opens the wizard on the build itself
 *  (`?build=`), which is the ONE builder for that address. */
export function carryOnPath(connectionId: string, park: WizardParkRow | null): string {
  return park === null
    ? draftBuildPath(connectionId)
    : `${draftBuildPath(connectionId)}&parked=${encodeURIComponent(park.id)}`;
}

export interface BuildDraftBodyProps {
  t: Translator;
  detail: ConnectionDetail;
  park: WizardParkRow | null;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  path: (segment: string) => string;
}

/**
 * The draft's Overview: where it stopped, why it is parked, and the groups
 * answered so far.
 */
export function BuildDraftBody(props: BuildDraftBodyProps) {
  const { t, park } = props;
  const reached = park === null ? null : stepOf(park);
  const tiles: KpiTile[] = [];

  if (reached !== null) {
    tiles.push({
      id: "reached",
      label: t("customers.build.draft.reached", { defaultValue: "Reached" }),
      // ⚠ **THE COUNT COMES FROM THE DECLARED LIST** (`BR-SHL-046`), never
      // from a literal: `stepOf` reads the same `NEW_CONNECT_STEPS` the
      // wizard's rail renders, so this line and the rail cannot disagree.
      value: t("customers.build.draft.stepOf", {
        step: reached.step,
        of: reached.of,
        name: t(NEW_CONNECT_STEPS[reached.step - 1].labelKey, {
          defaultValue: NEW_CONNECT_STEPS[reached.step - 1].en,
        }),
        defaultValue: `Step ${reached.step} of ${reached.of}`,
      }),
    });
  }
  if (park !== null && park.waiting_on !== "") {
    tiles.push({
      id: "parked-because",
      label: t("customers.build.draft.because", { defaultValue: "Parked because" }),
      value: waitingOnLabel(park.waiting_on, t),
    });
  }
  if (park !== null && park.parked_at !== null) {
    tiles.push({
      id: "parked-at",
      label: t("customers.build.draft.parked", { defaultValue: "Parked" }),
      value: (
        <DateCell
          value={park.parked_at}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
          withTime
        />
      ),
    });
  }

  return (
    <>
      {tiles.length > 0 && (
        <div data-build-facts="draft">
          <KPIStrip kpis={tiles} />
        </div>
      )}
      <Panel as="section" data-build-section="answered">
        <h3>
          {t("customers.build.draft.answeredTitle", { defaultValue: "What has been answered" })}
        </h3>
        <ul className="m-0 flex list-none flex-col gap-2 p-0">
          {NEW_CONNECT_STEPS.map((step, index) => {
            // A step is ANSWERED when the draft reached past it. With no park
            // row nothing is known about progress, so nothing claims to be.
            const answered = reached !== null && index + 1 <= reached.step;
            return (
              <li
                key={step.id}
                data-draft-group={step.id}
                data-answered={answered ? "yes" : "no"}
                className={
                  "flex items-center justify-between gap-4 border border-divider px-3 py-2.5 " +
                  (answered ? "bg-surface text-text" : "bg-neutral-100 text-neutral-700")
                }
              >
                <span>
                  <span className="font-semibold">
                    {t(step.labelKey, { defaultValue: step.en })}
                  </span>
                  {!answered && (
                    <span>
                      {" · "}
                      {t("customers.build.draft.notReached", { defaultValue: "not reached" })}
                    </span>
                  )}
                </span>
                {answered && (
                  <Link
                    data-draft-edit={step.id}
                    to={`${props.path(carryOnPath(props.detail.id, park))}&step=${index + 1}`}
                  >
                    {t("customers.build.draft.edit", { defaultValue: "Edit" })}
                  </Link>
                )}
              </li>
            );
          })}
        </ul>
      </Panel>
    </>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// RE-PARK — the draft's own menu act, beside Cancel build
// ══════════════════════════════════════════════════════════════════════════

const REPARK_SCHEMA = z.object({ reason: z.string().trim().min(1) });

/**
 * ⚠ **IT PATCHES THE PARK ROW AND REFUSES BY NAME WITHOUT ONE.** Re-parking a
 * draft nobody parked has nothing to patch; `patchWizardPark` would need an id
 * this screen cannot invent, so the commit says so rather than appearing to
 * work. The nine reasons are `WIZARD_PARK_REASON_COPY`'s — the SAME closed
 * list the wizard's own park panel offers, so the words a clerk chose here and
 * the words the waiting list prints are one vocabulary (B18 §4.2).
 */
export function BuildRepakDialog(props: {
  t: Translator;
  park: WizardParkRow | null;
  client?: ApiClient;
  onClose: () => void;
  onDone?: () => void;
}) {
  const { t } = props;
  const client = props.client ?? api;
  const [reason, setReason] = useState(props.park?.waiting_on ?? "");

  async function submit(): Promise<FormSubmitOutcome> {
    if (props.park === null) {
      return {
        ok: false,
        error: { code: "UNAVAILABLE", message_key: "customers.build.draft.nothingParked" },
      };
    }
    try {
      await patchWizardPark(props.park.id, { waiting_on: reason }, client);
      props.onDone?.();
      props.onClose();
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "UNEXPECTED", message_key: UNEXPECTED_ERROR_KEY } };
    }
  }

  return (
    <FormModal
      title={t("customers.build.draft.repark", { defaultValue: "Re-park" })}
      schema={REPARK_SCHEMA}
      values={{ reason }}
      submitLabel={t("customers.build.draft.repark", { defaultValue: "Re-park" })}
      onClose={props.onClose}
      onSubmit={submit}
    >
      <SelectField
        id="repark-reason"
        label={t("customers.build.draft.because", { defaultValue: "Parked because" })}
        required
        value={reason}
        onChange={setReason}
        options={WIZARD_PARK_REASON_COPY.map((row) => ({
          value: row.code,
          label: t(row.key, { defaultValue: row.en }),
        }))}
        placeholder={t("customers.build.draft.pickReason", { defaultValue: "Choose a reason" })}
      />
    </FormModal>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-150-BRC09 task 13 · `10-draft.png`, read as an IMAGE (B14 rule 42)
// generated: 2026-09-28 by the DETAIL PAGE lane
// checklist: A=n/a(no backend half in this lane) B✔ C✔ D✔ E✔ F✔ G✔
//   H=deferred(PO)
// exceptions:
//   (1) **THE DRAWING SHOWS FIVE ANSWERED GROUPS AND THE DECLARED LIST HOLDS
//       EIGHT.** `Step 3 of 5` is a figure in a wireframe, which B14 rule 37
//       makes an ILLUSTRATION, and `BR-SHL-046` makes `NEW_CONNECT_STEPS` the
//       ONE list this panel and the wizard's rail may both read. The groups
//       are therefore the eight declared steps, in their declared order.
//   (2) **THE DRAWN SUMMARY BESIDE EACH GROUP** — *"Jonas Janssen · new ·
//       gov-ID missing"* — is NOT built. A park row's `values` are opaque by
//       declaration (*"Opaque here; each wizard narrows its own"*), and
//       narrowing eight steps' worth of typing into a sentence is the wizard's
//       own knowledge rather than this page's. REPORTED.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
