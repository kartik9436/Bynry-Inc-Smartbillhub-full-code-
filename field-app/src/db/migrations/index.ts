/**
 * Every migration, in order. Numbered forward-only like the server's
 * (`06-backend/apps/<module>/migrations`): append a new file, never edit a shipped
 * one — a technician may carry the old build for days (Mobile data §9).
 */
import { m0001 } from './0001_initial';
import { m0002 } from './0002_document_help';
import { m0003 } from './0003_reading_kind_text';
import { m0004 } from './0004_read_formats';
import { m0005 } from './0005_outbox_work_order_number';
import { m0006 } from './0006_photo_route_read';
import { m0007 } from './0007_route_read_lower_than_last';
import type { Migration } from './types';

export const MIGRATIONS: readonly Migration[] = [m0001, m0002, m0003, m0004, m0005, m0006, m0007];

export type { Migration } from './types';
