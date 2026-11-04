// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-042 (the job on the phone: everything copied from the
//           template, and nothing on the screen was fetched — it arrived with
//           the job, `WM-33`) · US-WRK-043 (safety blocks the task list — on
//           the phone AND the server, `WM-34`).  Screen: Work-011
// Rules:    BR-WRK-037 (the safety lock; *two of three ticked is locked, not
//           two-thirds unlocked*) · BR-WRK-038 (help rides with the job and
//           opens offline) · BR-WRK-042 (the bundle is fetched at sync, never
//           on tap) · BR-WRK-008 (everything here is the ORDER's copy) ·
//           B14 rule 21 · rule 31 · rule 32 · rule 33 · MQ-017 (PO
//           2026-10-24: a REQUIRED task photo blocks the tick until taken)
// Tests:    src/features/work/mobile/JobPage.test.tsx ·
//           src/features/work/mobile/heldPanes.test.ts
// Impacts:  06-backend/apps/work/mobile.py (#89) · apps/work/checklist.py
//           (the ONE evaluator this renders)
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";

import { capture, capturePhoto } from "./capture";
import { PhotoTooLarge } from "./compressPhoto";
import { HELD_PANES, HELD_PANE_REFUSAL_KEY } from "./heldPanes";
import { startFix } from "./location";
import { acceptJob, loadJob, syncJob, type MobileBundle, type MobileTaskRow } from "./mobileEndpoints";
import { declaredPhotos, markOnSite, onStoreChange, syncMarker, writeJob, type SyncMarker } from "./offlineStore";
import { OfflineMarker } from "./TodayPage";

/**
 * `Work-011` — safety first, then the work.
 *
 * ⚠ **THE TAP READS THE STORE AND MAKES NO REQUEST** (`BR-WRK-042`,
 * `US-WRK-042` TC-1: *"zero network requests during the tap"*). `loadJob` is a
 * store read with no network fallback, deliberately: a read that fell back to
 * the network on a miss would pass every test with a signal and fail the only
 * case that matters, which is a meter pit with none. A job that is not in the
 * store shows a sentence saying to sync — never a spinner that never resolves.
 *
 * ⚠ **THE LOCK RENDERED HERE IS THE SERVER'S, NOT THIS COMPONENT'S**
 * (`BR-WRK-037`). `bundle.safety_lock` comes from `checklist.safety_lock`, the
 * one evaluator, and this greys the task list from `locked`. It does NOT
 * recompute the condition from the safety rows, and a lane that "simplifies" it
 * into `safety.every(r => r.ticked_at)` would create the second opinion the
 * rule exists to prevent — the phone and the office disagreeing about whether a
 * job may proceed.
 *
 * ⚠ **AND THE GREY IS A COURTESY.** The guarantee is the server refusing the
 * tick and the completion (`apps/work/checklist.py`, and
 * `_refuse_unticked_safety` in metering's `submit_field_result`). r10: *"Build
 * both or you have built neither."*
 */
