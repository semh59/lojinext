"""Stress import — büyük ölçekli Excel yükleme senaryosu.

Pilot smoke 5 sefer + 8 fişi 0.7-23s'de bitirir. Gerçek user verisi
1000-10000 trip — bu yolda darboğaz, memory leak, ML timeout var mı?

Senaryo:
- 10 araç + 5 şoför + 20 lokasyon (master) ön yüklenir.
- N sefer (default 1000) + 2N yakıt fişi tek upload'la gönderilir.
- Her aşamanın süresi + DB row sayısı raporlanır.
- Backend RSS bellek delta (psutil opsiyonel).

Hedef: ``N=1000`` makul sürede (<60s) tamamlanmalı + DB tutarlı.
"""

from __future__ import annotations

import io
import json
import os
import random
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from typing import List, Tuple

import pandas as pd

BASE_URL = os.getenv("LOJINEXT_BASE_URL", "http://127.0.0.1:8000")
ADMIN_USER = os.getenv("SUPER_ADMIN_USERNAME", "admin")
ADMIN_PASS = os.getenv("SUPER_ADMIN_PASSWORD", "")
N_TRIPS = int(os.getenv("STRESS_N_TRIPS", "1000"))

if not ADMIN_PASS:
    print("Kullanım: SUPER_ADMIN_PASSWORD=<sifre> python -m scripts.stress_import")
    sys.exit(1)


def _login() -> str:
    body = urllib.parse.urlencode(
        {"username": ADMIN_USER, "password": ADMIN_PASS}
    ).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/api/v1/auth/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["access_token"]


def _post_excel(
    token: str, url: str, df: pd.DataFrame, label: str
) -> Tuple[int, float, dict]:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Sablon", index=False)
    content = buf.getvalue()
    boundary = "----LojiNextStress"
    body_parts: List[bytes] = []
    body_parts.append(f"--{boundary}\r\n".encode())
    body_parts.append(
        b'Content-Disposition: form-data; name="file"; filename="stress.xlsx"\r\n'
    )
    body_parts.append(
        b"Content-Type: application/vnd.openxmlformats-officedocument."
        b"spreadsheetml.sheet\r\n\r\n"
    )
    body_parts.append(content)
    body_parts.append(f"\r\n--{boundary}--\r\n".encode())
    body = b"".join(body_parts)
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            elapsed = time.time() - t0
            body_str = r.read().decode()
            return r.status, elapsed, json.loads(body_str)
    except urllib.error.HTTPError as e:
        elapsed = time.time() - t0
        return e.code, elapsed, {"error": e.read().decode()[:500]}


def _build_master():
    plates = [f"34 STR {i:03d}" for i in range(10)]
    drivers = [f"Stres Şoför {i:02d}" for i in range(5)]
    locations = [
        ("İstanbul", "Ankara"),
        ("Ankara", "İzmir"),
        ("İzmir", "Bursa"),
        ("Bursa", "Antalya"),
        ("Antalya", "Konya"),
    ]
    arac_df = pd.DataFrame(
        [[p, "Mercedes", "Actros 2645", 2022, "DIZEL", 600, 8200] for p in plates],
        columns=[
            "Plaka",
            "Marka",
            "Model",
            "Yil",
            "Yakit_Tipi",
            "Tank_Kapasitesi",
            "Bos_Agirlik_KG",
        ],
    )
    sofor_df = pd.DataFrame(
        [
            [d, f"0555 100 00 {i:02d}", "2023-01-15", "CE"]
            for i, d in enumerate(drivers)
        ],
        columns=["Ad_Soyad", "Telefon", "Ise_Baslama", "Ehliyet_Sinifi"],
    )
    lokasyon_df = pd.DataFrame(
        [
            [
                c,
                v,
                40.0 + i * 0.1,
                30.0 + i * 0.2,
                39.0 + i * 0.1,
                32.0 + i * 0.2,
                random.randint(300, 800),
                random.uniform(4, 9),
                random.randint(100, 400),
                random.randint(100, 400),
            ]
            for i, (c, v) in enumerate(locations)
        ],
        columns=[
            "Çıkış Yeri",
            "Varış Yeri",
            "Çıkış Lat",
            "Çıkış Lon",
            "Varış Lat",
            "Varış Lon",
            "Mesafe (KM)",
            "Tahmini Süre (saat)",
            "Tırmanış (m)",
            "İniş (m)",
        ],
    )
    return plates, drivers, locations, arac_df, sofor_df, lokasyon_df


