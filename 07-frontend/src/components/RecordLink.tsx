// RecordLink — a record shown by its label opens that record, when it can.
//
// Record links (PO ruling 2026-10-19, decision log "Record links (navigation
// design)"): wherever a premises, unit, plan, asset, account, bill, payment,
// work order … is shown as text and a detail page exists, the text is a link
// to it. A row does not always carry the id that addresses the record, so the
// one honest fallback is the same text, unlinked — never a link to a guessed
// or filtered destination.
//
// ⚠ IT IS `InlineLinkTo` WITH A NULL CASE AND NOTHING ELSE (B14 rule 43): the
// look, the focus ring and the `data-inlinelink` hook are `InlineLinkTo`'s, so
// a record link cannot drift from every other identity link in the product.
// Absence of the LABEL is the caller's to draw (each screen has its own dash).
import type { ReactNode } from "react";
import { InlineLinkTo } from "./Surfaces";

export function RecordLink(props: { to: string | null | undefined; className?: string; children: ReactNode }) {
  if (props.to === null || props.to === undefined || props.to === "") {
    return props.className === undefined ? <>{props.children}</> : <span className={props.className}>{props.children}</span>;
  }
  return (
    <InlineLinkTo to={props.to} className={props.className}>
      {props.children}
    </InlineLinkTo>
  );
}
