// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-042 (EP-CWP-08) — *Send your own reading: one validation,
//           two sources*. Screen: CWP-035 (blueprint `P21`, built from
//           `04-docs/05-modules/15-portal/wireframes/CWP-035.png` as an image —
//           B14 rule 42)
// Defect:   DEF-CWP-10175 — gap E of the PO's 2026-10-17 meter-reading ruling
// Rules:    BR-CWP-067 (one validation, two sources — nothing is judged here) ·
//           BR-CWP-070 / BR-CWP-074 (a figure the check objects to is ACCEPTED
//           and flagged, never refused; every customer reading carries the
//           provenance flag on the server) · CR-068 R8 / US-CWP-042 TC-7 (off
//           → unreachable) · CLAUDE.md hard rule 3 (a reading with its unit) ·
//           B14 rules 21 (Tailwind only), 31 (no database id on screen), 33
//           (copy budgets), 35 (the catalogue writes the words), 36/43 (compose
//           the kit), 44 (our UI standard builds the drawing) ·
//           22-product-maintenance-process.md §6 — the eight questions
// Tests:    src/portal/usage/SendReading.dom.test.tsx
// Impacts:  src/portal/api/portalClient.ts `getSelfReadFrame` · `sendReading` ·
//           src/portal/routing/portalRoutes.tsx · screenIds.ts ·
//           src/portal/usage/Readings.tsx (the head action that opens this)
// ───────────────────────────────────────────────────────
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { ButtonLink } from "@/components/Button";
import { isApiError, type ApiError } from "@/api/client";
import { refusalText } from "@/api/refusalText";

import {
  Card,
  ChecklistTimeline,
  CommitButton,
  DialInput,
  FormField,
  KVList,
  PhotoPicker,
  SectionTitle,
  SelectInput,
  TextInput,
  TwoCol,
  WizardFooter,
  fieldErrorId,
  formatDialFigure,
  usePortalPath,
} from "../components/primitives";
import { usePortalDate } from "../components/regional";
import { PortalScreen, PortalState } from "../components/states";
import {
  getSelfReadFrame,
  sendReading,
  type PortalSelfReadFrame,
  type PortalSelfReadResult,
} from "../api/portalClient";
import { Announced } from "../components/a11y";

/** The address the drawing's own bar carries — `/pine-hill/portal/usage/submit`. */
export const SEND_A_READING_PATH = "/usage/submit";
export const SEND_A_READING_SCREEN = "CWP-035";

type FieldErrors = Partial<Record<"meter" | "register" | "read_on" | "value", string>>;

/** A refusal's sentence per input, keyed by the server's own field name, so
 *  each sentence is tied to the box it is about (question 3). */
function fieldErrorsOf(
  t: (key: string, params?: Record<string, unknown>) => string,
  error: unknown,
): FieldErrors {
  if (!isApiError(error)) return {};
  const out: FieldErrors = {};
  for (const problem of (error as ApiError).fieldErrors) {
    const field = problem.field as keyof FieldErrors;
    if (field === "meter" || field === "register" || field === "read_on" || field === "value") {
      out[field] = t(problem.message_key, problem.params ?? {});
    }
  }
  return out;
}

/**
 * `CWP-035` — *Send us your reading*.
 *
 * ⚠ **NOTHING ON THIS SCREEN JUDGES THE FIGURE.** `BR-CWP-067`: the reading runs
 * through Meter Reads' own validation on the server, exactly as a clerk's does.
 * The screen sends what was typed and reports what came back — *Received*, or
 * *Received – we will check it* when the check objected (`BR-CWP-074`'s
 * validation flag). A threshold computed here would be a second, weaker set of
 * rules, which is the one thing the blueprint's Figure 6 forbids.
 *
 * ⚠ **THE DRAWING'S *WHAT HAPPENS TO IT* SAID *held, not billed yet*, AND THAT
 * IS SUPERSEDED.** The drawing predates `OQ-1393`'s ruling (`BR-CWP-074`,
 * 2026-09-04): a reading is ACCEPTED and recorded at once, and only a flagged
 * one is looked at. The three rows say what the product does now.
 *
 * ⚠ **THE PHOTO IS HELD** (`US-CWP-042` TC-11 — consumer upload is a signed
 * deferral, PO 2026-08-08 DF-4): the picker renders its sentence and no file
 * input.
 *
 * ⚠ **44px TARGETS ON THIS SCREEN ONLY, IN UTILITIES** (accessibility question
 * 6 and the build brief). The kit's controls are shared by every portal form,
 * so the minimum is set on this form's own container with arbitrary variants
 * rather than by changing the kit underneath ninety other screens.
 */
