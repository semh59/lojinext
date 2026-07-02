import { AlertTriangle, Trash2 } from "lucide-react";

import { cn } from "../../lib/utils";
import { Button } from "./Button";
import { Modal } from "./Modal";

interface DeleteConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void | Promise<void>;
  title: string;
  description: string;
  confirmLabel: string;
  cancelLabel: string;
  /** "danger" (hard delete) or "warning" (soft delete / deactivate) styling. */
  variant?: "danger" | "warning";
  isConfirming?: boolean;
}

/**
 * 2026-07-02 prod-grade denetimi P2 (Tier B madde 10): `VehicleDeleteModal`
 * ve `TrailerDeleteModal` neredeyse birebir aynı overlay/ikon/başlık/buton
 * markup'ını kopya-yapıştır tutuyordu ve `ui/Modal.tsx`'in (focus-trap,
 * aria-modal) hiçbirini kullanmıyordu. Bu paylaşılan bileşen ikisinin de
 * temelini oluşturur — domain-özel modaller kendi prop sözleşmelerini
 * korurken bu bileşene delege eder.
 */
export function DeleteConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  title,
  description,
  confirmLabel,
  cancelLabel,
  variant = "danger",
  isConfirming = false,
}: DeleteConfirmModalProps) {
  const isWarning = variant === "warning";

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="sm">
      <div className="text-center">
        <div
          className={cn(
            "mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-2xl",
            isWarning
              ? "bg-warning/10 text-warning"
              : "bg-danger/10 text-danger",
          )}
        >
          {isWarning ? (
            <AlertTriangle className="h-10 w-10" />
          ) : (
            <Trash2 className="h-10 w-10" />
          )}
        </div>

        <h2 className="mb-2 text-2xl font-black text-primary">{title}</h2>

        <p className="mb-8 font-medium leading-relaxed text-secondary">
          {description}
        </p>

        <div className="flex gap-3">
          <Button
            variant="secondary"
            onClick={onClose}
            disabled={isConfirming}
            className="h-12 flex-1 text-base"
          >
            {cancelLabel}
          </Button>
          <Button
            variant="danger"
            onClick={onConfirm}
            isLoading={isConfirming}
            className={cn(
              "h-12 flex-1 text-base",
              isWarning && "bg-warning text-bg-base hover:bg-warning/80",
            )}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
