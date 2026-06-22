import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { notificationService, type Notification } from "@/api/notifications";
import type { WsNotification } from "./useMonitoringSocket";

export function useNotifications(wsNotifications: WsNotification[]) {
  const queryClient = useQueryClient();
  const [optimisticRead, setOptimisticRead] = useState<Set<number>>(new Set());

  const { data: history = [], isLoading } = useQuery({
    queryKey: ["notifications", "my"],
    queryFn: notificationService.getMyNotifications,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  // Convert WS shape to Notification shape
  const wsAsDb: Notification[] = wsNotifications.map((n) => ({
    id: n.id,
    baslik: n.baslik,
    icerik: n.icerik,
    olay_tipi: n.olay_tipi ?? "",
    okundu: false,
    olusturma_tarihi: n.olusturma_tarihi,
  }));

  // Dedup: only WS items not yet in DB history
  const historyIds = new Set(history.map((n) => n.id));
  const freshWs = wsAsDb.filter((n) => !historyIds.has(n.id));

  // Merge: fresh WS first, then DB history; apply optimistic read state
  const all: Notification[] = [...freshWs, ...history].map((n) => ({
    ...n,
    okundu: n.okundu || optimisticRead.has(n.id),
  }));

  const unreadCount = all.filter((n) => !n.okundu).length;

  const markRead = useMutation({
    mutationFn: (id: number) => notificationService.markAsRead(id),
    onMutate: (id) => setOptimisticRead((prev) => new Set([...prev, id])),
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: ["notifications", "my"] }),
  });

  const markAllRead = useMutation({
    mutationFn: notificationService.markAllAsRead,
    onMutate: () => setOptimisticRead(new Set(all.map((n) => n.id))),
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: ["notifications", "my"] }),
  });

  return { notifications: all, unreadCount, isLoading, markRead, markAllRead };
}
