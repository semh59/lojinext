"""Arac.yas_faktoru — yil=None guard tests.

2026-07-01 prod-grade denetiminde bulunan bug: `yas_faktoru` computed_field
`self.yas`'ı (yil=None ise None döner) doğrudan `if yas <= 2:` karşılaştırmasına
sokuyordu. `yil` DB'de nullable ve entity'de Optional[int]=None — Excel
import'ta üretim yılı eksik bırakılan bir araç her API yanıtında/serialize
edilişinde `TypeError: '<=' not supported between instances of 'NoneType' and
'int'` ile 500 patlıyordu.
"""

import pytest

from app.core.entities.models import Arac

pytestmark = pytest.mark.unit


def _arac(**overrides) -> Arac:
    defaults = dict(plaka="34 ABC 123", marka="Mercedes")
    defaults.update(overrides)
    return Arac(**defaults)


class TestAracYasFaktoru:
    def test_yas_faktoru_does_not_raise_when_yil_is_none(self):
        """yil=None iken yas_faktoru artık TypeError fırlatmamalı."""
        arac = _arac(yil=None)
        assert arac.yas is None
        assert arac.yas_faktoru == 1.0  # nötr fallback

    def test_model_dump_does_not_raise_when_yil_is_none(self):
        """Tam API-response serileştirme yolu (computed_field dahil) da güvenli olmalı."""
        arac = _arac(yil=None)
        dumped = arac.model_dump()
        assert dumped["yas"] is None
        assert dumped["yas_faktoru"] == 1.0

    def test_yas_faktoru_new_vehicle(self):
        this_year = __import__("datetime").date.today().year
        arac = _arac(yil=this_year - 1)
        assert arac.yas_faktoru == 0.98

    def test_yas_faktoru_baseline_vehicle(self):
        this_year = __import__("datetime").date.today().year
        arac = _arac(yil=this_year - 5)
        assert arac.yas_faktoru == 1.0

    def test_yas_faktoru_old_vehicle(self):
        this_year = __import__("datetime").date.today().year
        arac = _arac(yil=this_year - 12)
        assert arac.yas_faktoru > 1.05
