// ── Trace ──────────────────────────────────────────────
// REQ-03 tasks 8–10 — **THE RENDERED-OUTPUT HARNESS.**
//
// ⚠ **WHY THIS FILE EXISTS, AND WHAT IT IS NOT.** Hard-won law 6 — *diff the
// running app against the drawing* — is the only check in this repository that
// reads rendered output, and it has no tool behind it. The full stack cannot be
// booted in this container: there is no Docker daemon (`/var/run/docker.sock`
// does not exist), so there is no API, no tenant and no sign-in, and a
// screenshot of the real `/requests/new` would be a spinner.
//
// **So this mounts the REAL components, with the REAL stylesheet and the real
// token file, on fixture rows** — which proves the drawn SHAPE: the columns and
// their order, the controls in the rows, the add buttons under the tables, the
// Total, and the communication card's three states, at 1440, 1280 and 420.
//
// ⚠ **IT DOES NOT PROVE THE PAGE AROUND THEM** — the frame, the stepper, the
// panel order and the Review's two columns are NOT shown here, and a reader must
// not take these shots as that proof. Say what a check skipped beside what it
// checked (law 7's fifth shape).
//
// It is excluded from the product bundle: nothing imports it but
// `10-scripts/req03_step34_shots.mjs`.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "@/i18n";
import i18n from "@/i18n";
import "@/styles/tailwind.css";

import {
  ApplicationFeesTableArray,
  CustomerMessagesCard,
  ReviewServicesTable,
  ServicesTableArray,
} from "./serviceRequestTableArrays";
import type { ServiceRequestFeeLine } from "./serviceRequestEndpoints";

const t = (key: string, params?: Record<string, unknown>): string =>
  i18n.t(key, params as never) as unknown as string;

const FEE: ServiceRequestFeeLine = {
  id: "fee-1",
  line_no: 1,
  charge_code: "CONN",
  description: "Connection fee",
  basis: "per request",
  quantity: "1.0000",
  unit_amount: { amount: "45.0000", display: "45.00", currency: "USD" },
  amount: { amount: "45.0000", display: "45.00", currency: "USD" },
  waived: false,
  waive_reason: null,
  settled_at: null,
  invoice_ref: null,
};

/** The platform's eleven, in the seed order (`BR-RAT-024`). A FIXTURE and not
 *  a source of truth — the product reads `GET /tenant-services`, and a screen
 *  that typed this list out would be `CR-063`'s silent failure. */
const SEEDED_SERVICES = [
  { value: "electric", label: "Electric" },
  { value: "water", label: "Water" },
  { value: "gas", label: "Gas" },
  { value: "sewer", label: "Sewer" },
  { value: "trash", label: "Trash" },
  { value: "storm_water", label: "Storm water" },
  { value: "solar", label: "Solar" },
  { value: "broadband", label: "Broadband" },
  { value: "thermal_heat", label: "Thermal/Heat" },
  { value: "battery", label: "Battery" },
  { value: "fire", label: "Fire" },
];

