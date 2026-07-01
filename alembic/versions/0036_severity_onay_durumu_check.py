"""anomalies.severity + seferler.onay_durumu: add CHECK constraints (P1 madde 15)

2026-07-01 prod-grade denetimi Dalga 3 madde 15: `Anomaly.severity` ve
`Sefer.onay_durumu` kritik enum-benzeri kolonlardı ama DB seviyesinde hiçbir
CHECK kısıtı yoktu — typo'lu bir değer (örn. "hihg" yerine "high") hiç
engellenmiyordu, sessizce kaydediliyordu.

NOT VALID ile eklendi — mevcut satırlar migration zamanında doğrulanmaz
(prod'da beklenmeyen bir değer olabilir, migration'ı bloklamasın).

Revision ID: 0036_severity_onay_durumu_check
Revises: 0035_sefer_periyot_id_fk
Create Date: 2026-07-01
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0036_severity_onay_durumu_check"
down_revision: Union[str, Sequence[str], None] = "0035_sefer_periyot_id_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE anomalies
          ADD CONSTRAINT check_anomaly_severity_enum
          CHECK (severity IN ('low', 'medium', 'high', 'critical'))
          NOT VALID;
    """)
    op.execute("""
        ALTER TABLE seferler
          ADD CONSTRAINT check_sefer_onay_durumu_enum
          CHECK (onay_durumu IS NULL OR onay_durumu IN
                 ('beklemede', 'onaylandi', 'reddedildi'))
          NOT VALID;
    """)


def downgrade() -> None:
    op.execute(
        "ALTER TABLE seferler DROP CONSTRAINT IF EXISTS check_sefer_onay_durumu_enum;"
    )
    op.execute(
        "ALTER TABLE anomalies DROP CONSTRAINT IF EXISTS check_anomaly_severity_enum;"
    )
