import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  name: string;
  children: ReactNode;
}
interface State {
  error: Error | null;
}

/** Isolates a section: if it throws, show the error here instead of crashing
 *  the whole page. Lets the rest of the dashboard keep working. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[${this.props.name}] crashed:`, error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="card" style={{ borderColor: "var(--bad)" }}>
          <div className="card-title" style={{ color: "var(--bad)" }}>
            {this.props.name} — render error (rest of dashboard still works)
          </div>
          <p className="muted-txt" style={{ fontFamily: "monospace", fontSize: 12 }}>
            {this.state.error.message}
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}
