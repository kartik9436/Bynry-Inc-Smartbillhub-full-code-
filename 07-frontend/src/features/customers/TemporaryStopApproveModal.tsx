// ── Trace ──────────────────────────────────────────────
// Change:   CR-183-BRC10 T3 — the Approve window for a *Temporary stop* or a
//           *Restart now* request (PO rulings B1–B4, 2026-10-14).
// Rules:    BR-CUS-1120 (B1 base charge only during the hold · B2 *Field visit
//           needed* is the clerk's tick · B4 restart from today) · BR-CUS-1121
//           (B3 limits — the window draws the SERVER's problems and decides
//           none) · B14 rule 43 (its own component; the request page mounts
//           it) · rule 36/38/44 (the kit: `FormModal`, `DatePickerField`,
//           `CheckboxField`, `CheckList`, `ConsequenceBox`) · rule 31 (the
//           account NUMBER, never an id) · rule 33 (labels ≤ 3 words, facts ≤ 6,
//           no rationale) · BR-SHL-025 (Approve disabled WITH its reason)
// Tests:    src/features/customers/TemporaryStopApproveModal.dom.test.tsx ·
//           ServiceRequestDetailPage.dom.test.tsx (mounted under the real route)
// ───────────────────────────────────────────────────────
//
//     Approve SR-26-0017 · Temporary stop
//     Stop from   [ 2026-10-20 ]      Restart on  [ 2026-10-30 ]
//     Checks
//      ✓  Account        AC-2026-00551
//      ✓  Dates          10 days
//      !  During hold    Base charge only
//     [ ] Field visit needed
//      ▌ The account stays open.
//      ▌ Base charge only from 20-Oct-26.
//                                  Cancel   [ Approve ]
//
// ⚠ **NEW CONNECTION AND MOVE-IN ARE NOT OFFERED HERE AND CANNOT BE.** The
// PO's report on SR-26-0017 was exactly that a stop ask could only become one
// of those two; the server refuses both for this request by name.
//
// ⚠ **THE DATES ARE EDITABLE** (the clerk agrees different ones on the phone),
// and the problems shown are the server's for the dates it HOLDS. A date moved
// here is checked by the server on the press — the window holds no copy of the
// limits beyond the figures it prints.
import { useState } from "react";
import { z } from "zod";

import { CheckList } from "@/components/CheckList";
import type { CheckRow } from "@/components/CheckList";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { formatDate } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { CheckboxField, DatePickerField, FormModal } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";

import type { ServiceRequestDetail } from "./serviceRequestEndpoints";
import type { TemporaryStopForRequest } from "./temporaryStopEndpoints";

type Translate = (key: string, params?: Record<string, unknown>) => string;

const NS = "customers.temporaryStop";
const SCHEMA = z.object({});

export interface TemporaryStopChoice {
  stopFrom?: string;
  restartOn?: string;
  fieldVisitNeeded: boolean;
}

