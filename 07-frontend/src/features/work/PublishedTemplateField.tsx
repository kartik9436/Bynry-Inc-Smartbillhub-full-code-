// ── Trace ──────────────────────────────────────────────
// Change:   CR-192-BRC10 — MQ-033 task 11: a read-format question's *Raise a
//           job* names a PUBLISHED Work job template (decision log 2026-10-24,
//           server judgment 1: *"The job 'type' a question raises is a
//           published Work job TEMPLATE"*).
// Rules:    BR-WRK-008 (a job is raised from a template) · BR-WRK-011 (a
//           draft is not a version — never offered) · NFR-3 (searched on the
//           server, one page at a time) · B14 rule 31 (a template shows its
//           name, never its id) · B14 rule 43 (a component, not inline code)
// Tests:    src/features/metering/readFormats.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **THE SEARCH IS THE ONE `FollowOnDialog` ALREADY RUNS** (`work/field/
// ComeBackDialogs.tsx`): `GET /work/templates?q=` through `listTemplates`, one
// page of 20, published rows only, into the kit's `RemoteSearchSelectField`.
// It was inline in that dialog; this is the same picker as a component so a
// second screen imports it instead of writing a third copy. `FollowOnDialog`
// still carries its own inline copy — moving it here is a refactor of a
// shipped screen with its own proof, and is left to that screen's owner.
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { ApiClient } from "@/api/client";
import { api } from "@/api/client";
import { RemoteSearchSelectField } from "@/components/RemoteSearchSelectField";

import { listTemplates } from "./workEndpoints";

/** One page of matches — the same page `FollowOnDialog` asks for. */
export const TEMPLATE_PICKER_PER = 20;

export function PublishedTemplateField(props: {
  id: string;
  label: string;
  value: string;
  onChange: (templateId: string) => void;
  /** The chosen template's NAME when the form opens on an existing value. */
  initialName?: string;
  required?: boolean;
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const [term, setTerm] = useState(props.initialName ?? "");
  const search = useQuery({
    queryKey: ["work", "templates", "published-picker", term],
    queryFn: () => listTemplates({ q: term, page: 1, per: TEMPLATE_PICKER_PER }, client),
    enabled: term.trim().length >= 1,
    retry: false,
  });
  const options = (search.data?.results ?? [])
    .filter((row) => row.status === "published")
    .map((row) => ({ value: row.id, label: row.name }));
  return (
    <RemoteSearchSelectField
      id={props.id}
      label={props.label}
      term={term}
      onTermChange={(next) => {
        setTerm(next);
        props.onChange("");
      }}
      status={{
        idle: term.trim().length < 1,
        searching: search.isFetching,
        searched: search.isSuccess,
        failed: search.isError,
      }}
      options={options}
      value={props.value}
      onChange={props.onChange}
      startClosed={props.initialName !== undefined && props.initialName !== ""}
      words={{
        tooShort: t("work.field.templateSearch.tooShort"),
        searching: t("work.field.templateSearch.searching"),
        failed: t("work.field.templateSearch.failed"),
        noMatch: t("work.field.templateSearch.noMatch"),
      }}
      required={props.required}
    />
  );
}