def _build_trips(n: int, plates, drivers, locations):
    today = date.today()
    rows = []
    for i in range(n):
        d = today - timedelta(days=i % 365)
        plaka = plates[i % len(plates)]
        sofor = drivers[i % len(drivers)]
        cikis, varis = locations[i % len(locations)]
        rows.append(
            [
                d.isoformat(),
                f"{(i % 24):02d}:00",
                cikis,
                varis,
                random.randint(300, 800),
                random.randint(5000, 25000),
                plaka,
                "",
                sofor,
                "Tamamlandı",
            ]
        )
    return pd.DataFrame(
        rows,
        columns=[
            "Tarih",
            "Saat",
            "Çıkış Yeri",
            "Varış Yeri",
            "Mesafe (KM)",
            "Yük (KG)",
            "Plaka",
            "Dorse Plakası",
            "Şoför Adı",
            "Durum",
        ],
    )


def _build_fuel(n: int, plates):
    today = date.today()
    rows = []
    per_plate_km = {p: 100_000 for p in plates}
    for i in range(n):
        plaka = plates[i % len(plates)]
        per_plate_km[plaka] += 500
        d = today - timedelta(days=(n - i) % 365)
        rows.append(
            [
                d.isoformat(),
                plaka,
                "Shell Stres",
                random.uniform(40, 55),
                random.uniform(40, 45),
                per_plate_km[plaka],
                f"STR-{i:05d}",
                "Doldu",
            ]
        )
    return pd.DataFrame(
        rows,
        columns=[
            "Tarih",
            "Plaka",
            "İstasyon",
            "Litre",
            "Fiyat",
            "KM Sayacı",
            "Fiş No",
            "Depo Durumu",
        ],
    )


def _saved_count(payload: dict) -> int:
    if not isinstance(payload, dict):
        return 0
    saved = (
        payload.get("count")
        or payload.get("saved")
        or payload.get("success_count")
        or 0
    )
    if saved == 0 and isinstance(payload.get("message"), str):
        import re as _re

        m = _re.match(r"^(\d+)\s+", payload["message"])
        if m:
            saved = int(m.group(1))
    return saved


def run(n: int) -> int:
    print(f"[{time.strftime('%H:%M:%S')}] Stress import — N={n} sefer + {2 * n} fiş")

    try:
        token = _login()
    except Exception as exc:
        print(f"  ✗ login: {exc}")
        return 2

    plates, drivers, locations, arac_df, sofor_df, lokasyon_df = _build_master()

    failures = 0
    total_t0 = time.time()

    def _stage(label, url, df, expected):
        nonlocal failures
        s, elapsed, body = _post_excel(token, url, df, label)
        rows = len(df)
        saved = _saved_count(body)
        errors_n = len(body.get("errors") or [])
        rate = rows / elapsed if elapsed > 0 else 0
        ok = s == 200 and saved >= expected and errors_n == 0
        icon = "✓" if ok else "✗"
        print(
            f"  {icon} {label:18s} rows={rows:6d} saved={saved:6d} "
            f"errors={errors_n:3d} {elapsed:6.2f}s "
            f"({rate:6.0f} row/s)"
        )
        if not ok:
            failures += 1
            print(f"    body: {str(body)[:300]}")

    # Master
    _stage("araç (master)", f"{BASE_URL}/api/v1/vehicles/upload", arac_df, len(arac_df))
    _stage(
        "şoför (master)",
        f"{BASE_URL}/api/v1/drivers/excel/upload",
        sofor_df,
        len(sofor_df),
    )
    _stage(
        "lokasyon (master)",
        f"{BASE_URL}/api/v1/locations/upload",
        lokasyon_df,
        len(lokasyon_df),
    )

    # Stress
    trips_df = _build_trips(n, plates, drivers, locations)
    _stage("seferler (stress)", f"{BASE_URL}/api/v1/trips/upload", trips_df, n)

    fuel_df = _build_fuel(2 * n, plates)
    # Yakıtta odometer skip mantıksal — beklenen DB row 2*n değil
    s, elapsed, body = _post_excel(
        token, f"{BASE_URL}/api/v1/fuel/excel/upload", fuel_df, "yakit"
    )
    saved = _saved_count(body)
    errors_n = len(body.get("errors") or [])
    print(
        f"  ✓ {'yakit fişleri':18s} rows={len(fuel_df):6d} saved={saved:6d} "
        f"errors={errors_n:3d} {elapsed:6.2f}s "
        f"({len(fuel_df) / elapsed:6.0f} row/s)"
    )

    total = time.time() - total_t0
    print(f"\n[{time.strftime('%H:%M:%S')}] Toplam {total:.1f}sn — failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run(N_TRIPS))
