// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-150-BRC09 · the New Connect BUILD DETAIL page — tasks 4, 5, 13.
// Rules:    CLAUDE.md hard-won law 2 (built is not wired — and its MIRROR, a
//           live screen behind a dead control) · law 6 (no gate reads
//           rendered output, so this is the only instrument that can see a
//           tab strip) · B14 rule 31 · rule 33 · rule 37 (no figure from a
//           PNG is asserted anywhere below).
// ───────────────────────────────────────────────────────
//
// WHAT WOULD MAKE THESE PASS WRONGLY (law 7, habit 2)
// ---------------------------------------------------
// * **Mounting the page outside its route.** A bare `MemoryRouter` with no
//   `/:tenant/connections/:connectionId` leaves `useParams().tenant`
//   undefined, so every address the page builds comes out `//connections/…` —
//   a protocol-relative URL to another host, which reads as a perfectly good
//   string to `toContain`. That fixture fault is how a whole portal front page
//   shipped with two working doors out of eight. **Every mount below uses the
//   real path pattern, and the tab assertions compare the WHOLE href against
//   the tenant-scoped address** rather than asking whether it contains a word.
// * **Asserting a tab by the component it renders.** A tab is an ADDRESS and a
//   SCREEN, so each case below reads `data-screen` and the `href`.
// * **Asserting a menu item is disabled without reading its REASON.** A
//   hardcoded `disabled` passes that; the cases read
//   `data-blocked-reason`, which can only come from `actBlockedReason`.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { BuildDetailPage } from "./BuildDetailPage";
import {
  BUILD_ID,
  PREMISES_ID,
  TENANT,
  buildDetailFixture,
  buildRecordFixture,
  premisesBuildFixture,
} from "./buildDetailFixture";
import type { ConnectionDetail } from "./newConnectEndpoints";
import { NEW_CONNECT_STEPS } from "./newConnectShared";

