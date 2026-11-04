// ── Trace ──────────────────────────────────────────────
// Change:  CR-190-BRC10 lane AGREEMENT — the click-to-accept page (PO
//          2026-10-22: *"direct customer to screen where weshow them the
//          aggrement and customer can check a box and put a date and they can
//          submit request … make this as component so we can use this for other
//          aggrement also"*; answer 2, *"B: tick + date + typed name"*)
// Rules:   B14 rule 43 (a COMPONENT, not code inside a page) · rule 21
//          (Tailwind only) · rule 31 (no id on screen — the token is never
//          shown) · rule 33 (labels ≤3 words, facts ≤6, no rationale) · rule 35
//          (eleven native catalogues) · the eight portal accessibility
//          questions (`22-product-maintenance-process.md` §6)
// Tests:   src/portal/agreements/AgreementPage.dom.test.tsx
// ───────────────────────────────────────────────────────
import { useEffect, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { WorkingButton } from "@/components/StateFrame";

import type { AcceptBody, AgreementOpen } from "../api/agreementClient";
import { FormScope, usePortalForm } from "../components/a11y";
import { PortalDateBox } from "../components/PortalDateField";
import { Card, FormField, KVList, SectionTitle, TextInput } from "../components/primitives";
import { usePortalDate } from "../components/regional";

/** Field refusals by field — the server's `field_errors`, already in words. */
export type AgreementFieldErrors = Partial<Record<"agreed" | "date" | "name", string>>;

/**
 * ONE agreement to accept: who it is for, its text exactly as published, the
 * PDF, and the three things the PO ruled the customer gives — the tick, today's
 * date, their typed name. Any Contracts template renders through this; the
 * page around it only fetches and posts.
 */
export function AgreementAcceptance(props: {
  agreement: AgreementOpen;
  documentHref: string;
  onAccept: (body: AcceptBody) => void;
  working: boolean;
  errors?: AgreementFieldErrors;
}) {
  const { t } = useTranslation();
  const formatDate = usePortalDate();
  const ids = useId();
  const [agreed, setAgreed] = useState(false);
  const [date, setDate] = useState("");
  const [name, setName] = useState("");
  // A refusal is shown until its field is changed: an error left under a
  // field the customer has already corrected reads as a second refusal.
  const [edited, setEdited] = useState<Set<string>>(new Set());
  useEffect(() => setEdited(new Set()), [props.errors]);
  // F-02 / F-04: a refused acceptance lands on the error summary.
  const form = usePortalForm();
  const { failed } = form;
  useEffect(() => {
    if (props.errors && Object.keys(props.errors).length > 0) failed();
  }, [props.errors, failed]);
  const touch = (field: string) => setEdited((prev) => new Set(prev).add(field));
  const raw = props.errors ?? {};
  const errors: AgreementFieldErrors = Object.fromEntries(
    Object.entries(raw).filter(([field]) => !edited.has(field)),
  );
  const { agreement } = props;
  const tickId = `${ids}-agreed`;
  const dateId = `${ids}-date`;
  const nameId = `${ids}-name`;
  const textId = `${ids}-text`;

  return (
    <Card testId="agreement-acceptance">
      <div data-screen="agreement-acceptance" className="flex flex-col gap-4">
        <div>
          {agreement.utility_name !== null ? <SectionTitle>{agreement.utility_name}</SectionTitle> : null}
          <h1 className="text-h1 leading-tight text-neutral-900">{agreement.agreement_name}</h1>
          <p className="mt-1 text-base text-neutral-600" data-agreement-version="">
            {agreement.effective_from !== null
              ? t("portal.agreement.version", {
                  version: agreement.version,
                  date: formatDate(agreement.effective_from),
                })
              : t("portal.agreement.versionOnly", { version: agreement.version })}
          </p>
        </div>
        <KVList
          rows={[
            { key: "customer", label: t("portal.agreement.customer"), value: agreement.customer_name },
            { key: "account", label: t("portal.agreement.account"), value: agreement.account_no },
          ]}
        />
        <section aria-labelledby={textId} className="flex flex-col gap-2">
          <h2 id={textId} className="m-0 text-md font-semibold text-neutral-900">
            {t("portal.agreement.textTitle")}
          </h2>
          {/* The text as published — preformatted so its paragraphs are its own. */}
          <div
            className="max-h-[480px] overflow-y-auto whitespace-pre-wrap border border-neutral-200 bg-neutral-100 p-4 text-body leading-relaxed text-neutral-800"
            tabIndex={0}
            data-agreement-text=""
          >
            {agreement.text}
          </div>
          <a
            href={props.documentHref}
            download
            className="inline-flex min-h-11 items-center self-start font-semibold text-accent-text underline"
            data-agreement-download=""
          >
            {t("portal.agreement.download")}
          </a>
        </section>
        <form
          className="flex max-w-[420px] flex-col gap-3"
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            props.onAccept({ agreed, date, name });
          }}
        >
          <div className="flex flex-col">
            <label
              htmlFor={tickId}
              className="flex min-h-11 cursor-pointer items-center gap-2 text-base font-semibold text-neutral-900"
            >
              <input
                id={tickId}
                type="checkbox"
                className="size-4"
                checked={agreed}
                aria-invalid={errors.agreed !== undefined}
                aria-describedby={`${tickId}-error`}
                onChange={(event) => {
                  setAgreed(event.target.checked);
                  touch("agreed");
                }}
                data-agreement-tick=""
              />
              {t("portal.agreement.agree")}
            </label>
            <p
              id={`${tickId}-error`}
              aria-live="polite"
              className={errors.agreed ? "mt-1.5 text-base font-semibold text-danger-700" : "sr-only"}
            >
              {errors.agreed ?? ""}
            </p>
          </div>
          <FormScope form={form}>
          <FormField id={dateId} label={t("portal.agreement.date")} required error={errors.date ?? null}>
            <PortalDateBox
              id={dateId}
              value={date}
              onChange={(value) => {
                setDate(value);
                touch("date");
              }}
              invalid={errors.date !== undefined}
              min={agreement.today}
              max={agreement.today}
              required
            />
          </FormField>
          <FormField id={nameId} label={t("portal.agreement.name")} required error={errors.name ?? null}>
            <TextInput
              id={nameId}
              value={name}
              onChange={(value) => {
                setName(value);
                touch("name");
              }}
              invalid={errors.name !== undefined}
              describedBy={`${nameId}-error`}
              required
              autoComplete="name"
            />
          </FormField>
          </FormScope>
          <div>
            <WorkingButton working={props.working} type="submit">
              {t("portal.agreement.submit")}
            </WorkingButton>
          </div>
        </form>
      </div>
    </Card>
  );
}

