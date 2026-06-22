import json
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from app.database.base_repository import BaseRepository
from app.database.models import AdminAuditLog, Kullanici, SeferLog


class AuditRepository(BaseRepository[AdminAuditLog]):
    """
    Data access for audit/timeline records.
    """

    model = AdminAuditLog

    @staticmethod
    def _safe_parse_json(raw_value: Optional[str]) -> Dict[str, Any]:
        if not raw_value:
            return {}
        try:
            parsed = json.loads(raw_value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _normalize_event_type(islem_tipi: str, changes: List[Dict[str, Any]]) -> str:
        if islem_tipi == "INSERT":
            return "CREATE"
        if islem_tipi == "DELETE":
            return "DELETE"

        changed_fields = {change["alan"] for change in changes}
        if "durum" in changed_fields:
            return "STATUS_CHANGE"
        if "tahmini_tuketim" in changed_fields or "tahmin_meta" in changed_fields:
            return "PREDICTION_REFRESH"
        if {"tuketim", "dagitilan_yakit", "periyot_id"} & changed_fields:
            return "RECONCILIATION"
        return "UPDATE"

    @staticmethod
    def _build_summary(
        tip: str, old_data: Dict[str, Any], new_data: Dict[str, Any]
    ) -> str:
        if tip == "CREATE":
            return "Sefer kaydi olusturuldu."
        if tip == "DELETE":
            return "Sefer kaydi silindi."
        if tip == "STATUS_CHANGE":
            return (
                f"Durum degisti: {old_data.get('durum', '-')}"
                f" -> {new_data.get('durum', '-')}"
            )
        if tip == "PREDICTION_REFRESH":
            return "Yakit tahmini yenilendi."
        if tip == "RECONCILIATION":
            return "Gerceklesme/tahmin uzlastirma verileri guncellendi."
        return "Sefer kaydi guncellendi."

    @staticmethod
    def _extract_changes(
        old_data: Dict[str, Any], new_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        ignored = {"updated_at", "created_at"}
        changed: List[Dict[str, Any]] = []
        keys = set(old_data.keys()) | set(new_data.keys())
        for key in sorted(keys):
            if key in ignored:
                continue
            old_value = old_data.get(key)
            new_value = new_data.get(key)
            if old_value != new_value:
                changed.append(
                    {
                        "alan": key,
                        "eski": old_value,
                        "yeni": new_value,
                    }
                )
        return changed

    @staticmethod
    def _extract_prediction_block(
        old_data: Dict[str, Any], new_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        if (
            "tahmini_tuketim" not in new_data
            and "tahmin_meta" not in new_data
            and "tahmini_tuketim" not in old_data
            and "tahmin_meta" not in old_data
        ):
            return None
        return {
            "onceki_tahmini_tuketim": old_data.get("tahmini_tuketim"),
            "tahmini_tuketim": new_data.get("tahmini_tuketim"),
            "tahmin_meta": new_data.get("tahmin_meta"),
        }

    async def get_sefer_timeline(self, sefer_id: int) -> List[Dict[str, Any]]:
        """
        Fetch normalized timeline entries for a specific trip from seferler_log.
        """
        stmt = (
            select(SeferLog)
            .where(SeferLog.sefer_id == sefer_id)
            .order_by(SeferLog.created_at.asc())
        )
        result = await self.session.execute(stmt)
        logs = list(result.scalars().all())
        if not logs:
            return []

        user_ids = sorted({log.degistiren_id for log in logs if log.degistiren_id})
        user_map: Dict[int, str] = {}
        if user_ids:
            user_stmt = select(Kullanici).where(Kullanici.id.in_(user_ids))
            user_result = await self.session.execute(user_stmt)
            users = user_result.scalars().all()
            for user in users:
                name = getattr(user, "ad_soyad", None) or getattr(user, "email", None)
                user_map[user.id] = name or "Sistem"

        timeline: List[Dict[str, Any]] = []
        for log in logs:
            old_data = self._safe_parse_json(log.eski_deger)
            new_data = self._safe_parse_json(log.yeni_deger)

            if log.islem_tipi == "INSERT":
                changes = self._extract_changes({}, new_data)
            elif log.islem_tipi == "DELETE":
                changes = self._extract_changes(old_data, {})
            else:
                changes = self._extract_changes(old_data, new_data)

            tip = self._normalize_event_type(log.islem_tipi, changes)
            has_prediction_change = any(
                change["alan"] in {"tahmini_tuketim", "tahmin_meta"}
                for change in changes
            )
            prediction_block = (
                self._extract_prediction_block(old_data, new_data)
                if has_prediction_change
                else None
            )

            timeline.append(
                {
                    "id": log.id,
                    "zaman": log.created_at,
                    "tip": tip,
                    "ozet": self._build_summary(tip, old_data, new_data),
                    "kullanici": user_map.get(log.degistiren_id, "Sistem"),
                    "changes": changes,
                    "prediction": prediction_block,
                    "technical_details": {
                        "islem_tipi": log.islem_tipi,
                        "degisen_alan_sayisi": len(changes),
                    },
                }
            )

        return timeline
