// @vitest-environment jsdom
/**
 * The searchable account dropdown (one-time bill plan F4): keyboard ↑ ↓ Enter
 * Esc, the typed text picked out in the name, the status pill, the second line
 * that tells two alike names apart, and the money rule — typing drops the
 * choice.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AccountCombobox, highlightMatch } from "./AccountCombobox";
import type { AccountComboboxOption } from "./AccountCombobox";
import type { RemoteSearchStatus } from "./RemoteSearchSelectField";

afterEach(cleanup);

const OPTIONS: AccountComboboxOption[] = [
  { value: "id-1", name: "Maria Alvarez", detail: "AC-2026-00042 · 1408 Elm St · Unit A", status: { label: "Active", tone: "success" } },
  { value: "id-2", name: "Luis Alvarez", detail: "AC-2026-00117 · 22 Birch Ct", status: { label: "Active", tone: "success" } },
  { value: "id-3", name: "Maria Alvarez", detail: "AC-2025-01904 · 61 Oak Ave", status: { label: "Closed", tone: "muted" } },
];

const SEARCHED: RemoteSearchStatus = { idle: false, searching: false, searched: true, failed: false };
const WORDS = { tooShort: "Type two letters.", searching: "Searching…", failed: "Search failed.", noMatch: "No account found." };

function Host(props: { onChange?: (value: AccountComboboxOption | null) => void; status?: RemoteSearchStatus; options?: AccountComboboxOption[] }) {
  const [term, setTerm] = useState("");
  const [chosen, setChosen] = useState<AccountComboboxOption | null>(null);
  return (
    <AccountCombobox
      id="account_id"
      label="Find account"
      required
      term={term}
      onTermChange={setTerm}
      status={props.status ?? SEARCHED}
      options={props.options ?? OPTIONS}
      value={chosen?.value ?? ""}
      selectedName={chosen?.name ?? ""}
      onChange={(option) => {
        setChosen(option);
        props.onChange?.(option);
      }}
      words={WORDS}
      help="Name, account no. or address."
    />
  );
}

describe("AccountCombobox", () => {
  it("draws each option with its name, its second line and its status pill", () => {
    render(<Host />);
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "Alv" } });
    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(3);
    expect(options[0]).toHaveTextContent("Maria Alvarez");
    expect(options[0]).toHaveTextContent("AC-2026-00042 · 1408 Elm St · Unit A");
    expect(options[2]).toHaveTextContent("Closed");
    // Two customers with one name are told apart by the second line alone.
    expect(options[0].textContent).not.toEqual(options[2].textContent);
  });

  it("picks out the typed text in the name", () => {
    render(<Host />);
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "alv" } });
    const marks = document.querySelectorAll("[data-match]");
    expect(marks[0]).toHaveTextContent("Alv");
  });

  it("walks the list with ↓ and ↑ and takes the highlighted one on Enter", () => {
    const onChange = vi.fn();
    render(<Host onChange={onChange} />);
    const box = screen.getByRole("combobox");
    fireEvent.change(box, { target: { value: "Alv" } });
    fireEvent.keyDown(box, { key: "ArrowDown" });
    fireEvent.keyDown(box, { key: "ArrowDown" });
    fireEvent.keyDown(box, { key: "ArrowUp" });
    expect(box).toHaveAttribute("aria-activedescendant", "account_id-opt-0");
    fireEvent.keyDown(box, { key: "ArrowDown" });
    fireEvent.keyDown(box, { key: "Enter" });
    expect(onChange).toHaveBeenLastCalledWith(OPTIONS[1]);
    expect(box).toHaveValue("Luis Alvarez");
    expect(box).toHaveAttribute("aria-expanded", "false");
  });

  it("closes on Esc without choosing", () => {
    const onChange = vi.fn();
    render(<Host onChange={onChange} />);
    const box = screen.getByRole("combobox");
    fireEvent.change(box, { target: { value: "Alv" } });
    expect(box).toHaveAttribute("aria-expanded", "true");
    fireEvent.keyDown(box, { key: "Escape" });
    expect(box).toHaveAttribute("aria-expanded", "false");
    expect(onChange).not.toHaveBeenCalled();
  });

  it("drops the choice the moment the clerk types again — a stale id is money on the wrong account", () => {
    const onChange = vi.fn();
    render(<Host onChange={onChange} />);
    const box = screen.getByRole("combobox");
    fireEvent.change(box, { target: { value: "Alv" } });
    fireEvent.click(screen.getAllByRole("option")[0]);
    expect(onChange).toHaveBeenLastCalledWith(OPTIONS[0]);
    fireEvent.change(box, { target: { value: "Maria Alvarez x" } });
    expect(onChange).toHaveBeenLastCalledWith(null);
  });

  it("says no match, and says a failed search differently", () => {
    const { unmount } = render(<Host options={[]} />);
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "Zz" } });
    expect(screen.getByRole("status")).toHaveTextContent("No account found.");
    unmount();
    render(<Host options={[]} status={{ idle: false, searching: false, searched: false, failed: true }} />);
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "Zz" } });
    expect(screen.getByRole("alert")).toHaveTextContent("Search failed.");
  });

  it("leaves a name plain when the match was on the number or the address", () => {
    expect(highlightMatch("Maria Alvarez", "00042")).toBe("Maria Alvarez");
  });
});
