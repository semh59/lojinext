import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Loader2, Trash2, X } from "lucide-react";
import { safeHref } from "../../lib/utils";
import {
  investigationService,
  type InvestigationStatus,
  type ResolutionType,
} from "../../api/investigations";
import { useNotify } from "../../context/NotificationContext";
import { useInvestigationsResources } from "../../resources/useResources";
import { useTranslation } from "react-i18next";

interface InvestigationDetailDialogProps {
  investigationId: number | null;
  onClose: () => void;
}

const STATUS_OPTIONS: InvestigationStatus[] = [
  "open",
  "assigned",
  "investigating",
  "resolved",
  "closed",
];
const RESOLUTION_OPTIONS: ResolutionType[] = [
  "real_theft",
  "false_alarm",
  "data_error",
  "inconclusive",
];

export function InvestigationDetailDialog({
  investigationId,
  onClose,
}: InvestigationDetailDialogProps) {
  const { t } = useTranslation();
  const { investigationsText } = useInvestigationsResources();
  const queryClient = useQueryClient();
  const { notify } = useNotify();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["investigations", "detail", investigationId],
    queryFn: () => investigationService.get(investigationId!),
    enabled: investigationId !== null,
    staleTime: 30 * 1000,
  });

  const [draft, setDraft] = useState<{
    status?: InvestigationStatus;
    notes?: string;
    resolution_type?: ResolutionType;
    evidence_files?: string[];
    assigned_to_user_id?: number;
  }>({});
  const [newEvidence, setNewEvidence] = useState("");

  useEffect(() => {
    // Modal her açılışta draft'ı sıfırla
    if (data) {
      setDraft({});
      setNewEvidence("");
    }
  }, [data]);

  const update = useMutation({
    mutationFn: () => investigationService.update(data!.id, draft),
    onSuccess: () => {
      notify(
        "success",
        t("investigations.updated_title"),
        investigationsText.successUpdate,
      );
      queryClient.invalidateQueries({ queryKey: ["investigations"] });
      onClose();
    },
    onError: (err: any) => {
      const detail =
        err?.response?.data?.error?.message ??
        err?.response?.data?.detail ??
        investigationsText.errorUpdate;
      notify("error", t("investigations.error_title"), detail);
    },
  });

  const closeMutation = useMutation({
    mutationFn: () => investigationService.close(data!.id),
    onSuccess: () => {
      notify(
        "success",
        t("investigations.closed_title"),
        investigationsText.successClose,
      );
      queryClient.invalidateQueries({ queryKey: ["investigations"] });
      onClose();
    },
  });

  if (investigationId === null) return null;

  const inv = data;
  const currentStatus = (draft.status ?? inv?.status) as
    | InvestigationStatus
    | undefined;
  const currentResolution = (draft.resolution_type ?? inv?.resolution_type) as
    | ResolutionType
    | undefined;
  const evidenceList = draft.evidence_files ?? inv?.evidence_files ?? [];
  const isClosed = inv?.status === "closed";

  const handleAddEvidence = () => {
    const url = newEvidence.trim();
    if (!url) return;
    if (!safeHref(url)) {
      notify(
        "warning",
        t("investigations.invalid_url_title"),
        t("investigations.invalid_url_hint"),
      );
      return;
    }
    if (evidenceList.length >= 10) {
      notify(
        "warning",
        t("investigations.limit_title"),
        t("investigations.limit_hint"),
      );
      return;
    }
    setDraft((d) => ({
      ...d,
      evidence_files: [...evidenceList, url],
    }));
    setNewEvidence("");
  };

  const handleRemoveEvidence = (idx: number) => {
    setDraft((d) => ({
      ...d,
      evidence_files: evidenceList.filter((_, i) => i !== idx),
    }));
  };

  const handleSave = () => {
    // Boş draft → no-op
    if (Object.keys(draft).length === 0) {
      onClose();
      return;
    }
    update.mutate();
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
      <div className="relative flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-modal border border-border bg-surface shadow-2xl">
        <div className="flex items-center justify-between border-b border-border bg-elevated/40 p-4">
          <div>
            <h3 className="text-sm font-semibold text-primary">
              {t("investigations.detail_title", { id: investigationId })}
            </h3>
            {inv && (
              <p className="text-[11px] text-secondary">
                {inv.plaka ?? "—"}
                {inv.sofor_adi ? ` · ${inv.sofor_adi}` : ""}
                {inv.sapma_yuzde != null &&
                  ` · sapma ${
                    inv.sapma_yuzde > 0 ? "+" : ""
                  }${inv.sapma_yuzde.toFixed(1)}%`}
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            className="rounded-full p-1.5 text-secondary transition-colors hover:bg-elevated hover:text-primary"
            aria-label={t("common.close")}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="custom-scrollbar flex-1 space-y-4 overflow-y-auto p-5">
          {isLoading ? (
            <div className="flex items-center gap-2 py-6 text-secondary">
              <Loader2 className="h-4 w-4 animate-spin" />
              {t("common.loading")}
            </div>
          ) : isError || !inv ? (
            <div className="flex items-center gap-2 rounded-card border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
              <AlertCircle className="h-4 w-4" />
              {investigationsText.errorUpdate}
            </div>
          ) : (
            <>
              {isClosed && (
                <div className="flex items-center gap-2 rounded-card border border-warning/30 bg-warning/5 px-3 py-2 text-xs text-warning">
                  <AlertCircle className="h-3.5 w-3.5" />
                  {t("investigations.closed_warning")}
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <Field label={investigationsText.fields.status}>
                  <select
                    value={currentStatus}
                    onChange={(e) =>
                      setDraft((d) => ({
                        ...d,
                        status: e.target.value as InvestigationStatus,
                      }))
                    }
                    disabled={isClosed}
                    className="input-base !h-8 text-xs"
                  >
                    {STATUS_OPTIONS.map((s) => (
                      <option key={s} value={s}>
                        {investigationsText.columnLabels[s]}
                      </option>
                    ))}
                  </select>
                </Field>

                <Field label={investigationsText.fields.assigned}>
                  <input
                    type="number"
                    min={1}
                    value={
                      draft.assigned_to_user_id ?? inv.assigned_to_user_id ?? ""
                    }
                    onChange={(e) =>
                      setDraft((d) => ({
                        ...d,
                        assigned_to_user_id: e.target.value
                          ? Number(e.target.value)
                          : undefined,
                      }))
                    }
                    disabled={isClosed}
                    placeholder="user_id"
                    className="input-base !h-8 text-xs"
                  />
                </Field>
              </div>

              <Field label={investigationsText.fields.resolution}>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      setDraft((d) => ({ ...d, resolution_type: undefined }))
                    }
                    disabled={isClosed}
                    className={`rounded-card border px-2 py-1 text-[10px] font-semibold ${
                      !currentResolution
                        ? "border-accent/40 bg-accent/10 text-accent"
                        : "border-border text-secondary hover:bg-elevated"
                    }`}
                  >
                    {t("investigations.no_resolution")}
                  </button>
                  {RESOLUTION_OPTIONS.map((r) => (
                    <button
                      key={r}
                      type="button"
                      onClick={() =>
                        setDraft((d) => ({ ...d, resolution_type: r }))
                      }
                      disabled={isClosed}
                      className={`rounded-card border px-2 py-1 text-[10px] font-semibold ${
                        currentResolution === r
                          ? "border-accent/40 bg-accent/10 text-accent"
                          : "border-border text-secondary hover:bg-elevated"
                      }`}
                    >
                      {investigationsText.resolutionLabels[r]}
                    </button>
                  ))}
                </div>
              </Field>

              <Field label={investigationsText.fields.notes}>
                <textarea
                  rows={4}
                  value={draft.notes ?? inv.notes ?? ""}
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, notes: e.target.value }))
                  }
                  disabled={isClosed}
                  placeholder={t("investigations.notes_placeholder")}
                  maxLength={4000}
                  className="input-base text-sm"
                />
              </Field>

              <Field label={investigationsText.fields.evidence}>
                <div className="space-y-1.5">
                  {evidenceList.length === 0 && (
                    <p className="text-[11px] text-tertiary">
                      {t("investigations.no_evidence")}
                    </p>
                  )}
                  {evidenceList.map((url, idx) => (
                    <div
                      key={idx}
                      className="flex items-center gap-2 rounded-card border border-border/50 bg-elevated/30 px-2 py-1"
                    >
                      <a
                        href={safeHref(url)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex-1 truncate font-mono text-[11px] text-info hover:underline"
                      >
                        {url}
                      </a>
                      {!isClosed && (
                        <button
                          onClick={() => handleRemoveEvidence(idx)}
                          className="rounded p-1 text-secondary hover:bg-danger/10 hover:text-danger"
                          aria-label={t("common.delete")}
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      )}
                    </div>
                  ))}
                  {!isClosed && evidenceList.length < 10 && (
                    <div className="flex gap-2">
                      <input
                        type="url"
                        value={newEvidence}
                        onChange={(e) => setNewEvidence(e.target.value)}
                        placeholder="https://..."
                        className="input-base !h-8 text-xs"
                      />
                      <button
                        type="button"
                        onClick={handleAddEvidence}
                        disabled={!newEvidence.trim()}
                        className="shrink-0 rounded-card border border-border px-3 text-xs font-semibold text-primary hover:bg-elevated disabled:opacity-50"
                      >
                        {investigationsText.actions.addEvidence}
                      </button>
                    </div>
                  )}
                </div>
              </Field>
            </>
          )}
        </div>

        {inv && !isClosed && (
          <div className="flex items-center justify-between gap-2 border-t border-border bg-elevated/40 p-3">
            <button
              type="button"
              onClick={() => {
                if (window.confirm(investigationsText.confirmClose)) {
                  closeMutation.mutate();
                }
              }}
              disabled={closeMutation.isPending}
              className="rounded-card border border-danger/30 bg-danger/5 px-3 py-1.5 text-xs font-semibold text-danger hover:bg-danger/10 disabled:opacity-50"
            >
              {investigationsText.actions.delete}
            </button>
            <div className="flex gap-2">
              <button
                onClick={onClose}
                disabled={update.isPending}
                className="rounded-card px-3 py-1.5 text-xs font-semibold text-secondary hover:bg-elevated hover:text-primary disabled:opacity-50"
              >
                {investigationsText.actions.cancel}
              </button>
              <button
                onClick={handleSave}
                disabled={update.isPending}
                className="inline-flex items-center gap-2 rounded-card bg-accent px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-accent/90 disabled:opacity-50"
              >
                {update.isPending && (
                  <Loader2 className="h-3 w-3 animate-spin" />
                )}
                {investigationsText.actions.save}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <p className="mb-1 text-[10px] font-bold uppercase tracking-wider text-secondary">
        {label}
      </p>
      {children}
    </div>
  );
}
