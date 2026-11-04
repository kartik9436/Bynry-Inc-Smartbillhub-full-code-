# `className` grammar — one source, two readers (OQ-277)

The regex that pulls class names out of a `.tsx` file **used to exist twice**, in
two languages, in two workflows that share no runtime:

| reader | asks | runs in |
|---|---|---|
| `10-scripts/gates/g31_declared_classes.py` | *is this class declared by a stylesheet?* | `gates.yml` — **Python and nothing else** |
| `07-frontend/src/styles/routeBUtilities.test.ts` | *does the Tailwind compiler accept this utility?* | `ci-frontend.yml` — **node and nothing else** |

Neither can call the other, and neither can be deleted: they answer different
questions and both are load-bearing. So they duplicated the grammar, and
**every correction to it had landed in one language only**:

1. G31's first draft counted a comparison operand (`row.state === "auto"`) as a
   class — 130 reported, 125 real.
2. Its second draft consumed an interpolated template whole and **silently
   lost** `is-selected`/`is-blocked` while gaining a false name. The referenced
   count went 871 → 870, which looks like an improvement.
3. G34's `^\s*` matched across a newline and misreported a line number.

## What is here

| file | what it is |
|---|---|
| `patterns.json` | **the grammar.** Five regex *source strings* both readers compile, plus per-pattern probes that prove each one means the same thing in Python `re` and JS `RegExp`, plus the list of constructs that may never appear because they do **not**. |
| `corpus.tsx` | **the golden fixture** — ten cases, each one a bug that has already happened. Not application code; never imported, built or rendered. |
| `corpus.expected.json` | **the expected extraction**, and the case-to-defect mapping in prose. |

## The two halves, and why both are needed

Sharing `patterns.json` stops the two readers *spelling* the grammar
differently. It does not stop them *using* it differently — none of the three
bugs above was a wrong character of regex; all three were in the surrounding
code. So each reader also asserts the corpus **in its own workflow**, as **set
equality**, and neither needs the other's runtime. Sharing catches textual
drift; the corpus catches semantic drift.

Set equality, not "contains": bug 2 gained a name while losing two, so any
assertion that only checks for the names it expects passes it.

## One pattern is deliberately NOT shared

`TOKEN`. G31 asks *"could a stylesheet declare this name?"* and must reject
`sm:foo` and `text-[13px]` forever; the vitest check asks *"could Tailwind
compile this candidate?"* and must accept them. Merging the two breaks one.
It is also the only pattern that needs anchors, which is the construct the two
engines least agree on. **Unshared is not unwatched:** corpus case C10 gives the
divergence an exact size of one token, asserted on both sides.

## Changing the grammar

Edit `patterns.json`. Both readers change together, and both corpus checks run
on the next push. To add a case, add it to `corpus.tsx` **and**
`corpus.expected.json` — half a change fails immediately, in both languages,
which is the intent.

## Why it lives outside `07-frontend/src/`

Four reasons, none cosmetic: G31 scans `src/**/*.tsx` and its ratchet is **0**,
so a fixture inside `src/` would add ten undeclared names to the product's own
count; `tsconfig.json` includes only `src`; `npm run lint` lints only `src`;
vitest collects only `src/**/*.test.{ts,tsx}`. And it lives **inside
`07-frontend/`** because `ci-frontend.yml` triggers on `07-frontend/**` — put it
in `10-scripts/` and editing the grammar would not run the reader that has no
Python.
