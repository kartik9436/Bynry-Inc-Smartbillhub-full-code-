// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-041 (EP-WRK-08) — today's jobs: a time-ordered day, an
//           honest offline state, and the dog and the gate code carried to the
//           point of work (`WM-32`).  Screen: Work-010
// Rules:    BR-WRK-035 (ordered by appointment time; priority is a PILL and
//           does not reorder) · BR-WRK-036 (the offline marker is always
//           visible, with the time the phone last reached the server) ·
//           BR-WRK-008 (access notes and the gate code are the ORDER's copy) ·
//           B14 rule 21 (Tailwind only; on route-b-migrated.txt) · rule 31 (no
//           database id is a visible value) · rule 32 (one sentence per
//           section) · rule 33 (a refusal caps at five or six words)
// Tests:    src/features/work/mobile/TodayPage.test.tsx
// Impacts:  06-backend/apps/work/mobile.py (serves this, #88)
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";

import { loadDay, loadJob, syncChanges, syncJob, type MobileDay, type MobileJobCard } from "./mobileEndpoints";
import { onStoreChange, syncMarker, type SyncMarker } from "./offlineStore";

/**
 * `Work-010` — *4 jobs · 2 done* for the day, in appointment order.
 *
 * ⚠ **THIS COMPONENT DOES NOT SORT, AND THAT IS DELIBERATE** (`BR-WRK-035`).
 * The server orders by `window_start`, then `due_at`, then the order number,
 * and this renders `day.jobs` in the order it arrived. A `.sort()` here would
 * be a second opinion about a RULE — and the plausible one to write is by
 * priority, which is exactly what the rule forbids: *"an Urgent job across town
 * does not jump the one they are standing outside."* `US-WRK-041` TC-2 asserts
 * that moving a job to Urgent changes the pill and NOT the position.
 */
