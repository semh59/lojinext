"""Normalize sefer status contract and tighten status constraint.

Revision ID: 1b2f3d4e5a6b
Revises: 0faddb9b5a10
Create Date: 2026-03-10 12:20:00
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1b2f3d4e5a6b"
down_revision: Union[str, Sequence[str], None] = "0faddb9b5a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CANONICAL_STATUSES: tuple[str, ...] = (
    "Bekliyor",
    "Planlandı",
    "Yolda",
    "Devam Ediyor",
    "Tamamlandı",
    "Tamam",
    "İptal",
)

LEGACY_TO_CANONICAL: dict[str, str] = {
    "Iptal": "İptal",
    "IPTAL": "İptal",
    "iptal": "İptal",
    "Planlandi": "Planlandı",
    "PLANLANDI": "Planlandı",
    "planlandi": "Planlandı",
    "Tamamlandi": "Tamamlandı",
    "TAMAMLANDI": "Tamamlandı",
    "tamamlandi": "Tamamlandı",
    "PlanlandÄ±": "Planlandı",
    "TamamlandÄ±": "Tamamlandı",
    "Ä°ptal": "İptal",
}


def _refresh_trip_stats_mv_if_exists() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.sefer_istatistik_mv') IS NOT NULL THEN
                REFRESH MATERIALIZED VIEW sefer_istatistik_mv;
            END IF;
        END $$;
        """
    )


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()

    for legacy_status, canonical_status in LEGACY_TO_CANONICAL.items():
        bind.execute(
            sa.text("UPDATE seferler SET durum = :canonical WHERE durum = :legacy"),
            {"canonical": canonical_status, "legacy": legacy_status},
        )

    invalid_status_rows = bind.execute(
        sa.text(
            """
            SELECT durum, COUNT(*) AS row_count
            FROM seferler
            WHERE durum IS NOT NULL
              AND durum NOT IN :canonical_statuses
            GROUP BY durum
            ORDER BY row_count DESC
            """
        ).bindparams(sa.bindparam("canonical_statuses", expanding=True)),
        {"canonical_statuses": CANONICAL_STATUSES},
    ).fetchall()
    if invalid_status_rows:
        details = ", ".join(f"{row[0]}:{row[1]}" for row in invalid_status_rows)
        raise RuntimeError(
            "Unexpected sefer durum values remain before tightening constraint: "
            f"{details}"
        )

    op.execute("ALTER TABLE seferler DROP CONSTRAINT IF EXISTS check_sefer_durum_enum")
    op.create_check_constraint(
        "check_sefer_durum_enum",
        "seferler",
        "durum IN ('Bekliyor', 'Planlandı', 'Yolda', 'Devam Ediyor', 'Tamamlandı', 'Tamam', 'İptal')",
    )

    _refresh_trip_stats_mv_if_exists()


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE seferler DROP CONSTRAINT IF EXISTS check_sefer_durum_enum")
    op.create_check_constraint(
        "check_sefer_durum_enum",
        "seferler",
        "durum IN ('Bekliyor', 'Onaylandi', 'Reddedildi', 'Tamam', 'Hata', 'İptal', 'Planlandı', 'Yolda', 'Devam Ediyor', 'Tamamlandı', 'Iptal', 'Planlandi', 'Tamamlandi')",
    )

    _refresh_trip_stats_mv_if_exists()
