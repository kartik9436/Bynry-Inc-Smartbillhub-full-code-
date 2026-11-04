// @vitest-environment jsdom
// CR-169-BRC10 §5 (PO 2026-10-04, option (a)) — the recorder masks every input
// AND the customer details a screen SHOWS; menus, buttons and labels stay
// readable. Proved through the REAL recorder posthog-js ships (rrweb), fed the
// exact options `client.ts` passes — not by asserting a config object.
// Written before `privacy.ts` (red first).
import { record } from "posthog-js/rrweb";
import { afterEach, describe, expect, it } from "vitest";

import { RECORDING_PRIVACY, cleanEventUrls, cleanUrl } from "./privacy";

const SCREEN = `
  <aside><button class="foot" aria-haspopup="menu"><span class="av">DW</span><div class="foot-name">Dana Whitfield</div><div class="foot-role">System admin</div></button></aside>
  <nav aria-label="Main"><a href="/brazosbend/payments">Payments</a></nav>
  <nav class="crumbs"><a href="/brazosbend/accounts">Accounts</a><span>Maria Lopez</span></nav>
  <h1 class="text-h2">Maria Lopez</h1>
  <h3>Balance</h3>
  <table><thead><tr><th>Account</th><th>Balance</th></tr></thead>
    <tbody><tr><td>AC-2026-00012</td><td>$186.40</td></tr></tbody></table>
  <p>412 Oak St, Austin TX</p>
  <p>maria.lopez@example.com · (512) 555-0142</p>
  <label for="cheque">Cheque number</label>
  <input id="cheque" value="4471" />
  <button type="button">Record payment</button>
  <a href="/brazosbend/accounts/AC-2026-00012" title="Maria Lopez">Open</a>
`;

function snapshotText(): string {
  const events: unknown[] = [];
  const stop = record({
    emit: (event) => {
      events.push(event);
    },
    ...RECORDING_PRIVACY,
  });
  stop?.();
  return JSON.stringify(events);
}

describe("session recording privacy (CR-169-BRC10 §5)", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("masks the record values a screen shows — name, amount, address, account, email, phone", () => {
    document.body.innerHTML = SCREEN;
    const recorded = snapshotText();
    for (const secret of [
      "Maria Lopez",
      "186.40",
      "412 Oak St",
      "AC-2026-00012",
      "maria.lopez@example.com",
      "555-0142",
      "Dana Whitfield",
      '"DW"',
    ]) {
      expect(recorded, secret).not.toContain(secret);
    }
  });

  it("masks what is TYPED into an input", () => {
    document.body.innerHTML = SCREEN;
    expect(snapshotText()).not.toContain("4471");
  });

  it("leaves the chrome readable — nav, buttons, labels, column headings, section headings", () => {
    document.body.innerHTML = SCREEN;
    const recorded = snapshotText();
    for (const chrome of ["Payments", "Record payment", "Cheque number", "Account", "Balance"]) {
      expect(recorded, chrome).toContain(chrome);
    }
  });

  it("a NEW element nobody marked is masked (mask by default, law 3)", () => {
    document.body.innerHTML = `<section><div><span>Hollis Grant owes 92.10</span></div></section>`;
    const recorded = snapshotText();
    expect(recorded).not.toContain("Hollis");
    expect(recorded).not.toContain("92.10");
  });

  it("scrubs digits and emails even inside chrome", () => {
    document.body.innerHTML = `<button>Pay $186.40</button><nav><a>dana@utility.com</a></nav>`;
    const recorded = snapshotText();
    expect(recorded).not.toContain("186.40");
    expect(recorded).not.toContain("dana@utility.com");
    expect(recorded).toContain("Pay");
  });
});

describe("address cleaning (errorReport's cleaner, reused)", () => {
  it("withholds record references, typed search text and the fragment", () => {
    expect(cleanUrl("https://app.bynry.com/brazosbend/accounts/AC-2026-00012?q=Hollis&tab=bills#x")).toBe(
      "https://app.bynry.com/brazosbend/accounts/(withheld)?q=(withheld)&tab=bills",
    );
  });

  it("withholds a capability UUID in the path", () => {
    expect(cleanUrl("https://app.bynry.com/brazosbend/portal/pay/0b1e7a52-9d2c-4c3e-8a4f-2f0c9d1e2a3b")).toBe(
      "https://app.bynry.com/brazosbend/portal/pay/(withheld)",
    );
  });

  it("keeps only the origin of a foreign referrer", () => {
    expect(cleanUrl("https://mail.example.com/inbox/123?id=9")).toBe("https://mail.example.com/");
  });

  it("cleans $current_url, $pathname and the initial-url family, and drops $title", () => {
    const cleaned = cleanEventUrls(
      {
        $current_url: "https://app.bynry.com/brazosbend/accounts/AC-2026-00012",
        $pathname: "/brazosbend/accounts/AC-2026-00012",
        $title: "Maria Lopez · SMARTBillHub",
        $set_once: { $initial_current_url: "https://app.bynry.com/brazosbend/accounts/AC-2026-00012?q=Maria" },
      },
      "https://app.bynry.com",
    );
    expect(JSON.stringify(cleaned)).not.toContain("AC-2026-00012");
    expect(JSON.stringify(cleaned)).not.toContain("Maria");
    expect(cleaned.$pathname).toBe("/brazosbend/accounts/(withheld)");
  });
});
