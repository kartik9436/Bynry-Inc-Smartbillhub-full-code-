/* ── Trace ──────────────────────────────────────────────
 * Story:   US-RBS-003 (EP-RBS-01) — CR-075 wave D task D2.
 * Screens: RBS-001.1 region 2, region 6.
 * Rules:   A12 (a tone is status MEANING, never decoration) · B14 rule 31 ·
 *          NFR-3 / NFR-5 (a total is the SERVER's, never a page length).
 * Defects: DEF-RBS-4304 (two tiles have no total) · DEF-RBS-4327 (the run list
 *          serves no verdict) · DEF-WRK-4096 (a zero we cannot stand behind is
 *          drawn as a dash).
 * ─────────────────────────────────────────────────────── */

/**
 * Every case here asserts a RULE, not an impression — the plan's definition of
 * done says so in terms.
 *
 * The one worth reading twice is *a dash is not a zero*: `homeKpis` must answer
 * `null` for the two figures nothing serves, and a future lane "fixing" that to
 * `0` would print *nothing is stopping the bill run* on the strip of a utility
 * whose bill run is blocked.
 */
import { describe, expect, it } from "vitest";

import { RUN_STATUS } from "./homeEndpoints";
import {
  formatTook,
  HEAD_DESTINATIONS,
  HELD_DESTINATIONS,
  homeKpis,
  isOpen,
  kindTone,
  OPEN_DESTINATIONS,
  statusTone,
} from "./runbooksHomeModel";
import type { RunRow } from "./homeEndpoints";
import { runResultPath } from "./runbooksHomeModel";

describe("RBS-001 region 2 — the KPI strip of four", () => {
  it("draws four tiles, in the frame's order", () => {
    expect(homeKpis({ awaitingApproval: 1, running: 0 }).map((k) => k.id)).toEqual([
      "blockBilling",
      "waitingForYou",
      "runningNow",
      "ranCleanToday",
    ]);
  });

  it("DEF-RBS-4304 — the two tiles with no source are NULL, never zero", () => {
    // A confident `0` under *Block billing* reads as "nothing is stopping the
    // bill run". The only honest answer the module can give today is "this is
    // not counted", and the screen draws that as a dash with a four-word line.
    const kpis = homeKpis({ awaitingApproval: 7, running: 2 });
    const byId = Object.fromEntries(kpis.map((k) => [k.id, k.value]));
    expect(
      byId.blockBilling,
      "Block billing has a number. The only work-item figure the module serves is open_items " +
        "PER RUNBOOK on the current page of GET /runbooks — a page total. If an aggregate now " +
        "exists, wire it and delete this case; do not fill the tile with a near-right number.",
    ).toBeNull();
    expect(
      byId.ranCleanToday,
      "Ran clean today has a number. status=done is equally true of a run that found three " +
        "blockers, so a done-today count is a different fact wearing the same label.",
    ).toBeNull();
  });

  it("the two servable tiles carry the SERVER's totals, unchanged", () => {
    const kpis = homeKpis({ awaitingApproval: 7, running: 2 });
    const byId = Object.fromEntries(kpis.map((k) => [k.id, k.value]));
    expect(byId.waitingForYou).toBe(7);
    expect(byId.runningNow).toBe(2);
  });

  it("a zero the server really answered is drawn as a zero", () => {
    // The mirror of the case above, and it matters just as much: *nothing is
    // waiting for you* is a true, useful answer and must not become a dash.
    const byId = Object.fromEntries(
      homeKpis({ awaitingApproval: 0, running: 0 }).map((k) => [k.id, k.value]),
    );
    expect(byId.waitingForYou).toBe(0);
    expect(byId.runningNow).toBe(0);
  });
});

describe("A12 — a status tone is status MEANING", () => {
  it("maps each of the eight run statuses to the meaning it has", () => {
    expect(statusTone(RUN_STATUS.done)).toBe("success");
    expect(statusTone(RUN_STATUS.failed)).toBe("danger");
    expect(statusTone(RUN_STATUS.awaitingApproval)).toBe("warning");
    expect(statusTone(RUN_STATUS.stopped)).toBe("muted");
    expect(statusTone(RUN_STATUS.approved)).toBe("info");
    expect(statusTone(RUN_STATUS.acting)).toBe("info");
    expect(statusTone(RUN_STATUS.running)).toBe("neutral");
    expect(statusTone(RUN_STATUS.queued)).toBe("neutral");
  });

  it("an unknown status is neutral rather than alarming", () => {
    // Wave L adds statuses. A word this screen has never seen must not arrive
    // in the danger colour, which B14 rule 6 reserves for destructive commits.
    expect(statusTone("something-wave-L-adds")).toBe("neutral");
  });

  it("Check is info and Action is danger — the same pairing RBS-002 uses", () => {
    expect(kindTone("check")).toBe("info");
    expect(kindTone("action")).toBe("danger");
  });
});