export function TemporaryStopApproveModal(props: {
  detail: ServiceRequestDetail;
  stop: TemporaryStopForRequest;
  t: Translate;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  onClose: () => void;
  onSubmit: (choice: TemporaryStopChoice) => Promise<FormSubmitOutcome>;
}) {
  const { t, stop } = props;
  const isRestart = stop.kind === "restart_now";
  const [stopFrom, setStopFrom] = useState(stop.stop.stop_from);
  const [restartOn, setRestartOn] = useState(stop.stop.restart_on ?? "");
  const [fieldVisit, setFieldVisit] = useState(false);
  const date = (value: string) => formatDate(value, props.timeZone, props.dateFormat);

  // What the server said about the dates it HOLDS. Once the clerk moves a
  // date, those problems describe dates that are no longer on screen, so the
  // window stops drawing them and the server judges the new pair on the press.
  const moved =
    !isRestart && (stopFrom !== stop.stop.stop_from || restartOn !== (stop.stop.restart_on ?? ""));
  const problems = moved ? [] : stop.problems;
  const days =
    stopFrom !== "" && restartOn !== ""
      ? Math.round((Date.parse(restartOn) - Date.parse(stopFrom)) / 86_400_000)
      : null;

  const rows: CheckRow[] = [
    {
      id: "account",
      label: t(`${NS}.check.account`),
      state: problems.some((p) => p.code === "account_not_active" || p.code === "already_on_hold")
        ? "bad"
        : "ok",
      fact: stop.stop.account_no,
    },
  ];
  if (isRestart) {
    rows.push({
      id: "restart",
      label: t(`${NS}.check.restart`),
      state: problems.length > 0 ? "bad" : "ok",
      fact: t(`${NS}.fact.backOnFrom`, { date: date(stop.restart_from ?? "") }),
    });
  } else {
    const dateProblem = problems.find(
      (p) => p.code !== "account_not_active" && p.code !== "already_on_hold",
    );
    rows.push({
      id: "dates",
      label: t(`${NS}.check.dates`),
      state: dateProblem === undefined ? "ok" : "bad",
      fact:
        dateProblem !== undefined
          ? t(dateProblem.message_key, dateProblem.params)
          : days === null
            ? t(`${NS}.restartRequired`)
            : t(`${NS}.fact.days`, { days }),
    });
    rows.push({
      id: "billing",
      label: t(`${NS}.check.billing`),
      state: "noted",
      fact: t(`${NS}.fact.baseOnly`),
    });
  }

  const blocked = problems.length > 0 ? t(problems[0]?.message_key ?? "", problems[0]?.params) : undefined;

  return (
    <FormModal
      title={t(isRestart ? `${NS}.approve.titleRestart` : `${NS}.approve.title`, {
        number: props.detail.header.request_no ?? "",
      })}
      schema={SCHEMA}
      values={{}}
      submitLabel={t(`${NS}.approve.submit`)}
      commitBlocked={blocked}
      onClose={props.onClose}
      onSubmit={() =>
        props.onSubmit(
          isRestart
            ? { fieldVisitNeeded: false }
            : {
                stopFrom: stopFrom || undefined,
                restartOn: restartOn || undefined,
                fieldVisitNeeded: fieldVisit,
              },
        )
      }
    >
      {!isRestart && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2" data-temporary-stop-dates="">
          <DatePickerField
            id="temporary-stop-from"
            label={t(`${NS}.field.stopFrom`)}
            value={stopFrom}
            onChange={setStopFrom}
            dateFormat={props.dateFormat}
            required
          />
          <DatePickerField
            id="temporary-stop-restart"
            label={t(`${NS}.field.restartOn`)}
            value={restartOn}
            onChange={setRestartOn}
            dateFormat={props.dateFormat}
            required
          />
        </div>
      )}
      <section data-temporary-stop-checks={stop.kind}>
        <h4 className="m-0 mb-1 text-xs font-semibold tracking-wide text-accent uppercase">
          {t("customers.serviceRequest.approveChecks.checks")}
        </h4>
        <CheckList
          rows={rows}
          label={t("customers.serviceRequest.approveChecks.checksLabel")}
          stateLabels={{
            ok: t("customers.serviceRequest.check.state.ok"),
            bad: t("customers.serviceRequest.check.state.bad"),
            noted: t("customers.serviceRequest.check.state.noted"),
            notReached: t("customers.serviceRequest.check.state.notReached"),
          }}
        />
      </section>
      {!isRestart && (
        <CheckboxField
          id="temporary-stop-field-visit"
          label={t(`${NS}.field.fieldVisit`)}
          checked={fieldVisit}
          onChange={setFieldVisit}
        />
      )}
      <ConsequenceBox
        tone="check"
        tag={t("customers.serviceRequest.approveChecks.effectTag")}
        title={t(isRestart ? `${NS}.consequence.restartTitle` : `${NS}.consequence.title`)}
        body={
          isRestart
            ? t(`${NS}.consequence.restartBody`, { date: date(stop.restart_from ?? "") })
            : t(`${NS}.consequence.body`, { date: stopFrom === "" ? "" : date(stopFrom) })
        }
        data-consequence={`approve-${stop.kind}`}
      />
    </FormModal>
  );
}
