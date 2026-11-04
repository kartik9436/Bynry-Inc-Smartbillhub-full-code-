// ── Trace ────────────────────────────────────────────────────────────────
// ⚠ `DEF-GOV-10106`: THE MODAL ITSELF (`ConnectModal`) IS DELETED. CON-01
//           became a table on 2026-09-17 (`53b8f3038`) and its Connect / Edit
//           icons open `ConnectorSetupPage` at its own address, so nothing
//           rendered the modal. What stays is what that page and
//           `FieldGroupPanel` import from here: `RENDER`, `fieldLabel`,
//           `testableOperation` and the slot types. The trace below
//           describes the modal as it was.
// Story:    US-INT-019 (EP-INT-05) — S141, the connect/manage modal: one
//           frame written once, a field slot rendered from the manifest, and
//           the three field kinds a plain field cannot express. US-INT-002
//           (the four endpoints it presses) · US-INT-017 (the server's
//           refusal, shown) · US-INT-016 (the 202 it receives).
//           Screens: S141 · frames 25.1 (custom SMTP) · 49.1 (a password or a
//           key) · 49.2 (a sign-in redirect) · 50.1 (a key we issue) · 50.2
//           (a file channel) · 55.1 (disconnect) · 55.2 (the refusal line).
// Rules:    BR-INT-043 (the field slot is generated from the manifest's
//           field list over a CLOSED vocabulary of kinds — the map below is
//           exhaustive and has no fallback branch) · BR-INT-002 (every card
//           opens this one modal) · BR-INT-026 (environment in words; a test
//           goes to a typed address) · BR-INT-019 (testing sends one real
//           message; a provider with no safe instance says so) · BR-INT-003
//           (a secret is typed once and never shown again; the hint is all a
//           screen holds) · B14 rule 5 (two button sizes) · rule 6 (Disconnect
//           is danger-tier, and disabled until the name is typed) · rule 21
//           (Tailwind only; this file is on route-b-migrated.txt) · rule 31
//           (no database id is a visible value) · rule 32 (one sentence per
//           section) · rule 33 (a refusal is the server's, ≤ 6 words).
// Tests:    src/features/integrations/ConnectModal.dom.test.tsx
// Impacts:  src/api/integrationsEndpoints.ts (the six writes) ·
//           src/features/integrations/IntegrationsTab.tsx (mounts it from
//           the card's button) · the eleven locale catalogues
//           (`integrations.modal.*`, `integrations.refusal.*`).
// ─────────────────────────────────────────────────────────────────────────
//
// ⚠ ONE MODAL, SEVENTEEN PROVIDERS, AND NO PROVIDER IS NAMED IN THIS FILE.
// The pack's own test: *"nine providers do not become nine components."* The
// frame is identical for every card — How to sign in · Environment · the
// field slot · How often · the footer — and the ONLY thing that varies is the
// slot, drawn from `card.fields`. Three of the kinds are not fields at all
// (BR-INT-043, `T27`): `redirect` is a button and a return trip, so the footer
// has no Save (49.2); `issued_secret` is a key WE hand them, shown once, so
// the footer is Done and *nothing to test* (50.1); `mapping_editor` is a
// second step that appears once a file has been seen (50.2). Each is a branch
// on the KIND, never on the provider — `G77`'s rule, one language over.
//
// ⚠ WHAT HAPPENS ON *Save and test* IN THIS RELEASE. The server refuses a
// connect on a coming-soon card (*This connection is not available yet.*) and
// on a live card whose adapter has not arrived (*Cannot be connected yet.*) —
// both in six words, both with nothing saved. This modal shows that sentence
// in the `RefusalLine` under the footer (55.2) and does not pretend. The first
// adapter is wave E's, after the crypto sign-off; until then no real password
// is stored, which is the point.
//
// `OQ-INT-1479` (may a clerk press *Test it now*) is OPEN — Admin-only ships,
// and a read-only role sees every control disabled with the reason.

