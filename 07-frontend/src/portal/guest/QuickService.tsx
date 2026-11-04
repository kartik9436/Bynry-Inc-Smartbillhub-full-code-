// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-015 (EP-CWP-04) — ask for a quick service. Screens:
//           CWP-010 · wireframes/CWP-010.png
// Rules:    08-screen-layouts.md CWP-010 (T1: PageHead kicker QUICK SERVICE ·
//           title · subtitle → CardGrid3 × 2 with six ErrandCards and an
//           outlined *Ask →* → InfoBar with the boundary sentence, bold
//           clause) · US-CWP-015 §5 (⚠ the cards read from the TENANT'S
//           configuration, never a hardcoded list) · BR-CWP-026 (a form a
//           stranger can fill may create work, never change an account) ·
//           BR-CWP-028 (it ends on a reference) · B14 rules 21, 31, 32
// Tests:    src/portal/guest/QuickService.test.tsx ·
//           10-scripts/render-checks/cr068-c-start-service.mjs
// ───────────────────────────────────────────────────────
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { refusalText } from "@/api/refusalText";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/Button";
import { LoadingSkeleton } from "@/components/StateFrame";

import { askForQuickService, getAvailability, getQuickServices } from "../api/guestClient";
import type { AddressSuggestion, QuickServiceCategory } from "../api/guestClient";
import {
  AddressSuggestInput,
  ApartmentChoice,
  NOT_LISTED,
  suggestionLine,
} from "../components/AddressSuggest";
import { Announced, FormScope, refocus, usePortalForm } from "../components/a11y";
import {
  Card,
  CardGrid3,
  ErrandCard,
  errandActionName,
  FormField,
  InfoBar,
  KVList,
  TextInput,
  WizardFooter,
} from "../components/primitives";

import { GuestPage } from "./GuestPage";

