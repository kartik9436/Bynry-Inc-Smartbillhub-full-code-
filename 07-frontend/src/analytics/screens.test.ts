// CR-169-BRC10 — screen_viewed names the screen id from each app's own register.
import { describe, expect, it } from "vitest";

import { pageScreen } from "./screens";

describe("pageScreen", () => {
  it("names a staff screen by its id, with the tenant from the path", () => {
    const page = pageScreen("/brazosbend/payments");
    expect(page.app).toBe("staff");
    expect(page.tenant).toBe("brazosbend");
    expect(page.screen).not.toBeNull();
  });

  it("names a portal screen from the portal's register", () => {
    expect(pageScreen("/brazosbend/portal/track")).toEqual({
      app: "portal",
      tenant: "brazosbend",
      screen: "CWP-012",
      screenA1: null,
    });
  });

  it("names a field-app screen from the field app's register", () => {
    expect(pageScreen("/brazosbend/work/mobile").screen).toBe("WRK-21");
    expect(pageScreen("/brazosbend/work/mobile/jobs/abc").screen).toBe("WRK-22");
    expect(pageScreen("/brazosbend/work/mobile/jobs/abc").app).toBe("field");
  });

  it("a public page has no tenant", () => {
    expect(pageScreen("/").tenant).toBeNull();
  });
});
