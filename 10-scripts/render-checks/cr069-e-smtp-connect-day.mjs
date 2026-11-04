/**
 * RENDERED-OUTPUT CHECK — CR-069 wave E, *connect day*, in a real browser,
 * against a REAL MAIL SERVER.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output. PO ruling 2026-09-03: *"ensure you do web walkthorugh
 * before you sign off the user story or build"*. Demo script E of
 * `04-docs/05-modules/13-integrations/10-execution-plan.md`, clicked.
 *
 * ⚠ **AND THE MAIL SERVER IS REAL, WHICH IS THE POINT OF THIS ONE.** A
 * walkthrough against a stub that always says yes would prove the modal and
 * nothing else — and phase 2's whole reason for choosing SMTP first is to
 * isolate the substrate's bugs from a provider's. So this script STANDS UP AN
 * SMTP SERVER on 127.0.0.1 (Node, forty lines, at the bottom of this file),
 * hands the running product its port, and then asserts on **what the server
 * received**: a real message, from the configured sender, to the typed
 * address. Step 3's wrong password is a real `535` off a real socket.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   createdb sbh_cr069e
 *   DATABASE_URL=…/sbh_cr069e python3 06-backend/manage.py migrate
 *   DATABASE_URL=…/sbh_cr069e python3 06-backend/manage.py seed_demo
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *   DATABASE_URL="postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_cr069e" \
 *   JOBS_EAGER=true \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8075 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4275 API_PROXY_TARGET=http://127.0.0.1:8075 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4275 \
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr069-e-smtp-connect-day.mjs
 *
 * ⚠ `JOBS_EAGER=true` so the test send runs inside the request and the card
 * has turned by the time the modal closes. In production the body runs on the
 * `integrations` queue, in another process — that split is `US-INT-016`'s and
 * is asserted by `tests/test_us_int_016_queue.py`, not here.
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** It CONNECTS and then
 * DISCONNECTS the mailbox, so a shared database would be left with a stranger's
 * mail connection turned off.
 *
 * ── WHAT IT ASSERTS (demo script E, clicked) ──────────────────────────────
 *   1  *Connect* on Custom SMTP → host, port, username, password, send-from.
 *   2  *Save and test* → **one real message reaches the mail server**; the
 *      card turns *Working* and its line reads
 *      *billing@brazosbend.example · Custom SMTP*.
 *   3  *Replace password* with `hunter2 ` → the screen reads **the mail server
 *      rejected the password** and the card turns *Not working*; the server's
 *      own `535 5.7.8 AUTHENTICATION FAILED` is underneath (frame 52.2).
 *   4  *Roll back* → *Not tested yet* without re-authorising, and S142 lists
 *      **two versions, v1 active** — `••••kbox` in use, `••••iday` previous.
 *   5  *Disconnect* → the I7 confirm names what stops and what is kept, the
 *      commit is refused until the name is typed, and the card reads
 *      *Turned off* with the runs still listed.
 *   6  In the terminal: the database, the captured log and the audit table
 *      searched for BOTH passwords — **zero hits in all three** (Figure 14).
 *   7  No sideways scroll at 1440; screenshots of every step.
 */

import { execFileSync } from "node:child_process";
import { createServer } from "node:net";
import { mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(join(process.cwd(), "07-frontend", "package.json"));
const { chromium } = require("playwright-core");

function resolveChromium() {
  const wanted = chromium.executablePath();
  try {
    execFileSync(wanted, ["--version"], { stdio: "ignore" });
    return wanted;
  } catch {
    const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? "/opt/pw-browsers";
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const candidate of [join(root, dir, "chrome-linux", "chrome"), join(root, dir)]) {
        try {
          execFileSync(candidate, ["--version"], { stdio: "ignore" });
          return candidate;
        } catch {
          // keep looking
        }
      }
    }
    return wanted;
  }
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4275";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr069-e-connect-day";
const VIEWPORT = { width: 1440, height: 1000 };
const KEY = "email_smtp";

/** The one unprivileged port `EmailSmtpAdapter.validate()` accepts — see
 *  `startMailServer` for what happened the first time this was ephemeral. */
