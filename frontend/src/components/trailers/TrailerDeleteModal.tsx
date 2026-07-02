import { Dorse } from "../../types";
import { DeleteConfirmModal } from "../ui/DeleteConfirmModal";
import { useTrailersResources } from "../../resources/useResources";

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
  const { trailerDeleteText } = useTrailersResources();
  if (!trailer) {
    return null;
  }

  return (
    <DeleteConfirmModal
      isOpen={isOpen}
      onClose={onClose}
      onConfirm={onConfirm}
      isConfirming={isDeleting}
      variant="danger"
      title={trailerDeleteText.title}
      description={trailerDeleteText.description(trailer.plaka)}
      confirmLabel={trailerDeleteText.confirm}
      cancelLabel={trailerDeleteText.cancel}
    />
  );
};

export default TrailerDeleteModal;
