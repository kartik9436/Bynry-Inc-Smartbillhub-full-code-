// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-089 wave D — D1 (`PUJ-21`) and D2 (`PUJ-48`)
// Screens: PRM-02 header (S14) · PRM-03 header (S15)
// Rules:   BR-MET-1164 (the refusal NAMES what is blocking, and every count
//          links to the list that clears it) · B14 rule 6 (danger tier) ·
//          B14 rule 11 (a consequence preview) · B14 rule 33 (a refusal caps
//          at five or six words and says what to do)
// ───────────────────────────────────────────────────────
// ⚠ **MOUNTED UNDER THE REAL PATH PATTERN, NOT BARE IN A `MemoryRouter`**
// (hard-won law 2). Every link this dialog draws is built from
// `useParams().tenant`; a fixture with no `/:tenant/…` route leaves that
// undefined and every address comes out `//premises/…` — a protocol-relative
// URL to another host, which reads as a perfectly good string to `toContain`.
// That is exactly how the portal front page's eight dead doors hid.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createApiClient } from "@/api/client";
import type { StatusChangeView } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { StatusChangeDialog, statusChangeQueryKey } from "./StatusChangeDialog";

const TENANT = "brazosbend";
const PREMISES = "p-101";

/** The server's answer for a building with everything still live on it —
 *  CR-089 §6 D1's own figures. */
function blockedPremises(): StatusChangeView {
  return {
    entity: "premises",
    id: PREMISES,
    status: "active",
    target_status: "inactive",
    blocked: true,
    held_by: "open_accounts",
    dependencies: [
      {
        kind: "open_accounts",
        count: 3,
        blocking: true,
        link: { route: "premises_units", premises_id: PREMISES },
      },
      {
        kind: "unpaid_balances",
        count: 0,
        blocking: true,
        link: { route: "premises_units", premises_id: PREMISES },
      },
      {
        kind: "attached_assets",
        count: 9,
        blocking: true,
        link: { route: "premises_assets", premises_id: PREMISES },
      },
      {
        kind: "active_units",
        count: 4,
        blocking: true,
        link: { route: "premises_units", premises_id: PREMISES },
      },
    ],
  };
}

function clearPremises(): StatusChangeView {
  const view = blockedPremises();
  return {
    ...view,
    blocked: false,
    held_by: null,
    dependencies: view.dependencies.map((row) => ({ ...row, count: 0 })),
  };
}

function blockedUnit(): StatusChangeView {
  return {
    entity: "unit",
    id: "u-101a",
    status: "active",
    target_status: "inactive",
    blocked: true,
    held_by: "open_accounts",
    dependencies: [
      {
        kind: "open_accounts",
        count: 1,
        blocking: true,
        // ⚠ **A FIXTURE NUMBER, NOT THE FRAME'S.** B14 rule 37 (PO
        // 2026-09-10): *"Treat every number drawn in a wireframe as an
        // illustration, never a fact to build to."* The frame draws
        // `A-10517`; what this asserts is that whatever the server sends
        // reaches the row, so the fixture uses its own.
        reference: "A-90001",
        link: { route: "unit_account", unit_id: "u-101a" },
      },
      {
        kind: "unpaid_balances",
        count: 0,
        blocking: true,
        link: { route: "unit_account", unit_id: "u-101a" },
      },
      {
        kind: "attached_assets",
        count: 2,
        blocking: false,
        link: { route: "unit_assets", unit_id: "u-101a" },
      },
    ],
  };
}

/** Every request this dialog makes, in order — so a test can assert that a
 *  press posted NOTHING as easily as that it posted the right thing. */
interface Call {
  url: string;
  method: string;
  body: string;
}

