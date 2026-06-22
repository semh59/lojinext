"""add_error_events_notify_trigger

Revision ID: 9cefef01eaec
Revises: 2f052e500be8
Create Date: 2026-05-19 08:46:23.617416

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9cefef01eaec"
down_revision: Union[str, Sequence[str], None] = "2f052e500be8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION notify_error_event()
        RETURNS TRIGGER AS $$
        BEGIN
            PERFORM pg_notify(
                'error_events_channel',
                LEFT(json_build_object(
                    'id',          NEW.id,
                    'fingerprint', NEW.fingerprint,
                    'layer',       NEW.layer::text,
                    'category',    NEW.category,
                    'severity',    NEW.severity::text,
                    'message',     LEFT(NEW.message, 200),
                    'count',       NEW.count,
                    'last_seen',   NEW.last_seen
                )::text, 7500)
            );
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("DROP TRIGGER IF EXISTS error_events_notify ON error_events;")
    op.execute("""
        CREATE TRIGGER error_events_notify
        AFTER INSERT OR UPDATE ON error_events
        FOR EACH ROW
        WHEN (NEW.severity IN ('error', 'critical') AND NEW.resolved_at IS NULL)
        EXECUTE FUNCTION notify_error_event();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS error_events_notify ON error_events;")
    op.execute("DROP FUNCTION IF EXISTS notify_error_event();")
