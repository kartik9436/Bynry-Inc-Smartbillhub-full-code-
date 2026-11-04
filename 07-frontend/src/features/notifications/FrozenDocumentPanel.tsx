// ── Trace ──────────────────────────────────────────────
// Change:   CR-049 task 3 — the SCREEN half. "A reprint and a regulator request
//           serve the stored copy and never re-render."
// Rules:    BR-NOT-027 (a sent legal document is FROZEN as the document — PO
//           2026-08-30) · BR-NOT-025 / BR-BIL-026 (the pin is PROVENANCE) ·
//           BR-SHL-020 (plain language when something is absent) · B14 rule 21
//           (new UI is Tailwind utilities and adds NO class to a stylesheet —
//           this file is on route-b-migrated.txt from its first commit) ·
//           hard-won law 2 (built is not wired)
// Tests:    07-frontend/src/features/notifications/frozenDocument.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// SHOW ME WHAT WE ACTUALLY SENT.
//
// ⚠ THE WHOLE POINT OF THIS COMPONENT IS THAT TWO STATES LOOK DIFFERENT.
// Until CR-049 this product kept everything a letter was built FROM and no copy
// of the letter, so asking to see a notice again rebuilt it from that data using
// today's settings — and if somebody had edited the wording in between, the
// "reprint" quietly carried the new words. The Product Owner's reason, verbatim:
//
//     *"otherwie everytime we reproduce it using data in table, we might change
//     something about it and that is not correct"*
//
// So this draws ONE of two things and never blurs them:
//
//   · **THE ORIGINAL** — the document as it was sealed at send, byte for byte,
//     with its hash re-checked on this read. Headed as the original, with the
//     moment it was sealed.
//   · **NOT THE ORIGINAL** — no sealed copy exists. **Nothing is rendered in its
//     place.** The panel says so in a warning tier and stops. A screen that
//     showed a reconstruction here, however well captioned, would be the defect
//     the whole change request exists to remove.
//
// **THE SERVER DECIDES WHICH, AND THE SERVER WRITES THE SENTENCE.** This file
// branches on `is_original` and prints `message_key` — it never composes its own
// account of provenance, because the backend and the screen describing the same
// state in two different ways is how they drift apart.
//
// ⚠ THERE IS NO RE-RENDER PATH HERE EITHER. This component has no template, no
// merge context and no fallback: `document` is `null` on every non-original
// answer, so there is nothing to print by mistake.
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getOutboundDocument } from "@/api/endpoints";
import type { OutboundDocumentResponse } from "@/api/endpoints";
import { ButtonAnchor } from "@/components/Button";
import { LoadingSkeleton } from "@/components/StateFrame";
import { Panel, apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";

export const frozenDocumentKey = (messageId: string) =>
  ["notifications", "frozen-document", messageId] as const;

/** Whole hours, for the sentence beside the download link. The server sends
 *  SECONDS because the TTL is a setting it can shorten without a deploy; this
 *  turns it into the number a person reads, and never hardcodes four. */
export function ttlHours(seconds: number): number {
  return Math.max(1, Math.round(seconds / 3600));
}

/** Bytes as a short human figure. A letter is kilobytes; nothing here is big
 *  enough to need more than one decimal. */
export function byteLabel(bytes: number): string {
  if (bytes < 1024) {
    return `${String(bytes)} B`;
  }
  return `${(bytes / 1024).toFixed(1)} KB`;
}

/**
 * THE ORIGINAL — the document as it left the building.
 *
 * The text is drawn in a `<pre>` because that is what was stored: print freezes
 * the letter text handed to the vendor and SMS the message text, both with
 * their own line breaks (CR-049 decision 2 — print is TEXT and not a PDF until
 * a page renderer exists, `OQ-149`). Collapsing that whitespace would reflow a
 * legal document on its way to a screen, which is a small version of the exact
 * thing this rule forbids.
 */
function OriginalDocument(props: {
  document: NonNullable<OutboundDocumentResponse["document"]>;
  t: Translator;
}) {
  const { document: doc, t } = props;
  return (
    <div className="flex flex-col gap-3">
      {/* ⚠ THE SERVER'S OWN SENTENCE FOR THIS STATE, from the key the backend
          named — `frozen_documents.I18N_ORIGINAL`. The backend and this screen
          MUST describe one state with one sentence, or they drift apart and the
          product ends up making two different claims about the same document.
          The key already carries `{{sentOn}}`; nothing here composes a second
          "when was it sealed" sentence beside it. */}
      <p className="m-0 rounded-md border border-success-500 bg-success-100 px-3 py-2 text-sm text-text">
        <strong>
          {t("notifications.frozenDocument.original", {
            sentOn: new Date(doc.stored_at).toLocaleString(),
          })}
        </strong>
      </p>
      {doc.subject !== null && doc.subject !== "" ? (
        <p className="m-0 text-sm text-text">
          <span className="uppercase tracking-tag text-xs text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">
            {t("notifications.frozenDocument.subject")}
          </span>
          <br />
          <strong>{doc.subject}</strong>
        </p>
      ) : null}
      <pre className="m-0 max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-md border border-divider bg-surface px-3 py-2 font-mono text-xs leading-relaxed text-text">
        {doc.text ?? ""}
      </pre>
      <dl className="m-0 grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-3 text-xs">
        <div>
          <dt className="uppercase tracking-tag text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">
            {t("notifications.frozenDocument.fileName")}
          </dt>
          <dd className="m-0 mt-1 break-words">{doc.display_name}</dd>
        </div>
        <div>
          <dt className="uppercase tracking-tag text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">
            {t("notifications.frozenDocument.size")}
          </dt>
          <dd className="m-0 mt-1">{byteLabel(doc.byte_length)}</dd>
        </div>
        <div>
          {/* The hash is shown because it is the thing that PROVES this copy is
              unchanged, and a regulator or an auditor holding their own copy can
              compare it without asking us. It was re-computed and matched on
              THIS read — a mismatch never reaches this component, it is a
              refusal. */}
          <dt className="uppercase tracking-tag text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">
            {t("notifications.frozenDocument.checksum")}
          </dt>
          <dd className="m-0 mt-1 break-all font-mono">{doc.content_hash}</dd>
        </div>
      </dl>
      <div className="flex flex-wrap items-center gap-2">
        <ButtonAnchor variant="secondary" href={doc.download_url} target="_blank" rel="noreferrer">
          {t("notifications.frozenDocument.download")}
        </ButtonAnchor>
        {/* ⚠ SAID OUT LOUD, because the link is a BEARER TOKEN. Whoever holds it
            reads this one document with no session until it expires — the PO
            accepted that exposure when they ruled the TTL up from minutes to
            hours so a bulk export could work through a manifest in parallel. A
            person forwarding it in an email should know that. */}
        <span className="text-xs text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">
          {t("notifications.frozenDocument.linkExpires", {
            hours: ttlHours(doc.url_expires_in_seconds),
          })}
        </span>
      </div>
    </div>
  );
}

/**
 * NOT THE ORIGINAL — and nothing is drawn in its place.
 *
 * ⚠ **THE ABSENCE OF CONTENT IS THE FEATURE.** The temptation is to show the
 * re-render under a caption, and a caption is exactly what nobody reads. So this
 * branch has no document to show, says which of the two reasons applies, and
 * ends.
 *
 * `exempt` separates the innocent cases — an in-app staff alert and a send test,
 * both ruled out of the freeze by the PO — from a real gap. They are not the
 * same fact, and telling a clerk "we did not keep this" about a rehearsal they
 * sent themselves would be false.
 */
function NotTheOriginal(props: { answer: OutboundDocumentResponse; t: Translator }) {
  const { answer, t } = props;
  const tone = answer.exempt ? "border-divider bg-surface" : "border-warning-500 bg-warning-100";
  return (
    <div className={`flex flex-col gap-2 rounded-md border px-3 py-2 ${tone}`}>
      <p className="m-0 text-sm text-text">
        <strong>{t(answer.message_key)}</strong>
      </p>
      {/* The server's own sentence, in its own words. It knows which of the
          reasons applies and this screen does not re-say it differently. */}
      <p className="m-0 text-xs text-[color-mix(in_srgb,var(--color-text)_75%,transparent)]">
        {answer.detail}
      </p>
    </div>
  );
}

/**
 * The panel a clerk opens from a queue row.
 *
 * `client` is PASSED, never defaulted at the call site — the whole DEF-007..010
 * class is a component with an optional prop nothing supplies (hard-won law 2).
 */
export function FrozenDocumentPanel(props: {
  messageId: string;
  client?: ApiClient;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;

  const answer = useQuery({
    queryKey: frozenDocumentKey(props.messageId),
    queryFn: () => getOutboundDocument(props.messageId, client),
    // A reprint is a legal read, not a cached figure: it must reflect the store
    // as it is now, including a document that has since failed its hash check.
    staleTime: 0,
    retry: false,
  });

  return (
    <Panel
      title={t("notifications.frozenDocument.title")}
      hint={t("notifications.frozenDocument.description")}
    >
      <div className="mb-3 flex justify-end">
        <button type="button" onClick={props.onClose}>
          {t("notifications.frozenDocument.close")}
        </button>
      </div>
      {answer.isPending ? <LoadingSkeleton variant="card" /> : null}
      {answer.error !== null && answer.error !== undefined ? (
        // ⚠ A REFUSAL IS SHOWN AS A REFUSAL. The two that matter here are a
        // document whose bytes no longer match their hash and one whose bytes
        // have gone: both mean a sealed legal record is damaged, and neither may
        // be softened into "we did not keep a copy" — that sentence is for a
        // document that was never stored, and blurring them would hide a
        // corrupted record behind a reassuring caption.
        <p className="m-0 rounded-md border border-danger-500 bg-danger-100 px-3 py-2 text-sm text-text">
          {apiErrorText(answer.error, translate)}
        </p>
      ) : null}
      {answer.data !== undefined ? (
        answer.data.is_original && answer.data.document !== null ? (
          <OriginalDocument document={answer.data.document} t={translate} />
        ) : (
          <NotTheOriginal answer={answer.data} t={translate} />
        )
      ) : null}
    </Panel>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-049 task 3 (sources: 12-governance/11-change-requests.md CR-049 steps 5b/5c/5d(e) · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-027 · 06-backend/apps/notifications/reprint_api.py, this lane's route · 06-backend/apps/notifications/frozen_documents.py reproduce())
// generated: 2026-08-30 by the CR-049 task 3 lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — the panel was shown drawing NOTHING for a served notice before the route existed, and the two-state assertion was shown failing against a draft that rendered `detail` for both provenances. Verbatim transcripts in the lane report.
// exceptions: (1) NO RE-RENDER FALLBACK, deliberately — `document` is null on every non-original answer, so this component has nothing to draw in place of a letter and cannot acquire one without a new prop. (2) PRINT IS TEXT, NOT A PDF (CR-049 decision 2, OQ-149) — the `<pre>` is the honest presentation of what is actually stored, and it becomes a PDF viewer the day a page renderer lands, with no change to the rule. (3) THE DOWNLOAD LINK IS A BEARER TOKEN and the panel says so rather than leaving a clerk to discover it.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
