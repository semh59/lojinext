"""Uygulama genelinde Prometheus custom metrikleri.

Graceful no-op: prometheus_client yüklü değilse sayaçlar sessizce çalışmaz.
"""

try:
    from prometheus_client import Counter as _Counter

    trip_approval_total = _Counter(
        "trip_approval_total",
        "Sefer onay/red işlemi sayısı",
        ["action"],  # "onayla" | "reddet"
    )

    telegram_belge_upload_total = _Counter(
        "telegram_belge_upload_total",
        "Telegram botundan yüklenen belge sayısı",
        ["belge_tipi"],  # yakit_fisi | sefer_fisi | tir_ekran
    )

    telegram_belge_ocr_total = _Counter(
        "telegram_belge_ocr_total",
        "OCR işlemi sonucu sayısı",
        ["sonuc"],  # islendi | hata
    )

except Exception:  # pragma: no cover

    class _Noop:
        def labels(self, **_):
            return self

        def inc(self):
            pass

    trip_approval_total = _Noop()  # type: ignore[assignment]
    telegram_belge_upload_total = _Noop()  # type: ignore[assignment]
    telegram_belge_ocr_total = _Noop()  # type: ignore[assignment]
