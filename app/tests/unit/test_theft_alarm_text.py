"""Feature B.5 — _build_theft_alarm_text saf yardımcı testleri."""

from datetime import date, datetime, timezone


def _mk_anomaly(*, id: int = 1, sapma: float = 35.0):
    """Anomaly benzeri stub — gerçek SQLAlchemy modeli kullanmıyoruz."""
    from types import SimpleNamespace

    return SimpleNamespace(
        id=id,
        sapma_yuzde=sapma,
        severity="high",
        tarih=date.today(),
        created_at=datetime.now(timezone.utc),
    )


def _mk_classification(score: float = 0.82, level: str = "high", anomaly_id: int = 1):
    from v2.modules.anomaly.schemas import TheftClassification

    return TheftClassification(
        anomaly_id=anomaly_id,
        suspicion_score=score,
        suspicion_level=level,  # type: ignore[arg-type]
        factors=["test"],
        suggested_action="Investigate",
    )


def test_build_alarm_text_includes_all_fields():
    from v2.modules.anomaly.api.investigation_routes import _build_theft_alarm_text

    txt = _build_theft_alarm_text(
        inv_id=42,
        classification=_mk_classification(0.85),
        anomaly=_mk_anomaly(id=7, sapma=32.5),
        plaka="34 ABC 123",
        sofor_adi="Ali Veli",
    )
    assert "Yüksek Şüpheli Yakıt Olayı" in txt
    assert "Soruşturma #42" in txt
    assert "Anomali #7" in txt
    assert "34 ABC 123" in txt
    assert "Ali Veli" in txt
    assert "+32.5%" in txt
    assert "0.85" in txt
    assert "(high)" in txt
    # HTML parse_mode → <b> tag'leri korunmuş
    assert "<b>Plaka:</b>" in txt


def test_build_alarm_text_html_escapes_evil_input():
    from v2.modules.anomaly.api.investigation_routes import _build_theft_alarm_text

    txt = _build_theft_alarm_text(
        inv_id=1,
        classification=_mk_classification(),
        anomaly=_mk_anomaly(),
        plaka="<script>alert(1)</script>",
        sofor_adi="A & B",
    )
    # Plaka içeriği escape edilmiş → ham <script> görünmez
    assert "<script>" not in txt
    assert "&lt;script&gt;" in txt
    assert "A &amp; B" in txt
    # Bizim <b> tag'leri hâlâ render-edilebilir (template'in dışı)
    assert "<b>Plaka:</b>" in txt


def test_build_alarm_text_handles_nulls():
    from v2.modules.anomaly.api.investigation_routes import _build_theft_alarm_text

    a = _mk_anomaly()
    a.sapma_yuzde = None  # type: ignore[assignment]
    txt = _build_theft_alarm_text(
        inv_id=99,
        classification=_mk_classification(),
        anomaly=a,
        plaka=None,
        sofor_adi=None,
    )
    assert "—" in txt  # plaka/sofor/sapma boş
    assert "Soruşturma #99" in txt
