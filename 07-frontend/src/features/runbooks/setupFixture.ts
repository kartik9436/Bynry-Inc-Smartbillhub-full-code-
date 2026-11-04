// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-016 · US-RBS-001 · CR-075 wave C task C3.
// Screens: RBS-004.1 … RBS-004.7 — the SAMPLE VALUES the seven sheets draw.
// Rules:   CLAUDE.md hard-won law 6 (diff the running app against the drawing).
// ───────────────────────────────────────────────────────
// RUNBOOK 8, *DUNNING AND NOTICES*, EXACTLY AS THE SEVEN SHEETS DRAW IT.
//
// ⚠ **ONE FIXTURE, TWO READERS, AND THAT IS THE WHOLE REASON IT IS A FILE.**
// `RunbookSetup.test.tsx` asserts against it and
// `10-scripts/render-checks/rbs-c-setup-renderer.render.tsx` paints it in a real
// browser. A second copy would drift, and the drift would be invisible: the unit
// test would keep passing against its copy while the screenshot showed the
// other. `cr075-c-runbook-kit.render.tsx` records the same reasoning about
// importing components rather than re-typing their markup, and
// `column-chooser-geometry.mjs` says in its own comment that a copy which
// drifts measures nothing.
//
// ⚠ **THE VALUES ARE THE SHEETS' OWN, TYPED OUT RATHER THAN INVENTED.** Every
// sheet closes with *"Sample values are illustrative; the words around them are
// not"* — so the FIGURES here carry no authority and the LABELS around them
// carry all of it. That is why a walkthrough can compare this against
// `RBS-004.*.png` region by region and mean something.
//
// ⚠ **IT IS NOT SEED DATA AND NOTHING SHIPS IT.** `GET /runbooks/{key}` (task
// `D1`) is what feeds the real screen. This file exists so the renderer can be
// PROVED before that endpoint lands, which is the difference between a screen
// that is finished and a screen that is merely written.
import type { RunbookSetupView } from "./setupTypes";

/** `RBS-004.1` … `.7`, region by region. */
export const COLLECTIONS_LADDER: RunbookSetupView = {
  // The slug from the sheet's own route line — `silvercreek / operations /
  // runbooks / collections-ladder`. There is no id field on the view model at
  // all, so B14 rule 31 holds by construction (see `setupTypes.ts`).
  key: "collections-ladder",
  name: "Collections ladder",
  kind: "action",
  category: "Collections",
  purpose: "Sends the notice each account is due.",
  paused: false,

  // ── RBS-004.1 regions 4–5 ────────────────────────────────────────────────
  schedule: {
    runs: { kind: "text", text: "Mondays 07:00" },
    timeZone: { kind: "text", text: "America/Chicago" },
    next: { kind: "text", text: "8 Sep 07:00" },
  },

  // ── RBS-004.1 regions 6–7 ────────────────────────────────────────────────
  lastRun: {
    when: { kind: "text", text: "Today 07:00" },
    state: { kind: "pill", label: "Waiting", tone: "warning" },
    planned: { kind: "text", text: "812" },
  },

  // ── RBS-004.1 regions 8–9 ────────────────────────────────────────────────
  // Runbook 8 holds `queue_notice` and `apply_fee` (`12-the-contract.md` §8) and
  // no port that changes a bill — which is what the frame's third row says. The
  // derivation is the SERVER's; this is what it produces (decision log,
  // 2026-09-06).
  capabilities: [
    { id: "notices", label: "Send notices", can: true },
    { id: "fees", label: "Charge fees", can: true },
    { id: "bills", label: "Change bills", can: false },
  ],

  // ── RBS-004.2 region 2 — six steps, four read, two write ─────────────────
  steps: [
    { id: "s1", label: "Find accounts past due", why: "Balance over $5.00, due date passed", writes: false },
    { id: "s2", label: "Remove protected accounts", why: "Medical, dispute, sample", writes: false },
    { id: "s3", label: "Work out the tier due", why: "Reminder · 10-day · 5-day · certified", writes: false },
    { id: "s4", label: "Check the address works", why: "A dead channel is skipped, not sent", writes: false },
    { id: "s5", label: "Queue the notice", why: "One per account per run", writes: true },
    { id: "s6", label: "Record what was sent", why: "Audit row names this runbook", writes: true },
  ],
  // The frame draws this note; the sheet's region table does not list it. Both
  // are derived from the same source markup, so the sheet under-reports — see
  // `08-screen-layouts.md`, where the divergence is stamped.
  settingsOwned: { to: "/silvercreek/settings/collections" },

  // ── RBS-004.3 region 2 — the runbook's own inputs (`BR-RBS-042`) ─────────
  scope: [
    { id: "accounts", label: "Accounts included", value: { kind: "text", text: "Past due over $5.00" } },
    { id: "services", label: "Services", value: { kind: "text", text: "Water · Sewer" } },
    // ⚠ *All* is stored as THE WORD and resolved at run start (`BR-RBS-042`
    // clause 1, `BR-RBS-009`). A utility that sets *all services* with Water and
    // Sewer and adds Trash next month must get three — so the screen shows the
    // word, never the two it would have expanded to today.
    { id: "cycles", label: "Cycles", value: { kind: "text", text: "All" } },
    { id: "types", label: "Account types", value: { kind: "text", text: "All except Municipal" } },
  ],
  settingsFields: [],
  scopeMatches: 1004,

  // ── RBS-004.4 region 2 ───────────────────────────────────────────────────
  guards: [
    { id: "medical", label: "Medical protection" },
    { id: "dispute", label: "Open dispute" },
    { id: "sample", label: "Sample records" },
  ],

  // ── RBS-004.5 region 2 ───────────────────────────────────────────────────
  limits: {
    mostPerRun: { kind: "text", text: "400" },
    approval: { kind: "text", text: "Every run" },
    fees: { kind: "text", text: "Second approval" },
    whoCanApprove: { kind: "text", text: "Admin" },
  },

  // ── RBS-004.6 regions 2–3 — four of thirty-four, server-paged ────────────
  runs: {
    rows: [
      { id: "r1", when: "Today 07:00", outcome: { label: "Waiting", tone: "warning" }, acted: null },
      { id: "r2", when: "1 Sep 07:00", outcome: { label: "Done", tone: "success" }, acted: 248 },
      { id: "r3", when: "25 Aug 07:00", outcome: { label: "Stopped", tone: "danger" }, acted: 120 },
      { id: "r4", when: "18 Aug 07:00", outcome: { label: "Done", tone: "success" }, acted: 301 },
    ],
    total: 34,
    page: 1,
    // ⚠ The sheet's footer reads *Showing 1–4 of 34*, which is four rows out of
    // thirty-four on ONE page — a drawing that fits its frame, not a page size.
    // `IS-2`'s options are 50/100/200/500/1000 with a default of 50, and a
    // twelfth page size would be a change to a ratified standard rather than a
    // fixture detail. The rendered range therefore reads *1–34 of 34* here and
    // the divergence is stamped in `08-screen-layouts.md`.
    per: 50,
    loading: false,
  },

  // ── RBS-004.7 region 2 ───────────────────────────────────────────────────
  // ⚠ `summary` has no engine field behind it (`DEF-RBS-4285`). These four are
  // the frame's own words.
  activity: [
    { id: "v4", version: 4, summary: "Cap raised to 400", actor: "Dana W.", when: "2 Sep" },
    { id: "v3", version: 3, summary: "Paused", actor: "Ray P.", when: "26 Aug" },
    { id: "v2", version: 2, summary: "Schedule set to Mondays", actor: "Dana W.", when: "12 Aug" },
    { id: "v1", version: 1, summary: "Added from templates", actor: "Dana W.", when: "12 Aug" },
  ],
};

