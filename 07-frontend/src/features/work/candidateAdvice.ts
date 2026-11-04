// ── Trace ──────────────────────────────────────────────
// Story:    CR-168-BRC10 round 3, lane ASSIGN — P4.12 (advice beside every
//           name), P4.13 (bulk assign says who fits)
// Rules:    ruling 2 (PO 2026-09-23, *"a guideline, never a block"*; answer 2,
//           2026-10-04: a lapsed certificate only WARNS — BR-WRK-029 and
//           BR-WRK-030 superseded) · B14 rule 33 (each piece is a FACT, ≤ 6
//           words) · rule 35 (every word from the catalogue) · rule 37 (the
//           drawn counts are illustrations)
// Tests:    src/features/work/cr168Assign.dom.test.tsx
// Impacts:  CandidatePicker.tsx · OrderEditPage.tsx · dispatchModals.tsx
// ───────────────────────────────────────────────────────
//
// The words beside a name, as PURE functions, so the arithmetic of a bulk
// selection can be checked without a DOM.
//
// ⚠ **NOTHING HERE DECIDES WHETHER A NAME IS OFFERED.** Every function returns
// words; none returns a boolean a picker could use to grey a name out. That is
// ruling 2 written into the shape of the module: the match is advice, so the
// only thing advice can produce is a sentence.
import type { Candidate, CandidatePage } from "./workEndpoints";

type Translate = (key: string, params?: Record<string, unknown>) => string;

/** Best fit first; otherwise the server's own order (it pages, so its order is
 *  the one the next page continues). Stable. */
export function bestFitFirst(list: Candidate[]): Candidate[] {
  return [...list.filter((c) => c.best_fit), ...list.filter((c) => !c.best_fit)];
}

/** The candidate's kind as a word: *Technician · Crew · Contractor*. */
export function kindWord(kind: string, t: Translate): string {
  const key = kind === "person" ? "person" : kind === "contractor" ? "contractor" : "crew";
  return t(`work.edit.holderKind.${key}`);
}

/**
 * FB-033 (D1 = A, D2 = A) — the technician's own word from the phone, as a
 * warning beside the name: *Off duty since 16:10* in RED, *On break since
 * 10:42* as a plain warning. Words only — the name stays choosable and the
 * assignment is accepted (ruling 2). Null when the phone said neither.
 */
export function availabilityAlert(
  candidate: Candidate,
  t: Translate,
): { text: string; tone: "danger" | "warning" } | null {
  const said = candidate.advice.availability ?? null;
  if (said === null) return null;
  const time = /T(\d{2}:\d{2})/.exec(said.since ?? "")?.[1] ?? null;
  if (said.status === "off_duty") {
    return {
      text: time === null ? t("work.crews.status.off_duty") : t("work.assign.advice.offDuty", { time }),
      tone: "danger",
    };
  }
  return {
    text: time === null ? t("work.crews.status.on_break") : t("work.assign.advice.onBreak", { time }),
    tone: "warning",
  };
}

/**
 * The facts beside one name, in image 12's order — the skill, the area, then
 * the day — joined with ` · `. A fact the server did not send is left out
 * rather than guessed (hard-won law 1): `jobs_that_day: null` is no clause,
 * never *0 jobs*.
 */
export function adviceText(
  candidate: Candidate,
  t: Translate,
  formatDay: (iso: string) => string,
  options: { availabilityShownApart?: boolean } = {},
): string {
  const advice = candidate.advice;
  const alert = availabilityAlert(candidate, t);
  const parts: string[] = [];
  if (advice.skill !== null) {
    parts.push(
      advice.has_skill
        ? t("work.assign.advice.hasSkill", { skill: advice.skill.name })
        : t("work.assign.advice.missingSkill", { skill: advice.skill.name }),
    );
  }
  for (const lapsed of advice.certifications_lapsed) {
    parts.push(t("work.assign.advice.lapsed", { date: formatDay(lapsed.expired_on) }));
  }
  // Image 12's *Field crew B · Meter I ✓ · 2 people* — a crew's head-count.
  if (candidate.members !== undefined) parts.push(t("work.assign.advice.people", { count: candidate.members }));
  if (advice.area_match) parts.push(t("work.assign.advice.inArea"));
  // FB-033 — Off duty says why the person is off; *Off that day* would repeat it.
  if (advice.off_that_day && advice.availability?.status !== "off_duty") parts.push(t("work.assign.advice.off"));
  if (alert !== null && options.availabilityShownApart !== true) parts.push(alert.text);
  if (advice.jobs_that_day !== null) {
    parts.push(t("work.assign.advice.jobs", { count: advice.jobs_that_day }));
  }
  // CR-168-BRC10 §30 — over the person's daily job limit that day (PO answer
  // (2), 2026-10-05). Advice: the name stays choosable (ruling 2).
  if (advice.over_daily_limit === true && typeof advice.daily_job_limit === "number") {
    parts.push(t("work.assign.advice.overLimit", { limit: advice.daily_job_limit }));
  }
  return parts.join(" · ");
}

