/* CR-075 wave C · C1a — the rule `SettingsOwnedField` exists to enforce.
 *
 * Node environment on purpose: this reads the component's own SOURCE, and
 * `import.meta.url` under jsdom is an `http:` URL that `fileURLToPath` refuses.
 * The interactive assertions live in `SettingsOwnedField.dom.test.tsx`. */
import { describe, expect, it } from "vitest";

const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: string, enc: string): string;
};
const nodeUrl = (await import(/* @vite-ignore */ ["node", "url"].join(":"))) as {
  fileURLToPath(url: URL | string): string;
};

const SOURCE = nodeFs.readFileSync(
  nodeUrl.fileURLToPath(new URL("./SettingsOwnedField.tsx", import.meta.url)),
  "utf8",
);

describe("SettingsOwnedField — the rule, not the rendering", () => {
  it("THERE IS NO `value` PROP, AND THE SOURCE IS THE ASSERTION", () => {
    // `09-component-inventory.md` Part 5 §5 states it as a rule rather than a
    // preference: "the component reads Settings and takes no value prop — a
    // component with a value prop here is the bug." The reason is one sentence
    // further up the same file: "Duplicating one is how a utility ends up with
    // two ladders and no way to tell which one sent the notice."
    //
    // `tsc` cannot refuse a prop nobody declared, so the file itself is the
    // check, and the next lane's obvious convenience is exactly what is refused.
    const props = SOURCE.split("export interface SettingsOwnedFieldProps")[1];
    expect(props, "the props interface has been renamed — this check now covers nothing").toBeDefined();
    const body = props.split("\n}")[0];
    expect(body).not.toMatch(/^\s*value\??:/m);
    expect(body).not.toMatch(/^\s*defaultValue\??:/m);
  });

  it("it reads through the context and nowhere else", () => {
    expect(SOURCE).toContain("useSettingsOwnedValues");
    // and the context starts at null, so "not yet" is distinguishable from a
    // real answer — TenantRegional.tsx's DEF-SHL-3964 lesson, copied on purpose.
    expect(SOURCE).toContain("createContext<SettingsOwnedValues | null>(null)");
  });

  it("every word a reader sees arrives already translated — no catalogue key is built here", () => {
    // A message_key with no catalogue entry renders as nothing (DEF-INT-4269,
    // filed the same day). This component cannot have that defect because it
    // never resolves a key: the caller hands in finished words.
    expect(SOURCE).not.toContain("useTranslation");
    expect(SOURCE).not.toMatch(/\bt\(/);
  });
});
