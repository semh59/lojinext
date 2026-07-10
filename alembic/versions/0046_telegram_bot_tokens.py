"""telegram bot tokens in entegrasyon_ayarlari

Extends the multi-tenant API key epic (0045) to Telegram bot tokens.
Unlike mapbox/openroute/groq, these two rows' plaintext DOES cross a
process boundary — the telegram-driver-bot/telegram-ops-bot containers
must authenticate with Telegram's own API, so they fetch the plaintext
at startup via the new internal-only /bot-token/{servis_adi} endpoint
(shared-secret authenticated, not reachable from the public reverse
proxy). See app/core/services/integration_secrets.py's BOT_TOKEN_SERVICES
and app/api/v1/endpoints/internal.py.

Revision ID: 0046_telegram_bot_tokens
Revises: 0045_entegrasyon_ayarlari
Create Date: 2026-07-10

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0046_telegram_bot_tokens"
down_revision: Union[str, Sequence[str], None] = "0045_entegrasyon_ayarlari"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_SERVICES = ("telegram_driver_bot", "telegram_ops_bot")


def upgrade() -> None:
    conn = op.get_bind()
    for servis in _NEW_SERVICES:
        conn.execute(
            sa.text(
                "INSERT INTO entegrasyon_ayarlari (servis_adi) VALUES (:s) "
                "ON CONFLICT (servis_adi) DO NOTHING"
            ),
            {"s": servis},
        )


def downgrade() -> None:
    conn = op.get_bind()
    for servis in _NEW_SERVICES:
        conn.execute(
            sa.text("DELETE FROM entegrasyon_ayarlari WHERE servis_adi = :s"),
            {"s": servis},
        )
