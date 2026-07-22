"""Coverage tests for app/workers/tasks/ocr_tasks.py (0% → ≥75%).

0-mock (Dilim 31): patch("...UnitOfWork", return_value=uow) replaced with
narrow patch.object(UnitOfWork, '__aenter__'/__aexit__) — the class is
never replaced; only its context-manager dunders are stubbed out.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

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


def _make_uow_inst(belge=None):
    """Build a fake UoW instance returned from __aenter__."""
    uow = MagicMock()
    # AUDIT-162: _mark_hata ayrı transaction'da await commit() çağırır → AsyncMock.
    uow.commit = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = belge
    uow.session = AsyncMock()
    uow.session.execute = AsyncMock(return_value=result)
    return uow


def _uow_ctx(uow_inst):
    """Return context managers patching UnitOfWork's __aenter__/__aexit__."""
    return (
        patch.object(UnitOfWork, "__aenter__", AsyncMock(return_value=uow_inst)),
        patch.object(UnitOfWork, "__aexit__", AsyncMock(return_value=False)),
    )


# ---------------------------------------------------------------------------
# Task registration
# ---------------------------------------------------------------------------


class TestOcrTaskRegistration:
    def test_task_is_importable(self):
        from v2.modules.import_excel.infrastructure.tasks import process_belge_ocr

        assert process_belge_ocr is not None

    def test_task_name(self):
        from v2.modules.import_excel.infrastructure.tasks import process_belge_ocr

        assert process_belge_ocr.name == "ocr.process_belge"

    def test_task_max_retries(self):
        from v2.modules.import_excel.infrastructure.tasks import process_belge_ocr

        assert process_belge_ocr.max_retries == 3

    def test_task_acks_late(self):
        from v2.modules.import_excel.infrastructure.tasks import process_belge_ocr

        assert process_belge_ocr.acks_late is True

    def test_task_default_retry_delay(self):
        from v2.modules.import_excel.infrastructure.tasks import process_belge_ocr

        assert process_belge_ocr.default_retry_delay == 30

    def test_task_registered_with_worker_via_celery_app_import_list(self):
        """Regression guard (2026-07-17 dedektif denetimi): `ocr.process_belge`
        yalnız task modülünü doğrudan import ederek değil, worker'ın gerçekten
        yüklediği `v2.modules.platform_infra.background.celery_app`'in kendi
        `celery_app.tasks` registry'sinden de görünür olmalı — aksi halde
        `.delay()` çağıran gerçek kod (`internal.py`'nin Telegram belge-yükleme
        akışı) worker'da `NotRegistered` ile sessizce patlar (task modülü
        `celery_app.py`'nin explicit import listesinde YOKTU, wave 9 taşımasında
        atlanmıştı — diğer testler task fonksiyonunu doğrudan import ettiği için
        bunu hiç yakalamamıştı)."""
        from v2.modules.platform_infra.background.celery_app import celery_app

        assert "ocr.process_belge" in celery_app.tasks


# ---------------------------------------------------------------------------
# Functional tests (run via asyncio.run inside task)
# ---------------------------------------------------------------------------


class TestOcrTaskBelgeNotFound:
    def test_returns_not_found_when_belge_missing(self):
        """When SeferBelge is not in DB, task returns {ok: False, error: not_found}."""
        from v2.modules.import_excel.infrastructure.tasks import process_belge_ocr

        uow_inst = _make_uow_inst(belge=None)
        enter_p, exit_p = _uow_ctx(uow_inst)

        with enter_p, exit_p:
            result = process_belge_ocr.apply(args=[999]).get()

        assert result == {"ok": False, "error": "not_found"}


class TestOcrTaskFileReadError:
    def test_retries_on_os_error(self):
        """OSError when opening the file triggers a retry."""
        from v2.modules.import_excel.infrastructure.tasks import process_belge_ocr

        belge = _make_belge()
        uow_inst = _make_uow_inst(belge=belge)
        enter_p, exit_p = _uow_ctx(uow_inst)

        with enter_p, exit_p:
            with patch("builtins.open", side_effect=OSError("no such file")):
                with pytest.raises(Exception):
                    process_belge_ocr.apply(args=[1]).get(propagate=True)

        # ocr_durumu should be set to "hata" before retry
        assert belge.ocr_durumu == "hata"


class TestOcrTaskOcrServiceError:
    def test_sets_hata_status_on_network_error(self):
        """HTTP error from OCR service sets ocr_durumu='hata' and triggers retry."""
        from v2.modules.import_excel.infrastructure.tasks import process_belge_ocr

        belge = _make_belge()
        uow_inst = _make_uow_inst(belge=belge)
        enter_p, exit_p = _uow_ctx(uow_inst)

        fake_client = AsyncMock()
        fake_client.__aenter__ = AsyncMock(return_value=fake_client)
        fake_client.__aexit__ = AsyncMock(return_value=False)
        fake_client.post = AsyncMock(side_effect=Exception("connection refused"))

        with enter_p, exit_p:
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
                    "v2.modules.import_excel.infrastructure.tasks.get_monitored_client",
                    return_value=fake_client,
                ):
                    with pytest.raises(Exception):
                        process_belge_ocr.apply(args=[1]).get(propagate=True)

        assert belge.ocr_durumu == "hata"


