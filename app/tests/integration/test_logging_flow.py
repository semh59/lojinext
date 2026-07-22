import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

import json  # noqa: E402
import logging  # noqa: E402
import uuid  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from v2.modules.platform_infra.logging.logger import (  # noqa: E402
    LOG_DIR,
    get_audit_logger,
)


def test_request_logging_and_correlation_id(caplog):
    """
    Test: RequestLoggingMiddleware çalışıyor mu?
    Beklenti:
    1. X-Correlation-ID header'ı yanıtla dönmeli.
    2. Middleware 'Incoming Request' ve 'Request Completed'/'Slow Request' loglamalı.
    3. Loglanan correlation_id response header ile eşleşmeli.
    """
    middleware_logger = "v2.modules.platform_infra.middleware.logging_middleware"

    with caplog.at_level(logging.INFO, logger=middleware_logger):
        with TestClient(app) as client:
            response = client.get("/api/v1/health/")

    assert response.status_code in [200, 503]

    # Header kontrolü
    assert "X-Correlation-ID" in response.headers
    correlation_id = response.headers["X-Correlation-ID"]
    assert len(correlation_id) > 0

    # Middleware log kayıtlarını kontrol et
    mw_records = [r for r in caplog.records if r.name == middleware_logger]

    found_request = False
    found_response = False
    for record in mw_records:
        msg = record.getMessage()
        if "Incoming Request" in msg:
            found_request = True
        if "Request Completed" in msg or "Slow Request" in msg:
            found_response = True
            assert hasattr(record, "latency_ms"), "latency_ms alanı eksik"

    assert found_request, (
        f"'Incoming Request' logu bulunamadı. "
        f"Yakalanan mesajlar: {[r.getMessage() for r in mw_records]}"
    )
    assert found_response, (
        f"'Request Completed'/'Slow Request' logu bulunamadı. "
        f"Yakalanan mesajlar: {[r.getMessage() for r in mw_records]}"
    )


def test_audit_logging():
    """
    Test: AuditLogger çalışıyor mu?
    Beklenti: audit.log dosyasına doğru formatta kayıt düşmeli.
    """
    audit = get_audit_logger()
    test_event_id = str(uuid.uuid4())
    test_user = "test_admin"

    # Audit kaydı oluştur
    audit.log(
        event="TEST_VERIFICATION",
        user=test_user,
        details={"verification_id": test_event_id, "note": "Loglama sistemi kontrolü"},
        status="SUCCESS",
    )

    # Audit dosyasını kontrol et
    audit_file = LOG_DIR / "audit.log"
    assert audit_file.exists()

    found_audit = False
    with open(audit_file, "r", encoding="utf-8") as f:
        for line in f.readlines():  # Son satırlara bakmak yeterli olur ama basitçe oku
            if test_event_id in line:
                try:
                    log_entry = json.loads(line)
                    if (
                        log_entry.get("audit_event") == "TEST_VERIFICATION"
                        and log_entry.get("actor") == test_user
                    ):
                        found_audit = True
                        assert log_entry["details"]["verification_id"] == test_event_id
                except Exception:
                    pass

    assert found_audit, "Audit log kaydı bulunamadı veya format hatalı"