export function TodayPage({ days = 1 }: { days?: number }) {
  const { t } = useTranslation();
  const { tenant } = useParams();
  const [day, setDay] = useState<MobileDay | null>(null);
  const [marker, setMarker] = useState<SyncMarker>({ offline: false, lastSyncAt: null, jobsToSend: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let live = true;
    void (async () => {
      const { day: loaded, fromStore } = await loadDay({ days });
      const stamp = await syncMarker();
      if (!live) return;
      setDay(loaded);
      setMarker(stamp);
      setLoading(false);
      // ── THE BUNDLES — `BR-WRK-042`, and `DEF-WRK-4061` is why it is here ──
      //
      // *"The bundle is fetched AT SYNC, never on tap."* `JobPage` implements
      // the second half exactly: `loadJob` reads the store with NO network
      // fallback, because a read that fell back would pass every test with a
      // signal and fail the only case that matters. **Nothing performed the
      // first half.** `syncJob` had no caller anywhere in the tree, so the
      // store never held a bundle and tapping ANY job showed *Not on this
      // phone yet.* — the field app's main screen, unreachable in normal use,
      // with `tsc`, eslint, G13 and every unit test green over it, because the
      // job screen's tests MOCK the store. Found by pointing a browser at it
      // (hard-won law 6), and it is hard-won law 2 in the wave that quotes it.
      //
      // ⚠ **PER JOB, AND A FAILURE ON ONE MUST NOT COST THE OTHERS.** A single
      // unreachable bundle — a help document whose link would not mint, a
      // network that dropped mid-day — would otherwise leave a technician with
      // three jobs they cannot open because the first one failed.
      //
      // ⚠ **AND NOT WHEN THE DAY CAME FROM THE STORE**, which is the offline
      // case: there is no signal, the fetches would fail one by one, and the
      // bundles are already there from the last sync. That is the whole point
      // of having them.
      //
      // ⚠ **CR-168-BRC10 §F — THE CHANGE FEED, NOT A RE-DOWNLOAD OF EVERY
      // BUNDLE.** TECHNICIAN SYNC DESIGN (3): *"The phone asks for everything
      // changed since my cursor, paged, including removals … It never
      // re-downloads whole lists."* So the bundles refreshed here are the jobs
      // the feed says changed (and a job taken away is forgotten), from THIS
      // technician's own cursor. A job on today's list whose bundle is not on
      // the phone at all — a cleared store, a first sign-in on this tablet —
      // is fetched once, because a list that opens onto *not on this phone
      // yet* is `DEF-WRK-4061` again.
      if (!fromStore) {
        try {
          await syncChanges();
        } catch {
          // The feed failed (signal dropped mid-sync): the bundles stay as
          // they were, and the gap below still fills what is missing.
        }
        for (const job of loaded?.jobs ?? []) {
          if (await loadJob(job.id)) continue;
          try {
            await syncJob(job.id);
          } catch {
            // Left in the store as it was. The job opens if a previous sync
            // reached it, and says so plainly if not.
          }
        }
      }
    })();
    // The marker follows the outbox: a capture, an acknowledgement or an
    // upload anywhere in the app moves *N waiting to send* here at once.
    const off = onStoreChange(() => {
      void syncMarker().then((stamp) => {
        if (live) setMarker(stamp);
      });
    });
    const tick = () => void syncMarker().then((stamp) => live && setMarker(stamp));
    window.addEventListener("online", tick);
    window.addEventListener("offline", tick);
    return () => {
      live = false;
      off();
      window.removeEventListener("online", tick);
      window.removeEventListener("offline", tick);
    };
  }, [days]);

  return (
    <div>
      <header className="px-4 pt-4 pb-3 border-b border-divider bg-surface">
        <div className="flex items-baseline justify-between gap-2">
          <h1 className="text-lead font-semibold">
            {day?.technician?.name || t("work.mobile.today.title")}
          </h1>
          <span className="text-sm text-neutral-600">
            {day ? t("work.mobile.today.count", { count: day.count, done: day.done }) : ""}
          </span>
        </div>
        <OfflineMarker marker={marker} />
      </header>

      {loading ? null : !day || day.empty_reason ? (
        <EmptyDay reason={day?.empty_reason ?? "no_jobs_today"} />
      ) : (
        <>
          <JobList jobs={day.jobs.filter((job) => job.unscheduled !== true)} tenant={tenant} />
          {/* `DEF-WRK-9693` — a job given out with no visit booked. The server
              sends these LAST (the sort's NULLs-last leg), so this splits the
              list where it already divides and reorders nothing. */}
          {day.jobs.some((job) => job.unscheduled === true) ? (
            <>
              <h2
                className="px-4 pt-4 pb-1 text-sm font-semibold text-neutral-600"
                data-testid="unscheduled-heading"
              >
                {t("work.mobile.today.unscheduled")}
              </h2>
              <JobList jobs={day.jobs.filter((job) => job.unscheduled === true)} tenant={tenant} />
            </>
          ) : null}
        </>
      )}
    </div>
  );
}

/**
 * *◍ offline · synced 08:12* — `BR-WRK-036`, and `WS-10` calls it *"the single
 * most important thing on this screen"*.
 *
 * ⚠ **IT NEVER RENDERS A TIME IT DOES NOT HAVE** (`US-WRK-041` TC-4). A phone
 * that has never synced reads *never synced*; the tempting default — no stored
 * value, so use now — would make a phone that has never reached the server
 * claim it synced this minute, which is the one thing this marker exists to
 * make impossible.
 *
 * ⚠ **AND IT IS ALWAYS RENDERED, ONLINE OR OFF.** The rule says *always
 * visible*: a marker that appears only when something is wrong is a marker
 * nobody learns to read.
 */