class TestOcrTaskSuccess:
    def test_successful_ocr_sets_fields(self):
        """Happy path: belge fields are populated after successful OCR."""
        from v2.modules.import_excel.infrastructure.tasks import process_belge_ocr

        belge = _make_belge()
        uow_inst = _make_uow_inst(belge=belge)
        enter_p, exit_p = _uow_ctx(uow_inst)

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

        with enter_p, exit_p:
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
                    "v2.modules.import_excel.infrastructure.tasks.get_monitored_client",
                    return_value=fake_client,
                ):
                    result = process_belge_ocr.apply(args=[1]).get()

        assert result == {"ok": True, "belge_id": 1}
        assert belge.ocr_ham == "İstanbul 450L Motorin"
        assert belge.ocr_veri == {"litre": 450, "aciklama": "Akaryakıt fişi"}
        assert belge.ocr_durumu == "islendi"

    def test_successful_ocr_increments_metric(self):
        """On success the Prometheus counter label 'islendi' is incremented."""
        from v2.modules.import_excel.infrastructure.tasks import process_belge_ocr

        belge = _make_belge()
        uow_inst = _make_uow_inst(belge=belge)
        enter_p, exit_p = _uow_ctx(uow_inst)

        ocr_response = MagicMock()
        ocr_response.json.return_value = {"ham_metin": "test", "yapilandirilmis": {}}
        ocr_response.raise_for_status = MagicMock()

        fake_client = AsyncMock()
        fake_client.__aenter__ = AsyncMock(return_value=fake_client)
        fake_client.__aexit__ = AsyncMock(return_value=False)
        fake_client.post = AsyncMock(return_value=ocr_response)

        mock_metric = MagicMock()
        mock_metric.labels.return_value = MagicMock()

        with enter_p, exit_p:
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
                    "v2.modules.import_excel.infrastructure.tasks.get_monitored_client",
                    return_value=fake_client,
                ):
                    with patch(
                        "v2.modules.import_excel.infrastructure.tasks.telegram_belge_ocr_total",
                        mock_metric,
                    ):
                        process_belge_ocr.apply(args=[1]).get()

        mock_metric.labels.assert_called_with(sonuc="islendi")

    def test_ocr_result_missing_fields_handled_gracefully(self):
        """If OCR response lacks fields, belge gets None values (no crash)."""
        from v2.modules.import_excel.infrastructure.tasks import process_belge_ocr

        belge = _make_belge()
        uow_inst = _make_uow_inst(belge=belge)
        enter_p, exit_p = _uow_ctx(uow_inst)

        ocr_response = MagicMock()
        ocr_response.json.return_value = {}  # empty
        ocr_response.raise_for_status = MagicMock()

        fake_client = AsyncMock()
        fake_client.__aenter__ = AsyncMock(return_value=fake_client)
        fake_client.__aexit__ = AsyncMock(return_value=False)
        fake_client.post = AsyncMock(return_value=ocr_response)

        with enter_p, exit_p:
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
                    "v2.modules.import_excel.infrastructure.tasks.get_monitored_client",
                    return_value=fake_client,
                ):
                    result = process_belge_ocr.apply(args=[1]).get()

        assert result["ok"] is True
        assert belge.ocr_ham is None
        assert belge.ocr_veri is None


class TestOcrTaskMetricOnError:
    def test_error_metric_incremented_on_http_failure(self):
        """On OCR service error, counter label 'hata' is incremented."""
        from v2.modules.import_excel.infrastructure.tasks import process_belge_ocr

        belge = _make_belge()
        uow_inst = _make_uow_inst(belge=belge)
        enter_p, exit_p = _uow_ctx(uow_inst)

        fake_client = AsyncMock()
        fake_client.__aenter__ = AsyncMock(return_value=fake_client)
        fake_client.__aexit__ = AsyncMock(return_value=False)
        fake_client.post = AsyncMock(side_effect=Exception("timeout"))

        mock_metric = MagicMock()
        mock_metric.labels.return_value = MagicMock()

        with enter_p, exit_p:
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
                    "v2.modules.import_excel.infrastructure.tasks.get_monitored_client",
                    return_value=fake_client,
                ):
                    with patch(
                        "v2.modules.import_excel.infrastructure.tasks.telegram_belge_ocr_total",
                        mock_metric,
                    ):
                        with pytest.raises(Exception):
                            process_belge_ocr.apply(args=[1]).get(propagate=True)

        # AUDIT-162: hata yolunda _mark_hata (ayrı transaction) + labels(sonuc="hata").
        # Celery eager retry birden fazla deneme çalıştırabildiği için son çağrı yerine
        # 'hata' çağrısının yapıldığını assert_any_call ile doğrula.
        mock_metric.labels.assert_any_call(sonuc="hata")
