"""2026-07-01 prod-grade denetimi P1 (Dalga 4 madde 19) — Idempotency-Key testleri.

`fuel.py`/`trips.py` POST uçlarında client timeout+retry çift kayıt
(yakıt/sefer) oluşturabiliyordu. `Idempotency-Key` header'ı desteği:
aynı key + aynı gövde → önbelleklenen yanıt, gerçek ikinci kayıt yok.
Aynı key + farklı gövde → 409.
"""

import asyncio
import uuid
from datetime import date

import pytest

pytestmark = pytest.mark.integration


def _plaka(prefix: str = "34 IK") -> str:
    num = int(uuid.uuid4().hex[:4], 16) % 9000 + 1000
    return f"{prefix} {num}"


async def _create_vehicle(async_client, admin_auth_headers) -> int:
    resp = await async_client.post(
        "/api/v1/vehicles/",
        json={
            "plaka": _plaka(),
            "marka": "Mercedes",
            "model": "Actros",
            "yil": 2021,
            "tank_kapasitesi": 600,
            "hedef_tuketim": 31.5,
            "aktif": True,
        },
        headers=admin_auth_headers,
    )
    assert resp.status_code == 201, resp.text
    return int(resp.json()["id"])


@pytest.mark.asyncio
async def test_fuel_create_same_idempotency_key_and_body_does_not_duplicate(
    async_client, admin_auth_headers
):
    arac_id = await _create_vehicle(async_client, admin_auth_headers)
    key = f"test-key-{uuid.uuid4().hex}"
    payload = {
        "tarih": date.today().isoformat(),
        "arac_id": arac_id,
        "litre": "100.00",
        "fiyat_tl": "42.00",
        "toplam_tutar": "4200.00",
        "km_sayac": 150000,
        "depo_durumu": "Dolu",
        "durum": "Bekliyor",
    }

    resp1 = await async_client.post(
        "/api/v1/fuel/",
        json=payload,
        headers={**admin_auth_headers, "Idempotency-Key": key},
    )
    assert resp1.status_code == 201, resp1.text
    first_id = resp1.json()["id"]

    resp2 = await async_client.post(
        "/api/v1/fuel/",
        json=payload,
        headers={**admin_auth_headers, "Idempotency-Key": key},
    )
    assert resp2.status_code == 201, resp2.text
    assert resp2.json()["id"] == first_id, (
        "İkinci istek AYNI kaydı dönmeliydi (önbelleklenmiş yanıt) — "
        "yeni bir yakıt kaydı oluşturuldu, idempotency çalışmıyor."
    )

    list_resp = await async_client.get(
        f"/api/v1/fuel/?arac_id={arac_id}", headers=admin_auth_headers
    )
    assert list_resp.status_code == 200
    matching = [r for r in list_resp.json()["items"] if r["id"] == first_id]
    assert len(matching) == 1


@pytest.mark.asyncio
async def test_fuel_create_same_idempotency_key_different_body_returns_409(
    async_client, admin_auth_headers
):
    arac_id = await _create_vehicle(async_client, admin_auth_headers)
    key = f"test-key-{uuid.uuid4().hex}"
    base_payload = {
        "tarih": date.today().isoformat(),
        "arac_id": arac_id,
        "litre": "100.00",
        "fiyat_tl": "42.00",
        "toplam_tutar": "4200.00",
        "km_sayac": 150000,
        "depo_durumu": "Dolu",
        "durum": "Bekliyor",
    }

    resp1 = await async_client.post(
        "/api/v1/fuel/",
        json=base_payload,
        headers={**admin_auth_headers, "Idempotency-Key": key},
    )
    assert resp1.status_code == 201, resp1.text

    different_payload = {**base_payload, "litre": "200.00", "km_sayac": 150500}
    resp2 = await async_client.post(
        "/api/v1/fuel/",
        json=different_payload,
        headers={**admin_auth_headers, "Idempotency-Key": key},
    )
    assert resp2.status_code == 409, resp2.text


@pytest.mark.asyncio
async def test_fuel_create_without_idempotency_key_keeps_prior_duplicate_guard(
    async_client, admin_auth_headers
):
    """Header gönderilmezse eski davranış korunuyor. Not: `yakit_service`
    (arac_id, tarih, litre) için kendi duplicate kontrolüne zaten sahip —
    idempotency-key olmadan aynı gövdeyi tekrar POST etmek bu ÖNCEDEN VAR
    OLAN iş kuralına takılıp 400 döner (yeni davranış değil, regresyon değil)."""
    arac_id = await _create_vehicle(async_client, admin_auth_headers)
    payload = {
        "tarih": date.today().isoformat(),
        "arac_id": arac_id,
        "litre": "100.00",
        "fiyat_tl": "42.00",
        "toplam_tutar": "4200.00",
        "km_sayac": 150000,
        "depo_durumu": "Dolu",
        "durum": "Bekliyor",
    }

    resp1 = await async_client.post(
        "/api/v1/fuel/", json=payload, headers=admin_auth_headers
    )
    assert resp1.status_code == 201, resp1.text
    resp2 = await async_client.post(
        "/api/v1/fuel/", json=payload, headers=admin_auth_headers
    )
    assert resp2.status_code == 400, resp2.text


