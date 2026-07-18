"""
DI Container - Kapsamlı Test Suite
===================================

Bu test modülü Container sınıfının Dependency Injection implementasyonunu
kapsamlı şekilde test eder.

Test Kategorileri:
1. Singleton Pattern
2. Initialization
3. Dependency Injection Verification
4. Mock Injection (Test Isolation)
5. Factory Function Binding
6. Thread-Safety
7. Reset/Cleanup
8. Edge Cases
"""

import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from unittest.mock import Mock

import pytest

# Ensure app directory is in path
APP_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(APP_DIR))


# =============================================================================
# FIXTURES
# =============================================================================

# NOT: pytest_configure ile modül seviyesinde container reset yapıyoruz
# Bu sadece bu dosya için geçerli, diğer test dosyalarını etkilemez


def setup_module(module):
    """Modül başlangıcında container'ı sıfırla."""
    from app.core.container import reset_container

    reset_container()


def teardown_module(module):
    """Modül sonunda container'ı sıfırla."""
    from app.core.container import reset_container

    reset_container()


@pytest.fixture
def fresh_container():
    """Her test için temiz container sağlar."""
    from app.core.container import get_container, reset_container

    reset_container()
    container = get_container()
    yield container
    reset_container()


@pytest.fixture
def mock_event_bus():
    """Mock EventBus for testing."""
    mock = Mock()
    mock.publish = Mock(return_value=1)
    mock.subscribe = Mock()
    return mock


@pytest.fixture
def mock_arac_repo():
    """Mock AracRepository for testing."""
    mock = Mock()
    mock.get_all = Mock(return_value=[])
    mock.get_by_id = Mock(return_value=None)
    mock.add = Mock(return_value=1)
    return mock


@pytest.fixture
def mock_sefer_repo():
    """Mock SeferRepository for testing."""
    mock = Mock()
    mock.get_all = Mock(return_value=[])
    mock.add = Mock(return_value=1)
    return mock


@pytest.fixture
def mock_sofor_repo():
    """Mock SoforRepository for testing."""
    mock = Mock()
    mock.get_all = Mock(return_value=[])
    mock.add = Mock(return_value=1)
    return mock


@pytest.fixture
def mock_yakit_repo():
    """Mock YakitRepository for testing."""
    mock = Mock()
    mock.get_all = Mock(return_value=[])
    mock.add = Mock(return_value=1)
    mock.get_son_km = Mock(return_value=None)
    return mock


# =============================================================================
# 1. SINGLETON PATTERN TESTS
# =============================================================================


class TestContainerSingleton:
    """Container singleton pattern testleri."""

    def test_get_container_returns_same_instance(self):
        """get_container() her çağrıda aynı instance'ı döndürmeli."""
        from app.core.container import get_container

        container1 = get_container()
        container2 = get_container()
        container3 = get_container()

        assert container1 is container2
        assert container2 is container3
        assert id(container1) == id(container2) == id(container3)

    def test_singleton_preserves_state(self):
        """Singleton instance state'i korumalı."""
        from app.core.container import get_container

        container1 = get_container()
        # State'i kontrol et
        original_sefer_service = container1.sefer_service

        container2 = get_container()
        # Aynı service instance olmalı
        assert container2.sefer_service is original_sefer_service

    def test_reset_clears_singleton(self):
        """reset_container() singleton'ı temizlemeli."""
        from app.core.container import get_container, reset_container

        container1 = get_container()
        original_id = id(container1)

        reset_container()

        container2 = get_container()
        # Yeni instance olmalı
        assert id(container2) != original_id
        assert container1 is not container2


# =============================================================================
# 2. CONTAINER INITIALIZATION TESTS
# =============================================================================


