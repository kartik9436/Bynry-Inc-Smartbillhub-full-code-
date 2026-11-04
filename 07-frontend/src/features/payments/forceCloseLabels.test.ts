// DEF-PAY-8026 — the Force close dialog printed two raw catalogue keys
// ("payments.counter.forceClose.openSince …") because neither existed in any
// catalogue; i18next prints the key and nothing else fails. Every key the
// dialog asks for must resolve (a count key through its _one/_other forms).
import { describe, expect, it } from "vitest";

import en from "@/i18n/locales/en.json";

import source from "./ForceCloseCounterModal.tsx?raw";

const catalogue = en as Record<string, string>;

describe("DEF-PAY-8026 · the Force close dialog's words exist", () => {
  it("every t() key in ForceCloseCounterModal resolves in en.json", () => {
    const keys = [...source.matchAll(/t\("([a-zA-Z0-9_.]+)"(, \{[^}]*count)?/g)].map((m) => ({
      key: m[1],
      counted: m[2] !== undefined,
    }));
    expect(keys.length).toBeGreaterThan(0);
    const missing = keys
      .filter(({ key, counted }) =>
        counted ? !(catalogue[`${key}_one`] && catalogue[`${key}_other`]) && !catalogue[key] : !catalogue[key],
      )
      .map(({ key }) => key);
    expect(missing).toEqual([]);
  });
});
