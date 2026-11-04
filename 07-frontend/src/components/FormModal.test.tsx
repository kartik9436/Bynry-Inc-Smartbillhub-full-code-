// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-009 (EP-SHL-03 §Stories)  Screens: S12, S13, S16, S22, S114
// Rules:    BR-SHL-017 (field kit + inline validation; PasswordField closes the S3/S114 E1 gap) ·
//           BR-SHL-033 (date picker + searchable long lists) · BR-PAY-033 (pre-fill default)
// ───────────────────────────────────────────────────────
// TC tests for FE-05 FormModal + the US-SHL-009 field kit. Same conventions as
// the prior packet runs: no DOM library in package.json, so markup asserts on
// react-dom/server static output and orchestration laws run through the
// exported pure functions (collectFormErrors, envelopeErrors, missingUnit).
// Anything needing a live browser (clicks, scroll, focus) is an honest
// it.todo for the Playwright journeys.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { z } from "zod";

import i18n from "@/i18n"; // the i18next singleton with the five catalogs

import {
  CheckboxField,
  DatePickerField,
  FormModal,
  ModalShell,
  PasswordField,
  SearchSelectField,
  SegmentedField,
  SelectField,
  TextField,
  collectFormErrors,
  envelopeErrors,
  filterOptions,
  passwordToggle,
  resolveDateInputValue,
  stepActiveOption,
} from "./FormModal";
import type { ServerErrorEnvelope } from "./FormModal";
import { FormErrorSummary, INVALID_INPUT_CLASS } from "./StateFrame";

const noop = () => undefined;

// §4 test data — S22 Record payment for A-10432. The amount is validated as a
// raw decimal STRING: no Number()/parseFloat anywhere (CLAUDE.md rule 2 — the
// server owns parsing; client checks are string-shaped UX only).
const DECIMAL_RE = /^\d+(\.\d+)?$/;
const ZERO_RE = /^0*(\.0*)?$/;
const s22Schema = z.object({
  amount: z.string().refine(
    (raw) => DECIMAL_RE.test(raw) && !ZERO_RE.test(raw),
    "Amount must be greater than 0.", // A18 §5 example copy (consumer-localized)
  ),
});

// §4 test data — S12 New Charge Code, four required fields blank for TC-2.
const s12Schema = z.object({
  code: z.string().min(1, "Enter a code."),
  name: z.string().min(1, "Enter a name."),
  gl_account: z.string().min(1, "Pick a GL account."),
  amount_type: z.string().min(1, "Pick an amount type."),
});