class TestContainerInitialization:
    """Container initialization testleri."""

    def test_all_repositories_initialized(self):
        """Tüm repository'ler initialize edilmeli."""
        from app.core.container import get_container

        container = get_container()

        assert container.arac_repo is not None
        assert container.sefer_repo is not None
        assert container.sofor_repo is not None
        assert container.yakit_repo is not None

    def test_all_services_initialized(self):
        """Tüm servisler initialize edilmeli."""
        from app.core.container import get_container

        container = get_container()

        assert container.sefer_service is not None
        # container.analiz_service removed — AnalizService class deleted in
        # dalga 11 (dead-code temizliği, hiçbir prod kod çağırmıyordu);
        # container.analiz_repo hâlâ var (read-model repo, asserted above).
        # container.import_service removed — ImportService class deleted in
        # dalga 9 (B.1 free-function refactor, v2.modules.import_excel).
        # container.report_service removed — ReportService class deleted in
        # dalga 10 (B.1 free-function refactor, v2.modules.reports).

    def test_event_bus_initialized(self):
        """EventBus initialize edilmeli."""
        from app.core.container import get_container

        container = get_container()

        assert container.event_bus is not None

    def test_container_is_correct_type(self):
        """Container doğru tipte olmalı."""
        from app.core.container import Container, get_container

        container = get_container()

        assert isinstance(container, Container)


# =============================================================================
# 3. DEPENDENCY INJECTION VERIFICATION TESTS
# =============================================================================


class TestDependencyInjection:
    """Bağımlılık enjeksiyonu doğrulama testleri."""

    def test_sefer_service_has_correct_repo(self):
        """SeferService doğru repository'yi almalı."""
        from app.core.container import get_container

        container = get_container()

        assert container.sefer_service.repo is container.sefer_repo

    # test_yakit_service_has_correct_repo removed — YakitService class deleted
    # in dalga 4 (B.1 free-function refactor, v2.modules.fuel); fuel use-cases
    # open their own UnitOfWork() and never held a constructor-injected repo
    # (container.yakit_repo still exists, used by other services e.g.
    # analiz_service/report_service, asserted below).

    # test_arac_service_has_correct_repo removed — AracService class deleted
    # in dalga 3; container.arac_repo still exists (used by other services
    # e.g. analiz_service/import_service/report_service, asserted below).

    # test_sofor_service_has_correct_repo removed — SoforService class deleted
    # in dalga 5 (B.1 free-function refactor, v2.modules.driver); driver
    # use-cases open their own UnitOfWork() and never held a
    # constructor-injected repo (container.sofor_repo still exists, used by
    # other services e.g. import_service/report_service, asserted below).

    # test_analiz_service_has_all_repos removed — AnalizService class +
    # container.analiz_service property both deleted in dalga 11 (dead-code
    # temizliği, hiçbir prod kod çağırmıyordu); container.{arac,sefer,yakit}_repo
    # still exist, used by other services e.g. report use-cases, asserted above.

    # test_import_service_has_services_and_repos removed — ImportService
    # class + container.import_service property both deleted in dalga 9
    # (B.1 free-function refactor, v2.modules.import_excel); each use-case
    # opens its own UnitOfWork() or reaches container.sefer_service inline
    # (bkz. v2/modules/import_excel/CLAUDE.md).

    # test_report_service_has_all_repos removed — ReportService class deleted
    # in dalga 10 (B.1 free-function refactor, v2.modules.reports); reports
    # use-cases take an explicit ReportRepos bundle (resolve_repos(uow)),
    # never a constructor-injected repo (container.{arac,sofor,yakit,sefer}_repo
    # still exist, used by other services e.g. analiz_service, asserted above).

    def test_all_services_share_same_event_bus(self):
        """Event-publishing servisler aynı EventBus'ı paylaşmalı."""
        from app.core.container import get_container

        container = get_container()

        # EventBus kullanan tüm servisler
        event_bus = container.event_bus

        assert container.sefer_service.event_bus is event_bus
        # container.yakit_service removed — YakitService class deleted (dalga
        # 4, B.1 free-function refactor); fuel use-cases don't hold a
        # persistent event_bus reference to assert against.
        # container.arac_service removed — AracService class deleted (dalga 3,
        # B.1 free-function refactor); fleet vehicle use-cases don't hold a
        # persistent event_bus reference to assert against.
        # container.sofor_service removed — SoforService class deleted (dalga
        # 5, B.1 free-function refactor); driver use-cases don't hold a
        # persistent event_bus reference to assert against.


# =============================================================================
# 4. MOCK INJECTION TESTS (Test Isolation)
# =============================================================================


