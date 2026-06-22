import {
  chatWithAiApiV1AiChatPost,
  getAiStatusApiV1AiStatusGet,
  aiQueryApiV1AiQueryPost,
} from "../generated/api/ai/ai";

// Re-export generated request types under the original names
export type { ChatRequest } from "../generated/types/chatRequest";

// Original interface shapes preserved for consumers

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface ChatResponse {
  response: string;
  timestamp: string;
}

export interface AIStatus {
  is_ready: boolean;
  progress: {
    status: string;
    percent: number;
    speed: string;
  };
}

export interface AiChartSpec {
  type: string;
  title: string;
  x_key: string;
  series: { key: string; label: string }[];
  data: Record<string, unknown>[];
}

export interface AiQueryResponse {
  category: string;
  answer: string;
  chart: AiChartSpec | null;
  actions: { label: string; url: string }[];
}

export const aiApi = {
  chat: async (data: {
    message: string;
    history?: ChatMessage[];
  }): Promise<ChatResponse> => {
    const response = await chatWithAiApiV1AiChatPost({
      message: data.message,
      history: data.history as unknown as
        | { [key: string]: unknown }[]
        | null
        | undefined,
    });
    return response as unknown as ChatResponse;
  },

  /** Faz 9 — kategori-farkında AI sorgu (grafik + aksiyon linkleri dönebilir). */
  query: async (
    message: string,
    category: string,
  ): Promise<AiQueryResponse> => {
    const response = await aiQueryApiV1AiQueryPost({ message, category });
    return response as unknown as AiQueryResponse;
  },

  getStatus: async (): Promise<AIStatus> => {
    const response = await getAiStatusApiV1AiStatusGet();
    return response as unknown as AIStatus;
  },
};
