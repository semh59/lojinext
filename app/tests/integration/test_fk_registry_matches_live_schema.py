"""FAZ2 Wave 1 — `arch/fk_registry.yml` must exactly match the live schema.

Symmetric diff: a new cross-schema FK that isn't registered fails, AND a
stale registry entry whose FK no longer exists also fails. This is the
CI-blocking mechanism that turns "add a cross-schema FK" into "add a
reviewed line to arch/fk_registry.yml" — see that file's own header and
`scripts/faz2_generate_fk_registry_seed.py` for how it was seeded.
"""

from pathlib import Path

import pytest
import yaml
from sqlalchemy import text

pytestmark = pytest.mark.integration

_REGISTRY_PATH = Path(__file__).resolve().parents[3] / "arch" / "fk_registry.yml"

_LIVE_EDGES_QUERY = """
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


async def test_fk_registry_matches_live_schema(db_session):
    result = await db_session.execute(text(_LIVE_EDGES_QUERY))
    live_edges = {
        (f"{row.from_schema}.{row.from_table}.{row.from_column}", f"{row.to_schema}.{row.to_table}.{row.to_column}")
        for row in result
    }

    registry = yaml.safe_load(_REGISTRY_PATH.read_text(encoding="utf-8"))
    registered_edges = {(edge["from"], edge["to"]) for edge in registry["edges"]}

    undocumented = live_edges - registered_edges
    stale = registered_edges - live_edges

    assert not undocumented, (
        f"Cross-schema FK(s) exist in the live schema but are NOT in "
        f"arch/fk_registry.yml — add them: {sorted(undocumented)}"
    )
    assert not stale, (
        f"arch/fk_registry.yml has edge(s) that no longer exist in the "
        f"live schema — remove them: {sorted(stale)}"
    )
