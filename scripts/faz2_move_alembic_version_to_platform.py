"""FAZ2 şema-per-modül — tek-seferlik cutover: `alembic_version`'ı
`platform` şemasına taşır.

NEDEN BU BİR ALEMBIC MİGRATION'I DEĞİL (kasıtlı, bkz. 0060_platform_
schema_move.py'nin docstring'i): Alembic kendi versiyon-takip tablosunun
konumunu `env.py`'deki `context.configure(version_table_schema=...)`
parametresiyle SÜREÇ BAŞINDA sabitler. `alembic_version`'ı bir migration'ın
KENDİSİ İÇİNDE taşırsak, alembic o migration'ın revision numarasını
yazmaya çalıştığında (`upgrade()` döndükten hemen sonra, hâlâ AYNI
çalıştırma/transaction içinde) hâlâ ESKİ konumu arar — tablo artık orada
olmadığı için "relation does not exist" ile patlar (gerçek bir Postgres 16
instance'ında doğrulandı). Bu, Alembic'in taşıması gereken KENDİ
bookkeeping tablosunu taşırken düştüğü, belgelenmiş bir tavuk-yumurta
sınırı — güvenli tek yol, taşımayı migration zincirinin DIŞINDA, ayrı bir
adım olarak yapmak.

UYGULAMA SIRASI (zorunlu, atlanamaz):

    1. `alembic upgrade head` — 0060_platform_schema_move dahil TÜM
       migration'lar `alembic/env.py`'nin `version_table_schema="platform"`
       satırı EKLENMEDEN ÖNCE (veya bu satır varken ama henüz bu script
       çalıştırılmadan) çalıştırılırsa, alembic HÂLÂ `public.alembic_version`'ı
       arayacağı için env.py'deki `version_table_schema="platform"` satırı
       bu script çalışana kadar YORUM SATIRINA alınmış/geri alınmış olmalı
       — pratikte: önce bu satır OLMADAN `alembic upgrade head` çalıştırılır
       (0060 dahil tüm tablo taşımaları biter, `alembic_version` hâlâ
       `public`'te kalır), SONRA bu script çalıştırılır, SONRA env.py'nin
       `version_table_schema="platform"` satırı commit'lenir/aktif bırakılır.
    2. Bu script çalıştırılır: `ALTER TABLE alembic_version SET SCHEMA platform`.
    3. Bundan sonraki HER `alembic` çağrısı (upgrade/downgrade/check/current)
       `platform.alembic_version`'ı bulur ve normal çalışmaya devam eder.

KULLANIM:
    docker compose exec backend python -m scripts.faz2_move_alembic_version_to_platform
    (veya lokal/CI'da: python -m scripts.faz2_move_alembic_version_to_platform)

Idempotent: tablo zaten `platform` şemasındaysa sessizce no-op geçer (tekrar
çalıştırmak güvenli).
"""

from __future__ import annotations

import sys

from sqlalchemy import create_engine, text

from app.config import settings


def _to_sync_url(url: str) -> str:
    """Mirrors alembic/env.py's own URL normalisation (async driver → sync)."""
    url = url.replace("+asyncpg", "").replace("+aiosqlite", "")
    if "?" in url:
        url = url.split("?", 1)[0]
    return url


def main() -> int:
    sync_url = _to_sync_url(settings.DATABASE_URL)
    engine = create_engine(sync_url)

    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS platform"))

        current_schema = conn.execute(
            text(
                """
                SELECT n.nspname
                FROM pg_class c
                JOIN pg_namespace n ON c.relnamespace = n.oid
                WHERE c.relname = 'alembic_version'
                """
            )
        ).scalar()

        if current_schema is None:
            print("FATAL: alembic_version tablosu hiçbir şemada bulunamadı.")
            return 1

        if current_schema == "platform":
            print("alembic_version zaten platform şemasında — no-op.")
            return 0

        if current_schema != "public":
            print(
                f"FATAL: alembic_version beklenmedik şemada ({current_schema}), "
                "elle inceleyin."
            )
            return 1

        conn.execute(text("ALTER TABLE alembic_version SET SCHEMA platform"))
        print("alembic_version → platform şemasına taşındı.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
