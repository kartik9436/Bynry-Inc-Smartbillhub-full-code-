// ── Trace ──────────────────────────────────────────────
// Story:    US-AST-011 (capture and store consumption + export read records on
//           net-meter reads — BR-AST-029's TWO records) · US-AST-012 (surface
//           the typed records; TC-1: "the S29 drawer shows each record's type +
//           a link to its paired record") · US-MET-013 (the drawer this renders
//           inside)   Screens: S29 (S25 lists the two rows separately)
// Rules:    BR-AST-029 (a net meter's cycle read is ONE consumption record and
//           ONE export record sharing a `read_at`; a missing export record →
//           0-value record + review flag, never silence) · BR-AST-010 (only
//           assets with `net_metering = true` carry export records) ·
//           BR-AST-025 (reads feed rating as INPUTS ONLY — export renders as
//           quantity + unit everywhere and NEVER as money; the credit math is
//           rating's EP-RAT-06, gated by OQ-001) · BR-AST-016 (net reads render
//           as two typed rows) · CLAUDE.md rule 3 (a quantity carries its unit)
// Tests:    07-frontend/src/features/metering/NetMeterPair.test.tsx ·
//           06-backend/tests/test_us_ast_011_012_net_reads.py (the read half)
// ───────────────────────────────────────────────────────
// A solar customer's cycle, as a PAIR — which is the whole of US-AST-011/012
// and is the thing that did not exist.
//
// The surface-debt register said it plainly on 2026-08-16: *"US-AST-011's
// net-metering import/export read PAIR — `apps/metering/validation.py` enforces
// the rule and `models.py` carries the channel, and no screen shows the two
// channels AS A PAIR, which is the whole point of the story."* The storage
// model shipped in W2, the validation refused an export record on a flat meter,
// the import wizard created a flagged 0-value record when a net cycle arrived
// without one — and a clerk looking at a solar account saw two unrelated rows
// in a list sorted by date. The rule was enforced and invisible.
//
// THREE THINGS THIS COMPONENT WILL NOT DO, each because a rule says so:
//
//   1. **It never nets the two figures.** 684 kWh in and 120 kWh out is not
//      "564 kWh". Subtracting one from the other IS the net-metering credit
//      computation, that lives in rating (EP-RAT-06) and is gated by OQ-001 —
//      v1 bills solar as capacity charges. Two quantities of the same unit can
//      measure entirely different things (CLAUDE.md rule 3), and this pair is
//      exactly that case: energy DELIVERED against energy FED BACK.
//
//   2. **It never shows money.** BR-AST-025: *"export renders as quantity +
//      unit everywhere, never money"*. There is no currency prop on this
//      component and no arithmetic in it.
//
//   3. **It never prints a zero it did not measure.** A flat meter renders
//      NOTHING — not "Export: 0", which would be a measurement of a register
//      that does not exist. A net meter whose export register was not read says
//      so in words. The server sends a CODE for each case and this file renders
//      one sentence per code (`absent_reason`).
import { useTranslation } from "react-i18next";

import { PAIR_NOT_NET_METER, PAIR_NO_CONSUMPTION_RECORD } from "@/api/endpoints";
import type { NetMeterPair as NetMeterPairPayload, NetMeterPairSide } from "@/api/endpoints";

import "./reads.css";
import { Kicker } from "@/components/TextBits";

// ── Pure pieces (provable without a browser or a network) ─────────────────

/**
 * Does this reading have a pair worth drawing?
 *
 * FALSE for a flat meter, and that is the load-bearing case: every ordinary
 * water and electric reading in the product passes through this drawer, and a
 * net-metering panel on all of them would be noise at best and a claim about a
 * register that does not exist at worst (BR-AST-010).
 */
export function hasNetPair(pair: NetMeterPairPayload | undefined): boolean {
  return pair !== undefined && pair.is_net_meter && pair.absent_reason !== PAIR_NOT_NET_METER;
}

/**
 * The sentence for a pair that is incomplete, or null when it is whole.
 *
 * One key per server CODE. A default is deliberately absent: a reason the
 * server starts sending tomorrow renders as its own code rather than as a
 * confident sentence this file invented for it.
 */