/**
 * Runbook 1, *Configuration check* — a CHECK, so it holds no ports at all.
 *
 * ⚠ **THIS FIXTURE EXISTS TO PROVE ONE SENTENCE ON SCREEN.** `BR-RBS-002` says
 * a Check is CONSTRUCTED with no writer — *"the capability is absent, not
 * merely unused"* — and that is the reason a two-person utility can press Run
 * on a thousand accounts. An empty `capabilities` list drawn as nothing would
 * hide the best thing this screen has to say, so the renderer draws the
 * sentence and this fixture is what makes it testable and paintable.
 */
export const CONFIGURATION_CHECK: RunbookSetupView = {
  key: "configuration-check",
  name: "Configuration check",
  kind: "check",
  category: "Platform",
  purpose: "Says what is stopping billing today.",
  paused: false,
  schedule: {
    runs: { kind: "text", text: "On request" },
    timeZone: { kind: "text", text: "America/Chicago" },
    // Nothing is scheduled, so there is no next run — and `absent` draws the
    // screen's *Not set* rather than an empty cell that reads as a zero.
    next: { kind: "absent" },
  },
  lastRun: null,
  capabilities: [],
  steps: [
    { id: "c1", label: "Check the services are on", writes: false },
    // ⚠ THE MIDDLE STEP HAS NO `why`, ON PURPOSE. `contract.py`'s `Step`
    // declares no field for it (`DEF-RBS-4285`), so a real definition will
    // arrive with some steps explained and some not — and the renderer must
    // draw NOTHING for an absent one rather than a dash. Asserted.
    { id: "c2", label: "Check the tax region", writes: false },
    { id: "c3", label: "Check every plan has rates", why: "A block above the top tier", writes: false },
  ],
  settingsOwned: null,
  scope: [{ id: "tenant", label: "Subject", value: { kind: "text", text: "This utility" } }],
  settingsFields: [],
  scopeMatches: null,
  guards: [],
  limits: {
    mostPerRun: { kind: "absent" },
    approval: { kind: "text", text: "Not needed" },
    fees: { kind: "text", text: "None" },
    whoCanApprove: { kind: "text", text: "Any staff" },
  },
  runs: { rows: [], total: 0, page: 1, per: 50, loading: false },
  activity: [],
};
