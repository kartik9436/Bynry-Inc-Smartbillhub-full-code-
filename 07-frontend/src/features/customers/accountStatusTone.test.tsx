// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-722 — a clerk cannot tell "never started" from "cut off" on the
//          accounts list: `Pending activation` and `Disconnected` share
//          behaviour class `non_billable` and both rendered the same neutral
//          grey. RULED 2026-08-26, PO verbatim: *"have differnt color for diff
//          pill - you can define colors - recommendation: A"* — one colour per
//          status, and the palette is ours to choose.
// Screens: S17 (accounts list) · S21 (account detail) · S20 (`MOV-02`, the
//          move-out wizard's account facts and its done page)
// Rules:   BR-CUS-055 (account statuses are tenant-extensible REFERENCE DATA,
//          behaviour-class mapped) · BR-CUS-107 (the sixth status,
//          `Disconnected` / non_billable) · BR-CUS-016 (the STORED status) ·
//          A12 §Semantic tokens (status meaning only, never decoration) ·
//          B14 rule 8 (one pill set) · hard-won law 7 (proved RED first)
// ───────────────────────────────────────────────────────
//
// ⚠ **NONE OF THIS CAN BE VERIFIED BY LOOKING AT THE PRODUCT, AND THAT IS THE
// REASON THE FILE IS SHAPED THIS WAY.** Two of the six statuses have no writer:
// `commit_cut` assigns no `accounts` status at all (DEF-701, open) so nothing
// is ever `disconnected`, and nothing sets `marked_disconnect` either. Both are
// seeded rows waiting for a flow. So every status below is CONSTRUCTED, and a
// lane that "checks in the browser" will correctly see five statuses it cannot
// produce and wrongly conclude the defect is not real.
//
// ⚠ **AND THE ASSERTIONS ARE ON RENDERED MARKUP, NOT ON THE TONE NAME.** A tone
// is a string until a stylesheet or the Tailwind compiler makes it a colour;
// `expect(tone).toBe("info")` passes just as happily when `bg-info-100`
// compiles to nothing at all. That failure has a register of its own in this
// repo — DEF-244, DEF-305, DEF-308, DEF-314, DEF-315, DEF-327, all one shape —
// so what is asserted here is the exact `class` attribute that reaches the DOM.
// The complementary half runs in `src/styles/routeBUtilities.test.ts`, which
// asks the REAL Tailwind compiler whether those utilities exist.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { StatusPill } from "@/components/StatusPill";
import type { AccountRow } from "@/api/endpoints";

import { accountStatusLabel, accountStatusTone } from "./customersShared";

/** The composition all four call sites render, and nothing else. */
function pill(status: string, behaviorClass: string, label: string): string {
  const row = {
    status,
    status_behavior_class: behaviorClass,
    status_name: label,
  } as AccountRow;
  return renderToStaticMarkup(
    <StatusPill tone={accountStatusTone(row)}>
      {accountStatusLabel(row, (key: string) => key)}
    </StatusPill>,
  );
}

// The six BR-CUS-055 seeds in SEED ORDER, their classes, and the ruled tone's
// rendered utilities. Written as a literal table rather than derived from the
// map under test, because a test that re-derives its expectation from the code
// it is testing agrees with any change including the wrong one.
const SEEDED = [
  ["pending_activation", "non_billable", "pill bg-neutral-200 text-neutral-700"],
  ["active", "billable", "pill bg-success-100 text-success-700"],
  ["marked_disconnect", "billable", "pill bg-warning-100 text-warning-700"],
  ["vacation_hold", "billable_base_only", "pill bg-info-100 text-info-700"],
  ["closed", "terminal", "pill bg-neutral-400 text-neutral-900"],
  ["disconnected", "non_billable", "pill past"],
] as const;