function mount(
  subject: "premises" | "unit",
  view: StatusChangeView,
  options: { calls?: Call[]; postResponse?: () => Response } = {},
) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(statusChangeQueryKey(subject, view.id), view);
  // ⚠ THE SEEDED ANSWER IS RE-READ, NOT TRUSTED. The dialog asks for the counts
  // with `staleTime: 0` on purpose (BR-MET-1164 refuses on LIVE dependencies),
  // so a fixture that only seeds the cache is serving a payload the component
  // immediately replaces — which is how the first draft of this file crashed on
  // `{}`. The fake server answers the read for real.
  const fetchImpl = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = String(init?.method ?? "GET").toUpperCase();
    options.calls?.push({ url, method, body: String(init?.body ?? "") });
    if (method === "GET") {
      // The body IS the payload — this client returns the parsed body as
      // `data`, so an envelope wrapper here would hand the component a shape
      // the server never sends.
      return new Response(JSON.stringify(view), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    return (
      options.postResponse?.() ??
      new Response(JSON.stringify({ id: view.id, status: view.target_status }), {
        status: 200,
        headers: { "content-type": "application/json" },
      })
    );
  };
  const client = createApiClient({ tenant: TENANT, fetchImpl });
  const onChanged = vi.fn();
  const path =
    subject === "premises" ? "/:tenant/premises/:premisesId" : "/:tenant/premises/units/:unitId";
  const entry =
    subject === "premises"
      ? `/${TENANT}/premises/${view.id}`
      : `/${TENANT}/premises/units/${view.id}`;
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[entry]}>
          <Routes>
            <Route
              path={path}
              element={
                <StatusChangeDialog
                  subject={subject}
                  id={view.id}
                  name="412 Cypress Row"
                  client={client}
                  timeZone="America/Chicago"
                  dateFormat="MM/DD/YYYY"
                  onClose={() => undefined}
                  onChanged={onChanged}
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { onChanged };
}

afterEach(cleanup);

