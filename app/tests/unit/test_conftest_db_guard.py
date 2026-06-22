"""conftest'in test-DB çözümleme guard'ı — dev DB'ye DROP SCHEMA atılmasını önler.

Gerekçe: TEST_DATABASE_URL yokken fallback dev DB'yi (lojinext_db) gösteriyordu;
async_db_engine bu DB'de pg_terminate_backend + DROP SCHEMA public CASCADE
çalıştırır. Guard: URL zorunlu VE veritabanı adı 'test' içermek zorunda.
"""

import pytest

from app.tests.conftest import resolve_test_db_url


@pytest.mark.unit
def test_missing_url_raises():
    with pytest.raises(RuntimeError, match="TEST_DATABASE_URL"):
        resolve_test_db_url(None)


@pytest.mark.unit
def test_non_test_db_name_rejected():
    # Dev/prod adlı DB'lere işaret eden URL kabul edilmez — 'test' şartı
    with pytest.raises(RuntimeError, match="test"):
        resolve_test_db_url("postgresql+asyncpg://u:p@localhost:5432/lojinext_db")


@pytest.mark.unit
def test_valid_test_url_passes_through():
    url = "postgresql+asyncpg://postgres:postgres@localhost:5432/lojinext_test"  # pragma: allowlist secret
    assert resolve_test_db_url(url) == url