class TestMockInjection:
    """Mock injection testleri - Test isolation için kritik."""

    def test_sefer_service_accepts_mock_repo(self, mock_sefer_repo, mock_event_bus):
        """SeferService mock repo kabul etmeli."""
        from v2.modules.trip.application.trip_service import SeferService

        service = SeferService(repo=mock_sefer_repo, event_bus=mock_event_bus)

        assert service.repo is mock_sefer_repo
        assert service.event_bus is mock_event_bus

    # test_yakit_service_accepts_mock_repo removed — YakitService class
    # deleted in dalga 4 (B.1 free-function refactor, v2.modules.fuel); fuel
    # use-cases no longer take a constructor-injected repo.

    # test_arac_service_accepts_mock_repo removed — AracService class deleted
    # in dalga 3 (B.1 free-function refactor, v2.modules.fleet); vehicle
    # use-cases no longer take a constructor-injected repo.

    # test_sofor_service_accepts_mock_repo removed — SoforService class
    # deleted in dalga 5 (B.1 free-function refactor, v2.modules.driver);
    # driver use-cases no longer take a constructor-injected repo.

    # test_analiz_service_accepts_mock_repos removed — AnalizService class
    # deleted in dalga 11 (dead-code temizliği, hiçbir prod kod
    # çağırmıyordu, container.analiz_service property'siyle birlikte).

    # test_import_service_accepts_mocks removed — ImportService class
    # deleted in dalga 9 (B.1 free-function refactor, v2.modules.import_excel);
    # its use-cases (execute_import/process_*_import) take no constructor,
    # they open their own UnitOfWork() or reach container.sefer_service inline.


# =============================================================================
# 5. FACTORY FUNCTION BINDING TESTS
# =============================================================================


class TestFactoryFunctions:
    """Factory fonksiyonlarının Container ile bağlantısı."""

    def test_get_sefer_service_returns_container_instance(self):
        """get_sefer_service() Container'daki instance'ı döndürmeli."""
        from app.core.container import get_container
        from v2.modules.trip.application.trip_service import get_sefer_service

        container = get_container()
        service = get_sefer_service()

        assert service is container.sefer_service

    # test_get_yakit_service_returns_container_instance removed —
    # YakitService class + container.yakit_service property + get_yakit_service()
    # factory all deleted in dalga 4 (B.1 free-function refactor, v2.modules.fuel).

    # test_get_arac_service_returns_container_instance removed — AracService
    # class + container.arac_service property deleted in dalga 3 (B.1
    # free-function refactor, v2.modules.fleet).

    # test_get_sofor_service_returns_container_instance removed — SoforService
    # class + container.sofor_service property + get_sofor_service() factory
    # all deleted in dalga 5 (B.1 free-function refactor, v2.modules.driver).

    # test_get_import_service_returns_container_instance removed —
    # get_import_service() factory + container.import_service property both
    # deleted in dalga 9 (B.1 free-function refactor, v2.modules.import_excel).

    # test_get_report_service_returns_container_instance removed —
    # get_report_service() factory + container.report_service property both
    # deleted in dalga 10 (B.1 free-function refactor, v2.modules.reports).


# =============================================================================
# 6. THREAD-SAFETY TESTS
# =============================================================================


class TestThreadSafety:
    """Thread-safety testleri."""

    def test_concurrent_get_container_returns_same_instance(self):
        """Concurrent get_container() çağrıları aynı instance döndürmeli."""
        from app.core.container import get_container

        results = []
        num_threads = 20

        def get_container_thread():
            container = get_container()
            return id(container)

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(get_container_thread) for _ in range(num_threads)
            ]
            results = [f.result() for f in as_completed(futures)]

        # Tüm thread'ler aynı instance ID'yi almalı
        assert len(set(results)) == 1, (
            f"Farklı instance ID'leri bulundu: {set(results)}"
        )

    def test_concurrent_service_access(self):
        """Concurrent servis erişimi thread-safe olmalı."""
        from app.core.container import get_container

        container = get_container()
        errors = []
        num_threads = 10
        iterations = 100

        def access_services():
            try:
                for _ in range(iterations):
                    # Çeşitli servislere erişim
                    _ = container.sefer_service
                    _ = container.yakit_repo
                    _ = container.arac_repo
                    _ = container.analiz_repo
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=access_services) for _ in range(num_threads)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread-safety hataları: {errors}"


# =============================================================================
# 7. RESET/CLEANUP TESTS
# =============================================================================


