// ── Trace ──────────────────────────────────────────────
// Change:  CR-016 ADDENDUM — "EVERY SCREEN CARRIES ITS ID, VISIBLE" (PO,
//          2026-08-19): *"for time bing also display that as a tag - right
//          bottom for every UI screen so that we know which scren has a
//          problem"*, narrowed the same day by *"assign tags that are visible
//          on screen those should be as per modules how we are using in r10"*
// Defects: DEF-137 — *"screens do not carry their own id in the frontend, so
//          no gate can [check screen coverage]"*
// Rules:   `05-prototype/r10-2026-08-16/SMARTBillHub.dc.html` line 8830 — the
//          badge this copies, bottom-right, `pointer-events:none`, z 70 ·
//          `routing/screenIds.ts` — the map, and the ONE switch
// ───────────────────────────────────────────────────────
// THE DIAGNOSTIC TAG, AND THE DOM ATTRIBUTE THAT OUTLIVES IT.
//
// Two halves, and they are deliberately not the same thing:
//
// **THE VISIBLE HALF** is what the Product Owner asked for and what r10 already
// draws. It exists because every UI defect reported on 2026-08-19 arrived as
// *"this screen"* plus a photograph, and matching that to a component cost a
// grep every time. It is the PO's own *"for time being"*, so it is behind ONE
// switch: build with `VITE_SCREEN_ID_TAG=off` and it is gone from the whole
// product. No component takes a prop for it; no screen has to be edited.
//
// **THE MACHINE-READABLE HALF** — `data-screen-id` (r10) and `data-screen-a1`
// (the S-id) on `<body>` — is NOT behind that switch, on purpose. It is what
// makes DEF-137's coverage gate possible and what an e2e assertion holds on to,
// and a diagnostic the PO turns off must not quietly take the harness's only
// handle with it. It is also the more durable half: an attribute survives a
// restyle, a print sheet and a screenshot crop.
//
// WHY `<body>` AND NOT THE TAG ELEMENT ALONE. The tag renders nothing at all on
// a screen r10 has no id for (see screenIds.ts — an absent id is reported, not
// invented), and it renders nothing when the switch is off. `<body>` always
// exists, always carries whichever ids the screen HAS, and needs no selector
// that knows where the tag is drawn.
//
// WHAT IT MUST NEVER DO, all three enforced in `ScreenIdTag.css`:
//   · cover a control — `position: fixed` in the corner r10 uses, and
//     `pointer-events: none`, so a click passes straight through it to whatever
//     is underneath. It cannot intercept anything, ever.
//   · reach a printed bill or an exported PDF — `@media print { display: none }`.
//   · reach a screen reader — `aria-hidden`, because an id is not content.
import { useEffect } from "react";
import { useLocation } from "react-router-dom";

import { SCREEN_ID_TAG_ENABLED, resolveScreen } from "@/routing/screenIds";


/**
 * Mounted ONCE, above every route (`ROOT_ROUTES` in App.tsx), so that public
 * pages, the sign-in page and every screen inside the shell are covered by one
 * mount rather than by a prop threaded through a hundred components.
 */
export function ScreenIdTag() {
  const location = useLocation();
  const screen = resolveScreen(location.pathname, location.search);
  const { a1, r10 } = screen;
  // CR-068 wave A: an address a SECOND application root serves with its own
  // register (`noScreen: "own-register"`) is not this tag's to write or to
  // blank — the portal's own tag sets `<body data-screen-id>` there, and an
  // effect here that deleted it would run AFTER the child's and erase it.
  const ownRegister = screen.route?.noScreen === "own-register";

  useEffect(() => {
    if (ownRegister) {
      return undefined;
    }
    const { body } = document;
    if (r10 === null) {
      delete body.dataset.screenId;
    } else {
      body.dataset.screenId = r10;
    }
    if (a1 === null) {
      delete body.dataset.screenA1;
    } else {
      body.dataset.screenA1 = a1;
    }
    // Cleaned up on unmount so a test that renders two routers in one JSDOM
    // document cannot read the previous one's screen — a stale attribute is
    // exactly the "comment claiming a guarantee" of hard-won law 1, in the DOM.
    return () => {
      delete body.dataset.screenId;
      delete body.dataset.screenA1;
    };
  }, [a1, r10, ownRegister]);

  // Nothing to draw: the switch is off, or r10 allocates no id for this screen.
  // The second case is a FINDING and is listed in screenIds.ts, not papered
  // over with an id no authority defines.
  if (!SCREEN_ID_TAG_ENABLED || screen.label === "") {
    return null;
  }

  return (
    // The ids ride on the element as well as on `<body>`. `<body>` is the
    // durable handle — it is there when the switch is off and when r10 has no
    // id — and these are what the unit suite can reach without a DOM
    // environment, so the shape is exercised somewhere cheap as well as
    // somewhere real.
    // CR-018 Route B: ScreenIdTag.css (deleted) ported value for value from
    // r10's own badge — fixed 12px off the bottom-right, z-70 (below a modal
    // backdrop, above the page), ink chip at --text-xs with the named
    // tracking/leading pair, 0.8 opacity. The three load-bearing declarations
    // survive by name: pointer-events-none (the tag can NEVER intercept a
    // click), fixed (it participates in no layout), print:hidden (an internal
    // id has no business on a bill). `tabular-nums` is the kit's spelling of
    // r10's font-feature-settings:'tnum'. `data-testid` was already the
    // machine handle; the unit suite and the CR-016 spec both read it now.
    <div
      className="pointer-events-none fixed bottom-3 right-3 z-70 select-none bg-text px-[9px] py-[3px] font-heading text-xs font-extrabold leading-screen-id tracking-screen-id text-bg tabular-nums opacity-80 print:hidden"
      aria-hidden="true"
      data-testid="screen-id-tag"
      data-screen-id={r10 ?? undefined}
      data-screen-a1={a1 ?? undefined}
    >
      {screen.label}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-016 addendum "EVERY SCREEN CARRIES ITS ID, VISIBLE" (PO 2026-08-19) + DEF-137
// screens: every routed screen — this component is what carries the id on all of them
// generated: 2026-08-19 by story-coder (CR-016 screen-id lane)
// checklist: A✔ B✔ C✔ D=deferred(no API call — the id is derived from the URL) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: g29_screen_ids.py (proved RED by pointing /:tenant/dashboard at "S999" and by blanking a mapping) · screenIds.test.tsx
// exceptions: (1) NO i18n key — an id is an id in every language, so this renders no translatable copy and adds nothing to the eleven catalogues · (2) the visible half is a temporary diagnostic by the PO's own framing and is behind VITE_SCREEN_ID_TAG; the DOM attribute is not, and the docstring says why
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