describe("CR-089 D1 — a property can be taken out of service", () => {
  it("draws each blocker as a row with a link of its own, and holds the commit", () => {
    mount("premises", blockedPremises());

    // The drawn panel: a heading, then one ROW per blocker. The frame's own
    // words — `NOT WHILE THESE ARE LIVE`.
    expect(screen.getByText("Not while these are live")).toBeInTheDocument();
    const panel = document.querySelector("[data-status-refusal-panel]");
    expect(panel).not.toBeNull();
    expect(panel!.querySelector("[data-plaintable]")).not.toBeNull();

    // CR-089 §6 D1, in the PO's own order. A zero-count row is NOT drawn: the
    // panel says something is holding this, and a nought is not.
    const kinds = [...document.querySelectorAll("[data-dependency]")].map((row) =>
      row.getAttribute("data-dependency"),
    );
    // ⚠ THE ORDER IS `DEPENDENCY_ORDER`'s, WHICH IS NOT `P11`'s DRAWN ORDER.
    // The frame draws units · accounts · meters; this renders units · meters ·
    // accounts. Recorded rather than changed: the premises row order belongs to
    // `CR-089-p041`'s own lane, and this one is here for `U12`.
    expect(kinds).toEqual(["active_units", "attached_assets", "open_accounts"]);

    expect(screen.getByText("4 active units")).toBeInTheDocument();
    expect(screen.getByText("9 attached assets")).toBeInTheDocument();
    expect(screen.getByText("3 open accounts")).toBeInTheDocument();

    // ⚠ THE ADDRESSES ARE ASSERTED IN FULL, tenant segment included. A link
    // built without the tenant comes out `//premises/…` and still contains
    // "premises" — the assertion that cannot fail.
    const links = screen.getAllByRole("link", { name: "Show them →" });
    expect(links.map((link) => link.getAttribute("href"))).toEqual([
      `/${TENANT}/premises/${PREMISES}?tab=units`,
      `/${TENANT}/premises/${PREMISES}?tab=assets`,
      `/${TENANT}/premises/${PREMISES}?tab=units`,
    ]);
    expect(links).toHaveLength(3);

    // B14 rule 33 — four words, and it says what to do.
    const hold = screen.getByText("Close the accounts first");
    expect(hold).toBeInTheDocument();
    expect(hold.textContent!.trim().split(/\s+/)).toHaveLength(4);

    const commit = screen.getByRole("button", { name: "Take out of service" });
    expect(commit).toBeDisabled();
    // B14 rule 6 — the danger tier, computed from the action. Asserted on
    // `data-variant`, which `Button` declares as part of its contract precisely
    // so a test asks about MEANING rather than about a class name CR-018 moved.
    expect(commit).toHaveAttribute("data-variant", "danger");
  });

  it("the three drawn inputs come FIRST, and the refusal panel follows them", () => {
    mount("premises", blockedPremises());

    // The frame's order — `New status`, `From`, `Why`, then the panel that says
    // whether it can be done. It shipped the other way round (`DEF-MET-4763`),
    // so a clerk read the verdict before saying what they were doing.
    // The frame's order — `New status`, `From`, `Why`, then the panel that says
    // whether it can be done. It shipped the other way round (`DEF-MET-4763`),
    // so a clerk read the verdict before saying what they were doing.
    const body = document.querySelector("[data-status-dialog]")!;
    const marks = [
      ...body.querySelectorAll(
        "#status-new, #status-effective-date, #status-reason, [data-status-refusal-panel]",
      ),
    ].map((node) => (node.id === "" ? "refusal-panel" : node.id));
    expect(marks).toEqual([
      "status-new",
      "status-effective-date",
      "status-reason",
      "refusal-panel",
    ]);
  });

  it("the New status field says in words what the record becomes", () => {
    mount("premises", blockedPremises());
    const field = screen.getByLabelText(/New status/) as HTMLSelectElement;
    expect(field.value).toBe("inactive");
    // ONE option: a live place can only go inactive, and a second choice that
    // can only be refused is worse than no choice at all.
    expect([...field.options].map((option) => option.textContent)).toEqual([
      "Inactive — no longer takes service",
    ]);
  });

  it("B14 rule 11 — the consequence REPLACES the refusal, it does not sit beside it", () => {
    mount("premises", blockedPremises());
    // Blocked: the panel, and no consequence at all. Both frames say the two
    // are alternatives, and this screen used to draw them together.
    expect(document.querySelector('[data-consequence="status-change"]')).toBeNull();
    expect(document.querySelector("[data-status-refusal-panel]")).not.toBeNull();

    cleanup();
    mount("premises", clearPremises());
    const box = document.querySelector('[data-consequence="status-change"]');
    expect(box).not.toBeNull();
    expect(box!.textContent).toContain("Billing stops here.");
    expect(box!.textContent).toContain("Units, meters and history stay.");
    expect(document.querySelector("[data-status-refusal-panel]")).toBeNull();
  });

  it("with the blockers clear it still refuses to commit until both answers are given", async () => {
    const user = userEvent.setup();
    const calls: Call[] = [];
    const { onChanged } = mount("premises", clearPremises(), { calls });

    const commit = screen.getByRole("button", { name: "Take out of service" });
    expect(commit).toBeEnabled();

    // Pressing with an empty form posts NOTHING and names both fields.
    await user.click(commit);
    expect(calls.filter((call) => call.method === "POST")).toHaveLength(0);
    expect(screen.getByText("Give the date of the change.")).toBeInTheDocument();
    expect(screen.getByText("Say why this is changing.")).toBeInTheDocument();
    expect(onChanged).not.toHaveBeenCalled();

    await user.type(screen.getByLabelText(/^From/), "2026-09-08");
    await user.type(screen.getByLabelText(/^Why/), "Demolished");
    await user.click(commit);

    const posts = calls.filter((call) => call.method === "POST");
    expect(posts).toHaveLength(1);
    expect(posts[0].url).toContain(`/premises/${PREMISES}/status`);
    expect(JSON.parse(posts[0].body)).toEqual({
      status: "inactive",
      effective_date: "2026-09-08",
      reason: "Demolished",
    });
    expect(onChanged).toHaveBeenCalledWith("inactive");
  });

  it("an already-inactive property offers reactivation, held by nothing", () => {
    const view: StatusChangeView = {
      ...blockedPremises(),
      status: "inactive",
      target_status: "active",
      blocked: false,
      held_by: null,
    };
    mount("premises", view);

    // CR-089 §8: the half the rollback must keep. No counts are drawn — every
    // one of them is a reason not to STOP serving an address, and none is a
    // reason not to start again.
    const commit = screen.getByRole("button", { name: "Put back in service" });
    expect(commit).toBeEnabled();
    expect(commit).toHaveAttribute("data-variant", "primary");
    expect(screen.queryByText("4 active units")).toBeNull();
    // The same two answers are still required.
    expect(screen.getByLabelText(/^From/)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Why/)).toBeInTheDocument();
  });
});

