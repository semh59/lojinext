import { Link } from "react-router-dom";
import { Home, MoveLeft } from "lucide-react";
import { usePageTitle } from "../hooks/usePageTitle";

export default function NotFoundPage() {
  usePageTitle("Sayfa Bulunamadı");

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-base px-6 text-center">
      <p className="text-[120px] font-bold leading-none text-accent/20 select-none">
        404
      </p>
      <h1 className="mt-4 text-2xl font-bold text-primary">Sayfa Bulunamadı</h1>
      <p className="mt-2 max-w-sm text-sm text-secondary">
        Aradığınız sayfa mevcut değil ya da taşınmış olabilir.
      </p>
      <div className="mt-8 flex items-center gap-3">
        <button
          onClick={() => window.history.back()}
          className="flex items-center gap-2 rounded-xl border border-border bg-surface px-5 py-2.5 text-sm font-semibold text-secondary hover:bg-elevated transition-colors"
        >
          <MoveLeft size={16} />
          Geri Dön
        </button>
        <Link
          to="/trips"
          className="flex items-center gap-2 rounded-xl bg-accent px-5 py-2.5 text-sm font-semibold text-white hover:bg-accent/90 transition-colors"
        >
          <Home size={16} />
          Ana Sayfa
        </Link>
      </div>
    </div>
  );
}
