// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 §30, lane BOARDS — the At risk board becomes its own
//           Work tab, right after Orders, with its own address and badge.
// Ruling:   PO answer (1) of 2026-10-05, verbatim: *"(b) Make At risk its own
//           tab next to Orders, because the design says "a dispatcher opens it
//           first". Schedule and Raise across buildings stay inside
//           Performance."* (decision log *"FOUR PO ANSWERS ON WORK"*). It
//           supersedes lane PERFORMANCE's judgment (2.514.0) that the board is
//           a view of Performance.
// Rules:    B14 rule 2 (one page header, the shared strip) · rule 20 · rule 21
//           (on route-b-migrated.txt) · rule 32 (one sentence) · rule 43 (the
//           board is a COMPONENT, mounted here and nowhere else) · NFR-3 (the
//           board pages on the server, unchanged) · G29 (`WRK-25`, minted)
// Tests:    src/features/work/performance/cr168Performance.dom.test.tsx ·
//           src/features/work/WorkShell.test.tsx
// ───────────────────────────────────────────────────────
//
// THE BOARD IS UNCHANGED; ONLY WHERE IT LIVES MOVED. `AtRiskBoard` reads the
// same `GET /work/at-risk` it read as a view of Performance. The old address,
// `/work/performance?view=at-risk`, forwards here (`PerformancePage`), so a
// bookmark or a link made under 2.514.0 lands on this tab rather than on the
// Results view it would otherwise fall back to.
import { useTranslation } from "react-i18next";

import type { ApiClient } from "@/api/client";
import { PageHeader } from "@/components/PageHeader";

import { useWorkTabs } from "./WorkShell";
import { AT_RISK_SCREEN, AtRiskBoard } from "./performance/AtRiskBoard";

export function AtRiskPage(props: { client?: ApiClient }) {
  const { t } = useTranslation();
  const strip = useWorkTabs(t("work.atRisk.description"));
  return (
    <section aria-label={t("work.tabs.atRisk")} data-work-at-risk="" data-screen={AT_RISK_SCREEN}>
      <PageHeader title={t("work.tabs.atRisk")} {...strip} />
      <AtRiskBoard client={props.client} />
    </section>
  );
}

export default AtRiskPage;
