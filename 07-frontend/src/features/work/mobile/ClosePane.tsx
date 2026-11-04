// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-045 (the technician closes the job from the phone) TC-1..TC-7
//           · US-WRK-044 (the queue that never loses a day and never adds it
//           twice) TC-2/TC-5/TC-7.  Screen: Work-012 (`WS-12`)
// Rules:    BR-WRK-041 (the close is `submit_field_result`; it activates
//           nothing; the offline label) · BR-WRK-040 (a missing REQUIRED
//           photograph stops the close) · BR-WRK-046 (a signature or its
//           refusal) · BR-WRK-042 (a per-item idempotency key) · BR-MET-110 ·
//           B14 rule 11 (the consequence before the commit) · rule 21
//           (Tailwind only; this file joins route-b-migrated.txt in the commit
//           that creates it) · rule 31 · rule 32 · rule 33
// Tests:    src/features/work/mobile/ClosePane.dom.test.tsx
// Impacts:  offlineStore.ts (the queue) · mobileEndpoints.ts (#90) ·
//           heldPanes.ts (this file RELEASES the `close` hold — same commit,
//           hard-won law 2's mirror) · routePaths.ts · MobileApp.tsx
// ───────────────────────────────────────────────────────
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";

import { capture } from "./capture";
import { loadCloseReadiness, type CloseReadiness } from "./evidenceEndpoints";
import { bestFix, startFix, type LocationFix } from "./location";
import { loadJob, loadJobMoney } from "./mobileEndpoints";
import { onSiteSince, syncMarker } from "./offlineStore";
import { PAID_OUTCOME, paidSnapshot, paymentCheckStep, type PaymentSeen } from "./paidClose";

/**
 * `Work-012`'s close — *Close job*, or *Close job · send when back online*.
 *
 * ⚠ **THE BUTTON SAYS WHAT WILL HAPPEN, AND THAT IS THE WHOLE OF `WS-12`'s
 * OFFLINE LABEL** (`BR-WRK-041`). With a signal the job goes now; without one
 * it queues and the marker says so. A single label reading *Close job* over a
 * phone with no signal is a promise the app cannot keep, and the technician
 * finds out at 18:00 when the office rings.
 *
 * ⚠ **CLOSING DOES NOT SWITCH THE SUPPLY ON, AND THE SCREEN SAYS SO BEFORE THE
 * COMMIT** (`BR-MET-110`, B14 rule 11). `WS-12`'s own last line is *"The office
 * reviews this and accepts it."* The server agrees independently: the close
 * inside a sync batch is `submit_field_result` and nothing more — `accepted_by`
 * stays NULL, no service state moves and no meter read is written.
 *
 * ⚠ **FOUR OUTCOMES, NOT FIVE.** *Passed · Partly done · Failed · Waiting on
 * someone*. The fifth token, `cancelled`, is the DISPATCHER's and is not
 * offered here: a technician standing at a job cannot cancel it, and a picker
 * that offered the word would make that look like a decision they may take.
 *
 * ⚠ **AND A SIXTH, *NOT DONE — PAYMENT RECEIVED*, ONLY WHEN THE STEP WAS
 * STOPPED** (FB-013, PO rulings 2026-10-28; `DEF-WRK-10644`). Offered, and
 * chosen, when the next step to do declares a payment check and a FRESH read
 * (that step's own bar) shows the balance cleared — the phone's FF-27 stop.
 * The remark is written and editable; what was seen travels as
 * `field_data.money_seen`, without which the server refuses the paid close.
 *
 * ⚠ **THE VERDICT ON WHETHER IT MAY CLOSE IS THE SERVER'S** (`close_readiness`),
 * and when the phone is offline there is no verdict — which is shown as
 * *unknown*, never as *you may close*. `BR-WRK-040`'s missing-photograph refusal
 * is the office's rule and the phone does not get a second opinion on it; what
 * the phone can do offline is queue the close and let the server refuse it, at
 * which point the item comes back REFUSED and stays in the queue.
 *
 * ⚠ **THE KEY IS MINTED AT CAPTURE, HERE** (`BR-WRK-042`). Tapping *Close job*
 * twice queues ONE item, because `enqueue` writes to the same key — which is
 * `US-WRK-045` TC-5 on the handset rather than after a round trip the
 * technician does not have.
 */

/** `work_orders.outcome`'s five tokens, minus the dispatcher's — the SERVER's
 *  spellings (`connection_models.WORK_ORDER_OUTCOMES`). `DEF-WRK-10798`: this
 *  list read `partly_done`, which the server refuses, so every *Partly done*
 *  close from this screen came back refused. The native app sends
 *  `partially_done` (`field-app/src/screens/closing/CloseScreen.tsx`). */