@pytest.mark.asyncio
async def test_trip_create_without_idempotency_key_creates_duplicate_as_before(
    async_client, admin_auth_headers
):
    """`sefer_no` belirtilmeden POST edilirse otomatik üretilir — sefer
    domain'inde fuel'in aksine bir iş-kuralı duplicate koruması yok, bu
    yüzden header'sız aynı gövdeyi tekrar POST etmek gerçekten İKİ AYRI sefer
    oluşturur — bu, madde 19'un asıl önlemek istediği senaryo."""
    resp_arac = await async_client.post(
        "/api/v1/vehicles/",
        json={
            "plaka": _plaka("34 TR"),
            "marka": "Mercedes",
            "model": "Actros",
            "yil": 2021,
            "tank_kapasitesi": 600,
            "hedef_tuketim": 31.5,
            "aktif": True,
        },
        headers=admin_auth_headers,
    )
    assert resp_arac.status_code == 201, resp_arac.text
    arac_id = resp_arac.json()["id"]

    resp_sofor = await async_client.post(
        "/api/v1/drivers/",
        json={
            "ad_soyad": f"Idempotency Test {uuid.uuid4().hex[:6]}",
            "telefon": "05551112233",
            "ise_baslama": date.today().isoformat(),
            "ehliyet_sinifi": "E",
            "aktif": True,
        },
        headers=admin_auth_headers,
    )
    assert resp_sofor.status_code == 201, resp_sofor.text
    sofor_id = resp_sofor.json()["id"]

    payload = {
        "tarih": date.today().isoformat(),
        "arac_id": arac_id,
        "sofor_id": sofor_id,
        "cikis_yeri": "Istanbul",
        "varis_yeri": "Ankara",
        "mesafe_km": 450.0,
        "net_kg": 22000,
        "bos_sefer": False,
        "durum": "Planlandı",
    }

    resp1 = await async_client.post(
        "/api/v1/trips/", json=payload, headers=admin_auth_headers
    )
    assert resp1.status_code == 201, resp1.text
    resp2 = await async_client.post(
        "/api/v1/trips/", json=payload, headers=admin_auth_headers
    )
    assert resp2.status_code == 201, resp2.text
    assert resp2.json()["id"] != resp1.json()["id"], (
        "İki ayrı sefer kaydı bekleniyordu (Idempotency-Key gönderilmedi) — "
        "bu davranış madde 19'un koruması sadece header VARSA devreye "
        "girdiğini kanıtlıyor."
    )


@pytest.mark.asyncio
async def test_trip_create_same_idempotency_key_does_not_duplicate(
    async_client, admin_auth_headers
):
    resp_arac = await async_client.post(
        "/api/v1/vehicles/",
        json={
            "plaka": _plaka("34 TR"),
            "marka": "Mercedes",
            "model": "Actros",
            "yil": 2021,
            "tank_kapasitesi": 600,
            "hedef_tuketim": 31.5,
            "aktif": True,
        },
        headers=admin_auth_headers,
    )
    assert resp_arac.status_code == 201, resp_arac.text
    arac_id = resp_arac.json()["id"]

    resp_sofor = await async_client.post(
        "/api/v1/drivers/",
        json={
            "ad_soyad": f"Idempotency Test {uuid.uuid4().hex[:6]}",
            "telefon": "05551112233",
            "ise_baslama": date.today().isoformat(),
            "ehliyet_sinifi": "E",
            "aktif": True,
        },
        headers=admin_auth_headers,
    )
    assert resp_sofor.status_code == 201, resp_sofor.text
    sofor_id = resp_sofor.json()["id"]

    key = f"test-key-{uuid.uuid4().hex}"
    payload = {
        "tarih": date.today().isoformat(),
        "arac_id": arac_id,
        "sofor_id": sofor_id,
        "cikis_yeri": "Istanbul",
        "varis_yeri": "Ankara",
        "mesafe_km": 450.0,
        "net_kg": 22000,
        "bos_sefer": False,
        "durum": "Planlandı",
    }

    resp1 = await async_client.post(
        "/api/v1/trips/",
        json=payload,
        headers={**admin_auth_headers, "Idempotency-Key": key},
    )
    assert resp1.status_code == 201, resp1.text
    first_id = resp1.json()["id"]

    resp2 = await async_client.post(
        "/api/v1/trips/",
        json=payload,
        headers={**admin_auth_headers, "Idempotency-Key": key},
    )
    assert resp2.status_code == 201, resp2.text
    assert resp2.json()["id"] == first_id, (
        "İkinci istek AYNI sefer kaydını dönmeliydi (önbelleklenmiş yanıt) — "
        "yeni bir sefer oluşturuldu, idempotency çalışmıyor."
    )