export function pairAbsenceKey(pair: NetMeterPairPayload): string | null {
  if (pair.absent_reason === null) {
    return null;
  }
  if (pair.absent_reason === PAIR_NO_CONSUMPTION_RECORD) {
    return "metering.read.netPair.noConsumption";
  }
  return "metering.read.netPair.noExport";
}

// ── The panel ──────────────────────────────────────────────────────────────

export function NetMeterPair(props: { pair: NetMeterPairPayload }) {
  const { t } = useTranslation();
  const { pair } = props;
  if (!hasNetPair(pair)) {
    return null;
  }
  const absence = pairAbsenceKey(pair);
  return (
    <section className="rd-block rd-netpair">
      <Kicker>{t("metering.read.netPair.title")}</Kicker>
      {/* The pair, side by side, because side by side IS the feature. A clerk
          answering "did this customer export more than they used?" reads two
          numbers in one glance; two rows a scroll apart in a date-sorted list
          is what this replaces. */}
      <div className="rd-netpair-grid">
        <NetSide
          side={pair.consumption}
          labelKey="metering.read.netPair.imported"
          helpKey="metering.read.netPair.importedHelp"
        />
        <NetSide
          side={pair.export}
          labelKey="metering.read.netPair.exported"
          helpKey="metering.read.netPair.exportedHelp"
        />
      </div>
      {absence !== null && (
        <p className="rd-netpair-absent" role="status">
          {t(absence)}
        </p>
      )}
      {/* OQ-001, on the screen rather than in a comment. Without this line the
          two figures read like a bill in the making, and they are not: v1
          bills solar as a capacity charge and computes no credit at all. */}
      <p className="met-panel-hint">{t("metering.read.netPair.noCreditYet")}</p>
    </section>
  );
}

/**
 * One side. Renders the SERVER's `usage_display` and has no prop that could
 * take a bare number — the same construction `UsageCell` uses, for the same
 * reason: a quantity that reaches a screen without its unit cannot get it back.
 */
function NetSide(props: { side: NetMeterPairSide | null; labelKey: string; helpKey: string }) {
  const { t } = useTranslation();
  return (
    <div className="rd-netpair-side">
      <Kicker>{t(props.labelKey)}</Kicker>
      <span className="rd-netpair-value">
        {/* An em-dash, never a 0. The absence line below the grid says which
            of the two absences this is. */}
        {props.side?.usage_display ?? "—"}
      </span>
      <span className="rd-netpair-help">{t(props.helpKey)}</span>
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-AST-011@9d8d058 (EP-AST-05 net-meter reads — BR-AST-029's two-record model; co-story US-AST-012@9d8d058)
// generated: 2026-08-16 by story-coder v1 (surface-debt lane — the metering line's last unreachable story)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(N/A — not a 🔒 path: no money, no key, no rounding rule; the panel renders quantities the server composed)
// gates: tsc✔ eslint --max-warnings 0✔ vitest (see the lane report) · G15 11 catalogues, identical key sets✔ · G13 unwired-props✔
// exceptions: E3 the panel is drawn INSIDE the S29 drawer rather than as a screen of its own — US-AST-012 TC-1 puts it there by name ("the S29 drawer shows each record's type + a link to its paired record"), and a solar cycle is a property of a reading rather than a page · E3 the S50 asset Reads tab (US-AST-012 TC-2) does NOT show the pair, and the reason is one story further back — VERIFIED rather than assumed: S50 HAS a Reads tab (`AssetDetailPage`'s `ASSET_DETAIL_TABS` declares `reads`) and it renders an `ArrivesWith` placeholder, because US-AST-005's `GET /assets/{id}/reads` is not served and an empty table there would claim *this asset has no reads*. So there is no per-asset read LIST for this panel to sit in yet; the story's own §1 lists three surfaces and S25/S29 are the two that exist. REPORTED · E4 the two figures are NEVER combined: 684 kWh delivered against 120 kWh exported does not render "564" anywhere, because that subtraction IS the net-metering credit math (rating's EP-RAT-06, gated by OQ-001) and v1 bills solar as capacity charges. The screen says so in a sentence rather than leaving a reader to assume a credit is coming · E4 a flat meter renders NOTHING here rather than "Export: 0" — a zero would be a measurement of a register that does not exist (BR-AST-010)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
