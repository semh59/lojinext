import { useState } from "react";
import { Download, Loader2 } from "lucide-react";

import { useNotify } from "@/context/NotificationContext";
import { executiveService } from "@/api/executive";
import { useExecutiveResources } from "@/resources/useResources";

export function DownloadPdfButton() {
  const { executiveText } = useExecutiveResources();
  const [downloading, setDownloading] = useState(false);
  const { notify } = useNotify();
  const t = executiveText.pdf;

  const handleClick = async () => {
    setDownloading(true);
    try {
      await executiveService.downloadPdf();
      notify("success", t.success);
    } catch (err: unknown) {
      const e = err as {
        response?: {
          status?: number;
          data?: { detail?: string; error?: { message?: string } };
        };
      };
      if (e?.response?.status === 404 || e?.response?.status === 501) {
        notify("warning", t.notReady);
      } else {
        const detail =
          e?.response?.data?.error?.message ?? e?.response?.data?.detail;
        notify("error", t.error, detail || t.error);
      }
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="flex justify-end">
      <button
        type="button"
        onClick={handleClick}
        disabled={downloading}
        className="inline-flex items-center gap-2 rounded-card bg-accent px-4 py-2 text-xs font-semibold text-white shadow-sm transition-all hover:bg-accent/90 disabled:opacity-50"
      >
        {downloading ? (
          <>
            <Loader2 className="h-3 w-3 animate-spin" />
            {t.downloading}
          </>
        ) : (
          <>
            <Download className="h-3 w-3" />
            {t.downloadButton}
          </>
        )}
      </button>
    </div>
  );
}
