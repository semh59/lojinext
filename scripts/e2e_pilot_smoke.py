"""End-to-end pilot smoke testi.

KULLANIM:
    python scripts/e2e_pilot_smoke.py

NE YAPAR:
    1. TRUNCATE iş verisini (auth korunur)
    2. /tmp altına 5 sample Excel dosyası üretir (araç, şoför, lokasyon,
       sefer, yakıt)
    3. Her birini sırasıyla backend'e yükler (auth + upload endpoint)
    4. Yanıtları assert eder (success_count beklenen, errors == [])
    5. Final state: DB'den dashboard + reports endpoint'leri probe eder
    6. Toplam süreyi raporlar

AMAÇ: Senin kullanacağın gerçek pipeline'ı sample data ile doğrula.
       Sapma varsa burada yakalanır, gerçek Excel'in geldiğinde temiz olsun.
"""

from __future__ import annotations

import io
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from typing import List, Tuple

import pandas as pd

BASE_URL = os.getenv("LOJINEXT_BASE_URL", "http://127.0.0.1:8000")
ADMIN_USER = os.getenv("SUPER_ADMIN_USERNAME", "admin")
ADMIN_PASS = os.getenv("SUPER_ADMIN_PASSWORD")
if not ADMIN_PASS:
    raise SystemExit(
        "SUPER_ADMIN_PASSWORD env var zorunlu — script default şifre içermez."
    )


def _login() -> str:
    """OAuth2 form login → bearer token."""
    body = urllib.parse.urlencode(
        {"username": ADMIN_USER, "password": ADMIN_PASS}
    ).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/api/v1/auth/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        import json as _json

        return _json.load(r)["access_token"]


