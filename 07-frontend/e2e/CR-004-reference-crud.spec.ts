// ── Trace ──────────────────────────────────────────────
// Change:  CR-004 tasks 11–16 (12-governance/11-change-requests.md) — the six
//          r10 SET-04 reference lists that shipped "BUILT, NOT PROVEN".
// Story:   US-TEN-009 (card grid) · US-TEN-010 (view/search/add/edit) ·
//          US-TEN-011 (delete/deactivate)
//          Screens: S8 → Settings → Configure → Reference data (S75–S80)
// Rules:   BR-TEN-029 (counts + Used-by computed LIVE) · BR-TEN-030 (codes
//          unique per tenant, CASE-INSENSITIVE, and the refusal NAMES the
//          existing entry) · BR-TEN-031 (the owning module validates) ·
//          BR-TEN-034 (audit-lock: a referenced row cannot be deleted) ·
//          BR-TEN-036 (a platform-seeded row is deactivatable, never
//          deletable) · BR-SHL-025 (a control that cannot work stays VISIBLE
//          and DISABLED WITH ITS REASON) · BR-SHL-032 (the confirm names the
//          action) · BR-SHL-035 (ONE frame for every reference list)
// Defect:  DEF-187 (`HostedFlatLookupHandler.used_by` called a `None` seam, so
//          every one of these six lists answered HTTP 500 the moment a user
//          opened it) · DEF-188 (a platform-seeded row offered an ENABLED
//          Delete whose refusal printed the raw key
//          `settings.lookups.system_row_not_deletable`)
// ───────────────────────────────────────────────────────
//
// **THE PO'S BAR, VERBATIM, IS THE ONLY REASON THIS FILE EXISTS:**
// *"full CRUD working - from Ui scren not just backend"*.
//
// CR-004 §Task status marks tasks 11–16 **BUILT, NOT PROVEN** and says exactly
// what is missing: *"Part (d) — someone signs in, opens the card, adds a row,
// edits it, deactivates it and deletes one — has not happened"*. The backend
// tests were green THROUGH DEF-187: the two pre-CR-004 handlers set a real
// `used_by_seam`, the six new ones did not, and nothing in 3,000 backend tests
// or 1,250 component tests ever asked the ONE question this file asks — does
// the list open in a browser at all.
//
// So every assertion here is on RENDERED TEXT a person reads, never on a
// payload. Three of them are worth naming because they are the ones a mock
// cannot fake:
//
//   1. **The card's count is the list's row count.** BR-TEN-029 says the count
//      is live. A card reading "6 ›" over a list that renders four rows is the
//      failure that a fixture-driven component test cannot produce.
//   2. **The duplicate refusal NAMES the existing entry** (BR-TEN-030). The
//      rule is not "codes are unique" — it is that a clerk typing `dtwn` is
//      told **which** row already holds it, in the capitalisation the row
//      actually uses. Asserting a 409 proves nothing about that sentence.
//   3. **The seeded row's Delete is disabled AND ITS TOOLTIP IS ENGLISH.**
//      DEF-188's whole cost was that the refusal arrived as
//      `settings.lookups.system_row_not_deletable`. So this file asserts the
//      HUMAN SENTENCE and asserts the RAW KEY IS ABSENT — a screen that has
//      merely stopped 500ing still fails if it speaks in developer.
//
// **PROVED RED BEFORE TRUSTED GREEN (hard-won law 7), ONCE PER DEFECT.** Both
// proofs were run against this stack on 2026-08-17 by reverting the fix,
// restarting the affected process, and re-running `--grep Areas`:
//
//   · **DEF-187** — `used_by`'s `is None` branch removed. Django logged
//     `TypeError: 'NoneType' object is not callable`; the spec failed with
//     *"DEF-187: this list answered HTTP 500 and the frame rendered the failure
//     card — expect(locator).toHaveCount(0) … Received: 1"*.
//   · **DEF-188** — `deleteIsLocked` reverted to `entry.used_by > 0`. The spec
//     failed with *"locator … getByRole('button', { name: '🔒 Delete' })
//     Expected: visible … Error: element(s) not found"* — because the pre-fix
//     build draws an ENABLED `aria-label="Delete"` there instead.
//
// **AND THE FIRST RED PROOF FAILED THIS FILE RATHER THAN THE PRODUCT**, which
// is the reason law 7 exists. Version one asserted the DEF-187 failure card was
// absent immediately after the click; against the broken build that assertion
// PASSED (the query was still in flight, so nothing was on screen and "absent"
// was trivially true) and the test only went red four lines later on the pager
// range, blaming the pager. The ordering fix is at the assertion itself and is
// commented there.
//
// ⚠ **THIS SPEC WRITES, AND ONLY TO A DISPOSABLE TENANT.** Each list gets ONE
// row added, edited, deactivated and then deleted, under a run-unique code
// (`QA{list}{timestamp}`), so a completed run leaves the seeded vocabulary
// exactly as it found it. A run that dies mid-test leaves one inactive row
// behind; the next run's code differs, so it never collides.
//
// **THE SEEDED VOCABULARIES ARE PINNED ON PURPOSE.** CR-004 §"Two further PO
// requirements" is explicit that the content is *"transcribed from r10's own
// sub-screens, never invented"*, and four of these vocabularies were corrected
// to r10's real codes after the first draft. A change to any code below is a
// change to a signed transcription and should be made deliberately, through
// the change process — not absorbed by a loose assertion.
import { expect, test } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";

