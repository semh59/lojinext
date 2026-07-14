"""Feature A.1 + B.1 — singleton race condition regression testleri.

Geçmiş bug: get_driver_coaching_engine() ve get_fuel_theft_classifier()
double-checked locking yapmıyordu. İki concurrent çağrı aynı anda
None check'i geçip iki ayrı instance oluşturabilirdi.

Bu test:
1. Hem singleton modülünde threading.Lock olduğunu doğrular
2. Yüksek thread sayısı ile concurrent çağrı yapıp aynı instance
   referansının döndüğünü garanti eder.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor


def test_driver_coaching_engine_singleton_has_lock():
    """Module-level _engine_lock var ve threading.Lock instance'ı."""
    from v2.modules.driver.application import generate_coaching as mod

    assert hasattr(mod, "_engine_lock"), "Lock attribute eksik"
    # threading.Lock() bir factory; isinstance test'i lock tipiyle uyum
    assert isinstance(mod._engine_lock, type(threading.Lock()))


def test_fuel_theft_classifier_singleton_has_lock():
    """Module-level _classifier_lock var."""
    from app.core.ai import fuel_theft_classifier as mod

    assert hasattr(mod, "_classifier_lock"), "Lock attribute eksik"
    assert isinstance(mod._classifier_lock, type(threading.Lock()))


def test_driver_coaching_engine_concurrent_calls_return_same_instance():
    """20 paralel thread aynı engine instance'ı almalı."""
    from v2.modules.driver.application import generate_coaching as mod

    # Test izolasyonu için sıfırla
    mod._engine_singleton = None

    with ThreadPoolExecutor(max_workers=20) as pool:
        instances = list(
            pool.map(lambda _: mod.get_driver_coaching_engine(), range(20))
        )

    first = instances[0]
    for inst in instances[1:]:
        assert inst is first, "Singleton race: farklı instance döndü"


def test_fuel_theft_classifier_concurrent_calls_return_same_instance():
    """20 paralel thread aynı classifier instance'ı almalı."""
    from app.core.ai import fuel_theft_classifier as mod

    mod._classifier_singleton = None

    with ThreadPoolExecutor(max_workers=20) as pool:
        instances = list(pool.map(lambda _: mod.get_fuel_theft_classifier(), range(20)))

    first = instances[0]
    for inst in instances[1:]:
        assert inst is first, "Singleton race: farklı instance döndü"
