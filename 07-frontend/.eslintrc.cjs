// B8 TypeScript/React conventions: strict lint, no `any` (CI-gated).
module.exports = {
  root: true,
  parser: "@typescript-eslint/parser",
  parserOptions: {
    ecmaVersion: 2022,
    sourceType: "module",
  },
  plugins: ["@typescript-eslint", "react-hooks"],
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react-hooks/recommended",
    "prettier",
  ],
  rules: {
    "@typescript-eslint/no-explicit-any": "error",
    "react-hooks/rules-of-hooks": "error",
    "react-hooks/exhaustive-deps": "error",

    // ── CR-018 Phase 2b · THE TYPE SCALE HAS NO BACK DOOR ────────────────────
    //
    // Phase 0 cleared Tailwind's `--text-*` namespace so `text-2xl` compiles to
    // nothing. That is HALF a fence: it does not touch `text-[12.5px]`, because
    // arbitrary values come from a namespace no `@theme` block can empty. Every
    // half-step Phase 2 spent a day absorbing can return in bracket notation,
    // and until this rule landed nothing in the repo could see it.
    //
    // ⚠ THESE THREE ENTRIES ARE THE EDITOR'S HALF OF THE CHECK, NOT THE CHECK.
    // `npm run lint` ran in NO CI workflow at all (DEF-339): gates.yml installs
    // Python only and ci-frontend.yml ran build + vitest. A lint rule nobody
    // runs is a comment claiming a guarantee (hard-won law 1), so Phase 2b did
    // BOTH — it wired `npm run lint` into ci-frontend.yml AND wrote
    // `10-scripts/gates/g34_type_scale_escape.py`, which gates.yml runs on every
    // push and which also reads `.css`, a file type ESLint never opens.
    //
    // ⚠ AND THEY ARE DELIBERATELY NARROW. Tailwind's `text-` prefix carries both
    // the size and the colour, so `text-[color-mix(in_srgb,var(--color-text)_70%,
    // transparent)]` is an arbitrary COLOUR and must NOT trip: it is the correct
    // spelling here, because the opacity modifier that would replace it
    // (`text-text/70`) emits `color-mix(in oklab)` and this design system writes
    // `in srgb`. Only a LENGTH in the brackets is a type value. A rule that
    // fired on the correct spelling would be switched off within a week.
    "no-restricted-syntax": [
      "error",
      {
        selector:
          "Literal[value=/text-\\[-?[0-9.]+(px|rem|em|ch|ex|vw|vh|vmin|vmax|pt|pc|%)\\]|leading-\\[|tracking-\\[|font-\\[/]",
        message:
          "Arbitrary Tailwind type value. The ruled scale names every step — text-xs/sm/base/md/body, text-h1..h5, text-display, text-metric-sm/metric/metric-lg, text-btn/btn-sm. Use the name (decision log 2026-08-19, OQ-275/276/278). An arbitrary COLOUR such as text-[color-mix(in_srgb,…)] is fine and is not what this matches.",
      },
      {
        selector:
          "TemplateElement[value.raw=/text-\\[-?[0-9.]+(px|rem|em|ch|ex|vw|vh|vmin|vmax|pt|pc|%)\\]|leading-\\[|tracking-\\[|font-\\[/]",
        message:
          "Arbitrary Tailwind type value inside a template literal. Use a ruled step name. ⚠ Tailwind only generates what its scanner SEES, so a class name BUILT from a template is already broken for a second reason (tailwind-specimen/README.md).",
      },
      {
        selector: "Property[key.name='fontSize'], Property[key.value='font-size']",
        message:
          "Inline font size. B14 rule 5 — 'No inline font sizes.' Put it in the stylesheet against a ruled token, or write the utility.",
      },
    ],
  },
  ignorePatterns: ["dist", "playwright-report", "test-results"],
};
