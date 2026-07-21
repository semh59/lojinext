"""GET /fuel/documents belge arşivi testleri."""

import pytest
from sqlalchemy import text

from v2.modules.driver.public import Sofor

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def test_documents_lists_fuel_receipts(
    async_client, admin_auth_headers, db_session
):
    sofor = Sofor(ad_soyad="S", aktif=True)
    db_session.add(sofor)
    await db_session.commit()
    await db_session.refresh(sofor)
    sofor_id = sofor.id
    await db_session.execute(
        text(
            "INSERT INTO sefer_belgeler (sofor_id, belge_tipi, dosya_yolu, ocr_durumu) "
            "VALUES (:s, 'yakit_fisi', '/tmp/x.jpg', 'islendi')"
        ),
        {"s": sofor_id},
    )
    await db_session.commit()

    resp = await async_client.get("/api/v1/fuel/documents", headers=admin_auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(i["belge_tipi"] == "yakit_fisi" for i in items)


async def test_documents_requires_admin(async_client, normal_auth_headers):
    resp = await async_client.get("/api/v1/fuel/documents", headers=normal_auth_headers)
    assert resp.status_code == 403