export function OfflineMarker({ marker }: { marker: SyncMarker }) {
  const { t } = useTranslation();
  const at = marker.lastSyncAt ? new Date(marker.lastSyncAt) : null;
  const time = at
    ? at.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })
    : null;
  return (
    <p
      className={[
        "mt-1 text-sm",
        marker.offline ? "text-warning-700" : "text-neutral-600",
      ].join(" ")}
      data-testid="offline-marker"
    >
      {time
        ? t(marker.offline ? "work.mobile.marker.offline" : "work.mobile.marker.online", { time })
        : t("work.mobile.marker.never")}
      {/* ⚠ **CR-070 wave L — WHAT IS WAITING TO SEND, COUNTED IN JOBS.**
          `US-WRK-044` TC-7 and `WS-12`'s own *◍ offline · 1 job to send*. The
          count is JOBS with a queued close, never ITEMS: a technician who has
          ticked four safety rows on a job they are still working is not waiting
          to send anything, and counting items would read *17 to send* over one
          unfinished job. The catalogue owns the plural — a sentence assembled in
          JavaScript is a plural nobody can translate (B14 rule 32's neighbour,
          and the reason this file interpolates an integer rather than composing
          a phrase). */}
      {marker.jobsToSend > 0 && (
        <span data-testid="jobs-to-send">
          {" · "}
          {t("work.mobile.marker.toSend", { count: marker.jobsToSend })}
        </span>
      )}
      {/* TECHNICIAN SYNC DESIGN (6), 2026-10-04 — *always counted*: every
          captured item the server has not yet ACKNOWLEDGED, beside the jobs
          count above (which stays the count of closes). The design ruled the
          count visible so a gap is a number rather than silence; it amends the
          "jobs, not items" reasoning above for this second figure only. */}
      {/* ⚠ ALWAYS RENDERED, ZERO INCLUDED (CR-168-BRC10 §F, lane FIELD-2):
          *"The phone always shows N waiting to send"*. A count that appears
          only when something is waiting cannot tell *nothing waiting* from
          *not counted*. */}
      <span data-testid="items-waiting">
        {" · "}
        {t("work.mobile.marker.waiting", { count: marker.itemsWaiting ?? 0 })}
      </span>
    </p>
  );
}

function EmptyDay({ reason }: { reason: string }) {
  const { t } = useTranslation();
  // A TOKEN chooses the sentence; the sentence lives in the catalogue. Six
  // words — *"No field work for this login."* (B14 rule 33).
  const key =
    reason === "no_technician_profile" ? "work.mobile.empty.noProfile" : "work.mobile.empty.noJobs";
  return <p className="px-4 py-8 text-center text-neutral-600">{t(key)}</p>;
}

function JobList({ jobs, tenant }: { jobs: MobileJobCard[]; tenant: string | undefined }) {
  if (jobs.length === 0) return null;
  return (
    <ol className="divide-y divide-divider">
      {jobs.map((job) => (
        <li key={job.id}>
          <Link
            to={`/${tenant}/work/mobile/jobs/${job.id}`}
            className="block px-4 py-3 active:bg-neutral-100"
          >
            <JobCard job={job} />
          </Link>
        </li>
      ))}
    </ol>
  );
}

/** *08:00–12:00* — the promise in the UTILITY's zone as the server read it
 *  (`DEF-WRK-9688`); the phone's own clock only when the server sent none. */
function cardTime(job: MobileJobCard): string | null {
  const booked = job.appointment;
  if (booked?.start) return booked.end ? `${booked.start}–${booked.end}` : booked.start;
  return job.window_start
    ? new Date(job.window_start).toLocaleTimeString(undefined, {
        hour: "2-digit",
        minute: "2-digit",
      })
    : null;
}

function JobCard({ job }: { job: MobileJobCard }) {
  const { t } = useTranslation();
  const when = cardTime(job);
  const access = [job.access_notes, job.gate_code && t("work.mobile.card.gate", { code: job.gate_code })]
    .filter(Boolean)
    .join(" · ");
  return (
    <div>
      <div className="flex items-baseline gap-2">
        {/* B14 rule 31 — the order NUMBER, never the uuid the link is built from. */}
        <span className="font-semibold">{job.order_no}</span>
        <span className="text-neutral-700">{job.type}</span>
        {/*
          THE PILL. `BR-WRK-035`: it says how urgent the job is and it changes
          NOTHING about where this card sits in the list.
        */}
        {job.priority ? <PriorityPill name={job.priority.name} /> : null}
      </div>
      <div className="text-sm text-neutral-600">
        {[job.premise?.address_line, when, job.est_minutes ? t("work.mobile.card.minutes", { count: job.est_minutes }) : null]
          .filter(Boolean)
          .join(" · ")}
      </div>
      {access ? (
        <p className="mt-1 text-sm text-warning-700">
          {t("work.mobile.card.access", { detail: access })}
        </p>
      ) : null}
    </div>
  );
}

/** `WM-32`'s pill. A label, never a sort key — see `TodayPage`'s docstring. */
export function PriorityPill({ name }: { name?: string }) {
  if (!name) return null;
  return (
    <span className="rounded-full border border-divider px-2 py-0.5 text-xs text-neutral-700">
      {name}
    </span>
  );
}
