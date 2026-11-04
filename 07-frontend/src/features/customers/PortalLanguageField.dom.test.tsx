// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CUS-6364 — Preferred language (relabelled 2026-10-29, PO option B)
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** a select that merely DISPLAYS the
// utility's language while the form still holds `""` would look right and save
// nothing — so the case asserts the FORM value, not only the control; and a
// utility whose default is English would pass even if the default were
// hard-coded — so the fixture's utility defaults to Mexican Spanish.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { queryKeys } from "@/api/queryClient";
import { LANGUAGE_OPTIONS } from "@/features/tenancy/SettingsRegionalTab";
import type { Translator } from "@/features/tenancy/settingsShared";
import i18n from "@/i18n";

import { PortalLanguageField } from "./PortalLanguageField";

afterEach(cleanup);

const t: Translator = (key, params) => i18n.t(key, params);

function Harness(props: { initial: string; onValue: (value: string) => void }) {
  const [value, setValue] = useState(props.initial);
  props.onValue(value);
  return <PortalLanguageField value={value} onChange={setValue} t={t} />;
}

function mount(initial: string, onValue: (value: string) => void) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  client.setQueryData(queryKeys.shellDisplay, { regional: { language: "es-MX" } });
  render(
    <QueryClientProvider client={client}>
      <Harness initial={initial} onValue={onValue} />
    </QueryClientProvider>,
  );
}

describe("PortalLanguageField", () => {
  it("is a dropdown of the Settings languages, labelled Preferred language", () => {
    mount("en", () => undefined);
    const select = screen.getByLabelText("Preferred language") as HTMLSelectElement;
    expect(select.tagName).toBe("SELECT");
    const values = [...select.options].map((option) => option.value).filter((value) => value !== "");
    expect(values).toEqual([...LANGUAGE_OPTIONS]);
  });

  it("an empty form takes the utility's default, and the FORM holds it", async () => {
    let latest = "";
    mount("", (value) => (latest = value));
    await waitFor(() => expect(latest).toBe("es-MX"));
    expect((screen.getByLabelText("Preferred language") as HTMLSelectElement).value).toBe("es-MX");
  });

  it("a code the list does not hold is kept, never silently replaced", () => {
    let latest = "";
    mount("fr", (value) => (latest = value));
    const select = screen.getByLabelText("Preferred language") as HTMLSelectElement;
    expect(select.value).toBe("fr");
    expect(latest).toBe("fr");
  });
});