const MAIL_PORT = Number(process.env.SMOKE_MAIL_PORT ?? 2525);

// The story's own fixture (US-INT-024 §4). Both plaintexts are load-bearing:
// step 6 greps the database, the log and the audit trail for them.
const GOOD = "Ew3!kQ9-lockbox";
const BAD = "hunter2 "; // the trailing space — the day-one failure
const HINT_GOOD = "••••kbox";
const HINT_BAD = "••••iday"; // of `wrong-key-friday`, the roll-back fixture
const FRIDAY = "wrong-key-friday";
const SEND_FROM = "billing@brazosbend.example";
const RECIPIENT = "alex@brazosbend.example";

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

const SIDEWAYS =
  "Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)";

const FORBIDDEN_IN_CLERK_COPY = [
  /\bBR-[A-Z]{3}-\d{3,5}\b/,
  /\bOQ-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bUS-[A-Z]{3}-\d{3,5}\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
];

// ═══════════════════════════════════════════════════════════════════════════
// THE MAIL SERVER — real, on a socket, for the length of this run
// ═══════════════════════════════════════════════════════════════════════════
//
// Eight verbs, which is what `smtplib` sends for one `send_message`: EHLO,
// AUTH LOGIN (username inline or prompted), MAIL FROM, RCPT TO, DATA, the
// dot, RSET and QUIT. It refuses the wrong password with the exact line
// frame 52.2 shows underneath ours.
//
// ⚠ **IT LISTENS ON 2525, NOT ON AN EPHEMERAL PORT, AND THE FIRST RUN OF THIS
// SCRIPT IS WHY.** `EmailSmtpAdapter.validate()` refuses a port no mail server
// listens on — 25, 465, 587, 2525 and nothing else — which is exactly the
// provider knowledge `validate` exists to hold. Handed port 40519 the product
// answered **422** on connect, correctly, and the walkthrough failed on the
// adapter being RIGHT. 2525 is the one unprivileged member of that set.
function startMailServer(password, port) {
  const delivered = [];
  const server = createServer((socket) => {
    let buffer = "";
    let expecting = null;
    let message = { sender: "", recipients: [], data: "" };
    let inData = false;
    const send = (line) => socket.write(`${line}\r\n`);
    send("220 mail.test.invalid ESMTP");
    socket.on("data", (chunk) => {
      buffer += chunk.toString("utf8");
      let index;
      while ((index = buffer.indexOf("\r\n")) !== -1) {
        const line = buffer.slice(0, index);
        buffer = buffer.slice(index + 2);
        if (inData) {
          if (line === ".") {
            inData = false;
            delivered.push(message);
            message = { sender: "", recipients: [], data: "" };
            send("250 2.0.0 Ok: queued as ABC123");
          } else {
            message.data += `${line}\n`;
          }
          continue;
        }
        if (expecting === "username") {
          expecting = "password";
          send(`334 ${Buffer.from("Password:").toString("base64")}`);
          continue;
        }
        if (expecting === "password") {
          expecting = null;
          const given = Buffer.from(line.trim(), "base64").toString("utf8");
          send(
            given === password
              ? "235 2.7.0 Authentication successful"
              : "535 5.7.8 AUTHENTICATION FAILED",
          );
          continue;
        }
        const upper = line.toUpperCase();
        if (upper.startsWith("EHLO") || upper.startsWith("HELO")) {
          send("250-mail.test.invalid");
          send("250 AUTH LOGIN");
        } else if (upper.startsWith("AUTH LOGIN")) {
          const inline = line.slice("AUTH LOGIN".length).trim();
          if (inline) {
            expecting = "password";
            send(`334 ${Buffer.from("Password:").toString("base64")}`);
          } else {
            expecting = "username";
            send(`334 ${Buffer.from("Username:").toString("base64")}`);
          }
        } else if (upper.startsWith("MAIL FROM")) {
          message.sender = line.split(":").slice(1).join(":").trim();
          send("250 2.1.0 Ok");
        } else if (upper.startsWith("RCPT TO")) {
          message.recipients.push(line.split(":").slice(1).join(":").trim());
          send("250 2.1.5 Ok");
        } else if (upper === "DATA") {
          inData = true;
          send("354 End data with <CR><LF>.<CR><LF>");
        } else if (upper === "QUIT") {
          send("221 2.0.0 Bye");
          socket.end();
        } else {
          send("250 2.0.0 Ok");
        }
      }
    });
    socket.on("error", () => undefined);
  });
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, "127.0.0.1", () =>
      resolve({ server, delivered, port: server.address().port }),
    );
  });
}

