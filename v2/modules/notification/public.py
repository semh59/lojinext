"""Public surface of the notification module.

Other modules that need to call into notification must import from here,
not from `application/`, `domain/`, or `infrastructure/` directly (see
TASKS/modules/notification.md and .importlinter's forbidden-imports
contract, enforced from FAZ1's import-linter gate task onward).

There is no ``NotificationService`` class — each use-case is a standalone
function (same rationale as the location module: six otherwise-unrelated
use-cases don't need a stateful facade). ``handle_event``/``register_handlers``
stay paired in one file because they're two halves of a single
event-subscription use-case, not independent use-cases.
"""

from v2.modules.notification.application.get_user_notifications import (
    get_user_notifications,
)
from v2.modules.notification.application.handle_trip_events import (
    handle_event,
    register_handlers,
)
from v2.modules.notification.application.manage_notification_rules import (
    create_rule,
    delete_rule,
    list_rules,
    update_rule,
)
from v2.modules.notification.application.manage_push_subscription import (
    subscribe_push,
    unsubscribe_push,
)
from v2.modules.notification.application.mark_all_notifications_read import (
    mark_all_as_read,
)
from v2.modules.notification.application.mark_notification_read import mark_as_read
from v2.modules.notification.application.quiet_hours import (
    is_user_quiet_now,
    is_within_quiet_hours,
)
from v2.modules.notification.application.send_push_broadcast import (
    send_push_broadcast,
)
from v2.modules.notification.application.send_push_to_user import send_push_to_user
from v2.modules.notification.domain.vapid import vapid_configured
from v2.modules.notification.infrastructure.email_client import (
    send_password_reset,
    send_text,
)
from v2.modules.notification.infrastructure.models import (
    BildirimDurumu,
    BildirimGecmisi,
    BildirimKurali,
    PushSubscription,
)
from v2.modules.notification.infrastructure.repository import NotificationRepository
from v2.modules.notification.infrastructure.telegram_client import (
    notify_error,
    notify_feedback,
)
from v2.modules.notification.infrastructure.ws_broadcaster import (
    notification_ws_manager,
)
from v2.modules.notification.schemas import (
    PushSendResult,
    PushSubscriptionRequest,
    PushSubscriptionResponse,
    PushTestRequest,
    VapidPublicKeyResponse,
)

__all__ = [
    # ORM (dalga 16 task #58 — database/models.py bölünmesi)
    "BildirimKurali",
    "BildirimDurumu",
    "BildirimGecmisi",
    "PushSubscription",
    "register_handlers",
    "handle_event",
    "get_user_notifications",
    "list_rules",
    "create_rule",
    "update_rule",
    "delete_rule",
    "mark_as_read",
    "mark_all_as_read",
    "subscribe_push",
    "unsubscribe_push",
    "send_push_to_user",
    "send_push_broadcast",
    "vapid_configured",
    "is_user_quiet_now",
    "is_within_quiet_hours",
    "notify_error",
    "notify_feedback",
    "send_password_reset",
    "send_text",
    "notification_ws_manager",
    "NotificationRepository",
    "PushSubscriptionRequest",
    "PushSubscriptionResponse",
    "PushTestRequest",
    "PushSendResult",
    "VapidPublicKeyResponse",
]