import { APP_SERVER_TAG } from "./support/census";
import { signIn, skipUnlessAppServer, tenant } from "./support/app";

skipUnlessAppServer(test);

// ── The catalogue under test ───────────────────────────────────────────────
interface ListUnderTest {
  /** `?list=` code, and the API path segment. */
  code: string;
  /** The card label, en — `settings.reference.card.<code>`. */
  label: string;
  /** The r10 SET-04 module heading the card files under. */
  group: string;
  /** Every seeded code, in the list's own `code ASC` order (IS-2). */
  seeded: string[];
  /** One seeded NAME, quoted whole — the cell a human actually reads. */
  seededName?: string;
}

const LISTS: ListUnderTest[] = [
  {
    code: "areas",
    label: "Areas & sub-areas",
    group: "Platform-wide",
    seeded: ["DTWN", "EAST", "IND", "NORTH"],
    seededName: "Downtown · 2 sub-areas",
  },
  {
    code: "service_size_classes",
    label: "Utility service size classes",
    group: "Plans & Rates",
    // ── 7 → 40 on 2026-08-27, then 40 → 53 on 2026-09-02 (CR-062 A) ─────
    // then 53 → 60 (CR-063, fire's seven), 60 → 59 (the private hydrant
    // withdrawn 2026-09-03) and 59 → 64 on 2026-09-07 (CR-080, thermal).
    // ⚠ **THE SIX `FL-*` ROWS WERE MISSING FROM THIS ARRAY FROM 2026-09-02
    // UNTIL 2026-09-07 AND ARE ADDED HERE BY THE CR-080 LANE**, which had to
    // touch the array for its own three codes and could not leave a count
    // assertion it knew to be wrong. That is `DEF-971` recurring exactly as
    // that defect predicted — *"a test nobody runs is a comment"*: no gate
    // boots the app, so a stale literal here is only ever found by a human
    // opening the file for another reason. This is the second time.
    // ── CR-080 (PO 2026-09-07): THERMAL'S THREE `TH-CW-*` BANDS ARE
    // WITHDRAWN and replaced by EIGHT connected-tonnage capacities. Each of
    // the three was a RANGE ("≤25 tons", "25–100"), and a range has no single
    // value a capacity could be. This spec runs against a FRESHLY provisioned
    // tenant, which is why the three codes can be dropped outright —
    // BR-TEN-071 leaves them on any tenant that already had them.
    // CR-062 group A: solar's four inverter BANDS are withdrawn for ten
    // panel types, storm water's four ERU bands are reversed into five
    // property sizes, and battery gains six capacities. A capacity is a
    // NUMBER WITH A UNIT that sums; a band is a label that picks a rate.
    // `E-3P` LEAVES (2026-08-27):
    // The ratified electric list names 3φ 200A and 3φ 400A; a bare 3φ with
    // no amperage is neither, so no NEW tenant receives it. This spec runs
    // against a FRESHLY provisioned tenant, which is why the code can be
    // dropped from the expectation outright — BR-TEN-071 leaves it on any
    // tenant that already had it, and such a tenant reads 54 rows, not 53.
    seeded: [
      "BAT-10",
      "BAT-15",
      "BAT-20",
      "BAT-25",
      "BAT-30",
      "BAT-5",
      "BB-100",
      "BB-1000",
      "BB-500",
      "CART-35",
      "CART-64",
      "CART-96",
      "DUMP-2",
      "DUMP-4",
      "DUMP-6",
      "DUMP-8",
      "E-1P-100",
      "E-1P-200",
      "E-1P-400",
      "E-3P-200",
      "E-3P-400",
      "E-CT",
      "FL-10",
      "FL-12",
      "FL-2",
      "FL-4",
      "FL-6",
      "FL-8",
      "G-1000",
      "G-250",
      "G-425",
      "G-630",
      "SOL-P1",
      "SOL-P10",
      "SOL-P2",
      "SOL-P3",
      "SOL-P4",
      "SOL-P5",
      "SOL-P6",
      "SOL-P7",
      "SOL-P8",
      "SOL-P9",
      "SW-APT",
      "SW-COM-L",
      "SW-COM-S",
      "SW-DUP",
      "SW-SF",
      "TH-T10",
      "TH-T100",
      "TH-T200",
      "TH-T25",
      "TH-T400",
      "TH-T5",
      "TH-T50",
      "TH-T800",
      "W-1",
      "W-112",
      "W-2",
      "W-3",
      "W-34",
      "W-4",
      "W-5",
      "W-58",
      "W-6",
    ],
    // The φ this spec also exists to check — see the dedicated test below.
    // ⚠ The old expectation here read `"Electric 1φ 100A · base $18.50"` and
    // had been WRONG since CR-010 stripped every `· base $X` from this list's
    // names (PO 2026-08-17: *"you dont need Base charge - we agreed"*). Ten
    // days stale, in a spec no gate runs — DEF-971.
    seededName: "Electric 1φ 100A",
  },
  {
    code: "occupancy_statuses",
    label: "Occupancy statuses",
    group: "Premises",
    seeded: ["LNDLRD", "OCC-O", "OCC-T", "VAC", "VAC-OFF"],
    seededName: "Vacant · base charges only",
  },
  {
    code: "device_types",
    label: "Device types (BTM)",
    group: "Assets",
    seeded: ["BACKFLOW", "BATT", "COMM", "EVCHG", "INVERTER", "OTHER"],
    seededName: "Backflow preventer · annual test",
  },
  {
    code: "certification_types",
    label: "Certification types",
    group: "Assets",
    seeded: ["BF-TST", "CONF-SP", "FA-CPR", "HV-AW", "TRAF", "TRENCH"],
    seededName: "Confined space · 3-yr validity",
  },
  {
    // SEEDED EMPTY BY DESIGN, and that is a decision, not a gap: CR-004 §Task
    // status records it in `UNSEEDABLE_REFERENCE_LISTS` with its reason — *"an
    // import mapping describes THIS tenant's file, so a seeded one describes a
    // layout they do not have"*. The card must therefore read `0 ›`, the list
    // must render the honest empty state, and **Add must still work** — an
    // empty list whose only affordance is broken is indistinguishable from an
    // unbuilt one.
    code: "import_mappings",
    label: "Import mappings",
    group: "Finance",
    seeded: [],
  },
];

