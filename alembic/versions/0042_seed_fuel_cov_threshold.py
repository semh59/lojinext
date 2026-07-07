"""seed_fuel_coverage_threshold

sistem_konfig için FUEL_COVERAGE_ALERT_THRESHOLD_PCT varsayılan satırı
(fuel-coverage ops alarmı, 2026-07-07).

0041'in devamı — sadece kodun app/core/services/runtime_config.py üzerinden
GERÇEKTEN okuduğu anahtarlar seed'lenir (bkz. 0041 docstring'i). Bu anahtar
app/workers/tasks/fuel_coverage_check.py'nin monitoring.fuel_coverage_check
beat task'ında get_runtime_float ile okunur: son 7 gün tamamlanmış sefer
coverage'ı (tahmini olan / toplam) bu eşiğin altına düşerse Telegram ops
uyarısı tetiklenir.

Revision ID: 0042_seed_fuel_cov_threshold
Revises: 0041_seed_runtime_config
Create Date: 2026-07-07

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
# NOT: alembic_version.version_num varchar(32) — revision id 32 karakteri
# aşamaz (0042_seed_fuel_coverage_threshold 34 karakterdi, ilk denemede
# StringDataRightTruncation ile patladı).
revision: str = "0042_seed_fuel_cov_threshold"
down_revision: Union[str, Sequence[str], None] = "0041_seed_runtime_config"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (anahtar, deger_json, tip, birim, min, max, grup, aciklama, yeniden_baslat)
_SEED_ROWS = [
    (
        "FUEL_COVERAGE_ALERT_THRESHOLD_PCT",
        "50.0",
        "number",
        "%",
        "0",
        "100",
        "ml",
        "Son 7 gün tamamlanmış seferlerde yakıt tahmini coverage eşiği. "
        "Coverage bu değerin altına düşerse (ve örneklem >= 5 ise) ops "
        "ekibine Telegram uyarısı gider.",
        "false",
    ),
]


def upgrade() -> None:
    # ON CONFLICT DO NOTHING: mevcut kurulumlarda (satır elle/testle
    # oluşturulmuşsa) operatörün değerini EZME.
    for anahtar, deger, tip, birim, min_d, max_d, grup, aciklama, restart in _SEED_ROWS:
        op.execute(
            f"""
            INSERT INTO sistem_konfig
              (anahtar, deger, tip, birim, min_deger, max_deger, grup,
               aciklama, yeniden_baslat)
            VALUES
              ('{anahtar}', '{deger}'::jsonb, '{tip}',
               {f"'{birim}'" if birim is not None else "NULL"},
               {min_d if min_d is not None else "NULL"},
               {max_d if max_d is not None else "NULL"},
               '{grup}', '{aciklama}', {restart})
            ON CONFLICT (anahtar) DO NOTHING
            """
        )


def downgrade() -> None:
    # Sadece bizim seed'lediğimiz anahtarları kaldır; operatörün sonradan
    # DEĞİŞTİRDİĞİ değerler de silinir (downgrade zaten veri kaybıdır),
    # ama başka anahtarlara dokunulmaz.
    keys = ", ".join(f"'{row[0]}'" for row in _SEED_ROWS)
    op.execute(f"DELETE FROM sistem_konfig WHERE anahtar IN ({keys})")
