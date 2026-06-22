import { Bell, BellOff, Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { usePushNotifications } from "../../hooks/usePushNotifications";
import { cn } from "../../lib/utils";

export function PushNotificationToggle() {
  const { t } = useTranslation();
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
              {t("profile.push_title", "Push Notifications")}
            </h3>
            <p className="mt-1 text-xs text-secondary">
              {t(
                "profile.push_unsupported",
                "Your browser does not support Web Push. iOS Safari 16.4+ or Chrome/Edge is required.",
              )}
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
              {t("profile.push_title", "Push Notifications")}
            </h3>
            <p className="mt-1 text-xs text-secondary">
              {subscribed
                ? t(
                    "profile.push_subscribed_desc",
                    "This device subscription is active. Critical anomalies and investigations will be delivered as push notifications.",
                  )
                : t(
                    "profile.push_unsubscribed_desc",
                    "Enable to receive critical alerts instantly on your mobile device.",
                  )}
            </p>
            {blocked && (
              <p className="mt-2 text-xs text-danger">
                {t(
                  "profile.push_permission_denied",
                  "Notification permission denied. Please grant permission in your browser settings.",
                )}
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
              {t("profile.push_disable_btn", "Disable")}
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
                  {t("profile.push_connecting", "Connecting")}
                </>
              ) : (
                t("profile.push_enable_btn", "Enable")
              )}
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}
