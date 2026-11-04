// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-PAY-6342 — marking post returned reached nobody: no banner on
//           the account, no list of what came back, no way to clear it.
// Story:    US-PAY-016   Screens: S21 (the account)
// Rules:    BR-PAY-018 (VERBATIM: "Returned mail: delivery record marked
//           returned (single/bulk) → account bad-address flag → needs-attention
//           queue + banner → paper suppressed until address verified (config);
//           balances unaffected; audited.") · PO ruling 2026-09-23, verbatim:
//           "fx it - ensure you update correct address - mailing or service" ·
//           CLAUDE.md hard rule 8 (the service address lives on the PREMISES;
//           a mailing address is its one named exception) · BR-TEN-043 (the
//           date is the clerk's, prefilled with the tenant's today) · B14
//           rules 21 (Tailwind only), 31 (no database id on screen), 33 (a
//           fact ≤ 6 words, a label ≤ 3, rationale zero), 43 (a component, not
//           code inside a page)
// ───────────────────────────────────────────────────────
// THE BANNER, AND THE CLEAR STEP THAT SENDS THE CLERK TO THE RIGHT ADDRESS.
//
// It renders only while `accounts.bad_address` is true — the ONE bad-address
// fact since DEF-PAY-6342 — so the banner, the Overview's `Bad address` row and
// the unit page's `Post came back` row can never disagree.
//
// ⚠ **THIS FILE EDITS NO ADDRESS, AND THAT IS THE PO's RULING RATHER THAN A
// GAP.** A letter went either to the account's MAILING address or to its
// SERVICE address (the premises), and the clear step routes on which:
//
//   went to              the clerk is offered
//   ─────────────────    ─────────────────────────────────────────────────────
//   mailing_address      correct the mailing address (blank street removes it,
//                        so post falls back to the premises) · address correct
//   service_address      ADD a mailing address · address correct · and the
//                        premises as a LINK only — editing it changes the
//                        address for every account at that property
//   unknown (no address  add/correct the mailing address · address correct
//   on the letter)
//
// "Correct/add" opens customers' OWN mailing-address door
// (`AccountPanelEditDialog`, `PATCH /accounts/{id}/mailing-address`) and only
// after it SAVES is the resolution recorded as `address_corrected`. "Address is
// correct" records `verified_current` — the carrier was wrong. Either way the
// server closes every open return and lowers the flag, and audits both.
//
// ⚠ **NOTHING HERE SAYS POST IS STOPPED.** Paper suppression is out of this
// release by PO ruling; the banner states the fact and nothing else.
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { z } from "zod";

import { formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import type { AccountDetail } from "@/api/endpoints";
import {
  RESOLUTION_ADDRESS_CORRECTED,
  RESOLUTION_VERIFIED_CURRENT,
  clearReturnedPost,
  getReturnedPost,
  returnedPostQueryKey,
} from "@/api/returnedMailEndpoints";
import type { ReturnedLetterWentTo, ReturnedPostRow } from "@/api/returnedMailEndpoints";
import { Button } from "@/components/Button";
import { formatDate, todayInZone } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { DatePickerField, FormModal, SegmentedField } from "@/components/FormModal";
import type { FormSubmitOutcome, Translator } from "@/components/FormModal";
import { LoadingSkeleton } from "@/components/StateFrame";
import { InlineLinkTo } from "@/components/Surfaces";
import { WarningBox } from "@/components/WarningBox";
import { premisesDetailPath } from "@/features/metering/meteringShared";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { AccountPanelEditDialog } from "./AccountPanelEdits";

/** What the clerk found. `fix` opens the mailing door; `correct` clears. */
type Finding = "fix" | "correct";

/** Built per render so both refusals are in the clerk's own language. */
function findingSchema(t: Translator) {
  return z.object({
    // DEF-CUS-10107 — a schema-level `errorMap` is OUTRANKED by
    // the form kit's parse-level `kitErrorMap` (zod 3 lets the contextual map
    // win), so the clerk saw the generic "This is required." A message bound
    // to a CHECK survives it, so the choice is a string checked twice.
    finding: z
      .string({ message: t("customers.account.returnedPost.outcomeRequired") })
      .min(1, t("customers.account.returnedPost.outcomeRequired"))
      .refine((v) => v === "fix" || v === "correct", t("customers.account.returnedPost.outcomeRequired")),
    resolved_on: z.string().min(1, t("customers.account.returnedPost.dateRequired")),
  });
}

/** The address the MOST RECENT open letter went to — the one the clerk is
 *  holding. Rows arrive oldest first. */
export function latestWentTo(rows: ReturnedPostRow[]): ReturnedLetterWentTo {
  return rows.length === 0 ? null : rows[rows.length - 1].went_to;
}

/** The catalogue key for where a letter went. Exported for the test. */
export function wentToKey(wentTo: ReturnedLetterWentTo): string {
  if (wentTo === "mailing_address") return "customers.account.returnedPost.wentTo.mailing";
  if (wentTo === "service_address") return "customers.account.returnedPost.wentTo.service";
  return "customers.account.returnedPost.wentTo.unknown";
}

export function ReturnedPostBanner(props: {
  detail: AccountDetail;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  client?: ApiClient;
  t: Translator;
  /** The flag moved: re-read the account and say so. */
  onDone: (message: string) => void;
}) {
  const { detail, t } = props;
  const [step, setStep] = useState<"closed" | "choose" | "mailing">("closed");
  const [resolvedOn, setResolvedOn] = useState("");

  if (!detail.bad_address) return null;

  async function recordCorrected(): Promise<void> {
    try {
      await clearReturnedPost(
        {
          account_id: detail.id,
          resolution: RESOLUTION_ADDRESS_CORRECTED,
          resolved_on: resolvedOn,
        },
        props.client,
      );
      props.onDone(t("customers.account.returnedPost.cleared"));
    } catch (error) {
      // The address DID save; only the clear failed. The banner stays up,
      // which is the truth, and the server's own sentence says why.
      props.onDone(apiErrorText(error, t));
    }
  }

  return (
    <div className="mt-4 mb-4" data-returned-post-banner="">
      <WarningBox
        tone="now"
        data-warning="returned-post"
        sentence={t("customers.account.returnedPost.banner")}
        action={
          <Button size="sm" onClick={() => setStep("choose")}>
            {t("customers.account.returnedPost.resolve")}
          </Button>
        }
      />
      {step === "choose" && (
        <ReturnedPostDialog
          detail={detail}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
          client={props.client}
          t={t}
          resolvedOn={resolvedOn}
          onResolvedOn={setResolvedOn}
          onClose={() => setStep("closed")}
          onFixMailing={() => setStep("mailing")}
          onCleared={() => {
            setStep("closed");
            props.onDone(t("customers.account.returnedPost.cleared"));
          }}
        />
      )}
      {step === "mailing" && (
        <AccountPanelEditDialog
          detail={detail}
          group="mailing"
          client={props.client}
          t={t}
          dateFormat={props.dateFormat}
          onClose={() => setStep("closed")}
          onSaved={() => {
            setStep("closed");
            void recordCorrected();
          }}
        />
      )}
    </div>
  );
}

function ReturnedPostDialog(props: {
  detail: AccountDetail;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  client?: ApiClient;
  t: Translator;
  resolvedOn: string;
  onResolvedOn: (value: string) => void;
  onClose: () => void;
  onFixMailing: () => void;
  onCleared: () => void;
}) {
  const { detail, t } = props;
  const tenantPath = useTenantPath();
  const [finding, setFinding] = useState<Finding | "">("");
  const returns = useQuery({
    queryKey: returnedPostQueryKey(detail.id),
    queryFn: () => getReturnedPost({ accountId: detail.id, per: 50 }, props.client),
    retry: false,
  });
  const rows = returns.data?.rows ?? [];
  const wentTo = latestWentTo(rows);
  const hasMailing = detail.addresses.some((address) => address.kind === "mailing");
  const premisesId = detail.service_premises_id ?? null;

  async function submit(): Promise<FormSubmitOutcome> {
    if (finding === "fix") {
      props.onFixMailing();
      return { ok: true };
    }
    try {
      await clearReturnedPost(
        {
          account_id: detail.id,
          resolution: RESOLUTION_VERIFIED_CURRENT,
          resolved_on: props.resolvedOn,
        },
        props.client,
      );
      props.onCleared();
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) return { ok: false, error: formErrorEnvelope(error) };
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t("customers.account.returnedPost.title")}
      kicker={detail.account_no ?? undefined}
      schema={findingSchema(t)}
      values={{ finding, resolved_on: props.resolvedOn }}
      submitLabel={
        finding === "fix"
          ? t("customers.account.returnedPost.submit.editMailing")
          : t("customers.account.returnedPost.submit.clear")
      }
      onSubmit={submit}
      onClose={props.onClose}
    >
      {returns.isError ? (
        <p className="m-0 mb-3 text-sm" role="alert">
          {apiErrorText(returns.error, t)}
        </p>
      ) : returns.data === undefined ? (
        <LoadingSkeleton variant="table" />
      ) : rows.length === 0 ? (
        <p className="m-0 mb-3 text-sm" data-returned-post-none="">
          {t("customers.account.returnedPost.none")}
        </p>
      ) : (
        <ul className="m-0 mb-3 list-none p-0 text-base" data-returned-post-letters="">
          {rows.map((row) => (
            <li key={row.event_id} className="mb-1" data-went-to={row.went_to ?? "unknown"}>
              {formatDate(row.returned_on, props.timeZone, props.dateFormat)}
              {" · "}
              {t(wentToKey(row.went_to))}
              {row.address !== null && ` · ${row.address}`}
            </li>
          ))}
        </ul>
      )}
      <SegmentedField
        id="finding"
        label={t("customers.account.returnedPost.outcome")}
        value={finding}
        onChange={(value) => setFinding(value as Finding)}
        required
        options={[
          {
            value: "fix",
            label: hasMailing
              ? t("customers.account.returnedPost.option.correctMailing")
              : t("customers.account.returnedPost.option.addMailing"),
          },
          { value: "correct", label: t("customers.account.returnedPost.option.addressCorrect") },
        ]}
      />
      {wentTo === "service_address" && premisesId !== null && (
        <p className="m-0 mb-3 text-sm" data-returned-post-premises="">
          <InlineLinkTo to={tenantPath(premisesDetailPath(premisesId))}>
            {t("customers.account.returnedPost.openPremises")}
          </InlineLinkTo>
        </p>
      )}
      <DatePickerField
        id="resolved_on"
        label={t("customers.account.returnedPost.dateChecked")}
        value={props.resolvedOn}
        onChange={props.onResolvedOn}
        prefill={todayInZone(props.timeZone)}
        dateFormat={props.dateFormat}
        required
      />
    </FormModal>
  );
}
