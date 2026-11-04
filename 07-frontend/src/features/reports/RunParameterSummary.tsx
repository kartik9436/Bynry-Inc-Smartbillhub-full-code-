// ── Trace ──────────────────────────────────────────────
// Change:  CR-179-BRC10 — the walk of 2026-10-12
//          (`05-prototype/rate-impact-2026-10-12/walk/README.md`): History's
//          PARAMETERS cell printed a Rate Impact run's raw `rows` JSON, with
//          schedule and version DATABASE IDS and size codes in it.
// Rules:   B14 rule 31 (no database id is ever a visible value) · rule 43 (a
//          piece of UI is a COMPONENT) · rule 21 (Tailwind utilities; this
//          file is on `src/styles/route-b-migrated.txt`) · CLAUDE.md hard
//          rule 2 (an amount shows 2 places, a unit price up to 4)
// Tests:   src/features/reports/runHistoryOpenInReport.dom.test.tsx
// Impacts: ReportRunsPage.tsx (the PARAMETERS cell)
// ───────────────────────────────────────────────────────
import type { RunSummaryLine, RunSummaryPart } from "@/api/runHistoryEndpoints";
import { formatMoneyInput, formatRateNumber } from "@/components/MoneyCell";
import type { Translator } from "@/features/tenancy/settingsShared";

import { inputText } from "./ReportInputs";

function partText(part: RunSummaryPart, t: Translator): string {
  if ("text" in part) return part.text;
  return inputText(part.label_key, t, part.params);
}

/**
 * A run's parameters IN WORDS — what the server's report said the run
 * modelled (`apps/reports/run_history.summary`). One line per part of the
 * question: services · classes · months, then each modelled row as
 * *item · version · capacity* and its typed figures.
 *
 * The run's stored filters are NOT read here: they hold ids, and they stay
 * untouched for *Open in report*, which replays them.
 */
export function RunParameterSummary(props: { lines: readonly RunSummaryLine[]; t: Translator }) {
  return (
    <ul className="m-0 flex list-none flex-col gap-1 p-0" data-run-summary="">
      {props.lines.map((line, index) => {
        const head = line.parts.map((part) => partText(part, props.t)).filter((text) => text !== "");
        const figures = (line.figures ?? []).map(
          (figure) =>
            `${props.t(figure.label_key)} ${
              figure.kind === "unit_price" ? formatRateNumber(figure.value) : formatMoneyInput(figure.value)
            }`,
        );
        return (
          <li key={index}>
            {head.join(" · ")}
            {figures.length > 0 && <span className="text-neutral-600"> · {figures.join(" · ")}</span>}
          </li>
        );
      })}
    </ul>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-179-BRC10 walk of 2026-10-12 (05-prototype/rate-impact-2026-10-12/walk/)
// screens: 5·1 History
// generated: 2026-10-12 by the Rate Impact walk-fix lane
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
