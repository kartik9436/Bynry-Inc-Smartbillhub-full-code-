# Templates redesign — the drawing (2026-10-29)

**PO, verbatim (2026-10-29):** *"Please build template redeisgn UI product screen using images and not content. Use -https://claude.ai/artifact/AoKYfff93LEMN5b2x5J6MB this html artifact start and complete all tasks"*

**The `images/` folder IS the drawing (B14 rule 42).** Open each PNG and build to what it shows.
`templates-redesign.html` is the same mock-up, clickable, for checking a flow; its text is an
index, never the specification. Rendered from the published artifact with Playwright at
1440×1000 (light and dark) and 390×844 (phone).

**What the drawing does NOT decide (B14 rules 37 and 44):** every number, name and amount in
it is an illustration. Spacing, sizes, the type scale, tokens and the component kit come from
our UI standard and win on every disagreement — including the sidebar and the settings tabs,
which are drawn only to place the screen. The "What this design fixes" table under the frame is
a review aid, not part of the screen.

## Images

| File | Shows |
|---|---|
| `01-list.png` | Template list: channel chips with counts, search + Category/Language/Status filters, columns Template · Channels · Category · Languages · Variants · Status · Last edited · **Actions** (View, Edit wording, Duplicate as variant icons) |
| `02-workspace-email-view.png` | Template workspace, viewing: Channel / Language / Customers pickers, language rule line with customer count, status line, **one action bar**, Wording pane (Rich/Plain, Insert placeholder, Subject, formatting bar, Message, counter) beside Preview (sample customer switch, Expand, branding line, branded email with logo header, Pay now button, footer) |
| `03-workspace-email-edit-placeholders.png` | Editing, with the placeholder picker open (search, name, `{key}`, "link" tag, description + example) |
| `04-workspace-email-plain.png` | Plain text format: preview prints full link addresses |
| `05-workspace-text.png` | Text message: phone frame, characters + number of texts |
| `06-new-variant.png` | **+ New variant**: Channel, Language (utility's only), Customers, Start from |
| `07-history.png` | History: Version · Status · Saved · Actions (Preview, **Make live again** on earlier published versions); preview shown under the table |
| `08-make-live-again.png` | Confirmation: "v1 goes out from now. v3 stays in history." |
| `09-restored.png` | Status line after restore: "Published v1 (restored)" |
| `10-duplicate-as-variant.png` | Duplicate as variant: same form, Start from "This variant" |
| `11-publish-confirm.png` | Publish confirmation |
| `12-send-test.png` | Send test |
| `13-legal-notice.png` | Legal notice: "Needs approval" tag, primary button reads **Send for approval** |
| `14-letter.png` | Letter preview |
| `15-legal-history.png` | Legal notice history: the restore action reads **Send for approval** |
| `16-spanish.png` | Spanish variant + its customer count |
| `17-warnings.png` | Warnings: a placeholder that can't be filled; a link placeholder used as bare text ("Make it a button or link.") |
| `18-start-from-english.png` | Picking a language not written yet: "Start from English" |
| `19-list-dark.png`, `20-workspace-dark.png` | Dark mode |
| `21-list-phone.png`, `22-workspace-phone.png` | Phone width |

## Known mock-up shortcuts — build the real behaviour, not these

- History **Preview** in the mock-up renders the wording on screen; the product renders **that version's own stored wording**.
- Customer counts, dates, names and the "Springfield" brand are sample data.
- The rich-text markup the mock-up stores (`**bold**`, `[text](link)`, `[[Button|link]]`, `- list`) is a mock-up device; the storage format is the server lane's decision, provided it is a closed safe set and never raw HTML from a clerk.

## Rulings this drawing carries (decision log 2026-10-29)

A1 C (only legal notices need approval) · A2 A (allowed placeholders only; an unknown one blocks saving) · A3 A (variant = channel × language × customer category) · A4 B (only the utility's switched-on languages) (twelve-question ruling) · 1A logo link set once per utility in
Settings › Company › Branding · 2A simple rich editor with a safe preview · **B: a message goes in
the customer's preferred language, falling back to the utility's language** (supersedes
`OQ-CUS-12619` (a) for messages).
