/**
 * THE DOOR — the Bills page's `One-time bill` tab opens the redrawn page.
 *
 * Hard-won law 2's mirror (`DEF-CWP-3925`): a screen can be built, routed and
 * tested at its own address while the control a clerk actually presses points
 * somewhere else. So this asserts BY ADDRESS, through the router's own table:
 * the tab's address is `/billing/one-time`, and matching that address against
 * `APP_ROUTES` lands on `OneTimeBillPage` — not on the Bills list with a tab
 * selected, and not on the retired three-step shell.
 */
import { isValidElement } from "react";
import { matchRoutes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { APP_ROUTES } from "@/App";

import { BILLING_ROUTE, BILLING_TABS } from "../billingShared";
import { BillsListPage } from "../BillsListPage";

import { ONE_TIME_BILL_ROUTE, OneTimeBillPage } from "./OneTimeBillPage";

function leafElementType(pathname: string): unknown {
  const matches = matchRoutes(APP_ROUTES, pathname) ?? [];
  const leaf = matches[matches.length - 1]?.route.element;
  return isValidElement(leaf) ? leaf.type : null;
}

describe("the One-time bill tab opens the one-time bill page", () => {
  it("the tab's address is the page's address", () => {
    const tab = BILLING_TABS.find((entry) => entry.id === "one-time");
    expect(tab).toBeDefined();
    // BillsListPage navigates a tab to `/billing/<id>`.
    expect(`${BILLING_ROUTE}/${tab?.id}`).toBe(ONE_TIME_BILL_ROUTE);
  });

  it("that address mounts OneTimeBillPage, not the Bills list", () => {
    expect(leafElementType(`/brazosbend${ONE_TIME_BILL_ROUTE}`)).toBe(OneTimeBillPage);
    // A sibling tab still lands on the list — the static route took ONE address.
    expect(leafElementType(`/brazosbend${BILLING_ROUTE}/history`)).toBe(BillsListPage);
  });

  it("the retired three-step address no longer mounts a one-time screen", () => {
    expect(leafElementType(`/brazosbend${ONE_TIME_BILL_ROUTE}/who`)).not.toBe(OneTimeBillPage);
  });
});
