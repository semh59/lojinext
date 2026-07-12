"""Pure text-normalization helpers for location/route matching.

No I/O — safe to unit-test without a database.
"""


def route_key(cikis: str, varis: str) -> tuple[str, str]:
    """SQL tarafındaki ``LokasyonRepository.get_by_route`` neutralize_sql
    mantığıyla eşdeğer Python-side normalizasyon (dict key üretimi için).

    Modül seviyesinde serbest fonksiyon (sınıf metodu DEĞİL) — çünkü
    ``ImportService`` bunu doğrudan çağırabilmeli (bulk import path).

    Sıra önemli: önce Türkçe İ/ı katlama, SONRA lower() — aksi halde
    Python'un str.lower()'ı 'İ'yi (U+0130) 'i' + birleşik nokta (U+0307)
    olarak ayrıştırır (bkz. ``normalize_turkish_title`` içindeki aynı bug
    notu). Bu sıra ile o ayrışma hiç oluşmaz.
    """
    return (
        cikis.strip().replace("İ", "i").replace("ı", "i").lower(),
        varis.strip().replace("İ", "i").replace("ı", "i").lower(),
    )


def normalize_turkish_title(s: str) -> str:
    """Turkish-aware title case: 'i' → 'İ' (not 'I') at word start.

    Normalize names to prevent duplicates (e.g., Istanbul vs İstanbul).

    BUG (found via 0-mock epiği real-DB test): str.lower() decomposes
    'İ' (U+0130) into 'i' + a combining dot above (U+0307) — that stray
    combining mark then leaked into w[1:], corrupting every word
    starting with capital İ (e.g. "İstanbul" -> "İ̇stanbul",
    double-dotted). Neutralize İ to plain 'i' BEFORE lower() so the
    decomposition never happens.
    """
    return " ".join(
        ("İ" if w[0] == "i" else "I" if w[0] == "ı" else w[0].upper()) + w[1:].lower()
        for w in s.strip().replace("İ", "i").lower().split()
        if w
    )
