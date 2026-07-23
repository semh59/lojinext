"""Admin generic bulk import — import-job kaydı + ``inserted_ids`` ile
satır-bazlı ``rollback_import``'a (bkz. rollback_import.py) izin veren
raw-INSERT akışı.

İMPORT MİMARİSİ (ARCH-002 — kasıtlı ayrım, merge ETME): bu dosyanın
``execute_import``'u admin generic bulk import (arac/surucu/sefer/yakit),
job/rollback zorunlu. Domain-özel ``process_*_import`` (bkz. kardeş
dosyalar) Pydantic ``bulk_add_*`` yolu (job/rollback yok) — farklı akış.

**TEK UoW BLOĞU BÖLÜNMEZ**: ``async with UnitOfWork() as uow`` bloğu
``create_import_job`` + ``session.flush()`` (job id, commit YOK) + raw
INSERT'ler + ``inserted_ids`` takibini TEK atomik birim olarak tutar —
``rollback_import``'un kontratı budur.
"""

from typing import Any, Dict, List

from fastapi import HTTPException, UploadFile
from sqlalchemy import text

from v2.modules.import_excel.application.preview_import import parse_import_file
from v2.modules.import_excel.domain.constants import SUPPORTED_TYPES
from v2.modules.import_excel.domain.row_validators import validate_import_rows
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork
from v2.modules.trip.public import SEFER_STATUS_PLANLANDI


async def execute_import(
    file: UploadFile, aktarim_tipi: str, user_id: int, mapping: Dict[str, str]
) -> Dict[str, Any]:
    """
    Executes the import against mapping inside a single transaction.
    Tracks inserted IDs to allow future rollbacks.
    """
    if aktarim_tipi not in SUPPORTED_TYPES:
        raise HTTPException(status_code=400, detail="Desteklenmeyen aktarım tipi.")

    content = await file.read()
    rows = await parse_import_file(file.filename, content)

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
    # validate_import_rows bunu {internal_key: excel_col} olarak bekler.
    inv_mapping = {v: k for k, v in mapping.items()}
    valid_rows, hatalar = validate_import_rows(
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
                    result = await uow.session.execute(stmt, {"plaka": vrow["plaka"]})
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
                    from v2.modules.platform_infra.public import (
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

                    from v2.modules.platform_infra.public import (
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
