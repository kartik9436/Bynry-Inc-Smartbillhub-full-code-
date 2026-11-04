// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-009 (EP-CWP-03) — report sent: a reference a stranger can
//           keep. Screens: CWP-007
// Rules:    B14 rule 36 (layout from `08-screen-layouts.md` CWP-007 and
//           `wireframes/CWP-007.png`; look from r10; compose the kit) ·
//           BR-CWP-028 (every guest flow ends on a reference and offers to send
//           it) · BR-CWP-024 · CR-068 R3 / BR-CWP-056 (a control that may not
//           be used yet is disabled WITH its reason) · B14 rule 31 (no id is a
//           visible value — the reference is a NUMBER a person quotes, not a
//           database id) · rule 33
// Tests:    src/portal/guest/ReportProblem.test.tsx (the flow ends here)
// Impacts:  06-backend/apps/portal/guest_api.reports
// ───────────────────────────────────────────────────────
import { useTranslation } from "react-i18next";

import { Panel } from "@/components/Panel";

import type { ReportSentView } from "../api/guestClient";
import {
  ButtonRow,
  Card,
  ChecklistTimeline,
  HeldButton,
  KVList,
  SectionTitle,
  TwoCol,
} from "../components/primitives";

import { KIND_COPY } from "./ReportProblem";

/** `2 Sep 2026, 9:52am` — the wireframe's format, in the visitor's locale. */
export function reportedAtText(iso: string, locale: string): string {
  const at = new Date(iso);
  const day = at.toLocaleDateString(locale, { day: "numeric", month: "short", year: "numeric" });
  const time = at.toLocaleTimeString(locale, { hour: "numeric", minute: "2-digit" });
  return `${day}, ${time}`;
}

export function ReportSent(props: { sent: ReportSentView }) {
  const { t, i18n } = useTranslation();
  const { sent } = props;
  return (
    <div data-screen="CWP-007">
      <TwoCol
        main={
          <Card testId="cwp007-sent">
            <SectionTitle>{t("portal.sent.kicker")}</SectionTitle>
            <h2 className="m-0 text-h3 font-bold leading-tight text-neutral-900">
              {t("portal.sent.title")}
            </h2>
            <p className="m-0 max-w-measure text-body text-neutral-600">
              {t("portal.sent.lead")}
            </p>
            <KVList
              rows={[
                {
                  key: "reference",
                  label: t("portal.sent.reference"),
                  value: <span data-reference="">{sent.reference}</span>,
                },
                {
                  key: "reported",
                  label: t("portal.sent.reported"),
                  value: reportedAtText(sent.reported_at, i18n.language),
                },
                { key: "where", label: t("portal.sent.where"), value: sent.location_text },
                { key: "what", label: t("portal.sent.what"), value: t(KIND_COPY[sent.kind].label) },
              ]}
            />
            <ButtonRow>
              {/* ⚠ HELD. SMS is live from 2026-10-29 (CR-198-BRC10), but a
                  guest's number has no path to subscribe to this report's
                  updates — see `holds.ts`. Never hidden, never live-but-inert. */}
              <HeldButton
                label={t("portal.sent.textMe")}
                reason={t("portal.sent.textMeHeld")}
                size="default"
              />
            </ButtonRow>
          </Card>
        }
        rail={
          <Panel as="aside" title={t("portal.sent.whatHappensNow")}>
            <ChecklistTimeline
              steps={[
                {
                  label: t("portal.sent.step1"),
                  detail: t("portal.sent.step1note"),
                  state: "done",
                },
                {
                  label: t("portal.sent.step2"),
                  detail: t("portal.sent.step2note"),
                  state: "current",
                },
                {
                  label: t("portal.sent.step3"),
                  detail: t("portal.sent.step3note"),
                  state: "future",
                },
                {
                  label: t("portal.sent.step4"),
                  detail: t("portal.sent.step4note"),
                  state: "future",
                },
              ]}
            />
            {/* ⚠ THE CLOSING LINE MATTERS: people suppress a second report
                assuming it is a nuisance, and for a burst main it is the
                opposite (US-CWP-009 §1). */}
            <p className="mt-3 border-t border-neutral-200 pt-3 text-body text-neutral-600">
              {t("portal.sent.closing")}
            </p>
            {sent.already_reported_street !== null ? (
              <p className="mt-2 text-body text-neutral-600">
                {t("portal.sent.alreadyReported", { street: sent.already_reported_street })}
              </p>
            ) : null}
          </Panel>
        }
      />
    </div>
  );
}
