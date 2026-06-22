import axiosInstance from "./axios-instance";

export interface TicketResponse {
  ticket: string;
  expires_in: number;
}

/**
 * WebSocket Ticket Service
 * WS bağlantıları için güvenli, kısa ömürlü bilet sağlar.
 */
export const wsService = {
  /**
   * Yeni bir WebSocket bileti alır
   */
  getTicket: async (): Promise<string> => {
    try {
      const response = await axiosInstance.post<TicketResponse>("/ws/ticket");
      return response.data.ticket;
    } catch (error) {
      console.error("Failed to fetch WS ticket:", error);
      throw error;
    }
  },
};