import type { ReactNode } from "react";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";

import type {
  FieldKind,
  ManifestField,
  OperationRow,
  ProviderCard,
} from "@/api/integrationsEndpoints";
import { SegmentedControl } from "@/components/SegmentedControl";

export type ModalMode = "connect" | "manage";

/** The testable operation — the first declaring a safe instance (BR-INT-019). */
export function testableOperation(card: ProviderCard): OperationRow | null {
  return card.operations.find((one) => one.test_action !== null) ?? null;
}

/**
 * The inventory's `Segmented` — the KIT's now (`components/SegmentedControl`).
 *
 * ⚠ THIS FILE HELD ITS OWN COPY UNTIL 2026-09-04 AND WORK > PARTS HELD A
 * SECOND ONE (B14 rule 36, `DEF-3722`). Neither matched r10's `.seg`: this one
 * drew a selected segment as a pale grey box, the other drew it in the PAGE
 * background colour, and r10 fills it with the accent and reverses the ink.
 * One control, one visual decision, both call sites. The manifest still
 * decides which segment is lit — `disabled` on an option is a fact about the
 * provider, not a refusal owed a sentence, which is why `Segment.disabled` is
 * separate from `Segment.disabledReason`.
 */
function Segmented(props: {
  name: string;
  value: string;
  options: { value: string; label: string; disabled?: boolean }[];
  onChange?: (value: string) => void;
  readOnly?: boolean;
}) {
  const { t } = useTranslation();
  return (
    <SegmentedControl
      purpose="choice"
      name={props.name}
      label={t(`integrations.modal.segmentLabel.${props.name}`, { defaultValue: props.name })}
      active={props.value}
      readOnly={props.readOnly}
      onSelect={(value) => props.onChange?.(value)}
      segments={props.options.map((option) => ({
        id: option.value,
        label: option.label,
        disabled: option.disabled,
      }))}
    />
  );
}

export interface SlotProps {
  card: ProviderCard;
  field: ManifestField;
  value: string;
  error: string | undefined;
  mode: ModalMode;
  replacing: boolean;
  readOnly: boolean;
  onChange: (name: string, value: string) => void;
  onStartOAuth: () => void;
}

/**
 * ⚠ `input` IS A STYLESHEET CLASS AND THAT IS THE RIGHT ANSWER, NOT AN
 * EXCEPTION TO B14 RULE 21. Rule 21 says new UI adds NO class to a stylesheet;
 * `.input` is already declared (`components/FormModal.css`), so reusing it
 * adds none and makes these boxes the same 36px control as every other field
 * in the product. Building the same box out of utilities would be a second
 * opinion about what an input looks like — which is what rule 21 exists to
 * prevent, not to cause. `FilterBar`'s two date boxes record the same reading.
 *
 * ⚠ AND THEY WERE `font-mono` UNTIL 2026-09-04. A host name and a port really
 * are machine text; a send-from address and a username are not, and a form
 * whose every box is typewriter type reads as a terminal rather than as a
 * settings page (B14 rule 36).
 */
const INPUT = "input w-full";
const INVALID = "input w-full border-danger-500";

function textInput(
  props: SlotProps,
  type: "text" | "email",
  inputMode?: "numeric",
  placeholder?: string,
) {
  const id = `field-${props.field.name}`;
  return (
    <input
      id={id}
      name={props.field.name}
      type={type}
      inputMode={inputMode}
      className={props.error ? INVALID : INPUT}
      value={props.value}
      placeholder={placeholder}
      required={props.field.required}
      disabled={props.readOnly || (props.mode === "manage" && !props.replacing)}
      onChange={(event) => props.onChange(props.field.name, event.target.value)}
      aria-invalid={props.error !== undefined}
    />
  );
}

