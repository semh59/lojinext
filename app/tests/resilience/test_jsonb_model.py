from datetime import datetime, timezone

import pytest
from sqlalchemy import select, text

from app.database.models import OutboxEvent


@pytest.mark.asyncio
async def test_jsonb_outbox_payload_integrity(db_session):
    """Verify that JSONB columns correctly store and retrieve complex nested data."""
    complex_payload = {
        "event_id": "evt_123",
        "nested": {"list": [1, 2, 3], "details": {"status": "ok", "value": 42.5}},
        "turkish_chars": "ığüşöç İĞÜŞÖÇ",
    }

    # Create event
    event = OutboxEvent(
        event_type="test_jsonb",
        payload=complex_payload,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(event)
    await db_session.commit()

    # Retrieve and verify
    result = await db_session.execute(
        select(OutboxEvent).where(OutboxEvent.id == event.id)
    )
    retrieved = result.scalar_one()

    assert retrieved.payload == complex_payload
    assert retrieved.payload["nested"]["details"]["value"] == 42.5
    assert retrieved.payload["turkish_chars"] == "ığüşöç İĞÜŞÖÇ"

    # Test JSONB containment operator (if postgres)
    # This might fail on SQLite but passes on real Postgres linter/test-db
    try:
        stmt = text(
            'SELECT id FROM outbox_events WHERE payload @> \'{"nested": {"details": {"status": "ok"}}}\''
        )
        result = await db_session.execute(stmt)
        assert result.scalar() == event.id
    except Exception as e:
        # If running on a driver that doesn't support @> (like some sqlite setups in tests), skip this specific check
        if "operator does not exist" in str(e) or "syntax error" in str(e):
            pytest.skip(
                "JSONB containment operator not supported by current test database driver"
            )
        else:
            raise e
