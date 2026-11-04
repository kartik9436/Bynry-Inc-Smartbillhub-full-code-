// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CWP-nnnn — ⚠ `nnnn` IS A PLACEHOLDER, NOT A TYPO: the row is
//           handed over in `scratchpad/lane-NOTIF-defects.md` and its id is
//           allocated at merge. Fill it in here in the same diff.
//           The portal enrolment code is minted, queued and
//           readable by nobody, so a beta tenant with no provider cannot finish
//           an enrolment. PO: *"Atleast show me 6 digit code on this screen -
//           so that I can copy and paste it during enrolement"*.
// Ruling:   12-governance/02-decision-log.md 2026-09-05 §2 — the body shows
//           ONLY while the tenant has no provider connected for that channel.
// Rules:    B14 rule 21 (new UI is Tailwind utilities and adds NO class to a
//           stylesheet — this file is on route-b-migrated.txt from its first
//           commit) · rule 32 (one sentence per section; no rule id or internal
//           code in clerk-facing copy) · rule 36 (the shared component kit is
//           how you comply) · hard-won law 2 (built is not wired)
// Tests:    07-frontend/src/features/notifications/unsentMessage.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// SHOW ME WHAT IS WAITING TO GO OUT, WHEN NOTHING CAN SEND IT.
//
// ⚠ **THIS IS NOT `FrozenDocumentPanel` AND THE TWO MUST NOT BE MERGED.**
// That one answers *what did we SEND* and draws the sealed copy or nothing at
// all; it may never render, and a test parses its route's AST to keep it that
// way. This one answers *what is WAITING, on a channel with nothing behind
// it* — a different fact about a different state. One panel serving both would
// be one edit away from showing a re-render where a legal original belongs.
//
// ⚠ **THE SERVER DECIDES WHETHER ANYTHING IS SHOWN. THIS FILE HAS NO GATE.**
// There is no `if (import.meta.env.DEV)`, no prop that forces the content and
// no local guess from `status === "queued"` — a row can be queued on a channel
// that is perfectly connected. `disclosable` and `message_key` come off the
// wire, and the whole condition lives in
// `06-backend/apps/notifications/unsent_preview.py` with its reasoning.
//
// ⚠ **AND EVERY OPEN OF THIS PANEL IS AUDITED SERVER-SIDE**, which is why it
// fetches once per open with `staleTime: 0` and why the control that opens it
// is not rendered on rows it would refuse: a click that shows nothing would
// still be a request, and the honest signal is the control's absence.
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getOutboundUnsent } from "@/api/endpoints";
import type { OutboundUnsentResponse, UnsentFact } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { LoadingSkeleton } from "@/components/StateFrame";
import { RefusalStrip } from "@/components/Surfaces";
import { Kicker, Note } from "@/components/TextBits";
import { Panel, apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";

import { KV_FIGURE, KV_KEY, KV_LIST, KV_ROW } from "./notificationsKit";

export const unsentMessageKey = (messageId: string) =>
  ["notifications", "unsent-message", messageId] as const;

/**
 * ⚠ **THE ENGLISH THIS PANEL RENDERS UNTIL ITS CATALOGUE ENTRIES LAND, AND IT
 * IS A HAND-OVER RATHER THAN A SECOND HOME FOR THE COPY.**
 *
 * These thirteen keys are written in all eleven languages in
 * `scratchpad/lane-NOTIF-keys.json`; the lane that built this screen may not
 * edit `src/i18n/locales/*.json`, so the two halves merge together. Under a key
 * no catalogue defines yet, i18next renders the `defaultValue` — the precedent
 * and the reasoning are `features/identity/SignInHelpPage.tsx`'s, verbatim:
 * *"Under a key nothing defines yet, the `defaultValue` below renders …
 * TODAY."*
 *
 * **A CATALOGUE ENTRY BEATS A `defaultValue`**, so every line here goes inert
 * the moment the keys land and none of them can hold a screen at stale copy.
 * The English below is byte-identical to `en` in that file; if the two ever
 * disagree the catalogue is the one that shows.
 *
 * **WITHOUT THIS THE PANEL WOULD PRINT ITS OWN DOTTED KEYS AT A CLERK** —
 * which is the second defect this lane is fixing, in the panel that fixes the
 * first one.
 */
const UNTIL_THE_CATALOGUE_LANDS: Record<string, string> = {
  "notifications.unsent.title": "Waiting to go out",
  "notifications.unsent.description":
    "Nothing is connected to send this, so what it would say is shown here.",
  "notifications.unsent.noProvider": "Nothing is connected to send this.",
  "notifications.unsent.providerConnected": "This went out through your provider.",
  "notifications.unsent.providerUnknown": "We cannot check your provider.",
  "notifications.unsent.bodyFactsOnly": "No wording is published yet. These are the details.",
  "notifications.unsent.bodyNothing": "Nothing was stored to show.",
};

/** One sentence the SERVER named the key for, drawn with its hand-over English
 *  behind it. The key is data here, so no gate reads this call — the fallback
 *  is for the person looking at the screen, not for a check. */
function served(t: Translator, key: string): string {
  return t(key, { defaultValue: UNTIL_THE_CATALOGUE_LANDS[key] ?? key });
}

/** The letter text as it would have been handed over, in the whitespace it was
 *  written in. `<pre>` for `FrozenDocumentPanel`'s reason: reflowing a message
 *  on its way to a screen changes it. */
const BODY_BOX =
  "m-0 max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-md " +
  "border border-divider bg-surface px-3 py-2 font-mono text-xs leading-relaxed text-text";

/**
 * THE FACTS THE WRITER STAMPED, when no wording has been published.
 *
 * ⚠ **THIS IS THE BRANCH THE ONE-TIME CODE ACTUALLY LANDS IN**, and it is not a
 * degraded version of the one below. No `portal_enrolment_code` template
 * exists, so there IS no body — and rendering one anyway would be this product
 * inventing a message. The six digits are a stamped fact and this draws them as
 * one, at the size a person copying them needs.
 *
 * The labels come off the wire already in a person's words; there is no label
 * table here, because a second one would go stale against the server's.
 */
function StampedFacts(props: { facts: UnsentFact[] }) {
  return (
    <ul className={KV_LIST}>
      {props.facts.map((fact) => (
        <li key={fact.label} className={KV_ROW}>
          <span className={KV_KEY}>{fact.label}</span>
          <span className={`${KV_FIGURE} select-all font-mono`}>{fact.value}</span>
        </li>
      ))}
    </ul>
  );
}

function Content(props: { answer: OutboundUnsentResponse; t: Translator }) {
  const { answer, t } = props;
  if (!answer.disclosable) {
    // A provider is connected, or nobody could tell. Both are correct states
    // and neither is an error, so this is a plain note and not a danger tier.
    return (
      <RefusalStrip role="note" data-testid="unsent-closed">
        {served(t, answer.message_key)}
      </RefusalStrip>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      {/* The server's own sentence for this state, from the key it named — the
          backend and this screen describe one state once (DEF-335's rule). */}
      <Note data-testid="unsent-open">{served(t, answer.message_key)}</Note>
      {answer.subject !== null && answer.subject !== "" ? (
        <p className="m-0 text-sm text-text">
          <Kicker>{t("notifications.frozenDocument.subject")}</Kicker>
          <br />
          <strong>{answer.subject}</strong>
        </p>
      ) : null}
      {answer.body !== null && answer.body !== "" ? (
        <pre className={BODY_BOX} data-testid="unsent-body">
          {answer.body}
        </pre>
      ) : null}
      {answer.facts.length > 0 ? (
        <div data-testid="unsent-facts">
          <StampedFacts facts={answer.facts} />
        </div>
      ) : null}
      {/* WHY there is a fact list rather than a letter, or nothing at all. One
          sentence, from the server, and only when it has something to add. */}
      {answer.body_state_key !== null && answer.body === null ? (
        <Note>{served(t, answer.body_state_key)}</Note>
      ) : null}
    </div>
  );
}

/**
 * The panel a clerk opens from a queue row.
 *
 * `client` is PASSED at the call site and never left to the default — the whole
 * DEF-007..010 class is a component with an optional prop nothing supplies
 * (hard-won law 2).
 */
export function UnsentMessagePanel(props: {
  messageId: string;
  client?: ApiClient;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;

  const answer = useQuery({
    queryKey: unsentMessageKey(props.messageId),
    // Never cached: the gate can close between two looks — somebody connects a
    // provider on the next tab — and a cached body would outlive the condition
    // that made it safe to show. Every open is also its own audit row.
    queryFn: () => getOutboundUnsent(props.messageId, client),
    staleTime: 0,
    gcTime: 0,
    retry: false,
  });

  return (
    <Panel
      title={t("notifications.unsent.title", {
        defaultValue: UNTIL_THE_CATALOGUE_LANDS["notifications.unsent.title"],
      })}
      hint={t("notifications.unsent.description", {
        defaultValue: UNTIL_THE_CATALOGUE_LANDS["notifications.unsent.description"],
      })}
    >
      <div className="mb-3 flex justify-end">
        <Button variant="secondary" size="sm" onClick={props.onClose}>
          {t("notifications.frozenDocument.close")}
        </Button>
      </div>
      {answer.isPending ? <LoadingSkeleton variant="card" /> : null}
      {answer.error !== null && answer.error !== undefined ? (
        <RefusalStrip role="alert" data-testid="unsent-failed">
          {apiErrorText(answer.error, translate)}
        </RefusalStrip>
      ) : null}
      {answer.data !== undefined ? <Content answer={answer.data} t={translate} /> : null}
    </Panel>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: decision log 2026-09-05 §2 · 06-backend/apps/notifications/unsent_preview.py (the gate and its reasoning) · FrozenDocumentPanel.tsx (the sibling this is deliberately NOT)
// generated: 2026-09-05 by the NOTIF lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — the closed branch was shown drawing the body before `disclosable` was branched on, and the row control was shown offered on a connected channel before it read `disclosable_channels`. Verbatim in the lane report.
// exceptions: (1) NO LOCAL GATE OF ANY KIND — there is no dev flag, no prop and no guess from `status`; the server decides and this file only draws. (2) `select-all` on a fact value is deliberate: the one thing a person does with a six-digit code is copy it.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