@pytest.mark.asyncio
async def test_reserve_or_get_cached_concurrent_first_use_does_not_500(
    async_db_engine, monkeypatch
):
    """2026-07-01 derin kontrol bulgusu #1: ilk implementasyon (SELECT sonra
    ayrı bir INSERT/commit) aynı YENİ key ile gerçek eşzamanlı iki istekte
    ikisi de SELECT'te "yok" buluyor, ikisi de gerçek işi yapıyor, sonra
    ikinci commit yakalanmamış `IntegrityError` ile patlıyordu (500).

    `reserve_or_get_cached`/`finalize_response` artık kendi bağımsız
    session'larını `v2.modules.platform_infra.public.AsyncSessionLocal` üzerinden açıp
    anında commit ediyor (derin kontrol bulgusu #2 — bkz. idempotency_service.py
    modül docstring'i). Bu testte o isim GERÇEK bir `async_sessionmaker`'a
    (fixture'ın `async_db_engine`'ine bağlı) monkeypatch'lenir — fixture'ın
    normal test-session wrapper'ı TEK bir paylaşılan session döndürüp gerçek
    eşzamanlılığı maskeler, bu test tam da o maskelemeyi bypass etmeli."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    import v2.modules.platform_infra.public as platform_infra_public
    from v2.modules.admin_platform.application.idempotency_service import (
        IdempotencyKeyInProgressError,
        finalize_response,
        reserve_or_get_cached,
    )
    from v2.modules.admin_platform.public import IdempotencyKey

    real_session_local = async_sessionmaker(
        bind=async_db_engine, class_=AsyncSession, expire_on_commit=False
    )
    monkeypatch.setattr(platform_infra_public, "AsyncSessionLocal", real_session_local)

    key = f"race-key-{uuid.uuid4().hex}"
    endpoint = "TEST /race"
    request_body = {"foo": "bar"}

    a_reserved = asyncio.Event()
    release_a = asyncio.Event()
    results: dict[str, object] = {}

    async def actor_a():
        reservation = await reserve_or_get_cached(
            key=key, endpoint=endpoint, request_body=request_body
        )
        assert reservation.reserved is True
        a_reserved.set()
        await release_a.wait()
        await finalize_response(
            key=key, endpoint=endpoint, status_code=201, response_body={"winner": "a"}
        )
        results["a"] = "finalized"

    async def actor_b():
        await a_reserved.wait()
        # A henüz finalize etmedi (release_a set edilmedi) — B'nin isteği bu
        # dar pencerede gelirse eskiden yakalanmamış IntegrityError/500
        # üretiyordu; artık zarif bir IdempotencyKeyInProgressError bekleniyor.
        try:
            await reserve_or_get_cached(
                key=key, endpoint=endpoint, request_body=request_body
            )
            results["b"] = "reserved_unexpectedly"
        except IdempotencyKeyInProgressError:
            results["b"] = "in_progress"

    task_a = asyncio.create_task(actor_a())
    task_b = asyncio.create_task(actor_b())

    await a_reserved.wait()
    await asyncio.sleep(0.3)
    release_a.set()

    await asyncio.wait_for(asyncio.gather(task_a, task_b), timeout=10)

    assert results["a"] == "finalized"
    assert results["b"] == "in_progress", (
        f"B'nin isteği zarif bir IdempotencyKeyInProgressError almalıydı, "
        f"'{results['b']}' oldu — eşzamanlı ilk-kullanım yarışı hâlâ "
        "yakalanmamış bir hataya veya sessiz veri kaybına yol açıyor olabilir."
    )

    # A finalize ettikten SONRA aynı key ile üçüncü bir çağrı — artık
    # önbelleklenmiş (finalize edilmiş) yanıtı görmeli.
    third = await reserve_or_get_cached(
        key=key, endpoint=endpoint, request_body=request_body
    )
    assert third.reserved is False
    assert third.cached == (201, {"winner": "a"})

    async with real_session_local() as check_session:
        rows = (
            (
                await check_session.execute(
                    select(IdempotencyKey).where(
                        IdempotencyKey.key == key, IdempotencyKey.endpoint == endpoint
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1, (
            f"Tabloda tam olarak 1 satır bekleniyordu, {len(rows)} bulundu — "
            "eşzamanlı ilk-kullanım yarışı duplicate/orphan satır bırakmış."
        )
        assert rows[0].response_status_code == 201