describe("how long it took", () => {
  it("spells a duration the way the frame does", () => {
    expect(formatTook(12)).toBe("12s");
    expect(formatTook(2)).toBe("2s");
    expect(formatTook(64)).toBe("1m 04s");
    expect(formatTook(242)).toBe("4m 02s");
    expect(formatTook(0)).toBe("0s");
  });

  it("a run with no duration answers null, so the cell draws a dash", () => {
    // A run in flight has no duration. Printing the seconds so far would be a
    // number that changes meaning between two reads of the same page.
    expect(formatTook(null)).toBeNull();
    expect(formatTook(Number.NaN)).toBeNull();
    expect(formatTook(-1)).toBeNull();
  });
});

describe("the held destinations, and the address of a run", () => {
  it("names the three screens RBS-001's head points at, in the frame's order", () => {
    // Templates → · History → · Work list →. The ORDER never moves; only the
    // tier does, so a clerk who learned where *History →* sits does not have to
    // learn again the week it starts working.
    //
    // ⚠ **THIS CASE SAID `OPEN = ["templates"]` AND `isOpen("history") === false`
    // UNTIL 2026-09-07, AND IT WAS TURNED AROUND RATHER THAN DELETED** — the
    // day `RBS-008` landed (`CR-075` wave I task `I6`). That is the whole job
    // of a hold-expiry assertion: it goes red when the hold expires, and the
    // repair is to state the opposite claim. Deleting it would leave the next
    // release with no clock at all, which is `DEF-CWP-3925` — six of eight
    // front-page doors still refusing over screens that shipped days earlier.
    expect(HEAD_DESTINATIONS.map((h) => h.screen)).toEqual(["RBS-002", "RBS-008", "RBS-007"]);
    //
    // ⚠ **AND TURNED AROUND AGAIN ON 2026-10-02 FOR *Work list →*** — `RBS-007`
    // had been declared and routed at `runbooks/work` since 2026-09-07
    // (`df1ade52e`) while this case still asserted the button was held.
    expect(OPEN_DESTINATIONS.map((h) => h.id)).toEqual(["templates", "history", "workList"]);
    expect(HELD_DESTINATIONS.map((h) => h.id)).toEqual([]);
    expect(isOpen("templates")).toBe(true);
    expect(isOpen("history")).toBe(true);
    expect(isOpen("workList")).toBe(true);
  });

  it("every held path is tenant-RELATIVE, so nothing builds //host/…", () => {
    // DEF-CWP-3925: a path that already carries a tenant comes out
    // `/{tenant}/{tenant}/…`, and a path with no leading slash comes out
    // protocol-relative — both of which read as perfectly good strings.
    for (const action of HEAD_DESTINATIONS) {
      expect(action.path.startsWith("/")).toBe(true);
      expect(action.path.startsWith("//")).toBe(false);
    }
  });

  it("a run's address is built from the tenant, the runbook KEY and the run id", () => {
    const row = {
      id: "018f-aaaa",
      runbook_key: "configuration_check",
      runbook_name: "Can we bill?",
    } as RunRow;
    expect(runResultPath("brazosbend", row)).toBe(
      "/brazosbend/runbooks/configuration_check/runs/018f-aaaa",
    );
  });

  it("a key with a slash in it is escaped rather than opening a different screen", () => {
    const row = { id: "r/1", runbook_key: "a/b", runbook_name: "x" } as RunRow;
    expect(runResultPath("t", row)).toBe("/t/runbooks/a%2Fb/runs/r%2F1");
  });
});

/* ── Lifecycle ─────────────────────────────────────────────
 * packet: US-RBS-003 (CR-075 wave D task D2)
 * generated: 2026-09-06 by the CR-075 wave D task D2 build lane
 * checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a
 * gates: ./node_modules/.bin/vitest run src/features/runbooks/home/runbooksHomeModel.test.ts
 * exceptions: none
 * status: VERIFIED-UNRATIFIED
 * ────────────────────────────────────────────────────────── */
