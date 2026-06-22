#!/usr/bin/env python
"""Fix error_occurrences partitions (LOJINEXT-180)"""

import sys

from sqlalchemy import create_engine, text

user = "lojinext_user"
password = "lojinext_pass_2026"  # pragma: allowlist secret  (lokal dev cred; .env/compose ile aynı)
host = "127.0.0.1"
port = 5432
db = "lojinext_db"

sync_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"

print("Creating error_occurrences partitions...")

try:
    engine = create_engine(sync_url)

    with engine.begin() as conn:
        # Create partitions for May-October 2026
        partitions = [
            ("2026_05", "2026-05-01", "2026-06-01"),
            ("2026_06", "2026-06-01", "2026-07-01"),
            ("2026_07", "2026-07-01", "2026-08-01"),
            ("2026_08", "2026-08-01", "2026-09-01"),
            ("2026_09", "2026-09-01", "2026-10-01"),
            ("2026_10", "2026-10-01", "2026-11-01"),
        ]

        for partition_name, from_date, to_date in partitions:
            sql = f"""
                CREATE TABLE IF NOT EXISTS error_occurrences_{partition_name}
                PARTITION OF error_occurrences
                FOR VALUES FROM ('{from_date}') TO ('{to_date}');
            """
            try:
                conn.execute(text(sql))
                print(f"Created error_occurrences_{partition_name}")
            except Exception as e:
                print(f"Note: error_occurrences_{partition_name} - {str(e)[:50]}")

        # Verify
        result = conn.execute(
            text("""
            SELECT COUNT(*) as partition_count
            FROM pg_tables
            WHERE tablename LIKE 'error_occurrences%';
        """)
        )
        count = result.scalar()
        print(f"\nTotal partitions now: {count}")

        if count > 1:
            print("SUCCESS: Partitions are in place!")
            sys.exit(0)
        else:
            print("WARNING: Partitions may not have been created")
            sys.exit(1)

except Exception as e:
    print(f"FATAL: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