/** The confirmation, once accepted. */
export function AgreementAccepted(props: { agreementName: string; date: string; name: string }) {
  const { t } = useTranslation();
  const formatDate = usePortalDate();
  return (
    <Card testId="agreement-accepted">
      <div data-screen="agreement-accepted" role="status" className="flex flex-col gap-2">
        <h1 className="text-h1 leading-tight text-neutral-900">{t("portal.agreement.doneTitle")}</h1>
        <p className="text-body text-neutral-800">{props.agreementName}</p>
        <p className="text-body text-neutral-800" data-agreement-done="">
          {t("portal.agreement.done", { date: formatDate(props.date), name: props.name })}
        </p>
        <p className="text-base text-neutral-600">{t("portal.agreement.doneEmail")}</p>
      </div>
    </Card>
  );
}

/**
 * The dead end — the PO's own words, *"This link has expired. Call the
 * office"*, with the utility's number from Settings. One screen for every link
 * that does not open, so nothing tells a stranger which links once existed.
 */
export function AgreementLinkExpired(props: { phone: string | null }) {
  const { t } = useTranslation();
  return (
    <Card testId="agreement-expired">
      <div data-screen="agreement-expired" className="flex flex-col gap-2">
        <h1 className="text-h1 leading-tight text-neutral-900">{t("portal.agreement.expiredTitle")}</h1>
        <p className="text-body text-neutral-800" data-agreement-call="">
          {props.phone !== null ? (
            <>
              {t("portal.agreement.callOfficeOn")}{" "}
              <a className="font-semibold text-accent-text underline" href={`tel:${props.phone.replace(/[^\d+]/g, "")}`}>
                {props.phone}
              </a>
            </>
          ) : (
            t("portal.agreement.callOffice")
          )}
        </p>
      </div>
    </Card>
  );
}
