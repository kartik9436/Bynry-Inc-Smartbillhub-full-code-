// ── Trace ──────────────────────────────────────────────
// Change:   CR-162-BRC10 items 9 and 48 (Q3) — the To-do tab, with notes.
// Ruling:   decision log 2026-10-02 (commit 56eb54ba9), Q3: *"a To-do tab
//           replaces Mark/Close outstanding"* — *"+ Add a to-do, per-row Done,
//           reopen; Overview summary"* — and the PO the same day, verbatim:
//           *"in to do also keep notes - allow user to add notes"*.
// Server:   `GET /connections/{id}/todos` · `POST …/outstanding-work`
//           (`kind`) · `…/close` · `…/reopen` · `…/edit`
//           (apps/metering/connections.py, `BR-MET-114`).
// Rules:    BR-MET-114 (a person writes and closes; nothing blocks) ·
//           B14 rule 15 (row actions are icons) · rule 20 (one table type) ·
//           rule 31 (who, never an id) · rule 33 · rule 43 · rule 21
// ───────────────────────────────────────────────────────
/**
 * **To-dos and notes together, newest first, each saying which it is.**
 *
 * ⚠ **NOT THE ACCOUNT'S NOTES TAB, AND THAT WAS LOOKED FOR FIRST.** The PO's
 * *"reuse account Notes if present"* names a real component
 * (`AccountNotesTab`) over `account_notes` — and a build often has no account
 * to hang a note on (a single-family home opens none, Q1), so the storage is
 * the build's own to-do list with `kind = note` (`metering/0065`). The SHAPE is
 * the account notes' convention: who and when on every row, an edit only by
 * the author, audited, and no delete.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/Button";
import { DateCell } from "@/components/DateCell";
import { FormModal, SegmentedField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { CommitIcon, PencilIcon, RollBackIcon } from "@/components/icons";
import { RowAction, RowActions } from "@/components/RowActions";
import { PlainTable } from "@/components/Surfaces";
import {
  addBuildTodo,
  editBuildNote,
  getBuildTodos,
  reopenBuildTodo,
  todosQueryKey,
} from "@/features/customers/buildLifecycleEndpoints";
import type { BuildTodoRow } from "@/features/customers/buildLifecycleEndpoints";
import { closeOutstandingWork, connectionDetailQueryKey } from "@/features/customers/newConnectEndpoints";
import type { Translator } from "@/features/customers/newConnectShared";
import { z } from "zod";

import { Section } from "./buildTabShell";
import type { BuildTabProps } from "./buildTabShell";

const TEXT_SCHEMA = z.object({ text: z.string().trim().min(1), kind: z.string() });

/** The Overview's one line — *"2 to-dos open"*, or nothing at all. */
export function todoSummary(open: number, t: Translator): string | null {
  if (open <= 0) {
    return null;
  }
  return t("customers.build.todo.summary", { count: open, defaultValue: `To-dos open: ${open}` });
}

function kindWord(row: BuildTodoRow, t: Translator): string {
  return row.kind === "note"
    ? t("customers.build.todo.kindNote", { defaultValue: "Note" })
    : t("customers.build.todo.kindTodo", { defaultValue: "To-do" });
}

