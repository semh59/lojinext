"""Toplu sefer ekleme (Excel import'un tükettiği ana use-case).

KRİTİK İNVARYANT — bölünmez: ``net_kg`` CHECK enforcement'ı
(``arac_bos_map`` prefetch → ``dolu=max(dolu,bos)`` → ``net=dolu-bos``
sırası) `arac_bos_map`/`route_map`/`active_arac`/`sofor` setleri ve
`seen_sefer_nos` dedup ile birlikte TEK blokta taşındı — task dosyası
madde 5.3'ün açık kararı.
"""

from datetime import date
from typing import Any, Dict, List

from app.infrastructure.audit import audit_log
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.monitoring.service_probe import monitor_errors
from v2.modules.shared_kernel.infrastructure.unit_of_work import UnitOfWork
from v2.modules.trip.application.stats_refresh import refresh_stats
from v2.modules.trip.application.trip_prediction_enrichment import (
    PREDICTION_TIMEOUT_SECONDS,
    build_prediction_quality_flags,
    build_prediction_route_analysis,
    extract_prediction_values,
)
from v2.modules.trip.domain.trip_validation import safe_durum
from v2.modules.trip.schemas import SeferCreate

logger = get_logger(__name__)


@monitor_errors(category="sefer_write", severity="error")
@audit_log("BULK_CREATE", "sefer", log_params=True)
async def bulk_add_sefer(sefer_list: List[SeferCreate]) -> int:
    """Toplu sefer ekle (Batch Insert & Smart Enrichment)"""
    if not sefer_list:
        return 0

    count = 0
    from v2.modules.prediction_ml.public import get_prediction_service

    pred_service = get_prediction_service()

    async with UnitOfWork() as uow:
        try:
            # 1. Pre-fetch Logic
            sorted_list = sorted(sefer_list, key=lambda x: (x.tarih, x.saat or ""))
            all_loc_names = await uow.lokasyon_repo.get_benzersiz_lokasyonlar()

            # Araç boş ağırlığı pre-fetch — check constraint
            # ``net_kg = dolu_agirlik_kg - bos_agirlik_kg`` zorunluluğunda
            # tek SeferCreate'in tek tek arac master sorgusu yerine batch.
            arac_ids = {s.arac_id for s in sorted_list if s.arac_id}
            arac_bos_map: Dict[int, float] = {}
            active_arac_ids: set[int] = set()
            if arac_ids:
                araclar = await uow.arac_repo.get_all(sadece_aktif=False)
                for a in araclar:
                    if a["id"] in arac_ids:
                        arac_bos_map[a["id"]] = float(a.get("bos_agirlik_kg") or 0)
                        if a.get("aktif"):
                            active_arac_ids.add(a["id"])

            # N+1 optimization: pre-fetch all arac/sofor objects before prediction loop
            # predict_consumption opens new UoW for each call; batch loading here reduces queries
            arac_objs = await uow.arac_repo.get_by_ids(list(arac_ids))
            sofor_ids = {s.sofor_id for s in sorted_list if s.sofor_id}
            sofor_objs = await uow.sofor_repo.get_by_ids(list(sofor_ids))

            # Active sofor set for validation
            active_sofor_ids: set[int] = set()
            if sofor_ids:
                soforler = await uow.sofor_repo.get_all(sadece_aktif=False)
                for sf in soforler:
                    if sf["id"] in sofor_ids and sf.get("aktif"):
                        active_sofor_ids.add(sf["id"])

            # sefer_no uniqueness: within-batch dedup + existing DB check
            batch_sefer_nos = {s.sefer_no for s in sorted_list if s.sefer_no}
            existing_sefer_nos: set[str] = await uow.sefer_repo.get_existing_sefer_nos(
                list(batch_sefer_nos)
            )
            seen_sefer_nos: set[str] = set()  # within-batch dedup

            all_routes = await uow.lokasyon_repo.get_all(limit=1000)
            route_map = {
                (
                    r["cikis_yeri"].upper().strip(),
                    r["varis_yeri"].upper().strip(),
                ): r
                for r in all_routes
            }

            items_to_add: List[Dict[str, Any]] = []

            for data in sorted_list:
                if data.mesafe_km <= 0:
                    continue

                # Arac aktif kontrolü
                if data.arac_id and data.arac_id not in active_arac_ids:
                    logger.warning(
                        "bulk_add_sefer: arac_id=%s aktif değil, satır atlandı",
                        data.arac_id,
                    )
                    continue

                # Sofor aktif kontrolü (sofor_id opsiyonel)
                if data.sofor_id and data.sofor_id not in active_sofor_ids:
                    logger.warning(
                        "bulk_add_sefer: sofor_id=%s aktif değil, satır atlandı",
                        data.sofor_id,
                    )
                    continue

                # sefer_no tekrar kontrolü
                if data.sefer_no:
                    if data.sefer_no in existing_sefer_nos:
                        logger.warning(
                            "bulk_add_sefer: sefer_no=%s zaten DB'de var, atlandı",
                            data.sefer_no,
                        )
                        continue
                    if data.sefer_no in seen_sefer_nos:
                        logger.warning(
                            "bulk_add_sefer: sefer_no=%s batch içinde tekrar, atlandı",
                            data.sefer_no,
                        )
                        continue
                    seen_sefer_nos.add(data.sefer_no)

                matched_cikis = await uow.lokasyon_repo.find_closest_match(
                    data.cikis_yeri, pre_fetched_names=all_loc_names
                )
                if matched_cikis:
                    data.cikis_yeri = matched_cikis

                matched_varis = await uow.lokasyon_repo.find_closest_match(
                    data.varis_yeri, pre_fetched_names=all_loc_names
                )
                if matched_varis:
                    data.varis_yeri = matched_varis

                if data.cikis_yeri.lower() == data.varis_yeri.lower():
                    continue

                route_key = (
                    data.cikis_yeri.upper().strip(),
                    data.varis_yeri.upper().strip(),
                )
                route_metadata = route_map.get(route_key)

                if route_metadata:
                    if not data.ascent_m:
                        data.ascent_m = route_metadata.get("ascent_m", 0.0)
                    if not data.descent_m:
                        data.descent_m = route_metadata.get("descent_m", 0.0)
                    if not data.flat_distance_km:
                        data.flat_distance_km = route_metadata.get(
                            "flat_distance_km", 0.0
                        )
                    if not data.guzergah_id:
                        data.guzergah_id = route_metadata.get("id")

                # Bulk ML prediction: her sefer için predict_consumption
                # 5 fresh DB fetch yapıyor (araclar, soforler,
                # arac_bakimlari, sofor stat, AVG tuketim) → N+1 pattern.
                # 20+ sefer'lik batch'te DB sorgu sayısı 5N'e çıkıyor.
                # Geçmiş veri import'unda gerçek tüketim zaten kayıtlı,
                # prediction değer katmaz; tek tek sefer create
                # (POST /trips/) yolunda ise predict_consumption hala
                # çalışır. Threshold 20: detector eşiğinden hemen önce.
                tahmini_tuk = None
                tahmin_meta = None
                skip_prediction = len(sefer_list) > 20
                if skip_prediction:
                    logger.info(
                        "bulk_add_sefer: batch size %d > 20, ML prediction skipped for all rows",
                        len(sefer_list),
                    )
                if not skip_prediction:
                    import asyncio as _asyncio

                    try:
                        tonaj = data.ton or (
                            data.net_kg / 1000.0 if data.net_kg else 0.0
                        )
                        prediction = await _asyncio.wait_for(
                            pred_service.predict_consumption(
                                arac_id=data.arac_id,
                                mesafe_km=data.mesafe_km,
                                ton=tonaj,
                                ascent_m=data.ascent_m or 0.0,
                                descent_m=data.descent_m or 0.0,
                                flat_distance_km=data.flat_distance_km or 0.0,
                                sofor_id=data.sofor_id,
                                dorse_id=data.dorse_id,
                                target_date=data.tarih
                                if isinstance(data.tarih, date)
                                else date.fromisoformat(data.tarih),
                                route_analysis=build_prediction_route_analysis(
                                    route_details=route_metadata
                                ),
                                _arac_obj=arac_objs.get(data.arac_id),
                                _sofor_obj=sofor_objs.get(data.sofor_id)
                                if data.sofor_id
                                else None,
                            ),
                            timeout=PREDICTION_TIMEOUT_SECONDS,
                        )
                        tahmini_tuk, tahmin_meta = extract_prediction_values(
                            prediction,
                            quality_flags=build_prediction_quality_flags(
                                route_details=route_metadata
                            ),
                        )
                    except _asyncio.TimeoutError:
                        logger.debug(
                            "Bulk prediction timeout (arac=%s) skipped",
                            data.arac_id,
                        )
                    except Exception as pe:
                        logger.error(f"Bulk Prediction Error: {pe}")

                # Ağırlık enrichment — DB check constraint:
                # ``net_kg = dolu_agirlik_kg - bos_agirlik_kg``. Excel'den
                # gelen SeferCreate sadece ``net_kg`` taşıyor; bos/dolu
                # boş kalırsa constraint patlar. Arac master'dan bos al,
                # dolu = bos + net.
                bos_kg = float(
                    data.bos_agirlik_kg or arac_bos_map.get(data.arac_id, 0) or 0
                )
                net_kg = float(data.net_kg or 0)
                dolu_kg = float(data.dolu_agirlik_kg or (bos_kg + net_kg))
                # CHECK: net_kg = dolu_agirlik_kg - bos_agirlik_kg.
                # Clamp dolu first so dolu >= bos, then derive net exactly.
                dolu_kg = max(dolu_kg, bos_kg)
                net_kg = dolu_kg - bos_kg

                items_to_add.append(
                    {
                        "tarih": data.tarih,
                        "saat": data.saat or "",
                        "arac_id": data.arac_id,
                        "dorse_id": data.dorse_id,
                        "sofor_id": data.sofor_id,
                        "guzergah_id": data.guzergah_id,
                        "net_kg": net_kg,
                        "ton": data.ton or round(net_kg / 1000, 2),
                        "bos_agirlik_kg": bos_kg,
                        "dolu_agirlik_kg": dolu_kg,
                        "cikis_yeri": data.cikis_yeri,
                        "varis_yeri": data.varis_yeri,
                        "mesafe_km": data.mesafe_km,
                        "bos_sefer": data.bos_sefer,
                        "ascent_m": data.ascent_m or 0.0,
                        "descent_m": data.descent_m or 0.0,
                        "flat_distance_km": data.flat_distance_km or 0.0,
                        "tahmini_tuketim": tahmini_tuk,
                        "tahmin_meta": tahmin_meta,
                        "durum": safe_durum(data.durum),
                        "notlar": data.notlar,
                        "sefer_no": data.sefer_no,
                    }
                )

            if items_to_add:
                await uow.sefer_repo.bulk_create(items_to_add)
                count = len(items_to_add)
                await uow.commit()
                await refresh_stats(uow)

        except Exception as e:
            logger.error(f"Bulk insert hatası (Sefer): {e}")
            await uow.rollback()
            raise e

    return count
