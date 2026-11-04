// ── Trace ──────────────────────────────────────────────
// Change:   the Reads→Work door — PO ruling 2026-09-14, *"please build this"*.
//           Drawing: blueprint p028 (the stage-3 DECISION cell), p045/p051.
// Rules:    BR-WRK-055 (a partial raise is an ANSWER, and both halves are
//           rendered) · BR-WRK-016 (the offer is the utility's own published
//           templates) · B14 rule 31 (a work order shows its `WO-…` number,
//           never a uuid) · rule 33 (rationale is ZERO words on screen)
// ───────────────────────────────────────────────────────
// THREE THINGS ARE GUARDED HERE AND EVERY ONE OF THEM SHIPS SILENTLY.
//
// 1. **A PARTIAL RAISE IS NEVER RENDERED AS A SUCCESS.** `POST /work/flows/
//    meter-read/raise` answers 200 with `raised` AND `not_raised`, because one
//    meter with no address must not cost the other four their visits. A screen
//    that read only `raised` would tell a clerk five crews were coming when
//    four were — `DEF-708`'s shape, an act reported that never happened. The
//    case feeds a mixed answer and asserts the UNRAISED half is on screen.
//
// 2. **NO UUID EVER REACHES THE SCREEN (B14 rule 31).** The server sends
//    `not_raised[].meter_id` as a uuid because that is what matches the two
//    lists; the dialog resolves it back to the METER NUMBER it already holds.
//    The case asserts the uuid is ABSENT from the rendered text, not merely
//    that the number is present — a check that only looks for the number passes
//    on a screen printing both.
//
// 3. **THE MERGE ACROSS METERS IS PER METER, NOT PER ROW, AND IT UNIONS.** A
//    group can hold meters on different services; asking only the first would
//    offer an electric job over a water meter. And a refusal on one meter is
//    not a refusal of the panel.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { FieldWorkOffer, FieldWorkTemplate } from "@/components/RaiseFieldWork";

import { RaiseOutcome, mergeOffers, sendSomeoneOutSchema } from "./SendSomeoneOutModal";
import type { FieldVisitMeter } from "./SendSomeoneOutModal";
import type { RaiseFieldWorkResult } from "./readsFieldWorkEndpoints";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** ⚠ A REAL uuid, because the assertion is that it does NOT appear. A short
 *  placeholder would pass the `not.toContain` on a screen that leaks the real
 *  thing (hard-won law 7: what would make this check pass wrongly?). */
const BAD_METER_ID = "01a09e06-452a-7db4-8d5f-6b33e4f2e3da";
const GOOD_METER_ID = "01a09e06-4523-7226-9328-26cbe9839a9e";

const METERS: FieldVisitMeter[] = [
  { assetId: GOOD_METER_ID, meterNo: "MTR-0463" },
  { assetId: BAD_METER_ID, meterNo: "MTR-0501" },
];

function template(id: string, name: string, code = "electric"): FieldWorkTemplate {
  return {
    template_id: id,
    template_no: null,
    name,
    service: { code, name: code },
    scope: "per_asset",
    is_gate: false,
    est_duration_minutes: 30,
  };
}

function offer(proposed: FieldWorkTemplate[], refused = false): FieldWorkOffer {
  return {
    flow: { kind: "meter_read", id: "x", ref: "MTR-0463" },
    proposed,
    count: proposed.length,
    refusal: refused ? { code: "flow_has_no_anchor", message_key: "work.fromFlows.noAnchor" } : null,
  };
}

describe("mergeOffers — one offer per meter, unioned", () => {
  it("unions templates across meters on different services and never duplicates one", () => {
    const merged = mergeOffers([
      offer([template("t1", "Re-read the meter"), template("t2", "Meter exchange")]),
      offer([template("t1", "Re-read the meter"), template("t3", "Leak check", "water")]),
    ]);
    expect(merged.proposed.map((row) => row.template_id).sort()).toEqual(["t1", "t2", "t3"]);
    expect(merged.refusedCount).toBe(0);
  });

  it("counts a refused meter WITHOUT losing the other meters' templates", () => {
    // Judgment 8 bites per meter — a spare on no service point has no address.
    // The panel must still offer the jobs the reachable meters can take.
    const merged = mergeOffers([offer([template("t1", "Re-read the meter")]), offer([], true)]);
    expect(merged.proposed).toHaveLength(1);
    expect(merged.refusedCount).toBe(1);
  });

  it("treats a meter whose offer has not arrived as neither offered nor refused", () => {
    const merged = mergeOffers([undefined, offer([template("t1", "Re-read the meter")])]);
    expect(merged.proposed).toHaveLength(1);
    expect(merged.refusedCount).toBe(0);
  });
});

