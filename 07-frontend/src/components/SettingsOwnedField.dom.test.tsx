// @vitest-environment jsdom
/* CR-075 wave C · C1a — the `ref:setting` parameter.
 *
 * ⚠ MOUNTED UNDER THE REAL PATH PATTERN, NEVER BARE IN A `MemoryRouter`.
 * `DEF-CWP-3925`'s second half: the portal's front page mounted bare with no
 * `/:tenant/portal` route, so `useParams().tenant` was undefined and every
 * address the page built came out `//portal/…` — a protocol-relative URL to
 * another host, which reads as a perfectly good string to `toContain`. So the
 * link's resolved `href` is asserted here, not the string handed in. */
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { SettingsOwnedField, SettingsOwnedProvider } from "./SettingsOwnedField";

afterEach(cleanup);

const TENANT = "silvercreek";

/** `RBS-004-R8`'s Parameters panel, at its real address. */
function mount(values: Record<string, string> | null) {
  return render(
    <MemoryRouter initialEntries={[`/${TENANT}/runbooks/collections-ladder`]}>
      <Routes>
        <Route
          path="/:tenant/runbooks/:key"
          element={
            <SettingsOwnedProvider values={values}>
              <SettingsOwnedField
                setting="ladder.tiers"
                label="Ladder tiers"
                ownedBy="From Settings"
                to={`/${TENANT}/settings/collections`}
                openLabel="Open settings →"
                absent={{ notLoaded: "Not loaded", notSet: "Not set in Settings" }}
              />
            </SettingsOwnedProvider>
          }
        />
        <Route path="/:tenant/settings/collections" element={<div>the ladder settings</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("SettingsOwnedField — RBS-004-R8, five of these on one screen", () => {
  it("shows the value Settings holds, with its label and its provenance", () => {
    mount({ "ladder.tiers": "5 tiers" });
    expect(screen.getByText("Ladder tiers")).toBeInTheDocument();
    expect(screen.getByText("From Settings")).toBeInTheDocument();
    expect(screen.getByText("5 tiers")).toBeInTheDocument();
  });

  it("Open settings → resolves to a REAL address, not a protocol-relative one", () => {
    mount({ "ladder.tiers": "5 tiers" });
    const link = screen.getByRole("link", { name: "Open settings →" });
    expect(link).toHaveAttribute("href", `/${TENANT}/settings/collections`);
    // the DEF-CWP-3925 shape: `//host/…` reads as a good string and is not one
    expect(link.getAttribute("href")?.startsWith("//")).toBe(false);
  });

  it("UNWIRED IS VISIBLE, NOT BLANK — DEF-SHL-3964's lesson, kept", () => {
    // Its cure was to hold null until the value is known so a consumer can tell
    // "not yet" from a real answer. A default here would be a plausible wrong
    // answer, which is the defect and not the cure.
    mount(null);
    expect(screen.getByText("Not loaded")).toBeInTheDocument();
    expect(document.querySelector('[data-settings-state="notLoaded"]')).not.toBeNull();
  });

  it("PUBLISHED-BUT-EMPTY is a THIRD state and says something different", () => {
    mount({ "grace.days": "3" });
    expect(screen.getByText("Not set in Settings")).toBeInTheDocument();
    expect(document.querySelector('[data-settings-state="notSet"]')).not.toBeNull();
  });

  it("the three states are visibly different from one another", () => {
    const states = new Set<string>();
    const cases: (Record<string, string> | null)[] = [
      { "ladder.tiers": "5 tiers" },
      null,
      { other: "x" },
    ];
    for (const values of cases) {
      mount(values);
      states.add(document.querySelector("[data-settings-state]")?.getAttribute("data-settings-state") ?? "");
      cleanup();
    }
    expect(states).toEqual(new Set(["loaded", "notLoaded", "notSet"]));
  });

  it("the setting KEY is never the visible value of a field — B14 rule 31", () => {
    mount({ "ladder.tiers": "5 tiers" });
    expect(screen.queryByText("ladder.tiers")).toBeNull();
  });

});
