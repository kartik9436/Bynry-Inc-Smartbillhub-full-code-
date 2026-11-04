/**
 * The native component kit (task T-07). A screen imports from here; it never
 * defines a control inline (Stack page: "components/ the kit. A screen
 * imports; it never defines a control inline"; B14 rule 43).
 *
 * Every component reads its colours and sizes from `useTheme()` and nothing
 * else — `tests/components/noLiterals.test.ts` fails a hex colour or a pixel
 * literal anywhere in this folder.
 */
export { AppText, Kicker, textStyle } from './AppText';
export type { AppTextProps, TextVariant, TextWeight, TextTone } from './AppText';
export { Button, IconButton, buttonHeight } from './Button';
export type { ButtonProps, ButtonVariant, ButtonSize } from './Button';
export { Field, FieldGroup } from './Field';
export type { FieldProps, FieldTone } from './Field';
export { Card } from './Card';
export type { CardProps, CardTone } from './Card';
export { ListRow } from './ListRow';
export type { ListRowProps } from './ListRow';
export { StatusChip, StatusPill } from './StatusChip';
export type { StatusChipProps, StatusTone } from './StatusChip';
export { Notice } from './Notice';
export type { NoticeTone } from './Notice';
export { Sheet } from './Sheet';
export type { SheetProps } from './Sheet';
export { EmptyState } from './EmptyState';
export type { EmptyStateProps } from './EmptyState';
export {
  ToastProvider,
  ToastSurface,
  createToastQueue,
  useToast,
  useToastIfMounted,
  TOAST_DISMISS_MS,
} from './Toast';
export type { ToastQueue } from './Toast';
export { TopBar } from './TopBar';
export type { TopBarProps } from './TopBar';
export { ChoiceChips } from './ChoiceChips';
export type { ChoiceChipsProps, Segment } from './ChoiceChips';
export { Stepper } from './Stepper';
export type { StepperProps } from './Stepper';
export { Glyph } from './Glyph';
export type { GlyphName } from './Glyph';
// Added by the job screens (T-18, T-19).
export { SheetScreen } from './SheetScreen';
export type { SheetScreenProps } from './SheetScreen';
export { PhotoThumb } from './PhotoThumb';
export type { PhotoThumbProps } from './PhotoThumb';
export { DashedButton } from './DashedButton';
export type { DashedButtonProps } from './DashedButton';
export { CheckRow } from './CheckRow';
export type { CheckRowProps, CheckRowTapProps, CheckRowProgressProps, CheckState } from './CheckRow';
export { ProgressBar } from './ProgressBar';
export type { ProgressBarProps } from './ProgressBar';
export { Initials } from './Initials';
export { ToggleRow } from './ToggleRow';
export type { ToggleRowProps } from './ToggleRow';
// Added by the me wave (T-23..T-26).
export { Avatar, initialsOf } from './Avatar';
export type { AvatarProps } from './Avatar';
export { Dot } from './Dot';
export { Meter } from './Meter';
export type { MeterPart, MeterProps } from './Meter';
export { SyncChip } from './SyncChip';
export { AlarmSurface, AlarmText, AlarmPanel, AlarmCallout, AlarmButton } from './Alarm';
export type { SyncChipProps } from './SyncChip';
// Added by the screen waves gettingIn / theDay (T-15, T-16): blocks drawn on
// more than one board, so they are components rather than screen code.
export { Page } from './Page';
export type { PageProps } from './Page';
export { SegmentTabs } from './SegmentTabs';
export type { SegmentTab, SegmentTabsProps } from './SegmentTabs';
export { IconCircle } from './IconCircle';
export type { IconCircleProps } from './IconCircle';
export { Figure } from './Figure';
export type { FigureProps, FigureTone } from './Figure';
export { SyncStrip } from './SyncStrip';
export type { SyncStripProps } from './SyncStrip';
// Added by the reads wave (RW-01…RW-29): blocks that repeat across its screens.
// (ProgressBar, RadioList and ToggleRow were already in the kit from other
// waves; each is ONE component serving every caller, exported once.)
export { RadioList } from './RadioList';
export type { RadioListProps, RadioOption } from './RadioList';
export { Stat, StatRow } from './Stat';
export type { StatProps } from './Stat';
export { ActionBar } from './ActionBar';
export { Keypad, keyHeight } from './Keypad';
export type { KeypadProps, KeypadSize } from './Keypad';
// Added by the tablet lane (T-28): FF-13 T's numbered stop.
export { NumberDisc } from './NumberDisc';
// FB-030: a photograph in a record — the file, or loaded on tap from the server.
export { RecordPhoto, RemotePhotoProvider, useRemotePhoto } from './RecordPhoto';
export type { RecordPhotoProps, RemotePhotoKind, RemotePhotoPort } from './RecordPhoto';
