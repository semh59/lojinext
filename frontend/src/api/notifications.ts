import {
  getMyNotificationsApiV1AdminNotificationsMyGet,
  markAllReadApiV1AdminNotificationsMarkAllReadPost,
  markSingleReadApiV1AdminNotificationsNotificationIdReadPatch,
} from "../generated/api/admin-notifications/admin-notifications";

export interface Notification {
  id: number;
  baslik: string;
  icerik: string;
  olay_tipi: string;
  okundu: boolean;
  olusturma_tarihi: string;
}

export const notificationService = {
  /**
   * Kullanıcının bildirimlerini getirir.
   */
  getMyNotifications: async (): Promise<Notification[]> => {
    const result = await getMyNotificationsApiV1AdminNotificationsMyGet();
    return result as unknown as Notification[];
  },

  /**
   * Bildirimi okundu olarak işaretler.
   */
  markAsRead: async (notificationId: number): Promise<void> => {
    await markSingleReadApiV1AdminNotificationsNotificationIdReadPatch(
      notificationId,
    );
  },

  /**
   * Tüm bildirimleri okundu olarak işaretler.
   */
  markAllAsRead: async (): Promise<void> => {
    await markAllReadApiV1AdminNotificationsMarkAllReadPost();
  },
};
