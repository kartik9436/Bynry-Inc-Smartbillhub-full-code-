// ── Trace ──────────────────────────────────────────────
// **B14 rule 43's named surface.** The rule points at
// `apps/tenancy/document_store.py` as the shape to aim for — *"a named surface
// (`store`, `for_source`, `reference`, `fetch`, `download_url`) with callers in
// two modules"*. This is that surface on the front end: one import path, and
// the test of whether a block is a component is whether a sibling screen can
// reach it without copying it.
// ───────────────────────────────────────────────────────
export { DocumentCapture } from "./DocumentCapture";
export { DocumentCaptureForm } from "./DocumentCaptureForm";
export type { DocumentTypeOption } from "./DocumentCaptureForm";
export { DocumentStateCell, documentVerdict } from "./DocumentStateCell";
export type { DocumentVerdict } from "./DocumentStateCell";
export { DocumentTable } from "./DocumentTable";
export {
  DOCUMENT_ACCEPT,
  DOCUMENT_FILTERS,
  REJECT_REASON_ROW_CHARS,
  documentFileType,
  emptyDocumentCapture,
  filterDocumentRows,
  formatDocumentSize,
  refusedFileExtension,
  shortReason,
} from "./documentCapture";
export type {
  DocumentCaptureValue,
  DocumentFilter,
  DocumentRequiredOf,
  DocumentRow,
  DocumentTranslator,
} from "./documentCapture";
export {
  DOCUMENT_LINK_NOT_BROWSABLE,
  documentContentUrl,
  isBrowsableDocumentUrl,
  openDocumentContent,
  openStoredDocument,
} from "./openStoredDocument";
export type { DocumentContentMode, StoredDocumentLink } from "./openStoredDocument";