/**
 * ONE list for a bulk selection: every name offered for ANY of the orders,
 * with the advice that holds across ALL of them.
 *
 * ⚠ **A UNION, NOT AN INTERSECTION — AND THAT REVERSES THIS FILE'S
 * PREDECESSOR ON PURPOSE.** `intersectCandidates` offered only the people
 * eligible for every ticked order, which was right while the server refused a
 * mismatch (`BR-WRK-029`) and is a silent block now that ruling 2 says it may
 * not. So a name missing the skill on one order of three is OFFERED, and the
 * advice says so.
 *
 * Across the orders: missing a skill on any → *Missing skill*; a lapsed
 * certificate on any → listed once; off on any order's day → *Off that day*;
 * *Best fit* only when best for every order; *jobs that day* is dropped,
 * because three orders can be on three days and one number would be a lie.
 */
export function mergeAcross(pages: CandidatePage[]): Candidate[] {
  const order: string[] = [];
  const seen = new Map<string, { candidate: Candidate; lists: number; best: number }>();
  for (const page of pages) {
    for (const row of page.results) {
      const key = `${row.kind}:${row.id}`;
      const held = seen.get(key);
      if (held === undefined) {
        order.push(key);
        seen.set(key, {
          // Several days: neither the count nor *over the limit* holds (§30).
          candidate: { ...row, advice: { ...row.advice, jobs_that_day: null, over_daily_limit: false } },
          lists: 1,
          best: row.best_fit ? 1 : 0,
        });
        continue;
      }
      const into = held.candidate.advice;
      const from = row.advice;
      if (into.has_skill && !from.has_skill) {
        into.has_skill = false;
        into.skill = from.skill;
      } else if (into.skill === null && from.skill !== null) {
        into.skill = from.skill;
      }
      into.off_that_day = into.off_that_day || from.off_that_day;
      into.area_match = into.area_match && from.area_match;
      for (const lapsed of from.certifications_lapsed) {
        if (!into.certifications_lapsed.some((one) => one.name === lapsed.name && one.expired_on === lapsed.expired_on)) {
          into.certifications_lapsed = [...into.certifications_lapsed, lapsed];
        }
      }
      held.lists += 1;
      held.best += row.best_fit ? 1 : 0;
    }
  }
  return bestFitFirst(
    order.map((key) => {
      const held = seen.get(key) as { candidate: Candidate; lists: number; best: number };
      return { ...held.candidate, best_fit: held.best === pages.length && held.lists === pages.length };
    }),
  );
}

/**
 * Image 02's line under *Who is going* — *"Advice: all five have Meter I;
 * M. Chen is off 25 Sep."* — as up to three FACTS (B14 rule 33), each from
 * the catalogue. `complete` is false while more pages exist: then no sentence
 * claims *all*, because the screen has not seen all.
 */
export function bulkAdviceLine(candidates: Candidate[], complete: boolean, t: Translate): string | null {
  if (candidates.length === 0) return null;
  const parts: string[] = [];
  const missing = candidates.filter((c) => !c.advice.has_skill).length;
  const skills = new Set(candidates.map((c) => c.advice.skill?.name).filter((name): name is string => Boolean(name)));
  if (missing > 0) {
    parts.push(t("work.assign.bulk.missing", { count: missing }));
  } else if (complete && skills.size === 1) {
    parts.push(t("work.assign.bulk.allHave", { count: candidates.length, skill: [...skills][0] }));
  }
  const off = candidates.filter((c) => c.advice.off_that_day).map((c) => c.name);
  if (off.length > 0) parts.push(t("work.assign.bulk.off", { names: off.join(", ") }));
  if (parts.length === 0) return null;
  return `${t("work.assign.bulk.prefix")} ${parts.join(" ")}`;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-168-BRC10 §8 row R3 ASSIGN · §7.3 candidates shape · images 02, 12, 13
// generated: 2026-10-04 by lane ASSIGN
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// gates: tsc · eslint · vitest cr168Assign.dom.test.tsx
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
