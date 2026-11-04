/**
 * Renders the eight CR-075 wave C kit components to a static HTML fragment, so
 * `cr075-c-runbook-kit.mjs` can open them in a REAL browser with the REAL built
 * stylesheet and measure what a person would see.
 *
 * ⚠ THE COMPONENTS ARE IMPORTED, NOT RE-TYPED. `column-chooser-geometry.mjs`
 * next door copies its markup hunk-for-hunk from `DataTable.tsx` and says in
 * its own comment that a copy which drifts measures nothing. Importing removes
 * that failure mode entirely: if a component changes, this measures the change.
 *
 * RUN (from 07-frontend, which owns the alias and the deps):
 *   npx vite-node ../10-scripts/render-checks/cr075-c-runbook-kit.render.tsx
 */
import { writeFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
// ⚠ `MemoryRouter`, NOT `StaticRouter`. Under vite-node, `react-router-dom`
// and `react-router-dom/server` resolve to two module instances, so the
// server router's context is invisible to the `Link`s inside it and every
// render dies on `Cannot destructure property 'basename' of null`. One
// module, one context.
import { MemoryRouter } from "react-router-dom";

import {
  ActionBlock, BreakdownBlock, FactsBlock, ReconciledBlock, RowDecisionsBlock,
} from "../../07-frontend/src/features/runbooks/blocks";
import type { BlockContext } from "../../07-frontend/src/features/runbooks/blocks";
import { Chain } from "../../07-frontend/src/components/Chain";
import { ContributionBars } from "../../07-frontend/src/components/ContributionBars";
import { OutcomeCard } from "../../07-frontend/src/components/OutcomeCard";
import { PercentCell } from "../../07-frontend/src/components/PercentCell";
import { RecordGrid } from "../../07-frontend/src/components/RecordGrid";
import {
  SettingsOwnedField,
  SettingsOwnedProvider,
} from "../../07-frontend/src/components/SettingsOwnedField";
import { Sparkline } from "../../07-frontend/src/components/Sparkline";
import { VerdictBand } from "../../07-frontend/src/components/VerdictBand";

/** `RBS-006-R1` region 3, cell for cell. */
const CHAIN = [
  { id: "1", position: 1, label: "Services", state: "ok" as const },
  { id: "2", position: 2, label: "Reference data", state: "ok" as const },
  { id: "3", position: 3, label: "Tax", state: "bad" as const, note: "No tax region set" },
  { id: "4", position: 4, label: "Plans", state: "ok" as const },
  { id: "5", position: 5, label: "Rate coverage", state: "bad" as const, note: "No block above 20,000 gal" },
  { id: "6", position: 6, label: "Account chain", state: "bad" as const, note: "240 accounts have no unit" },
  { id: "7", position: 7, label: "Meters", state: "ok" as const },
  { id: "8", position: 8, label: "Reads", state: "ok" as const },
  { id: "9", position: 9, label: "Documents", state: "ok" as const },
  { id: "10", position: 10, label: "Books", state: "ok" as const },
];

/** `RBS-006-R4` region 4. */
const BARS = [
  { id: "a", label: "More water used", detail: "7,240 gal vs 5,250 gal · 4 more days", weight: 46.4, value: "+$46.40" },
  { id: "b", label: "Reached tier 2", detail: "Usage above 5,000 gal priced higher", weight: 14.8, value: "+$14.80" },
  { id: "c", label: "Late fee", detail: "August paid 12 days late", weight: 12, value: "+$12.00" },
  { id: "d", label: "Tax on the above", detail: "Follows the charges", weight: 9, value: "+$9.00" },
  { id: "e", label: "Rate change", detail: "None between the two bills", weight: 0, value: "$0.00" },
  { id: "f", label: "Meter", detail: "Same meter, same multiplier", weight: 0, value: "$0.00" },
];

const GRID = [
  ...Array.from({ length: 21 }, (_, i) => ({
    id: `c${i}`, label: `Account ${i + 1}`, state: "clean" as const,
    to: `/silvercreek/runbooks/coverage-grid/records/c${i}`,
  })),
  { id: "e0", label: "Hale, T.", state: "estimated" as const, to: "/silvercreek/runbooks/coverage-grid/records/e0" },
  { id: "e1", label: "Nunes, R.", state: "estimated" as const, to: "/silvercreek/runbooks/coverage-grid/records/e1" },
  { id: "r0", label: "Marsh Farms", state: "refused" as const, to: "/silvercreek/runbooks/coverage-grid/records/r0", reason: "No rate above 20,000 gal" },
  { id: "r1", label: "Riverside Apts", state: "refused" as const, to: "/silvercreek/runbooks/coverage-grid/records/r1", reason: "No tax region set" },
];

const BCTX: BlockContext = { timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" };

const TWELVE = [5100, 5250, 5180, 5300, 5220, 5400, 9100, 5300, 5250, 5310, 5280, 7240];

function section(id: string, title: string, body: React.ReactNode) {
  return (
    <section data-probe={id} style={{ marginBottom: "28px" }}>
      <h2 style={{ font: "700 12px/1.4 system-ui", letterSpacing: ".08em", textTransform: "uppercase", color: "#7d7979", margin: "0 0 8px" }}>
        {title}
      </h2>
      {body}
    </section>
  );
}

const body = renderToStaticMarkup(
  <MemoryRouter initialEntries={["/silvercreek/runbooks/configuration-check/runs/today"]}>
    <div style={{ padding: "24px", maxWidth: "1180px" }}>
      {section("verdict", "VerdictBand · RBS-006-R9",
        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          <VerdictBand word="Not balanced" tone="danger" count="6 of 9 steps clear"
            detail="Tax off by $14.25 · $312.00 unapplied · 3 bank lines unmatched" />
          <VerdictBand word="Balanced" tone="success" count="9 of 9 steps clear"
            detail="Receivables · revenue · tax · deposits all tie · exports ready"
            action={<button type="button" className="border border-danger-500 bg-transparent px-3 py-1 text-md text-danger-700">Close period ✓</button>} />
          <VerdictBand word="14 eligible" tone="warning" count="9 removed since the letter"
            detail="4 paid overnight · 3 protected · 2 under minimum" />
        </div>)}
      {section("chain", "Chain · RBS-006-R1 region 3",
        <Chain cells={CHAIN} label="Ten steps, three stopped billing." />)}
      {section("bars", "ContributionBars · RBS-006-R4 region 4",
        <ContributionBars rows={BARS} label="What caused it, largest first." />)}
      {section("outcome", "OutcomeCard · RBS-006-R4 region 6",
        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          <OutcomeCard tone="success" label="Read this aloud">
            &quot;Your September bill is $82.20 higher. You used 38.00% more water over 4 more days,
            which also took you into the higher price tier. A $12.00 late fee was added for August.
            Your rate did not change.&quot;
          </OutcomeCard>
          <OutcomeCard tone="danger" label="Stop"><strong>3 things stop billing.</strong> Nothing was sent.</OutcomeCard>
          <OutcomeCard tone="muted">Nothing to do today.</OutcomeCard>
        </div>)}
      {section("settings", "SettingsOwnedField · RBS-004-R8",
        <SettingsOwnedProvider values={{ "ladder.tiers": "5 tiers", "quiet.hours": "20:00–08:00" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            <SettingsOwnedField setting="ladder.tiers" label="Ladder tiers" ownedBy="From Settings"
              to="/silvercreek/settings/collections" openLabel="Open settings →"
              absent={{ notLoaded: "Not loaded", notSet: "Not set in Settings" }} />
            <SettingsOwnedField setting="quiet.hours" label="Quiet hours" ownedBy="From Settings"
              to="/silvercreek/settings/notifications" openLabel="Open settings →"
              absent={{ notLoaded: "Not loaded", notSet: "Not set in Settings" }} />
            <SettingsOwnedField setting="grace.days" label="Grace days" ownedBy="From Settings"
              to="/silvercreek/settings/collections" openLabel="Open settings →"
              absent={{ notLoaded: "Not loaded", notSet: "Not set in Settings" }} />
          </div>
        </SettingsOwnedProvider>)}
      {section("percent", "PercentCell · hard rule 2 — DISPLAY 2",
        <table className="w-full" style={{ borderCollapse: "collapse" }}>
          <tbody>
            {[
              ["Tax rate (stored 0.062500, a fraction)", <PercentCell key="a" value="0.062500" basis="fraction" />],
              ["Bill change (stored 38, points)", <PercentCell key="b" value="38" basis="points" signed direction="up" />],
              ["Revenue (stored 4.7, points)", <PercentCell key="c" value="4.7" basis="points" signed direction="up" />],
              ["Of total (stored 0.29, points)", <PercentCell key="d" value="0.29" basis="points" />],
              ["Limit (stored 0.05, points)", <PercentCell key="e" value="0.05" basis="points" />],
              ["Down (stored -12.25, points)", <PercentCell key="f" value="-12.25" basis="points" direction="down" />],
            ].map(([label, cell], i) => (
              <tr key={i}>
                <td className="text-base text-neutral-700" style={{ padding: "3px 16px 3px 0" }}>{label}</td>
                <td className="text-md" style={{ padding: "3px 0", textAlign: "right", width: "120px" }}>{cell}</td>
              </tr>
            ))}
          </tbody>
        </table>)}
      {section("sparkline", "Sparkline · RBS-006-R5 column 4",
        <table style={{ borderCollapse: "collapse" }}>
          <tbody>
            <tr><td className="text-base" style={{ padding: "4px 16px 4px 0" }}>▲ Spike · Jul</td>
              <td><Sparkline points={TWELVE} label="Twelve months of water use, in gallons." markAt={6} /></td></tr>
            <tr><td className="text-base" style={{ padding: "4px 16px 4px 0" }}>▬ Flat · 5 months</td>
              <td><Sparkline points={[5200, 5200, 5200, 5200, 5200, 5200]} label="Flat for five months, in gallons." /></td></tr>
            <tr><td className="text-base" style={{ padding: "4px 16px 4px 0" }}>≈ Estimated · 6 of 12</td>
              <td><Sparkline points={TWELVE} label="Estimated, in gallons." source="estimated" /></td></tr>
          </tbody>
        </table>)}
      {section("blocks", "C1b blocks · Reconciled + Facts + Action + Row decisions",
        <div style={{ display: "flex", flexDirection: "column", gap: "18px" }}>
          <ReconciledBlock ctx={BCTX} payload={{
            heading: "Tie-out", tiesLabel: "Ties",
            columns: [
              { key: "line", label: "Line" },
              { key: "recorded", label: "Recorded", numeric: true },
              { key: "books", label: "In the books", numeric: true },
              { key: "diff", label: "Difference", numeric: true },
            ],
            rows: [
              { id: "r1", cells: {
                line: { kind: "text", text: "Receivables" },
                recorded: { kind: "money", amount: "1204318.2200", currency: "USD" },
                books: { kind: "money", amount: "1204318.2200", currency: "USD" },
                diff: { kind: "pill", label: "Ties", tone: "success" } } },
              { id: "r2", cells: {
                line: { kind: "text", text: "Tax" },
                recorded: { kind: "money", amount: "23304.7600", currency: "USD" },
                books: { kind: "money", amount: "23290.5100", currency: "USD" },
                diff: { kind: "money", amount: "-14.2500", currency: "USD" } } },
            ] }} />
          <FactsBlock ctx={BCTX} payload={{ heading: "Three kinds of number, one table", rows: [
            { id: "a", label: "Bill change", value: { kind: "percent", value: "38", basis: "points", signed: true, direction: "up" } },
            { id: "b", label: "Tax rate", value: { kind: "percent", value: "0.062500", basis: "fraction" } },
            { id: "c", label: "Tariff rate", value: { kind: "rate", rate: "8.290000", currency: "USD" } },
            { id: "d", label: "Charge", value: { kind: "money", amount: "8.2900", currency: "USD" } },
            { id: "e", label: "Usage", value: { kind: "unit", quantity: "7240", unit: "gal" } },
          ] }} />
          <div style={{ display: "flex", gap: "24px", alignItems: "flex-start" }}>
            <ActionBlock onAct={() => {}} payload={{ label: "Close period ✓", tier: "danger", enabled: false, reason: "3 items open." }} />
            <ActionBlock onAct={() => {}} payload={{ label: "Raise work items ✓", tier: "primary", enabled: true }} />
          </div>
          <RowDecisionsBlock ctx={BCTX} onDecide={() => {}} payload={{
            heading: "Parcels that disagree",
            columns: [
              { key: "p", label: "Premises" },
              { key: "ours", label: "Ours" },
              { key: "theirs", label: "The City" },
            ],
            rows: [
              { id: "d1", cells: { p: { kind: "text", text: "14 Cedar St" }, ours: { kind: "text", text: "R-1" }, theirs: { kind: "text", text: "R-2" } } },
              { id: "d2", cells: { p: { kind: "text", text: "2 Mill Rd" }, ours: { kind: "text", text: "C-1" }, theirs: { kind: "text", text: "C-3" } } },
            ],
            choices: [{ id: "theirs", label: "Accept theirs →" }, { id: "ours", label: "Keep ours" }] }} />
          <BreakdownBlock ctx={BCTX} payload={{ heading: "By channel", columns: [
              { key: "c", label: "Channel" }, { key: "n", label: "Sent", numeric: true },
            ], rows: [
              { id: "b1", cells: { c: { kind: "text", text: "Email" }, n: { kind: "text", text: "248" } } },
              { id: "b2", cells: { c: { kind: "text", text: "Post" }, n: { kind: "text", text: "31" } } },
            ] }} />
        </div>)}
      {section("grid", "RecordGrid · the coverage grid, 21 clean · 2 estimated · 2 refused",
        <RecordGrid cells={GRID} label="25 accounts priced."
          empty={<span>Nothing priced yet. Run the coverage grid.</span>} />)}
    </div>
  </MemoryRouter>,
);

const out = process.argv[2];
if (out === undefined) throw new Error("usage: cr075-c-runbook-kit.render.tsx <out.html>");
writeFileSync(out, body);
console.log(`wrote ${body.length} bytes of markup to ${out}`);
