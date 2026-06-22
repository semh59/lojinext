from typing import Dict, Tuple


class RouteValidator:
    """
    Guzergah verisi dogrulama ve duzeltme servisi.
    Anormal verileri tespit eder ve makul sinirlara ceker.
    """

    # Maksimum egim (grade) limitleri
    MAX_HIGHWAY_GRADE = 0.06  # %6
    MAX_TRUCK_ROUTE_GRADE = 0.08  # %8

    @staticmethod
    def _get_grade_thresholds(distance_km: float) -> Tuple[float, float]:
        """
        Return a suspicious cumulative-grade threshold and correction cap.

        Short regional routes can legitimately accumulate more climbing than
        long-haul motorway routes, so the allowed threshold narrows as route
        distance grows.
        """
        if distance_km < 50:
            threshold = 0.025
        elif distance_km < 150:
            threshold = 0.015
        elif distance_km < 400:
            threshold = 0.010
        else:
            threshold = 0.007
        return threshold, threshold * 1.5

    @staticmethod
    def validate_and_correct(route_data: Dict) -> Dict:
        """
        Rota verisini analiz et ve gerekirse duzelt.

        Returns:
            Duzeltilmis route_data. Girdi mutate edilmez.
        """
        data = route_data.copy()

        dist_km = (
            data.get("distance_km") or data.get("mesafe_km") or data.get("mesafe") or 0
        )
        ascent = data.get("ascent_m") or 0
        descent = data.get("descent_m") or 0

        if dist_km <= 0:
            return data

        is_corrected = False
        reasons = []
        threshold, cap = RouteValidator._get_grade_thresholds(dist_km)

        avg_incline = ascent / (dist_km * 1000)
        if avg_incline > threshold:
            ascent = round(dist_km * 1000 * cap, 1)
            is_corrected = True
            reasons.append(f"High Incline ({avg_incline:.1%})")

        avg_decline = descent / (dist_km * 1000)
        if avg_decline > threshold:
            descent = round(dist_km * 1000 * cap, 1)
            is_corrected = True
            reasons.append(f"High Decline ({avg_decline:.1%})")

        data["is_corrected"] = is_corrected
        if is_corrected:
            data["ascent_m"] = ascent
            data["descent_m"] = descent
            data["correction_reason"] = " | ".join(reasons)

        return data
