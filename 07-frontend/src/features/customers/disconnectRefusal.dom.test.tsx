// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  **DEF-CUS-7680** — the disconnect wizard refuses on its last step
//          after every step is filled and says nothing useful. Reported by the
//          Product Owner from deployed `v2.352.0`: screen `DSC-02`,
//          `/{tenant}/disconnects/new?step=4`, `POST /disconnects/schedule` →
//          **422**, `BIZ-COMPLETENESS`, key `customers.disconnects.refused`,
//          trace reference `2FA5-0006`, *"Diagnostic: none shown"*.
// Rules:   BR-SHL-020 r2 (server `detail` never reaches a screen; the CODE is
//          what a screen branches on) · B14 rule 32 (no rule id and no
//          internal code in clerk-facing copy) · B14 rule 33 (a FACT ≤ 6
//          words; an INSTRUCTION ≤ 6 words per sentence; RATIONALE is ZERO
//          words) · BR-CUS-039 · BR-CUS-082 · CLAUDE.md hard-won law 2 (built
//          is not wired) · law 6 (no gate reads rendered output) · law 7
// Tests:   this file · ./DisconnectWizard.test.tsx (the static half) ·
//          06-backend/tests/test_def_cus_7680_schedule_refusals_carry_their_
//          code.py (the server half)
// ───────────────────────────────────────────────────────
//
// ⚠ **EVERY ASSERTION HERE IS ON RENDERED OUTPUT, DRIVEN BY A CLICK, UNDER THE
// REAL ROUTE PATTERN — AND ALL THREE OF THOSE ARE THE POINT.**
//
//   · **RENDERED OUTPUT**, because the defect is that a sentence the server
//     sends never reaches a screen. A case asserting `disconnectRefusalText()`
//     returns the right string would have been green over the shipped build:
//     the function did not exist, and the wizard called something else.
//   · **DRIVEN BY A CLICK**, because the failure card only exists after a
//     commit. `DisconnectWizard.test.tsx` renders to static markup and cannot
//     press anything, which is exactly why the shipped wizard's refusal path
//     had no rendered-output case at all.
//   · **UNDER `/:tenant/disconnects/new`**, because a bare `MemoryRouter`
//     leaves `useParams().tenant` undefined and every address the page builds
//     comes out `//…` — a protocol-relative URL to another host that reads as
//     a perfectly good string to `toContain` (CLAUDE.md law 2's fixture note,
//     `DEF-CWP-3925`).
//
// ⚠ **RED-FIRST PROOF, MEASURED (law 7), IN THE HARNESS THAT WILL RUN IT.**
// Every case below was run in a SECOND `git worktree` at this branch's tip
// `8f9bef45d`, with the lane's source changes absent — this file copied in and
// nothing else — through `vitest run`:
//
//     13 failed | 7 passed (20)
//
// and the failures ARE the finding, in the runner's own words:
//
//     expected 'This disconnect step can't be done a…'
//              to be 'No case is open.'                                  ×6
//     expected [ 'cut_reason_unknown', …(6) ] to deeply equal []          ×1
//     expected null not to be null   (no `[data-preflight]` anywhere)     ×5
//     expected 'This disconnect step can't be done a…'
//              to be 'A protection is in force.'                          ×1
//
// ⚠ **THE FIRST ATTEMPT AT THIS PROOF WAS WORTHLESS AND IS RECORDED BECAUSE
// OF IT.** Run unmodified, the file could not even RESOLVE
// `./disconnect/disconnectRefusal` and vitest reported *"Tests: no tests"* —
// a red that proves an import is missing and says nothing at all about the
// SCREEN. The two constants were inlined into the copy so the file COLLECTS,
// and only then does each case speak. **A suite that cannot run is not a
// failing suite**, which is law 7's *incapable of passing* wearing its
// friendliest face.
//
// ⚠ **SEVEN PASSED BEFORE THE FIX AND FOUR OF THEM PASSED FOR THE WRONG
// REASON — SAYING WHICH IS PART OF THE PROOF** (law 7, habit 2: ask what
// would make this check pass wrongly).
//   · GENUINE GUARDS, green before and after, and worth keeping: the two
//     fallback cases (an unmapped code and a code-less refusal must render
//     the generic line), the two *no refusal is drawn* cases, and *the commit
//     is still attempted*.
//   · **PASSED VACUOUSLY:** *the six do not collapse to one sentence* — four
//     of the six keys did not exist, so i18next returned the KEY STRING and
//     six distinct strings looked like six distinct sentences. And *every
//     sentence obeys rule 33* — an absent key measured as an empty string,
//     and an empty string is never too long.
//   **Both are covered by *every code … has a sentence of its own in
//   en.json*, which is the case that went red and named all seven missing
//   keys.** They are kept because after the fix they measure real copy.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import en from "@/i18n/locales/en.json";
import i18n from "@/i18n";
import { createApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import { shellBootSeed } from "@/components/shellBootSeed";
import { SEEDED_REGIONAL } from "@/components/tenantRegionalFixture";

import { DisconnectWizard } from "./DisconnectWizard";
import { DISCONNECT_WIZARD_ROUTE } from "./transferDisconnectShared";
import {
  DISCONNECT_GENERIC_REFUSAL_KEY,
  DISCONNECT_SCHEDULE_REFUSAL_CODES,
} from "./disconnect/disconnectRefusal";

afterEach(cleanup);

const TENANT = "brazosbend";
const ACCOUNT = "acc-11340";
const t = (key: string): string => i18n.t(key) as string;

/** What the shipped build showed for all eighteen refusals. */
const GENERIC = t(DISCONNECT_GENERIC_REFUSAL_KEY);

function json(body: unknown, status = 200): Response {
  return new Response(body === null ? "" : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** `A-11340 · Northwind Mfg.`, as `GET /accounts/{id}` really serves it. */
const ACCOUNT_ROW = {
  id: ACCOUNT,
  account_no: "A-11340",
  customer_no: "C-0140",
  name: "Northwind Mfg.",
  unit_id: "unit-77",
  unit_label: "77 Industrial Way",
  premise: "77 Industrial Way",
  services: ["electric", "water"],
  balance: "8240.0000",
  balance_currency: "USD",
  balance_unavailable: [],
  currency: "USD",
  status: "active",
  status_name: "Active",
  status_behavior_class: "billable",
  kind: "regular",
  account_type: "commercial",
  autopay: false,
  opened_at: "2021-03-01",
  closed_at: null,
  contacts: [],
};

/**
 * `_as_catalog_refusal`'s envelope, byte for byte as the route answers it.
 *
 * ⚠ **`detail` IS INCLUDED ON PURPOSE AND NO CASE ASSERTS IT ON SCREEN.**
 * `BR-SHL-020` r2 strips it before i18next sees it; a fixture that left it out
 * could not prove that, and the one thing this file must never let back in is
 * engineering prose reaching a clerk.
 */
function refusal(code: string | null, detail: string) {
  return json(
    {
      code: "BIZ-COMPLETENESS",
      message_key: "customers.disconnects.refused",
      params: code === null ? { detail } : { detail, code },
      field_errors: [],
      br_ref: "BR-CUS-039",
      trace_id: "2fa50006aa1c4f0e9d3b7c2e5a8f10b4",
    },
    422,
  );
}

interface Options {
  /** What `POST /disconnects/schedule` answers. */
  commitRefusal?: { code: string | null; detail: string };
  /** What `GET /accounts/{id}/ladder` carries under `schedule_readiness`. */
  preflight?: { code: string; br_ref: string; detail: string } | null;
  /** Older builds serve no `schedule_readiness` at all — see the case below. */
  omitReadiness?: boolean;
  step?: number;
}

function mount(options: Options = {}) {
  const posted: string[] = [];
  const client = createApiClient({
    tenant: TENANT,
    fetchImpl: async (input, init) => {
      const url = String(input);
      const method = (init?.method ?? "GET").toUpperCase();
      const path = url.split("?")[0];
      if (method === "POST" && path.endsWith("/disconnects/schedule")) {
        posted.push(url);
        const answer = options.commitRefusal;
        return answer === undefined
          ? json({ case_id: "case-1" }, 201)
          : refusal(answer.code, answer.detail);
      }
      if (path.endsWith("/ladder")) {
        const readiness =
          options.preflight === undefined || options.preflight === null
            ? { account_id: ACCOUNT, as_of: "2026-09-28", ready: true, blockers: [], refusal: null }
            : {
                account_id: ACCOUNT,
                as_of: "2026-09-28",
                ready: false,
                blockers: [options.preflight],
                refusal: options.preflight,
              };
        const body: Record<string, unknown> = {
          account_id: ACCOUNT,
          runs: true,
          halt_code: null,
          detail: "the ladder runs",
          tier: "TIER 3 · 48-HOUR",
          next_tier: null,
          balance: { stored: "8240.0000", display: "8,240.00", currency: "USD" },
          sequence: "service",
          scheduler: { advances_on_a_schedule: false, tracks: "", detail: "" },
          case: null,
          case_no: "DSC-26-0001",
        };
        if (options.omitReadiness !== true) {
          body.schedule_readiness = readiness;
        }
        return json(body);
      }
      if (path.endsWith(`/accounts/${ACCOUNT}`)) {
        return json(ACCOUNT_ROW);
      }
      if (path.endsWith("/reconnection-terms")) {
        // ⚠ **THE REAL SHAPE, NOT AN EMPTY PAGE.** Step 4 reads
        // `terms.deposit.on_file`, so a `{count: 0, results: []}` fallback
        // throws inside `ConfirmStep` and the commit button never renders —
        // a fixture that cannot show the screen cannot prove anything about
        // it (law 7's *looking at the wrong thing*).
        return json({
          account_id: ACCOUNT,
          charge_code: "RECON",
          fee: null,
          fee_absence: { code: "reconnect_charge_code_not_seeded" },
          fees: [],
          to_clear: {
            arrears: { stored: "8240.0000", display: "8,240.00" },
            arrears_absence: null,
            fee: null,
            total: null,
            total_absence: { code: "reconnection_total_not_computable" },
          },
          deposit: {
            on_file: { stored: "500.0000", display: "500.00" },
            election: null,
            new_deposit_required: null,
            detail: "",
            posting: { code: "deposit_application_not_posted" },
          },
          posting: { code: "fee_posted" },
          timing: { code: "fee_timing_ruled" },
        });
      }
      if (path.endsWith("/protections")) {
        return json({
          account_id: ACCOUNT,
          as_of: "2026-09-28",
          checks: [],
          all_clear: true,
          protections_in_force: [],
        });
      }
      return json({ count: 0, next: null, previous: null, results: [] });
    },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.shellDisplay, shellBootSeed(SEEDED_REGIONAL));
  queryClient.setQueryData(queryKeys.regionalSettings, SEEDED_REGIONAL);
  const search = `?step=${options.step ?? 4}&account=${ACCOUNT}`;
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}${DISCONNECT_WIZARD_ROUTE}${search}`]}>
          <Routes>
            {/* ⚠ THE REAL PATTERN, so `useParams().tenant` resolves. */}
            <Route path={`/:tenant${DISCONNECT_WIZARD_ROUTE}`} element={<DisconnectWizard client={client} />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { posted };
}

/** Press `Schedule the disconnection ✓` and wait for the failure card. */
async function commitAndReadTheRefusal(): Promise<string> {
  const user = userEvent.setup();
  const button = await screen.findByRole("button", {
    name: (name) => name.includes("Schedule the disconnection"),
  });
  await user.click(button);
  const card = await screen.findByRole("alert");
  await waitFor(() => {
    expect(card.querySelector(".state-failed-reason")).not.toBeNull();
  });
  return card.querySelector(".state-failed-reason")?.textContent ?? "";
}

// ══════════════════════════════════════════════════════════════════════════
// 1 · THE REASON REACHES THE CLERK — one case per code
// ══════════════════════════════════════════════════════════════════════════

/**
 * The six `DEF-CUS-7680` names, each with the sentence a clerk must now read.
 *
 * ⚠ **THE EXPECTED STRINGS ARE THE CATALOGUE'S, LOOKED UP BY KEY.** Spelling
 * them out here would make this file a second copy of the copy, and the two
 * would drift the first time a sentence is shortened. What the case asserts is
 * the LINK — that this code selects that key — plus the two properties that
 * make the fix real: the sentence is not the generic line, and the six are not
 * all the same sentence.
 */
const SIX = [
  ["no_open_case", "there is no open disconnect case on this account to schedule a cut for."],
  [
    "cut_before_final_tier",
    "a cut is scheduled after TIER 3 · 48-HOUR, the certified final notice (BR-CUS-039…). This case is at 'TIER 1 · REMINDER'.",
  ],
  ["already_cut", "this account was already cut on 2026-09-14, so there is no cut left to schedule."],
  [
    "collections_sequence_cannot_cut",
    "this is a COLLECTIONS sequence and it cannot reach a cut. BR-CUS-082 (PO 2026-08-24, closing OQ-346)…",
  ],
  ["cut_reason_unknown", "'because' is not one of the five reasons `DSC-02.1` draws for cutting service…"],
  [
    "deposit_disposition_unknown",
    "'spend_it' is not one of the two things `DSC-02.4` offers to do with a deposit…",
  ],
] as const;

describe("DEF-CUS-7680 · the refusal the server sent reaches the clerk", () => {
  for (const [code, detail] of SIX) {
    it(`step 4 · \`${code}\` renders ITS OWN sentence, not the generic line`, async () => {
      mount({ commitRefusal: { code, detail } });
      const shown = await commitAndReadTheRefusal();

      const expected = t(`customers.disconnectRecord.refused.${code}`);
      expect(shown).toBe(expected);
      expect(shown).not.toBe(GENERIC);

      // ⚠ **B14 rule 32, ASSERTED AND NOT ASSUMED.** `CR-125-BRC07` put the
      // Python keyword `cut_on` on this very screen through an interpolated
      // `{{field}}`; handing a screen a code to branch on is one careless
      // template literal away from printing `cut_before_final_tier` at a
      // billing clerk.
      expect(shown).not.toContain(code);
      expect(shown).not.toContain("BR-CUS");
      // ⚠ **AND THE SERVER'S OWN PROSE STAYS OFF THE SCREEN** — BR-SHL-020 r2.
      expect(shown).not.toContain("DSC-02");
      expect(shown.length).toBeLessThan(detail.length);
    });
  }

  it("the six do not collapse to one sentence — which is the whole defect", async () => {
    const seen = new Set<string>();
    for (const [code] of SIX) {
      seen.add(t(`customers.disconnectRecord.refused.${code}`));
    }
    // `collections_sequence_cannot_cut` and `account_closed_cannot_cut` share
    // *"This account is closed."* deliberately — BR-CUS-082's two grounds are
    // one fact to a clerk — so six codes are five sentences and that is right.
    expect(seen.size).toBeGreaterThanOrEqual(5);
    expect(seen.has(GENERIC)).toBe(false);
  });

  it("an UNMAPPED code falls back to the generic line, never to a blank", async () => {
    // A refusal this front end has no sentence for must still say something
    // true. `DEF-320` is the row where an empty line was chosen over a
    // readable one and cost a support cycle.
    mount({
      commitRefusal: { code: "a_rule_nobody_has_written_yet", detail: "something new" },
    });
    expect(await commitAndReadTheRefusal()).toBe(GENERIC);
  });

  it("a refusal carrying NO code at all falls back the same way", async () => {
    mount({ commitRefusal: { code: null, detail: "something old" } });
    expect(await commitAndReadTheRefusal()).toBe(GENERIC);
  });

  it("every code the schedule can raise has a sentence of its own in en.json", () => {
    // ⚠ **THE LIST IS THE ONE IN `disconnectRefusal.ts`, MEASURED OFF
    // `schedule_cut`'s CALL GRAPH — eighteen, not the six the report named.**
    // A code with no key would render the generic line silently, which is the
    // defect surviving in miniature; this is the only check that can see it
    // from this side of the wire.
    const catalogue = en as Record<string, string>;
    const missing = DISCONNECT_SCHEDULE_REFUSAL_CODES.filter(
      (code) => catalogue[`customers.disconnectRecord.refused.${code}`] === undefined,
    );
    expect(missing).toEqual([]);
  });

  it("every one of those sentences obeys B14 rule 33 — six words, two sentences", () => {
    // G33 walks the keys a SERVER refusal resolves to, and these are looked up
    // by a screen, so the gate does not reach them. The rule still binds, and
    // this is what makes it bind.
    const catalogue = en as Record<string, string>;
    const over: string[] = [];
    for (const code of DISCONNECT_SCHEDULE_REFUSAL_CODES) {
      const value = catalogue[`customers.disconnectRecord.refused.${code}`] ?? "";
      const sentences = value
        .split(/(?<=[.!?])\s+/)
        .map((part) => part.trim())
        .filter((part) => part !== "");
      const longest = Math.max(...sentences.map((part) => part.split(/\s+/).length));
      if (longest > 6 || sentences.length > 2) {
        over.push(`${code} = ${value}`);
      }
    }
    expect(over).toEqual([]);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 2 · STEP 1 REFUSES EARLY — four steps are not spent on a case that cannot go
// ══════════════════════════════════════════════════════════════════════════

const KNOWABLE = [
  "no_open_case",
  "already_cut",
  "collections_sequence_cannot_cut",
  "cut_before_final_tier",
] as const;

describe("DEF-CUS-7680 · step 1 says it, instead of costing four steps", () => {
  for (const code of KNOWABLE) {
    it(`step 1 · \`${code}\` is shown the moment the account is chosen`, async () => {
      mount({
        step: 1,
        preflight: { code, br_ref: "BR-CUS-039", detail: "engineering prose" },
      });
      const strip = await waitFor(() => {
        const found = document.body.querySelector(`[data-preflight="${code}"]`);
        expect(found).not.toBeNull();
        return found as HTMLElement;
      });
      expect(strip.textContent).toBe(t(`customers.disconnectRecord.refused.${code}`));
      // The server's prose does not travel onto the screen with the code.
      expect(strip.textContent).not.toContain("engineering prose");
      expect(strip.getAttribute("role")).toBe("alert");
    });
  }

  it("`Continue` does not move the clerk on, and says the same sentence", async () => {
    mount({ step: 1, preflight: { code: "no_open_case", br_ref: "BR-CUS-039", detail: "x" } });
    const user = userEvent.setup();
    await waitFor(() => {
      expect(document.body.querySelector('[data-preflight="no_open_case"]')).not.toBeNull();
    });
    await user.click(await screen.findByRole("button", { name: /continue/i }));
    // Still on step 1: the `Choose` step's own content is still mounted.
    await waitFor(() => {
      expect(document.body.querySelector('[data-step="choose"]')).not.toBeNull();
    });
    // …and the reason is on screen, from the same map the commit uses.
    expect(document.body.textContent).toContain(
      t("customers.disconnectRecord.refused.no_open_case"),
    );
  });

  it("a ready case draws NO refusal and lets the clerk through", async () => {
    // ⚠ **THE SECOND DIRECTION, AND IT IS WHAT KEEPS THIS FROM BECOMING A WALL.**
    // A pre-flight that refused everything would stop every disconnection in
    // the product and would still pass a suite that only asserted refusals —
    // law 7's *incapable of passing*, one screen up.
    mount({ step: 1, preflight: null });
    await screen.findByText("Northwind Mfg.", { exact: false });
    expect(document.body.querySelector("[data-preflight]")).toBeNull();
  });

  it("a build that serves no readiness at all lets the clerk through", async () => {
    // Hard-won law 3 pointing the other way: here the UNSAFE option is
    // refusing. An absent key is *not asked*, never *not allowed*, and the
    // commit is the guard that always runs.
    mount({ step: 1, omitReadiness: true });
    await screen.findByText("Northwind Mfg.", { exact: false });
    expect(document.body.querySelector("[data-preflight]")).toBeNull();
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 3 · THE COMMIT STILL REFUSES — the screen decides nothing
// ══════════════════════════════════════════════════════════════════════════

describe("DEF-CUS-7680 · the pre-flight is a preview and the commit is the guard", () => {
  it("a ready pre-flight does NOT stop the server refusing at step 4", async () => {
    // ⚠ **A SCREEN THAT DECIDED ELIGIBILITY FOR ITSELF WOULD BE THE NEXT
    // DEFECT.** Days pass between step 1 and the button, and a case can be
    // stopped, paid or cut in between. This proves the two halves were not
    // traded for each other: the pre-flight says ready, the commit refuses,
    // and the clerk reads the commit's reason.
    mount({
      preflight: null,
      commitRefusal: { code: "protected", detail: "the ladder is FROZEN by a protection in force" },
    });
    expect(await commitAndReadTheRefusal()).toBe(
      t("customers.disconnectRecord.refused.protected"),
    );
  });

  it("the commit is still attempted — the screen does not short-circuit it", async () => {
    const { posted } = mount({
      commitRefusal: { code: "no_open_case", detail: "no case" },
    });
    await commitAndReadTheRefusal();
    expect(posted).toHaveLength(1);
    expect(posted[0]).toContain("/disconnects/schedule");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-CUS-7680 (MAINTENANCE — 12-governance/22-product-maintenance-
//         process.md). Reproduced in a browser and at the API against real
//         PostgreSQL 16 before a line of code was read.
// generated: 2026-09-28 by lane DSC-WIZARD-REFUSAL
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// exceptions:
//   E3 **THE CATALOGUE IS THE EXPECTED VALUE, NOT A LITERAL.** Spelling the
//      sentences out here would be a second copy of the copy. What is pinned
//      is the LINK (this code selects that key), that the sentence is not the
//      generic line, and that the six are not one sentence.
//   E1 ⛔ **A SERVER CODE ABSENT FROM `DISCONNECT_SCHEDULE_REFUSAL_CODES` IS
//      INVISIBLE TO THE CATALOGUE CASE ABOVE** — the list is measured by hand
//      off `schedule_cut`'s call graph, so a NEW refusal degrades to the
//      generic line and nothing on this side of the wire can see it. The
//      server suite holds the contract that the code is published; nothing
//      holds the contract that the list is complete. REPORTED.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
