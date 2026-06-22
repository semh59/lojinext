import { Component, ErrorInfo, ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { motion } from "framer-motion";
import i18n from "../../i18n";

interface Props {
  children?: ReactNode;
  fallbackMessage?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    // Update state so the next render will show the fallback UI.
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught component error:", error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  public render() {
    if (this.state.hasError) {
      return (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="w-full h-full min-h-[300px] flex flex-col items-center justify-center p-8 bg-surface/50 backdrop-blur rounded-2xl border border-danger/20 shadow-sm"
        >
          <div className="w-16 h-16 rounded-full bg-danger/10 flex items-center justify-center mb-6">
            <AlertTriangle className="w-8 h-8 text-danger" />
          </div>
          <h2 className="text-xl font-bold text-primary mb-2 text-center">
            {this.props.fallbackMessage ||
              i18n.t("common.error_something_wrong", "Something went wrong")}
          </h2>
          <p className="text-sm text-secondary text-center max-w-md mb-8">
            {i18n.t(
              "common.error_boundary_desc",
              "An unexpected error occurred while loading this section. Please try refreshing the page or restarting the component.",
            )}
          </p>

          <div className="flex gap-4">
            <button
              onClick={this.handleReset}
              className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-accent text-bg-base font-medium hover:bg-accent/80 transition-colors shadow-lg shadow-accent/20 active:scale-95"
            >
              <RefreshCw className="w-4 h-4" />
              {i18n.t("common.retry", "Try Again")}
            </button>
          </div>

          {this.state.error && process.env.NODE_ENV === "development" && (
            <div className="mt-8 w-full max-w-2xl bg-elevated rounded-lg p-4 overflow-auto border border-border">
              <pre className="text-xs text-danger whitespace-pre-wrap font-mono">
                {this.state.error.toString()}
              </pre>
            </div>
          )}
        </motion.div>
      );
    }

    return this.props.children;
  }
}