export function SendReadingView(props: { accountId: string }) {
  const { t } = useTranslation();
  const path = usePortalPath();
  const showDate = usePortalDate();
  const [frame, setFrame] = useState<PortalSelfReadFrame | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [meter, setMeter] = useState("");
  const [register, setRegister] = useState("");
  const [readOn, setReadOn] = useState("");
  const [value, setValue] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [refused, setRefused] = useState<string | null>(null);
  const [working, setWorking] = useState(false);
  const [result, setResult] = useState<PortalSelfReadResult | null>(null);

  useEffect(() => {
    let live = true;
    getSelfReadFrame(props.accountId)
      .then((answer) => {
        if (!live) return;
        setFrame(answer);
        setReadOn(answer.today);
        const first = answer.meters[0];
        if (first !== undefined) {
          setMeter(first.meter);
          setRegister(first.registers[0]?.register ?? "");
        }
      })
      .catch((error: unknown) => {
        if (live) setFailed(refusalText(t, error));
      });
    return () => {
      live = false;
    };
  }, [props.accountId, t]);

  const head = (
    <PageHeader
      kicker={t("portal.kicker.readings")}
      title={t("portal.sendReading.title")}
      backTo={{ to: path("/readings"), label: t("portal.readings.title") }}
    />
  );

  if (failed !== null) {
    return (
      <PortalScreen screen="CWP-035" head={head}>
        <PortalState
          kind="failed"
          testId="send-reading"
          sentence={failed}
          waysOut={[
            { label: t("portal.sendReading.seeReadings"), to: path("/readings"), tone: "primary" },
          ]}
        />
      </PortalScreen>
    );
  }
  if (frame === null) {
    return (
      <PortalScreen screen="CWP-035" head={head}>
        <PortalState kind="loading" testId="send-reading" sentence={t("portal.sendReading.opening")} />
      </PortalScreen>
    );
  }
  if (frame.meters.length === 0) {
    return (
      <PortalScreen screen="CWP-035" head={head}>
        <PortalState
          kind="empty"
          testId="send-reading"
          sentence={t("portal.sendReading.noMeters")}
          waysOut={[{ label: t("portal.sendReading.seeReadings"), to: path("/readings") }]}
        />
      </PortalScreen>
    );
  }

  if (result !== null) {
    return (
      <PortalScreen screen="CWP-035" head={head}>
        {/* ⚠ `role="status"` — question 7: *Received* is ANNOUNCED, not only
            shown. */}
        <Card testId="send-reading-result">
          {/* F-02 / F-04: announced through the frame and focused (`Announced`). */}
          <Announced
            tone="status"
            as="div"
            data-received={result.flagged ? "flagged" : "clean"}
            say={result.flagged ? t("portal.sendReading.receivedFlagged") : t("portal.sendReading.received")}
          >
            <SectionTitle>
              {result.flagged ? t("portal.sendReading.receivedFlagged") : t("portal.sendReading.received")}
            </SectionTitle>
            <p className="text-body text-neutral-800" data-sent-reading="">
              {t("portal.sendReading.whatYouSent", {
                reading: formatDialFigure(result.reading) ?? result.reading,
                date: showDate(result.read_on),
              })}
            </p>
            {result.flagged ? (
              <p className="text-body text-neutral-700" data-flag-fact="">
                {result.times_usual !== null
                  ? t("portal.sendReading.timesUsual", { times: result.times_usual })
                  : t("portal.sendReading.looksUnusual")}
              </p>
            ) : null}
          </Announced>
          <div className="mt-4">
            <ButtonLink to={path("/readings")} variant="primary" data-see-readings="">
              {t("portal.sendReading.seeReadings")}
            </ButtonLink>
          </div>
        </Card>
      </PortalScreen>
    );
  }

  const chosen = frame.meters.find((one) => one.meter === meter) ?? frame.meters[0];
  const reg =
    chosen?.registers.find((one) => one.register === register) ?? chosen?.registers[0] ?? null;
  const ready = value.trim() !== "" && readOn !== "" && chosen !== undefined;

  async function send() {
    if (chosen === undefined || reg === null) return;
    setWorking(true);
    setErrors({});
    setRefused(null);
    try {
      setResult(
        await sendReading(props.accountId, {
          meter: chosen.meter,
          register: reg.register,
          value: value.trim(),
          read_on: readOn,
        }),
      );
    } catch (error) {
      const tied = fieldErrorsOf(t, error);
      setErrors(tied);
      if (Object.keys(tied).length === 0) setRefused(refusalText(t, error));
    } finally {
      setWorking(false);
    }
  }

  const meterLabel = (one: (typeof frame.meters)[number]) =>
    t("portal.readings.meterOfService", {
      service: one.service_name ?? one.service ?? "",
      serial: one.serial ?? one.meter,
    });

  const lastRows =
    reg === null
      ? []
      : reg.last_read_on === null
        ? [{ key: "none", label: t("portal.sendReading.noReadingYet"), value: "" }]
        : [
            {
              key: "taken",
              label: t("portal.sendReading.lastTaken", { date: showDate(reg.last_read_on) }),
              value: `${formatDialFigure(reg.last_reading) ?? "—"}`,
            },
            ...(reg.expected_now !== null
              ? [
                  {
                    key: "expected",
                    label: t("portal.sendReading.expectedNow"),
                    value: t("portal.sendReading.about", {
                      value: formatDialFigure(reg.expected_now) ?? reg.expected_now,
                    }),
                  },
                ]
              : []),
          ];

  return (
    <div data-screen="CWP-035">
      {/* ⚠ The screen id is a LITERAL on the populated branch — three source
          scanners find a portal screen by the exact string (see
          `plans/AskForPlan.tsx`). */}
      {head}
      {frame.window !== null && frame.window.open_now ? (
        <p className="mb-4 text-body text-neutral-700" data-window-open="">
          {t("portal.sendReading.windowOpen", { date: showDate(frame.window.to) })}
        </p>
      ) : null}
      <TwoCol
        main={
          <Card testId="send-reading">
            <form
              className="flex flex-col gap-5 [&_a]:min-h-11 [&_button]:min-h-11 [&_input]:min-h-11 [&_select]:min-h-11"
              noValidate
              onSubmit={(event) => {
                event.preventDefault();
                if (ready && !working) void send();
              }}
            >
              <FormField id="sr-meter" label={t("portal.sendReading.fieldMeter")} error={errors.meter}>
                <SelectInput
                  id="sr-meter"
                  value={chosen?.meter ?? ""}
                  options={frame.meters.map((one) => ({ value: one.meter, label: meterLabel(one) }))}
                  invalid={errors.meter !== undefined}
                  describedBy={fieldErrorId("sr-meter")}
                  onChange={(next) => {
                    setMeter(next);
                    const picked = frame.meters.find((one) => one.meter === next);
                    setRegister(picked?.registers[0]?.register ?? "");
                  }}
                />
              </FormField>
              {chosen !== undefined && chosen.registers.length > 1 ? (
                <FormField
                  id="sr-register"
                  label={t("portal.sendReading.fieldRegister")}
                  error={errors.register}
                >
                  <SelectInput
                    id="sr-register"
                    value={reg?.register ?? ""}
                    options={chosen.registers.map((one) => ({
                      value: one.register,
                      label: t(`metering.reads.channel.${one.register}`, {
                        defaultValue: one.register,
                      }),
                    }))}
                    describedBy={fieldErrorId("sr-register")}
                    onChange={setRegister}
                  />
                </FormField>
              ) : null}
              <FormField id="sr-date" label={t("portal.sendReading.fieldDate")} required error={errors.read_on}>
                <TextInput
                  id="sr-date"
                  type="date"
                  value={readOn}
                  required
                  invalid={errors.read_on !== undefined}
                  describedBy={fieldErrorId("sr-date")}
                  onChange={setReadOn}
                />
              </FormField>
              <FormField
                id="sr-value"
                label={t("portal.sendReading.fieldValue")}
                required
                error={errors.value}
              >
                <DialInput
                  id="sr-value"
                  value={value}
                  inputMode="decimal"
                  autoComplete="off"
                  required
                  flagged={errors.value !== undefined}
                  invalid={errors.value !== undefined}
                  describedBy={fieldErrorId("sr-value")}
                  onChange={setValue}
                />
              </FormField>
              <div className="flex flex-col" data-field="sr-photo">
                <span className="mb-1.25 text-base font-semibold text-neutral-800">
                  {t("portal.sendReading.fieldPhoto")}
                </span>
                <PhotoPicker reason={t("portal.sendReading.photoHeld")} />
              </div>
              {refused !== null ? (
                <Announced tone="error" className="text-body font-semibold text-danger-700" data-refused="">
                  {refused}
                </Announced>
              ) : null}
              <WizardFooter
                back={
                  <ButtonLink to={path("/readings")} variant="secondary" data-cancel="">
                    {t("portal.sendReading.cancel")}
                  </ButtonLink>
                }
                forward={
                  <CommitButton
                    label={t("portal.sendReading.send")}
                    working={working}
                    ready={ready}
                    reason={t("portal.sendReading.sendHeld")}
                    onClick={() => void send()}
                  />
                }
              />
            </form>
          </Card>
        }
        rail={
          <>
            <Panel as="aside" title={t("portal.sendReading.lastHeading")}>
              <div data-last-reading="">
                <KVList rows={lastRows} />
              </div>
            </Panel>
            <Panel as="aside" title={t("portal.sendReading.whatHappens")}>
              <ChecklistTimeline
                steps={[
                  {
                    label: t("portal.sendReading.step1"),
                    detail: t("portal.sendReading.step1note"),
                    state: "current",
                  },
                  {
                    label: t("portal.sendReading.step2"),
                    detail: t("portal.sendReading.step2note"),
                    state: "future",
                  },
                  {
                    label: t("portal.sendReading.step3"),
                    detail: t("portal.sendReading.step3note"),
                    state: "future",
                  },
                ]}
              />
            </Panel>
          </>
        }
      />
    </div>
  );
}