export function JobPage() {
  const { t } = useTranslation();
  const { orderId, tenant } = useParams();
  const [bundle, setBundle] = useState<MobileBundle | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [said, setSaid] = useState<string | null>(null);
  const [declared, setDeclared] = useState<Record<string, string>>({});
  const [marker, setMarker] = useState<SyncMarker>({ offline: false, lastSyncAt: null, jobsToSend: 0 });

  useEffect(() => {
    let live = true;
    // ⚠ BR-WRK-061 — LOCATION STARTS WHEN THE JOB DOES. A precise fix can take
    // three minutes; asked for at the close it would be a guess every time.
    if (orderId) startFix(orderId);
    // `DEF-WRK-4127` — the phone's own clock when the job was first opened; the
    // close pre-fills it as *Arrived* and the technician corrects it there.
    if (orderId) void markOnSite(orderId);
    const reread = async () => {
      const stamp = await syncMarker();
      const photos = orderId ? await declaredPhotos(orderId) : {};
      if (!live) return;
      setMarker(stamp);
      setDeclared(photos);
    };
    void (async () => {
      const found = orderId ? await loadJob(orderId) : null;
      if (!live) return;
      setBundle(found);
      setLoading(false);
      await reread();
    })();
    const off = onStoreChange(() => void reread());
    return () => {
      live = false;
      off();
    };
  }, [orderId]);

  if (loading) return null;
  if (!bundle) {
    // Five words. The job is not on this phone yet; syncing is the fix, and
    // saying so is more use than a spinner (B14 rule 33).
    return <p className="px-4 py-8 text-center text-neutral-600">{t("work.mobile.job.notSynced")}</p>;
  }

  const locked = bundle.safety_lock.locked;
  // CR-168-BRC10 §F — work captured before the technician takes the job is
  // HELD for the office's review (`BR-WRK-059`), so the job is taken first.
  const awaitingAccept = bundle.technician_acceptance?.state === "pending";

  async function accept() {
    if (!orderId || !bundle) return;
    setBusy("accept");
    setSaid(null);
    try {
      const answer = await acceptJob(orderId);
      const next = { ...bundle, technician_acceptance: answer.technician_acceptance };
      await writeJob(orderId, next);
      setBundle(next);
    } catch {
      setSaid(t("work.mobile.job.acceptFailed"));
    } finally {
      setBusy(null);
    }
  }

  /**
   * A safety row or a task, ticked — `DEF-WRK-9636`.
   *
   * ⚠ **THROUGH THE HANDSET'S QUEUE, NEVER `POST …/tick`.** Those two routes
   * are the OFFICE's (`WorkOrdersReadAnyWriteAdminOrClerk`) and answer a field
   * login 403; the phone's door is the sync batch, which applies the SAME
   * `checklist.tick_*` call. The key is the row's own, so a second tap queues
   * nothing new (`BR-WRK-042`).
   *
   * ⚠ **THE LOCK SHOWN AFTERWARDS IS RE-READ FROM THE SERVER** (`syncJob`),
   * never recomputed here — see the component docstring. With no signal the
   * tick waits in the queue and the screen keeps the last lock the server gave,
   * which is the honest reading: nothing has been checked yet.
   */
  async function tick(kind: "safety_tick" | "task_tick", rowId: string) {
    if (!orderId) return;
    setBusy(rowId);
    setSaid(null);
    try {
      const { sent } = await capture({
        orderId,
        kind,
        key: `${kind}-${rowId}`,
        payload: kind === "safety_tick" ? { safety_id: rowId } : { task_id: rowId },
      });
      if (sent === null) {
        // Offline (CR-168 §F): the tick is ON THE PHONE and waiting to send.
        // The row shows ticked now; the LOCK stays the server's last word,
        // which is the honest reading — nothing has been checked yet.
        const current = (await loadJob(orderId)) ?? bundle;
        if (current) {
          const next = markTicked(current, kind, rowId);
          await writeJob(orderId, next);
          setBundle(next);
        }
        return;
      }
      const refused = sent.flatMap((r) => r.items).filter((i) => i.result === "refused" && i.key === `${kind}-${rowId}`);
      if (refused.length > 0) setSaid(t("work.mobile.readings.save_failed"));
      setBundle(await syncJob(orderId));
    } catch {
      setSaid(t("work.mobile.readings.save_failed"));
    } finally {
      setBusy(null);
    }
  }

  /**
   * A photograph taken FOR a task — `DEF-WRK-9619`.
   *
   * ⚠ **`taskId` IS THE WHOLE FIX.** The Photographs pane sends a photograph
   * that belongs to the JOB, and `close_readiness` counts a task's photograph
   * only through `work_order_tasks.photo_attachment_id`, which #77 writes when
   * — and only when — the upload names the task. So a technician took two
   * pictures and the close went on saying *2 photographs still needed*.
   *
   * The row the server returns is written into the STORED bundle, the
   * `mergeReadingIntoJob` posture (`DEF-WRK-4113`): opening the job reads the
   * store, and a store that still said *photo required* would contradict the
   * close pane's live count.
   */
  async function photograph(task: MobileTaskRow, file: File) {
    if (!orderId || !bundle) return;
    setBusy(task.id);
    setSaid(null);
    try {
      // CR-168 §F — the photo's DATA joins the outbox (its link is made when
      // the server saves it) and its BYTES upload in the background. With no
      // signal both simply wait on the phone; *Photo taken* is true at once.
      await capturePhoto({ orderId, file, taskId: task.id });
    } catch (error) {
      setSaid(
        error instanceof PhotoTooLarge
          ? t("work.mobile.readings.photo_too_large")
          : t("work.mobile.readings.photo_failed"),
      );
    } finally {
      setBusy(null);
    }
  }
  // ⚠ SPELLED WITHOUT THE TENANT, like every other route in this module
  // (`DEF-WRK-4051`, 2026-09-05): `App.tsx` mounts the field app under a
  // `:tenant` route, so a link that carried the tenant again came out
  // `:tenant/:tenant/...`, matched nothing, and fell through to "not built
  // yet" — with `tsc`, 44 tests, the build and G13 all green over it. Here the
  // tenant IS needed because this is an absolute href built from `useParams`,
  // which is the same shape `MobileApp`'s bottom bar uses.
  const base = `/${tenant ?? ""}/work/mobile/jobs/${orderId}`;

  return (
    <div className="pb-4">
      <header className="px-4 pt-4 pb-3 border-b border-divider bg-surface">
        {/* B14 rule 31 — the order number, never the uuid. */}
        <h1 className="text-lead font-semibold">{bundle.order_no}</h1>
        <OfflineMarker marker={marker} />
        {bundle.customer ? (
          <p className="text-sm text-neutral-600">
            {bundle.customer.name}
            {bundle.customer.phone ? (
              <>
                {" · "}
                {/* A tap-to-call link — `US-WRK-042` TC-5. */}
                <a className="text-accent" href={`tel:${bundle.customer.phone}`}>
                  {bundle.customer.phone}
                </a>
              </>
            ) : null}
          </p>
        ) : null}
      </header>

      {awaitingAccept ? (
        <section className="px-4 py-3 border-b border-divider" data-testid="accept-job">
          <p className="text-sm text-neutral-700">{t("work.mobile.job.acceptFirst")}</p>
          <button
            type="button"
            className="mt-2 w-full rounded-md bg-accent px-4 py-3 text-btn font-heading font-extrabold text-bg disabled:opacity-45"
            disabled={busy !== null}
            onClick={() => void accept()}
          >
            {t("work.mobile.job.accept")}
          </button>
        </section>
      ) : null}

      {/* ── SAFETY, FIRST ON THE SCREEN — `WM-34` ───────────────────────── */}
      <section className="px-4 py-3 border-b border-divider">
        <h2 className="text-xs font-semibold tracking-wide text-neutral-700 uppercase">
          {locked
            ? t("work.mobile.safety.locked", {
                ticked: bundle.safety_lock.ticked,
                total: bundle.safety_lock.mandatory_total,
              })
            : t("work.mobile.safety.done")}
        </h2>
        <ul className="mt-2 space-y-2">
          {bundle.safety.map((row) => (
            <li key={row.id} className="text-sm" data-safety-id={row.id}>
              {/* `DEF-WRK-9636` — a real control, not a drawn box. A ticked
                  row stays ticked: the server records the tick and never an
                  untick. */}
              <label className="flex min-h-11 items-start gap-2">
                <input
                  type="checkbox"
                  className="mt-1 size-5"
                  checked={Boolean(row.ticked_at)}
                  disabled={Boolean(row.ticked_at) || busy !== null}
                  onChange={() => void tick("safety_tick", row.id)}
                />
                <span>{row.text}</span>
              </label>
            </li>
          ))}
        </ul>
      </section>

      {/* ── THE TASKS, LOCKED UNTIL EVERY MANDATORY SAFETY ROW IS TICKED ── */}
      <section className="px-4 py-3 border-b border-divider" aria-busy={locked}>
        <h2 className="text-xs font-semibold tracking-wide text-neutral-700 uppercase">
          {t("work.mobile.tasks.heading", {
            count: bundle.tasks_total,
            minutes: bundle.tasks_est_minutes,
          })}
        </h2>
        <ul
          className={["mt-2 space-y-2", locked ? "opacity-50" : ""].join(" ")}
          data-testid="task-list"
          data-locked={locked ? "true" : "false"}
        >
          {bundle.tasks.map((task) => {
            const photoMissing = task.photo_required && !task.photo_attachment_id && !declared[task.id];
            // MQ-017 (PO 2026-10-24): a REQUIRED photo blocks the tick until it
            // is taken, and the row says so; a task already ticked keeps its
            // plain flag. The server still accepts a tick and records the gap.
            const blocked = photoMissing && !task.ticked_at;
            return (
              <li key={task.id} className="text-sm" data-task-id={task.id}>
                <div className="flex items-start justify-between gap-2">
                  <label className="flex min-h-11 items-start gap-2">
                    <input
                      type="checkbox"
                      className="mt-1 size-5"
                      checked={Boolean(task.ticked_at)}
                      disabled={locked || Boolean(task.ticked_at) || busy !== null || blocked}
                      aria-describedby={blocked ? `task-photo-${task.id}` : undefined}
                      onChange={() => {
                        if (!blocked) void tick("task_tick", task.id);
                      }}
                    />
                    <span>{task.title}</span>
                  </label>
                  {/* `DEF-WRK-9619` — the camera is ON the row that asks for the
                      photograph, so the picture is sent FOR that task. */}
                  {task.photo_required ? (
                    <label className="shrink-0 py-1 text-sm text-accent" data-task-camera={task.id}>
                      {t("work.mobile.readings.camera")}
                      <input
                        type="file"
                        accept="image/*"
                        capture="environment"
                        className="sr-only"
                        disabled={locked || busy !== null}
                        aria-label={`${t("work.mobile.readings.camera")} · ${task.title}`}
                        onChange={(event) => {
                          const file = event.target.files?.[0];
                          if (file) void photograph(task, file);
                        }}
                      />
                    </label>
                  ) : null}
                </div>
                {photoMissing ? (
                  <p id={`task-photo-${task.id}`} className="ml-7 text-sm text-warning-700" data-flag="missing-photo">
                    {blocked ? t("work.mobile.tasks.photoToFinish", { count: 1 }) : t("work.mobile.tasks.photoRequired")}
                  </p>
                ) : null}
                {task.photo_attachment_id || declared[task.id] ? (
                  <p className="ml-7 text-sm text-neutral-600" data-flag="photo-taken">
                    {t("work.mobile.readings.photo_taken")}
                  </p>
                ) : null}
              </li>
            );
          })}
        </ul>
        {said !== null ? (
          <p className="mt-2 text-sm text-danger-700" role="alert">
            {said}
          </p>
        ) : null}
        {locked ? (
          // `BR-WRK-037` names the row; B14 rule 33 caps the sentence. So the
          // sentence is short and the row is printed BESIDE it — the same shape
          // the server's refusal uses (`params.safety`).
          <p className="mt-2 text-sm text-warning-700">
            {t("work.mobile.tasks.finishSafety")}
            {bundle.safety_lock.first_outstanding ? ` — ${bundle.safety_lock.first_outstanding}` : ""}
          </p>
        ) : null}
      </section>

      {/* ── HELP, AND IT OPENS WITH NO SIGNAL — `BR-WRK-038` ─────────────── */}
      <section className="px-4 py-3 border-b border-divider">
        <h2 className="text-xs font-semibold tracking-wide text-neutral-700 uppercase">
          {t("work.mobile.help.heading", { count: bundle.help.length })}
        </h2>
        <ul className="mt-2 space-y-2">
          {bundle.help.map((row) => (
            <li key={row.id} className="text-sm">
              {row.kind === "phone" ? (
                <a className="text-accent" href={`tel:${row.ref ?? ""}`}>
                  {row.label}
                </a>
              ) : row.kind === "link" && row.ref ? (
                // CR-168 P3.25 — a video or a web page OPENS, and says before
                // the tap that it needs a signal (a document is carried; a
                // link is not). Opened outside the app so the job stays put.
                <a className="text-accent" href={row.ref} target="_blank" rel="noreferrer">
                  {row.label}
                  <span className="ml-2 text-xs text-neutral-700">{t("work.mobile.help.needsSignal")}</span>
                </a>
              ) : row.kind === "document" && row.url ? (
                <a className="text-accent" href={row.url}>
                  {row.label}
                </a>
              ) : (
                // A document with no link is LISTED, never dropped
                // (`US-WRK-042` TC-4): a missing SOP a technician can see is
                // missing is a phone call; one that quietly is not on the list
                // is a technician improvising in a basement.
                <span>{row.label}</span>
              )}
            </li>
          ))}
        </ul>
      </section>

      {/*
        ── CR-070 wave K — THE THREE PANES THAT WERE HELD ARE NOW DOORS ──────
        These were `<span>`s carrying "Arrives in the next release." until
        2026-09-05. They are `<Link>`s in the same commit that mounted their
        routes and deleted their rows from `HELD_PANES` — hard-won law 2's
        mirror, which cost the customer portal two working doors out of eight
        by treating "land the screen" and "release the control" as two acts.
      */}
      <section className="px-4 py-3 border-b border-divider">
        <ul className="space-y-2">
          <PaneLink to={`${base}/readings`} label={t("work.mobile.pane.readings")} id="readings" />
          <PaneLink to={`${base}/photos`} label={t("work.mobile.pane.photos")} id="photos" />
          <PaneLink to={`${base}/signature`} label={t("work.mobile.pane.signature")} id="signature" />
          {/* ── CR-070 wave L — THE CLOSE, AND IT WAS THE LAST HELD PANE ──
              A `<span>` reading "Arrives in the next release." until 2026-09-05.
              It is a `<Link>` in the same commit that mounted
              `jobs/:orderId/close` and deleted the row from `HELD_PANES`.
              `heldPanes.test.ts` went red on the route and named this file. */}
          <PaneLink to={`${base}/close`} label={t("work.mobile.pane.close")} id="close" />
        </ul>
      </section>

      <HeldPanes />
    </div>
  );
}