describe("US-SHL-009 — form field patterns & inline validation", () => {
  it("US-SHL-009 TC-1: S22 amount 0 — danger border + 'Amount must be greater than 0.' under the field; nothing posted", () => {
    const values = { amount: "0" };
    const result = collectFormErrors(s22Schema, values);
    expect(result.errors.amount).toBe("Amount must be greater than 0.");
    expect(result.count).toBe(1);
    expect(result.first).toBe("amount"); // count > 0 → FormModal returns BEFORE
    // onSubmit — the modal stays open and nothing is posted (see handleSubmit).
    const html = renderToStaticMarkup(
      <TextField
        id="amount"
        label="Amount"
        value="0"
        onChange={noop}
        numeric
        error="Amount must be greater than 0."
      />,
    );
    expect(html).toContain(INVALID_INPUT_CLASS); // A18 §5 danger border
    expect(html).toContain("Amount must be greater than 0.");
    expect(html).toContain("field-error"); // 12px danger message directly under
    expect(html).toContain("input-num"); // A12: money input, tabular numerals
  });

  it("US-SHL-009 TC-2: 4 invalid fields — all four error inline, 'Fix 4 fields to continue.' renders, first error is the target", () => {
    const result = collectFormErrors(s12Schema, {
      code: "",
      name: "",
      gl_account: "",
      amount_type: "",
    });
    expect(result.count).toBe(4);
    expect(Object.keys(result.errors)).toEqual(["code", "name", "gl_account", "amount_type"]);
    expect(result.errors.code).toBe("Enter a code.");
    expect(result.first).toBe("code"); // scroll/focus target (A18 §5)
    // >3 errors → the shared summary line (StateFrame's, composed not rebuilt).
    expect(renderToStaticMarkup(<FormErrorSummary count={result.count} />)).toContain(
      "Fix 4 fields to continue.",
    );
  });

  it.todo(
    "US-SHL-009 TC-2 (browser scope): the viewport scrolls to the first invalid field on submit — Playwright journey",
  );

  it("US-SHL-009 TC-3: fixed values re-validate clean — errors clear per-field and submit proceeds", () => {
    const result = collectFormErrors(s12Schema, {
      code: "LATE",
      name: "Late payment fee",
      gl_account: "4100",
      amount_type: "flat",
    });
    // The error map is rebuilt from current values on every submit, so a fixed
    // field's error is simply gone (BR-SHL-017 re-validate-on-click).
    expect(result.errors).toEqual({});
    expect(result.count).toBe(0);
    expect(result.first).toBeNull();
  });

  it("US-SHL-009 TC-4 (negative): malformed '12.3.4' errors inline; the raw string is never coerced into a number", () => {
    const values = { amount: "12.3.4" };
    const result = collectFormErrors(s22Schema, values);
    expect(result.errors.amount).toBe("Amount must be greater than 0.");
    // CLAUDE.md rule 2: the value stays the raw STRING the user typed — the
    // server owns parsing; nothing here produced a float from it.
    expect(typeof values.amount).toBe("string");
    expect(values.amount).toBe("12.3.4");
  });

  it("US-SHL-009 TC-5: labels and errors are programmatically associated (htmlFor/id, aria-describedby, aria-invalid)", () => {
    const html = renderToStaticMarkup(
      <TextField
        id="code"
        label="Code"
        value=""
        onChange={noop}
        required
        help="Shown on bills."
        error="Enter a code."
      />,
    );
    expect(html).toContain('for="code"');
    expect(html).toContain('id="code"');
    expect(html).toContain('aria-describedby="code-help code-error"');
    expect(html).toContain('aria-invalid="true"');
    expect(html).toContain('aria-required="true"');
    expect(html).toContain('id="code-error"'); // FieldError wired to the input
    expect(html).toContain("field-required"); // visible required mark (aria-hidden)
  });

  it.todo(
    "US-SHL-009 TC-5 (browser scope): keyboard-only Tab order through S12 + screen-reader announcement of errors — Playwright journey",
  );

  // ── FE-05 frame + shell (supplementary, non-TC coverage) ─────────────────

  it("US-SHL-009 / IS-10: ModalShell — the ONE modal shell with dialog semantics and a labelled ✕", () => {
    const html = renderToStaticMarkup(
      <ModalShell title="Record payment" kicker="Account A-10432" onClose={noop}>
        <div className="modal-body">body</div>
      </ModalShell>,
    );
    expect(html).toContain('role="dialog"');
    expect(html).toContain('aria-modal="true"');
    expect(html).toContain("aria-labelledby"); // title labels the dialog
    expect(html).toContain("Record payment");
    expect(html).toContain("Account A-10432");
    expect(html).toContain('aria-label="Close"');
    expect(html).toContain("modal-head");
  });

  it.todo(
    "US-SHL-009 / IS-10 (browser scope): Esc, backdrop click and ✕ close the modal; Tab focus stays trapped inside — Playwright journey",
  );

  it("US-SHL-009 / FE-05: FormModal composes shell + field kit + ghost Cancel + WorkingButton submit", () => {
    const html = renderToStaticMarkup(
      <FormModal
        title="Record payment"
        schema={s22Schema}
        values={{ amount: "247.30" }}
        onSubmit={async () => ({ ok: true as const })}
        onClose={noop}
        submitLabel="Record payment"
      >
        <TextField id="amount" label="Amount" value="247.30" onChange={noop} numeric required />
      </FormModal>,
    );
    expect(html).toContain("<form"); // submit → re-validate orchestration lives here
    expect(html).toContain('role="dialog"');
    expect(html).toContain("Cancel"); // forms.cancel, ghost
    // ⚠ CLASS NAME -> `data-variant` (CR-018 Phase 4a, 2026-08-20). Route B
    // deletes the name; `buttonKit` stamps `data-variant`/`data-size` on every
    // kit button precisely so a check has something stable to read.
    expect(html).toContain('data-variant="ghost"');
    expect(html).toContain('data-variant="primary"'); // WorkingButton idle
    expect(html).toContain("modal-foot");
    // No errors yet → no summary line, no invalid borders (A18 §5).
    expect(html).not.toContain("form-error-summary");
    expect(html).not.toContain(INVALID_INPUT_CLASS);
  });

  it("US-SHL-009 / B12 §3: the server error envelope renders via message_key + params — never client-built sentences", () => {
    // Catalog stand-ins with params prove the t(key, params) path; the real
    // VAL-/BIZ- keys arrive with the generated A11 client's consumers.
    const envelope: ServerErrorEnvelope = {
      code: "VAL-003",
      message_key: "states.validation.summary",
      params: { count: 4 },
      field_errors: [{ field: "amount", message_key: "states.working" }],
      br_ref: "BR-SHL-017",
      trace_id: "trc_0001",
    };
    const mapped = envelopeErrors(envelope, (key, params) => i18n.t(key, params));
    expect(mapped.message).toBe("Fix 4 fields to continue.");
    expect(mapped.fields.amount).toBe("Working…");
  });

  it("US-SHL-009 / field kit: select, segmented radios and checkbox render the A12 patterns with associated labels", () => {
    const select = renderToStaticMarkup(
      <SelectField
        id="gl_account"
        label="GL account"
        value=""
        onChange={noop}
        placeholder="Pick an account"
        options={[{ value: "4100", label: "4100 — Late fees" }]}
        required
      />,
    );
    expect(select).toContain('for="gl_account"');
    expect(select).toContain("Pick an account");
    expect(select).toContain("4100 — Late fees");

    const seg = renderToStaticMarkup(
      <SegmentedField
        id="amount_type"
        label="Amount type"
        value="flat"
        onChange={noop}
        options={[
          { value: "flat", label: "Flat" },
          { value: "percent", label: "Percent" },
        ]}
      />,
    );
    expect(seg).toContain('class="seg"');
    expect(seg).toContain("seg-opt");
    expect(seg).toContain('role="radiogroup"');
    expect(seg).toContain("checked"); // the current value is the checked radio
    // ⚠ **`DEF-CUS-5082` — ABSENT MEANS UNMARKED, AND THAT MUST STAY TRUE.**
    // This control hard-coded `required={false}` with no prop to say otherwise.
    // A `required` prop was added for the service-request capture, whose step 1
    // gates `Continue` on the group; the eighteen existing call sites pass
    // nothing and must render exactly what they rendered before, so the
    // NEGATIVE is asserted here beside the positive below. A one-directional
    // assertion is `DEF-CUS-4298`'s recorded shape.
    expect(seg).not.toContain("field-required");
    expect(seg).not.toContain("aria-required");

    const segRequired = renderToStaticMarkup(
      <SegmentedField
        id="account_type_code"
        label="Customer category"
        value=""
        onChange={noop}
        required
        options={[
          { value: "residential", label: "Residential" },
          { value: "commercial", label: "Commercial" },
        ]}
      />,
    );
    // B14 rule 10 — the mark is on the LABEL and `aria-required` carries it to
    // assistive tech. ⚠ **ON THE `radiogroup`, NOT ON EACH RADIO:** the group
    // is the thing that must be answered, and a required radio INPUT would tell
    // a screen reader that every option is separately obligatory.
    expect(segRequired).toContain("field-required");
    expect(segRequired).toContain('role="radiogroup"');
    expect(segRequired).toMatch(/role="radiogroup"[^>]*aria-required="true"|aria-required="true"[^>]*role="radiogroup"/);
    expect(segRequired).not.toContain('type="radio" required');

    const checkbox = renderToStaticMarkup(
      <CheckboxField id="active" label="Active" checked={true} onChange={noop} />,
    );
    expect(checkbox).toContain('type="checkbox"');
    expect(checkbox).toContain('for="active"');
    // DEF-569 — a multi-select must NOT wear the radio's circle. The markup
    // assertion is the half a unit test can make (the shape is measured in the
    // browser, `border-radius: 0px`): no `.radio`/`.dot`, and a square mark
    // carrying the vocabulary's ✓.
    expect(checkbox).not.toContain('class="radio"');
    expect(checkbox).not.toContain("dot");
    expect(checkbox).toContain("data-checkbox-mark");
    expect(checkbox).toContain("<svg"); // CommitIcon, the one ✓ in the vocabulary
  });
});

