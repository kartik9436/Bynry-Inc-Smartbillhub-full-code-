/**
 * Catches a render crash in the tree below it and writes it to the crash file
 * through the scrubber, with React's component stack (component NAMES only —
 * props and text never leave). What the technician sees instead is the
 * `fallback`, which the screen lane draws; this component draws nothing of its own.
 */
import { Component, type ErrorInfo, type ReactNode } from 'react';
import type { CrashCapture } from './crashReporter';

interface Props {
  capture: CrashCapture;
  /** The FF/RW id of the screen this boundary wraps. */
  screen?: string;
  fallback?: ReactNode;
  children?: ReactNode;
}

interface State {
  failed: boolean;
}

export class TelemetryErrorBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    this.props.capture.record({
      error,
      fatal: false,
      screen: this.props.screen,
      componentStack: info.componentStack ?? undefined,
    });
  }

  render(): ReactNode {
    return this.state.failed ? (this.props.fallback ?? null) : this.props.children;
  }
}