export function QuickServiceBody(props: { client?: ApiClient }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const [picked, setPicked] = useState<QuickServiceCategory | null>(null);
  const [values, setValues] = useState({ name: "", phone: "", email: "", address: "", details: "", bill_number: "" });
  const [reference, setReference] = useState<string | null>(null);
  /** ⊕ `CR-200-BRC10` F4 (PO, Ask us A) — the suggestion picked, if any. It is
   *  dropped the moment the address box is edited, so what is sent is always
   *  what the box says. */
  const [place, setPlace] = useState<AddressSuggestion | null>(null);
  const [apartment, setApartment] = useState<string | null>(null);
  const form = usePortalForm();

  const categories = useQuery({
    queryKey: ["portal", "quick-services"],
    queryFn: () => getQuickServices(client),
  });
  // The picked building's apartments — labels only — from the same public
  // read Start service asks (nothing is looked up for a typed address).
  const building = useQuery({
    queryKey: ["portal", "availability", place?.street, place?.city, place?.postal_code, ""],
    queryFn: () =>
      getAvailability(
        { street: place?.street ?? "", city: place?.city ?? "", postalCode: place?.postal_code ?? "" },
        client,
      ),
    enabled: place !== null,
  });
  const labels = place !== null && building.data?.matched === true ? (building.data.units ?? []) : [];
  const ask = useMutation({
    mutationFn: () =>
      askForQuickService(
        {
          category: picked?.code,
          ...values,
          // The pick's PARTS (never an id); the server re-matches them and
          // links the request. A typed address travels as typed, alone.
          ...(place !== null
            ? {
                street: place.street,
                city: place.city,
                postal_code: place.postal_code ?? "",
                ...(apartment !== null && apartment !== NOT_LISTED ? { unit: apartment } : {}),
              }
            : {}),
        },
        client,
      ),
    onSuccess: (result) => setReference(result.reference),
  });

  if (categories.isPending) {
    return <LoadingSkeleton variant="card" />;
  }
  const rows = categories.data?.categories ?? [];

  if (reference !== null) {
    return (
      <div data-screen="CWP-010" data-asked="true">
        <PageHeader
          kicker={t("portal.quick.kicker")}
          title={t("portal.quick.askedTitle")}
          rollup={t("portal.quick.askedSubtitle")}
        />
        <Card testId="quick-service-done">
          <KVList
            rows={[
              {
                key: "reference",
                label: t("portal.apply.yourReference"),
                value: <span data-reference="">{reference}</span>,
              },
            ]}
          />
        </Card>
      </div>
    );
  }

  if (picked !== null) {
    const field = (name: keyof typeof values) => (value: string) =>
      setValues((old) => ({ ...old, [name]: value }));
    return (
      <div data-screen="CWP-010" data-asking={picked.code}>
        <PageHeader
          kicker={t("portal.quick.kicker")}
          // A utility's own label is shown verbatim; `t()` returns an unknown
          // key unchanged, which is exactly the behaviour a renamed category
          // needs (US-CWP-015 TC-7).
          title={t(picked.label ?? picked.code)}
          rollup={t("portal.quick.formSubtitle")}
        />
        <Card testId="quick-service-form">
          <FormScope form={form}>
          <FormField id="quick-name" label={t("portal.quick.yourName")} required>
            <TextInput id="quick-name" value={values.name} onChange={field("name")} />
          </FormField>
          <FormField id="quick-phone" label={t("portal.quick.yourPhone")} required>
            <TextInput id="quick-phone" value={values.phone} onChange={field("phone")} />
          </FormField>
          {/* Required, because `customers` refuses a request about nowhere
              (BR-CUS-070). A screen that made it optional would be accepted here
              and refused by the service. */}
          <FormField id="quick-address" label={t("portal.quick.theAddress")} required>
            {/* ⊕ `CR-200-BRC10` F4 — the same suggestions as Start service. */}
            <AddressSuggestInput
              id="quick-address"
              value={values.address}
              onChange={(value) => {
                setPlace(null);
                setApartment(null);
                field("address")(value);
              }}
              onPick={(row) => {
                setPlace(row);
                setApartment(null);
                field("address")(suggestionLine(row));
              }}
              client={client}
              autoComplete="street-address"
            />
          </FormField>
          {labels.length > 1 ? (
            <ApartmentChoice labels={labels} value={apartment} onChange={setApartment} />
          ) : null}
          {picked.needs_bill_number ? (
            <FormField id="quick-bill" label={t("portal.quick.billNumber")} required>
              <TextInput id="quick-bill" value={values.bill_number} onChange={field("bill_number")} />
            </FormField>
          ) : null}
          <FormField id="quick-details" label={t("portal.quick.details")}>
            <TextInput id="quick-details" value={values.details} onChange={field("details")} />
          </FormField>
          </FormScope>
          {ask.isError ? (
            <Announced tone="error" className="text-base font-semibold text-danger-700" data-ask-error="">
              {refusalText(t, ask.error)}
            </Announced>
          ) : null}
          {/* `DEF-CWP-9164` — the way back on the LEFT, Send on the RIGHT. */}
          <WizardFooter
            back={
              // r10 rule 1: this is not a stepper, so it is an EXIT and it
              // names where it exits to — never the stepper's `← Back`.
              // F-04 (`DEF-CWP-10552`): Back returns focus to the card that
              // opened this form, not to the top of the page.
              <Button
                variant="secondary"
                size="default"
                data-action="cancel-ask"
                onClick={() => {
                  refocus(`button[data-action="ask-${picked.code}"]`);
                  setPicked(null);
                }}
              >
                {t("portal.quick.backToCards")}
              </Button>
            }
            forward={
              <Button
                variant="primary"
                size="default"
                data-action="send-ask"
                disabled={ask.isPending}
                onClick={form.guard(() => ask.mutate())}
              >
                {t("portal.quick.send")}
              </Button>
            }
          />
        </Card>
      </div>
    );
  }

  return (
    <div data-screen="CWP-010">
      <PageHeader
        kicker={t("portal.quick.kicker")}
        title={t("portal.quick.title")}
        rollup={t("portal.quick.subtitle")}
      />
      {/* ⚠ NOTHING EMPTY EVER APPEARS (BR-CWP-093): a utility that has switched
          requests off gets an empty list from the server, and this section is
          simply absent rather than a heading over nothing. */}
      {rows.length > 0 ? (
        <>
          <CardGrid3>
            {rows.map((row) => (
              <ErrandCard
                key={row.code}
                cardKey={row.code}
                title={t(row.label ?? row.code)}
                description={row.hint ? t(row.hint) : ""}
                action={
                  <Button
                    variant="secondary"
                    size="sm"
                    data-action={`ask-${row.code}`}
                    // DEF-CWP-10566: six "Ask →" buttons; each is named for its card.
                    aria-label={errandActionName(t("portal.quick.ask"), t(row.label ?? row.code), (action, card) =>
                      t("portal.actionName", { label: action, value: card }),
                    )}
                    onClick={() => setPicked(row)}
                  >
                    {t("portal.quick.ask")}
                  </Button>
                }
              />
            ))}
          </CardGrid3>
          <div className="mt-4">
            {/* The closing note IS the boundary (US-CWP-015 §1). */}
            <InfoBar lead={t("portal.quick.boundaryLead")} bold={t("portal.quick.boundaryBold")} />
          </div>
        </>
      ) : null}
    </div>
  );
}

export function QuickServicePage(props: { client?: ApiClient }) {
  return (
    <GuestPage client={props.client}>
      <QuickServiceBody client={props.client} />
    </GuestPage>
  );
}