// ── BR-SHL-033 field-kit additions (PO 2026-08-09, batch item b rider) ─────
// DatePickerField + SearchSelectField ride US-SHL-009's kit; BR-SHL-033 mints
// no numbered TCs (Test column: "rides FE-05 field kit"), so titles cite the
// BR directly. Same honest split as above: pure laws + static markup here,
// live typing/clicking as it.todo for the Playwright journeys.

// §BR-SHL-033 test data — a 12-option GL-account list (> LONG_LIST_THRESHOLD).
const GL_OPTIONS = [
  { value: "4000", label: "4000 — Water revenue" },
  { value: "4010", label: "4010 — Electric revenue" },
  { value: "4020", label: "4020 — Gas revenue" },
  { value: "4030", label: "4030 — Sewer revenue" },
  { value: "4040", label: "4040 — Trash revenue" },
  { value: "4050", label: "4050 — Broadband revenue" },
  { value: "4100", label: "4100 — Late fees" },
  { value: "4110", label: "4110 — Connection fees" },
  { value: "4120", label: "4120 — NSF fees" },
  { value: "2100", label: "2100 — Customer deposits" },
  { value: "2200", label: "2200 — Sales tax payable" },
  { value: "1200", label: "1200 — Accounts receivable" },
];

describe("BR-SHL-033 — DatePickerField (date-picker law + BR-PAY-033 pre-fill)", () => {
  it("BR-PAY-033: pre-fill renders — an empty value shows the proposed default in a native date input", () => {
    // Pure half: the proposal only stands in for an EMPTY value.
    expect(resolveDateInputValue("", "2026-08-09")).toBe("2026-08-09");
    expect(resolveDateInputValue("", undefined)).toBe("");
    const html = renderToStaticMarkup(
      <DatePickerField
        id="posting_date"
        label="Posting date"
        value=""
        onChange={noop}
        prefill="2026-08-09"
        dateFormat="MM/DD/YYYY"
        required
      />,
    );
    expect(html).toContain('type="date"'); // BR-SHL-033: date picker + manual entry
    expect(html).toContain('value="2026-08-09"'); // the proposal renders immediately
    // ⚠ **THE IS-8 LINE IS NOW CONDITIONAL, AND THIS ASSERTION MOVED RATHER
    // THAN WEAKENED (CR-043 finding 15).** It used to read `MM/DD/YYYY` and
    // expect `08/09/2026` under the input — which is the same eight characters
    // the native control was already printing to a US browser, twice, directly
    // under themselves. The RULE is unchanged: a tenant whose format differs
    // from the browser's still gets their format, and that is what is asserted.
    const german = renderToStaticMarkup(
      <DatePickerField
        id="posting_date"
        label="Posting date"
        value=""
        onChange={noop}
        prefill="2026-08-09"
        dateFormat="DD.MM.YYYY"
        required
      />,
    );
    expect(german).toContain("09.08.2026"); // IS-8 regional rendering (ONE formatDate path)
    expect(german).toContain("field-date-display");
    // ...and the redundant copy is gone where the two agree.
    expect(html).not.toContain("field-date-display");
  });

  it("BR-PAY-033: override works — a user-entered value beats the prefill", () => {
    expect(resolveDateInputValue("2026-08-15", "2026-08-09")).toBe("2026-08-15");
    const html = renderToStaticMarkup(
      <DatePickerField
        id="posting_date"
        label="Posting date"
        value="2026-08-15"
        onChange={noop}
        prefill="2026-08-09"
        dateFormat="DD.MM.YYYY"
      />,
    );
    expect(html).toContain('value="2026-08-15"');
    expect(html).not.toContain('value="2026-08-09"'); // the proposal never fights the user
    expect(html).toContain("15.08.2026");
  });

  it("BR-SHL-033 / IS-8: the tenant Regional format drives the display line (switching the setting re-renders it)", () => {
    const ddmm = renderToStaticMarkup(
      <DatePickerField
        id="due_date"
        label="Due date"
        value="2026-08-15"
        onChange={noop}
        dateFormat="DD/MM/YYYY"
      />,
    );
    expect(ddmm).toContain("15/08/2026");
    const iso = renderToStaticMarkup(
      <DatePickerField
        id="due_date"
        label="Due date"
        value="2026-08-15"
        onChange={noop}
        dateFormat="YYYY-MM-DD"
      />,
    );
    expect(iso).toContain("2026-08-15");
    expect(iso).not.toContain("15/08/2026");
  });

  it("BR-SHL-017/IS-10 a11y: label, help and error wire to the date input like every kit field", () => {
    const html = renderToStaticMarkup(
      <DatePickerField
        id="posting_date"
        label="Posting date"
        value="2026-08-09"
        onChange={noop}
        dateFormat="MM/DD/YYYY"
        required
        help="The date the money was received."
        error="Enter a posting date."
      />,
    );
    expect(html).toContain('for="posting_date"');
    expect(html).toContain('aria-required="true"');
    expect(html).toContain('aria-invalid="true"');
    expect(html).toContain('aria-describedby="posting_date-help posting_date-error"');
    expect(html).toContain('id="posting_date-error"');
    expect(html).toContain(INVALID_INPUT_CLASS); // A18 §5 danger border
  });

  it.todo(
    "BR-PAY-033 (browser scope): the mount effect commits the prefill into consumer state so the proposal is what posts — Playwright journey",
  );
});

