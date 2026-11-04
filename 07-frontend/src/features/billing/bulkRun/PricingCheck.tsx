// ── Trace ──────────────────────────────────────────────
// Screen:   S31 · BIL-02 — the bill run, step 2 Check (S31.2's pricing check)
// Ruling:   OQ-BIL-12791 → A (PO 2026-10-13, decision log "THREE PO RULINGS ON
//           THE LEFT-OVER SCREEN PIECES") — the Check step shows it again
// Defect:   DEF-BIL-10121 — the comparison left the run in 91eca0bff
// Server:   GET /billing/runs/{id}/pricing-shadow (apps/billing/api.py
//           `run_pricing_shadow` → `shadow_report.report_for_prepared`)
// Rules:    B14 rules 21, 33 (a fact ≤ 6 words), 43 (a component), 44
// ───────────────────────────────────────────────────────
/**
 * THE PRICING CHECK — one line on the Check step: does the new pricing chain
 * give a different answer from today's billing on any bill in this run?
 *
 * Most months it reads **0 differences**. When it does not, it reads
 * `3 bills differ` and *Show bills* opens `PricingShadowPanel` — the S31.2
 * comparison, kept whole, with both figures side by side and NEITHER chosen.
 *
 * ⚠ **NO "LARGEST +$X".** The PO was shown *"3 bills differ, largest +$4.20"*
 * as an illustration (B14 rule 37). The comparison's own ruling is that nothing
 * subtracts the two figures — which one is right is the Product Owner's call at
 * cutover step 4, not this screen's — and phase 1 computes no bill total to
 * subtract from. So the count is the fact; the figures are in the list.
 *
 * ⚠ **FOUR STATES, AND ONLY ONE OF THEM MAY SAY 0.** A read in flight, a read
 * that failed, and a body the screen cannot read (`isPricingShadow`, DEF-2402)
 * each say what they are. `attempted === 0` is "No bills checked", never a
 * clean zero — *"0 disagreed is also what perfect agreement looks like."*
 *
 * It is a SEPARATE read from the Check's findings on purpose (the server's own
 * docstring): an advisory comparison that is slow or fails never takes the
 * Check down with it, so its failure is drawn here and nowhere else.
 */
import { useEffect, useState } from "react";

import type { BillRunPricingShadow } from "@/api/endpoints";
import { getBillRunPricingShadow } from "@/api/endpoints";
import type { ApiClient } from "@/api/client";
import { isApiError } from "@/api/client";
import { Button } from "@/components/Button";
import type { Translator } from "@/components/FormModal";
import { Kicker } from "@/components/TextBits";

import { PricingShadowPanel, isPricingShadow, shadowMeasuredNothing } from "../billRunShared";

type Read =
  | { state: "loading" }
  | { state: "failed" }
  | { state: "not_a_cycle_run" }
  | { state: "ready"; shadow: BillRunPricingShadow };

/** The server's own refusal for a run with no billing cycle (a one-off run):
 *  there is no comparison to make, so the line is not drawn — saying "did not
 *  load" on every such run would be a failure that never happened. */
const NOT_A_CYCLE_RUN = "billing.oneTime.notACycleRun";

/** The one-line fact, as catalogue calls — exported so a test can read it bare. */
export function pricingFact(shadow: BillRunPricingShadow, t: Translator): { text: string; tone: "ok" | "differ" | "gap" } {
  if (shadowMeasuredNothing(shadow)) return { text: t("billing.bulkRun.pricing.nothing"), tone: "gap" };
  const parts = [
    shadow.disagreed === 0
      ? t("billing.bulkRun.pricing.none")
      : t("billing.bulkRun.pricing.differ", { count: shadow.disagreed }),
  ];
  if (shadow.not_attempted > 0) parts.push(t("billing.bulkRun.pricing.notChecked", { count: shadow.not_attempted }));
  return { text: parts.join(" · "), tone: shadow.disagreed > 0 ? "differ" : shadow.not_attempted > 0 ? "gap" : "ok" };
}

const TONE: Record<"ok" | "differ" | "gap", string> = {
  ok: "text-success-700",
  differ: "text-danger-700",
  gap: "text-warning-700",
};

export function PricingCheck(props: {
  runId: string;
  client: ApiClient;
  /** When the Check was last saved — a new Check reads the comparison again. */
  checkedAt: string | null;
  t: Translator;
  /** Record links (PO 2026-10-19): where an account number opens (new tab). */
  accountHref?: (accountId: string) => string;
}) {
  const { runId, client, checkedAt, t } = props;
  const [read, setRead] = useState<Read>({ state: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let live = true;
    setRead({ state: "loading" });
    getBillRunPricingShadow(runId, client).then(
      (body) => {
        if (!live) return;
        // DEF-2402 — a body that is not a comparison is a failed read, never zeros.
        setRead(isPricingShadow(body) ? { state: "ready", shadow: body } : { state: "failed" });
      },
      (error: unknown) => {
        if (!live) return;
        setRead(
          isApiError(error) && error.messageKey === NOT_A_CYCLE_RUN ? { state: "not_a_cycle_run" } : { state: "failed" },
        );
      },
    );
    return () => {
      live = false;
    };
  }, [runId, client, checkedAt, attempt]);

  const shadow = read.state === "ready" ? read.shadow : null;
  const fact = shadow === null ? null : pricingFact(shadow, t);
  const listable = shadow !== null && (shadow.disagreed > 0 || shadow.not_attempted > 0);

  if (read.state === "not_a_cycle_run") return null;

  return (
    <section
      aria-label={t("billing.bulkRun.pricing.title")}
      className="border border-divider px-3 py-2"
      data-pricing-check={read.state}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="flex items-baseline gap-3">
          <Kicker>{t("billing.bulkRun.pricing.title")}</Kicker>
          {read.state === "loading" && (
            <span className="text-base" role="status">
              {t("billing.bulkRun.pricing.loading")}
            </span>
          )}
          {read.state === "failed" && (
            <span className="text-base text-danger-700" role="status">
              {t("billing.bulkRun.pricing.failed")}
            </span>
          )}
          {fact !== null && (
            <span className={`font-heading text-base font-semibold ${TONE[fact.tone]}`} data-pricing-fact="">
              {fact.text}
            </span>
          )}
        </span>
        {read.state === "failed" && (
          <Button size="sm" onClick={() => setAttempt((was) => was + 1)}>
            {t("billing.bulkRun.tryAgain")}
          </Button>
        )}
        {listable && (
          <Button size="sm" aria-expanded={open} onClick={() => setOpen((was) => !was)}>
            {open ? t("billing.bulkRun.pricing.hide") : t("billing.bulkRun.pricing.show")}
          </Button>
        )}
      </div>
      {listable && open && shadow !== null && <PricingShadowPanel t={t} shadow={shadow} accountHref={props.accountHref} />}
    </section>
  );
}
