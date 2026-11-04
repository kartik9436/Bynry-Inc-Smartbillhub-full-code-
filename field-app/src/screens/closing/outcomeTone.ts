/**
 * The tone each close outcome is drawn in — FF-35's strip, its record's chip
 * and the tablet's detail. Its own file so the list (`CompletedScreen`) and
 * the record (`CompletedRecord`) share it without importing each other.
 */
import type { StatusTone } from '../../theme';

export const OUTCOME_TONE: Record<string, StatusTone> = {
  passed: 'success',
  partially_done: 'warning',
  failed: 'danger',
  waiting_on_someone_else: 'warning',
};
