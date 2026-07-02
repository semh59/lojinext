"""Tier E madde 26: PII encryption-at-rest for soforler.ad_soyad/telefon and
kullanicilar.email/ad_soyad.

Adds deterministic blind-index columns (email_bidx, ad_soyad_bidx) for exact-
match lookup/uniqueness, and a trigram-index child table
(sofor_ad_soyad_trigram) for substring search on the encrypted driver name.
Backfills existing plaintext rows in place — after this migration, the
former plaintext columns hold Fernet ciphertext.

Revision ID: 0040_pii_encryption
Revises: 0039_route_idx_cleanup
Create Date: 2026-07-02
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0040_pii_encryption"
down_revision: Union[str, Sequence[str], None] = "0039_route_idx_cleanup"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.infrastructure.security.pii_encryption import (
        blind_index,
        decrypt_pii,
        encrypt_pii,
        trigram_blind_indexes,
    )

    bind = op.get_bind()

    # 1. Widen the plaintext columns to TEXT — Fernet ciphertext exceeds the
    #    original VARCHAR(100)/VARCHAR(255) bounds for short inputs.
    op.alter_column("soforler", "ad_soyad", type_=sa.Text(), existing_nullable=False)
    op.alter_column("soforler", "telefon", type_=sa.Text(), existing_nullable=True)
    op.alter_column("kullanicilar", "email", type_=sa.Text(), existing_nullable=False)
    op.alter_column(
        "kullanicilar", "ad_soyad", type_=sa.Text(), existing_nullable=False
    )

    # 2. New nullable columns for the backfill pass.
    op.add_column("soforler", sa.Column("ad_soyad_bidx", sa.String(64), nullable=True))
    op.add_column("kullanicilar", sa.Column("email_bidx", sa.String(64), nullable=True))

    op.create_table(
        "sofor_ad_soyad_trigram",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "sofor_id",
            sa.Integer(),
            sa.ForeignKey("soforler.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("trigram_hash", sa.CHAR(64), nullable=False),
        sa.UniqueConstraint("sofor_id", "trigram_hash", name="uq_sofor_trigram"),
    )
    op.create_index("ix_sofor_trigram_hash", "sofor_ad_soyad_trigram", ["trigram_hash"])

    # 3. Backfill existing rows: encrypt plaintext in place, compute bidx +
    #    trigrams. Small dataset expected (soforler/kullanicilar are not
    #    bulk-import targets) — plain Python loop, no batching needed.
    soforler = sa.table(
        "soforler",
        sa.column("id", sa.Integer),
        sa.column("ad_soyad", sa.Text),
        sa.column("ad_soyad_bidx", sa.String),
        sa.column("telefon", sa.Text),
    )
    kullanicilar = sa.table(
        "kullanicilar",
        sa.column("id", sa.Integer),
        sa.column("email", sa.Text),
        sa.column("email_bidx", sa.String),
        sa.column("ad_soyad", sa.Text),
    )
    trigram_table = sa.table(
        "sofor_ad_soyad_trigram",
        sa.column("sofor_id", sa.Integer),
        sa.column("trigram_hash", sa.CHAR),
    )

    for row in bind.execute(
        sa.select(soforler.c.id, soforler.c.ad_soyad, soforler.c.telefon)
    ).fetchall():
        plaintext_name = row.ad_soyad
        bind.execute(
            sa.update(soforler)
            .where(soforler.c.id == row.id)
            .values(
                ad_soyad=encrypt_pii(plaintext_name),
                ad_soyad_bidx=blind_index(plaintext_name),
                telefon=encrypt_pii(row.telefon) if row.telefon else None,
            )
        )
        trigram_rows = [
            {"sofor_id": row.id, "trigram_hash": h}
            for h in set(trigram_blind_indexes(plaintext_name))
        ]
        if trigram_rows:
            bind.execute(sa.insert(trigram_table), trigram_rows)

    for row in bind.execute(
        sa.select(kullanicilar.c.id, kullanicilar.c.email, kullanicilar.c.ad_soyad)
    ).fetchall():
        bind.execute(
            sa.update(kullanicilar)
            .where(kullanicilar.c.id == row.id)
            .values(
                email=encrypt_pii(row.email),
                email_bidx=blind_index(row.email),
                ad_soyad=encrypt_pii(row.ad_soyad),
            )
        )

    # 4. Drop the old plaintext-value unique indexes, replace with bidx ones;
    #    enforce NOT NULL on the now-backfilled bidx columns.
    op.drop_index("ix_soforler_ad_soyad", table_name="soforler")
    op.drop_index("ix_kullanicilar_email", table_name="kullanicilar")

    op.alter_column("soforler", "ad_soyad_bidx", nullable=False)
    op.alter_column("kullanicilar", "email_bidx", nullable=False)

    op.create_index(
        "ix_soforler_ad_soyad_bidx", "soforler", ["ad_soyad_bidx"], unique=True
    )
    op.create_index(
        "ix_kullanicilar_email_bidx", "kullanicilar", ["email_bidx"], unique=True
    )

    # Sanity: prove decrypt round-trips before finishing (no-op if it raises).
    sample = bind.execute(sa.select(kullanicilar.c.email).limit(1)).fetchone()
    if sample is not None:
        decrypt_pii(sample.email)


def downgrade() -> None:
    from app.infrastructure.security.pii_encryption import decrypt_pii

    bind = op.get_bind()

    soforler = sa.table(
        "soforler",
        sa.column("id", sa.Integer),
        sa.column("ad_soyad", sa.Text),
        sa.column("telefon", sa.Text),
    )
    kullanicilar = sa.table(
        "kullanicilar",
        sa.column("id", sa.Integer),
        sa.column("email", sa.Text),
        sa.column("ad_soyad", sa.Text),
    )

    for row in bind.execute(
        sa.select(soforler.c.id, soforler.c.ad_soyad, soforler.c.telefon)
    ).fetchall():
        bind.execute(
            sa.update(soforler)
            .where(soforler.c.id == row.id)
            .values(
                ad_soyad=decrypt_pii(row.ad_soyad),
                telefon=decrypt_pii(row.telefon) if row.telefon else None,
            )
        )

    for row in bind.execute(
        sa.select(kullanicilar.c.id, kullanicilar.c.email, kullanicilar.c.ad_soyad)
    ).fetchall():
        bind.execute(
            sa.update(kullanicilar)
            .where(kullanicilar.c.id == row.id)
            .values(
                email=decrypt_pii(row.email),
                ad_soyad=decrypt_pii(row.ad_soyad),
            )
        )

    op.drop_index("ix_soforler_ad_soyad_bidx", table_name="soforler")
    op.drop_index("ix_kullanicilar_email_bidx", table_name="kullanicilar")

    op.drop_index("ix_sofor_trigram_hash", table_name="sofor_ad_soyad_trigram")
    op.drop_table("sofor_ad_soyad_trigram")

    op.drop_column("soforler", "ad_soyad_bidx")
    op.drop_column("kullanicilar", "email_bidx")

    op.alter_column(
        "soforler", "ad_soyad", type_=sa.String(100), existing_nullable=False
    )
    op.alter_column("soforler", "telefon", type_=sa.String(20), existing_nullable=True)
    op.alter_column(
        "kullanicilar", "email", type_=sa.String(255), existing_nullable=False
    )
    op.alter_column(
        "kullanicilar", "ad_soyad", type_=sa.String(100), existing_nullable=False
    )

    op.create_index("ix_soforler_ad_soyad", "soforler", ["ad_soyad"], unique=True)
    op.create_index("ix_kullanicilar_email", "kullanicilar", ["email"], unique=True)