export function BuildTodoTab(props: BuildTabProps) {
  const { t, detail } = props;
  const queryClient = useQueryClient();
  const list = useQuery({
    queryKey: todosQueryKey(detail.id),
    queryFn: () => getBuildTodos(detail.id, props.client),
    retry: false,
  });
  const [adding, setAdding] = useState<"todo" | "note" | null>(null);
  const [editing, setEditing] = useState<BuildTodoRow | null>(null);
  const cancelled = detail.state === "cancelled";

  function refresh(): void {
    void queryClient.invalidateQueries({ queryKey: todosQueryKey(detail.id) });
    void queryClient.invalidateQueries({ queryKey: connectionDetailQueryKey(detail.id) });
  }

  const act = useMutation<unknown, unknown, { row: BuildTodoRow; to: "done" | "reopen" }>({
    mutationFn: ({ row, to }) =>
      to === "done"
        ? closeOutstandingWork(detail.id, row.id, props.client)
        : reopenBuildTodo(detail.id, row.id, props.client),
    onSettled: refresh,
  });

  const rows = list.data?.rows ?? [];

  return (
    <Section id="todos" title={t("customers.build.todo.title", { defaultValue: "To-dos and notes" })}>
      <div className="mb-3 flex flex-wrap gap-2" data-todo-actions="">
        <Button
          variant="secondary"
          data-act="addTodo"
          disabled={cancelled || Boolean(props.readOnlyReason)}
          title={props.readOnlyReason ?? undefined}
          data-blocked-reason={props.readOnlyReason ?? undefined}
          onClick={() => setAdding("todo")}
        >
          {t("customers.build.todo.addTodo", { defaultValue: "+ Add a to-do" })}
        </Button>
        <Button
          variant="secondary"
          data-act="addNote"
          disabled={cancelled || Boolean(props.readOnlyReason)}
          title={props.readOnlyReason ?? undefined}
          data-blocked-reason={props.readOnlyReason ?? undefined}
          onClick={() => setAdding("note")}
        >
          {t("customers.build.todo.addNote", { defaultValue: "+ Add a note" })}
        </Button>
      </div>
      {list.isPending ? (
        <p className="text-sm text-neutral-700">
          {t("customers.build.units.loading", { defaultValue: "Loading…" })}
        </p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-neutral-700" data-build-empty="todos">
          {t("customers.build.todo.none", { defaultValue: "No to-dos or notes yet." })}
        </p>
      ) : (
        <PlainTable data-table="build-todos">
          <thead>
            <tr>
              <th>{t("customers.build.todo.col.when", { defaultValue: "When" })}</th>
              <th>{t("customers.build.todo.col.kind", { defaultValue: "Kind" })}</th>
              <th>{t("customers.build.todo.col.what", { defaultValue: "What" })}</th>
              <th>{t("customers.build.todo.col.who", { defaultValue: "Who" })}</th>
              <th>{t("customers.build.todo.col.state", { defaultValue: "State" })}</th>
              <th>{t("customers.build.units.col.actions", { defaultValue: "Actions" })}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} data-todo-row={row.kind} data-todo-done={row.done ? "true" : "false"}>
                <td>
                  <DateCell
                    value={row.written_at}
                    timeZone={props.timeZone}
                    dateFormat={props.dateFormat}
                  />
                </td>
                <td>{kindWord(row, t)}</td>
                <td>{row.title}</td>
                <td>{row.written_by}</td>
                <td>
                  {row.kind === "note"
                    ? null
                    : row.done
                      ? t("customers.build.todo.done", { defaultValue: "Done" })
                      : t("customers.build.todo.open", { defaultValue: "Open" })}
                </td>
                <td>
                  <RowActions>
                    {row.kind === "todo" && !row.done && (
                      <RowAction
                        label={t("customers.build.todo.markDone", { defaultValue: "Mark done" })}
                        icon={<CommitIcon />}
                        reason={cancelled ? t("customers.connection.act.whyCancelled") : null}
                        testId={`todo-done-${row.id}`}
                        onClick={() => act.mutate({ row, to: "done" })}
                      />
                    )}
                    {row.kind === "todo" && row.done && (
                      <RowAction
                        label={t("customers.build.todo.reopen", { defaultValue: "Reopen" })}
                        icon={<RollBackIcon />}
                        reason={cancelled ? t("customers.connection.act.whyCancelled") : null}
                        testId={`todo-reopen-${row.id}`}
                        onClick={() => act.mutate({ row, to: "reopen" })}
                      />
                    )}
                    {row.kind === "note" && row.mine && (
                      <RowAction
                        label={t("customers.build.todo.editNote", { defaultValue: "Edit note" })}
                        icon={<PencilIcon />}
                        reason={cancelled ? t("customers.connection.act.whyCancelled") : null}
                        testId={`note-edit-${row.id}`}
                        onClick={() => setEditing(row)}
                      />
                    )}
                  </RowActions>
                </td>
              </tr>
            ))}
          </tbody>
        </PlainTable>
      )}
      {(adding !== null || editing !== null) && (
        <TodoForm
          t={t}
          kind={editing !== null ? "note" : (adding ?? "todo")}
          initial={editing?.title ?? ""}
          editing={editing !== null}
          onClose={() => {
            setAdding(null);
            setEditing(null);
          }}
          onSave={async (kind, text) => {
            if (editing !== null) {
              await editBuildNote(detail.id, editing.id, text, props.client);
            } else {
              await addBuildTodo(detail.id, { title: text, kind }, props.client);
            }
            setAdding(null);
            setEditing(null);
            refresh();
            return { ok: true };
          }}
        />
      )}
    </Section>
  );
}

function TodoForm(props: {
  t: Translator;
  kind: "todo" | "note";
  initial: string;
  editing: boolean;
  onClose: () => void;
  onSave: (kind: "todo" | "note", text: string) => Promise<FormSubmitOutcome>;
}) {
  const { t } = props;
  const [text, setText] = useState(props.initial);
  const [kind, setKind] = useState<"todo" | "note">(props.kind);
  const title = props.editing
    ? t("customers.build.todo.editNote", { defaultValue: "Edit note" })
    : kind === "note"
      ? t("customers.build.todo.addNoteTitle", { defaultValue: "Add a note" })
      : t("customers.build.todo.addTodoTitle", { defaultValue: "Add a to-do" });
  return (
    <FormModal
      title={title}
      schema={TEXT_SCHEMA}
      values={{ text, kind }}
      submitLabel={t("customers.build.todo.save", { defaultValue: "Save" })}
      onClose={props.onClose}
      onSubmit={() => props.onSave(kind, text.trim())}
    >
      {!props.editing && (
        <SegmentedField
          id="kind"
          label={t("customers.build.todo.col.kind", { defaultValue: "Kind" })}
          value={kind}
          options={[
            { value: "todo", label: t("customers.build.todo.kindTodo", { defaultValue: "To-do" }) },
            { value: "note", label: t("customers.build.todo.kindNote", { defaultValue: "Note" }) },
          ]}
          onChange={(value) => setKind(value === "note" ? "note" : "todo")}
        />
      )}
      <TextField
        id="text"
        label={t("customers.build.todo.col.what", { defaultValue: "What" })}
        required
        value={text}
        onChange={setText}
      />
    </FormModal>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-162-BRC10 (Q3; PO 2026-10-02 notes)
// generated: 2026-10-02 by lane NC-A
// gates: G31 (route-b-migrated.txt) · G13 (mounted by BuildDetailPage's BuildTabBody)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
