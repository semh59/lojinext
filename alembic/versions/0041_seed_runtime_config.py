"""seed_runtime_config

sistem_konfig için varsayılan satır seed'i (runtime-config epiği, 2026-07-07).

Tablo migration 0001'den beri vardı ama HİÇBİR ortamda satır seed'lenmedi —
taze kurulumda admin Konfigürasyon sayfası kalıcı boştu ve HTTP'den satır
YARATILAMIYOR (endpoint'ler sadece GET + PUT; PUT satır yoksa 404).

Sadece kodun app/core/services/runtime_config.py üzerinden GERÇEKTEN
okuduğu anahtarlar seed'lenir — okunmayan anahtar seed'lemek "değeri
değiştirdim ama sistem umursamıyor" diyen yalancı bir UI üretir. Yeni bir
anahtar bağlanırken buraya değil, YENİ bir data-migration'a ekle.

Revision ID: 0041_seed_runtime_config
Revises: 0040_pii_encryption
Create Date: 2026-07-07

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0041_seed_runtime_config"
down_revision: Union[str, Sequence[str], None] = "0040_pii_encryption"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (anahtar, deger_json, tip, birim, min, max, grup, aciklama, yeniden_baslat)
_SEED_ROWS = [
    (
        "ANOMALY_Z_THRESHOLD",
        "2.5",
        "number",
        "σ",
        "1",
        "5",
        "anomali",
        "Anomali tespiti için Z-skoru eşiği. Düşük değer = daha hassas "
        "(daha çok anomali), yüksek değer = daha toleranslı.",
        "false",
    ),
    (
        "VEHICLE_AGE_DEGRADATION_RATE",
        "0.01",
        "number",
        None,
        "0",
        "0.1",
        "ml",
        "Araç yaşı başına yıllık motor verimi düşüş oranı (yakıt tahmini yaş faktörü).",
        "false",
    ),
    (
        "default_base_location",
        '"FABRIKA"',
        "string",
        None,
        None,
        None,
        "rota",
        "Rota hesaplarında varsayılan başlangıç/üs lokasyonu adı.",
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
