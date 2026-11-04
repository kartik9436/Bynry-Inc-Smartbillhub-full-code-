// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-001 (EP-TEN-03 §Stories; US-TEN-002 seed toggle at S111)  Screens: S110, S111, S112, S113, S114
// Rules:    BR-TEN-010 (one atomic, idempotent commit) · BR-TEN-011 (slug grammar; live check ADVISORY, commit re-checks) ·
//           BR-TEN-012 (seed only when the S111 toggle is on) · BR-TEN-014 (14-day trial, no card) · BR-TEN-003 (tenant never client input) ·
//           BR-TEN-045 OBSOLETE (PO 2026-08-10): with one origin the commit signs the owner in, so the
//           cross-host handoff screen is gone and S114 routes straight to /{tenant}/checklist ·
//           BR-SHL-018 (rail semantics) · BR-SHL-019 (single-flight commit) · BR-SHL-020 (plain-language failure) ·
//           BR-SHL-033 (long lists are searchable) · BR-SHL-017 (field kit + inline validation)
// ───────────────────────────────────────────────────────
// S110–S114 self-serve signup. The five steps are A1's canonical order
// (1 Your utility · 2 How you bill · 3 Utility size (was Plan & setup until DEF-TEN-4222, 2026-10-02) · 4 Review · 5 Create
// login), and the commit sits on S114 exactly as US-TEN-001 §1 and the signed
// prototype place it.
//
// Everything transactional belongs to FE-06 WizardFrame: it owns the rail, the
// Back/Continue row, the ✓ working state and the SINGLE-FLIGHT commit
// (BR-SHL-019), so a double-clicked "Create utility & go live" cannot post
// twice. This file owns only the fields, the per-step validation and the ONE
// `POST /tenants` call. Draft values live here (above the frame), which is what
// makes them survive rail jumps (BR-SHL-018).
//
// Fields are exactly what `POST /tenants` accepts. Three A1 controls are
// deliberately NOT rendered, because the ratified provisioning payload has
// nowhere to put them and a field that silently discards input is a lie:
// starting rate style / billing cycle / bill-on day (S111), the implementation
// package (S112) and country (S110). Reported with this packet.
//
// WHAT HAPPENS AFTER THE COMMIT (PO 2026-08-10, path tenancy). BR-TEN-045's
// cross-host handoff is OBSOLETE: the tenant now lives at a path on this same
// origin, so `POST /api/tenants` signs the owner in at commit and the wizard
// routes straight to `/{subdomain}/checklist` — S62, with a session. There is
// no success screen, no "go to your new address and sign in again", and no host
// to compose: the whole VITE_TENANT_HOST_SUFFIX mechanism existed only to name
// a cross-host address and is deleted with it. The subdomain the route is built
// from is the SERVER's (`ProvisionResult.subdomain`), never the typed draft.
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api, diagnosticOf } from "@/api/client";
import type { ApiClient, JobRecord, SampleStep } from "@/api/client";
import { checkSubdomain, createTenant } from "@/api/endpoints";
import type {
  ProvisionResult,
  SamplePlant,
  SignupPayload,
  SubdomainCheck,
} from "@/api/endpoints";
import { refusalText } from "@/api/refusalText";
import { Button } from "@/components/Button";
import { createSearchDebouncer } from "@/components/DataTable";
import type { SearchDebouncer } from "@/components/DataTable";
import {
  CheckboxField,
  PasswordField,
  SearchSelectField,
  SelectField,
  TextField,
} from "@/components/FormModal";
import type { Translator } from "@/components/FormModal";
import { FieldError } from "@/components/StateFrame";
import { useToast } from "@/components/Toast";
import { Kicker } from "@/components/TextBits";
import { SIZE_BANDS, sizeBandForPlan, sizeBandRange } from "@/features/public/sizeBands";
import { tenantPathFrom } from "@/routing/tenantPath";
import {
  WizardFrame,
  clampStepToReached,
  initialWizardNav,
  jumpBackTo,
} from "@/components/WizardFrame";
import type { WizardCommitOutcome, WizardNavState, WizardStep } from "@/components/WizardFrame";
import { US_STATE_OPTIONS } from "@/components/usStates";


// ── Reference data mirrored from the server-side authorities ───────────────
// Neither list has a public endpoint, so both are mirrored here with the file
// that owns them named. They are DATA (codes + proper nouns), not UI copy —
// the labels the user reads for services ARE catalog keys.

// A1 §S110 "Which services do you bill?" — ALL ELEVEN platform services, in
// `SERVICE_SEED` order (BR-RAT-024; 06-backend/apps/tenancy/migrations/
// 0001_initial.py is the authority for the first ten, and
// 0033_cr063_fire_service.py for `fire`).
//
// ⚠ **IT WENT TO ELEVEN ON 2026-09-02 (CR-063) AND THE HAZARD BELOW IS
// UNCHANGED, NOT HISTORICAL.** Nothing in this repository compares this
// constant to the database seed, so the next service added to the catalogue
// will be absent from this screen exactly as four were before — and the tenant
// will sign up successfully, get it `enabled=False`, and see no control.
// `SignupWizard.test.tsx` asserts the COUNT for that reason: it is the only
// thing standing between the catalogue and this list.
//
// ⚠ **THIS LIST HELD SIX UNTIL 2026-08-27 AND THE RULING WAS TEN SINCE
// 2026-08-17 — CR-039 wave A task 2, and it is hard-won law 2 one layer up.**
// The PO ruled it with CR-010 B-9 and mandate 4, verbatim: *"we will provdie
// full list for all services - they can always select what they want out of
// it; more is better ; less is contraint"*, re-confirmed 2026-08-27 (*"yes I
// already confirmed it"*). The BACKEND was rewritten to match on 2026-08-18 —
// `_validate_signup` checks each posted code against the live `Service`
// catalogue rather than a hard-coded six, and `_enable_signup_services` gives
// every one of the ten a `tenant_services` row with the chosen ones enabled.
// **Only this constant stayed at six**, so a storm-water, solar, thermal or
// battery utility signed up successfully and got every service it sells
// `enabled=False` — silently, because the chip was never on the page. That is
// CR-039's own finding 1 (*"an electric+gas tenant signs up successfully and
// gets nothing"*), and no gate in this repo compares a frontend constant to a
// database seed, which is why it survived ten days after being ruled.
//
// A1 §S110 draws six. **The ruling is nine days newer than A1's extraction and
// wins**, per the precedent stamped for r10 SET-15 on 2026-08-27: the newest
// signed statement wins and the divergence is recorded rather than followed.
export const SIGNUP_SERVICES: readonly { code: string; labelKey: string }[] = [
  { code: "electric", labelKey: "tenancy.signup.service.electric" },
  { code: "water", labelKey: "tenancy.signup.service.water" },
  { code: "gas", labelKey: "tenancy.signup.service.gas" },
  { code: "sewer", labelKey: "tenancy.signup.service.sewer" },
  { code: "trash", labelKey: "tenancy.signup.service.trash" },
  { code: "storm_water", labelKey: "tenancy.signup.service.storm_water" },
  { code: "solar", labelKey: "tenancy.signup.service.solar" },
  { code: "broadband", labelKey: "tenancy.signup.service.broadband" },
  { code: "thermal_heat", labelKey: "tenancy.signup.service.thermal_heat" },
  { code: "battery", labelKey: "tenancy.signup.service.battery" },
  // CR-063 — the ELEVENTH service, APPENDED (BR-RAT-024, amended 2026-09-02).
  // ⚠ **THIS ROW IS THE WHOLE OF WHY CR-063 PUT THE FRONT END BEFORE THE DEMO
  // DATA.** The catalogue row, the API and every backend test were green
  // without it, and a utility that sells fire protection would have signed up,
  // received `fire` with `enabled=False`, and never seen a tick to change it —
  // the same silent shape this constant produced for four services for ten days
  // (see the note above). A real customer is being onboarded on this one.
  { code: "fire", labelKey: "tenancy.signup.service.fire" },
];

// ⚠ **THE LIST MOVED TO THE KIT ON 2026-09-23 (`components/usStates.ts`)** so
// the service-request billing address and `UsAddressFields` read the same
// fifty-two rows as sign-up. Re-exported here under its old name so nothing
// that imported it from this file moves.
export { US_STATE_OPTIONS };

// US-TEN-001 §5: USD or CAD.
export const SIGNUP_CURRENCIES: readonly string[] = ["USD", "CAD"];

// ── The draft (lives above WizardFrame, so rail jumps keep values) ─────────

export interface SignupDraft {
  name: string;
  subdomain: string;
  state: string;
  services: string[];
  currency: string;
  taxRegion: string;
  loadDefaults: boolean; // S111 toggle, default ON (BR-TEN-012)
  plan: string; // plan CODE the picked size band maps to (features/public/sizeBands.ts)
  ownerName: string;
  ownerEmail: string;
  ownerPassword: string;
  ownerPhone: string;
  termsAccepted: boolean;
}

export const EMPTY_SIGNUP_DRAFT: SignupDraft = {
  name: "",
  subdomain: "",
  state: "",
  services: [],
  currency: "USD",
  taxRegion: "",
  loadDefaults: true,
  plan: "",
  ownerName: "",
  ownerEmail: "",
  ownerPassword: "",
  ownerPhone: "",
  termsAccepted: false,
};

// ── DEF-539 · the draft SURVIVES a reload ──────────────────────────────────
// The step travelled in the URL (`?step=3`) while every field lived only in
// React state, so any reload — F5, an email-verification link, a recovered
// tab — rendered step 1 empty under a URL still claiming step 3, and a
// prospective customer typed ~10 fields again. The draft now round-trips
// through sessionStorage: tab-scoped, gone when the tab closes, which is the
// right lifetime for pre-account PII. ⚠ **THE PASSWORD IS NEVER STORED** —
// a restored session lands on the account step to retype it, and
// `stepValid(5)` already refuses to commit without it.
export const SIGNUP_DRAFT_STORAGE_KEY = "smartbillhub.signup.draft.v1";

export function storableSignup(draft: SignupDraft, reached: number): string {
  // ⚠ Built by COPY-THEN-DELETE rather than by destructuring the password into
  // a discarded binding: the discard reads as intentional to a human and as an
  // unused variable to eslint, which is a lint error rather than a style
  // opinion. The property is removed by name so the omission stays obvious.
  const rest: Partial<SignupDraft> = { ...draft };
  delete rest.ownerPassword;
  return JSON.stringify({ draft: rest, reached });
}

/** Tolerates anything: absent, truncated, hand-edited, or from an older
 *  shape — every field is re-checked against the draft's own types, and
 *  garbage restores to `null` rather than to a half-broken form. */