/**
 * The panes not yet built, shown as REFUSED rather than hidden.
 *
 * ⚠ **`HELD_PANES` IS EMPTY SINCE CR-070 WAVE L, SO THIS RENDERS NOTHING, AND
 * IT IS KEPT ANYWAY.** It is the machinery rather than the data: the next lane
 * that has to hold a pane back gets the refusal rendering AND the expiry test
 * for free, instead of writing them from scratch — and writing them from
 * scratch is precisely what nobody does (`DEF-CWP-3925`: eight doors on one
 * page, two of them working, five refusing over screens that had shipped days
 * earlier, with every check green).
 *
 * The rule it embodies: **a held pane is SHOWN, because a technician needs to
 * know the job is not closeable here yet.** Hiding one leaves somebody hunting
 * for a Close button on a screen that has none.
 */
/**
 * A pane that has landed — a real link, with the address it opens.
 *
 * ⚠ **A `<Link>` AND NOT A `<span>`, WHICH IS THE ENTIRE DIFFERENCE FROM
 * `HeldPanes` BELOW.** `DEF-CWP-3925` is what a held control looks like after
 * its screen ships: it still renders, still reads sensibly, and goes nowhere.
 */
function PaneLink({ to, label, id }: { to: string; label: string; id: string }) {
  return (
    <li data-pane={id}>
      <Link className="block py-2 text-sm text-accent" to={to}>
        {label}
      </Link>
    </li>
  );
}

