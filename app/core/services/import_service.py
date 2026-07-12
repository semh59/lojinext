import io
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, cast

import pandas as pd
from fastapi import HTTPException, UploadFile
from sqlalchemy import text

from app.core.exceptions import ExcelExportError, ImportValidationError
from app.core.services.excel_parser import MAX_EXCEL_ROWS
from app.core.services.excel_service import ExcelService
from app.core.utils.sefer_status import SEFER_STATUS_PLANLANDI
from app.database.unit_of_work import UnitOfWork
from app.infrastructure.logging.logger import get_logger
from app.schemas.validators import PLAKA_PATTERN

logger = get_logger(__name__)


class ImportService:
    """Service handling bulk data imports and rollback mechanisms.

    TYPE: SINGLETON
    SCOPE: Application lifetime
    SINGLETON_REASON: İçe aktarma servisi — Excel parse ve toplu kayıt.
    CREATED_BY: app/core/container.py (lazy property)

    İMPORT MİMARİSİ (ARCH-002 — kasıtlı ayrım, merge ETME):
      * ``execute_import`` — admin generic bulk import (arac/surucu/sefer/yakit),
        import-job kaydı + ``inserted_ids`` ile satır-bazlı ``rollback_import``.
        Raw INSERT ... RETURNING id rollback için ZORUNLU; bu yüzden bulk_add_*
        ile değiştirilemez (id takibi kaybolur).
      * ``process_*_import`` (vehicle/driver/yakit) — domain endpoint'lerinin
        kullandığı Pydantic ``bulk_add_*`` yolu (job/rollback yok).
      * ``process_sefer_import`` — prod'da çağrılmıyor (test-covered legacy yol);
        sefer importu canlıda ``services/api/SeferImportService`` üzerinden yapılır.

    DURUM (status) sözleşmesi: tüm yollar canonical ``SEFER_STATUS_PLANLANDI``
    sabitini kullanır (literal KOPYALAMA yasak — BUG-002 bu drift'ten çıktı).
    """

    SUPPORTED_TYPES = ["arac", "surucu", "sefer", "yakit"]

    def __init__(
        self,
        sefer_service=None,
        yakit_service=None,
        arac_repo=None,
        sofor_repo=None,
        arac_service=None,
        sofor_service=None,
        dorse_repo=None,
        lokasyon_repo=None,
    ):
        self.sefer_service = sefer_service
        self._sefer_service = sefer_service
        self.yakit_service = yakit_service
        self._yakit_service = yakit_service
        self.arac_repo = arac_repo
        self._arac_repo = arac_repo
        self.sofor_repo = sofor_repo
        self._sofor_repo = sofor_repo
        self.arac_service = arac_service
        self._arac_service = arac_service
        self.sofor_service = sofor_service
        self._sofor_service = sofor_service
        self.dorse_repo = dorse_repo
        self._dorse_repo = dorse_repo
        self.lokasyon_repo = lokasyon_repo
        self._lokasyon_repo = lokasyon_repo
        self.guzergah_service = None
        self._guzergah_service = None
        self._route_service_lazy = None

    async def _report_infra_failure(self, source: str, exc: Exception) -> None:
        """Üst-seviye (parse/altyapı) hatalarını gerçek bir monitoring alarmına
        bağlar. Satır-bazlı hatalar zaten kendi iç `try/except`'lerinde
        `errors` listesine toplanıyor ve buraya hiç gelmiyor — bu handler'a
        düşen istisnalar (DB-down, beklenmedik bug vb.) önceden sessizce
        "Sistem hatası" string'ine çevrilip hiçbir alarm tetiklemiyordu
        (Tier B madde 13). Import'un `(count, errors)` dönüş sözleşmesini
        korumak için exception yutulmaya devam ediyor — sadece görünürlük
        ekleniyor."""
        logger.error("%s: beklenmeyen hata: %s", source, exc, exc_info=True)
        try:
            from app.infrastructure.monitoring import aemit
            from app.infrastructure.monitoring.models import (
                ErrorEvent,
                ErrorLayer,
                ErrorSeverity,
            )

            await aemit(
                ErrorEvent(
                    layer=ErrorLayer.SERVICE,
                    category="import_unexpected_error",
                    severity=ErrorSeverity.CRITICAL,
                    message=f"{source}: {type(exc).__name__}: {str(exc)[:300]}",
                )
            )
        except Exception:
            pass

    async def parse_and_preview(
        self, file: UploadFile, aktarim_tipi: str
    ) -> Dict[str, Any]:
        """Reads Excel/CSV file and provides a mapping preview without writing to DB."""
        if aktarim_tipi not in self.SUPPORTED_TYPES:
            raise HTTPException(
                status_code=400, detail=f"Desteklenmeyen aktarım tipi: {aktarim_tipi}"
            )

        content = await file.read()
        try:
            if file.filename.endswith(".csv"):
                df = pd.read_csv(io.BytesIO(content))
            else:
                df = pd.read_excel(io.BytesIO(content))
        except Exception as e:
            logger.error(f"Dosya okuma hatası: {e}")
            raise HTTPException(status_code=400, detail="Dosya formatı geçersiz.")

        if len(df) > MAX_EXCEL_ROWS:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"Dosya satır sayısı ({len(df)}) izin verilen üst sınırı "
                    f"({MAX_EXCEL_ROWS}) aşıyor. Dosyayı bölüp tekrar deneyin."
                ),
            )

        df = df.fillna("")
        headers = df.columns.tolist()
        total_rows = len(df)
        preview_data = df.head(5).to_dict(orient="records")

        return {
            "filename": file.filename,
            "aktarim_tipi": aktarim_tipi,
            "headers": headers,
            "total_rows": total_rows,
            "preview": preview_data,
        }

    async def _parse_import_file(
        self, filename: str, content: bytes
    ) -> List[Dict[str, Any]]:
        """Dosyayı türüne göre okur; pandas DataFrame'den sözlük listesi döner."""
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
        if len(df) > MAX_EXCEL_ROWS:
            raise ExcelExportError(
                f"Dosya satır sayısı ({len(df)}) izin verilen üst sınırı "
                f"({MAX_EXCEL_ROWS}) aşıyor. Dosyayı bölüp tekrar deneyin."
            )
        df = df.fillna("")
        return df.to_dict(orient="records")

    def _validate_import_rows(
        self,
        rows: List[Dict[str, Any]],
        aktarim_tipi: str,
        mapping: Dict[str, str],
        vehicles: List[Dict[str, Any]],
        drivers: List[Dict[str, Any]],
        trailers: List[Dict[str, Any]],
        routes: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
        """
        Her satırı doğrular ve gerekli alanları çözer.
        (geçerli_satırlar, hata_mesajları_dict) döner.
        Geçerli satırlar insert için hazır parametre dict'leri içerir.
        """
        valid: List[Dict[str, Any]] = []
        errors: Dict[str, str] = {}

        for index, row in enumerate(rows):
            try:
                if aktarim_tipi == "arac":
                    plaka = row.get(mapping.get("plaka", "plaka"))
                    if not plaka:
                        raise ImportValidationError(
                            ["Plaka alanı zorunludur."], row=index
                        )
                    valid.append({"_index": index, "plaka": plaka})

                elif aktarim_tipi == "surucu":
                    ad_soyad = row.get(mapping.get("ad_soyad", "ad_soyad"))
                    ehliyet_key = mapping.get("ehliyet_sinifi", "ehliyet_sinifi")
                    ehliyet_sinifi = row.get(ehliyet_key)
                    telefon = row.get(mapping.get("telefon", "telefon"))
                    valid.append(
                        {
                            "_index": index,
                            "ad_soyad": ad_soyad,
                            "ehliyet": ehliyet_sinifi,
                            "tel": telefon,
                        }
                    )

                elif aktarim_tipi == "sefer":
                    plaka = row.get(mapping.get("plaka", "plaka"))
                    sofor_ad = row.get(mapping.get("sofor_ad", "sofor_ad"))
                    dorse_plaka = row.get(mapping.get("dorse_plakasi", "dorse_plakasi"))
                    cikis_yeri = str(
                        row.get(mapping.get("cikis_yeri", "cikis_yeri")) or ""
                    ).strip()
                    varis_yeri = str(
                        row.get(mapping.get("varis_yeri", "varis_yeri")) or ""
                    ).strip()
                    tarih = _parse_date_flexible(row.get(mapping.get("tarih", "tarih")))
                    mesafe = self._validate_numeric(
                        row.get(mapping.get("mesafe_km", "mesafe_km"), 0), "Mesafe"
                    )
                    ton_raw = self._validate_numeric(
                        row.get(mapping.get("ton", "ton"), 0), "Yük"
                    )
                    # "Yük" kolonu kg cinsinden beklenir. 200'den küçük değer
                    # büyük ihtimalle ton cinsinden girilmiş (örn. 20 ton yerine
                    # 20000 kg yazılmalıydı). 1000 ile çarp ve uyar.
                    if 0 < ton_raw < 200:
                        logger.warning(
                            "Satır %d: Yük=%s küçük — ton olarak yorumlandı, "
                            "kg'a çevrildi (%s kg). Excel şablonuna kg giriniz.",
                            index,
                            ton_raw,
                            int(ton_raw * 1000),
                        )
                        net_kg = int(round(ton_raw * 1000))
                    else:
                        net_kg = int(round(ton_raw))
                    ton = round(net_kg / 1000.0, 2)

                    # Araç boş ağırlığını master listeden al → dolu = bos + net
                    arac_id = self._resolve_arac_id(plaka, vehicles)
                    bos_agirlik_kg = 0
                    if arac_id is not None:
                        _arac = next((v for v in vehicles if v["id"] == arac_id), None)
                        bos_agirlik_kg = (
                            int(_arac.get("bos_agirlik_kg") or 0) if _arac else 0
                        )
                    dolu_agirlik_kg = bos_agirlik_kg + net_kg

                    if not cikis_yeri or not varis_yeri:
                        raise ImportValidationError(
                            ["Çıkış veya varış yeri eksik"],
                            row=index,
                            reason="ROUTE_NOT_FOUND",
                        )

                    sofor_id = self._resolve_sofor_id(
                        str(sofor_ad or "").strip(), drivers
                    )
                    guzergah_id = self._resolve_route_id(cikis_yeri, varis_yeri, routes)

                    dorse_id = None
                    if dorse_plaka:
                        dorse_id = self._resolve_dorse_id(dorse_plaka, trailers)

                    valid.append(
                        {
                            "_index": index,
                            "arac_id": arac_id,
                            "sofor_id": sofor_id,
                            "dorse_id": dorse_id,
                            "guzergah_id": guzergah_id,
                            "tarih": tarih,
                            "mesafe": mesafe,
                            "net_kg": net_kg,
                            "ton": ton,
                            "bos_agirlik_kg": bos_agirlik_kg,
                            "dolu_agirlik_kg": dolu_agirlik_kg,
                            "cikis_yeri": cikis_yeri,
                            "varis_yeri": varis_yeri,
                        }
                    )

                elif aktarim_tipi == "yakit":
                    plaka = row.get(mapping.get("plaka", "plaka"))
                    tarih = _parse_date_flexible(row.get(mapping.get("tarih", "tarih")))
                    litre = self._validate_numeric(
                        row.get(mapping.get("litre", "litre"), 0), "Litre"
                    )
                    tutar = self._validate_numeric(
                        row.get(mapping.get("toplam_tutar", "toplam_tutar"), 0), "Tutar"
                    )
                    km = self._validate_numeric(
                        row.get(mapping.get("km_sayac", "km_sayac"), 0), "Kilometre"
                    )
                    arac_id = self._resolve_arac_id(plaka, vehicles)
                    valid.append(
                        {
                            "_index": index,
                            "arac_id": arac_id,
                            "tarih": tarih,
                            "litre": litre,
                            "tutar": tutar,
                            "km": km,
                        }
                    )

            except Exception as e:
                errors[str(index)] = str(e)

        return valid, errors

    async def execute_import(
        self, file: UploadFile, aktarim_tipi: str, user_id: int, mapping: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Executes the import against mapping inside a single transaction.
        Tracks inserted IDs to allow future rollbacks.
        """
        if aktarim_tipi not in self.SUPPORTED_TYPES:
            raise HTTPException(status_code=400, detail="Desteklenmeyen aktarım tipi.")

        content = await file.read()
        rows = await self._parse_import_file(file.filename, content)

        # Master listeleri UoW içinde çek — singleton repo'lar session
        # bağımlı, dışarıdan çağrılınca raw SQL crash.
        vehicles: List[Dict[str, Any]] = []
        drivers: List[Dict[str, Any]] = []
        trailers: List[Dict[str, Any]] = []
        routes: List[Dict[str, Any]] = []
        if aktarim_tipi in ("sefer", "yakit"):
            async with UnitOfWork() as uow_ref:
                vehicles = await uow_ref.arac_repo.get_all(sadece_aktif=False)
                if aktarim_tipi == "sefer":
                    drivers = await uow_ref.sofor_repo.get_all(sadece_aktif=False)
                    trailers = await uow_ref.dorse_repo.get_all(include_inactive=True)
                    routes = await uow_ref.lokasyon_repo.get_all(include_inactive=True)

        # API mapping: {excel_col: internal_key} (SafeColumnMapper / frontend yönü).
        # _validate_import_rows bunu {internal_key: excel_col} olarak bekler.
        inv_mapping = {v: k for k, v in mapping.items()}
        valid_rows, hatalar = self._validate_import_rows(
            rows, aktarim_tipi, inv_mapping, vehicles, drivers, trailers, routes
        )

        async with UnitOfWork() as uow:
            # 1. Kayıt Geçmişi Oluştur
            job_data = {
                "dosya_adi": file.filename,
                "aktarim_tipi": aktarim_tipi,
                "durum": "PROCESSING",
                "toplam_kayit": len(rows),
                "yukleyen_id": user_id,
            }
            job = await uow.import_repo.create_import_job(job_data)
            await uow.session.flush()  # Flush job id safely to memory, don't commit yet

            basarili = 0
            hatali = len(hatalar)
            inserted_ids = []

            # 2. DB Inserts for validated rows
            #
            # NOT (de-mock ile ortaya çıktı): raw INSERT'ler ilgili tablonun
            # NOT NULL + server_default'suz kolonlarını atlarsa prod'da NOT NULL
            # ihlali → import 500. sefer/surucu/yakit yolları teknik default'lar
            # (sefer: is_deleted/flat_distance_km; surucu: skorlar=1.0; yakit:
            # aktif/durum/depo + tutar/litre'den türetilen fiyat_tl) ile
            # düzeltildi. KALAN BİLİNEN SINIR — ``arac``: ``marka`` (NOT NULL)
            # import'ta TOPLANMIYOR; uydurma marka yazmak yanlış olur → mapping
            # genişletme / marka'yı nullable yapma ürün kararı bekliyor.
            for vrow in valid_rows:
                idx = vrow["_index"]
                # Her satır kendi SAVEPOINT'inde — başarısız bir satır (örn.
                # NOT NULL ihlali) yalnız kendini geri alır, tüm transaction'ı
                # abort ETMEZ. Aksi halde sonraki update_job_status
                # InFailedSQLTransactionError ile patlar → COMPLETED_WITH_ERRORS
                # durumu erişilemez + tek hatalı satır tüm import'u 500 yapar.
                savepoint = await uow.session.begin_nested()
                try:
                    if aktarim_tipi == "arac":
                        stmt = text(
                            "INSERT INTO araclar (plaka, aktif)"
                            " VALUES (:plaka, TRUE) RETURNING id"
                        )
                        result = await uow.session.execute(
                            stmt, {"plaka": vrow["plaka"]}
                        )
                        inserted_ids.append(result.scalar())
                        basarili += 1

                    elif aktarim_tipi == "surucu":
                        # score/manual_score/hiz_disiplin_skoru/
                        # agresif_surus_faktoru NOT NULL + server_default YOK
                        # (yalnız Python default=1.0). Raw INSERT atlarsa NOT
                        # NULL ihlali → tüm surucu import 500. Teknik default 1.0.
                        #
                        # Tier E madde 26: ad_soyad/telefon şifreli-at-rest;
                        # bu raw INSERT ORM TypeDecorator'ı atladığı için
                        # şifreleme + blind-index + trigram burada elle
                        # uygulanır (aksi halde ad_soyad_bidx UNIQUE NOT NULL
                        # ihlali ile import çöker).
                        from app.infrastructure.security.pii_encryption import (
                            blind_index,
                            encrypt_pii,
                            trigram_blind_indexes,
                        )

                        raw_ad_soyad = vrow["ad_soyad"]
                        raw_tel = vrow["tel"]
                        stmt = text(
                            "INSERT INTO soforler"
                            " (ad_soyad, ad_soyad_bidx, ehliyet_sinifi, telefon,"
                            "  aktif, score, manual_score, hiz_disiplin_skoru,"
                            "  agresif_surus_faktoru)"
                            " VALUES (:ad_soyad, :ad_soyad_bidx, :ehliyet, :tel,"
                            "  TRUE, 1.0, 1.0, 1.0, 1.0)"
                            " RETURNING id"
                        )
                        result = await uow.session.execute(
                            stmt,
                            {
                                "ad_soyad": encrypt_pii(raw_ad_soyad),
                                "ad_soyad_bidx": blind_index(raw_ad_soyad),
                                "ehliyet": vrow["ehliyet"],
                                "tel": encrypt_pii(raw_tel) if raw_tel else None,
                            },
                        )
                        new_sofor_id = result.scalar()
                        trigram_hashes = set(trigram_blind_indexes(raw_ad_soyad))
                        if trigram_hashes:
                            await uow.session.execute(
                                text(
                                    "INSERT INTO sofor_ad_soyad_trigram"
                                    " (sofor_id, trigram_hash)"
                                    " VALUES (:sofor_id, :trigram_hash)"
                                ),
                                [
                                    {"sofor_id": new_sofor_id, "trigram_hash": h}
                                    for h in trigram_hashes
                                ],
                            )
                        inserted_ids.append(new_sofor_id)
                        basarili += 1

                    elif aktarim_tipi == "sefer":
                        # is_deleted ve flat_distance_km NOT NULL + server_default
                        # YOK (yalnız Python-side default). Raw INSERT bunları
                        # atlarsa NOT NULL ihlali → transaction abort → tüm
                        # admin sefer import 500 verir. Teknik default'ları
                        # açıkça yaz.
                        stmt = text(
                            """
                            INSERT INTO seferler (
                                arac_id, sofor_id, dorse_id, guzergah_id,
                                tarih, mesafe_km, net_kg, ton,
                                bos_agirlik_kg, dolu_agirlik_kg,
                                cikis_yeri, varis_yeri, durum,
                                is_deleted, flat_distance_km
                            )
                            VALUES (
                                :arac_id, :sofor_id, :dorse_id, :guzergah_id,
                                :tarih, :mesafe, :net_kg, :ton,
                                :bos_agirlik_kg, :dolu_agirlik_kg,
                                :cikis_yeri, :varis_yeri, :durum,
                                FALSE, 0
                            )
                            RETURNING id
                            """
                        )
                        result = await uow.session.execute(
                            stmt,
                            {
                                "durum": SEFER_STATUS_PLANLANDI,
                                "arac_id": vrow["arac_id"],
                                "sofor_id": vrow["sofor_id"],
                                "dorse_id": vrow["dorse_id"],
                                "guzergah_id": vrow["guzergah_id"],
                                "tarih": vrow["tarih"],
                                "mesafe": vrow["mesafe"],
                                "net_kg": vrow["net_kg"],
                                "ton": vrow["ton"],
                                "bos_agirlik_kg": vrow["bos_agirlik_kg"],
                                "dolu_agirlik_kg": vrow["dolu_agirlik_kg"],
                                "cikis_yeri": vrow["cikis_yeri"],
                                "varis_yeri": vrow["varis_yeri"],
                            },
                        )
                        sefer_id = result.scalar()
                        inserted_ids.append(sefer_id)
                        basarili += 1

                        from app.infrastructure.events.event_bus import (
                            Event,
                            EventType,
                            get_event_bus,
                        )

                        await get_event_bus().publish_async(
                            Event(
                                type=EventType.SEFER_UPDATED,
                                data={"sefer_id": sefer_id, "trigger": "bulk_import"},
                            )
                        )

                    elif aktarim_tipi == "yakit":
                        # aktif/durum/depo_durumu NOT NULL (teknik default) +
                        # fiyat_tl NOT NULL ama toplanmıyor → tutar/litre'den
                        # türet. Hepsi atlanırsa NOT NULL ihlali → yakit import
                        # 500. fiyat_tl>0 constraint'i: litre/tutar 0 ise satır
                        # zaten hatalı (per-row except'e düşer).
                        _litre = vrow["litre"] or 0
                        _tutar = vrow["tutar"] or 0
                        fiyat_tl = round(_tutar / _litre, 2) if _litre else 0
                        stmt = text(
                            "INSERT INTO yakit_alimlari"
                            " (arac_id, tarih, litre, toplam_tutar, km_sayac,"
                            "  fiyat_tl, aktif, durum, depo_durumu)"
                            " VALUES (:arac_id, :tarih, :litre, :tutar, :km,"
                            "  :fiyat_tl, TRUE, 'Bekliyor', 'Bilinmiyor')"
                            " RETURNING id"
                        )
                        result = await uow.session.execute(
                            stmt,
                            {
                                "arac_id": vrow["arac_id"],
                                "tarih": vrow["tarih"],
                                "litre": vrow["litre"],
                                "tutar": vrow["tutar"],
                                "km": vrow["km"],
                                "fiyat_tl": fiyat_tl,
                            },
                        )
                        inserted_ids.append(result.scalar())
                        basarili += 1

                    await savepoint.commit()
                except Exception as e:
                    await savepoint.rollback()
                    hatali += 1
                    hatalar[str(idx)] = str(e)

            # 3. Güncelle
            await uow.import_repo.update_job_status(
                job.id,
                durum="COMPLETED" if hatali == 0 else "COMPLETED_WITH_ERRORS",
                basarili_kayit=basarili,
                hatali_kayit=hatali,
                islem_haritasi={"inserted_ids": inserted_ids},
                hatalar=hatalar,
            )

            await uow.commit()
            return {
                "job_id": job.id,
                "basarili": basarili,
                "hatali": hatali,
                "errors": hatalar,
            }

    async def rollback_import(self, job_id: int, user_id: int) -> bool:
        """
        Reverts a previous import by cascading deletions on the tracked IDs.
        """
        async with UnitOfWork() as uow:
            job = await uow.import_repo.get_by_id(job_id)
            if not job:
                raise HTTPException(
                    status_code=404, detail="Aktarım geçmişi bulunamadı."
                )

            if job.durum == "ROLLED_BACK":
                raise HTTPException(
                    status_code=400, detail="Bu aktarım zaten geri alındı."
                )

            if not job.islem_haritasi or "inserted_ids" not in job.islem_haritasi:
                raise HTTPException(
                    status_code=400, detail="Geri alınacak veri haritası yok."
                )

            inserted_ids = job.islem_haritasi["inserted_ids"]

            if not inserted_ids:
                return True  # Nothing to delete

            try:
                if job.aktarim_tipi == "arac":
                    stmt = text("DELETE FROM araclar WHERE id = ANY(:ids)")
                    await uow.session.execute(stmt, {"ids": inserted_ids})
                elif job.aktarim_tipi == "surucu":
                    stmt = text("DELETE FROM soforler WHERE id = ANY(:ids)")
                    await uow.session.execute(stmt, {"ids": inserted_ids})
                elif job.aktarim_tipi == "sefer":
                    stmt = text("DELETE FROM seferler WHERE id = ANY(:ids)")
                    await uow.session.execute(stmt, {"ids": inserted_ids})
                elif job.aktarim_tipi == "yakit":
                    stmt = text("DELETE FROM yakit_alimlari WHERE id = ANY(:ids)")
                    await uow.session.execute(stmt, {"ids": inserted_ids})

                await uow.import_repo.update_job_status(
                    job.id,
                    durum="ROLLED_BACK",
                    degisiklik_sebebi=f"Geri alındı, yetkili: {user_id}",
                )
                await uow.commit()
                return True
            except Exception as e:
                logger.error(f"Rollback hatası (Job {job_id}): {e}")
                raise HTTPException(
                    status_code=500,
                    detail="Rollback sırasında kritik veritabanı hatası oluştu.",
                )

    async def process_sefer_import(self, content: bytes) -> Tuple[int, list]:
        """Processes Excel import for trips (Seferler)."""
        try:
            items = await ExcelService.parse_sefer_excel(content)
            if not items:
                return 0, ["Excel dosyasında veri bulunamadı."]

            errors: List[object] = []
            sefer_list = []

            # Master listeleri UoW context'inde çek — singleton repo'da
            # session yok, raw SQL crash ediyor.
            async with UnitOfWork() as uow_ref:
                vehicles = await uow_ref.arac_repo.get_all(sadece_aktif=False)
                drivers = await uow_ref.sofor_repo.get_all(sadece_aktif=False)
                trailers = await uow_ref.dorse_repo.get_all(include_inactive=True)
                routes = await uow_ref.lokasyon_repo.get_all(include_inactive=True)

            for idx, item in enumerate(items, 1):
                try:
                    # Validate and Resolve
                    plaka = self._validate_plaka(item.get("plaka"))
                    arac_id = self._resolve_arac_id(plaka, vehicles)

                    name = self._validate_name(item.get("sofor_adi"))
                    sofor_id = self._resolve_sofor_id(name, drivers)

                    dorse_id = None
                    if item.get("dorse_plakasi"):
                        d_plaka = self._validate_plaka(item.get("dorse_plakasi"))
                        dorse_id = self._resolve_dorse_id(d_plaka, trailers)

                    cikis_yeri = str(item.get("cikis_yeri") or "").strip()
                    varis_yeri = str(item.get("varis_yeri") or "").strip()
                    guzergah_id = self._resolve_route_id(cikis_yeri, varis_yeri, routes)

                    # Create Sefer Data
                    sefer_data = {
                        "arac_id": arac_id,
                        "sofor_id": sofor_id,
                        "guzergah_id": guzergah_id,
                        "dorse_id": dorse_id,
                        "tarih": item.get("tarih"),
                        "baslangic_km": self._validate_numeric(
                            item.get("baslangic_km", 0), "Kilometre"
                        ),
                        "bitis_km": self._validate_numeric(
                            item.get("bitis_km", 0), "Kilometre"
                        ),
                        "mesafe_km": self._validate_numeric(
                            item.get("mesafe_km", 1.0), "Mesafe"
                        ),
                        "net_kg": self._validate_numeric(item.get("net_kg", 0), "Yük"),
                        "cikis_yeri": cikis_yeri or "Bilinmiyor",
                        "varis_yeri": varis_yeri or "Bilinmiyor",
                        "durum": SEFER_STATUS_PLANLANDI,
                    }
                    sefer_list.append(sefer_data)

                except ImportValidationError as ive:
                    # ImportValidationError carries reason code — map to field name
                    reason_code = ive.reason or ""
                    if reason_code in ("ARAC_NOT_FOUND", "INVALID_PLAKA"):
                        field = "plaka"
                    elif reason_code in ("SOFOR_NOT_FOUND", "INVALID_NAME"):
                        field = "sofor_adi"
                    elif reason_code == "ROUTE_NOT_FOUND":
                        field = "guzergah"
                    elif reason_code == "INVALID_NUMERIC":
                        field = "net_kg"
                    else:
                        field = "genel"
                    errors.append({"row": idx, "field": field, "reason": str(ive)})
                except ValueError as ve:
                    # Eski ValueError path (diğer servislerden gelebilir)
                    msg = str(ve)
                    field = "Bilinmiyor"
                    if "Plaka" in msg or "Araç" in msg:
                        field = "plaka"
                    elif "Sofor" in msg or "Şoför" in msg:
                        field = "sofor_adi"
                    elif "Guzergah" in msg:
                        field = "guzergah"
                    elif "ay" in msg or "Yük" in msg:
                        field = "net_kg"
                    errors.append({"row": idx, "field": field, "reason": msg})
                except Exception as e:
                    errors.append(
                        {
                            "row": idx,
                            "field": "genel",
                            "reason": f"Beklenmedik hata: {str(e)}",
                        }
                    )

            count = 0
            if sefer_list:
                # Delegate to SeferService for bulk processing
                count = await self.sefer_service.bulk_add_sefer(sefer_list)

            return count, errors

        except Exception as e:
            await self._report_infra_failure("process_sefer_import", e)
            return 0, [f"Sistem hatası: {str(e)}"]

    async def process_yakit_import(self, content: bytes) -> Tuple[int, list]:
        """Yakıt fişleri Excel import + otomatik periyot hesabı.

        Pipeline:
          1. Excel parse (tarih, plaka, litre, fiyat, km_sayac)
          2. Plaka → arac_id; bulunamayanlar errors[] satırına düşer
          3. bulk_add_yakit (Pydantic YakitCreate listesi)
          4. Etkilenen her arac için recalculate_vehicle_periods çağrılır
             (km aralıklarına göre tüketim periyotları hesaplanır)
        """
        from app.schemas.yakit import YakitCreate

        try:
            items = await ExcelService.parse_yakit_excel(content)
            if not items:
                return 0, ["Excel dosyasında veri bulunamadı."]

            errors: List[str] = []
            yakit_list: List[YakitCreate] = []
            affected_arac_ids: set[int] = set()
            async with UnitOfWork() as uow_ref:
                vehicles = await uow_ref.arac_repo.get_all(sadece_aktif=False)

            for idx, item in enumerate(items, 1):
                try:
                    # Plaka normalize: boşluk + büyük harf. Strict regex
                    # araç ekleme'de yapılır; yakıt fişinde araç zaten
                    # kayıtlı, sade normalize yeterli.
                    plaka_raw = item.get("plaka") or ""
                    plaka = str(plaka_raw).replace(" ", "").upper().strip()
                    if not plaka:
                        raise ValueError("Plaka boş.")

                    arac_id = self._resolve_arac_id(plaka, vehicles)
                    if not arac_id:
                        raise ValueError(
                            f"Araç bulunamadı: '{plaka}'. Önce araç kaydı gerekli."
                        )

                    tarih = item.get("tarih")
                    if tarih is None:
                        raise ValueError(
                            "Tarih boş — fişler için tarih sütunu zorunlu."
                        )

                    # depo_durumu None ise Pydantic Literal reddediyor —
                    # explicit default "Bilinmiyor".
                    depo_durumu = item.get("depo_durumu") or "Bilinmiyor"

                    yakit = YakitCreate(
                        arac_id=arac_id,
                        tarih=tarih,
                        istasyon=item.get("istasyon") or "Bilinmiyor",
                        litre=Decimal(
                            str(self._validate_numeric(item.get("litre", 0), "Litre"))
                        ),
                        fiyat_tl=Decimal(
                            str(
                                self._validate_numeric(item.get("fiyat_tl", 0), "Fiyat")
                            )
                        ),
                        toplam_tutar=None,  # backend hesaplar (YakitCreate'de Optional)
                        km_sayac=int(
                            self._validate_numeric(item.get("km_sayac", 0), "Kilometre")
                        ),
                        fis_no=(
                            str(item.get("fis_no")) if item.get("fis_no") else None
                        ),
                        depo_durumu=cast("Any", depo_durumu),
                        durum="Bekliyor",
                    )
                    yakit_list.append(yakit)
                    affected_arac_ids.add(arac_id)
                except ValueError as ve:
                    errors.append(f"Satır {idx}: {str(ve)}")
                except Exception as ex:  # Pydantic validation vs.
                    errors.append(f"Satır {idx}: {str(ex)}")

            count = 0
            if yakit_list:
                count = await self.yakit_service.bulk_add_yakit(yakit_list)

                # Periyot recalc — yakıt fişi km aralıklarından tüketim türetir.
                # YAKIT_ADDED event burada subscribe edilmiyor; bulk import'tan
                # sonra manuel çağrı tek seferde tetikleyici.
                try:
                    from app.core.services.period_calculation_service import (
                        get_period_calculation_service,
                    )

                    period_svc = get_period_calculation_service()
                    for arac_id in affected_arac_ids:
                        try:
                            await period_svc.recalculate_vehicle_periods(arac_id)
                        except Exception as pe:
                            logger.warning(
                                "Period recalc failed for arac %s: %s",
                                arac_id,
                                pe,
                            )
                except Exception as exc:
                    logger.warning("Period recalc skipped: %s", exc)

            return count, errors
        except Exception as e:
            await self._report_infra_failure("process_yakit_import", e)
            return 0, [f"Sistem hatası: {str(e)}"]

    async def process_vehicle_import(self, content: bytes) -> Tuple[int, list]:
        """Processes vehicle import."""
        try:
            items = await ExcelService.parse_vehicle_data(content)
            if not items:
                return 0, ["Excel dosyasında veri bulunamadı."]

            from app.schemas.arac import AracCreate

            errors: List[str] = []
            count = 0
            to_add: list[AracCreate] = []

            # Phase 1: read existing + reactivate in a short UoW.
            # Closed before bulk_add_arac opens its own UoW (avoid nested UoW).
            async with UnitOfWork() as uow:
                existing_vehicles = await uow.arac_repo.get_all(sadece_aktif=False)
                for idx, item in enumerate(items, 1):
                    try:
                        plaka = self._validate_plaka(item.get("plaka"))

                        existing = next(
                            (
                                v
                                for v in existing_vehicles
                                if v["plaka"].replace(" ", "").upper() == plaka
                            ),
                            None,
                        )
                        if existing:
                            if not existing.get("aktif", True):
                                await uow.arac_repo.update(existing["id"], aktif=True)
                                errors.append(
                                    f"Araç {plaka} zaten mevcuttu, aktifleştirildi."
                                )
                            continue

                        # Per-item Pydantic cast — bad rows become errors, batch continues.
                        try:
                            to_add.append(AracCreate(**item))
                        except Exception as cast_err:
                            errors.append(f"Satır {idx}: geçersiz alan — {cast_err}")

                    except ValueError as ve:
                        errors.append(f"Satır {idx}: {str(ve)}")
                await uow.commit()

            # Phase 2: create new vehicles in bulk_add_arac's own UoW.
            if to_add:
                count = await self.arac_service.bulk_add_arac(to_add)

            return count, errors
        except Exception as e:
            await self._report_infra_failure("process_vehicle_import", e)
            return 0, [f"Sistem hatası: {str(e)}"]

    async def process_driver_import(self, content: bytes) -> Tuple[int, list]:
        """Processes driver import."""
        try:
            items = await ExcelService.parse_driver_data(content)
            if not items:
                return 0, ["Excel dosyasında veri bulunamadı."]

            errors: List[str] = []
            count = await self.sofor_service.bulk_add_sofor(items)
            return count, errors
        except Exception as e:
            await self._report_infra_failure("process_driver_import", e)
            return 0, [f"Sistem hatası: {str(e)}"]

    async def import_routes(self, content: bytes) -> Tuple[int, list]:
        """Lokasyon/güzergah Excel'ini içe aktarır.

        Hedef: ``v2.modules.location.application.create_location`` — dict →
        ``LokasyonCreate`` Pydantic. Her satır kendi UoW'unda işlenir;
        container.lokasyon_repo singleton'ı (session'sız) raw SQL atınca
        crash ediyordu.
        """
        from v2.modules.location.application.create_location import create_location
        from v2.modules.location.domain.route_key import route_key
        from v2.modules.location.schemas import LokasyonCreate

        try:
            items = await ExcelService.parse_route_excel(content)
            if not items:
                return 0, ["Excel dosyası boş veya veri bulunamadı."]

            # N+1 önleme (Sentry LOJINEXT-17A): satır-başına ayrı get_by_route
            # SELECT'i atmak yerine mevcut tüm güzergahları TEK sorguyla
            # bellek-içi index'e çek; create_location bu index verildiğinde
            # kendi SELECT'ini atlar (aynı batch içi tekrarlar dahil,
            # index insert/reaktivasyon sonrası yerinde güncelleniyor).
            # route_key modül-seviyesinde serbest bir fonksiyon — testlerin
            # create_location'ı monkeypatch'lediği senaryolarda bile
            # (bkz. test_import_routes_valid) çağrılabilir kalması için.
            async with UnitOfWork() as index_uow:
                existing_rows = await index_uow.lokasyon_repo.get_all_route_keys()
            existing_index = {
                route_key(r["cikis_yeri"], r["varis_yeri"]): {
                    "id": r["id"],
                    "aktif": r["aktif"],
                }
                for r in existing_rows
            }

            errors: List[str] = []
            count = 0
            for idx, item in enumerate(items, 1):
                try:
                    payload = LokasyonCreate(**item)
                    async with UnitOfWork() as uow:
                        await create_location(
                            uow.lokasyon_repo, payload, existing_index=existing_index
                        )
                        await uow.commit()
                    count += 1
                except Exception as e:
                    errors.append(f"Satır {idx}: {str(e)}")
            return count, errors
        except Exception as e:
            await self._report_infra_failure("import_routes", e)
            return 0, [f"Sistem hatası: {str(e)}"]

    def _resolve_arac_id(
        self, plaka: Optional[str], vehicles: List[Dict[str, Any]]
    ) -> Optional[int]:
        if not plaka:
            return None
        search_p = plaka.replace(" ", "").upper()
        for v in vehicles:
            if v["plaka"].replace(" ", "").upper() == search_p:
                return v["id"]
        raise ImportValidationError(["Araç bulunamadı"], reason="ARAC_NOT_FOUND")

    def _resolve_sofor_id(
        self, name: Optional[str], drivers: List[Dict[str, Any]]
    ) -> int:
        if not name:
            raise ImportValidationError(["Şoför adı boş"], reason="SOFOR_NOT_FOUND")
        search_n = name.strip().upper()
        for d in drivers:
            if d["ad_soyad"].strip().upper() == search_n:
                return d["id"]
        raise ImportValidationError(
            [f"Şoför bulunamadı: {name}"], reason="SOFOR_NOT_FOUND"
        )

    def _resolve_route_id(
        self,
        cikis_yeri: Optional[str],
        varis_yeri: Optional[str],
        routes: List[Dict[str, Any]],
    ) -> int:
        cikis_norm = self._normalize_text(cikis_yeri)
        varis_norm = self._normalize_text(varis_yeri)
        if not cikis_norm or not varis_norm:
            raise ImportValidationError(
                ["Çıkış/varış yeri boş"], reason="ROUTE_NOT_FOUND"
            )

        for route in routes:
            route_cikis = self._normalize_text(route.get("cikis_yeri", ""))
            route_varis = self._normalize_text(route.get("varis_yeri", ""))
            if route_cikis == cikis_norm and route_varis == varis_norm:
                return route["id"]

        raise ImportValidationError(
            [f"Güzergah bulunamadı: {cikis_yeri} → {varis_yeri}"],
            reason="ROUTE_NOT_FOUND",
        )

    def _resolve_dorse_id(
        self, plaka: Optional[str], trailers: List[Dict[str, Any]]
    ) -> Optional[int]:
        if not plaka:
            return None
        search_p = plaka.replace(" ", "").upper()
        for t in trailers:
            if t["plaka"].replace(" ", "").upper() == search_p:
                return t["id"]
        return None

    def _validate_plaka(self, plaka: Any) -> str:
        if not plaka:
            raise ImportValidationError(["Plaka boş olamaz"], reason="INVALID_PLAKA")
        p = str(plaka).replace(" ", "").upper()
        if len(p) < 5:
            raise ImportValidationError(
                ["Plaka uzunluğu geçersiz"], reason="INVALID_PLAKA"
            )
        if not PLAKA_PATTERN.match(p):
            raise ImportValidationError(
                ["Plaka formatı geçersiz"], reason="INVALID_PLAKA"
            )
        return p

    def _validate_name(self, name: Any) -> str:
        if not name or len(str(name).strip()) < 2:
            raise ImportValidationError(
                ["İsim en az 2 karakter olmalı"], reason="INVALID_NAME"
            )
        return str(name).strip().title()

    def _validate_location(self, loc: Any) -> Any:
        return loc

    def _normalize_text(self, value: Any) -> str:
        s = str(value or "").strip().upper()
        # Türkçe büyük İ (U+0130) → ASCII I; karşılaştırma tutarlılığı için
        return s.replace("İ", "I")

    def _validate_numeric(self, val: Any, field: str) -> float:
        try:
            return float(val)
        except (ValueError, TypeError):
            raise ImportValidationError(
                [f"{field} sayı olmalı"], reason="INVALID_NUMERIC"
            )

    @property
    def route_service(self):
        """Lazy-loaded route service to avoid circular imports at module level."""
        if self._route_service_lazy is None:
            from v2.modules.route_simulation.application.get_route_details import (
                RouteService,
            )

            self._route_service_lazy = RouteService()
        return self._route_service_lazy


def _parse_date_flexible(val):
    """Helper to parse dates from various Excel formats."""
    from app.core.services.excel_service import _parse_date_flexible as pdf

    return pdf(val)


_import_service: Optional[ImportService] = None


def get_import_service() -> ImportService:
    """Thread-safe singleton getter — delegates to the DI container for full wiring."""
    from app.core.container import get_container

    return get_container().import_service