function Harness() {
  return (
    // ⚠ **NO PAGE-BACKGROUND UTILITY HERE — THE ONE THIS HELD DECLARED
    // NOTHING AND RENDERED NOTHING.** `G134` caught it: no stylesheet
    // declares that name and Tailwind generates no rule for it, so `tsc`,
    // eslint and a `toHaveClass` all pass over a class the browser drops
    // (the invisible-class trap, `DEF-SHL-5088`). The harness needs no page
    // fill; the components carry their own surfaces. The token is not spelled
    // here either — a dead class named in a comment is the next lane's
    // copy-paste.
    <div className="p-6">
      <section className="mb-8" data-shot="services">
        <h3 className="mb-2">{t("customers.serviceRequest.capture.services")}</h3>
        <p className="mb-2 text-sm text-neutral-700">
          {t("customers.serviceRequest.capture.servicesSelected", { selected: 3, total: SEEDED_SERVICES.length })}
        </p>
        <ServicesTableArray
          rows={[
            { code: "water", requested_start: "2026-10-20", status: "new" },
            { code: "sewer", requested_start: "2026-10-20", status: "new" },
            { code: "trash", requested_start: "2026-10-20", status: "already_on_site" },
          ]}
          // ⚠ **ALL ELEVEN, IN THE SEED ORDER — `BR-RAT-024`, and `G47` caught
          // this fixture naming six.** A hand-typed partial list is the exact
          // shape `CR-063`'s fire lesson is about: the eleventh service
          // exists, the API serves it, every check passes, and the screen
          // simply never offers it. **A FIXTURE IS NOT EXEMPT** — it is where
          // the next lane copies the list from.
          options={SEEDED_SERVICES}
          onChange={() => undefined}
          t={t}
          dateFormat="MM/DD/YYYY"
        />
      </section>

      <section className="mb-8" data-shot="fees">
        <h3 className="mb-2">{t("customers.serviceRequest.fees.applicationFees")}</h3>
        <ApplicationFeesTableArray
          fees={{
            lines: [FEE],
            quoted: { amount: "45.0000", display: "45.00", currency: "USD" },
          }}
          codes={[
            { value: "CONN", label: "Connection fee" },
            { value: "METER", label: "Meter fee" },
          ]}
          t={t}
          busy={false}
          pendingRow={false}
          onAddRow={() => undefined}
          onDropPendingRow={() => undefined}
          onPick={() => undefined}
          onRemove={() => undefined}
        />
      </section>

      <section className="mb-8" data-shot="review-services">
        <h3 className="mb-2">{t("customers.serviceRequest.capture.reviewAskingFor")}</h3>
        <ReviewServicesTable
          rows={[
            { code: "water", requested_start: "2026-10-20", status: "new" },
            { code: "sewer", requested_start: "2026-10-20", status: "new" },
            { code: "trash", requested_start: "2026-10-20", status: "new" },
          ]}
          t={t}
          timeZone="America/Chicago"
          dateFormat="DD-MMM-YY"
        />
      </section>

      {/* ⚠ **THE KEYS HERE ARE THE SERVER'S OWN** — `told.<occasion>` and
          `toldNotSent.<reason>`, which is what `detail.told_on_submit` sends
          and what the screen resolves. An earlier fixture named keys this
          lane had invented and later retired, and the card PHOTOGRAPHED THE
          RAW KEYS; nothing but looking at the picture could have caught it
          (hard-won law 6), because the product was correct throughout. */}
      <section className="mb-8" data-shot="messages">
        <h3 className="mb-2">{t("customers.serviceRequest.messages.card")}</h3>
        <CustomerMessagesCard
          rows={[
            {
              key: "request_received",
              message: t("customers.serviceRequest.told.request_received"),
              channel: t("customers.serviceRequest.messages.channel.email"),
              to: "mike@yopmail.com",
              when: t("customers.serviceRequest.messages.when.on_submit"),
            },
            {
              key: "balance_outstanding",
              message: t("customers.serviceRequest.told.balance_outstanding"),
              channel: t("customers.serviceRequest.messages.channel.email"),
              to: "mike@yopmail.com",
              when: t("customers.serviceRequest.messages.when.on_submit"),
            },
            {
              key: "documents_outstanding",
              message: t("customers.serviceRequest.told.documents_outstanding"),
              channel: t("customers.serviceRequest.messages.channel.email"),
              to: "mike@yopmail.com",
              when: t("customers.serviceRequest.toldNotSent.this_product_has_no_wording_for_this_one_yet"),
              withheld: true,
            },
          ]}
          absence={null}
          t={t}
        />
      </section>

      <section data-shot="messages-absent">
        <h3 className="mb-2">{t("customers.serviceRequest.messages.card")}</h3>
        <CustomerMessagesCard
          rows={[]}
          absence={t("customers.serviceRequest.messages.serverCannotAnswer")}
          t={t}
        />
      </section>
    </div>
  );
}

createRoot(document.getElementById("root") as HTMLElement).render(
  <StrictMode>
    <Harness />
  </StrictMode>,
);