// The two DEF-188 sentences, quoted from `en.json` rather than paraphrased.
const SYSTEM_LOCK_TOOLTIP = "Came with the platform — cannot be deleted. Deactivate it instead.";
const RAW_KEY_THAT_MUST_NEVER_RENDER = "settings.lookups.system_row_not_deletable";

function referenceDataPath(): string {
  return `/${tenant()}/settings/reference-data`;
}

/** The card tile for a list, in the grid. */
function cardTile(page: Page, label: string): Locator {
  return page.locator(".lookup-card").filter({ hasText: label });
}

/** A list row, matched on its CODE cell exactly — never on a substring. */
function rowFor(page: Page, code: string): Locator {
  return page
    .locator("tr.data-table-row")
    .filter({ has: page.getByRole("cell", { name: code, exact: true }) });
}

/** The modal's primary button, whatever its label. */
function modalSubmit(page: Page): Locator {
  return page.locator(".modal-card .modal-foot button[type=submit]");
}

/**
 * PRE-FLIGHT, AND EXPLICITLY NOT PART OF THE PROOF — the only API calls in this
 * file, kept in one function so that is impossible to miss.
 *
 * The walkthrough asserts the card's count is EXACTLY the seeded count
 * (BR-TEN-029), which is the assertion worth having and also the one a crashed
 * previous run breaks: a run that dies between "add" and "delete" leaves one
 * `QA-…` row behind, and the NEXT run then fails on the card count with a
 * message that blames the product for the harness's mess. That happened on the
 * first execution of this file (all six lists timed out mid-walkthrough, and
 * the re-run reported "expected 6 › received 7 ›" on every one of them).
 *
 * So each test sweeps its own list clean of `QA-` rows before it starts. It
 * touches nothing else: the seeded vocabulary is `is_system` and the server
 * refuses to delete it (BR-TEN-036), which is the same rule step 2b proves
 * from the screen.
 */
