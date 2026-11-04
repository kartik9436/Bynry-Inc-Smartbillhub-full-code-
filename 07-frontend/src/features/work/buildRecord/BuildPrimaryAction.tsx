// ── Trace ──────────────────────────────────────────────
// Change:   CR-150-BRC09 task 5 — the page header's primary act. MOVED here
//           from `features/customers/BuildDetailShared.tsx:596` by
//           `DEF-CUS-7618`, unchanged.
// Rules:    `BR-SHL-025` (the control says why first; the server refuses
//           regardless) · `BR-SHL-044 (a)` (the primary act is per tab) ·
//           B14 rule 43 · rule 33 (a two-word label)
// Tests:    src/features/customers/BuildDetailPage.dom.test.tsx
// ───────────────────────────────────────────────────────
/**
 * The primary act, in the header. Its refusal is the same shared check.
 *
 * ⚠ **IT IS NOT `BuildRecordActions`, AND THE DIFFERENCE IS THE SLOT RATHER
 * THAN THE ACT.** `buildRecord/BuildRecordActions.tsx` is the RECORD's action
 * row — three buttons side by side (Add work order · Edit details ·
 * Activate), drawn by blueprint p105 inside `BuildRecordHeader`. `PageHeader`
 * takes ONE `primaryAction` per tab (`BR-SHL-044 (a)`), and `01-overview.png`
 * draws exactly one beside `More ▾`. Mounting the record's three-button row in
 * that slot would put two of them on a page whose header the Product Owner had
 * just finished taking buttons OFF (2026-09-28, *"since we have given link for
 * them in overview"*).
 *
 * ⚠ **WHAT IS SHARED IS THE THING THAT MATTERS: THE REFUSAL.**
 * `actBlockedReason` is `buildViews.tsx`'s one answer to *may this build be
 * acted on*, and `BuildRecordActions` asks it too — so a cancelled build
 * refuses this button on the screen and not at the server, and the two hosts
 * cannot disagree about one build.
 */
import { Button } from "@/components/Button";
import type { Translator } from "@/features/customers/newConnectShared";

import { actBlockedReason } from "../buildViews";
import type { BuildFacts } from "../workEndpoints";

export function BuildPrimaryAction(props: {
  t: Translator;
  build: BuildFacts;
  working: boolean;
  onPress: () => void;
  /** ⊕ `DEF-MET-9238` — a read-only role's reason, ahead of the build's own. */
  blockedReason?: string | null;
}) {
  const reason = props.blockedReason || actBlockedReason("raiseOrder", props.build, props.t);
  return (
    <Button
      variant="primary"
      data-act="raiseOrder"
      disabled={reason !== null || props.working}
      title={reason ?? undefined}
      data-blocked-reason={reason ?? undefined}
      onClick={reason === null ? props.onPress : undefined}
    >
      {props.t("customers.build.act.raiseOrder", { defaultValue: "Raise order" })}
    </Button>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-CUS-7618 · CR-151-BRC09 §2 rule (2)
// generated: 2026-09-28 by the DETAIL PAGE lane; MOVED into the kit the same
//   day by the DEF-CUS-7618 lane, unchanged
// checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=deferred(PO)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
