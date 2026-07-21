from datetime import date

import pytest
from sqlalchemy import text

from v2.modules.trip.schemas import SeferCreate


class TestDetailedScenarios:
    """
    Kapsamlı Senaryo Testleri:
    1. Raporlama (Pasif Veri)
    2. Atomic Transactions
    3. Sefer Mantığı
    4. İlişkisel Bütünlük (FK)
    """

    @pytest.mark.asyncio
    async def test_reporting_scenario_passive_driver(
        self, db_session, report_repos, sefer_service
    ):
        """SENARYO 1: Pasif şoförlerin raporlarda görünmesi"""
        from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

        async with UnitOfWork() as uow:
            # 1. Şoför oluştur
            sofor_model = await uow.sofor_repo.add(
                ad_soyad="Pasif Şoför",
                telefon="555",
                ise_baslama=date(2023, 1, 1),
                ehliyet_sinifi="E",
            )
            sofor_id = sofor_model.id if hasattr(sofor_model, "id") else sofor_model

            # 2. Araç oluştur
            arac_model = await uow.arac_repo.add(
                plaka="34 PAS 99", marka="Test", model="Model", yil=2023
            )
            arac_id = arac_model.id if hasattr(arac_model, "id") else arac_model

            # 3. Güzergah/Lokasyon oluştur
            from sqlalchemy import text

            await uow.session.execute(
                text(
                    "INSERT INTO lokasyonlar (cikis_yeri, varis_yeri, mesafe_km, zorluk, flat_distance_km, aktif, is_corrected) VALUES ('Ankara', 'İstanbul', 450, 'Normal', 0, true, false)"  # noqa: E501
                )
            )
            guz_id = 1
            await uow.commit()

        # 3. Seferler ekle (Bu şoför 2 sefer yapsın)
        # SeferService.add_sefer kullanıyoruz (Validasyonlar için)
        await sefer_service.add_sefer(
            SeferCreate(
                tarih=date(2023, 1, 1),
                arac_id=arac_id,
                sofor_id=sofor_id,
                guzergah_id=guz_id,
                mesafe_km=100,
                net_kg=25000,
                cikis_yeri="Ankara",
                varis_yeri="İstanbul",
            )
        )
        await sefer_service.add_sefer(
            SeferCreate(
                tarih=date(2023, 1, 2),
                arac_id=arac_id,
                sofor_id=sofor_id,
                guzergah_id=guz_id,
                mesafe_km=100,
                net_kg=25000,
                cikis_yeri="İstanbul",
                varis_yeri="Ankara",
            )
        )

        # 4. Şoförü PASİF yap ve doğrula
        from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

        async with UnitOfWork() as uow:
            await uow.sofor_repo.delete(sofor_id)  # Bu soft delete yapar (aktif=0)
            await uow.commit()

            sofor = await uow.sofor_repo.get_by_id(sofor_id, include_inactive=True)
            assert sofor["aktif"] == 0

        # 6. RAPOR SORGUSU (ReportService üzerinden)
        # generate_driver_report son 30 günü alır, o yüzden tarihleri yakın seçelim veya days parametresini artıralım
        # Senaryo gereği 2023 Ocak verilerini istiyoruz.
        # generate_driver_report default 30 gün geriye gider.
        days_diff = (date.today() - date(2023, 1, 1)).days + 1
        async with UnitOfWork():
            # NOT: burada eskiden container'ın repo'larına session enjekte
            # ediliyordu — provası yoktu, generate_driver_report zaten
            # `report_repos` fixture'ının kendi (db_session'a bağlı, container'dan
            # tamamen bağımsız) repo'larını kullanıyor. Dalga 17 denetiminde
            # bu satırların no-op olduğu doğrulandı (bkz.
            # TASKS/modules/platform-infra.md madde 0), kaldırıldı.
            from v2.modules.reports.application.generate_driver_report import (
                generate_driver_report,
            )

            stats = await generate_driver_report(report_repos, sofor_id, days=days_diff)

        # 7. Sonuçları doğrula
        assert stats is not None
        assert stats["sofor"]["ad_soyad"] == "Pasif Şoför"
        # generate_driver_report içindeki değerlendirme (evaluate_driver)
        # şoförün seferlerini bulmalı (aktif=0 olsa bile)
        assert stats["degerlendirme"] is not None
        # Bazı alanları kontrol edelim
        assert stats["degerlendirme"]["toplam_sefer"] >= 2

    @pytest.mark.asyncio
    async def test_atomic_transaction_fail(self, db_session):
        """SENARYO 2: Atomik İşlem (Rollback) Testi"""
        # 1. Başlangıç durumu
        result = await db_session.execute(text("SELECT COUNT(*) FROM araclar"))
        count = result.scalar()

        try:
            # db_session zaten bir transaction içinde olabilir pytest-asyncio ile,
            # ama açıkça bir savepoint (nested) yaratarak rollback'i zorlayalım.
            async with db_session.begin_nested():
                # 1. Başarılı insert
                await db_session.execute(
                    text(
                        "INSERT INTO araclar (plaka, marka, model, yil) VALUES ('34 OK 01', 'Test', 'X', 2020)"
                    )
                )
                # 2. İkinci insert
                await db_session.execute(
                    text(
                        "INSERT INTO araclar (plaka, marka, model, yil) VALUES ('34 OK 02', 'Test', 'X', 2020)"
                    )
                )
                # 3. KASITLI HATA (Constraint Violation - Aynı plaka)
                await db_session.execute(
                    text(
                        "INSERT INTO araclar (plaka, marka, model, yil) VALUES ('34 OK 01', 'Test', 'X', 2020)"
                    )
                )
                await db_session.flush()
        except Exception:
            # Hata yakalandı, nested transaction rollback oldu
            pass

        # Kontrol: DB'de HİÇBİR kayıt eklenmemiş olmalı (eski sayı korunmalı)
        result = await db_session.execute(text("SELECT COUNT(*) FROM araclar"))
        final_count = result.scalar()
        assert final_count == count

    @pytest.mark.asyncio
    async def test_sefer_service_logic(self, sefer_service):
        """SENARYO 3: Sefer Servisi Mantığı (Validasyon & Boş Dönüş)"""
        from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

        async with UnitOfWork() as uow:
            sofor_model = await uow.sofor_repo.add(
                ad_soyad="Seferci", telefon="555", ise_baslama=date(2023, 1, 1)
            )
            sofor_id = sofor_model.id if hasattr(sofor_model, "id") else sofor_model

            arac_model = await uow.arac_repo.add(
                plaka="06 SEF 01", marka="Test", model="Model", yil=2023
            )
            arac_id = arac_model.id if hasattr(arac_model, "id") else arac_model

            # 3. Güzergah/Lokasyon oluştur
            from sqlalchemy import text

            await uow.session.execute(
                text(
                    "INSERT INTO lokasyonlar (cikis_yeri, varis_yeri, mesafe_km, zorluk, flat_distance_km, aktif, is_corrected) VALUES ('Ankara', 'İstanbul', 450, 'Normal', 0, true, false)"  # noqa: E501
                )
            )
            guz_id = 1
            await uow.commit()

        # 1. Hatalı Sefer (Negatif mesafe) - Pydantic validasyonu
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SeferCreate(
                tarih=date.today(),
                arac_id=arac_id,
                sofor_id=sofor_id,
                guzergah_id=guz_id,
                cikis_yeri="CikisYeri",
                varis_yeri="VarisYeri",
                mesafe_km=-50,
                net_kg=1000,
            )

        # 2. Başarılı Sefer + Boş Dönüş
        valid_sefer = SeferCreate(
            tarih=date.today(),
            arac_id=arac_id,
            sofor_id=sofor_id,
            guzergah_id=guz_id,
            cikis_yeri="Ankara",
            varis_yeri="İstanbul",
            mesafe_km=450,
            net_kg=20000,
            bos_sefer=True,
        )

        sid = await sefer_service.add_sefer(valid_sefer)
        async with UnitOfWork() as uow:
            saved = await uow.sefer_repo.get_by_id(sid)
            assert saved["bos_sefer"] is True or saved["bos_sefer"] == 1

    @pytest.mark.asyncio
    async def test_foreign_key_integrity(self, db_session):
        """SENARYO 4: Foreign Key Bütünlüğü — PostgreSQL enforces FK constraints natively."""
        from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork

        async with UnitOfWork() as uow:
            arac_model = await uow.arac_repo.add(
                plaka="34 FK 01", marka="Test", model="X", yil=2022
            )
            arac_id = arac_model.id if hasattr(arac_model, "id") else arac_model

            sofor_model = await uow.sofor_repo.add(
                ad_soyad="Test",
                telefon="555",
                ise_baslama=date(2020, 1, 1),
                ehliyet_sinifi="E",
            )
            sofor_id = sofor_model.id if hasattr(sofor_model, "id") else sofor_model

            await uow.sefer_repo.add(
                tarih=date(2023, 1, 1),
                arac_id=arac_id,
                sofor_id=sofor_id,
                mesafe_km=100,
                bos_agirlik_kg=10000,
                dolu_agirlik_kg=11000,
                net_kg=1000,
                cikis_yeri="A",
                varis_yeri="B",
            )
            await uow.commit()

        # Aracı silmeye çalış (Hard Delete simülasyonu - FK hatası vermeli)
        from sqlalchemy.exc import IntegrityError

        # SQLite'da FK hatasını tetiklemek için flush() veya commit() lazım
        with pytest.raises(IntegrityError):
            async with db_session.begin_nested():
                await db_session.execute(
                    text("DELETE FROM araclar WHERE id = :id"), {"id": arac_id}
                )
                await db_session.flush()