describe("CR-089 D2 — a unit can be taken out of service", () => {
  it("the blocked row NAMES the account, and the assets row is a sentence beside it", () => {
    mount("unit", blockedUnit());

    // The frame draws a NAME here, not a count — `DEF-MET-4763`. The number is
    // the fixture's; what is asserted is that the server's reaches the row.
    expect(screen.getByText("Account A-90001 is still open")).toBeInTheDocument();
    expect(screen.getByText("2 assets are still on this unit")).toBeInTheDocument();

    // One destination is a single record and one is a list, so the two links
    // are not the same word.
    expect(screen.getByRole("link", { name: "Open it →" })).toHaveAttribute(
      "href",
      `/${TENANT}/premises/units/u-101a?tab=account`,
    );
    expect(screen.getByRole("link", { name: "Show them →" })).toHaveAttribute(
      "href",
      `/${TENANT}/premises/units/u-101a?tab=assets`,
    );

    expect(screen.getByText("Not while this is live")).toBeInTheDocument();
    // ⚠ **THE ACCOUNT LEADS, AND THE PROPERTY'S ORDER DOES NOT APPLY HERE.**
    // The `U12` frame draws the open account first and the meters second, which
    // is also the order the work is done in — the account is the only thing
    // that HOLDS the commit. One shared list rendered the unit assets-first
    // until a browser walk read the rows in order (`DEF-MET-4763`).
    expect(
      [...document.querySelectorAll("[data-dependency]")].map((row) =>
        row.getAttribute("data-dependency"),
      ),
    ).toEqual(["open_accounts", "attached_assets"]);
    const hold = screen.getByText("Close the account first");
    expect(hold.textContent!.trim().split(/\s+/)).toHaveLength(4);
    // The drawn commit label, which used to live on the door that recorded
    // nothing (`DEF-MET-4761`).
    expect(screen.getByRole("button", { name: "Deactivate unit" })).toBeDisabled();
  });

  it("an account with no number falls back to the count sentence", () => {
    const view = blockedUnit();
    mount("unit", {
      ...view,
      dependencies: view.dependencies.map((row) =>
        row.kind === "open_accounts" ? { ...row, reference: undefined } : row,
      ),
    });
    expect(screen.getByText("1 account is still open")).toBeInTheDocument();
  });

  it("the server's own refusal is rendered verbatim when the counts moved under us", async () => {
    const user = userEvent.setup();
    const free: StatusChangeView = {
      ...blockedUnit(),
      blocked: false,
      held_by: null,
      dependencies: blockedUnit().dependencies.map((row) =>
        row.kind === "open_accounts" ? { ...row, count: 0 } : row,
      ),
    };
    // ⚠ The screen's counts are a FORECAST; the server re-reads them on the
    // press. A colleague opening an account while this dialog was open is
    // refused HERE, by the server, and the screen says so.
    mount("unit", free, {
      postResponse: () =>
        new Response(
          // The ratified envelope is the body ITSELF (`{code, message_key,
          // params}`), never nested under an `error` key — a shape the client
          // reads as "not the envelope" and answers with the generic sentence.
          JSON.stringify({
            code: "BIZ-STATE",
            message_key: "metering.units.status.holdAccount",
            params: {},
            br_ref: "BR-MET-1164",
          }),
          { status: 409, headers: { "content-type": "application/json" } },
        ),
    });

    await user.type(screen.getByLabelText(/^From/), "2026-09-08");
    await user.type(screen.getByLabelText(/^Why/), "Knocked through");
    await user.click(screen.getByRole("button", { name: "Deactivate unit" }));

    expect(await screen.findByText("Close the account first")).toBeInTheDocument();
  });
});