/**
 * THE FIELD SLOT — one renderer per kind, exhaustively (BR-INT-043). Adding a
 * kind to `FieldKind` without a row here is a compile error; there is no
 * `default`, so no manifest can reach a branch nobody wrote.
 */
export const RENDER: Record<FieldKind, (props: SlotProps, t: TFunction) => ReactNode> = {
  text: (props) => textInput(props, "text"),
  host: (props) => textInput(props, "text"),
  // ⚠ `type="text"` AND NOT `type="url"` (`DEF-INT-5589`). A browser's own
  // `url` validity check accepts `javascript:alert(1)` and `ftp://x` and
  // refuses nothing this product cares about, so it would add a SECOND
  // opinion about what an address is — one that disagrees with the server's
  // and shows a bubble no catalogue can translate. The server's refusal is
  // the only one, and it arrives under the field like every other.
  url: (props) => textInput(props, "text"),
  // ⚠ AN EXAMPLE ADDRESS, BECAUSE *Send bills from* WAS AN EMPTY BOX WITH NO
  // ASTERISK, NO PLACEHOLDER AND NO HELP (`DEF-INT-4230`). The asterisk is the
  // rule (r10 rule 10) and it is drawn by `Row` now; this is the other half of
  // what the Product Owner actually needed, which is knowing WHAT to type. The
  // shape is the one the secret field already uses in this file, so it adds no
  // new pattern — and the example is a `.example` domain, which is reserved by
  // RFC 2606 and can never be a real utility's address.
  email: (props, t) => textInput(props, "email", undefined, t("integrations.modal.emailExample")),
  port: (props) => textInput(props, "text", "numeric"),
  secret: (props, t) => {
    const hint = props.card.connection?.credential?.hint ?? null;
    if (props.mode === "manage" && !props.replacing) {
      // The hint is all a screen ever holds of a secret (BR-INT-003).
      return (
        <p className="font-mono text-base text-neutral-600" data-secret-hint="true">
          {hint === null ? "—" : t("integrations.modal.currentHint", { hint })}
        </p>
      );
    }
    return (
      <input
        id={`field-${props.field.name}`}
        name={props.field.name}
        type="password"
        autoComplete="new-password"
        data-secret="true"
        className={props.error ? INVALID : INPUT}
        value={props.value}
        placeholder={t("integrations.modal.secretPlaceholder")}
        required={props.field.required}
        disabled={props.readOnly}
        onChange={(event) => props.onChange(props.field.name, event.target.value)}
        aria-invalid={props.error !== undefined}
      />
    );
  },
  // ⚠ THE LABEL GOES THROUGH THE CATALOGUE (`DEF-INT-4240`). It used to be the
  // STORED VALUE, so *File format* offered `bai2 | camt053 | csv | ofx | qbo |
  // qfx` and *Where it comes from* offered `upload | sftp`, in lower case, next
  // to *Sign-in*, *Production* and *Nightly*. Not B14 rule 31 — these are enum
  // values rather than ids, which is why `G69` is silent and right to be — but
  // they are still machine words on a clerk's screen, and the same modal words
  // everything else properly.
  //
  // ⚠ **NO CATALOGUE LINE IS AUTHORED HERE AND THAT IS DELIBERATE.** The
  // fallback is the raw value, so today's screen is unchanged and the words can
  // be written in the eleven catalogues with no further code change. What
  // `camt053` should read as to a utility clerk is manifest copy about bank
  // file formats, and a wrong word there is worse than a raw one — so it is
  // filed rather than guessed.
  select: (props, t) => (
    <Segmented
      name={props.field.name}
      value={props.value}
      readOnly={props.readOnly || (props.mode === "manage" && !props.replacing)}
      options={props.field.options.map((value) => ({
        value,
        label: t(`integrations.option.${value}`, { defaultValue: value }),
      }))}
      onChange={(value) => props.onChange(props.field.name, value)}
    />
  ),
  // 49.2 — no credential field at all: a button and a return trip.
  //
  // ⚠ **THE BUTTON IS NOT HERE ANY MORE — IT IS THE FOOTER'S PRIMARY
  // (`DEF-INT-4229`).** It used to sit in this panel, in SECONDARY tier, in the
  // middle of the form, inside the field slot's box — while the footer below
  // held nothing but *Cancel*. So on Microsoft 365 and Google Workspace the
  // only button a person found at the bottom of the modal was the way out, and
  // the Product Owner's reading was *"I dont understand this modal"*.
  //
  // Frame 49.2 is right that there is no Save — the round trip IS the save —
  // and what it does not say is that the sign-in press is THEREFORE the commit
  // and must carry a commit's weight and position. What stays here is the
  // sentence explaining where the person is about to go; the act itself is in
  // the footer with every other act in this product.
  redirect: (props, t) => (
    <p className="py-2 text-sm text-neutral-700" data-redirect-note="true">
      {t("integrations.modal.redirectNote", { name: props.card.display_name })}
    </p>
  ),
  // 50.2 — the second step, stated absent until a file has been seen.
  mapping_editor: (_props, t) => (
    <div className="border border-divider bg-surface p-3" data-mapping-editor="true">
      <p className="text-sm font-semibold text-neutral-700">
        {t("integrations.modal.mapping.caption")}
      </p>
      <p className="mt-1 text-sm text-neutral-600">{t("integrations.modal.mapping.afterFile")}</p>
    </div>
  ),
  // 50.1 — a key WE give them: shown once, on issue; afterwards the hint only.
  issued_secret: (props, t) => {
    const hint = props.card.connection?.credential?.hint ?? null;
    return (
      <div className="border border-divider bg-surface p-3" data-issued-key-panel="true">
        <p className="text-sm font-semibold text-neutral-700">
          {t("integrations.modal.issuedKey.caption")}
        </p>
        {/* ⚠ THE TYPEWRITER TYPE FOLLOWS THE HINT AND NOT THE PARAGRAPH
            (`DEF-INT-4228`). `••••7Q2F` is characters a person compares one by
            one against something in front of them, which is the one thing
            monospace is FOR; *No key yet. Save this connection, then issue one
            from Keys we issue.* is a sentence, and setting a sentence in
            typewriter type is what made this modal read as console output. */}
        {hint === null ? (
          <p className="mt-2 text-sm text-neutral-600">
            {t("integrations.modal.issuedKey.beforeIssue")}
          </p>
        ) : (
          <p className="mt-2 font-mono text-base text-neutral-700">
            {t("integrations.modal.currentHint", { hint })}
          </p>
        )}
      </div>
    );
  },
};

export function fieldLabel(t: TFunction, card: ProviderCard, field: ManifestField): string {
  return t(`integrations.provider.${card.key}.field.${field.name}`, { defaultValue: field.label });
}

// ── Lifecycle ────────────────────────────────────────────────────────────
// packet: US-INT-019 (EP-INT-05) · US-INT-002 (EP-INT-01) · US-INT-017 · US-INT-016
// generated: 2026-09-03 by the CR-069 wave B build lane
// checklist: A✔ B✔ C✔ D✔(connect · test · credential · DELETE · oauth/start) E✔(mounted from IntegrationsTab's card button) F✔ G✔ H=n/a
// gates: tsc · vitest (ConnectModal.dom.test.tsx) · G13 (every prop is supplied by the tab) · G15/G18 (every key above in all eleven) · G31 / routeBUtilities.test (this file is on route-b-migrated.txt) · G69 (no id is a visible value)
// exceptions: the Manage view is the modal's (US-INT-019 §1); S142's detail page, the cadence PATCH surface and the credential history (54.2) are waves C and E · `disconnectTypeName` is the one catalogue key this file adds beyond the story's list — the frame (55.1) draws it
// status: VERIFIED-UNRATIFIED
// ─────────────────────────────────────────────────────────────────────────
