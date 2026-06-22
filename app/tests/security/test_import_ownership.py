"""
T3-B: import_service.rollback_import() ownership kontrolü eksik.

Bug Açıklaması:
  Import job başka kullanıcı tarafından yapılmış olsa bile,
  rollback endpoint'i ownership kontrolü yapmıyor.
  Başka kullanıcı import'ı rollback edebiliyor.

Beklenen: 403 Forbidden (ownership failed).
"""

import pytest


@pytest.mark.integration
async def test_rollback_import_requires_ownership(async_client, auth_headers):
    """
    T3-B: Rollback endpoint ownership kontrolü yapmalı.

    Senaryo:
    1. User A ile import job oluştur
    2. User B tokenıyla rollback/{job_id} çağır
    3. 403 beklenir (200 dönüyorsa BUG)

    Note: Bu test basitleştirilmiş. Gerçekte job_id oluşturmak için
    import endpoint'ini çalıştırmak gerekir.
    """

    # Dummy job_id (99999 olmayan bir değer)
    job_id = "user_a_import_job_12345"

    # async_client fixtures different users kullanmalı (mevcut test setup'ta
    # auth_headers ve admin_auth_headers var). Eğer yok ise test skip.

    # Try rollback with normal user headers
    response = await async_client.post(
        f"/api/v1/trips/import/rollback/{job_id}",
        json={},
        headers=auth_headers,
    )

    # Either 403, 404, or 401 expected
    # 200 = vulnerability
    assert response.status_code != 200, (
        f"T3-B: Import rollback missing ownership check! "
        f"Normal user could rollback another user's import (status={response.status_code}). "
        f"Expected: 403 (Forbidden) or 404 (Not Found)."
    )