export function restoreSignup(
  raw: string | null,
): { draft: SignupDraft; reached: number } | null {
  if (raw === null) {
    return null;
  }
  try {
    const parsed: unknown = JSON.parse(raw);
    const stored = (parsed as { draft?: unknown }).draft;
    if (typeof stored !== "object" || stored === null) {
      return null;
    }
    const source = stored as Record<string, unknown>;
    const draft: SignupDraft = { ...EMPTY_SIGNUP_DRAFT };
    for (const key of Object.keys(EMPTY_SIGNUP_DRAFT) as (keyof SignupDraft)[]) {
      if (key === "ownerPassword") {
        continue; // never stored, never restored
      }
      const value = source[key];
      if (key === "services") {
        if (Array.isArray(value)) {
          draft.services = value.filter((item): item is string => typeof item === "string");
        }
        continue;
      }
      if (typeof value === typeof EMPTY_SIGNUP_DRAFT[key]) {
        (draft as unknown as Record<string, unknown>)[key] = value;
      }
    }
    const rawReached = (parsed as { reached?: unknown }).reached;
    const reached =
      typeof rawReached === "number" && Number.isInteger(rawReached)
        ? Math.min(Math.max(rawReached, 1), SIGNUP_STEP_COUNT)
        : 1;
    return { draft, reached };
  } catch {
    return null;
  }
}

/** sessionStorage can throw (private mode, storage off) — a signup that
 *  cannot persist still signs up; it just loses the DEF-539 convenience. */
