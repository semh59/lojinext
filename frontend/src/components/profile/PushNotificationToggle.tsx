import { Bell, BellOff, Loader2 } from "lucide-react";

import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { usePushNotifications } from "../../hooks/usePushNotifications";
import { cn } from "../../lib/utils";

export function PushNotificationToggle() {
  const {
    supported,
    permission,
    subscribed,
    enabling,
    error,
    enable,
    disable,
  } = usePushNotifications();

  if (!supported) {
    return (
      <Card className="p-5">
        <div className="flex items-start gap-3">
          <BellOff className="h-5 w-5 text-tertiary" />
          <div>
            <h3 className="text-sm font-semibold text-primary">
              Push Bildirimleri
            </h3>
            <p className="mt-1 text-xs text-secondary">
              Tarayıcınız Web Push desteklemiyor. iOS Safari 16.4+ veya
              Chrome/Edge gereklidir.
            </p>
          </div>
        </div>
      </Card>
    );
  }

  const blocked = permission === "denied";

  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <Bell
            className={cn(
              "h-5 w-5",
              subscribed ? "text-accent" : "text-tertiary",
            )}
          />
          <div>
            <h3 className="text-sm font-semibold text-primary">
              Push Bildirimleri
            </h3>
            <p className="mt-1 text-xs text-secondary">
              {subscribed
                ? "Bu cihaz aboneliği aktif. Kritik anomali ve soruşturmalar push olarak gelir."
                : "Mobil cihazınızda kritik uyarıları anında almak için açın."}
            </p>
            {blocked && (
              <p className="mt-2 text-xs text-danger">
                Bildirim izni reddedildi. Tarayıcı ayarlarından izin
                vermelisiniz.
              </p>
            )}
            {error && !blocked && (
              <p className="mt-2 text-xs text-danger">{error}</p>
            )}
          </div>
        </div>
        <div className="shrink-0">
          {subscribed ? (
            <Button
              variant="secondary"
              disabled={enabling}
              onClick={() => void disable()}
            >
              Kapat
            </Button>
          ) : (
            <Button
              disabled={enabling || blocked}
              onClick={() => void enable()}
              className="gap-2"
            >
              {enabling ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Bağlanıyor
                </>
              ) : (
                "Etkinleştir"
              )}
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}
