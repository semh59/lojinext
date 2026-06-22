"""Coverage tests for app/workers/tasks/ocr_tasks.py (0% → ≥75%)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_belge(
    belge_id: int = 1,
    dosya_yolu: str = "/tmp/belge_1.jpg",
    belge_tipi: str = "yakit_fisi",
):
    belge = MagicMock()
    belge.id = belge_id
    belge.dosya_yolu = dosya_yolu
    belge.belge_tipi = belge_tipi
    belge.ocr_durumu = None
    belge.ocr_ham = None
    belge.ocr_veri = None
    return belge


def _make_uow(belge=None):
    """Build a fake async UnitOfWork context manager."""
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    # AUDIT-162: _mark_hata ayrı transaction'da await commit() çağırır → AsyncMock.
    uow.commit = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = belge
    uow.session = AsyncMock()
    uow.session.execute = AsyncMock(return_value=result)
    return uow


# ---------------------------------------------------------------------------
# Task registration
# ---------------------------------------------------------------------------


class TestOcrTaskRegistration:
    def test_task_is_importable(self):
        from app.workers.tasks.ocr_tasks import process_belge_ocr

        assert process_belge_ocr is not None

    def test_task_name(self):
        from app.workers.tasks.ocr_tasks import process_belge_ocr

        assert process_belge_ocr.name == "ocr.process_belge"

    def test_task_max_retries(self):
        from app.workers.tasks.ocr_tasks import process_belge_ocr

        assert process_belge_ocr.max_retries == 3

    def test_task_acks_late(self):
        from app.workers.tasks.ocr_tasks import process_belge_ocr

        assert process_belge_ocr.acks_late is True

    def test_task_default_retry_delay(self):
        from app.workers.tasks.ocr_tasks import process_belge_ocr

        assert process_belge_ocr.default_retry_delay == 30


# ---------------------------------------------------------------------------
# Functional tests (run via asyncio.run inside task)
# ---------------------------------------------------------------------------


class TestOcrTaskBelgeNotFound:
    def test_returns_not_found_when_belge_missing(self):
        """When SeferBelge is not in DB, task returns {ok: False, error: not_found}."""
        from app.workers.tasks.ocr_tasks import process_belge_ocr

        uow = _make_uow(belge=None)

        with patch("app.workers.tasks.ocr_tasks.UnitOfWork", return_value=uow):
            result = process_belge_ocr.apply(args=[999]).get()

        assert result == {"ok": False, "error": "not_found"}


class TestOcrTaskFileReadError:
    def test_retries_on_os_error(self):
        """OSError when opening the file triggers a retry."""
        from app.workers.tasks.ocr_tasks import process_belge_ocr

        belge = _make_belge()
        uow = _make_uow(belge=belge)

        with patch("app.workers.tasks.ocr_tasks.UnitOfWork", return_value=uow):
            with patch("builtins.open", side_effect=OSError("no such file")):
                with pytest.raises(Exception):
                    process_belge_ocr.apply(args=[1]).get(propagate=True)

        # ocr_durumu should be set to "hata" before retry
        assert belge.ocr_durumu == "hata"


class TestOcrTaskOcrServiceError:
    def test_sets_hata_status_on_network_error(self):
        """HTTP error from OCR service sets ocr_durumu='hata' and triggers retry."""
        from app.workers.tasks.ocr_tasks import process_belge_ocr

        belge = _make_belge()
        uow = _make_uow(belge=belge)

        fake_client = AsyncMock()
        fake_client.__aenter__ = AsyncMock(return_value=fake_client)
        fake_client.__aexit__ = AsyncMock(return_value=False)
        fake_client.post = AsyncMock(side_effect=Exception("connection refused"))

        with patch("app.workers.tasks.ocr_tasks.UnitOfWork", return_value=uow):
            with patch(
                "builtins.open",
                MagicMock(
                    return_value=MagicMock(
                        __enter__=MagicMock(
                            return_value=MagicMock(
                                read=MagicMock(return_value=b"imgbytes")
                            )
                        ),
                        __exit__=MagicMock(return_value=False),
                    )
                ),
            ):
                with patch(
                    "app.workers.tasks.ocr_tasks.get_monitored_client",
                    return_value=fake_client,
                ):
                    with pytest.raises(Exception):
                        process_belge_ocr.apply(args=[1]).get(propagate=True)

        assert belge.ocr_durumu == "hata"


class TestOcrTaskSuccess:
    def test_successful_ocr_sets_fields(self):
        """Happy path: belge fields are populated after successful OCR."""
        from app.workers.tasks.ocr_tasks import process_belge_ocr

        belge = _make_belge()
        uow = _make_uow(belge=belge)

        ocr_response = MagicMock()
        ocr_response.json.return_value = {
            "ham_metin": "İstanbul 450L Motorin",
            "yapilandirilmis": {"litre": 450, "aciklama": "Akaryakıt fişi"},
        }
        ocr_response.raise_for_status = MagicMock()

        fake_client = AsyncMock()
        fake_client.__aenter__ = AsyncMock(return_value=fake_client)
        fake_client.__aexit__ = AsyncMock(return_value=False)
        fake_client.post = AsyncMock(return_value=ocr_response)

        with patch("app.workers.tasks.ocr_tasks.UnitOfWork", return_value=uow):
            with patch(
                "builtins.open",
                MagicMock(
                    return_value=MagicMock(
                        __enter__=MagicMock(
                            return_value=MagicMock(
                                read=MagicMock(return_value=b"imgbytes")
                            )
                        ),
                        __exit__=MagicMock(return_value=False),
                    )
                ),
            ):
                with patch(
                    "app.workers.tasks.ocr_tasks.get_monitored_client",
                    return_value=fake_client,
                ):
                    result = process_belge_ocr.apply(args=[1]).get()

        assert result == {"ok": True, "belge_id": 1}
        assert belge.ocr_ham == "İstanbul 450L Motorin"
        assert belge.ocr_veri == {"litre": 450, "aciklama": "Akaryakıt fişi"}
        assert belge.ocr_durumu == "islendi"

    def test_successful_ocr_increments_metric(self):
        """On success the Prometheus counter label 'islendi' is incremented."""
        from app.workers.tasks.ocr_tasks import process_belge_ocr

        belge = _make_belge()
        uow = _make_uow(belge=belge)

        ocr_response = MagicMock()
        ocr_response.json.return_value = {"ham_metin": "test", "yapilandirilmis": {}}
        ocr_response.raise_for_status = MagicMock()

        fake_client = AsyncMock()
        fake_client.__aenter__ = AsyncMock(return_value=fake_client)
        fake_client.__aexit__ = AsyncMock(return_value=False)
        fake_client.post = AsyncMock(return_value=ocr_response)

        mock_metric = MagicMock()
        mock_metric.labels.return_value = MagicMock()

        with patch("app.workers.tasks.ocr_tasks.UnitOfWork", return_value=uow):
            with patch(
                "builtins.open",
                MagicMock(
                    return_value=MagicMock(
                        __enter__=MagicMock(
                            return_value=MagicMock(
                                read=MagicMock(return_value=b"bytes")
                            )
                        ),
                        __exit__=MagicMock(return_value=False),
                    )
                ),
            ):
                with patch(
                    "app.workers.tasks.ocr_tasks.get_monitored_client",
                    return_value=fake_client,
                ):
                    with patch(
                        "app.workers.tasks.ocr_tasks.telegram_belge_ocr_total",
                        mock_metric,
                    ):
                        process_belge_ocr.apply(args=[1]).get()

        mock_metric.labels.assert_called_with(sonuc="islendi")

    def test_ocr_result_missing_fields_handled_gracefully(self):
        """If OCR response lacks fields, belge gets None values (no crash)."""
        from app.workers.tasks.ocr_tasks import process_belge_ocr

        belge = _make_belge()
        uow = _make_uow(belge=belge)

        ocr_response = MagicMock()
        ocr_response.json.return_value = {}  # empty
        ocr_response.raise_for_status = MagicMock()

        fake_client = AsyncMock()
        fake_client.__aenter__ = AsyncMock(return_value=fake_client)
        fake_client.__aexit__ = AsyncMock(return_value=False)
        fake_client.post = AsyncMock(return_value=ocr_response)

        with patch("app.workers.tasks.ocr_tasks.UnitOfWork", return_value=uow):
            with patch(
                "builtins.open",
                MagicMock(
                    return_value=MagicMock(
                        __enter__=MagicMock(
                            return_value=MagicMock(read=MagicMock(return_value=b"x"))
                        ),
                        __exit__=MagicMock(return_value=False),
                    )
                ),
            ):
                with patch(
                    "app.workers.tasks.ocr_tasks.get_monitored_client",
                    return_value=fake_client,
                ):
                    result = process_belge_ocr.apply(args=[1]).get()

        assert result["ok"] is True
        assert belge.ocr_ham is None
        assert belge.ocr_veri is None


class TestOcrTaskMetricOnError:
    def test_error_metric_incremented_on_http_failure(self):
        """On OCR service error, counter label 'hata' is incremented."""
        from app.workers.tasks.ocr_tasks import process_belge_ocr

        belge = _make_belge()
        uow = _make_uow(belge=belge)

        fake_client = AsyncMock()
        fake_client.__aenter__ = AsyncMock(return_value=fake_client)
        fake_client.__aexit__ = AsyncMock(return_value=False)
        fake_client.post = AsyncMock(side_effect=Exception("timeout"))

        mock_metric = MagicMock()
        mock_metric.labels.return_value = MagicMock()

        with patch("app.workers.tasks.ocr_tasks.UnitOfWork", return_value=uow):
            with patch(
                "builtins.open",
                MagicMock(
                    return_value=MagicMock(
                        __enter__=MagicMock(
                            return_value=MagicMock(read=MagicMock(return_value=b"x"))
                        ),
                        __exit__=MagicMock(return_value=False),
                    )
                ),
            ):
                with patch(
                    "app.workers.tasks.ocr_tasks.get_monitored_client",
                    return_value=fake_client,
                ):
                    with patch(
                        "app.workers.tasks.ocr_tasks.telegram_belge_ocr_total",
                        mock_metric,
                    ):
                        with pytest.raises(Exception):
                            process_belge_ocr.apply(args=[1]).get(propagate=True)

        # AUDIT-162: hata yolunda _mark_hata (ayrı transaction) + labels(sonuc="hata").
        # Celery eager retry birden fazla deneme çalıştırabildiği için son çağrı yerine
        # 'hata' çağrısının yapıldığını assert_any_call ile doğrula.
        mock_metric.labels.assert_any_call(sonuc="hata")
