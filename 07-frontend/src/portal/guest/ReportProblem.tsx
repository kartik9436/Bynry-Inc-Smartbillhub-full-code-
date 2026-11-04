// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-007 (EP-CWP-03) — report a problem, and the reporter need
//           not be a customer. Screens: CWP-006 (→ CWP-007 on send)
// Rules:    B14 rule 36 (the captured pack gives the LAYOUT — `08-screen-layouts.md`
//           CWP-006 and `wireframes/CWP-006.png`; `05-prototype/r10-2026-08-16/
//           UI-RULES.md` gives the LOOK; the shared kit is how you comply) ·
//           r10 rule 4 (`Verb ✓` commits) · rule 6 (danger is for DESTRUCTIVE
//           commits — reporting a burst is not one, so nothing here is danger)
//           · rule 9 (a single-choice field is a radio list, never a wall of
//           boxes) · rule 10 (required asterisk) · rule 11 (a consequence box
//           before the commit) · B14 rule 21 (`src/portal/` is on
//           route-b-migrated.txt) · rule 31 (no id is a visible value) ·
//           rule 32 (one sentence per section) · rule 33 (six-word refusals) ·
//           BR-CWP-027 · BR-CWP-056 (a held control keeps its place and its
//           reason) · CR-068 §2b (consumer upload is a signed deferral)
// Tests:    src/portal/guest/ReportProblem.test.tsx
// Impacts:  06-backend/apps/portal/guest_api.reports
// ───────────────────────────────────────────────────────
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { refusalText } from "@/api/refusalText";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { PortalRefusal } from "../components/a11y";

import type { ProblemKind, ReportResult } from "../api/guestClient";
import { PROBLEM_KINDS, postReport } from "../api/guestClient";
import {
  ButtonRow,
  Card,
  CommitButton,
  ConsequenceBox,
  FormField,
  PhotoPicker,
  RadioList,
  SectionTitle,
  TextInput,
  TwoCol,
  TwoUp,
} from "../components/primitives";

/**
 * The catalogue keys, written as LITERALS so the catalogue gate can see every
 * one. The six kinds and their inline hints; three of the six have no hint and
 * that is the wireframe, not an omission.
 */
export const KIND_COPY: Record<ProblemKind, { label: string; hint?: string }> = {
  no_water: { label: "portal.report.kind.no_water", hint: "portal.report.kind.no_water.hint" },
  leak_or_burst: {
    label: "portal.report.kind.leak_or_burst",
    hint: "portal.report.kind.leak_or_burst.hint",
  },
  low_pressure: { label: "portal.report.kind.low_pressure" },
  gas_smell: { label: "portal.report.kind.gas_smell", hint: "portal.report.kind.gas_smell.hint" },
  missed_collection: { label: "portal.report.kind.missed_collection" },
  damaged_meter: { label: "portal.report.kind.damaged_meter" },
};

