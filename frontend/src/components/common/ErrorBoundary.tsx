import { Component, ErrorInfo, ReactNode } from "react";
import { AlertTriangle, RefreshCw, Home } from "lucide-react";
import { errorTracker } from "../../services/error-tracker";

interface Props {
  children?: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught error:", error, errorInfo);
    errorTracker.capture(error, {
      componentStack: errorInfo.componentStack || undefined,
      severity: "fatal",
    });
  }

  private handleReset = () => {
    this.setState({ hasError: false });
    window.location.reload();
  };

  private handleGoHome = () => {
    this.setState({ hasError: false });
    window.location.href = "/";
  };

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <div className="min-h-screen flex items-center justify-center p-6 bg-base relative overflow-hidden">
          {/* Background decorations */}
          <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-danger/5 blur-[120px] rounded-full pointer-events-none" />
          <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-accent/5 blur-[120px] rounded-full pointer-events-none" />

          <div className="relative max-w-lg w-full bg-surface/40 backdrop-blur-xl border border-white/10 p-10 rounded-[40px] text-center shadow-2xl animate-fade-in">
            <div className="w-24 h-24 bg-danger/10 border border-danger/20 rounded-3xl flex items-center justify-center mx-auto mb-8 rotate-3 shadow-lg shadow-danger/5">
              <AlertTriangle className="w-12 h-12 text-danger" />
            </div>

            <h1 className="text-3xl font-bold text-primary mb-4 tracking-tight">
              Sistem Kesintisi
            </h1>

            <p className="text-secondary mb-10 leading-relaxed text-lg px-4 font-medium opacity-80">
              Beklenmedik bir hata tespit edildi. Veri güvenliğiniz için oturum
              askıya alındı. Teknik ekip anlık olarak bilgilendirildi.
            </p>

            <div className="grid grid-cols-1 gap-4">
              <button
                onClick={this.handleReset}
                className="group relative h-14 bg-accent hover:bg-accent-hover text-white font-bold rounded-2xl transition-all shadow-lg shadow-accent/20 flex items-center justify-center gap-3 overflow-hidden active:scale-[0.98]"
              >
                <RefreshCw className="w-5 h-5 group-hover:rotate-180 transition-transform duration-500" />
                <span className="relative z-10">Sistemi Yeniden Başlat</span>
                <div className="absolute inset-0 bg-gradient-to-r from-white/0 via-white/10 to-white/0 translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-1000" />
              </button>

              <button
                onClick={this.handleGoHome}
                className="h-14 bg-surface hover:bg-elevated border border-border text-secondary hover:text-primary font-bold rounded-2xl transition-all flex items-center justify-center gap-3 active:scale-[0.98]"
              >
                <Home className="w-5 h-5" />
                Ana Sayfaya Dön
              </button>
            </div>

            {import.meta.env.DEV && (
              <div className="mt-10 p-6 bg-black/20 border border-white/5 rounded-2xl text-left overflow-auto max-h-48 custom-scrollbar group">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-[10px] font-bold text-danger uppercase tracking-widest opacity-60">
                    Geliştirici Detayları
                  </span>
                  <span className="text-[10px] bg-danger/10 text-danger px-2 py-0.5 rounded-full font-bold">
                    CRITICAL
                  </span>
                </div>
                <p className="text-xs font-mono text-danger/90 leading-relaxed break-all">
                  {this.state.error?.toString()}
                </p>
                {this.state.error?.stack && (
                  <p className="text-[10px] font-mono text-secondary mt-3 leading-relaxed whitespace-pre opacity-40 group-hover:opacity-100 transition-opacity">
                    {this.state.error.stack}
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
