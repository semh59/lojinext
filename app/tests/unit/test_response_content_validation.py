"""
Response içerik doğrulama pattern örnekleri.
Bu testler mock kullanır; gerçek DB testleri integration/ altında.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from v2.modules.fleet.schemas import AracCreate


class TestCRUDResponseContent:
    """CRUD endpoint response içeriklerini doğrula."""

    async def test_create_vehicle_returns_id_and_data(self):
        """Araç oluşturma: id > 0 ve doğru veri dönmeli."""
        from v2.modules.fleet.api import vehicle_routes as v_mod

        # Gelen payload
        arac_data = AracCreate(
            plaka="34 ABC 123",
            marka="Mercedes",
            model="Actros",
            yil=2020,
            tank_kapasitesi=600,
            hedef_tuketim=32.0,
        )

        # create_vehicle use-case → yeni ID döner
        mock_create_vehicle = AsyncMock(return_value=42)

        # uow.arac_repo.get_by_id → oluşturulan kaydı döner
        expected_record = {
            "id": 42,
            "plaka": "34 ABC 123",
            "marka": "Mercedes",
            "model": "Actros",
            "yil": 2020,
            "tank_kapasitesi": 600,
            "hedef_tuketim": 32.0,
            "aktif": True,
            "toplam_km": 0.0,
            "toplam_sefer": 0,
            "ort_tuketim": 0.0,
        }
        mock_uow = AsyncMock()
        mock_uow.arac_repo.get_by_id = AsyncMock(return_value=expected_record)

        mock_admin = MagicMock()
        mock_admin.email = "admin@test.com"

        with patch.object(v_mod, "create_vehicle", mock_create_vehicle):
            result = await v_mod.create_arac(
                arac=arac_data,
                uow=mock_uow,
                current_admin=mock_admin,
            )

        # ID gerçek bir pozitif tamsayı olmalı
        assert result["id"] == 42, "Dönen ID, use-case'in atadığı ID ile eşleşmeli"
        assert result["id"] > 0, "ID pozitif olmalı"

        # Plaka ve marka doğru dönmeli
        assert result["plaka"] == "34 ABC 123"
        assert result["marka"] == "Mercedes"

        # create_vehicle tam doğru argümanlarla çağrılmalı
        mock_create_vehicle.assert_awaited_once_with(arac_data, uow=mock_uow)

    async def test_list_vehicles_returns_list_with_items(self):
        """Araç listesi: içerik ve count doğrulanmalı."""
        from v2.modules.fleet.api import vehicle_routes as v_mod

        mock_items = [
            {"id": 1, "plaka": "06 TT 001", "marka": "Volvo"},
            {"id": 2, "plaka": "34 BB 002", "marka": "Scania"},
        ]

        mock_get_all_paged = AsyncMock(return_value={"items": mock_items, "total": 2})

        mock_db = MagicMock()
        mock_user = MagicMock()

        with patch.object(v_mod, "get_all_vehicles_paged", mock_get_all_paged):
            result = await v_mod.read_araclar(
                db=mock_db,
                current_user=mock_user,
                skip=0,
                limit=100,
                aktif_only=True,
                search=None,
                marka=None,
                model=None,
                min_yil=None,
                max_yil=None,
            )

        # Dönen yapı StandardResponse olmalı; data listesi içermeli
        assert result.data == mock_items, "data alanı mock items ile eşleşmeli"
        assert result.meta.count == 2, "meta.count doğru adet göstermeli"
        assert result.meta.total == 2, "meta.total kullanım-durumu toplamını yansıtmalı"
        assert result.meta.offset == 0
        assert result.meta.limit == 100

        # get_all_vehicles_paged doğru parametrelerle çağrılmalı
        mock_get_all_paged.assert_awaited_once_with(
            skip=0,
            limit=100,
            aktif_only=True,
            search=None,
            marka=None,
            model=None,
            min_yil=None,
            max_yil=None,
        )

    async def test_list_vehicles_empty_result(self):
        """Araç listesi boşsa count=0 ve data=[] dönmeli."""
        from v2.modules.fleet.api import vehicle_routes as v_mod

        mock_get_all_paged = AsyncMock(return_value={"items": [], "total": 0})

        with patch.object(v_mod, "get_all_vehicles_paged", mock_get_all_paged):
            result = await v_mod.read_araclar(
                db=MagicMock(),
                current_user=MagicMock(),
                skip=0,
                limit=100,
                aktif_only=True,
                search=None,
                marka=None,
                model=None,
                min_yil=None,
                max_yil=None,
            )

        assert result.data == []
        assert result.meta.count == 0
        assert result.meta.total == 0


class TestFileDownloadContent:
    """Dosya indirme endpoint'lerinin içeriğini doğrula."""

    async def test_excel_export_content_type_and_bytes(self):
        """Excel export: XLSX magic bytes ve gerçek bytes."""
        from app.core.services.excel_service import ExcelService

        data = [{"test": "veri", "deger": 42}]
        result = await ExcelService.export_data(data, type="generic")

        assert isinstance(result, bytes)
        assert len(result) > 100, "coroutine değil gerçek bytes döndürülmeli"
        # XLSX = ZIP container — ilk 4 byte PK\x03\x04
        assert result[:4] == b"PK\x03\x04", "XLSX (ZIP) magic bytes eksik"

    def test_pdf_magic_bytes_pattern(self):
        """PDF generator gerçek PDF bytes döndürmeli."""
        from app.core.services.report_generator import PDFReportGenerator

        gen = PDFReportGenerator()
        result = gen.generate_driver_comparison(
            [{"ad_soyad": "Ali Yılmaz", "trips": 5, "consumption": 28.5, "score": 85.0}]
        )
        assert isinstance(result, bytes), "Sonuç bytes olmalı"
        assert result[:4] == b"%PDF", "Geçerli PDF magic bytes eksik"
        assert len(result) > 100, "PDF içeriği boş olamaz"

    async def test_excel_template_is_valid_xlsx(self):
        """Excel şablonu geçerli XLSX formatında olmalı."""
        from app.core.services.excel_service import ExcelService

        result = await ExcelService.generate_template("arac")

        assert isinstance(result, bytes)
        assert len(result) > 100, "Şablon boş olamaz"
        assert result[:4] == b"PK\x03\x04", "Şablon XLSX (ZIP) magic bytes içermeli"