export function ReportProblem(props: {
  emergencyPhone: string | null;
  onSent: (result: ReportResult) => void;
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const [kind, setKind] = useState<ProblemKind | null>(null);
  const [where, setWhere] = useState("");
  const [notes, setNotes] = useState("");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [working, setWorking] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);

  // ⚠ THE FORM REFUSES BEFORE THE SERVER DOES, and the server refuses anyway.
  // Three required fields (r10 rule 10 marks them; the server's own refusal is
  // what enforces them — BR-SHL-025).
  const ready = kind !== null && where.trim() !== "" && name.trim() !== "" && phone.trim() !== "";

  async function send() {
    if (kind === null) return;
    setWorking(true);
    setRefusal(null);
    try {
      props.onSent(
        await postReport(
          {
            kind,
            location_text: where.trim(),
            notes: notes.trim(),
            reporter_name: name.trim(),
            reporter_phone: phone.trim(),
          },
          client,
        ),
      );
    } catch (error) {
      setRefusal(refusalText(t, error));
    } finally {
      setWorking(false);
    }
  }

  return (
    <div data-screen="CWP-006">
      {/* ⚠ **ABOVE EVERYTHING, ON EVERY WIDTH — `CR-085` (2026-09-08), and it
          is a safety fix rather than a layout preference.** The signed-off
          drawing for this screen is unambiguous about where this band goes:
          *"The emergency band — Above everything, on every width, in the danger
          tier. A form that quietly accepts a gas-smell report is the most
          dangerous screen in the product."*

          It lived in the RAIL, which reads correctly at 1280 — the band sits
          beside the form — and is exactly wrong at 390, where `TwoCol` stacks
          the rail UNDER the main column: somebody standing in the street
          smelling gas scrolled past six radio choices, five fields and the
          Send button before being told to ring instead. **Nothing in this repo
          could see it**: `tsc` passes, and the screen's own DOM test asserts
          the band is PRESENT and never asks WHERE — the shape hard-won law 7
          calls *looking at the wrong thing*. The test below it now compares
          positions.

          The *already reported* note stays in the rail. It is a note, and it is
          the one thing this band must never be confused with — which is what
          `DEF-CWP-3986` was about one tone earlier. */}
      {/* ⚠ **ONLY WHEN THE FRAME DRAWS NONE — `DEF-CWP-4937`, `CR-085` step 2
          (2026-09-11), AND IT IS A DUPLICATE BEING REMOVED RATHER THAN A BAND
          BEING TAKEN AWAY.** `GuestFrame` gained its own `EmergencyBand` in the
          same CR, above the children on EVERY signed-out screen — which is what
          `s3`'s *"Emergency number on every unauthenticated screen"* asks for
          and what this screen alone used to provide. Measured in a browser at
          390 AND 1280 on a tenant with a number published: **two identical red
          panels, stacked**, on the most dangerous screen in the product.

          ⚠ **THE FRAME DRAWS NOTHING WHEN THE UTILITY HAS PUBLISHED NO NUMBER**
          (`BR-CWP-093` — no phone, no band), and that is exactly the tenant
          where this form still has something to say: *ring the number on your
          bill, any hour, do not use this form*. So this band survives as the
          FALLBACK and disappears the moment the frame has a number of its own.
          Both branches were opened in a browser; `brazosbend` (no number) shows
          this one, `pine-hill` (a number) shows the frame's.

          ⚠ **WHAT THE FALLBACK KEEPS THAT THE FRAME'S BAND DOES NOT IS THE
          SENTENCE *Do not use this form*** — `portal.report.emergencyTail`
          against the frame's `portal.emergency.anyHour`. On a tenant WITH a
          number that sentence is no longer on this screen. It is a frame
          decision rather than a screen one, so it is recorded and filed
          (`DEF-CWP-4937`) instead of being restored here as a third band. */}
      {props.emergencyPhone === null ? (
        <div className="mb-4" data-emergency-band="">
          <Panel as="aside" tone="emergency" title={t("portal.report.emergencyTitle")}>
            {t("portal.report.emergencyLead")}{" "}
            <span className="font-bold text-neutral-900" data-emergency-phone="">
              {t("portal.report.emergencyNoPhone")}
            </span>
            {t("portal.report.emergencyTail")}
          </Panel>
        </div>
      ) : null}
      <PageHeader
        kicker={t("portal.report.kicker")}
        title={t("portal.report.title")}
        rollup={t("portal.report.subtitle")}
      />
      <TwoCol
        main={
          <Card testId="cwp006-form">
            <SectionTitle>{t("portal.report.whatIsHappening")}</SectionTitle>
            <RadioList
              name={t("portal.report.whatIsHappening")}
              value={kind}
              options={PROBLEM_KINDS.map((one) => ({
                value: one,
                label: t(KIND_COPY[one].label),
                hint: KIND_COPY[one].hint === undefined ? undefined : t(KIND_COPY[one].hint),
              }))}
              onChange={(value) => setKind(value as ProblemKind)}
            />
            {/* ⚠ **`gap-5` — B14 rule 39's *field → field 20px* (`DEF-CWP-4856`).**
                These five fields were direct children of `Card`, whose own gap is
                the scale's BLOCK step (16) and is correct for blocks — a card's
                sections, a panel and the button row. A FIELD stack is the
                anatomy's third figure and it is 20, which is what makes a
                helper (6px under its own input) read as attached to that input
                rather than floating between two. Measured here before the
                change at both widths: **16**, against the helper's 6 — a
                ratio of 1 : 4.3 : 4 where the rule asks for 1 : 1 : 4.

                ⚠ **A WRAPPER RATHER THAN A CHANGE TO `Card`.** `Card` is the
                kit's and it is the container of every guest screen's main
                column; moving its gap would move panels, consequence boxes and
                button rows on screens four other lanes own. The kit already
                says where 20 lives — `TwoUp` is `gap-5` — and this is the same
                figure for the same relationship, one level up. */}
            <div className="flex flex-col gap-5">
              <FormField
                id="cwp006-where"
                label={t("portal.report.where")}
                helper={t("portal.report.whereHelp")}
                required
              >
                <TextInput id="cwp006-where" value={where} onChange={setWhere} />
              </FormField>
              <FormField id="cwp006-notes" label={t("portal.report.anythingElse")}>
                <TextInput id="cwp006-notes" value={notes} onChange={setNotes} multiline />
              </FormField>
              <FormField id="cwp006-photo" label={t("portal.report.photo")}>
                <PhotoPicker reason={t("portal.report.photoHeldReason")} />
              </FormField>
              <TwoUp>
                <FormField id="cwp006-name" label={t("portal.report.yourName")} required>
                  <TextInput id="cwp006-name" value={name} onChange={setName} />
                </FormField>
                <FormField id="cwp006-phone" label={t("portal.report.phone")} required>
                  <TextInput id="cwp006-phone" value={phone} onChange={setPhone} />
                </FormField>
              </TwoUp>
            </div>
            <ConsequenceBox
              heading={t("portal.report.consequences")}
              bullets={[
                t("portal.report.consequence.job"),
                t("portal.report.consequence.reference"),
                t("portal.report.consequence.ring"),
              ]}
            />
            {refusal !== null ? <PortalRefusal>{refusal}</PortalRefusal> : null}
            <ButtonRow>
              {/* r10 rule 4: `Verb ✓` commits. NOT the danger tier — rule 6
                  reserves that for a destructive commit, and raising a job is
                  the opposite of destructive. */}
              <CommitButton
                label={t("portal.report.send")}
                working={working}
                ready={ready}
                reason={t("portal.report.notReady")}
                onClick={() => void send()}
              />
            </ButtonRow>
          </Card>
        }
        rail={
          <>
            {/* ⚠ **THE EMERGENCY BAND USED TO BE HERE AND IS NOW ABOVE THE PAGE
                HEAD** — see the long note at the top of this component. It kept
                `tone="emergency"` when it moved (`DEF-CWP-3986`: the tone did
                not exist until 2026-09-05, so the band rendered as a plain grey
                box indistinguishable from the note directly below it). What it
                could not keep was this POSITION, which put it under the whole
                form at 390.

                ⚠ **A PLAIN PANEL, AND `tone="info"` WAS WRONG HERE — SEEN BY LOOKING,
                which is the only way it could be (hard-won law 6).** This rail note
                used to be a quiet grey box; the B14 rule 36 fold gave it the kit's
                `info` tone, which is a blue border — and on `CWP-005` that put the
                loudest thing on the page around *"someone may have reported this
                already"* while the panel that says *ring this number, a smell of gas
                is an emergency* stayed quiet. r10 draws no blue at all: its device
                for an aside is `.hint`, grey text, and its emphasis is a rule in
                `--color-accent`. A second hue also competes with the tenant's own
                colour, which is the whole point of this wave. `info` still means
                blue-bordered and `CWP-013`'s holiday panel still uses it; a note is
                not an `info`. */}
            <Panel as="aside">
              {t("portal.report.alreadyLead")}{" "}
              <span className="font-bold text-neutral-900">{t("portal.report.alreadyBold")}</span>
            </Panel>
          </>
        }
      />
    </div>
  );
}