export const PHONE_OUTCOMES = [
  "passed",
  "partially_done",
  "failed",
  "waiting_on_someone_else",
] as const;

export type PhoneOutcome = (typeof PHONE_OUTCOMES)[number];

/** The catalogue's word for a token where the two differ: *Partly done* stays
 *  under its existing key in all eleven catalogues; only the wire token moved. */
const OUTCOME_WORD: Partial<Record<string, string>> = { partially_done: "partly_done" };

/** What this close can send: the four, or the paid one when it is offered. */
export type CloseOutcome = PhoneOutcome | typeof PAID_OUTCOME;

/** `US-WRK-045` TC-7 — *Waiting on someone* needs a reason; the others do not. */
export function reasonRequired(outcome: CloseOutcome | null): boolean {
  return outcome === "waiting_on_someone_else";
}

/** An instant as a `datetime-local` value in the PHONE's own zone — the clock
 *  the technician reads. `2026-03-15T09:00`. */
export function localInputValue(at: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${at.getFullYear()}-${pad(at.getMonth() + 1)}-${pad(at.getDate())}T${pad(at.getHours())}:${pad(at.getMinutes())}`;
}

/**
 * `DEF-WRK-4127` — the two times the labour is priced from (PO 2026-10-05:
 * *"allow technicain to fill in time"*). Null when they may be sent: both
 * read, *Finished* after *Arrived*, neither ahead of the phone's clock. The
 * server asks the same three questions and holds a close that fails them.
 */
export function labourTimeProblem(arrived: string, finished: string, now: Date = new Date()): string | null {
  const from = new Date(arrived);
  const to = new Date(finished);
  if (arrived === "" || finished === "" || Number.isNaN(from.getTime()) || Number.isNaN(to.getTime())) {
    return "work.mobile.close.timesRequired";
  }
  if (to.getTime() <= from.getTime() || to.getTime() > now.getTime() + 60_000) {
    return "work.mobile.close.timesOutOfOrder";
  }
  return null;
}

export function ClosePane() {
  const { t, i18n } = useTranslation();
  const { orderId } = useParams();
  const navigate = useNavigate();
  const [outcome, setOutcome] = useState<CloseOutcome | null>(null);
  const [reason, setReason] = useState("");
  // DEF-WRK-10644 — the fresh cleared read that stopped the step, and the
  // paid close's remark (null = the written default, still editable).
  const [paidSeen, setPaidSeen] = useState<PaymentSeen | null>(null);
  const [remark, setRemark] = useState<string | null>(null);
  const [ready, setReady] = useState<CloseReadiness | null>(null);
  const [orderNo, setOrderNo] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [busy, setBusy] = useState(false);
  const [said, setSaid] = useState<string | null>(null);
  const [fix, setFix] = useState<LocationFix | null>(null);
  // `DEF-WRK-4127` — pre-filled from the phone's own clock: *Arrived* is when
  // this job was first opened here, *Finished* is now. Both are editable.
  const [arrived, setArrived] = useState("");
  const [finished, setFinished] = useState(() => localInputValue(new Date()));

  const refresh = useCallback(async () => {
    if (!orderId) return;
    // BR-WRK-061 — keep acquiring (a close opened straight from a link still
    // gets a fix), and show the one the close will carry.
    startFix(orderId);
    setFix(await bestFix(orderId));
    const bundle = await loadJob(orderId);
    setOrderNo(bundle?.order_no ?? null);
    // DEF-WRK-10644 — only a step that declares a payment check is read for
    // money (R18); no signal or a stale/owing figure offers nothing new.
    const step = paymentCheckStep(bundle?.tasks ?? []);
    if (step !== null) {
      try {
        const seen = paidSnapshot(step, await loadJobMoney(orderId), new Date());
        setPaidSeen(seen);
        if (seen !== null) setOutcome((current) => current ?? PAID_OUTCOME);
      } catch {
        setPaidSeen(null);
      }
    }
    const since = await onSiteSince(orderId);
    setArrived((current) => (current !== "" ? current : localInputValue(since ? new Date(since) : new Date())));
    setOffline((await syncMarker()).offline);
    try {
      setReady(await loadCloseReadiness(orderId));
    } catch {
      // Offline. No verdict is UNKNOWN, never "you may close" — see the
      // component docstring, and `ReadingsPane` takes the same position.
      setReady(null);
    }
  }, [orderId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // The fix improves while the technician stands there; re-read it so the
  // line under the outcome says what the close will actually carry.
  useEffect(() => {
    if (!orderId) return;
    const timer = setInterval(() => void bestFix(orderId).then(setFix), 3000);
    return () => clearInterval(timer);
  }, [orderId]);

  const paidRemark = remark ?? t("work.mobile.close.paidRemark");

  async function close() {
    if (!orderId || outcome === null) return;
    if (reasonRequired(outcome) && reason.trim() === "") {
      setSaid(t("work.mobile.close.reason_required"));
      return;
    }
    const timeProblem = labourTimeProblem(arrived, finished);
    if (timeProblem !== null) {
      setSaid(t(timeProblem));
      return;
    }
    setBusy(true);
    setSaid(null);
    try {
      // ⚠ **QUEUED FIRST, ALWAYS — ONLINE OR OFF.** The close is written to the
      // handset's own store before anything is attempted over the network, so a
      // request that dies halfway leaves the work recorded rather than lost.
      // With a signal the queue is then flushed immediately; without one it
      // waits. One path, two speeds — a phone that posted directly when online
      // and queued when offline would have two code paths and only one of them
      // would ever be tested.
      const capturedAt = new Date().toISOString();
      // Minted AT CAPTURE. A second tap writes the same key and queues
      // nothing new (`US-WRK-045` TC-5). The capture token and the best fix
      // are stamped by `capture` (CR-168-BRC10 §F, `BR-WRK-059`/`061`).
      const key = `close-${orderId}-${capturedAt.slice(0, 16)}`;
      const { sent } = await capture({
        orderId,
        kind: "close",
        key,
        payload: {
          outcome,
          field_data:
            outcome === PAID_OUTCOME && paidSeen !== null
              ? // DEF-WRK-10644 — what was SEEN, and the remark the office
                // reads as the reason (the phone's `closeJob`, field for field).
                { money_seen: paidSeen, ...(paidRemark.trim() === "" ? {} : { reason: paidRemark.trim() }) }
              : reason.trim() === ""
                ? {}
                : { note: reason.trim() },
          // `DEF-WRK-4127` — the technician's confirmed times, as instants.
          arrived_at: new Date(arrived).toISOString(),
          finished_at: new Date(finished).toISOString(),
        },
        send: !offline,
      });
      if (sent !== null) {
        const refused = sent.flatMap((r) => r.items).filter((i) => i.result === "refused" && i.key === key);
        if (refused.length > 0) {
          // The SERVER's own sentence — the safety row that is outstanding, the
          // photograph that was asked for and not taken. The phone composes no
          // wording of its own (`BR-SHL-025`), and the item stays queued.
          // The server's sentence in THIS phone's language when its key is in
          // the catalogue — `detail.message` is the exception's own text, which
          // no catalogue translates (`DEF-WRK-9625` added a refusal a
          // technician meets); that text is the fallback, ours the last resort.
          const key = refused[0].detail?.message_key;
          setSaid(
            key && i18n.exists(key)
              ? t(key)
              : (refused[0].detail?.message ?? t("work.mobile.close.refused")),
          );
          return;
        }
      }
      navigate("..", { relative: "path" });
    } catch {
      // A failed send is NOT an error here, it is *offline* — the close is
      // already in the queue and the marker will say so. `US-WRK-041` TC-3's
      // reasoning, one screen along.
      navigate("..", { relative: "path" });
    } finally {
      setBusy(false);
    }
  }

  const blocking = ready?.blocking ?? [];
  // `BR-WRK-040` SUPERSEDED 2026-10-21 (PO: *"warn"*) — the server serves
  // missing required photographs here and no longer in `blocking`. They WARN
  // and never stop the close; the server records the gap on the close for the
  // office. An older server still sends them in `blocking`, which still stops.
  const missingPhotos = ready?.missing_photos ?? [];
  const canCommit = outcome !== null && !busy && blocking.length === 0;
  const offered: CloseOutcome[] = paidSeen === null ? [...PHONE_OUTCOMES] : [...PHONE_OUTCOMES, PAID_OUTCOME];

  return (
    // ⚠ `WRK-23`, the badge `screenIds.ts` allocates — the close is the FOURTH
    // pane of `Work-012`, not a screen of its own. A first draft stamped
    // `WRK-12` here and the two would have disagreed, which is the whole
    // thing that file exists to stop.
    <section className="px-4 py-3" data-screen="WRK-23">
      {/* B14 rule 31 — the visible reference is `WO-4822`, never the uuid. */}
      <h2 className="text-base font-semibold text-text">
        {orderNo === null ? t("work.mobile.close.title") : t("work.mobile.close.titleFor", { order: orderNo })}
      </h2>

      {/* DEF-WRK-10644 — the phone's FF-27 stop, as a fact (B14 rule 33). */}
      {paidSeen !== null && (
        <p className="mt-3 text-sm font-semibold text-danger-700" data-testid="close-balance-cleared">
          {t("work.mobile.close.balanceCleared")}
        </p>
      )}

      <fieldset className="mt-3 border-0 p-0 m-0">
        <legend className="text-sm text-neutral-600">{t("work.mobile.close.outcome")}</legend>
        <div className="mt-2 flex flex-col gap-2">
          {offered.map((token) => (
            <label key={token} className="flex items-center gap-2 text-md text-text">
              <input
                type="radio"
                name="outcome"
                value={token}
                checked={outcome === token}
                onChange={() => setOutcome(token)}
              />
              {t(`work.mobile.close.outcomes.${OUTCOME_WORD[token] ?? token}`)}
            </label>
          ))}
        </div>
      </fieldset>

      {outcome === PAID_OUTCOME && (
        <label className="mt-3 block text-sm text-neutral-600">
          {t("work.mobile.close.remark")}
          <textarea
            className="mt-1 w-full rounded-md border border-field-border p-2 text-md text-text"
            rows={2}
            value={paidRemark}
            onChange={(event) => setRemark(event.target.value)}
          />
        </label>
      )}

      {reasonRequired(outcome) && (
        <label className="mt-3 block text-sm text-neutral-600">
          {t("work.mobile.close.reason")}
          <textarea
            className="mt-1 w-full rounded-md border border-field-border p-2 text-md text-text"
            rows={3}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </label>
      )}

      {/* `DEF-WRK-4127` — when they got there and when they finished, by the
          phone's clock and corrected here. The labour is priced from these. */}
      <div className="mt-3 grid grid-cols-2 gap-3" data-testid="close-times">
        <label className="block text-sm text-neutral-600">
          {t("work.mobile.close.arrived")}
          <input
            type="datetime-local"
            className="mt-1 w-full rounded-md border border-field-border p-2 text-md text-text"
            value={arrived}
            onChange={(event) => setArrived(event.target.value)}
          />
        </label>
        <label className="block text-sm text-neutral-600">
          {t("work.mobile.close.finished")}
          <input
            type="datetime-local"
            className="mt-1 w-full rounded-md border border-field-border p-2 text-md text-text"
            value={finished}
            onChange={(event) => setFinished(event.target.value)}
          />
        </label>
      </div>

      {/* ⚠ `BR-WRK-040` — the office's rule, shown as the office states it, and
          it STOPS the close. An out-of-range value is a different thing and does
          not appear here at all (`BR-WRK-039`, and `ReadingsPane` draws it). */}
      {blocking.length > 0 && (
        <p className="mt-3 text-sm text-warning-700" data-testid="close-blocked">
          {t("work.mobile.close.blocked", { count: blocking.length })}
        </p>
      )}
      {/* The same sentence as a WARNING — *2 photographs still needed.* — over
          a Close that stays enabled (`BR-WRK-040` as superseded 2026-10-21). */}
      {/* DEF-WRK-10644 — on the paid close the photo is optional (the phone's
          FF-34), so the warning is not drawn over it. */}
      {blocking.length === 0 && missingPhotos.length > 0 && outcome !== PAID_OUTCOME && (
        <p className="mt-3 text-sm text-warning-700" data-testid="close-photos-missing">
          {t("work.mobile.close.blocked", { count: missingPhotos.length })}
        </p>
      )}

      {/* CR-168-BRC10 §F, `BR-WRK-061` — the fix this close will carry, as a
          FACT (B14 rule 33: six words at most). Never a refusal: a close is
          never stopped for location (the PO's (a)). */}
      <p className="mt-3 text-sm text-neutral-600" data-testid="close-fix">
        {fix
          ? t("work.mobile.close.fix", { metres: Math.round(fix.accuracy_m) })
          : t("work.mobile.close.noFix")}
      </p>

      {/* B14 rule 11 — the consequence precedes the irreversible commit, and
          rule 32 gives it ONE sentence. */}
      <p className="mt-3 text-sm text-neutral-600" data-consequence="mobile-close">
        {t("work.mobile.close.consequence")}
      </p>

      {/* ⚠ `text-danger-700`, NOT `text-danger`. `--text-*: initial` deleted
          Tailwind's own type scale, so a bare `text-danger` compiles to NO RULE
          and renders as nothing at all — while `tsc`, eslint and every
          `toContain("text-danger")` assertion pass, because the class IS in the
          DOM (`DEF-CWP-3774`, `DEF-974`). G31 caught this one, and it is the
          only check in the repository that could. */}
      {said !== null && (
        <p className="mt-2 text-sm text-danger-700" data-testid="close-refusal">
          {said}
        </p>
      )}

      <button
        type="button"
        className="mt-4 w-full rounded-md bg-accent px-4 py-3 text-btn font-heading font-extrabold text-bg disabled:opacity-45 disabled:cursor-not-allowed"
        disabled={!canCommit}
        onClick={() => void close()}
      >
        {/* ⚠ THE LABEL SAYS WHAT WILL HAPPEN — see the component docstring. */}
        {offline ? t("work.mobile.close.commitOffline") : t("work.mobile.close.commit")}
      </button>
    </section>
  );
}
