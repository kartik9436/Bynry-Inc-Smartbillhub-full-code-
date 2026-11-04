// @vitest-environment jsdom
// DEF-WRK-9671 — a job's *where* cell: the premises' address, else the meter's
// stored-at note, else a dash; never a blank.
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { WhereCell } from "./WhereCell";

afterEach(cleanup);

describe("DEF-WRK-9671 · where a job is", () => {
  it("names the premises' address, with the list's suffix, and never the note", () => {
    const { container } = render(
      <WhereCell premise={{ address: "903 Birch Ln" }} storedAt="Warehouse bay 3" suffix=" · A-10222" />,
    );
    expect(container.textContent).toBe("903 Birch Ln · A-10222");
  });

  it("a meter in the warehouse reads where it is stored", () => {
    const { container } = render(<WhereCell premise={null} storedAt="Warehouse bay 3" />);
    expect(container.textContent).toBe("Warehouse bay 3");
    expect(container.querySelector("[data-stored-at]")).not.toBeNull();
  });

  it("with no premises and no note it is a dash, never a blank", () => {
    const { container } = render(<WhereCell premise={null} storedAt={null} />);
    expect(container.textContent).toBe("—");
  });
});
