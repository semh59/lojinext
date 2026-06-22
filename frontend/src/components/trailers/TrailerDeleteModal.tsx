import { AnimatePresence, motion } from "framer-motion";
import { Trash2 } from "lucide-react";

import { Dorse } from "../../types";
import { trailerDeleteText } from "../../resources/tr/trailers";

interface TrailerDeleteModalProps {
  trailer: Dorse | null;
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  isDeleting?: boolean;
}

const TrailerDeleteModal = ({
  trailer,
  isOpen,
  onClose,
  onConfirm,
  isDeleting = false,
}: TrailerDeleteModalProps) => {
  if (!trailer) {
    return null;
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center p-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
          />

          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            className="relative w-full max-w-md overflow-hidden rounded-[2.5rem] border border-border bg-surface p-8 text-center shadow-2xl"
          >
            <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-3xl border border-danger/20 bg-danger/10 text-danger shadow-danger/10">
              <Trash2 size={40} />
            </div>

            <h2 className="mb-3 text-2xl font-bold text-primary">
              {trailerDeleteText.title}
            </h2>
            <p className="mb-8 leading-relaxed text-secondary">
              {trailerDeleteText.description(trailer.plaka)}
            </p>

            <div className="flex flex-col gap-3">
              <button
                onClick={onConfirm}
                disabled={isDeleting}
                className="flex w-full items-center justify-center gap-2 rounded-2xl bg-danger py-4 font-bold text-bg-base shadow-lg shadow-danger/20 transition-all hover:bg-danger/80 active:scale-95 disabled:opacity-50"
              >
                {isDeleting ? (
                  <div className="h-5 w-5 animate-spin rounded-full border-2 border-bg-base/30 border-t-bg-base" />
                ) : (
                  trailerDeleteText.confirm
                )}
              </button>
              <button
                onClick={onClose}
                disabled={isDeleting}
                className="w-full rounded-2xl border border-border bg-elevated py-4 font-bold text-secondary transition-all hover:bg-surface"
              >
                {trailerDeleteText.cancel}
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};

export default TrailerDeleteModal;
