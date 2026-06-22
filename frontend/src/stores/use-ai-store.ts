import { create } from "zustand";
import { persist, createJSONStorage, StateStorage } from "zustand/middleware";
import { withErrorTracking } from "../services/error-middleware";
import { ChatMessage, aiApi } from "../api/ai";
import { storageService } from "../services/storage-service";

const userScopedStorage: StateStorage = {
  getItem: (name: string) => {
    const key = storageService.getUserScopedKey(name);
    return localStorage.getItem(key);
  },
  setItem: (name: string, value: string) => {
    const key = storageService.getUserScopedKey(name);
    localStorage.setItem(key, value);
  },
  removeItem: (name: string) => {
    const key = storageService.getUserScopedKey(name);
    localStorage.removeItem(key);
  },
};

interface AiState {
  messages: ChatMessage[];
  isOpen: boolean;
  isExpanded: boolean;
  status: "offline" | "loading" | "ready" | "error";

  // Actions
  addMessage: (message: ChatMessage) => void;
  setIsOpen: (isOpen: boolean) => void;
  toggleOpen: () => void;
  setIsExpanded: (isExpanded: boolean) => void;
  toggleExpanded: () => void;
  clearHistory: () => void;
  checkStatus: () => Promise<void>;
}

export const useAiStore = create<AiState>()(
  persist(
    withErrorTracking((set, get) => ({
      messages: [
        {
          role: "assistant",
          content:
            "Merhaba! Ben LojiNext Asistan. Filo verileriniz, yakıt tüketimi veya operasyonel analizler hakkında size nasıl yardımcı olabilirim?",
        },
      ],
      isOpen: false,
      isExpanded: false,
      status: "offline",

      addMessage: (message: ChatMessage) =>
        set((state: AiState) => ({
          messages: [...state.messages, message],
        })),

      setIsOpen: (isOpen: boolean) => {
        set({ isOpen });
        if (isOpen) {
          get().checkStatus();
        }
      },
      toggleOpen: () => {
        const willOpen = !get().isOpen;
        set({ isOpen: willOpen });
        if (willOpen) {
          get().checkStatus();
        }
      },

      setIsExpanded: (isExpanded: boolean) => set({ isExpanded }),
      toggleExpanded: () =>
        set((state: AiState) => ({ isExpanded: !state.isExpanded })),

      clearHistory: () =>
        set({
          messages: [
            {
              role: "assistant",
              content:
                "Merhaba! Ben LojiNext Asistan. Filo verileriniz, yakıt tüketimi veya operasyonel analizler hakkında size nasıl yardımcı olabilirim?",
            },
          ],
        }),

      checkStatus: async () => {
        try {
          const statusData = await aiApi.getStatus();
          // Map backend status to frontend status
          // Backend returns: { is_ready: bool, progress: { status: "ready"|"downloading"|"error" } }
          // We want: 'loading' | 'ready' | 'error'
          let newStatus: "loading" | "ready" | "error" = "loading";

          if (statusData.is_ready) {
            newStatus = "ready";
          } else {
            const s = statusData.progress?.status;
            if (s === "ready") newStatus = "ready";
            else if (s === "error") newStatus = "error";
            else newStatus = "loading";
          }
          set({ status: newStatus });
        } catch (err) {
          console.error(err);
          set({ status: "error" });
        }
      },
    })),
    {
      name: "loji-ai-storage",
      storage: createJSONStorage(() => userScopedStorage),
      partialize: (state: AiState) => ({
        messages: state.messages,
        isOpen: state.isOpen,
        isExpanded: state.isExpanded,
      }),
    },
  ),
);
