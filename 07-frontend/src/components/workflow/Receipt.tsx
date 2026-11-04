// ── Trace ──────────────────────────────────────────────
// Change:   CR-023 — Stage 5 RESULT, the receipt (design B15 §4.5)
// Rules:    BR-MET-018 (the file hash is what identifies a run) ·
//           B14 rule 21 (Tailwind) · B14 rule 18 (descriptions at 80%)
// Impacts:  components/workflow/WorkflowRunner.tsx composes this.
// ───────────────────────────────────────────────────────
import { useTranslation } from "react-i18next";

import { Kicker } from "@/components/TextBits";

import type { Receipt as ReceiptData } from "./contract";
import * as WF from "./workflowKit";

/**
 * The six-field record: source · file hash · run by · session and IP · mapping
 * used · rollback point with its expiry.
 *
 * ⚠ THE SIX ARE THE AUDIT TRAIL OF A WRITE, WHICH IS WHY NONE OF THEM MAY GO
 * QUIETLY BLANK. This product already implements the shape once — `metering`'s
 * `ReadImportBatch` records the file name, its SHA-256, the uploader, a session
 * reference and an IP for exactly this reason — and a receipt with an empty
 * session line reads like a receipt with nothing to hide. Every absent field
 * prints "Not recorded", so the gap is countable rather than invisible.
 *
 * ⚠ THE ROLLBACK EXPIRY IS THE SERVER'S SENTENCE, NOT "30 DAYS" TYPED HERE.
 * B15 §8 Q7 asks whether the window is 30 days at all and it is unruled; if the
 * screen held the number, the screen would be making the promise. The kit
 * prints `expiry_label` and knows nothing about calendars.
 *
 * ⚠ `verified` IS A FLAG, NOT A WORD IN THE HASH STRING. r10 prints
 * `c19a…4407 · verified` as one run of text. A screen that concatenates the
 * word can say "verified" about a hash nothing checked; a boolean the server
 * sets cannot.
 */
export interface ReceiptProps {
  receipt: ReceiptData;
  /** `DEF-PAY-10758` — false where the target can never roll back (payments). */
  showRollback?: boolean;
}

export function Receipt({ receipt, showRollback = true }: ReceiptProps) {
  const { t } = useTranslation();
  const notRecorded = t("workflow.receipt.notRecorded");
  return (
    <div className={WF.RECEIPT_GRID} data-workflow="receipt" data-run={receipt.run_id}>
      <div data-workflow="receipt-source">
        <Kicker as="div">{t("workflow.receipt.source")}</Kicker>
        <div className={WF.RECEIPT_VALUE}>{receipt.source_label ?? notRecorded}</div>
      </div>

      <div data-workflow="receipt-hash">
        <Kicker as="div">{t("workflow.receipt.hash")}</Kicker>
        <div className={WF.RECEIPT_VALUE_SMALL}>
          {/* ⚠ **THE FINGERPRINT MOVES TO `title` — DEF-767, and this half is a
              JUDGEMENT the PO may reverse.** Sixty-four hex characters were the
              headline of this row. Unlike the rollback id it is NOT a database
              key — it is a fingerprint of the operator's OWN file, and it is
              real evidence for a utility auditing a migration — so it is kept
              rather than deleted, and moved to where evidence belongs: the
              hover, and the export. What a clerk reads is the only part they
              can act on, which is whether it matched. */}
          {receipt.file_sha256 === null ? (
            notRecorded
          ) : (
            <span title={receipt.file_sha256}>
              {receipt.file_hash_verified
                ? t("workflow.receipt.hashVerifiedPlain", {
                    defaultValue: "Matched the file you uploaded.",
                  })
                : t("workflow.receipt.hashUnverifiedPlain", {
                    defaultValue:
                      "Could not be checked against the file you uploaded.",
                  })}
            </span>
          )}
        </div>
      </div>

      <div data-workflow="receipt-runby">
        <Kicker as="div">{t("workflow.receipt.runBy")}</Kicker>
        <div className={WF.RECEIPT_VALUE}>{receipt.run_by ?? notRecorded}</div>
      </div>

      <div data-workflow="receipt-session">
        <Kicker as="div">{t("workflow.receipt.session")}</Kicker>
        <div className={WF.RECEIPT_VALUE_SMALL}>{receipt.session_and_ip ?? notRecorded}</div>
      </div>

      <div data-workflow="receipt-mapping">
        <Kicker as="div">{t("workflow.receipt.mapping")}</Kicker>
        <div className={WF.RECEIPT_VALUE}>{receipt.mapping_used ?? notRecorded}</div>
      </div>

      {showRollback && (
      <div data-workflow="receipt-rollback">
        <Kicker as="div">{t("workflow.receipt.rollback")}</Kicker>
        <div className={WF.RECEIPT_VALUE}>
          {/* ⚠ **THE ID IS GONE — DEF-767.** This read
              `${receipt.rollback_point.id} · ${expiry_label}` and printed a raw
              uuid — `01a03d62-3811-765d-a214-79352d02c075` — to a clerk. PO,
              2026-08-26, looking at the deployed receipt: *"We get database keys
              on this screen"*. CR-016 says a clerk must never read a rule code
              or a column name, and a primary key is further from their world
              than either. **Nothing here was ever actionable through that id:**
              the `Roll back this run` control below performs the rollback, and
              a clerk has nowhere to type a uuid even if they wanted to. What IS
              actionable is the DEADLINE, which is all that remains. */}
          {receipt.rollback_point === null ? notRecorded : receipt.rollback_point.expiry_label}
        </div>
      </div>
      )}
    </div>
  );
}
