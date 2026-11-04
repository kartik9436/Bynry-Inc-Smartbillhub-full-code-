// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-RAT-8741 — rate schedule sizes sorted as TEXT, so "Battery 5 kW"
//           came after "Battery 30 kW" on RAT-03 step 2 and on the review.
// Rules:    hard rule 2 (nothing here is money; the numbers read are SIZES, used
//           only to order rows and never shown or posted)
// Tests:    src/features/rating/sizeOrder.test.ts
// ───────────────────────────────────────────────────────
/**
 * **THE ORDER A SIZE CLASS IS READ IN — BY THE SIZE IT NAMES, NOT BY ITS SPELLING.**
 *
 * The server serves `service_size_classes` ordered by CODE, and a schedule's
 * `size_rows` the same way, so `BAT-10 … BAT-30, BAT-5` and `W-1, W-112, W-2 …
 * W-34 … W-58` reach the screen in an order no clerk would write. The lookup row
 * carries no sort column, so the order is read from the NAME a clerk reads:
 * every number in it, in turn — `Electric 1φ 200A` is `(1, 200)` and sits after
 * `1φ 100A` and before `3φ 200A`; `Water 5/8"` is `0.625` and sits before
 * `3/4"` (`0.75`) and `1½"` (`1.5`); `1,000 Mbps` is a thousand.
 *
 * A name with no number keeps the place it arrived in (the sort is stable), and
 * sits after the numbered ones — storm water's `Single-family home` and
 * `Apartment building` are a list somebody ordered, and this has nothing better
 * to offer than that order.
 */
const VULGAR: Record<string, number> = { "¼": 0.25, "½": 0.5, "¾": 0.75 };

export function sizeNumbers(name: string): number[] {
  const out: number[] = [];
  const pattern = /(\d[\d,]*(?:\.\d+)?)(?:\s*\/\s*(\d+))?([¼½¾])?|([¼½¾])/g;
  for (const match of name.matchAll(pattern)) {
    if (match[4] !== undefined) {
      out.push(VULGAR[match[4]]);
      continue;
    }
    let value = Number(match[1].replace(/,/g, ""));
    if (match[2] !== undefined && Number(match[2]) !== 0) {
      value = value / Number(match[2]);
    }
    if (match[3] !== undefined) {
      value += VULGAR[match[3]];
    }
    out.push(value);
  }
  return out;
}

export function compareSizeNames(a: string, b: string): number {
  const left = sizeNumbers(a);
  const right = sizeNumbers(b);
  if (left.length === 0 || right.length === 0) {
    // Numbered before un-numbered; two un-numbered keep their arrival order.
    return (left.length === 0 ? 1 : 0) - (right.length === 0 ? 1 : 0);
  }
  for (let i = 0; i < Math.min(left.length, right.length); i += 1) {
    if (left[i] !== right[i]) {
      return left[i] - right[i];
    }
  }
  return left.length - right.length;
}

/** A copy of `items` in size order. `nameOf` returns the name a clerk reads. */
export function sortBySize<T>(items: readonly T[], nameOf: (item: T) => string): T[] {
  return items
    .map((item, index) => ({ item, index }))
    .sort((a, b) => compareSizeNames(nameOf(a.item), nameOf(b.item)) || a.index - b.index)
    .map((entry) => entry.item);
}

/** A size name without the service word it opens with — `Water 5/8"` on a
 *  Water row reads `5/8"`. A name that does not open with it is left whole. */
export function sizeWithoutService(name: string, serviceName: string): string {
  const prefix = `${serviceName.trim()} `;
  return serviceName.trim() !== "" && name.toLowerCase().startsWith(prefix.toLowerCase())
    ? name.slice(prefix.length)
    : name;
}
