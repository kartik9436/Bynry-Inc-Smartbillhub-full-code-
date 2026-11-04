// FI-06 support — the journey-tagging convention (B12 r3 §5; e2e/README.md).
// One spec file per journey, NAMED FOR ITS ID: J1.spec.ts, J07.spec.ts,
// T3M-001.spec.ts, T5-04.spec.ts … A spec is authored only when the wiring
// index (08-qa/01-e2e/01-journey-story-index.md) shows every story the journey
// needs is built — activation is the index's decision, never this directory's.
//
// journey() wraps test.describe with the journey ID as a Playwright tag, so
// one journey (or a tier) is selectable:
//   npx playwright test --grep @J1
//   npx playwright test --grep "@T3M-"
// It ALSO carries APP_SERVER_TAG, since 2026-08-11. A journey drives the real
// product by definition, and the census counts browser assertions by that tag
// alone (support/census.ts): a journey spec tagged only `@J12` would have had
// every one of its assertions counted in the SERVER-FREE bucket, so a run where
// all its browser tests skipped would still have shown a healthy total and
// exited 0 — DEF-057 wearing the journey directory's hat. Tagging here rather
// than asking each spec to remember means no journey can be authored into that
// hole. `--grep @J1` still selects one journey; `--grep @app-server` now selects
// every browser test including the journeys.
import { test } from "@playwright/test";

import { APP_SERVER_TAG } from "./census";

export function journey(id: string, title: string, body: () => void): void {
  test.describe(`${id} — ${title}`, { tag: [`@${id}`, APP_SERVER_TAG] }, body);
}
