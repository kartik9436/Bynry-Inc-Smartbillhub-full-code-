// ── Trace ──────────────────────────────────────────────
// Change:   CR-192-BRC10 — MQ-033 task 13: the answers a reader gave, on the
//           reading's page (*"shown on the reading"*, decision log 2026-10-24).
// Rules:    BR-MET-1218 · BR-MET-1216 (a flagged answer is kept — so it is
//           shown, with its flag) · BR-WRK-008 (the words are the stamped
//           version's) · B14 rules 31 (an order NUMBER, never an id), 33
//           (labels ≤ 3 words, facts ≤ 6, no rationale), 36/43 (the kit's
//           Panel, built as a component) · rule 44 (our spacing and type)
// Tests:    ReadFormatAnswersPanel.dom.test.tsx
// ───────────────────────────────────────────────────────
/**
 * ⑯ READ FORMAT — one information group on the reading's page, a `Panel` like
 * the five beside it.
 *
 * What it holds, top to bottom: the format's name and version; *Needs review*
 * when the server flagged any answer; then one row per question — the
 * utility's OWN words verbatim (a label is tenant prose, never translated),
 * the answer, the flag when there is one, and the job an answer raised.
 *
 * A reading that carried no format renders NOTHING: it reads exactly as it
 * did before formats existed (*"a utility with no template reads exactly as
 * today"*), and a panel saying so would be rationale (B14 rule 33).
 *
 * A photograph answer is a THUMBNAIL that opens the picture. The bytes come
 * through the API (`GET reads/photos/{id}/content`) for `DEF-WRK-9594`'s
 * reason — the page policy draws images only from itself.
 */
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";

import type { ReadFormatAnswer, ReadFormatAnswers } from "@/api/endpoints";
import { ModalShell } from "@/components/FormModal";
import { Panel } from "@/components/Panel";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkTo } from "@/components/Surfaces";
import { Kicker } from "@/components/TextBits";
import { WORK_ORDERS_ROUTE } from "@/features/work/WorkShell";
import { useTenantPath } from "@/routing/tenantPath";

import { Dash } from "./meteringShared";
import { answerPhotoHref, answerValueText } from "./readAnswersShared";

const PHOTO = "photo";

export function ReadFormatAnswersPanel(props: { answers: ReadFormatAnswers | null | undefined }) {
  const { t } = useTranslation();
  const [viewing, setViewing] = useState<ReadFormatAnswer | null>(null);
  const block = props.answers ?? null;
  if (block === null) return null;
  const format = block.read_format;
  return (
    <Panel as="section" title={<Kicker>{t("metering.read.panel.readFormat")}</Kicker>}>
      <div className="flex flex-wrap items-center gap-2" data-read-format="">
        {format === null ? (
          <span className="text-sm">{t("metering.read.answers.formatUnknown")}</span>
        ) : (
          <span className="text-sm font-semibold" title={format.id}>
            {format.version_no === null
              ? format.name
              : t("metering.read.answers.formatVersion", {
                  name: format.name,
                  version: format.version_no,
                })}
          </span>
        )}
        {block.needs_review && (
          <StatusPill tone="warning">
            <span data-needs-review="">{t("metering.read.answers.needsReview")}</span>
          </StatusPill>
        )}
      </div>

      {block.answers.length === 0 ? (
        <p className="m-0 mt-3 text-sm">{t("metering.read.answers.none")}</p>
      ) : (
        // The same fact list the EVIDENCE panel beside it draws (one shape per page).
        <dl className="met-facts mt-3 text-sm leading-note">
          {block.answers.map((answer) => (
            <AnswerRow key={answer.question_key} answer={answer} onView={() => setViewing(answer)} />
          ))}
        </dl>
      )}

      {viewing !== null && (
        <AnswerPhotoViewer answer={viewing} onClose={() => setViewing(null)} />
      )}
    </Panel>
  );
}

function AnswerRow(props: { answer: ReadFormatAnswer; onView: () => void }) {
  const { t } = useTranslation();
  const tenantPath = useTenantPath();
  const { answer } = props;
  const order = answer.work_order;
  return (
    <>
      {/* The utility's own words, verbatim — tenant prose, never translated. */}
      <dt data-answer-label={answer.question_key}>
        {answer.label ?? answer.question_key}
      </dt>
      <dd className="flex flex-wrap items-center gap-2" data-answer={answer.question_key}>
        <AnswerValue answer={answer} onView={props.onView} />
        {answer.issue !== null && (
          <StatusPill tone="warning">
            <span data-answer-issue={answer.issue}>
              {t(`metering.read.answers.issue.${answer.issue}`)}
            </span>
          </StatusPill>
        )}
        {order !== null && order.order_no !== null && order.order_no !== "" && (
          <InlineLinkTo
            to={tenantPath(`${WORK_ORDERS_ROUTE}/${order.order_no}`)}
            data-answer-job={order.order_no}
          >
            {order.order_no}
          </InlineLinkTo>
        )}
      </dd>
    </>
  );
}

function AnswerValue(props: { answer: ReadFormatAnswer; onView: () => void }) {
  const { t } = useTranslation();
  const { tenant = "" } = useParams();
  const { answer } = props;
  if (answer.data_type === PHOTO && answer.photo_id !== null) {
    const src = answerPhotoHref(tenant, answer.photo_id);
    return (
      <button
        type="button"
        data-answer-photo=""
        className="h-12 w-16 cursor-pointer border border-divider bg-surface p-0 focus-visible:outline-2 focus-visible:outline-accent"
        aria-label={t("metering.read.answers.openPhoto", {
          label: answer.label ?? answer.question_key,
        })}
        onClick={props.onView}
      >
        {src !== null ? <img src={src} alt="" className="h-full w-full object-cover" /> : <Dash />}
      </button>
    );
  }
  const text = answerValueText(answer.value, (key, params) => t(key, params));
  return text === null ? <Dash /> : <span>{text}</span>;
}

function AnswerPhotoViewer(props: { answer: ReadFormatAnswer; onClose: () => void }) {
  const { tenant = "" } = useParams();
  const title = props.answer.label ?? props.answer.question_key;
  const src = props.answer.photo_id === null ? null : answerPhotoHref(tenant, props.answer.photo_id);
  return (
    <ModalShell title={title} onClose={props.onClose} size="wide">
      <div className="modal-body" data-answer-photo-viewer="">
        <div className="flex min-h-64 items-center justify-center border border-divider bg-surface">
          {src !== null ? (
            <img src={src} alt={title} className="max-h-96 w-full object-contain" />
          ) : (
            <Dash />
          )}
        </div>
      </div>
    </ModalShell>
  );
}