describe("RaiseOutcome — BR-WRK-055's two halves", () => {
  const MIXED: RaiseFieldWorkResult = {
    raised: [
      {
        id: "01a09e06-0000-7000-8000-000000000001",
        order_no: "WO-26-0117",
        name: "Re-read the meter",
        source: "meter_read",
        source_ref: "MTR-0463",
      },
    ],
    count: 1,
    not_raised: [
      {
        meter_id: BAD_METER_ID,
        code: "flow_has_no_anchor",
        message_key: "work.fromFlows.noAnchor",
      },
    ],
    warning: {
      code: "work_orders_not_raised",
      message_key: "work.fromFlows.notRaised",
    },
  };

  it("renders the meter that got NO visit, not only the one that did", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={["/brazosbend/reads/upload"]}>
        <RaiseOutcome result={MIXED} meters={METERS} t={t} />
      </MemoryRouter>,
    );
    expect(html).toContain("WO-26-0117");
    // Record links (PO 2026-10-19): the number opens its order, by number.
    expect(html).toContain(`href="/brazosbend/work/orders/WO-26-0117"`);
    // The half a screen reading only `raised` would silently drop.
    expect(html).toContain("MTR-0501");
  });

  it("never renders a uuid — the unraised meter is named by its NUMBER", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={["/brazosbend/reads/upload"]}>
        <RaiseOutcome result={MIXED} meters={METERS} t={t} />
      </MemoryRouter>,
    );
    expect(html).not.toContain(BAD_METER_ID);
    expect(html).not.toContain("01a09e06-0000-7000-8000-000000000001");
  });

  it("says nothing was raised when nothing was, rather than drawing an empty list", () => {
    const none: RaiseFieldWorkResult = { ...MIXED, raised: [], count: 0 };
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={["/brazosbend/reads/upload"]}>
        <RaiseOutcome result={none} meters={METERS} t={t} />
      </MemoryRouter>,
    );
    expect(html).toContain(t("metering.fieldVisit.noneRaisedTitle"));
    expect(html).not.toContain(t("metering.fieldVisit.raisedTitle"));
  });
});

describe("the dialog's own contract", () => {
  it("accepts an EMPTY tick list — nothing ticked is an answer, not an error", () => {
    // `from_flows` rule 1: the raise is OFFERED. A schema that demanded a pick
    // would turn a recorded choice into a validation failure.
    expect(sendSomeoneOutSchema.safeParse({ template_ids: [] }).success).toBe(true);
    expect(sendSomeoneOutSchema.safeParse({ template_ids: ["t1"] }).success).toBe(true);
    expect(sendSomeoneOutSchema.safeParse({ template_ids: [""] }).success).toBe(false);
  });

  it("carries every catalogue key it renders, in English", () => {
    // A missing key reaches a clerk as SILENCE, not as an error. `i18n.t`
    // returns the KEY when it resolves nothing, so this is the check that the
    // eleven catalogues were actually written rather than assumed.
    for (const key of [
      "metering.fieldVisit.title",
      "metering.fieldVisit.kicker",
      "metering.fieldVisit.lede",
      "metering.fieldVisit.submit",
      "metering.fieldVisit.raisedTitle",
      "metering.fieldVisit.noneRaisedTitle",
      "metering.fieldVisit.unknownMeter",
      "metering.fieldVisit.consequence.tag",
      "metering.fieldVisit.consequence.title",
      "metering.fieldVisit.consequence.body",
      "work.fromFlows.noMeters",
    ]) {
      expect(t(key)).not.toBe(key);
    }
    for (const key of [
      "metering.fieldVisit.meterCount",
      "metering.fieldVisit.noAddress",
      "metering.fieldVisit.notRaised",
    ]) {
      expect(t(key, { count: 1 })).not.toBe(key);
      expect(t(key, { count: 4 })).not.toBe(key);
    }
  });

  it("mounts under a routed tenant path, the way App.tsx mounts it", async () => {
    // ⚠ hard-won law 2's fixture clause: a bare MemoryRouter leaves
    // `useParams().tenant` undefined and every URL the app builds comes out
    // protocol-relative, which reads as a perfectly good string to `toContain`.
    const { SendSomeoneOutModal } = await import("./SendSomeoneOutModal");
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={["/brazosbend/reads/upload"]}>
        <QueryClientProvider client={client}>
          <SendSomeoneOutModal
            meters={METERS}
            onClose={() => undefined}
            onRecordDecision={async () => undefined}
          />
        </QueryClientProvider>
      </MemoryRouter>,
    );
    expect(html).toContain(t("metering.fieldVisit.title"));
    // The consequence, before the commit (B14 rule 11).
    expect(html).toContain(t("metering.fieldVisit.consequence.title"));
    // The FACT of how many meters this acts on — and no uuid with it.
    expect(html).toContain(t("metering.fieldVisit.meterCount", { count: 2 }));
    expect(html).not.toContain(BAD_METER_ID);
    expect(html).not.toContain(GOOD_METER_ID);
  });
});
