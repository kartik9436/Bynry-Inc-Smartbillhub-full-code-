// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   `CR-136-BRC07` `P2.9` — 2·3a's counter banner, the branch that says
//           *we could not ask* rather than *you have none*.
// Defect:   `DEF-PAY-6245` — `stubClient` in `counterScreens.dom.test.tsx` has
//           taken `{ fail: true }` since it was written and nothing ever passed
//           it, so `RecordCounterBanner`'s `isError` branch had no case at all.
// Rules:    hard-won law 2's mirror (a refusal nothing asserts is a refusal
//           that rots — the blueprint says it in `P1.23`) · law 7 (a check that
//           cannot pass is not a weaker check, it is none) · `DEF-127`
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS IS ITS OWN FILE AND NOT A CASE IN `counterScreens.dom.test.tsx`
// ══════════════════════════════════════════════════════════════════════════
// **That file renders STATICALLY** — `renderToStaticMarkup`, one synchronous
// pass — and seeds each query's data into the cache so the render has an answer
// already. That works for *no till* and for *a till is open*, because both are
// DATA and `setQueryData` can plant them. **It cannot work for a FAILED read.**
// An error arrives by rejecting a promise; a static render never advances past
// the first frame, so the query stays `pending`, the component returns `null`
// on its loading guard, and the case asserts against an empty string for ever.
//
// That was tried first, and it failed — **and then it failed IDENTICALLY with
// the hook reverted to its pre-`DEF-PAY-6235` shape**, which is what proves the
// harness is the obstacle rather than the code. A case that cannot pass is not
// a weaker check than one that can; it is none, and it would have been read as
// *the branch is broken*.
//
// So this file opts into jsdom and waits, which is the only way the error state
// can exist at all.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT IT PROTECTS, AND IT IS TWO THINGS
// ══════════════════════════════════════════════════════════════════════════
// **1 — `DEF-127`'s shape, on the form that takes money.** `CounterDoors`'s own
// comment states it: *"saying start your counter first to a clerk who HAS one
// open, because the server did not answer, sends them to open a second till the
// database will refuse."* An absence and a failure are different facts and the
// screen must not state the more alarming one as though it knew.
//
// **2 — the spread in `useMyOpenCounter`.** `DEF-PAY-6235`'s fix folds the
// session read into the loading state by returning `{ ...counter, isLoading }`.
// A spread copies OWN ENUMERABLE properties; if React Query ever returns a
// result whose flags are prototype getters, `isError` comes through as
// `undefined`, this branch never fires, and a failed read renders *You have no
// counter open* — the exact wrong answer, with every other case still green.
// Nothing else in the suite would notice. This is the case that would.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { ApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";

import { CounterHeadSlot, RecordCounterBanner } from "./CounterDoors";

afterEach(cleanup);

const TENANT = "brazosbend";
const OWNER = "D. Whitfield";

/**
 * A client whose session read works and whose COUNTER read does not.
 *
 * ⚠ **THE TWO HALVES ARE SPLIT ON PURPOSE.** `useMyOpenCounter` waits for
 * `/me` before it asks about tills, so a stub that failed everything would
 * leave the counter query DISABLED and never in an error state at all — the
 * branch would go unrendered again, for a second reason, and the case would
 * look like it was testing something.
 *
 * ⚠ **A REAL `ApiError`, NOT A SHAPED OBJECT.** `isApiError` is
 * `value instanceof ApiError`, and a plain `Error` carrying `status` takes a
 * different path through the hook.
 */
function counterReadFails(): ApiClient {
  return {
    get: async (path: string) => {
      if (path === "/me") {
        return {
          status: 200,
          data: {
            id: "u-dana",
            full_name: OWNER,
            email: "dana@brazosbendutilities.com",
            phone: null,
            role: "system_admin",
            role_name: "System Admin",
            must_change_password: false,
          },
        };
      }
      throw new ApiError(500, { code: "server_error", message_key: "api.error.unexpected" });
    },
  } as unknown as ApiClient;
}

function mount(node: JSX.Element) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.me, {
    id: "u-dana",
    full_name: OWNER,
    email: "dana@brazosbendutilities.com",
    phone: null,
    role: "system_admin",
    role_name: "System Admin",
    must_change_password: false,
  });
  return render(
    <QueryClientProvider client={queryClient}>
      {/* THE REAL PATH PATTERN. Without `:tenant`, `useTenantPath` builds
          `//payments/…` — a protocol-relative URL to another host that every
          address assertion accepts happily. */}
      <MemoryRouter initialEntries={[`/${TENANT}/payments/record`]}>
        <Routes>
          <Route path="/:tenant/payments/:tab" element={node} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("P2.9 — a failed counter read is not the same as having no counter", () => {
  it("says it could not check, and does NOT claim the absence it cannot know", async () => {
    mount(
      <RecordCounterBanner
        client={counterReadFails()}
        dateFormat="MM/DD/YYYY"
        timeZone="America/Chicago"
        methodCode="cash"
      />,
    );
    await waitFor(() =>
      expect(document.body.textContent).toContain("Your counter could not be checked."),
    );
    // ⚠ **THE SECOND HALF IS THE ONE THAT BITES.** Rendering the right sentence
    // while ALSO rendering *You have no counter open* would pass a `toContain`
    // on the first and still be the defect.
    expect(document.body.textContent).not.toContain("You have no counter open");
  });

  // The head slot deliberately does NOT have an error branch, and its own
  // comment says why: *"a server that cannot answer must not leave the only
  // door out of §3.4's refusal invisible."* So a failed read draws the way IN.
  // Asserted rather than left to the comment — this is the pair of behaviours
  // that must not accidentally converge.
  it("still offers the way in from the page head, because a door must not vanish", async () => {
    mount(<CounterHeadSlot client={counterReadFails()} dateFormat="MM/DD/YYYY" />);
    await waitFor(() => expect(document.querySelector("a[href]")).not.toBeNull());
    const door = document.querySelector("a[href]");
    expect(door?.getAttribute("href")).toBe(`/${TENANT}/payments/counter?start=1`);
  });
});
