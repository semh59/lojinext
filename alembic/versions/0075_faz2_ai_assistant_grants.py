"""FAZ2 Wave 2 pilot fix #16 — m_ai_assistant grant gaps (3 found).

Found live during the ai_assistant-module pilot (2026-07-30), via a
comprehensive public.py + source-code cross-module audit performed BEFORE
wiring. `m_ai_assistant` previously only had `["fleet", "trip", "driver",
"location"]`.

3 new schemas added to READER_SELECT_GRANTS:

- `fuel`: `AIService._build_context` (orchestrate_ai_response.py) calls
  `uow.analiz_repo.get_dashboard_stats()`, which reads
  `fuel.yakit_alimlari` (SUM(litre)) alongside the already-granted trip/
  fleet/driver tables. `ai_routes.py`'s `_fuel_trend_chart` also calls
  `fuel.public.get_monthly_cost_trend()` (same table, monthly aggregate).
- `anomaly`: the same `_build_context` call also runs `uow.analiz_repo.
  get_recent_unread_alerts()`, a raw SELECT directly against
  `anomaly.anomalies`.
- `admin_platform`: `groq_client.py`/`raw_client.py` (the two independent
  LLM HTTP clients) both call `admin_platform.public.
  get_integration_secret()` to resolve a DB-stored Groq API key override,
  reading `admin_platform.entegrasyon_ayarlari` -- the same
  sistem_konfig/entegrasyon_ayarlari-read pattern already granted for
  m_location/m_route_simulation/m_anomaly/m_prediction_ml.
  `get_integration_secret()` never raises (falls back to the env var on
  any DB error), so a missing grant here would not crash `/ai/chat` --
  it would just silently make the DB-based key override permanently
  inert for this module. Granted anyway for consistency with every other
  module hitting this exact table.

Re-runs `apply_role_grants_sync` — idempotent.

Revision ID: 0075_faz2_ai_assistant_grants
Revises: 0074_faz2_admin_platform_grants2
Create Date: 2026-07-30
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0075_faz2_ai_assistant_grants"
down_revision: Union[str, Sequence[str], None] = "0074_faz2_admin_platform_grants2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from v2.modules.platform_infra.database.role_grants import apply_role_grants_sync

    apply_role_grants_sync(op.get_bind())


def downgrade() -> None:
    # No-op: 0061's own downgrade() does a full REVOKE ALL + DROP ROLE for
    # every role in the matrix, which already covers undoing this grant.
    pass
