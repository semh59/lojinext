import sys
import unittest
from pathlib import Path

import pytest

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.core.container import Container, get_container


class TestNoModuleLevelContainerImport:
    def test_sefer_import_service_has_no_module_level_container_import(self):
        """sefer_import_service.py modül seviyesinde get_container import etmemeli."""
        import ast
        import importlib
        import inspect

        mod = importlib.import_module(
            "v2.modules.import_excel.application.sefer_upload_importer"
        )
        source = inspect.getsource(mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "app.core.container":
                if hasattr(node, "lineno") and node.lineno <= 20:
                    pytest.fail(
                        f"sefer_upload_importer.py satır {node.lineno}'de "
                        "modül seviyesinde container import bulundu"
                    )

    def test_get_container_returns_same_instance(self):
        """get_container() her çağrıda aynı instance döndürmeli."""
        c1 = get_container()
        c2 = get_container()
        assert c1 is c2


class TestContainerLazyLoading:
    def test_get_container_returns_same_instance(self):
        """get_container() her çağrıda aynı instance döndürmeli (singleton)."""
        c1 = get_container()
        c2 = get_container()
        assert c1 is c2

    def test_container_has_all_expected_singleton_categories(self):
        """Container property'leri beklenen kategorileri içermeli."""
        container = get_container()
        # ML/AI Subsystem
        assert hasattr(container, "prediction_service")
        assert hasattr(container, "anomaly_detector")
        assert hasattr(container, "time_series_service")
        # Infrastructure
        assert hasattr(container, "event_bus")
        assert hasattr(container, "health_service")
        # Repos
        assert hasattr(container, "arac_repo")
        assert hasattr(container, "sefer_repo")

    def test_no_module_level_container_import_in_endpoint_services(self):
        """Endpoint servisleri modül seviyesinde container import etmemeli."""
        import ast
        import importlib
        import inspect

        # Bilinen kritik servis — diğerleri deferred kullanıyor
        mod = importlib.import_module(
            "v2.modules.import_excel.application.sefer_upload_importer"
        )
        source = inspect.getsource(mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "app.core.container":
                if hasattr(node, "lineno") and node.lineno <= 20:
                    pytest.fail(
                        f"sefer_upload_importer.py satır {node.lineno}'de "
                        "modül seviyesinde container import var"
                    )


class TestContainer(unittest.TestCase):
    def test_container_initialization(self):
        """Container should initialize all services with dependencies"""
        container = get_container()

        self.assertIsInstance(container, Container)

        # Check Repos
        self.assertIsNotNone(container.arac_repo)
        self.assertIsNotNone(container.sefer_repo)
        self.assertIsNotNone(container.sofor_repo)
        self.assertIsNotNone(container.yakit_repo)

        # Check Services
        self.assertIsNotNone(container.sefer_service)
        self.assertIsNotNone(container.analiz_service)
        self.assertIsNotNone(container.report_service)
        # NOT: container.import_service YOK — ImportService sınıfı B.1
        # free-function geçişinde kaldırıldı (dalga 9), import_excel modülü
        # artık container'a değil v2.modules.import_excel.public'e bağlı.

        # Check Injection (White-box testing)
        self.assertEqual(container.sefer_service.repo, container.sefer_repo)

        # Analiz Service Injection
        self.assertEqual(container.analiz_service.yakit_repo, container.yakit_repo)
        self.assertEqual(container.analiz_service.sefer_repo, container.sefer_repo)


if __name__ == "__main__":
    unittest.main()
