// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-040 (EP-RBS-01) — CR-075 wave E task E6, the **Change
//          limits** commit that stopped refusing. Screens: RBS-004.5.
// Rules:   `07-endpoints.md` row 3 — `PUT /runbooks/{key}`, *"change schedule,
//          cap, gate or enabled; write a new version"* · `BR-RBS-038` (every
//          edit makes a new version) · `NFR-5` (no hard cap anywhere).
// Defects: DEF-RBS-4311 (a live route behind a dead control).
// Tests:   src/features/runbooks/setupModel.test.ts
// ───────────────────────────────────────────────────────
/**
 * The two fields `RBS-004.5` lets a person change, and the shape they travel in.
 *
 * Kept out of the page so a test can assert a RULE — that a blank cap CLEARS
 * rather than sends zero, that a non-number is refused before a request is
 * made — rather than an impression of a rendered modal.
 *
 * ⚠ **A BLANK CAP IS `null` AND `null` IS *NO CAP*, NOT ZERO.** `OQ-RBS-1731`
 * is CLOSED — *ship 100* — and what is BUILT is still option (a): `cap` is
 * required with no default, and wave `L4` carries the change. So `null` here
 * means *this Action cannot be enabled until an admin types a number*, which is
 * the safe direction, and `0` would mean *act on nobody*, which is a different
 * and silent thing. The two must never collapse.
 *
 * ⚠ **AND THE UPPER END IS NOT CAPPED BY THIS FORM.** CLAUDE.md's opening
 * paragraph makes `NFR-5` the deliverable rather than the background: nobody may
 * add a per-tenant maximum that would have to be removed when T4 arrives. The
 * schema refuses a NEGATIVE number and nothing else.
 */
import { z } from "zod";

import type { RunbookDetailBody, RunbookEditBody } from "./setupWire";

/** The modal's raw values. Numbers stay STRINGS on the client — hard rule 2's
 *  posture, applied here for the same reason it is applied to money: a numeric
 *  input that round-trips through `Number` loses the difference between an
 *  empty box and a zero. */
export interface LimitsDraft {
  cap: string;
  gate_mode: string;
}

/** Whole, non-negative, or blank. The message keys are the server's own
 *  vocabulary so a client refusal and a server refusal read identically. */
export const LIMITS_SCHEMA = z.object({
  cap: z
    .string()
    .refine((value) => value.trim() === "" || /^\d+$/.test(value.trim()), {
      message: "errors.val-002",
    }),
  gate_mode: z.enum(["approve_each_run", "approved_up_front"]),
});

/** What the modal opens with — the runbook's own current values, never a
 *  remembered draft: a form seeded from anything but the server is a form that
 *  can silently re-send a stale number. */
export function limitsDraft(body: RunbookDetailBody): LimitsDraft {
  return { cap: body.cap === null ? "" : String(body.cap), gate_mode: body.gate_mode };
}

/** The `PUT` body. Only the two fields this form owns travel: a request that
 *  echoed every field back would make a no-op edit look like a change, and
 *  `services.update_runbook` writes no version for a value that did not move —
 *  *"the alternative turns the Activity tab into a log of who opened the
 *  settings sheet, which is the one screen an auditor asks for first."* */
export function limitsToWire(draft: LimitsDraft): RunbookEditBody {
  const cap = draft.cap.trim();
  return { cap: cap === "" ? null : Number(cap), gate_mode: draft.gate_mode };
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-040 (EP-RBS-01; CR-075 wave E task E6) · 07-endpoints.md row 3 · NFR-5
// generated: 2026-09-06 by the CR-075 wave E · E4/E5/E6 build lane
// checklist: A✔ B=n/a C✔ D✔ E=n/a F✔ G✔ H=n/a
// gates: tsc --noEmit (the LOCAL compiler) · vitest setupModel.test.ts
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