export function safeSessionGet(key: string): string | null {
  try {
    return window.sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

export function safeSessionSet(key: string, value: string | null): void {
  try {
    if (value === null) {
      window.sessionStorage.removeItem(key);
    } else {
      window.sessionStorage.setItem(key, value);
    }
  } catch {
    // nothing to do — see above
  }
}

export const SIGNUP_STEP_COUNT = 5;
export const MAX_UTILITY_NAME = 120; // US-TEN-001 §5

/**
 * A1 friction control: the web address is auto-suggested from the utility name.
 * Shapes the name into the BR-TEN-011 grammar (lowercase DNS label, [a-z0-9-],
 * no edge hyphen, ≤63) — a SUGGESTION only; the server owns the verdict.
 */
export function suggestSubdomain(name: string): string {
  const shaped = name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
  return shaped.slice(0, 63).replace(/-$/, "");
}

const EMAIL_SHAPE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export interface SubdomainState {
  checking: boolean;
  result: SubdomainCheck | null;
}

export const IDLE_SUBDOMAIN: SubdomainState = { checking: false, result: null };

/**
 * Per-step Continue gate (BR-SHL-018: an invalid step stays put). Client-side
 * only — the server re-validates everything at commit, including the subdomain
 * race the live check cannot see (BR-TEN-011, US-TEN-004 TC-2).
 */
export function stepValid(step: number, draft: SignupDraft, subdomain: SubdomainState): boolean {
  if (step === 1) {
    const named = draft.name.trim() !== "" && draft.name.trim().length <= MAX_UTILITY_NAME;
    // The live check is advisory but it is the only client-side knowledge of
    // the BR-TEN-011 grammar and the reserved list — those live server-side and
    // are never duplicated here.
    const addressOk =
      draft.subdomain.trim() !== "" && subdomain.result !== null && subdomain.result.available;
    return named && addressOk && draft.services.length > 0;
  }
  if (step === 2) {
    return SIGNUP_CURRENCIES.includes(draft.currency);
  }
  if (step === 3) {
    return draft.plan !== "";
  }
  if (step === 4) {
    return true; // review is read-only
  }
  return (
    draft.ownerName.trim() !== "" &&
    EMAIL_SHAPE.test(draft.ownerEmail.trim()) &&
    draft.ownerPassword !== "" &&
    draft.termsAccepted
  );
}

/** Exactly the payload `provision_tenant` validates — no invented fields. */
export function signupPayload(draft: SignupDraft): SignupPayload {
  return {
    name: draft.name.trim(),
    subdomain: draft.subdomain.trim().toLowerCase(),
    state: draft.state === "" ? null : draft.state,
    currency: draft.currency,
    tax_region: draft.taxRegion === "" ? null : draft.taxRegion,
    plan: draft.plan,
    services: draft.services,
    load_defaults: draft.loadDefaults,
    owner: {
      full_name: draft.ownerName.trim(),
      email: draft.ownerEmail.trim(),
      password: draft.ownerPassword,
      phone: draft.ownerPhone.trim() === "" ? null : draft.ownerPhone.trim(),
    },
  };
}

/** A9 `?step=` restore, clamped to the highest validated step (BR-SHL-018). */
export function navFromStepParam(raw: string | null, nav: WizardNavState): WizardNavState {
  if (raw === null) {
    return nav;
  }
  return clampStepToReached(Number.parseInt(raw, 10), nav, SIGNUP_STEP_COUNT);
}

// ── The new utility's address (pure, provable without a browser) ───────────

/** Where S114 lands the owner: the S62 checklist, inside the new tenant. */
export const CHECKLIST_SEGMENT = "/checklist";

/**
 * The address the S110 line shows and the S114 commit routes to, composed from
 * the SAME helper the router uses — so what the first screen promises and where
 * the last screen goes cannot diverge:
 *
 *   tenantAddress("smartbillhub.bynry.com", "brazosbend")
 *     → "smartbillhub.bynry.com/brazosbend"
 *
 * Path tenancy (PO 2026-08-10) is what makes this trivial: the utility lives at
 * a PATH on the origin the visitor is already on, so there is no host to
 * configure, derive or get wrong. `appHost` is just `window.location.host`.
 */
export function tenantAddress(appHost: string, subdomain: string): string {
  return `${appHost}${tenantPathFrom(subdomain, "")}`;
}

/** The ONE `POST /tenants` call, lifted out of the component so the commit law
 *  can be driven through WizardFrame's controller in a test without a browser.
 *  Returns the server's answer alongside the frame outcome: the success screen
 *  names the subdomain the SERVER assigned, never the value the user typed. */
export interface SignupCommitResult {
  outcome: WizardCommitOutcome;
  provisioned: ProvisionResult | null;
}

export async function commitSignup(
  draft: SignupDraft,
  client: ApiClient,
  t: Translator,
): Promise<SignupCommitResult> {
  try {
    const result = await createTenant(signupPayload(draft), client);
    return { outcome: { ok: true }, provisioned: result };
  } catch (error) {
    // BR-SHL-020 r2: plain language, from the catalogue entry for message_key
    // and NOTHING else — never a raw code, never a built sentence, and never
    // the server's `params.detail` (DEF-322).
    const reason = refusalText(t, error);
    return { outcome: { ok: false, reason }, provisioned: null };
  }
}

// ── The screen ─────────────────────────────────────────────────────────────

export interface SignupWizardProps {
  client?: ApiClient; // test seam — screens never build their own transport
  appHost?: string; // test seam — SSR has no window.location
  initialNav?: WizardNavState; // test seam — renders a later step statically
}

function currentAppHost(): string {
  return typeof window === "undefined" ? "" : window.location.host;
}

export function SignupWizard(props: SignupWizardProps) {
  const { t, i18n } = useTranslation();
  const fireToast = useToast();
  const navigate = useNavigate();
  const client = props.client ?? api;
  const appHost = props.appHost ?? currentAppHost();

  const [searchParams, setSearchParams] = useSearchParams();
  // DEF-539: one read at mount; `useState` initialisers run once, so a
  // re-render never re-restores over live typing.
  const [restored] = useState(() => restoreSignup(safeSessionGet(SIGNUP_DRAFT_STORAGE_KEY)));
  const [navState, setNavState] = useState<WizardNavState>(
    () =>
      props.initialNav ??
      (restored === null
        ? initialWizardNav()
        : { step: restored.reached, reached: restored.reached }),
  );
  const nav = navFromStepParam(searchParams.get("step"), navState);
  function handleNav(next: WizardNavState): void {
    setNavState(next);
    const params = new URLSearchParams(searchParams);
    params.set("step", String(next.step)); // A9: the step is URL state
    setSearchParams(params, { replace: true });
  }

  const [draft, setDraft] = useState<SignupDraft>(restored === null ? EMPTY_SIGNUP_DRAFT : restored.draft);
  function patch(change: Partial<SignupDraft>): void {
    setDraft((current) => ({ ...current, ...change }));
  }

  // ── S110 live availability (ADVISORY, BR-TEN-011) ────────────────────────
  // IS-3 mechanics through the ONE debouncer (300 ms / min 2 chars) — never
  // re-implemented (DataTable/AppShell/SearchSelectField precedent).
  const [subdomain, setSubdomain] = useState<SubdomainState>(IDLE_SUBDOMAIN);
  const checkRef = useRef<(value: string) => void>(() => undefined);
  checkRef.current = (value: string) => {
    if (value === "") {
      setSubdomain(IDLE_SUBDOMAIN);
      return;
    }
    setSubdomain({ checking: true, result: null });
    void checkSubdomain(value, client)
      .then((result) => setSubdomain({ checking: false, result }))
      // A failed check must never claim "available" — it stays unknown, and
      // Continue stays blocked until an answer arrives.
      .catch(() => setSubdomain(IDLE_SUBDOMAIN));
  };
  const debouncerRef = useRef<SearchDebouncer | null>(null);
  if (debouncerRef.current === null) {
    debouncerRef.current = createSearchDebouncer((value) => checkRef.current(value));
  }
  const debouncer = debouncerRef.current;
  useEffect(() => {
    const active = debouncerRef.current;
    return () => active?.clear();
  }, []);

  // DEF-539: the advisory availability check re-runs for a RESTORED subdomain
  // — the verdict is the server's and was never stored, so a reload must ask
  // again before Continue can pass step 1.
  useEffect(() => {
    if (restored !== null && restored.draft.subdomain !== "") {
      checkRef.current(restored.draft.subdomain);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mount only, by design
  }, []);

  function handleSubdomainChange(value: string): void {
    const cleaned = value.trim().toLowerCase();
    patch({ subdomain: cleaned });
    setSubdomain(IDLE_SUBDOMAIN);
    debouncer.type(cleaned);
  }

  function handleNameChange(value: string): void {
    // Friction control: keep suggesting an address until the user edits one.
    const suggestion = suggestSubdomain(value);
    const following = draft.subdomain === "" || draft.subdomain === suggestSubdomain(draft.name);
    patch({ name: value, ...(following ? { subdomain: suggestion } : {}) });
    if (following) {
      setSubdomain(IDLE_SUBDOMAIN);
      debouncer.type(suggestion);
    }
  }


  // ── S114 commit — ONE call (BR-SHL-019/BR-TEN-010) ───────────────────────
  // Single-flight is WizardFrame's (its controller ignores a second click while
  // one commit is in flight); this file supplies the call and keeps the answer.
  const provisionedRef = useRef<ProvisionResult | null>(null);

  // ── CR-017 · the provisioning screen (PO 2026-08-19) ─────────────────────
  // *"We want to display confirmation to user process is taking place in the
  // background and data seeding is in progress, that you for wating your
  // Utility will be provision soon; … otherwise they are left hi and dry"*
  //
  // `committing` flips the moment the button is pressed — SYNCHRONOUSLY, before
  // the await — because the wait it exists to cover starts there. It does not
  // wait for the response: with JOBS_EAGER on (every deployment today) the
  // sample-data plant runs INSIDE this request, and that is where the seconds
  // go. A screen that appeared only after the response would narrate a wait
  // that was already over.
  const [committing, setCommitting] = useState(false);
  const [provisioned, setProvisioned] = useState<ProvisionResult | null>(null);

  // DEF-539: every keystroke and step advance lands in sessionStorage; a
  // provisioned signup clears it — the draft's job is done and the PII with it.
  useEffect(() => {
    if (provisioned !== null) {
      safeSessionSet(SIGNUP_DRAFT_STORAGE_KEY, null);
      return;
    }
    safeSessionSet(SIGNUP_DRAFT_STORAGE_KEY, storableSignup(draft, navState.reached));
  }, [draft, navState.reached, provisioned]);

  async function handleCommit(): Promise<WizardCommitOutcome> {
    setCommitting(true);
    const { outcome, provisioned: result } = await commitSignup(draft, client, (key, params) =>
      t(key, params),
    );
    if (result !== null) {
      // BR-TEN-010: a replay answers with the SAME tenant and `created: false`.
      // That is a success, not a duplicate — nothing was written twice.
      provisionedRef.current = result;
      setProvisioned(result);
      fireToast(
        result.created
          ? t("tenancy.signup.toast.created", { name: result.name })
          : t("tenancy.signup.toast.replayed", { name: result.name }),
      );
    } else {
      // A REFUSED commit goes back to the wizard, where WizardFrame's own
      // plain-language failure panel already lives (BR-SHL-020). The
      // provisioning screen never reports a signup error: it is the screen for
      // work that IS happening, and pretending otherwise would put two
      // different failure surfaces in front of one refusal.
      setCommitting(false);
    }
    return outcome;
  }

  function handleCommitted(): void {
    // ⚠ THE HANDOVER MOVED (CR-017). It used to fire here, the instant the
    // commit resolved. It now belongs to the provisioning screen, which owns
    // the whole post-commit wait and hands over when the background work is
    // finished (or has honestly stopped waiting for it). Nothing else changed:
    // the address is still built from the SERVER's slug, never the typed draft.
  }

  function handleProvisioningDone(subdomain: string): void {
    // PO 2026-08-10: one origin, so the commit already signed the owner in —
    // the wizard hands straight over to S62 inside the new tenant.
    navigate(tenantPathFrom(subdomain, CHECKLIST_SEGMENT));
  }

  const steps: WizardStep[] = [
    {
      id: "utility",
      label: t("tenancy.signup.step.utility"),
      validate: () => stepValid(1, draft, subdomain),
      content: (
        <div className="card">
          <Kicker>{t("tenancy.signup.stepOf", { step: 1, total: 5 })}</Kicker>
          <h2 className="my-1 text-h4">{t("tenancy.signup.utility.title")}</h2>
          <p className="m-0 mb-4 text-base text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">{t("tenancy.signup.utility.hint")}</p>
          <TextField
            id="signup-name"
            label={t("tenancy.signup.utility.name")}
            value={draft.name}
            onChange={handleNameChange}
            required
            placeholder={t("tenancy.signup.utility.namePlaceholder")}
          />
          <TextField
            id="signup-subdomain"
            label={t("tenancy.signup.utility.subdomain")}
            value={draft.subdomain}
            onChange={handleSubdomainChange}
            required
            help={t("tenancy.signup.utility.subdomainHelp")}
          />
          <SubdomainAvailability state={subdomain} appHost={appHost} />
          {/* BR-SHL-033: 52 entries is a long list — searchable, never a bare
              scroll list. */}
          <SearchSelectField
            id="signup-state"
            label={t("tenancy.signup.utility.state")}
            value={draft.state}
            onChange={(value) => patch({ state: value })}
            options={US_STATE_OPTIONS}
            placeholder={t("tenancy.signup.utility.statePlaceholder")}
          />
          <fieldset
            className="m-0 mb-4 flex flex-wrap gap-2 border-0 p-0"
            data-signup="services"
          >
            <legend className="mb-2 text-sm text-[color-mix(in_srgb,var(--color-text)_70%,transparent)]">
              {t("tenancy.signup.utility.services")}
            </legend>
            {SIGNUP_SERVICES.map((service) => (
              <label
                key={service.code}
                className="inline-flex cursor-pointer items-center gap-2 border-2 border-divider px-3 py-2 text-base has-[input:checked]:border-accent has-[input:checked]:bg-accent-100"
              >
                <input
                  type="checkbox"
                  checked={draft.services.includes(service.code)}
                  onChange={(event) =>
                    patch({
                      services: event.target.checked
                        ? [...draft.services, service.code]
                        : draft.services.filter((code) => code !== service.code),
                    })
                  }
                />
                <span>{t(service.labelKey)}</span>
              </label>
            ))}
            {draft.services.length === 0 && (
              <FieldError message={t("tenancy.signup.utility.servicesRequired")} />
            )}
          </fieldset>
        </div>
      ),
    },
    {
      id: "billing",
      label: t("tenancy.signup.step.billing"),
      validate: () => stepValid(2, draft, subdomain),
      content: (
        <div className="card">
          <Kicker>{t("tenancy.signup.stepOf", { step: 2, total: 5 })}</Kicker>
          <h2 className="my-1 text-h4">{t("tenancy.signup.billing.title")}</h2>
          <p className="m-0 mb-4 text-base text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">{t("tenancy.signup.billing.hint")}</p>
          <TextField
            id="signup-tax-region"
            label={t("tenancy.signup.billing.taxRegion")}
            value={draft.taxRegion}
            onChange={(value) => patch({ taxRegion: value })}
            help={t("tenancy.signup.billing.taxRegionHelp")}
          />
          <SelectField
            id="signup-currency"
            label={t("tenancy.signup.billing.currency")}
            value={draft.currency}
            onChange={(value) => patch({ currency: value })}
            options={SIGNUP_CURRENCIES.map((code) => ({ value: code, label: code }))}
            required
          />
          {/* BR-TEN-012: seeding runs only when this is on. */}
          <CheckboxField
            id="signup-load-defaults"
            label={t("tenancy.signup.billing.loadDefaults")}
            checked={draft.loadDefaults}
            onChange={(checked) => patch({ loadDefaults: checked })}
          />
        </div>
      ),
    },
    {
      id: "plan",
      label: t("tenancy.signup.step.plan"),
      validate: () => stepValid(3, draft, subdomain),
      content: (
        <div className="card">
          <Kicker>{t("tenancy.signup.stepOf", { step: 3, total: 5 })}</Kicker>
          <h2 className="my-1 text-h4">{t("tenancy.signup.plan.title")}</h2>
          <p className="m-0 mb-4 text-base text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">{t("tenancy.signup.plan.hint")}</p>
          {/* DEF-TEN-4222 (reopened 2026-10-02): NO PRICE on this step. The PO
              took the prices off the home page pending a new pricing model, and
              this step showed the same three one click later. A prospect now
              says only roughly how many accounts they bill; each band carries
              the existing plan code the server needs at commit (sizeBands.ts),
              and nothing here reads or shows what that plan costs. */}
          <div className="mb-4 grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-3" data-signup-sizes>
            {SIZE_BANDS.map((band) => (
              <label key={band.key} className="group relative block cursor-pointer">
                <input
                  className="absolute opacity-0"
                  type="radio"
                  name="signup-plan"
                  value={band.plan}
                  checked={draft.plan === band.plan}
                  onChange={() => patch({ plan: band.plan })}
                />
                <span className="flex h-full flex-col gap-2 border-2 border-divider p-4 group-has-[input:checked]:border-accent group-has-[input:checked]:bg-[color-mix(in_srgb,var(--color-accent)_6%,transparent)] group-has-[input:focus-visible]:outline-2 group-has-[input:focus-visible]:outline-offset-2 group-has-[input:focus-visible]:outline-accent">
                  <span className="font-heading text-lead font-extrabold">{sizeBandRange(t, band, i18n.language)}</span>
                  <span className="text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
                    {t("public.home.sizes.unit")}
                  </span>
                </span>
              </label>
            ))}
          </div>
          {/* BR-TEN-002 · NFR-5: a band guides setup and never caps billing. */}
          <p className="m-0 mb-4 text-base text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">{t("public.home.sizes.noCap")}</p>
        </div>
      ),
    },
    {
      id: "review",
      label: t("tenancy.signup.step.review"),
      content: (
        <div className="card">
          <Kicker>{t("tenancy.signup.stepOf", { step: 4, total: 5 })}</Kicker>
          <h2 className="my-1 text-h4">{t("tenancy.signup.review.title")}</h2>
          <p className="m-0 mb-4 text-base text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">{t("tenancy.signup.review.hint")}</p>
          <ReviewBlock
            title={t("tenancy.signup.step.utility")}
            editLabel={t("tenancy.signup.review.edit")}
            onEdit={() => handleNav(jumpBackTo(nav, 1))}
            rows={[
              { label: t("tenancy.signup.utility.name"), value: draft.name },
              { label: t("tenancy.signup.utility.subdomain"), value: draft.subdomain },
              { label: t("tenancy.signup.utility.state"), value: draft.state },
              {
                label: t("tenancy.signup.utility.services"),
                value: draft.services
                  .map((code) => {
                    const found = SIGNUP_SERVICES.find((service) => service.code === code);
                    return found === undefined ? code : t(found.labelKey);
                  })
                  .join(" · "),
              },
            ]}
          />
          <ReviewBlock
            title={t("tenancy.signup.step.billing")}
            editLabel={t("tenancy.signup.review.edit")}
            onEdit={() => handleNav(jumpBackTo(nav, 2))}
            rows={[
              { label: t("tenancy.signup.billing.currency"), value: draft.currency },
              { label: t("tenancy.signup.billing.taxRegion"), value: draft.taxRegion },
              {
                label: t("tenancy.signup.billing.loadDefaults"),
                value: draft.loadDefaults
                  ? t("tenancy.signup.review.yes")
                  : t("tenancy.signup.review.no"),
              },
            ]}
          />
          <ReviewBlock
            title={t("tenancy.signup.step.plan")}
            editLabel={t("tenancy.signup.review.edit")}
            onEdit={() => handleNav(jumpBackTo(nav, 3))}
            rows={[{ label: t("tenancy.signup.step.plan"), value: sizeLabel(t, draft.plan, i18n.language) }]}
          />
          {/* BR-TEN-014: 14-day trial, no card at signup. */}
          <p className="m-0 mt-4 bg-text p-4 text-base text-bg">{t("tenancy.signup.review.trial")}</p>
        </div>
      ),
    },
    {
      id: "login",
      label: t("tenancy.signup.step.login"),
      validate: () => stepValid(5, draft, subdomain),
      content: (
        <div className="card">
          <Kicker>{t("tenancy.signup.stepOf", { step: 5, total: 5 })}</Kicker>
          <h2 className="my-1 text-h4">{t("tenancy.signup.login.title")}</h2>
          <p className="m-0 mb-4 text-base text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">{t("tenancy.signup.login.hint")}</p>
          <TextField
            id="signup-owner-name"
            label={t("tenancy.signup.login.name")}
            value={draft.ownerName}
            onChange={(value) => patch({ ownerName: value })}
            required
          />
          <TextField
            id="signup-owner-email"
            label={t("tenancy.signup.login.email")}
            value={draft.ownerEmail}
            onChange={(value) => patch({ ownerEmail: value })}
            required
          />
          {/* The kit's PasswordField (BR-SHL-017) — the same control S3 uses.
              The commit signs the owner in, so this is the password for the
              NEXT sign-in (at /{tenant}/signin); the help line says so. */}
          <PasswordField
            id="signup-owner-password"
            label={t("tenancy.signup.login.password")}
            value={draft.ownerPassword}
            onChange={(value) => patch({ ownerPassword: value })}
            required
            autoComplete="new-password"
            help={t("tenancy.signup.login.passwordHelp")}
          />
          <TextField
            id="signup-owner-phone"
            label={t("tenancy.signup.login.phone")}
            value={draft.ownerPhone}
            onChange={(value) => patch({ ownerPhone: value })}
            help={t("tenancy.signup.login.phoneHelp")}
          />
          <CheckboxField
            id="signup-terms"
            label={t("tenancy.signup.login.terms")}
            checked={draft.termsAccepted}
            onChange={(checked) => patch({ termsAccepted: checked })}
          />
        </div>
      ),
    },
  ];

  return (
    <div className="mx-auto max-w-[820px] px-6 py-8" data-signup="page">
      <h1 className="mt-2 mb-8 text-center text-h2">
        {committing ? t("tenancy.signup.provisioning.title") : t("tenancy.signup.title")}
      </h1>
      {/* The frame stays MOUNTED behind the provisioning screen and is hidden,
          never unmounted: it owns the in-flight commit (BR-SHL-019 single
          flight) and its controller is what resolves the promise this screen is
          waiting on. Unmounting it mid-commit would tear down the thing doing
          the work the screen is describing. */}
      <div className="flex flex-col gap-4 [&[hidden]]:hidden" hidden={committing}>
        <WizardFrame
          steps={steps}
          nav={nav}
          onNavChange={handleNav}
          commitLabel={t("tenancy.signup.commit")}
          commitFailedTitle={t("tenancy.signup.failedTitle")}
          onCommit={handleCommit}
          onCommitted={handleCommitted}
        />
      </div>
      {committing && (
        <ProvisioningPanel
          utilityName={draft.name}
          result={provisioned}
          client={client}
          onDone={handleProvisioningDone}
        />
      )}
      <p className="mt-6 text-center text-sm text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]">{t("tenancy.signup.foot")}</p>
    </div>
  );
}

// ── CR-017 · the provisioning screen ───────────────────────────────────────
//
// PO, 2026-08-19, twice and in their own words:
//
//   "after this step at the time of new tenant creation you need new screen
//    showcaing data migration is going on so that User wil know whats going on
//    in the background - add new screen after this"
//
//   "We want to display confirmation to user process is taking place in the
//    background and data seeding is in progress, that you for wating your
//    Utility will be provision soon; that will help business user to udnerstand
//    what we are doing - otherwise they are left hi and dry"
//
// ⚠ IT IS NOT A NEW SCREEN ID, AND THAT IS DELIBERATE. A1 is the ticket
// vocabulary and its canonical range is S1–S114; CLAUDE.md is explicit that a
// screen with no A1 id is "a finding to report, not a licence to mint one". So
// this is S114's POST-COMMIT STATE: no route of its own, no entry in the
// inventory, and OQ-268 asks the PO whether it should be allocated one.
//
// WHAT IT PROMISES AND WHAT IT REFUSES TO PROMISE. Every line it draws comes
// from the server: the reference-list counts are `reference_seed`, and the
// sample-data line is a REAL BE-07 job record polled at `/api/jobs/{id}`, with
// real `progress.done / progress.total`. There is no timer, no fake bar and no
// invented percentage — a wait that finishes early would make a bar lie, and a
// wait that finishes late would make it lie the other way.
//
// THE THREE DEPLOYMENT SHAPES IT HAS TO BE HONEST IN (DEF-320):
//   · JOBS_EAGER on  — the plant ran inside the commit, so the job is already
//     `succeeded` when the response lands; the screen shows the finished work.
//   · JOBS_EAGER off, a runner behind it — `queued` → `running` → `succeeded`,
//     narrated block by block as it goes.
//   · JOBS_EAGER off, NO runner — the record rests `queued` forever, which is
//     the deployed build today. The screen stops waiting after
//     PLANT_POLL_MAX_MS and says the utility is ready and the sample records
//     have not landed yet. That is C-15's soft posture (PO 2026-08-17: "flag on
//     the S62 checklist + alert support, tenant still opens") rendered, rather
//     than a spinner that never stops.

// ── HOW LONG THE SCREEN FOLLOWS THE RUN ───────────────────────────────────
//
// ⚠ **`DEF-3500` — THIS USED TO BE A TOTAL BUDGET AND THE TOTAL WENT STALE.**
// It read `PLANT_POLL_MAX = 120` — three minutes — under a comment that said,
// accurately, *"Sized off the measured plant: 41 s on this stack for the full
// TEN blocks (CR-017 profile, 2026-08-19)"*. The plant walks **eighteen**
// blocks now. Nothing pointed at this number, so `DEF-3340`'s seventeen-to-
// eighteen sweep moved the constants, the locale keys and the tests and never
// came near it, and the Product Owner watched the screen stop:
//
//     "Currently It does not complete all 18 steps on screen - after step 13
//      it does background job and then just jump insight the applciation"
//
// **A TOTAL BUDGET IS THE WRONG QUESTION AND WILL GO STALE AGAIN THE DAY A
// NINETEENTH BLOCK LANDS.** What the screen actually needs to know is whether
// the run is STILL MOVING, so that is what it asks: it keeps following while
// the job's block count keeps rising, and stops only once nothing has moved
// for `PLANT_STALL_MS`. A slower machine, a bigger estate and a longer block
// all extend the wait by themselves; a run that has genuinely died still ends
// in bounded time.
const PLANT_POLL_INTERVAL_MS = 1500;

/** One `pollJob` call — a WINDOW, not the whole wait. `pollJob` rejects when it
 *  spends its polls, and the panel decides whether to open another. */
const PLANT_POLL_WINDOW = 120; // 120 × 1.5 s = 3 minutes per window

/** How long the run may stand still before the screen stops asking. Sized off
 *  the measured plant rather than guessed: the slowest single block on this
 *  stack is the first meter-read walk at 13 s (2026-09-03 profile, 18 blocks in
 *  42 s end to end), so four minutes is roughly eighteen times the worst block
 *  and is a stall rather than a slow patch. It is also the deployment where NO
 *  runner is behind the queue: the record rests `queued`, nothing ever moves,
 *  and the screen says so after four minutes instead of spinning for ever. */
const PLANT_STALL_MS = 4 * 60_000;

/** A hard ceiling on windows, so a server answering `running` for ever without
 *  advancing a single block cannot keep this effect alive indefinitely.
 *
 *  ⚠ IT IS NOT PURELY A BACKSTOP, AND SAYING SO WOULD BE THE COMMENT-THAT-IS-
 *  NOT-THE-GUARANTEE (hard-won law 1). A window that ends because the poll
 *  BUDGET was spent took three minutes, so the stall budget above always wins
 *  first. A window that ends because a REQUEST failed comes back immediately
 *  and waits one interval before retrying — so against a server that is simply
 *  down, this ceiling is what stops us, at roughly a minute rather than at four.
 *  That is the right answer for that case: nothing has moved and nothing is
 *  going to, and the screen says so and stays put. */
const PLANT_POLL_MAX_WINDOWS = 40;

export type PlantPhase = "committing" | "seeding" | "ready" | "waiting" | "partial";

/**
 * ⚠ TWO WORDS ARRIVED WITH CR-064 AND NEITHER IS COSMETIC.
 *
 * `skipped` and `notStarted` used to be spelled `failed` and `queued`, and both
 * conflations are exactly what the Product Owner asked us to stop doing on
 * 2026-09-02: *"if you skip the step, then show the reason for that step
 * also"*, and *"this will help us to understand why it is breaking down"*.
 *
 *   · A block whose seam is not published did not FAIL — nothing broke, a part
 *     of the product is not wired, and it says so in its own sentence
 *     (BR-TEN-060). Calling it "Not loaded" beside a real database error made
 *     the two indistinguishable, which is the whole diagnosis lost.
 *   · A step nothing has recorded is NOT "Waiting" once the run has finished —
 *     it is a step the run never reached, and CR-064 sizes THAT as the real
 *     risk in this change: *"a step list that reports Done because a row is
 *     missing would be worse than the three lines it replaces"*.
 */
export type StepState = "working" | "done" | "queued" | "failed" | "skipped" | "notStarted";

export interface PlantView {
  committed: boolean;
  plant: SamplePlant | null;
  job: JobRecord | null;
  gaveUp: boolean;
}

/**
 * WHICH of the five things the screen is currently saying — the ONE decision
 * this screen makes, lifted out of the component so it can be driven through
 * every state without a browser (this suite renders to static markup, so an
 * effect-driven state is otherwise unreachable).
 *
 * Read it top to bottom: nothing is claimed before the commit answers; a tenant
 * with no plant asked for is READY, not waiting on something that was never
 * started; a plant that ended badly is PARTIAL and never READY; and giving up
 * waiting is its own answer, distinct from both success and failure, because
 * "we stopped asking" is what actually happened.
 */
export function plantPhase(view: PlantView): PlantPhase {
  if (!view.committed) {
    return "committing";
  }
  if (view.plant === null) {
    return "ready"; // the S111 toggle was off: no sample set was ever asked for
  }
  if (view.job !== null && view.job.status === "succeeded") {
    // ⚠ **DEF-2380 — A SUCCEEDED JOB IS NOT A SUCCEEDED RUN, AND READING IT AS
    // ONE WALKED THE OWNER STRAIGHT PAST THE BROKEN STEP.**
    //
    // PO, 2026-09-02, watching a real signup stop at step 8 ("Bills, first
    // month") and then be handed into the app anyway: *"also if it break -
    // dont login , just keep it on same screen"*.
    //
    // The job status is the WORKER's verdict, and the worker is *supposed* to
    // finish: `BR-TEN-063` gives each block its own transaction so one failure
    // cannot roll back the rest, and `C-15` (PO 2026-08-17, *"B soft: flag on
    // the S62 checklist + alert support, tenant still opens"*) says a short
    // block must not stop the tenant opening. Both are right and neither says
    // the SCREEN should hand over. So `succeeded` here means *the walk
    // completed*, not *everything seeded* — and this function was reading the
    // first as the second, which is the only reason `partial` almost never
    // fired: it needed the whole JOB to fail, and the whole job failing is the
    // rare case, not the ordinary one.
    //
    // The per-step outcomes are already served (CR-064). A run that finished
    // with any block not seeded is PARTIAL, which is the phase that already
    // withholds the automatic hand-over and leaves the owner on the screen
    // with the reason on the step's own line. Nothing about the ruling that a
    // tenant still opens changes — the *Go to your utility* button is live on
    // `partial` and is the way off the screen. What changes is that leaving is
    // now the owner's act rather than a timer's.
    return anyStepFellShort(view.job) ? "partial" : "ready";
  }
  if (view.job !== null && view.job.status === "failed") {
    return "partial";
  }
  return view.gaveUp ? "waiting" : "seeding";
}

/**
 * Did any step of a finished run NOT seed?
 *
 * `skipped` counts as well as `failed`, and deliberately: `BR-TEN-060` makes an
 * unwired seam a NAMED line rather than a silence, and to the person watching
 * the screen "this step did not put anything in your utility" is the same fact
 * whichever of the two produced it. The step list still shows them as different
 * words in different colours, because *why* it did not seed is a different
 * question from *whether* it did.
 *
 * A job that served no step rows at all — a server predating CR-064 — answers
 * false, so this cannot invent a failure out of an absence.
 *
 * ⚠ **`not_started` COUNTS TOO, AND LEAVING IT OUT WAS `DEF-3501`.** This
 * function listed the two outcomes a block RECORDS, and `not_started` is
 * SERVED rather than stored — `step_states()` is the catalogue left-joined onto
 * the ledger, so a block the run never reached has no row and is reported as
 * having none. That is the difference between a run that finished and a run
 * that STOPPED, and this function could not see it.
 *
 * It matters because `run_job` marks the record `succeeded` whenever the body
 * returns without raising. A plant that ended early therefore arrived here as
 * `succeeded` with ten `not_started` rows, answered `false`, and the screen
 * called it `ready` — the exact shape CR-064 exists to end, in the PO's own
 * summary of 2026-09-02: *the product said a thing succeeded and the thing had
 * not happened*.
 *
 * Read it as the question the operator is asking: **did every step put
 * something in my utility?** Failed, skipped and never-reached are three
 * different answers to *why not* and one answer to *whether*.
 */
export function anyStepFellShort(job: JobRecord | null): boolean {
  return (job?.steps ?? []).some(
    (row) =>
      row.outcome === "failed" || row.outcome === "skipped" || row.outcome === "not_started",
  );
}

/** The state word on the sample-data row, which is the only row with a life of
 *  its own — the other three land together with the commit (BR-TEN-010). */
export function sampleStepState(phase: PlantPhase, plant: SamplePlant | null): StepState {
  if (phase === "committing") {
    return "queued";
  }
  if (plant === null) {
    return "queued"; // never asked for — the detail line says so in words
  }
  if (phase === "ready") {
    return "done";
  }
  if (phase === "partial") {
    return "failed";
  }
  return phase === "waiting" ? "queued" : "working";
}

/**
 * MAY THE OWNER LEAVE THIS SCREEN YET — the one question both the automatic
 * hand-over and the *Go to your utility* button ask.
 *
 * ⚠ IT IS A FUNCTION BECAUSE THE TWO USED TO ANSWER IT DIFFERENTLY, AND THAT
 * WAS DEF-2370. The effect below has always waited for `ready` or `waiting`;
 * the button three lines under it rendered on `subdomain !== null` and named no
 * phase at all, so it was live and inviting while the list underneath read
 * *"Sample data so you can see it working — WORKING — Block 2 of 14"*. PO,
 * 2026-08-28, on a fresh database: *"dont enable go to utility until all jobs
 * are completed"*. Two call sites reading one predicate cannot drift again.
 *
 * ⚠ THE TWO ARE NOT THE SAME SET, AND THE DIFFERENCE IS DELIBERATE. The effect
 * fires on `ready` and `waiting` only. This also admits **`partial`**, which
 * never hands over on its own precisely because something did not land and the
 * owner has to see WHICH block before they leave — so on that phase the button
 * is the only way off the screen and disabling it would strand them. Written as
 * the negative for exactly that reason: the phases that BLOCK a hand-over are
 * the two where work is still in flight, and every other phase is a finished
 * answer of some kind, `partial` included.
 */
export function handoverReady(phase: PlantPhase): boolean {
  return phase !== "committing" && phase !== "seeding";
}

// ── CR-064 · THE TWENTY-EIGHT (PO 2026-09-02) ─────────────────────────────
//
//   "During tenent creation - when we are at the screen where we seed data in
//    backround job, can you show all 17 step - -list down all 17 steps and
//    show 1 by 1 when they finish - if step breaks - then show the reason
//    behind it at that step itself , if you skip the step, then show the
//    reason for that step also - this will help us to understand why it is
//    breaking down in real time, you ahve to provide specific error on the
//    screen itself"
//
// ⚠ **THIS IS A SECOND, HAND-WRITTEN COPY OF A BACKEND LIST, AND THAT IS THE
// EXACT SHAPE THAT PUT SIX SERVICES ON THIS SCREEN FOR TEN DAYS.** It is here
// anyway, for one reason the alternative cannot meet: *"list down all 17
// steps"* means BEFORE the first poll answers, and during the commit there is
// no server answer of any kind. So the list is typed once, in creation order,
// and `provisioningSteps.test.ts` PARSES `SAMPLE_MODULES` OUT OF
// `06-backend/apps/tenancy/sample_data.py` and asserts this constant is that
// tuple, in that order — the same instrument `signupServices.test.ts` is, and
// for the same reason. A derived list would only ever agree with itself.
//
// ⚠ AND THE SERVER'S OWN CATALOGUE STILL WINS WHEN IT ARRIVES. `stepCatalogue`
// below prefers `sample_plant.steps` and falls back to this, so an EIGHTEENTH
// step is on screen the moment the backend has one, with the server's English
// label, rather than silently absent until somebody edits this file.
export const PROVISIONING_STEPS: readonly string[] = [
  "identity:seed_sample_records",
  "rating:seed_sample_records",
  "metering:seed_sample_records",
  "assets:seed_sample_records",
  // ── DEF-TEN-4509 · THE TWENTIETH AND TWENTY-FIRST, BOTH APPENDED IN PYTHON
  // AND NOT HERE — AND THE CHECK THAT SAYS SO HAD BEEN RED SINCE 2026-09-06 ──
  // `assets:seed_sample_aged_meters` (position 6) and `work:seed_sample_records`
  // (position 20) landed with CR-070 wave M. `provisioningSteps.test.ts` went
  // red on both the moment they landed, exactly as its own comment says it
  // does, and stayed red — CLAUDE.md law 7's *proved red, then never read*: the
  // guard was working and its output was not. That is the FOURTH time a block
  // has been added in Python and not here (DEF-3320, DEF-PAY-3631, these two),
  // so the same assertion now also lives in the suite lanes DO run —
  // `tests/test_cr064_seventeen_steps.py`.
  "assets:seed_sample_aged_meters",
  "customers:seed_sample_records",
  // ── DEF-MET-6302 · THE OWNERS' ACCOUNTS (PO 2026-09-23) ──────────────────
  // *"attach master accounts to the sample data"*. Straight after the accounts
  // block, because these accounts are opened through the same door and four of
  // them ahead of the estate's fifty would renumber all fifty. Added HERE in
  // the same commit as the Python row — the FIFTH time is what this file's own
  // comment three lines up exists to stop.
  "customers:seed_sample_owner_accounts",
  // ── DEF-3320 · THE EIGHTEENTH, AND IT ARRIVED IN THE MIDDLE ──────────────
  // CR-062 addendum J2 (PO 2026-09-02: *"What is the government discount
  // called? Municipal account - yes; What rate? 20% off the bill before taxes
  // - yes"*) inserted `rating:seed_sample_enrolments` at POSITION 6 — after
  // customers, because an enrolment needs an account to grant to.
  //
  // ⚠ **IT WAS APPENDED IN PYTHON AND NOT HERE FOR A DAY, AND EVERY BACKEND
  // TEST STAYED GREEN** — they all assert against `len(SAMPLE_MODULES)`, which
  // is the right way to write them and is exactly why none of them could see
  // it. The one thing that DID go red is the guard below this constant's own
  // comment describes: `provisioningSteps.test.ts` parses `SAMPLE_MODULES` out
  // of the Django module and compares. That is the check earning its keep.
  "rating:seed_sample_enrolments",
  "metering:seed_sample_reads",
  // ── THE PRODUCT OWNER'S OWN ORDER, 2026-09-07 (`CR-083`) ─────────────────
  // *"before step 29 this - you ahve to set all the self service data in
  // settings -> configure -> Customer portal - {overview, branding, Help &
  // Answer, Tips  + service centers }"*, where step 29 is the login. The
  // configuration comes first because a customer who signs in to an
  // unconfigured portal sees branding that is not there, no answers, no tips
  // and no counter to walk into.
  //
  // ⚠ **IT RUNS HERE, TENTH, SINCE 2026-09-23 (`DEF-PAY-6321`, `f27c46d27`),
  // AND THIS LIST CAUGHT UP ON 2026-10-02 (`DEF-TEN-9127`).** The money blocks
  // below bank counter payments THROUGH a service centre, and the centres are
  // this block's, so `SAMPLE_MODULES` moved it ahead of them. It is still
  // before the login, which is all the ruling asks. For nine days this list
  // kept it at 26th, and because the Working marker is the step at index
  // `progress.done`, while steps 10–25 ran the screen marked the NEXT one.
  "tenancy:seed_sample_portal_content",
  "billing:seed_sample_records",
  "payments:seed_sample_records",
  "payments:seed_sample_refund",
  // ── DEF-PAY-3631 · THE NINETEENTH, AND THE POSITION IS THE FEATURE ───────
  // The cheque settles the landlord's three June bills, which
  // `payments:seed_sample_records` above deliberately leaves open, so it runs
  // AFTER that block and BEFORE the second billing cycle — a multi-property
  // cheque dated 8 August that arrived after July had billed would be paying
  // bills the demo's own timeline says were already settled.
  //
  // ⚠ **IT WAS APPENDED IN PYTHON AND NOT HERE, EXACTLY AS THE EIGHTEENTH
  // WAS**, and every backend test stayed green for the same reason: they all
  // assert against `len(SAMPLE_MODULES)`. What caught it is what the comment
  // above says catches it — `provisioningSteps.test.ts` parses `SAMPLE_MODULES`
  // out of the Django module and compares — and it had been red at the tip
  // since the block landed, because CI has no runner to run it.
  "payments:seed_sample_multi_account_tender",
  "billing:seed_sample_correction",
  "metering:seed_sample_second_cycle_reads",
  "billing:seed_sample_second_cycle",
  "metering:seed_sample_next_cycle_reads",
  "payments:seed_sample_cycle_collections",
  // ── DEF-CUS-4628 · THE ONE TENANCY THAT ENDS, AND THE POSITION IS THE
  // FEATURE ────────────────────────────────────────────────────────────────
  // Until 2026-09-07 no seeded tenant held a single account in the terminal
  // state, so `Closed` was a status a clerk could pick from a list and never
  // see. It runs AFTER the collections above because a closed account leaves
  // the bill run's population entirely: put it any earlier and that account is
  // billed neither month.
  "customers:seed_sample_move_out",
  "customers:seed_sample_payment_plans",
  "payments:seed_sample_plan_payments",
  // ── DEF-TEN-4522 · THE TWENTY-SECOND AND TWENTY-THIRD, AND THIS IS THE
  // FIFTH TIME A BLOCK HAS BEEN ADDED IN PYTHON AND NOT HERE ───────────────
  // `work:seed_sample_workforce` and `work:seed_sample_field_work` landed with
  // CR-070 on 2026-09-07 — thirty-nine work orders and nobody to send — and
  // `provisioningSteps.test.ts` went red at the tip the moment they did,
  // exactly as its own comment says it does. They are added here by the next
  // lane through, which is precisely the pattern DEF-TEN-4509 records: the
  // guard works, and reading its output is the part that stops.
  "work:seed_sample_workforce",
  "work:seed_sample_field_work",
  "work:seed_sample_records",
  "customers:seed_sample_wizard_parks",
  // The portal's CONTENT used to sit here, immediately before the login, and
  // moved to straight after the reads on 2026-10-02 — see the note there.
  "tenancy:seed_sample_portal_login",
  // ── "STEP 30, INTEGRATIONS" — PO 2026-09-07 (`CR-083`) ───────────────────
  // Verbatim: *"Im okay with this - please add- Step 30, Integrations"*, where
  // step 29 is the portal login above. LAST, because the block records one
  // accounting handover and a handover needs a month that is closed with books
  // that foot — which is only true once every money block has run.
  "integrations:seed_sample_records",
];

/** The locale key for a step's clerk-facing label.
 *
 *  B14 rule 32 is why this exists at all rather than the screen printing the
 *  server's `label`: those strings carry `spec §4 case 14` and `S17.2` — a
 *  fixture reference and a screen id — and *"no rule id or internal code in
 *  clerk-facing copy"* is binding. The server label survives as the fallback
 *  for a step this catalogue does not know yet, which is a real trade: an
 *  unpolished English line on screen beats a missing row. */
export function stepLabelKey(key: string): string {
  const [module, block] = key.split(":");
  return `tenancy.signup.provisioning.block.${module}.${block}`;
}

/** One row of the twenty-eight, ready to draw. */
export interface ProvisioningStepRow {
  key: string;
  position: number;
  /** The server's English label — the FALLBACK when the catalogue has no key. */
  fallbackLabel: string;
  state: StepState;
  /** The server's own sentence for this step, verbatim. Null when there is none. */
  reason: string | null;
  /**
   * OUR sentence for a step the SERVER said nothing about — a locale key, not a
   * sentence, because this one is ours to translate.
   *
   * ⚠ **IT IS A SECOND FIELD AND NOT A DEFAULT FOR `reason`, DELIBERATELY.**
   * `reason` is a promise: it is the server's own bytes, rendered verbatim and
   * untranslated because it names the exact seam function or the exact database
   * error (CR-064 task B3, the `SettingsSampleData` precedent). Folding a
   * message of ours into that field would quietly make the promise false, and
   * the next lane reading `reason` would have no way to tell which kind of
   * sentence it was holding.
   *
   * `DEF-3500` is why it exists at all. The PO asked for a reason on every step
   * that did not seed — *"if you skip the step, then show the reason for that
   * step also"* — and a step the run never REACHED is the third case that
   * sentence covers and the only one that carried no words at all.
   */
  reasonKey: string | null;
}

/** What a step says when nothing recorded it and the run is over. */
const STEP_NOT_REACHED_KEY = "tenancy.signup.provisioning.steps.notReached";

/**
 * WHICH TWENTY-EIGHT, and in which order — the server's list when it has sent one.
 *
 * The commit response carries the catalogue (`sample_plant.steps`) and the
 * poll carries the same keys with outcomes, so the two join on `key` and the
 * screen never holds a second copy of the order.
 */
export function stepCatalogue(plant: SamplePlant | null, job: JobRecord | null): SampleStep[] {
  // ⚠ THE CATALOGUE IS NEVER TAKEN FROM THE POLL BODY, AND THE FIRST DRAFT OF
  // THIS FUNCTION TOOK IT FROM THERE. `sample_plant.steps` is a CATALOGUE — all
  // of them, sent once, before the run — and `job.steps` is a REPORT about
  // them. Reading the report as the catalogue means a body carrying two rows
  // draws a list of two, and a list that STOPS cannot be told apart from a list
  // that FINISHED, which is the one thing CR-064 exists to end.
  //
  // Caught by `CR-064 A4` before this shipped:
  //     AssertionError: expected [ … ] to have a length of 17 but got +2
  const base: SampleStep[] =
    plant?.steps !== undefined && plant.steps.length > 0
      ? plant.steps
      : PROVISIONING_STEPS.map((key, index) => ({
          position: index + 1,
          key,
          module: key.split(":")[0],
          block: key.split(":")[1],
          label: key,
          tables: [],
        }));
  // …and anything the RUN knows about that the catalogue does not is appended
  // rather than dropped. That is hard-won law 2 read forwards: an eighteenth
  // block added in Python is on this screen the day it lands, with the server's
  // own label, instead of silently missing until somebody edits the constant.
  const known = new Set(base.map((entry) => entry.key));
  const extra = (job?.steps ?? []).filter((entry) => !known.has(entry.key));
  return extra.length === 0
    ? base
    : [...base, ...extra.map((entry, index) => ({ ...entry, position: base.length + index + 1 }))];
}

/**
 * THE ONE DECISION THE STEP LIST MAKES, lifted out of the component so every
 * state can be driven without a browser (this suite renders to static markup).
 *
 * Read it top to bottom, because the ORDER is the honesty:
 *
 *   1. **What the server recorded wins, always.** A step with a row reports
 *      that row's outcome and that row's sentence, and nothing here overrides
 *      it — the screen reports what the run said, never what it expects.
 *   2. **A step with no row is never Done.** This is CR-064's own stated risk
 *      and the reason task A4 was tested before this function was written: a
 *      list that says Done because a row is missing is worse than the single
 *      line it replaces, because it is confidently wrong.
 *   3. **Exactly one step is Working**, and it is the one after the last the
 *      job counted — `progress.done` is blocks FINISHED, so the block in
 *      flight is `done + 1`. No timer, no guess, no invented percentage.
 *   4. **Before the commit answers, every step is Waiting** — not "not
 *      started", which would claim we know the run has not begun. We have not
 *      been told yet, and CR-017's own `sampleSkipped` comment records what
 *      happens when a null with two meanings is read as one of them.
 */
export function provisioningStepStates(
  phase: PlantPhase,
  plant: SamplePlant | null,
  job: JobRecord | null,
): ProvisioningStepRow[] {
  const catalogue = stepCatalogue(plant, job);
  const served = new Map((job?.steps ?? []).map((row) => [row.key, row]));
  const done = job?.progress?.done ?? 0;
  return catalogue.map((entry, index) => {
    const row = served.get(entry.key);
    const base = {
      key: entry.key,
      position: entry.position ?? index + 1,
      fallbackLabel: entry.label,
    };
    if (row !== undefined && row.outcome !== "not_started") {
      const state: StepState =
        row.outcome === "seeded" ? "done" : row.outcome === "skipped" ? "skipped" : "failed";
      return {
        ...base,
        state,
        // A SEEDED step's sentence is a fact about the estate, not a problem,
        // and it goes on the `detail` line; only a step that did NOT seed puts
        // its sentence on the reason line, which is what the PO asked to see.
        reason: state === "done" ? null : (row.detail ?? null),
        reasonKey: null,
      };
    }
    if (phase === "committing") {
      return { ...base, state: "queued" as StepState, reason: null, reasonKey: null };
    }
    if (plant === null) {
      // The commit answered and no plant was asked for (the S111 toggle was
      // off). Nothing is pending, so nothing is "Waiting" — and nothing went
      // wrong either, so this one carries no reason: the summary row above
      // already says "Not requested at signup" for the whole list.
      return { ...base, state: "notStarted" as StepState, reason: null, reasonKey: null };
    }
    if (phase === "seeding") {
      return {
        ...base,
        state: (index === done ? "working" : "queued") as StepState,
        reason: null,
        reasonKey: null,
      };
    }
    // ready · partial · waiting, with no row for this step. NEVER "Done".
    //
    // ⚠ AND NEVER SILENT EITHER (`DEF-3500`). The run has stopped and this step
    // has nothing recorded against it, which is a FACT about the run and not an
    // absence of one — so it says so on its own line, in the operator's
    // language, exactly as a skipped or a broken step does.
    return {
      ...base,
      state: "notStarted" as StepState,
      reason: null,
      reasonKey: STEP_NOT_REACHED_KEY,
    };
  });
}

/**
 * The id of the line that says WHY the hand-over is refused.
 *
 * BR-SHL-025 makes the REASON part of a disabled control, and B14 rule 32 puts
 * a fact — including the reason a control is disabled — on a declared line of
 * its own rather than inside the control row. The screen already renders that
 * line for this exact wait, and it renders on exactly the phases that refuse
 * the hand-over, so the button points AT it instead of a second sentence that
 * could drift away from the first.
 */
const HANDOVER_REASON_ID = "signup-provisioning-reassure";

export interface ProvisioningPanelProps {
  utilityName: string;
  /** null while `POST /tenants` is still in flight. */
  result: ProvisionResult | null;
  client: ApiClient;
  onDone: (subdomain: string) => void;
}

export function ProvisioningPanel(props: ProvisioningPanelProps) {
  const { t } = useTranslation();
  const { result, client, onDone } = props;
  const [job, setJob] = useState<JobRecord | null>(null);
  const [gaveUp, setGaveUp] = useState(false);
  // CR-064 task B4 — the poll's own failure was thrown away, and it is the one
  // case the twenty-eight steps CANNOT explain: if we could not ask, no step knows
  // anything. `diagnosticOf` turns it into the short line a person reads aloud
  // to support (`HTTP 502 · ref 5F2B-9C1D`), which is the 2026-08-10 ruling.
  const [pollError, setPollError] = useState<unknown>(null);

  const plant = result?.sample_plant ?? null;

  // ── the poll ─────────────────────────────────────────────────────────────
  // Through the client's ONE job helper, never a hand-rolled interval. It
  // returns immediately when the record is already terminal, which is the eager
  // case, so this costs one request there and is not special-cased.
  //
  // ⚠ **`DEF-3500` — ONE `pollJob` CALL IS A WINDOW, NOT THE WHOLE WAIT.**
  // `pollJob` REJECTS on two quite different events and this effect used to
  // treat both as the end of the story:
  //
  //   · it spent its poll budget — three minutes, sized for a plant of TEN
  //     blocks in August and never moved when the plant became EIGHTEEN;
  //   · a single request could not be completed — one 502 from the API
  //     pass-through, and the narration ended at whatever step it had reached,
  //     which is why the step it stopped on looked arbitrary.
  //
  // Neither of those is *"the run is over"*. So the window is reopened while
  // the run is still MOVING, and only a run that has stood still for
  // `PLANT_STALL_MS` ends the wait. `lastMovedAt` is the whole state that
  // decision needs, and it lives in this effect's own closure rather than in
  // React state on purpose: putting it in state would re-render the screen on
  // every poll and — because the effect's deps would then have to carry it —
  // restart the very poll it is measuring.
  useEffect(() => {
    if (plant === null) {
      return;
    }
    let live = true;
    let windows = 0;
    let bestDone = -1;
    let lastMovedAt = Date.now();
    let resumeTimer: ReturnType<typeof setTimeout> | null = null;
    const abort = new AbortController();

    const observe = (record: JobRecord) => {
      if (!live) {
        return;
      }
      const done = record.progress?.done ?? 0;
      if (done > bestDone) {
        bestDone = done;
        lastMovedAt = Date.now();
      }
      setJob(record);
    };

    const follow = () => {
      if (!live) {
        return;
      }
      windows += 1;
      void client
        .pollJob(plant.job_id, {
          intervalMs: PLANT_POLL_INTERVAL_MS,
          maxPolls: PLANT_POLL_WINDOW,
          signal: abort.signal,
          onProgress: observe,
        })
        .then(observe)
        .catch((error: unknown) => {
          if (!live) {
            return;
          }
          const stalled = Date.now() - lastMovedAt >= PLANT_STALL_MS;
          if (!stalled && windows < PLANT_POLL_MAX_WINDOWS) {
            // Still moving, so ask again. The wait is deliberate: a window that
            // ended because ONE request failed comes back instantly, and a
            // resume with no pause would be a hot loop against a server that is
            // already having a bad time.
            resumeTimer = setTimeout(follow, PLANT_POLL_INTERVAL_MS);
            return;
          }
          // Giving up is a STATE, not an error to show. The tenant exists and is
          // signed in; what we cannot say is whether the sample records landed,
          // and the screen says exactly that. (This is also the path a REPLAY
          // takes: BR-TEN-010 mints no session on a replay, so the poll is
          // unauthenticated and 404s — the tenant is still perfectly real.)
          //
          // ⚠ THE STATE IS STILL THE ANSWER; THE ERROR IS THE DIAGNOSIS BESIDE
          // IT (CR-064 task B4). Until 2026-09-02 this catch discarded its
          // argument, so a 502 from the API pass-through and a three-minute
          // timeout produced byte-identical screens — the 2026-08-10 report
          // exactly: *"unable to see what is the error on screen"*.
          //
          // ⚠ AND IT NO LONGER NAVIGATES. Until 2026-09-03 this state was one
          // of the two the automatic hand-over fired on, so *"we stopped
          // asking"* was rendered as *"we are done"* and the operator was taken
          // into the application four seconds later. See the hand-over comment
          // below, which is now about why there is no timer at all.
          setGaveUp(true);
          setPollError(error);
        });
    };

    follow();
    return () => {
      live = false;
      if (resumeTimer !== null) {
        clearTimeout(resumeTimer);
      }
      abort.abort();
    };
  }, [plant, client]);

  const phase = plantPhase({ committed: result !== null, plant, job, gaveUp });

  // ── the handover ─────────────────────────────────────────────────────────
  //
  // ⚠ **THERE IS NO AUTOMATIC HAND-OVER ANY MORE, AND ITS ABSENCE IS THE
  // FIX (`DEF-3500`, PO ruling 2026-09-03).** Verbatim:
  //
  //     "Currently It does not complete all 18 steps on screen - after step 13
  //      it does background job and then just jump insight the applciation, I
  //      want to complete all 18 steps on this screen itself; and see all jobs
  //      are completed"
  //
  // What stood here was a four-second timer that fired on `ready` **and on
  // `waiting`** — and `waiting` is the state the screen reaches when it stops
  // being able to follow the run. So the one case where the operator most needs
  // to stay and read is the case that took them away, and it did it while
  // saying *"The sample records are still being prepared in the background"*.
  //
  // ⚠ **IT SUPERSEDES THE SURVIVING HALF OF CR-017 CLAUSE (c), AND THE
  // SUPERSESSION IS STATED RATHER THAN ASSUMED** (change process step 2). That
  // clause read *"the handover is automatic after 4 s on success … and the *Go
  // to your utility* button is live from the first frame"*. `DEF-2370`
  // (2026-08-28) already superseded the button half on the PO's *"dont enable
  // go to utility until all jobs are completed"*, and recorded that the other
  // half stood: *"the automatic hand-over is still 4 s on `ready`/`waiting`"*.
  // **That is the half this ruling reverses.** `handoverReady` is UNTOUCHED —
  // the 2026-08-28 ruling still decides when the button lights up — so the
  // button remains the way off the screen on `ready`, `waiting` and `partial`,
  // and leaving is now the operator's act on every one of them rather than a
  // timer's on two of them.
  //
  // The cost is one click, and it is the click the PO asked for.
  const subdomain = result?.subdomain ?? null;

  const seeded = result?.reference_seed.seeded ?? {};
  const listCount = Object.keys(seeded).length;
  const rowCount = Object.values(seeded).reduce((sum, count) => sum + count, 0);
  const committed = result !== null;
  const blocksDone = job?.progress?.done ?? 0;
  const blocksTotal = job?.progress?.total ?? plant?.total ?? 0;

  const sampleState = sampleStepState(phase, plant);
  // CR-064 — the seventeen, joined from the catalogue and the poll. Derived on
  // every render from props and state only, so the list can never disagree
  // with the summary row above it: both read the same job record.
  const stepRows = provisioningStepStates(phase, plant, job);
  const pollDiagnostic = pollError === null ? null : diagnosticOf(pollError);

  return (
    <section
      className="card border-t-4 border-t-accent"
      data-signup="provisioning"
      aria-live="polite" aria-busy={phase !== "ready"}>
      <Kicker>{t("tenancy.signup.provisioning.kicker")}</Kicker>
      <h2 className="my-1 text-h4">
        {phase === "ready" || phase === "partial"
          ? t("tenancy.signup.provisioning.ready.title", { name: props.utilityName })
          : t("tenancy.signup.provisioning.building", { name: props.utilityName })}
      </h2>
      <p className="m-0 mb-4 text-base text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
        {phase === "committing" || phase === "seeding"
          ? t("tenancy.signup.provisioning.lead")
          : phase === "partial"
            ? t("tenancy.signup.provisioning.partial.lead")
            : phase === "waiting"
              ? t("tenancy.signup.provisioning.waiting.lead")
              : t("tenancy.signup.provisioning.ready.lead")}
      </p>

      <ol className="mx-0 my-4 grid list-none gap-2 p-0">
        <ProvisioningStep
          state={committed ? "done" : "working"}
          label={t("tenancy.signup.provisioning.step.tenant")}
          detail={committed ? t("tenancy.signup.provisioning.step.tenantDone") : null}
        />
        {/* The reference lists, the chart of accounts, the number series, the
            holiday calendar and both template catalogues are ONE transaction
            (BR-TEN-010) — they land together or not at all — so they tick
            together. Two rows rather than one because they are two different
            things to the person reading, and the counts come from the server's
            own `reference_seed`, never from a number typed here. */}
        <ProvisioningStep
          state={committed ? "done" : "working"}
          label={t("tenancy.signup.provisioning.step.reference")}
          detail={
            committed
              ? t("tenancy.signup.provisioning.step.referenceDone", {
                  lists: listCount,
                  rows: rowCount,
                })
              : null
          }
        />
        <ProvisioningStep
          state={committed ? "done" : "working"}
          label={t("tenancy.signup.provisioning.step.foundations")}
          detail={committed ? t("tenancy.signup.provisioning.step.foundationsDone") : null}
        />
        <ProvisioningStep
          state={sampleState}
          label={t("tenancy.signup.provisioning.step.sample")}
          detail={
            sampleState === "done"
              ? t("tenancy.signup.provisioning.step.sampleDone", { total: blocksTotal })
              : sampleState === "working" && blocksTotal > 0
                ? t("tenancy.signup.provisioning.step.sampleProgress", {
                    done: blocksDone,
                    total: blocksTotal,
                  })
                : sampleState === "failed"
                  ? t("tenancy.signup.provisioning.step.sampleFailed")
                  : // ⚠ "Not requested at signup" is only true once the commit
                    // has ANSWERED with no plant. Before that, `plant` is null
                    // because we have not been told yet — and the first
                    // walkthrough of this screen showed exactly that sentence
                    // for the whole wait, about a sample set that WAS requested
                    // and was being built at that moment. A null with two
                    // meanings has to be split on the phase, not on the value.
                    phase !== "committing" && plant === null
                    ? t("tenancy.signup.provisioning.step.sampleSkipped")
                    : t("tenancy.signup.provisioning.step.samplePending")
          }
        />
      </ol>

      {/* ── CR-064 · THE TWENTY-EIGHT, NAMED AND NUMBERED (PO 2026-09-02) ─
          *"list down all 17 steps and show 1 by 1 when they finish"*.

          ⚠ EVERY ONE OF THEM IS ON SCREEN FROM THE FIRST FRAME, INCLUDING
          BEFORE THE COMMIT ANSWERS. That is the request read literally: a
          count that grows is not a list, and the four rows above already told
          the operator a number. What they could never tell them is WHICH step
          the run is on and WHY it stopped there.

          B14 rule 32 — one sentence for this section, on the summary row
          above; the step rows carry a label and, when the server recorded one,
          that step's own reason. Nothing here prints a rule id, a screen id or
          an error code to the operator. */}
      <section data-signup="provisioning-steps">
        <h3 className="m-0 mb-1 text-md font-semibold">
          {t("tenancy.signup.provisioning.steps.title")}
        </h3>
        <p className="m-0 mb-2 max-w-measure text-sm text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">
          {t("tenancy.signup.provisioning.steps.lead", { total: stepRows.length })}
        </p>
        <ol className="mx-0 my-0 grid list-none gap-0 p-0">
          {stepRows.map((row) => (
            <ProvisioningStep
              key={row.key}
              stepKey={row.key}
              position={row.position}
              state={row.state}
              label={t(stepLabelKey(row.key), { defaultValue: row.fallbackLabel })}
              detail={null}
              reason={row.reason}
              reasonKey={row.reasonKey}
            />
          ))}
        </ol>
        {/* ⚠ THE ONE THING THE SEVENTEEN CANNOT EXPLAIN: we could not ASK.
            When the poll itself fails, no step knows anything, so the reason
            belongs to the list rather than to any row in it. `diagnosticOf` is
            codes and identifiers only — HTTP status, the envelope's code, and
            the SHORTENED trace reference a person can read aloud (DEF-328) —
            never a raw 32-hex id and never a `BR-` id (DEF-332, B14 rule 31). */}
        {pollDiagnostic !== null && (
          <p
            className="m-0 mt-2 max-w-measure text-sm text-danger-700"
            role="note"
            data-testid="signup-provisioning-diagnostic"
          >
            {t("tenancy.signup.provisioning.steps.unreadable")} {pollDiagnostic}
          </p>
        )}
        {/* The job's OWN sentence when the whole run failed, verbatim — the
            same posture as a step's reason, one level up. */}
        {job?.error !== null && job?.error !== undefined && job.error !== "" && (
          <p
            className="m-0 mt-2 max-w-measure text-sm text-danger-700"
            role="note"
            data-testid="signup-provisioning-job-error"
          >
            {job.error}
          </p>
        )}
      </section>

      {/* The reassurance is for the WAIT. Once the work is finished the lead
          line above already says what happens next, and repeating "we will take
          you there as soon as everything is in place" under a list of ticks
          reads as though something were still pending. */}
      {!handoverReady(phase) && (
        <p
          id={HANDOVER_REASON_ID}
          className="m-0 mb-4 bg-success-100 p-3 text-base text-success-700"
        >
          {t("tenancy.signup.provisioning.reassure")}
        </p>
      )}

      {/* BR-SHL-025: a control the owner may not use yet is DISABLED WITH ITS
          REASON, never hidden. Rendering it and then taking it away when the
          job finishes would be a control that vanishes and reappears, which is
          worse than one that is visibly not ready — so the button holds its
          place from the first frame and only its state changes. The kit already
          draws the disabled tier (`disabled:opacity-45 disabled:cursor-not-
          allowed` in `buttonKit`'s STRUCTURE), so nothing here styles it. */}
      {subdomain !== null && (
        <Button
          variant="primary"
          disabled={!handoverReady(phase)}
          aria-describedby={handoverReady(phase) ? undefined : HANDOVER_REASON_ID}
          onClick={() => onDone(subdomain)}
          data-testid="signup-provisioning-continue"
        >
          {t("tenancy.signup.provisioning.continue")}
        </Button>
      )}
    </section>
  );
}

/* The dot and the state word are the only two things a step's state changes, and
 * `SignupWizard.css` said so with six `.signup-provisioning-step.is-X .Y`
 * descendant rules. Each value here is ONE WHOLE STRING per state: Tailwind's
 * scanner reads source text, so `bg-${state}` would compile to nothing and
 * `routeBUtilities.test.ts` refuses an interpolated class in a migrated file by
 * name. `queued` is the base grey and the base (inherited) ink, which is why the
 * stylesheet had no rule for it and why its state entry here is empty. */
const MARK_TONE: Record<StepState, string> = {
  queued: "bg-neutral-400",
  // CR-064: a step the run has not reached is a HOLLOW mark, so twenty-eight
  // untouched rows do not read as twenty-eight waiting ones at a glance.
  notStarted: "border border-neutral-400 bg-transparent",
  working: "bg-accent animate-provisioning-pulse motion-reduce:animate-none",
  done: "bg-success-500",
  // An unwired seam is not a failure and is not coloured like one — warning,
  // not danger. Nothing broke; a part of the product is not there yet.
  skipped: "bg-warning-500",
  failed: "bg-danger-500",
};

const STATE_TONE: Record<StepState, string> = {
  queued: "",
  notStarted: "",
  working: "text-accent-700",
  done: "text-success-700",
  skipped: "text-warning-700",
  failed: "text-danger-700",
};

function ProvisioningStep(props: {
  state: StepState;
  label: string;
  detail: string | null;
  /** CR-064: the step's number in the twenty-eight. Absent on the commit rows,
   *  which are not a numbered sequence and never were. It is a POSITION IN A
   *  LIST, not a database id — B14 rule 31 is why the row's identity travels
   *  in `data-step` and never as a visible value. */
  position?: number;
  /** CR-064 task B3 — the SERVER's own sentence for this step, rendered
   *  verbatim and untranslated. See the block comment on `ProvisioningSteps`. */
  reason?: string | null;
  /** `DEF-3500` — OUR sentence for a step the server said nothing about, as a
   *  locale key. It goes on the same line as `reason` and never beside it: a
   *  step has one reason, and which of the two produced it is our problem and
   *  not the operator's. */
  reasonKey?: string | null;
  /** The step key, for a test and for support reading the DOM. Never shown. */
  stepKey?: string;
}) {
  const { t } = useTranslation();
  // The server's own bytes win whenever there are any; ours is the fallback for
  // a step it never recorded.
  const reasonText =
    props.reason !== null && props.reason !== undefined && props.reason !== ""
      ? props.reason
      : props.reasonKey !== null && props.reasonKey !== undefined
        ? t(props.reasonKey)
        : null;
  return (
    <li
      className="grid grid-cols-[12px_1fr_auto] items-baseline gap-2 border-b border-b-divider py-2 text-md"
      data-step={props.stepKey}
      data-state={props.state}
    >
      <span className={`size-2.5 self-center rounded-[50%] ${MARK_TONE[props.state]}`} aria-hidden="true" />
      <span className="font-semibold">
        {props.position === undefined ? props.label : `${props.position}. ${props.label}`}
      </span>
      {/* The state word is ALWAYS rendered, and the detail rides beside it —
          never instead of it. "20 lists · 187 rows" says what landed and not
          whether it landed, and a coloured dot is not a word a screen reader
          can read out. */}
      <span className={`text-sm uppercase tracking-label ${STATE_TONE[props.state]}`}>
        {t(`tenancy.signup.provisioning.state.${props.state}`)}
      </span>
      {props.detail !== null && props.detail !== undefined && (
        <span className="col-[2/-1] text-sm text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]">
          {props.detail}
        </span>
      )}
      {/* ⚠ THE REASON THIS WHOLE CHANGE EXISTS, AND IT IS ON THE STEP'S OWN
          LINE. PO, 2026-09-02: *"if step breaks - then show the reason behind
          it at that step itself , if you skip the step, then show the reason
          for that step also … you ahve to provide specific error on the screen
          itself"*. A link to Settings does not satisfy that sentence and
          neither does a summary.

          RENDERED VERBATIM AND UNTRANSLATED, which is a deliberate divergence
          from the all-strings-translated posture and is the SAME one
          `SettingsSampleData` already records for the same sentences: it names
          the exact seam function or the exact database error, and a translated
          paraphrase would drift from the thing it names. Every LABEL around it
          goes through the catalogues. */}
      {reasonText !== null && (
        <span
          // A step nobody reached is not a failure and is not coloured like
          // one — the same argument `MARK_TONE` already makes for `skipped`.
          // Nothing broke; the run did not get this far.
          className={`col-[2/-1] max-w-measure text-sm ${
            props.state === "notStarted"
              ? "text-[color-mix(in_srgb,var(--color-text)_60%,transparent)]"
              : "text-danger-700"
          }`}
          role="note"
          data-step-reason={props.stepKey}
        >
          {reasonText}
        </span>
      )}
    </li>
  );
}

// ── Small presentational pieces (this screen's, not registry components) ───

function SubdomainAvailability(props: { state: SubdomainState; appHost: string }) {
  const { t } = useTranslation();
  if (props.state.checking) {
    return <p className="m-0 -mt-1 mb-4 text-xs text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]">{t("tenancy.signup.utility.checking")}</p>;
  }
  const result = props.state.result;
  if (result === null) {
    return null;
  }
  if (result.available) {
    // The address named here is built by the SAME helper the router uses, so
    // S110 can never promise an address the commit will not land on. It is a
    // PATH now (smartbillhub.bynry.com/brazosbend), not a host: the line used
    // to carry a hardcoded "…smartbillhub.app", then a composed host, and the
    // ruling made both wrong.
    return (
      <p className="m-0 -mt-1 mb-4 text-xs text-success-700">
        {t("tenancy.signup.utility.available", {
          address: tenantAddress(props.appHost, result.subdomain),
        })}
      </p>
    );
  }
  // BR-TEN-011 problem codes render as their own catalog lines — the reason is
  // named, never a bare "invalid".
  return (
    <FieldError message={t(`tenancy.signup.utility.problem.${result.problem ?? "unknown"}`)} />
  );
}

function ReviewBlock(props: {
  title: string;
  editLabel: string;
  onEdit: () => void;
  rows: { label: string; value: string }[];
}) {
  return (
    <div className="mb-4 border-t-2 border-t-divider pt-3">
      <div className="flex items-center justify-between">
        <Kicker>{props.title}</Kicker>
        <Button variant="ghost"  onClick={props.onEdit}>
          {props.editLabel}
        </Button>
      </div>
      {props.rows.map((row) => (
        <div key={row.label} className="flex justify-between gap-4 py-1 text-base">
          <span>{row.label}</span>
          <b>{row.value}</b>
        </div>
      ))}
    </div>
  );
}

/** The band a stored plan code stands for, as the prospect picked it —
 *  "3,000–10,000 accounts". Never a plan NAME and never a price (DEF-TEN-4222). */
function sizeLabel(t: Translator, plan: string, locale: string): string {
  const band = sizeBandForPlan(plan);
  return band === undefined ? plan : `${sizeBandRange(t, band, locale)} ${t("public.home.sizes.unit")}`;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-001@d5f8c32 (story+rules snapshot hash — EP-TEN-03; regenerated for the BR-TEN-045 post-signup handoff; fix pass 2026-08-10 for the PO's smartbillhub.bynry.com host choice)
// generated: 2026-08-09 by story-coder v1 · amended 2026-08-10 by story-coder v1 (tenant host suffix becomes build-time configuration) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`) · AMENDED 2026-08-19 by story-coder (CR-017 provisioning-screen lane — S114 gains its POST-COMMIT STATE: `ProvisioningPanel` names the work while the commit is in flight and polls the sample-data plant's real BE-07 job record; the handover moved out of `onCommitted` and into that screen; DEF-325 fixed in the same slice)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: 2026-08-10 re-run — trace_lint✔ tsc✔ eslint✔ vitest 509/509✔ (132 todo repo-wide; 3 in this file's suite — browser/journey/v2-deferred scope) · run_gates 11 PASS · 0 FAIL · 1 SKIP (G12 is the wave-close journey gate) · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: E2 REOPENED-AND-CLOSED THE OTHER WAY (PO 2026-08-10) — US-TEN-001 §6's "the owner is signed in" is TRUE again: BR-TEN-045 was the cross-HOST workaround, and with one origin the commit's session is the owner's, so S114 routes to /{subdomain}/checklist (S62) and the success screen is deleted · E3 CLOSED-BY-DELETION 2026-08-10 — the whole tenant-host mechanism is gone (VITE_TENANT_HOST_SUFFIX, its .env.example/README entries, configuredTenantHostSuffix/derivedTenantHostSuffix/tenantHostSuffix/tenantHost/tenantHomeUrl): a path-based address is composed from window.location, so there is no suffix to configure and no label-dropping guess left to get wrong · E1 A1 controls with no home in the ratified payload (rate style / cycle / bill-on day / implementation package / country) are NOT rendered — reported · E1 CLOSED — the owner step composes the kit's PasswordField · E1 the S110 availability line now interpolates the composed PATH address (smartbillhub.bynry.com/brazosbend) from the same helper the router uses, so S110 and the commit cannot name two different addresses — reported
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
