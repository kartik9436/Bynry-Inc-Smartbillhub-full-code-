// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-016 · US-RBS-001 · CR-075 wave C task C3, AMENDED by wave E
//          task E4 (the mapper this file promised).
// Screens: RBS-004 (`S150`) · RBS-006 (`S152`).
// Rules:   `07-endpoints.md` row 2 — `GET /runbooks/{key}`.
// Defects: DEF-RBS-4284 · DEF-RBS-4285 (the engine and the renderer
//          disagreeing about a shape, twice, at two levels) ·
//          **DEF-RBS-4308** (the claim this file made, and what it cost).
// ───────────────────────────────────────────────────────
// THE DEFAULT CLIENT FOR THE RUNBOOKS SCREENS — AND THE RECORD OF A RULING
// THIS FILE MADE AND THAT WAS SETTLED THE OTHER WAY.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THIS FILE USED TO SAY, AND WHY THE CORRECTION IS WRITTEN OUT RATHER
// THAN QUIETLY APPLIED
// ══════════════════════════════════════════════════════════════════════════
// It held `getRunbookSetup`, which declared `Promise<RunbookSetupView>` and
// cast the body straight to it **with no mapper on purpose**. Its header
// argued the case in terms: *the wire shape IS the renderer's shape*, because
// `contract.py` rules that direction one level down, and because a mapper
// written against an endpoint that did not exist yet would be *"a contract
// nobody agreed"*. It ended by naming its own risk exactly:
//
//     ⚠ SO THIS FILE IS A CLAIM ON `D1` … If `D1` serves something else, the
//     fix is one mapper in this file and no change to the screen.
//
// **`D1` served something else, and said so in ITS docstring, for a good
// reason** — a view model is translated chrome, and serving one from Django
// would put screen copy out of the eleven locale catalogues. Both files were
// right about their own half; neither closed the gap. Nothing went red: `tsc`
// is satisfied because an unchecked cast is not a runtime check, the screen's
// tests passed a hand-built view model as a prop, and the render-check painted
// a fixture. What a BROWSER did was throw — `Cannot read properties of
// undefined (reading 'length')` — and `RBS-004` drew nothing at all from 16:23
// on 2026-09-06 until wave `E4` wrote the mapper. That is `DEF-RBS-4308`.
//
// ⚠ **THE CALL AND ITS CLAIM ARE BOTH GONE FROM THIS FILE.** Leaving a dead
// `getRunbookSetup` behind would be hard-won law 2's front half — an export
// nothing calls — and leaving its header behind would be hard-won law 1: a
// comment claiming a guarantee that is no longer the guarantee, in the one
// file a lane would read first to find out how `RBS-004` talks to the server.
// **Two files describing one call, disagreeing, is the shape this module has
// now paid for three times** (`DEF-RBS-4284`, `DEF-RBS-4285`, `DEF-RBS-4308`).
//
// **Where it lives now:** `features/runbooks/setupWire.ts` is the wire (what
// the server actually sends, transcribed from a running server, with the four
// calls `RBS-004` makes), and `features/runbooks/setupModel.ts` is the mapper.
// `setupTypes.ts` stays the renderer's shape and did not move.
//
// ⚠ **AND THE RULING IT MADE STILL STANDS FOR `RBS-006`, WHICH IS WHY THE
// ARGUMENT IS KEPT RATHER THAN DELETED.** A run's REPORT is frozen at close
// (`BR-RBS-020`), so a mapper there would re-shape a stored artefact on every
// read and *a past run reopened draws exactly what it drew that day* would
// depend on the mapper never changing. `resultTypes.ts` and
// `RunResultPage.tsx` carry that half, and each says which half it is.
import { api } from "./client";

/** The default client for the runbooks screens.
 *
 *  It is exported from here rather than from a feature folder because
 *  `RunResultPage` and the setup screens are three lanes' territory and a
 *  shared default that lives in one of them is a coupling nobody chose. */
export const runbooksApi = api;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-016 · US-RBS-001 (CR-075 wave C task C3) · amended by wave E task E4
// generated: 2026-09-06 by the CR-075 wave C · C3 build lane
// amended:   2026-09-06 by the CR-075 wave E · E4/E5/E6 lane — `getRunbookSetup`
//            and the claim it carried are removed; the mapper it named exists
//            (`features/runbooks/setupWire.ts` + `setupModel.ts`), DEF-RBS-4308
// checklist: A✔ B=n/a C✔ D✔ E=n/a F✔ G✔ H=n/a
// gates: tsc --noEmit (the LOCAL compiler, never npx) · vitest
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
