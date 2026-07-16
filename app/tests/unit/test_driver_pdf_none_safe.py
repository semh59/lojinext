def test_generate_driver_comparison_with_all_none_values():
    """Tüm alanları None olan şoför verisi ile PDF oluşturulabilmeli."""
    from v2.modules.reports.infrastructure.pdf_export import PDFReportGenerator

    gen = PDFReportGenerator()
    driver_data = [
        {
            "ad_soyad": None,
            "trips": None,
            "consumption": None,
            "score": None,
        }
    ]
    result = gen.generate_driver_comparison(driver_data)
    assert isinstance(result, bytes)
    assert result[:4] == b"%PDF"


def test_generate_driver_comparison_with_partial_none():
    """Bazı alanlar None, bazıları gerçek değer."""
    from v2.modules.reports.infrastructure.pdf_export import PDFReportGenerator

    gen = PDFReportGenerator()
    driver_data = [
        {"ad_soyad": "Ali", "trips": 5, "consumption": None, "score": 72.5},
        {"ad_soyad": None, "trips": None, "consumption": 31.2, "score": None},
    ]
    result = gen.generate_driver_comparison(driver_data)
    assert isinstance(result, bytes)
    assert result[:4] == b"%PDF"


def test_generate_driver_comparison_empty_list():
    """Boş liste — exception değil PDF dönmeli."""
    from v2.modules.reports.infrastructure.pdf_export import PDFReportGenerator

    gen = PDFReportGenerator()
    result = gen.generate_driver_comparison([])
    assert isinstance(result, bytes)
    assert result[:4] == b"%PDF"