async function sweepPreviousRunResidue(page: Page, listCode: string): Promise<void> {
  const base = `/api/${tenant()}/lookups/${listCode}`;
  const response = await page.request.get(`${base}?per=1000`);
  if (!response.ok()) {
    return;
  }
  const payload = (await response.json()) as { results?: { id: string; code: string }[] };
  for (const row of payload.results ?? []) {
    if (row.code.startsWith("QA-")) {
      await page.request.delete(`${base}/${row.id}`);
    }
  }
}

// ── The walkthrough, once per list ─────────────────────────────────────────
for (const list of LISTS) {
  test.describe(`CR-004 · ${list.label} ${APP_SERVER_TAG}`, () => {
    test(`full CRUD from the screen, and both refusals ${APP_SERVER_TAG}`, async ({ page }) => {
      // MEASURED, not guessed. `vite build` emits ONE 3.5 MB chunk and a full
      // page load of the built SPA costs ~10 s in this sandbox (the same fact
      // playwright.config.ts records for the 90 s default). This walkthrough is
      // deliberately a WALKTHROUGH — sign in, open the card, add, refuse,
      // refuse again, edit, deactivate, delete — and it re-reads the server
      // from scratch after every write, because "persisted" and "still on
      // screen" are different claims. Seven full loads is the floor for that,
      // and at the default the first run timed out on all six lists at exactly
      // the same line with every earlier assertion already green. The budget is
      // raised rather than the proof trimmed.
      test.setTimeout(300_000);

      // A run-unique code, so a crashed run can never block the next one.
      const stamp = Date.now().toString().slice(-7);
      const newCode = `QA-${stamp}`;
      const newName = `QA walkthrough ${stamp}`;
      const editedName = `QA walkthrough ${stamp} (edited)`;

      await signIn(page);
      await sweepPreviousRunResidue(page, list.code);

      // ── 1 · THE CARD RENDERS, IN ITS r10 GROUP, WITH THE LIVE COUNT ──────
      await page.goto(referenceDataPath());
      const tile = cardTile(page, list.label);
      await expect(tile).toHaveCount(1);
      await expect(tile).toBeVisible();
      // BR-TEN-029: the count is the server's, and it is the row count.
      // `import_mappings` is seeded empty, so this asserts "0 ›" for it — the
      // grid must NOT fall back to "Not set up yet", which is what an UNWIRED
      // list says and would hide a regression of DEF-187 in plain sight.
      await expect(tile.locator(".v")).toHaveText(`${list.seeded.length} ›`);
      // CR-004 task 1: the card files under its module heading.
      const section = page.locator("section.lookup-group").filter({ hasText: list.label });
      await expect(section.locator("h3")).toHaveText(list.group);

      // ── 2 · OPENING IT LISTS THE SEEDED ENTRIES ──────────────────────────
      // The assertion DEF-187 would have failed: before the `is None` branch
      // this navigation answered HTTP 500 and the frame rendered
      // "We couldn't load your reference data."
      await tile.click();
      await expect(page).toHaveURL(new RegExp(`list=${list.code}`));

      // ⚠ THE ORDER OF THE NEXT TWO LINES IS THE WHOLE ASSERTION, AND THE
      // FIRST DRAFT HAD IT WRONG. A bare `expect(failureCard).toHaveCount(0)`
      // straight after the click PASSES INSTANTLY — the query is still pending,
      // so nothing is on screen yet and "absent" is trivially true. Run against
      // a DEF-187 build it reported green and the test only went red four lines
      // later on the pager, with a message that named the pager. So: wait for
      // the body to SETTLE into one of its three possible states first, and
      // only then say which one it must not be.
      const failureCard = page.getByText("We couldn't load your reference data.");
      const listBody = page.locator("main.view table.data-table, main.view .state-empty");
      await expect(failureCard.or(listBody).first()).toBeVisible();
      await expect(
        failureCard,
        "DEF-187: this list answered HTTP 500 and the frame rendered the failure card",
      ).toHaveCount(0);

      if (list.seeded.length === 0) {
        // The honest empty state (A18), not a broken screen — and it must
        // still offer the way out.
        await expect(page.getByText(`No entries in ${list.label} yet.`)).toBeVisible();
        await expect(
          page.getByText("Add the first one — it appears in every picker that uses this list."),
        ).toBeVisible();
      } else {
        await expect(page.locator(".table-pager-range")).toHaveText(
          `1–${list.seeded.length} of ${list.seeded.length}`,
        );
        for (const code of list.seeded) {
          await expect(rowFor(page, code), `seeded row ${code} is on the screen`).toHaveCount(1);
        }
        if (list.seededName !== undefined) {
          await expect(
            page.getByRole("cell", { name: list.seededName, exact: true }),
            "the seeded NAME renders whole, mojibake and all escapes included",
          ).toBeVisible();
        }

        // ── 2b · BR-TEN-036 / DEF-188 · A SEEDED ROW'S DELETE ─────────────
        // Every one of these rows arrived with the platform (`is_system`), so
        // the control must be VISIBLE, DISABLED, and carry the reason in
        // English (BR-SHL-025). The pre-DEF-188 build drew an ENABLED delete
        // here and answered a raw key when it was pressed.
        const seededRow = rowFor(page, list.seeded[0]);
        const lockedDelete = seededRow.getByRole("button", { name: "🔒 Delete" });
        await expect(lockedDelete).toBeVisible();
        await expect(lockedDelete).toBeDisabled();
        await expect(lockedDelete).toHaveAttribute("title", SYSTEM_LOCK_TOOLTIP);
        // …and the same row still offers the alternative the sentence names.
        await expect(seededRow.getByRole("button", { name: "Deactivate" })).toBeEnabled();
        // The raw key must not be anywhere on this screen.
        await expect(page.locator("body")).not.toContainText(RAW_KEY_THAT_MUST_NEVER_RENDER);
      }

      // ── 3 · ADD PERSISTS ────────────────────────────────────────────────
      await page.getByRole("button", { name: "+ Add entry" }).first().click();
      await expect(page.locator(".modal-card")).toBeVisible();
      await expect(page.locator(".modal-title")).toHaveText(`Add to ${list.label}`);
      await page.locator("#code").fill(newCode);
      await page.locator("#name").fill(newName);
      await modalSubmit(page).click();
      await expect(page.locator(".toast")).toHaveText(`${newCode} added.`);
      await expect(rowFor(page, newCode)).toHaveCount(1);
      await expect(page.getByRole("cell", { name: newName, exact: true })).toBeVisible();
      // Persisted, not merely optimistic: a full reload re-reads the server.
      await page.reload();
      await expect(rowFor(page, newCode)).toHaveCount(1);
      // BR-TEN-029 again — the card's count moved with the write. Walked with
      // the screen's own "← Reference data" return (BR-SHL-035) rather than a
      // fresh `goto`: it is what a person clicks, and it costs no page load.
      await page.getByRole("button", { name: "← Reference data" }).click();
      await expect(cardTile(page, list.label).locator(".v")).toHaveText(
        `${list.seeded.length + 1} ›`,
      );
      await cardTile(page, list.label).click();
      await expect(page).toHaveURL(new RegExp(`list=${list.code}`));

      // ── 4 · BR-TEN-030 · A CASE-INSENSITIVE DUPLICATE IS REFUSED, AND THE
      //        REFUSAL NAMES THE EXISTING ENTRY ────────────────────────────
      await page.getByRole("button", { name: "+ Add entry" }).first().click();
      await page.locator("#code").fill(newCode.toLowerCase());
      await page.locator("#name").fill("QA duplicate probe");
      await modalSubmit(page).click();
      // The sentence a clerk reads, under the field they typed in — and it
      // says WHICH row, in the capitalisation that row actually uses.
      await expect(page.locator("#code-error")).toHaveText(
        `${newCode} already exists in this list. Codes are unique, whatever the capitalisation.`,
      );
      await expect(page.locator("#code")).toHaveAttribute("aria-invalid", "true");
      // Refused means refused: nothing was written.
      await page.locator(".modal-foot .btn-ghost").click();
      await expect(rowFor(page, "QA duplicate probe")).toHaveCount(0);
      await expect(page.locator(".table-pager-range")).toHaveText(
        `1–${list.seeded.length + 1} of ${list.seeded.length + 1}`,
      );

      // The same rule against a SEEDED code, where one exists — the codes the
      // r10 transcription supplied are the ones a clerk is most likely to
      // retype, and they are the rows a tenant cannot delete out of the way.
      if (list.seeded.length > 0) {
        await page.getByRole("button", { name: "+ Add entry" }).first().click();
        await page.locator("#code").fill(list.seeded[0].toLowerCase());
        await page.locator("#name").fill("QA seeded duplicate probe");
        await modalSubmit(page).click();
        await expect(page.locator("#code-error")).toHaveText(
          `${list.seeded[0]} already exists in this list. Codes are unique, whatever the capitalisation.`,
        );
        await page.locator(".modal-foot .btn-ghost").click();
      }

      // ── 5 · EDIT PERSISTS ───────────────────────────────────────────────
      await rowFor(page, newCode).getByRole("button", { name: "Edit" }).click();
      await expect(page.locator(".modal-title")).toHaveText(`Edit ${list.label} entry`);
      // The modal opens on the row's real values, not on blanks.
      await expect(page.locator("#code")).toHaveValue(newCode);
      await expect(page.locator("#name")).toHaveValue(newName);
      await page.locator("#name").fill(editedName);
      await modalSubmit(page).click();
      await expect(page.locator(".toast")).toHaveText(`${newCode} updated.`);
      await expect(page.getByRole("cell", { name: editedName, exact: true })).toBeVisible();
      await page.reload();
      await expect(page.getByRole("cell", { name: editedName, exact: true })).toBeVisible();

      // ── 6 · DEACTIVATE CHANGES THE STATUS ───────────────────────────────
      const ourRow = rowFor(page, newCode);
      await expect(ourRow.locator(".pill")).toHaveText("Active");
      await ourRow.getByRole("button", { name: "Deactivate" }).click();
      await expect(page.locator(".toast")).toHaveText(`${newCode} deactivated.`);
      await expect(rowFor(page, newCode).locator(".pill")).toHaveText("Inactive");
      await page.reload();
      await expect(rowFor(page, newCode).locator(".pill")).toHaveText("Inactive");
      // …and the control is now the other half of the same button (r10 draws
      // one control, not two), so the state is reversible from the screen.
      await expect(
        rowFor(page, newCode).getByRole("button", { name: "Reactivate" }),
      ).toBeEnabled();

      // ── 7 · DELETE REMOVES IT ───────────────────────────────────────────
      // Allowed here and refused two steps up, for the reason BR-TEN-034/036
      // give: this row is ours (`is_system` false) and nothing references it.
      await rowFor(page, newCode).getByRole("button", { name: "Delete", exact: true }).click();
      // BR-SHL-032 / IS-6: the confirm names the action and states what it costs.
      await expect(page.locator(".modal-title")).toHaveText(`Delete ${newCode}?`);
      await expect(page.locator(".confirm-consequence")).toHaveText(
        `${newCode} — ${editedName} is removed from this list. Nothing references it, so nothing else changes.`,
      );
      await page.getByRole("button", { name: `Delete ${newCode}` }).click();
      await expect(page.locator(".toast")).toHaveText(`${newCode} deleted.`);
      await expect(rowFor(page, newCode)).toHaveCount(0);
      await page.reload();
      await expect(rowFor(page, newCode)).toHaveCount(0);

      // ── 8 · THE LIST IS BACK EXACTLY AS IT WAS ──────────────────────────
      await page.getByRole("button", { name: "← Reference data" }).click();
      await expect(cardTile(page, list.label).locator(".v")).toHaveText(`${list.seeded.length} ›`);
    });
  });
}

