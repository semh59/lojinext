"""FAZ2 Wave 1 — `arch/fk_registry.yml` tek-seferlik üretici (CI'da ÇALIŞMAZ).

`arch/fk_registry.yml`'in amacı insan incelemesi: yeni bir çapraz-şema FK
eklendiğinde bir PR reviewer'ı görsün diye elle commit'lenen bir dosya. Bu
script yalnız o dosyanın İLK haline seed sağlar — gerçek/migrate edilmiş bir
DB'ye karşı `pg_constraint`/`pg_class`/`pg_namespace` sorgusuyla mevcut TÜM
çapraz-şema FK'ları bulup YAML basar. Çıktı, doğrulanmış 42-kenar listesiyle
(bkz. TASKS/faz2-db-rol-izolasyonu-ve-read-model-grantlari.md) çapraz
kontrol edilip elle `arch/fk_registry.yml`'e yazılır.

Kullanım:
    DATABASE_URL=postgresql+asyncpg://... python -m scripts.faz2_generate_fk_registry_seed
"""

from __future__ import annotations

import asyncio
import os
import sys

import yaml
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

_QUERY = """
SELECT ns.nspname AS from_schema, cl.relname AS from_table, att.attname AS from_column,
       fns.nspname AS to_schema, fcl.relname AS to_table, fatt.attname AS to_column
FROM pg_constraint con
JOIN pg_class cl ON cl.oid = con.conrelid
JOIN pg_namespace ns ON ns.oid = cl.relnamespace
JOIN pg_class fcl ON fcl.oid = con.confrelid
JOIN pg_namespace fns ON fns.oid = fcl.relnamespace
JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS ck(attnum, ord) ON true
JOIN LATERAL unnest(con.confkey) WITH ORDINALITY AS cfk(attnum, ord) ON ck.ord = cfk.ord
JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = ck.attnum
JOIN pg_attribute fatt ON fatt.attrelid = con.confrelid AND fatt.attnum = cfk.attnum
WHERE con.contype = 'f' AND ns.nspname <> fns.nspname
ORDER BY 1, 2, 3;
"""


async def _fetch_edges(database_url: str) -> list[dict]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text(_QUERY))
            edges = []
            for row in result:
                edges.append(
                    {
                        "from": f"{row.from_schema}.{row.from_table}.{row.from_column}",
                        "to": f"{row.to_schema}.{row.to_table}.{row.to_column}",
                    }
                )
            return edges
    finally:
        await engine.dispose()


async def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL env var gerekli.", file=sys.stderr)
        sys.exit(1)

    edges = await _fetch_edges(database_url)
    print(f"# {len(edges)} cross-schema FK edges found", file=sys.stderr)
    print(yaml.safe_dump({"edges": edges}, sort_keys=False, allow_unicode=True))


if __name__ == "__main__":
    asyncio.run(main())