describe("BR-SHL-033 — SearchSelectField (searchable-long-list law)", () => {
  it("BR-SHL-033: search filters options — case-insensitive label match, whole list when the query is empty", () => {
    expect(filterOptions(GL_OPTIONS, "late")).toEqual([{ value: "4100", label: "4100 — Late fees" }]);
    expect(filterOptions(GL_OPTIONS, "REVENUE")).toHaveLength(6);
    expect(filterOptions(GL_OPTIONS, "41")).toHaveLength(3); // 4100/4110/4120 — numbers live in labels
    expect(filterOptions(GL_OPTIONS, "  late  ")).toHaveLength(1); // trimmed
    expect(filterOptions(GL_OPTIONS, "")).toHaveLength(12); // no query → the full list
    expect(filterOptions(GL_OPTIONS, "zzz")).toEqual([]); // no matches → empty-state row
  });

  it("BR-SHL-033: keyboard navigation law — Arrow stepping wraps at both ends and enters the list from -1", () => {
    expect(stepActiveOption(-1, 1, 12)).toBe(0); // ArrowDown opens on the first
    expect(stepActiveOption(-1, -1, 12)).toBe(11); // ArrowUp opens on the last
    expect(stepActiveOption(11, 1, 12)).toBe(0); // wraps forward
    expect(stepActiveOption(0, -1, 12)).toBe(11); // wraps backward
    expect(stepActiveOption(3, 1, 12)).toBe(4);
    expect(stepActiveOption(0, 1, 0)).toBe(-1); // empty filtered list → nothing active
  });

  it("BR-SHL-033/IS-10 a11y: the ARIA combobox pattern renders — input wired to a listbox, selection marked", () => {
    const html = renderToStaticMarkup(
      <SearchSelectField
        id="gl_account"
        label="GL account"
        value="4100"
        onChange={noop}
        options={GL_OPTIONS}
        placeholder="Search accounts"
        required
      />,
    );
    expect(html).toContain('role="combobox"');
    expect(html).toContain('aria-expanded="false"'); // closed at rest
    expect(html).toContain('aria-controls="gl_account-listbox"');
    expect(html).toContain('aria-autocomplete="list"');
    expect(html).toContain('role="listbox"');
    expect(html).toContain('role="option"');
    expect(html).toContain('id="gl_account-opt-4100"');
    expect(html).toContain('aria-selected="true"'); // the current value is marked
    expect(html).toContain('value="4100 — Late fees"'); // at rest the input shows the label
    expect(html).toContain('for="gl_account"');
    expect(html).toContain('aria-required="true"');
    // IS-3 mechanics arrive through the ONE createSearchDebouncer — its 300 ms /
    // min-2-chars laws are proven in DataTable.test.tsx (US-SHL-006 TC-3).
    expect(i18n.t("forms.searchSelect.noMatches")).toBe("No matching options."); // catalog key exists
  });

  it.todo(
    "BR-SHL-033 (browser scope): typing filters after the shared 300 ms debounce; Enter picks the active option; first Esc closes the list, second closes the modal; blur restores the selected label — Playwright journey",
  );
});

