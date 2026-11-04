import { describe, expect, it } from "vitest";

import { carriesLinkSecret, readLinkSecret, strippedLocation } from "@/routing/linkSecret";

describe("readLinkSecret — one-time link secrets (decision log 2026-10-22)", () => {
  it("reads the fragment", () => {
    expect(readLinkSecret({ search: "", hash: "#ref=r1&token=t1" }, ["ref", "token"])).toEqual({
      ref: "r1",
      token: "t1",
    });
  });

  it("still reads a link emailed before the change, from the query", () => {
    expect(readLinkSecret({ search: "?token=old", hash: "" }, ["token"])).toEqual({
      token: "old",
    });
  });

  it("prefers the fragment when both carry a value", () => {
    expect(readLinkSecret({ search: "?token=old", hash: "#token=new" }, ["token"])).toEqual({
      token: "new",
    });
  });

  it("decodes what the server encoded", () => {
    expect(readLinkSecret({ search: "", hash: "#token=a%2Bb%3D" }, ["token"])).toEqual({
      token: "a+b=",
    });
  });

  it("answers nothing for an address with no secret", () => {
    expect(readLinkSecret({ search: "?x=1", hash: "#top" }, ["token"])).toEqual({});
    expect(carriesLinkSecret({ search: "?x=1", hash: "#top" }, ["token"])).toBe(false);
  });
});

describe("strippedLocation", () => {
  it("drops the fragment and the secret, keeps every other parameter", () => {
    const where = { search: "?lang=fr&token=old", hash: "#token=new" };
    expect(carriesLinkSecret(where, ["token"])).toBe(true);
    expect(strippedLocation(where, ["token"])).toEqual({ search: "?lang=fr", hash: "" });
  });

  it("leaves an empty search when nothing else was there", () => {
    expect(strippedLocation({ search: "?ref=a&token=b", hash: "" }, ["ref", "token"])).toEqual({
      search: "",
      hash: "",
    });
  });
});