def _post_excel(
    token: str, url: str, df: pd.DataFrame, sheet_name: str = "Sablon"
) -> Tuple[int, str]:
    """Pandas DataFrame'i XLSX olarak gönderir, (status, body) döner."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
    content = buf.getvalue()
    boundary = "----LojiNextSmoke7e8d"
    body_parts: List[bytes] = []
    body_parts.append(f"--{boundary}\r\n".encode())
    body_parts.append(
        b'Content-Disposition: form-data; name="file"; filename="sample.xlsx"\r\n'
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
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def _get(token: str, path: str) -> Tuple[int, str]:
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def _post_json(token: str, path: str, body: dict) -> Tuple[int, str]:
    import json as _json

    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=_json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


# ── Sample data builders ───────────────────────────────────────────────────


def vehicles_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ["34 PIL 001", "Mercedes", "Actros 2645", 2022, "DIZEL"],
            ["34 PIL 002", "Volvo", "FH16", 2021, "DIZEL"],
            ["06 PIL 003", "Scania", "R450", 2023, "DIZEL"],
        ],
        columns=["Plaka", "Marka", "Model", "Yil", "Yakit_Tipi"],
    )


def drivers_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ["Pilot Şoför Bir", "0555 100 00 01", "2023-01-15", "CE"],
            ["Pilot Şoför İki", "0555 100 00 02", "2022-08-01", "CE"],
        ],
        columns=["Ad_Soyad", "Telefon", "Ise_Baslama", "Ehliyet_Sinifi"],
    )


def locations_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            [
                "İstanbul Kadıköy",
                "Ankara Sincan",
                40.9924,
                29.0271,
                39.9709,
                32.5816,
                450,
                5.5,
                320,
                180,
            ],
            [
                "Ankara Sincan",
                "İzmir Bornova",
                39.9709,
                32.5816,
                38.4731,
                27.2117,
                580,
                7.0,
                280,
                250,
            ],
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


def trips_df() -> pd.DataFrame:
    today = date.today()
    rows = []
    for i in range(5):
        d = today - timedelta(days=i * 2)
        plaka = ["34 PIL 001", "34 PIL 002", "06 PIL 003"][i % 3]
        sofor = ["Pilot Şoför Bir", "Pilot Şoför İki"][i % 2]
        if i % 2 == 0:
            cikis, varis, mesafe = "İstanbul Kadıköy", "Ankara Sincan", 450
        else:
            cikis, varis, mesafe = "Ankara Sincan", "İzmir Bornova", 580
        rows.append(
            [
                d.isoformat(),
                "09:00",
                cikis,
                varis,
                mesafe,
                15000,
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


def fuel_df() -> pd.DataFrame:
    today = date.today()
    rows = []
    # Yakıt fişleri her araç için ayrı km zinciri — bulk_add_yakit
    # ``km_sayac < last_km`` ise skip eder. Tarih ascending sıralanır;
    # km de tarih ile beraber artmalı yoksa odometer kontrolü skip eder.
    plates = ["34 PIL 001", "34 PIL 002", "06 PIL 003"]
    per_plate_km = {p: 100_000 for p in plates}
    rows_data = []
    for day_offset in range(7, -1, -1):  # 7 gün önce → bugün (eski→yeni)
        plaka = plates[day_offset % len(plates)]
        per_plate_km[plaka] += 500  # her dolumda 500 km
        rows_data.append((day_offset, plaka, per_plate_km[plaka]))
    for idx, (day_offset, plaka, km) in enumerate(rows_data):
        d = today - timedelta(days=day_offset)
        rows.append(
            [
                d.isoformat(),
                plaka,
                "Shell Pilot",
                42.5 + idx * 0.1,  # Litre (40-50 L)
                42.0 + idx * 0.05,  # Fiyat (TL/L)
                km,
                f"PILOT-{idx:03d}",
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


# ── Pilot runner ──────────────────────────────────────────────────────────


def _check(label: str, status: int, expected: int, body: str) -> bool:
    ok = status == expected
    icon = "[OK]" if ok else "[FAIL]"
    print(
        f"  {icon} {label}: HTTP {status} {'OK' if ok else 'EXPECTED ' + str(expected)}"
    )
    if not ok:
        print(f"    body: {body[:300]}")
    return ok


def _check_upload(label: str, status: int, body: str, expected_rows: int) -> bool:
    """Upload response'unun gerçekten DB'ye veri yazdığını doğrular.

    Backend her şablon için farklı şema döndürdüğü için her şemayı tek tek
    kontrol et:
      - arac/sofor:  ``{"success": bool, "message": str, "errors": list}``
      - route:       ``{"count": int, "errors": list}``
      - sefer/fuel:  ``{"success_count": int, "saved": int, "errors": list}``

    Sadece HTTP 200 değil; ``saved/success_count/count >= expected_rows`` ve
    ``errors`` boş olmalı.
    """
    import json as _json

    if status != 200:
        print(f"  [FAIL] {label}: HTTP {status} (beklenen 200)")
        print(f"    body: {body[:300]}")
        return False
    try:
        payload = _json.loads(body)
    except Exception:
        print(f"  [FAIL] {label}: response JSON parse edilemedi → {body[:200]}")
        return False

    saved = (
        payload.get("count")
        or payload.get("saved")
        or payload.get("success_count")
        or 0
    )
    # arac/sofor için ``message: "N araç yüklendi"`` parse fallback
    if saved == 0 and isinstance(payload.get("message"), str):
        import re as _re

        m = _re.match(r"^(\d+)\s+", payload["message"])
        if m:
            saved = int(m.group(1))

    errors = payload.get("errors") or []
    ok = saved >= expected_rows and not errors
    icon = "[OK]" if ok else "[FAIL]"
    print(
        f"  {icon} {label}: HTTP 200, saved={saved}/{expected_rows}, "
        f"errors={len(errors)}"
    )
    if errors:
        # İlk 3 hatayı göster
        for err in errors[:3]:
            print(f"      - {err}")
    return ok


def run() -> int:
    print(f"[{time.strftime('%H:%M:%S')}] LojiNext pilot smoke başlıyor — {BASE_URL}")
    t0 = time.time()

    # 1) Login
    try:
        token = _login()
    except Exception as exc:
        print(f"  [FAIL] login: {exc}")
        return 2
    print(f"  [OK] login OK (token len={len(token)})")

    failures = 0

    # 2) Araçlar
    print("\n[1/5] Araçlar")
    df = vehicles_df()
    s, b = _post_excel(token, f"{BASE_URL}/api/v1/vehicles/upload", df)
    if not _check_upload("araç upload", s, b, expected_rows=len(df)):
        failures += 1

    # 3) Şoförler
    print("\n[2/5] Şoförler")
    df = drivers_df()
    s, b = _post_excel(token, f"{BASE_URL}/api/v1/drivers/excel/upload", df)
    if not _check_upload("şoför upload", s, b, expected_rows=len(df)):
        failures += 1

    # 4) Lokasyonlar
    print("\n[3/5] Lokasyonlar")
    df = locations_df()
    s, b = _post_excel(token, f"{BASE_URL}/api/v1/locations/upload", df)
    if not _check_upload("lokasyon upload", s, b, expected_rows=len(df)):
        failures += 1

    # 5) Seferler
    print("\n[4/5] Seferler")
    df = trips_df()
    s, b = _post_excel(token, f"{BASE_URL}/api/v1/trips/upload", df)
    if not _check_upload("sefer upload", s, b, expected_rows=len(df)):
        failures += 1

    # 6) Yakıt fişleri
    print("\n[5/5] Yakıt fişleri")
    df = fuel_df()
    s, b = _post_excel(token, f"{BASE_URL}/api/v1/fuel/excel/upload", df)
    if not _check_upload("yakıt upload", s, b, expected_rows=len(df)):
        failures += 1

    # ── Verify ────────────────────────────────────────────────────────────
    print("\n[Verify] Dashboard + RV2 endpoint'leri")
    for path, expect in [
        ("/api/v1/health/", 200),
        ("/api/v1/auth/me", 200),
        ("/api/v1/locations/", 200),
        ("/api/v1/predictions/ensemble/status", 200),
        ("/api/v1/reports/dashboard", 200),
        ("/api/v1/trips/", 200),
        ("/api/v1/vehicles/", 200),
        ("/api/v1/drivers/", 200),
        ("/api/v1/fuel/stats", 200),
        ("/api/v1/anomalies/fleet/insights?days=30", 200),
        ("/api/v1/reports/today/triage", 200),
        ("/api/v1/reports/insights/fleet/comparison?period=week", 200),
        ("/api/v1/reports/studio/templates", 200),
    ]:
        s, b = _get(token, path)
        if not _check(path, s, expect, b):
            failures += 1

    dt = time.time() - t0
    print(f"\n[{time.strftime('%H:%M:%S')}] Toplam {dt:.1f}sn — failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run())