function mount(
  options: { detail?: ConnectionDetail; tab?: string; premisesAccess?: string } = {},
) {
  const urls: string[] = [];
  const detail = options.detail ?? buildDetailFixture();
  const client = createApiClient({
    tenant: TENANT,
    fetchImpl: async (input: RequestInfo | URL) => {
      const url = String(input);
      urls.push(url);
      const json = (body: unknown) =>
        new Response(JSON.stringify(body), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      // ⊕ `DEF-MET-9238` — the caller's own A4 row, the server's shape.
      if (url.includes("/me/permissions")) {
        const access = options.premisesAccess ?? "Full";
        return json({
          role: access === "Full" ? "billing_clerk" : "executive",
          role_name: access === "Full" ? "Billing Clerk" : "Executive",
          permissions: [
            {
              code: "premises_accounts",
              label: "Premises / Accounts",
              access,
            },
          ],
        });
      }
      // ⚠ THE RECORD FIRST: `/connections/{id}/record` also matches
      // `/connections/{id}`, and answering the detail to both would make every
      // assertion below read the wrong payload.
      if (url.includes(`/connections/${BUILD_ID}/record`)) {
        return json(buildRecordFixture());
      }
      if (url.includes(`/premises/${PREMISES_ID}/build`)) {
        return json({ build: premisesBuildFixture() });
      }
      if (url.includes(`/connections/${BUILD_ID}`)) {
        return json(detail);
      }
      if (url.includes("/wizard-parks")) {
        return json({ count: 0, results: [] });
      }
      // ⚠ **A BARE ARRAY, BECAUSE THAT IS WHAT THE ROUTE ANSWERS.** A fixture
      // that answered an envelope here crashed the page in `enabledServiceRows`
      // — the first RED this suite produced, and a real reminder that a stub
      // shaped unlike the server proves nothing about the server.
      if (url.includes("/settings/services")) {
        return json([]);
      }
      return json({ count: 0, results: [], rows: [], methods: [] });
    },
  });
  const entry = `/${TENANT}/connections/${BUILD_ID}${
    options.tab === undefined ? "" : `?tab=${options.tab}`
  }`;
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <ToastProvider>
        <MemoryRouter initialEntries={[entry]}>
          <Routes>
            <Route
              path="/:tenant/connections/:connectionId"
              element={<BuildDetailPage client={client} timeZone="UTC" dateFormat="MM/DD/YYYY" />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return urls;
}

const TAB_IDS = ["overview", "units", "work", "charges", "documents", "messages", "audit"];

describe("CR-150-BRC09 · the build page's shell (task 4)", () => {
  afterEach(cleanup);

  it("carries its screen id, so a reader and a walkthrough name the same screen", async () => {
    mount();
    await waitFor(() =>
      expect(document.querySelector('[data-screen="NCT-02"]')).not.toBeNull(),
    );
  });

  it("the kicker is the two BUSINESS numbers and never a database id (rule 31)", async () => {
    mount();
    const detail = buildDetailFixture();
    await waitFor(() =>
      expect(screen.getByText(`${detail.connection_no} · ${detail.request_no}`)).toBeInTheDocument(),
    );
    // The uuid never reaches the page's text.
    expect(document.body.textContent).not.toContain(BUILD_ID);
  });

  it("DEF-MET-9649: a one-unit build reads `1 unit`, never `1 units`", async () => {
    mount({ detail: { ...buildDetailFixture(), units: 1 } });
    await waitFor(() =>
      expect(document.querySelector('[data-screen="NCT-02"]')).not.toBeNull(),
    );
    await waitFor(() => expect(document.body.textContent).toContain("1 unit"));
    expect(document.body.textContent).not.toContain("1 units");
    // …and the word comes from the catalogue, not a default baked into the page.
    expect(i18n.exists("customers.build.rollup.units_one")).toBe(true);
    expect(i18n.exists("customers.build.rollup.raised")).toBe(true);
  });

  it("the title is the premise NAME, because that is what people call the build", async () => {
    mount();
    await waitFor(() =>
      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Cedar Court"),
    );
  });

  it("the `←` exits to the list it came from (B14 rule 1)", async () => {
    mount();
    await waitFor(() => expect(screen.getByText(/New connects/)).toBeInTheDocument());
    const back = document.querySelector(".page-header-back") as HTMLAnchorElement | null;
    // THE WHOLE ADDRESS, tenant-scoped. `toContain` would pass on `//accounts…`.
    expect(back?.getAttribute("href")).toBe(`/${TENANT}/accounts?tab=new-connects`);
  });

  it("all seven tabs are addresses under THIS build, tenant-scoped", async () => {
    mount();
    await waitFor(() => expect(document.querySelector("[data-page-header-tabs]")).not.toBeNull());
    for (const id of TAB_IDS) {
      const tab = document.querySelector(`[data-tab="${id}"]`) as HTMLAnchorElement | null;
      expect(tab, `tab ${id} is missing`).not.toBeNull();
      expect(tab?.getAttribute("href")).toBe(
        `/${TENANT}/connections/${BUILD_ID}?tab=${id}`,
      );
    }
  });

  it("has NO Open premises and NO Open account button — the PO removed both", async () => {
    mount();
    await waitFor(() => expect(document.querySelector(".page-header-actions")).not.toBeNull());
    const actions = document.querySelector(".page-header-actions") as HTMLElement;
    expect(actions.textContent).not.toMatch(/Open premises/i);
    expect(actions.textContent).not.toMatch(/Open account/i);
  });
});

describe("CR-150-BRC09 · the More menu (task 5)", () => {
  afterEach(cleanup);

  // ⚠ **CR-162-BRC10 (PO 2026-10-02, Q3): *"a To-do tab replaces Mark/Close
  // outstanding; Release → Resume"*, and item 7 adds *Add unit*.** So the menu
  // holds SIX acts in THREE groups now; the To-do tab adds, completes and
  // reopens the to-dos the two retired acts used to.
  it("holds the SIX acts, in three groups, Resume for Release, with Cancel build last", async () => {
    mount();
    await waitFor(() => expect(document.querySelector("[data-build-more]")).not.toBeNull());
    const panel = document.querySelector("[data-build-more-panel]") as HTMLElement;
    const acts = Array.from(panel.querySelectorAll("[data-act]")).map((el) =>
      el.getAttribute("data-act"),
    );
    expect(acts).toEqual(["hold", "release", "waitingOn", "addUnit", "addService", "cancel"]);
    const groups = Array.from(panel.querySelectorAll("[data-build-menu-group]")).map((el) =>
      el.getAttribute("data-build-menu-group"),
    );
    expect(groups).toEqual(["move", "change", "end"]);
    expect(panel.querySelector('[data-act="release"]')?.textContent).toContain("Resume");
  });

  it("the primary act is Raise order, and it is NOT in the menu", async () => {
    mount();
    await waitFor(() => expect(document.querySelector('[data-act="raiseOrder"]')).not.toBeNull());
    const panel = document.querySelector("[data-build-more-panel]") as HTMLElement;
    expect(panel.querySelector('[data-act="raiseOrder"]')).toBeNull();
    const primary = document.querySelector('[data-act="raiseOrder"]') as HTMLButtonElement;
    expect(primary.getAttribute("data-variant")).toBe("primary");
  });

  it("Raise order OPENS A FORM and posts nothing on the press (DEF-CUS-9177)", async () => {
    const urls = mount();
    await waitFor(() => expect(document.querySelector('[data-act="raiseOrder"]')).not.toBeNull());
    const primary = document.querySelector('[data-act="raiseOrder"]') as HTMLButtonElement;
    await waitFor(() => expect(primary.disabled).toBe(false));
    fireEvent.click(primary);
    await waitFor(() => expect(document.getElementById("build-raise-template")).not.toBeNull());
    expect(document.getElementById("build-raise-unit")).not.toBeNull();
    expect(document.getElementById("build-raise-date")).not.toBeNull();
    // The old press POSTed `type: "Meter set"` straight away; the form posts
    // only on its own submit.
    expect(urls.filter((url) => url.endsWith("/work-orders"))).toHaveLength(0);
  });

  it("a disabled item carries a REAL reason from the shared check, never a hardcoded false", async () => {
    // This build is NOT on hold, so `Release` is refused — by
    // `actBlockedReason`, which is the SERVER's own rule restated.
    mount();
    await waitFor(() => expect(document.querySelector('[data-act="release"]')).not.toBeNull());
    const release = document.querySelector('[data-act="release"]') as HTMLButtonElement;
    expect(release.disabled).toBe(true);
    expect(release.getAttribute("data-blocked-reason")).toBe("This build is not on hold.");
    // …and the one that CAN act is live, which is the other half: a menu where
    // everything is disabled would pass the assertion above and be useless.
    const hold = document.querySelector('[data-act="hold"]') as HTMLButtonElement;
    expect(hold.disabled).toBe(false);
    expect(hold.getAttribute("data-blocked-reason")).toBeNull();
  });

  it("DEF-MET-9238 · a role that only VIEWS Premises / Accounts gets every act refused WITH its reason", async () => {
    // The walk's Executive was offered live Approve, Raise order and More, and
    // every press met a 403. The reason is read off each control, so a
    // hardcoded `disabled` cannot pass this.
    const reason = "Your role can view this but not change it.";
    mount({ premisesAccess: "View" });
    await waitFor(() =>
      expect(
        document.querySelector('[data-act="raiseOrder"]')?.getAttribute("data-blocked-reason"),
      ).toBe(reason),
    );
    for (const act of ["raiseOrder", "approve", "hold", "waitingOn", "addUnit", "addService", "cancel"]) {
      const item = document.querySelector(`[data-act="${act}"]`) as HTMLButtonElement;
      expect(item.disabled, `${act} should be refused`).toBe(true);
      expect(item.getAttribute("data-blocked-reason"), act).toBe(reason);
    }
  });

  it("DEF-MET-9238 · a role with Full Premises / Accounts keeps its acts", async () => {
    mount({ premisesAccess: "Full" });
    await waitFor(() => expect(document.querySelector('[data-act="hold"]')).not.toBeNull());
    await waitFor(() =>
      expect((document.querySelector('[data-act="raiseOrder"]') as HTMLButtonElement).disabled).toBe(
        false,
      ),
    );
    const hold = document.querySelector('[data-act="hold"]') as HTMLButtonElement;
    expect(hold.disabled).toBe(false);
    expect(hold.getAttribute("data-blocked-reason")).toBeNull();
  });

  it("a CANCELLED build refuses every act, each with the reason the server would give", async () => {
    mount({ detail: buildDetailFixture({ state: "cancelled" }) });
    await waitFor(() => expect(document.querySelector('[data-act="hold"]')).not.toBeNull());
    for (const act of ["hold", "release", "waitingOn", "addService", "cancel"]) {
      const item = document.querySelector(`[data-act="${act}"]`) as HTMLButtonElement;
      expect(item.disabled, `${act} should be refused`).toBe(true);
      expect(item.getAttribute("data-blocked-reason")).toBe("This build is canceled.");
    }
  });

  it("Cancel build is the danger tier and nothing else is (B14 rule 6)", async () => {
    mount();
    await waitFor(() => expect(document.querySelector('[data-act="cancel"]')).not.toBeNull());
    const cancel = document.querySelector('[data-act="cancel"]') as HTMLElement;
    expect(cancel.className).toContain("text-danger-700");
    const hold = document.querySelector('[data-act="hold"]') as HTMLElement;
    expect(hold.className).not.toContain("text-danger-700");
  });
});

describe("CR-150-BRC09 · the draft variant (task 13)", () => {
  afterEach(cleanup);

  const draft = () =>
    buildDetailFixture({
      state: "draft",
      // A draft raised directly has no request behind it (`BR-MET-1178` —
      // provenance, never a dependency).
      request_no: null,
    });

  it("keeps the same tab bar, and the four with nothing behind them are NOT addresses", async () => {
    mount({ detail: draft() });
    await waitFor(() => expect(document.querySelector("[data-page-header-tabs]")).not.toBeNull());
    for (const id of TAB_IDS) {
      const tab = document.querySelector(`[data-tab="${id}"]`);
      expect(tab, `tab ${id} must still be SHOWN`).not.toBeNull();
    }
    for (const id of ["units", "work", "charges", "messages"]) {
      expect(
        document.querySelector(`[data-tab="${id}"]`)?.getAttribute("href"),
        `${id} must not be selectable on a draft`,
      ).toBeNull();
    }
    for (const id of ["overview", "documents", "audit"]) {
      expect(document.querySelector(`[data-tab="${id}"]`)?.getAttribute("href")).toBe(
        `/${TENANT}/connections/${BUILD_ID}?tab=${id}`,
      );
    }
  });

  it("the primary act is Carry on, and it opens the wizard ON THIS BUILD", async () => {
    mount({ detail: draft() });
    await waitFor(() => expect(document.querySelector('[data-act="carryOn"]')).not.toBeNull());
    const carryOn = document.querySelector('[data-act="carryOn"]') as HTMLAnchorElement;
    expect(carryOn.getAttribute("href")).toBe(
      `/${TENANT}/connections/new?build=${BUILD_ID}`,
    );
  });

  it("its menu is Re-park and Cancel build, and nothing else", async () => {
    mount({ detail: draft() });
    await waitFor(() => expect(document.querySelector("[data-build-more-panel]")).not.toBeNull());
    const panel = document.querySelector("[data-build-more-panel]") as HTMLElement;
    const acts = Array.from(panel.querySelectorAll("[data-act]")).map((el) =>
      el.getAttribute("data-act"),
    );
    expect(acts).toEqual(["repark", "cancel"]);
  });

  it("draws the answered-so-far groups from the ONE declared step list (BR-SHL-046)", async () => {
    mount({ detail: draft() });
    await waitFor(() =>
      expect(document.querySelector('[data-build-section="answered"]')).not.toBeNull(),
    );
    const groups = Array.from(document.querySelectorAll("[data-draft-group]")).map((el) =>
      el.getAttribute("data-draft-group"),
    );
    // ⊕ **AMENDED 2026-09-29 (`ed4e7cb30`, `CR-150-BRC09`).** This line read
    // EIGHT and justified it *"never the five a wireframe drew, which B14 rule
    // 37 makes an illustration"* — correct when written, and superseded by a
    // PO ruling of 2026-09-28 that took the five-step redesign as the
    // specification: *"we dont want any information to be reduced or lost - 8
    // steps → 5"*. That is rule 41's own named exception — a drawing the PO has
    // ruled on directly — and `newConnectShared.tsx` writes the whole chain
    // out. **The reasoning was not wrong about rule 37; it was outlived.**
    //
    // ⚠ **THE LIST IS READ FROM THE CONSTANT NOW, WHICH IS WHAT THE CASE'S OWN
    // TITLE ASKS.** `BR-SHL-046` is *one declared step list*; typing the ids
    // here made this file a SECOND declaration, and a second declaration is
    // what went stale today. The literal is kept BESIDE it rather than
    // dropped, so a silent reshape of the flow still goes red and names
    // itself to a human instead of quietly agreeing with whatever the
    // constant now says.
    expect(groups).toEqual(NEW_CONNECT_STEPS.map((step) => step.id));
    expect(groups).toEqual(["customer", "premise", "units", "charges", "review"]);
  });

  it("a draft asks for NO account and NO record-derived account link", async () => {
    mount({ detail: draft() });
    await waitFor(() =>
      expect(document.querySelector('[data-build-section="answered"]')).not.toBeNull(),
    );
    // Nothing on a draft page claims an account exists.
    expect(document.body.textContent).not.toContain("AC-26-0088");
  });
});
