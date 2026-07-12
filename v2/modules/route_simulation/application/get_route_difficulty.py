"""Use-case: classify a route's difficulty from its grade profile."""


def get_route_difficulty(ascent: float, descent: float, distance_km: float) -> str:
    """Calculate route difficulty from grade profile."""
    if distance_km == 0:
        return "Bilinmiyor"

    gradient_factor = (ascent / (distance_km * 1000)) * 100
    if gradient_factor < 0.5:
        return "Düz"
    if gradient_factor < 1.5:
        return "Hafif Eğimli"
    return "Dik/Dağlık"


__all__ = ["get_route_difficulty"]
