// ── Trace ──────────────────────────────────────────────
// Defects: DEF-INT-4224 · DEF-INT-4235 · DEF-GOV-4232 (G103 reads only the
//          customer portal, so nothing else covers these rows)
// Rules:   CLAUDE.md hard-won law 2, mirror clause (*"when you write a hold,
//          write the test that fires when the hold expires, in the same
//          commit"*) · law 7 (a guard is a claim only while somebody reads its
//          output) · B14 rule 33 (a refusal is five or six words)
// ───────────────────────────────────────────────────────
//
// THE TEST THAT FIRES WHEN AN INTEGRATIONS HOLD EXPIRES.
//
// `G103` does this for the customer portal and CANNOT see this module — it
// scans paths beginning `portal/` and keys matching `(?:portal|settings)\.`
// (`DEF-GOV-4232`). So the coverage these rows get is here, in the suite every
// lane runs, rather than at a merge gate. That is weaker in one specific way
// and it is worth naming rather than implying: a lane can push with this file
// failing if it does not read the output. It is stronger in another — it runs
// on every change to this feature, not only at a merge.

import { describe, expect, it } from "vitest";

import en from "@/i18n/locales/en.json";
import type { ProviderCard } from "@/api/integrationsEndpoints";

import { INTEGRATIONS_HOLDS } from "./holds";
import { providerIsConnectable } from "./IntegrationsTab";

const CATALOGUE = en as unknown as Record<string, string>;

function card(over: Partial<ProviderCard> = {}): ProviderCard {
  return {
    key: "print_vendor",
    adapter_registered: false,
    operations: [
      { name: "hand_over_batch", direction: "out", initiative: "us" },
    ],
    ...over,
  } as unknown as ProviderCard;
}

// ⚠ A ROW IS EITHER **DRAWN** OR **RECORDED**, AND THE DIFFERENCE IS NOT
// COSMETIC. A DRAWN row holds a real control and a person reads its sentence,
// so that sentence must exist in all eleven catalogues or the control reaches
// the clerk as SILENCE — a disabled button explaining nothing, which is the
// shape G32 found twenty-one of one level down. A RECORDED row deliberately
// holds NOTHING: it is a boundary written down so the next lane finds a reason
// instead of an oversight, and it must NOT carry catalogue copy, because a key
// with no producer is translated into eleven languages for ever and nothing
// ever removes it (`DEF-INT-4227`, which is exactly that, live today).
const DRAWN = ["integrations.hold.notConnectable"];
const RECORDED = ["integrations.hold.signInNotSetUp", "integrations.hold.scheduleIsRunbooks"];

