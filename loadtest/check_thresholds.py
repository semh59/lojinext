"""Locust CSV özet sonucunu gate eşiklerine göre doğrular (GO gate #4).

Locust `--csv <prefix>` ile `<prefix>_stats.csv` üretir; "Aggregated" satırından
istek/başarısızlık sayısı ve p95 latency okunur. Eşik aşılırsa exit 1 → CI job FAIL.

Kullanım:
    python loadtest/check_thresholds.py <prefix> [--p95-ms 2000] [--fail-pct 1.0]

Env ile de override edilebilir: LT_P95_MS, LT_FAIL_PCT.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys


def _load_aggregated(stats_csv: str) -> dict[str, str]:
    with open(stats_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if (row.get("Name") or "").strip() == "Aggregated":
                return row
    raise SystemExit(f"'Aggregated' satırı bulunamadı: {stats_csv}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("prefix", help="locust --csv prefix (örn. loadtest/results)")
    ap.add_argument(
        "--p95-ms",
        type=float,
        default=float(os.getenv("LT_P95_MS", "2000")),
        help="İzin verilen maksimum p95 latency (ms)",
    )
    ap.add_argument(
        "--fail-pct",
        type=float,
        default=float(os.getenv("LT_FAIL_PCT", "1.0")),
        help="İzin verilen maksimum başarısızlık oranı (%%)",
    )
    args = ap.parse_args()

    row = _load_aggregated(f"{args.prefix}_stats.csv")
    reqs = int(row["Request Count"])
    fails = int(row["Failure Count"])
    p95 = float(row["95%"])
    fail_pct = (fails / reqs * 100) if reqs else 0.0

    print(f"Toplam istek : {reqs}")
    print(f"Başarısız    : {fails} ({fail_pct:.2f}%)  [eşik < {args.fail_pct}%]")
    print(f"p95 latency  : {p95:.0f} ms          [eşik < {args.p95_ms:.0f} ms]")

    breaches = []
    if reqs == 0:
        breaches.append("hiç istek kaydedilmedi (harness/host hatası)")
    if fail_pct > args.fail_pct:
        breaches.append(f"fail oranı {fail_pct:.2f}% > {args.fail_pct}%")
    if p95 > args.p95_ms:
        breaches.append(f"p95 {p95:.0f}ms > {args.p95_ms:.0f}ms")

    if breaches:
        print("\nGATE #4 FAIL:")
        for b in breaches:
            print(f"  - {b}")
        return 1

    print("\nGATE #4 PASS ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