// ── PasswordField (E1 from the Settings lane, closed in the kit) ───────────
// BR-SHL-017 mints no numbered TC for a password control (none was designed),
// so the titles cite the BR. Same honest split: the reveal LAW is a pure
// function, the a11y wiring is static markup, and the live click is a journey.

describe("BR-SHL-017 — PasswordField (the ONE password control in the field kit)", () => {
  it("BR-SHL-017: the reveal law — hidden renders type=password, revealed renders type=text, and the toggle renames itself", () => {
    expect(passwordToggle(false).inputType).toBe("password");
    expect(passwordToggle(true).inputType).toBe("text");
    // The accessible name changes with the state, so a screen reader is never
    // told "Show password" while the password is already showing.
    expect(passwordToggle(false).labelKey).toBe("forms.password.showLabel");
    expect(passwordToggle(true).labelKey).toBe("forms.password.hideLabel");
    expect(i18n.t(passwordToggle(false).labelKey)).toBe("Show password");
    expect(i18n.t(passwordToggle(true).labelKey)).toBe("Hide password");
    expect(i18n.t(passwordToggle(false).textKey)).toBe("Show");
    expect(i18n.t(passwordToggle(true).textKey)).toBe("Hide");
  });

  it("BR-SHL-017: the toggle is a real BUTTON with an accessible name, and type=button so revealing never submits the form", () => {
    const html = renderToStaticMarkup(
      <PasswordField
        id="signin-password"
        label="Password"
        value=""
        onChange={noop}
        required
        autoComplete="current-password"
      />,
    );
    // Role + accessible name, not markup trivia: this is what AT announces.
    expect(html).toContain('aria-label="Show password"');
    expect(html).toContain('<button type="button"'); // never a default submit
    expect(html).toContain('aria-pressed="false"'); // a toggle, and it starts off
    expect(html).toContain('aria-controls="signin-password"'); // wired to its input
    expect(html).toContain('id="signin-password" type="password"'); // hidden at rest
    // The credential-manager hint survives the move into the kit (react-dom's
    // static renderer keeps the JSX casing; the browser lowercases it).
    expect(html).toMatch(/autocomplete="current-password"/i);
  });

  it("BR-SHL-017/IS-10 a11y: label, help and error wire to the password input exactly like every other kit field", () => {
    const html = renderToStaticMarkup(
      <PasswordField
        id="signup-owner-password"
        label="Password"
        value=""
        onChange={noop}
        required
        help="You'll sign in with this at your new web address."
        error="Enter your password."
      />,
    );
    expect(html).toContain('for="signup-owner-password"');
    expect(html).toContain('aria-required="true"');
    expect(html).toContain('aria-invalid="true"');
    expect(html).toContain(
      'aria-describedby="signup-owner-password-help signup-owner-password-error"',
    );
    expect(html).toContain('id="signup-owner-password-error"');
    expect(html).toContain(INVALID_INPUT_CLASS); // A18 §5 danger border
    expect(html).toContain("field-required"); // visible required mark (aria-hidden)
  });

  it.todo(
    "BR-SHL-017 (browser scope): clicking the toggle flips the input to type=text and back, and does NOT submit the surrounding form — Playwright journey",
  );
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-009@b9eb83e (story+rules snapshot hash — EP-SHL-03; regenerated for PasswordField, the BR-SHL-017 E1 rider)
// generated: 2026-08-09 by story-coder v1
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: trace_lint✔ tsc✔ eslint✔ vitest 239/239✔ (6 todo this file's suite — browser/journey scope) · run_gates 9 PASS · 2 FAIL · 1 SKIP — BOTH FAILs are 06-backend-owned and in flight from the two backend lanes (G5 isolation collection errors, G10 backend stories still missing test_us_*_tc* files); reproduced IDENTICALLY with 07-frontend stashed, so nothing in this packet caused them
// exceptions: none — the live toggle CLICK is an honest it.todo (browser scope); the reveal law itself is proven pure
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