describe("the integrations holds register", () => {
  it("the register accounts for every row — none is silently neither", () => {
    expect([...DRAWN, ...RECORDED].sort()).toEqual(Object.keys(INTEGRATIONS_HOLDS).sort());
  });

  // ⚠ **THE HALF THAT KEEPS THE REGISTER FROM SILENTLY STOPPING COVERING THE
  // HOLDS**, and it is G103's FIRST assertion rather than an extra. Without it
  // a lane adds a held control, does not add a row, and the register goes on
  // looking complete — *a gate that cannot fail*. The portal's version of this
  // is enforced at merge; ours runs here, because G103 reads only `portal/`
  // (`DEF-GOV-4232`).
  it("every hold key the SCREENS actually draw has a row here", () => {
    // ⚠ **`import.meta.glob`, NOT `node:fs` — AND THIS FILE WALKED INTO THE
    // TRAP THREE OTHER FILES ALREADY DOCUMENT.** `readFileSync` works at
    // runtime under vitest and FAILS `tsc --noEmit`, because the front end's
    // tsconfig carries no node types: *Cannot find module 'node:fs'*, *Cannot
    // find name 'process'*. `ConfirmDialogTier.dom.test.tsx`,
    // `DataTable.test.tsx` and `buttonKit.test.ts` each say so in their own
    // comments. The lesson is the repo's own: look for how this codebase
    // already does a thing before reaching for the obvious general-purpose
    // tool.
    const sources = import.meta.glob("./*.tsx", {
      query: "?raw",
      eager: true,
      import: "default",
    }) as Record<string, string>;

    const drawn = new Set<string>();
    for (const [path, text] of Object.entries(sources)) {
      if (path.includes(".test.")) continue; // a test naming a key is not a screen drawing it
      // Comments are stripped first: the code that explains why a hold exists
      // names these keys in prose (G103 strips comments for the same reason).
      const code = text.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
      for (const m of code.matchAll(/["'`](integrations\.hold\.[\w.]+)["'`]/g)) drawn.add(m[1]);
    }

    // ⚠ TWO CONTROLS, AND THE FIRST DRAFT NEEDED THEM. Without them a glob that
    // matched nothing, or a regex that found nothing, passes the subset check
    // below over an EMPTY SET and reports a tick — law 7's *structurally
    // incapable of failing*. The `node:fs` draft did exactly that and this is
    // what caught it.
    expect(Object.keys(sources).length, "the glob matched no screens at all").toBeGreaterThan(0);
    expect(drawn.size, "the scan found no hold keys — it is not reading the screens").toBeGreaterThan(0);

    for (const key of drawn) {
      expect(
        Object.keys(INTEGRATIONS_HOLDS),
        `${key} is drawn on a screen and has no row in holds.ts saying what would release it`,
      ).toContain(key);
    }
  });

  it("a DRAWN hold's reason is a real sentence a clerk can read", () => {
    for (const key of DRAWN) {
      expect(CATALOGUE[key], `${key} is not in the English catalogue`).toBeTruthy();
    }
  });

  it("a RECORDED hold carries no copy — it holds nothing, so nothing says it", () => {
    for (const key of RECORDED) {
      expect(CATALOGUE[key], `${key} has catalogue copy but draws no control`).toBeUndefined();
    }
  });

  it("a hold reason is five or six words (B14 rule 33)", () => {
    for (const key of DRAWN) {
      const words = CATALOGUE[key].split(/\s+/).filter(Boolean);
      expect(words.length, `${key}: "${CATALOGUE[key]}"`).toBeLessThanOrEqual(6);
    }
  });

  it("every hold row is one of the three kinds, and the weak kind is COUNTED", () => {
    const kinds = Object.values(INTEGRATIONS_HOLDS).map((one) => one.kind);
    for (const kind of kinds) expect(["server", "policy", "unwatched"]).toContain(kind);
    // ⚠ THE NUMBER IS THE POINT (law 7, fifth shape). A declared blind spot
    // with no figure beside it is indistinguishable from an empty one, so the
    // count of holds nothing mechanical can watch is asserted rather than
    // described. One today: sign-in readiness, which is DEPLOYMENT state and
    // is not on the wire at all (`DEF-INT-4235`). If this number grows, a lane
    // has added a promise nobody is keeping and has to say so here.
    expect(kinds.filter((one) => one === "unwatched")).toHaveLength(1);
  });
});

describe("DEF-INT-4224 · the notConnectable hold releases itself", () => {
  // ⚠ THIS IS THE EXPIRY TEST, AND FOR THIS HOLD IT IS AN ASSERTION ABOUT THE
  // SERVER RATHER THAN A DATE. The row is `kind: "server"`: the day an adapter
  // is registered, `adapter_registered` comes back true and the card goes live
  // with no edit anywhere in this repo. What could still break that is someone
  // changing the predicate, so the predicate is what is pinned.

  it("holds a live provider we would have to dial and cannot", () => {
    expect(providerIsConnectable(card())).toBe(false);
  });

  it("RELEASES the moment the server registers an adapter — nothing to remember", () => {
    expect(providerIsConnectable(card({ adapter_registered: true }))).toBe(true);
  });

  it("never holds a connector we never dial, whatever the adapter says", () => {
    // `Manifest.we_never_dial` — every operation is theirs to start, so there
    // is no call for an adapter to make and none is missing (`DEF-INT-4215`).
    // Computed from `initiative` and NOT from `auth.mode`, which is the
    // narrower and safer test and the one the server uses: a connector could
    // hold our key and still have an operation WE start.
    const partner = card({
      key: "gl_partner",
      adapter_registered: false,
      operations: [
        { name: "read_payments", direction: "out", initiative: "them" },
        { name: "read_bills", direction: "out", initiative: "them" },
      ],
    } as unknown as Partial<ProviderCard>);
    expect(providerIsConnectable(partner)).toBe(true);
  });

  it("one operation we start is enough to need an adapter", () => {
    // The case the server's docstring names as the reason it reads `initiative`
    // rather than `auth.mode` — a partner who holds our key AND has a half we
    // dial. That half needs an adapter, so the card must not claim otherwise.
    const mixed = card({
      key: "mixed_partner",
      adapter_registered: false,
      operations: [
        { name: "they_read", direction: "out", initiative: "them" },
        { name: "we_push", direction: "out", initiative: "us" },
      ],
    } as unknown as Partial<ProviderCard>);
    expect(providerIsConnectable(mixed)).toBe(false);
  });

  it("a provider with no operations at all is not claimed connectable", () => {
    // `[].every(...)` is TRUE, so a naive reading of *every operation is
    // theirs* would call an empty manifest a connector we never dial and set
    // it live. Fails closed instead (hard-won law 3).
    expect(providerIsConnectable(card({ operations: [] }))).toBe(false);
  });
});