function HeldPanes() {
  const { t } = useTranslation();
  return (
    <section className="px-4 py-3">
      <ul className="space-y-2">
        {HELD_PANES.map((pane) => (
          <li key={pane.id} className="text-sm text-neutral-600" data-held-pane={pane.id}>
            {t(`work.mobile.pane.${pane.id}`)} — {t(HELD_PANE_REFUSAL_KEY)}
          </li>
        ))}
      </ul>
    </section>
  );
}

/**
 * A tick captured with NO SIGNAL, shown ticked on the row that was tapped.
 *
 * ⚠ **OFFLINE, THE LOCK IS PROVISIONAL — AND THAT DOES NOT MAKE IT A SECOND
 * OPINION** (CR-168-BRC10 §F, lane FIELD-2). The component docstring forbids
 * recomputing `BR-WRK-037`'s lock on the phone, and online this file still
 * never does: the lock is re-read from the server after every tick. But a
 * phone in a basement cannot ask, and the PO ruled that the technician app
 * WORKS OFFLINE — a task list that stayed grey after every safety row was
 * ticked would make offline work impossible. So, offline only, the bundle's
 * own `safety_lock` is moved by the rows ticked HERE, and the server's
 * guarantee is untouched: the items go in capture order, and a task tick that
 * reached the server before its safety tick would be REFUSED and kept on the
 * phone (`BIZ-LOCKED`, the one refusal that is not acknowledged).
 */
function markTicked(bundle: MobileBundle, kind: "safety_tick" | "task_tick", rowId: string): MobileBundle {
  const at = new Date().toISOString();
  if (kind === "task_tick") {
    return { ...bundle, tasks: bundle.tasks.map((r) => (r.id === rowId ? { ...r, ticked_at: at } : r)) };
  }
  const safety = bundle.safety.map((r) => (r.id === rowId ? { ...r, ticked_at: at } : r));
  const outstanding = safety.filter((r) => r.is_mandatory && !r.ticked_at);
  return {
    ...bundle,
    safety,
    safety_lock: {
      ...bundle.safety_lock,
      locked: outstanding.length > 0,
      remaining: outstanding.length,
      ticked: safety.filter((r) => r.ticked_at).length,
      first_outstanding: outstanding[0]?.text ?? null,
    },
  };
}
