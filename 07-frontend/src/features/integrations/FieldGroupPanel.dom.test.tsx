// @vitest-environment jsdom
// CR-173-BRC10 — *Send to City folder*: drawn from the manifest's group, saved by
// its own route, and the password is never on screen — only its hint.
//
// What would make these pass wrongly (law 7): a panel that rendered the
// fields but posted to the connection's PATCH would satisfy "the fields are
// drawn"; so the WRITE is asserted by ADDRESS and by BODY. A hint assertion
// would pass over a page that ALSO echoed the password, so the password's
// absence from the whole document is asserted separately.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { ApiClient, ApiResponse } from "@/api/client";
import type { FieldGroupView } from "@/api/fileDropEndpoints";
import type { ManifestField, ProviderCard } from "@/api/integrationsEndpoints";

import { FieldGroupPanel, fieldGroups } from "./FieldGroupPanel";

afterEach(cleanup);

const FAKE = "test-password-not-real";

const FIELDS: ManifestField[] = [
  { name: "allowed_addresses", label: "Allowed addresses", kind: "text", required: false, options: [], group: null },
  { name: "sftp_host", label: "Server", kind: "host", required: false, options: [], group: "send_file" },
  { name: "sftp_port", label: "Port", kind: "port", required: false, options: [], group: "send_file" },
  { name: "sftp_username", label: "User name", kind: "text", required: false, options: [], group: "send_file" },
  { name: "sftp_password", label: "Password", kind: "secret", required: false, options: [], group: "send_file" },
  { name: "sftp_path", label: "Folder", kind: "text", required: false, options: [], group: "send_file" },
  { name: "sftp_host_key", label: "Server key", kind: "text", required: false, options: [], group: "send_file" },
];

const CARD = { key: "erp_newworld", display_name: "New World / Logos", fields: FIELDS } as unknown as ProviderCard;

const VIEW: FieldGroupView = {
  group: "send_file",
  connected: true,
  settings: {
    sftp_host: "sftp.city.example",
    sftp_port: "22",
    sftp_username: "Bynry-test",
    sftp_path: "/",
    sftp_host_key: "",
  },
  password_hint: "••••real",
  set_up: true,
  deliveries: [],
};

interface Write {
  method: string;
  path: string;
  body: unknown;
}

function client(writes: Write[]): ApiClient {
  const answer = <T,>(body: unknown): Promise<ApiResponse<T>> =>
    Promise.resolve({ status: 200, data: body as T, headers: new Headers() } as ApiResponse<T>);
  return {
    get: <T,>(path: string) => {
      if (path === "/integrations/erp_newworld/groups/send_file") return answer<T>(VIEW);
      throw new Error(`unexpected GET ${path}`);
    },
    post: <T,>(path: string, body?: unknown) => {
      writes.push({ method: "POST", path, body });
      return answer<T>({
        ok: true,
        sentence: "Signed in and wrote a file.",
        server_key: "SHA256:fakefakefake",
        server_key_captured: true,
        test_file: "/x.txt",
        trace: "ABCD1234",
      });
    },
    put: <T,>(path: string, body?: unknown) => {
      writes.push({ method: "PUT", path, body });
      return answer<T>(VIEW);
    },
  } as unknown as ApiClient;
}

function mount() {
  const writes: Write[] = [];
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <FieldGroupPanel card={CARD} group="send_file" client={client(writes)} />
    </QueryClientProvider>,
  );
  return writes;
}

describe("FieldGroupPanel — Send to City folder", () => {
  it("finds the group on the card, and only the grouped fields", () => {
    expect(fieldGroups(CARD)).toEqual(["send_file"]);
  });

  it("draws the six items in the manifest's order, under the section title", async () => {
    mount();
    expect(await screen.findByText("Send to City folder")).toBeInTheDocument();
    await screen.findByLabelText("Server");
    for (const label of ["Server", "Port", "User name", "Password", "Folder", "Server key"]) {
      expect(screen.getByLabelText(label)).toBeInTheDocument();
    }
    expect(screen.queryByLabelText("Allowed addresses")).toBeNull();
  });

  it("shows the password only as its hint, and the box starts empty", async () => {
    mount();
    expect(await screen.findByText(/••••real/)).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toHaveValue("");
  });

  it("Save writes the section by its own address, with the typed password", async () => {
    const writes = mount();
    const box = await screen.findByLabelText("Password");
    fireEvent.change(box, { target: { value: FAKE } });
    fireEvent.click(screen.getByRole("button", { name: "Save ✓" }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0].method).toBe("PUT");
    expect(writes[0].path).toBe("/integrations/erp_newworld/groups/send_file");
    const fields = (writes[0].body as { fields: Record<string, string> }).fields;
    expect(fields.sftp_host).toBe("sftp.city.example");
    expect(fields.sftp_password).toBe(FAKE);
    // After the save the box is emptied again: the password is not kept on screen.
    await waitFor(() => expect(screen.getByLabelText("Password")).toHaveValue(""));
    expect(document.body.textContent).not.toContain(FAKE);
  });

  it("Test connection posts to the test route and shows the result and the key", async () => {
    const writes = mount();
    fireEvent.click(await screen.findByRole("button", { name: "Test connection" }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0].path).toBe("/integrations/erp_newworld/groups/send_file/test");
    expect(await screen.findByText("Signed in and wrote a file.")).toBeInTheDocument();
    expect(screen.getByText("SHA256:fakefakefake")).toBeInTheDocument();
  });
});