// ── The mojibake check the walkthrough was asked to carry ──────────────────
//
// Three seeded meter-size-class names carried a double-escaped `Ï†` where a
// `φ` belonged — UTF-8 bytes read back as Latin-1 and re-encoded, the classic
// shape. It is asserted on the RENDERED CELL rather than on the seeder,
// because the seeder is one of four places the bytes pass through and the only
// one that matters is the one a person looks at.
test(`CR-004 · utility service size classes render φ, not Ï† ${APP_SERVER_TAG}`, async ({ page }) => {
  await signIn(page);
  await page.goto(`${referenceDataPath()}?list=service_size_classes`);
  await expect(page.getByRole("button", { name: "← Reference data" })).toBeVisible();

  for (const name of [
    "Electric 1φ 100A · base $18.50",
    "Electric 1φ 200A · base $24.00",
    "Electric 3φ · base $34.00",
  ]) {
    await expect(page.getByRole("cell", { name, exact: true })).toBeVisible();
  }
  // The negative half, and it is the half that would have caught the defect:
  // a passing positive assertion elsewhere on the page cannot rule out a
  // mojibake sitting in a row nobody named.
  await expect(page.locator("main.view")).not.toContainText("Ï†");
  await expect(page.locator("main.view")).not.toContainText("Ã");
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-004 tasks 11–16 · PO bar "full CRUD working - from Ui scren not
//   just backend" · DEF-187 · DEF-188
// generated: 2026-08-17 by the CR-004 browser-walkthrough QA lane
// gates: run against `08-qa/01-e2e/stack/boot_stack.sh` on a seeded
//   `brazosbend`; every quoted string copied from the running screen, not from
//   the catalogue
// exceptions: this spec WRITES (add/edit/deactivate/delete) and must only ever
//   be pointed at a disposable tenant — the same posture, and the same warning,
//   as DEF-178-primary-actions.spec.ts
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