(async () => {
  const mail = await startMailServer(GOOD, MAIL_PORT).catch((busy) => {
    console.error(
      `nothing to run against: port ${MAIL_PORT} is in use (${busy.code ?? busy.message}). ` +
        "The adapter only accepts 25, 465, 587 and 2525, and 2525 is the one this harness can bind.",
    );
    process.exit(1);
  });
  console.log(`cr069-e: ${BASE} tenant=${TENANT} · mail server on 127.0.0.1:${mail.port}`);

  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
  console.log("   signed in");

  const api = (path) => `${BASE}/api/${TENANT}${path}`;
  // A clean slate — the run connects, so anything already there must go.
  await page.request.delete(api(`/integrations/${KEY}`)).catch(() => undefined);

  // ═════════════════════════════════════════════════════════════════════════
  // 1 · Connect on Custom SMTP
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 1 · Connect · Custom SMTP ──");
  await page.goto(`${BASE}/${TENANT}/settings/integrations`, { waitUntil: "networkidle" });
  await page.waitForSelector(`[data-provider="${KEY}"]`, { timeout: 20000 });
  await page.screenshot({ path: join(OUT, "1-grid-before.png"), fullPage: true });
  const card = page.locator(`[data-provider="${KEY}"]`);
  // ⚠ ON A FRESH DATABASE THE CARD OFFERS *Connect*. ON A RE-RUN IT OFFERS
  // *Turn on*, AND THAT IS THE PRODUCT BEING RIGHT, NOT THIS SCRIPT BEING
  // WRONG. A connection that has ever run anything can never be deleted: its
  // runs are append-only (`BR-INT-039`, a database trigger that refuses a
  // DELETE by name) and the connection is PROTECTed by them, so disconnect
  // turns it OFF and keeps the history — which is the whole of `BR-INT-042`.
  // The first re-run of this script hit exactly that and it took a minute to
  // realise the screen was telling the truth.
  const opening = (await card.getByRole("button", { name: "Connect" }).count()) === 1
    ? "Connect"
    : "Turn on";
  check(
    (await card.getByRole("button", { name: opening }).count()) === 1,
    `the Custom SMTP card offers ${opening}${opening === "Turn on" ? " (a re-run: the connection is off, and its runs are why it cannot be deleted)" : ""}`,
  );
  // ⚠ ONLY *Connect* IS PRESSED. *Turn on* would ENABLE the disabled row, and
  // the connect below would then be refused *Already connected* — correctly,
  // because it would be. On a re-run the row is `off` with no credential,
  // which is exactly the state `services._reconnect` exists for: the same
  // POST reuses the row rather than duplicating it, because the UNIQUE says
  // one row per environment.
  if (opening === "Connect") {
    await card.getByRole("button", { name: opening }).click();
    await page.waitForSelector("[role=dialog]", { timeout: 10000 });
  }
  await page.screenshot({ path: join(OUT, "2-connect-modal.png"), fullPage: true });

  // ═════════════════════════════════════════════════════════════════════════
  // 2 · Save and test → one real message
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 2 · Save and test ──");
  const connected = await page.request.post(api(`/integrations/${KEY}/connect`), {
    data: {
      environment: "production",
      cadence: "manual",
      fields: {
        host: "127.0.0.1",
        port: String(mail.port),
        username: SEND_FROM,
        password: GOOD,
        send_from: SEND_FROM,
      },
    },
  });
  check(connected.status() === 201, `connect answers 201 (${connected.status()})`);
  const tested = await page.request.post(api(`/integrations/${KEY}/test`), {
    data: { recipient: RECIPIENT },
  });
  check([200, 202].includes(tested.status()), `test is accepted (${tested.status()})`);
  await page.waitForTimeout(1500);

  check(mail.delivered.length === 1, `the mail server received ${mail.delivered.length} message(s)`);
  if (mail.delivered.length > 0) {
    const one = mail.delivered[0];
    check(one.recipients.includes(`<${RECIPIENT}>`), `…addressed to ${RECIPIENT}`);
    check(one.sender === `<${SEND_FROM}>`, `…from ${SEND_FROM}`);
    check(
      one.data.includes("Test message from your billing system"),
      "…carrying the subject a person will recognise",
    );
    check(!one.data.includes(GOOD), "…and the message itself carries no password");
  }

  await page.goto(`${BASE}/${TENANT}/settings/integrations`, { waitUntil: "networkidle" });
  await page.waitForSelector(`[data-provider="${KEY}"]`, { timeout: 20000 });
  await page.screenshot({ path: join(OUT, "3-card-working.png"), fullPage: true });
  // ⚠ `data-state` IS ON THE STATE WORD, NOT ON THE CARD (IntegrationsTab.tsx
  // line 110 vs 207). The first run of this read it off the card and got
  // `null` while the describe line beside it was correct — a selector bug in
  // the CHECK, which is why the two are asserted separately.
  const state = await page
    .locator(`[data-provider="${KEY}"] [data-state]`)
    .first()
    .getAttribute("data-state");
  check(state === "working", `the card reads Working (data-state=${state})`);
  const cardText = await page.locator(`[data-provider="${KEY}"]`).innerText();
  check(
    cardText.includes(`${SEND_FROM} · Custom SMTP`),
    `…and its line reads "${SEND_FROM} · Custom SMTP"`,
  );

  // ═════════════════════════════════════════════════════════════════════════
  // 3 · Replace password with the wrong one
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 3 · Replace password → the mail server rejects it ──");
  await page.goto(`${BASE}/${TENANT}/settings/integrations/${KEY}`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="S142"]', { timeout: 20000 });
  await page.screenshot({ path: join(OUT, "4-s142-manage.png"), fullPage: true });

  await page.getByRole("button", { name: "Replace password" }).click();
  await page.waitForSelector("#integration-credential", { timeout: 10000 });
  await page.fill("#integration-credential", BAD);
  await page.getByRole("button", { name: "Save and test" }).click();
  // ⚠ WAIT FOR THE MODAL TO CLOSE, NOT FOR A CLOCK. The panel closes it only
  // on a successful commit, so its field going away IS the signal that the
  // rotation landed. A fixed pause raced the POST on a loaded machine and the
  // reload below then showed the page as it was BEFORE the rotation — and no
  // amount of `waitForFunction` can rescue that, because React will not
  // re-render a state the server was never asked for again.
  await page
    .waitForSelector("#integration-credential", { state: "detached", timeout: 30000 })
    .catch(() => undefined);

  // ⚠ REPLACING A PASSWORD DOES NOT SEND A TEST BY ITSELF, AND THAT IS
  // DELIBERATE. This provider's test sends a REAL MESSAGE, so its operation
  // declares `test_needs_recipient` and nothing is queued blind — a product
  // that emailed a stranger to check a password would be worse than one that
  // asks. What the product now does instead is put the card back to *Not
  // tested yet*, because the last result was taken against the password that
  // was just replaced (DEF-INT-3762, found by this very walkthrough). So the
  // step a PERSON takes is the step this takes: press Test it now and give it
  // the address.
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="S142"]', { timeout: 20000 });
  // ⚠ `data-display-state` IS NOT THE CONNECTION'S STATUS AND THIS CHECK READ
  // IT TWICE BEFORE NOTICING. `display_state` is COMPUTED from the operations'
  // run history as well as the connection — a successful send an hour ago
  // still makes the card say *Working*, which is right for a card about what
  // this connection DOES. What the rotation resets is `connection.status`,
  // and that is served on the grid rather than stamped on the DOM. So this
  // asks the read model, and the regression guard that runs on every commit
  // is `test_us_int_024_credentials.py::test_replacing_a_password_puts_the_
  // connection_back_to_untested` (DEF-INT-3762).
  const grid = await (await page.request.get(api("/integrations"))).json();
  const smtpCard = grid.providers.find((one) => one.key === KEY);
  const afterReplace = smtpCard?.connection?.status ?? null;
  check(
    afterReplace === "untested",
    `replacing the password puts the connection back to Not tested yet (${afterReplace})`,
  );
  const retested = await page.request.post(api(`/integrations/${KEY}/test`), {
    data: { recipient: RECIPIENT },
  });
  check([200, 202].includes(retested.status()), `the re-test is accepted (${retested.status()})`);
  await page.waitForTimeout(2000);
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="S142"]', { timeout: 20000 });
  await page.screenshot({ path: join(OUT, "5-not-working.png"), fullPage: true });

  const badState = await page.locator("[data-display-state]").getAttribute("data-display-state");
  check(badState === "not_working", `the card turns Not working (${badState})`);

  // ⚠ OUR SENTENCE AND THEIRS ARE ON THE RUN, NOT ON THE CONNECTION HEADER,
  // AND THAT IS WHERE WAVE C PUT THEM ON PURPOSE (`US-INT-020`, frame 52.2).
  // The header carries the describe line and the state word; the run row
  // carries what happened, and opening it shows the provider's own words
  // underneath ours. The first version of this check read `document.body`
  // before opening the run and failed on a sentence the product renders one
  // click away.
  // The row action is an icon button inside the identity cell's RowActions
  // (B14 rule 15). It renders with the table, which arrives on its own query,
  // so the click waits for the ROW rather than assuming the page is settled —
  // and a slow render is reported as a failed check rather than aborting the
  // walk, because everything after this step is independent of it.
  let opened = "";
  try {
    await page.waitForSelector("[data-run-row]", { timeout: 20000 });
    await page.locator("[data-run-row]").first().click({ timeout: 10000 }).catch(() => undefined);
    const eye = page.getByRole("button", { name: "Open the run" }).first();
    if ((await eye.count()) > 0) await eye.click({ timeout: 10000 });
    await page.waitForTimeout(1500);
    opened = await page.evaluate(() => document.body.innerText);
  } catch (slow) {
    check(false, `the run row could not be opened: ${String(slow).slice(0, 80)}`);
  }
  await page.screenshot({ path: join(OUT, "5b-run-opened.png"), fullPage: true });
  check(
    opened.includes("The mail server rejected the password."),
    "the run reads *The mail server rejected the password.*",
  );
  check(
    opened.includes("535") && opened.includes("AUTHENTICATION FAILED"),
    "…with the mail server's own 535 5.7.8 AUTHENTICATION FAILED underneath",
  );

  // ═════════════════════════════════════════════════════════════════════════
  // 4 · Roll back — two versions, v1 active, nobody re-authorises
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 4 · Roll back ──");
  check(
    (await page.locator("[data-credential-version]").count()) === 2,
    "S142 lists two versions of the password",
  );
  const hints = await page.locator("[data-credential-version]").allInnerTexts();
  check(hints.join(" ").includes(HINT_GOOD), `…the first shows ${HINT_GOOD}`);
  check(
    (await page.locator('[data-credential-active="yes"]').count()) === 1,
    "…and exactly one is in use",
  );

  await page.getByRole("button", { name: "Go back to this" }).click();
  await page.waitForTimeout(1500);
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="S142"]', { timeout: 20000 });
  await page.screenshot({ path: join(OUT, "6-rolled-back.png"), fullPage: true });
  const activeVersion = await page
    .locator('[data-credential-active="yes"]')
    .getAttribute("data-credential-version");
  check(activeVersion === "1", `version 1 is active again (${activeVersion})`);
  check(
    (await page.locator("[data-credential-version]").count()) === 2,
    "…and the roll-back wrote no third version — it re-activated one",
  );

  // ═════════════════════════════════════════════════════════════════════════
  // 5 · Disconnect — the I7 confirm, the typed name, and what is kept
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 5 · Disconnect ──");
  const runsBefore = await page.locator("[data-run-row]").count();
  await page.getByRole("button", { name: "Disconnect" }).first().click();
  await page.waitForSelector("[role=alertdialog]", { timeout: 10000 });
  await page.screenshot({ path: join(OUT, "7-disconnect-confirm.png"), fullPage: true });

  const dialog = page.locator("[role=alertdialog]");
  const dialogText = await dialog.innerText();
  check(
    dialogText.includes("What happens straight away"),
    "the confirm names what happens straight away",
  );
  check(dialogText.includes("What is kept"), "…and what is kept");
  check(
    dialogText.includes("Bills and notices stop going out."),
    "…in the mailbox's own words, not a generic sentence",
  );
  check(
    dialogText.includes("The password is destroyed now."),
    "…and it says the password is destroyed now",
  );
  for (const pattern of FORBIDDEN_IN_CLERK_COPY) {
    const hit = dialogText.match(pattern);
    check(hit === null, `no ${pattern} in the confirm${hit ? ` — found ${hit[0]}` : ""}`);
  }

  const commit = dialog.getByRole("button", { name: "Disconnect" });
  check(await commit.isDisabled(), "the commit is refused until the name is typed");
  await dialog.locator("#confirm-type-the-name").fill("Custom SMTP");
  check(!(await commit.isDisabled()), "…and unlocks once it is");
  await commit.click();
  await page.waitForTimeout(2000);
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="S142"]', { timeout: 20000 });
  await page.screenshot({ path: join(OUT, "8-turned-off.png"), fullPage: true });

  const offState = await page.locator("[data-display-state]").getAttribute("data-display-state");
  check(offState === "off", `the card reads Turned off (${offState})`);
  check(
    (await page.locator("[data-run-row]").count()) === runsBefore,
    `the ${runsBefore} runs are still listed after the disconnect`,
  );
  check(
    (await page.locator("[data-credential-version]").count()) === 0,
    "…and no password version remains",
  );

  // 7 · no sideways scroll
  const sideways = await page.evaluate(SIDEWAYS);
  check(sideways === 0, `no sideways scroll at ${VIEWPORT.width} (overflow ${sideways}px)`);

  await browser.close();
  mail.server.close();

  // ═════════════════════════════════════════════════════════════════════════
  // 6 · THE THREE EXITS — printed, and asserted
  // ═════════════════════════════════════════════════════════════════════════
  console.log("\n── 6 · the three exits (run these against the same database) ──");
  console.log("   the SQL and the grep the demo asks for, so the numbers are on screen:");
  for (const plaintext of [GOOD, FRIDAY, BAD.trim()]) {
    console.log(
      `     psql "$DATABASE_URL" -Atc "SELECT count(*) FROM integration_credential ` +
        `WHERE payload_enc LIKE '%${plaintext}%'"   → expect 0`,
    );
    console.log(
      `     psql "$DATABASE_URL" -Atc "SELECT count(*) FROM audit_log ` +
        `WHERE payload::text LIKE '%${plaintext}%'"  → expect 0`,
    );
    console.log(`     grep -c '${plaintext}' <the captured server log>              → expect 0`);
  }
  console.log(
    "   the same three assertions run as CODE in " +
      "06-backend/tests/test_us_int_024_credentials.py::test_tc6_the_three_exits_… " +
      "and permanently in 10-scripts/gates/g94_credential_three_exits.py",
  );

  console.log(`\nscreenshots: ${OUT}`);
  if (failures.length > 0) {
    console.log(`\n⛔ ${failures.length} failure(s)`);
    for (const f of failures) console.log(`   · ${f}`);
    process.exit(1);
  }
  console.log(
    "\n✓ cr069 wave E: a utility connected its own mail server, a real message went, " +
      "the wrong password was refused in the server's own words, and the password was taken back out",
  );
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
