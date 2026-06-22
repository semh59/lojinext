"""LojiNext yük testi — Locust senaryosu (GO harekatı gate #4).

Pilot trafiğinin 3-5x'ini simüle eder. READ-ağırlıklı: prod/staging veriyi
bozmaz (yazma görevleri default kapalı, ENABLE_WRITES=1 ile açılır).

Çalıştırma:
    pip install -r loadtest/requirements.txt
    # Web UI ile:
    LOAD_USER=admin LOAD_PASS=*** locust -f loadtest/locustfile.py --host https://staging.lojinext.example
    # Headless (CI/otomasyon), pilot 3-5x:
    LOAD_USER=admin LOAD_PASS=*** locust -f loadtest/locustfile.py \
        --host https://staging.lojinext.example \
        --headless -u 150 -r 15 -t 10m --csv loadtest/results

Parametreler (env):
    LOAD_USER / LOAD_PASS   — giriş kimlik bilgileri (zorunlu)
    API_PREFIX              — default /api/v1
    ENABLE_WRITES=1         — sefer create gibi yazma görevlerini de koş (DİKKAT: veri üretir)

Eşik (GO gate #4 — pilot trafiğinin 3-5x'inde karşılanmalı):
    - p95 latency < 800ms (read endpoint'leri)
    - hata oranı (5xx) < %1
    - 0 unhandled exception (Sentry'de doğrula)
    - /system/silent-fallbacks sayaçları yük altında patlamamalı
"""

from __future__ import annotations

import os
import random

from locust import HttpUser, between, events, task

API_PREFIX = os.getenv("API_PREFIX", "/api/v1")
LOAD_USER = os.getenv("LOAD_USER", "")
LOAD_PASS = os.getenv("LOAD_PASS", "")
ENABLE_WRITES = os.getenv("ENABLE_WRITES", "0") == "1"


@events.test_start.add_listener
def _check_creds(environment, **_kwargs):
    if not LOAD_USER or not LOAD_PASS:
        raise SystemExit(
            "LOAD_USER ve LOAD_PASS env değişkenleri zorunlu. "
            "Örn: LOAD_USER=admin LOAD_PASS=*** locust -f loadtest/locustfile.py ..."
        )


class OperatorUser(HttpUser):
    """Tipik bir operatörün okuma-ağırlıklı oturumunu taklit eder."""

    # Gerçek kullanıcı düşünme süresi — saniyede sürekli istek değil.
    wait_time = between(1, 4)

    def on_start(self) -> None:
        """Oturum başında giriş yap, token'ı sakla."""
        resp = self.client.post(
            f"{API_PREFIX}/auth/token",
            data={"username": LOAD_USER, "password": LOAD_PASS},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            name="POST /auth/token",
        )
        if resp.status_code != 200:
            resp.failure(f"Login failed: {resp.status_code} {resp.text[:120]}")
            self.token = None
            return
        self.token = resp.json().get("access_token")

    @property
    def _auth(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    # ── Yüksek frekans: liste + dashboard (operatörün en çok baktığı) ─────────

    @task(10)
    def list_trips(self):
        page = random.randint(1, 5)
        self.client.get(
            f"{API_PREFIX}/trips/?page={page}&page_size=20",
            headers=self._auth,
            name="GET /trips/ (list)",
        )

    @task(8)
    def trip_stats(self):
        self.client.get(
            f"{API_PREFIX}/trips/stats",
            headers=self._auth,
            name="GET /trips/stats",
        )

    @task(6)
    def today_trips(self):
        self.client.get(
            f"{API_PREFIX}/trips/today",
            headers=self._auth,
            name="GET /trips/today",
        )

    @task(5)
    def fleet_stats(self):
        self.client.get(
            f"{API_PREFIX}/vehicles/fleet-stats",
            headers=self._auth,
            name="GET /vehicles/fleet-stats",
        )

    # ── Orta frekans: envanter listeleri ─────────────────────────────────────

    @task(5)
    def list_vehicles(self):
        self.client.get(
            f"{API_PREFIX}/vehicles/",
            headers=self._auth,
            name="GET /vehicles/",
        )

    @task(4)
    def list_drivers(self):
        self.client.get(
            f"{API_PREFIX}/drivers/",
            headers=self._auth,
            name="GET /drivers/",
        )

    @task(3)
    def list_fuel(self):
        self.client.get(
            f"{API_PREFIX}/fuel/",
            headers=self._auth,
            name="GET /fuel/",
        )

    @task(3)
    def fuel_performance(self):
        self.client.get(
            f"{API_PREFIX}/trips/analytics/fuel-performance",
            headers=self._auth,
            name="GET /trips/analytics/fuel-performance",
        )

    # ── Düşük frekans: ağır hesaplama + raporlar ─────────────────────────────

    @task(2)
    def executive_kpi(self):
        self.client.get(
            f"{API_PREFIX}/reports/executive/kpi?days=30",
            headers=self._auth,
            name="GET /reports/executive/kpi",
        )

    @task(2)
    def anomalies(self):
        self.client.get(
            f"{API_PREFIX}/anomalies/?status=open",
            headers=self._auth,
            name="GET /anomalies/",
        )

    # ── Observability — yük altında silent fallback / coverage izle ──────────

    @task(1)
    def observability_probe(self):
        # Bu iki endpoint gate #3'ün gözlemlenebilirlik yüzeyidir; yük altında
        # silent-fallback sayaçlarının patlayıp patlamadığını burada görürüz.
        self.client.get(
            f"{API_PREFIX}/admin/fuel-accuracy",
            headers=self._auth,
            name="GET /admin/fuel-accuracy",
        )
        self.client.get(
            f"{API_PREFIX}/system/silent-fallbacks",
            headers=self._auth,
            name="GET /system/silent-fallbacks",
        )

    # ── Yazma görevi (default KAPALI — veri üretir) ──────────────────────────

    @task(1)
    def create_trip_optional(self):
        if not ENABLE_WRITES:
            return
        payload = {
            "cikis_yeri": "Istanbul",
            "varis_yeri": "Ankara",
            "mesafe_km": 450.0,
            "tarih": "2026-06-10",
            "arac_id": 1,
            "sofor_id": 1,
        }
        self.client.post(
            f"{API_PREFIX}/trips/",
            json=payload,
            headers=self._auth,
            name="POST /trips/ (write)",
        )
