// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CUS-9043 — no screen let a clerk LINK an existing customer to a
//           service request. PO 2026-10-01: *"you will ahve to create or link
//           customer ID - those cases also should be tested"*. CR-159-BRC10
//           built the server half (the link reaches the account,
//           DEF-CUS-9035); the only caller of `POST …/customer-link` sent
//           `customer_id: null` — *Record that I searched*.
// Rules:    B14 rule 43 (a piece of UI is a COMPONENT, not inline code) ·
//           rule 31 (the customer NUMBER, never the id) · BR-CUS-089 (only a
//           strong match may move money) · decision log 2026-10-02 (the
//           portal walk's judgments: a clerk's explicit link is `strong`)
// Defect:   DEF-CUS-10043 (PO 2026-10-11) — *Search customer* matches by the
//           request's ID: found → the customer's card, none → *No customer
//           found.* PO, verbatim: *"please use existing customer ID search
//           function. We already build this compotent and rules - use existing
//           rule"* — so the free-text finder is replaced by the move-in's
//           *Search customer ID* (`GET …/customer-search` → `owner_lookup`'s Q5
//           verdicts) drawn by the move-in's own `CustomerMatchPanel`.
// Ruling:   PO 2026-10-11, option B — *Record that I searched* merges in here:
//           after a search, *No match* (`onNoMatch`) records *searched, no
//           prior customer* — the same `customer_id: null` the Arrears row's
//           button sent — so one place answers the Arrears check.
// Tests:    RequestCustomerLink.dom.test.tsx
// ───────────────────────────────────────────────────────
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import type { ApiClient } from "@/api/client";
import { Button } from "@/components/Button";
import type { RegionalDateFormat } from "@/components/DateCell";

import { CustomerMatchPanel } from "./customerMatch/CustomerMatchPanel";
import type { CustomerSearchResult, CustomerSearchRow } from "./customerEndpoints";
import { searchRequestCustomer } from "./serviceRequestEndpoints";

type Translator = (key: string, options?: Record<string, unknown>) => string;

/**
 * **LINK A CUSTOMER ON FILE TO THE REQUEST — by the request's own ID.**
 *
 * It sits in the Approve window, where the Arrears check asks *has anybody
 * looked*, and it is the ONLY place that answers it: *Link* on a match, or
 * *No match* once a search has run (PO 2026-10-11, option B). *No match* is
 * offered only after a search ANSWERED — a failed search found nothing, it did
 * not find that there is nothing. One press asks the
 * move-in's *Search customer ID* with what the application holds (SSN,
 * driving licence, name and date of birth): **found** or **possible** shows
 * the customer's card with *Link*, **new** says *No customer found.* Nothing is
 * typed and no identifier crosses the wire (last four only).
 */
export function RequestCustomerLink(props: {
  t: Translator;
  client: ApiClient;
  requestId: string;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  working?: boolean;
  onLink: (customerId: string) => void;
  /** *No match* — records *searched, no prior customer*. */
  onNoMatch?: () => void;
}) {
  const [answer, setAnswer] = useState<CustomerSearchResult | null>(null);
  const [linked, setLinked] = useState<CustomerSearchRow | null>(null);
  const [dismissed, setDismissed] = useState<string[]>([]);
  const [noMatch, setNoMatch] = useState(false);
  const search = useMutation({
    mutationFn: () => searchRequestCustomer(props.requestId, props.client),
    onSuccess: (result) => {
      setAnswer(result);
      setDismissed([]);
      setNoMatch(false);
    },
    onError: () => setAnswer(null),
  });

  return (
    <section data-request-customer-link="">
      <h4 className="m-0 mb-1 text-xs font-semibold tracking-wide text-accent uppercase">
        {props.t("customers.serviceRequest.match.title")}
      </h4>
      <Button
        variant="secondary"
        data-customer-search=""
        disabled={search.isPending}
        onClick={() => search.mutate()}
      >
        {props.t("customers.finder.search")}
      </Button>
      <CustomerMatchPanel
        result={answer}
        pending={search.isPending}
        failed={search.isError}
        linkedId={linked?.id ?? null}
        linkedRow={linked}
        dismissed={dismissed}
        onLink={(row) => {
          if (props.working === true) return;
          setLinked(row);
          props.onLink(row.id);
        }}
        onUnlink={() => setLinked(null)}
        onNotThem={(row) => setDismissed([...dismissed, row.id])}
        timeZone={props.timeZone}
        dateFormat={props.dateFormat}
      />
      {answer !== null && linked === null && props.onNoMatch !== undefined && (
        <div className="mt-3 flex items-center gap-3" data-request-no-match="">
          {noMatch ? (
            <span className="text-sm text-neutral-700">
              {props.t("customers.serviceRequest.match.noMatchRecorded")}
            </span>
          ) : (
            <Button
              variant="secondary"
              size="sm"
              data-action="record-search"
              disabled={props.working === true}
              onClick={() => {
                setNoMatch(true);
                props.onNoMatch?.();
              }}
            >
              {props.t("customers.serviceRequest.match.noMatch")}
            </Button>
          )}
        </div>
      )}
    </section>
  );
}
