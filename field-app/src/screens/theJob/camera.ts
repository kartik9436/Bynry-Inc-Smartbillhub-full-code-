/**
 * The job screens' camera, shrink and file picker. They are the APP's, not
 * this wave's: since the integration lane they live in `src/device/photo.ts`,
 * one set every wave reads, and this file re-exports them so the job screens
 * and their tests import from where they always did.
 */
export * from '../../device/photo';
