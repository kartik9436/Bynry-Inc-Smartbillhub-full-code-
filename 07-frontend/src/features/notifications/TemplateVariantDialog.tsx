// ── Trace ──────────────────────────────────────────────
// Story:    CR-199-BRC10 F4 — + New variant (`06`) and Duplicate as variant
//           (`10`), one form
// Rules:    PO rulings A3 A (a variant is channel × language × customer
//           category) · A4 B (the utility's languages only) · BR-NOT-001 (the
//           route is idempotent on the variant's key) · B14 rules 31 · 38 · 43
// ───────────────────────────────────────────────────────
// THE DIALOG BOTH VARIANT ACTIONS OPEN. The drawing draws them as one form with
// two titles: Channel · Language · Customers · Start from, and *Create draft*.
// What differs is the default of *Start from* — the published wording for a
// new variant, *this variant (vN)* for a duplicate.
//
// ⚠ **IT POSTS TO THE ONE ROUTE A VARIANT HAS EVER BEEN MADE THROUGH** —
// `POST /template-catalog/{code}/variants` — with `{code}` the CHANNEL picked
// (each channel of a notice is its own template). The old inline forms asked a
// person to TYPE a variant name and a language code; neither is a choice a
// clerk should have to spell, so the name is composed from the three picks and
// the language is picked from the utility's own list (B14 rule 38: the form is
// built our way, what it contains is the drawing's).
//
// ⚠ **`Start from` IS DRAWN ONLY WHEN THE SERVER CAN HONOUR IT.** Copying a
// variant's wording into the new one is the variants lane's write
// (`CR-199-BRC10` §5); a select whose choice the request then ignored would be
// a control that lies. Until it lands the new variant starts as the route has
// always made it.
import { useId, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import type { ApiClient } from "@/api/client";
import { createTemplateVariant } from "@/api/endpoints";
import type { TemplateVariantRow } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { ModalShell, SelectField } from "@/components/FormModal";
import { useToast } from "@/components/Toast";
import { RefusalNotice, refusalOf } from "@/features/tenancy/settingsShared";
import type { Refusal } from "@/features/tenancy/settingsShared";
import type { PickerOption } from "./TemplateVariantPickers";

export type VariantDialogMode = "new" | "duplicate";

/** The server's three *Start from* values; an empty pick is a blank start. */
function startFromValue(raw: string): "blank" | "published" | "variant" {
  return raw === "published" || raw === "variant" ? raw : "blank";
}

export interface StartFromOption extends PickerOption {
  /** What the server is asked to copy — `published`, `blank`, or a version. */
  value: string;
}

export function TemplateVariantDialog(props: {
  mode: VariantDialogMode;
  client: ApiClient;
  channels: readonly PickerOption[];
  channel: string;
  languages: readonly PickerOption[];
  language: string;
  customers: readonly PickerOption[];
  customer: string;
  /** Empty = the server cannot copy wording yet, and the field is not drawn. */
  startFrom: readonly StartFromOption[];
  /** True when the language list is the utility's own (PO ruling A4 B). */
  utilityLanguagesOnly: boolean;
  /** The variant on screen — what *Start from: this variant* copies. */
  sourceVariant: string | null;
  onClose: () => void;
  onCreated: (code: string, variant: TemplateVariantRow) => void;
  onRefusal: (refusal: Refusal | null) => void;
}) {
  const { t } = useTranslation();
  const ids = useId();
  const fireToast = useToast();
  const queryClient = useQueryClient();
  const [channel, setChannel] = useState(props.channel);
  const [language, setLanguage] = useState(props.language);
  const [customer, setCustomer] = useState(props.customer);
  /* `06` starts from the published wording, `10` from this variant. The
     choices arrive with `variant-options`, so the default is DERIVED on every
     render until the person picks — a default frozen at first render would be
     the empty list's, and a duplicate would silently start blank. */
  const [picked, setStartFrom] = useState<string | null>(null);
  /* ⚠ DEF-NOT-10685 — THE REFUSAL IS THE DIALOG'S OWN. Handed to the
     workspace's page strip it was drawn BEHIND the overlay, so a refused
     Create draft looked like nothing happening. */
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const preferred = props.mode === "duplicate" ? "variant" : "published";
  const startFrom =
    picked ??
    (props.startFrom.some((option) => option.value === preferred)
      ? preferred
      : (props.startFrom[0]?.value ?? ""));

  const create = useMutation({
    /* `POST …/new-variant` (`CR-199-BRC10` §5): the server names the variant
       from the three picks and copies the wording `Start from` asked for into
       its first DRAFT. Nothing is published. */
    mutationFn: () =>
      createTemplateVariant(
        channel,
        {
          language,
          category: customer,
          start_from: startFromValue(startFrom),
          ...(startFrom === "variant" && props.sourceVariant !== null
            ? { source_variant: props.sourceVariant }
            : {}),
        },
        props.client,
      ),
    onSuccess: async ({ variant }) => {
      setRefusal(null);
      props.onRefusal(null);
      fireToast(t("templates.catalog.variantCreated", { name: variant.name }));
      await queryClient.invalidateQueries({ queryKey: ["template-catalog"] });
      props.onCreated(channel, variant);
    },
    onError: (error: unknown) => setRefusal(refusalOf(error, t)),
  });

  return (
    <ModalShell
      title={t(
        props.mode === "duplicate"
          ? "templates.workspace.duplicate"
          : "templates.workspace.newVariantTitle",
      )}
      onClose={props.onClose}
      busy={create.isPending}
    >
      <form
        className="modal-body flex flex-col gap-3"
        data-testid={props.mode === "duplicate" ? "duplicate-variant-form" : "new-variant-form"}
        onSubmit={(event) => {
          event.preventDefault();
          create.mutate();
        }}
        id={`${ids}-form`}
      >
        <RefusalNotice refusal={refusal} />
        <SelectField
          id={`${ids}-channel`}
          label={t("templates.workspace.channel")}
          value={channel}
          onChange={setChannel}
          options={[...props.channels]}
          disabled={props.channels.length < 2}
        />
        <SelectField
          id={`${ids}-language`}
          label={t("templates.workspace.language")}
          value={language}
          onChange={setLanguage}
          options={[...props.languages]}
          help={
            props.utilityLanguagesOnly ? t("templates.workspace.utilityLanguagesOnly") : undefined
          }
        />
        <SelectField
          id={`${ids}-customers`}
          label={t("templates.workspace.customers")}
          value={customer}
          onChange={setCustomer}
          options={[...props.customers]}
        />
        {props.startFrom.length > 0 && (
          <SelectField
            id={`${ids}-start`}
            label={t("templates.workspace.startFrom")}
            value={startFrom}
            onChange={setStartFrom}
            options={[...props.startFrom]}
          />
        )}
      </form>
      <div className="modal-foot">
        <Button variant="ghost" onClick={props.onClose} data-testid="variant-cancel">
          {t("forms.cancel")}
        </Button>
        <Button
          variant="primary"
          type="submit"
          form={`${ids}-form`}
          disabled={create.isPending}
          data-testid={props.mode === "duplicate" ? "duplicate-save" : "new-variant-save"}
        >
          {create.isPending ? t("states.working") : t("templates.workspace.createDraft")}
        </Button>
      </div>
    </ModalShell>
  );
}
