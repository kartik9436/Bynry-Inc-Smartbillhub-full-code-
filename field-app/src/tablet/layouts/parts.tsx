/**
 * What the T-28 layouts share: a pane with its OWN header (the boards draw
 * every pane of a shape-changing screen with one — *Today 11 jobs*,
 * *WO-4822 ON SITE*, *Stops 38 mi*, *Assets* — so the stack's bar is hidden
 * over them, `framedScreens.tsx`), and the job read for a pane.
 */
import { useIsFocused } from '@react-navigation/native';
import { type ReactNode, useMemo } from 'react';
import { View } from 'react-native';

import { TopBar } from '../../components';
import { ScreenFrame } from '../../components/ScreenFrame';
import { useJobPort } from '../../screens/theJob/JobPort';
import { type JobView, loadJob } from '../../screens/theJob/jobModel';
import { useTheme } from '../../theme';

/** A pane: its header, a scrolling body, and its acts pinned under it. */
export function PaneScreen(props: {
  title: string;
  trailing?: ReactNode;
  onBack?: () => void;
  backLabel?: string;
  backTestID?: string;
  header?: ReactNode;
  footer?: ReactNode;
  children?: ReactNode;
  testID?: string;
}) {
  const theme = useTheme();
  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.page }} testID={props.testID}>
      <TopBar
        title={props.title}
        trailing={props.trailing}
        onBack={props.onBack}
        backLabel={props.backLabel}
        backTestID={props.backTestID}
      />
      <ScreenFrame header={props.header} footer={props.footer}>
        {props.children}
      </ScreenFrame>
    </View>
  );
}

/** A pane with a header over a body it lays out itself (a list screen, the map). */
export function HeadedPane(props: { title: string; trailing?: ReactNode; children: ReactNode; testID?: string }) {
  const theme = useTheme();
  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.page }} testID={props.testID}>
      <TopBar title={props.title} trailing={props.trailing} />
      <View style={{ flex: 1 }}>{props.children}</View>
    </View>
  );
}

/** One job, read through the job services and re-read after every capture. Null with no store or no id. */
export function useJobView(workOrderId: string | null): JobView | null {
  const port = useJobPort();
  const focused = useIsFocused();
  const version = port?.version ?? 0;
  return useMemo(
    () => (port && workOrderId ? loadJob(port, workOrderId) : null),
    // `version` and `focused` are re-read triggers.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [port, workOrderId, version, focused],
  );
}