describe("DEF-722 · one colour per account status, class as the fallback", () => {
  it("every seeded status renders its own ruled pill", () => {
    for (const [status, behaviorClass, expected] of SEEDED) {
      expect(pill(status, behaviorClass, status), status).toBe(
        `<span class="${expected}">${status}</span>`,
      );
    }
  });

  it("SIX statuses, SIX pills — no two seeded statuses share a colour", () => {
    // This is the defect stated as one line. It was `4` before the ruling,
    // because `active`/`marked_disconnect` shared `success` and
    // `pending_activation`/`disconnected` shared `neutral`.
    const classes = SEEDED.map(([status, cls]) => {
      const html = pill(status, cls, status);
      return html.slice(html.indexOf('class="') + 7, html.indexOf('">'));
    });
    expect(new Set(classes).size, "two seeded statuses render the same pill").toBe(6);
  });

  it("the two pairs the four-tone map collapsed are the two this must keep apart", () => {
    // Named separately from the count above so a failure says WHICH meaning
    // was lost, not merely that one was.
    //   non_billable: never started        vs  cut off, owes money, recoverable
    expect(pill("pending_activation", "non_billable", "x")).not.toBe(
      pill("disconnected", "non_billable", "x"),
    );
    //   billable:     running normally     vs  queued to have the service cut
    expect(pill("active", "billable", "x")).not.toBe(
      pill("marked_disconnect", "billable", "x"),
    );
    // …and the money-owed one is not the finished one either, which is the
    // trade lane ACCTSTALE refused to make and the reason `Closed` moved OFF
    // danger rather than `Disconnected` being denied it.
    expect(pill("disconnected", "non_billable", "x")).not.toBe(
      pill("closed", "terminal", "x"),
    );
  });

  it("BR-CUS-055: a TENANT-ADDED status falls back to its behaviour class, never to grey-by-accident", () => {
    // The constraint that survives from the pre-ruling analysis: statuses are
    // reference data, a tenant can add a seventh tomorrow, and a code-keyed map
    // alone would hand it the neutral fall-through this defect complains about.
    for (const [behaviorClass, expected] of [
      ["billable", "pill bg-success-100 text-success-700"],
      ["billable_base_only", "pill bg-warning-100 text-warning-700"],
      ["terminal", "pill past"],
    ] as const) {
      expect(pill("legal_hold", behaviorClass, "Legal hold"), behaviorClass).toBe(
        `<span class="${expected}">Legal hold</span>`,
      );
    }
    // An unknown CLASS claims nothing rather than guessing.
    expect(pill("legal_hold", "something_new", "Legal hold")).toBe(
      '<span class="pill bg-neutral-200 text-neutral-700">Legal hold</span>',
    );
  });

  it("BR-CUS-055: the LABEL still carries the meaning, so nothing here depends on colour alone", () => {
    // Accessibility is not a property of the palette; it is the property that
    // the palette is the SECOND channel. The tenant's own `status_name` is
    // rendered on every pill (a colour-blind clerk, a black-and-white print of
    // the list, a screen reader), and the tones only rank and group.
    const html = pill("disconnected", "non_billable", "Cut off — snowbirds");
    expect(html).toContain("Cut off — snowbirds");
  });
});

// ── THE SEED IS THE SERVER'S, SO IT IS READ FROM THE SERVER ────────────────
// The table above is a claim about `apps/customers/services.SEED_ACCOUNT_STATUSES`
// (mirrored in migration `customers/0025_br_cus_107_disconnected_status.py` and
// the platform fixture at V2.48.0.0, all three pinned equal by
// `06-backend/tests/test_br_cus_107_disconnected_status.py`). A SEVENTH seeded
// status would be a status with no ruled colour, falling to its class — exactly
// the state DEF-722 was filed about — and no check in the repo would say so.
// This one does, and it fails on the day the seed grows rather than on the day
// a clerk notices.
//
// Read at runtime through a non-literal dynamic import, the pattern
// `src/styles/tailwindTheme.test.ts` established and documents: the app carries
// no `@types/node` on purpose, so a static `import { readFileSync }` would fail
// `tsc --noEmit` and break `npm run build`.
const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(path: string, encoding: string): string;
};
const nodeUrl = (await import(/* @vite-ignore */ ["node", "url"].join(":"))) as {
  fileURLToPath(url: URL): string;
};

describe("DEF-722 · the palette covers exactly what the server seeds", () => {
  it("BR-CUS-055 seeds SIX statuses, in this order, and each one has a ruled colour", () => {
    const source = nodeFs.readFileSync(
      nodeUrl.fileURLToPath(
        new URL("../../../../06-backend/apps/customers/services.py", import.meta.url),
      ),
      "utf8",
    );
    const start = source.indexOf("SEED_ACCOUNT_STATUSES:");
    expect(start, "services.py no longer declares SEED_ACCOUNT_STATUSES").toBeGreaterThan(-1);
    const block = source.slice(start, source.indexOf("\n)", start));
    // ("code", "Name", CLASS_CONST) — the code is all this needs.
    const seeded = [...block.matchAll(/\(\s*"([a-z_]+)"\s*,\s*"/g)].map((m) => m[1]);
    expect(seeded).toEqual(SEEDED.map(([code]) => code));
  });
});