class TestContainerReset:
    """Container reset mekanizması testleri."""

    def test_reset_clears_container(self):
        """reset_container() container'ı temizlemeli."""
        from app.core.container import get_container, reset_container

        container1 = get_container()
        service1 = container1.sefer_service

        reset_container()

        container2 = get_container()
        service2 = container2.sefer_service

        # Farklı container ve servis instance'ları olmalı
        assert container1 is not container2
        assert service1 is not service2

    def test_multiple_resets_work(self):
        """Birden fazla reset çalışmalı."""
        from app.core.container import get_container, reset_container

        containers = []
        for i in range(3):
            reset_container()
            containers.append(get_container())

        # Tüm container'lar farklı olmalı
        assert len(set(id(c) for c in containers)) == 3

    def test_fresh_container_after_reset_is_functional(self):
        """Reset sonrası yeni container fonksiyonel olmalı."""
        from app.core.container import get_container, reset_container

        reset_container()
        container = get_container()

        # Tüm bileşenler çalışmalı
        assert container.event_bus is not None
        assert container.sefer_service is not None
        assert container.sefer_service.repo is not None


# =============================================================================
# 8. EDGE CASE & ERROR TESTS
# =============================================================================


class TestEdgeCases:
    """Edge case ve hata durumu testleri."""

    def test_service_with_none_repo_uses_default(self):
        """None repo geçilirse default kullanılmalı."""
        from v2.modules.trip.application.trip_service import SeferService

        service = SeferService(repo=None, event_bus=None)

        # Default repo ve event_bus kullanılmalı
        assert service.repo is not None
        assert service.event_bus is not None

    def test_container_initialization_is_idempotent(self):
        """Container birden fazla kez oluşturulabilmeli (reset sonrası)."""
        from app.core.container import Container, get_container, reset_container

        # İlk oluşturma
        container1 = get_container()
        assert isinstance(container1, Container)

        # Reset ve tekrar oluşturma
        reset_container()
        container2 = get_container()
        assert isinstance(container2, Container)

        # Her iki container da fonksiyonel olmalı
        assert container1.sefer_service is not None
        assert container2.sefer_service is not None

    def test_container_services_are_not_none_after_init(self):
        """Container init sonrası hiçbir servis None olmamalı (Property erişimi sonrası)."""
        from app.core.container import Container

        container = Container()

        # Reflection ile tüm public property'leri kontrol et
        # Private field'lar (_ ile başlayan) lazy loading nedeniyle None olabilir,
        # ancak bunlara karşılık gelen property'ler erişildiğinde initialize edilmeli.
        for attr_name in dir(container):
            # Sadece property'leri ve public attribute'ları kontrol et
            if (
                attr_name.endswith("_service") or attr_name.endswith("_repo")
            ) and not attr_name.startswith("_"):
                attr_value = getattr(container, attr_name)
                assert attr_value is not None, f"{attr_name} is None!"


# =============================================================================
# INTEGRATION SANITY CHECK
# =============================================================================


class TestContainerIntegration:
    """Container entegrasyon testleri."""

    def test_full_dependency_chain_works(self):
        """Tam bağımlılık zinciri çalışmalı."""
        from app.core.container import get_container

        container = get_container()

        # SeferService -> SeferRepo
        assert container.sefer_service.repo is container.sefer_repo

        # NOT: eskiden burada ImportService -> SeferService -> SeferRepo
        # zinciri doğrulanıyordu — ImportService sınıfı dalga 9'da kaldırıldı
        # (B.1 free-function refactor, v2.modules.import_excel); import_excel
        # artık container.sefer_service'e her çağrıda inline erişiyor,
        # kalıcı bir constructor-injection zinciri yok.

    def test_event_bus_consistency(self):
        """Tüm event-publishing servisler aynı bus'ı kullanmalı."""
        from app.core.container import get_container

        container = get_container()

        # Tüm servisler aynı event_bus instance'ını kullanmalı
        # (container.sofor_service kaldırıldı — dalga 5, B.1 free-function refactor)
        event_buses = [
            container.event_bus,
            container.sefer_service.event_bus,
        ]

        # Hepsi aynı instance olmalı
        first_bus = event_buses[0]
        for bus in event_buses[1:]:
            assert bus is first_bus


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
